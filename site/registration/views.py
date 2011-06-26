from django import forms
from django.http import HttpResponseNotFound, HttpResponseRedirect
from django.core.urlresolvers import reverse, resolve
from django.shortcuts import render_to_response
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.backends import ModelBackend
from django.template import RequestContext
from django.contrib import messages

import urlparse

from jquery.ajax import json_response, validation_error_message
from emailverification.utils import send_email_verification

import providers
from models import *
from helpers import validate_username, validate_password, validate_email, captcha_html, validate_captcha

from settings import SITE_ROOT_URL, LOGIN_REDIRECT_URL, APP_NICE_SHORT_NAME

def loginform(request):
	errors = ""
	
	if "email" in request.POST and "password" in request.POST:
		email = None
		try:
			email = forms.EmailField().clean(request.POST["email"])
		except forms.ValidationError, e:
			errors = "That's not a valid email address."
			
		password = None
		try:
			password = forms.CharField().clean(request.POST["password"])
		except forms.ValidationError, e:
			#print e
			pass
	
		if email != None and password != None:
			user = authenticate(email=email, password=password)
			if user is not None:
				if user.is_active:
					login(request, user)
					if request.POST.get("next","").strip() != "":
						try:
							validate_next(request, request.POST["next"]) # raises exception on error
							return HttpResponseRedirect(request.POST["next"])
						except Exception, e:
							#print e
							pass # fall through
					return HttpResponseRedirect(LOGIN_REDIRECT_URL)
				else:
					errors = "Your account has been disabled!"
			else:
				errors = "Your email and password were incorrect."
		    
	return render_to_response('registration/login.html', {
		"errors": errors,
		"email": "" if not "email" in request.POST else request.POST["email"],
		"password": "" if not "password" in request.POST else request.POST["password"],
		"next": "" if not "next" in request.REQUEST else request.REQUEST["next"],
		},
		context_instance=RequestContext(request))

class EmailPasswordLoginBackend(ModelBackend):
	"""
	Allows us to log users in with an email address instead of a username.
	
	This backend is registered with Django automatically by __init__.py.
	"""
	supports_object_permissions = False
	supports_anonymous_user = False

	def authenticate(self, email = None, password = None):
		try:
			user = User.objects.get(email=email)
			if user.check_password(password):
				return user
		except:
			pass
		return None

def validate_next(request, next):
	# We must not allow anyone to use the redirection that occurs in logins
	# to create an open redirector to spoof URLs.
	
	# The easiest thing to do would be to only allow local URLs to be redirected
	# to, however if we're operating in an iframe then we may want to open
	# a OAuth lijnk a link with target=_top (otherwise Chrome loses the referer
	# header which happens to be important to me) and a next= that is off
	# our domain but to a page that will re-load the widget. Sooooo... we'll allow
	# unrestricted next= if the referer is on our domain. (nb. <base target="_top"/>)
	try:
		if urlparse.urlparse(request.META.get("HTTP_REFERER", "http://www.example.org/")).hostname == urlparse.urlparse(SITE_ROOT_URL).hostname:
			return
	except: # invalid referrer header
		pass

	# Check that the page is a local page by running it through URLConf's reverse.
	
	if "#" in next: # chop off fragment
		next = next[0:next.index("#")]
	if "?" in next: # chop off query string
		next = next[0:next.index("?")]
	if next[0:len(SITE_ROOT_URL)] == SITE_ROOT_URL:
		next = next[len(SITE_ROOT_URL):]
	func, args, kwargs = resolve(next) # validate that it's on our site. raises a Http404, though maybe wrapping it in a 403 would be better
	
