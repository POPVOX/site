from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import get_object_or_404
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from django.db.models import F

from models import *
from adselection import show_banner

def banner(request, formatid):
	format = get_object_or_404(Format, id=formatid)
	
	targets = [get_object_or_404(Target, key=target)
		for target in request.GET.get("target", "").split(",") if target != ""]
	
	response = HttpResponse(
		show_banner(format, request, RequestContext(request), targets, request.META.get('HTTP_REFERER', '-')),
		mimetype="text/html"
		)
	response['Cache-Control'] = 'no-cache'
	return response

def click(request):
	impr = get_object_or_404(Impression, code=request.GET["imx"])
	ImpressionBlock.objects.filter(id=impr.block.id).update(clicks=F('clicks')+1, clickcost=F("clickcost")+impr.cpccost)
	
	return HttpResponseRedirect(impr.block.banner.targeturl)

