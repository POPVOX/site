from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.forms import ValidationError
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import cache_control
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache

from popvox.models import *
from popvox.govtrack import statelist, statenames, CURRENT_CONGRESS, getMemberOfCongress

from widgets import do_not_track_compliance
from bills import save_user_comment
from utils import require_lock, csrf_protect_if_logged_in, cache_page_postkeyed

from registration.helpers import validate_email, validate_password
from emailverification.utils import send_email_verification

from jquery.ajax import json_response, validation_error_message, ajax_fieldupdate_request

from settings import DEBUG, SITE_ROOT_URL, MIXPANEL_TOKEN, MIXPANEL_API_KEY

import urlparse
import json
import re
import random, math
from itertools import chain
from base64 import urlsafe_b64decode

@csrf_protect_if_logged_in
def widget_config(request):
	# Collect all of the ServiceAccounts that the user has access to.
	
	return render_to_response('popvox/services_widget_config.html', {
		'accounts': request.user.userprofile.service_accounts(create=True) if request.user.is_authenticated() else [],
		
		'issueareas': IssueArea.objects.filter(parent__isnull=True),
		"states": statelist,
		"current_congress": CURRENT_CONGRESS,
		
		"MIXPANEL_API_KEY": MIXPANEL_API_KEY
		}, context_instance=RequestContext(request))

@csrf_protect
@json_response
@ajax_fieldupdate_request
@login_required
def service_account_set_option(request, field, value, validate_only):
	acct = request.user.userprofile.service_accounts().filter(id=request.POST["account"])
	if len(acct) == 0:
		raise Http404()
	acct = acct[0]
	
	if field == "fb_page_code":
		if validate_only:
			return { "status": "success" }
		acct.setopt("fb_page_code", value)
		return { "status": "success" }
	else:
		raise Exception("Bad request: Invalid field.")

def validate_widget_request(request, api_key):
	if not api_key:
		return (None, []) # no permissions

	# Validate the key
	try:
		account = ServiceAccount.objects.get(api_key=api_key)
	except ServiceAccount.DoesNotExist:
		return "Invalid API key."

	perms = [p.name for p in account.permissions.all()]

	# Validate the referrer header.
	try:
		host = urlparse.urlparse(request.META["HTTP_REFERER"]).hostname.lower()
		if host.startswith("www."):
			host = host[4:]
	except:
		return "You have disabled the HTTP Referrer Header in your web browser, your web browser sent an invalid value, or you visited the widget iframe URL directly. Enable the HTTP Referrer Header to access this content if it has been disabled."

	if request.META["REQUEST_METHOD"] == "POST":
		# We trust post requests with a proper referrer header.
		# We *should* be sending a CSRF token but because we want to cache
		# the widget HTML we don't. 
		if host == "popvox.com" or host.endswith(".popvox.com"):
			return (account, perms)
		else:
			return "POST referrer check failed."

	# Allow the referrer to be us so we can show a preview on our site.
	if host == "popvox.com" or host.endswith(".popvox.com"):
		return (account, perms) # widget preview

	# Get the permitted referring hostnames.
	permitted_hosts = [s.strip().lower() for s in account.hosts.split("\n") if s.strip() != ""]
	
	if len(permitted_hosts) == 0 and account.org != None and account.org.website != "":
		# the default host is the domain of the org's configured website
		website_hostname = urlparse.urlparse(account.org.website).hostname
		if website_hostname.startswith("www."):
			website_hostname = website_hostname[4:]
		permitted_hosts = [website_hostname]
	
	salsa = account.getopt("salsa", {})
	if "node" in salsa:
		permitted_hosts.append(salsa["node"])

	# Validate the referrer.
	# For now, if the permitted hosts list is empty, allow all hosts.
	if host in permitted_hosts or len(permitted_hosts) == 0:
		return (account, perms)

	return "This widget has been placed on a website (%s) that is not authorized." % host

def widget_render(request, widgettype, api_key=None):
	account_permissions = validate_widget_request(request, api_key)
	if type(account_permissions) == str:
		return HttpResponseForbidden(account_permissions)
	account, permissions = account_permissions
	
	if widgettype == "commentstream":
		return widget_render_commentstream(request, account, permissions)
	if widgettype == "writecongress":
		# remember: needs session state
		return widget_render_writecongress(request, account, permissions)

	raise Http404()

