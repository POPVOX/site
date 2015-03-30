import re
import urllib
import urllib2
from httplib import HTTPException
import cookielib
import urlparse
import html5lib
import xml.sax.saxutils
from time import clock, sleep

from django.core.mail import send_mail
from django.conf import settings

from writeyourrep.models import *
from writeyourrep.district_lookup import get_zip_plus_four

from popvox.govtrack import getMemberOfCongress, statenames, CURRENT_CONGRESS
import pdb

last_connect_time = { }

import socket
socket.setdefaulttimeout(10) # ten seconds
cookiejar = cookielib.CookieJar()
proxy_handler = urllib2.ProxyHandler({'http': 'http://localhost:8124/'})
http = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookiejar))
    # ssh -L8124:localhost:8124 tauberer@tauberer.dyndns.org polipo proxyPort=8124
#http = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookiejar), proxy_handler)
http_last_url = ""
extra_cookies = { }

def urlopen(url, data, method, deliveryrec, store_as_next_referrer=True):
    global http_last_url
    global cookiejar
    
    # haven't seen that this is important for any form, but you never know
    def get_origin(url):
        p = urlparse.urlparse(http_last_url)
        return p.scheme + "://" + p.hostname.lower()
    http.addheaders = [
        ('User-agent', "POPVOX.com Message Delivery <info@popvox.com>"),
        ('Referer', http_last_url),
        ('Origin', "" if http_last_url == "" else get_origin(http_last_url)),
        #('Accept', 'text/html,application/xhtml+xml'),
        #('Accept-Charset', 'ISO-8859-1,utf-8'),
        #('Accept-Language', 'en-US'),
        ]
    cookiestate = repr([("%s=%s" % (c.name, c.value)) for c in cookiejar])

    if extra_cookies:
        http.addheaders += [("Cookie", ";".join("%s=%s" % (kv[0], kv[1]) for kv in extra_cookies.items()))]
        cookiestate += " " + repr(extra_cookies)

    if method.upper() == "POST":
        deliveryrec.trace += unicode("POST " + url + "\n")
        if not isinstance(data, (str, unicode)):
            for k, v in data.items():
                if type(k) == str: k = k.decode("utf8", "replace")
                if type(v) == str: v = v.decode("utf8", "replace")
                deliveryrec.trace += "\t" + k + "=" + v + "\n"
            data = urllib.urlencode(data)
        else:
            deliveryrec.trace += unicode(data) + u"\n"
        deliveryrec.trace += "\tcookies: " + cookiestate + "\n"
        ret = http.open(url, data)
    else:
        if not isinstance(data, (str, unicode)):
            data = urllib.urlencode(data)
        if len(data) > 0:
            url = url + ("?" if not "?" in url else "&") + data
        deliveryrec.trace += unicode("GET " + url + "\n")
        deliveryrec.trace += "\tcookies: " + cookiestate + "\n"
        ret = http.open(url)
    
    deliveryrec.trace += unicode(ret.getcode()) + unicode(" " + ret.geturl() + "\n")
    deliveryrec.trace += unicode("".join(ret.info().headers) + "\n")
    
    if store_as_next_referrer:
        http_last_url = url
    
    return ret

class Message:
    def __repr__(self):
        return self.__unicode__()
    def __unicode__(self):
            import re
            return re.sub(
                r"%(\w+)",
                lambda m : unicode(getattr(self, m.group(1))),
u"""%prefix %firstname %lastname %suffix <%email>
%address1; %address2
%city, %state %zipcode
%phone

%topicarea / %support_oppose 
%subjectline

%message

Campaign:
    %campaign_id
    %campaign_info
    %form_url 
Org:
    %org_name
    %org_description
    %org_url
    %org_contact
Delivery:
    %delivery_agent
    %delivery_agent_contact
""")
    
    def text(self):
        ret = u""
        if self.prefix != "": ret += self.prefix + u" "
        ret += self.firstname + u" " + self.lastname
        if self.suffix != "": ret += u" " + self.suffix
        ret += u"\n"
        
        ret += self.address1 + u"\n"
        if self.address2 != "": ret += self.address2 + u"\n"
        ret += self.city + u", " + self.state + u" " + self.zipcode + u"\n"
        if self.phone != "": ret += self.phone + u"\n"
        ret += self.email + u"\n\n"
        
        ret += self.subjectline + u"\n\n"
        ret += self.message
        
        ret += u"\n\ntracking info:\n"
        if self.org_name != "" and self.org_url != "":
            ret += u"organization: " + self.org_name + u" (" + self.org_url + u")\n"
        ret += u"topic code: " + self.campaign_id + u"\n"
        
        return ret
        
    def xml(self, template=None):
        if template == None:
            template = u"""<APP>CUSTOM
<PREFIX>%prefix</PREFIX>
<FIRST>%firstname</FIRST>
<LAST>%lastname</LAST>
<SUFFIX>%suffix</SUFFIX>
<ADDR1>%address1</ADDR1>
<ADDR2>%address2</ADDR2>
<CITY>%city</CITY>
<STATE>%state</STATE>
<ZIP>%zipcode</ZIP>
<PHONE>%phone</PHONE>
<EMAIL>%email</EMAIL>
<TOPIC>%campaign_id</TOPIC>
<RSP>Y</RSP>
<MSG>%message</MSG>
</APP>"""
        return re.sub(
            r"%(\w+)",
            lambda m : xml.sax.saxutils.escape(unicode(getattr(self, m.group(1)))),
            template)

