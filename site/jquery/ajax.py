from django.http import HttpResponse, HttpResponseServerError
from django.utils import simplejson
from django import forms

import sys
import hashlib

from BeautifulSoup import BeautifulSoup, Comment

from settings import DEBUG

# Utility functions.

def validation_error_message(validationerror):
	# Turns a ValidationException or a ValueError, KeyError into a string.
	if not hasattr(validationerror, "messages"):
		return unicode(validationerror)

	from django.utils.encoding import force_unicode
	#m = e.messages.as_text()
	m = u'; '.join([force_unicode(g) for g in validationerror.messages])
	if m.strip() == "":
		m = "Invalid value."
	return m
	
def sanitize_html(value):
	"""Sanitizes HTML."""
	valid_tags = 'p i em strong b u a h1 h2 h3 pre br ul ol li blockquote'.split()
	valid_attrs = 'href'.split()
	soup = BeautifulSoup(value)
	for comment in soup.findAll(
		text=lambda text: isinstance(text, Comment)):
		comment.extract()
	for tag in soup.findAll(True):
		if tag.name not in valid_tags:
			tag.hidden = True
		tag.attrs = [(attr, val) for attr, val in tag.attrs
			if attr in valid_attrs]
	return soup.renderContents().decode('utf8').replace('javascript:', '')

# These decorators wrap view functions used to process AJAX JSON
# requests.

def json_response(f):
	"""Turns dict output into a JSON response."""
	def g(*args, **kwargs):
		try:
			ret = f(*args, **kwargs)
			if isinstance(ret, HttpResponse):
				return ret
			return HttpResponse(simplejson.dumps(ret), mimetype="application/json")
		except ValueError, e:
			sys.stderr.write(unicode(e) + "\n")
			return HttpResponse(simplejson.dumps({ "status": "fail", "msg": unicode(e) }), mimetype="application/json")
		except forms.ValidationError, e :
			m = validation_error_message(e)
			sys.stderr.write(unicode(m) + "\n")
			return HttpResponse(simplejson.dumps({ "status": "fail", "msg": m, "field": getattr(e, "source_field", None) }), mimetype="application/json")
		except Exception, e:
			if DEBUG:
				print e
			else:
				sys.stderr.write(unicode(e) + "\n")
			return HttpResponseServerError(simplejson.dumps({ "status": "generic-failure", "msg": unicode(e) }), mimetype="application/json")
	return g
	
def ajax_fieldupdate_request(f):
	"""Simplifies AJAX request views to update a single field."""
	def g(request):
		if request.POST == None or "name" not in request.POST or "value" not in request.POST or not request.user.is_authenticated():
			raise ValueError("Bad call: Missing required field. " + repr(request.POST))
			
		return f(request, request.POST["name"], request.POST["value"].strip(), "validate" in request.POST and request.POST["validate"] == "validate")
	return g

def ajaxmultifieldupdate(globalargs=[]):
	"""Simplifies AJAX calls to update multiple fields at once with JSON return values."""
	def h(f):
		def g(request):
			# Call the underlying function f(globalargs, name, value, validate) once for each
			# parameter, except parameters listed in globalargs which get passed through
			# to f.
			status = { "status": "fail", "byfield": { } }
			for p in request.POST:
				if p in globalargs or p == "validate":
					continue
				try:
					ret = f(request, p, request.POST[p].strip(), "validate" in request.POST and request.POST["validate"] == "validate")
					if isinstance(ret, HttpResponse):
						return ret # debugging?
					if ret["status"] != "success":
						raise ValueError(ret["msg"])
					for key in ret:
						if key != "status" and key != "value":
							status[key] = ret[key]
				except ValueError, e:
					status["byfield"][p] = unicode(e)
				except forms.ValidationError, e :
					status["byfield"][p] = validation_error_message(e)
				except Exception, e:
					if DEBUG:
						print e
					status["status"] = "generic-failure"
					status["byfield"][p] = unicode(e)
			
			if len(status["byfield"]) == 0:
				status["status"] = "success"
			
			return HttpResponse(simplejson.dumps(status), mimetype="application/json")
		return g
	return h

