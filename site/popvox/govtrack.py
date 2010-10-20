# TODO: Caching needs to be thread-safe?

CURRENT_CONGRESS = 111

from django.core.cache import cache

from urllib import urlopen, urlencode
from xml.dom import minidom
from datetime import datetime
import feedparser

stateabbrs = ["AL", "AK", "AS", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "GU", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "MP", "OH", "OK", "OR", "PA", "PR", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VI", "VA", "WA", "WV", "WI", "WY"]

statenames = {"AL":"Alabama", "AK":"Alaska", "AS":"American Samoa", "AZ":"Arizona", "AR":"Arkansas", "CA":"California", "CO":"Colorado", "CT":"Connecticut", "DE":"Deleware", "DC":"District of Columbia", "FL":"Florida", "GA":"Georgia", "GU":"Guam", "HI":"Hawaii", "ID":"Idaho", "IL":"Illinois", "IN":"Indiana", "IA":"Iowa", "KS":"Kansas", "KY":"Kentucky", "LA":"Louisiana", "ME":"Maine", "MD":"Maryland", "MA":"Massachusetts", "MI":"Michigan", "MN":"Minnesota", "MS":"Mississippi", "MO":"Missouri", "MT":"Montana", "NE":"Nebraska", "NV":"Nevada", "NH":"New Hampshire", "NJ":"New Jersey", "NM":"New Mexico", "NY":"New York", "NC":"North Carolina", "MP":"Northern Mariana Islands", "OH":"Ohio", "OK":"Oklahoma", "OR":"Oregon", "PA":"Pennsylvania", "PR":"Puerto Rico", "RI":"Rhode Island", "SC":"South Carolina", "SD":"South Dakota", "TN":"Tennessee", "TX":"Texas", "UT":"Utah", "VT":"Vermont", "VI":"Virgin Islands", "VA":"Virginia", "WA":"Washington", "WV":"West Virginia", "WI":"Wisconsin", "WY":"Wyoming"}

statelist = list(statenames.items())
statelist.sort(key=lambda x : x[1])

stateapportionment = {"AL":7, "AK":1, "AS":1, "AZ":8, "AR":4, "CA":54, "CO":7, "CT":5, "DE":1, "DC":1, "FL":25, "GA":13, "GU":1, "HI":2, "ID":2, "IL":19, "IN":9, "IA":5, "KS":4, "KY":6, "LA":7, "ME":2, "MD":8, "MA":10, "MI":15, "MN":8, "MS":4, "MO":9, "MT":1, "NE":3, "NV":3, "NH":2, "NJ":13, "NM":3, "NY":29, "NC":13, "MP":1, "OH":18, "OK":5, "OR":5, "PA":19, "PR":1, "RI":2, "SC":6, "SD":1, "TN":9, "TX":32, "UT":3, "VT":1, "VI":1, "VA":11, "WA":9, "WV":3, "WI":8, "WY":1}

people = None # map of all IDs to people records
people_list = None # sorted list of people records for current people only
senators = None # map of state abbrs to list of IDs
congresspeople = None # map of state+district strings to ID
committees = None # list of committees, each committee a dict

def open_govtrack_file(fn):
	import os.path
	import settings
	return open(os.path.dirname(settings.__file__) + "/data/govtrack/" + fn)

def loadpeople():
	global people
	global people_list
	global senators
	global congresspeople
	
	if people != None:
		return
	
	# TODO: We're only loading in current Members of Congress. Doing this for
	# the whole historical people.xml takes way too long. We need to load that
	# into the database if we're going to provide access to it.
	
	people = { }
	senators = { }
	congresspeople = { }
	xml = minidom.parse(open_govtrack_file("us/" + str(CURRENT_CONGRESS) + "/people.xml"))
	for node in xml.getElementsByTagName("person"):
		people[int(node.getAttribute("id"))] = {
			"id": int(node.getAttribute("id")),
			"name": node.getAttribute("name"),
			"lastname": node.getAttribute("lastname"),
			"current": False,
			"sortkey": node.getAttribute("lastname") + ", " + node.getAttribute("firstname") + " " + node.getAttribute("middlename")
		}
				
		for role in node.getElementsByTagName("role"):
			if role.getAttribute("current") == "1":
				people[int(node.getAttribute("id"))]["current"] = True
				people[int(node.getAttribute("id"))]["type"] = role.getAttribute("type")
				people[int(node.getAttribute("id"))]["state"] = role.getAttribute("state")
				people[int(node.getAttribute("id"))]["district"] = role.getAttribute("district")
			
				if role.getAttribute("type") == "sen":
					if not role.getAttribute("state") in senators:
						senators[role.getAttribute("state")] = []
					senators[role.getAttribute("state")].append(int(node.getAttribute("id")))
					senators[role.getAttribute("state")].sort(key = lambda x : people[x]["sortkey"])
				
				if role.getAttribute("type") == "rep":
					congresspeople[role.getAttribute("state")+role.getAttribute("district")] = int(node.getAttribute("id"))

	people_list = [ ]
	people_list.extend([p for p in people.values() if p["current"]])
	people_list.sort(key = lambda x : x["sortkey"])

def getMembersOfCongress():
	global people_list
	loadpeople()
	return people_list
	
def getMemberOfCongress(id):
	global people
	loadpeople()
	if not id in people:
		return { "id": id, "name": "Unknown", "lastname": "Unknown", "sortkey": "", "current": False }
	return people[id]

def getMembersOfCongressForDistrict(district, moctype="all"):
	# district is specified as e.g. NY2 or DC0
	loadpeople()
	ret = []
	if moctype in ("all", "sen") and district[0:2] in senators:
		ret.extend( [people[s] for s in senators[district[0:2]]] )
	if moctype in ("all", "rep") and district in congresspeople:
		ret.append( people[congresspeople[district]] )
	return ret

def getSponsoredBills(id):
	# TODO: Cache
	xml = minidom.parse(urlopen("http://www.govtrack.us/congress/person_api.xpd?session=" + str(CURRENT_CONGRESS) + "&id=" + str(id)))
	ret = []
	for node1 in xml.getElementsByTagName("SponsoredBills"):
		for node in node1.getElementsByTagName("Bill"):
			ret.append( {
				"congressnumber": CURRENT_CONGRESS,
				"billtype": node.getAttribute("Type"),
				"billnumber": int(node.getAttribute("Number")),
				"displaynumber": node.getElementsByTagName("Number")[0].firstChild.data,
				"title": node.getElementsByTagName("Title")[0].firstChild.data,
				"officialtitle": node.getElementsByTagName("OfficialTitle")[0].firstChild.data}
				)
	return ret

def getBillMetadata(bill):
	id = str(bill.congressnumber) + ":" + bill.billtype + ":" + str(bill.billnumber)
	data = cache.get("govtrack_bill_" + id)
	if data != None:
		return minidom.parseString(data)
	else:
		data = minidom.parse(open_govtrack_file("us/" + str(bill.congressnumber) + "/bills/" + bill.billtype + str(bill.billnumber) + ".xml"))
		cache.set("govtrack_bill_" + id, data.toxml("utf-8"), 60*60*6) # 6 hours
		return data
	
def getBillSponsor(metadata):
	loadpeople()
	sp = metadata.getElementsByTagName("sponsor")
	if len(sp) == 0:
		return None # some bills have no sponsor!
	id = int(sp[0].getAttribute("id"))
	if not id in people:
		return None
	return people[id]

def getBillCosponsors(metadata):
	loadpeople()
	ret = []
	for cs in metadata.getElementsByTagName("cosponsor"):
		id = int(cs.getAttribute("id"))
		if id in people:
			ret.append( people[id] )
	ret.sort(key = lambda x : x["sortkey"])
	return ret

def getBillNumber(metadata):
	# Compute display form.
	BILL_TYPE_DISPLAY = [ ('h', 'H.R.'), ('s', 'S.'), ('hr', 'H.Res.'), ('sr', 'S.Res.'), ('hc', 'H.Con.Res.'), ('sc', 'S.Con.Res.'), ('hj', 'H.J.Res.'), ('sj', 'S.J.Res.') ]
	def ordinate(num):
		if num % 100 >= 11 and num % 100 <= 13:
			return "th"
		elif num % 10 == 1:
			return "st"
		elif num % 10 == 2:
			return "nd"
		elif num % 10 == 3:
			return "rd"
		return "th"
	ret = [x[1] for x in BILL_TYPE_DISPLAY if x[0]==metadata.documentElement.attributes["type"].value][0] + " " + str(metadata.documentElement.attributes["number"].value)
	if int(metadata.documentElement.attributes["session"].value) != CURRENT_CONGRESS :
		ret += " - " + metadata.documentElement.attributes["session"].value + ordinate(int(metadata.documentElement.attributes["session"].value)) + " Congress"
	return ret

def getBillTitle(metadata, for_display_title):
	# To compute the title, look for the last "as" attribute, and use popular title if exists, else short title, else official title.
	def find_title(m, titletype):
		elems = m.getElementsByTagName('title')
		# Find last "as" for this title type ("as introduced", "as passe house", etc).
		ta = None
		for x in elems:
			if x.attributes["type"].value == titletype:
				ta = x.attributes["as"].value
		if ta == None:
			return None
		# Return first title with this "as".
		for x in elems:
			if x.attributes["type"].value == titletype and x.attributes["as"].value == ta:
				return x.firstChild.data
	
	# Look for a popular or, failing that, a short title.
	title = find_title(metadata, "short")
	if title == None:
		title = find_title(metadata, "popular")
	
	# If this is for the official title text but we didn't find another title so we're going to use that
	# for the display title, then return nada so that we don't repeat ourselves.
	if not for_display_title and title == None:
		return None
	
	# Continue on to find the official title.	If this is for the official title text, ignore what we previously found.
	if title == None or not for_display_title:
		title = find_title(metadata, "official")
	if title == None:
		for x in metadata.getElementsByTagName('title'):
			title = x.firstChild.data
	if title == None:
		title = "No Title"
	
	if not for_display_title:
		return title
		
	return getBillNumber(metadata) + ": " + title
		
def parse_govtrack_date(d):
	try:
		return datetime.strptime(d, "%Y-%m-%dT%H:%M:%S")
	except:
		return datetime.strptime(d, "%Y-%m-%d")
		
def getBillStatus(metadata) :
	status = metadata.getElementsByTagName('state')[0].firstChild.data
	date = parse_govtrack_date(metadata.getElementsByTagName('state')[0].getAttribute("datetime")).strftime("%B %d, %Y").replace(" 0", " ")
	
	# Some status messages depend on whether the bill is current:
	if int(metadata.documentElement.attributes["session"].value) == CURRENT_CONGRESS:
		if status == "INTRODUCED":
			status = "This bill or resolution is in the first stage of the legislative process. It was introduced into Congress on %s. Most bills and resolutions are assigned to committees which consider them before they move to the House or Senate as a whole."
		elif status == "REFERRED":
			status = "This bill or resolution was assigned to a congressional committee on %s, which will consider it before possibly sending it on to the House or Senate as a whole. The majority of bills never make it past this point."
		elif status == "REPORTED":
			status = "The committees assigned to this bill or resolution sent it to the House or Senate as a whole for consideration on %s."
		elif status == "PASS_OVER:HOUSE":
			status = "This bill or resolution passed in the House on %s and goes to the Senate next for consideration."
		elif status == "PASS_OVER:SENATE":
			status = "This bill or resolution passed in the Senate on %s and goes to the House next for consideration."
		elif status == "PASSED:BILL":
			status = "This bill passed by Congress on %s and goes to the President next."
		elif status == "PASS_BACK:HOUSE":
			status = "This bill or resolution passed in the Senate and the House, but the House made changes and sent it back to the Senate on %s."
		elif status == "PASS_BACK:SENATE":
			status = "This bill or resolution has been passed in the House and the Senate, but the Senate made changes and sent it back to the House on %s."
		elif status == "PROVKILL:SUSPENSIONFAILED" or status == "PROVKILL:CLOTUREFAILED" or status == "PROVKILL:PINGPONGFAIL":
			status = "This bill or resolution is provisionally dead due to a failed vote for cloture, under a fast-track vote called \"suspension\", or when resolving differences on %s."
		elif status == "PROVKILL:VETO":
			status = "This bill was vetoed by the President on %s. The bill is dead unless Congress can override it."
		elif status == "OVERRIDE_PASS_OVER:HOUSE":
			status = "After a presidential veto, the House succeeeded in an override on %s. It goes to the Senate next."
		elif status == "OVERRIDE_PASS_OVER:SENATE":
			status = "After a presidential veto, the Senate succeeded in an override on %s. It goes to the House next."
	
	else: # Bill is not current.
		if status == "INTRODUCED" or status == "REFERRED" or status == "REPORTED":
			status = "This bill or resolution was introduced on %s, in a previous session of Congress, but was not passed."
		elif status == "PASS_OVER:HOUSE":
			status = "This bill or resolution was introduced in a previous session of Congress and was passed by the House on %s but was never passed by the Senate."
		elif status == "PASS_OVER:SENATE":
			status = "This bill or resolution was introduced in a previous session of Congress and was passed by the Senate on %s but was never passed by the House."
		elif status == "PASSED:BILL":
			status = "This bill was passed by Congress on %s but was not enacted before the end of its Congressional session."
		elif status == "PASS_BACK:HOUSE" or status == "PASS_BACK:SENATE":
			status = "This bill or resolution was introduced in a previous session of Congress and though it was passed by both chambers on %s it was passed in non-identical forms and the differences were never resolved."
		elif status == "PROVKILL:SUSPENSIONFAILED" or status == "PROVKILL:CLOTUREFAILED" or status == "PROVKILL:PINGPONGFAIL":
			status = "This bill or resolution was introduced in a previous session of Congress but was killed due to a failed vote for cloture, under a fast-track vote called \"suspension\", or while resolving differences on %s."
		elif status == "PROVKILL:VETO":
			status = "This bill was vetoed by the President on %s and Congress did not attempt an override before the end of the Congressional session."
		elif status == "OVERRIDE_PASS_OVER:HOUSE" or status == "OVERRIDE_PASS_OVER:SENATE":
			status = "This bill was vetoed by the President and Congress did not finish an override begun on %s before the end of the Congressional session."
		
	# Some status messages do not depend on whether the bill is current.
	
	if status == "PASSED:SIMPLERES":
		status = "This simple resolution passed on %s. That is the end of the legislative process for a simple resolution."
	elif status == "PASSED:CONSTAMEND":
		status = "This proposal for a constitutional amendment passed Congress on %s and goes to the states for consideration next."
	elif status == "PASSED:CONCURRENTRES":
		status = "This concurrent resolution passed both chambers of Congress on %s. That is the end of the legislative process for concurrent resolutions. They do not have the force of law."
	elif status == "FAIL:ORIGINATING:HOUSE":
		status = "This bill or resolution failed in the House on %s."
	elif status == "FAIL:ORIGINATING:SENATE":
		status = "This bill or resolution failed in the Senate on %s."
	elif status == "FAIL:SECOND:HOUSE":
		status = "After passing in the Senate, this bill failed in the House on %s."
	elif status == "FAIL:SECOND:SENATE":
		status = "After passing in the House, this bill failed in the Senate on %s."
	elif status == "VETOED:OVERRIDE_FAIL_ORIGINATING:HOUSE" or status == "VETOED_OVERRIDE_FAIL_SECOND:HOUSE":
		status = "This bill was vetoed. The House attempted to override the veto on %s but failed."
	elif status == "VETOED:OVERRIDE_FAIL_ORIGINATING:SENATE" or status == "VETOED:OVERRIDE_FAIL_SECOND:SENATE":
		status = "This bill was vetoed. The Senate attempted to override the veto on %s but failed."
	elif status == "VETOED:POCKET":
		status = "This bill was pocket vetoed on %s."
	elif status == "ENACTED:SIGNED":
		status = "This bill was enacted after being signed by the President on %s."
	elif status == "ENACTED:VETO_OVERRIDE":
		status = "This bill was enacted after a congressional override of the President's veto on %s."
	
	return status % date

def getBillStatusAdvanced(metadata) :
	status = metadata.getElementsByTagName('state')[0].firstChild.data
	
	# Some status messages depend on whether the bill is current:
	if int(metadata.documentElement.attributes["session"].value) == CURRENT_CONGRESS:
		if status == "INTRODUCED":
			status = "Introduced"
		elif status == "REFERRED":
			status = "Referred to Committee"
			ctr = 0
			for n in metadata.getElementsByTagName("committee"):
				if status == "Referred to Committee":
					status = "Referred to "
				else:
					status += ", "
				status += n.getAttribute("name")
				if n.getAttribute("subcommittee") != "":
					status += ": " + n.getAttribute("subcommittee")
				ctr += 1
				if ctr > 3:
					status += "..."
					break
		elif status == "REPORTED":
			status = "Reported by Committee"
		elif status == "PASS_OVER:HOUSE":
			status = "Passed House"
		elif status == "PASS_OVER:SENATE":
			status = "Passed Senate"
		elif status == "PASSED:BILL":
			status = "Engrossed (Passed House and Senate)"
		elif status == "PASS_BACK:HOUSE":
			status = "Sent Back to Senate With Changes"
		elif status == "PASS_BACK:SENATE":
			status = "Sent Back to House with Changes"
		elif status == "PROVKILL:SUSPENSIONFAILED":
			status = "Failed Under Suspension"
		elif status == "PROVKILL:CLOTUREFAILED":
			status = "Failed Cloture"
		elif status == "PROVKILL:PINGPONGFAIL":
			status = "Failed Resolving Differences"
		elif status == "PROVKILL:VETO":
			status = "Vetoed"
		elif status == "OVERRIDE_PASS_OVER:HOUSE":
			status = "Override Succeeded in House"
		elif status == "OVERRIDE_PASS_OVER:SENATE":
			status = "Override Succeeded in Senate"
	else: # Bill is not current.
		if status == "INTRODUCED" or status == "REFERRED" or status == "REPORTED":
			status = "This bill or resolution was introduced in a previous session of Congress but was not passed."
		elif status == "PASS_OVER:HOUSE":
			status = "This bill or resolution was introduced in a previous session of Congress and was passed by the House but was never passed by the Senate."
		elif status == "PASS_OVER:SENATE":
			status = "This bill or resolution was introduced in a previous session of Congress and was passed by the Senate but was never passed by the House."
		elif status == "PASSED:BILL":
			status = "This bill was passed by Congress but was not enacted before the end of its Congressional session."
		elif status == "PASS_BACK:HOUSE" or status == "PASS_BACK:SENATE":
			status = "This bill or resolution was introduced in a previous session of Congress and though it was passed by both chambers it was passed in non-identical forms and the differences were never resolved."
		elif status == "PROVKILL:SUSPENSIONFAILED" or status == "PROVKILL:CLOTUREFAILED" or status == "PROVKILL:PINGPONGFAIL":
			status = "This bill or resolution was introduced in a previous session of Congress but was killed due to a failed vote for cloture, under a fast-track vote called \"suspension\", or while resolving differences."
		elif status == "PROVKILL:VETO":
			status = "This bill was vetoed by the President and Congress did not attempt an override before the end of the Congressional session."
		elif status == "OVERRIDE_PASS_OVER:HOUSE" or status == "OVERRIDE_PASS_OVER:SENATE":
			status = "This bill was vetoed by the President and Congress did not finish an override before the end of the Congressional session."
		
	# Some status messages do not depend on whether the bill is current.
	
	if status == "PASSED:SIMPLERES":
		status = "Passed"
	elif status == "PASSED:CONSTAMEND":
		status = "Passed Congress"
	elif status == "PASSED:CONCURRENTRES":
		status = "Passed"
	elif status == "FAIL:ORIGINATING:HOUSE":
		status = "Failed in House"
	elif status == "FAIL:ORIGINATING:SENATE":
		status = "Failed in Senate"
	elif status == "FAIL:SECOND:HOUSE":
		status = "Failed in House"
	elif status == "FAIL:SECOND:SENATE":
		status = "Failed in Senate"
	elif status == "VETOED:OVERRIDE_FAIL_ORIGINATING:HOUSE" or status == "VETOED_OVERRIDE_FAIL_SECOND:HOUSE":
		status = "Veto Override Failed in House"
	elif status == "VETOED:OVERRIDE_FAIL_ORIGINATING:SENATE" or status == "VETOED:OVERRIDE_FAIL_SECOND:SENATE":
		status = "Veto Override Failed in Senate"
	elif status == "VETOED:POCKET":
		status = "Pocket Vetoed"
	elif status == "ENACTED:SIGNED":
		status = "Signed"
	elif status == "ENACTED:VETO_OVERRIDE":
		status = "Veto Overridden"
	
	date = parse_govtrack_date(metadata.getElementsByTagName('state')[0].getAttribute("datetime")).strftime("%b %d, %Y").replace(" 0", " ")
	
	return status + " (" + date + ")"
	
def billFinalStatus(metadata):
	status = metadata.getElementsByTagName('state')[0].firstChild.data
	date = parse_govtrack_date(metadata.getElementsByTagName('state')[0].getAttribute("datetime")).strftime("%B %d, %Y").replace(" 0", " ")
	
	if status in ("PASSED:SIMPLERES", "PASSED:CONSTAMEND", "PASSED:CONCURRENTRES"):
		return "passed " + date
	elif status in ("ENACTED:SIGNED", "ENACTED:VETO_OVERRIDE"):
		return "was enacted " + date
	elif status in ("FAIL:ORIGINATING:HOUSE", "FAIL:ORIGINATING:SENATE", "FAIL:SECOND:HOUSE", "FAIL:SECOND:SENATE"):
		return "failed "  + date
	elif status in ("VETOED:OVERRIDE_FAIL_ORIGINATING:HOUSE", "VETOED_OVERRIDE_FAIL_SECOND:HOUSE", "VETOED:OVERRIDE_FAIL_ORIGINATING:SENATE", "VETOED:OVERRIDE_FAIL_SECOND:SENATE", "VETOED:POCKET"):
		return "was vetoed "  + date
	elif int(metadata.documentElement.attributes["session"].value) != CURRENT_CONGRESS:
		return "died"
	return None

def getCommitteeList():
	global committees
	if committees != None:
		return committees

	committees = cache.get('govtrack_committees')
	if committees != None:
		return committees

	committees = [ ]
	xml = minidom.parse(open_govtrack_file("us/committees.xml"))
	for node in xml.getElementsByTagName("committee"):
		if node.getAttribute("obsolete") == "1":
			continue
		committees.append( { "id": node.getAttribute("code"), "name": node.getAttribute("displayname") } )
	committees.sort(key = lambda x : x["name"].replace("the ", ""))
	
	cache.set('govtrack_committees', committees, 60*60*24) # cache one day

	return committees
	
def getCommittee(id):
	for c in getCommitteeList():
		if c["id"] == id:
			return c
	return { "name": "Unknown" }
	
def loadfeed(monitors):
	try:
		feed = feedparser.parse("http://www.govtrack.us/users/events-atom.xpd?" + urlencode({ "monitors": ",".join(monitors), "days": "28", "hint": "no"}))
		return feed
	except:
		return None

