#!runscript

from popvox.models import UserComment, ServiceAccountCampaign 
from django.contrib.auth.models import User
import unicodedata
import urllib2
import urlparse
import ast
import re

sep = "\t"

with open('qpc-campaign_info.csv','w') as info:
    for ServiceAccountCampaign.objects.filter(account__id=1196):
        for record in campaign.actionrecords.all():
            try:
                user = User.objects.get(email=record.email)
                lastcomment = UserComment.objects.filter(user=user).latest('created')
                if lastcomment:
                    state = lastcomment.state
                    dist = lastcomment.congressionaldistrict
                    statedist = str(state)+sep+str(dist)
                else:
                    statedist = sep
            except:
                statedist = sep
            
            #try:
            position = sep
            message = sep
            #it's choking on nonexistant comments rather than evaluating them as False.
            try:
                comment = record.completed_comment
            except:
                comment = False
            if comment:
                position = record.completed_comment.position
                message = record.completed_comment.message
                if message:
                    message = unicodedata.normalize('NFKD',message).encode('ascii','ignore').replace("\n"," ")
                    message = message.replace("\r","")

                
            optin = record.optin
            
            source = ''
            #grabbing the utm_source. First need the request dump dictified:
            try:
                reqdump = ast.literal_eval(record.request_dump)
                if 'HTTP_COOKIE' not in reqdump:
                    reqdump['HTTP_COOKIE'] = None
            except:
                reqdump = {'HTTP_COOKIE': None}
            #now getting the urlencoding out of the cookie:
            if reqdump['HTTP_COOKIE']:
                cookie = urllib2.unquote(reqdump['HTTP_COOKIE']).decode('utf8')
                #this next bit assumes we're dealing with utm codes in the url,
                #and that mixpanel is processing them. If that's not the case,
                #set source to blank.

                #getting the referrer info out of the cookie as a dict:
                cookiedict = re.sub(r'^.+=(?={)', '', cookie, count=1)
                cookiedict = re.sub(r'(?<=});.+$', '', cookiedict, count=1)
                
                try:
                    refinfo = ast.literal_eval(cookiedict)
                except:
                    refinfo = {}
                if 'all' in refinfo:
                    refinfo = refinfo['all']
                
                if '$initial_referrer' in refinfo:
                    #pulling the referrer url:
                    ref = refinfo['$initial_referrer']
                    #and turning query section of the referrer url into a dict:
                    refquery = urlparse.urlparse(ref).query
                    refdict = dict(urlparse.parse_qsl(refquery, keep_blank_values=True))
                    #the source:
                    if 'utm_source' in refdict:
                        source = refdict['utm_source']
            
            
            try:
                info.write( str(record.campaign) +sep+ str(record.firstname) +sep+ str(record.lastname) +sep+ statedist +sep+ str(record.zipcode) +sep+ str(record.email) +sep+ str(record.created) +sep+ str(record.updated) +sep+ str(record.completed_stage)+ sep + source + sep + str(position) + sep +str(message) +"\n" )
            except UnicodeEncodeError:
                print str(record.id) + " UnicodeError."
            
#info.write( str(record.firstname) +","+ str(record.lastname) +","+ statedist +","+ str(record.zipcode) +","+ str(record.email) +","+ str(record.created) +","+ str(record.updated) +","+ str(record.completed_stage) ) +"\n"
            
