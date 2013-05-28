from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.views.generic.simple import direct_to_template
from django.contrib.auth.decorators import login_required, user_passes_test
from django import forms
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

# working on this...
def new_bills(request, NumDays):
    
    
    LookupDays = int(NumDays)
    
    NewBills = []
    # Get all bills from past 7 days
    bills = Bill.objects.filter(introduced_date__gt=datetime.now()-timedelta(days=LookupDays))
    
    
    #House Bills
    HR = bills.filter(billtype='h')
    #Senate Bills
    S = bills.filter(billtype='s')
    #House Resolutions
    HRes = bills.filter(billtype='hr')
    #Senate Resolutions
    SRes = bills.filter(billtype='sr')
    #House Concurrent Resolutions
    HCRes = bills.filter(billtype='hc')
    #Senate Concurrent Resolutions
    SCRes = bills.filter(billtype='sc')
    #House Joint Resolutions
    HJRes = bills.filter(billtype='hj')
    #Senate Joint Resolutions
    SJRes = bills.filter(billtype='sj')
    
    for b in bills:
        NewBills.append(b)
    
    return render_to_response('popvox/bill_list_NewBills.html',
            {
                "HR": HR,
                "S": S,
                "HRes": HRes,
                "SRes": SRes,
                "HCRes": HCRes,
                "SCRes": SCRes,
                "HJRes": HJRes,
                "SJRes": SJRes,
                "NumDays":NumDays
            },
            context_instance=RequestContext(request))
# ******************

def annotate_track_status(profile, bills):
    tracked_bills = profile.tracked_bills.all()
    antitracked_bills = profile.antitracked_bills.all()
    for b in bills:
        if b in tracked_bills:
            b.trackstatus = True
        if b in antitracked_bills:
            b.antitrackstatus = True
    return bills

def get_legstaff_suggested_bills(user, counts_only=False, id=None, include_extras=True):
    prof = user.userprofile
    
    suggestions = [  ]
    
    #from settings import DEBUG
    #if DEBUG:
    #    from django.db import connection, transaction
    #    connection.cursor().execute("RESET QUERY CACHE;")
    
    def select_bills(**kwargs):
        return Bill.objects.filter(
            congressnumber=popvox.govtrack.CURRENT_CONGRESS,
            vehicle_for=None,
            **kwargs) \
            .exclude(antitrackedby=prof) \
            .order_by()
            
    boss = user.legstaffrole.member
    if boss != None:
        bossname = boss.name()
    else:
        bossname = ""
    
    suggestions.append({
        "id": "tracked",
        "type": "tracked",
        "name": "Bookmarked Legislation",
        "shortname": "Bookmarked",
        "bills": prof.tracked_bills.all()
        })
    
    if boss != None:
        moc = popvox.govtrack.getMemberOfCongress(boss.id)
        suggestions.append({
            "id": "sponsor",
            "type": "sponsor",
            "name": "Sponsored by " + bossname,
            "shortname": boss.lastname,
            "bills": select_bills(sponsor = boss)
            })
        
        if "committees" in moc and user.legstaffrole.committee == None:
            for cid in sorted(moc["committees"]):
                try:
                    cx = CongressionalCommittee.objects.get(code=cid)
                except:
                    continue
                name = cx.name()
                shortname = cx.abbrevname()
                committeename = cx.shortname()
                suggestions.append({
                    "id": "committee_" + cid,
                    "type": "committeereferral",
                    "name": "Referred to the " + name,
                    "shortname": shortname + " (Referral)",
                    "bills": select_bills(committees = cx)
                    })
                

    localbills = get_legstaff_district_bills(user)
    if localbills != None and len(localbills) > 0:
        d = moc["state"] + ("" if moc["type"] == "sen" else "-" + str(moc["district"]))
        suggestions.append({
            "id": "local",
            "type": "local",
            "name": "Hot Bills In Your " + ("State" if moc["type"] == "sen" else "District") + ": " + d,
            "shortname": "Hot in " + d,
            "bills": localbills
            })
        
    committeename = ""
    if user.legstaffrole.committee != None:
        cx = user.legstaffrole.committee
        name = cx.name()
        shortname = cx.abbrevname()
        committeename = cx.shortname()

        suggestions.append({
            "id": "committeereferral",
            "type": "committeereferral",
            "name": "Referred to the " + name,
            "shortname": shortname + " (Referral)",
            "bills": select_bills(committees = cx)
            })

        suggestions.append({
            "id": "committeemember",
            "type": "committeemember",
            "name": "Introduced by a Member of the " + name,
            "shortname": shortname + " (Member)",
            "bills": select_bills(sponsor__in = govtrack.getCommittee(user.legstaffrole.committee.code)["members"])
            })
        
    

    for ix in prof.issues.all():
        suggestions.append({
            "id": "issue_" + str(ix.id),
            "type": "issue",
            "issue": ix,
            "name": "Issue Area: " + ix.name,
            "shortname": ix.shortname if ix.shortname != None else ix.name,
            "bills": select_bills(issues__id__in=[ix.id] + list(ix.subissues.all().values_list('id', flat=True))) # the disjunction was slow: select_bills(issues=ix) | select_bills(issues__parent=ix)
            })

    if include_extras:
        #suggestions.append({
        #    "id": "allbills",
        #    "type": "allbills",
        #    "name": "All Bills",
        #    "shortname": "All",
        #    "bills": select_bills()
        #    })
        
        suggestions.append({
            "id": "hidden",
            "type": "hidden",
            "name": "Legislation You Have Hidden",
            "shortname": "Hidden",
            "bills": prof.antitracked_bills.all()
            })

    # If id != None, then we're requesting just one group. We can do this now
    # since the queries are lazy-loaded.
    if id != None:
        suggestions = [s for s in suggestions if s["id"] == id]

    # If the user wants to filter out only bills relevant to a particular chamber, then
    # we have to filter by status. Note that PROV_KILL:PINGPONGFAIL is included in
    # both H and S bills because we don't know what chamber is next.
    chamber_of_next_vote = prof.getopt("home_legstaff_filter_nextvote", None)
    ext_filter = None
    if chamber_of_next_vote == "h":
        ext_filter = lambda q : \
            q.filter(billtype__in = ('h', 'hr', 'hc', 'hj'), current_status__in = ("INTRODUCED", "REFERRED", "REPORTED", "PROV_KILL:VETO")) |\
            q.filter(current_status__in = ("PASS_OVER:SENATE", "PASS_BACK:SENATE", "OVERRIDE_PASS_OVER:SENATE", "PROV_KILL:SUSPENSIONFAILED", "PROV_KILL:PINGPONGFAIL"))
    elif chamber_of_next_vote == "s":
        ext_filter = lambda q : \
            q.filter(billtype__in = ('s', 'sr', 'sc', 'sj'), current_status__in = ("INTRODUCED", "REFERRED", "REPORTED", "PROV_KILL:VETO")) |\
            q.filter(current_status__in = ("PASS_OVER:HOUSE", "PASS_BACK:HOUSE", "OVERRIDE_PASS_OVER:HOUSE", "PROV_KILL:CLOTUREFAILED", "PROV_KILL:PINGPONGFAIL"))
    if ext_filter != None:
        for s in suggestions:
            if s["type"] not in ("tracked", "sponsor") and isinstance(s["bills"], QuerySet):
                try:
                    s["bills"] = ext_filter(s["bills"])
                except: # can't filter hot-in-your-district because it's got a slice
                    pass
        
    if counts_only:
        def count(x):
            if isinstance(x, QuerySet):
                return x.count()
            else:
                return len(x)
        for s in suggestions:
            s["count"] = count(s["bills"])
        return [{"id": s["id"], "type": s["type"], "shortname": s["shortname"], "count": s["count"] } for s in suggestions if s["count"] > 0 or s["id"] == "tracked"]

    # Clear out any groups with no bills. We can call .count() if we just want
    # a count, but since we are going to evaluate later it's better to evaluate
    # it once here so the result is cached.
    suggestions = [s for s in suggestions if len(s["bills"]) > 0 or s["id"] == "tracked"]

    def concat(lists):
        ret = []
        for lst in lists:
            ret.extend(lst)
        return ret
    all_bills = concat([s["bills"] for s in suggestions])

    # Pre-fetch all of the committee assignments of all of the bills, in bulk.
    if len(all_bills) > 0:
        # Load the committee assignments and put into a hash.
        committee_assignments = { }
        for b in Bill.objects.raw("SELECT popvox_bill.id AS id, popvox_congressionalcommittee.id AS committee_id, popvox_congressionalcommittee.code AS committee_code FROM popvox_bill LEFT JOIN popvox_bill_committees ON popvox_bill.id=popvox_bill_committees.bill_id LEFT JOIN popvox_congressionalcommittee ON popvox_congressionalcommittee.id=popvox_bill_committees.congressionalcommittee_id WHERE popvox_bill.id IN (%s)" % ",".join([str(b.id) for b in all_bills])):
            if not b.id in committee_assignments:
                committee_assignments[b.id] = []
            if b.committee_code in (None, ""): # ??
                continue
            c = CongressionalCommittee()
            c.id = b.committee_id
            c.code = b.committee_code
            committee_assignments[b.id].append(c)
            
        # We can't replace the 'committees' field on each bill object with the list because
        # access to the field seems to be protected (i.e. setattr overridden??) so we set
        # a secondary field. In govtrack.py, we check for the presence of that field when
        # getting committee assignments.
        for b in all_bills:
            b.committees_cached = committee_assignments[b.id]
            
        # Pre-create MemberOfCongress objects because they don't have any info...
        for b in all_bills:
            b.sponsor = MemberOfCongress(id=b.sponsor_id)
            
    # Preset the tracked and antitracked status.
    annotate_track_status(prof, all_bills)
    
    # Pre-fetch all of the top terms for categorization.
    top_terms = {}
    for ix in IssueArea.objects.filter(parent__isnull=True):
        top_terms[ix.id] = ix
    
    # Group any of the suggestion groups that have too many bills in them.
    # This is the only part of this routine that actually iterates through the
    # bills. We can report the categories and total counts of suggestions
    # without this.
    myissues = [ix.name for ix in prof.issues.all()]
    counter = 0
    for s in suggestions:
        s["count"] = len(s["bills"])
        
        if s["count"] <= 15:
            s["subgroups"] = [ {"bills": s["bills"], "id": counter } ]
            counter += 1
        else:
            ixd = { }
            for b in s["bills"]:
                if b.congressnumber != popvox.govtrack.CURRENT_CONGRESS:
                    ix = str(b.congressnumber) + popvox.govtrack.ordinate(b.congressnumber) +  " Congress"
                elif s["type"] != "sponsor" and boss != None and b.sponsor_id != None and b.sponsor_id == boss.id:
                    ix = "Sponsored by " + bossname
                elif (s["type"] != "issue" or s["issue"].parent != None) and b.topterm_id != None:
                    ix = top_terms[b.topterm_id].name
                elif s["type"] != "committeereferral" and len(b.committees_cached) > 0 and b.committees_cached[0].shortname() != "":
                    ix = b.committees_cached[0].shortname()
                else:
                    ix = "Other"
                if not ix in ixd:
                    ixd[ix] = { "name": ix, "bills": [], "id": counter }
                    counter += 1
                ixd[ix]["bills"].append(b)
            s["subgroups"] = ixd.values()
            s["subgroups"].sort(key = lambda x : (
                x["name"] == "Other",
                x["name"] != "Sponsored by " + bossname,
                x["name"] != committeename,
                x["name"] not in myissues,
                x["name"]))
            
        for g in s["subgroups"]:
            g["bills"] = list(g["bills"])
            g["bills"].sort(key = lambda b : b.current_status_date, reverse = True)
    
    return suggestions

