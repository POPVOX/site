#!runscript

from django.contrib.auth.models import User

from writeyourrep.send_message import Message

comment = User.objects.get(username="POPVOXTweets").comments.all()[0]

#comment.address.firstname = "John"
#comment.address.lastname = "Doe"
#comment.address.phone = "516-458-9919"
#comment.address.address1 = "95 Nonexistent Drive"
#comment.address.save()

msg = Message()
msg.email = comment.user.email
msg.email = "josh@popvox.com" ####
msg.prefix = comment.address.nameprefix
msg.firstname = comment.address.firstname
msg.lastname = comment.address.lastname
msg.suffix = comment.address.namesuffix
msg.address1 = comment.address.address1
msg.address1 = "150 1st Ave NE # 370" ####
msg.address2 = comment.address.address2
msg.city = comment.address.city
msg.city = "Cedar Rapids" ###
msg.state = comment.address.state
msg.state = "IA" ### 
msg.zipcode = comment.address.zipcode
msg.zipcode = "52401-1115" ###
msg.phone = comment.address.phonenumber
msg.phone = "(319) 365-4504" ###
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
	msg.topicarea = topterm.name
else:
	msg.topicarea = (comment.bill.hashtag(always_include_session=True), comment.bill.title)
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

template = u"""<APP>
<Prefix>#prefix#</Prefix>
<FIRST>#firstname#</FIRST>
<LAST>#lastname#</LAST>
<ADDR1>#address1#</ADDR1>
<ADDR2>#address2#</ADDR2>
<CITY>#city#</CITY>
<STATE>#state#</STATE>
<ZIP>#zipcode#</ZIP>
<HOMEPHONE>#phone#</HOMEPHONE>
<EMAIL>#email#</EMAIL>
<RESPOND>Y</RESPOND>
<ISSUE>#simple_topic_code#</ISSUE>
<MSG>#message#</MSG>
<CAMPAIGNID>#campaign_id#</CAMPAIGNID>
<MODIFIED>Y</MODIFIED>
<URI>#form_url#</URI>
<ORGURL>#org_url#</ORGURL>
<ORGNAME>#org_name#</ORGNAME>
</APP>
"""

import re, xml.dom.minidom, xml.dom
def getmsgattr(mgs, attr):
	v = getattr(msg, attr)
	if isinstance(v, tuple) or isinstance(v, list):
		v = v[0]
	v = unicode(v)
	if attr == "message":
		v = open("popvox/wyr/unicodetestcharacters.txt", "r").read().decode("utf-8")
	return v
def applymsgattrs(node):
	has_elem = False
	for n in list(node.childNodes): # list() prevents messing up the iterator when we delete elements as we go
		if n.nodeType != xml.dom.Node.ELEMENT_NODE:
			continue
		has_elem = True
		if applymsgattrs(n) or n.firstChild == None: # don't touch elements that contain other elements
			continue
		n.normalize()
		v = re.sub(r"#([\w_]+)#",
					lambda m : getmsgattr(msg, m.group(1)),
					n.firstChild.data)
		if v.strip() == "":
			if n.nextSibling and n.nextSibling.nodeType == xml.dom.Node.TEXT_NODE:
				node.removeChild(n.nextSibling)
			node.removeChild(n)
		else:
			n.replaceChild(xml_message.createTextNode(v), n.firstChild)
	return has_elem


xml_message = xml.dom.minidom.parseString(template)
applymsgattrs(xml_message)
xml_message = xml_message.toxml("utf-8").replace('<?xml version="1.0" encoding="utf-8"?>', '')
print xml_message

from django.core.mail import EmailMessage
email = EmailMessage(
	'Test --- POPVOX Constituent Message',
	xml_message,
	'constituent.mail.automated@popvox.com',
	['Harkin_Intake@harkin.senate.gov'], # TO
	['josh@popvox.com', 'daniel@citizencontact.com'], # BCC
	headers = {'Reply-To': 'team@popvox.com'})
email.send()

