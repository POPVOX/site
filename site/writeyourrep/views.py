from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.contrib.auth.decorators import login_required
from django.utils import simplejson

from jquery.ajax import json_response

from models import SynonymRequired
from popvox.models import Bill

@json_response
def synreq(request):
	seen = { }
	
	ret = []
	for sr in SynonymRequired.objects.all():
		termtype = "crs"
		term = sr.term1set.strip().split("\n")[0]
		
		if term[0] == "#":
			termtype = "bill"
		
		if termtype != request.GET.get("type", ""):
			continue
		
		if termtype == "bill":
			bill = Bill.from_hashtag(term)
			term = bill.title
			ot = bill.officialtitle()
			if ot != None:
				term += "\n\n" + ot

		choices = "|".join([
			t.replace('|', '&#124;').replace('\\', '\\\\').replace('"', '\\"')
			for t in sr.term2set.strip().split("\n")
			])

		seenkey = term + "||" + choices
		if seenkey in seen:
			continue
			seen[seen] = True

		ret.append({
				"term": term,
				"options": choices
		})
	
	return ret

