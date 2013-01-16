from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.views.generic.simple import direct_to_template
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.contrib.auth.decorators import login_required
from django import forms
from django.core.urlresolvers import reverse
from django.views.decorators.cache import cache_page
from django.template.defaultfilters import truncatewords
from django.utils.html import strip_tags
from django.db.models import Count
from django.db import connection
from django.core.cache import cache

from jquery.ajax import json_response, ajax_fieldupdate_request, sanitize_html, validation_error_message

import os, re, math
from xml.dom import minidom
import urllib, urllib2
import datetime
import json

from popvox.models import *
from popvox.views.main import strong_cache
from registration.helpers import captcha_html, validate_captcha
from popvox.govtrack import CURRENT_CONGRESS, getMembersOfCongressForDistrict, open_govtrack_file, statenames, getStateReps
from emailverification.utils import send_email_verification
from utils import formatDateTime, cache_page_postkeyed, csrf_protect_if_logged_in

from settings import DEBUG, SERVER_EMAIL, SITE_ROOT_URL
import operator

popular_bills_cache = None
popular_bills_cache_2 = None
issue_areas = None

def getissueareas():
    # Gets the issue areas in batch.
    global issue_areas
    if issue_areas != None:
        return issue_areas
    all_issues = IssueArea.objects.all()
    issues = { }
    for ix in all_issues:
        if ix.parent_id == None:
            issues[ix.id] = { "object": ix, "subissues": [] }
    for ix in all_issues:
        if ix.parent_id != None and ix.parent.id in issues:
            issues[ix.parent_id]["subissues"].append(ix)
    issues = issues.values()
    issues.sort(key = lambda x : x["object"].name)
    issue_areas = issues
    return issues

@cache_page(60 * 60 * 2) # two hours
def issuearea_chooser_list(request):
    return render_to_response('popvox/issueareachooser_list.html', {'issues': getissueareas()}, context_instance=RequestContext(request))    

def get_popular_bills(searchstate = None, searchdistrict = None, newdist = False):
    global popular_bills_cache

    if popular_bills_cache != None and (datetime.datetime.now() - popular_bills_cache[0] < timedelta(minutes=30)):
        return popular_bills_cache[1]
        
    popular_bills = []

    if False:
        # Select bills with the most number of comments in the last week.
        pop = Bill.objects.filter(usercomments__created__gt=datetime.datetime.now()-timedelta(days=7)).exclude(billtype = 'x').annotate(Count('usercomments')).order_by('-usercomments__count').select_related("sponsor")[0:12]
        for b in pop:
            if b.usercomments__count == 0:
                break
            if not b in popular_bills:
                popular_bills.append(b)
                if len(popular_bills) > 12:
                    break
    else:
        # Look at multiple time periods and compute the top bills that have
        # the highest number of comments with the time period relative to
        # comments within a longer time period, meaning show bills that are
        # moving fast relative to past performance.
        seen_bills = set()
        for time_period_name, time_period, how_many in (('few hours', timedelta(hours=3), 1), ('day', timedelta(days=1), 2), ('two days', timedelta(days=2), 3), ('week', timedelta(days=7), 3), ('month', timedelta(days=30), 4)):
            # Collect counts grouped by bill and time period.
            bill_data = { }
            max_count = 0
            if (searchstate == None):
                comments = UserComment.objects
            elif (searchdistrict == None):
                comments = UserComment.objects.filter(state=searchstate)
            elif (newdist == True):
                comments = UserComment.objects.filter(state=searchstate,address__congressionaldistrict2013=searchdistrict)
            else:
                comments = UserComment.objects.filter(state=searchstate,congressionaldistrict=searchdistrict)
            if not newdist:
                for rec in comments\
                    .exclude(bill__in=seen_bills)\
                    .filter(created__gt=datetime.datetime.now() - 5*time_period)\
                    .extra(select={"half":"created>='%s'" % (datetime.datetime.now() - time_period).isoformat()})\
                    .values("half", "bill")\
                    .annotate(count=Count('id')).order_by('-count')\
                    [0:50]:
                    if not rec["bill"] in bill_data: bill_data[rec["bill"]] = [None, None]
                    bill_data[rec["bill"]][rec["half"]] = rec["count"]
                    max_count = max(max_count, rec["count"])
                
            if max_count < 5: continue
                
            # Sort.
            for bill, (half_a, half_b) in bill_data.items():
                # compute the score, accounting for zeros that come back as missing data
                # the score is based on a ratio, but half_a is de-exaggerated so that
                # bills with high counts are a little more prominant, rather than just
                # looking at percent change.
                bill_data[bill] = (half_b, float(half_b if half_b else 0) / math.pow(float(half_a if half_a>max_count/5 else max_count/5), .85))
            bill_data = list(bill_data.items())
            bill_data.sort(key = lambda x : -x[1][1]) # take the top how_many with highest score
            bill_data = bill_data[0:how_many]
            bill_data.sort(key = lambda x : x[1][0]) # then resort to put them in ascending order of raw count, so they display better
            
            for bill, (commentcount, score) in bill_data:
                bill = Bill.objects.get(id=bill)
                bill.trending_time_period = time_period_name
                bill.new_positions = commentcount
                popular_bills.append(bill)
                seen_bills.add(bill.id)
                
    popular_bills_cache = (datetime.datetime.now(), popular_bills)
    
    return popular_bills

def get_popular_bills2(searchstate = None, searchdistrict = None, newdist = False):
    global popular_bills_cache_2

    if popular_bills_cache_2 != None and (datetime.datetime.now() - popular_bills_cache_2[0] < timedelta(minutes=30)):
        return popular_bills_cache_2[1]

    popular_bills = get_popular_bills(searchstate,searchdistrict,newdist)

    # Get the campaigns that support or oppose any of the bills, in batch.
    #cams = OrgCampaign.objects.filter(positions__bill__in = popular_bills, visible=True, org__visible=True).select_related() # note recursive SQL which goes from OrgCampaign to Org
    
    # Annotate the list of popular bills with the org information.
    popular_bills2 = [ ]
    bmap = { }
    for bill in popular_bills:
        if bill.billtype != 'x':
            b = { }
            popular_bills2.append(b)
            b["bill"] = bill
            bmap[bill.id] = b

    popular_bills_cache_2 = (datetime.datetime.now(), popular_bills2)
    
    return popular_bills2

@strong_cache
def bills(request):
    return render_to_response('popvox/bill_list.html', {
        'trending_bills': get_popular_bills2(),
        "issues": bills_issue_areas(),
        "show_share_footer": True,
        }, context_instance=RequestContext(request))

def bills_issue_areas():
    issues = IssueArea.objects\
        .filter(toptermbills__congressnumber=CURRENT_CONGRESS)\
        .annotate(billcount=Count("toptermbills"))
    
    # since we can't annotate on two things at once (messes up the counts)
    # and we also want a count of bills and also of comments...
    issues_dict = dict((ix.id, ix) for ix in issues)
    for issue in \
        IssueArea.objects\
        .filter(toptermbills__congressnumber=CURRENT_CONGRESS)\
        .annotate(commentcount=Count("toptermbills__usercomments")):
        issues_dict[issue.id].commentcount = issue.commentcount
    
    for i, ix in enumerate(issues):
        ix.primaryorder = i
        
    uncat_count = Bill.objects.filter(congressnumber=CURRENT_CONGRESS, topterm=None).count()
    if uncat_count > 0:
        issues = list(issues)
        issues.append( { "primaryorder": len(issues), "commentcount": 0, "id": "other", "name": "Uncategorized Bills", "billcount": uncat_count } )
        
    return issues

@strong_cache
def bills_issues_bills(request):
    ix = request.GET.get('ix', "0")
    if ix != "other":
        ix = get_object_or_404(IssueArea, id=ix)
        name = ix.name
        bills = Bill.objects.filter(topterm=ix)
    else:
        ix = None
        name = "Uncategorized Bills"
        bills = Bill.objects.filter(topterm=None)
    
    # order by number of recent comments.... but don't exclude bills without
    # any comments, by adding them back after by unioning with the whole set.
    # does that really work and not create dupes?
    bills = bills.filter(congressnumber=CURRENT_CONGRESS, migrate_to=None)
    bills = bills.\
        filter(usercomments__created__gt=datetime.datetime.now()-timedelta(days=21))\
        .annotate(Count('usercomments')).order_by('-usercomments__count') \
        | bills
    
    from utils import group_by_issue
    groups = group_by_issue(bills, top_title="Top Bills", exclude_issues=[ix], other_title="Other Bills")
    if len(groups) == 1:
        groups[0]["name"] = name
    
    return render_to_response('popvox/bill_list_issues_bills.html', {
        'groups': groups,
        }, context_instance=RequestContext(request))

def billsearch_internal(q, cn=CURRENT_CONGRESS):
    bill_number_re = re.compile(r"(hr|s|hconres|sconres|hjres|sjres|hres|sres|x)(\d+)(/(\d+))?", re.I)
    m = bill_number_re.match(q.replace(" ", "").replace(".", "").replace("-", ""))
    if m != None:
        if m.group(3) != None:
            cn = int(m.group(4))
        try:
            b = bill_from_url("/bills/us/%d/%s%d" % (cn, m.group(1).lower(), int(m.group(2))))
            return ([b], None, None)
        except:
            pass
            
    from sphinxapi import SphinxClient, SPH_MATCH_EXTENDED
    c = SphinxClient()
    c.SetServer("localhost" if not "REMOTEDB" in os.environ else os.environ["REMOTEDB"], 3312)
    c.SetMatchMode(SPH_MATCH_EXTENDED)
    c.SetFilter("congressnumber", [cn])
    c.SetLimits(0, 1000)
    ret = c.Query(q, "bill_titles")
    bill_weights = { }
    status = "ok"
    error = None
    if ret == None:
        error = c.GetLastError()
        status = "callfail"
    else:
        for b in ret["matches"]:
            bill_weights[b["id"]] = (0, 0, -b["weight"]) # default sort order
            if len(bill_weights) == 100:
                status = "overflow"
                break

    # Pull in the bill objects for the search result matches.

    # Update sort order for those bills with comments in the last three weeks.
    for b in Bill.objects.filter(id__in=bill_weights.keys()).filter(usercomments__created__gt=datetime.datetime.now()-timedelta(days=21)).annotate(count=Count('usercomments')).values("id", "count") :
         bill_weights[b["id"]] = (-b["count"], bill_weights[b["id"]][1], bill_weights[b["id"]][2])
    
    # Update sort order for those bills with comments ever.
    for b in Bill.objects.filter(id__in=bill_weights.keys()).annotate(count=Count('usercomments')).values("id", "count") :
         bill_weights[b["id"]] = (bill_weights[b["id"]][0], -b["count"], bill_weights[b["id"]][2])

    # The previous query omits bills without comments, so re-pull the complete
    # match list and assign weights.
    bills = list(Bill.objects.filter(id__in=bill_weights.keys()))
    for b in bills:
        b.weight = bill_weights[b.id]
        #b.title += repr(b.weight)
        
    # Combine the three sort orders, but first compute the min/max value for each.
    weightrange = ([None, None], [None, None], [None, None])
    for b in bills:
        for v in xrange(len(b.weight)):
            if weightrange[v][0] == None or b.weight[v] < weightrange[v][0]: weightrange[v][0] = b.weight[v]
            if weightrange[v][1] == None or b.weight[v] > weightrange[v][1]: weightrange[v][1] = b.weight[v]
    for b in bills:
        w = 0
        for v in xrange(len(b.weight)):
            if weightrange[v][0] == weightrange[v][1]: continue
            w += 1.0/(v+1) * (b.weight[v]-weightrange[v][0])/(weightrange[v][1]-weightrange[v][0])
        b.weight = w
        
    bills.sort(key = lambda bill : bill.weight)
        
    return (bills, status, error)

