from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist

from popvox.models import *

from settings import SITE_ROOT_URL

def bill_js(request):
	return render_to_response('popvox/widgets/bill.js', {
		"siteroot": SITE_ROOT_URL,
		"bill": get_object_or_404(Bill, id=request.GET["bill"]) if "bill" in request.GET else None
	}, context_instance=RequestContext(request))


