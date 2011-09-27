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
	
	if request.GET.get("start_type", "") not in ("path", "view", "goal"):
		return HttpResponseBadRequest("Invalid value.")
	if request.GET.get("goal_type", "") not in ("", "path", "view", "goal"):
		return HttpResponseBadRequest("Invalid value.")

	# get every hit to the start page
	hits = Hit.objects.filter(**{request.GET["start_type"]: request.GET["start_value"]}).only("id", "session_key")
		
	# follow each hit a certain number of steps
	depth = int(request.GET.get("depth", 5))
	def new_item(): return { "count": 0, "next": { }, "converted": 0 }
	trail = new_item()
	trail["label"] = request.GET["start_value"]
	for hit in hits:
		trail_position = trail
		trail_position["count"] += 1
		parents = [trail_position]
		
		for next in (list(Hit.objects.filter(session_key=hit.session_key, id__gt=hit.id).order_by('id')) + [None])[0:depth]:
			if next == None:
				pathkey = "EXIT"
			else:
				pathkey = next.goal
				if not pathkey:
					pathkey = next.view
			
			if not pathkey in trail_position["next"]: trail_position["next"][pathkey] = new_item()
			trail_position = trail_position["next"][pathkey]
			trail_position["count"] += 1
			parents.append(trail_position)
			
			if next != None and request.GET.get("goal_type", "") != "":
				if getattr(next, request.GET.get("goal_type")) == request.GET.get("goal_value", ""):
					for parent in parents:
						parent["converted"] += 1
					break
			
	def fixup(kv):
		kv[1]["label"] = kv[0]
		condense(kv[1])
		return kv[1]
	def condense(pathitem):
		for k, v in pathitem["next"].items():
			if k not in ("EXIT","OTHER") and v["count"] < trail["count"]/50:
				if not "OTHER" in pathitem["next"]: pathitem["next"]["OTHER"] = new_item()
				pathitem["next"]["OTHER"]["count"] += v["count"]
				pathitem["next"]["OTHER"]["converted"] += v["converted"]
				del pathitem["next"][k]
		pathitem["next"] = [fixup(kv) for kv in pathitem["next"].items()]
		pathitem["next"].sort(key = lambda x : x["count"], reverse=True)
	condense(trail)
			
	return trail
