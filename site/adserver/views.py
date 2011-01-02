from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.views.generic.simple import direct_to_template
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django import forms

from models import *

def click(request):
	impr = get_object_or_404(ImpressionBlock, id=request.GET["imx"])
	
	# atomic increments
	ImpressionBlock.objects.filter(id=request.GET["imx"]).update(clicks=F('clicks')+1, clickcost=F("clickcost")+impr.cpccost)
	
	return HttpResponseRedirect(impr.banner.targeturl)

