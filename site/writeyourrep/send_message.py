import re
import urllib
import urllib2
import cookielib
import urlparse
import html5lib
import xml.sax.saxutils

from django.core.mail import send_mail

from writeyourrep.models import *

from popvox.govtrack import getMemberOfCongress, statenames

cookiejar = cookielib.CookieJar()
http = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookiejar))
http.addheaders = [('User-agent', "POPVOX.com Message Delivery <info@popvox.com>")]
def urlopen(url, data, method, deliveryrec):
	if method.upper() == "POST":
		deliveryrec.trace += "POST " + url + "\n"
		deliveryrec.trace += urllib.urlencode(data) + "\n"
		ret = http.open(url, urllib.urlencode(data))
	else:
		if len(data) > 0:
			url = url + ("?" if not "?" in url else "&") + urllib.urlencode(data)
		deliveryrec.trace += "GET " + url + "\n"
		ret = http.open(url)
	deliveryrec.trace += str(ret.getcode()) + " " + ret.geturl() + "\n"
	deliveryrec.trace += "".join(ret.info().headers) + "\n"
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
		
	def xml(self):
			import re
			return re.sub(
				r"%(\w+)",
				lambda m : xml.sax.saxutils.escape(unicode(getattr(self, m.group(1)))),
u"""<APP>CUSTOM
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
</APP>""")

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
	#"county": "county",
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
	"last": "lastname",
	"lname": "lastname",
	"namelast": "lastname",
	"last_name": "lastname",
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
	"mailing_city": "city",
	"hcity": "city",
	"citytown": "city",
	"statecode": "state",
	"hstate": "state",
	"mailing_state": "state",
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

	"messagesubject": "subjectline",
	"email_subject": "subjectline",
	"message_topic_select": "topicarea",
	"subject_text": "subjectline",
	"subject_select": "topicarea",
	"topic_text": "subjectline",
	"topic_select": "topicarea",
	"issue_text": "subjectline",
	"issue_select": "topicarea",
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
	
	"responserequested": "response_requested",
	"responserequest": "response_requested",
	"response": "response_requested",
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
	
	'view_select': 'support_oppose',
	}

# Here are field names that we assume are optional everywhere.
# All lowercase here.
skippable_fields = ("prefixother", "middle", "middlename", "name_middle", "title", "addr3", "unit", "areacode", "exchange", "final4", "daytimephone", "workphone", "phonework", "work_phone_number", "worktel", "phonebusiness", "business-phone", "phone_b", "phone_c", "ephone", "mphone", "cell", "newsletter", "subjectother", "plusfour", "nickname", "firstname_spouse", "lastname_spouse", "mi", "cellphone", "rank", "branch", "militaryrank", "middleinitial", "other", "organization", "enews_subscribe", "district-contact", "appelation",
	"survey_answer_1", "survey_answer_2", "survey_answer_3", "survey", "affl_del",
	"speech", "authfailmsg",
	"flag_name", "flag_send", "flag_address", "tour_arrive", "tour_leave", "tour_requested", "tour_dates", "tour_adults", "tour_children", "tour_needs", "tour_comment",
	"org")

select_override_validate = ("county",)
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
}

custom_mapping = {
	"757_name_text": "firstname",
	"789_phone8_text": "phone",
	"33_field_ccfdbe3a-7b46-4b3f-b920-20416836d599_textarea": "message",
}

