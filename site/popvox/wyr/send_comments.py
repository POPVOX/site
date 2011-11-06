#!runscript

import os, os.path, sys
import datetime

# set the backend flag to anything to avoid Amazon SES because
# when we do delivery by plain SMTP, we send from the user's
# email address.
os.environ["EMAIL_BACKEND"] = "BASIC"

from popvox.models import UserComment, UserCommentOfflineDeliveryRecord, Org, OrgCampaign, Bill, MemberOfCongress, IssueArea
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
	412265,412287,400141,412427,400247,400640,412427,400435)

stats_only = (len(sys.argv) < 2 or sys.argv[1] != "send")
success = 0
failure = 0
needs_attention = 0
held_for_offline = 0
pending = 0
target_counts = { }

# Build a Baysean classification model to assign bills without top terms
# into subject areas automatically.
from reverend.thomas import Bayes
top_term_model = Bayes()
excluded_top_terms = (IssueArea.objects.get(name="Private Legislation"), IssueArea.objects.get(name="Native Americans"))
def get_bill_model_text(bill):
	return bill.title_no_number() + " " + (bill.description if bill.description else "")
if os.path.exists("writeyourrep/crs-training-model"):
	top_term_model.load("writeyourrep/crs-training-model")
else:
	for bill in Bill.objects.filter(topterm__isnull=False).exclude(topterm__in=excluded_top_terms).iterator():
		top_term_model.train(bill.topterm_id, get_bill_model_text(bill))
	top_term_model.save("writeyourrep/crs-training-model")

# it would be nice if we could skip comment records that we know we
# don't need to send but what are those conditions, given that there
# are several potential recipients for a message (two sens, one rep,
# maybe wh in the future).
comments_iter = UserComment.objects.filter(
	bill__congressnumber=CURRENT_CONGRESS,
	status__in=(UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED, UserComment.COMMENT_REJECTED), # everything but rejected-no-delivery and rejected-revised
	updated__lt=datetime.datetime.now()-datetime.timedelta(hours=16), # let users revise
	)

if "COMMENT" in os.environ:
	comments_iter = comments_iter.filter(id=int(os.environ["COMMENT"]))
if "ADDR" in os.environ:
	comments_iter = comments_iter.filter(address__id=int(os.environ["ADDR"]))
if "TARGET" in os.environ:
	m = getMemberOfCongress(int(os.environ["TARGET"]))
	comments_iter = comments_iter.filter(state=m["state"])
	if m["type"] == "rep":
		comments_iter = comments_iter.filter(congressionaldistrict=m["district"])
if "LAST_ERR" in os.environ:
	if os.environ["LAST_ERR"] == "SR":
		comments_iter = comments_iter.filter(delivery_attempts__next_attempt__isnull=True, delivery_attempts__failure_reason=DeliveryRecord.FAILURE_SELECT_OPTION_NOT_MAPPABLE)
	if os.environ["LAST_ERR"] == "TIMEOUT":
		comments_iter = comments_iter.filter(delivery_attempts__next_attempt__isnull=True, delivery_attempts__failure_reason=DeliveryRecord.FAILURE_HTTP_ERROR, delivery_attempts__trace__contains="timed out")
	if os.environ["LAST_ERR"] == "HTTP":
		comments_iter = comments_iter.filter(delivery_attempts__next_attempt__isnull=True, delivery_attempts__failure_reason=DeliveryRecord.FAILURE_HTTP_ERROR)
	if os.environ["LAST_ERR"] == "UE":
		comments_iter = comments_iter.filter(delivery_attempts__next_attempt__isnull=True, delivery_attempts__failure_reason=DeliveryRecord.FAILURE_UNHANDLED_EXCEPTION)
	if os.environ["LAST_ERR"] == "DD":
		comments_iter = comments_iter.filter(delivery_attempts__next_attempt__isnull=True, delivery_attempts__failure_reason=DeliveryRecord.FAILURE_DISTRICT_DISAGREEMENT)
if "RECENT" in os.environ:
	comments_iter = comments_iter.filter(created__gt=datetime.datetime.now()-datetime.timedelta(days=7))
	
