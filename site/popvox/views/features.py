from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.core.cache import cache

from popvox.models import Bill, UserComment
from popvox.views.bills import bill_statistics, get_default_statistics_context

supercommittee_bill_list = [
	{
		"bill": Bill.objects.get(id=19773), # millionaries
		"savings": 453,
		"category_name": "Tax",
		"category_icon": "i_tax",
		"source": "House Ways & Means Minority",
		"source_url": "http://www.democraticleader.gov/pdf/WaysMeans101311.pdf",
	},
	{
		"bill": Bill.objects.get(id=19774), # estate tax
		"savings": 106,
		"category_name": "Tax",
		"category_icon": "i_tax",
		"source": u"The President\u2019s Proposal",
		"source_url": "http://www.whitehouse.gov/sites/default/files/omb/budget/fy2012/assets/jointcommitteereport.pdf",
	},
	{
		"bill": Bill.objects.get(id=19775), # limit itemized deductions
		"savings": 410,
		"category_name": "Tax",
		"category_icon": "i_tax",
		"source": u"The President\u2019s Proposal",
		"source_url": "http://www.whitehouse.gov/sites/default/files/omb/budget/fy2012/assets/jointcommitteereport.pdf",
	},
	{
		"bill": Bill.objects.get(id=19776), # raising medicare premiums
		"savings": 240,
		"category_name": "Health",
		"category_icon": "i_health",
		"source": "Lieberman-Coburn Health Proposal",
		"source_url": "http://lieberman.senate.gov/index.cfm/issues-legislation/health-and-social-policy/saving-medicare-the-liebermancoburn-plan",
	},
	{
		"bill": Bill.objects.get(id=19777), # increasing tricare
		"savings": 17,
		"category_name": "Health",
		"category_icon": "i_health",
		"source": u"The President\u2019s Proposal",
		"source_url": "http://www.whitehouse.gov/sites/default/files/omb/budget/fy2012/assets/jointcommitteereport.pdf",
	},
	{
		"bill": Bill.objects.get(id=19778), # reducing spending on non-dod contracts
		"savings": 73,
		"category_name": "Defense",
		"category_icon": "i_defense",
		"title": "Reduce Spending on Non-DoD Federal Service Contractors by 15%",
		"source": "Project on Government Oversight",
		"source_url": "http://www.pogo.org/pogo-files/reports/national-security/spending-less-spending-smarter-ns-wds-20110721.html#Cancel%20one%20version%20of%20the%20Littoral%20Combat%20Ship%20%28LCS%29",
	},
	#{
	#	"bill": Bill.objects.get(id=19357), # attrition
	#	"savings": 100,
	#	"category_name": "Government Reform",
	#	"category_icon": "i_govreform",
	#	"title": "Reducing the Size of the Federal Government Through Attrition",
	#	"description": "Reduces the total number of federal employees by 10 percent over a five year period, lowering the deficit by $100 billion over 10 years. This is a proposal the Supercommittee may be considering and was proposed by Americans for Prosperity.",
	#	"source": "Americans for Prosperity",
	#	"source_url": "http://www.americansforprosperity.org/files/Policy_Paper_JSC_Recommendations.pdf",
	#},
	{
		"bill": Bill.objects.get(id=19780), # auction remaining tarp
		"savings": 166,
		"category_name": "Financial Services",
		"category_icon": "i_financial",
		"source": "Americans for Prosperity",
		"source_url": "http://www.americansforprosperity.org/files/Policy_Paper_JSC_Recommendations.pdf",
	},
]
supercommittee_bill_list_ids = [bill["bill"].id for bill in supercommittee_bill_list]
	
def supercommittee(request):
	bill_list = list(supercommittee_bill_list) # clone
	for i in xrange(len(bill_list)):
		bill_list[i] = dict(bill_list[i]) # clone
		bill = bill_list[i]
		if not "title" in bill:
			bill["title"] = bill["bill"].nicename.replace(" (Proposal to Super Committee)", "")
		if not "description" in bill:
			bill["description"] = bill["bill"].description
		bill["sentiment"] = bill_statistics(bill["bill"], "POPVOX Nation", "POPVOX Nation")
		if bill["sentiment"]:
			bill["sentiment"]["scaled_pro"] = 142 * bill["sentiment"]["pro_pct"] / 100
			bill["sentiment"]["scaled_con"] = 142 - bill["sentiment"]["scaled_pro"]
		if request.user.is_authenticated():
			try:
				c = UserComment.objects.get(user=request.user, bill=bill_list[i]["bill"])
				bill_list[i]["user_position"] = c.position
			except UserComment.DoesNotExist:
				pass
	
	return render(request, "popvox/features/supercommittee.html",
		{
			"bills": bill_list
		})

