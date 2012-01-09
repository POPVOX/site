#!runscript

import sys
sys.path.append('../libs/primary-maps-2008')

import pickle
import base64

from django.db import connection

import shpUtils

import settings

statefips = {
	1: "AL", 2: "AK", 4: "AZ", 5: "AR", 6: "CA", 8: "CO", 9: "CT",
	10: "DE", 11: "DC", 12: "FL", 13: "GA", 15: "HI", 16: "ID", 17: "IL",
	18: "IN", 19: "IA", 20: "KS", 21: "KY", 22: "LA", 23: "ME", 24: "MD",
	25: "MA", 26: "MI", 27: "MN", 28: "MS", 29: "MO", 30: "MT", 31: "NE",
	32: "NV", 33: "NH", 34: "NJ", 35: "NM", 36: "NY", 37: "NC", 38: "ND",
	39: "OH", 40: "OK", 41: "OR", 42: "PA", 44: "RI", 45: "SC", 46: "SD",
	47: "TN", 48: "TX", 49: "UT", 50: "VT", 51: "VA", 53: "WA", 54: "WV",
	55: "WI", 56: "WY", 60: "AS", 66: "GU", 69: "MP", 72: "PR", 78: "VI"
	}

for layer, censusfile in (("congressionaldistrict", "cd112"), ("county", "county"),): 
	got_state = set()
		
	cursor = connection.cursor()
	try:
		cursor.execute("DROP TABLE IF EXISTS %spolygons_" % layer)
	except:
		# even though it has IF EXISTS, a warning is being generated that busts everything
		pass
	cursor.execute("CREATE TABLE %spolygons_ (state VARCHAR(2), district TINYINT, name VARCHAR(32), bbox POLYGON NOT NULL, pointspickle LONGTEXT)" % layer)
	cursor.execute("CREATE SPATIAL INDEX bbox_index ON %spolygons_ (bbox)" % layer)
	
	for shpf in ('us',): # previously 'us' file didn't include island areas: '60', '66', '69', '78'
		shpRecords = shpUtils.loadShapefile("/mnt/persistent/gis/tl_2011_%s_%s.shp" % (shpf, censusfile))
		for district in shpRecords["features"]:
			state = statefips[int(district["info"]["STATEFP"])]
			if layer == "congressionaldistrict":
				cd = int(district["info"]["CD111FP"])
				if cd in (98, 99):
					cd = 0
				name = None
			else:
				cd = None
				name = district["info"]["NAME"].decode("latin1")
				
			for part in district["shape"]["parts"]:
				print shpf, state, cd, name, part["bounds"]
				got_state.add(state)
				cursor.execute("INSERT INTO " + layer + "polygons_ VALUES(%s, %s, %s, GeomFromText('POLYGON((%s %s, %s %s, %s %s, %s %s, %s %s))'), %s)",
					[state, cd, name,
						# the point order matters for district_metadata: 1: southwest 2: ... 3: northeast 4: ...
					 part["bounds"][0][0], part["bounds"][0][1],
					 part["bounds"][1][0], part["bounds"][0][1],
					 part["bounds"][1][0], part["bounds"][1][1],
					 part["bounds"][0][0], part["bounds"][1][1],
					 part["bounds"][0][0], part["bounds"][0][1],
					 base64.b64encode(pickle.dumps(part["points"]))])
	
	for state in statefips.values():
		if not state in got_state:
			print "No data for", state, "!"
	
	try:
		cursor.execute("DROP TABLE IF EXISTS %spolygons" % layer)
	except:
		# again, a warning is causing problems even though we have IF NOT EXISTS
		pass
	cursor.execute("RENAME TABLE %spolygons_ TO %spolygons" % (layer, layer))

