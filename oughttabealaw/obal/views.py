from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.core.context_processors import csrf

from obal.models import *

from emailverification.utils import send_email_verification

import random

def main(request):
	# choose a submission at random
	lawcount = Law.objects.filter(status=Law.APPROVED).count()
	if lawcount == 0:
		law = Law()
		law.text = "(empty database)"
		law.author = "(empty database)"
	else:
		law = Law.objects.filter(status=Law.APPROVED)[random.randint(0, lawcount-1)]
	
	# render
	return render_to_response('index.html', {'law': law})

def post(request):
	#if "text" not in request.POST:
	#	return HttpResponse("ERROR", mimetype="text/plain")
	
	law = Law()
	law.text = request.REQUEST["text"]
	law.author = request.REQUEST["author"]
	law.save()
	
	for tag in request.REQUEST["tags"].split():
		law.tags.add(Tag.objects.get_or_create(text=tag.lower())[0])
	law.save()
	
	axn = ApprovalAction()
	axn.id = law.id
	
	send_email_verification("josh@popvox.com", None, axn)
	
	return HttpResponse("OK", mimetype="text/plain")
	

def approve(request):
	if not "authenticated" in request.session:
		return HttpResponse("not authenticated", mimetype="text/plain")
	if not "id" in request.POST:
		return HttpResponse("missing id parameter", mimetype="text/plain")
	
	law = Law.objects.get(id=int(request.POST["id"]))
	if request.POST["action"] == "Approve":
		law.status = Law.APPROVED
	if request.POST["action"] == "Reject":
		law.status = Law.REJECTED
	law.save()
	
	return HttpResponse("OK", mimetype="text/plain")

class ApprovalAction:
	id = None
	
	def email_subject(self):
		return "Oughttabealaw Submission Needs Approval"
	
	def email_body(self):
		return """<URL>"""
	
	def get_response(self, request, vrec):
		request.session["authenticated"] = True
		law = Law.objects.get(id=self.id)
		c = {'law': law}
		c.update(csrf(request))
		return render_to_response('approve.html', c)

