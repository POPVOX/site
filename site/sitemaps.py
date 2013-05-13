from django.contrib.sitemaps import Sitemap
from popvox.models import *
from datetime import datetime
from popvox.govtrack import CURRENT_CONGRESS

#TODO: Fix whatever the hell is wrong with the memberbio model that is preventing it from loading in admin, so that I can then change Menendez's pvurl so that it doesn't contain unicode, so that the member page site map will fucking load.

#once this fucking rabbit hole has finally been filled in, uncomment the memberpage sitemap in urls.py.

class MemberpageSitemap(Sitemap):

    priority = 0.8

    def changefreq(self, obj):
        return 'daily'

    def items(self):
        today = datetime.today()
        currentmems = [m for m in MemberOfCongress.objects.all() if m.info()['current']]
        memlist = []
        for mem in currentmems:
            personid = mem.id
            member = MemberOfCongress.objects.get(id=personid)
            memlist.append(member)
        return memlist #excluding past members who don't have member pages anymore.
        
    def location(self, obj):
        try:
            return '/member/'+str(obj.pvurl())+"/"
        except MemberBio.DoesNotExist:
            return
    

class BillSitemap(Sitemap):
    def priority(self, obj):
        if obj.congressnumber == CURRENT_CONGRESS:
            return 0.8
        else:
            return 0.4

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
    priority = 0.8

    def changefreq(self, obj):
        return 'weekly'

    def items(self):
        return Org.objects.all()
        
    def lastmod (self, obj):
        return obj.updated
        
    def location(self, obj):
        return '/orgs/'+str(obj.slug)
        
class KeyvoteSitemap(Sitemap):
    priority = 0.7

    def changefreq(self, obj):
        return 'weekly'

    def items(self):
        return Slate.objects.filter(visible = True)
        
    def location(self, obj):
        return '/keyvotes/'+str(obj.org.slug)+'/'+str(obj.slug)
