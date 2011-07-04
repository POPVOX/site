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

from writeyourrep.models import *

from popvox.govtrack import getMemberOfCongress, statenames

last_connect_time = { }

import socket
socket.setdefaulttimeout(10) # ten seconds
cookiejar = cookielib.CookieJar()
#proxy_handler = urllib2.ProxyHandler({'http': 'http://localhost:8080/'})
http = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookiejar)) # , proxy_handler
http_last_url = ""

def urlopen(url, data, method, deliveryrec):
	global http_last_url
	http.addheaders = [
		('User-agent', "POPVOX.com Message Delivery <info@popvox.com>"),
		('Referer', http_last_url)
		]
	
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
		deliveryrec.trace += "\tcookies: " + unicode(cookiejar) + "\n"
		ret = http.open(url, data)
	else:
		if not isinstance(data, (str, unicode)):
			data = urllib.urlencode(data)
		if len(data) > 0:
			url = url + ("?" if not "?" in url else "&") + data
		deliveryrec.trace += unicode("GET " + url + "\n")
		deliveryrec.trace += "\tcookies: " + unicode(cookiejar) + "\n"
		ret = http.open(url)
	
	deliveryrec.trace += unicode(ret.getcode()) + unicode(" " + ret.geturl() + "\n")
	deliveryrec.trace += unicode("".join(ret.info().headers) + "\n")
	
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
	"organization": "org_name",
	"advocacyorganizationname": "org_name",
	"organizationcontact": "org_contact",
	"organizationdescription": "org_description",
	"delivery_agent": "delivery_agent",
	"deliveryagent": "delivery_agent",
	"delivery_agent_contact": "delivery_agent_contact",
	"deliveryagentcontact": "delivery_agent_contact",

	# other aliases
	"salutation": "prefix",
	"prefixlist": "prefix",
	"title": "prefix",
	"first": "firstname",
	"fname": "firstname",
	"namefirst": "firstname",
	"first_name": "firstname",
	"name_first": "firstname",
	"first-name": "firstname",
	"last": "lastname",
	"lname": "lastname",
	"namelast": "lastname",
	"last_name": "lastname",
	"last-name": "lastname",
	"name_last": "lastname",
	"fullname": "name",
	"name_suffix": "suffix",
	"suffix2": "suffix",
	"address": "address1",
	"street_address": "address1",
	"street_address_2": "address2",
	"address01": "address1",
	"address02": "address2",
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
	"addressline2": "address2",
	"address-line1": "address1",
	"address-line2": "address2",
	"addressstreet1": "address1",
	"addressstreet2": "address2",
	"mailing_city": "city",
	"hcity": "city",
	"citytown": "city",
	"addresscity": "city",
	"statecode": "state",
	"hstate": "state",
	"mailing_state": "state",
	"addressstate": "state",
	"zip": "zipcode",
	"hzip": "zipcode",
	"zip5": "zip5",
	"zip_verify": "zipcode",
	"zip4": "zip4",
	"zipfour": "zip4",
	"zip2": "zip4",
	"plusfour": "zip4",
	"zip_plus4": "zip4",
	"postalcode": "zipcode",
	"mailing_zipcode": "zipcode",
	"addresszip": "zipcode",
	"phone": "phone",
	"phone_number": "phone",
	"phonenumber": "phone",
	"home_phone_number": "phone",
	"homephone": "phone",
	"phonehome": "phone",
	"phone_home": "phone",
	"phone_h": "phone",
	"primaryphone": "phone",
	"phone1": "phone",
	"hphone": "phone",
	"phone-number": "phone",
	"home-phone": "phone",
	"emailaddress": "email",
	"email_address": "email",
	"email_verify": "email",
	"verify_email": "email",
	"vemail": "email",
	"valid-email": "email",
	"email2": "email",
	"fromemail": "email",
	
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
	
	"textmodified": "message_personal",
	"modified": "message_personal",

	"messagesubject": "subjectline",
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
	
	'view_select': 'support_oppose',
	
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
	
	}