@csrf_protect_if_logged_in
def billsearch(request):
    if not "q" in request.GET or request.GET["q"].strip() == "":
        return HttpResponseRedirect("/bills")
    q = request.GET["q"].strip()
    
    cn = CURRENT_CONGRESS
    if "congressnumber" in request.GET and request.GET["congressnumber"].isdigit():
        cn = int(request.GET["congressnumber"])
    
    bills, status, error = billsearch_internal(q, cn=cn)

    if request.user.is_authenticated():
        import home
        home.annotate_track_status(request.user.userprofile, bills)

    if len(bills) == 1:
        if request.user.is_authenticated() and request.user.userprofile.is_leg_staff():
            return HttpResponseRedirect(bills[0].url() + "/report")
        else:
            return HttpResponseRedirect(bills[0].url())
    return render_to_response('popvox/billsearch.html', {'bills': bills, "q": request.GET["q"].strip(), "congressnumber": request.GET.get("congressnumber", ""), "status": status, "errormsg": error}, context_instance=RequestContext(request))

def getbill(congressnumber, billtype, billnumber, vehicleid=None):
    if vehicleid != None:
        try:
            vehicleid = int(vehicleid[1:])
        except:
            raise "Invalid bill number. Invalid vehicle id \"" + vehicleid + "\"."
        b = [getbill(congressnumber, billtype, billnumber)]
        while b[0].replaced_vehicle.exists():
            x = b[0].replaced_vehicle.all()[0]
            b.insert(0, x)
        if vehicleid < 1 or vehicleid > len(b):
            raise "Invalid bill number. Invalid vehicle id \"" + vehicleid + "\"."
        return b[vehicleid-1]

    if int(congressnumber) < 1 or int(congressnumber) > 1000: 
        raise Http404("Invalid bill number. \"" + congressnumber + "\" is not valid.")
    try:
        billtype = Bill.slug_to_type[billtype]
    except:
        raise Http404("Invalid bill number. \"" + billtype + "\" is not valid.")
    try:
        return Bill.objects.filter(congressnumber=congressnumber, billtype=billtype, billnumber=billnumber, vehicle_for=None).select_related("sponsor")[0]
    except:
        raise Http404("Invalid bill number. There is no bill by that number.")
    
@json_response
def billsearch_ajax(request):
    bill = getbill(
        request.POST["congressnumber"] if request.POST["congressnumber"] != "0" else CURRENT_CONGRESS,
        request.POST["billtype"].lower(),
        request.POST["billnumber"])
    return {
        "status": "success",
        "congressnumber": bill.congressnumber,
        "billtype": bill.billtype,
        "billnumber": bill.billnumber,
        "url": bill.url(),
        "title": bill.title,
        "billstatus": bill.status_advanced(),
        "is_bill": bill.is_bill(),
        "sponsor": { "id": bill.sponsor.id, "name": bill.sponsor.name() } if bill.sponsor != None else None,
        }
    
def bill_comments(bill, **filterargs):
    def filter_null_args(kv):
        ret = { }
        for k, v in kv.items():
            if v != None:
                ret[k] = v
        return ret
    
    return bill.usercomments.filter(**filter_null_args(filterargs))\
        .select_related("user")

def bill_statistics_cache(f):
    def g(bill, shortdescription, longdescription, want_timeseries=False, want_totalcomments=False, force_data=False, as_of=None, **filterargs):
        cache_key = ("bill_statistics_cache:%d,%s,%s,%s,%s" % (bill.id, shortdescription.replace(" ", ""), want_timeseries, want_totalcomments, as_of))
        if as_of: cache_key = None
        
        ret = cache.get(cache_key) if cache_key else None
        if ret != None:
            return ret
        
        ret = f(bill, shortdescription, longdescription, want_timeseries, want_totalcomments, force_data, as_of, **filterargs)
        
        if cache_key: cache.set(cache_key, ret, 60*60*2 if want_timeseries else 30) # for timeseries two hours, otherwise 30 seconds

        return ret
    return g

@bill_statistics_cache # the arguments must match in the decorator!
def bill_statistics(bill, shortdescription, longdescription, want_timeseries, want_totalcomments, force_data, as_of, **filterargs):
    # If any of the filters is None, meaning it is based on demographic info
    # that the user has not set, return None for the whole statistic group.
    for key in filterargs:
        if filterargs[key] == None:
            return None
            
    # Get comments that were left only before the session ended.
    enddate = govtrack.getCongressDates(bill.congressnumber)[1] + timedelta(days=1)
    
    # Get all counts at once, where stage = 0 if the comment was before the end of
    # the session, 1 if after the end of the session.
    if as_of: filterargs["created__lt"] = as_of
    
    if bill.congressnumber < CURRENT_CONGRESS:
        counts = bill_comments(bill, **filterargs).order_by().extra(select={"stage": "popvox_usercomment.created > '" + enddate.strftime("%Y-%m-%d") + "'"}).values("position", "stage").annotate(count=Count("id"))
    else:
        if len(filterargs) > 0:
            counts = bill_comments(bill, **filterargs).order_by().values("position").annotate(count=Count("id"))
        else:
            # Django 1.3 messes up this query by duplicating position in the GROUP BY, making MySQL
            # "Using temporary; Using filesort". 
            # For the simple case, write our own SQL.
            c = connection.cursor()
            c.execute("SELECT position, COUNT(*) as count FROM popvox_usercomment WHERE bill_id=%d GROUP BY position" % bill.id)
            counts = [{ "position": r[0], "count": r[1] } for r in c.fetchall()]
    
    pro = 0
    con = 0
    pro_reintro = 0
    for item in counts:
        if item["position"] == "+" and item.get("stage", 0) == 0:
            pro = item["count"]
        if item["position"] == "-" and item.get("stage", 0) == 0:
            con = item["count"]
        if item["position"] == "+" and item.get("stage", 0) == 1:
            pro_reintro = item["count"]
        
    # Don't display statistics when there's very little data,
    # and definitely not when pro+con == 0 since that'll gen
    # an error down below.
    if (pro+con+pro_reintro < 10 and not force_data) or pro+con+pro_reintro == 0:
        return None

    if pro+con < 10:
        want_timeseries = False
    
    time_series = None
    if want_timeseries:
        all_comments = bill_comments(bill, **filterargs).exclude(created__gt=enddate).defer("message")
    
        # Get a time-series. Get the time bounds --- use the national data for the
        # time bounds so that if we display multiple charts together they line up.
        firstcommentdate = bill.usercomments.filter(created__lte=enddate).defer("message").order_by('created')[0].created.date()
        lastcommentdate = bill.usercomments.filter(created__lte=enddate).defer("message").order_by('-created')[0].updated.date()
        
        # Compute a bin size (i.e. number of days per point). Try to have 30 bins,
        # unless that subdivides a day into multiple bins, which would be weird.
        binsize = 1
        if firstcommentdate < lastcommentdate:
            binsize = int((lastcommentdate - firstcommentdate).days / 30)
        if binsize < 1:
            binsize = 1
        
        # Bin the observations.
        bins = { }
        for c in all_comments:
            days = int(round((c.created.date() - firstcommentdate).days / binsize) * binsize)
            if not days in bins:
                bins[days] = { "+": 0, "-": 0 }
            bins[days][c.position] += 1
        ndays = (lastcommentdate - firstcommentdate).days + 1
        days = sorted(bins.keys())
        time_series = {
            "xaxis": [(firstcommentdate + timedelta(x)).strftime("/%x").replace("/0", "/")[1:] for x in days],
            "pro": [sum([bins[y]["+"] for y in xrange(0, ndays) if y <= x and y in bins]) for x in days],
            "con": [sum([bins[y]["-"] for y in xrange(0, ndays) if y <= x and y in bins]) for x in days],
            }
            
    return {
        "shortdescription": shortdescription,
        "longdescription": longdescription,
        "total": pro+con, "pro":pro, "con":con,
        "pro_pct": int(round(100.0*pro/float(pro+con))) if pro+con > 0 else 0, "con_pct": int(round(100.0*con/float(pro+con))) if pro+con > 0 else 0,
        "total_comments": bill_comments(bill, **filterargs).filter(message__isnull=False).count() if want_totalcomments else None,
        "timeseries": time_series,
        "pro_reintro": pro_reintro}

@strong_cache
def bill(request, congressnumber, billtype, billnumber, vehicleid):
    bill = getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)
    if bill.migrate_to:
        return HttpResponseRedirect(bill.migrate_to.url())
    
    ch = bill.getChamberOfNextVote() if bill.is_bill() else None
    if not ch: ch = ""

    # Get the orgs who support or oppose the bill, and the relevant campaigns
    # within the orgs.
    orgs = [ ["support", {}], ["oppose", {}], ["neutral", {}], ["administration", {}] ]
    for p in bill.campaign_positions():
        cam = p.campaign

        grp = {"+":"support","-":"oppose","0":"neutral"}[p.position]
        if cam.org.id == 2123: grp = "administration" # The Administration
        grp = [g[1] for g in orgs if g[0] == grp][0]

        if not cam.org.slug in grp:
            grp[cam.org.slug] = {
                "id": cam.org.id,
                "name": cam.org.name,
                "url": cam.org.url(),
                "object": cam.org,
                "campaigns": [],
                "comment": None,
                "documents": cam.org.documents.filter(bill=bill).defer("text"),
            }
        if cam.default or grp[cam.org.slug]["comment"] == None:
            grp[cam.org.slug]["comment"] = p.comment
        if not cam.default:
            grp[cam.org.slug]["campaigns"].append(
                { "name": cam.name,
                     "url": cam.url(),
                     "description": cam.description,
                     "message": cam.message,
                     "comment": p.comment
                     })
    # Sort orgs by fan counts.
    def sort_orgs(orgs):
        orgs = list(orgs)
        orgs.sort(key = lambda org : -org["object"].fan_count_sort_order)
        return orgs
    for grp in orgs:
        grp[1] = sort_orgs(grp[1].values())
        
    billsup = len(bill.usercomments.filter(position='+'))
    billopp = len(bill.usercomments.filter(position='-'))
    
    return render_to_response('popvox/bill.html', {
            'bill': bill,
            'billsup': billsup,
            'billopp': billopp,
            "deadbox": not bill.isAlive(),
            "nextchamber": ch,
            "orgs": orgs,
            "show_share_footer": True,
        }, context_instance=RequestContext(request))

