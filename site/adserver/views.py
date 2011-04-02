from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import get_object_or_404
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.template.defaultfilters import escapejs

import re

from models import *
from adselection import show_banner

def banner(request, formatid):
	# To comply with Do-Not-Track, we should not set a session cookie.
	# To prevent this, we'll clear the session state ahead of time.
	if request.META.get("DNT", "0") == "1":
		delattr(request, "session")
		
	format = get_object_or_404(Format, id=formatid)
	
	targets = [get_object_or_404(Target, key=target)
		for target in request.GET.get("targets", "").split(",") if target != ""]
	
	# In the database, store the path where the banner is shown based
	# on the HTTP_REFERER, but to save space in the field translate
	# http://www.example.com/abc to example.com::abc.
	path = request.META.get('HTTP_REFERER', '-')
	path = re.sub(r"^https?://(www\.)?([^/:]+)(:\d+)?", r"\2::", path)

	html = show_banner(format, request, RequestContext(request), targets, path)
	
	if request.GET.get("method", '') == "":
		response = HttpResponse(html, mimetype="text/html")
	elif request.GET.get("method", '') == "js":
		js = "document.write(\"" + escapejs(html) + "\");"
		response = HttpResponse(js, mimetype="text/javascript")
	else:
		raise Http404()
	response['Cache-Control'] = 'no-cache'

	response.goal = None
	
	return response

def click(request):
	impr = get_object_or_404(Impression, code=request.GET["imx"])
	ImpressionBlock.objects.filter(id=impr.block.id).update(clicks=F('clicks')+1, clickcost=F("clickcost")+impr.cpccost)

	request.goal = None
	
	return HttpResponseRedirect(impr.targeturl)

