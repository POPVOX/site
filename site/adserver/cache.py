from django.core.cache.backends.locmem import CacheClass as LocMemCache
from django.core.cache.backends.dummy import CacheClass as DummyCache

from settings import DEBUG

def create():
	if not DEBUG or True:
		return LocMemCache(None, {})
	else:
		return DummyCache({})

cache = create()

def get(ns, key, value):
	global cache
	key = str(ns) + str(key)
	ret = cache.get(key)
	if ret == None:
		ret = value(key)
		cache.set(key, ret, 60*5) # five minutes
	return ret

def req_get(request, ns, key, value):
	if not hasattr(request, "request_cache"):
		request.request_cache = create()
	
	key = str(ns) + str(key)
	ret = request.request_cache.get(key)
	if ret == None:
		ret = value(key)
		request.request_cache.set(key, ret) # duration won't matter
	return ret


