from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.core.cache import cache
from django.db import connection

from jquery.ajax import json_response, ajax_fieldupdate_request

import pickle
import base64
from xml.dom import minidom
from urllib import urlopen, quote_plus

@json_response
def district_lookup(request):
	if "zipcode" in request.POST:
		# take only the digits in the zipcode
		zipcode = "".join([ d for d in request.POST["zipcode"] if d.isdigit() ])
		if len(zipcode) in (5, 9):
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
					return { "status": "success", "method": "zipcode", "state": rows[0][0], "district": rows[0][1] }
					
	lat = request.POST.get("lat", None)
	lng = request.POST.get("lng", None)
	fromaddress = False
					
	if "address" in request.POST:
		addr = request.POST["address"].strip()
		
		addr = addr.replace("\r", "\n")
		addr = addr.replace("\n\n", "\n")
		
		# Use the Google API to geocode. Note that we have to display the
		# result on a map to satisfy TOS and it is rate limited to 2,500 per day.
		data = minidom.parse(urlopen("http://maps.googleapis.com/maps/api/geocode/xml?address=" + quote_plus(addr) + "&region=us&sensor=false"))
		if data.getElementsByTagName("status")[0].firstChild.data == "ZERO_RESULTS":
			return { "status": "fail", "msg": "Sorry I couldn't find your congressional district." }
		elif data.getElementsByTagName("status")[0].firstChild.data == "OVER_QUERY_LIMIT":
			return { "status": "fail", "msg": "Sorry, district lookups are unavailable at this time." }
		elif data.getElementsByTagName("status")[0].firstChild.data == "OK":
			r = data.getElementsByTagName("location")
			if len(r) == 1:
				lat = r[0].getElementsByTagName("lat")[0].firstChild.data
				lng = r[0].getElementsByTagName("lng")[0].firstChild.data
				fromaddress = True
			
	if lat != None and lng != None:
		# Find all of the districts whose bounding box contains the point.
		cursor = connection.cursor()
		cursor.execute("SELECT state, district, pointspickle FROM congressionaldistrictpolygons WHERE swlong <= %s and nelong >= %s and swlat <= %s and nelat >= %s", [lng, lng, lat, lat])
		rows = cursor.fetchall()
		
		# If there's just one row, that must be the right district.
		if len(rows) == 1:
			return { "status": "success", "method": "coordinate", "state": rows[0][0], "district": rows[0][1] }
			
		# Otherwise, we need to do a point-in-polygon test for each polygon.
		for row in rows:
			poly = pickle.loads(base64.b64decode(row[2]))
			if point_in_poly(float(lng), float(lat), poly):
				return { "status": "success", "method": "coordinate" if not fromaddress else "address", "state": row[0], "district": row[1] }
		
	return { "status": "fail", "msg": "Sorry I couldn't find your congressional district." }

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

