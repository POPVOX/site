from django.db import models
from django.contrib.auth.models import User
from django.core.urlresolvers import resolve

from settings import SITE_ROOT_URL

import base64
import pickle

from datetime import datetime

from uasparser import UASparser  
uas_parser = UASparser(update_interval = None)

class Session(models.Model):
	"""A user session whose path through the website we are tracking."""
	
	# the starting and ending time (last seen time) of the session
	start = models.DateTimeField(auto_now_add=True)
	end = models.DateTimeField(auto_now=True)
	
	# The user associated with the session, if any, so we can resume
	# a previous session.
	user = models.ForeignKey(User, blank=True, null=True, db_index=True)
	
	# The path is a list of PathEntry objects.
	ua = models.TextField(default="") # last seen user agent sring, parsed and pickled
	path = models.TextField(default="")
	
	class Meta:
		ordering = ["-end"]
		
	def set_ua(self, request):
		if not "HTTP_USER_AGENT" in request.META:
			return None
		ua = uas_parser.parse(request.META["HTTP_USER_AGENT"])
		self.ua = base64.b64encode(pickle.dumps(ua))
		return ua
	def get_ua(self):
		return pickle.loads(base64.b64decode(self.ua))
			
	def path_append(self, pe):
		self.path += base64.b64encode(pickle.dumps(pe)) + "\n"
	def get_path(self):
		return (pickle.loads(base64.b64decode(pe)) for pe in self.path.split("\n") if pe != "")
	
class PathEntry:
	time = None
	
	path = None # path string
	view = None # the name of the class handling the request
	method = None # GET, POST, ...
	qs = None # querystring dictionary
	loggedin = False # true/false if user is logged in at the time of this request

	referrer = None # referrer string
	ip = None # string IP address of user
	
	rcode = None # integer response code of the request, i.e. 200

	def __init__(self, request, response):
		self.time = datetime.now()
		self.path = request.path
		try:
			self.view, self.viewargs, self.viewkwargs = resolve(self.path)
			self.view = self.view.__module__ + "." + self.view.__name__
		except:
			pass
		self.method = request.method
		self.qs = dict(request.GET)
		self.loggedin = (request.user.is_authenticated())
		if "HTTP_REFERER" in request.META:
			self.referrer = request.META["HTTP_REFERER"]
			if self.referrer[0:len(SITE_ROOT_URL)+1] == SITE_ROOT_URL + "/":
				self.referrer = None
		if "REMOTE_ADDR" in request.META:
			self.ip = request.META["REMOTE_ADDR"]
		self.rcode = response.status_code
		
		# Copy any properties set in the goal attribute of the
		# request and response objects into attributes of this object.
		for rr in (request, response):
			extra = getattr(rr, "goal", { })
			for k, v in extra.items():
				setattr(self, k, v)

	def __repr__(self):
		return unicode(self.__dict__)

