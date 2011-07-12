from django.core.mail import send_mail, EmailMultiAlternatives
from django.template import Context, Template
from django.template.loader import get_template

from models import *

from datetime import datetime, timedelta

import settings

def send_email_verification(email, searchkey, action, send_email=True):
	r = Record()
	r.email = email
	r.set_code()
	r.searchkey = searchkey
	r.set_action(action)
	
	if send_email:
		send_record_email(email, action, r)
		
	r.save()

	return r
	
def send_record_email(email, action, r):
		emailsubject = action.email_subject()
		
		if hasattr(action, "email_body"):
			emailbody = action.email_body()
			emailbody = emailbody.replace("<URL>", r.url())
		elif hasattr(action, "email_text_template"):
			template_name, template_context_vars = action.email_text_template()
			templ = get_template(template_name)
			ctx = Context(template_context_vars)
			ctx["URL"] = r.url()
			emailbody = templ.render(ctx)
		else:
			raise ValueError("Action object is missing email_body and email_text_template. You must implement one.")
		
		fromaddr = getattr(settings, 'EMAILVERIFICATION_FROMADDR',
				getattr(settings, 'SERVER_EMAIL', 'no.reply@example.com'))
		if hasattr(action, "email_from_address"):
			fromaddr = action.email_from_address()
			
		if not hasattr(action, "email_html_template"):
			# text only
			send_mail(emailsubject, emailbody, fromaddr,
				[email], fail_silently=False)
		
		else:
			# text+html
			email = EmailMultiAlternatives(emailsubject, emailbody, fromaddr, [email])
			
			template_name, template_context_vars = action.email_html_template()
			templ = get_template(template_name)
			ctx = Context(template_context_vars)
			ctx["URL"] = r.url()
			html_content = templ.render(ctx)

			email.attach_alternative(html_content, "text/html")
			
			email.send(fail_silently=False)
	
def resend_verifications():
	for rec in Record.objects.filter(retries = 0, hits = 0,
		created__gt = datetime.now() - timedelta(days=EXPIRATION_DAYS),
		created__lt = datetime.now() - timedelta(minutes=20),
		):

		try:
			action = rec.get_action()
		except:
			continue
		
		if not hasattr(action, "email_should_resend"):
			continue
		if not action.email_should_resend():
			continue
			
		print rec.created, rec
			
		send_record_email(rec.email, action, rec)
			
		rec.retries += 1
		rec.save()

