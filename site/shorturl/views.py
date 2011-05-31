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
		raise Http404("'%s' (type %s) doesn't have a get_absolute_url() method." % (str(rec.target), str(type(rec.target))))
		
	rec.increment_hits()
	if hasattr(request, "session"):
		request.session["shorturl"] = rec
		request.just_added_shorturl = True
	
	return HttpResponsePermanentRedirect(url)