def external_start(request, login_associate, provider):
	if not provider in providers.providers:
		return HttpResponseNotFound()

	if login_associate == "associate" and not request.user.is_authenticated():
		login_associate = "login"

	if "next" in request.GET:
		validate_next(request, request.GET["next"]) # raises exception on error
		request.session["oauth_finish_next"] = request.GET["next"]
		
	if providers.providers[provider]["method"] =="openid2" or True:
		# the callback must match the realm, which is always SITE_ROOT_URL
		callback = SITE_ROOT_URL + reverse(external_return, args=[login_associate, provider])
	else:
		# be nicer and build the callback URL from the HttpRequest, in case we are not
		# hosting SITE_ROOT_URL (i.e. debugging).
		callback = request.build_absolute_uri(reverse(external_return, args=[login_associate, provider]))
	request.session["oauth_finish_url"] = callback

	scope = request.GET.get("scope", None)
	mode = request.GET.get("mode", None)

	response = HttpResponseRedirect( providers.methods[providers.providers[provider]["method"]]["get_redirect"](request, provider, callback, scope, mode))
	response['Cache-Control'] = 'no-store'
	return response
		
def external_return(request, login_associate, provider):
	try:
		finish_authentication = providers.methods[providers.providers[provider]["method"]]["finish_authentication"]
		
		(provider, auth_token, profile) = finish_authentication(
			request,
			provider,
			request.session["oauth_finish_url"]
			)
		del request.session["oauth_finish_url"]
	except providers.UserCancelledAuthentication:
		request.goal = { "goal": "oauth-cancel" }
		return HttpResponseRedirect(request.session["oauth_finish_next"] if "oauth_finish_next" in request.session else reverse(loginform))
	except Exception, e:
		# Error might indicate a protocol error or else the user denied the
		# authorization.
		import sys
		sys.stderr.write("oauth-fail: " + str(e) + "\n");
		request.goal = { "goal": "oauth-fail" }
		messages.error(request, "There was an error logging in.")
		return HttpResponseRedirect(request.session["oauth_finish_next"] if "oauth_finish_next" in request.session else reverse(loginform))
		
	uid = providers.providers[provider]["profile_uid"](profile)
	
	# be sure to get this before possibly logging the user out, which clears session state
	next = LOGIN_REDIRECT_URL
	if "oauth_finish_next" in request.session:
		next = request.session["oauth_finish_next"]
	
	rr = AuthRecord.objects.filter(provider = provider, uid = uid)
	if len(rr) == 0:
		# These credentials are new to us.
		
		# If we are doing an association to an existing account, take care of it
		# now and redirect.
		user = None
		if login_associate == "associate" and request.user.is_authenticated():
			user = request.user
			request.goal = { "goal": "oauth-associate" }
			
		# If the profile provides a trusted email address which is tied to a
		# registered account here, then we can log them in and create
		# a new AuthRecord.
		elif "trust_email" in providers.providers[provider] and providers.providers[provider]["trust_email"] and "email" in profile:
			try:
				user = User.objects.get(email = profile["email"])
				request.goal = { "goal": "oauth-login" }
			except:
				pass
			
		if user != None:
			rec = AuthRecord()
			rec.provider = provider
			rec.uid = uid
			rec.user = user
			rec.auth_token = auth_token
			rec.profile = profile
			rec.save()
			
			if user != request.user: # new AuthRecord for existing account
				if request.user.is_authenticated(): # avoid clearing session state
					logout(request)
				user = authenticate(user_object = user)
				login(request, user)
			
			return HttpResponseRedirect(next)
			
		# Otherwise log the user out so we can do a new user registration.
		if request.user.is_authenticated():
			logout(request)
		
		# This is a third-party login that causes a new user registration. We need
		# to let the user choose a username and if the login provider does not
		# provide a trusted email address, then we have to ask for an email address
		# and check it. We'll store what we know in the session state for now.
		# Don't set a goal here since we'll set the registration goal when it's complete.
		request.session["registration_credentials"] = (provider, auth_token, profile, uid, next)
		return HttpResponseRedirect(reverse(external_finish))
	
	# Credentials exist.
	
	rr = rr[0]
	
	# update latest profile information
	rr.auth_token = auth_token
	rr.profile = profile
	rr.save()
	
	# If we are doing an association....
	if login_associate == "associate" and request.user.is_authenticated():
		request.goal = { "goal": "oauth-associate" }
		
		if rr.user != request.user:
			# if the record is associated with an inactive account allow
			# the credentials to be poached
			if not rr.user.is_active:
				rr.user = request.user
				rr.save()
				messages.info(request, "You have connected your " +  providers.providers[provider]["displayname"] + " account.")
				
			# But if it's associated with a different active user, we can't change
			# the association.
			else:
				messages.info(request, "Your " +  providers.providers[provider]["displayname"] + " account is already connected to a different account here. It cannot be connected to a second account.")
				
		## We already have made this association.
		### BUT WE MIGHT BE ADDING SCOPE.
		#else:
		#	messages.info(request, "You already are connected to a " +  providers.providers[provider]["displayname"] + " account. To connect to a different account, you may need to log out from the " +  providers.providers[provider]["displayname"] + " website first.")
		
	# We are logging the user in.
	else:
		# If the user is not logged in or the record is associated with a different user,
		# switch the login to that user. Otherwise, the user is already logged in with
		# that account so there is nothing to do.
		request.goal = { "goal": "oauth-login" }
		if not request.user.is_authenticated() or (request.user.is_authenticated() and request.user != rr.user):
			if not rr.user.is_active:
				# Can't log in an inactive user.
				messages.error(request, "Your account is disabled.")
				return HttpResponseRedirect(reverse(loginform))
				
			if request.user.is_authenticated():
				# The auth record points to a different user, so log the user out and
				# then log them back in as the other user.
				prev_username = request.user.username
				logout(request)
				messages.warning(request, "You have been logged out of the " + prev_username + " account and logged into the account named " + rr.user.username + ".")
			
			user = authenticate(user_object = rr.user)
			login(request, user)
		
	return HttpResponseRedirect(next)

