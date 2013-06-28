#!runscript

import urllib2
import json
import sys

last_response = None

class AddressVerificationError(ValueError):
    def __init__(self, message, mandatory=False):
        super(AddressVerificationError, self).__init__(message)
        self.mandatory = mandatory

def verify_adddress(address, validate=True):
    global last_response

    # import here so we can set env variables in the __main__ code
    from settings import CDYNE_LICENSE_KEY

    if validate and "pobox" in address.address1.replace(" ", "").lower() and address.address2.strip() != "":
        raise AddressVerificationError("A PO Box address cannot have a second address line. If your mail requires a street address and PO Box, enter the PO Box on the second line.", mandatory=True)

    if validate and len([s for s in address.phonenumber if s.isdigit()]) != 10:
        raise AddressVerificationError("Congressional offices only accept ten digit phone numbers without extensions. Please provide a ten digit phone number.", mandatory=True)

    if validate and address.state.lower() != "ak" and "pobox" in address.address1.replace(" ", "").lower():
        raise AddressVerificationError("Please enter the address of your residence so that we can determine your Congressional district. We cannot find your district based on a PO Box.")

    if address.address1.lower().strip() == address.address2.lower().strip():
        address.address2 = ""
    
    req = urllib2.Request("http://pav3.cdyne.com/PavService.svc/VerifyAddressAdvanced",
        json.dumps(
        {
            "LicenseKey": CDYNE_LICENSE_KEY,
            #"FirmOrRecipient": ,
            "PrimaryAddressLine": address.address1,
            "SecondaryAddressLine": address.address2 if "pobox" not in address.address2.replace(" ", "").lower() else "",
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
    
    return verify_adddress_cached(address, ret, validate)

def verify_adddress_cached(address, ret, validate=True):
    address.cdyne_response = json.dumps(ret)

    from popvox.govtrack import stateapportionment

    if ret["LegislativeInfo"]["CongressionalDistrictNumber"] is None:
        if not validate:
            return
        raise AddressVerificationError("We couldn't determine the Congressional district at that address. Make sure you haven't abbreviated the name of your street or city.")
    
    address.cdyne_return_code = ret["ReturnCode"]

    if ret["ResidentialDeliveryIndicator"] == "N":
        #raise AddressVerificationError("This address is believed to be a commercial delivery address. Use a residental address.")
        address.cdyne_return_code = 900 # for us
    
    # Correct fields...
    def nrml(x):
        return x.lower().replace(".", "").replace("#", "")
    for a, b in [('address1', 'PrimaryDeliveryLine'), ('address2', 'SecondaryDeliveryLine'), ('city', 'PreferredCityName'), ('state', 'StateAbbreviation'), ('zipcode', 'ZipCode')]:
        if hasattr(address, a) and nrml(getattr(address, a)) != nrml(ret[b]):
            setattr(address, a, ret[b])
            
    if address.address1.lower().strip() == address.address2.lower().strip():
        address.address2 = ""
    
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
    address.county = ret["County"]

def validate_phone(phonenumber):
    phonenumber = "".join([d for d in phonenumber if d.isdigit()])
    
    # chop off optional initial 1
    if phonenumber.startswith("1"):
        phonenumber = phonenumber[1:]

    # there must be at least 10 digits after that
    if len(phonenumber) < 10:
        raise ValueError("Phone number must be at least 10 digits.")

    if phonenumber[0] in ("0", "1"):
        raise ValueError("Phone number area code cannot start with a 0 or 1.")
    if phonenumber[3] in ("0", "1"):
        raise ValueError("Phone number local number cannot start with a 0 or 1.")
    if phonenumber[1:3] == "11" or phonenumber[0:3] == "555":
        raise ValueError("Phone number has an invalid area code.")
    if phonenumber[3:8] == "55501":
        raise ValueError("Phone number is in the fictitious block.")

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
    