@do_not_track_compliance
def widget_render_commentstream(request, account, permissions):
	comments = UserComment.objects.filter(message__isnull=False, status__in=(UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED)).order_by("-created")
	
	title1 = "Recent Comments from"
	title2 = "POPVOX Nation to Congress"

	show_bill_number = True
	url = None
	
	if "state" in request.GET:
		comments = comments.filter(state=request.GET["state"])
		title1 = "Comments Sent to Congress"
		title2 = "from " + statenames[request.GET["state"]]
		#url = SITE_ROOT_URL + "/activity#state=" + request.GET["state"]

	cx = []
	
	if "bills" in request.GET:
		for b in request.GET["bills"].split(","):
			position = None
			if b.endswith(":supporting"):
				position = "+"
				b = b[0:-len(":supporting")]
			if b.endswith(":opposing"):
				position = "-"
				b = b[0:-len(":opposing")]
			try:
				b = bill_from_url("/bills/" + b)
				
				if not position:
					cx.append(comments.filter(bill=b))
				else:
					cx.append(comments.filter(bill=b, position=position))
			except:
				# invalid bill
				title1 = "Comments sent to Congress"
				title2 = "Invalid bill number: " + b
			
		if len(cx) == 1: # the bills have to be processed first
			show_bill_number = False
			title1 = "Comments sent to Congress"
			title2 = b.title
			url = SITE_ROOT_URL + b.url()

	if "issue" in request.GET:
		ix = IssueArea.objects.get(id=request.GET["issue"])
		cx.append(comments.filter(bill__topterm=ix))
		title1 = "Comments sent to Congress"
		title2 = ix.name
		#url = SITE_ROOT_URL + ix.url()

	if len(cx) > 0:
		comments = cx[0]
		for c in cx[1:]:
			comments |= c
				
	comments = comments[0:50]
	
	return render_to_response('popvox/widgets/commentstream.html', {
		'title1': title1,
		'title2': title2,
		'comments': comments,
		"show_bill_number": show_bill_number,
		"url": url,
		"permissions": permissions,
		}, context_instance=RequestContext(request))


