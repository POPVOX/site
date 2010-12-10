from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.views.generic.simple import direct_to_template
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django import forms
from django.contrib import messages
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_protect
from django.utils.html import strip_tags

from jquery.ajax import json_response, ajax_fieldupdate_request, sanitize_html, ajaxmultifieldupdate

import re
from xml.dom import minidom
import urllib
import cgi
from StringIO import StringIO

from popvox.models import *
from popvox.views.bills import getissueareas

from settings import SITE_ROOT_URL, EMAILVERIFICATION_FROMADDR

def orgs(request):
	return render_to_response('popvox/org_list.html', {'issueareas': getissueareas()}, context_instance=RequestContext(request))

def org(request, orgslug):
	org = get_object_or_404(Org, slug=orgslug)
	if org.is_admin(request.user):
		cams = org.orgcampaign_set.all().order_by("-default", "name")
	elif not org.visible:
		raise Http404()
	else:
		cams = org.campaigns()
		
	set_last_campaign_viewed(request, org)
	
	return render_to_response('popvox/org.html', {'org': org, 'admin': org.is_admin(request.user), "cams": cams}, context_instance=RequestContext(request))

@login_required
def org_help(request, orgslug):
	org = get_object_or_404(Org, slug=orgslug)
	if not org.is_admin(request.user):
		return HttpResponseForbidden("You do not have permission to view this page.")
	
	set_last_campaign_viewed(request, org)

	return render_to_response('popvox/org_help.html', {'org': org}, context_instance=RequestContext(request))

@login_required
def org_edit(request, orgslug):
	org = get_object_or_404(Org, slug=orgslug)
	if not org.is_admin(request.user):
		return HttpResponseForbidden("You do not have permission to view this page.")
	
	set_last_campaign_viewed(request, org)

	return render_to_response('popvox/org_edit.html', {'org': org}, context_instance=RequestContext(request))
	
# this must be available to non-logged-in-users so potential org admins can choose
# their org
@json_response
def org_search(request):
	ret = ""
	if "term" in request.REQUEST:
		limit = 15 # int(request.REQUEST["limit"])
		q = Org.objects.filter(visible = True, name__icontains=request.REQUEST["term"])[0:limit]
	elif "issue" in request.POST:
		ix = IssueArea.objects.get(slug=request.REQUEST["issue"])
		q = ix.orgs()
	
	ret = [ { "label": org.name, "slug": org.slug, "url": org.url(), "createdbyus": org.createdbyus } for org in q ]
	
	if "format" in request.POST:
		ret = { "status": "success", "orgs":  ret }
		
	return ret
	
