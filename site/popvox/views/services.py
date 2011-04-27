from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.forms import ValidationError

from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout

from popvox.models import *
from popvox.govtrack import statelist, statenames, CURRENT_CONGRESS

from widgets import do_not_track_compliance

from registration.helpers import validate_email, validate_password

from jquery.ajax import json_response, validation_error_message

from settings import SITE_ROOT_URL

import urlparse
import json

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
		return render_to_response('popvox/widgets/writecongress.html', {
			"permissions": permissions,
			"screenname": None if not request.user.is_authenticated else request.user.username,
			"identity": None if not request.user.is_authenticated else json.dumps(widget_render_writecongress_get_identity(request.user))
			}, context_instance=RequestContext(request))
	else:
		return widget_render_writecongress_action(request)


@json_response
def widget_render_writecongress_action(request):
	if request.POST["action"] == "check-email":
		try:
			email = validate_email(request.POST["email"], for_login=True)
		except ValidationError:
			return { "status": "invalid-email" }
		
		try:
			u = User.objects.get(email = email)
		except User.DoesNotExist:
			return { "status": "not-registered" }
			
		sso = u.singlesignon.all()
		
		return {
			"status": "registered",
			"has_password": u.has_usable_password(),
			"sso_methods": [s.provider for s in sso],
			}

	if request.POST["action"] == "login":
		try:
			email = validate_email(request.POST["email"], for_login=True)
			password = validate_password(request.POST["password"])
		except ValidationError as e:
			return { "status": "error", "message": validation_error_message(e) }
		
		user = authenticate(email=email, password=password)
		
		if user == None:
			return { "status": "error", "message": "That's not the right password, sorry!" }
		elif not user.is_active:
			return { "status": "error", "message": "Your account has been disabled." }
		else:
			login(request, user)
			
			return {
				"status": "success",
				"identity": widget_render_writecongress_get_identity(user),
				}

def widget_render_writecongress_get_identity(user):
	try:
		pa = user.postaladdress_set.all().order_by("-created")[0]
	except:
		pa = object()
	
	return {
		"id": user.id,
		"screenname": user.username,
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