# Here are some common aliases for the field names we use.
# Don't include spaces, all lowercase.
common_fieldnames = {
    # cannonical names
    "email": "email",
    "prefix": "prefix",
    "firstname": "firstname",
    "lastname": "lastname",
    "name": "name",
    "suffix": "suffix",
    "address1": "address1",
    "address2": "address2",
    "city": "city",
    "state": "state",
    "zipcode": "zipcode",
    "county": "county",
    "message": "message",
    "subjectline": "subjectline",
    "response_requested": "response_requested",
    "bill": "billnumber",
    
    "campaign_id": "campaign_id",
    "campaignid": "campaign_id",
    "campaigninfo": "campaign_info",
    "form_url": "form_url",
    "campaignformurl": "form_url",
    "org_url": "org_url",
    "advocacyorganizationurl": "org_url",
    "org_name": "org_name",
    "delivery_agent": "delivery_agent",

    # other aliases
    "organization": "org_name",
    "advocacyorganizationname": "org_name",
    "organizationcontact": "org_contact",
    "organizationdescription": "org_description",
    "mailing_county": "county",
    "deliveryagent": "delivery_agent",
    "delivery_agent_contact": "delivery_agent_contact",
    "deliveryagentcontact": "delivery_agent_contact",
    "contact[salutation]": "prefix",
    "salutation": "prefix",
    "prefixlist": "prefix",
    "title": "prefix",
    "first": "firstname",
    "fname": "firstname",
    "namefirst": "firstname",
    "first_name": "firstname",
    "name_first": "firstname",
    "first-name": "firstname",
    "firstname_require": "firstname",
    "last": "lastname",
    "lname": "lastname",
    "namelast": "lastname",
    "last_name": "lastname",
    "last-name": "lastname",
    "name_last": "lastname",
    "lastname_require": "lastname",
    "fullname": "name",
    "name_suffix": "suffix",
    "suffix2": "suffix",
    "address": "address_combined",
    "street_address": "address_combined",
    "street_address_2": "address2",
    "address01": "address1",
    "address02": "address2",
    "streetaddresscontinued": "address2",
    "streetaddress1": "address1",
    "streetaddress2": "address2",
    "mailing_streetaddress1": "address1",
    "mailing_streetaddress2": "address2",
    "street2": "address2",
    "addr1": "address1",
    "addr2": "address2",
    "add1": "address1",
    "add2": "address2",
    "add": "address_combined",
    "street-address": "address_combined",
    "streetaddress": "address1",
    "street": "address1",
    "addressline1": "address1",
    "addressline2": "address2",
    "address-line1": "address1",
    "address-line2": "address2",
    "addressstreet1": "address1",
    "addressstreet2": "address2",
    "req_addrl": "address1",
    "mailing_city": "city",
    "hcity": "city",
    "citytown": "city",
    "addresscity": "city",
    "statecode": "state",
    "hstate": "state",
    "mailing_state": "state",
    "addressstate": "state",
    "state_require": "state",
    "zip": "zipcode",
    "hzip": "zipcode",
    "zip5": "zip5",
    "zip_verify": "zipcode",
    "ctl00$ctl13$Zip": "zip5",
    "mainzip": "zip5",
    "zip4": "zip4",
    "zipfour": "zip4",
    "zip2": "zip4",
    "plusfour": "zip4",
    "zip_plus4": "zip4",
    "zipcode4": "zip4",
    "pluszip": "zip4",
    "postalcode": "zipcode",
    "mailing_zipcode": "zipcode",
    "addresszip": "zipcode",
    "zip_require": "zipcode",
    "phone": "phone",
    "phone_number": "phone",
    "phonenumber": "phone",
    "home_phone_number": "phone",
    "homephone": "phone",
    "phonehome": "phone",
    "phone_home": "phone",
    "phonnum": "phone",
    "phone_h": "phone",
    "primaryphone": "phone",
    "phone1": "phone",
    "hphone": "phone",
    "phone-number": "phone",
    "home-phone": "phone",
    "required-phone": "phone",
    "daytime-phone": "phone",
    "phn": "phone",
    "emailaddress": "email",
    "email_confirmation": "email",
    "email_address": "email",
    "email_verify": "email",
    "verify_email": "email",
    "email_confirmation": "email",
    "vemail": "email",
    "valid-email": "email",
    "email2": "email",
    "fromemail": "email",
    "verify-email": "email",
    "emailaddress_require":"email",
    "EmailCheck": "email",
    "emailcheck": "email",
    "emailadress": "email",
    "required-valid-email": "email",
    "signup-email": "email",
    
    "messagebody": "message",
    "comment": "message",
    "yourmessage": "message",
    "pleasetypeyourmessage": "message",
    "pleasewriteyourmessage": "message",
    "comments": "message",
    "messagecomments": "message",
    "pleasetypeinyourmessage": "message",
    "details_textarea": "message",
    "msg": "message",
    "body": "message",
    "claim": "message",
    "message_require": "message",
    "additionalcomments": "message",
    "required-message": "message",
    "message": "message",
    
    "textmodified": "message_personal",
    "modified": "message_personal",

    "subject": "subjectline",
    "required-subject": "subjectline",
    "msubject": "subjectline",
    "messagesubject": "subjectline",
    "messageSubject_required": "subjectline",
    "email_subject": "subjectline",
    "message_topic_select": "topicarea",
    "subject_text": "subjectline",
    "subject_select": "topicarea",
    "topic_text": "subjectline",
    "topic_select": "topicarea",
    "issue_text": "subjectline",
    "issue_select": "topicarea",
    "issue1_select": "topicarea",
    "issues_select": "topicarea",
    "issueslist_select": "topicarea",
    "feedbackissueselector_select": "topicarea",
    "pleasetypethesubjectofyourmessage": "subjectline",
    "subjectofletter_text": "subjectline",
    "subjectofletter_select": "topicarea",
    "shortdescription": "subjectline",
    "messageissue_select": "topicarea",
    "topics_select": "topicarea",
    "whatisthegeneraltopicofyourmessage_select": "topicarea",
    "subject_code_select": "topicarea",
    "category_select": "topicarea",
    "contact[issue_id]": "topicarea",
    "topic_radio": "topicarea",
    "subject1_select": "topicarea",
    "whatisyourgeneraltopic_select": "topicarea",
    "field_250a9cb8-13dc-40f7-94fb-d301593db4c9": "topicarea",
    "field_6544a2ff-bc89-4c03-b786-c7927f5bc6f7": "topicarea",
    "field_ff576494-50ce-42fc-aff0-a14f510dc4d8": "topicarea",
    "subject_require": "topicarea",
    "leg-issues": "topicarea",
    "issue": "topicarea",
    "submitted[message_details][topic]": "topicarea",
    "submitted[message_details][please_type_the_subject_of_your_message]": "subject line",
    "submitted[message_details][message]": "message",
    "68_actions_select": "opinion", 
    "69_actions_select": "opinion",
    "528_actions_select": "opinion",
    "33_actions_select": "opinion",
    "584_actions_select": "opinion",
    "735_Subject_select": "topicarea",
    "92_subject_select": "topicarea",
    "1075_topic_select": "topicarea",
    "92_county'_select": "county",
    "561_whatlegislativeissueareyoucontactingmeabout_select": "topicarea",
    "579_field_f33b2309-b7af-40ca-aaf8-e40952fff259_select": "topicarea",
    "650_website_text": "www.popvox.com",
    "661_Issues_select": "topicarea",
    "661_Issues2_select": "topicarea",
    "795_topic_select": "topicarea",
    "795_subject_text": "subject line",


    
    
    
    "responserequested": "response_requested",
    "responserequest": "response_requested",
    "response": "response_requested",
    "requestresponse": "response_requested",
    "doyourequirearesponse": "response_requested",
    "respond": "response_requested",
    "response_requested_select": "response_requested",
    "wouldyoulikearesponse": "response_requested",
    "reqresponse": "response_requested",
    "rsp": "response_requested",
    "replychoice": "response_requested",
    "reqestresponse": "response_requested",
    "responseexpected": "response_requested",
    "correspondence_response": "response_requested",
    "answer": "response_requested",
    "responsereq": "response_requested",
    "ddlreply": "response_requested",
    "field_1f0bf197-193c-4a61-a149-feb5a1da4482": "response_requested",
    "required-response": "response_requested",
    "response_require": "response_requested",
    "response-needed": "response_requested",
    "radiogroup1": "response_requested",
    "field_response_requested[und]": "response_requested",
    
    'view_select': 'support_oppose',
    
    #NPS fields:
    'id_authorOrg': "org_name",
    'id_authorCity': "city",
    'stateprovince': "state",
    'authorstateprov': "state",
    "authorstateprovdd": "state",
    'id_authorPostalCode': "zipcode",
    'id_authorAddress1': "address1",
    'id_authorAddress2': "address2",
    'id_authorEmail': "email",
    'id_pubComments': "message",
    
    #FCC:
    'address.line1': "address1",
    'address.line2': "address2",
    'address.city': "city",
    'address.state.id': "state",
    'address.zip': "zipcode",
    'briefComment': "message",
    
    #Reid's Form
    "cf_field_2": "prefix",
    "cf_field_3": "firstname",
    "cf_field_4": "lastname",
    "cf_field_5": "address1",
    "cf_field_6": "city",
    "cf_field_7": "state",
    "cf_field_8": "zipcode",
    "cf_field_9": "email",
    "cf_field_10": "phone",
    "cf_field_11": "phone",
    "cf_field_12": "topicarea",
    "cf_field_13": "message",
    
    #Boxer's Form
    
    
    #McGovern
    "ctl00_ctl06_Street": "address1",
    
    #Renacci
    "field_1BDF891F-B1AA-4BC0-9EEB-7507CCA03AFA": "prefix",
    "field_067F5CC0-E4A5-4B4B-BD0E-714DBF4A797E": "firstname",
    "field_744F331D-F0B5-4713-B150-DC32777C7BB4": "lastname",
    "field_EBCF1290-DB1F-49D6-8039-A6C3BD6F02EA": "address1",
    "field_0F26F776-FF16-4E0D-AFA4-C0874A8DBDE1": "address2",
    "field_328DEB57-810A-44F0-99F2-5FB14FD96EBB": "city",
    "field_9FFAB92C-E0CC-4053-A581-9FDCB7E5F2EA": "state",
    "field_2891FFBE-1214-4A9A-96E3-7A9316F267BC": "zip5",
    "field_8b65f647-f47f-4482-ad11-c94379c3330b": "zip4",
    "field_96741AC5-3E05-45BE-AF0B-564673AD7194": "email",
    "field_97698BF0-168D-44BF-AEAA-0C8BBEAE8F5B": "phone",
    "field_2C5B5245-43D8-4AA0-8B6F-D1A7F1E8B0D5": "topicarea",
    "field_CAE2B870-76B8-4AB1-BE3F-785E757F4787": "subjectline",
    "field_57554A95-21E9-4705-AAF9-04F948CA65C6": "message",
    "field_079666C8-6C16-4A8F-BC14-C0BA698A280F": "response_requested",
    "telephonenumber": "phone",
    
    
    #Numbered senate fields
    "a01": "prefix",
    "b01": "firstname",
    "c01": "lastname",
    "d01": "address1",
    "e01": "address2",
    "f01": "city",
    "g01": "state",
    "h01": "zipcode",
    "h02": "phone",
    "i01": "email",
    "i02": "message",
    "j01": "topicarea",
    "j15": "response_requested",
    "k01": "message",
    
    #Obama's fields:
    "submitted[first_name]" : "firstname",
    "submitted[last_name]" : "lastname",
    "submitted[suffix]" : "suffix",
    "submitted[street]" : "address1",
    "submitted[zip]":"zipcode",
    "submitted[city]":"city",
    "submitted[state]" : "state",
    "submitted[subject]" : "topicarea",
    "submitted[message]" : "message",
    "submitted[contact_me][0]" : "response_requested",
    "submitted[bill_number]" : "billnumber",
    "submitted[name]" : "org_name",
    "submitted[about_organization]": "org_description",
    "submitted[delivery_agent_name]" : "delivery_agent",
    
    #Nonsense Senate Fields:
    "field_9a784ebc-408b-4eeb-a05b-05317a1df5d2": "prefix",
    "field_e1b6dbd1-0ad9-40be-ab0f-9f51a3d6e884": "firstname",
    "field_462d2bb9-db78-443e-be87-0b0b47dd00c5": "lastname",
    "field_117b579f-a706-4735-a966-dd5746ae6ebd": "address1",
    "field_e8f08f3d-981f-4f15-a76e-eb49b722c2b4": "address2",
    "field_4e978a1e-0b3b-41ee-8fdc-eb9c26d77405": "city",
    "field_193d88c0-8e02-4d0d-977c-749632d5d4e3": "state",
    "field_04fc034d-d107-4519-b606-afb75aa37526": "zipcode",
    "field_0919c49e-53e2-45f3-9967-4ac8ce6e4e96": "topicarea",
    "field_a04e48fc-dd84-4b78-b573-2be80de041e3": "email",
    "field_32e4bfdf-a639-47de-bdfb-6d0c705fd2ff": "message",
    
    "field_6dce4fee-bdb8-4dad-9496-d121f71a4bd9": "topicarea",
    "field_4bbb4940-5fa9-43e1-9f05-0a9eb169c378": "message",
    
    "field_3a2a6994-b89f-41c9-92a7-06d732a05c98": "zip4",
    "field_9982fec2-4791-45e6-863f-a2622820da95": "phone",
    }

# Here are field names that we assume are optional everywhere.
# All lowercase here.
skippable_fields = (
    #Whitehouse skippables:
    "submitted[prefix]",
    "submitted[middle_name]",
    "submitted[mname]",
    "submitted[phone]",
    "submitted[title]",
    "submitted[organization]",
    "submitted[class]",
    "submitted[type]",
    "submitted[non_us_state]",
    "submitted[country]",
    "submitted[congress_]",
    "submitted[position]",
    "submitted[summary]",
    "submitted[more_info_url]",
    "submitted[agency_contact_prefix]",
    "submitted[agency_contact_first_name]",
    "submitted[agency_contact_middle_name]",
    "submitted[agency_contact_last_name]",
    "submitted[agency_contact_suffix]",
    "submitted[agency_contact_email]",
    "submitted[agency_contact_phone]",
    "submitted[agency_contact_title]",
    "submitted[agency_contact_organization]",
    "submitted[agency_contact_type]",
    "submitted[agency_contact_street]",
    "submitted[agency_contact_zip]",
    "submitted[agency_contact_city]",
    "submitted[agency_contact_state]",
    "submitted[agency_contact_non_us_state]",
    "submitted[agency_contact_country]",
    "submitted[delivery_agent_middle_name]",
    "submitted[delivery_agent_suffix]",
    "submitted[delivery_agent_phone]",
    "submitted[delivery_agent_title]",
    "submitted[delivery_agent_organization]",
    "submitted[delivery_agent_type]",
    "submitted[delivery_agent_street]",
    "submitted[delivery_agent_zip]",
    "submitted[delivery_agent_city]",
    "submitted[delivery_agent_state]",
    "submitted[delivery_agent_non_us_state]",
    "submitted[delivery_agent_country]",
    
    #Reid's Form
    "cf_field_9", "cf_field_10",
    
    #Renacci
    "field_BD43206E-B2C5-4EF9-952D-DE3F1C00F6CA",
    "field_6EB7928D-D662-4BB0-A89B-402395CE1C38",
    "form_2BDE1712-8A30-41E5-815B-785CC6B44D37",
    
    
    #Cantor's survey
    "ratings[how_is_the_113th_congress_doing?]",
    "ratings[is_the_113th_congress_addressing_the_issues_that_concern_you?]",
    
    "lastcontact",
    
    #Hatch phone:
    "field_0aaeac3f-dfba-4b74-b884-2494e1be87f2",
    
    #Gosar radios
    "help",
    "meeting",
    "Yes, I would like a response."
    
    #National Park Service
    "authormiddleinitial", "howdidyouhear", "liketohear", "country",
    
    "ctl03$facebookidcontrol",
    
    #search bar on zipstage:zipauthform,custom_form:
    "searchkey",
    
    #what?
    "gender",


    "agency-issues", "agency", "prefixother", "mname", "middle", "middlename", "suffix", "preferredname",
    "name_middle",     "middle-initial", "title", "addr3", "unit", "areacode", "exchange", "final4", "daytimephone", "workphone", "phonework", "work_phone_number", "worktel", "phonebusiness", "business-phone", "phone_b", "phone_c", "ephone", "mphone", "cell", "newsletter", "esignup", "townhall", "subjectother", "plusfour", "nickname", "firstname_spouse", "lastname_spouse", "mi", "cellphone", "rank", "branch", "militaryrank", "middleinitial", "other", "organization", "enews_subscribe", "district-contact", "appelation", "company",
    "countdown",
    "affll",
    "contact-type",
    "dummy_zip",
    "signup",
    "survey_answer_1", "survey_answer_2", "survey_answer_3", "survey", "affl_del",
    "speech", "authfailmsg",
    "flag_name", "flag_send", "flag_address", "tour_arrive", "tour_leave", "tour_requested", "tour_dates", "tour_adults", "tour_children", "tour_needs", "tour_comment",
    "org",
    "h03", "H03",
    "name-title", 'military', "personalcode",
    "organization",
    "unsubscribe", "newsletteraction", "email.optin", "newslettercode","newsletteroptin","optintoemailsfromrepmarkey",
    "q1",
    "enewssign", "enewsletter", "newsletteraction",
    "countdown", "txthomesearch",
    "field_f0a5e486-09e8-4c79-8776-7c1ea0c45f27",
    "contactform$cd$rblformat",
    "occupation",
    "ratings[how_is_the_112th_congress_doing?]",
    "ratings[how_am_i_doing_as_your_representative?]",
    "ratings[is_the_112th_congress_addressing_the_issues_that_concern_you?]",
    "aff1req",
    "field_113f8513-8ef5-4595-938c-0576c6ee6112",
    "captcha_a989233d-1b27-4ab7-a270-e7767f58cb9e",
    "military_branch", "military_retired",
    "ecclesiastical_title", "ecclesiastical_toggle", "military_toggle",
    "phcell",
    "suffix",
    "phone2",
    "phone3",
    "enews",
    "affl1",
    "affll",
    "user-ip",
    "issueother",
    "input_8", #Issa's phone field
    "input_14", #issa's twitter field
    "privacyreleasemethod",
    "ctl04$facebookidcontrol",
    "uscgr",
    "twitter",
    "input_17",
    )

