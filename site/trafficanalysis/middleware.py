from models import *

class TrafficAnalysisMiddleware:
	def process_request(self, request):
		if request.META.get("HTTP_USER_AGENT", "").strip() != "":
			request.ua = uas_parser.parse(request.META["HTTP_USER_AGENT"])
		return None
	
	def process_response(self, request, response):
		return response # skip all of this

		# Can't do traffic analysis if there is no session state.
		if getattr(request, "session", None) == None:
			return response
		
		# Assume the ua has been set in the request handler and ignore
		# requests from robots.
		if getattr(request, "ua", None) == None:
			return response
		if request.ua["typ"] == "Robot":
			return response
		
		# Don't record AJAX requests unless the view has has a goal object
		# on either the request or response.
		if request.is_ajax() and (getattr(request, "goal", None) == None and getattr(response, "goal", None) == None):
			return response

		# If the goal has been set explicitly to none, don't record.
		if (hasattr(request, "goal") and getattr(request, "goal") == None) or (hasattr(response, "goal") and getattr(response, "goal") == None):
			return response

		# Don't record static content.
		if response["Content-Type"] in ("application/javascript", 'text/css', 'image/gif', 'image/png', 'image/jpeg', 'application/octet-stream'):
			return response
		
		# Get an existing session object if any.
		
		session = None
		if "trafficanalysis.sid" in request.session:
			try:
				session = Session.objects.get(id = request.session["trafficanalysis.sid"])
			except:
				pass
			
		if session == None and request.user.is_authenticated():
			try:
				session = Session.objects.get(user = request.user)
			except:
				pass
		
		if session == None:
			session = Session()
		
		if request.user.is_authenticated():
			session.user = request.user
			
		session.set_ua(request)
		
		# Append the new path entry at the end of the session and save.
		pe = PathEntry(request, response)
		session.path_append(pe)
		session.save()
		
		# Store the session id back in the session state so we can find the user again.
		request.session["trafficanalysis.sid"] = session.id
		
		return response