@csrf_protect_if_logged_in
def widget_render_writecongress(request, account, permissions):
	if request.META["REQUEST_METHOD"] == "GET":
		# Get bill, position, org, orgcampaignposition, and reason.
		campaign = None # indicates where to save user response data for the org to get
		org = None
		reason = None
		
		if "ocp" not in request.GET:
			if not "bill" in request.GET:
				return HttpResponseBadRequest("Invalid URL.")
			try:
				bill = bill_from_url("/bills/" + request.GET["bill"])
			except:
				return HttpResponseBadRequest("No bill with that number exists.")
			position_verb = request.GET.get("position", "")
			if position_verb == "support":
				position = "+"
			elif position_verb == "oppose":
				position = "-"
			else:
				position = None
				
		else:
			# ocp argument specifies the OrgCampaignPosition, which has all of the
			# information we need.
			try:
				ocp = OrgCampaignPosition.objects.get(id=request.GET["ocp"], campaign__visible=True, campaign__org__visible=True)
			except OrgCampaignPosition.DoesNotExist:
				return HttpResponseBadRequest("The campaign for the bill has become hidden or the widget URL is invalid")
			bill = ocp.bill
			position = ocp.position
			if position == "0": position = None
			if account != None and ocp.campaign.org == account.org:
				# We'll let the caller use an OCP id to get the bill and position, but
				# don't tie this request to the org if the request is not under a
				# verified api_key for that org.
				org = ocp.campaign.org
				reason = ocp.comment
			
		if account != None:
			campaign, is_new = ServiceAccountCampaign.objects.get_or_create(
				account = account,
				bill = bill,
				position = position if position != None else "0")
			
		if not bill.isAlive():
			return HttpResponseBadRequest("This letter-writing widget has been turned off because the bill is no longer open for comments.")
			
		# Get the user, but null out of the user is not allowed to comment so he can log in
		# as someone else.
		u = request.user
		if not request.user.is_authenticated():
			u = None
			
		# these checks are repeated below when checking emails
		elif u.userprofile.is_org_admin() or u.userprofile.is_leg_staff():
			u = None
		elif not u.postaladdress_set.all().exists():
			u = None
		elif u.comments.filter(bill=bill).exists():
			u = None
		
		displayname = None
		if u != None:
			displayname = u.username
			try:
				pa = u.postaladdress_set.all().order_by("-created")[0]
				displayname = pa.firstname + " " + pa.lastname #+ " (" + u.username + ")"
			except:
				pass
		
		# get the target URL for the share function, which can be overridden
		# in the url GET parameter, or it comes from the HTTP referrer, or
		# else it falls back to a long form URL for the bill.
		url = request.GET.get("url",
			request.META.get("HTTP_REFERER",
				SITE_ROOT_URL + bill.url()))
		
		# compute up to two suggestions for further action
		suggestions = {
			"+": ["support", "These bills also need your support", []],
			"-": ["oppose", "These bills also need your opposition", []],
			"0": ["neutral", "You may be interested in weighing in on these bills", []] }
		if org == None:
			# compute by bill similarity
			other_bills = [bs for bs in
				chain(( (s.bill2, s.similarity) for s in bill.similar_bills_one.all().select_related("bill2")), ( (s.bill1, s.similarity) for s in bill.similar_bills_two.all().select_related("bill1")))
				if bs[0].isAlive() and bs[0].id != bill.id]
			other_bills.sort(key = lambda bs : -bs[1])
			other_bills = [bs[0] for bs in other_bills[0:2]]
			suggestions["0"][2] = other_bills
		else:
			for p in OrgCampaignPosition.objects.filter(campaign__org=org, campaign__visible=True).exclude(bill=bill):
				if len(suggestions[p.position][2]) < 2 and p.bill.isAlive():
					suggestions[p.position][2].append(p.bill)
			if len(suggestions["+"][2]) + len(suggestions["-"][2]) >= 2:
				suggestions["0"] = []
		
		# user_info encoded json object passed from Facebook integration.
		user_info = {}
		if request.GET.get("user_info", "").strip() != "":
			user_info = json.loads(urlsafe_b64decode(request.GET["user_info"].encode("ascii").replace(".", "=")))
		
		# Render.
		response = render_to_response('popvox/widgets/writecongress.html', {
			"permissions": permissions,
			"displayname": displayname,
			"identity": None if u == None else json.dumps(widget_render_writecongress_get_identity(request.user)),
			
			"campaign": campaign,
			"reason": reason,
			"bill": bill,
			"position": position,
			"url": url,
			
			"suggestions": suggestions.values(),
			
			"user_info": user_info, 
			
			"useraddress_prefixes": PostalAddress.PREFIXES,
			"useraddress_suffixes": PostalAddress.SUFFIXES,
			
			"MIXPANEL_TOKEN": MIXPANEL_TOKEN,
			}, context_instance=RequestContext(request))
	else:
		response = widget_render_writecongress_action(request, account, permissions)

	# add a P3P compact policy so that IE will accept third-party cookies.
	# apparently the actual policy doesn't matter as long as one is sent,
	# but we're setting the following policy;
	#  access: ident-contact
	#  purpose: current, admin, develop, tailoring, individual-analysis, individual-decision, contact
	#  recipient: ours, same (i.e. Congress), public
	#  retention: business-practices
	#  data: (none)
	response["P3P"] = 'CP="IDC CUR ADM DEV TAI IVA IVD CON OUR SAM PUB BUS"'

	return response


