#!runscript

# This script generates an email report for a legislative office on activity in their
# district.

# support for reintro; remove franking note.

from django.db.models import Count
from django.core.mail import EmailMultiAlternatives
from django.template import Context, Template
from django.template.loader import get_template

from popvox.models import *
from popvox.govtrack import *

import cgi
from datetime import date, datetime, timedelta

def generate_report(recipients, office, report_start_date, report_end_date, download_csv):
	# an office is either e.g. "NY-S3" or "NY-H21".

	state = office[0:2]
	chamber = office[3]
	district = None
	districtord = None

	def strftime(date):
		return unicode(date.strftime("%b %d, %Y").replace(" 0", " "))
	def strftime2(date):
		return unicode(date.strftime("%b %d").replace(" 0", " "))
		
	if chamber == "H" and office[4:] != "0":
		district = int(office[4:])
		districtord = ordinate(district)
		subject = u"POPVOX Report %s for %s's %s%s Congressional District" % (strftime(report_end_date), statenames[state], str(district), ordinate(district))
	else:
		subject = u"POPVOX Report %s for %s (Senate Offices)" % (strftime(report_end_date), statenames[state])

	all_time_comments = UserComment.objects.filter(state = state)
	if district != None: all_time_comments = all_time_comments.filter(congressionaldistrict = district)
	comments = all_time_comments.filter(created__gte = report_start_date, created__lte = report_end_date)
	
	html_template = get_template("popvox/emails/legreport.html")
	text_template = get_template("popvox/emails/legreport.txt")
	
	template_ctx = Context()
	
	template_ctx["state"] = state
	template_ctx["statename"] = statenames[state]
	template_ctx["district"] = district
	template_ctx["districtord"] = districtord
	
	template_ctx["subject"] = subject
	
	template_ctx["startdate1"] = strftime(report_start_date)
	template_ctx["enddate1"] = strftime(report_end_date)
	template_ctx["startdate2"] = strftime2(report_start_date)
	template_ctx["enddate2"] = strftime2(report_end_date)
	
	template_ctx["download_csv"] = download_csv
	
	template_ctx["users"] = comments.values("user").distinct().count()
	template_ctx["positions"] = comments.count()
	template_ctx["letters"] = comments.filter(message__isnull=False).count()
	
	template_ctx["imgroot"] = "https://www.popvox.com/media/email"
	
	# Order by bill. Sort by whether the bill is up for a vote next in the chamber,
	# then by number of positions left.
	bills = list(comments.values("bill").annotate(count=Count("bill")))
	for bill in bills:
		bill["bill"] = Bill.objects.get(id=bill["bill"])
		bill["relevant"] = False
		if bill["bill"].isAlive():
			bill["relevant"] = (bill["bill"].getChamberOfNextVote() in (chamber.lower(), 'c'))
	bills.sort(key = lambda x : (not x["relevant"], -x["count"]))
	
	# Only the top 25 bills, and pull out just the bill part.
	bills = [b["bill"] for b in bills[0:25]]
	template_ctx["bills"] = bills
	
	# Output...
	for bill in bills:
		for key, source in (("new", comments), ("alltime", all_time_comments)):
			billcomments = source.filter(bill=bill)
			billcomments_letters = billcomments.filter(message__isnull=False)
			
			setattr(bill, "comments_" + key, {
					"positions": billcomments.count(),
					"letters": billcomments_letters.count(),
					"supporting": billcomments.filter(position="+").count(),
					"opposing": billcomments.filter(position="-").count(),
			})
	
	msg = EmailMultiAlternatives(
		subject,
		text_template.render(template_ctx),
		"POPVOX <info@popvox.com>",
		recipients)
	msg.attach_alternative(html_template.render(template_ctx), "text/html")
	msg.send()

if __name__ == "__main__":	
	generate_report(["josh@joshmlewis.com","joshlewis@g.popvox.com"], "PA-H02", date(2011, 06, 01), date(2015, 06, 19), True)

