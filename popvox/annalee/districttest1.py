#!runscript

import json
import mechanize
import random
import re
import system
import urllib

# create a Browser instance
br = mechanize.Browser()
# don't bother with robots.txt
br.set_handle_robots(False)
# add a custom header
br.addheaders = [('User-agent', 'Mozilla/5.0 Compatible')]


#----CHECK ADDRESS WITH USPS----#

def getuspszip(address1, city, state):

    #POST request
    form1 = {
        'address1': '',
        'address2': address1,
        'city': city,
        'firmname': '',
        'pagenumber': '0',
        'state':    state,
        'submit.x':   '29',
        'submit.y':   '8',
        'urbanization': '',
        'visited':  '1',
        'zip5': zipcode,
    }

    #submit
    clicky = br.open('http://zip4.usps.com/zip4/zcl_0_results.jsp', data = urllib.urlencode(form1))
    uspsresult = clicky.read()

    assert ("You Gave Us" in clicky.get_data()), 'USPS Form Text Assertion Failed'

    #find & extract zipcode
    zipsearch = re.compile (r";\d\d\d\d\d-\d\d\d\d")

    zipresult = zipsearch.search(uspsresult)

    if zipresult==None: return None
    
    uspszip = zipresult.group(0)

    uspszip = uspszip.replace(";", "")

    return uspszip

#----RETRIEVE DISTRICT GOVTRACK-STYLE---#
    #Govtrack uses the google API to get coordinates, that it compares to census cartographic data to get the zip.

def getdistgt(address1, city, state, zipcode):

    gtaddress = address1+", "+city+", "+state+" "+zipcode

    #POST request
    form1 = {
        'address': gtaddress,
    }

    #submit
    clicky = br.open('https://www.popvox.com/ajax/district-lookup', data = urllib.urlencode(form1))
    gtresult = clicky.read()

    gtdict = json.loads(gtresult)

    gtdistrict = str(gtdict['district'])
    gtstate =    gtdict['state']

    return gtstate+"-"+gtdistrict

#----HARD CODE VARIABLES FOR TESTING----#
#address1 = "1220 East-West Highway"
#address2 = "Apt 1716"
#city = "Silver Spring"
#state = "MD"
#zip5 = "20910"

#----COLLECT AND COMPARE USER DATA----#

#GET USER DATA

#error counters
ziperror=0
disterror=0
    
from popvox.models import PostalAddress

for addr in PostalAddress.objects.all()[0:10]:
    address1    = addr.address1
    city        = addr.city
    state       = addr.state
    zipcode     = addr.zipcode
    district    = str(addr.congressionaldistrict)

#PRINT USER DATA
    uspszip    = getuspszip(address1, city, state)
    gtdistrict = getdistgt(address1, city, state, zipcode)
    pvdistrict = state+"-"+district

    print address1+", "+city+", "+state+", "
    print "POPVOX Zip: "+zipcode
    print "USPS Zip: "+str(uspszip)
    print "govtrack district:"+gtdistrict
    print "popvox district:"+pvdistrict

#COMPARE USER DATA

    if zipcode==uspszip:
        print "zipcodes match"
    else:
        print "zipcode error"
        ziperror+=1
        

    if gtdistrict==pvdistrict:
        print "district match"
    else:
        print "district error"
        disterror+=1

#PRINT ERRORS
print "zipcode errors: "+str(ziperror)
print "district errors: "+str(disterror)


#from popvox.models import PostalAddress
#for addr in PostalAddress.objects.all()[0:10]:
#	print addr.address1, addr.state, addr.city, addr.zipcode, addr.congressionaldistrict
