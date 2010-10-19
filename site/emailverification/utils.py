from django.core.urlresolvers import reverse
from django.core.mail import send_mail

from models import *

from settings import SITE_ROOT_URL, EMAILVERIFICATION_FROMADDR

def send_email_verification(email, searchkey, action):
	r = Record()
	r.email = email
	r.set_code()
	r.searchkey = searchkey
	r.set_action(action)
	
	emailsubject = action.email_subject()
	emailbody = action.email_body()
	
	emailbody = emailbody.replace("<URL>", SITE_ROOT_URL + reverse("emailverification.views.processcode", args=[r.code]))

	send_mail(emailsubject, emailbody, EMAILVERIFICATION_FROMADDR, [email], fail_silently=False)
	
	r.save()

