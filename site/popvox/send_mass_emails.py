#!runscript

# for user stickiness emails:
# EMAIL_BACKEND=AWS-SES SEND=SEND LIMIT=250 popvox/send_mass_emails.py userstickinessemail

# For the remaining, maybe send only to users that haven't come back in 
# the last month or 6 weeks?

from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives

from popvox.models import UserProfile, RawText, UserComment

import os
import datetime
import sys
import random

if sys.argv[-1] == "welcome":
	email_from = "POPVOX <info@popvox.com>"
	body_obj = RawText.objects.get(name="registration-user")

	email_opts = [
		("Your message to Congress will soon be delivered by POPVOX", body_obj.text, body_obj.html()),
		]
		
	users = UserProfile.objects.filter(
		allow_mass_mails=True,
		registration_welcome_sent=False,
		user__date_joined__gt = datetime.datetime.now() - datetime.timedelta(hours=4),
		user__comments__id__isnull=False,
		).distinct()
		# user__comments__id__isnull filters out users that have not
		# left a comment, but it also creates duplicate rows from
		# the left join, so distinct fixes that.
	def mark(userprof):
		userprof.registration_welcome_sent = True
		userprof.save()
elif sys.argv[-1] == "survey":
	email_from = "POPVOX <rachna@popvox.com>"
	body_obj = RawText.objects.get(name="registration-userfollowup")

	email_opts = [
		("POPVOX survey -- We need your feedback", body_obj.text, body_obj.html()),
		]

	users = UserProfile.objects.filter(
		allow_mass_mails=True,
		registration_followup_sent=False,
		user__date_joined__gt = datetime.datetime.now() - datetime.timedelta(days=30),
		user__date_joined__lt = datetime.datetime.now() - datetime.timedelta(days=3)
		)
	def mark(userprof):
		userprof.registration_followup_sent = True
		userprof.save()
else:
	email_from = "POPVOX <info@popvox.com>"

	email_opts = []
	for rt in RawText.objects.filter(name=sys.argv[-1]) | RawText.objects.filter(name__startswith=sys.argv[-1]+"_"):
		# take the first line out as the email subject
		rt.text = rt.text.replace("\r\n", "\n").replace("\r", "\n")
		rt.text = rt.text.split("\n")
		sbj = rt.text.pop(0)
		rt.text = "\n".join(rt.text)
		email_opts.append( (sbj, rt.text, rt.html()) )

	users = UserProfile.objects.filter(
		allow_mass_mails=True,
		user__last_login__lt = datetime.datetime.now() - datetime.timedelta(days=15),
		user__comments__method__in = (UserComment.METHOD_SITE, UserComment.METHOD_CUSTOMIZED_PAGE)
		).distinct()
	print users.count()
	users = (user for user in users if not user.getopt("email_" + sys.argv[-1]))
	def mark(userprof):
		userprof.setopt("email_" + sys.argv[-1], True)

counter = 0
for userprof in users:
	if userprof.is_org_admin() or userprof.is_leg_staff():
		continue

	counter += 1
	user = userprof.user
		
	(sbj, email_body, email_body_html) = random.choice(email_opts)

	msg = EmailMultiAlternatives(sbj,
		email_body.replace("% ", "%% ") % (user.username,),
		email_from,
		[user.email])
	msg.attach_alternative(email_body_html.replace("% ", "%% ") % (user.username), "text/html")
	
	#print user.email, user.date_joined, user.last_login
	if os.environ.get("SEND", "") != "SEND":
		print "To:", user.email
		print "From:", email_from
		print "Subject:", sbj
		print
		print (email_body.replace("% ", "%% ") % (user.username,)).encode("utf8")
		break
	
	try:
		msg.send()
	except Exception, e:
		print user.email, str(e)
		if str(type(e)) == "<class 'boto.exception.BotoServerError'>":
			if e.error_message == "Address blacklisted.":
				userprof.allow_mass_mails = False
				userprof.save()
		continue

	mark(userprof)

	# only send 250 at a time while we're doing user stickiness
	# so we don't go over AWS quota
	if "LIMIT" in os.environ and counter == int(os.environ["LIMIT"]):
		break

print counter