def billbox(bill):
    stats = bill_statistics(bill, "POPVOX", "POPVOX Nation", want_timeseries=False, want_totalcomments=True, force_data=True)
    cosponsors = bill.cosponsors.all()
    dems = 0
    gops = 0
    indies = 0
    for sponsor in cosponsors:
        if sponsor.party() == 'R':
            gops += 1
        elif sponsor.party() == 'D':
            dems += 1
        else:
            indies += 1
    if bill.sponsor.party() == 'R':
        gops += 1
    elif bill.sponsor.party() == 'D':
        dems += 1
    else:
        indies += 1
    sponsors = {"dems":dems, "gops":gops, "indies":indies}
    return (bill, stats, sponsors)
    
def billboxes(bills):
    L = []
    for bill in bills:
        L.append(billbox(bill))
    return L

def new_bills(request, NumDays):
    
    LookupDays = int(NumDays)
    
    NewBills = []
    # Get all bills from past 7 days
    bills = Bill.objects.filter(introduced_date__gt=datetime.datetime.now()-timedelta(days=LookupDays))
    
    
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

        
# this is the view for the new newbills page. take out the first new_ and delete the other view when it's ready to go.
def new_new_bills(request, NumDays):
    
    
    LookupDays = int(NumDays)
    
    NewBills = []
    # Get all bills from past 7 days
    bills = Bill.objects.filter(introduced_date__gt=datetime.datetime.now()-timedelta(days=LookupDays))
    
    
    #House Bills
    HR = billboxes(bills.filter(billtype='h'))
    #Senate Bills
    S = billboxes(bills.filter(billtype='s'))
    #House Resolutions
    HRes = billboxes(bills.filter(billtype='hr'))
    #Senate Resolutions
    SRes = billboxes(bills.filter(billtype='sr'))
    #House Concurrent Resolutions
    HCRes = billboxes(bills.filter(billtype='hc'))
    #Senate Concurrent Resolutions
    SCRes = billboxes(bills.filter(billtype='sc'))
    #House Joint Resolutions
    HJRes = billboxes(bills.filter(billtype='hj'))
    #Senate Joint Resolutions
    SJRes = billboxes(bills.filter(billtype='sj'))
    
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
        
        
def bill_userstate(request, congressnumber, billtype, billnumber, vehicleid):
    ret = { }

    bill = getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)
    
    if "shorturl" in request.session and request.session["shorturl"].target == bill:
        # Referral to this bill.
        request.session["comment-referrer"] = {"bill": bill.id, "referrer": request.session["shorturl"].owner, "shorturl": request.session["shorturl"].id }
        del request.session["shorturl"]
        
    ret["canvote"] = (request.user.is_anonymous() or (not request.user.userprofile.is_leg_staff() and not request.user.userprofile.is_org_admin()))

    if request.user.is_authenticated():
        # Get the user's current position on the bill.
        # In principle by the data model, a user might take multiple positions
        # on a single bill. But we try to prevent that.
        for c in request.user.comments.filter(bill=bill):
            ret["user_position"] = {
                "position": c.position,
                "updated": formatDateTime(c.updated),
                "message": truncatewords(c.message, 30) if c.message else None,
                "url": c.url(),
            }
        
        # Get the list of Members of Congress who could vote on this bill
        # based on the user's most recent comment's congressional district.
        district = request.user.userprofile.most_recent_comment_district()
        if district != None:
            ch = bill.getChamberOfNextVote() if bill.is_bill() else None
            if ch == "s":
                ret["mocs"] = getMembersOfCongressForDistrict(district, moctype="sen")
            elif ch == "h":
                ret["mocs"] = getMembersOfCongressForDistrict(district, moctype="rep")
            if "mocs" in ret:
                ret["mocs"] = [m["name"] for m in ret["mocs"]]
                if len(ret["mocs"]) == 1:
                    ret["mocs"] = ret["mocs"][0]
                elif len(ret["mocs"]) == 2:
                    ret["mocs"] = " and ".join(ret["mocs"])
                else:
                    ret["mocs"][-1] = "and " + ret["mocs"][-1]
                    ret["mocs"] = ", ".join(ret["mocs"])
                    
        # Is the user tracking the bill?
        ret["tracked"] = request.user.userprofile.tracked_bills.filter(id=bill.id).exists()
        
        # For org admins, report the current endorsed state.
        ret["matched_campaigns"] = [
            {
                "id": p.id,
                "org": p.campaign.org.id,
                "orgname": p.campaign.org.name,
                "campaign": p.campaign.name if not p.campaign.default else "",
                "position": p.position,
                "comment": p.comment,
                "visible_state": p.campaign.visible_state() }
            for p in OrgCampaignPosition.objects.filter(bill=bill, campaign__org__admins__user=request.user).select_related("campaign__org")
        ]
        if "popvox_lastviewedcampaign" in request.session and not OrgCampaign.objects.get(id=request.session["popvox_lastviewedcampaign"]).default:
            ret["lastviewedcampaign"] = request.session["popvox_lastviewedcampaign"] 


    # administrative information
    if request.user.is_authenticated() and (request.user.is_staff or request.user.is_superuser):
        users_tracking_this_bill = bill.trackedby.filter(allow_mass_mails=True, user__orgroles__isnull = True, user__legstaffrole__isnull = True).distinct().order_by("user__date_joined").select_related("user")
        users_commented_on_this_bill = UserProfile.objects.filter(allow_mass_mails=True, user__comments__bill=bill).distinct().order_by("user__comments__created").select_related("user")
        ret["admin"] = { "tracking": [u.user.email for u in users_tracking_this_bill], "commented": [u.user.email for u in users_commented_on_this_bill] }

    return ret
bill.user_state = bill_userstate

def bill_get_object(request, congressnumber, billtype, billnumber, vehicleid):
    return getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)
bill.get_object = bill_get_object

pending_comment_session_key = "popvox.views.bills.billcomment__pendingcomment"

# This is an email verification callback.
class DelayedCommentAction:
    registrationinfo = None # a RegisterUserAction object
    bill = None
    comment_session_state = None
    
    def email_subject(self):
        return "Confirm Your Letter on " + Bill.objects.get(id=self.bill).shortname + " -- POPVOX"
        
    def email_templates(self):
        return ("popvox/emails/billcomment_confirm_email", {
            "bill": Bill.objects.get(id=self.bill).shortname,
            "comment": self.comment_session_state["message"].strip() if self.comment_session_state["message"].strip() != "" else ""
        })

    def email_should_resend(self):
        return not User.objects.filter(email = self.registrationinfo.email).exists()

    def get_response(self, request, vrec):
        # Create the user and log the user in.
        self.registrationinfo.finish(request)
        
        # Set the session state.
        request.session[pending_comment_session_key] = self.comment_session_state
        
        # Redirect to the comment form to continue.
        request.goal = { "goal": "comment-register-registered" }
        return HttpResponseRedirect(Bill.objects.get(id=self.bill).url() + "/comment/finish")

def get_comment_recipients(bill, address):
    if address == None: return None
    if address.state == None or address.congressionaldistrict == None: return # can be called with incomplete info
    if address.congressionaldistrict2013 == None: return
    c = UserComment(bill=bill, address=address)
    recips = c.get_recipients()
    if type(recips) != list: return None
    return recips

