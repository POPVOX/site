from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render, get_object_or_404, render_to_response
from django.template import RequestContext
from django.core.cache import cache
from django.contrib.auth.decorators import user_passes_test

from popvox.views.main import strong_cache
from popvox.models import Bill, UserComment
from popvox.views.bills import bill_statistics, get_default_statistics_context
from utils import formatDateTime

from jquery.ajax import json_response, ajax_fieldupdate_request, sanitize_html

import urllib, json, pytz
from datetime import datetime

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
	
	{
		"bill": Bill.objects.get(id=20063), # Reinstate Superfund Tax
		"savings": 18,
		"category_name": "Tax",
		"category_icon": "i_tax",
		"source": u"President\u2019s proposal",
		"source_url": "http://www.whitehouse.gov/sites/default/files/omb/budget/fy2012/assets/jointcommitteereport.pdf",
	},
	{
		"bill": Bill.objects.get(id=20064), # Make .02% unemployment tax permanent
		"savings": 15,
		"category_name": "Tax",
		"category_icon": "i_tax",
		"source": u"President\u2019s proposal",
		"source_url": "http://www.whitehouse.gov/sites/default/files/omb/budget/fy2012/assets/jointcommitteereport.pdf",
	},
	{
		"bill": Bill.objects.get(id=20065), # Tort Reform
		"savings": 62,
		"category_name": "Health",
		"category_icon": "i_health",
		"source": "House Republicans Road Map Plan",
		"source_url": "http://www.roadmap.republicans.budget.house.gov/Plan/#Healthsecurity",
	},
	{
		"bill": Bill.objects.get(id=20066), # Raising Medicare cost-sharing
		"savings": 70,
		"category_name": "Health",
		"category_icon": "i_health",
		"source": "Lieberman-Coburn Health Proposal",
		"source_url": "http://lieberman.senate.gov/index.cfm/issues-legislation/health-and-social-policy/saving-medicare-the-liebermancoburn-plan",
	},
	{
		"bill": Bill.objects.get(id=20067), # Reducing Post-Acute care payments
		"savings": 42,
		"category_name": "Health",
		"category_icon": "i_health",
		"source": u"President\u2019s proposal",
		"source_url": "http://www.whitehouse.gov/sites/default/files/omb/budget/fy2012/assets/jointcommitteereport.pdf",
	},
	{
		"bill": Bill.objects.get(id=20068), # Raise Medicare eligibility age
		"savings": 124,
		"category_name": "Health",
		"category_icon": "i_health",
		"source": u"Lieberman-Coburn Health Proposal",
		"source_url": "http://lieberman.senate.gov/index.cfm/issues-legislation/health-and-social-policy/saving-medicare-the-liebermancoburn-plan",
	},
	{
		"bill": Bill.objects.get(id=20069), # Increasing aviation and security fees 
		"savings": 25,
		"category_name": "Aviation",
		"category_icon": "i_aviation",
		"source": u"President\u2019s proposal",
		"source_url": "http://www.whitehouse.gov/sites/default/files/omb/budget/fy2012/assets/jointcommitteereport.pdf",
	},
	{
		"bill": Bill.objects.get(id=20070), # Withdraw 20,000 troops from Europe 
		"savings": 30,
		"category_name": "Defense",
		"category_icon": "i_defense",
		"source": "Project on Government Oversight",
		"source_url": "http://www.pogo.org/pogo-files/reports/national-security/spending-less-spending-smarter-ns-wds-20110721.html#Cancel%20one%20version%20of%20the%20Littoral%20Combat%20Ship%20%28LCS%29",
	},
	{
		"bill": Bill.objects.get(id=15771), # Disposal of Excess Federal Lands Act
		"title": "Dispose of Excess Federal Lands",
		"savings": 1,
		"category_name": "Government Reform",
		"category_icon": "i_govreform",
		"source": "Rep. Chaffetz",
		"source_url": "http://chaffetz.house.gov/in-the-news/2011/03/chaffetz-introduces-federal-lands-disposal-bill-1.shtml",
	},
	{
		"bill": Bill.objects.get(id=15780), # Fairness in Taxation Act
		"title": "Fairness in Taxation Act",
		"savings": 873,
		"category_name": "Tax",
		"category_icon": "i_tax",
		"source": "Congressional Progressive Caucus",
		"source_url": "http://cpc.grijalva.house.gov/index.cfm?sectionid=79&sectiontree=5,79",
	},

	{
		"bill": Bill.objects.get(id=19935), # The Wall Street Trading and Speculators Tax Act  S. 1787 / H.R. 3313
		"title": "Impose a Tax on Certain Trading Transactions",
		"savings": 353,
		"category_name": "Tax",
		"category_icon": "i_tax",
		"source": "Joint Committee on Taxation",
		"source_url": "http://www.defazio.house.gov/index.php?option=com_content&view=article&id=736:memo-joint-tax-committee-finds-harkin-defazio-wall-street-trading-and-speculators-tax-generates-more-than-350-billion&catid=63:2011-news",
	},
]
for bill in supercommittee_bill_list:
	if not "title" in bill:
		bill["title"] = bill["bill"].nicename.replace(" (Proposal to Super Committee)", "")
	if not "description" in bill:
		bill["description"] = bill["bill"].description

