from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.views.decorators.cache import cache_page
from django.db.models import Count

from popvox.models import *
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
		
@cache_page(60 * 60 * 2) # two hours
@do_not_track_compliance
def bill_js(request):
	try:
		bill = None if not "bill" in request.GET else bill_from_url("/bills/us/" + request.GET["bill"])
	except:
		bill = None
	
	return render_to_response('popvox/widgets/bill.js', {
		"siteroot": SITE_ROOT_URL,
		"bill": bill
	}, context_instance=RequestContext(request),
	mimetype="text/javascript")

@cache_page(60 * 60 * 2) # two hours
@do_not_track_compliance
def commentmapus(request):
	count = { }
	max_count = 0
	bill = None
	
	comments = None

	import widgets_usmap

	if "bill" in request.GET:
		bill = get_object_or_404(Bill, id=request.GET["bill"])
		
		# TODO: put this in the database
		comments = bill_comments(bill).only("state", "congressionaldistrict", "position")
	
	elif "sac" in request.GET and request.user.is_authenticated():
		
		if not request.user.has_perm("popvox.can_snoop_service_analytics"):
			# validate the service account campaign is in one of the accounts accessible
			# by the logged in user.
			user_accounts = request.user.userprofile.service_accounts(create=False)
			sac = get_object_or_404(ServiceAccountCampaign, id=request.GET["sac"], account__in=user_accounts)
		else:
			sac = get_object_or_404(ServiceAccountCampaign, id=request.GET["sac"])
		
		bill = sac.bill
		comments = UserComment.objects.filter(actionrecord__campaign=sac)

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
			comments = UserComment.objects.all()
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
		
		for comment in comments:
			district = comment.state + str(comment.congressionaldistrict)
			if not district in count:
				count[district] = { "+": 0, "-": 0, "mean_date": 0 } 
			count[district][comment.position] += 1
			
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
						2,
						int(math.sqrt(float(district["count"]) / float(max_count)) * 4.9999) + 1
						)
	
		else:
			def chartcolor(district):
				return "dot_clr_%d dot_sz_%d" % (
					#int(district["sentiment"]*4.9999) + 1,
					6 - (int(float(district["mean_date"]) / float(district["count"]) / float(comment_duration) * 4.9999) + 1),
					2
					)
		

	mapscale = 720.0 / widgets_usmap.map_scale[0]
	xoffset = 8
	yoffset = 196
	
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
	}, context_instance=RequestContext(request))

@cache_page(60 * 60 * 2) # two hours
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

@cache_page(60 * 60 * 2) # two hours
@do_not_track_compliance
def bill_text(request):
	return render_to_response('popvox/widgets/billtext.html', {
	}, context_instance=RequestContext(request))
	
@cache_page(60 * 60 * 2) # two hours
@do_not_track_compliance
def bill_text_js(request):
	width = int(float(request.GET.get("width", "600")))
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
document.write("<iframe src='https://%s/widgets/bill-text?%s&baseurl=" + escape(pv_qs_loc) + pv_qsargs + "' width='%d' height='%d' border='0' marginheight='0' marginwidth='0' frameborder='0'></iframe>");
""" % (request.get_host(), urllib.urlencode(request.GET), width, height)
	, mimetype="text/javascript")