def get_legstaff_district_bills(user):
    if user.legstaffrole.member == None:
        return []

    member = govtrack.getMemberOfCongress(user.legstaffrole.member_id)
    if not member["current"]:
        return []
    
    # Create some filters for the district.
    f1 = { "usercomments__state": member["state"] }
    cache_key = "get_legstaff_district_bills#" + member["state"]
    if member["type"] == "rep":
        cache_key += "," + str(member["district"])
        f1["usercomments__congressionaldistrict"] = member["district"]
    
    localbills = cache.get(cache_key)
    if localbills != None:
        return localbills
    
    # Now run an aggregate query to find the total number of comments
    # by bill w/in this district.
    localbills = Bill.objects.filter(**f1) \
        .annotate(num_comments=Count("usercomments")) \
        .filter(num_comments__gt = 2) \
        .order_by("-num_comments") \
        [0:15]
    
    cache.set(cache_key, localbills, 60*60*6) # six hours
    
    return localbills
    
def compute_prompts(user):
    # Compute prompts for action for users by looking at the bills he has commented
    # on, plus trending bills (with a weight).

    # Remove the recommendations that the user has anti-tracked or commented on.
    hidden_bills = set(user.userprofile.antitracked_bills.all().values_list("id", flat=True)) | set(Bill.objects.filter(usercomments__user=user).values_list("id", flat=True))

    targets = {}
    
    # For all active bill recommendations, test if the user matches the segment
    # and add the recommendations. Limit the number we put into the mix.
    from popvox.views.segmentation import UserSegment
    from math import log
    n = 0
    j = 0
    for b2b in BillRecommendation.objects.filter(active=True).order_by('-created'):
        seg = UserSegment.load(b2b.usersegment)
        if seg.matches(user):
            score = 2.0/(1+log(j+1)/4)
            j += 1
            recs = [int(b) for b in b2b.recommendations.split(",")]
            for i, target_bill in enumerate([b for b in recs if b not in hidden_bills]):
                if target_bill in hidden_bills: continue
                if not target_bill in targets: targets[target_bill] = []
                # when a b2b has multiple recommendations, de-weight them by position
                # so they scatter a bit in the UI.
                targets[target_bill].append( (None, score/(1+log(i+1)/4), "b2b", b2b.because) )
                n += 1
                if n == 10: break
            if n == 10: break
                
    # For each source bill, find similar target bills. Remember the similarity
    # and source for each target.
    max_sim = 0
    sb = set(Bill.objects.filter(usercomments__user=user).values_list('id', flat=True))
    for source_bill, target_bill, similarity in chain(
        BillSimilarity.objects.filter(bill1__in=sb).values_list("bill1", "bill2", "similarity").order_by('-similarity')[0:50],
        BillSimilarity.objects.filter(bill2__in=sb).values_list("bill2", "bill1", "similarity").order_by('-similarity')[0:50]):
            
        if target_bill in hidden_bills: continue
        if not target_bill in targets: targets[target_bill] = []
        targets[target_bill].append( (source_bill, similarity, "similarity", None) )
        max_sim = max(similarity, max_sim)
    
    from bills import get_popular_bills
    for bill in get_popular_bills():
        if bill.id not in targets and bill.id not in hidden_bills and bill.billtype != 'x':
            targets[bill.id] = [(None, max_sim/10.0, "trending", None)]
    
    # Put the targets in descending similarity order, summing over the similarity scores used to pick out the target across all sources.
    targets = list(targets.items()) # (target_bill, [list of (source,similarity) pairs]), where source can be null if it is coming from the tending bills list
    targets.sort(key = lambda x : -sum([y[1] for y in x[1]]))
    
    # Map the first N entries from id to Bill objects, filtering out bad suggestions.
    all_bills = set()
    for target_bill, source_sim_pairs in targets:
        all_bills.add(target_bill)
        for source, sim, sugtype, sugdescr in source_sim_pairs:
            if source != None:
                all_bills.add(source)
    all_bills = Bill.objects.in_bulk(all_bills)
    targets_ = []
    for target_bill, source_sim_pairs in targets:
        target_bill = all_bills[target_bill]
        if not target_bill.isAlive(): continue
        if "Super Committee" in target_bill.title: continue # HACK
        targets_.append( (target_bill, [(all_bills[ss[0]] if ss[0] != None else None, ss[1], ss[2], ss[3]) for ss in source_sim_pairs]) )
        if len(targets_) >= 20: break
    targets = targets_
    
    # Replace the list of target sources with just the highest-weighted source for each target.
    for i in xrange(len(targets)):
        targets[i][1].sort(key = lambda x : -x[1])
        targets[i] = { "bill": targets[i][0], "source": targets[i][1][0][0], "type": targets[i][1][0][2], "because": targets[i][1][0][3] }
    
    # targets is now a list of (target, source) pairs.
    
    adorn_bill_stats([item["bill"] for item in targets])
    
    return targets

@csrf_protect
@login_required
def home(request):
    user = request.user
    prof = user.get_profile()
    if prof == None:
        raise Http404()
        

    if user.is_authenticated() and (user.is_staff | user.is_superuser) and "user" in request.GET:
        return individual_dashboard(request)

    if prof.is_leg_staff():
        msgs = get_legstaff_undelivered_messages(user)
        if msgs != None: msgs = len(msgs)
        
        return render_to_response('popvox/home_legstaff_dashboard.html',
            {
                "docket": get_legstaff_suggested_bills(request.user, counts_only=True, include_extras=False),
                "calendar": get_calendar_agenda(user),
                "message_count": msgs,
            },
            context_instance=RequestContext(request))
        
    elif prof.is_org_admin():
        # Get a list of all campaigns in all orgs that the user is an admin
        # of, where the campaign has at least one bill position. Also get
        # a list of all issue areas relevant to the user and all bills.
        cams = []
        bills = []
        issues = []
        for role in prof.user.orgroles.all():
            for ix in role.org.issues.all():
                if not ix in issues:
                    issues.append(ix)
            for cam in role.org.orgcampaign_set.all():
                for p in cam.positions.all():
                    bills.append(p.bill)
                    if not cam in cams:
                        cams.append(cam)
        
        return render_to_response('popvox/home_orgadmin.html',
            {
               'cams': cams,
               "tracked_bills": annotate_track_status(prof, prof.tracked_bills.all()),
               "adserver_targets": ["org_admin_home"],
               },
            context_instance=RequestContext(request))
    else:
        return individual_dashboard(request)


@csrf_protect
@login_required
def docket(request):
    prof = request.user.get_profile()
    if prof == None:
        raise Http404()
        
    if not prof.is_leg_staff():
        raise Http404()

    member = None
    if request.user.legstaffrole.member != None:
        member = govtrack.getMemberOfCongress(request.user.legstaffrole.member_id)
    return render_to_response('popvox/home_legstaff.html',
        {
            "districtstr":
                    "" if member == None or not member["current"] else (
                        "State" if member["type"] == "sen" else "District"
                        ),
            "suggestions": get_legstaff_suggested_bills(request.user, counts_only=True),
            "filternextvotechamber": prof.getopt("home_legstaff_filter_nextvote", ""),
            "adserver_targets": ["leg_staff_home"],
        },
        context_instance=RequestContext(request))

@login_required
@json_response
def legstaff_bill_categories(request):
    prof = request.user.get_profile()
    if prof == None or not prof.is_leg_staff():
        raise Http404()
        
    if "filternextvotechamber" in request.POST and request.POST["filternextvotechamber"] in ("", "h", "s"):
        val = request.POST["filternextvotechamber"]
        if val == "":
            val = None
        request.user.userprofile.setopt("home_legstaff_filter_nextvote", val)
        
    return {
        "status": "success",
        "tabs": get_legstaff_suggested_bills(request.user, counts_only=True)
        }

@login_required
def legstaff_bill_category_panel(request):
    return render_to_response('popvox/home_legstaff_panel.html',
        {
            "group": get_legstaff_suggested_bills(request.user, id=request.POST["id"])[0],
        },
        context_instance=RequestContext(request))
    
def activity(request):
    default_state, default_district = get_default_statistics_context(request.user)
    
    msgs = None
    if request.user.is_authenticated() and request.user.userprofile.is_leg_staff():
        msgs = get_legstaff_undelivered_messages(request.user)
        if msgs != None: msgs = len(msgs)
        
    return render_to_response('popvox/activity.html', {
            "default_state": default_state if default_state != None else "",
            "default_district": default_district if default_district != None else "",
            
            "stateabbrs": 
                [ (abbr, govtrack.statenames[abbr]) for abbr in govtrack.stateabbrs],
            "statereps": govtrack.getStateReps(),
            
            # for leg staff only...
            "message_count": msgs,
        }, context_instance=RequestContext(request))