@csrf_protect
def billcomment(request, congressnumber, billtype, billnumber, vehicleid, position):
    from settings import BENCHMARKING

    position_original = position
    if position_original == None:
        position_original = ""
    
    bill = getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)
    
    # Get an existing comment the user has on this bill.
    existing_comment = None
    if request.user.is_authenticated():
        try:
            existing_comment = request.user.comments.get(bill = bill)
        except UserComment.DoesNotExist:
            pass
    
    # Clear out the session state for a pending comment (set e.g. if
    # user has to go away to do oauth login) if the pending comment
    # is for a different bill, or if the bill is not set (old cookie).
    if pending_comment_session_key in request.session and (not "bill" in request.session[pending_comment_session_key] or request.session[pending_comment_session_key]["bill"] != bill.url()):
        del request.session[pending_comment_session_key]
    
    # the user chooses the position on the main bill page and it gets
    # stored in the URL, or if the user is editing an existing comment
    # on the bill he can skip that part of the URL.
    if position == "/clear":
        position = "0"
    elif position == "/support":
        position = "+"
    elif position == "/oppose":
        position = "-"
    elif position == "/finish":
        # Get position from saved session, if any.
        if pending_comment_session_key in request.session:
            position = request.session[pending_comment_session_key]["position"]
        else:
            # Ruh-row.
            return HttpResponseRedirect(bill.url())
    elif position == None:
        if existing_comment:
            position = existing_comment.position
        else:
            return HttpResponseRedirect(bill.url())
    else:
        raise Http404()
        
    # Does the user have existing address information?
    address_record = None
    if existing_comment:
        # If we're editing an existing comment, then start with the address
        # tied to that comment.
        address_record = existing_comment.address
    elif request.user.is_authenticated():
        # If the user is logged in, take their most recent address as a
        # starting point.
        try:
            address_record = request.user.postaladdress_set.order_by("-created")[0]
        except IndexError:
            pass
    
    # Can the user revise the address record in-place, can he create a new address record,
    # or is his address fixed to prevent fraud?
    address_record_allow_save = False
    address_record_fixed = None
    if address_record:
        may_change = user_may_change_address(existing_comment, address_record, request.user)
        if may_change == "in-place":
            address_record_allow_save = True
        elif may_change == "new-record":
            address_record_allow_save = False
        else:
            address_record_fixed = may_change
                
    # Allow (actually require) the user to revise an address that does not have a prefix or phone number.
    if address_record != None and address_record_fixed != None and (address_record.nameprefix == "" or address_record.phonenumber == ""):
        address_record_fixed = None
    
    # We will require a captcha for this comment if the user is creating many comments
    # in a short period of time and if we are not editing an existing comment.
    require_captcha = False
    #if not request.user.is_anonymous() and request.user.id not in (1, 59):
    #    require_captcha = request.user.comments.filter(created__gt = datetime.now()-timedelta(days=20)).count() > 20 \
    #    and not request.user.comments.filter(bill = bill).exists()
    
    try:
        if len(request.POST) > 0: request.session.delete_test_cookie()
    except:
        pass
    
    if not "submitmode" in request.POST and position_original != "/finish":
        message = None
        has_been_delivered = False
        message_is_new = True

        request.goal = { "goal": "comment-begin" }
            
        # If the user has already saved a comment on this bill, load it up
        # as default values for the form.
        if position != "0" and request.user.is_authenticated():
            for c in request.user.comments.filter(bill = bill):
                request.goal = { "goal": "comment-edit-begin" }
                message = c.message
                has_been_delivered = c.has_been_delivered()
                message_is_new = False
                break
                
        # If we have a saved session, load the saved message.
        if pending_comment_session_key in request.session:
            message = request.session[pending_comment_session_key]["message"]
            
        # If we're coming from a customized org action page...
        if "orgcampaignposition" in request.POST:
            billpos = get_object_or_404(OrgCampaignPosition, id=request.POST["orgcampaignposition"], bill=bill)
            request.session["comment-referrer"] = {"bill": bill.id, "referrer": billpos.campaign }
            request.session["comment-default-address"] = (request.POST["name_first"], request.POST["name_last"], request.POST["zip"], request.POST["email"])
            if request.POST.get("share_with_org", "") == "1":
                request.session["comment-referrer"]["campaign"] = billpos.get_service_account_campaign().id
                billpos.get_service_account_campaign().add_action_record(
                    email = request.POST["email"],
                    firstname = request.POST["name_first"],
                    lastname = request.POST["name_last"],
                    zipcode = request.POST["zip"] )
    
        request.session.set_test_cookie() # tested in on the client side
        return render_to_response('popvox/billcomment_start.html', {
                'bill': bill,
                "position": position,
                "message": message,
                "has_been_delivered": has_been_delivered,
                "message_is_new": message_is_new,
            }, context_instance=RequestContext(request))
    
    elif ("submitmode" in request.POST and request.POST["submitmode"] == "Preview >") or (not "submitmode" in request.POST and position_original == "/finish" and not request.user.is_authenticated()):
        # The user clicks preview to get a preview page.
        # Or the user returns from a failed login.
        
        if "submitmode" in request.POST:
            # TODO: Validate that a message has been provided and that messages are
            # not too long or too short.
            message = request.POST.get("message", None)
            if message != None and (message.strip() == "" or message == "None"):
                message = None
        else:
            message = request.session[pending_comment_session_key]["message"]
        
        # If the user has to log in (via oauth etc), they will get redirected away, so
        # we will put the comment into a session variable which we handle when
        # they return here.
        #
        # This is also set in DelayedCommentAction.
        request.session[pending_comment_session_key] = {
            "bill": bill.url(),
            "position": position,
            "message": message
            }
        
        if message != None:
            request.goal = { "goal": "comment-preview" }
        else:
            request.goal = { "goal": "comment-nomessage" }

        return render_to_response('popvox/billcomment_preview.html', {
                'bill': bill,
                "position": position,
                "message": message,
                "email": request.session["comment-default-address"][3] if "comment-default-address" in request.session and type(request.session["comment-default-address"]) == tuple else "",
                "singlesignon_next": reverse(billcomment, args=[congressnumber, billtype, billnumber, "/finish"])
            }, context_instance=RequestContext(request))
        
    elif "submitmode" in request.POST and request.POST["submitmode"] == "< Go Back":
        # After clicking Preview, the user can go back and edit.
        request.goal = { "goal": "comment-revise" }
        return render_to_response('popvox/billcomment_start.html', {
                'bill': bill,
                "position": position,
                "message": request.POST["message"],
            }, context_instance=RequestContext(request))
        
    elif ("submitmode" in request.POST and request.POST["submitmode"] == "Next >") or (not "submitmode" in request.POST and position_original == "/finish"):
        if "submitmode" in request.POST:
            # User was already logged in and is just clicking to continue.
            message = request.POST.get("message", None)
        else:
            # User is returning from a login. Get the message info from the saved session.
            # OR user is coming from the last stage of the write congress widget
            message = request.session[pending_comment_session_key]["message"]

        request.goal = { "goal": "comment-addressform" }
        
        if address_record == None and "comment-default-address" in request.session:
            if type(request.session["comment-default-address"]) == PostalAddress:
                address_record = request.session["comment-default-address"]
            else:
                import writeyourrep.district_lookup
                address_record = PostalAddress()
                address_record.firstname = request.session["comment-default-address"][0]
                address_record.lastname = request.session["comment-default-address"][1]
                address_record.zipcode = request.session["comment-default-address"][2]
                address_record.state = writeyourrep.district_lookup.get_state_for_zipcode(address_record.zipcode)
            del request.session["comment-default-address"]
        
        return render_to_response('popvox/billcomment_address.html', {
                'bill': bill,
                "position": position,
                "message": message,
                "useraddress": address_record,
                "useraddress_fixed": address_record_fixed,
                "useraddress_prefixes": PostalAddress.PREFIXES,
                "useraddress_suffixes": PostalAddress.SUFFIXES,
                "useraddress_states": govtrack.statelist,
                "captcha": captcha_html() if require_captcha else "",
                "recipients": get_comment_recipients(bill, address_record),
            }, context_instance=RequestContext(request))

    elif request.POST["submitmode"] == "Use a Map >":
        request.goal = { "goal": "comment-address-map" }
        
        address_record = PostalAddress()
        address_record.user = request.user
        address_record.load_from_form(request.POST, validate=False)
        
        from writeyourrep.district_metadata import get_viewport
        bounds = get_viewport(address_record)
        
        return render_to_response('popvox/billcomment_address_map.html', {
            'bill': bill,
            "position": position,
            "message": request.POST["message"],
            "useraddress": address_record,
            "useraddress_prefixes": PostalAddress.PREFIXES,
            "useraddress_suffixes": PostalAddress.SUFFIXES,
            "useraddress_states": govtrack.statelist,
            "bounds": bounds,
            }, context_instance=RequestContext(request))
            
    elif request.POST["submitmode"] == "Submit Comment >" or request.POST["submitmode"] == "Clear Comment >":
        if not request.user.is_authenticated():
            raise Http404()
        
        if position == "0":
            # Clear the user's comment on this bill.
            request.goal = { "goal": "comment-clear" }
            request.user.comments.filter(bill = bill).delete()
            return HttpResponseRedirect("/home")
        
        request.goal = { "goal": "comment-submit-error" }
        
        message = request.POST["message"].strip()
        if message == "":
            message = None
        
        # Validation.
        
        if request.user.userprofile.is_leg_staff():
            return HttpResponse("Legislative staff cannot post comments on legislation.")
        if request.user.userprofile.is_org_admin():
            return HttpResponse("Organization staff cannot post comments on legislation.")
        
        # More validation.
        from writeyourrep.addressnorm import verify_adddress, AddressVerificationError
        try:
            # If we didn't lock the address, load it and validate it from the form.
            if address_record_fixed == None:
                # If we allow overwriting the existing address record, use it
                # and mark that we can save it if it's changed.
                if address_record and address_record_allow_save:
                    setattr(address_record, "pv_allow_save", True)
                # Otherwise initialize a new address object.
                else:
                    address_record = PostalAddress()
                    address_record.user = request.user
                    
                address_record.load_from_form(request.POST) # throws ValueError, KeyError
                
            # We don't display a captcha when we are editing an existing comment
            # or if the user has not left many comments yet.
            if require_captcha and not "latitude" in request.POST and not DEBUG:
                validate_captcha(request) # throws ValidationException and sets recaptcha_error attribute on the exception object
                
            if request.POST.get("latitude", "") != "":
                # If the user went to the map and specified a coordinate, skip address normalization.
                address_record.latitude = float(request.POST["latitude"])
                address_record.longitude = float(request.POST["longitude"])
                
                # But we have to convert the coordinate to a district...
                from writeyourrep.district_lookup import district_lookup_coordinate
                ret = district_lookup_coordinate(address_record.longitude, address_record.latitude,)
                if ret == None or ret[0] != address_record.state:
                    raise ValueError("You moved the marker to a location outside of the state indicated in your address.")
                address_record.congressionaldistrict = ret[1]
                
            elif BENCHMARKING:
                address_record.congressionaldistrict = -1

            elif address_record_fixed == None:
                # Now do verification against CDYNE to get congressional district.
                # Do this after the CAPTCHA to prevent any abuse.

                # if the address matches a previously entered address, don't recompute the district
                # (especially if we manually overrode it) --- it was probably a resubmission of
                # their last address that we provided as default values.
                for other in request.user.postaladdress_set.all():
                    if address_record.nameprefix == other.nameprefix and address_record.firstname == other.firstname and address_record.lastname == other.lastname and address_record.namesuffix == other.namesuffix and address_record.address1.lower() == other.address1.lower() and address_record.address2.lower() == other.address2.lower() and address_record.city.lower() == other.city.lower() and address_record.state == other.state and address_record.zipcode == other.zipcode and address_record.phonenumber == other.phonenumber:
                        address_record = other
                        break
                else:
                    verify_adddress(address_record)
                    
            # Save the address if it's been modified and the modifications passed validation.
            # If it wasn't modified, or it matched a previous address record, then we changed
            # the address_record variable above and it will no longer have the save flag.
            if hasattr(address_record, "pv_allow_save"):
                address_record.save()
        
        except Exception, e:
            import sys
            sys.stderr.write("leaving comment failed> " + unicode(e) + "\n")
            request.goal = { "goal": "comment-address-error" }
            return render_to_response('popvox/billcomment_address.html', {
                'bill': bill,
                "position": position,
                "message": request.POST["message"],
                "useraddress": address_record,
                "useraddress_fixed": address_record_fixed,
                "useraddress_prefixes": PostalAddress.PREFIXES,
                "useraddress_suffixes": PostalAddress.SUFFIXES,
                "useraddress_states": govtrack.statelist,
                "captcha": captcha_html(getattr(e, "recaptcha_error", None)) if require_captcha else "",
                "error": validation_error_message(e), # accepts ValidationError, KeyError, ValueError
                "error_is_validation": (isinstance(e, AddressVerificationError) and not e.mandatory) or str(e) == "cannot import name CDYNE_LICENSE_KEY",
                "recipients": get_comment_recipients(bill, address_record),
                }, context_instance=RequestContext(request))
        
            
        # Set the user's comment on this bill.
        
        request.goal = { "goal": "comment-submit" }

        # If the user came by a short URL to this bill, store the owner of
        # the short URL as the referrer on the comment.
        referrer = None
        campaign = None
        if "comment-referrer" in request.session and type(request.session["comment-referrer"]) == dict and request.session["comment-referrer"]["bill"] == bill.id:
            rx = request.session["comment-referrer"]
            
            referrer = rx.get("referrer", None)
            
            if "shorturl" in rx:
                import shorturl.models
                surl = shorturl.models.Record.objects.get(id=rx["shorturl"])
                surl.increment_completions()
                
            if "campaign" in rx:
                try: # sac/bill mismatch, ocp deleted?
                    campaign = ServiceAccountCampaign.objects.get(id=rx["campaign"], bill=bill)
                except:
                    pass
                
            del request.session["comment-referrer"]

        comment = save_user_comment(request.user, bill, position, referrer, message, address_record, campaign, UserComment.METHOD_SITE)
            
        # Clear the session state set in the preview. Don't clear until the end
        # because if the user is redirected back to ../finish we need the session
        # state to get the position.
        try:
            del request.session[pending_comment_session_key]
        except:
            pass
        
        return HttpResponseRedirect(comment.url())
            
    elif request.POST["submitmode"] == "Create Account >":
        # The user is creating an account.
            
        from registration.helpers import validate_username, validate_password, validate_email
        from profile import RegisterUserAction
        
        errors = { }
        username = validate_username(request.POST["createacct_username"], fielderrors = errors)
        password = validate_password(request.POST["createacct_password"], fielderrors = errors)
        email = validate_email(request.POST["createacct_email"], fielderrors = errors)

        if len(errors) > 0:
            request.goal = { "goal": "comment-register-error" }
            return render_to_response('popvox/billcomment_preview.html', {
                    'bill': bill,
                    "position": position,
                    "message": request.POST["message"],
                    "singlesignon_next": reverse(billcomment, args=[congressnumber, billtype, billnumber, "/finish"]),
                    "username": request.POST["createacct_username"],
                    "password": request.POST["createacct_password"],
                    "email": request.POST["createacct_email"],
                    "newaccount_error": errors,
                }, context_instance=RequestContext(request))
            
        else:
            # If no errors, begin the email verification process which will
            # delay the comment.

            axn = DelayedCommentAction()
            axn.registrationinfo = RegisterUserAction()
            axn.registrationinfo.email = email
            axn.registrationinfo.username = username
            axn.registrationinfo.password = password
            axn.bill = bill.id
            axn.comment_session_state = {
                "bill": bill.url(),
                "position": position,
                "message": request.POST["message"]
                }
            
            r = send_email_verification(email, None, axn, send_email=not BENCHMARKING)
            
            request.goal = { "goal": "comment-register-start" }

            # for BENCHMARKING, we want to get the activation link directly
            if BENCHMARKING:
                return HttpResponse(r.url(), mimetype="text/plain")

            return HttpResponseRedirect("/accounts/register/check_inbox?email=" + urllib.quote(email))
    
    else:
        raise Http404()