@ajaxmultifieldupdate(["org"])
def org_update_fields(request, field, value, validate_only):
	org = get_object_or_404(Org, slug=request.POST["org"])
	if not org.is_admin(request.user) :
		return HttpResponseForbidden("You do not have permission to view this page.")
	
	if field == "slug":
		value = forms.SlugField().clean(value) # raises ValidationException
		if value == org.slug:
			return { "status": "fail", "msg": "That's already your slug." }
		if len(Org.objects.filter(slug=value)) > 0:
			return { "status": "fail", "msg": "That slug is in use by another organization." }
		if value != value.lower():
			return { "status": "fail", "msg": "Slugs must be all lowercase." }
		if not validate_only and value != org.slug:
			org.slug = value
			org.save()
		return { "status": "success", "value": value, "newslug": value }
	elif field == "name":
		value = forms.CharField(min_length=5, error_messages = {'min_length': "That's too short."}).clean(value) # raises ValidationException
		if not validate_only and value != org.name:
			org.name = value
			org.save()
		return { "status": "success", "value": value }
	elif field == "website":
		if value != "" and value[0:7] != "http://":
			value = "http://" + value
		value = forms.URLField(required=False, verify_exists = True).clean(value) # raises ValidationException
		if not validate_only and value != org.website:
			org.website = value
			org.save()
		return { "status": "success", "value": value }
	elif field == "description":
		value = forms.CharField(min_length=5, max_length=200, error_messages = {'min_length': "You must provide a concise description of your organization."}).clean(value) # raises ValidationException
		if not validate_only and value != org.description:
			org.description = value
			org.save()
		return { "status": "success", "value": value }
	elif field == "postaladdress":
		if not validate_only and value != org.postaladdress:
			org.postaladdress = value
			org.save()
		return { "status": "success", "value": value }
	elif field == "phonenumber":
		from django.contrib.localflavor.us.forms import USPhoneNumberField
		if value != "":
			value = USPhoneNumberField().clean(value)
		if not validate_only and value != org.phonenumber:
			org.phonenumber = value
			org.save()
		return { "status": "success", "value": value }
	elif field == "twittername":
		if value == "":
			if not validate_only and org.twittername != None:
				org.twittername = None
				org.save()
			return { "status": "success", "value": value }
		else:
			from urllib import urlopen, quote_plus
			from xml.dom import minidom
			try:
				t = minidom.parse(urlopen("http://api.twitter.com/1/users/show.xml?screen_name=" + quote_plus(value.encode('utf-8'))))
				value = t.getElementsByTagName('screen_name')[0].firstChild.data
				if not validate_only and value != org.twittername:
					org.twittername = value
					org.save()
				return { "status": "success", "value": value }
			except Exception, e:
				raise ValueError("That is not a Twitter name.")
	elif field == "facebookurl":
		if value == "":
			if not validate_only and org.facebookurl != None:
				org.facebookurl = None
				org.save()
			return { "status": "success", "value": value }
		
		gid = None
		
		import re
		m = re.search(r"/pages/[^/]+/(\d+)", value)
		if m != None:
			gid = m.group(1)

		m = re.match(r"^http://(www.)?facebook.com/([^/ ]+)$", value)
		if m != None:
			gid = m.group(2)
			
		if gid == None:
			gid = value
			value = "http://www.facebook.com/" + value
		
		from urllib import urlopen, quote_plus
		import json
		fb = json.load(urlopen("http://graph.facebook.com/" + gid))
		if "error" in fb:
			raise ValueError("That is not a Facebook Page address.")
		if "link" in fb: # normalize value to what Facebook says
			value = fb["link"]
		if not validate_only and value != org.facebookurl:
			org.facebookurl = value
			
			# If no logo is set, grab it from Facebook, if set there.
			if not org.logo and "picture" in fb:
				try:
					data = urlopen(fb["picture"]).read() # python docs indicate this may not read to end??
					org_update_logo_2(org, data)
				except:
					pass
			
			org.save()
		return { "status": "success", "value": value }
	else:
		raise Exception("Bad request: Invalid field: " + field)
	
@json_response
@ajax_fieldupdate_request
def org_update_field(request, field, value, validate_only):
	org = get_object_or_404(Org, slug=request.POST["org"])
	if not org.is_admin(request.user) :
		return HttpResponseForbidden("You do not have permission to view this page.")
		
	if field == "visible":
		if not org.approved:
			return { "status": "fail", "msg": "An organization must be approved before it can be published." }
		value = (value == "true")
		if not validate_only and value != org.visible:
			org.visible = value
			org.save()
			return { "status": "success", "msg": "Your organization is now visible." if org.visible else "Your organization is now hidden." }
		return { "status": "success" }
	elif field == "issue-add":
		ix = get_object_or_404(IssueArea, id=value)
		if validate_only:
			return { "status": "success" }
		org.issues.add(ix)
		org.save()
		return { "status": "success" }
	elif field == "issue-remove":
		ix = get_object_or_404(IssueArea, id=value)
		if validate_only:
			return { "status": "success" }
		org.issues.remove(ix)
		org.save()
		return { "status": "success" }
	elif field == "admin-add":
		try:
			user = get_object_or_404(User, email=value)
		except:
			return { "status": "fail", "msg": "There is no user with that email address." }
		if validate_only:
			return { "status": "success" }
		if len(user.orgroles.filter(org=org)) > 0: # can't add twice
			return { "status": "fail", "msg": "That user is already listed on staff." }
		role = UserOrgRole()
		role.user = user
		role.org = org
		role.title = "Staff"
		role.save()
		return { "status": "success", "username": user.username, "id": user.id, "fullname": user.userprofile.fullname }
		# TODO: Set the user an email with instructions on adding their title and phone number.
	elif field == "admin-remove":
		if request.user.id == int(value):
			return { "status": "fail", "msg": "You cannot remove yourself as an administrator for this organization." }
		if validate_only:
			return { "status": "success" }
		get_object_or_404(User, id=value).orgroles.filter(org=org).delete()
		return { "status": "success" }
	elif field == "contact-remove":
		c = get_object_or_404(OrgContact, id=value)
		if c.org != org:
			return { "status": "fail" }
		if not validate_only:
			c.delete()
		return { "status": "success" }
	else:
		raise Exception("Bad request: Invalid field: " + field)