def activity_getinfo(request):
    format = ""
    
    state = request.REQUEST["state"] if "state" in request.REQUEST and request.REQUEST["state"].strip() != "" else None
    
    district = int(request.REQUEST["district"]) if state != None and "district" in request.REQUEST and request.REQUEST["district"].strip() != "" else None

    if "default-locale" in request.REQUEST:
        def_state, def_district = get_default_statistics_context(request.user)
        state, district = def_state, def_district

    can_see_user_details = False
    if request.user.is_authenticated() and request.user.userprofile.is_leg_staff():
        if request.user.legstaffrole.member != None:
            member = govtrack.getMemberOfCongress(request.user.legstaffrole.member_id)
            if member != None and member["current"]:
                if state == member["state"] and (member["type"] == "sen" or district == member["district"]):
                    can_see_user_details = True
    
    '''return render_to_response('popvox/activity_items' + format + '.html', {
        "items": [],
        "can_see_user_details": can_see_user_details,
        "bill": None,
        #"total_count": total_count,
        }, context_instance=RequestContext(request))''' #this returns an empty activity_getinfo.
    count = 80
    if "count" in request.REQUEST:
        count = int(request.REQUEST["count"])
    
    items = []
    total_count = None
    bill = None

    if request.REQUEST.get("comments", "true") != "false":
        filters = { }
        if state != None:
            filters["state"] = state
            if district != None:
                filters["congressionaldistrict"] = district
        
        if "bill" in request.REQUEST:
            bill = Bill.objects.get(id = request.REQUEST["bill"])
            filters["bill"] = bill
            format = "_bill"
        
        q = UserComment.objects.filter(
            message__isnull=False, 
            status__in=(UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED),
            **filters) \
            .select_related("user", "bill", "address") \
            .order_by('-created')[0:count]

        #if format == "_bill":
        #    total_count = q.count()
    
        #q = q[0:count]

        # batch load all of the appreciations
        c_id = {}
        for c in q:
            c_id[c.id] = c
            c.appreciates = 0 # in case comment has none, see next comment
        for c in UserComment.objects.filter(
            id__in=c_id.keys(), # putting a filter on diggs eliminates comments without any diggs
            diggs__diggtype=UserCommentDigg.DIGG_TYPE_APPRECIATE) \
            .annotate(appreciates=Count('diggs')):
            c_id[c.id].appreciates = c.appreciates
        
        items.extend(q)
    
    if state == None and district == None and format != "_bill":
        items.extend( Org.objects.filter(visible=True, createdbyus=False).exclude(slug="demo").order_by('-updated')[0:count] )
        items.extend( OrgCampaign.objects.filter(visible=True, default=False, org__visible=True, org__createdbyus=False).exclude(org__slug="demo").order_by('-updated')[0:count] )
        items.extend( OrgCampaignPosition.objects.filter(campaign__visible=True, campaign__org__visible=True, campaign__org__createdbyus=False).exclude(campaign__org__slug="demo").order_by('-updated')[0:count] )
        items.extend( PositionDocument.objects.filter(owner_org__visible=True, owner_org__createdbyus=False).exclude(owner_org__slug="demo").order_by('-updated')[0:count] )
        
        items.sort(key = lambda x : x.updated, reverse=True)
        items = items[0:count]
        
    if request.user.is_authenticated():
        annotate_track_status(request.user.userprofile,
            [item.bill for item in items if type(item)==UserComment])
        
    from popvox.views.bills import can_appreciate 
    for item in items:
        if isinstance(item, UserComment):
            item.can_appreciate = can_appreciate(request, item.bill)

    return render_to_response('popvox/activity_items' + format + '.html', {
        "items": items,
        "can_see_user_details": can_see_user_details,
        "bill": bill,
        #"total_count": total_count,
        }, context_instance=RequestContext(request))

def calendar(request):
    return render_to_response('popvox/legcalendar.html', {
        }, context_instance=RequestContext(request))

def get_calendar_agenda(user):
    chamber = user.legstaffrole.chamber()
    if chamber in ("H", "S"):
        agenda = get_calendar_agenda2(chamber)
    else:
        agenda = get_calendar_agenda2("H", prefix="House")
        agenda = get_calendar_agenda2("S", agenda=agenda, prefix="Senate")

    agenda = [(date, date.strftime("%A"), date.strftime("%b %d").replace(" 0", " "), items) for date, items in agenda.items()]
    agenda.sort(key = lambda x : x[0])
    
    return agenda

def get_calendar_agenda2(chamber, agenda=None, prefix=None):
    if chamber == "H":
        url = "http://www.google.com/calendar/ical/g.popvox.com_a29i4neivhp0ocsrkcd6jf2n30%40group.calendar.google.com/public/basic.ics"
    elif chamber == "S":
        url = "http://www.google.com/calendar/ical/g.popvox.com_dn12o3dcj27brhi8hk4v1ov09o%40group.calendar.google.com/public/basic.ics"
            
    cal = cache.get(url)
    if cal == None:
        import urllib2
        cal = urllib2.urlopen(url).read()
        cache.set(url, cal, 60*60*3) # 3 hours

    from datetime import datetime, date, timedelta
    
    # weird data bug from Google?
    cal = cal.replace("CREATED:00001231T000000Z\r\n", "")
    
    from icalendar import Calendar, Event
    cal = Calendar.from_string(cal)
    
    if agenda == None:
        agenda = { }
    
    for component in cal.walk():
        if "summary" in component:
            descr = component["summary"]
        elif "description" in component:
            descr = component["description"]
        else:
            continue
        if not "dtstart" in component or not "dtend" in component:
            continue
        dstart = component.decoded("dtstart")
        dend = component.decoded("dtend")
        
        if prefix != None:
            descr = prefix + ": " + descr
        
        # We're not interested in times right now...
        
        if isinstance(dstart, datetime): dstart = dstart.date()
        if isinstance(dend, datetime): dend = dend.date()
        
        if dend < datetime.now().date():
            continue
        
        while dstart < dend: # end date is exclusive
            if dstart >= datetime.now().date() and dstart <= datetime.now().date()+timedelta(days=5):
                if dstart not in agenda:
                    agenda[dstart] = []
                agenda[dstart].append({"description": descr})
            dstart = dstart + timedelta(days=1)
        
    return agenda

@user_passes_test(lambda u : u.is_authenticated() and (u.is_staff | u.is_superuser))
def testing(request):
    try:
        return render_to_response("testing.html", context_instance=RequestContext(request))
    except TemplateDoesNotExist:
        raise Http404()

@user_passes_test(lambda u : u.is_authenticated() and (u.is_staff | u.is_superuser))
def waiting_for_reintroduction(request):
    bills = { }
    
    # Quickly find non-staff users tracking any bill introduced in a previous congress.
    for user in UserProfile.objects.filter(allow_mass_mails=True, tracked_bills__congressnumber__lt = popvox.govtrack.CURRENT_CONGRESS, user__orgroles__isnull = True, user__legstaffrole__isnull = True).distinct(): # weird that we need a distinct here
        for bill in user.tracked_bills.filter(congressnumber__lt = popvox.govtrack.CURRENT_CONGRESS).distinct():
            if not bill in bills:
                bills[bill] = []
            bills[bill].append(user)
    
    bills = list(bills.items())
    bills.sort(key = lambda kv : len(kv[1]), reverse = True)
    
    return render_to_response('popvox/waiting_for_reintroduction.html', {
        "bills": bills,
        }, context_instance=RequestContext(request))
    
@user_passes_test(lambda u : u.is_authenticated() and (u.is_staff | u.is_superuser))
def delivery_status_report(request):
    from writeyourrep.models import Endpoint, DeliveryRecord
    report = []
    totals = [0, 0, 0]
    for moc in sorted(popvox.govtrack.getMembersOfCongress(), key = lambda m : m["type"] == "rep"):
        moc = dict(moc) # clone
        report.append(moc)
        
        try:
            ep = Endpoint.objects.get(govtrackid=moc["id"], office=moc["office_id"])
        except Endpoint.DoesNotExist:
            moc["delivery_status"] = "No Endpoint Defined"
            continue
            
        moc["endpoint"] = ep.id
            
        d = DeliveryRecord.objects.filter(target=ep, next_attempt__isnull=True)
        d_delivered = d.filter(success=True)
        d_delivered_electronically = d_delivered.exclude(method=Endpoint.METHOD_INPERSON)
            
        d = d.count()
        if d == 0:
            moc["delivery_status"] = "No messages/No method?"
        else:
            d_delivered = d_delivered.count()
            d_delivered_electronically = d_delivered_electronically.count()
            
            ratio = float(d_delivered_electronically) / float(d)
            ratio = int(100.0*(1.0-ratio))
            
            if ratio <= 1:
                moc["delivery_status"] = "OK!"
            elif ratio < 5:
                moc["delivery_status"] = "OK! (Mostly)"
            else:
                moc["delivery_status"] = "%s%% fail" % ratio
    
            moc["breaks"]  = " %d electronically/%d delivered/%d written" % (d_delivered_electronically, d_delivered, d)
        
            totals[0] += d_delivered_electronically
            totals[1] += d_delivered
            totals[2] += d

        if ep.method == Endpoint.METHOD_NONE and ep.tested:
            moc["delivery_status"] = "No Electronic Method"
            
    return render_to_response('popvox/delivery_status_report.html', {
        "report": report,
        "delivered_pct": int(float(totals[1])/float(totals[2])*100.0),
        "delivered_electronically_pct": int(float(totals[0])/float(totals[1])*100.0),
        "total_count": totals[2],
        }, context_instance=RequestContext(request))
    
def get_legstaff_undelivered_messages(user):
    # Return None if the account does not have access to download messages.
    # Otherwise return a QuerySet of the messages in this person's office's
    # district that have not been successfully delivered to the office (and are
    # not in an offline batch).
    
    role = user.legstaffrole
    if not role.verified or role.member == None:
        return None

    member = role.member.info()
    if not member["current"]:
        return None
    
    filters = { }    
    filters["state"] = member["state"]
    if member["type"] == "rep":
        filters["congressionaldistrict"] = member["district"]
        
    # Return undelivered messages that are also not queued for off-line delivery.
    q = UserComment.objects.filter(
            created__gt = datetime.now() - timedelta(days=60),
            **filters
        ).exclude(
            delivery_attempts__success=True,
            delivery_attempts__target__govtrackid=role.member.id,
        ).exclude(
            usercommentofflinedeliveryrecord__target=role.member,
            usercommentofflinedeliveryrecord__batch__isnull=False
        ).select_related()
    
    def deliv(m):
        # the time limit is also set in send_messages.py, should really go in
        # get_recipients.
        if m.message == None and m.updated < datetime.now()-timedelta(days=31): return False
        r = m.get_recipients()
        if not isinstance(r, (tuple,list)): return False
        return member in r
    return [m for m in q if deliv(m)]

