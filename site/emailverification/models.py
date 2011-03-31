from django.db import models
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse

import settings

import base64
import pickle
import random
from datetime import datetime

CODE_LENGTH = 16
EXPIRATION_DAYS = 7

class Record(models.Model):
	"""A record is for an email address pending verification, plus the action to take."""
	email = models.EmailField(db_index=True)
	code = models.CharField(max_length=CODE_LENGTH, db_index=True)
	searchkey = models.CharField(max_length=127, blank=True, null=True, db_index=True)
	action = models.TextField()
	created = models.DateTimeField(auto_now_add=True)
	
	def __unicode__(self):
		try:
			a = unicode(self.get_action())
		except:
			a = "(invalid action data)"
		return self.email + ": " + a
		
	def set_code(self):
		self.code = ''.join(random.choice(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z")) for x in range(CODE_LENGTH))

	def set_action(self, action):
		self.action = base64.encodestring(pickle.dumps(action))
		
	def get_action(self):
		return pickle.loads(base64.decodestring(self.action))

	def is_expired(self):
		if (datetime.now() - self.created).days >= EXPIRATION_DAYS:
			return True
		return False
	
	def url(self):
		return getattr(settings, 'SITE_ROOT_URL', "http://%s" % Site.objects.get_current().domain) \
			+ reverse("emailverification.views.processcode", args=[self.code])