radio_choices = {
    "reason": "legsitemail",
    "newslettersignup": "0",
    "newsletter_action": "unsubscribe",
    "newsletter-subscribe": "",
    "subscribe": "n",
    "affl1": "",
    "affl": "",
    "aff11": "",
    "aff12": "",
    "affl21": "",
    "aff1": "",
    "affl12": "",
    "updates": "no",
    "enewsletteroption": "eoptout",
    "rsptype": "email",
    "forums": "forums_no",
    "required-newsletter": "noAction",
    "887_ctl00$ctl22$ReplyChoice_radio": "Yes, I would like a response.",

}

custom_mapping = {
    "2_field_420f4180-d327-4c63-aac5-efd047b1b463_text": "zip5",
    "21_subject_select" : "topicarea",
    "message topic": "topicarea",
    "message_topic": "topicarea",
    "18_field_1f16bf7a-1773-4479-bc8f-995d37e73f17_radio": "response_requested",
    "23_field_db3de26e-1334-48c8-ac2a-d173968c6236_radio": "response_requested",
    "23_field_d401e225-88e5-407f-8efa-da1a2e2b979e_radio" : "response_requested",
    "24_i02": "message",
    "25_field_71436f5b-bd9c-4d93-b4ea-279d62bf4ab7_radio":"response_requested",
    "33_field_ccfdbe3a-7b46-4b3f-b920-20416836d599_textarea": "message",
    "37_affl3": "enews_subscribe",
    "37_field_302e8a41-000d-419e-991e-40c7cb96f97c_radio": "topicarea",
    "39_subject_radio": "topicarea", #this form uses radio buttons instead of dropdown for subject
    "64_field_38fba043-11a4-46cc-be06-78afff4ce884_radio": "response_requested",
    "141_enews_select": "response_requested",
    "146_topic_checkbox": "topicarea",
    "148_radiogroup1_radio": "response_requested",
    "230_phone3_text": "phone_prefix",
    "230_phone4_text": "phone_line",
    "477_radiogroup1_radio": "response_requested",
    "503_contact_pref_radio": "response_requested",
    "554_number_text": "address_split_number",
    "554_name_text": "address_split_street", 
    "554_quadrant_select": "address_split_quadrant", 
    "554_apartment_text": "address_split_suite", 
    "566_field_f14022b2-ce41-4b48-baaa-3ea936d0dc49_text": "firstname",
    "566_field_b1cbecaf-fa94-47ce-8e08-413af45c40a3_text": "lastname",
    "566_field_d9fc9586-2976-4549-af04-9cb756a4ccf6_text": "address1",
    "566_field_e593f76a-3be3-4e05-8b68-fd4c067eea76_text": "address2",
    "566_field_40d5d76f-f7f7-4d8b-bb9d-57bc5161e745_text": "city",
    "566_field_d8006472-32dd-437c-8e3a-9ec6919a1200_select": "state",
    "566_field_d612f7d3-c97e-40b4-9525-a3fb97965c23_text": "zipcode",
    "566_field_34077b89-d0f0-42cf-a62e-26a3cdefeab8_text": "phone",
    "566_field_502cc83d-39f8-415e-8205-061f1b2f23fa_select": "topicarea",
    "566_field_7694661f-5de4-433e-8682-3972ebcf2e27_text": "subjectline",
    "566_field_5d0df2c0-8a69-4230-aab8-b0f872ceb818_textarea": "message",
    "613_zipcode_text": "zip5",
    "624_phone_prefix_text" : "phone_areacode",
    "624_phone_first_text" : "phone_prefix",
    "624_phone_second_text" : "phone_line",
    "659_contact[postal_code]_text": "zip5",
    "666_daytime-phone_text": "phone",
    "721_field_5eb7428f-9e29-4ecb-a666-6bc56b6a435e_radio": "response_requested",
    "728_phone1_text": "phone_areacode",
    "728_phone2_text": "phone_prefix",
    "728_phone3_text": "phone_line",
    "740_phone_prefix_text": "phone_areacode",
    "740_phone_first_text": "phone_prefix",
    "740_phone_second_text": "phone_line",
    "741_field_0150929b-ae7d-4ec8-ac86-647e121e8610_text": "zip5",
    "741_field_a8731eec-5954-4ac5-a623-b840d3f4d9fc_select": "topicarea",
    "741_field_59e68b70-1f23-4b9a-a19c-e40156896a9b_textarea": "message",
    "752_input_1_12_select": "prefix",
    "752_input_1_16_text": "message",
    "755_field_e5d28fe4-5b68-4619-9940-81168686475d_radio": "response_requested",
    "757_name_text": "firstname",
    "761_phone1_text": "phone_areacode",
    "761_phone2_text": "phone_prefix",
    "761_phone3_text": "phone_line",
    "765_zipCode_text": "zip5",
    "789_phone8_text": "phone",
    "817_areacode_text" : "phone_areacode",
    "817_phone3_text" : "phone_prefix",
    "817_phone4_text" : "phone_line",
    "832_phone1_text" : "phone_areacode",
    "832_phone2_text" : "phone_prefix",
    "832_phone3_text" : "phone_line",
    "836_phone1_text" : "phone_areacode",
    "836_phone2_text" : "phone_prefix",
    "836_phone3_text" : "phone_line",
    "839_field_310ab902-1d78-4444-849d-077807c25eaf_text" : "address2",
    "839_field_83770021-924f-4be5-b642-98871ec90dee_text" : "zip5",
    "839_field_ad57e3b4-5705-489d-be8a-ee887514258c_select": "topicarea",
    "839_field_88cf096a-902e-4abd-9832-f24dcc3b9ee2_textarea": "message",
    "842_J01": "subjectline",
    "842_field_f6958bc0-eb9a-41ae-ad61-57221e74199f_text": "topicarea",
    "842_field_e9e2e61c-2fa8-40c3-8e90-374a97fd3322_radio": "response_requested",
    "849_radiogroup1_radio": "response_requested",
    "864_phone_prefix_text" : "phone_areacode",
    "864_phone_first_text" : "phone_prefix",
    "864_phone_second_text" : "phone_line",
    "920_required_phone1_text" : "phone_areacode",
    "920_required_phone2_text" : "phone_prefix",
    "920_required_phone3_text" : "phone_line",
    "920_phone1_text" : "phone_areacode",
    "920_phone2_text" : "phone_prefix",
    "920_phone3_text" : "phone_line",
    "942_phone1_text" : "phone_areacode",
    "942_phone2_text" : "phone_prefix",
    "942_phone3_text" : "phone_line",
    "978_phone3_text" : "phone_prefix",
    "978_phone4_text" : "phone_line",
    "1028_required-response_select":"response_requested",
    "1089_proceeding_select": "topicarea",
}

