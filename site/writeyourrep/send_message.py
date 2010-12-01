# DEBUG=1 PYTHONPATH=. DJANGO_SETTINGS_MODULE=settings python writeyourrep/send_message.py

import re
import urllib
import urlparse
import html5lib

from writeyourrep.models import *
from testzipcodes import testzipcodes

from popvox.govtrack import getMemberOfCongress

http = urllib.FancyURLopener()
http.version = "POPVOX.com Message Delivery <info@popvox.com>"

class Message:
	pass

msg = Message()
msg.email = "josh@popvox.com"
msg.prefix = "Mr."
msg.firstname = "Joshua"
msg.lastname = "Tauberer"
msg.suffix = ""
msg.address1 = "3460 14th St. NW #125"
msg.address2 = ""
msg.city = "Washington"
msg.county = "Adams"
msg.state = "DC"
msg.zipcode = "20010"
msg.phone = "516-458-9919"
msg.subjectline = "Test Message from popvox.com"
msg.message = "This is a test message from popvox.com, a constituent communication start-up launching in 2011  Our focus is to make sure the information is most useful to YOU. We apologize for the inconvenience while we test getting messages in to you. If you have any questions or concerns, please contact Joshua Tauberer, CTO of POPVOX, at 516-458-9919. Thanks."
msg.topicarea = ["Other", "Animal Welfare", "Veterans", "Veterans Affairs", "Veterans Legislation", "Gun Control"]
msg.response_requested = ("no",)

# Here are some common aliases for the field names we use.
# Don't include spaces, all lowercase.
common_fieldnames = {
	# cannonical names
	"email": "email",
	"prefix": "prefix",
	"firstname": "firstname",
	"lastname": "lastname",
	"suffix": "suffix",
	"address1": "address1",
	"address2": "address2",
	"city": "city",
	"state": "state",
	"zipcode": "zipcode",
	"county": "county",
	"message": "message",
	"response_requested": "response_requested",
	"responserequested": "response_requested",

	# other aliases
	"salutation": "prefix",
	"first": "firstname",
	"fname": "firstname",
	"namefirst": "firstname",
	"last": "lastname",
	"lname": "lastname",
	"namelast": "lastname",
	"address": "address1",
	"address01": "address1",
	"address02": "address2",
	"streetaddress1": "address1",
	"streetaddress2": "address2",
	"mailing_streetaddress1": "address1",
	"mailing_streetaddress2": "address2",
	"street2": "address2",
	"statecode": "state",
	"messagebody": "message",
	"yourmessage": "message",
	"pleasetypeyourmessage": "message",
	"pleasewriteyourmessage": "message",
	"comments": "message",
	"messagesubject": "subjectline",
	"zip": "zipcode",
	"zip5": "zipcode",
	"zip_verify": "zipcode",
	"phone": "phone",
	"phone_number": "phone",
	"phonenumber": "phone",
	"homephone": "phone",
	"emailaddress": "email",
	"email_verify": "email",
	"verify_email": "email",
	
	"subject_text": "subjectline",
	"subject_select": "topicarea",
	"topic_text": "subjectline",
	"topic_select": "topicarea",
	"issue_select": "topicarea",
	"issues_select": "topicarea",
	"feedbackissueselector_select": "topicarea",
	"pleasetypethesubjectofyourmessage": "subjectline",
	"subjectofletter_text": "subjectline",
	"subjectofletter_select": "topicarea",
	
	"response_requested_select": "response_requested",
	}

# Here are field names that we assume are optional everywhere.
# All lowercase here.
skippable_fields = ("prefixother", "unit", "daytimephone", "workphone", "newsletter", "subjectother", "plusfour", "nickname", "firstname_spouse", "lastname_spouse", "cellphone")

select_override_validate = ("county",)
radio_choices = {
	"reason": "legsitemail",
	"newslettersignup": "0",
}

