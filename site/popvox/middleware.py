from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.cache import patch_vary_headers
from django.conf import settings

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
			
		return None

# Applies some standard cache semantics throughout the site, unless
# Cache-Control is already set on the response.
#  * Set the header Vary: Cookie. Downstream caching should always
#     vary on the request session and csrf cookies.
#  * If the request has no session data and the response has no csrf cookie,
#     cache for one hour.
#  * Otherwise, don't cache.
class StandardCacheMiddleware:
	def process_response(self, request, response):
		if not "Cache-Control" in response and request.method == "GET":
			patch_vary_headers(response, ["Cookie"])
			
			session = getattr(request, "session", None)
			if session == None: session = {}
			
			if len(session.items()) == 0 and not response.has_header("Set-Cookie"):
				response['Cache-Control'] = 'max-age: 3600'
			else:
				response['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
				
				if settings.DEBUG:
					response["X-Django-Session"] = repr(session.items())
					
		# If no CSRF cookie was set, clear the client's cookie for the sake of being able
		# to cache future requests.
		if request.method == "GET" and not getattr(response, "csrf_procesing_done", False) and settings.CSRF_COOKIE_NAME in request.COOKIES:
			response.delete_cookie(settings.CSRF_COOKIE_NAME)
		
		return response

