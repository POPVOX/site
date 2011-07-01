#!runscript

# This script generates an email report for a legislative office on activity in their
# district.

# Include info on how to find names and addresses.

from django.db.models import Count
from django.core.mail import EmailMultiAlternatives

from popvox.models import *
from popvox.govtrack import *

import cgi
from datetime import date, datetime, timedelta

def generate_report(recipient, office, report_start_date, report_end_date):
	# an office is either e.g. "NY-S3" or "NY-H21".

	report = { "text": "", "html": "" }
	
	state = office[0:2]
	chamber = office[3]
	district = None

	def write(text, html, tag=None, escape=True, attrs=""):
		if text != None:
			if tag == "h2":
				report["text"] += "\n\n"
			report["text"] += text + "\n\n"

		if html == None:
			#if text[0] == "\t":
			#	attrs = " style='margin-left: 2em'"
			if escape:
				text = cgi.escape(text)
			html = "<%s%s>%s</%s>\n" % (tag, attrs, text, tag)
		report["html"] += html + "\n"
	
	if chamber == "H" and office[4:] != "0":
		district = int(office[4:])
		subject = u"POPVOX Report for %s's %s%s Congressional District" % (statenames[state], str(district), ordinate(district))
	else:
		subject = u"POPVOX Report for %s (Senate Offices)" % statenames[state]

	write(subject, None, tag="h1")

	all_time_comments = UserComment.objects.filter(state = state)
	if district != None: all_time_comments = comments.filter(congressionaldistrict = district)
	comments = all_time_comments.filter(created__gte = report_start_date, created__lte = report_end_date)
		
	def strftime(date):
		return unicode(date.strftime("%a, %b %d, %Y").replace(" 0", " "))
	write(strftime(report_start_date) + " to " + strftime(report_end_date), None, tag="p")
	
	write(unicode(comments.values("user").distinct().count()) + " constituents took " + str(comments.count()) + " new positions and wrote " + str(comments.filter(message__isnull=False).count()) + " letters", None, tag="p", escape=False)
	
	write(
		u"(The names and addresses of your constituents weighing in on POPVOX are available to you at www.popvox.com/congress. They were submitted as letters to Congress and so can be responded to under franking.)",
		u"<p>(The names and addresses of your constituents weighing in on POPVOX are available to you at <a href='http://www.popvox.com/congress'>popvox.com/congress</a>. They were submitted as letters to Congress and so can be responded to under franking.)</p>", escape=False)
	
	# Order by bill. Sort by whether the bill is up for a vote next in the chamber,
	# then by number of positions left.
	bills = list(comments.values("bill").annotate(count=Count("bill")))
	for bill in bills:
		bill["bill"] = Bill.objects.get(id=bill["bill"])
		bill["relevant"] = False
		if bill["bill"].isAlive():
			bill["relevant"] = (bill["bill"].getChamberOfNextVote() == chamber.lower())
	bills.sort(key = lambda x : (not x["relevant"], -x["count"]))
	
	# Only the top 25 bills.
	bills = bills[0:25]
	
	# Output...
	for bill in bills:
		title = bill["bill"].title
		if len(title) > 120: title = title[0:120] + "..."
		write(title, None, tag="h2")
		write(u"(Status: " + bill["bill"].status_advanced() + ")", None, tag="p")
	
		write(None, "<table><tr valign='top'>", escape=False)
	
		for label, source in ((u"New Since " + strftime(report_start_date), comments), (u"All-Time", all_time_comments)):
			billcomments = source.filter(bill=bill["bill"])
			
			write(None, "<td width='50%' style='padding: 0 1.5em 0 1.5em'>", escape=False)
			write(label + ":", None, tag="h3")
			
			lx = billcomments.filter(message__isnull=False).count()
			write(u"\t" + str(billcomments.count()) + " constituent(s) weighed in"
				+ (" and wrote " + str(lx) + " letter(s)" if lx > 0 else ""), None, tag="p")
			write(u"\t" + "Supporting: " + str(billcomments.filter(position="+").count()), None, tag="p")
			write(u"\t" + "Opposing: " + str(billcomments.filter(position="-").count()), None, tag="p")
			
			write(None, "</td>", escape=False)
			
		write(None, "</tr></table>", escape=False)
			
		write(u"for more see http://www.popvox.com" + bill["bill"].url() + "/report",
			"<p style='margin-left: 1.5em'>for more see <a href='http://www.popvox.com" + bill["bill"].url() + "/report'>popvox.com" + bill["bill"].url() + "/report</a>", escape=False)
	
	write(u"Let us know what other information you would like to see here!", None, tag="p")

	msg = EmailMultiAlternatives(subject, report["text"], "POPVOX <congress@popvox.com>", [recipient])
	msg.attach_alternative(report["html"], "text/html")
	msg.send()

if __name__ == "__main__":	
	generate_report("josh@popvox.com", "NY-S1", date(2011, 06, 01), date(2011, 06, 19))

