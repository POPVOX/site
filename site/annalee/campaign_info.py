# (Paste this into a ./manage shell)
# It'll make a file in the dir you ran it from called campaign_info.csv

import popvox.models as pv

with open('campaign_info.csv','w') as info:
        for campaign in pv.ServiceAccountCampaign.objects.filter(account__id=1926):
                    for record in campaign.actionrecords.all():
                                    info.write( str(record.firstname) +","+ str(record.lastname) +","+ str(record.zipcode) +","+ str(record.email) +","+ str(record.created) +","+ str(record.updated) +","+ str(record.completed_stage) ) +"\n"