def user_may_change_address(existing_comment, address_record, user):
    # Returns "in-place" if the user may revise address_record in place, "new-record" if
    # the user may create a new address record, or otherwise a string message telling
    # the user when he may next update his address.
    
    now = datetime.datetime.now()

    # Logical consistency?
    if existing_comment and existing_comment.delivery_attempts.filter(success=True).exists():
        # If the user's comment has already been delivered, then the address cannot be changed.
        return "You cannot change the address on a comment that has already been delivered to your Members of Congress."
    elif existing_comment and existing_comment.delivery_attempts.exists():
        # If the user's comment has already been attempted to be delivered, then also do not
        # allow change in address, since there might have been a successful delivery that
        # is currently marked failure.
        return "You cannot change the address on a comment once it is marked for delivery to your Members of Congress."
    
    # Revising freshly entered data?
    elif address_record and (now - address_record.created).days < 21 and not address_record.usercomments.filter(delivery_attempts__id__gt=0).exists():
        # If this recent address is not tied to a message whose delivery has been attempted,
        # then the address record can be modified in place to affect all pending comments
        # tied to this address.
        return "in-place"
        
    # At this point, user is creating a new comment and the user's most recent address
    # has already been used in a delivery, or the most recent address is pretty old.
    # We be a little creative to prevent the sort of fraud of a user being in a different
    # district for each comment.
    else:
        # How long should we lock the user for?
        lock_until = now
        
        for i, addr in enumerate(user.postaladdress_set.order_by("-created")[0:4]):
            # Each time the user makes an address change it should be more difficult
            # to change the address again, up to a certain limit.
            #
            # i is the number of address changes made after addr was created. Enforce
            # a delay of 6^i-1 days after addr was created (up to a limit).
            #   215 days since the 4th address ago  (i=3 --- lock limit)
            #    35 days since the 3rd address ago  (i=2)
            #     5 days since the 2nd address ago  (i=1)
            #     0 days since the previous address (i=0 --- a freebie)
            #
            # In the long run, the user will have many (>4) addresses, and this prevents
            # more than 4 addresses in 216 days (about one address every two months).
            d = addr.created + timedelta(days=6**i - 1)
            lock_until = max(lock_until, d)

        if lock_until > now:
            d = (lock_until - now).total_seconds()
            if d > 60*60*24: # one day
                return ("Since you have changed your address frequently recently, you will not be able to update your address for %d more days." % round(d/(60.0*60.0*24.0)))
            elif d.seconds > 60*60: # an hour
                return ("Since you have changed your address frequently recently, you will not be able to update your address for %d more hours." % round(d/(60.0*60.0)))
            else:
                return ("Since you have changed your address frequently recently, you will not be able to update your address for %d more minutes." % round(d/60.0))

    return "new-record"

def save_user_comment(user, bill, position, referrer, message, address_record, campaign, method):
    # If a comment exists, update that record.
    comment = None
    for c in user.comments.filter(bill = bill):
        if comment == None:
            comment = c
        else:
            # If we see more than one, we'll update the first and delete the rest.
            c.delete()
    
    # When migrating one bill (typically a non-bill action) to another bill,
    # start saving comments on the original to the new bill.
    if bill.migrate_to: bill = bill.migrate_to

    # If we're not updating an existing comment record, then create a new one.
    if comment == None:
        comment = UserComment()
        comment.user = user
        comment.bill = bill
        comment.position = position
        comment.method = method
        comment.seq = bill.usercomments.count()
    
    # We're updating an existing record.
    else:
        comment.bill = bill # make sure existing comment record gets migrated
        if comment.position != position:
            comment.position = position
            # When the user switches sides, any comment diggs he previously left on the
            # other side must be cleared.
            comment.my_diggs.all().delete()
        
    comment.message = message

    if address_record.id == None: # (parsed from form, not from a fixed record)
        # If the user gives the same address as one on file for the user,
        # reuse the record.... but overwrite it with new info because
        # the user might have updated something non-meaningful or
        # we might have gotten new address info from the address
        # normalization.
        for addr in user.postaladdress_set.all():
            if address_record.equals(addr):
                address_record.id = addr.id
                break
        
        address_record.user = user
        if getattr(address_record, "created", None) == None: # I think because of pickling in the write congress
            address_record.created = datetime.datetime.now()                 # widget this gets set as null which causes exception
        address_record.save()
        
    comment.address = address_record
    comment.updated = datetime.datetime.now()
    comment.state = address_record.state
    comment.congressionaldistrict = address_record.congressionaldistrict

    if user.email.endswith("@popvox.com") or user.email.endswith(".popvox.com"):
        comment.status = UserComment.COMMENT_HOLD
    elif comment.status in (UserComment.COMMENT_REJECTED, UserComment.COMMENT_REJECTED_STOP_DELIVERY):
        comment.status = UserComment.COMMENT_REJECTED_REVISED
    else:
        comment.status = UserComment.COMMENT_NOT_REVIEWED

    comment.save()
    
    if referrer != None:
        UserCommentReferral.create(comment, referrer)
    
    if campaign != None:
        campaign.add_action_record(
            email = user.email,
            firstname = address_record.firstname,
            lastname = address_record.lastname,
            zipcode = address_record.zipcode,
            completed_comment = comment,
            completed_stage = "finished")
        
    return comment
                
@csrf_protect_if_logged_in
def billshare(request, congressnumber, billtype, billnumber, vehicleid, commentid = None):
    bill = getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)

    if bill.migrate_to:
        if not commentid:
            return HttpResponseRedirect(bill.migrate_to.url() + "/comment")
        else:
            return HttpResponseRedirect(bill.migrate_to.url() + "/comment/" + commentid)
            
    # Get the user's comment.
    user_position = None
    if commentid != None:
        comment = get_object_or_404(UserComment, id=int(commentid))
        if request.user.is_authenticated():
            try:
                user_position = request.user.comments.get(bill=bill)
            except:
                pass
    else:
        if not request.user.is_authenticated():
            return HttpResponseRedirect(bill.url())
        comment = request.user.comments.filter(bill = bill)
        if len(comment) == 0:
            return HttpResponseRedirect(bill.url())
        comment = comment[0]

    # Default message text from saved session state.
    message = None
    includecomment = True
    try:
        message, includecomment = request.session["billshare_share.state"]
        del request.session["billshare_share.state"]
    except:
        pass

    # Referral?
    
    if "shorturl" in request.session and request.session["shorturl"].target == comment:
        surl = request.session["shorturl"]
        request.session["comment-referrer"] = {"bill": bill.id, "referrer": surl.owner, "shorturl": surl.id}
        del request.session["shorturl"] # so that we don't indefinitely display the message

    comment_rejected = False
    if comment.status > UserComment.COMMENT_ACCEPTED and (not request.user.is_authenticated() or (not request.user.is_staff and not request.user.is_superuser)):
        comment_rejected = True

    # Widget follow-up session state.
    follow_up = request.session.get("follow_up", "")
    if "follow_up" in request.session: del request.session["follow_up"]

    finished_url = "/home"
    
    ## supercommittee feature redirect
    ## when we ran the supercommittee feature, we wanted to bring users back to the
    ## supercommittee page after they finished leaving a comment, but now we want
    ## to avoid this dependency to another part of the code.
    #from features import supercommittee_bill_list_ids
    #if bill.id in supercommittee_bill_list_ids:
    #    finished_url = "/supercommittee"

    return render_to_response('popvox/billcomment_view.html', {
            'bill': bill,
            "comment": comment,
            "message": message,
            "includecomment": includecomment,
            "follow_up": follow_up,
            "user_position": user_position,
            "SITE_ROOT_URL": SITE_ROOT_URL,
            "finished_url": finished_url,
            "show_share_footer": True,
        }, context_instance=RequestContext(request))

