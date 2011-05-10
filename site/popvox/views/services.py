from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.forms import ValidationError

from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout

from popvox.models import *
from popvox.govtrack import statelist, statenames, CURRENT_CONGRESS, getMemberOfCongress

from widgets import do_not_track_compliance
from bills import save_user_comment
from utils import require_lock, csrf_protect_if_logged_in

from registration.helpers import validate_email, validate_password
from emailverification.utils import send_email_verification

from jquery.ajax import json_response, validation_error_message

from settings import DEBUG, SITE_ROOT_URL

import urlparse
import json
import re
import random
from itertools import chain

def widget_config(request):
	# Collect all of the ServiceAccounts that the user has access to.
	
	return render_to_response('popvox/services_widget_config.html', {
		'accounts': request.user.userprofile.service_accounts() if request.user.is_authenticated() else [],
		
		'issueareas': IssueArea.objects.filter(parent__isnull=True),
		"states": statelist,
		"current_congress": CURRENT_CONGRESS,
		}, context_instance=RequestContext(request))

def validate_widget_request(request):
	api_key = request.GET.get("api_key", "")

	try:
		host = urlparse.urlparse(request.META.get("HTTP_REFERER", "http://www.example.org/")).hostname
		if host.startswith("www."):
			host = host[4:]
	except:
		host = "example.com"

	if not api_key:
		# so that we can use our own widgets on our site without an API key
		if host == "popvox.com" or host.endswith(".popvox.com"):
			return ["commentstream_theme"]
		
		return [] # no permissions
	
	# Validate the key
	try:
		account = ServiceAccount.objects.get(api_key=api_key)
	except ServiceAccount.DoesNotExist:
		return None # invalid info
	
	# Get the permitted referring hostnames.
	permitted_hosts = [s.strip() for s in account.hosts.split("\n") if s.strip() != ""]
	if len(permitted_hosts) == 0 and account.org != None and account.org.website != "":
		# the default host is the domain of the org's configured website
		website_hostname = urlparse.urlparse(account.org.website).hostname
		if website_hostname.startswith("www."):
			website_hostname = website_hostname[4:]
		permitted_hosts = [website_hostname]
		
	# Validate the referrer.
	if host != "popvox.com" and not host.endswith(".popvox.com") and host not in permitted_hosts:
		return None # invalid call from other site
	
	return [p.name for p in account.permissions.all()]

def widget_render(request, widgettype):
	permissions = validate_widget_request(request)
	if permissions == None:
		return HttpResponseForbidden()
	
	if widgettype == "commentstream":
		return widget_render_commentstream(request, permissions)
	if widgettype == "writecongress":
		# remember: needs session state
		return widget_render_writecongress(request, permissions)

	raise Http404()