def external_finish(request):
	if not "registration_credentials" in request.session:
		# User is coming back to this page later on for no good reason?
		if request.user.is_authenticated():
			return HttpResponseRedirect(LOGIN_REDIRECT_URL)
		else:
			return HttpResponseRedirect("/")
	
	# Recover session info.
	(provider, auth_token, profile, uid, next) = request.session["registration_credentials"]
	
	if not "username" in request.POST:
		username = ""
		if "screen_name" in profile:
			username = profile["screen_name"]
		elif "email" in profile and "@" in profile["email"]:
			username = profile["email"][0:profile["email"].index("@")]
		
		# Show the form where the user can choose a username and email address.
		return render_to_response('registration/oauth_create_account.html',
			{
				"provider": provider,
				"username": username,
				"email": profile["email"] if "email" in profile and len(profile["email"]) <= 64 else "", # longer addresses might be proxy addresses provided by the service that the user isn't aware of and run the risk of getting truncated
			},
			context_instance=RequestContext(request))
		
	# Validation
		
	error = ""
		
	try:
		username = validate_username(request.POST["username"])
	except Exception, e:
		error += validation_error_message(e) + " "
		
	try:
		email = validate_email(request.POST["email"])
	except Exception, e:
		error += validation_error_message(e) + " "
	
	if error != "":
		# Show the form again with the last entered field values and the
		# validation error message.
		return render_to_response('registration/oauth_create_account.html',
			{
				"provider": provider,
				"username": request.POST["username"],
				"email": request.POST["email"],
				"error": error
			},
			context_instance=RequestContext(request))
	
	# Beign creating the account.
	
	axn = RegisterUserAction()
	axn.username = username
	axn.email = email
	axn.provider = provider
	axn.uid = uid
	axn.auth_token = auth_token
	axn.profile = profile
	axn.next = next
	
	# If we trust the email address --- because we trust the provider --- we can
	# create the account immediately.
	if "trust_email" in providers.providers[provider] and providers.providers[provider]["trust_email"] and "email" in profile and email == profile["email"]:
		return axn.finish(request)
		
	# Check that the email address is valid by sending an email and delaying registration.

	request.goal = { "goal": "oauth-register-emailcheck" }
	
	send_email_verification(email, None, axn)
	
	return render_to_response('registration/registration_check_inbox.html',
		{ "email": email },
		context_instance=RequestContext(request))

