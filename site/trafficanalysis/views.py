from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.contrib.auth.decorators import login_required

from jquery.ajax import json_response

from models import Hit

@login_required
def report(request):
	if not request.user.is_superuser:
		return HttpResponseForbidden()
	return render_to_response("trafficanalysis/report.html")

@json_response
@login_required
def report_data(request):
	if not request.user.is_superuser:
		return HttpResponseForbidden()
	
	if request.GET["start_type"] not in ("path", "view", "goal"):
		return HttpResponseBadRequest("Invalid value.")
	
	# get every hit to the start page
	hits = Hit.objects.filter(**{request.GET["start_type"]: request.GET["start_value"]}).only("id", "session_key")
		
	# follow each hit a certain number of steps
	depth = int(request.GET.get("depth", 5))
	trail = { "count": 0, "next": { } }
	for hit in hits:
		trail_position = trail
		trail_position["count"] += 1
		
		for next in (list(Hit.objects.filter(session_key=hit.session_key, id__gt=hit.id).order_by('id')) + [None])[0:depth]:
			if next == None:
				pathkey = "EXIT"
			else:
				pathkey = next.path
			
			if not pathkey in trail_position["next"]: trail_position["next"][pathkey] = { "count": 0, "next": { } }
			trail_position = trail_position["next"][pathkey]
			trail_position["count"] += 1
			
			
	return trail
