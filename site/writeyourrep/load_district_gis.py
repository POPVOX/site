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
	
cursor = connection.cursor()
cursor.execute("DROP TABLE IF EXISTS congressionaldistrictpolygons")
cursor.execute("CREATE TABLE congressionaldistrictpolygons (state VARCHAR(2), district TINYINT, swlong DOUBLE, swlat DOUBLE, nelong DOUBLE, nelat DOUBLE, pointspickle LONGTEXT)")
cursor.execute("CREATE INDEX swlong  ON congressionaldistrictpolygons (swlong)")
cursor.execute("CREATE INDEX nwlong ON congressionaldistrictpolygons (nelong)")

for st in statefips.keys():
	shpRecords = shpUtils.loadShapefile(settings.DATADIR + "gis/tl_2009_%02d_cd111.shp" % st)
	for district in shpRecords["features"]:
		state = statefips[int(district["info"]["STATEFP"])]
		cd = int(district["info"]["CD111FP"])
		if cd in (98, 99):
			cd = 0
		for part in district["shape"]["parts"]:
			print state, cd
			cursor.execute("INSERT INTO congressionaldistrictpolygons VALUES(%s, %s, %s, %s, %s, %s, %s)", [state, cd, part["bounds"][0][0], part["bounds"][0][1], part["bounds"][1][0], part["bounds"][1][1], base64.b64encode(pickle.dumps(part["points"]))])

