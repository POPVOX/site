#!/usr/bin/python
import sys, os, os.path

os.environ['ADMIN_SITE'] = "1"

os.chdir(os.path.dirname(__file__) + "/..")
sys.path.insert(0, ".")

os.environ['DJANGO_SETTINGS_MODULE'] = "settings"

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()
