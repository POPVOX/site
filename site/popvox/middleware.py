from django.shortcuts import render_to_response
from django.template import RequestContext

# This goes after the TrafficAnalysis middleware which sets the ua field.
class IE6BlockMiddleware:
	def process_request(self, request):
		if hasattr(request, "ua") and request.ua["ua_name"] == "IE 6.0":
			return render_to_response("static/ie6.html", context_instance=RequestContext(request))
		return None

