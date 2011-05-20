import urllib, urllib2, json
from math import log, sqrt

from django.db import connection

state_bounds = { }

def http_rest_json(url, args=None, method="GET"):
	if method == "GET" and args != None:
		url += "?" + urllib.urlencode(args).encode("utf8")
	req = urllib2.Request(url)
	r = urllib2.urlopen(req)
	return json.load(r, "utf8")

def get_viewport(address_record):
	bounds = None
	
	# First try Google Geocoding on the zipcode to get an approximate location
	# and a recommended bounding box (which we zoom out a bit).
	try:
		info = http_rest_json(
			"http://maps.googleapis.com/maps/api/geocode/json", {
			"address": address_record.zipcode, #address_string(),
			"region": "us",
			"sensor": "false"
			  })
		info = info["results"][0]["geometry"]
		bounds = info["location"]["lng"], info["location"]["lat"], \
			round(0 - log(sqrt(
					(info["viewport"]["northeast"]["lat"]-info["viewport"]["southwest"]["lat"])
					*(info["viewport"]["northeast"]["lng"]-info["viewport"]["southwest"]["lng"])
				)/24902.0))
		return bounds
	except:
		pass
	
	# If Google Geocoding fails, fall back on a default coordinate and zoom
	# level for the whole state.
	if address_record.state in state_bounds:
		bounds = state_bounds[address_record.state]

	else:
		cursor = connection.cursor()
		cursor.execute("SELECT MIN(X(PointN(ExteriorRing(bbox), 1))), MIN(Y(PointN(ExteriorRing(bbox), 1))), MAX(X(PointN(ExteriorRing(bbox), 3))), MAX(Y(PointN(ExteriorRing(bbox), 3))), SUM(Area(bbox)) FROM congressionaldistrictpolygons WHERE state=%s", [address_record.state])
		rows = cursor.fetchall()
		
		sw_lng, sw_lat, ne_lng, ne_lat, area = rows[0]

		bounds = (sw_lng+ne_lng)/2.0, (sw_lat+ne_lat)/2.0, round(1.0 - log(sqrt(area)/1000.0))
		state_bounds[address_record.state] = bounds

	return bounds

