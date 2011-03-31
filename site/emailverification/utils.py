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
	
	emailbody = emailbody.replace("<URL>", r.url())
	
	fromaddr = getattr(settings, 'EMAILVERIFICATION_FROMADDR',
			getattr(settings, 'SERVER_EMAIL', 'no.reply@example.com'))
	if hasattr(action, "get_from_address"):
		fromaddr = action.get_from_address()

	send_mail(emailsubject, emailbody, fromaddr,
		[email], fail_silently=False)
	
	r.save()

