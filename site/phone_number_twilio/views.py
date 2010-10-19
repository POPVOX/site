from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
import django.core.urlresolvers 
from django.contrib.auth.decorators import login_required

from jquery.ajax import json_response

from datetime import datetime, timedelta
import re
from xml.dom import minidom
from urllib import urlopen, quote_plus
import hashlib

from models import PhoneNumber, CODE_LENGTH, MAX_TRIES, LOCKED_DAYS
from settings import TWILIO_ACCOUNT_SID, TWILIO_ACCOUNT_TOKEN, TWILIO_OUTGOING_CALLERID, TWILIO_INCOMING_RESPONSE, TWILIO_STORE_HASHED_NUMBERS, SITE_ROOT_URL

import twilio

def hash_phone_number(pn):
	if not TWILIO_STORE_HASHED_NUMBERS:
		return pn
	m = hashlib.sha1()
	m.update(pn)
	return m.hexdigest()

@login_required
@json_response
def initiate(request):
	# Extract just the numbers to normalize.
	num = ""
	for d in request.POST["phonenumber"]:
		if d in ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9'):
			num += d
	if len(num) != 10:
		return { "status": "phone-number-invalid" }
		
	numhash = hash_phone_number(num)
	
	# Check if anyone (else) has verified or tried to verify the number already.
	try :
		pn = PhoneNumber.objects.get(phonenumber=numhash)
		if pn.user != request.user:
			if pn.verified:
				return { "status": "phone-number-taken" }
			elif (datetime.now() - pn.date).days <= LOCKED_DAYS:
				return { "status": "phone-number-locked" }
	except ObjectDoesNotExist:
		pass
	
	# Create a phone number verification record.
	try:
		pn = PhoneNumber.objects.get(user=request.user)

		if pn.verified and pn.phonenumber == numhash:
			return { "status": "thats-your-number" }

		# limit number of calls per account to prevent big bills from Twilio
		until = pn.locked_until()
		if until != None:
			return { "status": "you-are-already-verified", "until": until }
		if pn.callcount >= MAX_TRIES and (datetime.now() - pn.date).days <= LOCKED_DAYS:
			return { "status": "too-many-calls" }
		if (datetime.now() - pn.date).days > LOCKED_DAYS:
			pn.callcount = 0
	
	except ObjectDoesNotExist:
		pn = PhoneNumber()
		pn.user = request.user
		
	pn.date = datetime.now()
	pn.verified = False
	pn.phonenumber = numhash
	pn.make_verification_code()
	pn.callcount += 1
	pn.callinprogress = True
	pn.callstatus = "Making call..."
	pn.save()
	
	account = twilio.Account(TWILIO_ACCOUNT_SID, TWILIO_ACCOUNT_TOKEN)
	
	try:
		ret = account.request("/2010-04-01/Accounts/" + TWILIO_ACCOUNT_SID + "/Calls", "POST", {
			"From": TWILIO_OUTGOING_CALLERID,
			"To": "+1" + num,
			"Url": SITE_ROOT_URL + django.core.urlresolvers.reverse(pickup, args=[numhash]),
			"StatusCallback": SITE_ROOT_URL + django.core.urlresolvers.reverse(hangup, args=[numhash]),
			"Timeout": 15
			})
		if "RestException" in ret:
			return { "status": "fail" }
	except Exception, e:
		return { "status": "fail", "msg": str(e) }

	return { "status": "initiated", "code": pn.verificationcode }

@login_required
@json_response
def status(request):
	pn = PhoneNumber.objects.get(user=request.user)
	if pn == None:
		return { "status": "not-started" }
	if pn.verified:
		return { "status": "verified" }
	if (datetime.now() - pn.date).seconds > 60:
		return { "status": "expired" }
	return {
		"status": "waiting" if pn.callinprogress else "fail",
		"callstatus": pn.callstatus }

def callback(request, numhash):
	# Verify this is from Twilio.
	ut = twilio.Utils(TWILIO_ACCOUNT_SID, TWILIO_ACCOUNT_TOKEN)
	if not ut.validateRequest(request.build_absolute_uri(), request.POST, request.META["HTTP_X_TWILIO_SIGNATURE"]):
		raise HttpResponse("invalid hash", mimetype="text/plain")
	
	# Get the PhoneNumber record.
	try:
		return PhoneNumber.objects.get(phonenumber=numhash)
	except:
		r = twilio.Response()
		r.addHangup()
		return HttpResponse(str(r), mimetype="text/xml")

def pickup(request, numhash):
	# This is the callback on pickup.
	
	pn = callback(request, numhash)
	if type(pn) != PhoneNumber:
		return pn
				
	r = twilio.Response()
	g = r.addGather(timeout=15, numDigits=CODE_LENGTH,
		action=django.core.urlresolvers.reverse(digits, args=[numhash]))
	g.addSay("Hello. Please dial your verification code to confirm your phone number.")
	return HttpResponse(str(r), mimetype="text/xml")
		
def digits(request, numhash):
	# This is the callback after the user enters the digits.
	
	pn = callback(request, numhash)
	if type(pn) != PhoneNumber:
		return pn
		
	r = twilio.Response()
	if request.POST["Digits"] == pn.verificationcode:
		pn.date = datetime.now()
		pn.verified = True
		pn.callinprogress = False
		r.addSay("Thank you for verifying your phone number. Goodbye.")
	else:
		pn.callstatus = "Incorrect code entered..."
		g = r.addGather(timeout=15, numDigits=CODE_LENGTH)
		g.addSay("That's not right. Please dial the verification code given to you.")
	pn.save()
	return HttpResponse(str(r), mimetype="text/xml")

def hangup(request, numhash):
	# This is the call ended status callback.
	
	pn = callback(request, numhash)
	if type(pn) != PhoneNumber:
		return pn
				
	# Call failed before we got verification code...
	pn.callstatus = "Call ended. Verification failed."
	pn.callinprogress = False
	pn.save()

	r = twilio.Response()
	r.addHangup()
	return HttpResponse(str(r), mimetype="text/xml")


def incoming(request):
	# Someone is dialing our number!
	
	# Verify this is from Twilio.
	ut = twilio.Utils(TWILIO_ACCOUNT_SID, TWILIO_ACCOUNT_TOKEN)
	if not ut.validateRequest(request.build_absolute_uri(), request.POST, request.META["HTTP_X_TWILIO_SIGNATURE"]):
		return

	r = twilio.Response()
	r.addSay(TWILIO_INCOMING_RESPONSE)
	r.addHangup()
	return HttpResponse(str(r), mimetype="text/xml")
	