# Here are field names that we assume are optional everywhere.
# All lowercase here.
skippable_fields = ("prefixother", "middle", "middlename", "name_middle", "title", "addr3", "unit", "areacode", "exchange", "final4", "daytimephone", "workphone", "phonework", "work_phone_number", "worktel", "phonebusiness", "business-phone", "phone_b", "phone_c", "ephone", "mphone", "cell", "newsletter", "subjectother", "plusfour", "nickname", "firstname_spouse", "lastname_spouse", "mi", "cellphone", "rank", "branch", "militaryrank", "middleinitial", "other", "organization", "enews_subscribe", "district-contact", "appelation", "company",
	"contact-type",
	"dummy_zip",
	"survey_answer_1", "survey_answer_2", "survey_answer_3", "survey", "affl_del",
	"speech", "authfailmsg",
	"flag_name", "flag_send", "flag_address", "tour_arrive", "tour_leave", "tour_requested", "tour_dates", "tour_adults", "tour_children", "tour_needs", "tour_comment",
	"org",
	"h03", "H03")

radio_choices = {
	"reason": "legsitemail",
	"newslettersignup": "0",
	"newsletter_action": "unsubscribe",
	"subscribe": "n",
	"affl1": "",
	"affl": "",
	"aff11": "",
	"aff12": "",
	"aff1": "",
	"affl12": "",
	"updates": "no",
	"enewsletteroption": "eoptout",
	"rsptype": "email",
	"forums": "forums_no",
}

custom_mapping = {
	"24_i02": "message",
	"33_field_ccfdbe3a-7b46-4b3f-b920-20416836d599_textarea": "message",
	"37_affl3": "enews_subscribe",
	"613_zipcode_text": "zip5",
	"624_phone_prefix_text" : "phone_areacode",
	"624_phone_first_text" : "phone_prefix",
	"624_phone_second_text" : "phone_line",
	"659_contact[postal_code]_text": "zip5",
	"666_daytime-phone_text": "phone",
	"757_name_text": "firstname",
	"789_phone8_text": "phone",
	"817_areacode_text" : "phone_areacode",
	"817_phone3_text" : "phone_prefix",
	"817_phone4_text" : "phone_line",
	"832_phone1_text" : "phone_areacode",
	"832_phone2_text" : "phone_prefix",
	"832_phone3_text" : "phone_line",
	"842_J01": "subjectline",
	"864_phone_prefix_text" : "phone_areacode",
	"864_phone_first_text" : "phone_prefix",
	"864_phone_second_text" : "phone_line",
}

