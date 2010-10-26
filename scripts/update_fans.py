#!/usr/bin/python

import sys, os
sys.path.insert(0, ".")

os.environ['DJANGO_SETTINGS_MODULE'] = "settings"

import settings
from popvox.models import Org

for org in Org.objects.filter(visible=True):
	if org.twittername == "":
		org.twittername = None
	if org.facebookurl == "":
		org.facebookurl = None
	
	# TODO: We don't really want this because if an org goes from
	# having a page to not having a page, then we want to clear
	# the count record. But it makes it go faster when run remotely.
	if settings.DEBUG and org.twittername == None and org.facebookurl == None:
		continue
		
	org.sync_external_members()

