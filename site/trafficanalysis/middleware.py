from django.utils.http import cookie_date
from django.core.exceptions import SuspiciousOperation
from django.utils.hashcompat import md5_constructor
from django.conf import settings

from models import *

import base64, time, random, urllib, collections, os

SESSION_COOKIE_NAME = "tr_sid"

class TrafficAnalysisMiddleware:
	def process_request(self, request):
		if request.META.get("HTTP_USER_AGENT", "").strip() != "":
			request.ua = uas_parser.parse(request.META["HTTP_USER_AGENT"])
		return None
	
	def process_view(self, request, view_func, view_args, view_kwargs):
		request.trafficanalysis_view_info = ("%s.%s" % (view_func.__module__, view_func.__name__), view_args, view_kwargs)
		return None
		
	def process_response(self, request, response):
		# protect from any inadvertent errors
		try:
			return self.do_process_response(request, response)
		except:
			return response
		
	def do_process_response(self, request, response):
		# Can't do traffic analysis if there is no session state.
		if getattr(request, "session", None) == None:
			return response
		
		# Assume the ua has been set in the request handler and ignore
		# requests from robots.
		if getattr(request, "ua", None) == None:
			return response
		if request.ua["typ"] == "Robot":
			return response
		
		# If the view does not have an explicit goal on either the request or response...
		if getattr(request, "goal", None) == None and getattr(response, "goal", None) == None:
			# Ignore AJAX requests.
			if request.is_ajax():
				return response

			# Ignore typically static content.
			if response["Content-Type"] in ("application/javascript", 'text/css', 'image/gif', 'image/png', 'image/jpeg', 'application/octet-stream'):
				return response
			
		# If the goal has been set explicitly to none, don't record.
		if getattr(request, "goal", True) == None or getattr(response, "goal", True) == None:
			return response
		
		rec = LiveRecord()
		
		if request.user.is_authenticated():
			rec.user = request.user
			
		if SESSION_COOKIE_NAME in request.COOKIES:
			rec.session_key = request.COOKIES[SESSION_COOKIE_NAME].strip()
			
			# tamper check
			a, b = rec.session_key[0:8], rec.session_key[8:]
			if md5_constructor(a + settings.SECRET_KEY).hexdigest() != b:
				raise SuspiciousOperation("User tampered with traffic session cookie.")
		else:
			try:
				pid = os.getpid() # idea to use pid from Django session framework
			except AttributeError:
				# No getpid() in Jython, for example
				pid = 1
			sk_a = md5_constructor(str(pid) + str(time.time()) + ''.join(chr(random.randint(0, 255)) for x in xrange(16))).hexdigest()[0:8]
			sk_b = md5_constructor(sk_a + settings.SECRET_KEY).hexdigest()
			rec.session_key = sk_a + sk_b
			
		if rec.session_key:
			max_age = 60*60*24 * 30
			expires_time = time.time() + max_age
			response.set_cookie(SESSION_COOKIE_NAME,
					rec.session_key, max_age=max_age,
					expires=cookie_date(expires_time), domain=settings.SESSION_COOKIE_DOMAIN,
					path=settings.SESSION_COOKIE_PATH,
					secure=settings.SESSION_COOKIE_SECURE or None)

		rec.path = request.path[0:64]
		view_name, view_args, view_kwargs = getattr(request, "trafficanalysis_view_info", ("", (), {}))
		rec.view = view_name[0:64]
		rec.ua = request.META.get("HTTP_USER_AGENT", "").strip()[0:64]
		rec.referrer = request.META.get("HTTP_REFERER", "").strip()[0:64]
		if rec.referrer.startswith(request.build_absolute_uri("/")):
			rec.referrer = None
		rec.ipaddr = request.META.get("REMOTE_ADDR", "").strip()[0:15]
		rec.response_code = response.status_code
		
		properties = collections.OrderedDict() # so that user-specified data is first so it truncates last
		for rr in (request, response):
			extra = getattr(rr, "goal", { })
			if "goal" in extra:
				rec.goal = extra["goal"]
				del extra["goal"]
			properties.update(extra)
		properties.update(view_kwargs)
		properties.update(collections.OrderedDict( ("view_arg_%d" % x[0], str(x[1])) for x in enumerate(view_args) ))		
		rec.properties = urllib.urlencode(properties)[0:128]

		rec.save()
	
		return response