supercommittee_bill_list_ids = [bill["bill"].id for bill in supercommittee_bill_list]

@strong_cache
def supercommittee(request):
	bill_list = list(supercommittee_bill_list) # clone
	for i in xrange(len(bill_list)):
		bill_list[i] = dict(bill_list[i]) # clone
		bill = bill_list[i]
		bill["sentiment"] = bill_statistics(bill["bill"], "POPVOX Nation", "POPVOX Nation")
		if bill["sentiment"]:
			bill["sentiment"]["scaled_pro"] = 142 * bill["sentiment"]["pro_pct"] / 100
			bill["sentiment"]["scaled_con"] = 142 - bill["sentiment"]["scaled_pro"]
	
	return render(request, "popvox/features/supercommittee.html",
		{
			"bills": bill_list
		})

def supercommittee_userstate(request):
	resp = []
	if request.user.is_authenticated():
		for entry in supercommittee_bill_list:
			bill = entry["bill"]
			try:
				c = UserComment.objects.get(user=request.user, bill=bill)
				resp.append( (bill.id, c.position) )
			except UserComment.DoesNotExist:
				pass
	return { "positions": resp }
supercommittee.user_state = supercommittee_userstate

def legstaff_facebook_report(request):
	is_leg_staff = False
	if request.user.is_authenticated() and request.user.userprofile.is_leg_staff() \
		and request.user.legstaffrole.member != None:
			is_leg_staff = True
	
	return render_to_response('popvox/features/congress_facebook_report.html', {
		"is_leg_staff": is_leg_staff
		}, context_instance=RequestContext(request))
		
#@strong_cache
def grade_reps(request):
	import csv, popvox.govtrack
	repgrades = []
	with open('grade_reps.csv', 'rb') as f:
		reader = csv.reader(f)
		for row in reader:
			if row[0] == 'mid': continue # header
			row[6] = int(row[6])
			row[5] = float(row[5]) if row[5] != "N/A" else None
			repgrades.append(row)
	
	house = []
	senate = []
	for row in repgrades:
		memberinfo = popvox.govtrack.getMemberOfCongress(int(row[0])) #row[0] is the memberid
		if not memberinfo['current']: continue
		if memberinfo['type'] == 'sen': #sorting by chamber
			senate.append(row)
		else:
			house.append(row)
	
	house = sorted(house, key=lambda house: (house[5], house[6]), reverse=True) #sort house by score
	senate = sorted(senate, key=lambda senate: (senate[5], senate[6]), reverse=True) #sort senate by score
	for r in house+senate:
		if r[5] != None:
			r[5] = ("%0.f" % r[5])
	
	return render_to_response("popvox/features/grade_reps.html",
	{ 'scores': [('Representatives', house), ('Senators', senate)] },
	context_instance=RequestContext(request))
      

