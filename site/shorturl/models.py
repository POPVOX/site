from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.core.urlresolvers import reverse

import settings

import base64
import pickle
import random

CODE_LENGTH = getattr(settings, "SHORTURL_LENGTH", 6)

class RecordManager(models.Manager):
	def parseargs(self, kwargs, makeownernone=False):
		newargs = {}
		for k, v in kwargs.items():
			if k == "target":
				newargs["target_content_type"] = ContentType.objects.get_for_model(v)
				newargs["target_object_id"] = v.id
			elif k == "owner":
				if v == None:
					newargs["owner_content_type"] = None
					newargs["owner_object_id"] = None
				else:
					newargs["owner_content_type"] = ContentType.objects.get_for_model(v)
					newargs["owner_object_id"] = v.id
			else:
				newargs[k] = v
		if not "owner" in kwargs and makeownernone:
			newargs["owner_content_type"] = None
			newargs["owner_object_id"] = None
		return newargs
		
	def get(self, **kwargs):
		return super(RecordManager, self).get(**self.parseargs(kwargs))
	def filter(self, **kwargs):
		return super(RecordManager, self).filter(**self.parseargs(kwargs))
	def get_or_create(self, **kwargs):
		return super(RecordManager, self).get_or_create(**self.parseargs(kwargs, makeownernone=True))

class Record(models.Model):
	code = models.CharField(max_length=CODE_LENGTH, db_index=True)
	created = models.DateTimeField(auto_now_add=True)
	
	target_content_type = models.ForeignKey(ContentType, related_name="shorturlsto")
	target_object_id = models.PositiveIntegerField()
	target = generic.GenericForeignKey('target_content_type', 'target_object_id')
	
	owner_content_type = models.ForeignKey(ContentType, blank=True, null=True, db_index=True, related_name="shorturlsof")
	owner_object_id = models.PositiveIntegerField(blank=True, null=True, db_index=True)
	owner = generic.GenericForeignKey('owner_content_type', 'owner_object_id')

	hits = models.PositiveIntegerField(default=0)
	completions = models.PositiveIntegerField(default=0)
	
	###
	objects = RecordManager()
	###
	
	class Meta:
		ordering = ["-created"]
		unique_together = ["target_content_type", "target_object_id", "owner_content_type", "owner_object_id"]
	
	def __unicode__(self):
		ret = unicode(self.target_content_type) + u" (" + unicode(self.target)[0:60] + u")"
		if self.owner != None:
			ret += u" <= " + unicode(self.owner_content_type) + u" (" + unicode(self.owner)[0:30] + u")"
		#ret += u" (" + self.url() + u")"
		return ret
		
	def save(self, *args, **kwargs):
		if self.code == None or self.code == "":
			self.set_code()
		super(Record, self).save(*args, **kwargs)
		
	def set_code(self):
		for i in xrange(10):
			self.code = ''.join(random.choice(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z")) for x in range(CODE_LENGTH))
			if not Record.objects.filter(code=self.code).exists():
				break
			if i == 10:
				raise Exception("URL space is full.")

	def increment_hits(self):
		self.hits = models.F('hits') + 1
		self.save()
		
	def increment_completions(self):
		self.completions = models.F('completions') + 1
		self.save()

	def url(self):
		if hasattr(settings, 'SITE_SHORT_ROOT_URL'):
			return getattr(settings, 'SITE_SHORT_ROOT_URL') + "/" + self.code
		return getattr(settings, 'SITE_ROOT_URL') + self.get_absolute_url()
		
	def get_absolute_url(self):
		return reverse("shorturl.views.redirect", args=[self.code])

class SimpleRedirect(models.Model):
	url = models.CharField(max_length=128, blank=True, null=True)
	target_content_type = models.ForeignKey(ContentType, blank=True, null=True, related_name="simpleshorturlsto")
	target_object_id = models.PositiveIntegerField(blank=True, null=True)
	target = generic.GenericForeignKey('target_content_type', 'target_object_id')
	meta_pickled = models.TextField(blank=True)
	created = models.DateTimeField(auto_now_add=True)
	
	def __unicode__(self):
		if self.url:
			return self.url + " (" + repr(self.meta()) + ")"
		if self.target:
			return unicode(self.target) + " (" + repr(self.meta()) + ")"
		return "?"

	def get_absolute_url(self):
		return self.url

	def set_meta(self, meta):
		if meta == None:
			self.meta_pickled = ""
		else:
			self.meta_pickled = base64.encodestring(pickle.dumps(meta))
		
	def meta(self):
		if self.meta_pickled == "":
			return None
		return pickle.loads(base64.decodestring(self.meta_pickled))