@json_response
def widget_render_writecongress_action(request, account, permissions):
	from settings import BENCHMARKING
	
	def meta_log(meta):
		ret = {}
		for k in ('HTTP_REFERER', 'HTTP_HOST', 'PATH_INFO', 'HTTP_ORIGIN', 'HTTP_USER_AGENT', 'HTTP_COOKIE', 'REMOTE_ADDR'):
			ret[k] = meta.get(k, None)
		return repr(ret)
			
	
	########################################
	if request.POST["action"] == "check-email":
		try:
			email = validate_email(request.POST["email"], for_login=True)
		except ValidationError:
			return { "status": "invalid-email" }
		
		try:
			u = User.objects.get(email = email)
		except User.DoesNotExist:
			return { "status": "not-registered" }
			
		# these checks are repeated above when checking the logged in user
		if u.userprofile.is_org_admin() or u.userprofile.is_leg_staff():
			return { "status": "staff-cant-do-this" }
		if not u.postaladdress_set.all().exists():
			return { "status": "not-registered" } # if the user is registered but has no address info, pretend they are not registered
		if u.comments.filter(bill=request.POST["bill"]).exists():
			return { "status": "already-commented" } # TODO: Privacy??

		# In order to do single-sign-on login, we have to redirect away from the widget
		# and then come back. This messes up the referer header in Chrome, making
		# API key validation problematic, and also messs up cookies set by XHR if
		# third-party cookies are disabled (tested in Chrome). With third-party cookies
		# enabled, we could pass a simple cookie forward instructing us to trust the
		# API key once the user returns, since the referrer header will be junked. However
		# with third-party cookies disabled, it doesn't work (at least if we set the cookie
		# in XHR) and also Google login itself doesn't work. (Facebook login does work
		# but the cookie problem remains.)
		# 
		# I don't see a way to reliably do single sign on (we can't tell if third-party cookies
		# are enabled), so it is hereby disabled.
		
		#sso = u.singlesignon.all()

		if not u.has_usable_password(): # and sso.count() == 0:
			# no way to log in!
			return { "status": "not-registered" }

		return {
			"status": "registered",
			"has_password": u.has_usable_password(),
			"sso_methods": [], #[s.provider for s in sso],
			}
			
	########################################
	if request.POST["action"] == "newuser":
		try:
			# although this should be for new users only (and then we would take out for_login=True),
			# we also force any registered user who doesn't have an address record to go this route
			email = validate_email(request.POST["email"], for_login=True)
		except ValidationError as e:
			return { "status": "fail", "msg": validation_error_message(e) }
			
		from writeyourrep.district_lookup import get_state_for_zipcode
		
		identity = {
			"email": email,
			"firstname": request.POST["firstname"].strip(),
			"lastname": request.POST["lastname"].strip(),
			"state": get_state_for_zipcode(request.POST["zipcode"].strip()),
			"zipcode": request.POST["zipcode"].strip(),
			}
		if not re.search("[A-Za-z]", identity["firstname"]): return { "status": "fail", "msg": "Enter your first name." }
		if not re.search("[A-Za-z]", identity["lastname"]): return { "status": "fail", "msg": "Enter your last name." }
		if identity["state"] == None: return { "status": "fail", "msg": "That's not a ZIP code within a U.S. congressional district. Please enter the ZIP code where you vote." } 
		
		# if user is logged in, log him out; but not in demo mode to not destroy people's logins
		if "demo" not in request.POST:
			logout(request)
		
		# Record the information for the org. This also occurs at the point of returning user login, checking address, and submit.
		if "campaign" in request.POST and "demo" not in request.POST:
			ServiceAccountCampaign.objects.get(id=request.POST["campaign"]).add_action_record(
				firstname = identity["firstname"],
				lastname = identity["lastname"],
				zipcode = identity["zipcode"],
				email = identity["email"],
				completed_stage = "start",
				request_dump = meta_log(request.META) )
		
		return {
			"status": "success",
			"identity": identity,
			}

	########################################
	if request.POST["action"] == "login":
		try:
			email = validate_email(request.POST["email"], for_login=True)
			password = validate_password(request.POST["password"])
		except ValidationError as e:
			return { "status": "fail", "msg": validation_error_message(e) }
		
		user = authenticate(email=email, password=password)
		
		if user == None:
			return { "status": "fail", "msg": "That's not the right password, sorry!" }
		elif not user.is_active:
			return { "status": "fail", "msg": "Your account has been disabled." }
		else:
			# We can't log the user in because then future requests will require
			# a CSRF token, and we didn't set it on the main page load. So we'll
			# have to pass the password with future requests.
			
			# Another reason not to log the user in is if the user is on a shared
			# computer, they won't realize they've logged into something.

			# Record the information for the org. This also occurs at the point of new user information, checking the address, and submit.
			if "campaign" in request.POST and "demo" not in request.POST:
				ServiceAccountCampaign.objects.get(id=request.POST["campaign"]).add_action_record(
					email = email,
					completed_stage = "login",
					request_dump = meta_log(request.META) )
			

			return {
				"status": "success",
				"identity": widget_render_writecongress_get_identity(user),
				}
	
	########################################
	if request.POST["action"] == "address":
		p = PostalAddress()
		p.cdyne_response = None
		try:
			p.load_from_form(request.POST)
			
			if not BENCHMARKING:
				from writeyourrep.addressnorm import verify_adddress
				verify_adddress(p, validate=False) # we'll catch any problems later on
		except Exception as e:
			return { "status": "fail", "msg": validation_error_message(e) }

		if p.congressionaldistrict == None:
			recipients = []
		else:
			cx = UserComment()
			cx.bill = Bill.objects.get(id=request.POST["bill"])
			cx.address = p
			recipients = cx.get_recipients()
			if type(recipients) == str:
				recipients = []

		# Record the information for the org. This also occurs at the point of new user and returning user login and submit.
		if "campaign" in request.POST and "demo" not in request.POST:
			ServiceAccountCampaign.objects.get(id=request.POST["campaign"]).add_action_record(
				email = request.POST["email"],
				firstname = request.POST["useraddress_firstname"],
				lastname = request.POST["useraddress_lastname"],
				zipcode = request.POST["useraddress_zipcode"],
				completed_stage = "address",
				request_dump = meta_log(request.META) )

		user = User()
		user.id = request.POST.get("userid", None)
		user.email = request.POST["email"]
		
		return {
			"status": "success",
			"identity": widget_render_writecongress_get_identity(user, address=p),
			"recipients": [m["name"] for m in recipients],
			"cdyne_response": p.cdyne_response,
			}

	########################################
	if request.POST["action"] == "submit":
		cdyne_response = json.loads(request.POST["cdyne_response"])
		
		# Validate address fields.
		p = PostalAddress()
		try:
			p.load_from_form(request.POST)
		except Exception as e:
			return { "status": "fail", "msg": "Address error: " + validation_error_message(e) }

		bill = Bill.objects.get(id=request.POST["bill"])
		referrer, campaign, message = widget_render_writecongress_getsubmitparams(request.POST, account)

		# At this point we increment the service account beancounter for submitted comments for
		# the purpose of billing the account later. How do we know if we are supposed to charge
		# the account for this comment? Any advanced option means the user has a pro acct.,
		# which means we charge.
		if account != None and ("widget_theme" in permissions or "writecongress_ocp" in permissions) and "demo" not in request.POST:
			from django.db.models import F
			account.beancounter_comments = F('beancounter_comments') + 1
			account.save()
	
		# if the user is logged in and the address's congressional district
		# was determined, then we can save the comment immediately.
		if request.user.is_authenticated() and str(request.user.id) == request.POST.get("userid", None):
			user = request.user
		elif request.POST.get("userid", None) != None and "email" in request.POST and "password" in request.POST:
			user = authenticate(email=validate_email(request.POST["email"], for_login=True), password=validate_password(request.POST["password"])) # may return none on fail
			if user != None:
				# log the user in case he returns to another widget later, but this will spoil any
				# future requests back to this view because it will now require a CSRF token
				# which was not set when the page was loaded.
				login(request, user)
		else:
			user = None
			
		if user != None:
			# Normalize address/get district.
			from writeyourrep.addressnorm import verify_adddress_cached
			try:
				verify_adddress_cached(p, cdyne_response)
			except Exception as e:
				pass
			
			if getattr(p, "congressionaldistrict", None) != None:
				if "demo" in request.POST: return { "status": "demo-submitted", }
				save_user_comment(user, bill, request.POST["position"], referrer, message, p, campaign, UserComment.METHOD_WIDGET)
				status = "submitted"

			else:
				# The user is logged in but the address failed, so we have to have
				# him finish his comment. Since we don't need to create an account
				# for the user, we can redirect the user directly to the page to finish
				# the comment.
				status = "confirm-address"

		else:
			# We're going to have to confirm the user's email address, get
			# them to choose a screen name, and if their address did not
			# give a good address they'll have to pick their location on a map.
			status = "confirm-email"

		if "demo" in request.POST: return { "status": "demo-" + status, }

		# Record the information for the org. This also occurs at the point of new user and returning user login and address.
		if "campaign" in request.POST and "demo" not in request.POST:
			ServiceAccountCampaign.objects.get(id=request.POST["campaign"]).add_action_record(
				email = request.POST["email"],
				firstname = request.POST["useraddress_firstname"],
				lastname = request.POST["useraddress_lastname"],
				zipcode = request.POST["useraddress_zipcode"],
				completed_stage = status if status != "submitted" else "finished",
				request_dump = meta_log(request.META) )

		if status == "submitted":
			return { "status": status }

		axn = WriteCongressEmailVerificationCallback()
		axn.post = request.POST
		axn.password = User.objects.make_random_password()
		axn.account = account
		
		r = send_email_verification(request.POST["email"], None, axn, send_email=not BENCHMARKING)

		# for BENCHMARKING, we want to get the activation link directly
		if BENCHMARKING:
			return HttpResponse(r.url(), mimetype="text/plain")

		return { "status": status }
				
	
	######
	return {
		"status": "fail",
		"msg": "Invalid call."
		}

