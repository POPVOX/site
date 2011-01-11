# DEBUG=1 PYTHONPATH=. DJANGO_SETTINGS_MODULE=settings python popvox/send_comments.py

from popvox.models import *
from popvox.govtrack import CURRENT_CONGRESS, getMembersOfCongressForDistrict

from writeyourrep.send_message import Message, send_message

# it would be nice if we could skip comment records that we know we
# don't need to send but what are those conditions, given that there
# are several potential recipients for a message (two sens, one rep,
# maybe wh in the future).
for comment in UserComment.objects.filter(bill__congressnumber=CURRENT_CONGRESS).order_by('-created'):
	# Who are we delivering to?
	
	ch = comment.bill.getChamberOfNextVote()
	if ch == None:
		# it's too late to send a comment on this bill! we should alert the user!
		continue
		
	govtrackrecipientids = []
	d = comment.address.state + str(comment.address.congressionaldistrict)
	if ch == "s":
		# send to all of the senators for the state
		govtrackrecipientids = getMembersOfCongressForDistrict(d, moctype="sen")
		if len(govtrackrecipientids) == 0:
			# state has no senators, fall back to representative
			govtrackrecipientids = getMembersOfCongressForDistrict(d, moctype="rep")
	else:
		govtrackrecipientids = getMembersOfCongressForDistrict(d, moctype="rep")
		
	# Filter out delivery targets that we've already successfully delivered to.
	govtrackrecipientids = [
		g["id"] for g in govtrackrecipientids
		if not comment.delivery_attempts.filter(target__govtrackid = g["id"], success = True).exists() ]
		
	if len(govtrackrecipientids) == 0:
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
	msg.message = comment.message + "\n\n-----\nsent via popvox.com; info@popvox.com; see http://www.popvox.com" + comment.bill.url() + "/report"
	msg.topicarea = "Other"
	if comment.bill.topterm != None:
		msg.topicarea = comment.bill.topterm.name
	msg.response_requested = ("no","n","NRNW","no response necessary","Comment","No Response","")
	if comment.position == "+":
		msg.support_oppose = ('i support',)
	else:
		msg.support_oppose = ('i sppose',)
	
	if comment.referrer != None and isinstance(comment.referrer, Org):
		msg.campaign_id = "popvox.com" + comment.referrer.url()
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
		msg.campaign_id = "popvox.com" + comment.referrer.url()
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
		msg.campaign_id = "popvox.com" + comment.bill.url()
		msg.campaign_info = "Comments on Bill " + comment.bill.title
		msg.form_url = "http://www.popvox.com" + comment.bill.url()
		msg.org_url = "popvox.com" # harkin: no leading http://www.
		msg.org_name = "POPVOX.com Message Delivery Agent"
		msg.org_description = "POPVOX.com delivers constituent messages to Congress."
		msg.org_contact = "Josh Tauberer, CTO, POPVOX.com -- josh@popvox.com -- cell: 516-458-9919"
	
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
		
		try:
			delivery_record = send_message(msg, govtrackrecipientid, last_delivery_attempt)
			
			# If we got this far, a delivery attempt was made although it
			# may not have been successful. Whatever happened, record it
			# so we know not to try again.
			comment.delivery_attempts.add(delivery_record)
			comment.save()
			
			# We probably also want to congratulate the user with an email!
			# TODO
			
		except Exception, e:
			# Exceptions occur when we have no way to deliver the message.
			# There is nothing to record with the comment. Leaving the
			# last delivery attempt as None signals that we should try it again
			# at some point in the future.
			print e
	
	break
	
