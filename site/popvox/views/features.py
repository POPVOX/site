from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.core.cache import cache

from popvox.models import Bill
from popvox.views.bills import bill_statistics, get_default_statistics_context

def supercommittee(request):
	bill_list = [
		{
			"bill": Bill.objects.get(id=19773),
			"savings": 453,
			"category_name": "Tax",
			"category_icon": "i_tax",
		},
		{
			"bill": Bill.objects.get(id=19774),
			"savings": 106,
			"category_name": "Tax",
			"category_icon": "i_tax",
		},
		{
			"bill": Bill.objects.get(id=19775),
			"savings": 410,
			"category_name": "Tax",
			"category_icon": "i_tax",
		},
		{
			"bill": Bill.objects.get(id=19776),
			"savings": 240,
			"category_name": "Health",
			"category_icon": "i_health",
		},
		{
			"bill": Bill.objects.get(id=19777),
			"savings": 17,
			"category_name": "Health",
			"category_icon": "i_health",
		},
		{
			"bill": Bill.objects.get(id=19778),
			"savings": 73,
			"category_name": "Defense",
			"category_icon": "i_defense",
		},
		{
			"bill": Bill.objects.get(id=19357),
			"savings": 100,
			"category_name": "Government Reform",
			"category_icon": "i_govreform",
			"title": "Reducing the Size of the Federal Government Through Attrition",
			"description": "Reduces the total number of federal employees by 10 percent over a five year period, lowering the deficit by $100 billion over 10 years. This is a proposal the Supercommittee may be considering and was proposed by Americans for Prosperity."
		},
		{
			"bill": Bill.objects.get(id=19780),
			"savings": 166,
			"category_name": "Financial Services",
			"category_icon": "i_financial",
		},
	]

	for bill in bill_list:
		if not "title" in bill:
			bill["title"] = bill["bill"].nicename
		if not "description" in bill:
			bill["description"] = bill["bill"].description
		bill["sentiment"] = bill_statistics(bill["bill"], "POPVOX Nation", "POPVOX Nation")
		if bill["sentiment"]:
			bill["sentiment"]["scaled_pro"] = 150 * bill["sentiment"]["pro_pct"] / 100
			bill["sentiment"]["scaled_con"] = 150 - bill["sentiment"]["scaled_pro"]
	
	return render(request, "popvox/features/supercommittee.html",
		{
			"bills": bill_list
		})

