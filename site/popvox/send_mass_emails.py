# REMOTEDB=1 DEBUG=1 PYTHONPATH=. DJANGO_SETTINGS_MODULE=settings python popvox/send_mass_emails.py

from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives

from popvox.models import UserProfile, RawText

import datetime
import sys
import random

if sys.argv[-1] == "welcome":
	email_subject = "Welcome to POPVOX!"
	email_from = "POPVOX <info@popvox.com>"
	body_obj = RawText.objects.get(name="registration-user")
	users = UserProfile.objects.filter(
		allow_mass_mails=True,
		registration_welcome_sent=False,
		user__date_joined__gt = datetime.datetime.now() - datetime.timedelta(hours=4),
		)
	def mark(userprof):
		userprof.registration_welcome_sent = True
		userprof.save()
elif sys.argv[-1] == "survey":
	email_subject = "POPVOX survey -- We need your feedback"
	email_from = "POPVOX <rachna@popvox.com>"
	body_obj = RawText.objects.get(name="registration-userfollowup")
	users = UserProfile.objects.filter(
		allow_mass_mails=True,
		registration_followup_sent=False,
		user__date_joined__gt = datetime.datetime.now() - datetime.timedelta(days=30),
		user__date_joined__lt = datetime.datetime.now() - datetime.timedelta(days=1.5)
		)
	def mark(userprof):
		userprof.registration_followup_sent = True
		userprof.save()
else:
	email_subject = RawText.objects.get(name=sys.argv[-1] + "_subject").text.strip()
	email_from = "POPVOX <info@popvox.com>"
	body_obj = RawText.objects.get(name=sys.argv[-1])
	users = UserProfile.objects.filter(
		allow_mass_mails=True,
		user__last_login__lt = datetime.datetime.now() - datetime.timedelta(days=15)
		)
	users = (user for user in users if not user.getopt("email_" + sys.argv[-1]))
	def mark(userprof):
		userprof.setopt("email_" + sys.argv[-1], True)
	
email_body = body_obj.text
email_body_html = body_obj.html()

for userprof in users:
	if userprof.is_org_admin() or userprof.is_leg_staff():
		continue
		
	user = userprof.user
		
	sbj = random.choice( email_subject.replace("\r", "").split("\n") )
		
	msg = EmailMultiAlternatives(sbj,
		email_body % (user.username,),
		email_from,
		[user.email])
	msg.attach_alternative(email_body_html % (user.username), "text/html")
	
	#print user.email
	if False:
		print "To:", user.email
		print "From:", email_from
		print "Subject:", sbj
		print
		print email_body % (user.username,)
		break
	
	try:
		msg.send()
	except Exception, e:
		print user.email, str(e)

	mark(userprof)

	#break
	