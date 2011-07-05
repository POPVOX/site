from django.core.mail import send_mail, EmailMultiAlternatives
from django.template import Context, Template
from django.template.loader import get_template

from models import *

import settings

def send_email_verification(email, searchkey, action, send_email=True):
	r = Record()
	r.email = email
	r.set_code()
	r.searchkey = searchkey
	r.set_action(action)
	
	if send_email:
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
	
	r.save()

	return r
