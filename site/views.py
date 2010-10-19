from django.http import HttpResponse
from django.template import Context, loader

def sitedown(request):
	t = loader.get_template('503.html')
	c = Context({})
	return HttpResponse(t.render(c), status=503)
