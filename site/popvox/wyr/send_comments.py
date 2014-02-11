#!runscript

import os, os.path, sys
import re
import datetime
from django.db.models import Q
from django.core.exceptions import MultipleObjectsReturned

# set the backend flag to anything to avoid Amazon SES because
# when we do delivery by plain SMTP, we send from the user's
# email address.
os.environ["EMAIL_BACKEND"] = "BASIC"

from popvox.models import UserComment, UserCommentOfflineDeliveryRecord, Org, OrgCampaign, Bill, MemberOfCongress, IssueArea, FederalAgency
from popvox.govtrack import CURRENT_CONGRESS, getMemberOfCongress, getCongressDates

from writeyourrep.send_message import Message, send_message, Endpoint, DeliveryRecord
from writeyourrep.addressnorm import verify_adddress, validate_phone
from writeyourrep.district_lookup import county_lookup_coordinate

from settings import POSITION_DELIVERY_CUTOFF_DAYS
import time

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
duplicate_records = {}
needs_attention = 0
exec_delivery_failed = 0
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
lcenddate = getCongressDates(CURRENT_CONGRESS -1)[1] #end date of the previous congress. this is already a datetime object.
comments_iter = UserComment.objects.filter(
    bill__congressnumber=CURRENT_CONGRESS,
    status__in=(UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED, UserComment.COMMENT_REJECTED), # everything but rejected-no-delivery and rejected-revised
    #this next line is to send only recent comments:
    #updated__lt=datetime.datetime.now()-datetime.timedelta(hours=16), updated__gt=datetime.datetime.now()-datetime.timedelta(days=5)
    #to send very old comments:
    #updated__lt=datetime.datetime.now()-datetime.timedelta(days=45), updated__gt=lcenddate
    #this line is our standard send:
    updated__lt=datetime.datetime.now()-datetime.timedelta(hours=16), updated__gt=lcenddate# let users revise
    )

if "COMMENT" in os.environ:
    comments_iter = comments_iter.filter(id=int(os.environ["COMMENT"]))
if "ADDR" in os.environ:
    comments_iter = comments_iter.filter(address__id=int(os.environ["ADDR"]))
#whitehouse = [1866, 1872, 2731]
if "TARGET" in os.environ:
    if int(os.environ["TARGET"]) == 400629:
        comments_iter = comments_iter.filter(Q(actionrecord__campaign__id__contains=3658) | Q(actionrecord__campaign__id__contains=1872) | Q(actionrecord__campaign__id__contains=1866)) #whitehouse campaigns
    else:
        m = getMemberOfCongress(int(os.environ["TARGET"]))
        comments_iter = comments_iter.filter(state=m["state"])
        if m["type"] == "rep":
            comments_iter = comments_iter.filter(congressionaldistrict=m["district"])
if "AGENCY" in os.environ:
    #this is fuuuugly
    agency = FederalAgency.objects.get(acronym__iexact = str(os.environ["AGENCY"]))
    comments_iter.filter(Q(bill__executive_recipients=agency) | Q(regulation__executive_recipients=agency))

if "LAST_ERR" in os.environ:
    if os.environ["LAST_ERR"] == "ANY":
        comments_iter = comments_iter.filter(delivery_attempts__next_attempt__isnull=True, delivery_attempts__success=False)
    if os.environ["LAST_ERR"] == "SR":
        comments_iter = comments_iter.filter(delivery_attempts__next_attempt__isnull=True, delivery_attempts__failure_reason=DeliveryRecord.FAILURE_SELECT_OPTION_NOT_MAPPABLE)
    if os.environ["LAST_ERR"] == "TIMEOUT":
        comments_iter = comments_iter.filter(delivery_attempts__next_attempt__isnull=True, delivery_attempts__failure_reason=DeliveryRecord.FAILURE_HTTP_ERROR, delivery_attempts__trace__contains="timed out")
    if os.environ["LAST_ERR"] == "HTTP":
        comments_iter = comments_iter.filter(delivery_attempts__next_attempt__isnull=True, delivery_attempts__failure_reason=DeliveryRecord.FAILURE_HTTP_ERROR)
    if os.environ["LAST_ERR"] == "FP":
        comments_iter = comments_iter.filter(delivery_attempts__next_attempt__isnull=True, delivery_attempts__failure_reason=DeliveryRecord.FAILURE_FORM_PARSE_FAILURE)
    if os.environ["LAST_ERR"] == "UE":
        comments_iter = comments_iter.filter(delivery_attempts__next_attempt__isnull=True, delivery_attempts__failure_reason=DeliveryRecord.FAILURE_UNHANDLED_EXCEPTION)
    if os.environ["LAST_ERR"] == "DD":
        comments_iter = comments_iter.filter(delivery_attempts__next_attempt__isnull=True, delivery_attempts__failure_reason=DeliveryRecord.FAILURE_DISTRICT_DISAGREEMENT)
    if os.environ["LAST_ERR"] == "CAPTCHA":
        comments_iter = comments_iter.filter(delivery_attempts__next_attempt__isnull=True, delivery_attempts__failure_reason=DeliveryRecord.FAILURE_FORM_PARSE_FAILURE, delivery_attempts__trace__contains="CAPTCHA")
