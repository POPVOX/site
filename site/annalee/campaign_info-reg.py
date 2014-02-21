#!runscript

# It'll make a file in the dir you ran it from called campaign_info-addresses.csv

from popvox.models import *
from django.contrib.auth.models import User
import unicodedata

sep = "\t"
reg = Regulation.objects.get(id=3)

with open('campaign_info-reg.csv','w') as info:
    for comment in reg.usercomments.all():
        if not comment.message:
            #no sense delivering empty comments to regulatory agencies
            continue
        
        address = comment.address
        #clean unicode out of names:
        firstname = unicodedata.normalize('NFKD',address.firstname).encode('ascii','ignore')
        lastname  = unicodedata.normalize('NFKD',address.lastname).encode('ascii','ignore')
        
        state = address.state
        dist = address.congressionaldistrict
        statedist = state + "-"+str(dist)
        
        
        address1 = unicodedata.normalize('NFKD',address.address1).encode('ascii','ignore').replace("\n"," ")
        address2 = unicodedata.normalize('NFKD',address.address2).encode('ascii','ignore').replace("\n"," ")
        city    = address.city
        message = comment.message
        
        #clean up the message
        message = unicodedata.normalize('NFKD',message).encode('ascii','ignore').replace("\n"," ")
        message = message.replace("\r","")
        
        info.write( str(firstname) \
            +sep+ str(lastname) +sep+ statedist +sep+ str(address1)+sep+\
                str(address2)+sep+ str(city)+sep+ str(state) +sep+ str(address.zipcode)\
                +sep+ str(address.user.email) +sep+ str(comment.created) +sep+\
                str(comment.updated) +sep+ str(message) + sep +"\n" )
        
