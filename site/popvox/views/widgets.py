from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.views.decorators.cache import cache_page
from django.db.models import Count
from django.contrib.auth.models import AnonymousUser

from popvox.models import *
from popvox.views.main import strong_cache
from popvox.views.bills import bill_comments
from popvox.govtrack import statenames, ordinate, CURRENT_CONGRESS

from settings import SITE_ROOT_URL

import urllib

def do_not_track_compliance(f):
    def g(request, *args, **kwargs):
        # Do-Not-Track Compliance: Don't record in traffic stats. Don't set a session cookie
        # by not touching the session object: to enforce, clear the session object. Don't
        # even *use* the session!
        request.goal = None
        request.session = None
        return f(request, *args, **kwargs)
    return g
        
@strong_cache
@do_not_track_compliance
def bill_js(request):
    try:
        bill = None if not "bill" in request.GET else bill_from_url("/bills/us/" + request.GET["bill"])
        if bill.migrate_to:
            bill = bill.migrate_to
    except:
        bill = None
    
    return render_to_response('popvox/widgets/bill.js', {
        "siteroot": SITE_ROOT_URL,
        "bill": bill
    }, context_instance=RequestContext(request),
    mimetype="text/javascript")

@strong_cache
@do_not_track_compliance
def bill_iframe(request):
    try:
        bill = None if not "bill" in request.GET else bill_from_url("/bills/us/" + request.GET["bill"])
        if bill.migrate_to:
            bill = bill.migrate_to
    except:
        bill = None
       
    
    return HttpResponse("""<html><body><script src="/widgets/js/bill.js?%sstats=%d&title=%d&iframe=%d"> </script></body></html>""" % (
        ("bill=" + bill.url().replace("/bills/us/", "") + "&") if bill else "",
        int(request.GET.get("stats", "0")),
        int(request.GET.get("title", "0")),
        int(request.GET.get("iframe", "0"))))
        

@do_not_track_compliance
def bill_inline(request):

    if "bill" in request.GET:
        try:
            bill = bill_from_url("/bills/us/" + request.GET["bill"])
        except:
                return HttpResponseBadRequest("<small>(No bill with that number exists)</small>.")
    else:
        return HttpResponseBadRequest("Invalid URL.")
    
    if bill.migrate_to:
        bill = bill.migrate_to
    
    billtype = bill.billtypeslug().upper()
    billnum = billtype+' '+str(bill.billnumber)
    total = bill.usercomments.get_query_set().count()
    if total == 0:
        pro = 0
        con = 0
    else:
        pro = (100.0) * bill.usercomments.get_query_set().filter(position='+').count()/total
        con = (100.0) * bill.usercomments.get_query_set().filter(position='-').count()/total
    
    return HttpResponse("""<html><head> <link rel="stylesheet" href="/media/master/reset.css" type="text/css" media="screen" /> 
    <link rel="stylesheet" href="/media/master/stylesheet.css" type="text/css" media="screen" /> 
    <link rel="stylesheet" href="/media/master/fonts.css" type="text/css" media="screen" /> </head><body style="background:transparent"><div class="widget_mini"><p><strong width="4em">%s</strong><span class="w_stats"><em class="supporting">%d&#37;</em><em class="opposing">%d&#37;</em> by <a href="#">POPVOX</a></span><span class="w_end"></span></p></div> </body></html>""" % (
    billnum,
    int(pro),
    int(con)))

    '''except:
        bill = None
        raise Http404'''

