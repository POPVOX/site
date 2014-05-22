#! runscript

#runs the address's lat/long through the api in boundaries_us. Note: the boundaries_us project must be running on the development server for this to work.

#log in as ubuntu and run:

# SU boundaries
# cd /boundaries_us
# DEBUG=1 python manage.py runserver

import time
import json
from jquery.ajax import json_response, ajax_fieldupdate_request, sanitize_html

from popvox.models import *

import urllib
import urllib2
from xml.dom.minidom import parse, parseString

#addresses = [PostalAddress.objects.get(id=138817)]

addresses = PostalAddress.objects.filter(congressionaldistrict2013__isnull=True)

failcount = 0
wincount = 0
for address in addresses:
    
    #rounding to five decimal places because that's all the api can handle:
    if address.latitude and address.longitude:
        latitude = "%.5f" % address.latitude
        longitude = "%.5f" % address.longitude
        
        try:
            url = 'http://127.0.0.1:8000/boundaries/cd-2012/?contains='+str(latitude)+','+str(longitude)
            json_data = "".join(urllib2.urlopen(url).readlines())
            loaded_data = json.loads(json_data)

            district = loaded_data['objects'][0]['name'] #returns state and dist, as in MD-8. We only need district.

            districtnum=district.split('-')
            districtnum = int(districtnum[1])
            address.congressionaldistrict2013 = districtnum
            address.congressionaldistrict2003 = address.congressionaldistrict
            address.congressionaldistrict = districtnum

            address.save()
            
            if address.congressionaldistrict == districtnum:
                    print "success" + "\t" + str(address.id)
                    wincount += 1
            else:
                print "mismatch" + "\t" + str(address.id)
                failcount += 1
        
        except IndexError:
            print "IndexError on"+ "\t" +str(address.id)
            failcount += 1
            
        except:
            print "exception on"+ "\t" +str(address.id)
            failcount += 1
            
    else:
        print "lat and/or long missing on"+ "\t" +str(address.id)
        failcount += 1
    
print "success:"+"\t"+str(wincount)+"\n"+"fail:"+"\t"+str(failcount)