@csrf_protect
@user_passes_test(lambda u : u.is_authenticated() and u.userprofile.is_leg_staff())
def legstaff_download_messages(request):
    msgs = get_legstaff_undelivered_messages(request.user)
    if msgs == None: # no access to messages
        return render_to_response('popvox/legstaff_download_messages.html', {
            "access": "denied",
            }, context_instance=RequestContext(request))
        
    from writeyourrep.models import Endpoint, DeliveryRecord
    from datetime import datetime

    member_id = request.user.legstaffrole.member.id
    office_id = govtrack.getMemberOfCongress(member_id)["office_id"]
    
    date_format = "%Y-%m-%d %H:%M:%S.%f"
    
    if request.POST.get("clear", "") == "Return to Queue":
        # On the previous attempt record, reset the next attempt field.
        DeliveryRecord.objects.filter(
                next_attempt__success=True,
                next_attempt__target__govtrackid=member_id,
                next_attempt__target__office=office_id,
                next_attempt__method=Endpoint.METHOD_STAFFDOWNLOAD,
                next_attempt__created = request.POST["date"]
                ).update(next_attempt=None)
        
        # And delete the actual download record.
        DeliveryRecord.objects.filter(
                success=True,
                target__govtrackid=member_id,
                target__office=office_id,
                method=Endpoint.METHOD_STAFFDOWNLOAD,
                created = request.POST["date"]
                ).delete()
    
    elif "date" in request.POST:
        if request.POST["date"] == "new":
            # we already queried above
            is_new = True
            download_date = datetime.now()
        else:
            msgs = UserComment.objects.filter(
                delivery_attempts__success=True,
                delivery_attempts__target__govtrackid=member_id,
                delivery_attempts__target__office=office_id,
                delivery_attempts__method=Endpoint.METHOD_STAFFDOWNLOAD,
                delivery_attempts__created = request.POST["date"]
                ).select_related("address")
            is_new = False
            download_date = datetime.strptime(request.POST["date"], date_format)
            
        #msgs = msgs.order_by('created')
        msgs.sort(key = lambda c : c.created)
            
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(mimetype='text/csv')
        response['Content-Disposition'] = 'attachment; filename=constituent_messages_' + download_date.strftime("%Y-%m-%d_%H%M").strip() + '.csv'
    
        writer = csv.writer(response)
        writer.writerow(['pvcid', 'date', 'subject', 'topic_code', 'prefix', 'firstname', 'lastname', 'suffix', 'address1', 'address2', 'city', 'state', 'zipcode', 'phonenumber', 'district', 'email', 'message', 'referrer'])
        for comment in msgs:
            
            topic_code = "http://popvox.com" + comment.bill.url() + "#" + ("support" if comment.position == "+" else "oppose")
            campaign_id = ""
            
            # take the first referrer
            comment.referrer = None
            for ref in comment.referrers():
                comment.referrer = ref
                break
            if comment.referrer != None and isinstance(comment.referrer, Org):
                if comment.referrer.website == None:
                    campaign_id = "http://popvox.com" + comment.referrer.url()
                else:
                    campaign_id = comment.referrer.website
            elif comment.referrer != None and isinstance(comment.referrer, OrgCampaign):
                if comment.referrer.website_or_orgsite() == None:
                    campaign_id = "http://popvox.com" + comment.referrer.url()
                else:
                    campaign_id = comment.referrer.website_or_orgsite()
            
            writer.writerow([
                comment.id,
                comment.updated,
                comment.bill.hashtag() + " " + ("support" if comment.position=="+" else "oppose"),
                topic_code,
                
                comment.address.nameprefix.encode("utf8"),
                comment.address.firstname.encode("utf8"),
                comment.address.lastname.encode("utf8"),
                comment.address.namesuffix.encode("utf8"),
                comment.address.address1.encode("utf8"),
                comment.address.address2.encode("utf8"),
                comment.address.city.encode("utf8"),
                comment.address.state.encode("utf8"),
                comment.address.zipcode.encode("utf8"),
                comment.address.phonenumber.encode("utf8"),
                comment.address.congressionaldistrict,

                comment.user.email.encode("utf8"),
                comment.message.encode("utf8") if comment.message != None else "(This user chose not to write a personal message.)",
                campaign_id,
                ])

            if is_new:
                dr = DeliveryRecord()
                dr.target = Endpoint.objects.get(govtrackid=member_id, office=office_id)
                dr.trace = """comment #%d delivered via staff download by %s
                
email: %s
IP: %s
UA: %s
""" % (comment.id, request.user.username, request.user.email, request.META.get("REMOTE_ADDR", ""), request.META.get("HTTP_USER_AGENT", ""))
                
                
                dr.success = True
                dr.failure_reason = DeliveryRecord.FAILURE_NO_FAILURE
                dr.method = Endpoint.METHOD_STAFFDOWNLOAD
                dr.save()

                # explicitly set all of the records to the same date to group the batch
                dr.created = download_date
                dr.save()

                try:
                    prev_dr = comment.delivery_attempts.get(target__govtrackid = member_id, next_attempt__isnull = True)
                    prev_dr.next_attempt = dr
                    prev_dr.save()
                except DeliveryRecord.DoesNotExist:
                    pass
                
                comment.delivery_attempts.add(dr)

        return response
    
    delivered_message_dates = DeliveryRecord.objects.filter(
                success=True,
                target__govtrackid=member_id,
                target__office=office_id,
                method=Endpoint.METHOD_STAFFDOWNLOAD).values_list("created", flat=True).distinct().order_by('-created')
    delivered_message_dates = [(d, d.strftime(date_format)) for d in delivered_message_dates]

    return render_to_response('popvox/legstaff_download_messages.html', {
        "new_messages": len(msgs),
        "delivered_message_dates": delivered_message_dates,
        }, context_instance=RequestContext(request))
        
#function to get pro and con positions for bills, to pass in for pie charts:
def GetSentiment(member, bills_list):
    bills_sentiment = []
    for bill in bills_list:
        scope = None
        total = 0
        try:
            if member['district']:
                scope = "district"
                total = bill.usercomments.get_query_set().filter(state=member['state'],congressionaldistrict=member['district']).count()
                if total != 0:
                    pro = (100.0) * bill.usercomments.get_query_set().filter(position="+",state=member['state'],congressionaldistrict=member['district']).count()/total
                    con = (100.0) * bill.usercomments.get_query_set().filter(position="-",state=member['state'],congressionaldistrict=member['district']).count()/total
            elif member['state']:
                scope = "state"
                total = bill.usercomments.get_query_set().filter(state=member['state']).count()
                if total != 0:
                    pro = (100.0) * bill.usercomments.get_query_set().filter(position="+",state=member['state']).count()/total
                    con = (100.0) * bill.usercomments.get_query_set().filter(position="-",state=member['state']).count()/total
            else: #in case there's an error where a member is set to state and district both being none
                total = 0
        except KeyError:
            total = 0
        
        '''if total < 6 :
            scope = "nation"
            total = bill.usercomments.get_query_set().count()
            if total != 0:
                pro = (100.0) * bill.usercomments.get_query_set().filter(position="+").count()/total
                con = (100.0) * bill.usercomments.get_query_set().filter(position="-").count()/total'''
        if total < 4:
            pro = None
            con = None

        foo = (bill, scope, pro, con,total)
        bills_sentiment.append(foo)
    return bills_sentiment

@json_response
def getsponsoredbills(request):
    
    memberid = request.POST["memberid"]
    
    start = int(request.REQUEST.get("start", "0"))
    limit = int(request.REQUEST.get("count", "50"))

    # Get sponsored bills
    sponsored_bills_list = popvox.models.Bill.objects.filter(sponsor=memberid,congressnumber = popvox.govtrack.CURRENT_CONGRESS)
    
    sponsored_bills = GetSentiment(govtrack_data, sponsored_bills_list)
    sponsored_bills = sorted(sponsored_bills, key=lambda bills: bills[4], reverse=True)
    
    limited = False
    if sponsored_bills.count() > limit:
        sponsored_bills = sponsored_bills[start:limit]
        limited = True
    else:
        sponsored_bills = sponsored_bills[start:]

    
    return sponsored_bills
    
@json_response
def getcosponsoredbills(request):
    
    # Get cosponsored bills
    cosponsored_bills_list = popvox.models.Bill.objects.filter(cosponsors=member.id,congressnumber = popvox.govtrack.CURRENT_CONGRESS)

    cosponsored_bills = GetSentiment(govtrack_data, cosponsored_bills_list)
    cosponsored_bills = sorted(cosponsored_bills, key=lambda bills: bills[4], reverse=True)[0:20]
    return none

