from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.contrib.auth.decorators import login_required

from jquery.ajax import json_response, ajax_fieldupdate_request, sanitize_html, ajaxmultifieldupdate

import re

from models import Session

@login_required
def report(request):
	if not request.user.is_superuser:
		return HttpResponseForbidden()
		
	report = ""
	
	paths = None
	if "path" in request.POST:
		# Parse the path.
		paths = [ [] ]
		categories = []
		for line in request.POST["path"].split("\n"):
			if line.strip() == "":
				continue
			newpaths = [ ]
			newseries = [ ]
			for ls in line.strip().split("|"):
				pe = None
				if ls.strip()[0] == "/":
					pe = { "_": ls.strip(), "path": ls.strip() }
				elif "." in ls:
					pe = { "_": ls.strip(), "view": ls.strip() }
				elif ls.strip() == "*":
					pe = { "_": "Other" }
				else:
					pe = { "_": ls.strip(), "goal": ls.strip() }
				for path in paths:
					newpaths.append( path+[pe] )
			paths = newpaths
		
			categories.append( line.strip().replace("|", "\n") )
		
		maxdays = int(request.POST["maxdaysbetweenreq"])
		
	def docount(pe, attr, counts):
		v = getattr(pe, attr, None)
		if v == None:
			return
		if not attr in counts:
			counts[attr] = { }
		if not v in counts[attr]:
			counts[attr][v] = 0
		counts[attr][v] += 1
		
	counts = { }
	
	if paths != None:
		report = [ { "categories": [q["_"] for q in p], "counts": [ 0 for r in p] } for p in paths]
	else:
		report = None
		categories = None
	
	for session in Session.objects.all():
		if paths != None:
			path_indexes = [0 for p in paths]
		last_time = None
		end_of_session = False
		for pe in session.get_path():
			docount(pe, "path", counts)
			docount(pe, "view", counts)
			docount(pe, "goal", counts)
			
			if paths != None:
				# If a timeout occurs between hits, reset to zero.
				if last_time != None:
					td = pe.time - last_time
					ts =  (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6
					if ts/(60*60*24) > maxdays:
						path_indexes = [0 for p in paths]
				last_time = pe.time
			
				for i in xrange(len(paths)):
					if path_indexes[i] == len(paths[i]):
						continue
						
					# Does this path entry match the next line in the query traffic path?
					match = True
					for k, v in paths[i][path_indexes[i]].items():
						if k != "_" and getattr(pe, k, None) != v:
							match = False
							break
							
					# If so, advance.
					if match:
						path_indexes[i] += 1
				
		if paths != None:
			# At this point, we know how far the session got in
			# each of the possible paths. Classify it according to
			# the longest path.
			s, sl = None, 0
			for i in xrange(len(paths)):
				if s == None or path_indexes[i] > sl:
					s = i
					sl = path_indexes[i]
			
			# Now increment the report accordingly.
			for j in xrange(sl):
				report[s]["counts"][j] += 1
			
	counts_sorted = { }
	for attr in counts:
		counts_sorted[attr] = [ (k,v) for (k,v) in counts[attr].items() ]
		counts_sorted[attr].sort(key = lambda x : (-x[1], x[0]) )
		counts_sorted[attr] = counts_sorted[attr][0:50]
		
	return render_to_response("trafficanalysis/reportpage.html", {
			"path": request.POST["path"] if "path" in request.POST else "/home\n/about\n",
			"categories": categories,
			"report": report,
			"maxdaysbetweenreq": request.POST["maxdaysbetweenreq"] if "maxdaysbetweenreq" in request.POST else "1",
			"yaxis": "Sessions",
			"counts": counts_sorted
		})

