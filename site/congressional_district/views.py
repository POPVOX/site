from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.core.cache import cache

from jquery.ajax import json_response, ajax_fieldupdate_request

import re
from xml.dom import minidom
from urllib import urlopen, quote_plus

@json_response
def district_lookup(request):
	if "zipcode" in request.POST and request.POST["zipcode"].strip() != "":
		try :
			t = minidom.parse(urlopen("http://www.govtrack.us/perl/district-lookup.cgi?zipcode=" + quote_plus(request.POST["zipcode"].strip())))
			states = t.getElementsByTagName('state')
			districts = t.getElementsByTagName('district')
			if len(states) == 1:
				return { "status": "success", "method": "zipcode", "state": states[0].firstChild.data, "district": districts[0].firstChild.data }
		except Exception, e:
			pass
	
	if "address" in request.POST:
		addr = request.POST["address"].strip()
		
		addr = addr.replace("\r", "\n")
		addr = addr.replace("\n\n", "\n")
		
		# Try the API with the address method to get a lat/long.
		try :
			data = urlopen("http://www.govtrack.us/perl/district-lookup.cgi?address=" + quote_plus(addr))
			if data.getcode() != 200:
				return { "status": "fail", "msg": "Sorry I couldn't find your address." }
			t = minidom.parse(data)

			state = t.getElementsByTagName('state')[0].firstChild.data
			district = t.getElementsByTagName('district')[0].firstChild.data
			lat = t.getElementsByTagName('latitude')[0].firstChild.data
			lng = t.getElementsByTagName('longitude')[0].firstChild.data
			
			return { "status": "success", "method": "address", "state": state, "district": district, "lat": lat, "lng": lng }
		except Exception, e:
			print e
			return { "status": "fail", "msg": unicode(e) }
	
	elif "lat" in request.POST and "lng" in request.POST:
		# Try the API by lat/lng.
		t = minidom.parse(urlopen("http://www.govtrack.us/perl/district-lookup.cgi?lat=" + quote_plus(request.POST["lat"]) + "&long=" + quote_plus(request.POST["lng"])))
		states = t.getElementsByTagName('state')
		districts = t.getElementsByTagName('district')
		return { "status": "success", "method": "latlng", "state": states[0].firstChild.data, "district": districts[0].firstChild.data }
		
	else:
		raise Http404()

