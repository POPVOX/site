from django.http import HttpResponsePermanentRedirect, Http404
from django.template import RequestContext

from models import *

def redirect(request, code):
	try:
		rec = Record.objects.get(code=code)
	except:
		raise Http404("The short URL is not valid.")

	try:
		url = rec.target.get_absolute_url()
	except AttributeError:
		raise Http404("'%s' doesn't have a get_absolute_url() method." % str(rec.target))
		
	rec.increment_hits()
	request.session["shorturl"] = rec
		
	return HttpResponsePermanentRedirect(url)