def member_page(request, membername=None):
    user = request.user
    memberid = None
    member = None
    
    try:
        memberid = MemberBio.objects.get(pvurl=membername).id
        member = MemberOfCongress.objects.get(id=memberid)
        
    except (MemberBio.DoesNotExist, KeyError):
        raise Http404()
        #Now that we have all the members ever, supporting url-hacking is too hard.
        membername = membername.replace("-"," ")
        list = MemberOfCongress.objects.all()
        for mem in list:
            if (re.search(membername.lower(),mem.name().lower())):
                splitstring = str(mem).split(" ")
                member = mem
                
    if member is None:
        raise Http404()
    if not member.info()['current']:
        raise Http404()
    
    memberids = [member.id] #membermatch needs a list
    
    #Social media links and bio info from the sunlight API (and our own db, where necessary)
    mem_data = {}
    try:
        #url = "http://services.sunlightlabs.com/api/legislators.get.json?apikey=2dfed0d65519430593c36b031f761a11&govtrack_id="+str(member.id)
        url = "http://congress.api.sunlightfoundation.com/legislators?apikey=2dfed0d65519430593c36b031f761a11&&govtrack_id=\""+str(member.id)+"\""
        json_data = "".join(urllib2.urlopen(url).readlines())
        loaded_data = json.loads(json_data)
        mem_data = loaded_data['results'][0]
    except (urllib2.HTTPError, IndexError):
        pass

    if 'youtube_url' in mem_data and mem_data['youtube_url'] != "":
        youtube_id = mem_data['youtube_url'].rsplit("/",1)[1]
        url = "http://gdata.youtube.com/feeds/base/users/"+youtube_id+"/uploads?alt=rss&amp;v=2&amp;orderby=published&amp;"
        try:
            rss_data = "".join(urllib2.urlopen(url).readlines())
            mem_data['last_vid'] = None
            dom = parseString(rss_data)
            first = dom.getElementsByTagName('item')[0]
            guid = first.getElementsByTagName('guid')[0]
            mem_data['last_vid'] = guid.firstChild.data.rsplit("/",1)[1]
        except (IndexError, urllib2.HTTPError):
            pass
        
    if 'birthday' in mem_data:
        birthdate = datetime.strptime(mem_data['birthday'],"%Y-%m-%d").date()
        today = date.today()
        try: # raised when birth date is February 29 and the current year is not a leap year
            birthday = birthdate.replace(year=today.year)
        except ValueError:
            birthday = birthdate.replace(year=today.year, day=born.day-1)
        if birthday > today:
            age = today.year - birthdate.year - 1
        else:
            age = today.year - birthdate.year
        mem_data['birthday'] = datetime.strptime(mem_data['birthday'],"%Y-%m-%d")
    if 'age' in mem_data:
        mem_data['age'] = age
    
    bio = popvox.models.MemberBio.objects.get(id=member.id)
    mem_data['flickr_id'] = bio.flickr_id
    mem_data['googleplus'] = bio.googleplus
        

    govtrack_data = popvox.govtrack.getMemberOfCongress(member.id)
    committees = []
    if 'committees' in govtrack_data:
        for committee in govtrack_data['committees']:
            name = popvox.govtrack.getCommittee(committee)['name']
            committees.append(name)
    mem_data['committees'] = committees
    
    #checking if we have the member's picture:
    if 'gender' in mem_data:
        mem_data["gender"] = mem_data["gender"].lower()
    if not os.path.isfile("/home/www/sources/site/static/member_photos/"+str(member.id)+"-200px.jpeg"):
        mem_data["nophoto"] = True
    
    
    #membermatch runs all the comparison logic between the user's comments and the member's votes.
    #uncomment when we're ready to add membermatch to the member page.
    '''membermatch = popvox.match.membermatch(memberids, user)
    billvotes = membermatch[0]
    stats = membermatch[1]
    had_abstain = membermatch[2]'''
    
    # Get sponsored and cosponsored bills
    sponsored_bills_list = popvox.models.Bill.objects.filter(sponsor=member.id,congressnumber = popvox.govtrack.CURRENT_CONGRESS)
    cosponsored_bills_list = popvox.models.Bill.objects.filter(cosponsors=member.id,congressnumber = popvox.govtrack.CURRENT_CONGRESS)
    

    sponsored_bills = GetSentiment(govtrack_data, sponsored_bills_list)
    cosponsored_bills = GetSentiment(govtrack_data, cosponsored_bills_list)
    sponsored_bills = sorted(sponsored_bills, key=lambda bills: bills[4], reverse=True)[0:20]
    cosponsored_bills = sorted(cosponsored_bills, key=lambda bills: bills[4], reverse=True)[0:20]

    stateabbrs = [ (abbr, govtrack.statenames[abbr]) for abbr in govtrack.stateabbrs]

    return render_to_response('popvox/memberpage.html', {'memdata' : mem_data, 'member': member, 'sponsored': sponsored_bills, 'cosponsored': cosponsored_bills, "stateabbrs": stateabbrs},
        context_instance=RequestContext(request))
    
    #This return has the membermatch variables; uncomment when we're ready for them
    '''return render_to_response('popvox/memberpage.html', {'memdata' : mem_data, 'billvotes': billvotes, 'member': member, 'stats': stats, 'had_abstain': had_abstain, 'sponsored': sponsored_bills, 'cosponsored': cosponsored_bills},
    context_instance=RequestContext(request))'''

@login_required
def delete_account(request):
    user = request.user
    prof = user.get_profile()
        
    if prof.is_leg_staff():
        raise Http404()
        
    elif prof.is_org_admin():
        raise Http404()
    
    else:
        return render_to_response('popvox/delete_account.html', {},
        
    context_instance=RequestContext(request))
  

def district_info(request, searchstate=None, searchdistrict=None):
    trending = get_popular_bills2(searchstate.upper(), searchdistrict) 
    
    trending_bills = []
    
    if searchdistrict:
        for bill in trending:
            total = bill['bill'].usercomments.get_query_set().filter(state=searchstate,congressionaldistrict=searchdistrict).count()
            if total >=4:
                pro = (100.0) * bill['bill'].usercomments.get_query_set().filter(position="+",state=searchstate,congressionaldistrict=searchdistrict).count()/total
                con = (100.0) * bill['bill'].usercomments.get_query_set().filter(position="-",state=searchstate,congressionaldistrict=searchdistrict).count()/total
            else:
                pro = None
                con = None
            foo = (bill, pro, con,total)
            trending_bills.append(foo)
    else:
        for bill in trending:
            total = bill['bill'].usercomments.get_query_set().filter(state=searchstate).count()
            if total >=4:
                pro = (100.0) * bill['bill'].usercomments.get_query_set().filter(position="+",state=searchstate).count()/total
                con = (100.0) * bill['bill'].usercomments.get_query_set().filter(position="-",state=searchstate).count()/total
            else:
                pro = None
                con = None
            foo = (bill, pro, con,total)
            trending_bills.append(foo)

    trending_bills = sorted(trending_bills, key=lambda bills: bills[3], reverse=True)
    if searchdistrict:
        print "in here!"
        if int(searchdistrict) == 0:
            sd = searchstate.upper()+str(searchdistrict)
        else:
            sd = searchstate.upper()+str(searchdistrict).lstrip('0')

        members = popvox.govtrack.getMembersOfCongressForDistrict(sd)
        members = sorted(members, key=lambda member: member['type']) #sorting so reps come before senators on the district page
        try:
            print "now here!"
	        # FIXME when there's census data
            #censusdata = popvox.models.CensusData.objects.get(id=sd)
            censusdata = popvox.models.CensusData.objects.get(id=searchstate)
            maxdist = popvox.govtrack.stateapportionment[searchstate.upper()] 
            print "searchdistrict: "+str(searchdistrict)
            print "maxdist: "+str(maxdist)
            if int(searchdistrict) > int(maxdist):
                print "wtf"
                raise Http404()
	    
        except:
            raise Http404()
	    pass
    else:
        members = popvox.govtrack.getMembersOfCongressForState(searchstate.upper())
        members = sorted(members, key=lambda member: member['type'],reverse=True) #sorting so reps come before senators on the district page
        try:
            censusdata = popvox.models.CensusData.objects.get(id=searchstate)
        except:
            raise Http404()
    

    for member in members:
        member['pvurl'] = popvox.models.MemberBio.objects.get(id=member['id']).pvurl

    filters = {}
    filters["state"] = searchstate
    if searchdistrict:
        filters["congressionaldistrict"] = searchdistrict
    popular = Bill.objects.filter(congressnumber = popvox.govtrack.CURRENT_CONGRESS)\
        .filter(**dict( ("usercomments__"+k,v) for k,v in filters.items() ))\
        .annotate(count=Count('usercomments'))\
        .order_by('-count')\
        [0:10]

    popular_bills = []
    if searchdistrict:
        for bill in popular:
            total = bill.usercomments.get_query_set().filter(state=searchstate,congressionaldistrict=searchdistrict).count()
            if total >=4:
                pro = (100.0) * bill.usercomments.get_query_set().filter(position="+",state=searchstate,congressionaldistrict=searchdistrict).count()/total
                con = (100.0) * bill.usercomments.get_query_set().filter(position="-",state=searchstate,congressionaldistrict=searchdistrict).count()/total
            else:
                pro = None
                con = None
            
            foo = (bill, pro, con,total)
            popular_bills.append(foo)
    else:
        for bill in popular:
            total = bill.usercomments.get_query_set().filter(state=searchstate).count()
            if total >=4:
                pro = (100.0) * bill.usercomments.get_query_set().filter(position="+",state=searchstate).count()/total
                con = (100.0) * bill.usercomments.get_query_set().filter(position="-",state=searchstate).count()/total
            else:
                pro = None
                con = None
            
            foo = (bill, pro, con,total)
            popular_bills.append(foo)
    popular_bills = sorted(popular_bills, key=lambda bills: bills[3], reverse=True)
    
    statename = govtrack.statenames[searchstate.upper()]
    diststateabbrs = [ (abbr, govtrack.statenames[abbr]) for abbr in govtrack.stateabbrs]
    
    
    for state in diststateabbrs:
      if state[0] in ['AS', 'GU', 'MP', 'VI']:
          diststateabbrs.remove(state)
        
    return render_to_response('popvox/districtinfo.html', {"state":searchstate.upper(),"district":str(searchdistrict),"members":members,"trending_bills": trending_bills, "popular_bills": popular_bills, "census_data": censusdata, "diststateabbrs": diststateabbrs, "statename": statename, "show_share_footer":True},
    context_instance=RequestContext(request))
    
