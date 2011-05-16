#!/usr/bin/python
import sys, os, os.path

os.chdir(os.path.dirname(__file__))
sys.path.insert(0, ".")

os.environ['DJANGO_SETTINGS_MODULE'] = "settings"

if os.path.exists("/home/www/slave"):
	for line in open("/home/www/slave"):
		name, val = line.strip().split("=")
		os.environ[name] = val

#os.environ["SITE_DOWN"] = "1"

import django.core.handlers.wsgi
_application = django.core.handlers.wsgi.WSGIHandler()
def application(environ, start_response):
	os.environ['HTTPS'] = 'on'
	return _application(environ, start_response)

