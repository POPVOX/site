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
		return_url = r.url()
		kill_url = r.killurl()
	
		emailsubject = action.email_subject()
		
		if hasattr(action, "email_body"):
			emailbody = action.email_body()
			emailbody = emailbody.replace("<URL>", return_url)
			emailbody = emailbody.replace("<KILL_URL>", kill_url)
		elif hasattr(action, "email_text_template"):
			template_name, template_context_vars = action.email_text_template()
			templ = get_template(template_name)
			ctx = Context(template_context_vars)
			ctx["URL"] = return_url
			ctx["KILL_URL"] = kill_url
			emailbody = templ.render(ctx)
		elif hasattr(action, "email_templates"):
			template_name, template_context_vars = action.email_templates()
			templ = get_template(template_name + ".txt")
			ctx = Context(template_context_vars)
			ctx["URL"] = return_url
			ctx["KILL_URL"] = kill_url
			ctx["subject"] = emailsubject
			emailbody = templ.render(ctx)
		else:
			raise ValueError("Action object is missing email_body and email_text_template. You must implement one.")
		
		fromaddr = getattr(settings, 'EMAILVERIFICATION_FROMADDR',
				getattr(settings, 'SERVER_EMAIL', 'no.reply@example.com'))
		if hasattr(action, "email_from_address"):
			fromaddr = action.email_from_address()
			
		if not hasattr(action, "email_html_template") and not hasattr(action, "email_templates"):
			# text only
			send_mail(emailsubject, emailbody, fromaddr,
				[email], fail_silently=False)
		
		else:
			# text+html
			email = EmailMultiAlternatives(emailsubject, emailbody, fromaddr, [email])
			
			if hasattr(action, "email_html_template"):
				template_name, template_context_vars = action.email_html_template()
				templ = get_template(template_name)
				ctx = Context(template_context_vars)
				ctx["URL"] = return_url
				ctx["KILL_URL"] = kill_url
				ctx["subject"] = emailsubject
				html_content = templ.render(ctx)
			else:
				# template_name, ctx are already initialized above
				templ = get_template(template_name + ".html")
				html_content = templ.render(ctx)

			# Email clients are horribly bad at interpreting CSS and vary in how
			# they do so. Some clients like Gmail don't interpret <style> nodes
			# and that CSS should be repeated inline on each element. That is
			# very annoying to encode in a template, so we'll take care of that
			# here by parsing <style> nodes (except <style inline="false">) and
			# applying those CSS rules inline to all matching elements. Only a
			# small amount of CSS selectors are supported.
			#
			# This requires that cssutils be installed.
			#
			# The HTML body must be well-formed XML. If it is not, an exception
			# will be raised, caught, and ignored. Check your templates!
			try:
				import movecssinline
				html_content = movecssinline.apply_css(html_content)
			except:
				pass
			
			email.attach_alternative(html_content, "text/html")
			
			email.send(fail_silently=False)
	
def resend_verifications(test=True):
	# Build up a union of queries, one for each number of retries made so
	# far, starting with zero. Each level has a different delay time since the
	# last send.
	search = None
	for retries in xrange(len(RETRY_DELAYS)):
		q = Record.objects.filter(
			retries = retries,
			hits = 0,
			killed = False,
			created__gt = datetime.now() - timedelta(days=EXPIRATION_DAYS),
			last_send__lt = datetime.now() - RETRY_DELAYS[retries]
			)
		if search == None:
			search = q
		else:
			search |= q

	for rec in search:

		try:
			action = rec.get_action()
		except:
			continue
		
		if not hasattr(action, "email_should_resend"):
			continue
		if not action.email_should_resend():
			continue
			
		if test:
			print rec.retries, rec.created, rec.last_send, rec
			continue
		
		try:
			send_record_email(rec.email, action, rec)
		except Exception as e:
			print rec.retries, rec.created, rec.last_send, rec
			
			if str(type(e)) == "<class 'boto.exception.BotoServerError'>":
				if e.error_message == "Address blacklisted.":
					# for our purposes, mark as retry sent and automatically killed
					rec.retries += 1
					rec.last_send = datetime.now()
					rec.killed = True
					rec.save()
					print "\tfailed: AWS SES gives address blacklisted"
				else:
					print "\tfailed: AWS SES gives:", e.status, e.reason, e.error_code, e.error_message
			else:
				print "\tfailed:", e
			continue # don't mark as mail successfully sent
			
		rec.retries += 1
		rec.last_send = datetime.now()
		rec.save()

def clear_expired():
	return Record.objects.filter(created__lt = datetime.now() - timedelta(days=EXPIRATION_DAYS)).delete()
