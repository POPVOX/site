#!runscript
# REMOTEDB=1 DEBUG=1 PYTHONPATH=. DJANGO_SETTINGS_MODULE=settings python popvox/send_comments.py

import sys
import datetime

from popvox.models import UserComment, UserCommentOfflineDeliveryRecord, Org, OrgCampaign, Bill, MemberOfCongress
from popvox.govtrack import CURRENT_CONGRESS, getMemberOfCongress

from writeyourrep.send_message import Message, send_message, Endpoint, DeliveryRecord

mocs_require_phone_number = (
	412248,412326,412243,300084,400194,300072,412271,412191,400432,412208,
	300062,400255,400633,400408,400089,400310,412011,400325,400183,412378,
	400245,412324,400054,400142,400643,412485,400244,400142,400318,412325,
	412231,400266,412321,300070,400105,300018,400361,300040,400274,412308,
	400441,400111,412189,400240,412492,412456,412330,412398,412481,412292,
	400046)

stats_only = (len(sys.argv) > 1 and sys.argv[1] != "send")
offline = (len(sys.argv) > 1 and sys.argv[1] == "offline")
success = 0
failure = 0
needs_attention = 0
held_for_offline = 0
pending = 0

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
	for govtrackrecipientid in govtrackrecipientids:
		# Get the last attempt to deliver to this recipient.
		last_delivery_attempt = None
		try:
			last_delivery_attempt = comment.delivery_attempts.get(target__govtrackid = govtrackrecipientid, next_attempt__isnull = True)
		except DeliveryRecord.DoesNotExist:
			pass
		
		# Should we send the comment to this recipient?
		
		# Have we already successfully delivered this message?
		if last_delivery_attempt != None and last_delivery_attempt.success:
			success += 1
			continue
				
		# Check that we have no UserCommentOfflineDeliveryRecord for, meaning it is pending
		# offline delivery.
		if UserCommentOfflineDeliveryRecord.objects.filter(comment=comment, target=govtrackrecipientid).exists():
			held_for_offline += 1
			continue
	
		# If the delivery resulted in a FAILURE_UNEXPECTED_RESPONSE (which requires us to
		# take a look) or FAILURE_DISTRICT_DISAGREEMENT (which we have no solution for the
		# moment), then skip electronic delivery till we can resolve it.
		if last_delivery_attempt != None and last_delivery_attempt.failure_reason in (DeliveryRecord.FAILURE_UNEXPECTED_RESPONSE, DeliveryRecord.FAILURE_DISTRICT_DISAGREEMENT):
			needs_attention += 1
			if offline:
				UserCommentOfflineDeliveryRecord.objects.get_or_create(comment=comment, target=MemberOfCongress.objects.get(id=govtrackrecipientid))
			continue
	
		# if the name has no prefix, or if we know we need a phone number but don't have one,
		# or if we know we have no electronic delivery method for the target, then skip delivery.		
				#or Endpoint.objects.filter(govtrackid = govtrackrecipientid, method = Endpoint.METHOD_NONE, tested=True).exists() \
		if comment.address.nameprefix in (None, "") \
				or not Endpoint.objects.filter(govtrackid = govtrackrecipientid).exclude(method = Endpoint.METHOD_NONE).exists() \
				or (comment.address.phonenumber == "" and govtrackrecipientid in mocs_require_phone_number):
			failure += 1
			if offline:
				UserCommentOfflineDeliveryRecord.objects.get_or_create(comment=comment, target=MemberOfCongress.objects.get(id=govtrackrecipientid))
			continue
			
		# Send the comment.
		
		if stats_only:
			pending += 1
			continue
		
		delivery_record = send_message(msg, govtrackrecipientid, last_delivery_attempt, u"comment #" + unicode(comment.id))
		if delivery_record == None:
			print "no delivery method available"
			print govtrackrecipientid, getMemberOfCongress(govtrackrecipientid)["sortkey"]
			#print msg.xml().encode("utf8")
			#sys.stdin.readline()
			failure += 1
			continue
		
		# If we got this far, a delivery attempt was made although it
		# may not have been successful. Whatever happened, record it
		# so we know not to try again.
		comment.delivery_attempts.add(delivery_record)
		
		print delivery_record
		
		if delivery_record.success:
			success += 1
		else:
			failure += 1
		
print "Success:", success
print "Failure:", failure
print "Needs Attention:", needs_attention
print "Pending:", pending
print "Held for Offline Delivery:", held_for_offline 