def billshare_userstate(request, congressnumber, billtype, billnumber, vehicleid, commentid = None):
    ret = { }
    bill = getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)
    if request.user.is_authenticated() and not request.user.userprofile.is_leg_staff() and not request.user.userprofile.is_org_admin():
        # Get the user's current position on the bill.
        for c in request.user.comments.filter(bill=bill):
            ret["user_position"] = {
                "position": c.position,
                "updated": formatDateTime(c.updated),
                "message": truncatewords(c.message, 30) if c.message else None,
                "url": c.url(),
            }
    return ret
billshare.user_state = billshare_userstate

def billshare_get_object(request, congressnumber, billtype, billnumber, vehicleid, commentid = None):
    if commentid != None:
        return get_object_or_404(UserComment, id=int(commentid))
    elif request.user.is_authenticated():
        bill = getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)
        return request.user.comments.filter(bill = bill)
    else:
        return None
billshare.get_object = billshare_get_object

def send_mail2(subject, message, from_email, recipient_list, fail_silently=False):
    from django.core.mail import EmailMessage
    msg = EmailMessage(
        subject = subject,
        body = message,
        from_email = SERVER_EMAIL,
        to = recipient_list,
        headers = {"From": from_email})
    msg.send(fail_silently=fail_silently)

@csrf_protect_if_logged_in # getting a link doesn't require being logged in
@json_response
def billshare_share(request):
    try:
        comment = UserComment.objects.get(id = int(request.POST["comment"]))
    except:
        return { "status": "fail", "msg": "Invalid call." }
    
    bill = comment.bill
    
    # There are three factors that affect how we share this comment:
    #
    # 1. a) The comment has no message.
    #     b) This is the user's own comment but he has chosen to share it anonymously
    #          (via includecomment=0), which works similarly to (a).
    #     c) The user is sharing his own comment.
    #     d) The user is sharing someone else's comment.
    #
    # 2. a) The comment was written during the normal bill commenting period.
    #     b) The comment was written in support of reintroduction of the bill.
    #     (These only apply to 1c/d.)
    #
    # 3. a) The bill is still alive, so it is a call for normal action.
    #     b) The bill is dead and the comment is in support, so it is a call to reintroduce.
    #     c) The bill is dead and the comment was against, so it is not a call for action.
        
    if comment.message == None or (request.user == comment.user and request.POST["includecomment"] == "0"): # 1a/b
        includecomment = False
        target = comment.bill
        
        if comment.bill.isAlive(): # 3a
            if comment.position == "+":
                subject = "Support"
            elif comment.position == "-":
                subject = "Oppose"
        elif comment.bill.died() and comment.position == "+":  # 3b
            subject = "Support the reintroduction of"
        else: # 3c
            subject = "Take a look at"
        
        message = comment.bill.title
        
        extra_message_default = "There is a " + comment.bill.proposition_type() + " on POPVOX.com that I thought you would be interested in."
        
    else: # 1c/d
        #if comment.status not in (UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED):
        #    return { "status": "fail", "msg": "This comment cannot be shared." }

        includecomment = True
        target = comment
        
        if request.user == comment.user: # 2
            subject = "I " + comment.verb(tense="past")
            message = comment.message
            extra_message_default = "I am sharing with you this letter I wrote to Congress using POPVOX.com."
        else:
            subject = "Check out this message " + comment.verb(tense="ing")
            message = comment.user.username + " wrote:\n\n" + comment.message    
            extra_message_default = "I found this letter to Congress using POPVOX.com."

    subject += " " + truncatewords(comment.bill.title, 10) + " at POPVOX"
    
    import shorturl
    if not request.user.is_authenticated():
        surlrec, created = shorturl.models.Record.objects.get_or_create(target=target)
    else:
        surlrec, created = shorturl.models.Record.objects.get_or_create(owner=request.user, target=target)
    url = surlrec.url()
    
    if request.POST["method"] == "email":
        # validate and clean the email addresses
        from django.forms import EmailField
        emails = []
        for em in re.split("[\s,]+", request.POST["emails"]):
            if em.strip() == "":
                continue
            try:
                emails.append( EmailField().clean(em) )
            except:
                return { "status": "fail", "msg": "Email address(es) don't look right." }
        
        if len(emails) > 10:
            return { "status": "fail", "msg": "You can only share your message with 10 recipients at a time." }
        
        extra_message = request.POST["message"].strip()
        if extra_message == "":
            extra_message = extra_message_default
        
        ###
        body = """%s

%s

Go to %s to have your voice be heard!""" % (
            extra_message,
            message,
            url)
        ###

        for em in emails:
            send_mail2(
                subject = subject,
                message = body,
                from_email = request.user.email,
                recipient_list = [em],
                fail_silently = True)

        return { "status": "success", "msg": "Message sent." }

    elif request.POST["method"] == "twitter":
        from settings import TWITTER_OAUTH_TOKEN, TWITTER_OAUTH_TOKEN_SECRET
        
        tweet = ""
        if not bill.hashtag() in request.POST["message"]:
            tweet += " " + bill.hashtag()
        tweet += " " + url
        if request.user == comment.user and includecomment:
            tweet += " #" + comment.address.state + str(comment.address.congressionaldistrict)
        tweet = request.POST["message"][0:140-len(tweet)] + tweet # trim msg so total <= 140 but we don't cut off the important bits at the end, like the url
        
        tok = request.user.singlesignon.get(provider="twitter").auth_token
        
        import oauthtwitter
        twitter = oauthtwitter.OAuthApi(
            TWITTER_OAUTH_TOKEN, TWITTER_OAUTH_TOKEN_SECRET,
            token = tok["oauth_token"], token_secret = tok["oauth_token_secret"])
        
        # TODO: we might want to set in_reply_to_status_id in the call to something interesting, like if this comment's referrer is a user and the user commented on the same bill, and tweeted, then that tweet_id.
        ret = twitter.UpdateStatus(tweet.encode('utf-8'))
        if type(ret) == urllib2.HTTPError and ret.code == 401:
            request.session["billshare_share.state"] = request.POST["message"], includecomment
            return { "status": "fail", "error": "not-authorized" }
        if type(ret) != dict:
            return { "status": "fail", "msg": unicode(ret) }
        if "error" in ret:
            return { "status": "fail", "msg": ret["error"] }
        
        if request.user == comment.user:
            comment.tweet_id = ret["id"]
            comment.save()
        
        return { "status": "success", "msg": "Tweet sent: " + tweet, "url": url }

    elif request.POST["method"] == "facebook":
        fb = request.user.singlesignon.get(provider="facebook")
        
        ret = urllib.urlopen("https://graph.facebook.com/" + str(fb.uid) + "/feed",
            urllib.urlencode({
                "access_token": fb.auth_token["access_token"],
                "link": url,
                "name": subject.encode('utf-8'),
                "caption": "Voice your opinion on this bill at POPVOX.com",
                "description": message.encode('utf-8'),
                "message": request.POST["message"].encode('utf-8')
                }))
        
        if ret.getcode() in (400, 403):
            request.session["billshare_share.state"] = request.POST["message"], includecomment
            return { "status": "fail", "error": "not-authorized", "scope": "publish_stream" }
        if ret.getcode() != 200:
            import sys
            sys.stderr.write("post failed> " + ret.read() + "\n")
            return { "status": "success", "msg": "Post failed (" + str(ret.getcode()) + ")" }
        ret = json.loads(ret.read())
        
        if request.user == comment.user:
            comment.fb_linkid = ret["id"]
            comment.save()

        return { "status": "success", "msg": "A link has been posted on your Wall.", "url": url }

    elif request.POST["method"] == "link":
        return { "status": "success", "msg": "Here is a link.", "url": url }

def billcomment_moderate(request, commentid, action):
    if not request.user.is_authenticated() or (not request.user.is_staff and not request.user.is_superuser):
        raise Http404()
        
    from django.core.mail import EmailMessage
    
    comment = UserComment.objects.get(id = commentid)

    if comment.moderation_log == None:
        comment.moderation_log = ""
    comment.moderation_log = \
        unicode(datetime.datetime.now()) + " " + request.user.username \
        + " set status to " +action + "\n" \
        + request.GET.get("log", "") + "\n\n" \
        + (comment.message if comment.message != None else "[no message]") \
        + "\n\n" + comment.moderation_log
        
    if comment.status == UserComment.COMMENT_NOT_REVIEWED:
        if action in ("reject", "reject-stop-delivery"):
            if action == "reject":
                comment.status = UserComment.COMMENT_REJECTED
            elif action == "reject-stop-delivery":
                comment.status = UserComment.COMMENT_REJECTED_STOP_DELIVERY
                
            comment.save()
            
            msg = EmailMessage(
                subject = "Your comment on " + comment.bill.shortname + " at POPVOX needs to be revised",
                body = """Dear %s,

After reviewing the comment you left on POPVOX about the bill %s, we have
decided that it violates our guidelines for acceptable language. Comments
may not be profane, harassing, or threatening to others and may not include the
personal, private information of others. For our full guidelines, please see:

  https://www.popvox.com/legal

At this time, your comment has been hidden from the legislative reports that other
users see, and it may not be delivered to Congress.

We encourage you to revise your comment so that it meets our guidelines. After
you revise your comment, we will review it and hope to post it back on POPVOX.
You can revise your comment by following this link:

  https://www.popvox.com/home

Thank you,

POPVOX

(Please note that our decision is final.) 
""" % (comment.user.username, comment.bill.shortname),
                from_email = SERVER_EMAIL,
                to = [comment.user.email])
            msg.send(fail_silently=True)
    
    if comment.status == UserComment.COMMENT_REJECTED_REVISED:
        if action == "accept":
            comment.status = UserComment.COMMENT_ACCEPTED
            comment.save()
            msg = EmailMessage(
                subject = "Your revised comment on " + comment.bill.shortname + " at POPVOX has been accepted",
                body = """Dear %s,

After reviewing the revisions you made to the comment you left on POPVOX
about the bill %s, we have decided to restore your comment. Thank you
for taking the time to follow our language guidelines. Your comment now
appears on bill reports and other pages of POPVOX.

Thank you,

POPVOX
""" % (comment.user.username, comment.bill.shortname),
                from_email = SERVER_EMAIL,
                to = [comment.user.email])
            msg.send(fail_silently=True)
            
    return HttpResponseRedirect(comment.url())