def widget_render_writecongress_get_identity(user, address=None):
	if address == None:
		try:
			pa = user.postaladdress_set.all().order_by("-created")[0]
		except:
			pa = object()
	else:
		pa = address
	
	return {
		"id": getattr(user, "id", ""),
		"email": getattr(user, "email", ""),
		"nameprefix": getattr(pa, "nameprefix", ""),
		"firstname": getattr(pa, "firstname", ""),
		"lastname": getattr(pa, "lastname", ""),
		"namesuffix": getattr(pa, "namesuffix", ""),
		"address1": getattr(pa, "address1", ""),
		"address2": getattr(pa, "address2", ""),
		"city": getattr(pa, "city", ""),
		"state": getattr(pa, "state", ""),
		"zipcode": getattr(pa, "zipcode", ""),
		"phonenumber": getattr(pa, "phonenumber", ""),
		"congressionaldistrict": getattr(pa, "congressionaldistrict", ""),
		}

def widget_render_writecongress_getsubmitparams(post, account):
	referrer = account
	campaign = None
	if "campaign" in post:
		try:
			# Because this is called from an email callback and a
			# service account could have been deleted in the meanwhile
			# (especially if it was for testing), wrap in a try.
			campaign = ServiceAccountCampaign.objects.get(id=post["campaign"])
			if campaign.account.org != None:
				referrer = campaign.account.org
		except:
			pass
	message = post["message"]
	if len(message.strip()) < 8:
		message = None

	return referrer, campaign, message

