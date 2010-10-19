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

from popvox.models import *

def staticpage(request, page):
	if page == "":
		page = "homepage"
		if request.user.is_authenticated() and request.user.get_profile() != None:
			return HttpResponseRedirect("/home")
			
	page = page.replace("/", "_") # map URL structure to static files
			
	try:
		return direct_to_template(request, template="static/%s.html" % page)
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

