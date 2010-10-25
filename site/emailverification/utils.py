from django.core.urlresolvers import reverse
from django.core.mail import send_mail

from models import *

import settings

def send_email_verification(email, searchkey, action):
	r = Record()
	r.email = email
	r.set_code()
	r.searchkey = searchkey
	r.set_action(action)
	
	emailsubject = action.email_subject()
	emailbody = action.email_body()
	
	emailbody = emailbody.replace("<URL>", getattr(settings, 'SITE_ROOT_URL', 'http://www.example.com') + reverse("emailverification.views.processcode", args=[r.code]))

	send_mail(emailsubject, emailbody,
		getattr(settings, 'EMAILVERIFICATION_FROMADDR',
			getattr(settings, 'SERVER_EMAIL',
				'no.reply@example.com')),
		[email], fail_silently=False)
	
	r.save()

