from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.core.cache import cache
from django.db import connection

from jquery.ajax import json_response, ajax_fieldupdate_request

import cPickle
import base64
from xml.dom import minidom
from urllib import urlopen, urlencode, quote_plus

import settings

@json_response
def district_lookup(request):
	simulate_response = getattr(settings, "DISTRICT_LOOKUP_SIMULATE_RESPONSE", None)
	if simulate_response != None:
		return simulate_response
	
	# If DISTRICT_LOOKUP_API is set, then pass off this request to
	# the API at the given endpoint. The API is expected to be
	# implemented by this module, so it takes the same arguments.
	remoteapi = getattr(settings, "DISTRICT_LOOKUP_API", None)
	if remoteapi != None:
		import simplejson
		return simplejson.loads(urlopen(remoteapi, urlencode(request.REQUEST)).read())
	
	if "zipcode" in request.REQUEST:
		# take only the digits in the zipcode
		zipcode = "".join([ d for d in request.REQUEST["zipcode"] if d.isdigit() ])
		if len(zipcode) in (5, 9):
			ret = district_lookup_zipcode(zipcode)
			if ret != None:
				return { "status": "success", "method": "zipcode", "state": ret[0], "district": ret[1] }

	if "address" in request.REQUEST:
		addr = request.REQUEST["address"].strip()
		
		addr = addr.replace("\r", "\n")
		addr = addr.replace("\n\n", "\n")
		
		ret = district_lookup_address(addr)
		if ret != None:
			return { "status": "success", "method": "address", "state": ret[2], "district": ret[3], "latitude": ret[0], "longitude": ret[1] }
		
	lat = request.REQUEST.get("lat", None)
	lng = request.REQUEST.get("lng", None)
	if lat != None and lng != None:
		ret = district_lookup_coordinate(lng, lat)
		if ret != None:
			return { "status": "success", "method": "coordinate", "state": ret[0], "district": ret[1] }

	return { "status": "fail", "msg": "District lookup failed." }

def district_lookup_zipcode(zipcode):
	cursor = connection.cursor()
			
	# Get the first record that is lexicographically equal to or preceding
	# the supplied zipcode.
	cursor.execute("SELECT state, district, zip9 FROM zipcodes WHERE zip9 <= %s ORDER BY zip9 DESC LIMIT 1", [zipcode])
	rows = cursor.fetchall()
			
	if len(rows) == 1:
		# If the resulting row matches the zipcode exactly, then we have an exact
		# match record, but that's rare since most zipcodes aren't actually
		# in the database.
		#	
		# If the resulting row is not an exact match, then this zipcode is not
		# in the database. Either a more precise ZIP+9 prefix is in the database
		# (if zipcode is 5-digit) or a less precise ZIP+9 prefix is in the database.
		# If a more precise ZIP code is in the database, then the ZIP code spans
		# multiple districts and we are free to return a not-found. If a less precise
		# ZIP code is in the database then it is going to be the lexicographically
		# preceding one.
		if rows[0][2] == zipcode[0:len(rows[0][2])]:
			return rows[0][0], rows[0][1]

	return None

def district_lookup_address(addr):
	# Use the Google API to geocode. Note that we have to display the
	# result on a map to satisfy TOS and it is rate limited to 2,500 per day.
	data = minidom.parse(urlopen("http://maps.googleapis.com/maps/api/geocode/xml?address=" + quote_plus(addr.encode('utf-8')) + "&region=us&sensor=false"))
	if data.getElementsByTagName("status")[0].firstChild.data == "ZERO_RESULTS":
		return None #{ "status": "fail", "msg": "Sorry I couldn't find your congressional district." }
	elif data.getElementsByTagName("status")[0].firstChild.data == "OVER_QUERY_LIMIT":
		return None #{ "status": "fail", "msg": "Sorry, district lookups are unavailable at this time." }
	elif data.getElementsByTagName("status")[0].firstChild.data == "OK":
		r = data.getElementsByTagName("location")
		if len(r) == 1:
			lat = r[0].getElementsByTagName("lat")[0].firstChild.data
			lng = r[0].getElementsByTagName("lng")[0].firstChild.data
			ret = district_lookup_coordinate(lng, lat)
			if ret == None:
				return None
			return lat, lng, ret[0], ret[1]
	return None

