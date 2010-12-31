# DEBUG=1 PYTHONPATH=. DJANGO_SETTINGS_MODULE=settings python adserver/test.py std180x150

import sys

from adserver.models import Format
from adserver.adselection import select_banner

print select_banner(Format.objects.get(key=sys.argv[1]), None)

