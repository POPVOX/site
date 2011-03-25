from django.shortcuts import render_to_response
from django.template import RequestContext

# This goes after the TrafficAnalysis middleware which sets the ua field.
class IE6BlockMiddleware:
	def process_request(self, request):
		if hasattr(request, "ua") and request.ua["ua_name"] == "IE 6.0":
			return render_to_response("static/ie6.html", context_instance=RequestContext(request))
		return None

class AdserverTargetsMiddleware:
	def process_request(self, request):
		user = request.user
		if not user.is_authenticated():
			return None
		
		profile = user.get_profile()
		if profile.is_leg_staff():
			request.session["adserver-targets"] = ["popvox_legstaff"]
		elif profile.is_org_admin():
			request.session["adserver-targets"] = ["popvox_orgstaff"]
		else:
			request.session["adserver-targets"] = ["popvox_individual"]
			
		return None