def process_comment(comment, thread_id):
	global success, failure, needs_attention, pending, held_for_offline

	# since we don't deliver message-less comments, when we activate an endpoint we
	# end up sending the backlog of those comments. don't bother.
	if comment.message == None and comment.updated < datetime.datetime.now()-datetime.timedelta(days=21):
		return
	
	# Who are we delivering to? Anyone?
	govtrackrecipients = comment.get_recipients()
	if not type(govtrackrecipients) == list:
		return
		
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
	msg.congressionaldistrict = comment.address.congressionaldistrict
	msg.zipcode = comment.address.zipcode
	msg.county = comment.address.county # may be None!
	msg.phone = comment.address.phonenumber
	msg.subjectline = comment.bill.hashtag() + " #" + ("support" if comment.position == "+" else "oppose") + " " + comment.bill.title
	msg.billnumber = comment.bill.shortname

	msg.message = comment.updated.strftime("%x") + ". "
	if comment.message != None:
		msg.message += comment.message + \
			"\n\n-----\nsent via popvox.com; info@popvox.com; see http://www.popvox.com" + comment.bill.url() + "/report"
		if comment.created < datetime.datetime.now()-datetime.timedelta(days=16):
			msg.message += "\npopvox holds letters on bills until they are pending a vote in your chamber"
		msg.message_personal = "yes"
		msg.response_requested = ("yes", "response needed", "WEBRN")
	else:
		msg.message += ("Support" if comment.position == "+" else "Oppose") + " " + comment.bill.title + "\n\n[This constituent weighed in at POPVOX.com but chose not to leave a personal comment and is not expecting a response. See http://www.popvox.com" + comment.bill.url() + "/report. Contact info@popvox.com with delivery concerns.]"
		msg.message_personal = "no"
		msg.response_requested = ("no","n","NRNW","no response necessary","Comment","No Response","no, i do not require a response.","i do not need a response.","no response needed","WEBNRN","")
		
	topterm = comment.bill.topterm
	
	# if the bill has no top term assigned, look at another bill with the same number
	# from a previous Congress that has the same title.
	if topterm == None:
		b2 = Bill.objects.filter(billtype=comment.bill.billtype, billnumber=comment.bill.billnumber, topterm__isnull=False)
		if len(b2) > 0 and comment.bill.title_no_number() == b2[0].title_no_number():
			topterm = b2[0].topterm
	
	# Private Legislation, Native Americans are too vague. Don't use those.
	if topterm in excluded_top_terms:
		topterm = None
		
	# if there is still no top term, guess using the Baysean model
	if topterm == None:
		ix, score = top_term_model.guess(get_bill_model_text(comment.bill))[0]
		if score > .03:
			topterm = IssueArea.objects.get(id = ix)
	
	if topterm != None:
		msg.topicarea = (topterm.name, "legislation")
	else:
		msg.topicarea = (comment.bill.hashtag(always_include_session=True), comment.bill.title, "legislation")
	
	if comment.position == "+":
		msg.support_oppose = ('i support',)
	else:
		msg.support_oppose = ('i oppose',)
	
	msg.simple_topic_code = "http://popvox.com" + comment.bill.url() + "#" + ("support" if comment.position == "+" else "oppose")
	
	try:
		comment.referrer = comment.referrers()[0]
	except:
		comment.referrer = None
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
		if "TARGET" in os.environ and gid != int(os.environ["TARGET"]):
			continue
			
		# Special field cleanups for particular endpoints.
		if gid in (412246,400050) and msg.county == None and comment.address.cdyne_response == None:
			print thread_id, "Normalize Address", comment.address.id
			comment.address.normalize()
			msg.county = comment.address.county
		if msg.address2.lower() == msg.city.lower():
			msg.address2 = ""
		
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
			if ucodr.batch != None and comment.message != None:
				held_for_offline += 1
				continue
			else:
				ucodr.delete() # will recreate if needed, and delete records for messages whose content has been removed
		except UserCommentOfflineDeliveryRecord.DoesNotExist:
			pass

		endpoints = Endpoint.objects.filter(govtrackid=gid, office=getMemberOfCongress(gid)["office_id"])
		if len(endpoints) == 0:
			endpoint = None
		else:
			endpoint = endpoints[0]

		def mark_for_offline(reason):
			if comment.message == None or (endpoint != None and endpoint.no_print): return
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
			
		# If the delivery resulted in a FAILURE_DISTRICT_DISAGREEMENT/ADDRESS_REJECTED then don't retry
		# for a week.
		if last_delivery_attempt != None and last_delivery_attempt.failure_reason in (DeliveryRecord.FAILURE_DISTRICT_DISAGREEMENT, DeliveryRecord.FAILURE_ADDRESS_REJECTED) \
		   and "COMMENT" not in os.environ \
		   and "TARGET" not in os.environ \
		   and "ADDR" not in os.environ \
		   and False: #and datetime.datetime.now() - last_delivery_attempt.created < datetime.timedelta(days=7):
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
		if endpoint != None and endpoint.method == Endpoint.METHOD_NONE:
			failure += 1
			mark_for_offline("bad-webform")
			continue
				#or not Endpoint.objects.filter(govtrackid = gid).exclude(method = Endpoint.METHOD_NONE).exists() \

		if endpoint == None:
			failure += 1
			mark_for_offline("no-endpoint")
			continue
				
		# Send the comment.
		
		if stats_only:
			pending += 1
			mark_for_offline("not-attempted")
			continue
		
		delivery_record = send_message(msg, endpoint, last_delivery_attempt, u"comment #" + unicode(comment.id))
		if delivery_record == None:
			print thread_id, gid, comment.address.zipcode, endpoint
			mark_for_offline("no-method")
			if not gid in target_counts: target_counts[gid] = 0
			target_counts[gid] += 1
			failure += 1
			
			if len(comment.address.zipcode) == 5:
				continue
			
			#sys.stdin.readline()
			continue
		
		# If we got this far, a delivery attempt was made although it
		# may not have been successful. Whatever happened, record it
		# so we know not to try again.
		comment.delivery_attempts.add(delivery_record)
		
		print thread_id, comment.created, delivery_record
		
		if delivery_record.success:
			success += 1
		else:
			failure += 1
			if delivery_record.failure_reason == DeliveryRecord.FAILURE_UNEXPECTED_RESPONSE:
				mark_for_offline("UR")
				#sys.stdin.readline()
			elif delivery_record.failure_reason == DeliveryRecord.FAILURE_DISTRICT_DISAGREEMENT:
				mark_for_offline("DD")
			elif delivery_record.failure_reason == DeliveryRecord.FAILURE_ADDRESS_REJECTED:
				mark_for_offline("AR")
			elif delivery_record.failure_reason == DeliveryRecord.FAILURE_FORM_PARSE_FAILURE:
				# don't queue for offline print because these are almost certainly our fault
				pass
			elif delivery_record.failure_reason == DeliveryRecord.FAILURE_HTTP_ERROR:
				# don't queue for offline print because these are almost certainly our fault
				pass
			else:
				mark_for_offline("OTHER")

