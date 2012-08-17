#!/usr/bin/python
# Use this to get a count of how many comments an org has sent in a given month
import datetime
import popvox.models as pv
count = 0
org = pv.Org.objects.get(name__contains="Heritage")
campaigns = pv.ServiceAccountCampaign.objects.filter(account=org.service_account)
for campaign in campaigns:
        ars = campaign.actionrecords.filter(created__year='2012',created__month='7',completed_stage='finished')
            count += len(ars)
            print count