custom_overrides = {
	"18_prefix2_select": "Yes",
	"29_subject_radio": "CRNR", # no response requested
	"37_state_id_select": "83c503f1-e583-488d-ac7f-9ff476cfec25", #WTF Feinstein's form, seriously.
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
	'156_fp_fld2parts-fullname_text': '', # parse bug
	'157_newsletter_radio': 'noAction',
	'174_textmodified_hidden': 'yes',
	'179_affl_radio': 'on',
	'198_field_5eb7428f-9e29-4ecb-a666-6bc56b6a435e_radio': 'NO', #response req
	'204_action_radio': '', # subscribe
	'345_enews_radio': '',
	"426_aff1_radio": "<AFFL>Subscribe</AFFL>",
	"568_subject_radio": "CRNR", # no response
	"583_affl1_select": "no action",
	"585_aff1_radio": "<affl>subscribe</affl>",
	"590_response_select": "newsNo",
	"611_aff1req_text": "fill",
	"639_aff1req_text": "fill",
	"645_yes_radio": "NRN",
	"645_authfailmsg_hidden": "/andrews/AuthFailMsg.htm",
	"661_subject_hidden": "",
	"661_reqresponse_radio": "on",
	"661_issues_select": "",
	"661_issues2_select": "",
	"689_field_07c7727a-6c47-4ff9-a890-c904fa4d408f_radio": "express an opinion or share your views with me",
	"690_aff2_radio": "",
	"694_newsletter_radio": "No",
	"732_field_1807499f-bb47-4a2b-81af-4d6c2497c5e5_radio": " ",
	"748_messagetype_radio": "express an opinion or share your views with me",
	"757_add2_text": "",
	"757_affl_select": "no-action",
	"761_contact_nature_select": "comment or question",
	"761_enews_radio": "no",
	"776_formfield1234567894_text": "",
	"791_typeofresponse_select": "email",
	"805_issue_radio": "",
	"830_contactform:cd:rblformat_radio": "html",
	"869_aff1req_text": "",
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

def find_webform(htmlstring, webformid, webformurl):
	# cut out all table tags because when tables are mixed together with forms
	# html5lib can reorder the tags so that the fields fall out of the form.
	htmlstring = re.sub("</?(table|tr|td|tbody|TABLE|TR|TD|TBODY)( [^>]*)?>", "", htmlstring)
	
	# change all tag names to lower case
	htmlstring = re.sub(r"<(/?)([A-Z]+)", lambda m : "<" + (m.group(1) if m.group(1) != None else "") + m.group(2).lower(), htmlstring)
	
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

def parse_webform(webformurl, webform, webformid, id):
	#print webform
	doc, form, formaction, formmethod = find_webform(webform, webformid, webformurl)
	
	fields = []
	fieldlabels = { }
				
	for field in form.getElementsByTagName("input") + form.getElementsByTagName("select") + form.getElementsByTagName("textarea"):
		if field.getAttribute("type").lower() in ("image", "button"):
			continue
		if field.getAttribute("name").strip() == "":
			continue
			
		## Look at any preceding text.
		#if not field.hasAttribute("id") and field.previousSibling != None and field.previousSibling.data != None:
		#	field.parentNode.normalize()
		#	field.setAttribute('id', field.getAttribute("name"))
		#	fieldlabels[field.getAttribute("name")] = re.sub("[^a-zA-Z0-9]", "", re.sub(".*\n", "", field.previousSibling.data)).lower()
		
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
					if opttext == "" or "select" in opttext or "=" in opttext or opttext[0] == "-":
						continue
					if "required-" in field.getAttribute("name") and opt.hasAttribute("value") and opt.getAttribute("value").strip() == "":
						continue # confusing if the field is required
				
				options[opttext.lower()] = opt.getAttribute("value") if opt.hasAttribute("value") else opttext
				
			if len(options) == 0:
				raise WebformParseException("Select %s has no options at %s." % (field.getAttribute("name"), webformurl))
				
		elif field.getAttribute("type") == "checkbox":
			# just ignore checkboxes --- they should be to subscribe
			# users to the office's email list. We want to ignore them
			# outright because we want to specifically NOT submit
			# their value.
			continue
			
		elif field.getAttribute("type") == "radio":
			val = field.getAttribute("value")
			#if not field.hasAttribute("value"):
			#	val = "on" # specification says value is required, but Chrome submits "on" if it is missing so we'll do the same
			
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

		if ax.startswith("ctl00$") and ax.endswith("$zip"): ax = "zip5"
		if id == 636 and ax == "zipcode": ax = "zip5"
		
		ax = ax.replace("ctl00$contentplaceholderdefault$newslettersignup_1$", "")
		
		ax = re.sub(r"^(req(uired)?[\-\_]|ctl\d+\$ctl\d+\$)", "", ax)
		ax = re.sub(r"[\-\_]required$", "", ax)

		ax2 = ax + "_" + fieldtype.lower()
		
		if attr.lower() == "required-daytimephone": ax = "phone"
		
		if str(id) + "_" + ax + "_" + fieldtype.lower() in custom_overrides:
			field_default[attr] = custom_overrides[str(id) + "_" + ax + "_" + fieldtype.lower()]
			continue

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
		or "I'm sorry, but Congressional courtesy dictates that I only reply to residents of" in webform:
		deliveryrec.trace += u"\n" + webform.decode("utf8", "replace") + u"\n\n"
		raise DistrictDisagreementException()
	
def send_message_webform(di, msg, deliveryrec):
	# Load the web form and parse the fields.
	
	if not "#" in di.webform:
		raise WebformParseException("Webform URL should specify a # and the id, name, .class, or @action of the form")
		
	webformurl, webformid = di.webform.split("#")
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

	# Some webforms are in two stages: first enter your zipcode to verify,
	# and then enter the rest of the info. To signal this, we'll give a pair
	# of form IDs.
	if webform_stages[0].startswith("zipstage:"):
		# This is a two-stage webform.
		webformid_stage1 = webform_stages.pop(0)[len("zipstage:"):]
		
		# Parse the fields.
		field_map, field_options, field_default, webformurl, formmethod = parse_webform(webformurl, webform, webformid_stage1, di.id)
		
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
		
		test_zipcode_rejected(webform, deliveryrec)

	webformid = webform_stages.pop(0) if len(webform_stages) > 0 else "<not entered>"
	try:
		field_map, field_options, field_default, formaction, formmethod = parse_webform(webformurl, webform, webformid, di.id)
	except:
		deliveryrec.trace += u"\n" + webform.decode('utf8', 'replace') + u"\n\n"
		raise
			
	# Make sure that we've found the equivalent of all of the fields
	# that the form should be accepting.
	for field in ("email", ("firstname", "name"), ("lastname", "name"), ("address1", "address_combined"), ("address2", "address_combined"), "city", ("zipcode", "zip5"), "message"):
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
		if v == "prefix" and postdata[k] == "Reverend" and msg.firstname == "Jacob" and di.id == 677: postdata[k] = "Mr."
		if v == "prefix" and field_options[k] != None: field_options[k]["reverend"] = "Reverend"
		if v == "prefix" and field_options[k] != None: field_options[k]["pastor"] = "Pastor"
		if v == "prefix" and field_options[k] != None: field_options[k]["dr."] = "Dr."
		
		# Make sure that if there were options given for a suffix that we accept a blank suffix.
		if v == "suffix" and field_options[k] != None: field_options[k][""] = ""
		
		if field_options[k] == None:
			if type(postdata[k]) == tuple or type(postdata[k]) == list:
				# take first preferred value
				postdata[k] = postdata[k][0]
		else:
			# Must map postdata[k] onto one of the available options.
			if isinstance(postdata[k], str) or isinstance(postdata[k], unicode):
				postdata[k] = [postdata[k]]
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
			for q, l_r in alts:
				if q.lower() in field_options[k]:
					postdata[k] = field_options[k][q.lower()]
					break
				if q in field_options[k].values():
					postdata[k] = q
					break
			else:
				# There were no mappings from the keyword we have in the message to
				# one of the options on the form. Construct a list of the options so we can
				# store it in a SynonymRequired to be dealt with later.
				select_opts = list(field_options[k].keys())
				
				# Because of the one transitive step, we can expand the options to one
				# transitive step backwards from what's on the form. But only do this for
				# hashtag keywords because there's no sense in mapping CRS subject terms
				# to other CRS subject terms.
				if postdata[k][0].startswith("#"):
					for syn in Synonym.objects.filter(term2__in=select_opts).exclude(term1__startswith="#").values("term1").distinct():
						if syn["term1"] not in select_opts:
							select_opts.append(syn["term1"])
				
				# Issue a delivery error that will also trigger an INSERT into the synonym required
				# table with term1set set to the keyword alternatives in the message postdata[k]
				# and term2set set to select_opts.
				raise SelectOptionNotMappable("Can't map value %s for %s into available option from %s." % (postdata[k], k, field_options[k]), k, postdata[k], select_opts)
		
		postdata[k] = postdata[k].encode("utf8")
		
	for k, v in field_default.items():
		postdata[k] = v.encode("utf8")
		
	# This guy has some weird restrictions on the text input to prevent the user from submitting
	# SQL... rather than just escaping the input. 412305 Peters, Gary C. (House)
	if di.id in (13, 121, 124, 140, 147, 159, 161, 166, 176, 209, 221, 426, 585, 588, 598, 599, 600, 605, 607, 608, 611, 613, 641, 665, 678, 693, 706, 709, 718, 730, 734, 736, 746, 749, 774, 780, 784, 788, 791, 805, 808, 809, 811, 826, 827, 837, 851, 861, 869, 878):
		re_sql = re.compile(r"select|insert|update|delete|drop|--|alter|xp_|execute|declare|information_schema|table_cursor", re.I)
		for k in postdata:
			postdata[k] = re_sql.sub(lambda m : m.group(0)[0] + "." + m.group(0)[1:] + ".", postdata[k]) # the final period is for when "--" repeats

	# Debugging...
	if False:
		print formaction
		for k, v in postdata.items():
			print k, v
		return
			
	# submit the data via POST and check the result.

	ret = urlopen(formaction, postdata, formmethod, deliveryrec)
	ret, ret_code, ret_url = ret.read(), ret.getcode(), ret.geturl()
	
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
	
	if ret_code == 404:
		raise IOError("Form POST resulted in a 404.")
	
	test_zipcode_rejected(ret, deliveryrec)
	
	if type(ret) == str:
		ret = ret.decode('utf8', 'replace')

	if "experiencing technical difficulties" in ret:
		deliveryrec.trace += u"\n" + ret + u"\n\n"
		raise IOError("The site reports it is experiencing technical difficulties.")

	if "Phone number must be 10 digits" in ret:
		raise WebformParseException("Phone number must be 10 digits")
	
	if "&success=true" in ret_url:
		return
		
	re_red_error = re.compile('<span id=".*_(.*Error)"><font color="Red">(.*?)</font></span>')
	m = re_red_error.search(ret)
	if m:
		raise WebformParseException("Form-reported " + m.group(1) + ": " + m.group(2))

	re_class_error = re.compile(r'class="custom_form_error">\*?(.*?)<')
	m = re_class_error.search(ret)
	if m:
		raise WebformParseException("Form-reported " + m.group(1))
	
	if di.webformresponse == None or di.webformresponse.strip() == "":
		deliveryrec.trace += u"\n" + ret + u"\n\n"
		raise SubmissionSuccessUnknownException("Webform's webformresponse text is not set.")

	if di.webformresponse in ret:
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
		field_map, field_options, field_default, webformurl, formmethod = parse_webform(webformurl, ret, formname, "housewyr")
		
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

def send_message(msg, moc, previous_attempt, loginfo):
	cookiejar.clear()
	http_last_url = ""
	
	# Check for delivery information.
	
	method = moc.method
	govtrackrecipientid = moc.govtrackid
	mm = getMemberOfCongress(govtrackrecipientid)
	if "current" not in mm or mm["type"] not in ('sen', 'rep'):
		raise Exception("Recipient is not currently in office as a senator or representative.")

	if moc.method == Endpoint.METHOD_NONE:
		if mm["type"] == "rep":
			method = Endpoint.METHOD_HOUSE_WRITEREP

	if method == Endpoint.METHOD_NONE:
		return None
		
	# Create a new DeliveryRecord as a trace of what we are about to do.

	deliveryrec = DeliveryRecord()
	deliveryrec.target = moc
	deliveryrec.method = moc.method
	deliveryrec.success = False
	deliveryrec.trace = unicode(loginfo) + u" to " + getMemberOfCongress(govtrackrecipientid)["sortkey"] + u" (" + unicode(govtrackrecipientid) + u")\n" + unicode(msg.xml()) + u"\n\n"
	deliveryrec.failure_reason = DeliveryRecord.FAILURE_NO_FAILURE
	deliveryrec.save()

	if previous_attempt != None:
		previous_attempt.next_attempt = deliveryrec
		previous_attempt.save()

	#print mm["name"].encode('utf8'), msg.zipcode
	#print moc.admin_url()	
	
	# Generate some additional fields.
	msg.name = msg.firstname + " " + msg.lastname
	msg.address_combined = msg.address1 + ("" if msg.address2 == "" else "; " + msg.address2)
	if len(msg.zipcode.split("-")) != 2:
		msg.zip5 = msg.zipcode
		msg.zip4 = ""
	else:
		msg.zip5, msg.zip4 = msg.zipcode.split("-")
	msg.phone_areacode = "".join([c for c in msg.phone + "0000000000" if c.isdigit()])[0:3]
	msg.phone_prefix = "".join([c for c in msg.phone + "0000000000" if c.isdigit()])[3:6]
	msg.phone_line = "".join([c for c in msg.phone + "0000000000" if c.isdigit()])[6:10]
	if govtrackrecipientid == 400633 and len(msg.phone) > 0 and msg.phone[0] == '1': msg.phone = msg.phone[1:]

	# Begin the delivery attempt.
	try:
		
		if method == Endpoint.METHOD_WEBFORM:
			try:
				send_message_webform(moc, msg, deliveryrec)
				deliveryrec.success = True
				deliveryrec.failure_reason = DeliveryRecord.FAILURE_NO_FAILURE
			except SelectOptionNotMappable, e: # is a type of WebformParseException so must go first
				deliveryrec.trace += unicode(e) + u"\n"
				deliveryrec.failure_reason = DeliveryRecord.FAILURE_SELECT_OPTION_NOT_MAPPABLE
				
				sr = SynonymRequired()
				sr.term1set = "\n".join(e.values)
				sr.term2set = "\n".join(sorted([re.sub(r"\s+", " ", opt) for opt in e.options]))
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
			if deliveryrec.success and moc.method != method:
				moc.method = Endpoint.METHOD_HOUSE_WRITEREP
				moc.save()
				
		elif method == Endpoint.METHOD_SMTP:
			deliveryrec.trace += u"sending email to " + unicode(moc.webform) + u"\n\n"
			deliveryrec.trace += u"from: " + msg.email + u"\n"
			deliveryrec.trace += u"subject: " + msg.subjectline + u"\n\n"
			
			if moc.template == None or moc.template.strip() == "":
				msg_body = msg.text()
			elif moc.template.strip() == "@IQ":
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
				[moc.webform],
				fail_silently=False)

			deliveryrec.success = True
			deliveryrec.failure_reason = DeliveryRecord.FAILURE_NO_FAILURE
			
	# exceptions common to all delivery types
	except DistrictDisagreementException, e:
		deliveryrec.trace += unicode(e) + u"\n"
		deliveryrec.failure_reason = DeliveryRecord.FAILURE_DISTRICT_DISAGREEMENT
	
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
	
