from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist

from popvox.models import *

from settings import FACEBOOK_APP_SECRET

from base64 import urlsafe_b64decode, urlsafe_b64encode
import hmac, hashlib
import json, re
import urllib, urllib2

def org_check_api_key(request):
	api_key = request.GET.get("api_key", "")
	try:
		org = Org.objects.get(api_key=api_key)
		return HttpResponse("Great! That is the correct integration key for " + org.name + ".", mimetype="text/plain")
	except Org.DoesNotExist:
		return HttpResponse("That is not a correct organization integration key.", mimetype="text/plain")

def salsa_legagenda(request):
	api_key = request.GET.get("api_key", "")
	org = get_object_or_404(Org, api_key=api_key)
	return render_to_response("popvox/embed/salsa_legagenda.html", {
		"org": org,
	}, context_instance=RequestContext(request))
	
def b64_pad(s):
	m = 4 - (len(s) % 4)
	for i in xrange(m):
		s += "="
	return s
	
def http_rest_json(url, args=None, method="GET"):
	if method == "GET" and args != None:
		url += "?" + urllib.urlencode(args).encode("utf8")
	req = urllib2.Request(url)
	r = urllib2.urlopen(req)
	return json.load(r, "utf8")

def facebook_verify_signed_request(f):
	def g(request, *args, **kwargs):
		fields = request.REQUEST.get("signed_request", "").split(".", 2)
		
		if len(fields) != 2:
			return HttpResponseForbidden("signed_request was invalid")
		
		sig, fbargs = [urlsafe_b64decode(b64_pad(field.encode("ascii"))) for field in fields]
		fbargs = json.loads(fbargs)

		if fbargs["algorithm"].upper() != 'HMAC-SHA256':
			return HttpResponseForbidden("signed_request algorithm was invalid")

		expected_sig = hmac.new(FACEBOOK_APP_SECRET, fields[1], hashlib.sha256).digest()
		if sig != expected_sig:
			return HttpResponseForbidden("signed_request has an invalid signature")
		
		return f(request, fbargs, *args, **kwargs)
		
	return g
		
@facebook_verify_signed_request
def facebook_page(request, fbargs):
	# Let the Page admin set the fb_page_id on his service account by passing
	# the service account secret key.
	error_str = ""
	if fbargs["page"]["admin"] and "pv_secret_key" in request.POST:
		try:
			acct = ServiceAccount.objects.get(secret_key=request.POST["pv_secret_key"].strip())
			acct.fb_page_id = fbargs["page"]["id"]
			acct.save()
		except ServiceAccount.DoesNotExist:
			error_str = "That was not a valid POPVOX service account secret password."
	
	# Look for a service account tied to this Facebook Page.
	try:
		acct = ServiceAccount.objects.get(fb_page_id=fbargs["page"]["id"])
	except ServiceAccount.DoesNotExist:
		if not fbargs["page"]["admin"]:
			return HttpResponse("The administrator for this Page has not set up the POPVOX tab yet.", mimetype="text/html")
		else:
			# For Page admins, the initialization form.
			return HttpResponse("""
<html>
<head><style>body { font-family: sans-serif; }</style></head>
<body>
<h1>Configure POPVOX Tab</h1>
<p>In order to activate the POPVOX tab, please enter your POPVOX service account secret password found on the integrations tab of the <a href=\"https://www.popvox.com/services/widgets\"  target=\"_blank\">POPVOX widget configuration page</a>.</p>
<form method="post">
	<input type="hidden" name="signed_request" value="%s"/>
	<div>Service Account Secret Password:</div>
	<div><input type="text" name="pv_secret_key" value=""/></div>
	<div><input type="submit" value="Submit"/></div>
</form>
<p style="color: red">%s</p>
</body>
</html>
""" % (request.POST["signed_request"], error_str), mimetype="text/html")
	
	# Get the canvas code as published on the widget page.
	resp = acct.getopt("fb_page_code", None)
	
	# No code yet.
	if resp == None:
		if not fbargs["page"]["admin"]:
			return HttpResponse("The administrator for this Page has not set up the POPVOX tab yet.", mimetype="text/html")
			
		else:
			# Instructions for setting up the widget.
			return HttpResponse("""
<html>
<head><style>body { font-family: sans-serif; }</style></head>
<body>
<h1>Configure POPVOX Tab</h1>
<p>You have correctly connected this tab to your service account %s.</p>
<p>Use the <a href=\"https://www.popvox.com/services/widgets\"  target=\"_blank\">POPVOX widget configuration page</a> to publish a widget to this space. Reload this page after you have published your widget.</p>
</body>
</html>
""" % (unicode(acct), ), mimetype="text/html")
	
	# If the iframe code has a numeric height attribute, use it (with some padding)
	# to adjust the height of the canvas.
	htm = re.search(r'height="(\d+)"', resp)
	if htm:
		resp = ("""
<div id="fb-root"></div>
<script src="https://connect.facebook.net/en_US/all.js"></script>
<script>
FB.init({});
window.fbAsyncInit = function() {
	FB.Canvas.setSize({height: %d});
}
</script>
""" % (int(htm.group(1))+100,)) + resp

	# If the user has already authorized this app, then we get a user_id and oauth_token.
	# The only folks who would have authorized the app are those that logged in via Facebook
	# to the main site. But still.
	if "user_id" in fbargs:
		user_info = http_rest_json("https://graph.facebook.com/" + fbargs["user_id"],
			{ "oauth_token": fbargs["oauth_token"] })
		# re-write for what a widget can expect
		user_info = urlsafe_b64encode(json.dumps({
			"first_name": user_info["first_name"],
			"last_name": user_info["last_name"],
			"email": user_info["email"] if not "facebook" in user_info["email"] else "",
			}).encode("ascii")).replace("=", ".")
		resp = resp.replace("&user_info=", "&user_info=" + user_info)

	# Prepend some instructions for page admins.
	if fbargs["page"]["admin"]:
		resp = "<p style=\"font-size: 80%\">Administrator: Use <a href=\"https://www.popvox.com/services/widgets\"  target=\"_blank\">POPVOX Widget Configuration</a> to update this tab.</p>" + resp
	
	return HttpResponse(resp, mimetype="text/html")

