#!runscript
# REMOTEDB=1 DEBUG=1 PYTHONPATH=. DJANGO_SETTINGS_MODULE=settings python popvox/send_comments.py

import sys
import datetime

from popvox.models import UserComment, UserCommentOfflineDeliveryRecord, Org, OrgCampaign, Bill, MemberOfCongress
from popvox.govtrack import CURRENT_CONGRESS, getMemberOfCongress

from writeyourrep.send_message import Message, send_message, Endpoint, DeliveryRecord
from writeyourrep.addressnorm import verify_adddress

mocs_require_phone_number = (
	412248,412326,412243,300084,400194,300072,412271,412191,400432,412208,
	300062,400255,400633,400408,400089,400310,412011,400325,400183,412378,
	400245,412324,400054,400142,400643,412485,400244,400142,400318,412325,
	412231,400266,412321,300070,400105,300018,400361,300040,400274,412308,
	400441,400111,412189,400240,412492,412456,412330,412398,412481,412292,
	400046,300054,300093,412414,400222,400419,400321,400124,400185,400216,
	412265,412287,400141,412427,400247,400640)

stats_only = (len(sys.argv) < 2 or sys.argv[1] != "send")
success = 0
failure = 0
needs_attention = 0
held_for_offline = 0
pending = 0
target_counts = { }
gid_only = None
if len(sys.argv) == 4 and sys.argv[2] == "only":
	gid_only = int(sys.argv[3])

