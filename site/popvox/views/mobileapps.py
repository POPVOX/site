from django.http import HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist

from popvox.models import Bill
from popvox import govtrack

import collections

def ipad_billreader_welcome(request):
	return HttpResponse("Welcome!")

def ipad_billreader_report(request):
	bill = get_object_or_404(Bill, id=request.GET.get('bill', 0))

	orgs = collections.OrderedDict([("+", { }), ("-", { }), ("0", { })])
	for pos in bill.campaign_positions():
		p = pos.position
		if not pos.campaign.org in orgs[p]:
			orgs[p][pos.campaign.org] = pos
	if len(orgs["+"]) + len(orgs["-"]) > 0:
		org_support_percent = 100 * len(orgs["+"]) / (len(orgs["+"]) + len(orgs["-"]))
	else:
		org_support_percent = None
	
	for k in orgs:
		orgs[k] = list(orgs[k].items())
		orgs[k].sort(key = lambda x : -x[0].fan_count_sort_order)
		
	cosponsors = { "D": [], "R": [], "I": [] }
	for m in bill.cosponsors.all():
		cosponsors[m.party()].append(m)
	if bill.cosponsors.all().count() == 0:
		cosponsors_bar = -1
	else:
		cosponsors_bar = int( float(len(cosponsors["R"]))/float(bill.cosponsors.all().count()) *323 )
	
	# order the groups by count
	cosponsors = list(cosponsors.items())
	cosponsors.sort(key = lambda kv : -len(kv[1]))
	cosponsors = collections.OrderedDict(cosponsors)

	return render_to_response('popvox/mobile/report.html', {
			'bill': bill,
			"cosponsors": cosponsors,
			"cosponsors_bar": cosponsors_bar,
			"orgs": [kv for kv in orgs.items() if len(kv[1]) != 0],
			"org_support_percent": org_support_percent,
			"org_support_oppose_count": (len(orgs["+"]), len(orgs["-"])),
			"stateabbrs": 
				[ (abbr, govtrack.statenames[abbr]) for abbr in govtrack.stateabbrs],
			"statereps": govtrack.getStateReps(),
		}, context_instance=RequestContext(request))
