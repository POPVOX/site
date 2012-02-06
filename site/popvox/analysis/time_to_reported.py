#!runscript

from popvox.govtrack import CURRENT_CONGRESS, parse_govtrack_date
from xml.dom.minidom import parse, Element
from glob import glob
from numpy import percentile
import re

durations = []

for bill in glob("/mnt/persistent/data/govtrack/us/%d/bills/*.xml" % CURRENT_CONGRESS):
	if not re.search(r"/s\d", bill): continue
	
	dom1 = parse(bill)
	
	introdate = None
	for introd in dom1.getElementsByTagName("introduced"):
		introdate = parse_govtrack_date(introd.getAttribute("datetime"))
		break
	else:
		print "no introduced date", bill
		
	actionlist = dom1.getElementsByTagName("actions")
	actionlist = actionlist[0].childNodes
	
	for action in actionlist:
		if not isinstance(action, Element): continue
		if action.getAttribute('state') == "REPORTED":
			reporteddate = parse_govtrack_date(action.getAttribute("datetime"))
			duration = (reporteddate-introdate).total_seconds() / float(60*60*24)
			durations.append(duration)
			if bill.endswith("s968.xml"):
				print "PIPA:", duration, "days"

print len(durations), "bills have been reported"
for pctile in (1, 10, 25, 33, 40, 50, 75, 90, 99):
	print pctile, percentile(durations, pctile), "days"