if "RECENT" in os.environ:
    comments_iter = comments_iter.filter(created__gt=datetime.datetime.now()-datetime.timedelta(days=3))
if "REDISTRICTED" in os.environ:
    #Only run comments for users whose new districts we know we have.
    comments_iter = comments_iter.filter(address__congressionaldistrict2013__isnull=False)
    print comments_iter.count()
    
def process_comment(comment, thread_id):
    global success, failure, exec_delivery_failed, needs_attention, pending, held_for_offline

    # since we don't deliver message-less comments, when we activate an endpoint we
    # end up sending the backlog of those comments. don't bother. This is also in
    # the legstaff mail download function.
    if comment.message == None and comment.updated < datetime.datetime.now()-datetime.timedelta(days=POSITION_DELIVERY_CUTOFF_DAYS):
        return
    
    # skip flagged addresses... when I put this into the .filter(),
    # a SQL error is generated over ambiguous 'state' column
    try:
        if comment.address.flagged_hold_mail:
            print "mail is being held."
            return
    except:
        duplicate_records[comment.id] = ['exception'] #postal address does not exist
        return
    # Who are we delivering to? Anyone?
    try:
        govtrackrecipients = comment.get_recipients()
        if not type(govtrackrecipients) == list:
            return
    except KeyError:
        duplicate_records[comment.id] = ['KeyError'] #key error issue with the endpoint
        return
    
    govtrackrecipientids = [g["id"] for g in govtrackrecipients]
    
    execrecipients = []
    if comment.get_executive_recipients():
        execrecipients = comment.get_executive_recipients()
        
    
    
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
    if comment.bill:
        msg.subjectline = comment.bill.hashtag() + " #" + ("support" if comment.position == "+" else "oppose") + " " + comment.bill.title
        msg.billnumber = comment.bill.shortname
    else:
        msg.subjectline = comment.regulation.hashtag() + " #" + ("support" if comment.position == "+" else "oppose") + " " + comment.regulation.title
        msg.billnumber = comment.regulation.regnumber
    msg.message = comment.updated.strftime("%x") + ". "
    if comment.message != None:
        if "OLDMAIL" in os.environ and comment.created < datetime.datetime.now()-datetime.timedelta(days=45):
            msg.message += "We experienced problems delivering this message, which caused a significant delay in receipt by your office. The problem has been rectified and the individual notified that this was an issue in the POPVOX system -- not the Congressional office. We tremendously regret the delay and are committed to timely delivery. If you have any questions about this, please contact POPVOX CEO, Marci Harris, marci@popvox.com. We always welcome your feedback.\n\n"
        if comment.bill:
            msg.message += comment.message + \
                "\n\n-----\nsent via popvox.com; info@popvox.com; see http://www.popvox.com" + comment.bill.url() + "/report"
        else:
            msg.message += comment.message + \
                "\n\n-----\nsent via popvox.com; info@popvox.com; see http://www.popvox.com" + comment.regulation.url() + "/report"
        if comment.created < datetime.datetime.now()-datetime.timedelta(days=16):
            msg.message += "\npopvox holds letters on bills until they are pending a vote in your chamber"
        msg.message_personal = "yes"
        msg.response_requested = ("yes", "response needed", "WEBRN","Yes","Y", "Yes, please contact me")
    else:
        if comment.bill:
            msg.message += ("Support" if comment.position == "+" else "Oppose") + " " + comment.bill.title + "\n\n[This constituent weighed in at POPVOX.com but chose not to leave a personal comment and is not expecting a response. See http://www.popvox.com" + comment.bill.url() + "/report. Contact info@popvox.com with delivery concerns.]"
        else:
            msg.message += ("Support" if comment.position == "+" else "Oppose") + " " + comment.regulation.title + "\n\n[This constituent weighed in at POPVOX.com but chose not to leave a personal comment and is not expecting a response. See http://www.popvox.com" + comment.regulation.url() + "/report. Contact info@popvox.com with delivery concerns.]"
        msg.message_personal = "no"
        msg.response_requested = ("no","n","NRNW","no response necessary","Comment","No Response","no, i do not require a response.","i do not need a response.","no response needed","WEBNRN","No, I wanted to voice my opinion", "N","")
    if comment.bill:    
        topterm = comment.bill.topterm
    else:
        topterm = comment.regulation.topterm
    
    #Try to pull a topterm if we don't have one. Only bills need this.
    if comment.bill:
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
        if comment.bill:
            msg.topicarea = (comment.bill.hashtag(always_include_session=True), comment.bill.title, "legislation")
        else:
            msg.topicarea = (comment.regulation.hashtag, comment.regulation.title, "regulation.")
    
    if comment.position == "+":
        msg.support_oppose = ('i support',)
    elif comment.position == "-":
        msg.support_oppose = ('i oppose',)
    else:
        msg.support_oppose = ('',)
    
    if comment.bill:
        msg.simple_topic_code = "http://popvox.com" + comment.bill.url() + "#" + ("support" if comment.position == "+" else "oppose")
    else:
        msg.simple_topic_code = "http://popvox.com" + comment.regulation.url()
    
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
        if comment.referrer.default:
            # for the default campaign of an org, use org info
            msg.campaign_id = "http://popvox.com" + comment.referrer.org.url()
            msg.campaign_info = comment.referrer.org.name
            msg.form_url = "http://www.popvox.com" + comment.referrer.org.url()
        else:
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
    msg.delivery_agent_contact = "Annalee Flower Horne, POPVOX.com -- annalee@popvox.com"
    
    # Begin delivery.
    #Executive Delivery:
    for agency in execrecipients:
        print 'line 287'
        if "TARGET" in os.environ:
            continue
        if "AGENCY" in os.environ and agency.acronym.lower() == str(os.environ["AGENCY"]).lower():
            continue
        
        #we don't deliver blank messages to agencies. If there's no personal comment, skip.
        if msg.message_personal == "no":
            continue

        #The NPS uses a CAPTCHA if there's links in the message. Try to get around this.
        if agency.acronym.lower() == "nps":
            re_sql = re.compile(r"http://|https://|www|.com|.org|.net", re.I)
            msg.message = re_sql.sub(lambda m : m.group(0)[0] + " " + m.group(0)[1:] + " ", msg.message) # the final period is for when "--" repeats
        
        # Get the last attempt to deliver to this recipient.
        last_delivery_attempt = None
        try:
            last_delivery_attempt = comment.delivery_attempts.get(target__office = agency.acronym, next_attempt__isnull = True)
        except DeliveryRecord.DoesNotExist:
            pass
        except MultipleObjectsReturned:
            last_delivery_attempts = comment.delivery_attempts.filter(target__office = agency.acronym, next_attempt__isnull = True)
            attemptids = [int(x.id) for x in last_delivery_attempts]
            duplicate_records[comment.id] = attemptids
            continue
        
        # Should we send the comment to this recipient?
        
        # Have we already successfully delivered this message?
        if last_delivery_attempt != None and last_delivery_attempt.success:
            continue
        
        endpoints = Endpoint.objects.filter(office__iexact=str(agency.acronym))
        if len(endpoints) == 0:
            endpoint = None
        else:
            endpoint = endpoints[0]
    
        # If the delivery resulted in a FAILURE_UNEXPECTED_RESPONSE (which requires us to
        # take a look) then skip electronic delivery till we can resolve it.
        if last_delivery_attempt != None and last_delivery_attempt.failure_reason == DeliveryRecord.FAILURE_UNEXPECTED_RESPONSE:
            needs_attention += 1
            exec_delivery_failed +=1
            continue
            
        # If the delivery resulted in a FAILURE_DISTRICT_DISAGREEMENT/ADDRESS_REJECTED then don't retry
        # for a week.
        if last_delivery_attempt != None and last_delivery_attempt.failure_reason in (DeliveryRecord.FAILURE_DISTRICT_DISAGREEMENT, DeliveryRecord.FAILURE_ADDRESS_REJECTED) \
           and "COMMENT" not in os.environ \
           and "TARGET" not in os.environ \
           and "ADDR" not in os.environ \
           and False: #and datetime.datetime.now() - last_delivery_attempt.created < datetime.timedelta(days=7):
            needs_attention += 1
            exec_delivery_failed +=1
            continue
    
        # if the name has no prefix, or if we know we need a phone number but don't have one,
        # then skip delivery.        
        if (comment.address.nameprefix == "" and gid not in (412317,)) \
                or (comment.address.phonenumber == "" and gid in mocs_require_phone_number):
            failure += 1
            exec_delivery_failed +=1
            continue

        # If we know we have no delivery method for this target, fail fast.
        if endpoint == None or endpoint.method == Endpoint.METHOD_NONE:
            failure += 1
            exec_delivery_failed +=1
            continue
        
        if stats_only:
            pending += 1
            continue
        
        # Send the comment.
        delivery_record = send_message(msg, endpoint, last_delivery_attempt, u"comment #" + unicode(comment.id))

        if delivery_record == None:
            print thread_id, gid, comment.address.zipcode, endpoint
            if not agency.acronym in target_counts: target_counts[agency.acronym] = 0
            target_counts[agency.acronym] += 1
            failure += 1
            exec_delivery_failed +=1
            continue
        
        # If we got this far, a delivery attempt was made although it
        # may not have been successful. Whatever happened, record it
        # so we know not to try again.
        try:
            comment.delivery_attempts.add(delivery_record)
        except:
            print delivery_record
            duplicate_records[comment.id] = ['really unhandled exception.']
            continue
        
        print thread_id, comment.created, delivery_record
        
        if delivery_record.success:
            success += 1
        else:
            failure += 1
            exec_delivery_failed +=1
    
    #Congressional Delivery:
    for gid in govtrackrecipientids:
        if "AGENCY" in os.environ:
            continue
        if "TARGET" in os.environ and gid != int(os.environ["TARGET"]):
            continue
            
        # Special field cleanups for particular endpoints.
        if gid in (412246,400050) and msg.county == None:
            if comment.address.cdyne_response == None:
                print thread_id, "Normalize Address", comment.address.id
                comment.address.normalize()
                msg.county = comment.address.county
            else:
                continue #Polygons are broken right now.
                county = county_lookup_coordinate(comment.address.longitude, comment.address.latitude)
                if county and county[0] == comment.address.state: # is a (state, county) tuple
                    print thread_id, "Found County", comment.address.id, county
                    comment.address.county = county[1]
                    comment.address.save()
                    msg.county = comment.address.county
        if msg.address2.lower() == msg.city.lower():
            msg.address2 = ""
            
        # If we know the MoC wants a phone number, skip any message with an impossible phone number
        if gid in mocs_require_phone_number:
            try:
                validate_phone(comment.address.phonenumber)
            except:
                continue
    
        # Get the last attempt to deliver to this recipient.
        last_delivery_attempt = None
        try:
            last_delivery_attempt = comment.delivery_attempts.get(target__office = gid, next_attempt__isnull = True)
        except DeliveryRecord.DoesNotExist:
            pass
        except MultipleObjectsReturned:
            last_delivery_attempts = comment.delivery_attempts.filter(target__govtrackid = gid, next_attempt__isnull = True)
            attemptids = [int(x.id) for x in last_delivery_attempts]
            duplicate_records[comment.id] = attemptids
            continue
        
        # Should we send the comment to this recipient?
        
        # Have we already successfully delivered this message?
        if last_delivery_attempt != None and last_delivery_attempt.success:
            #success += 1 #old success numbers are not actually very helpful.
            continue
                
        # Check that we have no UserCommentOfflineDeliveryRecord, meaning it is pending
        # offline delivery.
        try:
            ucodr = UserCommentOfflineDeliveryRecord.objects.get(comment=comment, target=MemberOfCongress.objects.get(id=gid))
            if ucodr.batch != None:
                held_for_offline += 1
                continue
            else:
                ucodr.delete() # will recreate if needed, and delete records for messages whose content has been removed
        except (UserCommentOfflineDeliveryRecord.DoesNotExist, MemberOfCongress.DoesNotExist):
            pass

        endpoints = Endpoint.objects.filter(govtrackid=gid, office=getMemberOfCongress(gid)["office_id"])
        if len(endpoints) == 0:
            endpoint = None
        else:
            endpoint = endpoints[0]

        def mark_for_offline(reason):
            if endpoint != None and endpoint.no_print: return
            UserCommentOfflineDeliveryRecord.objects.create(
                comment=comment,
                target=MemberOfCongress.objects.get(id=gid),
                failure_reason=reason)
    
        # If the delivery resulted in a FAILURE_UNEXPECTED_RESPONSE (which requires us to
        # take a look) then skip electronic delivery till we can resolve it.
        if last_delivery_attempt != None and last_delivery_attempt.failure_reason == DeliveryRecord.FAILURE_UNEXPECTED_RESPONSE:
            needs_attention += 1
            mark_for_offline("UR")
            continue
            
        # If the delivery resulted in a FAILURE_DISTRICT_DISAGREEMENT/ADDRESS_REJECTED then don't retry
        # for a week.
        if last_delivery_attempt != None and last_delivery_attempt.failure_reason in (DeliveryRecord.FAILURE_DISTRICT_DISAGREEMENT, DeliveryRecord.FAILURE_ADDRESS_REJECTED) \
           and "COMMENT" not in os.environ \
           and "TARGET" not in os.environ \
           and "ADDR" not in os.environ \
           and False: #and datetime.datetime.now() - last_delivery_attempt.created < datetime.timedelta(days=7):
            needs_attention += 1
            mark_for_offline("DD")
            continue
    
        # if the name has no prefix, or if we know we need a phone number but don't have one,
        # then skip delivery.        
        if (comment.address.nameprefix == "" and gid not in (412317,)) \
                or (comment.address.phonenumber == "" and gid in mocs_require_phone_number):
            failure += 1
            mark_for_offline("missing-info")
            continue

        # If we know we have no delivery method for this target, fail fast.
        if endpoint == None or endpoint.method == Endpoint.METHOD_NONE:
            failure += 1
            mark_for_offline("bad-webform")
            continue
                
        # Send the comment.
        
        if stats_only:
            pending += 1
            mark_for_offline("not-attempted")
            continue
        
        if endpoint.id == 73:
            time.sleep(6)
        delivery_record = send_message(msg, endpoint, last_delivery_attempt, u"comment #" + unicode(comment.id))

        if delivery_record == None:
            print thread_id, gid, comment.address.zipcode, endpoint
            mark_for_offline("no-method")
            if not gid in target_counts: target_counts[gid] = 0
            target_counts[gid] += 1
            failure += 1
            continue
        
        # If we got this far, a delivery attempt was made although it
        # may not have been successful. Whatever happened, record it
        # so we know not to try again.
        try:
            comment.delivery_attempts.add(delivery_record)
        except:
            print delivery_record
            duplicate_records[comment.id] = ['really unhandled exception.']
            continue
        
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
                mark_for_offline("FP")
            elif delivery_record.failure_reason == DeliveryRecord.FAILURE_HTTP_ERROR:
                mark_for_offline("HTTP")
            else:
                mark_for_offline("OTHER")