@do_not_track_compliance
def commentmapus(request):
    print "0"
    count = { }
    totals = None
    max_count = 0
    bill = None
    width = int(request.GET.get("width", "720"))
    
    comments = None

    import widgets_usmap
    
    if "bill" in request.GET and request.GET["bill"].isdigit():
        bill = get_object_or_404(Bill, id=request.GET["bill"])
        
        # TODO: put this in the database
        comments = bill_comments(bill).only("state", "congressionaldistrict", "position")

        # strongly cache the page, but only for bill maps because sac maps
        # require authentication.
        request.strong_cache = True
        request.session = None
        request.user = AnonymousUser()
        
    elif "sac" in request.GET and request.user.is_authenticated():
        if not request.user.has_perm("popvox.can_snoop_service_analytics"):
            # validate the service account campaign is in one of the accounts accessible
            # by the logged in user.
            user_accounts = request.user.userprofile.service_accounts(create=False)
            sac = get_object_or_404(ServiceAccountCampaign, id=request.GET["sac"], account__in=user_accounts)
        else:
            sac = get_object_or_404(ServiceAccountCampaign, id=request.GET["sac"])
        
        bill = sac.bill
        comments = UserComment.objects.filter(actionrecord__campaign=sac).only("state", "congressionaldistrict", "position")
        
    elif "file" in request.GET:
        
        if request.GET["file"] == "cd_clusters":
            import csv, os.path
            for row in csv.reader(open(os.path.dirname(__file__) + "/../analysis/cd_clusters.txt")):
                if row[0] == "cd": continue
                count[row[0]] = {}
                count[row[0]]["class"] = ("dot_clr_%d dot_sz_%d" % ([1,5,3][int(row[1])-1], [3,3,1][int(row[1])-1]))

    elif "point" in request.GET:
        if request.GET["point"] == "all":
            for k in widgets_usmap.district_locations:
                count[k] = { }
                count[k]["class"] = "dot_clr_1 dot_sz_1"
        elif request.GET["point"] == "allcount":
            comments = UserComment.objects.all().only("state", "congressionaldistrict", "position", "bill")
            bill_party = { }
            def getpartyscore(comment):
                # return + for comments that support D-sponsored bills or oppose R-sponsored
                # bills and - for comments that oppose D-sponsored bills or support R-sponsored
                # bills.
                if comment.bill_id in bill_party:
                    p = bill_party[comment.bill_id]
                else:
                    sp = comment.bill.sponsor
                    if sp == None:
                        p = "0"
                    else:
                        p = comment.bill.sponsor.party()
                    bill_party[comment.bill_id] = p
                if not p in ("D", "R"): return "0"
                if p == "D": return comment.position
                if p == "R": return "+" if comment.position == "-" else "-"
        else:
            k = request.GET["point"]
            count[k] = { }
            count[k]["class"] = "dot_clr_5 dot_sz_5"
        
    by_date = False

    if comments != None:
        if by_date:
            comment_earliest = comments.order_by('created')[0].created
            comment_latest = comments.order_by('-created')[0].created
            comment_duration = (comment_latest-comment_earliest).total_seconds()
            
        totals = { "+": 0, "-": 0, "0": 0 } # 0 is only used in special cases
        
        for comment in comments:
            district = comment.state + str(comment.congressionaldistrict)
            if not district in count:
                count[district] = { "+": 0, "-": 0, "mean_date": 0, "0": 0} # 0 is used only in special cases
            p = comment.position
            if request.GET.get("point", "") == "allcount":
                p = getpartyscore(comment)
            count[district][p] += 1
            totals[p] += 1
            
            if by_date:
                count[district]["mean_date"] += (comment.created - comment_earliest).total_seconds()
    
        if not by_date:
            max_count = 0
            for district in count:
                max_count = max(max_count, count[district]["+"] + count[district]["-"])
            
            def chartcolor(district):
                return "dot_clr_%d dot_sz_%d" % (
                    int(district["sentiment"]*4.9999) + 1,
                    int(float(district["count"]) / float(max_count) * 4.9999) + 1
                    )

            if request.GET.get("point", "") == "allcount":
                def chartcolor(district):
                    import math
                    return "dot_clr_%d dot_sz_%d" % (
                        int(district["sentiment"]*4.9999) + 1,
                        int(math.sqrt(float(district["count"]) / float(max_count)) * 4.9999) + 1
                        )
    
        else:
            def chartcolor(district):
                return "dot_clr_%d dot_sz_%d" % (
                    #int(district["sentiment"]*4.9999) + 1,
                    6 - (int(float(district["mean_date"]) / float(district["count"]) / float(comment_duration) * 4.9999) + 1),
                    2
                    )
        

    mapscale = float(width) / widgets_usmap.map_scale[0]
    xoffset = int(8 * float(width)/720)
    yoffset = int(190 * float(width)/720)+5
    
    for district in count:
        # Some invalid congressional districts!
        if not district in widgets_usmap.district_locations:
            continue

        if comments:
            count[district]["sentiment"] = float(count[district]["+"])/float(count[district]["+"] + count[district]["-"])
            count[district]["count"] = count[district]["+"] + count[district]["-"]
            
            count[district]["class"] = chartcolor(count[district])
            
        count[district]["coord"] = { "left": int(widgets_usmap.district_locations[district][0]*mapscale)-xoffset,  "top": int(widgets_usmap.district_locations[district][1]*mapscale)-yoffset }
        
        count[district]["href"] = "state=" + district[0:2] + "&district=" + district[2:]
        
        if int(district[2:]) == 0:
            count[district]["label"] = statenames[district[0:2]] + u"\u2019s At-Large District"
        else:
            count[district]["label"] = statenames[district[0:2]] + u"\u2019s " + district[2:] + ordinate(int(district[2:])) + " District"
    
    return render_to_response('popvox/widgets/commentsmapus.html', {
        "bill": bill,
        "data": count.items(),
        "min_sz_num": int(float(max_count)/5.0) if max_count > 5 else 1,
        "max_sz_num": max_count,
        "width": width,
        "totals": totals,
    }, context_instance=RequestContext(request))

