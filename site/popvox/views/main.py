from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.views.generic.simple import direct_to_template
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django import forms

from jquery.ajax import json_response, ajax_fieldupdate_request, sanitize_html

import re
from xml.dom import minidom
import urllib
from datetime import datetime, timedelta

from popvox.models import *

def staticpage(request, page):
	varbls = { }

	if page == "":
		page = "homepage"
		varbls["news"] = get_news()
		#if request.user.is_authenticated():
		#	return HttpResponseRedirect("/home")
			
	page = page.replace("/", "_") # map URL structure to static files
			
	try:
		return render_to_response("static/%s.html" % page, varbls, context_instance=RequestContext(request))
	except TemplateDoesNotExist:
		raise Http404()

@json_response
def subscribe_to_mail_list(request):
	from django import forms
	email = forms.EmailField(required=False).clean(request.POST["email"]) # raises ValidationException on error
	u = MailListUser.objects.filter(email=email)
	if len(u) > 0:
		return { "status": "fail", "msg": "You are already on our list, but thanks!" }
	if request.POST["validate"] == "validate":
		return { "status": "success" }
	u = MailListUser()
	u.email = email
	u.save()
	return { "status": "success" }


_news_items = None
_news_updated = None
def get_news():
	global _news_items
	global _news_updated
	# Load the blog RSS feed for items tagged frontpage.
	if _news_items == None or datetime.now() - _news_updated > timedelta(minutes=60):
		import feedparser
		feed = feedparser.parse("http://www.popvox.com/blog/atom")
		_news_items = [{"link":entry.link, "title":entry.title, "date":datetime(*entry.updated_parsed[0:6]), "content":entry.content[0].value} for entry in feed["entries"][0:4]]
		_news_updated = datetime.now()
	return _news_items

