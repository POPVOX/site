from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.core.mail import send_mail
import django.core.urlresolvers

from jquery.ajax import json_response, validation_error_message, ajaxmultifieldupdate, ajax_fieldupdate_request
from registration.helpers import validate_username, validate_password, validate_email, captcha_html, validate_captcha, change_email_address

from datetime import datetime
import re

from settings import SITE_ROOT_URL, MANAGERS, EMAILVERIFICATION_FROMADDR
from popvox.models import *
import popvox.govtrack

from emailverification.utils import send_email_verification

def test_field_provided(request, fieldname, fielderrors=None):
	value = request.POST[fieldname].strip()
	if value == "":
		if fielderrors == None:
			e = forms.ValidationError("This field is required.")
			e.source_field = fieldname
			raise e
		else:
			fielderrors[fieldname] = "This field is required."
	return value

class ApproveOrgRoleCallback:
	user = None
	org = None
	title = None
	
	def email_subject(self):
		return "POPVOX: Approve New Org Admin: " + self.user.email + " for " + self.org.name
	
	def email_body(self):
		return """Hello!

""" + self.user.userprofile.fullname + """ <""" + self.user.email + """> (""" + self.user.username + """) has created a new user account and wants to be an administrator for """ + self.org.name + """. Approve this by following this link:

<URL>

If you do not want to approve this action, don't click the link. You might
want to email the individual to explain why.

POPVOX
"""

	def get_response(self, request, vrec):
		if UserOrgRole.objects.filter(user = self.user, org = self.org).exists():
			return HttpResponse("The org administrator was already approved.", mimetype="text/plain")
		
		role = UserOrgRole()
		role.user = self.user
		role.org = self.org
		role.title = self.title
		role.save()
		
		createdbyus = ""
		if self.org.createdbyus:
			createdbyus = """
Your may notice that your organization was already in our advocacy directory.
We at POPVOX created the initial account for your organization. However,
we will now leave it to you to finish your organization's profile and enter its
legislative agenda.
"""
		
		# also, automatically reset flags on our pre-populated orgs
		self.org.createdbyus = False
		self.org.approved = True
		self.org.save()
			
		send_mail("POPVOX: Account Confirmed",
"""Hello """ + self.user.username + """.

We've checked our records and you are now set to begin updating
your organization's profile on POPVOX. You can do so at this address:

""" + SITE_ROOT_URL + self.org.url() + """/_edit
""" + createdbyus + """
Thanks for participating!

POPVOX
""", EMAILVERIFICATION_FROMADDR, [self.user.email], fail_silently=False)
		
		####

		send_mail("POPVOX: New Org Admin Approved: " + self.user.email + " for " + self.org.name, "This is just a note that someone approved the new user.", EMAILVERIFICATION_FROMADDR, [MANAGERS[0][1]], fail_silently=True)
		
		####

		if request.user.is_staff: # redirect to admin page for the new org
			return HttpResponseRedirect(django.core.urlresolvers.reverse('admin:popvox_userorgrole_change', args=(role.id,)))
		return HttpResponse("Org administrator approved!", mimetype="text/plain")