@strong_cache
@do_not_track_compliance
def top_bills(request):
    congressnumber = CURRENT_CONGRESS
    count = 8
    
    # Select bills with the most number of recent comments.
    bills = []
    max_count = 0
    max_sup = 0
    max_opp = 0
    for b in Bill.objects.filter(congressnumber = CURRENT_CONGRESS) \
        .exclude(billtype = 'x') \
        .annotate(Count('usercomments')).order_by('-usercomments__count') \
        [0:count]:
        
        if b.usercomments__count == 0:
            break
            
        sup = b.usercomments.filter(position="+").count()
        opp = b.usercomments.filter(position="-").count()
        
        bills.append( (b, sup, opp, float(sup)/float(sup+opp), b.url()) )
        
        max_count = max(max_count, sup+opp)
        max_sup = max(max_sup, sup)
        max_opp = max(max_opp, opp)
        
    # sort by %support
    bills.sort(key = lambda b : b[3], reverse=True)
        
    return render_to_response('popvox/widgets/top_bills.html', {
        "bills": bills,
        "max": max_count,
        "max_sup": max_sup,
        "max_opp": max_opp,
    }, context_instance=RequestContext(request))
    
@strong_cache
@do_not_track_compliance
def minimap(request):
    congressnumber = CURRENT_CONGRESS
    count = 8
    
    if "bill" in request.GET:
        try:
            bill = bill_from_url("/bills/us/" + request.GET["bill"])
        except:
                return HttpResponseBadRequest("It looks like something is wrong--this bill doesn't exist. Contact the owner of this site and let them know. Or you can search for bills at <a href='https://www.popvox.com' target=_blank>POPVOX.com</a>")
    else:
        return HttpResponseBadRequest("Invalid URL.")
        
    billtype = bill.billtypeslug().upper()
    billnum = billtype+' '+str(bill.billnumber)
    total = bill.usercomments.get_query_set().count()
    if total == 0:
        pro = 0
        con = 0
    else:
        pro = (100.0) * bill.usercomments.get_query_set().filter(position='+').count()/total
        con = (100.0) * bill.usercomments.get_query_set().filter(position='-').count()/total
    
        
    return render_to_response('popvox/widgets/minimap.html', {
        "billurl": request.GET["bill"],
        "billnum": billnum,
        "bill": bill,
        "pro": pro,
        "con": con,
        "comments":total,
    }, context_instance=RequestContext(request))

@do_not_track_compliance
def bill_text(request):
    return render_to_response('popvox/widgets/billtext.html', {
    }, context_instance=RequestContext(request))
    
@strong_cache
@do_not_track_compliance
def bill_text_js(request):
    width = int(float(request.GET.get("width", "615")))
    height = int(float(request.GET.get("height", str(width*11/8.5))))
    
    return HttpResponse("""
var pv_fargs = window.location.hash.substring(1).split(",");
var pv_qsargs = "";
for (var pv_fargs_i = 0; pv_fargs_i < pv_fargs.length; pv_fargs_i++) {
    if (pv_fargs[pv_fargs_i].substring(0, 5) == "page=") pv_qsargs += "&" + pv_fargs[pv_fargs_i];
    if (pv_fargs[pv_fargs_i].substring(0, 7) == "zoomed=") pv_qsargs += "&" + pv_fargs[pv_fargs_i];
    if (pv_fargs[pv_fargs_i].substring(0, 7) == "format=") pv_qsargs += "&" + pv_fargs[pv_fargs_i];
}
var pv_qs_loc = document.location.href;
if (pv_qs_loc.indexOf("#") >= 0) pv_qs_loc = pv_qs_loc.substring(0, pv_qs_loc.indexOf("#"));
document.write("<iframe id='popvox_billtext_widget' src='https://%s/widgets/bill-text?%s&baseurl=" + escape(pv_qs_loc) + pv_qsargs + "' width='%d' height='%d' border='0' marginheight='0' marginwidth='0' frameborder='0'></iframe>");
""" % (request.get_host(), urllib.urlencode(request.GET), width, height)
    , mimetype="text/javascript")


@do_not_track_compliance
def leg_agenda(request):
    
    org = Org.objects.get(id=request.GET["org"])
    
    #legagenda widgets can cover all an org's bills, or just one campaign.
    '''if request.GET["campaign"]:
        #if there's one campaign, we'll want its name for the page, so storing it separately
        campaign = OrgCampaign.objects.get(id=request.GET["campaign"])
        campaigns = [campaign]
    else:'''
    campaign = False
    campaigns = OrgCampaign.objects.filter(org = org)
    
    #Positions include the bill, org position, and other useful data. We'll be building the actual table of bills from these.
    positions =  []
    for cam in campaigns:
        campositions = list(cam.positions.all())
        #this widget only includes bills that can still be weighed in on.
        livepositions = [position for position in campositions if position.bill.isAlive()]
        positions.extend(livepositions)
    
    return render_to_response('popvox/widgets/leg-agenda.html', {
        "org": org,
        "campaign": campaign,
        "positions": positions,
    }, context_instance=RequestContext(request))