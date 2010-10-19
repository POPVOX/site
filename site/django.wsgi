#!/usr/bin/python
import sys, os, os.path

os.chdir(os.path.dirname(__file__))
sys.path.insert(0, ".")

os.environ['DJANGO_SETTINGS_MODULE'] = "settings"

#os.environ["SITE_DOWN"] = "1"

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()
