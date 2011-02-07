# REMOTEDB=1 DEBUG=1 PYTHONPATH=. DJANGO_SETTINGS_MODULE=settings python popvox/registration_followup.py

from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives

from popvox.models import UserProfile, RawText

import datetime

import sys

if sys.argv[-1] == "welcome":
	email_subject = "Welcome to POPVOX!"
	email_from = "POPVOX <info@popvox.com>"
	body_obj = RawText.objects.get(name="registration-user")
	users = UserProfile.objects.filter(
		allow_mass_mails=True,
		registration_welcome_sent=False,
		user__date_joined__gt = datetime.datetime.now() - datetime.timedelta(hours=4),
		)
	mark = "registration_welcome_sent"
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
	mark = "registration_followup_sent"
else:
	raise ValueError("Specify 'welcome' or 'survey'.")
	
email_body = body_obj.text
email_body_html = body_obj.html()

for userprof in users:
	if userprof.is_org_admin() or userprof.is_leg_staff():
		continue
		
	user = userprof.user
		
	msg = EmailMultiAlternatives(email_subject,
		email_body % (user.username),
		email_from,
		[user.email])
	msg.attach_alternative(email_body_html % (user.username), "text/html")
	
	try:
		msg.send()
	except Exception, e:
		print user.email, str(e)

	setattr(userprof, mark, True)
	userprof.save()

