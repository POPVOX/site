from django.http import HttpResponse, HttpResponseServerError
from django.template import Context, loader
from django.conf import settings
from django.core.cache import cache

import sys, json, csv, urllib, urlparse

from registration.models import AuthRecord

from tagfriends.models import Photo, Tag

def get_network(networkname):
	if networkname == "facebook":
		return 1
	else:
		return 0

def ajaxreq(request):
	try:
		if request.GET.get("cmd", "") == "getfriends":
			if not request.user.is_authenticated(): raise Exception("Not logged in.")
			ret = []
			for ar in AuthRecord.objects.filter(user=request.user):
				if ar.provider == "facebook":
					fb_tok = get_facebook_app_access_token()
					fbret = urllib.urlopen("https://graph.facebook.com/" + ar.uid + "/friends?" + \
						urllib.urlencode({
							"offset": 0,
							"limit": 1000,
							"access_token": fb_tok
						}))
					if fbret.getcode() != 200: raise Exception("Failed to load Facebook friends.")
					for friend in json.loads(fbret.read())["data"]:
						ret.append( ("facebook", friend["id"], friend["name"]) )
		
		elif request.GET.get("cmd", "") == "load":
			ph = Photo.objects.get(id=request.GET.get("photo", "0"))
			ret = [
				((t.coord_x, t.coord_y),
				t.get_network_display(),
				t.uid,
				t.name,
				t.owner == request.user)
				for t in Tag.objects.filter(photo=ph)
			]
		
		elif request.GET.get("cmd", "") in ("save", "delete"):
			if not request.user.is_authenticated(): raise Exception("Not logged in.")

			ph = Photo.objects.get(id=request.GET.get("photo", "0"))
			
			# clear existing tags that this tag should overwrite
			if get_network(request.GET.get("network", "")) != 0:
				Tag.objects.filter(photo=ph, owner=request.user, network=get_network(request.GET.get("network", "")), uid=request.GET.get("uid", "")).delete()
			else:
				Tag.objects.filter(photo=ph, owner=request.user, network=0, name=request.GET.get("name", "")).delete()
			
			if request.GET.get("cmd", "") == "save":
				# add tag
				t = Tag()
				t.photo = ph
				t.owner = request.user
				t.coord_x = float(request.GET.get("x", "0"))
				t.coord_y = float(request.GET.get("y", "0"))
				t.network = get_network(request.GET.get("network", ""))
				t.uid = request.GET["uid"] if request.GET.get("uid", "") != "" else None
				t.name = request.GET.get("name", "")
				t.save()
			
			ret = "OK"
		else:
			raise Exception("Invalid Call!")
		return HttpResponse(json.dumps(ret), mimetype="application/json")
	except Exception, e:
		return HttpResponseServerError(json.dumps({ "status": "generic-failure", "msg": unicode(e) }), mimetype="application/json")

def get_facebook_app_access_token():
	key = "tagfriends_facebook_app_access_token"
	token = cache.get(key)
	if token: return token
	
	url = "https://graph.facebook.com/oauth/access_token?" \
		+ urllib.urlencode({
			"client_id": settings.FACEBOOK_APP_ID,
			"client_secret": settings.FACEBOOK_APP_SECRET,
			"grant_type": "client_credentials"
		})
	
	ret = urllib.urlopen(url)
	if ret.getcode() != 200:
		raise Exception("Failed to get a Facebook App access_token: " + ret.read())
	
	ret = dict(urlparse.parse_qsl(ret.read()))

	token = ret["access_token"]
	if "expires" in ret:
		expires = int(ret["expires"])
	else:
		expires = 60*60*4 # four hours
	
	cache.set(key, token, expires/2)
	
	return token


