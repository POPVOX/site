from django.contrib.sitemaps import Sitemap
from popvox.models import *
from datetime import datetime
from popvox.govtrack import CURRENT_CONGRESS

class MemberpageSitemap(Sitemap):

    priority = 0.8

    def changefreq(self, obj):
        return 'daily'

    def items(self):
        return MemberOfCongress.objects.filter(pvurl__contains="-") #excluding past members who don't have member pages anymore.
        
    def location(self, obj):
        return '/member/'+str(obj.pvurl)+"/"
    

class BillSitemap(Sitemap):
    def priority(self, obj):
        if obj.congressnumber == CURRENT_CONGRESS:
            return 0.8
        else:
            return 0.5

    def changefreq(self, obj):
        if obj.congressnumber != CURRENT_CONGRESS:
            return 'yearly'
        else:
            return 'daily'

    def items(self):
        return Bill.objects.all()
        
    def lastmod (self, obj):
        return obj.current_status_date
        
    def location(self, obj):
        return '/bills/us/'+str(obj.congressnumber)+'/'+str(obj.billtype)+str(obj.billnumber)
        
class BillReportSitemap(Sitemap):
    
    def priority(self, obj):
        if obj.congressnumber == CURRENT_CONGRESS:
            return 0.8
        else:
            return 0.5

    def changefreq(self, obj):
        if obj.congressnumber != CURRENT_CONGRESS:
            return 'yearly'
        else:
            return 'daily'

    def items(self):
        return Bill.objects.all()
        
    def lastmod (self, obj):
        return obj.current_status_date
        
    def location(self, obj):
        return '/bills/us/'+str(obj.congressnumber)+'/'+str(obj.billtype)+str(obj.billnumber)+'/report'
        
        
class OrgSitemap(Sitemap):
    priority = 0.5

    def changefreq(self, obj):
        return 'weekly'

    def items(self):
        return Org.objects.all()
        
    def lastmod (self, obj):
        return obj.updated
        
    def location(self, obj):
        return '/orgs/'+str(obj.slug)