class ApproveOrgCallback:
	user = None
	org = None
	
	def email_subject(self):
		return "POPVOX: Approve New Org: " + self.org.name
	
	def email_body(self):
		return """Hi, team! Someone has registered a new organization which now awaits approval:

Organization: """ + self.org.name + """ <""" + str(self.org.website) + """>
User: """ + self.user.userprofile.fullname + """ <""" + self.user.email + """> (""" + self.user.username + """)
Type: """ + self.org.get_type_display() + """
Members: """ + self.org.claimedmembership + """

The organization needs approval before the user can publish it. Approve the organization by following this link

<URL>

If you do not want to approve the organization, do not click the link.
You might want to explain to the individual why the organization was
not approved.

POPVOX
"""

	def get_response(self, request, vrec):
		self.org = Org.objects.get(id=self.org.id)
		if self.org.approved:
			return HttpResponse("The org was already approved.", mimetype="text/plain")
		
		self.org.approved = True
		self.org.save()
		
		send_mail("POPVOX: Organization Approved",
"""Hello """ + self.user.username + """.

Your organization has been approved for listing on POPVOX. You
can now publish your organization to our advocacy directory by
following this link to your organization profile.  You may have to
copy and paste the link into your web browser.

""" + SITE_ROOT_URL + self.org.url() + """/_edit

Thanks for participating!

POPVOX
""", EMAILVERIFICATION_FROMADDR, [self.user.email], fail_silently=False)
		
		####

		send_mail("POPVOX: New Org Approved: " + self.org.name, "This is just a note that someone approved the new organization.", EMAILVERIFICATION_FROMADDR, [MANAGERS[0][1]], fail_silently=True)
		
		####

		if request.user.is_staff: # redirect to admin page for the new org
			return HttpResponseRedirect(django.core.urlresolvers.reverse('admin:popvox_org_change', args=(self.org.id,)))
		return HttpResponse("Org approved!", mimetype="text/plain")

# This object is stored in the email verification app's model as a picked stream
# so if we want to add more fields, put them in etcetera or version the class
# (but possibly keep this one in case there are existing records).
class RegisterUserAction:
	email = None
	username = None
	password = None
	mode = None
	
	next = None # redirect
	
	# individuals
	state = None
	district = None
	
	# leg and org staff
	fullname = None
	
	# leg staff
	member = None
	committee = None
	position = None
	
	# org staff
	org = None
	orgname = None
	orgwebsite = None
	title = None
	orgtype = None
	orgclaimedmembership = None
	
	referralcode = None
	referralcampaign = None
	
	etcetera = { }

	def email_subject(self):
		return "POPVOX: Finish Creating Your Account"
		
	def email_body(self):
		return """Thanks for coming to POPVOX. To finish creating your account
just follow this link. You may have to copy and paste it into your web browser.

<URL>

All the best,

POPVOX

(If you did not request a POPVOX account, please ignore this email and
sorry for the inconvenience.)"""

	def get_response(self, request, vrec):
		request.goal = { "goal": "registration-email-confirmed", "mode": self.mode }
		return self.finish(request)
		
	# also called in bills.py when user is creating an account while making a comment
	def finish(self, request):
		redirect = "/home"
		if self.next != None:
			redirect = self.next
		
		is_repeat_click = False
		try:
			# Allow for the case where the user clicks the link twice.
			user = User.objects.get(email=self.email)
			is_repeat_click = True
		except:
			# TODO: If someone grabs the username before this guy can finish
			# registration, then this probably errors out. The user gets an invalid code
			# message, but at least the code stays live. While normally it wouldn't
			# be a big deal to just tell the user he should go back and choose another
			# name, since this object is wrapped by other delayed actions that expect
			# the user to be created after this, we should throw the user a bone and
			# make up an alternate, unique username. And then warn the user of
			# the change. Maybe.
			user = User.objects.create_user(self.username, self.email, self.password)
			user.save()
		
		# Set general profile info,
		profile = user.userprofile
		profile.state = self.state
		profile.district = self.district
		profile.fullname = self.fullname
		profile.save()
		
		if self.mode == "legstaff" and not is_repeat_click:
			# We only get here if the user provided a house.gov or senate.gov address
			# so we don't require approval for this role.
			role = UserLegStaffRole()
			role.user = user
			role.member = MemberOfCongress.objects.get(id=self.member) if self.member != None else None
			role.committee = CongressionalCommittee.objects.get(code=self.committee) if self.committee != None else None
			role.position = self.position
			role.save()
			
		if self.mode == "orgstaff":
			redirect = self.register_org(request, user)

		user = authenticate(user_object = user) # registration app auth backend
		login(request, user)
		
		if self.mode == "":
			messages.success(request, "Welcome to POPVOX!")
		
		return HttpResponseRedirect(redirect)

	def register_org(self, request, user):
		# De-dup based on the web address. If it's new, create a new Org.
		org = None
		
		dedupset = [self.orgwebsite, self.orgwebsite.replace("http://www.", "http://"), self.orgwebsite.replace("http://", "http://www.")]
		for url in list(dedupset):
			if url.endswith("/"):
				dedupset.append(url[0:len(url)-1])
			else:
				dedupset.append(url+"/")
	
		for url in dedupset:
			try:
				org = Org.objects.get(website = url)
				break
			except:
				pass
		
		if org != None and user.orgroles.filter(org = org).exists():
			# the user is already an admin for the org
			messages.success(request, "You are already an administrator for this organization,")
			redirect = org.url() + "/_edit"
			
		elif org != None:
			# If the org is existing, then we don't need to approve the org
			# but we do need to approve the user's role.
			a2 = ApproveOrgRoleCallback()
			a2.user = user
			a2.org = org
			a2.title = self.title
			send_email_verification(MANAGERS[0][1], None, a2)
			redirect = "/accounts/register/needs_approval"
			
		else:
			# If the org is new, then we automatically accept the person as
			# an administrator for the organization BUT we require that
			# the org be approved by us.
			
			org = Org()
			org.name = self.orgname
			org.website = self.orgwebsite
			org.type = self.orgtype
			org.claimedmembership = self.orgclaimedmembership
			org.set_default_slug()
			org.createdbyus = False
			org.approved = False
			org.save()
			
			role = UserOrgRole()
			role.user = user
			role.org = org
			role.title = self.title
			role.save()
			
			redirect = org.url() + "/_edit"
			
			a2 = ApproveOrgCallback()
			a2.user = user
			a2.org = org
			send_email_verification(MANAGERS[0][1], None, a2)
			
		return redirect

