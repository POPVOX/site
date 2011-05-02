from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.forms import ValidationError

from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout

from popvox.models import *
from popvox.govtrack import statelist, statenames, CURRENT_CONGRESS, getMemberOfCongress

from widgets import do_not_track_compliance

from registration.helpers import validate_email, validate_password

from jquery.ajax import json_response, validation_error_message

from settings import DEBUG, SITE_ROOT_URL

import urlparse
import json
import re
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
	except:
		host = "example.com"

	if not api_key:
		if host == "popvox.com":
			return ["commentstream_theme"]
		
		return [] # no permissions
	
	# Validate the key
	try:
		account = ServiceAccount.objects.get(api_key=api_key)
	except ServiceAccount.DoesNotExist:
		return None # invalid info
		
	# Validate the referrer.
	if host.startswith("www."):
		host = host[4:]
	if host != "popvox.com" and host not in account.hosts.split("\n"):
		return None # invalid call from other site
	
	return [p.name for p in account.permissions.all()]

def widget_render(request, widgettype):
	permissions = validate_widget_request(request)
	if permissions == None:
		return HttpResponseForbidden()
	
	if widgettype == "commentstream":
		return widget_render_commentstream(request, permissions)
	if widgettype == "writecongress":
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


def widget_render_writecongress(request, permissions):
	if request.META["REQUEST_METHOD"] == "GET":
		# Get bill, position, org, orgcampaignposition, and reason.
		ocp = None
		org = None
		reason = None
		if "ocp" not in request.GET:
			if not "bill" in request.GET:
				raise Http404()
			try:
				bill = bill_from_url("/bills/" + request.GET["bill"])
			except:
				raise Http404("Invalid bill")
			position = request.GET["position"]
			if not position in ("support", "oppose"):
				raise Http404("Invalid position")
		else:
			# ocp argument specifies the OrgCampaignPosition, which has all of the
			# information we need.
			ocp = get_object_or_404(OrgCampaignPosition, id=request.GET["ocp"], position__in=("+", "-"), campaign__visible=True, campaign__org__visible=True)
			org = ocp.campaign.org
			bill = ocp.bill
			position = "support" if ocp.position == "+" else "oppose"
			reason = ocp.comment
			
		if not bill.isAlive():
			raise Http404("Bill is not alive.")
			
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
			"screenname": None if u == None else request.user.username,
			"identity": None if u == None else json.dumps(widget_render_writecongress_get_identity(request.user)),
			
			"ocp": ocp,
			"org": org,
			"reason": reason,
			"verb": position,
			"bill": bill,
			"url": url,
			
			"suggestions": suggestions.values(),
			
			"useraddress_prefixes": PostalAddress.PREFIXES,
			"useraddress_suffixes": PostalAddress.SUFFIXES,
			}, context_instance=RequestContext(request))
	else:
		response = widget_render_writecongress_action(request)

	# add a P3P compact policy so that IE will accept third-party cookies.
	# apparently the actual policy doesn't matter as long as one is sent,
	# but we're setting the following policy;
	#  access: ident-contact
	#  purpose: current, admin, develop, tailoring, individual-analysis, individual-decision, contact
	#  recipient: ours, same (i.e. Congress), public
	#  retention: business-practices
	#  data: 
	response["P3P"] = 'CP="IDC CUR ADM DEV TAI IVA IVD CON OUR SAM PUB BUS"'

	return response


@json_response
def widget_render_writecongress_action(request):
	
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
		bill = Bill.objects.get(id=request.POST["bill"])
		if u.comments.filter(bill=bill).exists():
			return { "status": "already-commented" }

		sso = u.singlesignon.all()
		
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
		
		# if user is logged in, log him out
		logout(request)
		
		# Record the information for the org, and store a record id for later.
		if "ocp" in request.POST:
			ocpar = OrgCampaignPositionActionRecord()
			ocpar.ocp = OrgCampaignPosition.objects.get(id=request.POST["ocp"])
			ocpar.firstname = identity["firstname"]
			ocpar.lastname = identity["lastname"]
			ocpar.zipcode = identity["zipcode"]
			ocpar.email = identity["email"]
			ocpar.save()
			identity["ocpar"] = ocpar.id
		
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
			login(request, user)
			
			return {
				"status": "success",
				"identity": widget_render_writecongress_get_identity(user),
				}
	
	########################################
	if request.POST["action"] == "address":
		p = PostalAddress()
		try:
			p.load_from_form(request)
			
			if not DEBUG:
				from writeyourrep.addressnorm import verify_adddress
				verify_adddress(p, validate=False) # we'll catch any problems later on
			else:
				p.congressionaldistrict = 1
		except Exception as e:
			return { "status": "fail", "msg": validation_error_message(e) }

		if "id" in request.POST and request.POST["id"] != "":
			user = User.objects.get(id=request.POST["id"])
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

		identity = widget_render_writecongress_get_identity(user, address=p)

		# Record the information for the org, and store a record id for later.
		# If the user was a new user, then the record was created in the 
		# first step. Otherwise, we create the record only at this point.
		if "ocp" in request.POST and (not "ocpar" in request.POST or request.POST["ocpar"] == ""):
			ocpar = OrgCampaignPositionActionRecord()
			ocpar.ocp = OrgCampaignPosition.objects.get(id=request.POST["ocp"])
			ocpar.firstname = identity["firstname"]
			ocpar.lastname = identity["lastname"]
			ocpar.zipcode = identity["zipcode"]
			ocpar.email = identity["email"]
			ocpar.save()
			identity["ocpar"] = ocpar.id
		elif "ocpar" in request.POST:
			identity["ocpar"] = request.POST["ocpar"]

		return {
			"status": "success",
			"identity": identity,
			"recipients": [m["name"] for m in recipients],
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