# it would be nice if we could skip comment records that we know we
# don't need to send but what are those conditions, given that there
# are several potential recipients for a message (two sens, one rep,
# maybe wh in the future).
for comment in UserComment.objects.filter(
	message__isnull=False,
	bill__congressnumber=CURRENT_CONGRESS,
	status__in=(UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED, UserComment.COMMENT_REJECTED), # everything but rejected-no-delivery and rejected-revised
	updated__lt=datetime.datetime.now()-datetime.timedelta(days=1.5), # let users revise
	).order_by('created').select_related("bill").iterator():
	
	# Who are we delivering to? Anyone?
	govtrackrecipients = comment.get_recipients()
	if not type(govtrackrecipients) == list:
		continue
		
	govtrackrecipientids = [g["id"] for g in govtrackrecipients]
	
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
	msg.billnumber = comment.bill.displaynumber()
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
		msg.topicarea = (topterm.name, "legislation")
	else:
		msg.topicarea = (comment.bill.hashtag(always_include_session=True), comment.bill.title, "legislation")
	msg.response_requested = ("no","n","NRNW","no response necessary","Comment","No Response","no, i do not require a response.","i do not need a response.","")
	if comment.position == "+":
		msg.support_oppose = ('i support',)
	else:
		msg.support_oppose = ('i oppose',)
	
	msg.simple_topic_code = "http://popvox.com" + comment.bill.url() + "#" + ("support" if comment.position == "+" else "oppose")
	
	if comment.referrer != None and isinstance(comment.referrer, Org):
		msg.campaign_id = "http://popvox.com" + comment.referrer.url()
		msg.campaign_info = comment.referrer.name
		msg.form_url = "http://www.popvox.com" + comment.referrer.url()
		if comment.referrer.website == None:
			msg.org_url = "popvox.com" + comment.referrer.url() # harkin: no leading http://www.
		else:
			msg.org_url = comment.referrer.website.replace("http://www.", "").replace("http://", "") # harkin: no leading http://www.
			if msg.org_url.endswith("/"): msg.org_url = msg.org_url[0:-1]
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
			if msg.org_url.endswith("/"): msg.org_url = msg.org_url[0:-1]
		msg.org_name = comment.referrer.org.name
		msg.org_description = comment.referrer.org.description
		msg.org_contact = "(unknown)"
	else:
		msg.campaign_id = msg.simple_topic_code
		msg.campaign_info = "Comments " + ("Supporting" if comment.position == "+" else "Opposing") + " " + comment.bill.title
		msg.form_url = "http://www.popvox.com" + comment.bill.url()
		msg.org_url = "" # "popvox.com" # harkin: no leading http://www.
		msg.org_name = "" # "POPVOX.com Message Delivery Agent"
		msg.org_description = "" # "POPVOX.com delivers constituent messages to Congress."
		msg.org_contact = "" # "Josh Tauberer, CTO, POPVOX.com -- josh@popvox.com -- cell: 516-458-9919"
	
	msg.delivery_agent = "POPVOX.com"
	msg.delivery_agent_contact = "Josh Tauberer, CTO, POPVOX.com -- josh@popvox.com -- cell: 516-458-9919"
	
	# Begin delivery.
	for gid in govtrackrecipientids:
		if gid_only != None and gid != gid_only: continue

		# Get the last attempt to deliver to this recipient.
		last_delivery_attempt = None
		try:
			last_delivery_attempt = comment.delivery_attempts.get(target__govtrackid = gid, next_attempt__isnull = True)
		except DeliveryRecord.DoesNotExist:
			pass
		
		# Should we send the comment to this recipient?
		
		# Have we already successfully delivered this message?
		if last_delivery_attempt != None and last_delivery_attempt.success:
			success += 1
			continue
				
		# Check that we have no UserCommentOfflineDeliveryRecord for, meaning it is pending
		# offline delivery.
		try:
			ucodr = UserCommentOfflineDeliveryRecord.objects.get(comment=comment, target=MemberOfCongress.objects.get(id=gid))
			if ucodr.batch != None:
				held_for_offline += 1
				continue
			else:
				ucodr.delete() # will recreate if needed
		except UserCommentOfflineDeliveryRecord.DoesNotExist:
			pass
		
		def mark_for_offline(reason):
			if comment.message == None: return
			UserCommentOfflineDeliveryRecord.objects.create(
				comment=comment,
				target=MemberOfCongress.objects.get(id=gid),
				failure_reason=reason)
	
		# If the delivery resulted in a FAILURE_UNEXPECTED_RESPONSE (which requires us to
		# take a look) then skip electronic delivery till we can resolve it.
		if last_delivery_attempt != None and last_delivery_attempt.failure_reason == DeliveryRecord.FAILURE_UNEXPECTED_RESPONSE:
			needs_attention += 1
			mark_for_offline("unexp-response")
			continue
			
		# If the delivery resulted in a FAILURE_DISTRICT_DISAGREEMENT then don't retry
		# for a week.
		if last_delivery_attempt != None and last_delivery_attempt.failure_reason == DeliveryRecord.FAILURE_DISTRICT_DISAGREEMENT \
		   and datetime.datetime.now() - last_delivery_attempt.created < datetime.timedelta(days=7):
			needs_attention += 1
			mark_for_offline("district-disagr")
			continue
	
		# if the name has no prefix, or if we know we need a phone number but don't have one,
		# then skip delivery.		
		if (comment.address.nameprefix == "" and gid not in (412317,)) \
				or (comment.address.phonenumber == "" and gid in mocs_require_phone_number):
			failure += 1
			mark_for_offline("missing-info")
			continue

		# If we know we have no delivery method for this target, fail fast.
		if Endpoint.objects.filter(govtrackid = gid, method = Endpoint.METHOD_NONE, tested=True).exists():
			failure += 1
			mark_for_offline("bad-webform")
			continue
				#or not Endpoint.objects.filter(govtrackid = gid).exclude(method = Endpoint.METHOD_NONE).exists() \

		# Send the comment.
		
		if stats_only:
			pending += 1
			mark_for_offline("not-attempted")
			continue
		
		delivery_record = send_message(msg, gid, last_delivery_attempt, u"comment #" + unicode(comment.id))
		if delivery_record == None:
			print gid, comment.address.zipcode, Endpoint.objects.filter(govtrackid=gid)
			mark_for_offline("no-method")
			if not gid in target_counts: target_counts[gid] = 0
			target_counts[gid] += 1
			failure += 1
			
			if len(comment.address.zipcode) == 5:
				continue
			
			sys.stdin.readline()
			continue
		
		# If we got this far, a delivery attempt was made although it
		# may not have been successful. Whatever happened, record it
		# so we know not to try again.
		comment.delivery_attempts.add(delivery_record)
		
		print comment.created, delivery_record
		
		if delivery_record.success:
			success += 1
		else:
			failure += 1
			if delivery_record.failure_reason == DeliveryRecord.FAILURE_UNEXPECTED_RESPONSE:
				mark_for_offline("unexp-response")
				sys.stdin.readline()
			elif delivery_record.failure_reason == DeliveryRecord.FAILURE_DISTRICT_DISAGREEMENT:
				mark_for_offline("district-disagr")
			else:
				mark_for_offline("failure-oops")
		
print "Success:", success
print "Failure:", failure
print "Needs Attention:", needs_attention
print "Pending:", pending
print "Held for Offline Delivery:", held_for_offline 

#for gid in target_counts:
#	print target_counts[gid], gid, Endpoint.objects.get(govtrackid=gid).id, getMemberOfCongress(gid)["name"]

