from django.contrib.sitemaps import Sitemap
from popvox.models import *
from datetime import datetime
from popvox.govtrack import CURRENT_CONGRESS

class BillSitemap(Sitemap):
    priority = 0.5

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
    priority = 0.5

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