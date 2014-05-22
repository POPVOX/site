import sys
sys.path.insert(0, ".")

import os
os.environ["DJANGO_SETTINGS_MODULE"] = "settings"

from writeyourrep.district_lookup import district_lookup

class Request:
	POST = { }
	
r = Request()

r.POST[sys.argv[1]] = sys.argv[2]

print district_lookup(r)