def parse_webform(webformurl, webform, webformid):
	# cut out all table tags because when tables are mixed together with forms
	# html5lib can reorder the tags so that the fields fall out of the form.
	webform = re.sub("</?(table|tr|td|tbody)( [^>]*)?>", "", webform.read())	
	
	doc = html5lib.HTMLParser(tree=html5lib.treebuilders.getTreeBuilder("dom")).parse(webform)
	
	formaction = None
	fields = []
	fieldlabels = { }
	
	# scan <form>s
	for form in doc.getElementsByTagName("form"):
		if form.getAttribute("id") == webformid or \
			form.getAttribute("name") == webformid or \
			webformid in ["." + x for x in form.getAttribute("class").split()] or \
			"@" + form.getAttribute("action") == webformid:
			if form.getAttribute("action") != "":
				formaction = urlparse.urljoin(webformurl, form.getAttribute("action"))
			else:
				formaction = webformurl
				
			for field in form.getElementsByTagName("input") + form.getElementsByTagName("select") + form.getElementsByTagName("textarea"):
				if field.getAttribute("name").strip() != "":
					
					## Look at any preceding text.
					#if not field.hasAttribute("id") and field.previousSibling != None and field.previousSibling.data != None:
					#	field.parentNode.normalize()
					#	field.setAttribute('id', field.getAttribute("name"))
					#	fieldlabels[field.getAttribute("name")] = re.sub("[^a-zA-Z0-9]", "", re.sub(".*\n", "", field.previousSibling.data)).lower()
					
					options = None
					if field.nodeName == "select":
						options = { }
						for opt in field.getElementsByTagName("option"):
							opttext = ""
							opt.normalize()
							if opt.firstChild != None:
								opttext = opt.firstChild.data.lower()
								opttext = re.sub("^\s+", "", opttext)
								opttext = re.sub("\s+$", "", opttext)
							
							options[opttext] = opt.getAttribute("value") if opt.hasAttribute("value") else opttext
							
					elif field.getAttribute("type") == "checkbox":
						# just ignore checkboxes --- they should be to subscribe
						# users to the office's email list. We want to ignore them
						# outright because we want to specifically NOT submit
						# their value.
						continue
						
					elif field.getAttribute("type") == "radio":
						print field.toxml()
						for fieldtype, attr, attrid, default_value, options in fields:
							if fieldtype == "radio" and attr == field.getAttribute("name"):
								options[field.getAttribute("value").lower()] = field.getAttribute("value")
								break
						else:
							fields.append( ("radio", field.getAttribute("name"), field.getAttribute("id"), field.getAttribute("value") if field.hasAttribute("value") else None, { field.getAttribute("value").lower(): field.getAttribute("value") }))
						continue
							
					fieldtype = field.nodeName
					if fieldtype == "input":
						if field.getAttribute("type") == "":
							fieldtype = "text"
						else:
							fieldtype = 	field.getAttribute("type")
					
					fields.append( (fieldtype, field.getAttribute("name"), field.getAttribute("id"), field.getAttribute("value") if field.hasAttribute("value") else None, options))

	# scan <label>s
	for label in doc.getElementsByTagName("label"):
		label.normalize()
		try:
			fieldlabels[label.getAttribute("for")] = re.sub("[^a-zA-Z0-9]", "", label.firstChild.data).lower()
		except:
			# missing child or text in element
			pass
		
	if len(fields) == 0:
		raise Exception("Form %s is missing at %s." % (webformid, webformurl))

	# Map the form fields to our data structure and construct the POST data.

	# Create a mapping from form field names to source attributes
	# in our message objects.
	field_map = { }
	field_options = { }
	field_default = { }
	
	for fieldtype, attr, attrid, default_value, options in fields:
		field_options[attr] = options
		
		ax = attr.lower()
		ax2 = attr.lower() + "_" + fieldtype.lower()
		
		if ax in common_fieldnames:
			# we know what this field means
			field_map[attr] = common_fieldnames[ax]
		
		elif ax2 in common_fieldnames:
			# we know what this field means
			field_map[attr] = common_fieldnames[ax2]
			
		elif ax.startswith("required-") and ax[len("required-"):] in common_fieldnames:
			# we know what this field means
			field_map[attr] = common_fieldnames[ax[len("required-"):]]

		elif attrid in fieldlabels and fieldlabels[attrid].lower() in common_fieldnames:
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
		
		elif ax in skippable_fields or (attrid in fieldlabels and fieldlabels[attrid].lower() in skippable_fields):
			# we don't recognize the field but we consider it optional, and
			# we'll post it back with the empty string
			field_default[attr] = ""
			
		elif fieldtype == "submit":
			# even if submit buttons have a name, if they don't have a value
			# (which we would have handled earlier as a default value) we
			# don't need to submit anything.
			continue
			
		elif fieldtype == "radio" and ax in radio_choices:
			field_default[attr] = radio_choices[ax]

		else:
			raise Exception("Unhandled field: " + repr((fieldtype, ax, fieldlabels[attrid] if attrid in fieldlabels else attrid, options)))

	return field_map, field_options, field_default, formaction

