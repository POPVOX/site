#!runscript

import urllib2
import json

last_response = None

class AddressVerificationError(ValueError):
	pass

def verify_adddress(address):
	global last_response

	# import here so we can set env variables in the __main__ code
	from settings import CDYNE_LICENSE_KEY
	from popvox.govtrack import stateapportionment

	if address.state.lower() != "ak" and "pobox" in address.address1.replace(" ", "").lower():
		raise AddressVerificationError("Please enter the address of your residence so that we can determine your Congressional district. We cannot find your district based on a PO Box.")

	
	req = urllib2.Request("http://pav3.cdyne.com/PavService.svc/VerifyAddressAdvanced",
		json.dumps(
		{
			"LicenseKey": CDYNE_LICENSE_KEY,
			#"FirmOrRecipient": ,
			"PrimaryAddressLine": address.address1,
			"SecondaryAddressLine": address.address2,
			"CityName": address.city,
			"State": address.state,
			"ZipCode": address.zipcode,
			"ReturnGeoLocation": True,
			"ReturnLegislativeInfo": True,
			"ReturnResidentialIndicator": True,
		}),
		{
			"Content-Type": "application/json",
			"Accept": "application/json",
		})
	
	try:
		ret = json.loads(urllib2.urlopen(req).read())
	except Exception, e:
		raise AddressVerificationError("Address verification is not working at the moment.")
	
	last_response = ret
	
	if ret["ReturnCode"] not in (100, 101, 102, 103):
		raise AddressVerificationError("We couldn't determine the Congressional district at that address. Make sure you haven't abbreviated the name of your street or city.")
	
	address.cdyne_return_code = ret["ReturnCode"]

	if ret["ResidentialDeliveryIndicator"] == "N":
		#raise AddressVerificationError("This address is believed to be a commercial delivery address. Use a residental address.")
		address.cdyne_return_code = 900 # for us
	
	# Correct fields...
	def nrml(x):
		return x.lower().replace(".", "").replace("#", "")
	for a, b in [('address1', 'PrimaryDeliveryLine'), ('address2', 'SecondaryDeliveryLine'), ('city', 'PreferredCityName'), ('state', 'StateAbbreviation'), ('zipcode', 'ZipCode'), ('county', 'County')]:
		if hasattr(address, a) and nrml(getattr(address, a)) != nrml(ret[b]):
			setattr(address, a, ret[b])
	
	if ret["LegislativeInfo"]["CongressionalDistrictNumber"] == "AL": # hmm
		address.congressionaldistrict = 0
	elif stateapportionment[address.state] == 1: # at-large comes back as 98, etc.
		address.congressionaldistrict = 0
	else:
		address.congressionaldistrict = int(ret["LegislativeInfo"]["CongressionalDistrictNumber"])
	address.state_legis_upper = ret["LegislativeInfo"]["StateLegislativeUpper"]
	address.state_legis_lower = ret["LegislativeInfo"]["StateLegislativeLower"]
	address.latitude = float(ret["GeoLocationInfo"]["AvgLatitude"])
	address.longitude = float(ret["GeoLocationInfo"]["AvgLongitude"])
	address.timezone = ret["GeoLocationInfo"]["TimeZone"]


if __name__ == "__main__":
	from popvox.models import PostalAddress
	address = PostalAddress()
	
	import sys
	address.address1 = sys.stdin.readline().strip()
	city_state_zip = sys.stdin.readline().strip()
	address.city = city_state_zip.split(",")[0].strip()
	address.state = city_state_zip.split(",")[1].split(" ")[0].strip()
	address.zipcode = city_state_zip.split(",")[1].split(" ")[1].strip()
	
	try:
		verify_adddress(address)
	except:
		pass
	
	print "-------"
	
	print last_response
	
	print
	
	print address.address1
	print address.city + ",", address.state, address.zipcode
	print "CD", address.congressionaldistrict
	print "SLDU", address.state_legis_upper
	print "SLDL", address.state_legis_lower
	print "Coord", address.latitude, address.longitude
	
