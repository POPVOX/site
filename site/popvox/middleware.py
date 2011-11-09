from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.cache import patch_vary_headers
from django.conf import settings
from django.utils.importlib import import_module

import datetime

# This goes after the TrafficAnalysis middleware which sets the ua field.
class IE6BlockMiddleware:
	def process_request(self, request):
		if hasattr(request, "ua") and request.ua["ua_name"] == "IE 6.0":
			response = render_to_response("static/ie6.html", context_instance=RequestContext(request))
			response['Cache-Control'] = 'no-store'
			return response
		return None

class AdserverTargetsMiddleware:
	def process_request(self, request):
		if request.is_ajax(): # don't bother
			return None
		
		user = request.user
		if not user.is_authenticated():
			return None
		
		profile = user.get_profile()
		if profile.is_leg_staff():
			request.adserver_targets = ["popvox_legstaff"]
		elif profile.is_org_admin():
			request.adserver_targets = ["popvox_orgstaff"]
		else:
			request.adserver_targets = ["popvox_individual"]

			ip = request.META.get("REMOTE_ADDR", "0.0.0.0")
			if ip.startswith("137.18."):
				request.adserver_targets = ["net_house"]
			if ip.startswith("156.33."):
				request.adserver_targets = ["net_senate"]

		return None

# Applies some standard cache semantics throughout the site, unless
# Cache-Control is already set on the response.
#  * If strong_cache is set to True on the request and the response has
#     status 200, cache for one hour.
#  * Otherwise, don't cache.
# Also clears the csrf cookie when it is not needed so that the downstream
# cache can resume caching for the client.
class StandardCacheMiddleware:
	def process_response(self, request, response):
		if "Cache-Control" not in response and request.method == "GET" and response.status_code in (200, 302, 404) and getattr(request, "strong_cache", False):
			response['Cache-Control'] = 'max-age: 3600'
			response["X-Page-Generated-At"] = datetime.datetime.now().isoformat()
			return response
			
		response['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
				
		if settings.DEBUG and getattr(request, "session", None) != None:
			import re
			response["X-Django-Session"] = re.sub(r"\s+", " ", repr(request.session.items()))
					
		return response

# Put this between SessionMiddlware and AuthenticationMiddleware to load the session
# from a GET or POST session variable, if set, as an alternative to passing a session
# cookie.
#
# We use this for the POPVOX API (as a GET parameter), for file uploads (e.g. org
# profile image), and for web views from the iPad app.
class SessionFromFormMiddleware(object):
	def process_request(self, request):
		if "session" in request.REQUEST:
			engine = import_module(settings.SESSION_ENGINE)
			request.session = engine.SessionStore(request.REQUEST["session"])
			request.session.modified = True # force write to cookie so that session persists
