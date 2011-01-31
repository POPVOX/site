import urllib2
import json

from settings import CDYNE_LICENSE_KEY

from popvox.govtrack import stateapportionment

def verify_adddress(address):
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
		raise ValueError("Address verification is not working at the moment.")
	
	if ret["ReturnCode"] not in (100, 101, 102, 103):
		raise ValueError("The address was not found.")
	
	if ret["ResidentialDeliveryIndicator"] == "N":
		raise ValueError("This address is believed to be a commercial delivery address. Use a residental address.")
	
	address.cdyne_return_code = ret["ReturnCode"]
	
	# Correct fields...
	for a, b in [('address1', 'PrimaryDeliveryLine'), ('address2', 'SecondaryDeliveryLine'), ('city', 'PreferredCityName'), ('state', 'StateAbbreviation'), ('zipcode', 'ZipCode'), ('county', 'County')]:
		if hasattr(address, a) and getattr(address, a).lower() != ret[b].lower():
			setattr(address, a, ret[b])
	
	if ret["LegislativeInfo"]["CongressionalDistrictNumber"] == "AL":
		address.congressionaldistrict = 0
	else:
		address.congressionaldistrict = int(ret["LegislativeInfo"]["CongressionalDistrictNumber"])
	address.state_legis_upper = ret["LegislativeInfo"]["StateLegislativeUpper"]
	address.state_legis_lower = ret["LegislativeInfo"]["StateLegislativeLower"]
	address.latitude = float(ret["GeoLocationInfo"]["AvgLatitude"])
	address.longitude = float(ret["GeoLocationInfo"]["AvgLongitude"])
	
	# at-large comes back as 98, etc.
	if stateapportionment[address.state] == 1:
		address.congressionaldistrict = 0