class RegisterUserAction:
	username = None
	email = None
	provider = None
	uid = None
	auth_token = None
	profile = None
	next = None
	
	def get_response(self, request, vrec):
		return self.finish(request)
		
	def finish(self, request):
		try:
			del request.session["registration_credentials"]
		except:
			pass

		try:
			# If this user has already been created, just log the user in.
			user = authenticate(user_object = User.objects.get(email=self.email))
			login(request, user)
			return HttpResponseRedirect(self.next)
		except:
			pass
		
		user = User.objects.create(username=self.username, email=self.email)
		user.set_unusable_password()
		user.save()
				
		user = authenticate(user_object = user)
		login(request, user)
	
		rec = AuthRecord()
		rec.provider = self.provider
		rec.uid = self.uid
		rec.user = user
		rec.auth_token = self.auth_token
		rec.profile = self.profile
		rec.save()		
		
		request.goal = { "goal": "oauth-register" }
		
		return HttpResponseRedirect(self.next)
		
	def email_subject(self):
		return APP_NICE_SHORT_NAME + ": Finish Creating Your Account"
	def email_body(self):
		return """Thanks for coming to """ + APP_NICE_SHORT_NAME + """. To finish creating your account
just follow this link:

<URL>

All the best,

""" + APP_NICE_SHORT_NAME + """

(If you did not request an account, please ignore this email and
sorry for the inconvenience.)"""

class DirectLoginBackend(ModelBackend):
	"""
	Allows us to log users in without knowing the user's password
	from Python code, using authenticate(user_object = user). But
	if the user.is_active is False, then authentication fails!
	
	This backend is registered with Django automatically by __init__.py.
	"""
	supports_object_permissions = False
	supports_anonymous_user = False

	def authenticate(self, user_object = None):
		if not user_object.is_active:
			return None
		return user_object

@json_response
def ajax_login(request):
	email = validate_email(request.POST["email"], for_login=True)
	password = validate_password(request.POST["password"])
	user = authenticate(email=email, password=password)
	if user == None:
		sso = AuthRecord.objects.filter(user__email=email)
		if len(sso) >= 1: # could also be the password is wrong
			return { "status": "fail", "msg": "You use an identity service provider to log in. Click the %s log in button to sign into this site." % " or ".join(set([providers.providers[p.provider]["displayname"] for p in sso])) }
		return { "status": "fail", "msg": "That's not a username and password combination we have on file." }
	elif not user.is_active:
		return { "status": "fail", "msg": "Your account has been disabled." }
	else:
		login(request, user)
		return { "status": "success" }
		
class ResetPasswordAction:
	userid = None
	email = None
	def get_response(self, request, vrec):
		user = User.objects.get(id = self.userid, email = self.email)
		
		# randomize the password
		newpw = User.objects.make_random_password(length=8, allowed_chars='ABCDEFGHJKLMNPQRSTUVWXYZ23456789')
		user.set_password(newpw)
		user.save()
		
		user = authenticate(user_object = user)
		login(request, user)
		
		return render_to_response('registration/reset_password_done.html', {
			"newpassword": newpw,
			},
			context_instance=RequestContext(request))
		
	def email_subject(self):
		return APP_NICE_SHORT_NAME + ": Reset Password"
	def email_body(self):
		return """Hello!

You have requested to reset your """ + APP_NICE_SHORT_NAME + """ account password. To
continue, please follow this link:

<URL>

If it was not you who requested the password reset for this email address,
just ignore this email.

All the best,

""" + APP_NICE_SHORT_NAME + """
"""

def resetpassword(request):
	status = ""
	if "email" in request.POST:
		try:
			validate_captcha(request)
			
			try:
				user = User.objects.get(email = request.POST["email"].strip())
				
				axn = ResetPasswordAction()
				axn.userid = user.id
				axn.email = user.email 
				
				send_email_verification(user.email, None, axn)
			except:
				pass
			
			status = "We've sent an email to that address with further instructions. If you do not receive an email, 1) check your junk mail folder and 2) make sure you correctly entered the address that you registered on this site."
			
		except:
			status = "The reCAPTCHA validation words you typed weren't right."
		
	return render_to_response('registration/reset_password.html', {
		"status": status,
		"captcha": captcha_html(),
		},
		context_instance=RequestContext(request))