class WriteCongressEmailVerificationCallback:
	post = None
	password = None
	account = None
	
	def email_subject(self):
		referrer, campaign, message = widget_render_writecongress_getsubmitparams(self.post, self.account)
		if campaign:
			org = campaign.account.org
		else:
			org = None
		return "Finish Your Letter to Congress" + (" - " + org.name + " Needs Your Help" if org != None else "")
	
	def email_body(self):
		return """%s,

Thank you for sharing your opinion using the Write Congress tool from POPVOX.

In order to complete delivery to your Representative or Senators, we need to
verify your email address. We may also need some additional information from
you to meet your legislator's specific requirements.

To finish your letter and ensure delivery to Congress, click here:

     <URL>

     (If the link is not clickable, please copy and paste it into your web browser.)%s

Thanks again,

POPVOX


(We'll send this email again soon in case you miss it the first time.
If you do not wish to complete the action and do not want to get
a reminder, please follow this link instead to stop future reminders:
<KILL_URL>)""" % (self.post["useraddress_firstname"], ("""
	
We've also created an account for you at POPVOX so you can revise
your comment and check on its status.

     Your POPVOX password is: """ + self.password) if not User.objects.filter(email=self.post["email"]).exists() else "")

	def email_should_resend(self):
		if "userid" in self.post and self.post["userid"] != "":
			user = User.objects.get(id=self.post["userid"])
		else:
			try:
				user = User.objects.get(email=self.post["email"])
			except User.DoesNotExist:
				# If the account has not been created, then the action has not been completed.
				return True
		
		bill = Bill.objects.get(id=self.post["bill"])
		if not user.comments.filter(bill=bill).exists():
			# the comment does not exist, so the action has not been completed..... unless the user
			# decided to delete his comment after, which is why we need tracking of hits to the
			# verification URL and not test if the action was completed. 
			return True
			
		return False

	#@require_lock("auth_user", "popvox_userprofile") # prevent race conditions
	# The lock is too expensive. Making the requests operate in serial is an
	# enormous hit to the site's overall throughput. We'll take our chances.
	def create_user(self):
		# Get or create the User object.
		user_is_new = False
		try:
			if "userid" in self.post and self.post["userid"] != "":
				user = User.objects.get(id=self.post["userid"])
			else:
				user = User.objects.get(email=self.post["email"])
				
			user_is_new = user.username.startswith("Anonymous")
		except User.DoesNotExist:
			# At this point we know the user wants to leave his comment and even though
			# we don't have a screen name or password for the user, we want to get him
			# going as fast as possible. So we make up a username and create an account
			# with no password.
			
			# construct a new user with a random "Anonymous" username. Reminder:
			# usernames cannot contain spaces.
			while True:
				username = "Anonymous" + str(random.randint(User.objects.count()/2+1, User.objects.count()*10))
				if not User.objects.filter(username=username).exists():
					break
			
			user = User.objects.create_user(username, self.post["email"], password=self.password)
			user.save()

			# disable introductory emails, at least for now
			prof = user.userprofile
			prof.registration_welcome_sent = True
			prof.registration_followup_sent = True
			prof.save()
			
			user_is_new = True
			
		return user, user_is_new
	
	# do a lot of currying to make get_response in the shape of view(request)
	# so it can be wrapped in @csrf_protect.
	def csrf_protect_me(f):
		def g(self, request, vrec):
			@csrf_protect
			def h(request):
				return f(self, request, vrec)
			
			return h(request)
		return g
	
	@csrf_protect_me # because writecongress_followup calls back to set username/password
	def get_response(self, request, vrec):
		user, user_is_new = self.create_user()
		
		# Log the user in.
		user = authenticate(user_object = user)
		login(request, user)
		
		if user_is_new:
			# The next time the user gets to the bill share page (which might be
			# right now) we will ask them to provide a new screen name and
			# set a password.
			request.session["follow_up"] = "widget-screenname-password"
		
		# if a comment on the bill does not exist in the indicated account....
		bill = Bill.objects.get(id=self.post["bill"])
		if user.comments.filter(bill=bill).exists():
			# the session state will be used if we need to pop-up a lightbox
			# to get more info
			return HttpResponseRedirect(bill.url() + "/comment/share")
		else:
			# Fill in the address.
			p = PostalAddress()
			p.load_from_form(self.post, validate=False) # by now it really must validate
			cdyne_response = json.loads(self.post["cdyne_response"])
			if cdyne_response != None:
				from writeyourrep.addressnorm import verify_adddress_cached
				verify_adddress_cached(p, cdyne_response, validate=False)

			# Get the comment details.
			referrer, campaign, message = widget_render_writecongress_getsubmitparams(self.post, self.account)

			# If the address was OK, save the comment now.
			if getattr(p, "congressionaldistrict", None) != None:
				comment = save_user_comment(user, bill, self.post["position"], referrer, message, p, campaign, UserComment.METHOD_WIDGET)
				
				# the session state will be used if we need to pop up a lightbox
				return HttpResponseRedirect(bill.url() + "/comment/share")
	
			# Otherwise prepare session state for later and take the user
			# to the drag-your-home map.
			else:
				from bills import pending_comment_session_key
				request.session[pending_comment_session_key] = {
					"bill": bill.url(),
					"position": self.post["position"],
					"message": self.post["message"]
					}			
				request.session["comment-default-address"] = p
				if campaign != None or referrer != None:
					request.session["comment-referrer"] = { "bill": bill.id }
					if referrer != None:
						request.session["comment-referrer"]["referrer"] = referrer
					if campaign != None:
						request.session["comment-referrer"]["campaign"] = campaign.id
				elif "comment-referrer" in request.session:
					del request.session["comment-referrer"]
			
				from writeyourrep.district_metadata import get_viewport
				bounds = get_viewport(p)
				
				return render_to_response('popvox/billcomment_address_map.html', {
					'bill': bill,
					"position": self.post["position"],
					"message": message,
					"useraddress": p,
					"useraddress_prefixes": PostalAddress.PREFIXES,
					"useraddress_suffixes": PostalAddress.SUFFIXES,
					"useraddress_states": statelist,
					"bounds": bounds,
					"mode": "widget_writecongress",
					}, context_instance=RequestContext(request))

