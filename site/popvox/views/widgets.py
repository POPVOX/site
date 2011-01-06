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
	import colorsys
	from math import sqrt
	
	bill = get_object_or_404(Bill, id=request.GET["bill"])
	
	# TODO: put this in the database
	count = { }
	comments = bill_comments(bill, "+") | bill_comments(bill, "-")
	for comment in comments:
		district = comment.address.state + str(comment.address.congressionaldistrict)
		if not district in count:
			count[district] = { "+": 0, "-": 0 } 
		count[district][comment.position] += 1

	max_count = 0.0
	for district in count:
		max_count = max(max_count, float(count[district]["+"] + count[district]["-"]))
	
	def chartcolor(sentiment, contention):
		def colorhex(component):
			ret = hex(int(255*component)).replace("0x", "")
			while len(ret) < 2:
				ret = "0" + ret
			return ret
			
		return "#" + "".join([
					colorhex(component) for component in
					colorsys.hsv_to_rgb(
						sentiment*.66,
						contention,
						1)
				])
	
	import widgets_usmap
	mapscale = 720.0 / widgets_usmap.map_scale[0]
	yoffset = 192 # ??
	
	for district in count:
		# we'll compute a score on two dimensions (each from 0 to 1)
		#    overall sentiment, the % of comments in support
		#    contentiousness, the relative number of commets compared to districts nationally
		
		count[district]["sentiment"] = count[district]["+"]/(count[district]["+"] + count[district]["-"])
		count[district]["contention"] = (count[district]["+"] + count[district]["-"]) / max_count
		
		# then to compute a color, we'll map sentiment to hue and contention to
		# saturation, on an HSV color span
		count[district]["color"] = chartcolor(count[district]["sentiment"], count[district]["contention"])
			
		count[district]["coord"] = { "left": int(widgets_usmap.district_locations[district][0]*mapscale),  "top": int(widgets_usmap.district_locations[district][1]*mapscale)-yoffset }
		
		count[district]["href"] = "state=" + district[0:2] + "&district=" + district[2:]
		
		if int(district[2:]) == 0:
			count[district]["label"] = statenames[district[0:2]] + "'s At-Large District"
		else:
			count[district]["label"] = statenames[district[0:2]] + "'s " + district[2:] + ordinate(int(district[2:])) + " District"
	
	return render_to_response('popvox/widgets/commentsmapus.html', {
		"bill": bill,
		
		"data": count.items(),
		
		"legend":
			[
				{ "color": chartcolor(sentiment, contention), "label": label }
				for (sentiment, contention, label)
				in [(0,1,"Oppose"), (0,.1, "Weak Opp."), (1,1, "Support"), (1, .1,  "Weak Supp."), (.5, 1, "Mixed"), (.5,.1, "Few Users")]
			]
		
	}, context_instance=RequestContext(request))