def new_district_info(request, searchstate=None, searchdistrict=None, csv=False):
    newdist = True
    trending = get_popular_bills2(searchstate.upper(), searchdistrict, newdist) 
    
    trending_bills = []
    
    for bill in trending:
        total = bill['bill'].usercomments.get_query_set().filter(state=searchstate,address__congressionaldistrict2013=searchdistrict).count()
        if total >=4:
            pro = (100.0) * bill['bill'].usercomments.get_query_set().filter(position="+",state=searchstate,address__congressionaldistrict2013=searchdistrict).count()/total
            con = (100.0) * bill['bill'].usercomments.get_query_set().filter(position="-",state=searchstate,address__congressionaldistrict2013=searchdistrict).count()/total
        else:
            pro = None
            con = None
        foo = (bill, pro, con,total)
        trending_bills.append(foo)

    trending_bills = sorted(trending_bills, key=lambda bills: bills[3], reverse=True)

    filters = {}
    filters["state"] = searchstate
    filters["congressionaldistrict"] = searchdistrict
    popular = Bill.objects.filter(congressnumber = popvox.govtrack.CURRENT_CONGRESS)\
    .filter(**dict( ("usercomments__"+k,v) for k,v in filters.items() ))\
    .annotate(count=Count('usercomments'))\
    .order_by('-count')\
    [0:10]

    popular_bills = []
    for bill in popular:
        total = bill.usercomments.get_query_set().filter(state=searchstate,address__congressionaldistrict2013=searchdistrict).count()
        if total >=4:
            pro = (100.0) * bill.usercomments.get_query_set().filter(position="+",state=searchstate,address__congressionaldistrict2013=searchdistrict).count()/total
            con = (100.0) * bill.usercomments.get_query_set().filter(position="-",state=searchstate,address__congressionaldistrict2013=searchdistrict).count()/total
        else:
            pro = None
            con = None
        
        foo = (bill, pro, con,total)
        popular_bills.append(foo)

    popular_bills = sorted(popular_bills, key=lambda bills: bills[3], reverse=True)
    
    statename = govtrack.statenames[searchstate.upper()]
    diststateabbrs = [ (abbr, govtrack.statenames[abbr]) for abbr in govtrack.stateabbrs]


    for state in diststateabbrs:
      if state[0] in ['AS', 'GU', 'MP', 'VI']:
          diststateabbrs.remove(state)
    if csv == False:    
        return render_to_response('popvox/newdistrictinfo.html', {"state":searchstate.upper(),"district":str(searchdistrict),"trending_bills": trending_bills, "popular_bills": popular_bills, "diststateabbrs": diststateabbrs, "statename": statename, "show_share_footer":True},
        context_instance=RequestContext(request))
    else:
        r = render_to_response('popvox/newdistrictbills.csv', {"state":searchstate.upper(),"district":str(searchdistrict),"trending_bills": trending_bills, "popular_bills": popular_bills, "diststateabbrs": diststateabbrs, "statename": statename},
        context_instance=RequestContext(request))
        r['Content-Disposition'] = 'attachment; filename="'+searchstate.upper()+searchdistrict+'.csv"'
        return r
        
def district_archive(request, searchstate=None, searchdistrict=None, archive=None):
    if archive == str(2012):
        congress = 112
        archived = True
    else:
        raise Http404()
    
    #TODO: when we transfer the new districts into the congressionaldistrict column, we'll need to change the congressionaldistrict queries below to congressionaldistrict2003
    trending = get_popular_bills2(searchstate.upper(), searchdistrict) 
    
    trending_bills = []
    
    for bill in trending:
        total = bill['bill'].usercomments.get_query_set().filter(state=searchstate,congressionaldistrict=searchdistrict).count()
        if total >=4:
            pro = (100.0) * bill['bill'].usercomments.get_query_set().filter(position="+",state=searchstate,congressionaldistrict=searchdistrict).count()/total
            con = (100.0) * bill['bill'].usercomments.get_query_set().filter(position="-",state=searchstate,congressionaldistrict=searchdistrict).count()/total
        else:
            pro = None
            con = None
        foo = (bill, pro, con,total)
        trending_bills.append(foo)

    trending_bills = sorted(trending_bills, key=lambda bills: bills[3], reverse=True)

    if int(searchdistrict) == 0:
        sd = searchstate.upper()+str(searchdistrict)
    else:
        sd = searchstate.upper()+str(searchdistrict).lstrip('0')
    
    #TODO: we need to change this query to pull *historic* members of congress (for the archive year).
    members = popvox.govtrack.getMembersOfCongressForDistrict(sd)
    members = sorted(members, key=lambda member: member['type']) #sorting so reps come before senators on the district page
    try:
        censusdata = popvox.models.CensusData.objects.get(id=sd)
        #TODO: we need to store old and new census data, so we'll probably need to change the primary key on the census table.
    except:
        raise Http404()

    for member in members:
        member['pvurl'] = popvox.models.MemberBio.objects.get(id=member['id']).pvurl

    filters = {}
    filters["state"] = searchstate
    filters["congressionaldistrict"] = searchdistrict

    
    popular = Bill.objects.filter(congressnumber = 112)\
        .filter(**dict( ("usercomments__"+k,v) for k,v in filters.items() ))\
        .annotate(count=Count('usercomments'))\
        .order_by('-count')\
        [0:10]

    popular_bills = []
    for bill in popular:
        total = bill.usercomments.get_query_set().filter(state=searchstate,congressionaldistrict=searchdistrict).count()
        if total >=4:
            pro = (100.0) * bill.usercomments.get_query_set().filter(position="+",state=searchstate,congressionaldistrict=searchdistrict).count()/total
            con = (100.0) * bill.usercomments.get_query_set().filter(position="-",state=searchstate,congressionaldistrict=searchdistrict).count()/total
        else:
            pro = None
            con = None
        
        foo = (bill, pro, con,total)
        popular_bills.append(foo)

    popular_bills = sorted(popular_bills, key=lambda bills: bills[3], reverse=True)
    
    statename = govtrack.statenames[searchstate.upper()]
    diststateabbrs = [ (abbr, govtrack.statenames[abbr]) for abbr in govtrack.stateabbrs]
    
    
    for state in diststateabbrs:
      if state[0] in ['AS', 'GU', 'MP', 'VI']:
          diststateabbrs.remove(state)
        
    return render_to_response('popvox/districtinfo.html', {"archive":archive,"archived":archived,"state":searchstate.upper(),"district":str(searchdistrict),"members":members,"trending_bills": trending_bills, "popular_bills": popular_bills, "census_data": censusdata, "diststateabbrs": diststateabbrs, "statename": statename, "show_share_footer":True},
    context_instance=RequestContext(request))
    
def unsubscribe_me_makehash(email):
    from settings import SECRET_KEY, SITE_ROOT_URL
    import hashlib
    sha = hashlib.sha1()
    sha.update(SECRET_KEY)
    sha.update(email)
    return sha.hexdigest()
    
def unsubscribe_me(request):
    email = request.GET.get("email", "---invalid---")
    key = request.GET.get("key", "")
    
    if key != unsubscribe_me_makehash(email):
        return HttpResponse("You have followed an invalid link.")
    
    try:
        u = User.objects.get(email=email)
    except User.DoesNotExist:
        return HttpResponse("You have followed an invalid link.")
        
    p = u.userprofile
    p.allow_mass_mails = False
    p.save()
    
    return HttpResponse("You have been unsubscribed.")

@login_required
def delete_account_confirmed(request):
    user = request.user
    prof = user.get_profile()
        
    if prof.is_leg_staff():
        raise Http404()
        
    elif prof.is_org_admin():
        raise Http404()
    
    else:
        return render_to_response('popvox/delete_account_confirmed.html', {},
        
    context_instance=RequestContext(request))
    
@strong_cache
def spotlight(request, year, month, day, slug):
    #TODO:
    #add a slug field to the BillList model. And while we're messing with it, an optional organization (for slates).
    try:
        spotlight = BillList.objects.get(slug=slug, date__year=year, date__month=month, date__day=day)
    except:
        raise Http404()

    return render_to_response('popvox/spotlight.html', {"spotlight": spotlight},
        
    context_instance=RequestContext(request))
    
@strong_cache
def gettoknow(request):
  
    stateabbrs = [ (abbr, govtrack.statenames[abbr]) for abbr in govtrack.stateabbrs]
    diststateabbrs = stateabbrs[:]
    for state in diststateabbrs:
      if state[0] in ['AS', 'GU', 'MP', 'VI']:
        diststateabbrs.remove(state)

    all_members = govtrack.getMembersOfCongress()
    members = []
    for member in all_members:
        if member['current'] == True:
            mem = popvox.models.MemberOfCongress.objects.get(id=member['id'])
            member['pvurl'] = popvox.models.MemberBio.objects.get(id=member['id']).pvurl

            loaded_data=[]
            try:
                url = "http://services.sunlightlabs.com/api/legislators.get.json?apikey=2dfed0d65519430593c36b031f761a11&govtrack_id="+str(member['id'])
                json_data = "".join(urllib2.urlopen(url).readlines())
                loaded_data = json.loads(json_data)
                mem_data = loaded_data['response']['legislator']
            except urllib2.HTTPError:
                pass

            member['plain_name'] = mem_data['title']+" "+mem_data['firstname']+" "+mem_data['lastname']
            if mem_data['chamber'] == "house":
                member['party_state'] = "("+mem_data['party']+", "+mem_data['state']+"-"+mem_data['district']+")"
            else:
                member['party_state'] = "("+mem_data['party']+", "+mem_data['state']+")"
            members.append(member)


    return render_to_response('popvox/gettoknow.html', {"stateabbrs": stateabbrs, "diststateabbrs": diststateabbrs, "members": members},
        
    context_instance=RequestContext(request))
    
