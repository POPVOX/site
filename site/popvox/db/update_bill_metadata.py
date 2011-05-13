#!runscript

import sys

from glob import glob
from datetime import datetime, timedelta
from xml.dom import minidom
import re
import os, os.path

from popvox.models import MemberOfCongress, CongressionalCommittee, Bill, IssueArea
from popvox.govtrack import CURRENT_CONGRESS, getBillTitle, parse_govtrack_date, getMemberOfCongress

from settings import DATADIR

fre = re.compile(r"/govtrack/us/(\d+)/bills/([a-z]+)(\d+).xml")

stampfile = DATADIR + "govtrack_bill_metadata.stamp"
if os.path.exists(stampfile) and len(sys.argv) == 1:
	updatetime = os.stat(stampfile).st_mtime
else:
	updatetime = 0

cn = CURRENT_CONGRESS
if len(sys.argv) == 2:
	cn = sys.argv[1]

for fn in glob(DATADIR + "govtrack/us/" + str(cn) + "/bills/*.xml"):
	m = fre.search(fn)
	
	if os.stat(fn).st_mtime < updatetime:
		continue
	
	billsession, billtype, billnumber = m.group(1), m.group(2), m.group(3)
	
	try:
		bill = Bill.objects.get(congressnumber=billsession, billtype=billtype, billnumber=billnumber)
	except:
		bill = Bill()
		bill.congressnumber = int(billsession)
		bill.billtype = billtype
		bill.billnumber = int(billnumber)

	dom = minidom.parse(fn)
		
	# Title.
	bill.title = getBillTitle(bill, dom, "short")

	# Status.
	bill.current_status = dom.getElementsByTagName('state')[0].firstChild.data
	bill.current_status_date = parse_govtrack_date(dom.getElementsByTagName('state')[0].getAttribute("datetime"))
	
	# Sponsor.
	sponsor = dom.getElementsByTagName("sponsor")[0]
	if sponsor.hasAttribute("id"):
		moc, isnew = MemberOfCongress.objects.get_or_create(id=sponsor.getAttribute("id"))
		bill.sponsor = moc
	else:
		bill.sponsor = None
	
	# Cosponsor count.
	bill.num_cosponsors = len(dom.getElementsByTagName("cosponsor"))
	
	# Save before access to many-to-many fields.
	if bill.id == None:
		bill.save()
		
	# Committees.
	bill.committees.clear()
	for c in dom.getElementsByTagName("committee"):
		if not c.hasAttribute("code"):
			continue
		cc, isnew = CongressionalCommittee.objects.get_or_create(code=c.getAttribute("code"))
		bill.committees.add(cc)
	
	# Issue areas.
	subjects = dom.getElementsByTagName("subjects")[0]
	bill.issues.clear()
	first = True
	for term in subjects.getElementsByTagName("term"):
		try:
			ix = IssueArea.objects.get(name__iexact=term.getAttribute("name"))
			if first:
				bill.topterm = ix
				first = False
		except IssueArea.DoesNotExist:
			print "CRS term not found", term.getAttribute("name")
			continue
		
		bill.issues.add(ix)
		
	# Recent activity.
	latest_actions = []
	activity_start = datetime.now() - timedelta(days=7)
	
	# New cosponsors?
	new_cosponsors_date = None # the last date of a new cosponsor
	new_cosponsors = []
	for cs in dom.getElementsByTagName("cosponsor"):
		if cs.hasAttribute("withdrawn"): # not indicating cosponsor removals
			continue
		joined = parse_govtrack_date(cs.getAttribute("joined"))
		if joined > activity_start:
			if new_cosponsors_date == None or new_cosponsors_date < joined:
				new_cosponsors_date = joined
			new_cosponsors.append(getMemberOfCongress(int(cs.getAttribute("id")))["name"])
	if len(new_cosponsors) > 0:
		latest_actions.append( (new_cosponsors_date, str(len(new_cosponsors)) + " new cosponsor(s): " + ", ".join(new_cosponsors)) )
	
	# Finish recent activity.
	bill.latest_action = "\n".join([d.strftime("%Y-%m-%d") + "\t" + t for (d,t) in latest_actions])

	# Save.
		
	bill.save()

os.utime(stampfile, None)

