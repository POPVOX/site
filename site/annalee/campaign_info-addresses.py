#!runscript

# It'll make a file in the dir you ran it from called campaign_info-addresses.csv

import popvox.models as pv
from django.contrib.auth.models import User
import unicodedata

sep = "\t"
sac = pv.ServiceAccount.objects.get(id=6045)

#paidaccount ids:
    #Mayors Against Illegal Guns: 2882
    #Airlines for America: 5143

with open('campaign_info-addresses.csv','w') as info:
    for campaign in pv.ServiceAccountCampaign.objects.filter(account__id=sac.id):
        for record in campaign.actionrecords.all():
            #clean unicode out of names:
            firstname = unicodedata.normalize('NFKD',record.firstname).encode('ascii','ignore')
            lastname  = unicodedata.normalize('NFKD',record.lastname).encode('ascii','ignore')
            
            try:
                user = User.objects.get(email=record.email)
                lastcomment = pv.UserComment.objects.filter(user=user).latest('created')
                if lastcomment:
                    state = lastcomment.state
                    dist = lastcomment.congressionaldistrict
                    statedist = str(state)+sep+str(dist)
                else:
                    statedist = sep
            except:
                statedist = sep
            
            try:
                comment = record.completed_comment
            except:
                comment = None
                
            if comment:
                address1 = unicodedata.normalize('NFKD',comment.address.address1).encode('ascii','ignore').replace("\n"," ")
                address2 = unicodedata.normalize('NFKD',comment.address.address2).encode('ascii','ignore').replace("\n"," ")
                city    = comment.address.city
                state   = comment.address.state
                message = comment.message
                
                if message:
                    message = unicodedata.normalize('NFKD',message).encode('ascii','ignore').replace("\n"," ")
                    message = message.replace("\r","")
            else:
                address1 = ''
                address2 = ''
                city     = ''
                state    = ''
                message  = ''
            
            has_usertags = pv.UserTag.objects.filter(org=sac.org.id).exclude(value="None").exclude(value="Other").order_by("value")
            if has_usertags:
                rec_has_usertags = record.usertags.all()
                if rec_has_usertags:
                    tags = record.usertags.all()[0].value
                else:
                    tags = ''
            else:
                tags = ''
                
            
            info.write( str(firstname) +sep+ str(lastname) +sep+ statedist +sep+ str(address1)+sep+ str(address2)+sep+ str(city)+sep+ str(state) +sep+ str(record.zipcode) +sep+ str(record.email) +sep+ str(record.created) +sep+ str(record.updated) +sep+ str(record.completed_stage)+ sep +str(message) + sep + str(tags) +"\n" )
            
