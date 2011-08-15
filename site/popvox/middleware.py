from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.cache import patch_vary_headers
from django.conf import settings

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

			ip = request.META.get("HTTP_X_REAL_IP", "0.0.0.0")
			if ip.startswith("137.18."):
				request.adserver_targets = ["net_house"]
			if ip.startswith("156.33."):
				request.adserver_targets = ["net_senate"]

		if "98.204.156.74" == request.META.get("HTTP_X_REAL_IP", "0.0.0.0"):
			request.adserver_targets = ["test_josh"]
			
		return None

# Applies some standard cache semantics throughout the site, unless
# Cache-Control is already set on the response.
#  * Set the header Vary: Cookie. Downstream caching should always
#     vary on the request session and csrf cookies.
#  * If the request has no session data and the response has no csrf cookie,
#     cache for one hour.
#  * Otherwise, don't cache.
# Also clears the csrf cookie when it is not needed so that the downstream
# cache can resume caching for the client.
class StandardCacheMiddleware:
	def process_response(self, request, response):
		if not "Cache-Control" in response and request.method == "GET" and response.status_code == 200:
			patch_vary_headers(response, ["Cookie"])
			
			session = getattr(request, "session", None)
			if session == None: session = {}
			
			if len(session.items()) == 0 and not response.has_header("Set-Cookie") and not getattr(response, "csrf_processing_done", False):
				response['Cache-Control'] = 'max-age: 3600'
			else:
				response['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
				
				if settings.DEBUG:
					import re
					response["X-Django-Session"] = re.sub(r"\s+", " ", repr(session.items()))
					
		# If no CSRF cookie was set, we want to clear the client's cookie for the sake of being able
		# to cache future requests. But this can also occur on page-internal resources which then
		# messes up later AJAX calls.
		#if request.method == "GET" and not getattr(response, "csrf_processing_done", False) and settings.CSRF_COOKIE_NAME in request.COOKIES:
		#	response.delete_cookie(settings.CSRF_COOKIE_NAME)
		
		if request.method == "POST":
			response['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
		
		response["X-Page-Generated-At"] = datetime.datetime.now().isoformat()
		
		return response

