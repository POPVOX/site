from django.db import models
from django.contrib.auth.models import User
from django.core.urlresolvers import resolve

from settings import SITE_ROOT_URL

import base64
import cPickle

from datetime import datetime

from uasparser import UASparser  
uas_parser = UASparser(update_interval = None)

class LiveRecord(models.Model):
	"""The LiveRecord table is intended to record data as it streams in and should
	have a fast write time, so there are no extra indexes. Because many fields are fixed-length,
	the encoding of the data in each of these fields must be robust to truncation."""
	
	time = models.DateTimeField(auto_now_add=True)

	session_key = models.CharField(max_length=40)
	user = models.ForeignKey(User, blank=True, null=True)

	path = models.CharField(max_length=64) # request path
	view = models.CharField(max_length=64) # the name of the view class handling the request
	goal = models.CharField(max_length=64) # custom event name
	ua = models.CharField(max_length=64)
	referrer = models.CharField(max_length=64, blank=True, null=True)
	ipaddr = models.CharField(max_length=15)
	response_code = models.IntegerField()
	properties = models.CharField(max_length=128) # urlencoded

	batch = models.IntegerField(blank=True, null=True) # helps to move this to an indexed table

class Hit(models.Model):
	"""The Hit table is just an indexed version of the LiveRecord populated by the trafficanalysis_index management command."""
	
	time = models.DateTimeField(db_index=True)

	session_key = models.CharField(max_length=40, db_index=True)
	user = models.ForeignKey(User, blank=True, null=True, db_index=True)

	path = models.CharField(max_length=64, db_index=True) # request path
	view = models.CharField(max_length=64, db_index=True) # the name of the view class handling the request
	goal = models.CharField(max_length=64, db_index=True) # custom event name
	referrer = models.CharField(max_length=64, blank=True, null=True, db_index=True)
	ipaddr = models.CharField(max_length=15)
	response_code = models.IntegerField()
	properties = models.CharField(max_length=128) # urlencoded

