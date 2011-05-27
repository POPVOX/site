import traceback
import urllib, urllib2, json

def printexceptions(f):
	def g(*args, **kwargs):
		try:
			return f(*args, **kwargs)
		except Exception as e:
			traceback.print_exc()
			raise
	return g
	
def http_rest_json(url, args=None, method="GET"):
	if method == "GET" and args != None:
		url += "?" + urllib.urlencode(args).encode("utf8")
	req = urllib2.Request(url)
	r = urllib2.urlopen(req)
	return json.load(r, "utf8")
	