custom_overrides = {
    "18_prefix2_select": "Yes",
    "29_subject_radio": "CRNR", # no response requested
    "37_state_id_select": "83c503f1-e583-488d-ac7f-9ff476cfec25", #WTF Feinstein's form, seriously.
    "37_field_a3ffd5e3-91d9-4394-8aa0-52c160f1a94c_radio": "Y",
    "38_subsubject_select": "Other",
    "44_nl_radio": "no",
    "44_nl_format_radio": "text",
    "68_modified_hidden": "1",
    '73_re_select': 'issue',
    '74_field_c1492f1b-346e-4169-a569-80bc5f368d2e_radio': 'NO', #response req.
    '99_district-contact_text': 'InD',
    '107_response_radio': '1NR',
    '118_enews_subscribe_radio': '',
    '122_thall_radio': '',
    '140_phonetype_radio': 'voice',
    '140_contact_pref_radio': "no response necessary",
    '146_queryc112_text': '', # misparsed
    '146_docidc112_text': '', # misparsed
    '146_queryc112_hidden': '', # misparsed
    '146_url_select': '', # misparsed
    '146_subscription_radio': '', # misparsed
    '156_fp_fld2parts-fullname_text': '', # parse bug
    '157_newsletter_radio': 'noAction',
    '174_textmodified_hidden': 'yes',
    '179_affl_radio': 'on',
    "179_required-issue_select": "Comment on Policy",
    '198_field_5eb7428f-9e29-4ecb-a666-6bc56b6a435e_radio': 'NO', #response req
    '204_action_radio': '', # subscribe
    '345_enews_radio': '',
    "355_opt_radio":"no",
    "426_aff1_radio": "<AFFL>Subscribe</AFFL>",
    "503_phonetype_radio": "voice",
    "550_issue_type_radio": "issue",
    #"566_field_502cc83d-39f8-415e-8205-061f1b2f23fa_select": "AGR", #Rubio's form is choking on issue areas, which is generating unexpected responses instead of SRs. Fix what can be fixed, then uncomment to get the rest of them in.
    "568_subject_radio": "CRNR", # no response
    "568_idresident_radio": "yes",
    "576_group1_radio": "N",
    "583_affl1_select": "no action",
    "584_msub_select": "Other",
    "585_enews_select": "no",
    "585_affl1_select": "no",
    "590_response_select": "newsNo",
    "593_main-search_text": "",
    "610_ecclesiastical_toggle_select":"",
    "610_ecclesiastical_title_select":"",
    "611_aff1req_text": "fill",
    "629_suffix_select" : "",
    "637_radiogroup1_radio": "n",
    "639_aff1req_text": "fill",
    "644_subcategory_select": "",
    "645_yes_radio": "NRN",
    "645_authfailmsg_hidden": "/andrews/AuthFailMsg.htm",
    "658_human_radio": "on",
    "661_subject_hidden": "",
    "661_reqresponse_radio": "on",
    "661_issues_select": "",
    "661_issues2_select": "",
    "689_field_07c7727a-6c47-4ff9-a890-c904fa4d408f_radio": "express an opinion or share your views with me",
    "690_aff2_radio": "",
    "694_affll_radio": "No",
    "709_choice_select": "",
    "732_field_1807499f-bb47-4a2b-81af-4d6c2497c5e5_radio": " ",
    "741_field_217b8539-2613-4996-852b-f56184a42b20_radio": "email",
    "746_aff1req_text": "",
    "747_affl1_radio": "TEST",
    "748_messagetype_radio": "express an opinion or share your views with me",
    "757_add2_text": "",
    "757_affl_select": "no-action",
    "761_contact_nature_select": "comment or question",
    "761_enews_radio": "no",
    '764_phonetype_radio': 'voice',
    "776_formfield1234567891_text":"0",
    "776_formfield1234567892_text":"2",
    "776_formfield1234567894_text": "",
    "784_enews_radio": "",
    "789_affl1_radio": "",
    "791_typeofresponse_select": "email",
    "805_issue_radio": "",
    "808_enewssign_radio": "<AFFL_DEL>Subscribe</AFFL_DEL>",
    "830_contactform:cd:rblformat_radio": "html",
    "830_email_radio": "",
    "838_state_select": "KYKentucky",
    "839_field_5fef6d8e-3cf0-4915-aaec-a017cfbf311c_radio": "voice",
    "867_message-type_radio":"legislative",
    "869_aff1req_text": "",
    "886_submitted[delivery_agent_prefix]_select" : "2",
    "886_submitted[delivery_agent_first_name]_text" : "Annalee",
    "886_submitted[delivery_agent_last_name]_text" : "Flower Horne",
    "886_submitted[delivery_agent_email]_email" : "info@popvox.com",   
    "930_newsletter_radio": "noAction",
    '1060_phonetype_radio': 'voice',
    '1088_id_authorCountryAbbr_select': 'USA',
    '1088_usertype_radio': 'member',
    '1093_subscribe_select': 'N',
}

# Supply additional POST data from the message object that doesn't correspond to a form field.
custom_additional_fields = {
    757: { "zip4": "zip4" },
    870: { "address": "address_combined", "city": "city" }, # required fields not actually on form because he doesn't care
}

class WebformParseException(Exception):
     def __init__(self, value):
          self.parameter = value
     def __str__(self):
          return str(self.parameter)
           
class SelectOptionNotMappable(WebformParseException):
     def __init__(self, description, formfield, values, options):
          self.description = description
          self.formfield = formfield
          self.values = values # list of potential values to send, ordered by preference
          self.options = options # list of available options
     def __str__(self):
          return str(self.description)

class SubmissionSuccessUnknownException(Exception):
     def __init__(self, value):
          self.parameter = value
     def __str__(self):
          return str(self.parameter)

class DistrictDisagreementException(Exception):
    pass

class SubjectTooLongException(Exception):
    pass

class AddressRejectedException(Exception):
    pass

def find_webform(htmlstring, webformid, webformurl):
    # cut out all table tags because when tables are mixed together with forms
    # html5lib can reorder the tags so that the fields fall out of the form.
    htmlstring = re.sub("</?(table|tr|td|tbody|TABLE|TR|TD|TBODY)( [^>]*)?>", "", htmlstring)
    
    # change all tag names to lower case
    htmlstring = re.sub(r"<(/?)([A-Z]+)", lambda m : "<" + (m.group(1) if m.group(1) != None else "") + m.group(2).lower(), htmlstring)
    
    # remove <noscript> because we DO evaluate it and html5lib's parser treats it as CDATA basically
    htmlstring = re.sub(r"</?noscript>", "", htmlstring)
    
    # make sure all input tags are closed
    #htmlstring = re.sub(r"(<input[^/]+?)(checked)?>", lambda m : m.group(1) + ("" if m.group(2) == None else "checked='1'") + "></input>", htmlstring)

    doc = html5lib.HTMLParser(tree=html5lib.treebuilders.getTreeBuilder("dom")).parse(htmlstring)
    
    formmethod = "POST"
    formaction = None
    
    # scan <form>s
    altforms = []
    for form in doc.getElementsByTagName("form"):
        if form.getAttribute("id") == webformid or \
            form.getAttribute("name") == webformid or \
            webformid in ["." + x for x in form.getAttribute("class").split()] or \
            webformid[0] == "@" and webformid[1:] in form.getAttribute("action") or \
            webformid == "@@" or\
            webformid == "@@empty" and form.getAttribute("action")=="":
            if form.getAttribute("action") != "":
                formaction = urlparse.urljoin(webformurl, form.getAttribute("action"))
            else:
                formaction = webformurl
            if form.getAttribute("method") != "":
                formmethod = form.getAttribute("method")
                
            return doc, form, formaction, formmethod
    
        altforms.append( (form.getAttribute("id"), form.getAttribute("name"), form.getAttribute("class"), form.getAttribute("action")) )

    #print htmlstring
    raise WebformParseException("Form %s is missing at %s. Choices are: %s" % (webformid, webformurl, ", ".join([repr(s) for s in altforms])))