def send_messages_webform(di, msgs):
	# Load the web form and parse the fields.
	
	if not "#" in di.webform:
		raise Exception("webform URL should specify a # and the id, name, .class, or @action of the form")
	
	webformurl, webformid = di.webform.split("#")
	webform = http.open(webformurl)
	
	# Some webforms are in two stages: first enter your zipcode to verify,
	# and then enter the rest of the info. To signal this, we'll give a pair
	# of form IDs.
	if "," in webformid:
		# This is a two-stage webform.
		webformid_stage1, webformid = webformid.split(",")
		
		# Parse the fields.
		field_map, field_options, field_default, webformurl = parse_webform(webformurl, webform, webformid_stage1)
		
		# Submit the zipcode to get the second stage form.
		postdata = { }
		for k, v in field_map.items():
			if v == "zipcode":
				postdata[k] = testzipcodes[getMemberOfCongress(di.govtrackid)["state"] + getMemberOfCongress(di.govtrackid)["district"]]
			else:
				raise Exception("First-stage contact form requires " + repr((k,v)))
		for k, v in field_default.items():
			postdata[k] = v
		
		webform = http.open(webformurl, urllib.urlencode(postdata))

	field_map, field_options, field_default, formaction = parse_webform(webformurl, webform, webformid)
			
	# Make sure that we've found the equivalent of all of the fields
	# that the form should be accepting.
	for field in ("email", "firstname", "lastname", "address1", "city", "zipcode", "message"):
		if not field in field_map.values():
			raise Exception("Form does not seem to accept field " + field)

	# Deliver messages.
	for msg in msgs:
		# set form field values
		postdata = { }
		for k, v in field_map.items():
			postdata[k] = getattr(msg, v)
			
			if field_options[k] == None or k in select_override_validate:
				if type(postdata[k]) == tuple or type(postdata[k]) == list:
					# take first preferred value
					postdata[k] = postdata[k][0]
			else:
				# Must map postdata[k] onto one of the available options.
				if type(postdata[k]) == str:
					postdata[k] = [postdata[k]]
				for q in postdata[k]:
					if q.lower() in field_options[k]:
						postdata[k] = field_options[k][q.lower()]
						break
					elif q in field_options[k].values():
						break
				else:
					raise Exception("Cant map value %s into available option from %s." % (postdata[k], field_options[k]))
			
		for k, v in field_default.items():
			postdata[k] = v
				
		# submit the data via POST and check the result.
		ret = http.open(formaction, urllib.urlencode(postdata)).read()
		success = (di.webformresponse in ret)
		
		if di.webformresponse == None or di.webformresponse.strip() == "":
			print ret
			
		if not success:
			print ret
			raise Exception("Success message not found in result.")

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


# Test all webforms.
from testzipcodes import testzipcodes
for moc in Endpoint.objects.filter(method=Endpoint.METHOD_WEBFORM):
	if moc.tested:
		continue

	print getMemberOfCongress(moc.govtrackid)["name"]
	print moc.admin_url()
	send_messages_webform(moc, [msg])
	print "Pass!"
	break