def register(request, regtype):
	# regtype can be "/orgstaff" or "/legstaff". Show the appropriate template.
	# In either case they go through the same process.
	if regtype == None:
		regtype = ""
	else: # chop off /
		regtype = regtype[1:]
	return render_to_response('registration/registration_form.html',
		{
			"mocs": govtrack.getMembersOfCongress(),
			"committees": [c for c in govtrack.getCommitteeList() if not "parent" in c],
			"mode": regtype,
			"org_types": [t for t in Org.ORG_TYPES if t[0] != Org.ORG_TYPE_NOT_SET],
			"org_cm": Org.ORG_CLAIMEDMEMBERSHIP_CHOICES[1:],
			"captcha": captcha_html(),
			"next": None if not "next" in request.GET else request.GET["next"] },
		context_instance=RequestContext(request))
	
def register_response(request, page):
	return render_to_response('registration/registration_' + page + '.html',
		{ "email": request.GET["email"] if "email" in request.GET else "" }, 
		context_instance=RequestContext(request))

def legstaffemailcheck(value):
	if not value.lower().endswith("@mail.house.gov") and not value.lower().endswith("@senate.gov") and not value.lower().endswith(".senate.gov"):
		return False
	return True

from popvox import printexceptions

@json_response
@printexceptions
def register_validation(request):
	status = { }
	
	if request.POST["mode"] == "orgstaff" and request.user.is_authenticated():
		email = None
		username = None
		password = None
		
		if not request.user.orgroles.all().exists():
			# not sure where to put this status
			status["fullname"] = "You cannot register an organization under an invidual or legislative staff account. Contact POPVOX staff for assistance."
		
	else:
		password = validate_password(request.POST["password"], fielderrors = status)
		if password != request.POST["password2"]:
			status["password"] = "The passwords didn't match. Check that you entered it twice correctly."
		email = validate_email(request.POST["email"], fielderrors = status)
		
		if request.POST["mode"] == "":
			username = validate_username(request.POST["username"], fielderrors = status)
		else:
			# for leg staff and org staff, we'll use the email address for the username
			# too, since we never actually use it for anything but Django needs it.
			username = email
			
		if request.POST["mode"] != "legstaff" and legstaffemailcheck(email):
			status["email"] = "Congressional staff should register in the Congressional Staffer section. Click the Congressional Staffer button at the top of the page."
		
	axn = RegisterUserAction()
	axn.email = email
	axn.username = username
	axn.password = password
	
	if "next" in request.POST:
		axn.next = request.POST["next"]
	
	if request.POST["mode"] == "legstaff":
		if not legstaffemailcheck(axn.email):
			 status["email"] = "Provide a mail.house.gov or senate.gov email address."

		axn.mode = "legstaff"
		axn.fullname = test_field_provided(request, "fullname", fielderrors = status)
		#if request.POST["member"] == "" and request.POST["committee"] == "":
		#	status["member"] = "You must select either the Member of Congress you work for or the congressional committee you work for."
		axn.member = int(request.POST["member"]) if request.POST["member"] != "" else None
		axn.committee = request.POST["committee"]
		axn.position = test_field_provided(request, "position", fielderrors = status)
	
	if request.POST["mode"] == "orgstaff":
		axn.mode = "orgstaff"

		axn.fullname = test_field_provided(request, "fullname", fielderrors=status)

		axn.orgname = test_field_provided(request, "orgname", fielderrors=status)
		
		axn.orgwebsite = request.POST["orgwebsite"]
		if axn.orgwebsite != "" and axn.orgwebsite[0:7] != "http://":
			axn.orgwebsite = "http://" + axn.orgwebsite
		if axn.orgwebsite == "http://":
			status["orgwebsite"] = "This field is required."
		else:
			try:
				axn.orgwebsite = forms.URLField(required=True, verify_exists = True).clean(axn.orgwebsite) # raises ValidationException
			except forms.ValidationError, e:
				status["orgwebsite"] = validation_error_message(e)
		
		axn.title = test_field_provided(request, "title", fielderrors=status)

		axn.orgtype = test_field_provided(request, "orgtype", fielderrors=status)
		try:
			axn.orgtype = int(axn.orgtype)
		except:
			pass
		axn.orgclaimedmembership = test_field_provided(request, "orgclaimedmembership", fielderrors=status)
		
	if len(status) != 0:
		return { "status": "fail", "byfield": status }
	
	validate_captcha(request)
	
	if request.user.is_authenticated() and request.POST["mode"] == "orgstaff":
		# If the user is already logged in and attempts to register an organization,
		# skip the part about creating a new account.
		redirect = axn.register_org(request, request.user)
		return { "status": "success", "redirect": redirect }

	try:
		send_email_verification(email, None, axn)
	except Exception, e:
		return { "status": "fail", "msg": "There was a problem sending you an email: " + unicode(e) }
		
	request.goal = { "goal": "registration-start", "mode": axn.mode }

	return { "status": "success" }
		

