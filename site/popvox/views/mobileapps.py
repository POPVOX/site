from django.http import HttpResponse
from django.template import Context, loader

def ipad_billreader_welcome(request):
	return HttpResponse("Welcome!")


