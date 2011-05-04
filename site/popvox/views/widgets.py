from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.views.decorators.cache import cache_page
from django.db.models import Count

from popvox.models import *
from popvox.views.bills import bill_comments
from popvox.govtrack import statenames, ordinate, CURRENT_CONGRESS

from settings import SITE_ROOT_URL

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
	}, context_instance=RequestContext(request))

@cache_page(60 * 60 * 2) # two hours
@do_not_track_compliance
def commentmapus(request):
	bill = get_object_or_404(Bill, id=request.GET["bill"])
	
	# TODO: put this in the database
	count = { }
	comments = bill_comments(bill).defer("message")
	for comment in comments:
		district = comment.state + str(comment.congressionaldistrict)
		if not district in count:
			count[district] = { "+": 0, "-": 0 } 
		count[district][comment.position] += 1

	max_count = 0
	for district in count:
		max_count = max(max_count, count[district]["+"] + count[district]["-"])
	
	def chartcolor(sentiment, countpct):
		return "dot_clr_%d dot_sz_%d" % (
			int(sentiment*4.9999) + 1,
			int(countpct*4.9999) + 1
			)
	
	import widgets_usmap
	mapscale = 720.0 / widgets_usmap.map_scale[0]
	xoffset = 5
	yoffset = 196
	
	for district in count:
		# Some invalid congressional districts!
		if not district in widgets_usmap.district_locations:
			continue

		count[district]["sentiment"] = float(count[district]["+"])/float(count[district]["+"] + count[district]["-"])
		count[district]["count"] = count[district]["+"] + count[district]["-"]
		
		count[district]["class"] = chartcolor(count[district]["sentiment"], float(count[district]["+"] + count[district]["-"]) / float(max_count))
			
		count[district]["coord"] = { "left": int(widgets_usmap.district_locations[district][0]*mapscale)-xoffset,  "top": int(widgets_usmap.district_locations[district][1]*mapscale)-yoffset }
		
		count[district]["href"] = "state=" + district[0:2] + "&district=" + district[2:]
		
		if int(district[2:]) == 0:
			count[district]["label"] = statenames[district[0:2]] + u"\u2019s At-Large District"
		else:
			count[district]["label"] = statenames[district[0:2]] + u"\u2019s " + district[2:] + ordinate(int(district[2:])) + " District"
	
	return render_to_response('popvox/widgets/commentsmapus.html', {
		"bill": bill,
		"data": count.items(),
		"min_sz_num": int(float(max_count)/5.0)+1,
		"max_sz_num": max_count,
	}, context_instance=RequestContext(request))

#@cache_page(60 * 60 * 2) # two hours
@do_not_track_compliance
def top_bills(request):
	congressnumber = CURRENT_CONGRESS
	
	# Select bills with the most number of recent comments.
	bills = []
	max_count = 0
	max_sup = 0
	max_opp = 0
	for b in Bill.objects.filter(congressnumber = CURRENT_CONGRESS) \
		.annotate(Count('usercomments')).order_by('-usercomments__count') \
		[0:15]:
		
		if b.usercomments__count == 0:
			break
			
		sup = b.usercomments.filter(position="+").count()
		opp = b.usercomments.filter(position="-").count()
		
		bills.append( (b, sup, opp, float(sup)/float(sup+opp)) )
		
		max_count = max(max_count, sup+opp)
		max_sup = max(max_sup, sup)
		max_opp = max(max_opp, opp)
		
	# sort by %support
	bills.sort(key = lambda b : b[3])
		
	return render_to_response('popvox/widgets/top_bills.html', {
		"bills": bills,
		"max": max_count,
		"max_sup": max_sup,
		"max_opp": max_opp,
	}, context_instance=RequestContext(request))