def get_default_statistics_context(user, individuals=True):
    if hasattr(user, "popvox_default_statistics_context"):
        return user.popvox_default_statistics_context
    
    default_state = None
    default_district = None
    if user.is_authenticated():
        if user.userprofile.is_leg_staff():
            member = govtrack.getMemberOfCongress(user.legstaffrole.member_id)
            if member["current"]:
                default_state = member["state"]
                if member["type"] == "rep":
                    default_district = member["district"]
        elif individuals and False: # individuals dont seem to like to see local statistics
            addresses = user.postaladdress_set.order_by("-created")
            if len(addresses) > 0:
                default_state = addresses[0].state
                default_district = addresses[0].congressionaldistrict
    
    user.popvox_default_statistics_context = (default_state, default_district)    
            
    return default_state, default_district

@strong_cache
def billreport(request, congressnumber, billtype, billnumber, vehicleid):
    bill = getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)

    if bill.migrate_to:
        return HttpResponseRedirect(bill.migrate_to.url() + "/report")

    orgs_support = { }
    orgs_oppose = { }
    orgs_neutral = { }
    orgs_other = { }
    for pos in bill.campaign_positions():
        if pos.campaign.org.id == 2123:
            lst = orgs_other
        elif pos.position == "+":
            lst = orgs_support
        elif pos.position == "-":
            lst = orgs_oppose
        else:
            lst = orgs_neutral
        if not pos.campaign.org in lst:
            lst[pos.campaign.org] = {
                "has_document": pos.campaign.org.documents.filter(bill=bill).exists(),
                }
    orgs_support = list(orgs_support.items())
    orgs_oppose = list(orgs_oppose.items())
    orgs_neutral = list(orgs_neutral.items())
    orgs_other = list(orgs_other.items())
    for lst in orgs_support, orgs_oppose, orgs_neutral, orgs_other:
        lst.sort(key = lambda x : x[0].name.replace("The ", ""))

    bot_comments = []
    if "static" in request.GET:
        limit = 50
        pro_comments = bill_comments(bill, position="+").filter(message__isnull = False, status__in=(UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED))[0:limit]
        con_comments = bill_comments(bill, position="-").filter(message__isnull = False, status__in=(UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED))[0:limit]
        bot_comments = list(pro_comments) + list(con_comments)
        
    ## generate a tag cloud
    #TODO: Cache
    tag_cloud_support = False
    tag_cloud_oppose = False
    if False:
        text = { "+": "", "-": "" }
        for comment in bill_comments(bill).filter(message__isnull = False, status__in=(UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED)):
            text[comment.position] += comment.message + " "
        from utils import compute_frequencies, make_tag_cloud
        text["+"] = compute_frequencies(text["+"], stop_list=["support"])
        text["-"] = compute_frequencies(text["-"], stop_list=["oppose"])
        tag_cloud_support = make_tag_cloud(text["+"], text["-"], 50*4, 7, 9, 22, count_by_chars=True, width=350, color="#CC6A11")
        tag_cloud_oppose = make_tag_cloud(text["-"], text["+"], 50*4, 7, 9, 22, count_by_chars=True, width=350, color="#CC6A11")
        

    return render_to_response('popvox/bill_report.html', {
            'bill': bill,
            "orgs_supporting": orgs_support,
            "orgs_opposing": orgs_oppose,
            "orgs_neutral": orgs_neutral,
            "orgs_other": orgs_other,
            "stateabbrs": 
                [ (abbr, govtrack.statenames[abbr]) for abbr in govtrack.stateabbrs],
            "statereps": getStateReps(),
            "bot_comments": bot_comments,
            "tag_cloud_support": tag_cloud_support,
            "tag_cloud_oppose": tag_cloud_oppose,
            "show_share_footer": True,
        }, context_instance=RequestContext(request))
def billreport_userstate(request, congressnumber, billtype, billnumber, vehicleid):
    ret = { }
    bill = getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)
    if request.user.is_authenticated():
        # Is the user tracking the bill?
        ret["tracked"] = request.user.userprofile.tracked_bills.filter(id=bill.id).exists()

        # Default statistics context.
        default_state, default_district = get_default_statistics_context(request.user, individuals=False)
        ret["default_state"] = default_state if default_state else ""
        ret["default_district"] = default_district if default_district else ""
        
    return ret
billreport.user_state = billreport_userstate
def billreport_get_object(request, congressnumber, billtype, billnumber, vehicleid):
    return getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)
billreport.get_object = billreport_get_object

def can_appreciate(request, bill):
    # Can I appreciate comments? Only if I've weighed in on this bill and
    # then only on the side I've weighed in on, or if I'm leg staff. Returns
    # None if the user cannot appreciate any comments, True if the user
    # can appreciate all comments, or the user's comment if he is restricted
    # to commenting on the same side.
    if request.user.is_authenticated():
        if request.user.userprofile.is_leg_staff():
            return True
        comments = request.user.comments.filter(bill = bill)
        if len(comments) > 0:
            return comments[0]
    return False

@json_response
def billreport_getinfo(request, congressnumber, billtype, billnumber, vehicleid):
    # Get report information.
    
    bill = getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)
    
    state = request.REQUEST["state"] if "state" in request.REQUEST and request.REQUEST["state"].strip() != "" else None
    
    district = int(request.REQUEST["district"]) if state != None and "district" in request.REQUEST and request.REQUEST["district"].strip() != "" else None
    
    start = int(request.REQUEST.get("start", "0"))
    limit = int(request.REQUEST.get("count", "50"))
    
    def fetch(p):
        cache_key = ("billreport_getinfo_%d,%s,%s,%s,%d,%d" % (bill.id, p, state, str(district), start, limit))
        ret = cache.get(cache_key)
        if ret != None: return ret
        
        q = bill_comments(bill, position=p, state=state, congressionaldistrict=district)\
            .filter(message__isnull = False, status__in=(UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED))\
            .only("id", "created", "updated", "message", "position", "state", "congressionaldistrict", "bill__id", "bill__congressnumber", "bill__billtype", "bill__billnumber", "user__username", "address__id", "user__email")\
            .order_by("-created")
        count = q.count()
        '''limited = False
        if q.count() > limit:
            q = q[start:limit]
            limited = True
        else:
            q = q[start:]'''
            
        cache.set(cache_key, (q,count), 60*2) # cache results for two minutes
            
        '''return q, limited'''
        return q, count
    
    pro_comments, pro_count = fetch("+")
    con_comments, con_count = fetch("-")
    
    if state == None:
        reporttitle = "Legislative Report for POPVOX Nation"
    elif district == None or district == 0:
        reporttitle = "Legislative Report for " +  govtrack.statenames[state]
    else:
        reporttitle = "District Report for " + state + "-" + str(district)
    
    reportsubtitle = ""
    if state != None:
        reportsubtitle = \
            "Represented by " \
            + re.sub(r"\[[^\]]*\]", "", 
                " and ".join(
                    [p["name"] for p in 
                        getMembersOfCongressForDistrict(state + str(district),
                            moctype="rep" if district != None else "sen")]
                    )
                )
            
    # Functions for formatting comments.
    
    t = re.escape(bill.title).replace(":", ":?")
    re_because = re.compile(r"I (support|oppose) " + t + r" because[\s\.:]*(\S)") # remove common text
    re_because_repl = lambda x : x.group(2).upper()
    re_whitespace = re.compile(r"\n+\W*$") # remove trailing non-textual characters
    def msg(m):
        m = re_because.sub(re_because_repl, m)
        m = re_whitespace.sub("", m)
        return m

    from django.contrib.humanize.templatetags.humanize import ordinal
    def location(c):
        if district != None:
            return None
        if state != None:
            if c.congressionaldistrict == 0:
                return None
            return c.state + "-" + str(c.congressionaldistrict)
        if c.congressionaldistrict > 0:
            return statenames[c.state] + "'s " + ordinal(c.congressionaldistrict) + " District"
        return statenames[c.state] + " At Large"

    bill_end_congress = govtrack.getCongressDates(bill.congressnumber)[1]
    def verb(c):
        if c.created.date() <= bill_end_congress:
            if c.position == "+": return "supported"
            return "opposed"
        else:
            if c.position == "+": return "supported the reintroduction of"
            return "opposed the reintroduction of"

    # Appreciation

    # Can the user appreciate comments?
    appreciate = can_appreciate(request, bill)
    if type(appreciate) == UserComment:
        appreciate = appreciate.position
    elif appreciate:
        appreciate = "both"
    else:
        appreciate = "none"

    # Get the user's current set of appreciated comments, rather than query on each comment
    # if the user appreciated it.
    user_appreciated = set()
    if request.user.is_authenticated():
        for c in UserComment.objects.filter(diggs__diggtype=UserCommentDigg.DIGG_TYPE_APPRECIATE, diggs__user=request.user):
            user_appreciated.add(c.id)
    
    # Pre-load the count of num_appreciations.
    num_appreciations_pro = {}
    q = UserCommentDigg.objects.filter(
        comment__id__in = [c.id for c in pro_comments],
        diggtype = UserCommentDigg.DIGG_TYPE_APPRECIATE)\
        .values("comment")\
        .annotate(num_diggs=Count("id"))\
        .values("comment_id", "num_diggs")
    for c in q:
        num_appreciations_pro[c["comment_id"]] = c["num_diggs"]

    num_appreciations_con = {}
    q = UserCommentDigg.objects.filter(
        comment__id__in = [c.id for c in con_comments],
        diggtype = UserCommentDigg.DIGG_TYPE_APPRECIATE)\
        .values("comment")\
        .annotate(num_diggs=Count("id"))\
        .values("comment_id", "num_diggs")
    for c in q:
        num_appreciations_con[c["comment_id"]] = c["num_diggs"]

        
    # Legislative staff?
    show_private_info = False
    if state != None and request.user.is_authenticated() and request.user.userprofile.is_leg_staff() and request.user.legstaffrole.member:
        moc = govtrack.getMemberOfCongress(request.user.legstaffrole.member_id)
        show_private_info = moc["current"] and moc["state"] == state and (moc["type"] == "sen" or moc["district"] == district)
        
    # For legislative staff, show a town-by-town breakdown?
    by_town = None
    if show_private_info:
        # Gather aggregate stats by the user's address's city.
        by_town = { }
        for rec in bill_comments(bill, state=state, congressionaldistrict=district)\
            .values("position", "address__city")\
            .annotate(count=Count('address__city'))\
            .order_by():
            if not rec["address__city"] in by_town:
                by_town[rec["address__city"]] = { "name": rec["address__city"], "+": 0, "-": 0 }
            by_town[rec["address__city"]][rec["position"]] = rec["count"]
        # Sort.
        by_town = sorted(by_town.values(), key=lambda x : x["name"].lower())
        
    # For admins, show a breakdown by source.
    by_source = None
    if request.user.is_superuser or request.user.is_staff:
        by_source = { }
        for rec in bill_comments(bill, state=state, congressionaldistrict=district)\
            .values("method", "usercommentreferral__referrer_content_type", "usercommentreferral__referrer_object_id")\
            .annotate(count=Count('id'))\
            .order_by():
                
            # convert dict of content type and obj id into object
            method_name = UserComment.METHOD_NAMES[rec["method"]]
            if rec["usercommentreferral__referrer_content_type"] == None:
                referrer = method_name
            else:
                try:
                    from django.contrib.contenttypes.models import ContentType
                    referrer = ContentType.objects.get(id=rec["usercommentreferral__referrer_content_type"]).get_object_for_this_type(id=rec["usercommentreferral__referrer_object_id"])
                    referrer = unicode(referrer)
                except OrgCampaign.DoesNotExist:
                    referrer = "[Campaign Deleted]"
                except ServiceAccount.DoesNotExist:
                    referrer = "[Service Account Deleted]"
                referrer += " (" + method_name + ")"
            
            by_source[referrer] = rec["count"]
        by_source = sorted(by_source.items(), key=lambda x : -x[1]) # Sort
        
            
    # Return.
    
    bill_url = bill.url()
    
    debug_info = None
    if DEBUG:
        from django.db import connection
        debug_info = "".join(["%s: %s\n" % (q["time"], q["sql"]) for q in connection.queries])
        
    pro_comments_data_basic = [ {
                "id": c.id,
                "user": c.user.username,
                "msg": msg(c.message),
                "location": location(c),
                "date": formatDateTime(c.created),
                "pos": c.position,
                "share": bill_url + "/comment/" + str(c.id), #c.url(),
                "verb": verb(c), #c.verb(tense="past"),
                "private_info": { "name": c.address.name_string(), "address": c.address.address_string(), "email": c.user.email } if show_private_info else None,
                "appreciates": num_appreciations_pro[c.id] if c.id in num_appreciations_pro else 0,
                "appreciated": c.id in user_appreciated,
                "state": c.state,
                "district": c.congressionaldistrict
                } for c in pro_comments ]
                


    if pro_count > limit:
        pro_comments_data = sorted(pro_comments_data_basic, key=operator.itemgetter('appreciates'), reverse=True)[start:limit]
        pro_limited=True
    else:
        pro_comments_data = sorted(pro_comments_data_basic, key=operator.itemgetter('appreciates'), reverse=True)[start:]
        pro_limited=False

    con_comments_data_basic = [ {
                "id": c.id,
                "user": c.user.username,
                "msg": msg(c.message),
                "location": location(c),
                "date": formatDateTime(c.created),
                "pos": c.position,
                "share": bill_url + "/comment/" + str(c.id), #c.url(),
                "verb": verb(c), #c.verb(tense="past"),
                "private_info": { "name": c.address.name_string(), "address": c.address.address_string(), "email": c.user.email } if show_private_info else None,
                "appreciates": num_appreciations_con[c.id] if c.id in num_appreciations_con else 0,
                "appreciated": c.id in user_appreciated,
                "state": c.state,
                "district": c.congressionaldistrict
                } for c in con_comments ]
                

    if con_count > limit:
        con_comments_data = sorted(con_comments_data_basic, key=operator.itemgetter('appreciates'), reverse=True)[start:limit]
        con_limited=True
    else:
        con_comments_data = sorted(con_comments_data_basic, key=operator.itemgetter('appreciates'), reverse=True)[start:]
        con_limited=False

    comments_data_basic = pro_comments_data + con_comments_data
    comments_data = sorted(comments_data_basic, key=operator.itemgetter('appreciates'), reverse=True)

    return {
        "reporttitle": reporttitle,
        "reportsubtitle": reportsubtitle,
        
        "can_appreciate": appreciate,
        
        "pro_more": pro_limited,
        "con_more": con_limited,
        
        "debug_info": debug_info,
        
        "approved_for_private_info": show_private_info,
    
        "comments": comments_data,
        "stats": {
            "overall": bill_statistics(bill, "POPVOX", "POPVOX Nation", want_timeseries=True, want_totalcomments=True, force_data=True),
            "state": bill_statistics(bill,
                state,
                govtrack.statenames[state],
                want_timeseries=True,
                want_totalcomments=True,
                state=state)
                    if state != None else None,
            "district": bill_statistics(bill,
                state + "-" + str(district),
                state + "-" + str(district),
                want_timeseries=True,
                want_totalcomments=True,
                state=state,
                congressionaldistrict=district)
                    if state != None and district not in (None, 0) else None,
            "by_town": by_town,
            "by_source": by_source,
        }
    }