@json_response
@user_passes_test(lambda u : u.is_authenticated() and u.userprofile.is_leg_staff())
def legstaff_facebook_report_getinfo(request):
	id = request.user.legstaffrole.member_id
	
	limit = 500
	offset = 0
	
	info = {}
	
	from registration.models import AuthRecord
	from popvox.govtrack import getMemberOfCongress
	moc = getMemberOfCongress(id)
	
	info["person"] = moc
	
	if "facebookgraphid" in moc:
		pageid = moc["facebookgraphid"]
	
		from utils import get_facebook_app_access_token
		fb_tok = get_facebook_app_access_token()
		
		info["page"] = cache.get("facebook_metadata_" + pageid)
		if not info["page"]:	
			try:
				ret = urllib.urlopen("https://graph.facebook.com/" + pageid)
				if ret.getcode() != 200:
					raise Exception("Failed to load page metadata.")
				info["page"] = json.loads(ret.read())
				cache.set("facebook_metadata_" + pageid, info["page"], 60*20) # 20 minutes
			except Exception as e:
				info["error"] = str(e)
				return info
		
		lim_off = "_%d+%d" % (offset, limit)
		info["feed"] = cache.get("facebook_feed_" + pageid + lim_off)
		if not info["feed"]:
			try:
				url = "https://graph.facebook.com/" + str(pageid) + "/feed?" \
					+ urllib.urlencode({
						"offset": offset,
						"limit": limit,
						"access_token": fb_tok
					})
				ret = urllib.urlopen(url)
				if ret.getcode() != 200:
					raise Exception("Failed to load page feed.")
				info["feed"] = json.loads(ret.read())
				cache.set("facebook_feed_" + pageid + lim_off, info["feed"], 60*20) # 20 minutes
			except Exception as e:
				info["error"] = str(e)
	
		if info["feed"]:
			# get list of all Facebook IDs seen.
			uids = []
			for entry in info["feed"]["data"]:
				uids.append(entry["from"]["id"])
				if "comments" in entry and "data" in entry["comments"]:
					for comment in entry["comments"]["data"]:
						uids.append(comment["from"]["id"])
				if "likes" in entry and "data" in entry["likes"]:
					for like in entry["likes"]["data"]:
						uids.append(like["id"])
			
			# batch load the constituenthood of each UID
			uid_map = { }
			num_constit = 0
			for authrecord in AuthRecord.objects.filter(provider="facebook", uid__in=set(uids)).select_related("user"):
				addrs = authrecord.user.postaladdress_set.all().order_by('-created')
				if len(addrs) > 0:
					addr = addrs[0]
					if (addr.state == moc["state"] and (moc["district"]==None or addr.congressionaldistrict==moc["district"])):
						uid_map[authrecord.uid] = (True, addr.city, addr.name_string(), addr.address_string(), authrecord.user.email)
						num_constit += 1
					else:
						uid_map[authrecord.uid] = (False, "out-of-district")
			info["num_known"] = len(uid_map)
			info["num_constituents"] = num_constit
	
			# add constituenthood back to returned data
			def is_constituent(uid):
				if int(uid) == int(pageid): return (False, "page")
				if uid in uid_map: return uid_map[uid]
				return (False, "unknown")
			info["num_constituent_posts"] = [0, 0] # constituents, total known
			info["num_constituent_comments"] = [0, 0] # constituents, total known
			info["num_constituent_postlikes"] = [0, 0] # constituents, total known
			for entry in info["feed"]["data"]:
				entry["from"]["constituent"] = is_constituent(entry["from"]["id"])
				entry["constituent_comments"] = 0
				entry["constituent_likes"] = 0
				entry["created_time"] = formatDateTime(pytz.utc.localize(datetime.strptime(entry["created_time"], "%Y-%m-%dT%H:%M:%S+0000")))
				if entry["from"]["constituent"][1] not in ("page", "unknown"):
					info["num_constituent_posts"][1] += 1
					if entry["from"]["constituent"][0]:
						info["num_constituent_posts"][0] += 1
				if "comments" in entry and "data" in entry["comments"]:
					for comment in entry["comments"]["data"]:
						comment["from"]["constituent"] = is_constituent(comment["from"]["id"])
						comment["created_time"] = formatDateTime(pytz.utc.localize(datetime.strptime(comment["created_time"], "%Y-%m-%dT%H:%M:%S+0000")))
						if comment["from"]["constituent"][1] not in ("page", "unknown"):
							info["num_constituent_comments"][1] += 1
							if comment["from"]["constituent"][0]:
								entry["constituent_comments"] += 1
								info["num_constituent_comments"][0] += 1
				if "likes" in entry and "data" in entry["likes"]:
					for like in entry["likes"]["data"]:
						like["constituent"] = is_constituent(like["id"])
						if like["constituent"][1] not in ("page", "unknown"):
							info["num_constituent_postlikes"][1] += 1
							if like["constituent"][0]:
								entry["constituent_likes"] += 1
								info["num_constituent_postlikes"][0] += 1
				
	return info
	

