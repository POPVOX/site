from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext, TemplateDoesNotExist
from django.views.generic.simple import direct_to_template
from django.contrib.auth.decorators import login_required, user_passes_test
from django.forms import ModelForm, Form, BooleanField
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
    
#Checks if a user's an admin of a given org
def orgpermission(org, user):
    if user.is_superuser:
        return True
    try:
        haspermission = user.orgroles.get(org=org)
        return True
    except:
        return False
    
    
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
        
    return render_to_response('popvox/home_match.html', {'billvotes': billvotes, 'members': members, 'most_recent_address': most_recent_address, 'stats': stats, 'had_abstain': had_abstain, 'type':"match"},
        context_instance=RequestContext(request))


def key_votes(request, orgslug=None, slateslug=None):
    org = Org.objects.get(slug=orgslug)
    slate = Slate.objects.get(org=org,slug=slateslug)
    admin = False
    leadership = False

    #if user is logged out, leg staff, org staff, or has no address, set  memberids to current leadership.
    if request.user:
        user = request.user
        try:
            prof = user.get_profile()
            
            if prof.is_leg_staff(): # or prof.is_org_admin():
                leadership = True
                
            else:
                #check if the user is an admin for the org that owns the slate
                admin = orgpermission(org, user)
                
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
    
    #if the slate's not published, hide it from everyone but the admins.
    visible = slate.visible
    if not visible and not admin:
        raise Http404
        
    if leadership:
        memberids = popvox.govtrack.CURRENT_LEADERSHIP
    
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
    for bill in slate.bills_neutral.all():
        try:
            slatecomment = SlateComment.objects.get(bill=bill,slate=slate)
        except:
            slatecomment = ''
        myslate.append((bill, 'N', slatecomment))
    
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

    return render_to_response('popvox/home_match.html', {'admin': admin,'billvotes': billvotes, 'members': members, 'slate': slate, 'stats': stats, 'had_abstain': had_abstain, 'leadership': leadership, 'org': org, 'type': "keyvotes", 'visible': visible, 'is_admin': admin},
        context_instance=RequestContext(request))
        
def keyvotes_index(request):
    
    slates = Slate.objects.filter(visible = True)
    
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
        exclude = ('slug','bills_neutral')

class SlateLimitForm(SlateForm):
    def __init__(self, *args, **kwargs):
        if "request" in kwargs:
            request = kwargs.pop("request")
            user = request.user
            prof = user.get_profile()
            if user.is_superuser:
                orgs = Org.objects.all()
            else:
                orgs = Org.objects.filter(admins__user = user)


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
        #widget_neutral = self.fields['bills_neutral'].widget
        bill_choices = []
        for bill in bills:
            if bill.street_name != None:
                title = (bill.street_name[:100] + '..') if len(bill.street_name) > 100 else bill.street_name
            else:
                title = (bill.title[:100] + '..') if len(bill.title) > 100 else bill.title
            bill_choices.append((bill.id, title))
        widget_support.choices = bill_choices
        widget_oppose.choices  = bill_choices
        #widget_neutral.choices = bill_choices
        

@login_required       
def keyvotes_create(request, orgslug=None, slateslug=None):
    
    user = request.user
    prof = user.get_profile()
    
    if not user.is_superuser or not prof.is_org_admin():
        raise Http404
        
    if request.method == 'POST':
            if orgslug:
                org = Org.objects.get(slug=orgslug)
                editslate = Slate.objects.get(org=org, slug=slateslug)
                form = SlateForm(request.POST, instance = editslate)
                if form.is_valid():
                    myslate = form.save()
            else:
                form = SlateForm(request.POST)
                if form.is_valid():
                    myslate = form.save(commit=False)
                    myslate.set_default_slug()
                    myslate.save() 
                    form.save_m2m()
            return redirect("/keyvotes/"+myslate.org.slug+"/"+myslate.slug)
    else:
        kwargs = {}
        kwargs['request'] = request
        
        #orgslug will only be True on edit
        if orgslug:
            org = Org.objects.get(slug=orgslug)
            
            #make sure they're authorized to edit that slate:
            permission = orgpermission(org, user)
            if permission:
                kwargs['instance'] = Slate.objects.get(org=org, slug=slateslug)
                #set the action word for the title
                actionword = "edit"
            else:
                raise Http404
        else:
            actionword = "create"
        form = SlateLimitForm(**kwargs)
    return render_to_response('popvox/keyvotes_create.html', {'form':form, 'actionword': actionword}, context_instance=RequestContext(request))
 
class SlateDeleteForm(Form):
    delete = BooleanField(required=True, error_messages={'required':'You must check the box to delete this key vote slate'})
    
@login_required       
def keyvotes_delete(request, orgslug=None, slateslug=None):
    
    user = request.user
    prof = user.get_profile()
    org = Org.objects.get(slug=orgslug)
    slate = Slate.objects.get(org=org, slug=slateslug)
    
    #make sure they're authorized to edit that slate:
    permission = orgpermission(org, user)
    if not permission:
        raise Http404
        
    form = SlateDeleteForm(request.POST or None)
    
    if form.is_valid():
        slatecomments = SlateComment.objects.filter(slate=slate).delete()
        slate.delete()
        return redirect('popvox/keyvotes_delete_done.html')
    if request.method == 'POST':
        status = "You must check the box to delete this key vote slate"
    else:
        status = ""
        
    return render_to_response('popvox/keyvotes_delete.html', {'org':org, 'slate':slate, 'form':form, 'status':status}, context_instance=RequestContext(request))
        
        