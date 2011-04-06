from datetime import datetime, timedelta
from django.core.cache import cache

import urllib

def formatDateTime(d, withtime=True, tz="EST"):
	if (datetime.now().date() == d.date()):
		if withtime:
			return "Today at" + d.strftime(" %I:%M%p").replace(" 0", " ").lower() #+ " " + tz
		else:
			return "Today"
	elif ((datetime.now() - timedelta(.5)).date() == d.date()):
		if withtime:
			return "Yesterday at" + d.strftime(" %I:%M%p").replace(" 0", " ").lower() #+ " " + tz
		else:
			return "Yesterday"
	elif (datetime.now() - d).days < 7:
		if withtime:
			return d.strftime("%a") + " at" + d.strftime(" %I:%M%p").replace(" 0", " ").lower() #+ " " + tz
		else:
			return d.strftime("%A")
	elif (datetime.now() - d).days < 120:
		return d.strftime("%B %d").replace(" 0", " ")
	else:
		return d.strftime("%b %d, %Y").replace(" 0", " ")
		
def cache_page_postkeyed(duration):
	def f(func):
		def g(request, *args, **kwargs):
			key = "cache_page_postkeyed::" + request.path + "?"
			
			reqkeys = list(request.REQUEST.keys())
			reqkeys.sort()
			for k in reqkeys:
				key += "&" + urllib.quote(k) + "=" + urllib.quote(request.REQUEST[k])
			
			ret = cache.get(key)
			if ret == None:
				ret = func(request, *args, **kwargs)
				cache.set(key, ret, duration)
			
			return ret
		return g
	return f

