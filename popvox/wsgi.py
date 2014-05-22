import os
#!/usr/bin/env python
# -*- coding: utf-8 -*- 
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "popvox.settings")
# This application object is used by the development server
# as well as any WSGI server configured to use this file.
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