def process_comments_group(thread_index, thread_count):
    # divide work among the threads by taking only comments by users whose id
    # MOD the thread count is the thread index.
    #
    # thread_index should be in range 0 <= thread_index < thread_count so that
    # the modulus operator works right. the modulus is applied to the commenting
    # user's state so that each endpoint is confined to a particular thread so that
    # endpoint delays are properly executed in a serial fashion.


    cm = comments_iter\
        .extra(where=["MOD((ASCII(SUBSTRING(popvox_usercomment.state,1,1))+ASCII(SUBSTRING(popvox_usercomment.state,2,1))), %d) = %d" % (thread_count, thread_index)])\
        .order_by('created')\
        .select_related("bill", "user")

    count = cm.count()
    batch = 5000
    start = 0
    while start < count:
        # use list() to complete the query at once rather than
        # hog the db as we try to send items
        for comment in list(cm[start:min(start+batch, count)]):
            if os.path.exists("/tmp/break"): break
            process_comment(comment, "T" + str(thread_index+1))
        start += batch

        from django import db
        db.reset_queries()
        
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
print "Agency Failures:", exec_delivery_failed
if duplicate_records:
    for comment, records in duplicate_records.iteritems():
        print "comment id: "+str(comment)
        print "duplicates:"
        for rec in records:
            print rec
print "Needs Attention:", needs_attention
print "Pending:", pending
print "Held for Offline Delivery:", held_for_offline
print "Potential print-out size:", UserCommentOfflineDeliveryRecord.objects.all().count()

#for gid in target_counts:
#    print target_counts[gid], gid, Endpoint.objects.get(govtrackid=gid).id, getMemberOfCongress(gid)["name"]

