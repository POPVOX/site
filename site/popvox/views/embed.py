from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist

from popvox.models import *

def salsa_legagenda(request, apikey):
	org = get_object_or_404(Org, slug="demo", visible=True)
	return render_to_response("popvox/embed/salsa_legagenda.html", {
		"org": org,
	}, context_instance=RequestContext(request))
	
