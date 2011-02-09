from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist

from popvox.models import *
from popvox.views.bills import bill_comments
from popvox.govtrack import statenames, ordinate

from settings import SITE_ROOT_URL

def bill_js(request):
	# Don't record in traffic stats.
	request.goal = None

	try:
		bill = None if not "bill" in request.GET else bill_from_url("/bills/us/" + request.GET["bill"])
	except:
		bill = None
	
	return render_to_response('popvox/widgets/bill.js', {
		"siteroot": SITE_ROOT_URL,
		"bill": bill
	}, context_instance=RequestContext(request))

def commentmapus(request):
	bill = get_object_or_404(Bill, id=request.GET["bill"])
	
	# TODO: put this in the database
	count = { }
	comments = bill_comments(bill)
	for comment in comments:
		district = comment.address.state + str(comment.address.congressionaldistrict)
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
	yoffset = 192 # ??
	
	for district in count:
		# Some invalid congressional districts!
		if not district in widgets_usmap.district_locations:
			continue

		count[district]["sentiment"] = float(count[district]["+"])/float(count[district]["+"] + count[district]["-"])
		count[district]["count"] = count[district]["+"] + count[district]["-"]
		
		count[district]["class"] = chartcolor(count[district]["sentiment"], float(count[district]["+"] + count[district]["-"]) / float(max_count))
			
		count[district]["coord"] = { "left": int(widgets_usmap.district_locations[district][0]*mapscale),  "top": int(widgets_usmap.district_locations[district][1]*mapscale)-yoffset }
		
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

