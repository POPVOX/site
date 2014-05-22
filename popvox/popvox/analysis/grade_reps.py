#!runscript

from django.db.models import Count

from popvox.govtrack import CURRENT_CONGRESS, getMemberOfCongress, getMembersOfCongressForDistrict
from popvox.models import UserComment, Bill

import re, os, csv
from xml.dom.minidom import parseString
from StringIO import StringIO
from scipy.stats import binom

def getelemvalue(node, child):
	# read the contents of a child element by name
	ret = StringIO()
	def gettext(node):
		for n in node.childNodes:
			if hasattr(n, 'data'):
				ret.write(n.data)
			else:
				gettext(n)
	for n in node.getElementsByTagName(child):
		gettext(n)
	return ret.getvalue()
	
moc_score = { }

rolls = os.listdir('/mnt/persistent/data/govtrack/us/%d/rolls/' % CURRENT_CONGRESS)
for roll in rolls:
	rollxmlfile = "/mnt/persistent/data/govtrack/us/%d/rolls/%s" % (CURRENT_CONGRESS, roll)
	dom = parseString(open(rollxmlfile).read())
	
	if getelemvalue(dom, "category") not in ("passage", "passage-suspension"):
		continue
	
	for elem in dom.getElementsByTagName("bill"):
		bill_stn = elem.getAttribute("session"), elem.getAttribute("type"), elem.getAttribute("number")
		break
	else:
		print "no bill node for vote", roll
		continue
	
	bill = Bill.objects.filter(congressnumber=bill_stn[0], billtype=bill_stn[1], billnumber=bill_stn[2])
	if bill.count() == 0:
		print "no bill object for vote", roll
		continue
	elif bill.count() > 1:
		print "multiple bill objects for vote", roll
		continue
	bill = bill[0]
	
	# get counts of comments by state, by district, and by position.
	# query the comments grouped by state/district, and then double
	# count each row in a state+district bin and also in a state bin,
	# accumulating the total across all of the districts in the state.
	comments = UserComment.objects.filter(bill=bill).values("state", "congressionaldistrict", "position").annotate(count=Count("id"))
	counts = { }
	for row in comments:
		for key in (row["state"], None), (row["state"], row["congressionaldistrict"]):
			if not key in counts: counts[key] = { "+": 0, "-": 0 }
			counts[key][row["position"]] += row["count"]
	
	for voter in dom.getElementsByTagName("voter"):
		voterid = int(voter.getAttribute("id"))
		vote = voter.getAttribute("vote")
		
		if voterid == 0: continue # not sure which is used when
		if vote not in ("+", "-"): continue
		
		# get the MoC
		moc = getMemberOfCongress(voterid)
		if not moc["current"]: continue
		
		if not voterid in moc_score: moc_score[voterid] = { "positions_agreeing": 0, "positions_total": 0, "bills_agreeing": 0, "bills_total": 0 }
		
		# get the counts from the public on this bill
		mcounts = counts.get((moc["state"], moc["district"]), None)
		if mcounts == None: continue # no user positions
		
		# tally the number of user positions that agree with the MoC's position,
		# and the total number of positions on the bill.
		moc_score[voterid]["positions_agreeing"] += mcounts[vote]
		moc_score[voterid]["positions_total"] += mcounts["+"] + mcounts["-"]
		
		# tally the number of bills in which average public sentiment matches
		# the MoC's position, and the total number of bills for which public
		# sentiment is known according to a test of statistical significance.
		
		if mcounts["+"] > mcounts["-"]:
			cnt = mcounts["+"]
		else:
			cnt = mcounts["-"]
			pos = "-"
		
		# If the population distribution were 0.5, what is the probability
		# that we would see cnt or more positions on one side, out of
		# the total number of positions we have.
		total = mcounts["+"] + mcounts["-"]
		p = binom.cdf(total-cnt, total, 0.5)
		if p < .025: # 5% confidence level when two-tailed
			# the likelihood that we would see this many votes if the
			# population were split is so low that we reject the null
			# and accept that the population mean position is not
			# 0.5 but either greater or less (depending on which
			# side had more).
			if vote == pos:
				moc_score[voterid]["bills_agreeing"] += 1
			moc_score[voterid]["bills_total"] += 1
		else:
			if voterid == 412378:
				print 100*mcounts["+"]/total, total

		#if voterid == 412378:
		#	print rollxmlfile, bill, mcounts["+"], mcounts["-"], p, vote, pos
		
def pct(a, b):
	if b == 0: return "N/A"
	return 100*a/b
output = csv.writer(open("grade_reps.csv", "w"))
output.writerow([ "mid", "name", "%agreepositions", "#positions", "pos_significance", "%agreebills", "#bills" ])
for moc in moc_score:
	positions_agreeing = moc_score[moc]["positions_agreeing"]
	positions_total = moc_score[moc]["positions_total"]
	bills_agreeing = moc_score[moc]["bills_agreeing"]
	bills_total= moc_score[moc]["bills_total"]
	if positions_total == 0:
		pos_significance = "N/A"
	else:
		pos_significance = "%.3f" % (binom.cdf(positions_agreeing if positions_agreeing < positions_total/2 else positions_total-positions_agreeing, positions_total, 0.5))
	output.writerow([ moc, getMemberOfCongress(moc)["name"].encode("utf8"), pct(positions_agreeing, positions_total), positions_total, pos_significance, pct(bills_agreeing, bills_total), bills_total ])