@do_not_track_compliance
def widget_render_commentstream(request, permissions):
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
				title2 = "Invalid bill number."
			
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
def widget_render_writecongress(request, permissions):
	if request.META["REQUEST_METHOD"] == "GET":
		# Get bill, position, org, orgcampaignposition, and reason.
		ocp = None
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
				return HttpResponseBadRequest("Invalid URL.")
		else:
			# ocp argument specifies the OrgCampaignPosition, which has all of the
			# information we need.
			try:
				_ocp = OrgCampaignPosition.objects.get(id=request.GET["ocp"], position__in=("+", "-"), campaign__visible=True, campaign__org__visible=True)
			except OrgCampaignPosition.DoesNotExist:
				return HttpResponseBadRequest("The campaign for the bill has become hidden or the widget URL is invalid")
			bill = _ocp.bill
			position = _ocp.position
			position_verb = "support" if position == "+" else "oppose"
			if "writecongress_ocp" in permissions:
				# We'll let the caller use an OCP id to get the bill and position, but
				# don't tie this request to the org if the account doesn't have the
				# writecongress_ocp permission.
				ocp = _ocp
				org = ocp.campaign.org
				reason = ocp.comment
			
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
		
		# compute suggestions for further action
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
			other_bills = [bs[0] for bs in other_bills[0:3]]
			suggestions["0"][2] = other_bills
		else:
			for ocp in OrgCampaignPosition.objects.filter(campaign__org=org, campaign__visible=True).exclude(bill=bill):
				if len(suggestions[ocp.position][2]) < 2 and ocp.bill.isAlive():
					suggestions[ocp.position][2].append(ocp.bill)
			if len(suggestions["+"][2]) + len(suggestions["-"][2]) >= 4:
				suggestions["0"] = []
		
		# Render.
		response = render_to_response('popvox/widgets/writecongress.html', {
			"permissions": permissions,
			"displayname": displayname,
			"identity": None if u == None else json.dumps(widget_render_writecongress_get_identity(request.user)),
			
			"ocp": ocp,
			"org": org,
			"reason": reason,
			"verb": position_verb,
			"bill": bill,
			"position": position,
			"url": url,
			
			"suggestions": suggestions.values(),
			
			"useraddress_prefixes": PostalAddress.PREFIXES,
			"useraddress_suffixes": PostalAddress.SUFFIXES,
			}, context_instance=RequestContext(request))
	else:
		response = widget_render_writecongress_action(request, permissions)

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
def widget_render_writecongress_action(request, permissions):
	from settings import BENCHMARKING
	
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

		sso = u.singlesignon.all()
		if not u.has_usable_password() and sso.count() == 0:
			# no way to log in!
			return { "status": "not-registered" }
		
		return {
			"status": "registered",
			"has_password": u.has_usable_password(),
			"sso_methods": [s.provider for s in sso],
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
		if request.POST["demo"] != "true":
			logout(request)
		
		# Record the information for the org. This also occurs at the point of checking
		# the address.
		if "ocp" in request.POST and request.POST["demo"] != "true" and "writecongress_ocp" in permissions:
			ocp = OrgCampaignPosition.objects.get(id=request.POST["ocp"])
			if not OrgCampaignPositionActionRecord.objects.filter(ocp=ocp, email=identity["email"]).exists():
				ocpar = OrgCampaignPositionActionRecord()
				ocpar.ocp = ocp
				ocpar.firstname = identity["firstname"]
				ocpar.lastname = identity["lastname"]
				ocpar.zipcode = identity["zipcode"]
				ocpar.email = identity["email"]
				ocpar.save()
		
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
			# It is important to log the user in here. Since we don't re-send the
			# password later on, we rely on the log-in state to ensure that the
			# submitter is the user he claims to be at the point of submitting the
			# comment.
			
			# The trouble is, now that the user is logged in future calls are going
			# to require a CSRF token which was not provided on the original
			# GET request. Thus, the HTML page must reload.
			
			login(request, user)
			
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

		if request.user.is_authenticated() and request.user.id == request.POST.get("userid", None):
			user = request.user
		else:
			user = User()
			user.email = request.POST["email"]
		
		if p.congressionaldistrict == None:
			recipients = []
		else:
			cx = UserComment()
			cx.bill = Bill.objects.get(id=request.POST["bill"])
			cx.address = p
			recipients = cx.get_recipients()
			if type(recipients) == str:
				recipients = []

		# Record the information for the org. This also occurs at the point of new user login.
		if "ocp" in request.POST and request.POST["demo"] != "true" and "writecongress_ocp" in permissions:
			ocp = OrgCampaignPosition.objects.get(id=request.POST["ocp"])
			if not OrgCampaignPositionActionRecord.objects.filter(ocp=ocp, email=request.POST["email"]).exists():
				ocpar = OrgCampaignPositionActionRecord()
				ocpar.ocp = ocp
				ocpar.firstname = request.POST["useraddress_firstname"]
				ocpar.lastname = request.POST["useraddress_lastname"]
				ocpar.zipcode = request.POST["useraddress_zipcode"]
				ocpar.email = request.POST["email"]
				ocpar.save()

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
			return { "status": "fail", "msg": validation_error_message(e) }

		bill = Bill.objects.get(id=request.POST["bill"])
		referrer, ocp, message = widget_render_writecongress_getsubmitparams(request.POST, permissions)
		
		# We use the same object for any of the reasons why we might need to send
		# a follow-up email.
		axn = WriteCongressEmailVerificationCallback()
		axn.post = request.POST
		axn.permissions = permissions

		# if the user is logged in and the address's congressional district
		# was determined, then we can save the comment immediately.
		if request.user.is_authenticated() and request.user.id == request.POST.get("userid", None):
			user = request.user
			
			# Normalize address/get district.
			from writeyourrep.addressnorm import verify_adddress_cached
			try:
				verify_adddress_cached(p, cdyne_response)
			except Exception as e:
				pass
			
			if getattr(p, "congressionaldistrict", None) != None:
				if request.POST["demo"] == "true": return { "status": "demo-submitted", }
				save_user_comment(user, bill, request.POST["position"], referrer, message, p, ocp)
				return { "status": "submitted", }

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

		if request.POST["demo"] == "true": return { "status": "demo-" + status, }

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
		"screenname": getattr(user, "username", ""),
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

def widget_render_writecongress_getsubmitparams(post, permissions):
	referrer = None
	ocp = None
	if "ocp" in post and "writecongress_ocp" in permissions:
		ocp = OrgCampaignPosition.objects.get(id=post["ocp"])
		referrer = ocp.campaign
		if referrer.default: # instead of org default campaign, use org
			referrer = referrer.org
	message = post["message"]
	if len(message.strip()) < 8:
		message = None

	return referrer, ocp, message

class WriteCongressEmailVerificationCallback:
	post = None
	permissions = None
	
	def email_subject(self):
		return "Finish Your Letter to Congress"
	
	def email_body(self):
		return """%s,

Thank you for sharing your opinion using the POPVOX Write Congress tool.

POPVOX ensures your letter to Congress is most effective by verifying your
email address before submitting it to your representatives. We may also
need additional information from you.

To finish your letter to Congress, just follow this link:

<URL>

If the link is not clickable, please copy and paste it into your web browser.

Thanks again,

POPVOX""" % (self.post["useraddress_firstname"], )

	@require_lock("auth_user", "popvox_userprofile") # prevent race conditions
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
			
			user = User.objects.create_user(username, self.post["email"])
			user.save()
			
			user_is_new = True
			
		return user, user_is_new
	
	def get_response(self, request, vrec):
		user, user_is_new = self.create_user()
		
		# Log the user in.
		user = authenticate(user_object = user)
		login(request, user)
		
		# if a comment on the bill exists in the indicated account....
		comment = None
		bill = Bill.objects.get(id=self.post["bill"])
		if user.comments.filter(bill=bill).exists():
			# And if they are already fully registered, then redirect them to their comment share page.
			if not user_is_new:
				return HttpResponseRedirect(bill.url() + "/comment/share")
		
			# We'll need them to finish registration, but afterwards send them along to the share page.
			comment = user.comments.get(bill=bill)
		
		# Create the comment record.
		else:
			# Fill in the address.
			p = PostalAddress()
			p.load_from_form(self.post, validate=False) # by now it really must validate
			cdyne_response = json.loads(self.post["cdyne_response"])
			if cdyne_response != None:
				from writeyourrep.addressnorm import verify_adddress_cached
				verify_adddress_cached(p, cdyne_response, validate=False)
			
			if getattr(p, "congressionaldistrict", None) != None:
				# We have everything we need to save the comment.
				referrer, ocp, message = widget_render_writecongress_getsubmitparams(self.post, self.permissions)
				comment = save_user_comment(user, bill, self.post["position"], referrer, message, p, ocp)
	
				if not user_is_new:
					# The user had an account and all we needed to do was post the comment, so
					# show the user the pie chart page.
					return HttpResponseRedirect(bill.url() + "/comment/share")
					
			else:
				
				from bills import pending_comment_session_key
				request.session[pending_comment_session_key] = {
					"bill": bill.url(),
					"position": self.post["position"],
					"message": self.post["message"]
					}			
				request.session["comment-default-address"] = p
				
	
		# Now let the user choose a screen name and password, and then send them to the pie chart
		# or the address verifcation step.
		
		return render_to_response('popvox/widgets/writecongress_followup.html', {
			"user_is_new": user_is_new,
			"username": user.username,
			"post": self.post,
			"bill": bill,
			"comment": comment,
			}, context_instance=RequestContext(request))
			