@login_required
def account_profile(request):
	return render_to_response('registration/profile.html', {
			"mocs": govtrack.getMembersOfCongress(),
			"committees": govtrack.getCommitteeList(),
		},
		context_instance=RequestContext(request))

@ajaxmultifieldupdate([])
@login_required
def account_profile_update(request, field, value, validate_only):
	if field == "username":
		value = validate_username(value, skip_if_this_user=request.user)
		if not validate_only and value != request.user.username:
			request.user.username = value
			request.user.save()
		return { "status": "success", "value": value }
		
	elif field == "email":
		value = validate_email(value, skip_if_this_user = request.user)
		if request.user.userprofile.is_leg_staff() and not legstaffemailcheck(value):
			return { "status": "fail", "msg": "You must use a mail.house.gov or senate.gov email address." }
		
		if value == request.user.email:
			return { "status": "success" }
		
		users = User.objects.filter(email = value)
		if len(users) != 0:
			return { "status": "fail", "msg": "Someone else is using that address." }
			
		if validate_only:
			return { "status": "success" }
		
		change_email_address(request.user, value)
		
		return { "status": "success", "value": request.user.email, "msg": "We have sent a verification email to " + value + " to confirm the address. If you do not receive a message within the next minute or two, please check your junk mail folder." }
	
	elif field == "allow_mass_mails":
		if not validate_only:
			prof = request.user.get_profile()
			prof.allow_mass_mails = (value == "1")
			prof.save()
		return { "status": "success" }
	
	elif field == "congressionaldistrict":
		# I don't think we are using this for anything right now.
		prof = request.user.get_profile()
		if validate_only:
			return { "status": "success" }
		state, district = value.split("|")
		try:
			prof.state = state
			prof.district = district
			prof.save()
			return { "status": "success" }
		except Exception, e:
			return { "status": "fail", "msg": e }
			
	elif field == "fullname":
		if validate_only:
			return { "status": "success" }
		if value == "":
			value = None
		prof = request.user.get_profile()
		prof.fullname = value
		prof.save()
		return { "status": "success", "value": value }
		
	elif field == "member":
		# TODO: Validate
		value = int(value) if value != "" else None
		role = request.user.legstaffrole
		role.member = MemberOfCongress.objects.get(id=value) if value != None else None
		if validate_only:
			return { "status": "success" }
		role.save()
		return { "status": "success", "value": value }
	elif field == "committee":
		# TODO: Validate
		if value == "":
			value = None
		role = request.user.legstaffrole
		role.committee = CongressionalCommittee.objects.get(code=value) if value != None else None
		if validate_only:
			return { "status": "success" }
		role.save()
		return { "status": "success", "value": value }
	elif field == "position":
		# TODO: Validate
		if validate_only:
			return { "status": "success" }
		if value == "":
			value = None
		role = request.user.legstaffrole
		role.position = value
		role.save()
		return { "status": "success", "value": value }
		
	elif field.startswith("orgrole_"):
		m = re.match("orgrole_(.*)_(.*)", field)
		orgslug = m.group(1)
		field = m.group(2)
		
		userrole = request.user.orgroles.get(org__slug = orgslug)
		
		if field == "title":
			if validate_only:
				return { "status": "success" }
			userrole.title = value
			userrole.save()
			return { "status": "success" }
		else:
			raise Exception("Bad request: Invalid field.")
	else:
		raise Exception("Bad request: Invalid field.")

