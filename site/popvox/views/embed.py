from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist

from popvox.models import *

def org_check_api_key(request):
	api_key = request.GET.get("api_key", "")
	try:
		org = Org.objects.get(api_key=api_key)
		return HttpResponse("Great! That is the correct integration key for " + org.name + ".", mimetype="text/plain")
	except Org.DoesNotExist:
		return HttpResponse("That is not a correct organization integration key.", mimetype="text/plain")

def salsa_legagenda(request):
	api_key = request.GET.get("api_key", "")
	org = get_object_or_404(Org, api_key=api_key)
	return render_to_response("popvox/embed/salsa_legagenda.html", {
		"org": org,
	}, context_instance=RequestContext(request))
	