#@cache_page_postkeyed(60*60*12) # twelve hours
@cache_control(public=True, max_age=60*60*12)
def image(request, fn):
	if not re.match(r"^writecongress/(1|2|3|4|check|expand|next|preview|send|send-without|widget_writerep_progress|support-btn|oppose-btn)$", fn):
		raise Http404()
	
	import rsvg, cairo
	import os.path, StringIO
	import settings

	fn = os.path.dirname(settings.__file__) + '/media/widget/' + os.path.dirname(fn) + '/svg/' + os.path.basename(fn) + ".svg"
	data = open(fn, "r").read()

	for sub in request.GET.getlist("sub"):
		sp = sub.split(",")
		if len(sp) in (2, 3):
			find, replace = sp[0:2]
			
			if len(sp) == 3 and sp[2] == "darken":
				# reduce lightness by a factor
				def darken(c):
					h = hex(int(float(int(c,16)) * .5)).replace("0x","")
					if len(h) < 2: h = "0" + h
					return h
				replace = darken(replace[0:2]) + darken(replace[2:4]) + darken(replace[4:6])
		
			# TODO: Check that replace only has # and hex digits.
			data = data.replace(str(find), str(replace))

	svg = rsvg.Handle(data=data)

	width = svg.props.width
	height = svg.props.height
	
	# TODO 
	#if "width" in request.GET and "height" in request.GET:
	#	try:
	#		width = int(request.GET["width"])
	#		height = int(request.GET["height"])
	#	except:
	#		raise Http404()
	#elif "width" in request.GET:
	#	try:
	#		width = int(request.GET["width"])
	#		height = svg.props.height * width / svg.props.width
	#	except:
	#		raise Http404()
	#elif "height" in request.GET:
	#	try:
	#		height = int(request.GET["height"])
	#		width = svg.props.width * height / svg.props.height
	#	except:
	#		raise Http404()
	#
	#svg.set_dpi(
	#	dpi_x = svg.props.dpi_x * width / svg.props.width,
	#	dpi_y = svg.props.dpi_y * height / svg.props.height)

	surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
	svg.render_cairo(cairo.Context(surf))

	buf = StringIO.StringIO()
	surf.write_to_png(buf)

	return HttpResponse(buf.getvalue(), mimetype="image/png")