def parse_webform(webformurl, webform, webformid, id, dr):
    #print webform
    doc, form, formaction, formmethod = find_webform(webform, webformid, webformurl)
    
    fields = []
    fieldlabels = { }
                
    for field in form.getElementsByTagName("input") + form.getElementsByTagName("select") + form.getElementsByTagName("textarea"):
        if field.getAttribute("type").lower() in ("image", "button"):
            continue
        if field.getAttribute("name").strip() == "":
            continue
        
        # Rep. Tammy Baldwin has two <select> elements with the same id/name, but the
        # second should be ignored.
        if field.getAttribute("gtbfieldid") == "133":
            continue
            
        ## Look at any preceding text.
        #if not field.hasAttribute("id") and field.previousSibling != None and field.previousSibling.data != None:
        #    field.parentNode.normalize()
        #    field.setAttribute('id', field.getAttribute("name"))
        #    fieldlabels[field.getAttribute("name")] = re.sub("[^a-zA-Z0-9]", "", re.sub(".*\n", "", field.previousSibling.data)).lower()
        
        options = None
        if field.nodeName == "select":
            options = { }
            for opt in field.getElementsByTagName("option") + field.getElementsByTagName("OPTION"):
                opttext = ""
                opt.normalize()
                if opt.firstChild != None:
                    opttext = opt.firstChild.data
                    opttext = re.sub("^\W+", "", opttext)
                    opttext = re.sub("\s+$", "", opttext)
                    opttext = re.sub("\s+", " ", opttext)
                    opttext = re.sub(u"\xa0", "", opttext) # ?
                    if opttext == "" or "select" in opttext or "=" in opttext or opttext[0] == "-":
                        continue
                    if "required-" in field.getAttribute("name") and opt.hasAttribute("value") and opt.getAttribute("value").strip() == "":
                        continue # confusing if the field is required
                
                options[opttext.lower()] = opt.getAttribute("value") if opt.hasAttribute("value") else opttext
                
        elif field.getAttribute("type") == "checkbox":
            # just ignore checkboxes --- they should be to subscribe
            # users to the office's email list. We want to ignore them
            # outright because we want to specifically NOT submit
            # their value.
            continue
            
        elif field.getAttribute("type") == "radio":
            val = field.getAttribute("value")
            #if not field.hasAttribute("value"):
            #    val = "on" # specification says value is required, but Chrome submits "on" if it is missing so we'll do the same
            
            for fieldtype, attr, attrid, default_value, options, maxlen in fields:
                if fieldtype == "radio" and attr == field.getAttribute("name"):
                    options[field.getAttribute("value").lower()] = val
                    break
            else:
                fields.append( ("radio", field.getAttribute("name"), field.getAttribute("id"), val, { val.lower(): val }, None))
            continue
                
        fieldtype = field.nodeName
        if fieldtype == "input":
            if field.getAttribute("type") == "":
                fieldtype = "text"
            else:
                fieldtype = field.getAttribute("type")
                
        if field.getAttribute("style") == "display: none;":
            fieldtype = "hidden"
        
        fields.append( (fieldtype.lower(), field.getAttribute("name"), field.getAttribute("id"), field.getAttribute("value") if field.hasAttribute("value") else None, options, field.getAttribute("maxlength")))

    # scan <label>s
    for label in doc.getElementsByTagName("label"):
        label.normalize()
        try:
            fieldlabels[label.getAttribute("for")] = re.sub("[^a-zA-Z0-9]", "", label.firstChild.data).lower()
        except:
            # missing child or text in element
            pass
        
    if len(fields) == 0:
        raise WebformParseException("Form %s has no fields at %s." % (webformid, webformurl))
        
    # Map the form fields to our data structure and construct the POST data.

    # Create a mapping from form field names to source attributes
    # in our message objects.
    field_map = { }
    field_options = { }
    field_default = { }
    
    for fieldtype, attr, attrid, default_value, options, maxlength in fields:
        field_options[attr] = options
        
        ax = attr.lower()
        
        ax = ax.replace("contactform:cd:txt", "")
        ax = ax.replace("contactformcdtxt", "")
        ax = ax.replace("contactformcdddl", "")
        ax = ax.replace("contactformcimtxt", "")
        ax = ax.replace("contactform$cd$txt", "") # 830
        ax = ax.replace("contactform$cd$ddl", "") # 830
        ax = ax.replace("contactform:cd:ddl", "") # 830
        ax = ax.replace("contactform$cim$txt", "") # 830
        ax = ax.replace("contactform:cim:txt", "") # 830

        if ax.startswith("ctl00$") and ax.endswith("$zip"): ax = "zip5"
        if id == 636 and ax == "zipcode": ax = "zip5"
        
        ax = ax.replace("ctl00$contentplaceholderdefault$newslettersignup_1$", "")
        ax = ax.replace("ctl00$contentplaceholderdefault$runwaymastercontentplaceholder$item1$maincontactform_4$", "")
        
        ax = re.sub(r"^(req(uired)?[\-\_]|ctl\d+\$ctl\d+\$)", "", ax)
        ax = re.sub(r"[\-\_]required$", "", ax)

        ax2 = ax + "_" + fieldtype.lower()
        
        if attr.lower() == "required-daytimephone": ax = "phone"
        
        if str(id) + "_" + ax + "_" + fieldtype.lower() in custom_overrides:
            field_default[attr] = custom_overrides[str(id) + "_" + ax + "_" + fieldtype.lower()]
            continue

        if fieldtype.lower() == "select" and len(options) == 0:
            raise WebformParseException("Select %s has no options at %s." % (ax, webformurl))

        if str(id) + "_" + ax + "_" + fieldtype.lower() in custom_mapping:
            field_map[attr] = custom_mapping[str(id) + "_" + ax + "_" + fieldtype.lower()]
            continue

        elif ax in common_fieldnames:
            # we know what this field means
            field_map[attr] = common_fieldnames[ax]
        
        elif ax2 in common_fieldnames:
            # we know what this field means
            field_map[attr] = common_fieldnames[ax2]
            
        elif attrid != "" and attrid in fieldlabels and fieldlabels[attrid].lower() in common_fieldnames:
            # there was a <label> for this field whose text was recognized
            # in common_fieldnames.
            field_map[attr] = common_fieldnames[fieldlabels[attrid].lower()]
                
        elif attrid in fieldlabels and fieldlabels[attrid].lower()+"_"+fieldtype.lower() in common_fieldnames:
            # there was a <label> for this field whose text was recognized
            # in common_fieldnames.
            field_map[attr] = common_fieldnames[fieldlabels[attrid].lower()+"_"+fieldtype.lower()]

        elif default_value != None and fieldtype.lower() in ("hidden", "submit"):
            # we don't recognize the field but it provided a default which we'll take
            field_default[attr] = default_value
            continue
        
        elif ax in skippable_fields or (attrid in fieldlabels and fieldlabels[attrid].lower() in skippable_fields):
            # we don't recognize the field but we consider it optional, and
            # we'll post it back with the empty string
            field_default[attr] = ""
            continue
            
        elif fieldtype in ("submit", "reset"):
            # even if submit buttons have a name, if they don't have a value
            # (which we would have handled earlier as a default value) we
            # don't need to submit anything.
            continue
            
        elif fieldtype == "radio" and ax in radio_choices:
            if not attr.startswith("required-") or radio_choices[ax] != "":
                field_default[attr] = radio_choices[ax]
            else:
                field_default[attr] = "on"
            continue

        elif ax == "zip4":
            field_default[attr] = ""
            continue
        #commenting out the first part of the fix for the recaptcha forms we can't break, because
        #fixing it part way makes it call dbc and return incorrect values, which takes time and
        #money. The pdb.set_trace()s below are for debugging why they're returning bad values.
        elif ax == "recaptcha_challenge_field": #or re.match(r'captcha_[0-9a-f\-_]*', ax):
            # Use DeathByCaptcha to solve it!
            
            # get the iframe URL which will open HTML which will have a challenge field and
            # an image URL, and load that image.
            m = re.search(r'<iframe src="(https?://www.google.com/recaptcha/api/noscript\?k=[\w\-]+)"', webform)
            #pdb.set_trace()
            if not m: raise WebformParseException("Form uses reCAPTCHA but the reCAPTCHA noscript iframe wasn't found.")
            recaptcha_iframe = m.group(1)
            iframe_content = urllib2.urlopen(recaptcha_iframe).read()
            m = re.search(r'<input type="hidden" name="recaptcha_challenge_field" id="recaptcha_challenge_field" value="(.*?)">', iframe_content)
            if not m: raise WebformParseException("Form uses reCAPTCHA but the reCAPTCHA iframe content challenge field wasn't found.")
            recaptcha_challenge_field = m.group(1)
            m = re.search(r'<img width="300" height="57" alt="" src="(image\?.*?)">', iframe_content)
            if not m: raise WebformParseException("Form uses reCAPTCHA but the reCAPTCHA iframe content image wasn't found.")
            image_content = urllib2.urlopen("http://www.google.com/recaptcha/api/" + m.group(1)).read()
            
            # solve the captcha
            import deathbycaptcha, StringIO
            dbc = deathbycaptcha.SocketClient(settings.DEATHBYCAPTCHA_USERNAME, settings.DEATHBYCAPTCHA_PASSWORD)
            print 'Calling DeathByCaptcha, remaining balance $%s.' % (dbc.get_balance()/100.0)
            solution = dbc.decode(StringIO.StringIO(image_content))
            #pdb.set_trace()
            if not solution: raise WebformParseException("Form uses reCAPTCHA but DeathByCaptcha returned nothing.")
                
            # post solution back to reCAPTCHA to get the manual solution key
            recaptcha_response = urllib2.urlopen(recaptcha_iframe, urllib.urlencode({ "recaptcha_challenge_field": recaptcha_challenge_field, "recaptcha_response_field": solution['text'], "submit": "I'm a human" })).read()
            m = re.search(r'<textarea rows="5" cols="100">(.*)</textarea>', recaptcha_response)
            if not m: raise WebformParseException("Form uses reCAPTCHA but reCAPTCHA response didnt seem to be correct: " + recaptcha_response)
            
            dr.dbc_captcha_id = solution["captcha"]
            field_default[attr] = m.group(1)
            continue
            
        elif re.match(r"captcha[0-9a-f\-_]*", ax) \
            and ax not in ("captcha_code", "captcha_0ad40428-0789-4ce6-91ca-b7b15180caca","captcha_a989233d-1b27-4ab7-a270-e7767f58cb9e",):
        #elif ax in ("captcha_28f3334f-5551-4423-a1b9-b5f136dab92d", "captcha_e90e060e-8c67-4c62-9950-da8c62b3aa45", "captcha_cfe7dc28-a627-4272-acd0-8b34aa43828a", "captcha_9214d983-ad97-49c8-ac2a-a860df3ee1df"):
            m = re.search(r'<img src="(/CFFileServlet/_cf_captcha/_captcha_img-?\d+\.png)"', webform)
            #m = re.search(r'src="(http://www.google.com/recaptcha/api/image\?c=[a-zA-Z0-9_-]*)"', webform)
            if not m:
                #pdb.set_trace()
                raise WebformParseException("Form uses a CAPTCHA but the CAPTCHA img element wasn't found.")
            try:
                print urlparse.urljoin(webformurl, m.group(1))
                image_content = urllib2.urlopen(urlparse.urljoin(webformurl, m.group(1))).read()
            except:
                raise WebformParseException("Form uses a CAPTCHA but the CAPTCHA img did not load.")
            
            # solve the captcha
            import deathbycaptcha, StringIO
            dbc = deathbycaptcha.SocketClient(settings.DEATHBYCAPTCHA_USERNAME, settings.DEATHBYCAPTCHA_PASSWORD)
            print 'Calling DeathByCaptcha, remaining balance $%s.' % (dbc.get_balance()/100.0)
            solution = dbc.decode(StringIO.StringIO(image_content))
            if not solution: raise WebformParseException("Form uses a CAPTCHA but DeathByCaptcha returned nothing.")
                
            dr.dbc_captcha_id = solution["captcha"]
            field_default[attr] = solution['text']
            continue
            
        elif ax in ("verification", "validation", "contactform$captcha", "contactform:captcha", "captcha_0ad40428-0789-4ce6-91ca-b7b15180caca"):
            m = re.search(r'<img src="((http://.*.(senate|house).gov/)?(captcha/\d+.cfm|.*/captcha.cfm\?CFID=.*?&CFTOKEN=.*?|CaptchaImage.aspx\?guid=[\w\-]+))"', webform)
            if not m: raise WebformParseException("Form uses a CAPTCHA but the CAPTCHA img element wasn't found.")
            image_url = urlparse.urljoin(webformurl, m.group(1))
            try:
                image_content = urlopen(image_url, {}, "GET", dr, store_as_next_referrer=False).read()
            except Exception as e:
                raise WebformParseException("Form uses a CAPTCHA but the CAPTCHA img did not load: " + unicode(e))
            
            if len(image_content) == 0:
                raise WebformParseException("Form uses a CAPTCHA but the CAPTCHA image content was empty from %s." % image_url)
            
            # solve the captcha
            import deathbycaptcha, StringIO
            dbc = deathbycaptcha.SocketClient(settings.DEATHBYCAPTCHA_USERNAME, settings.DEATHBYCAPTCHA_PASSWORD)
            print 'Calling DeathByCaptcha, remaining balance $%s.' % (dbc.get_balance()/100.0)
            solution = dbc.decode(StringIO.StringIO(image_content))
            if not solution: raise WebformParseException("Form uses a CAPTCHA but DeathByCaptcha returned nothing.")
                
            dr.dbc_captcha_id = solution["captcha"]
            field_default[attr] = solution['text']
            continue
            
        elif ax == "captcha_code":
            m = re.search(r'captcha_audio/captcha_([^\.]+)\.wav', webform)
            if not m: raise WebformParseException("Form uses a dumb CAPTCHA but the answer wasn't found.")
            field_default[attr] = m.group(1)
            continue

        else:
            raise WebformParseException("Unhandled field: " + repr((fieldtype, ax, fieldlabels[attrid] if attrid in fieldlabels else attrid, options)))
        
        if field_map[attr] == "zipcode" and maxlength == "5":
            field_map[attr] = "zip5"

    for k, v in field_map.items():
        if v == "zipcode" and "zip4" in field_map.values():
            v = "zip5"
        if v == "address1" and not "address2" in field_map.values():
            v = "address_combined"
        field_map[k] = v
        
    if id in custom_additional_fields:
        for htmlattr, msgfield in custom_additional_fields[id].items():
            field_map[htmlattr] = msgfield
            field_options[htmlattr] = None

    return field_map, field_options, field_default, formaction, formmethod

