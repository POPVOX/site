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
	{
		"bill": Bill.objects.get(id=19780), # auction remaining tarp
		"savings": 166,
		"category_name": "Financial Services",
		"category_icon": "i_financial",
		"source": "Americans for Prosperity",
		"source_url": "http://www.americansforprosperity.org/files/Policy_Paper_JSC_Recommendations.pdf",
	},
	#{
	#	"bill": Bill.objects.get(id=19837), # eliminate student loans
	#	"savings": 43,
	#	"category_name": "Education",
	#	"category_icon": "i_edu",
	#	"source": "The President's National Commission on Fiscal Responsibility and Reform",
	#	"source_url": "http://www.fiscalcommission.gov/sites/fiscalcommission.gov/files/documents/TheMomentofTruth12_1_2010.pdf",
	#},
	{
		"bill": Bill.objects.get(id=19838), # cut aircraft carriers
		"savings": 7,
		"category_name": "Defense",
		"category_icon": "i_defense",
		"source": "Project on Government Oversight",
		"source_url": "http://www.pogo.org/pogo-files/reports/national-security/spending-less-spending-smarter-ns-wds-20110721.html#Cancel%20one%20version%20of%20the%20Littoral%20Combat%20Ship%20%28LCS%29",
	},
	{
		"bill": Bill.objects.get(id=19278), # currency optimization
		"savings": 1.8,
		"category_name": "Financial Services",
		"category_icon": "i_financial",
		"title": "Currency Optimization, Innovation, and National Savings Act",
		"description": "Improves the circulation of $1 coins, to remove barrier to the circulation of such coins, and for other purposes, reducing the deficit by $1.8 billion over ten years. This is a bill in Congress and the Super Committee may be considering it.",
		"source": "Rep. David Schweikert",
		"source_url": "https://www.popvox.com/bills/us/112/hr2977",
	},
	{
		"bill": Bill.objects.get(id=19839), # financial crisis responsibility
		"savings": 71,
		"category_name": "Tax",
		"category_icon": "i_tax",
		"source": "Congressional Progressive Caucus",
		"source_url": "http://cpc.grijalva.house.gov/index.cfm?sectionid=79&sectiontree=5,79",
	},
	{
		"bill": Bill.objects.get(id=19840), # eliminate commodity crop
		"savings": 51,
		"category_name": "Agriculture",
		"category_icon": "i_farm",
		"source": "Taxpayers for Common Sense",
		"source_url": "http://www.taxpayer.net/user_uploads/file/FederalBudget/2011/TCS_Super_Cuts_Sept2011.pdf",
	},
	{
		"bill": Bill.objects.get(id=19841), # modify mortgage interest
		"savings": 390,
		"category_name": "Tax",
		"category_icon": "i_tax",
		"source": "Taxpayers for Common Sense",
		"source_url": "http://www.taxpayer.net/user_uploads/file/FederalBudget/2011/TCS_Super_Cuts_Sept2011.pdf",
	},
	{
		"bill": Bill.objects.get(id=19842), # reform and reduce
		"savings": 100,
		"category_name": "Government Reform",
		"category_icon": "i_govreform",
		"source": "Americans for Prosperity",
		"source_url": "http://www.americansforprosperity.org/files/Policy_Paper_JSC_Recommendations.pdf",
	},
	{
		"bill": Bill.objects.get(id=19701), # Employee Misclassification Act
		"title": "Employee Misclassification Act",
		"description": "Requires employers to keep records of non-employees who perform labor or services for remuneration and to provide a special penalty for employers who misclassify employees as non-employees.",
		"savings": 57,
		"category_name": "Tax",
		"category_icon": "i_tax",
		"source": "House Education & Labor Committee Minority",
		"source_url": "http://www.democraticleader.gov/pdf/EducationWorkforce101311.pdf",
	},
	{
		"bill": Bill.objects.get(id=17180), # New Spectrum Auction
		"title": "Auction New Spectrum",
		"description": "Establishes the sense of Congress that Congress should enact, and the President should sign, bipartisan legislation to strengthen public safety and to enhance wireless communications.",
		"savings": 6,
		"category_name": "Wireless Spectrum",
		"category_icon": "i_wireless",
		"source": "Energy & Commerce Committee Minority, the President's proposal, and the Republican Budget",
		"source_url": "https://www.popvox.com/bills/us/112/s911",
	},
	{
		"bill": Bill.objects.get(id=14246), # Preserve Access to Affordable Generics
		"title": "Preserve Access to Affordable Generics",
		"description": "Limits the ability for brand name drug companies to pay generics manufacturers to delay their entry into the market",
		"savings": 3,
		"category_name": "Health",
		"category_icon": "i_health",
		"source": "Energy & Commerce Committee Minority and the President's Plan",
		"source_url": "https://www.popvox.com/bills/us/112/s27",
	},
	{
		"bill": Bill.objects.get(id=19874), # Big Bank fee
		"savings": 20,
		"category_name": "Financial Services",
		"category_icon": "i_financial",
		"source": "House Financial Services Minority",
		"source_url": "http://www.democraticleader.gov/pdf/FinancialServices101311.pdf",
	},
	{
		"bill": Bill.objects.get(id=15883), # "Internet Gambling Regulation, Consumer Protection, and Enforcement Act
		"title": "Regulate and Tax Internet Gambling",
		"description": "Legalizes, regulates and taxes Internet gambling.",
		"savings": 42,
		"category_name": "Financial Services",
		"category_icon": "i_financial",
		"source": "House Financial Services Committee Minority",
		"source_url": "http://www.democraticleader.gov/pdf/FinancialServices101311.pdf",
	},
	{
		"bill": Bill.objects.get(id=19875), # Tax carried interest as ordinary income
		"savings": 13,
		"category_name": "Tax",
		"category_icon": "i_tax",
		"source": u"President\u2019s proposal",
		"source_url": "http://www.whitehouse.gov/sites/default/files/omb/budget/fy2012/assets/jointcommitteereport.pdf",
	},
	{
		"bill": Bill.objects.get(id=19876), # End oil and gas tax preferences
		"savings": 42,
		"category_name": "Tax",
		"category_icon": "i_tax",
		"source": u"President\u2019s proposal",
		"source_url": "http://www.whitehouse.gov/sites/default/files/omb/budget/fy2012/assets/jointcommitteereport.pdf",
	},
	{
		"bill": Bill.objects.get(id=19877), # Derivatives and Speculation Tax
		"savings": 432,
		"category_name": "Tax",
		"category_icon": "i_tax",
		"source": "Congressional Progressive Caucus",
		"source_url": "http://cpc.grijalva.house.gov/index.cfm?sectionid=79&sectiontree=5,79",
	},
	{
		"bill": Bill.objects.get(id=19878), # Chained CPI
		"savings": 299,
		"category_name": "Government Reform",
		"category_icon": "i_govreform",
		"source": "Bowles-Simpson recommendations",
		"source_url": "http://www.momentoftruthproject.org/sites/default/files/MeasuringUp5_11_2011.pdf",
	},
]
for bill in supercommittee_bill_list:
	if not "title" in bill:
		bill["title"] = bill["bill"].nicename.replace(" (Proposal to Super Committee)", "")
	if not "description" in bill:
		bill["description"] = bill["bill"].description

supercommittee_bill_list_ids = [bill["bill"].id for bill in supercommittee_bill_list]
	
def supercommittee(request):
	bill_list = list(supercommittee_bill_list) # clone
	for i in xrange(len(bill_list)):
		bill_list[i] = dict(bill_list[i]) # clone
		bill = bill_list[i]
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

