#!runscript

# (Paste this into a ./manage shell)
# It'll make a file in the dir you ran it from called campaign_info.csv

import popvox.models as pv
from django.contrib.auth.models import User
import unicodedata

sep = "\t"

with open('campaign_info.csv','w') as info:
    for campaign in pv.ServiceAccountCampaign.objects.filter(account__id=1901):
        for record in campaign.actionrecords.all():
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
            
            #try:
            if record.completed_comment:
                position = record.completed_comment.position
                message = record.completed_comment.message
                if message:
                    message = unicodedata.normalize('NFKD',message).encode('ascii','ignore').replace("\n"," ")
                    message = message.replace("\r","")
            else:
                position = sep
                message = sep
            '''except:
                message = sep
                position = sep'''
            
            try:
                info.write( str(record.firstname) +sep+ str(record.lastname) +sep+ statedist +sep+ str(record.zipcode) +sep+ str(record.email) +sep+ str(record.created) +sep+ str(record.updated) +sep+ str(record.completed_stage)+ sep +str(position) + sep +str(message) +"\n" )
            except UnicodeEncodeError:
                print str(record.id) + " UnicodeError."

            
#info.write( str(record.firstname) +","+ str(record.lastname) +","+ statedist +","+ str(record.zipcode) +","+ str(record.email) +","+ str(record.created) +","+ str(record.updated) +","+ str(record.completed_stage) ) +"\n"
            