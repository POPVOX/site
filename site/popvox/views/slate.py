from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext, TemplateDoesNotExist
from django.views.generic.simple import direct_to_template
from django.contrib.auth.decorators import login_required, user_passes_test
from django.forms import ModelForm
from django.forms.util import ErrorList
from django.db import transaction, connection
from django.db.models import Count, Max
from django.db.models.query import QuerySet
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from popvox.views.main import strong_cache
from django.template.defaultfilters import slugify

from jquery.ajax import json_response, ajax_fieldupdate_request, sanitize_html
import json

import re
import os
from xml.dom import minidom
from itertools import chain, izip, cycle

from popvox.models import *
from popvox.views.bills import bill_statistics, get_default_statistics_context
from popvox.views.bills import get_popular_bills, get_popular_bills2
import popvox.govtrack
import popvox.match

from settings import SITE_ROOT_URL
from mempageurls import memurls

import csv
import urllib
import urllib2
from xml.dom.minidom import parse, parseString

from datetime import datetime, date, timedelta

from django.db.models import Count


@login_required
def who_members(request): #this page doesn't exist, but we could do some cool stuff with it.
    user = request.user
    prof = user.get_profile()
        
    if prof.is_leg_staff():
        raise Http404()
        
    elif prof.is_org_admin():
        raise Http404()
    
    else:
      address = PostalAddress.objects.get(user=request.user.id)
      userstate = address.state
      userdist  = address.congressionaldistrict
      usersd    = userstate+str(userdist)

      #find the govtrack ids corresponding to the user's members (note: can't assume number of reps):
      members = popvox.govtrack.getMembersOfCongressForDistrict(usersd)
      membernames = []

      for member in members:
        membernames.append(member['name'])
      return render_to_response('popvox/who_members.html', {'membernames': membernames},
        
    context_instance=RequestContext(request))
    
    
def getmemberids(address):
    #select the user's state and district:
    userstate = address.state
    userdist  = address.congressionaldistrict
    usersd    = userstate+str(userdist)
    
    #find the govtrack ids corresponding to the user's members (note: can't assume number of reps):
    members = popvox.govtrack.getMembersOfCongressForDistrict(usersd)
    memberids = []
    
    for member in members:
        memberids.append(member['id'])
    return memberids
        
        
_congress_match_attendance_data = None
@login_required
def congress_match(request):
    user = request.user
    
    try:
        most_recent_address = PostalAddress.objects.filter(user=user).order_by('-created')[0]
    except IndexError:
        # user has no address! therefore no comments either!
        return render_to_response('popvox/home_match.html', {'billvotes': [], 'members': []},
            context_instance=RequestContext(request))
            
    memberids = getmemberids(most_recent_address)
    
    membermatch = popvox.match.membermatch(memberids, user)
    
    billvotes = membermatch[0]
    stats = membermatch[1]
    had_abstain = membermatch[2]
    
    # get member info for column header
    members = []
    for id in memberids:
        members.append(popvox.govtrack.getMemberOfCongress(id))

    for member in members:
        url = [k for k, v in memurls.items() if member['id'] == v][0]
        member['pvurl'] = url

    return render_to_response('popvox/home_match.html', {'billvotes': billvotes, 'members': members, 'most_recent_address': most_recent_address, 'stats': stats, 'had_abstain': had_abstain},
        context_instance=RequestContext(request))