def test_zipcode_rejected(webform, deliveryrec):
    if "The zip code you typed in does not appear to be a zip code within my district" in webform\
        or "You might not be in my district" in webform \
        or "appears that you live outside of" in webform \
        or "You zipcode is not in Congressman Issa's district" in webform \
        or "A valid Zip code for the 5th District of Missouri was not entered" in webform\
        or "The zip code entered indicates that you reside outside the" in webform\
        or "Your zip code indicates that you are outside of the" in webform\
        or "multiple Representatives who share the 5-digit zip code which was entered" in webform\
        or "Your zip code is split between more that one Congressional District" in webform\
        or "The zip code you entered was either not found or not in our District" in webform\
        or "Zip Code Split Between Multiple Districts" in webform\
        or "Your zip code indicates that you live outside" in webform \
        or "This authentication has failed" in webform\
        or "<li>Zip Extension is required</li>" in webform\
        or "the zip code you entered is incomplete or lies outside of the boundaries" in webform\
        or "Access to the requested form is denied, the zip code which you entered" in webform\
        or "The zip code (or zip+4) entered is not a valid" in webform\
        or "I'm sorry, but Congressional courtesy dictates that I only reply to residents of" in webform\
        or "is not in Trent Frank's district" in webform\
        or "Postal code is not in Dan Burton's district" in webform\
        or "In order to confirm your address, please enter your full/correct ZIP+4 code on the previous page" in webform\
        or "I'm sorry, but it appears that you live outside of Florida's 6th Congressional district" in webform\
        or "is not in Bob Goodlatte's district" in webform\
        or "Your zip code is not an acceptable zip code." in webform\
        or "the zip code you entered is incomplete or lies outside" in webform\
        or "The zip code which was entered was not found." in webform\
        or "You belong to a different Congressional District" in webform\
        or "That address falls outside" in webform\
        or "We are sorry, but it appears that the zip code entered indicates that you reside outside of" in webform\
        or "The zip code (or zip+4) entered was not found to be a valid zip code or zip +4" in webform:
        deliveryrec.trace += u"\n" + webform.decode("utf8", "replace") + u"\n\n"
        raise DistrictDisagreementException()
    
def test_subject_toolong(webform, deliveryrec):
    if "Subject has exceeded the maximum length of 100 characters" in webform:
        deliveryrec.trace += u"\n" + webform.decode("utf8", "replace") + u"\n\n"
        raise SubjectTooLongException()
    
def send_message_webform(endpoint, msg, deliveryrec):
    # Load the web form and parse the fields.
    
    if not "#" in endpoint.webform:
        raise WebformParseException("Webform URL should specify a # and the id, name, .class, or @action of the form")
        
    alternate_post_url = None
    
    #regulations.gov uses hashmarks in their urls. Accounting for that with rsplit.
    webformurl, webformid = endpoint.webform.rsplit("#", 1)
    webform_stages = webformid.split(',')

    # enforce a delay between hits to the same target
    if webform_stages[0].startswith("delay:"):
        delay_secs = float(webform_stages.pop(0)[len("delay:"):])
        if deliveryrec.target.id in last_connect_time:
            current_delay = clock() - last_connect_time[deliveryrec.target.id]
            if current_delay < delay_secs:
                sleep(int(delay_secs - current_delay + 1.0))

    # Some webforms require a form POST just to get to the form.
    if webform_stages[0].startswith("post:"):
        postdata = webform_stages.pop(0)[len("post:"):]
        sleep(5)
        webform = urlopen(webformurl, postdata, "POST", deliveryrec).read()
    else:
        webform = urlopen(webformurl, {}, "GET", deliveryrec).read()

    if len(webform_stages) > 0 and webform_stages[0] == "add-district-zip-cookie":
        webform_stages.pop(0)
        extra_cookies["District"] = msg.zipcode
        
    # Some webforms are in two stages: first enter your zipcode to verify,
    # and then enter the rest of the info. To signal this, we'll give a pair
    # of form IDs.
    if webform_stages[0].startswith("zipstage:"):
        # This is a two-stage webform.
        webformid_stage1 = webform_stages.pop(0)[len("zipstage:"):]
        
        # Parse the fields.
        field_map, field_options, field_default, webformurl, formmethod = parse_webform(webformurl, webform, webformid_stage1, endpoint.id, deliveryrec)
        
        # Submit the zipcode to get the second stage form.
        postdata = { }
        for k, v in field_map.items():
            postdata[k] = getattr(msg, v)
            if type(postdata[k]) == tuple or type(postdata[k]) == list:
                # take first preferred value
                postdata[k] = postdata[k][0]
            postdata[k] = postdata[k].encode("utf8")
        for k, v in field_default.items():
            postdata[k] = v.encode("utf8")
        
        # Debugging...
        if False:
            print webformurl
            for k, v in postdata.items():
                print k, v
            return
            
        webform = urlopen(webformurl, postdata, formmethod, deliveryrec).read()
        
        if endpoint.id != 361: # text is always present in form
            test_zipcode_rejected(webform, deliveryrec)

        # Rep. Chandler via House WYR
        m = re.search(r'<meta http-equiv="refresh" content="0 ; URL=(https?:.*)"', webform)
        if m:
            webformurl = m.group(1).replace(" ", "%20")
            webform = urlopen(webformurl, {}, "GET", deliveryrec).read()
        
    if len(webform_stages) > 0 and webform_stages[0] == "add-district-zip-cookie":
        webform_stages.pop(0)
        extra_cookies["District"] = msg.zipcode

    webformid = webform_stages.pop(0) if len(webform_stages) > 0 else "<not entered>"
    try:
        field_map, field_options, field_default, formaction, formmethod = parse_webform(webformurl, webform, webformid, endpoint.id, deliveryrec)
    except:
        deliveryrec.trace += u"\n" + webform.decode('utf8', 'replace') + u"\n\n"
        raise

    # Make sure that we've found the equivalent of all of the fields
    # that the form should be accepting.
    if endpoint.endpointtype is 'c':
        for field in ("email", ("firstname", "name"), ("lastname", "name"), ("address1", "address_combined", "address_split_street"), ("address2", "address_combined", "address_split_street"), ("zipcode", "zip5"), "message"):
            if field == "email" and endpoint.id in [839, 886]: #form doesn't actually collect email address
                continue
            if field == "city" and endpoint.id == 554: # no need to collect city since there is only one city in DC
                continue
            if type(field) == str:
                field = [field]
            for f in field:
                if f in field_map.values():
                    break
            else:
                raise WebformParseException("Form does not seem to accept field " + repr(field) + " (we got " + ", ".join(field_map.values()) + ")")
    else: #executive endpoints generally require far less information.
        for field in ("email", ("firstname", "name"), ("lastname", "name"), "message"):
            if type(field) == str:
                field = [field]
            for f in field:
                if f in field_map.values():
                    break
            else:
                raise WebformParseException("Form does not seem to accept field " + repr(field) + " (we got " + ", ".join(field_map.values()) + ")")

    # Deliver message.
    
    # set form field values
    postdata = { }
    for k, v in field_map.items():
        postdata[k] = getattr(msg, v)
        if postdata[k] == None:
            raise WebformParseException("Message is missing field %s." % v)
        
        # Make sure that if there were options given for a prefix that they accept our
        # prefixes. We'll deal with the wrath of an unexpected response.
        if v == "prefix" and postdata[k] == "Reverend" and msg.firstname in ("Jacob", "Mike") and endpoint.id in (677, 691): postdata[k] = "Mr."
        if v == "prefix" and postdata[k] == "Dr." and msg.firstname in ("James","David") and endpoint.id in (57,710): postdata[k] = "Mr."
            # pretend they accept this... confusing to diagnose tho!
        #if v == "prefix" and field_options[k] != None: field_options[k]["reverend"] = "Reverend"
        #if v == "prefix" and field_options[k] != None: field_options[k]["pastor"] = "Pastor"
        #if v == "prefix" and field_options[k] != None: field_options[k]["dr."] = "Dr."
        
        # Make sure that if there were options given for a suffix that we accept a blank suffix.
        if v == "suffix" and field_options[k] != None: field_options[k][""] = ""
        
        def normalize_synreq_term2(opt):
            return re.sub(r"\s+", " ", opt)
        
        if field_options[k] == None:
            if type(postdata[k]) == tuple or type(postdata[k]) == list:
                # take first preferred value
                postdata[k] = postdata[k][0]
        else:
            # Must map postdata[k] onto one of the available options.
            if isinstance(postdata[k], str) or isinstance(postdata[k], unicode):
                postdata[k] = postdata[k].split(' #')
                if postdata[k][0].startswith("#"):
                    postdata[k][0] = postdata[k][0][:75]+"/"+str(CURRENT_CONGRESS)
            alts = []
            # For each value we have coming in from the message, also
            # try any of its mapped synonyms in the database,
            # and one transitive step for the case where a bill hashtag
            # maps to a CRS term which in turn has been mapped to a form option.

            for q in postdata[k]:
                alts.append((q, -1))
                for rec in Synonym.objects.filter(term1 = q):
                    alts.append((rec.term2, 0 if not rec.last_resort else 1))
                    if not rec.last_resort:
                        for rec2 in Synonym.objects.filter(term1 = rec.term2):
                            alts.append((rec2.term2, 0 if not rec.last_resort else 1))
            alts.sort(key = lambda x : x[1]) # put last_resort at the end
            
            # normalize
            for kk, vv in field_options[k].items():
                field_options[k][normalize_synreq_term2(kk)] = vv
                
            field_options_values = dict( (normalize_synreq_term2(v), v) for v in field_options[k].values() )
            
            for q, l_r in alts:
                if q.lower() in field_options[k]:
                    postdata[k] = field_options[k][q.lower()]
                    break
                elif q.lower()[:75] in field_options[k]:
                    postdata[k] = field_options[k][q.lower()[:75]]
                    break
                if q in field_options_values:
                    postdata[k] = field_options_values[q]
                    break
                elif q[:75] in field_options_values:
                    postdata[k] = field_options_values[q][:75]
                    break
            else:
                # There were no mappings from the keyword we have in the message to
                # one of the options on the form. Construct a list of the options so we can
                # store it in a SynonymRequired to be dealt with later.
                select_opts = [normalize_synreq_term2(kk) for kk in field_options[k].keys()]
                
                # Because of the one transitive step, we can expand the options to one
                # transitive step backwards from what's on the form. But only do this for
                # hashtag keywords because there's no sense in mapping CRS subject terms
                # to other CRS subject terms.
                if postdata[k][0].startswith("#"):
                    for syn in Synonym.objects.filter(term2__in=select_opts).exclude(term1__startswith="#").values("term1").distinct():
                        if syn["term1"] not in select_opts:
                            select_opts.append(normalize_synreq_term2(syn["term1"]))
                
                # Issue a delivery error that will also trigger an INSERT into the synonym required
                # table with term1set set to the keyword alternatives in the message postdata[k]
                # and term2set set to select_opts.
                #print postdata[k]
                raise SelectOptionNotMappable("Can't map value %s for %s into available option from %s." % (postdata[k], k, field_options[k]), k, postdata[k], select_opts)
        
        postdata[k] = postdata[k].encode("utf8")


        ### REALLY special cases
        # I think this was for Frankel or Walorski
        if k == "required-response":
            if "no" in  msg.response_requested:
                postdata[k] = "N"
            else:
                postdata[k] = "Y"

        # Calvert has a fake form item
        if endpoint.id == 934:
            if k == "ctl00$ctl14$Subject":
                postdata[k] = ''
                
        #Isakson won't take subjects over 100 chars
        if endpoint.id == 49:
            if v == 'subjectline':
                postdata[k] = postdata[k][0:99]
                

    for k, v in field_default.items():
        postdata[k] = v.encode("utf8")
        
    # Thess guys have some weird restrictions on the text input to prevent the user from submitting
    # SQL... rather than just escaping the input.
    if endpoint.id in (6, 13, 37, 61, 121, 124, 140, 147, 150, 159, 161, 166, 176, 192, 209, 221, 226, 228, 235, 244, 246, 280, 316, 319, 332, 324, 341, 386, 390, 410, 426, 458, 528, 556, 570, 577, 585, 586, 588, 598, 599, 600, 604, 605, 606, 607, 608, 610, 611, 613, 621, 639, 641, 646, 649, 652, 654, 663, 665, 674, 678, 688, 691, 693, 703, 706, 709, 710, 711, 713, 717, 718, 725, 730, 734, 736, 739, 746, 749, 750, 753, 756, 774, 775, 780, 783, 784, 787, 788, 789, 791, 798, 805, 807, 808, 809, 811, 826, 827, 837, 840, 850, 851, 857, 861, 869, 878, 882, 892, 899, 916, 946, 962, 988, 990, 1016, 1037, 1040, 1054, 1056, 1060, 1080, 1088):
        re_sql = re.compile(r"select|insert|update|delete|drop|--|alter|xp_|execute|declare|information_schema|table_cursor", re.I)
        for k in postdata:
            postdata[k] = re_sql.sub(lambda m : m.group(0)[0] + "." + m.group(0)[1:] + ".", postdata[k]) # the final period is for when "--" repeats

    # Debugging...
    if False:
        #pdb.set_trace()
        print formaction
        for k, v in postdata.items():
            print k, v
        return
            
    # submit the data via POST and check the result.
    
    # let us override the URL we post data to, to spoof Javascript
    if len(webform_stages) > 0 and webform_stages[0].startswith("post-to:"):
        formaction = webform_stages.pop()[len("post-to:"):]

    ret = urlopen(formaction, postdata, formmethod, deliveryrec)
    ret, ret_code, ret_url = ret.read(), ret.getcode(), ret.geturl()
    
    # if the response is the same form again, modulo changes to
    # VIEWSTATE and EVENTVALIDATION fields, then obviously it
    # failed because there will be no success message.
    compare = [webform, ret]
    for i in xrange(len(compare)):
        compare[i] = re.sub('id="__(VIEWSTATE|EVENTVALIDATION)" value=".*?"', "", compare[i]).strip()
    if compare[0] == compare[1]:
        deliveryrec.trace += u"\n" + ret.decode('utf8', 'replace') + u"\n\n"
        raise WebformParseException("Page did not change after form submission.")
    
    if endpoint.id != 361: # text is always present in form
        test_zipcode_rejected(ret, deliveryrec)

    # If this form has a final stage where the user is supposed to verify
    # what he entered, then re-submit the verification form presented to
    # him with no change.
    if len(webform_stages) > 0 and webform_stages[0].startswith("verifystage:"):
        webformid_stage2 = webform_stages.pop(0)[len("verifystage:"):]
        try:
            doc, form, formaction, formmethod = find_webform(ret, webformid_stage2, formaction)
        except WebformParseException:
            deliveryrec.trace += u"\n" + ret.decode('utf8', 'replace') + u"\n\n"
            raise
                    
        postdata = { }
        for field in form.getElementsByTagName("input") + form.getElementsByTagName("select") + form.getElementsByTagName("textarea"):
            if field.getAttribute("name").strip() == "":
                continue
            if field.nodeName == "select":
                for opt in field.getElementsByTagName("option"):
                    if opt.hasAttribute("selected"):
                        postdata[field.getAttribute("name").encode("utf8")] = opt.getAttribute("value").encode("utf8") if opt.hasAttribute("value") else opt.firstChild.data.encode("utf8")
            else:
                postdata[field.getAttribute("name").encode("utf8")] = field.getAttribute("value").encode("utf8")
                
        # submit the data via POST and check the result.
        ret = urlopen(formaction, postdata, formmethod, deliveryrec)
        ret, ret_code, ret_url = ret.read(), ret.getcode(), ret.geturl()
    
        test_zipcode_rejected(ret, deliveryrec)
    
    if ret_code == 404:
        raise IOError("Form POST resulted in a 404.")
    
    if type(ret) == str:
        ret = ret.decode('utf8', 'replace')

    if "experiencing technical difficulties" in ret:
        deliveryrec.trace += u"\n" + ret + u"\n\n"
        raise IOError("The site reports it is experiencing technical difficulties.")

    if "Phone number must be 10 digits" in ret:
        raise WebformParseException("Phone number must be 10 digits")
    
    if "&success=true" in ret_url:
        return
        
    if ret.strip() in ("", "<BR>"):
        raise IOError("Response is empty or essentially empty.")
    
    if "The street number in the input address was not valid" in ret\
        or "An exact street name match could not be found" in ret:
        deliveryrec.trace += u"\n" + ret + u"\n\n"
        raise AddressRejectedException("Address rejected: street number.")
        

    re_red_error = re.compile('<span id=".*_(.*Error)"><font color="Red">(.*?)</font></span>')
    m = re_red_error.search(ret)
    if m:
        if m.group(1) == "AddressError":
            raise AddressRejectedException("Address rejected: " + m.group(2))
    
        raise WebformParseException("Form-reported " + m.group(1) + ": " + m.group(2))

    re_class_error = re.compile(r'class="custom_form_error">\*?(.*?)<')
    m = re_class_error.search(ret)
    if m:
        raise WebformParseException("Form-reported " + m.group(1))
    
    for s in ("Invalid CAPTCHA value", "incorrect validation code", "Captcha failure", "Your secret code was not entered correctly", "Captcha Code does not match"):
        if s in ret:
            import deathbycaptcha, StringIO
            if hasattr(deliveryrec, "dbc_captcha_id"):
                dbc = deathbycaptcha.SocketClient(settings.DEATHBYCAPTCHA_USERNAME, settings.DEATHBYCAPTCHA_PASSWORD)
                print 'Calling DeathByCaptcha to report incorrect value.'
                try:
                    dbc.report(deliveryrec.dbc_captcha_id)
                except Exception as e:
                    print '...reporting failed: ' + str(e)
            
            raise WebformParseException("Response says invalid CAPTCHA value: " + s)

    #A lot of the forms use the same/similar responses; checking if any of those match before calling it an error:
    common_responses = [ "Thank you for contacting me",
    "Your form has been submitted",
    "Thank You! Your message has been sent",
    "Thank you for your e-mail submission",
    "Thank you for your email",
    "Thank you for contacting my office",
    "Thank you for contacting our office",
    "Thank you for your message",
    "Thank you for submitting your information",
    "The following information was sent to us",
    "Thank you for sending me your email",
    "Thank you for your correspondence",
    "The following information has been submitted",
    "Thank you for taking the time to write me"
    "Thank you, your message has been submitted",
    "Thank you for taking the time to write me",
    "Thank you for taking the time to share your thoughts and concerns with me",
    "Thank you for taking the time to contact me",
    "Your form has been successfully submitted",
    "Your request has been successfully submitted",
    "Your message has been successfully submitted",
    "Your email has been successfully submitted",
    "Your message has been submitted",
    "Your message has been received",
    "We have received your message"]
    
    for x in common_responses:
        if x in ret:
            return
            
    if endpoint.webformresponse == None or endpoint.webformresponse.strip() == "":
        deliveryrec.trace += u"\n" + ret + u"\n\n"
        raise SubmissionSuccessUnknownException("Webform's webformresponse text is not set.")
    
    if endpoint.webformresponse in ret:
        return
        
    deliveryrec.trace += u"\n" + ret + u"\n\n"
    raise SubmissionSuccessUnknownException("Success message not found in result.")