@json_response
def org_update_logo(request, orgslug):
	org = get_object_or_404(Org, slug=orgslug)
	if not org.is_admin(request.user) :
		return HttpResponseForbidden("You do not have permission to view this page.")
	
	# Get the image byte data.
	datafile = None
	for f in request.FILES:
		datafile = f
		break
	else:
		datafile = StringIO(request.raw_post_data)
	
	org_update_logo_2(org, datafile)
	return { "success": True, "url": org.logo.url }
	
def org_update_logo_2(org, imagedata):
	# Load the image and resize it to the right dimensions preserving aspect ratio.
	from PIL import Image
	dims = (220, 166)
	imx = Image.open(imagedata)
	topleftcolor = imx.getpixel((0,0))
	(w, h) = imx.size
	if w > h*dims[0]/dims[1]:
		dims2 = (dims[0], int(float(dims[0])*h/w))
	elif h > w*dims[1]/dims[0]:
		dims2 = (int(float(dims[1])*w/h), dims[1])
	imx = imx.resize(dims2, Image.BICUBIC)

	# Because we don't know the color of the padding, create a new
	# image with the right background color and then paste in the
	# uploaded+resized image at the center.
	im = Image.new(imx.mode, dims, topleftcolor) # fill w/ top-left color
	im.paste(imx, (im.size[0]/2 - imx.size[0]/2, im.size[1]/2 - imx.size[1]/2))

	# Get out the binary jpeg data.
	buf = StringIO()
	im.save(buf, "JPEG")
	
	try:
		org.logo.delete()
	except:
		pass
	
	buf.size = len(buf.getvalue())
	buf.name = "unnamed"
	buf.seek(0)
		
	from django.core.files import File
	org.logo.save(str(org.id) + ".jpeg", File(buf))

@json_response
def org_add_staff_contact(request):
	org = get_object_or_404(Org, slug=request.POST["org"])
	if not org.is_admin(request.user) :
		return HttpResponseForbidden("You do not have permission to view this page.")
	
	name = request.POST["name"].strip()
	title = request.POST["title"].strip()
	email = request.POST["email"].strip()
	phone = request.POST["phone"].strip()
	
	if name == "" or title == "" or email == "" or phone == "":
		return { "status": "fail", "msg": "All fields are required." }
	
	if request.POST["id"] != "":
		contact = OrgContact.objects.get(id=int(request.POST["id"]), org=org)
	else:
		contact = OrgContact()
	contact.org = org
	contact.name = name
	contact.title = title
	contact.email = email
	contact.phonenumber = phone
	try:
		contact.save()
	except Exception, e:
		return { "status": "fail", "msg": unicode(e) }
	
	return { "status": "success", "id": contact.id }

def create_new_campaign(org):
	# Find a slug.
	slug = None
	for i in range(1, 1000):
		cams = OrgCampaign.objects.filter(org=org, slug="campaign" + str(i))
		if len(cams) == 0:
			slug = "campaign" + str(i)
			break
	if slug == None:
		raise Exception("Cant autogenerate a slug.")
	
	ncampaigns = len(OrgCampaign.objects.filter(org=org, default=False)) + 1
	
	# Make it.
	cam = OrgCampaign()
	cam.org = org
	cam.slug = slug
	cam.name = "Campaign " + str(ncampaigns)
	cam.website = None
	cam.description = ""
	cam.message = ""
	cam.visible = False
	cam.save()
	return cam