def process_comments_group(thread_index, thread_count):
	# divide work among the threads by taking only comments by users whose id
	# MOD the thread count is the thread index.
	#
	# thread_index should be in range 0 <= thread_index < thread_count so that
	# the modulus operator works right. the modulus is applied to the commenting
	# user's ID since a single user targets the same endpoints so they should be
	# kept to a single thread.
	
	for comment in comments_iter\
		.extra(where=["auth_user.id MOD %d = %d" % (thread_count, thread_index)])\
		.order_by('created')\
		.select_related("bill", "user")\
		.iterator():
			
		if os.path.exists("/tmp/break"): break
		process_comment(comment, "T" + str(thread_index+1))
		
if not "THREADS" in os.environ or "TARGET" in os.environ:
	# when we are targetting a single endpoint, don't multi-thread it
	process_comments_group(0, 1)
else:
	import threading
	threads = []
	thread_count = int(os.environ["THREADS"])
	for thread_index in range(thread_count):
		t = threading.Thread(target=process_comments_group, args=(thread_index, thread_count))
		t.start()
		threads.append(t)
		
	# wait for all threads to finish
	for t in threads:
		t.join()
	

print "Success:", success
print "Failure:", failure
print "Needs Attention:", needs_attention
print "Pending:", pending
print "Held for Offline Delivery:", held_for_offline 

#for gid in target_counts:
#	print target_counts[gid], gid, Endpoint.objects.get(govtrackid=gid).id, getMemberOfCongress(gid)["name"]

