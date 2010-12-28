# REMOTEDB=1 DEBUG=1 PYTHONPATH=. DJANGO_SETTINGS_MODULE=settings python popvox/registration_followup.py

from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives

from popvox.models import UserProfile

import datetime
import markdown

email_subject = "POPVOX survey -- We need your feedback"
email_from = "POPVOX <rachna@popvox.com>"
email_body = """
Dear %s,

On behalf of our team, I'd like to personally thank you for trying POPVOX.com.

On January 5, the 112th Congress will begin its session with a clean legislative slate.  Many of the bills that have been discussed and debated on POPVOX and in the halls of Congress will be reintroduced and given a new bill number (which begins with HR or S).  We expect a flurry of activity.  In fact when the last session of Congress convened, over 400 bills were introduced on the first day!

With this in mind, I'm asking for your help. Since we're working every day to make improvements and add new features to the site, could you answer some questions for us about your experience on POPVOX?

We have set up a short survey at <http://www.surveymonkey.com/s/7SV8LC6>. Your opinions will help us improve the site and decide on next steps for POPVOX.  

Sincerely,

Rachna and the POPVOX Team
_____
Rachna Choudhry  
Chief Marketing Officer  
POPVOX  
<rachna@popvox.com>  
<http://www.popvox.com>  

_____
To opt out of future emails from us use your account settings page: <http://www.popvox.com/accounts/profile>.
"""

email_body_html = markdown.markdown(email_body, output_format='html4')

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