@login_required
@json_response
def org_support_oppose(request):
	if request.POST == None or not "org" in request.POST or not "bill" in request.POST or not "position" in request.POST or request.POST["position"] not in ("+", "-", "0"):
		raise Exception("Bad request: Missing/invalid field.")
	
	org = get_object_or_404(Org, slug=request.POST["org"])
	if not org.is_admin(request.user) :
		return HttpResponseForbidden("Not authorized.")

	newcam = False
	if "cam" in request.POST and request.POST["cam"] == "_default_":
		# Create the _default_ campaign if it doesn't exist.
		try:
			cam = OrgCampaign.objects.get(org__slug=request.POST["org"], slug=request.POST["cam"])
		except:
			cam = create_new_campaign(org)
			cam.default = True
			cam.slug = "_default_"
			cam.visible = True
			cam.save()
	elif "cam" in request.POST and request.POST["cam"] != "_new_":
		# Adding bill to existing campaign. Error if campaign doesn't exist.
		cam = get_object_or_404(OrgCampaign, org__slug=request.POST["org"], slug=request.POST["cam"])
	else:
		# Create a new campaign.
		cam = create_new_campaign(org)
		newcam = True
	
	# Get a bill object.
	bill = bill_from_url(request.POST["bill"])
	
	# Delete any existing positions 
	cam.positions.filter(bill = bill).delete()
	
	# Add the position to the campaign.
	p = OrgCampaignPosition()
	p.campaign = cam
	p.bill = bill
	p.position = request.POST["position"]
	if request.POST["comment"].strip() != "":
		p.comment = request.POST["comment"].strip()	
	p.save()

	if cam.slug == "_default_":
		message = p.bill.title + " has been added to " + org.name + "'s legislative agenda."
	elif not newcam:
		message = p.bill.title + " has been added to " + cam.name + "."
	else:
		message = "A new campaign has been created for " + p.bill.title + "."

	# Send an email to all of the org's administrators.
	send_mail("POPVOX: Legislative Agenda Changed: " + org.name,
"""This is an automated email to confirm the following change to the
legislative agenda of """ + org.name + """.

The following action was taken:

""" + message + """

For more information please see your organization profile:
""" + SITE_ROOT_URL + org.url() + """/_edit

Thanks for participating!

POPVOX
""",
		EMAILVERIFICATION_FROMADDR, [admin.user.email for admin in org.admins.all()], fail_silently=True)
	
	# Add a session message to be displayed on the next page.
	messages.success(request, message)

	return { "status": "success", "camurl": cam.url() }
		
@login_required
def org_newcampaign(request, orgslug):
	org = get_object_or_404(Org, slug=orgslug)
	if not org.is_admin(request.user) :
		return HttpResponseForbidden("Not authorized.")
	cam = create_new_campaign(org)
	return HttpResponseRedirect(cam.url() + "/_edit")

def orgcampaign(request, orgslug, campaignslug):
	cam = get_object_or_404(OrgCampaign, org__slug=orgslug, slug=campaignslug)
	if not cam.org.is_admin(request.user):
		if not cam.org.visible or not cam.visible:
			raise Http404()
			
	set_last_campaign_viewed(request, cam)
	
	return render_to_response('popvox/campaign.html', {'cam': cam, 'admin': cam.org.is_admin(request.user)}, context_instance=RequestContext(request))

@login_required
def orgcampaign_edit(request, orgslug, camslug):
	cam = get_object_or_404(OrgCampaign, org__slug=orgslug, slug=camslug)
	if not cam.org.is_admin(request.user):
		return HttpResponseForbidden("You do not have permission to view this page.")
	set_last_campaign_viewed(request, cam)
	return render_to_response('popvox/campaign_edit.html', {'cam': cam}, context_instance=RequestContext(request))

@ajaxmultifieldupdate(["org", "cam"])
def orgcampaign_updatefields(request, field, value, validate_only):
	cam = get_object_or_404(OrgCampaign, org__slug=request.POST["org"], slug=request.POST["cam"])
	if not cam.org.is_admin(request.user) :
		return HttpResponseForbidden("Not authorized.")
	
	if field == "name":
		value = forms.CharField(min_length=5, error_messages = {'min_length': "That's too short."}).clean(value) # raises ValidationException
		if not validate_only:
			cam.name = value
			cam.save()
		return { "status": "success", "value": value }
	elif field == "website":
		if value != "" and not value[0:7] == "http://":
			value = "http://" + value
		value = forms.URLField(required=False, verify_exists = True).clean(value) # raises ValidationException
		if not validate_only:
			cam.website = value
			cam.save()
		return { "status": "success", "value": value }
	elif field == "description":
		if not validate_only:
			cam.description = sanitize_html(value)
			cam.save()
		return { "status": "success" }
	elif field == "message":
		try:
			value = sanitize_html(value)
		except:
			return { "status": "fail", "msg": "It looks like you have entered forbidden HTML into the text." }
		if not validate_only:
			cam.message = value
			cam.save()
		return { "status": "success" }
	elif field == "slug":
		value = forms.SlugField().clean(value) # raises ValidationException
		if len(OrgCampaign.objects.filter(org=cam.org, slug=value)) > 0:
			return { "status": "fail", "msg": "That slug is in use by another one of your campaigns." }
		if value != value.lower():
			return { "status": "fail", "msg": "Slugs must be all lowercase." }
		if not validate_only:
			cam.slug = value
			cam.save()
		return { "status": "success", "value": value, "newslug": value }
	else:
		raise Exception("Bad request: Invalid field.")

