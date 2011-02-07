# REMOTEDB=1 DEBUG=1 PYTHONPATH=. DJANGO_SETTINGS_MODULE=settings python popvox/send_comments.py

import sys
import datetime

from popvox.models import *
from popvox.govtrack import CURRENT_CONGRESS, getMemberOfCongress

from writeyourrep.send_message import Message, send_message, Endpoint

stats_only = (len(sys.argv) > 1 and sys.argv[1] == "stats")
reject_no_prefix = 0
reject_no_method = 0
reject_no_phone = 0
messages_pending = 0
success = 0

# it would be nice if we could skip comment records that we know we
# don't need to send but what are those conditions, given that there
# are several potential recipients for a message (two sens, one rep,
# maybe wh in the future).
for comment in UserComment.objects.filter(
	message__isnull=False,
	bill__congressnumber=CURRENT_CONGRESS,
	status__in=(UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED, UserComment.COMMENT_REJECTED), # everything but rejected-no-delivery and rejected-revised
	updated__lt=datetime.datetime.now()-datetime.timedelta(days=1.5)
	).order_by('created').select_related("bill"):
	# Who are we delivering to? Anyone?
	govtrackrecipients = comment.get_recipients()
	if not type(govtrackrecipients) == list:
		continue
		
	# Filter out delivery targets that we've already successfully delivered to.
	govtrackrecipientids = [
		g["id"] for g in govtrackrecipients
		if not comment.delivery_attempts.filter(target__govtrackid = g["id"], success = True).exists()]
	if len(govtrackrecipientids) == 0:
		success += 1
		continue

	if comment.address.nameprefix in (None, ""):
		reject_no_prefix += 1
		continue # !!!
	
	# Filter out delivery targets that we know we have no delivery method for.
	govtrackrecipientids = [g for g in govtrackrecipientids
		if not Endpoint.objects.filter(govtrackid = g, method = Endpoint.METHOD_NONE, tested=True).exists()]
	if len(govtrackrecipientids) == 0:
		reject_no_method += 1
		continue

	# offices that we know require a phone number and we don't have it
	govtrackrecipientids = [g for g in govtrackrecipientids
		if comment.address.phonenumber != "" or g not in (412248,412326,412243,300084,400194,300072,412271,412191,400432,412208,300062,400255,400633,400408)]
	if len(govtrackrecipientids) == 0:
		reject_no_phone += 1
		continue
		
	if stats_only:
		messages_pending += 1
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
	msg.message = comment.message + \
		"\n\n-----\nsent via popvox.com; info@popvox.com; see http://www.popvox.com" + comment.bill.url() + "/report"
	msg.topicarea = comment.bill.hashtag(always_include_session=True)
	if comment.bill.topterm != None:
		msg.topicarea = comment.bill.topterm.name
	msg.response_requested = ("no","n","NRNW","no response necessary","Comment","No Response","")
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
	
	msg.delivery_agent = "POPVOX.com"
	msg.delivery_agent_contact = "Josh Tauberer, CTO, POPVOX.com -- josh@popvox.com -- cell: 516-458-9919"
	
	# Begin delivery.
	for govtrackrecipientid in govtrackrecipientids:
		print
		print comment.created
		print govtrackrecipientid, getMemberOfCongress(govtrackrecipientid)["sortkey"]
		print msg.xml().encode("utf8")
	
		# Get the last attempt to deliver to this recipient.
		last_delivery_attempt = None
		try:
			last_delivery_attempt = comment.delivery_attempts.get(target__govtrackid = govtrackrecipientid, next_attempt__isnull = True)
		except DeliveryRecord.DoesNotExist:
			pass
		
		delivery_record = send_message(msg, govtrackrecipientid, last_delivery_attempt)
		
		# If we got this far, a delivery attempt was made although it
		# may not have been successful. Whatever happened, record it
		# so we know not to try again.
		comment.delivery_attempts.add(delivery_record)
		
		print delivery_record
		
		sys.stdin.readline()

print "Rejected because no delivery method is available", reject_no_method
print "Rejected because name has no prefix", reject_no_prefix
print "Rejected because no phone number is available", reject_no_phone
print "Successfully delivered to all targets", success
print "Comments pending/undeliverable", messages_pending

