#!runscript

from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import connection, transaction
from django.db.models import Count
from django.contrib.auth.models import User
from django.conf import settings
from django.core.urlresolvers import reverse
from django.views.decorators.cache import cache_page

from popvox.models import UserComment, Org, OrgContact, UserLegStaffRole

from math import log, exp
from datetime import datetime, timedelta
import calendar
import csv
from scipy import stats
from collections import OrderedDict
import urllib

#def metrics_report_spreadsheet(request, sheet):

with open('powerusers.csv','w') as info:
    header = ['id', 'email', 'state', 'positions_count', 'firstname', 'lastname', 'unsubscribe_link',  '\n']
    qs = User.objects.filter(userprofile__allow_mass_mails=True).annotate(positions_count=Count("comments")).order_by('-positions_count')
    ct = 10000
    #st = int(request.GET.get("page", "1")) - 1
    #qs = qs[0+st*ct:st*ct+ct].iterator()
    sep = '\t'
    from settings import SITE_ROOT_URL
    from popvox.views.home import unsubscribe_me_makehash, unsubscribe_me
    unsub_base_url = SITE_ROOT_URL + reverse(unsubscribe_me) + "?"
    def make_user_unsubscribe_link(obj):
        # create a link that the user can visit to one-click unsubscribe himself,
        # just take care to hash something so that people can't guess the URL
        # to unsubscribe someone else.
        return unsub_base_url + urllib.urlencode({"email": obj.email, "key": unsubscribe_me_makehash(obj.email)})

    skipped = 0
    success = 0
    info.write("\t".join(header))
    for user in qs:
        try:
            postaladdress = user.postaladdress_set.order_by('-created')[0]
        except IndexError:
            print str(user.id)+' '+user.email+' '+str(skipped)
            skipped +=1
            continue
            
        firstname = postaladdress.firstname
        lastname =  postaladdress.lastname
        state =     postaladdress.state
        unsublink = make_user_unsubscribe_link(user)
        positioncount = str(user.positions_count)

        try:
            info.write(str(user.id)+sep+user.email\
                +sep+state+sep+positioncount+sep\
                +str(firstname.encode('utf8'))+sep\
                +str(lastname.encode('utf8'))+sep\
                +unsublink\
                +"\n")
            print success
            success +=1
        except UnicodeDecodeError:
            print str(user.id)+' '+user.email+' '+str(skipped)
            skipped +=1
    print skipped