custom_overrides = {
	"18_prefix2_select": "Yes",
	"29_subject_radio": "CRNR", # no response requested
	"38_subsubject_select": "Other",
	"44_modified_hidden": "1",
	"44_nl_radio": "no",
	"44_nl_format_radio": "text",
	"68_modified_hidden": "1",
	'73_re_select': 'issue',
	'74_field_c1492f1b-346e-4169-a569-80bc5f368d2e_radio': 'NO', #response req.
	'99_district-contact_text': 'InD',
	'107_response_radio': '1NR',
	'118_enews_subscribe_radio': '',
	'122_thall_radio': '',
	'156_fp_fld2parts-fullname_text': '', # parse bug
	'157_newsletter_radio': 'noAction',
	'174_textmodified_hidden': 'yes',
	'179_affl_radio': 'on',
	'198_field_5eb7428f-9e29-4ecb-a666-6bc56b6a435e_radio': 'NO', #response req
	'204_action_radio': '', # subscribe
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
	"690_aff2_radio": "",
	"732_field_1807499f-bb47-4a2b-81af-4d6c2497c5e5_radio": " ",
	"748_messagetype_radio": "express an opinion or share your views with me",
	"757_add2_text": "",
	"757_affl_select": "no-action",
	"761_contact_nature_select": "comment or question",
	"776_formfield1234567894_text": "",
	"791_typeofresponse_select": "email",
	"805_issue_radio": "",
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
			webformid == "@@":
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
		if field.getAttribute("type").lower() == "image":
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
					opttext = opt.firstChild.data.lower()
					opttext = re.sub("^\W+", "", opttext)
					opttext = re.sub("\s+$", "", opttext)
					if opttext == "" or "select" in opttext or "=" in opttext or opttext[0] == "-":
						continue
				
				options[opttext] = opt.getAttribute("value") if opt.hasAttribute("value") else opttext
				
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
		#if ax == "ctl00$ctl01$zip": ax = "zip5"
		#if ax == "ctl00$ctl04$zip": ax = "zip5"
		#if ax == "ctl00$ctl05$zip": ax = "zip5" # 171
		#if ax == "ctl00$ctl06$zip": ax = "zip5"
		#if ax == "ctl00$ctl08$zip": ax = "zip5" # 191
		#if ax == "ctl00$ctl09$zip": ax = "zip5" # 191
		#if ax == "ctl00$ctl10$zip": ax = "zip5" # 173
		#if ax == "ctl00$ctl105$zip": ax = "zip5"
		
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

	return field_map, field_options, field_default, formaction, formmethod

def send_message_webform(di, msg, deliveryrec):
	# Load the web form and parse the fields.
	
	if not "#" in di.webform:
		raise WebformParseException("Webform URL should specify a # and the id, name, .class, or @action of the form")
		
	webformurl, webformid = di.webform.split("#")
	
	webform = urlopen(webformurl, {}, "GET", deliveryrec).read()
	
	webform_stages = webformid.split(',')
	
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
		
		if "The zip code you typed in does not appear to be a zip code within my district" in webform\
			or "You might not be in my district" in webform \
			or "A valid Zip code for the 5th District of Missouri was not entered" in webform\
			or "The zip code entered indicates that you reside outside the" in webform\
			or "I'm sorry, but Congressional courtesy dictates that I only reply to residents of" in webform:
			deliveryrec.trace += "\n" + webform + "\n\n"
			raise DistrictDisagreementException()
			

	webformid = webform_stages.pop(0) if len(webform_stages) > 0 else "<not entered>"
	try:
		field_map, field_options, field_default, formaction, formmethod = parse_webform(webformurl, webform, webformid, di.id)
	except:
		deliveryrec.trace += "\n" + webform.decode('utf8', 'replace') + "\n\n"
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
		
		if v == "suffix" and field_options[k] != None: field_options[k][""] = ""
		
		if field_options[k] == None or k in select_override_validate:
			if type(postdata[k]) == tuple or type(postdata[k]) == list:
				# take first preferred value
				postdata[k] = postdata[k][0]
		else:
			# Must map postdata[k] onto one of the available options.
			if isinstance(postdata[k], str) or isinstance(postdata[k], unicode):
				postdata[k] = [postdata[k]]
			alts = []
			# For each value we have coming in from the message, also
			# try any of its mapped synonyms in the database.
			for q in postdata[k]:
				alts.append(q)
				for rec in Synonym.objects.filter(term1 = q):
					alts.append(rec.term2)
			alts.sort(key = lambda x : x in ("other", "others", "miscellaneous", "other - not listed", "optionally select an issue", "general concerns")) # put these at the end
			for q in alts:
				if q.lower() in field_options[k]:
					postdata[k] = field_options[k][q.lower()]
					break
				if q in field_options[k].values():
					postdata[k] = q
					break
			else:
				raise SelectOptionNotMappable("Can't map value %s for %s into available option from %s." % (postdata[k], k, field_options[k]), k, postdata[k], field_options[k].keys())
		
		postdata[k] = postdata[k].encode("utf8")
		
	for k, v in field_default.items():
		postdata[k] = v.encode("utf8")
		
	# This guy has some weird restrictions on the text input to prevent the user from submitting
	# SQL... rather than just escaping the input. 412305 Peters, Gary C. (House)
	if di.id == 736:
		for k in postdata:
			for badword in ("select","insert","update","delete","drop","--","alter","xp_","execute","declare","information_schema","table_cursor"):
				postdata[k] = postdata[k].replace(badword, badword[0] + "." + badword[1:] + ".") # the final period is for when "--" repeats

	# Debugging...
	if False:
		print formaction
		for k, v in postdata.items():
			print k, v
		return
			
	# submit the data via POST and check the result.

	ret = urlopen(formaction, postdata, formmethod, deliveryrec)
	ret, ret_code, ret_url = ret.read(), ret.getcode(), ret.geturl()
	
	# If this form has a final stage where the user is supposed to verify
	# what he entered, then re-submit the verification form presented to
	# him with no change.
	if len(webform_stages) > 0 and webform_stages[0].startswith("verifystage:"):
		webformid_stage2 = webform_stages.pop(0)[len("verifystage:"):]
		try:
			doc, form, formaction, formmethod = find_webform(ret, webformid_stage2, formaction)
		except WebformParseException:
			deliveryrec.trace += "\n" + webform.decode('utf8', 'replace') + "\n\n"
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
	
	if type(ret) == str:
		ret = ret.decode('utf8', 'replace')

	if "Your zip code indicates that you are outside of" in ret \
	 or "Your zip code indicates that you live outside" in ret \
	 or "The zip code entered indicates that you reside outside the" in ret\
	 or "This authentication has failed" in ret\
	 or "You might not be in my district" in ret:
		deliveryrec.trace += "\n" + ret + "\n\n"
		raise DistrictDisagreementException()
		
	if "experiencing technical difficulties" in ret:
		deliveryrec.trace += "\n" + ret + "\n\n"
		raise IOError("The site reports it is experiencing technical difficulties.")
	
	if "&success=true" in ret_url:
		return
	
	if di.webformresponse == None or di.webformresponse.strip() == "":
		deliveryrec.trace += "\n" + ret + "\n\n"
		raise SubmissionSuccessUnknownException("Webform's webformresponse text is not set.")

	if di.webformresponse in ret:
		return
		
	deliveryrec.trace += "\n" + ret + "\n\n"
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
	for formname, responsetext in (("@/htbin/wrep_const", '/htbin/wrep_save'), ("@/htbin/wrep_save", "Your message has been sent.|I want to thank you for contacting me through electronic mail|Thank you for contacting my office|Thank you for getting in touch|Your email has been submitted|I have received your message|Your email has been submitted|Thank You for Your Correspondence|your message has been received|we look forward to your comments|I have received your message|Thanks for your e-mail message|I will be responding to your email in specific detail|Thank you for your message|Your message has been received|Thank you for taking the time to contact me|Thank you for contacting me by email")):
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
			deliveryrec.trace += "\n" + ret + "\n\n"
			raise SubmissionSuccessUnknownException("Success message not found in result.")
					
	# Success.
		
	deliveryrec.success = True
	deliveryrec.failure_reason = DeliveryRecord.FAILURE_NO_FAILURE
	
	return True

# download a cache of all of the webforms (at least the first-stage page)
def cache_webforms():
	for moc in Endpoint.objects.filter(method=Endpoint.METHOD_WEBFORM):
		print moc.id
		webformurl = moc.webform
		if "#" in webformurl:
			webformurl, webformid = moc.webform.split("#")
		(filename, headers) = http.retrieve(webformurl, filename="writeyourrep/cache/" + str(moc.id) + ".html")
		fn = open(filename, "a")
		fn.write("\n<!-- " + webformurl + "-->\n")
		fn.close()

def send_message(msg, govtrackrecipientid, previous_attempt, loginfo):
	cookiejar.clear()
	
	# Check for delivery information.
	
	mm = getMemberOfCongress(govtrackrecipientid)
	if "current" not in mm or mm["type"] not in ('sen', 'rep'):
		raise Exception("Recipient is not currently in office as a senator or representative.")

	# Get an endpoint record for this member of congress. If none is
	# in the database, create a record but set the method to none. If
	# this is for a representative, we'll still try the House Write Your Rep
	# form.
	try:
		moc = Endpoint.objects.get(govtrackid = govtrackrecipientid)
		method = moc.method
	except Endpoint.DoesNotExist:
		# If we don't have an endpoint record and this is for a representative,
		# then try using the House's Write Your Rep generic form. If it
		# succeeds, we'll save this endpoint for later.
		moc = Endpoint()
		moc.govtrackid = govtrackrecipientid
		moc.method = Endpoint.METHOD_NONE
		moc.save()
		method = Endpoint.METHOD_NONE
		
	if moc.method == Endpoint.METHOD_NONE:
		if mm["type"] == "rep":
			method = Endpoint.METHOD_HOUSE_WRITEREP

	if method == Endpoint.METHOD_NONE:
		return None

	deliveryrec = DeliveryRecord()
	deliveryrec.target = moc
	deliveryrec.method = moc.method
	deliveryrec.success = False
	deliveryrec.trace = loginfo + u" to " + getMemberOfCongress(govtrackrecipientid)["sortkey"] + u" (" + unicode(govtrackrecipientid) + u")\n" + msg.xml() + u"\n\n"
	deliveryrec.failure_reason = DeliveryRecord.FAILURE_NO_FAILURE
	deliveryrec.save()

	if previous_attempt != None:
		previous_attempt.next_attempt = deliveryrec
		previous_attempt.save()

	#print mm["name"].encode('utf8'), msg.zipcode
	#print moc.admin_url()	
	
	# Generate some additional fields.
	msg.name = msg.firstname + " " + msg.lastname
	msg.address_combined = msg.address1 + "; " + msg.address2
	if len(msg.zipcode.split("-")) != 2:
		msg.zip5 = msg.zipcode
		msg.zip4 = ""
	else:
		msg.zip5, msg.zip4 = msg.zipcode.split("-")
	if msg.prefix == "Reverend":
		msg.prefix = ('Reverend', 'Mr.') # fallback

	# Begin the delivery attempt.
	try:
		
		if method == Endpoint.METHOD_WEBFORM:
			try:
				send_message_webform(moc, msg, deliveryrec)
				deliveryrec.success = True
				deliveryrec.failure_reason = DeliveryRecord.FAILURE_NO_FAILURE
			except SelectOptionNotMappable, e: # is a type of WebformParseException so must go first
				deliveryrec.trace += str(e) + "\n"
				deliveryrec.failure_reason = DeliveryRecord.FAILURE_SELECT_OPTION_NOT_MAPPABLE
				
				sr = SynonymRequired()
				sr.term1set = "\n".join(e.values)
				sr.term2set = "\n".join(sorted([re.sub(r"\s+", " ", opt) for opt in e.options]))
				if not SynonymRequired.objects.filter(term1set=sr.term1set, term2set=sr.term2set).exists():
					sr.save()
				
			except WebformParseException, e:
				deliveryrec.trace += str(e) + "\n"
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
			deliveryrec.trace += "sending email to " + moc.webform + "\n\n"
			deliveryrec.trace += msg.text()
			
			send_mail(
				msg.subjectline,
				msg.text(),
				msg.email,
				[moc.webform],
				fail_silently=False)

			deliveryrec.success = True
			deliveryrec.failure_reason = DeliveryRecord.FAILURE_NO_FAILURE
			
	# exceptions common to all delivery types
	except DistrictDisagreementException, e:
		deliveryrec.trace += str(e) + "\n"
		deliveryrec.failure_reason = DeliveryRecord.FAILURE_DISTRICT_DISAGREEMENT
	
	except IOError, e:
		deliveryrec.trace += str(e) + "\n"
		deliveryrec.failure_reason = DeliveryRecord.FAILURE_HTTP_ERROR
	
	except SubmissionSuccessUnknownException, e:
		deliveryrec.trace += str(e) + "\n"
		deliveryrec.failure_reason = DeliveryRecord.FAILURE_UNEXPECTED_RESPONSE
		
	except Exception, e:
		deliveryrec.trace += str(e) + "\n"
		deliveryrec.failure_reason = DeliveryRecord.FAILURE_UNHANDLED_EXCEPTION
		import traceback
		traceback.print_exc()
		
	deliveryrec.save()

	return deliveryrec
	