def send_message_housewyr(msg, deliveryrec):
    # Submit the state and ZIP+4 to get the main webform.
    writerep_house_gov = "https://writerep.house.gov/htbin/wrep_findrep"
    ret = http.open(writerep_house_gov, 
        urllib.urlencode({ "state": msg.state + statenames[msg.state], "zip": msg.zip5, "zip4": msg.zip4 }))
    if ret.getcode() != 200:
        raise IOError("Problem loading House WYR form: " + str(ret.getcode()))
    ret = ret.read()
    
    if "To prevent this practice we ask" in ret:
        doc, form, formaction, formmethod = find_webform(ret, "@wrep_findrep", writerep_house_gov)
        for label in doc.getElementsByTagName("label"):
            if label.getAttribute("for") == "HIP_response":
                resp = None
                
                numberz = r"(one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
                def nummap(n):
                    m = {"one":1, "two":2, "three":3, "four":4, "five":5, "six":6, "seven":7, "eight":8, "nine":9, "ten": 10}
                    if n in m: return m[n]
                    return int(n)
                
                m = re.match(r"What is " + numberz + " minus " + numberz + "\?", label.firstChild.data)
                if m != None: resp = nummap(m.group(1)) - nummap(m.group(2))
                
                m = re.match(r"What is the sum of " + numberz + " plus " + numberz + "\?", label.firstChild.data)
                if m != None: resp = nummap(m.group(1)) + nummap(m.group(2))
                
                m = re.match(r"Please solve the following math problem: " + numberz + " x " + numberz + "\?", label.firstChild.data)
                if m != None: resp = nummap(m.group(1)) * nummap(m.group(2))
                
                m = re.match(r"Which of the following numbers is largest: (.*)\?", label.firstChild.data)
                if m != None:
                    nn = m.group(1).replace("or", "").replace(" ", "").split(",")
                    resp = max([nummap(n) for n in nn])
                    
                m = re.match(numberz + r" : What number appears at the beginning of this question\?", label.firstChild.data)
                if m != None: resp = nummap(m.group(1))
                
                if label.firstChild.data == "What is the first letter of this question?":
                    resp = "W"
                
                if resp == None:
                    print "Unrecognized WYR captcha:", label.firstChild.data
                    return False
                ret = http.open(formaction, urllib.urlencode({ "HIP_response": resp }))
                if ret.getcode() != 200:
                    raise IOError("Problem loading House WYR form: " + str(ret.getcode()))
                ret = ret.read()
                break
        else:
            print "Couldn't find WYR captcha text."
            return False
    
    # Check if there is an actual webform, otherwise WYR is not
    # supported on this address.
    if "Write Your Representative general error message" in ret or not "Continue to Text Entry Form" in ret:
        return False
                    
    # Submit the address, then the comment....
    
    webformurl = writerep_house_gov
    for formname, responsetext in (("@/htbin/wrep_const", '/htbin/wrep_save'), ("@/htbin/wrep_save", "Your message has been sent.|I want to thank you for contacting me through electronic mail|Thank you for contacting my office|Thank you for getting in touch|Your email has been submitted|I have received your message|Your email has been submitted|Thank You for Your Correspondence|your message has been received|we look forward to your comments|I have received your message|Thanks for your e-mail message|I will be responding to your email in specific detail|Thank you for your message|Your message has been received|Thank you for taking the time to contact me|Thank you for contacting me by email|Thank you for contacting me through Write Your Representative|Thank you for contacting me and my staff!|<h2>Thank you for writing.</h2>|Thank you again for your comments")):
        field_map, field_options, field_default, webformurl, formmethod = parse_webform(webformurl, ret, formname, "housewyr", deliveryrec)
        
        postdata = { }
        for k, v in field_map.items():
            d = getattr(msg, v)
            if type(d) == tuple or type(d) == list:
                d = d[0]
            postdata[k] = d.encode("utf8")
        for k, v in field_default.items():
            postdata[k] = v
            
        ret = urlopen(webformurl, postdata, formmethod, deliveryrec)
        if ret.getcode() != 200:
            raise IOError("Form POST resulted in an error.")
        
        ret = ret.read()
        ret = ret.decode('utf8', 'replace')
        
        for rt in responsetext.split("|"):
            if rt in ret:
                break
        else: # not found
            deliveryrec.trace += u"\n" + ret + u"\n\n"
            raise SubmissionSuccessUnknownException("Success message not found in result.")
                    
    # Success.
        
    deliveryrec.success = True
    deliveryrec.failure_reason = DeliveryRecord.FAILURE_NO_FAILURE
    
    return True