@json_response
@ajax_fieldupdate_request
def orgcampaign_updatefield(request, field, value, validate_only):
	cam = get_object_or_404(OrgCampaign, org__slug=request.POST["org"], slug=request.POST["cam"])
	if not cam.org.is_admin(request.user) :
		return HttpResponseForbidden("Not authorized.")

	if field == "visible":
		if not validate_only:
			cam.visible = (value == "true")
			cam.save()
		return { "status": "success" }
	elif field == "billposition-remove":
		if not validate_only:
			OrgCampaignPosition.objects.get(campaign=cam, id = value).delete()
			if cam.default and len(cam.positions.all()) == 0:
				cam.delete()
			else:
				cam.save()
		return { "status": "success" }
	elif field.startswith("billposition-comment-"):
		id = int(field[len("billposition-comment-"):])
		p = OrgCampaignPosition.objects.get(campaign=cam, id=id)
		if not validate_only:
			p.comment = value
			p.save()
		if value == "":
			html = "<em>No comment.</em>"
		else:
			html = "\n".join(["<p>" + cgi.escape(line) + "</p>" for line in value.split("\n")])
		return { "status": "success", "html":html}
	if field == "action" and value == "delete-campaign":
		cam.delete()
		return { "status": "success" }

def set_last_campaign_viewed(request, cam):
	# If we're passed an org, take its default camaign if it
	# has one. Otherwise clear the session state.
	if type(cam) == Org:
		try:
			cam = cam.campaigns.get(default = True)
		except:
			cam = None

	# Clear session state.
	if cam == None:
		try:
			del request.session["popvox_lastviewedcampaign"]
		except:
			pass
		return
	
	# Otherwise, set it.
	request.session["popvox_lastviewedcampaign"] = cam.id

def action_defs(billpos):
	if billpos.action_headline == None or billpos.action_headline.strip() == "":
		billpos.action_headline = "Edit This Headline - Click Here"
	if billpos.action_body == None or strip_tags(billpos.action_body).strip() == "":
		billpos.action_body = "<p><strong>Take Action</strong></p><p>Edit message &mdash; click here to edit the text.</p> <p>Use this space to tell your members why they should take action.</p>"

@csrf_protect
def action(request, orgslug, billposid):
	org = get_object_or_404(Org, slug=orgslug)
	billpos = get_object_or_404(OrgCampaignPosition, id=billposid, campaign__org = org)

	set_last_campaign_viewed(request, billpos.campaign)

	action_defs(billpos)
	
	admin = org.is_admin(request.user)
	url = None
	num = None
	if admin:
		import shorturl
		surl, created = shorturl.models.Record.objects.get_or_create(target=billpos)
		url = surl.url()
	
		# If the admin is following his own link, make him not an admin for the
		# moment so he can see how it looks to others.
		if "shorturl" in request.session and request.session["shorturl"] == surl:
			admin = False
			del request.session["shorturl"]
			
		num = OrgCampaignPositionActionRecord.objects.filter(ocp=billpos).count()
	
	return render_to_response('popvox/org_action.html', {
		'position': billpos,
		'admin': admin,
		"shorturl": url,
		"num": num,
		}, context_instance=RequestContext(request))

@json_response
def orgcampaignpositionactionupdate(request):
	billpos = get_object_or_404(OrgCampaignPosition, id=request.POST["id"])
	if not billpos.campaign.org.is_admin(request.user) :
		return HttpResponseForbidden("Not authorized.")

	if "action_headline" in request.POST:
		billpos.action_headline = request.POST["action_headline"]
	if "action_body" in request.POST:
		billpos.action_body = sanitize_html(request.POST["action_body"])
	billpos.save()
	
	action_defs(billpos)
	
	return {"status": "success", "action_headline": billpos.action_headline, "action_body": billpos.action_body }

def action_download(request, orgslug, billposid):
	org = get_object_or_404(Org, slug=orgslug)
	billpos = get_object_or_404(OrgCampaignPosition, id=billposid, campaign__org = org)
	
	if not org.is_admin(request.user):
		return HttpResponseForbidden("You do not have permission to view this page.")

	import csv
	response = HttpResponse(mimetype='text/csv')
	response['Content-Disposition'] = 'attachment; filename=userdata.csv'
	
	writer = csv.writer(response)
	writer.writerow(['trackingid', 'date', 'email', 'firstname', 'lastname', 'zipcode'])
	for rec in OrgCampaignPositionActionRecord.objects.filter(ocp=billpos):
		writer.writerow([rec.id, rec.created, rec.email, rec.firstname, rec.lastname, rec.zipcode])
	
	return response

