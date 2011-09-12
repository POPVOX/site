from django.http import HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist

from popvox.models import Bill
from popvox import govtrack

def ipad_billreader_welcome(request):
	return HttpResponse("Welcome!")

def ipad_billreader_report(request):
	bill = get_object_or_404(Bill, id=request.GET.get('bill', 0))

	orgs = { "+": { }, "-": { }, "0": { } }
	for pos in bill.campaign_positions():
		p = pos.position
		if not pos.campaign.org in orgs[p]:
			orgs[p][pos.campaign.org] = pos
	for k in orgs:
		orgs[k] = list(orgs[k].items())
		orgs[k].sort(key = lambda x : x[0].name.replace("The ", ""))

	return render_to_response('popvox/mobile/report.html', {
			'bill': bill,
			"orgs": orgs.items(),
			"stateabbrs": 
				[ (abbr, govtrack.statenames[abbr]) for abbr in govtrack.stateabbrs],
			"statereps": govtrack.getStateReps(),
		}, context_instance=RequestContext(request))