def send_message(msg, endpoint, previous_attempt, loginfo):
    global extra_cookies
    global http_last_url

    cookiejar.clear()
    extra_cookies = { }
    http_last_url = ""
    
    # Check for delivery information.
    
    method = endpoint.method
    govtrackrecipientid = endpoint.govtrackid
    if govtrackrecipientid != 0:
        mm = getMemberOfCongress(govtrackrecipientid)
        if "current" not in mm or mm["type"] not in ('sen', 'rep'):
            if govtrackrecipientid != 400629:
                raise Exception("Recipient is not currently in office as a senator or representative.")

        if endpoint.method == Endpoint.METHOD_NONE:
            if mm["type"] == "rep":
                method = Endpoint.METHOD_HOUSE_WRITEREP

    if method == Endpoint.METHOD_NONE:
        return None
        
    # Create a new DeliveryRecord as a trace of what we are about to do.

    deliveryrec = DeliveryRecord()
    deliveryrec.target = endpoint
    deliveryrec.method = endpoint.method
    deliveryrec.success = False
    if govtrackrecipientid == 0:
        deliveryrec.trace = unicode(loginfo) + u" to " + endpoint.office + u"\n" + unicode(msg.xml()) + u"\n\n"
    else:
        deliveryrec.trace = unicode(loginfo) + u" to " + getMemberOfCongress(govtrackrecipientid)["sortkey"] + u" (" + unicode(govtrackrecipientid) + u")\n" + unicode(msg.xml()) + u"\n\n"
    deliveryrec.failure_reason = DeliveryRecord.FAILURE_NO_FAILURE
    deliveryrec.save()

    if previous_attempt != None:
        previous_attempt.next_attempt = deliveryrec
        previous_attempt.save()
    
    # Generate some additional fields.
    msg.name = msg.firstname + " " + msg.lastname
    msg.address_combined = msg.address1 + ("" if msg.address2 == "" else "; " + msg.address2)
    if len(msg.zipcode) == 5:
        # if we only have a 5-digit zip code, make up the +4 based on the congressional
        # district.
        alt_zip = None
        try:
            alt_zip = get_zip_plus_four(msg.zipcode, msg.state, msg.congressionaldistrict)
        except:
            try:
                print "zipcode error: "+str(msg.id)
                pass
            except AttributeError:
                pass
        if not alt_zip:
            from popvox.models import PostalAddress
            try:
                alt_zip = PostalAddress.objects.filter(state=msg.state, congressionaldistrict=msg.congressionaldistrict, zipcode__startswith=msg.zipcode+"-")[0].zipcode
            except IndexError:
                pass
        if alt_zip:
            msg.zipcode = alt_zip
    if len(msg.zipcode.split("-")) != 2:
        msg.zip5 = msg.zipcode
        msg.zip4 = "0000" # some forms need the field filled in, and when there is no +4 for the ZIP code, 0000 works
    else:
        msg.zip5, msg.zip4 = msg.zipcode.split("-")
    msg.phone_areacode = "".join([c for c in msg.phone + "0000000000" if c.isdigit()])[0:3]
    msg.phone_prefix = "".join([c for c in msg.phone + "0000000000" if c.isdigit()])[3:6]
    msg.phone_line = "".join([c for c in msg.phone + "0000000000" if c.isdigit()])[6:10]
    if govtrackrecipientid == 400633 and len(msg.phone) > 0 and msg.phone[0] == '1': msg.phone = msg.phone[1:]
    if govtrackrecipientid in (400616,400055,412469,412249,412469,400076,412309):
        msg.phone = "".join([d for d in msg.phone if d.isdigit()])
        if msg.phone[0] == "1": msg.phone = msg.phone[1:]
        msg.phone = msg.phone[0:10]
        if govtrackrecipientid in (412249,412309) and msg.phone != "":
            msg.phone = ("%s-%s-%s" % (msg.phone[0:3], msg.phone[3:6], msg.phone[6:10]))
        if govtrackrecipientid == 412469 and msg.phone != "":
            msg.phone = ("(%s)%s-%s" % (msg.phone[0:3], msg.phone[3:6], msg.phone[6:10]))
    #if govtrackrecipientid == 400295:
    #    # for Rep. Norton, the street address is split
    #    m = re.match(r"(\d+[a-zA-Z]?)\s+(.+?)\s+(N\.?E\.?|N\.?W\.?|S\.?E\.?|S\.?W\.?)\s*(.*)", msg.address1, re.I)
    #    if m:
    #        msg.address_split_number = m.group(1)
    #        msg.address_split_street = m.group(2)
    #        msg.address_split_quadrant = m.group(3).replace(".", "")
    #        msg.address_split_suite = m.group(4)
    #    else:
    #        # can't deliver without those fields
    #        print msg.address1
    #        return None
    if govtrackrecipientid == 400062:
        # Lois Capps accepts a space if a response is required
        if "yes" in msg.response_requested:
            msg.response_requested = list(msg.response_requested) + [" "]

    # Begin the delivery attempt.
    try:
        
        if method == Endpoint.METHOD_WEBFORM:
            try:
                send_message_webform(endpoint, msg, deliveryrec)
                deliveryrec.success = True
                deliveryrec.failure_reason = DeliveryRecord.FAILURE_NO_FAILURE
            except SelectOptionNotMappable, e: # is a type of WebformParseException so must go first
                deliveryrec.trace += unicode(e) + u"\n"
                deliveryrec.failure_reason = DeliveryRecord.FAILURE_SELECT_OPTION_NOT_MAPPABLE
                
                sr = SynonymRequired()
                tags = e.values
                if len(tags) == 1 and tags[0][0] == "#":
                    tags = tags[0].split(' #')
                    tags[0] = tags[0]+"/"+str(CURRENT_CONGRESS)
                sr.term1set = u"\n".join(tags)
                sr.term2set = u"\n".join(sorted(e.options))
                if not SynonymRequired.objects.filter(term1set=sr.term1set, term2set=sr.term2set).exists():
                    sr.save()
                    
                
            except WebformParseException, e:
                deliveryrec.trace += unicode(e) + u"\n"
                deliveryrec.failure_reason = DeliveryRecord.FAILURE_FORM_PARSE_FAILURE
                
        elif method == Endpoint.METHOD_HOUSE_WRITEREP:
            ok = send_message_housewyr(msg, deliveryrec)
            
            if not ok:
                if previous_attempt != None:
                    previous_attempt.next_attempt = None
                    previous_attempt.save()
                deliveryrec.delete()
                return None
        
            # If we got this far, House WYR supports this office. Since we
            # might have been guessing...
            if deliveryrec.success and endpoint.method != method:
                endpoint.method = Endpoint.METHOD_HOUSE_WRITEREP
                endpoint.save()
                
        elif method == Endpoint.METHOD_SMTP:
            deliveryrec.trace += u"sending email to " + unicode(endpoint.webform) + u"\n\n"
            deliveryrec.trace += u"from: " + msg.email + u"\n"
            deliveryrec.trace += u"subject: " + msg.subjectline + u"\n\n"
            
            if endpoint.template == None or endpoint.template.strip() == "":
                msg_body = msg.text()
            elif endpoint.template.strip() == "@IQ":
                if "no" in msg.response_requested:
                    msg.response_yn = "N"
                elif "yes" in msg.response_requested:
                    msg.response_yn = "Y"
                else:
                    raise Exception("Response_requested does not seem to be either yes or no.")
                
                msg_body = msg.xml("""<APP>CUSTOM
<PREFIX>%prefix</PREFIX>
<FIRST>%firstname</FIRST>
<LAST>%lastname</LAST>
<SUFFIX>%suffix</SUFFIX>
<ADDR1>%address1</ADDR1>
<ADDR2>%address2</ADDR2>
<CITY>%city</CITY>
<STATE>%state</STATE>
<ZIP>%zipcode</ZIP>
<PHONE>%phone</PHONE>
<EMAIL>%email</EMAIL>
<RSP>%response_yn</RSP>
<MSG>%message</MSG>
<TOPIC>%campaign_id</TOPIC>
</APP>""")
                
            deliveryrec.trace += msg_body
            
            send_mail(
                msg.subjectline,
                msg_body,
                msg.email,
                [endpoint.webform],
                fail_silently=False)

            deliveryrec.success = True
            deliveryrec.failure_reason = DeliveryRecord.FAILURE_NO_FAILURE
            
    # exceptions common to all delivery types
    except DistrictDisagreementException, e:
        deliveryrec.trace += unicode(e) + u"\n"
        deliveryrec.failure_reason = DeliveryRecord.FAILURE_DISTRICT_DISAGREEMENT

    except AddressRejectedException, e:
        deliveryrec.trace += unicode(e) + u"\n"
        deliveryrec.failure_reason = DeliveryRecord.FAILURE_ADDRESS_REJECTED
    
    except HTTPException, e:
        deliveryrec.trace += unicode(e) + u"\n"
        deliveryrec.failure_reason = DeliveryRecord.FAILURE_HTTP_ERROR
    
    except IOError, e:
        deliveryrec.trace += unicode(e) + u"\n"
        deliveryrec.failure_reason = DeliveryRecord.FAILURE_HTTP_ERROR
    
    except SubmissionSuccessUnknownException, e:
        deliveryrec.trace += unicode(e) + u"\n"
        deliveryrec.failure_reason = DeliveryRecord.FAILURE_UNEXPECTED_RESPONSE
        
    except Exception, e:
        deliveryrec.trace += unicode(e) + u"\n"
        deliveryrec.failure_reason = DeliveryRecord.FAILURE_UNHANDLED_EXCEPTION
        import traceback
        traceback.print_exc()
        
    deliveryrec.save()
    
    last_connect_time[deliveryrec.target.id] = clock()

    return deliveryrec
    
