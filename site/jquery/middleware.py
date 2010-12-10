from django.conf import settings
from django.utils.importlib import import_module
#from django.contrib.sessions import ...

# Put this between SessionMiddlware and AuthenticationMiddleware to load the session
# from a POST session_key variable if set.
class SessionFromPostMiddleware(object):
	def process_request(self, request):
		if "session_key" in request.POST:
			engine = import_module(settings.SESSION_ENGINE)
			request.session = engine.SessionStore(request.POST["session_key"])

