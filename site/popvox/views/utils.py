from django.core.cache import cache
from django.db import connection
from django.views.decorators.csrf import csrf_protect

import urllib
from datetime import datetime, timedelta, time

def formatDateTime(d, withtime=True, tz="EST"):
	if d.time() == time.min:
		# midnight usually means we have no time info
		withtime = False

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
		
def cache_page_postkeyed(duration, vary_by_user=False):
	def f(func):
		def g(request, *args, **kwargs):
			if vary_by_user and request.user.is_authenticated():
				return func(request, *args, **kwargs)

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


def require_lock(*tables):
	def _lock(func):
		def _do_lock(*args, **kwargs):
			cursor = connection.cursor()
			cursor.execute("LOCK TABLES %s" %', '.join([t + " WRITE" for t in tables]))
			try:
				return func(*args, **kwargs)
			finally:
				cursor.execute("UNLOCK TABLES")
				cursor.close()
		return _do_lock
	return _lock
	
def csrf_protect_if_logged_in(f):
	f_protected = csrf_protect(f)
	
	def g(request, *args, **kwargs):
		if request.user.is_authenticated():
			return f_protected(request, *args, **kwargs)
		else:
			return f(request, *args, **kwargs)
			
	return g