@json_response
@ajax_fieldupdate_request
@login_required
def account_profile_update2(request, field, value, validate_only):
	if field == "issue-add":
		ix = IssueArea.objects.filter(id=int(value))[0]
		if validate_only:
			return { "status": "success" }
		request.user.userprofile.issues.add(ix)
		request.user.userprofile.save()
		return { "status": "success" }
	elif field == "issue-remove":
		ix = IssueArea.objects.filter(id=int(value))[0]
		if validate_only:
			return { "status": "success" }
		request.user.userprofile.issues.remove(ix)
		request.user.userprofile.save()
		return { "status": "success" }
	else:
		raise Exception("Bad request: Invalid field.")

def switch_to_demo_account(request, acct):
	if not request.user.is_authenticated() or (not request.user.is_staff and not request.user.username == "POPVOXTweets" and not request.user.username == "demo_leg_staffer" and not request.user.username == "demo_org_staffer"):
		raise Http404()
	
	if acct == "demo_user":
		acct = "POPVOXTweets"
	user = authenticate(user_object = User.objects.get(username = acct))
	login(request, user)
	
	return HttpResponseRedirect(request.META["HTTP_REFERER"])

@json_response
@login_required
def trackbill(request):
	if not "bill" in request.POST or not "track" in request.POST:
		raise Http404()
	bill = get_object_or_404(Bill, id=int(request.POST["bill"]))
	
	if request.POST["track"] == "+":
		if bill not in request.user.userprofile.tracked_bills.all():
			request.user.userprofile.tracked_bills.add(bill)
			return { "status": "success", "value": "+" }
		else:
			request.user.userprofile.tracked_bills.remove(bill)
			return { "status": "success", "value": "0" }
	elif request.POST["track"] == "-":
		if bill not in request.user.userprofile.antitracked_bills.all():
			request.user.userprofile.antitracked_bills.add(bill)
			return { "status": "success", "value": "-" }
		else:
			request.user.userprofile.antitracked_bills.remove(bill)
			return { "status": "success", "value": "0" }

	raise Http404()