def key_votes(request, orgslug=None, slateslug=None):
    
    leadership = False
    #if user is logged out, leg staff, org staff, or has no address, set  memberids to current leadership.
    if request.user:
        user = request.user
        try:
            prof = user.get_profile()
            
            if prof.is_leg_staff(): # or prof.is_org_admin():
                leadership = True
            else:
                try:
                    most_recent_address = PostalAddress.objects.filter(user=user).order_by('-created')[0]
                    memberids = getmemberids(most_recent_address)
                except IndexError:
                    # user has no address.
                    leadership = True
                    
        except:
            leadership = True
    else:
        leadership = True
        
    if leadership:
        memberids = popvox.govtrack.CURRENT_LEADERSHIP

    org = Org.objects.get(slug=orgslug)
    slate = Slate.objects.get(org=org,slug=slateslug)
    
    myslate = []
    for bill in slate.bills_support.all():
        try:
            slatecomment = SlateComment.objects.get(bill=bill,slate=slate)
        except:
            slatecomment = ''
        myslate.append((bill, '+', slatecomment))
    for bill in slate.bills_oppose.all():
        try:
            slatecomment = SlateComment.objects.get(bill=bill,slate=slate)
        except:
            slatecomment = ''
        myslate.append((bill, '-', slatecomment))
    
    membermatch = popvox.match.membermatch(memberids, user, myslate)
    
    billvotes = membermatch[0]
    stats = membermatch[1]
    had_abstain = membermatch[2]
    
    # get member info for column header
    members = []
    for id in memberids:
        member = popvox.govtrack.getMemberOfCongress(id)
        members.append(member)


    for member in members:
        url = [k for k, v in memurls.items() if member['id'] == v][0]
        member['pvurl'] = url

    return render_to_response('popvox/keyvotes.html', {'billvotes': billvotes, 'members': members, 'slate': slate, 'stats': stats, 'had_abstain': had_abstain, 'leadership': leadership},
        context_instance=RequestContext(request))
        
def keyvotes_index(request):
    
    slates = Slate.objects.all()
    
    return render_to_response('popvox/keyvotes_index.html', {'slates': slates}, context_instance=RequestContext(request))
        
        
class SlateErrorList(ErrorList):
     def __unicode__(self):
         return self.as_divs()
     def as_divs(self):
         if not self: return u''
         return u'<div class="errorlist">%s</div>' % ''.join([u'<div class="error">%s</div>' % e for e in self])
 
#    user = request.user
#    prof = user.get_profile()
#    
#    if prof == None:
#        raise Http404()
#    
#    if prof.is_org_admin():
#        orgs = Org.objects.filter(admins__user = user)
class SlateForm(ModelForm):
    class Meta:
        model = Slate
        exclude = ('slug',)

class SlateLimitForm(SlateForm):
    def __init__(self, *args, **kwargs):
        if "request" in kwargs:
            request = kwargs.pop("request")
            user = request.user
            prof = user.get_profile()
            if prof.is_org_admin():
                orgs = Org.objects.filter(admins__user = user)
            else:
                orgs = Org.objects.all()


        super(SlateLimitForm, self).__init__(*args, **kwargs)
        org_choices = []
        if orgs:
            for org in orgs:
                org_choices.append((org.id, org.name))

                widget_org = self.fields['org'].widget
                widget_org.choices = org_choices
    
        bills = Bill.objects.annotate(roll_count=Count('rolls')).filter(roll_count__gt=0,congressnumber=112)
        widget_support = self.fields['bills_support'].widget
        widget_oppose = self.fields['bills_oppose'].widget
        bill_choices = []
        for bill in bills:
            if bill.street_name != None:
                title = (bill.street_name[:100] + '..') if len(bill.street_name) > 100 else bill.street_name
            else:
                title = (bill.title[:100] + '..') if len(bill.title) > 100 else bill.title
            bill_choices.append((bill.id, title))
        widget_support.choices = bill_choices
        widget_oppose.choices = bill_choices
        

       
def keyvotes_create(request):
    user = request.user
    prof = user.get_profile()
    if not prof.is_org_admin():
        raise Http404
        
    if request.method == 'POST':
        print "post"
        form = SlateForm(request.POST)
        if form.is_valid():
            print "valid"
            myslate = form.save(commit=False)
            myslate.set_default_slug()
            myslate.save() 
            form.save_m2m()
            #return redirect("http://google.com")
    else:
        kwargs = {}
        kwargs['request'] = request
        form = SlateLimitForm(**kwargs)
    return render_to_response('popvox/keyvotes_create.html', {'form':form}, context_instance=RequestContext(request))
        
        