@json_response    
def recommend_from_text(request):
    q = request.GET.get("q", "").strip()
    if q == "": return { "autocomplete": None, "bills": [] }
    
    q = re.sub(r"\s+", " ", q)
    
    # Recommend bills based on a short English phrase like "I lost my job."
    
    from sphinxapi import SphinxClient, SPH_MATCH_PHRASE, SPH_MATCH_ANY
    from django.template.defaultfilters import truncatewords, escape

    c = SphinxClient()
    c.SetServer("localhost" if not "REMOTEDB" in os.environ else os.environ["REMOTEDB"], 3312)
    c.SetFilter("congressnumber", [popvox.govtrack.CURRENT_CONGRESS])
    
    def fetch_dict(model, ids, only=[]):
        objs = model.objects.filter(id__in=ids)
        if only:
            objs = objs.only(*only)
        if model == Bill: # count up total comments
            objs = objs.annotate(comment_count=Count('usercomments'))
        return dict((obj.id, obj) for obj in objs)
    
    def pull_bills(bill_list):
        # bulk transform the bill ids into url and title, prune bills
        # that are not alive for commenting, and sort by total comments
        # left on the bill.
        bills = fetch_dict(Bill, [b["bill"] for b in bill_list])
        for b in bill_list:
            if b["bill"] in bills:
                bill = bills[b["bill"]]
                if bill.isAlive() or True:
                    b["url"] = bill.url()
                    b["name"] = bill.nicename
                    b["comment_count"] = bill.comment_count
                    continue
            b["bill"] = None
        bills = [b for b in bill_list if b["bill"] != None]
        bills.sort(key = lambda x : (-x["sort_group"], x["hit_count"], x["comment_count"]), reverse=True)
        return bills
    
    autocomplete = None
    prompts = []
    bills = { }

    # First try to match exact strings against the index of user comments.
    # Use the string match to fill an autocomplete.
    
    for sort_group, match_mode in [(0, SPH_MATCH_PHRASE), (1, SPH_MATCH_ANY)]:
        c.SetMatchMode(match_mode) # exact phrase
        ret = c.Query(q, "comments")
        if ret == None:
            return { "error": c.GetLastError() }
        
        # batch retrieve matching comments
        comments = fetch_dict(UserComment, [match["id"] for match in ret["matches"]])
        users = fetch_dict(User, [comment.user_id for comment in comments.values()])
        
        for match in ret["matches"]:
            if match["id"] not in comments: continue
            comment = comments[match["id"]]
            if comment.status not in (UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED): continue
            
            message = re.sub(r"\s+", " ", comment.message.lower())
            if not autocomplete and q in message:
                i = message.lower().index(q.lower())
                autocomplete = truncatewords(message[i:], 5).replace(" ...", "")
            
            if match["attrs"]["bill_id"] not in bills:
                # generate context
                text = re.sub(r"\s+", " ", message) # clean up whitespace
                text = escape(text) # turn into HTML before <b></b> is added by context generator, hopefully won't get in the way
                context = " ".join(c.BuildExcerpts([text], "comments", q, { "before_match": "<b>", "after_match": "</b>", "exact_phrase": True, "single_passage": True})).decode("utf8")
                context = re.sub(r"^\s*\.\.\.\s*|\s*\.\.\.\s*$", "", context) # clean up whitespace
                if comment.user_id in users:
                    context = escape(users[comment.user_id].username + " wrote: ") + context
                
                entry = {"bill": match["attrs"]["bill_id"], "context": context, "sort_group": sort_group, "hit_count": 0}
                bills[match["attrs"]["bill_id"]] = entry
                prompts.append(entry)
                if len(bills) == 10:
                    break
            else:
                bills[match["attrs"]["bill_id"]]["hit_count"] += 1
                
        if len(bills) > 10:
            return { "autocomplete": autocomplete, "bills": pull_bills(prompts) }
        
    # Add additional bills by searching bill text.
    
    c.SetMatchMode(SPH_MATCH_ANY) # any words
    c.SetFilter("doctype", [100]) # clear this in any future searches....
    ret = c.Query(q, "doc_text")
    if ret == None:
        return { "error": c.GetLastError() }

    # batch retrieve matching documents
    docs = fetch_dict(PositionDocument, [match["attrs"]["document_id"] for match in ret["matches"]], only=["bill"])

    for match in ret["matches"]:
        if match["attrs"]["document_id"] not in docs: continue
        doc = docs[match["attrs"]["document_id"]]
        bill_id = doc.bill_id
        if bill_id not in bills:
            entry = {"bill": bill_id, "sort_group": 2, "hit_count": 0}
            prompts.append(entry)
            bills[bill_id] = entry
        else:
            bills[bill_id]["hit_count"] += 1
        if len(bills) == 10:
            break
    
    return { "autocomplete": autocomplete, "bills": pull_bills(prompts) }

