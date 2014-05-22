from django.http import HttpResponse
from django.template import Context, loader

def csrf_failure_view(request, reason=""):
	if reason in ("No CSRF or session cookie.", "CSRF cookie not set."):
		t = loader.get_template('500.html')
		c = Context({"error": "You must have cookies enabled to access this part of the website."})
		return HttpResponse(t.render(c), status=403)
	else:
		# Send the user an oops and notify us.
		raise Exception("CSRF Failure: " + reason)

