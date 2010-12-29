# REMOTEDB=1 DEBUG=1 PYTHONPATH=. DJANGO_SETTINGS_MODULE=settings python popvox/registration_followup.py

from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives

from popvox.models import UserProfile, RawText

import datetime

email_subject = "POPVOX survey -- We need your feedback"
email_from = "POPVOX <rachna@popvox.com>"
body_obj = RawText.objects.get(name="registration-userfollowup")
email_body = body_obj.text
email_body_html = body_obj.html()

for userprof in UserProfile.objects.filter(
#	user__email = "tauberer@gmail.com",
	allow_mass_mails=True,
	registration_followup_sent=False,
	user__date_joined__gt = datetime.datetime.now() - datetime.timedelta(days=30),
	user__date_joined__lt = datetime.datetime.now() - datetime.timedelta(days=1.5)
	):
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
		print user.email
	except Exception, e:
		print user.email, str(e)

	userprof.registration_followup_sent = True
	userprof.save()

