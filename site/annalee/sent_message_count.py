#!runscript

# Use this to get a count of how many comments an org has sent in a given month
import datetime
from django.conf import settings
from popvox.models import *

count = 0
org = Org.objects.get(name__contains="Heritage")
campaigns = ServiceAccountCampaign.objects.filter(account=org.service_account)
for month in range(1,7):
    count = 0
    for campaign in campaigns:
            ars = campaign.actionrecords.filter(created__year='2012',created__month=month,completed_stage='finished')
            count += len(ars)
    print str(month)+": "+str(count)