def user_activity_feed(user):
    # Gets the user activity feed which is a list of feed items, each item
    # a dict with fields:
    #  ....
    
    # Define generators that iterate over feed items in reverse chronological
    # order for different sorts of events that go into your feed.
    #
    # CTA: primary call to action
    # AUX: auxiliary call to action
    # GFX: graphic/media to go along with item
    
    # other things we need:
    #    upcoming votes - haven't commented: weigh in [ share] | pie
    #     upcoming votes - already commented: share [ bill report ] | your position
    #    house bill reaches 100 cosponsors, senate bill reaches 10
    #    scan for the not-most-recent actions of a bill (reported, voted, etc) but make sure status text is not in present tense?
    #    when your MoC cosponsors a bill you commented on or bookmarked
    # if you weighed on a bill that was re-introduced
    # message deliveries
    
    # list() forces execution here so it does not get evaluated in subqueries
    your_bill_list_ids = list(user.comments.order_by().values_list('bill', flat=True))
    
    your_antitracked_bills = list(user.userprofile.antitracked_bills.values_list('id', flat=True))
    
    def comment_button(c):
        if c.message:
            return ("share your comment", "your_comment", c.url())
        return ("share the bill", "the_bill", c.bill.url())
    def comment_share(c):
        # Try to embed hashtag inside the bill name.
        # Turn the hashtag into a regular expression that admits spaces and
        # periods between its characters, to account for how bill numbers
        # are formatted in titles versus hashtags
        regex = r"[\.\s]*".join(re.escape(c) for c in c.bill.hashtag().replace("#", ""))
        title = re.sub(regex, c.bill.hashtag(), c.bill.nicename, flags=re.I)
        
        return (
            "share your comment" if c.message else "share this bill",
            "I " + c.verb(tense="past") + " " + title + " on @POPVOX",
            c.url() if c.message else c.bill.url(),
            c.bill.hashtag() if not c.bill.hashtag() in title else None)
    
    def your_comments(limit):
        # the positions you left
        #  CTA: share
        #  AUX: view bill
        #  GFX: preview?
        for c in user.comments.all().select_related("bill", "address").order_by('-updated')[0:limit]:
            yield {
                "action_type": "comment",
                "date": c.updated,
                "verb": c.verb(tense="past"),
                "bill": c.bill,
                "comment": c,
                "button": comment_button(c),
                "share": comment_share(c),
                "metrics_props": { "message": c.message != None },
            }

    def your_deliveries(limit):
        # deliveries of your comments
        #  CTA: share
        #  AUX: view bill
        #  GFX: ?
        
        # It is difficult to write an efficient ORM query to get the results ordered by the delivery
        # record creation date and get MySQL to do the join in the right order. We have to start with
        # UserComment to get the join right, but then we can't have the ORM return comments because
        # it'll be distinct and we'll lose the reference to the joined row of the delivery records table.
        # Filtering on a many-to-many and using values() will get the raw JOIN results which will have
        # the distinct delivery records.
        for row in user.comments.filter(delivery_attempts__success=True).order_by("-delivery_attempts__created").values("id", "delivery_attempts__id", "delivery_attempts__created"):
            yield {
                "action_type": "delivery",
                "date": row["delivery_attempts__created"],
                #"bill": c.bill,
                #"verb": c.verb(tense="ing"),
                #"message": c.message,
                #"recipient": getMemberOfCongress(d.target.govtrackid)["name"],
            }
        
        # Too slow!
        
        #from writeyourrep.models import DeliveryRecord
        from popvox.govtrack import getMemberOfCongress
        #for d in DeliveryRecord.objects.filter(comments__user=user, success=True).only("created", "target__govtrackid").order_by('-created')[0:limit]:
        #    c = d.comments.all().only("position", "created", "message", "bill__congressnumber", "bill__billtype", "bill__billnumber", "bill__title", "bill__street_name", "bill__vehicle_for")[0]
        #for c in user.comments
        #    yield {
        #        "action_type": "delivery",
        #        "date": d.created,
        #        "bill": c.bill,
        #        "verb": c.verb(tense="ing"),
        #        "message": c.message,
        #        "recipient": getMemberOfCongress(d.target.govtrackid)["name"],
        #    }
        
    billtypes_with_status = ('h', 's', 'hr', 'sr', 'hj', 'sj', 'hc', 'sc')
    
    def your_commented_bills_status(limit):
        # status of bills you have commented on
        #  CTA: share
        #  AUX: view bill
        #  GFX: ?
        
        # on the first attempt to pull the comment, pull in all of the comments
        # for any of the returned bills and cache them.
        bill_list = set()
        comment_cache = { }
        def get_comment_closure(bill, curry=None):
            def f():
                #return UserComment.objects.get(bill=bill, user=user)
                if len(comment_cache) == 0:
                    for c in user.comments.filter(bill__in=bill_list).select_related("bill"):
                        comment_cache[c.bill_id] = c
                if not curry:
                    return comment_cache[bill.id]
                else:
                    return curry(comment_cache[bill.id])
            return f
        
        def vote_results(comment):
            # If the current status of this bill is one in which a vote
            # may have occurred, check the bill XML file if there is
            # a recorded vote for that status, and if so, pull in
            # the votes of the Members for this user.
            
            from popvox.govtrack import isStatusAVote
            if not isStatusAVote(comment.bill.current_status): return None
            
            # Check the bill XML file for a recorded vote.
            try:
                dom1 = popvox.govtrack.getBillMetadata(comment.bill)
            except:
                return None
            for vote in dom1.getElementsByTagName("vote"):
                if vote.getAttribute("state") != comment.bill.current_status: continue
                if vote.getAttribute("how") != "roll":
                    return ("no-data", "The %s was voted on %s. No record of individual votes was kept." % (comment.bill.proposition_type(), vote.getAttribute("how")))
                break
            else:
                # did not find a recorded vote for this state
                return None
            
            # Who are the user's members?
            mocs = popvox.govtrack.getMembersOfCongressForDistrict(comment.state + str(comment.congressionaldistrict))
            mocs = set([m["id"] for m in mocs])
            
            # How did the user's Members vote?
            roll = vote.getAttribute("roll")
            where = vote.getAttribute("where")
            date =  vote.getAttribute("datetime")
            yearre = re.compile(r'^\d{4}')
            year = re.match(yearre, date).group(0)
            votexml = "/mnt/persistent/data/govtrack/us/" + str(comment.bill.congressnumber) + "/rolls/"+where+year+"-"+roll+".xml"
            try:
                dom2 = parse(open(votexml))
            except:
                return None
            verbs = { "+": "voted in favor", "-": "voted against", "0": "was absent", "P": "abstained" }
            for opt in dom2.getElementsByTagName("option"):
                if opt.getAttribute("key") in ("+", "-"):
                    verbs[opt.getAttribute("key")] = "voted " + opt.firstChild.data.lower() 
            ret = { }
            for voter in dom2.getElementsByTagName("voter"):
                voterid = int(voter.getAttribute("id"))
                votervote = voter.getAttribute("vote")
                if voterid in mocs and votervote in ("+", "-", "0", "P"):
                    ret[voterid] = verbs[votervote]
            
            # The user has no Members who voted on this bill.
            if len(ret) == 0: return None
            
            return ("table", [ (popvox.govtrack.getMemberOfCongress(m), ret[m]) for m in ret ])
        
        for status_type in ("current_status", "upcoming_event"):
            datefield = status_type + "_date"
            if status_type == "upcoming_event": datefield = status_type + "_post_date"
            
            for bill in Bill.objects.filter(id__in=your_bill_list_ids, billtype__in=billtypes_with_status).exclude(**{datefield: None}).order_by('-' + datefield)[0:limit]:
                bill_list.add(bill.id)
                yield {
                    "action_type": "bill_" + status_type,
                    "date": getattr(bill, datefield),
                    "bill": bill,
                    "comment": get_comment_closure(bill),
                    "mutually_exclusive_with": (status_type, bill), # used by your_bookmarked_bills_status
                    "button": get_comment_closure(bill, curry=comment_button),
                    "share": get_comment_closure(bill, curry=comment_share),
                    "metrics_props": get_comment_closure(bill, lambda c : { "source": "weighed_in", "message": c.message != None }),
                    "recorded_vote": get_comment_closure(bill, curry=vote_results),
                }
            
    def your_bookmarked_bills_status(limit):
        # status of bills you have bookmarked but not commented on
        #  CTA: weigh in
        #  AUX: share
        #  GFX: ?
        
        for status_type in ("current_status", "upcoming_event"):
            datefield = status_type + "_date"
            if status_type == "upcoming_event": datefield = status_type + "_post_date"
            
            for bill in Bill.objects.filter(trackedby__user=user, billtype__in=billtypes_with_status).exclude(**{datefield: None}).order_by('-' + datefield):
                yield {
                    "action_type": "bill_" + status_type,
                    "date": getattr(bill, datefield),
                    "bill": bill,
                    "mutually_exclusive_with": (status_type, bill), # used by your_bookmarked_bills_status
                    "button": ("weigh in", "weigh_in", bill.url()),
                    "share": ("share this bill", bill.nicename, bill.url(), bill.hashtag()),
                    "metrics_props": { "source": "bookmark" },
                }
        
    def your_bills_now(limit):
        # for each bill you have weighed in on, every time the number of people weighing
        # in doubles, include it in the feed.
        #  CTA: share
        #  AUX: view report
        #  GFX: pie chart
        
        # get a list of the total number of comments on all of the bills the user
        # has weighed in on. use a list() to force the inner query to evaluate first.
        # run the Count() on a column that is in the index (count(*) would be nice
        # but django won't allow that).
        bill_counts = dict(UserComment.objects.filter(bill__in=your_bill_list_ids).values("bill").annotate(count=Count("bill")).order_by().values_list("bill", "count"))
        
        import math
        from popvox.views.bills import bill_statistics
        ret = []
        for c in user.comments.all().select_related("bill"):
            # I suspect that people will want to see updates more for bills they
            # actually wrote something about.
            if c.message:
                doubling = 2
            else:
                doubling = 2.5
            
            # how many comments were left at the time you weighed in?
            nc1 = c.seq + 1 # c.bill.usercomments.filter(created__lt=c.created).count() + 1
            
            # how many comments are left now?
            nc2 = bill_counts.get(c.bill_id, 1) # c.bill.usercomments.count()
            
            # how many times has it doubled since then? i.e. 2^x = nc2/nc1
            x = (math.log(nc2) - math.log(nc1)) / math.log(doubling)
            
            # find the time of the most recent doubling, i.e. the time of the
            # nc1*2^[x]'th comment where [x] is x rounded down to the nearest integer.
            x = math.floor(x)
            if x <= 0.0: continue # has not doubled yet, or maybe it has gone down!
            new_count = int(doubling**x * nc1)
            
            try:
                #c2 = c.bill.usercomments.order_by('created')[int(doubling**x * nc1)]
                # Look at that numbered comment, or the next, in case that comment was
                # deleted, or if there was some weird concurrency thing and no comment
                # exists at that index.
                c2 = c.bill.usercomments.filter(seq__gte=new_count).order_by('seq')[0]
            except IndexError:
                # weird?
                continue
            
            ret.append({
                "action_type": "bill_now",
                "date": c2.created,
                "bill": c.bill,
                "your_number": nc1,
                "new_count": new_count,
                "comment": c,
                "button": comment_button(c),
                "share": comment_share(c),
                "metrics_props": { "message": c.message != None, "factor": x, "their_number": nc1 },
            })
            
        # We can't efficiently query these events in date order, so we pull them all
        # and return the most recent in date order.
        ret.sort(key = lambda item : item["date"], reverse=True)
        for item in ret[0:limit]:
            yield item
            
    def new_org_positions(limit):
        # What new organization position statements do we think you might be interested in?
        #  CTA: view position statement
        #  AUX: weigh in or share?
        #  GFX: ?
        
        # Look at the orgs that have agreed with this person on bills, and suggest other
        # positions they are taking.
        
        from django.db.models import F
        import math

        # First find the orgs that most agree with this user.
        orgs = { }
        for ocp in OrgCampaignPosition.objects.filter(bill__usercomments__user=user, position=F("bill__usercomments__position"), campaign__visible=True, campaign__org__visible=True).select_related("campaign__org"):
            org = ocp.campaign.org
            orgs[org] = orgs.get(org, 0) + 1
            
        # Get the number of bills on the legislative agendas of these orgs.
        org_agenda_size = dict(OrgCampaignPosition.objects.filter(campaign__org__in=orgs).values("campaign__org").annotate(count=Count("campaign__org")).order_by().values_list("campaign__org", "count"))
        
        # Sort orgs by the number of positions that the user has the same position
        # on, but weighed against the total number of positions in the org's agenda.
        orgs = sorted(orgs.items(), key = lambda kv : float(kv[1]) / math.sqrt(float(org_agenda_size.get(kv[0].id, 1))), reverse=True)
        
        counter = 0
        for org, agreecount in orgs:
            counter2 = 0
            for ocp in OrgCampaignPosition.objects.filter(campaign__org=org).select_related("campaign__org", "bill").order_by('-created'):
                if ocp.bill.id in your_antitracked_bills:
                    continue
                    
                yield {
                    "action_type": "org_position",
                    "date": ocp.created,
                    "org": ocp.campaign.org,
                    "verb": ocp.verb(),
                    "bill": ocp.bill,
                    "numagreements": agreecount,
                    "button": ("read their position", "org_position", org.url()),
                    "share": ("share this organization", org.name + " " + ocp.verb() + " " + ocp.bill.nicename, org.url(), ocp.bill.hashtag()),
                    "metrics_props": { "shared_bills": agreecount },
                }
                
                # Maximum of limit/2 actions returned.
                counter += 1
                if counter >= limit/2:
                    return
                    
                # Maximum of 3 actions returned per organization.
                counter2 += 1
                if counter2 == 3:
                    break

    feed_size = 10
    sources = (your_comments, your_commented_bills_status, your_bookmarked_bills_status, your_bills_now, new_org_positions)
    exclusions = set()
    feed = []
    for source in sources:
        for item in source(feed_size):
            # allow feed items to be hidden if some other particular feed item has
            # already been included.
            if item.get("mutually_exclusive_with", None) in exclusions:
                continue
                
            feed.append(item)
            
            # mark what this feed item is about if it is used to hide other types
            # of similar feed items.
            if "mutually_exclusive_with" in item:
                exclusions.add(item["mutually_exclusive_with"])
            
    
    feed.sort(key = lambda item : item["date"], reverse=True)
    feed = feed[0:feed_size]
    
    adorn_bill_stats([item["bill"] for item in feed if "bill" in item])
    
    return feed

def adorn_bill_stats(bills):
    # adorn all bill objects with pro/con counts
    if len(bills) == 0: return
    bill_list = { }
    for bill in bills:
        bill_list[bill.id] = { "+": 0, "-": 0 }
    c = connection.cursor()
    c.execute("SELECT bill_id, position, COUNT(*) as count FROM popvox_usercomment WHERE bill_id IN (%s) GROUP BY bill_id, position" % ",".join([str(id) for id in bill_list.keys()]))
    for row in c.fetchall():
        bill_list[row[0]][row[1]] = row[2]
    for bill in bills:
        bill.stats = (bill_list[bill.id]["+"], bill_list[bill.id]["-"], bill_list[bill.id]["+"]+bill_list[bill.id]["-"])

@csrf_protect
@login_required
def individual_dashboard(request):
    user = request.user

    random_user = False
    if user.is_authenticated() and (user.is_staff | user.is_superuser):
        if request.GET.get("user", "random") == "random":
            import random
            top_users = UserComment.objects.values("user").annotate(count=Count("user")).order_by('-count')
            user = top_users[800 + random.randint(0, 200)]
            user = User.objects.get(id=user["user"])
            random_user = True
        else:
            user = User.objects.get(id=request.GET["user"])

    prof = user.get_profile()
    if prof.is_leg_staff() or prof.is_org_admin():
        raise Http404()

    return render_to_response('popvox/dashboard.html',
        {
        "userid": user.id,
        "suggestions": compute_prompts(user),
        "feed_items": user_activity_feed(user),
        "SITE_ROOT_URL": SITE_ROOT_URL,
        "adserver_targets": ["user_home"],
        "random_user": random_user,
            },
        context_instance=RequestContext(request))

@csrf_protect
@login_required
def history(request):
    user = request.user
    prof = user.get_profile()
    if prof.is_leg_staff() or prof.is_org_admin():
        raise Http404()
    else:
        return render_to_response('popvox/history.html',
        { 
        "tracked_bills": annotate_track_status(prof, prof.tracked_bills.all()),
            "adserver_targets": ["user_home"],
            },
        context_instance=RequestContext(request))
