#!runscript
# REMOTEDB=1 DEBUG=1 PYTHONPATH=. DJANGO_SETTINGS_MODULE=settings python popvox/send_comments.py

import sys
import datetime

from popvox.models import UserComment, Org, OrgCampaign, Bill
from popvox.govtrack import CURRENT_CONGRESS, getMemberOfCongress

from writeyourrep.send_message import Message, send_message, Endpoint, DeliveryRecord

stats_only = (len(sys.argv) > 1 and sys.argv[1] == "stats")
reject_no_prefix = 0
reject_no_method = 0
reject_no_phone = 0
reject_needs_attention = 0
messages_pending = 0
success = 0
messages_pending_targets = { }


# it would be nice if we could skip comment records that we know we
# don't need to send but what are those conditions, given that there
# are several potential recipients for a message (two sens, one rep,
# maybe wh in the future).
for comment in UserComment.objects.filter(
	message__isnull=False,
	bill__congressnumber=CURRENT_CONGRESS,
	status__in=(UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED, UserComment.COMMENT_REJECTED), # everything but rejected-no-delivery and rejected-revised
	updated__lt=datetime.datetime.now()-datetime.timedelta(days=1.5), # let users revise
	created__gt=datetime.datetime.now()-datetime.timedelta(days=60), # abandon when it's too late
	).order_by('created').select_related("bill").iterator():
	
	# Who are we delivering to? Anyone?
	govtrackrecipients = comment.get_recipients()
	if not type(govtrackrecipients) == list:
		continue
		
	govtrackrecipientids = [	g["id"] for g in govtrackrecipients]
	
	# Filter out delivery targets that we've already successfully delivered to
	govtrackrecipientids = [g for g in govtrackrecipientids
		if not comment.delivery_attempts.filter(target__govtrackid = g, success = True).exists()]
	if len(govtrackrecipientids) == 0:
		success += 1
		continue
		
	# Or the delivery resulted in a FAILURE_UNEXPECTED_RESPONSE (which requires us to
	# take a look) or FAILURE_DISTRICT_DISAGREEMENT (which we have no solution for the
	# moment).
	govtrackrecipientids = [g for g in govtrackrecipientids
		if not comment.delivery_attempts.filter(target__govtrackid = g, next_attempt__isnull = True, failure_reason__in = (DeliveryRecord.FAILURE_UNEXPECTED_RESPONSE, DeliveryRecord.FAILURE_DISTRICT_DISAGREEMENT)).exists()]
	if len(govtrackrecipientids) == 0:
		reject_needs_attention += 1
		continue
		
	if comment.address.nameprefix in (None, ""):
		#print str(comment.address.id) + "\t" + comment.address.firstname + "\t" + comment.address.lastname
		reject_no_prefix += 1
		continue # !!!
	
	# Filter out delivery targets that we know we have no delivery method for.
	govtrackrecipientids = [g for g in govtrackrecipientids if
		not Endpoint.objects.filter(govtrackid = g, method = Endpoint.METHOD_NONE, tested=True).exists()
		#Endpoint.objects.filter(govtrackid = g).exclude(method = Endpoint.METHOD_NONE).exists()
		]
	if len(govtrackrecipientids) == 0:
		reject_no_method += 1
		continue

	# offices that we know require a phone number and we don't have it
	govtrackrecipientids = [g for g in govtrackrecipientids
		if comment.address.phonenumber != "" or g not in (
			412248,412326,412243,300084,400194,300072,412271,412191,400432,412208,
			300062,400255,400633,400408,400089,400310,412011,400325,400183,412378,
			400245,412324,400054,400142,400643,412485,400244,400142,400318,412325,
			412231,400266,412321,300070,400105,300018,400361,300040,400274,412308,
			400441,400111,412189,400240,412492,412456,412330,412398,412481,412292,
			400046)]
	if len(govtrackrecipientids) == 0:
		reject_no_phone += 1
		continue
		
	if stats_only:
		messages_pending += 1
		for g in govtrackrecipientids:
			if comment.delivery_attempts.filter(target__govtrackid = g, next_attempt__isnull = True, failure_reason = DeliveryRecord.FAILURE_SELECT_OPTION_NOT_MAPPABLE).exists():
				continue
			messages_pending_targets[g] = True
		continue
	
	# Set up the message record.
	
	msg = Message()
	msg.email = comment.user.email
	msg.prefix = comment.address.nameprefix
	msg.firstname = comment.address.firstname
	msg.lastname = comment.address.lastname
	msg.suffix = comment.address.namesuffix
	msg.address1 = comment.address.address1
	msg.address2 = comment.address.address2
	msg.city = comment.address.city
	msg.state = comment.address.state
	msg.zipcode = comment.address.zipcode
	msg.phone = comment.address.phonenumber
	msg.subjectline = comment.bill.hashtag() + " #" + ("support" if comment.position == "+" else "oppose") + " " + comment.bill.title
	if comment.message != None:
		msg.message = comment.message + \
			"\n\n-----\nsent via popvox.com; info@popvox.com; see http://www.popvox.com" + comment.bill.url() + "/report"
	else:
		msg.message = ("Support" if comment.position == "+" else "Oppose") + " " + comment.bill.title + "\n\n[This constituent weighed in at POPVOX.com but chose not to leave a personal comment. Delivered by popvox.com; info@popvox.com. See http://www.popvox.com" + comment.bill.url() + "/report]"
		
	topterm = comment.bill.topterm
	if topterm == None:
		b2 = Bill.objects.filter(billtype=comment.bill.billtype, billnumber=comment.bill.billnumber, topterm__isnull=False)
		if len(b2) > 0 and comment.bill.title_no_number() == b2[0].title_no_number():
			topterm = b2[0].topterm
		
	if topterm != None and topterm.name != "Private Legislation":
		msg.topicarea = topterm.name
	else:
		msg.topicarea = (comment.bill.hashtag(always_include_session=True), comment.bill.title)
	msg.response_requested = ("no","n","NRNW","no response necessary","Comment","No Response","no, i do not require a response.","i do not need a response.","")
	if comment.position == "+":
		msg.support_oppose = ('i support',)
	else:
		msg.support_oppose = ('i oppose',)
	
	if comment.referrer != None and isinstance(comment.referrer, Org):
		msg.campaign_id = "http://popvox.com" + comment.referrer.url()
		msg.campaign_info = comment.referrer.name
		msg.form_url = "http://www.popvox.com" + comment.referrer.url()
		if comment.referrer.website == None:
			msg.org_url = "popvox.com" + comment.referrer.url() # harkin: no leading http://www.
		else:
			msg.org_url = comment.referrer.website.replace("http://www.", "").replace("http://", "") # harkin: no leading http://www.
		msg.org_name = comment.referrer.name
		msg.org_description = comment.referrer.description
		msg.org_contact = "(unknown)"
	elif comment.referrer != None and isinstance(comment.referrer, OrgCampaign):
		msg.campaign_id = "http://popvox.com" + comment.referrer.url()
		msg.campaign_info = comment.referrer.name
		msg.form_url = "http://www.popvox.com" + comment.referrer.url()
		if comment.referrer.website_or_orgsite() == None:
			msg.org_url = "popvox.com" + comment.referrer.url() # harkin: no leading http://www.
		else:
			msg.org_url = comment.referrer.website_or_orgsite().replace("http://www.", "").replace("http://", "") # harkin: no leading http://www.
		msg.org_name = comment.referrer.org.name
		msg.org_description = comment.referrer.org.description
		msg.org_contact = "(unknown)"
	else:
		msg.campaign_id = "http://popvox.com" + comment.bill.url() + "#" + ("support" if comment.position == "+" else "oppose")
		msg.campaign_info = "Comments " + ("Supporting" if comment.position == "+" else "Opposing") + " " + comment.bill.title
		msg.form_url = "http://www.popvox.com" + comment.bill.url()
		msg.org_url = "popvox.com" # harkin: no leading http://www.
		msg.org_name = "POPVOX.com Message Delivery Agent"
		msg.org_description = "POPVOX.com delivers constituent messages to Congress."
		msg.org_contact = "Josh Tauberer, CTO, POPVOX.com -- josh@popvox.com -- cell: 516-458-9919"
		msg.dummy_campaign_info = True
	
	msg.delivery_agent = "POPVOX.com"
	msg.delivery_agent_contact = "Josh Tauberer, CTO, POPVOX.com -- josh@popvox.com -- cell: 516-458-9919"
	
	# Begin delivery.
	had_any_errors = False
	for govtrackrecipientid in govtrackrecipientids:
		#print
		#print comment.created
		#print govtrackrecipientid, getMemberOfCongress(govtrackrecipientid)["sortkey"]
		#print msg.xml().encode("utf8")
		
		# Get the last attempt to deliver to this recipient.
		last_delivery_attempt = None
		try:
			last_delivery_attempt = comment.delivery_attempts.get(target__govtrackid = govtrackrecipientid, next_attempt__isnull = True)
		except DeliveryRecord.DoesNotExist:
			pass
		
		delivery_record = send_message(msg, govtrackrecipientid, last_delivery_attempt, u"comment #" + unicode(comment.id))
		if delivery_record == None:
			had_any_errors = True
			print "no delivery method available"
			print govtrackrecipientid, getMemberOfCongress(govtrackrecipientid)["sortkey"]
			#print msg.xml().encode("utf8")
			#sys.stdin.readline()
			continue
		
		# If we got this far, a delivery attempt was made although it
		# may not have been successful. Whatever happened, record it
		# so we know not to try again.
		comment.delivery_attempts.add(delivery_record)
		
		print delivery_record
		
		if not delivery_record.success:
			had_any_errors = True
		
		#if not delivery_record.success and delivery_record.failure_reason != DeliveryRecord.FAILURE_SELECT_OPTION_NOT_MAPPABLE:
		#	sys.stdin.readline()
	
	if not had_any_errors:
		success += 1
	else:
		reject_needs_attention += 1

print "Rejected because no delivery method is available", reject_no_method
print "Rejected because name has no prefix", reject_no_prefix
print "Rejected because no phone number is available", reject_no_phone
print "Successfully delivered to all targets", success
print "Needs attention", reject_needs_attention
print "Comments in the queue", messages_pending, "covering", len(messages_pending_targets.keys()), "targets"

