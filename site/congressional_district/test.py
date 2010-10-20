import os
os.environ["DJANGO_SETTINGS_MODULE"] = "settings"

from congressional_district.views import district_lookup

class Request:
	POST = { }
	
r = Request()

import sys
r.POST[sys.argv[1]] = sys.argv[2]

print district_lookup(r)