@csrf_protect
@json_response
def comment_digg(request):
    bill = get_object_or_404(Bill, id=request.POST.get("bill", -1))
    comment = get_object_or_404(UserComment, id=request.POST.get("comment", -1))
    
    appreciate = can_appreciate(request, bill)
    if not appreciate or (type(appreciate) == UserComment and appreciate.position != comment.position):
        return { "status": "fail", "msg": "invalid action" }
        
    d = UserCommentDigg.objects.filter(comment=comment, diggtype=UserCommentDigg.DIGG_TYPE_APPRECIATE, user=request.user)
    if request.POST["action"] == "-":
        d.delete()
        action = "-"
    else:
        if len(d) == 0:
            d = UserCommentDigg(
                comment=comment,
                diggtype=UserCommentDigg.DIGG_TYPE_APPRECIATE,
                user=request.user)
            if type(appreciate) == UserComment:
                d.source_comment = appreciate
            d.save()
        action = "+"
        
    return { "status": "success", "action": action, "count": UserCommentDigg.objects.filter(comment=comment, diggtype=UserCommentDigg.DIGG_TYPE_APPRECIATE).count() }

@json_response
def getbillshorturl(request):
    if "billposid" in request.POST:
        pos = get_object_or_404(OrgCampaignPosition, id=request.POST["billposid"])
        
        org = pos.campaign.org
        if not org.is_admin(request.user) :
            return HttpResponseForbidden("Not authorized.")
            
        owner = pos.campaign
        bill = pos.bill
    elif "billid" in request.POST:
        if request.user.is_authenticated():
            owner = request.user
        else:
            owner = None
        bill = get_object_or_404(Bill, id=request.POST["billid"])
    else:
        raise Http404()
    
    import shorturl
    surl, created = shorturl.models.Record.objects.get_or_create(owner=owner, target=bill)
    
    return { "status": "success", "url": surl.url(), "new": created }

def uploaddoc1(request):
    prof = request.user.userprofile
    
    if request.user.is_anonymous():
        raise Http404()
    elif prof.is_leg_staff() and request.user.legstaffrole.member != None:
        types = ((0, "Press Release"), (1, "Introductory Statement"), (2, "Dear Colleague"), (99, "Other Document"))
        whose = request.user.legstaffrole.bossname
        docs = request.user.legstaffrole.memberbio().documents
    elif "org" in request.GET:
        org = Org.objects.get(slug=request.GET["org"])
        if not org.is_admin(request.user):
            raise Http404()
        types = ((0, "Press Release"), (3, "Report"), (4, "Letter to Congress"), (5, "Coalition Letter"), (99, "Other Document"))
        whose = org.name
        docs = org.documents
    else:
        raise Http404()
        
    return types, whose, docs

@csrf_protect
@login_required
def uploaddoc(request, congressnumber, billtype, billnumber, vehicleid):
    types, whose, docs = uploaddoc1(request)
        
    bill = getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)
    
    # check which documents are already uploaded
    types = [
        (typecode, typename, docs.filter(bill=bill, doctype=typecode).exists())
        for (typecode, typename) in types]
    
    return render_to_response('popvox/bill_uploaddoc.html', {
        'whose': whose,
        'types': types,
        'bill': bill,
        }, context_instance=RequestContext(request))

@login_required
@json_response
def getdoc(request):
    types, whose, docs = uploaddoc1(request)
        
    bill = get_object_or_404(Bill, id=request.POST["billid"])
    
    doctype = int(request.POST["doctype"])

    try:
        doc = docs.get(bill = bill, doctype = doctype)
        return { "title": doc.title, "text": doc.text, "link": doc.link, "updated": doc.updated.strftime("%x") }
    except:
        return { "status": "doesnotexist" }

@csrf_protect
@login_required
@json_response
def uploaddoc2(request):
    types, whose, docs = uploaddoc1(request)
    
    bill = get_object_or_404(Bill, id=request.POST["billid"])
    doctype = int(request.POST["doctype"])
    
    if request.POST.get("title", "").strip() == "" and strip_tags(request.POST.get("text", "").replace("&nbsp;", "")).strip() == "" and request.POST.get("link", "").strip() == "":
        try:
            doc = docs.get(bill = bill, doctype = doctype)
            doc.delete()
            return { "status": "success", "action": "delete" }
        except:
            # If there was no document to delete, then fall through because the user must be intenting to save...
            pass

    title = forms.CharField(min_length=5, max_length=128, error_messages = {'min_length': "The title is too short.", "max_length": "The title is too long.", "required": "The title is required."}).clean(request.POST.get("title", "")) # raises ValidationException
        
    text = forms.CharField(min_length=100, max_length=32767, error_messages = {'min_length': "The body text is too short.", "max_length": "The body text is too long.", "required": "The document text is required."}).clean(request.POST.get("text", "")) # raises ValidationException
    text = sanitize_html(text)
    
    link = request.POST.get("link", "")    
    if link != "" and link[0:7] != "http://":
        link = "http://" + link
    link = forms.URLField(required=False, verify_exists = True).clean(link) # raises
    
    if request.POST["validate"] != "validate":
        doc, is_new = docs.get_or_create(
            bill = bill,
            doctype = doctype,
            defaults = { "created": datetime.datetime.now() })
        doc.title = title
        doc.text = text
        doc.link = link
        doc.save()
    
    return { "status": "success", "action": "upload" }

def billdoc(request, congressnumber, billtype, billnumber, vehicleid, orgslug, doctype):
    bill = getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)
    
    from org import set_last_campaign_viewed
    org = get_object_or_404(Org, slug=orgslug, visible=True)
    set_last_campaign_viewed(request, org)
    
    try:
        doc = org.documents.get(bill=bill, doctype=doctype)
    except:
        raise Http404()
        
    return render_to_response('popvox/bill_doc_org.html', {
        'org': org,
        'bill': bill,
        'doc': doc,
        'admin': org.is_admin(request.user),
        'docupdated': doc.updated.strftime("%b %d, %Y %I:%M %p"),
        "show_share_footer": True,
        }, context_instance=RequestContext(request))