def district_lookup_coordinate(lng, lat):
	# Find all of the districts whose bounding box contains the point.
	cursor = connection.cursor()
	cursor.execute("SELECT state, district FROM congressionaldistrictpolygons WHERE MBRContains(bbox, GeomFromText('Point(%s %s)'))", [float(lng), float(lat)])
	rows = cursor.fetchall()

	# If there's just one distinct state/district pair, that must be the right district. There
	# can be multiple polygons for the same district.
	rets = set((row[0], row[1]) for row in rows)
	if len(rets) == 1:
		return rows[0]
			
	# Otherwise, we need to do a point-in-polygon test for each polygon.
	# Most times the point will be in a unique bounding box and we won't get this far, so we delay pulling the polygon itself until this point.
	cursor.execute("SELECT state, district, pointspickle FROM congressionaldistrictpolygons WHERE MBRContains(bbox, GeomFromText('Point(%s %s)'))", [float(lng), float(lat)])
	rows = cursor.fetchall()
	for row in rows:
		poly = cPickle.loads(base64.b64decode(row[2]))
		if point_in_poly(float(lng), float(lat), poly):
			return row[0], row[1]

	return None

def point_in_poly(x, y, poly):
    # ray casting method
    n = len(poly)
    inside = False
    p1x, p1y = poly[0]
    for i in xrange(n+1):
        p2x, p2y = poly[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def get_state_for_zipcode(zipcode):
	if zipcode == None:
		return None
		
	zipcode = "".join([ d for d in zipcode if d.isdigit() ])
	if len(zipcode) not in (5, 9):
		return None
		
	cursor = connection.cursor()
	
	# Get the first record that is lexicographically equal to or preceding the supplied zipcode
	# which is a prefix of the zipcode.
	cursor.execute("SELECT state, district, zip9 FROM zipcodes WHERE zip9 <= %s ORDER BY zip9 DESC LIMIT 1", [zipcode])
	rows = cursor.fetchall()
	if len(rows) == 1 and rows[0][2] == zipcode[0:len(rows[0][2])]:
		return rows[0][0]

	# This zipcode is split between districts, or doesn't occur in the database. But since zipcodes don't
	# span states, we can return the state of the first zipcode entry that this zipcode is a prefix of.
	# Get the first record that is lexicographically after the supplied zipcode which this
	# zipcode is a prefix of.
	cursor.execute("SELECT state, district, zip9 FROM zipcodes WHERE zip9 > %s ORDER BY zip9  LIMIT 1", [zipcode])
	rows = cursor.fetchall()
	if len(rows) == 1 and rows[0][2][0:len(zipcode)] == zipcode:
		return rows[0][0]

	return None

def get_zip_plus_four(zip5, state, district):
	# Returns the first zip+4 that matches the zipcode, state, and district.
	# This is used when we have a ZIP+5 and a district and want to make up
	# a complete ZIP+4 to get a message through a webform.
	
	zipcode = "".join([ d for d in zip5 if d.isdigit() ])
	if len(zipcode) != 5:
		raise ValueError("expects 5-digit zip code")
		
	cursor = connection.cursor()
	
	cursor.execute("SELECT zip9 FROM zipcodes WHERE zip9 LIKE %s AND state=%s AND district=%s and LENGTH(zip9)=9 LIMIT 1", [zipcode+"%", state, district])
	rows = cursor.fetchall()
	if len(rows) == 0:
		return None
		
	zip9 = rows[0][0]
	return zip9[0:5] + "-" + zip9[5:9]

