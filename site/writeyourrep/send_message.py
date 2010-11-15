import sys
sys.path.insert(0, ".")

import os
os.environ["DJANGO_SETTINGS_MODULE"] = "settings"

import re
import urllib
import urlparse

from writeyourrep.models import *

di = MemberOfCongressDeliveryInfo()
di.method = MemberOfCongressDeliveryInfo.METHOD_WEBFORM
di.webform = "http://akaka.senate.gov/email-senator-akaka.cfm#frmContact"
di.webformresponse = "Thank you for submitting your request."

di.webform = "http://alexander.senate.gov/public/index.cfm?p=Email#.uniForm"
di.webformresponse = "Thank you for contacting Senator Lamar Alexander's office"

class Message:
	pass

msg = Message()
msg.email = "josh@popvox.com"
msg.prefix = "Mr."
msg.firstname = "Joshua"
msg.lastname = "Tauberer"
msg.address1 = "3460 14th St. NW #125"
msg.address2 = ""
msg.city = "Washington"
msg.state = "DC"
msg.zipcode = "20010"
msg.message = "test message from popvox.com"
msg.subject = "Congress"

def send_messages_webform(di, msgs):
	# Load the web form and parse the fields.
	
	webformurl, webformid = di.webform.split("#")
	webform = urllib.urlopen(webformurl).read()
	
	from HTMLParser import HTMLParser
	class MyHTMLParser(HTMLParser):
		formaction = None
		fields = []
		inform = False
		localfieldnames = { }
		labelfield = None
		labeldata = ""
		
		def handle_starttag(self, tag, attrs_list):
			attrs = { }
			for k,v in attrs_list:
				attrs[k] = v
			
			if tag == "label" and "for" in attrs:
				self.labelfield = attrs["for"]
				self.labeldata = ""
				
			elif tag == "form" and (("id" in attrs and attrs["id"] == webformid)
				or ("class" in attrs and "." + attrs["class"] == webformid)):
				if "action" in attrs:
					self.formaction = urlparse.urljoin(webformurl, attrs["action"])
				else:
					self.formaction = webformurl
					
				self.inform = True
				
			elif self.inform and tag in ('input', 'select', 'textarea') and "name" in attrs:
				self.fields.append((attrs["name"], attrs["value"] if "value" in attrs else None))
		
		def handle_endtag(self, tag):
			if tag == "form":
				self.inform = False
			if tag == "label":
				self.localfieldnames[self.labelfield] = self.labeldata
				self.labelfield = None
				
		def handle_data(self, data):
			if self.labelfield != None:
				data = re.sub("[^a-zA-Z0-9]", "", data)
				self.labeldata += data.lower()
				
	parser = MyHTMLParser()
	parser.feed(webform)
	parser.close()
	
	if len(parser.fields) == 0:
		raise Exception("Form is missing.") 
	
	for msg in msgs:
		
		# Map the form fields to our data structure and construct the POST data.
		
		common_fieldnames = { "messagebody": "message", "zip": "zipcode", "emailaddress": "email", "topic": "subject" }
		skippable_fields = ("prefixother", "unit", "homephone", "workphone", "phonenumber", "newsletter", "subjectother")
		
		postdata = { }
		for field in parser.fields:
			attr = field[0]
			if hasattr(msg, field[0].lower()):
				pass
			elif field[0].lower() in common_fieldnames:
				attr = common_fieldnames[field[0].lower()]
			elif field[0] in parser.localfieldnames:
				attr = parser.localfieldnames[field[0]]
				if attr in common_fieldnames:
					attr = common_fieldnames[attr]
			
			if hasattr(msg, attr):
				postdata[field[0]] = getattr(msg, attr)
			elif field[1] != None and field[1] != '':
				postdata[field[0]] = field[1]
			elif attr.lower() in skippable_fields:
				postdata[field[0]] = ""
			else:
				raise Exception("Unhandled field: " + repr(field) + " / " + attr)
				
		# Submit the data via POST and check the result.
		ret = urllib.urlopen(parser.formaction, urllib.urlencode(postdata)).read()
		success = (di.webformresponse in ret)
		if not success:
			print ret
			raise Exception("Success message not found in result.")
	
send_messages_webform(di, [msg])