@login_required
def download_supporters(request, campaignid, dataformat):
	if not request.user.has_perm("popvox.can_snoop_service_analytics"):
		user_accounts = request.user.userprofile.service_accounts(create=False)
		campaign = get_object_or_404(ServiceAccountCampaign, id=campaignid, account__in=user_accounts)
	else:
		campaign = get_object_or_404(ServiceAccountCampaign, id=campaignid)
	
	column_names = ['trackingid', 'date', 'email', 'firstname', 'lastname', 'zipcode']
	column_keys = ['id', 'created', 'email', 'firstname', 'lastname', 'zipcode']
	
	import csv, json
	
	response = HttpResponse(mimetype='text/' + dataformat)
	response['Content-Disposition'] = 'attachment; filename=userdata.' + dataformat
	
	ret = []
	
	recs = campaign.actionrecords.all()
	total_records = recs.count()
	if request.GET.get("iSortingCols", "") != "":
		order = []
		for i in xrange(int(request.GET["iSortingCols"])):
			col = int(request.GET["iSortCol_" + str(i)])
			if request.GET.get('bSortable_' + str(col), "") == "true":
				order.append( ("" if request.GET.get("sSortDir_" + str(i), "asc") == "asc" else "-") + column_keys[col] )
		recs = recs.order_by(*order)
	if "iDisplayStart" in request.GET and "iDisplayLength" in request.GET:
		recs = recs[int(request.GET["iDisplayStart"]):int(request.GET["iDisplayStart"])+int(request.GET["iDisplayLength"])]
	
	if dataformat == "csv":
		writer = csv.writer(response)
		writer.writerow(column_names)
	
	for rec in recs:
		row = [unicode(getattr(rec, k)).encode("utf-8") for k in column_keys]
		if dataformat == "csv":
			writer.writerow(row)
		if dataformat == "json":
			ret.append(row)
			
	if dataformat == "json":
		ret = {
			"iTotalRecords": total_records,
			"iTotalDisplayRecords": total_records, # if there is filtering, which there is not
			"aaData": ret,
		}
		response.write(json.dumps(ret))
	
	return response

@csrf_protect
@login_required
def analytics(request):
	accts = request.user.userprofile.service_accounts()
	if request.user.has_perm("popvox.can_snoop_service_analytics") and "org" in request.GET:
		accts = ServiceAccount.objects.filter(org__slug=request.GET["org"])
	
	return render_to_response('popvox/services_analytics.html', {
			"accts": accts,
			"MIXPANEL_API_KEY": MIXPANEL_API_KEY,
			"has_campaigns": ServiceAccountCampaign.objects.filter(account__in=accts).exists()
		}, context_instance=RequestContext(request))

