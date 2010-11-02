from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.contrib.auth.decorators import login_required
from django.utils import simplejson

from jquery.ajax import json_response, ajax_fieldupdate_request, sanitize_html, ajaxmultifieldupdate

import math
import re
import datetime

from models import Session

def getnodename(pe):
	if pe.view == None:
		return None
		
	nodename = pe.view
	if hasattr(pe, "goal"):
		nodename = getattr(pe, "goal")

	return nodename

def report_sunburst(request, data_startdate):	
	starting_view = request.GET.get('path-start', "")
	max_depth = int(request.GET.get('depth', "4"))

	all_nodes = { }

	# Generate a hierarchy of paths out of the starting view.
	
	apps = { }
	graph = { "_VISITS_": 0,
				"_LABEL_":  "",
				'_MODULE_': '',
				}
	for session in Session.objects.filter(end__gte = data_startdate):
		depth = None
		for pe in session.get_path():
			if pe.time < data_startdate:
				continue
			
			nodename = getnodename(pe)
			if nodename == None:
				continue
				
			if not nodename in all_nodes:
				all_nodes[nodename] = 0
			all_nodes[nodename] += 1
			
			# Start the path search at a trigger view and proceed until
			# a certain depth. Note that whenever we hit the trigger, we
			# start over.
			if nodename == starting_view or starting_view == '':
				depth = 0
				node = graph
				ancestors = []
			elif depth == None:
				continue
			else:
				depth += 1
				if depth == max_depth:
					depth = None
					continue
			
			if len(ancestors) > 0 and nodename == ancestors[-1]: # basically a page refresh, so don't waste space
				continue
			
			if not nodename in node:
				node[nodename] = {
					"_VISITS_": 0,
					"_LABEL_":  getattr(pe, "goal", pe.view.split(".")[-1]),
					"_MODULE_": ".".join(pe.view.split(".")[0:-1]),
					"_PATH_": ancestors + [nodename]
					}
			
			node[nodename]["_VISITS_"] += 1
			
			ancestors.append(nodename)
			node = node[nodename]
		
	def prune(node, depth):
		# As we get closer and closer to the outermost ring, allow
		# fewer and fewer divisions by grouping small divisions together
		# into an (other) category. At the final depth max_depth-depth
		# equals zero, meaning we don't allow divisions beyond the final
		# depth, but that makes sense since we don't parse beyond that
		# depth anyway. At the core of the image, say with a max_depth
		# of 10, then we allow divisions up to 1/1.35^10 = 5%.
		if max_depth >= 8:
			prune_factor = 1/(1.35**(max_depth-depth))
		else:
			prune_factor = .02*1.35**depth
		
		n = { }
		other = 0
		for k, v in node.items():
			if type(v) != dict:
				n[k] = v
				continue
				
			elif v["_VISITS_"] < node["_VISITS_"]*prune_factor:
				other += v["_VISITS_"]
				
			else:
				n[k] = prune(v, depth+1)
		
		if other > node["_VISITS_"]/100:
			n["_OTHER_"] = { "_VISITS_": other, "_LABEL_":  "(other)", "_MODULE_":  "(other)" }
		
		return n
		
	# The actual start is the first value in the top-level dictionary. Prune the
	# internal nodes of the graph.
	if starting_view != '':
		graph = graph[starting_view]
	graph = prune(graph, 0)
	
	# Convert this to pre-order traversal list.
	def preorder(node, parentNode, out):
		index = len(out)
		out.append({ "parentNode": parentNode, "value": node["_VISITS_"], "label": node["_LABEL_"], "module": node["_MODULE_"], "path": None if not "_PATH_" in node else simplejson.dumps(node["_PATH_"])  })
		for k, v in node.items():
			if type(v) == dict:
				preorder(v, index, out)
	
	nodes = []	
	preorder(graph, None, nodes)
	
	nodenamelist = all_nodes.keys()
	nodenamelist.sort(key = lambda x : -all_nodes[x])
	nodenamelist = nodenamelist[0:50]
		
	return render_to_response("trafficanalysis/sunburst.html", {
		'pathstart': starting_view,
		'startdate': data_startdate.strftime("%Y-%m-%d"),
		'depth': max_depth,
		'nodenamelist': nodenamelist,
		"graph": nodes,
		})
				
def report_path(request, data_startdate):
	# Compute the funnel on a day-by-day basis.
	
	path = simplejson.loads(request.GET["path"])
	timeseries = { }
	
	def getts(pe):
		date = pe.time.date()
		if not date in timeseries:
			ts = [0 for x in path]
			timeseries[date] = ts
			return ts
		else:
			return timeseries[date]

	for session in Session.objects.filter(end__gte = data_startdate):
		path_index = 0
		for pe in session.get_path():
			if pe.time < data_startdate:
				continue
			nodename = getnodename(pe)
			if nodename == None:
				continue
				
			if nodename == path[path_index]:
				# If this request matches the next item on the path,
				# increment the counters. For this sequence, use
				# the counters array for the date on which the path
				# began.
				if path_index == 0:
					counts = getts(pe)
				counts[path_index] += 1
				path_index += 1
				
				# If we reached the end of the path, reset.
				if path_index == len(path):
					path_index = 0
					
			elif nodename == path[0]:
				# If it didn't match, allow the path to pick up from the
				# start if it matches the start.
				counts = getts(pe)
				counts[0] += 1
				path_index = 1
				
			else:
				# Otherwise if it doesn't match, reset to the beginning.
				path_index = 0
		
	# Normalize the timeseries into a tuple giving the total hits to the
	# starting request in the path (by day, of course) and the sizes
	# of the stacks which is for each item its value minus the value
	# to its right, divided by the first value.
	for k, v in timeseries.items():
		timeseries[k] = (k, v[0], [float(v[i]-(v + [0])[i+1])/float(v[0]) for i in xrange(len(v))])
	timeseries = list(timeseries.values())
	timeseries.sort(key = lambda x : x[0])
	
	# Transpose the timeseries and reverse series order so it is by stack.
	# Also add series labels to the part on the series with the max value.
	data = [
		[
			{ "x": date,
			   "y": timeseries[date][2][len(timeseries[0][2])-stack-1],
			   "series": path[len(timeseries[0][2])-stack-1],
			   "showserieslabel": timeseries[date][2][len(timeseries[0][2])-stack-1] == max([timeseries[d][2][len(timeseries[0][2])-stack-1] for d in xrange(1, len(timeseries))])
			   }
			for date in xrange(len(timeseries))
		]
		for stack in xrange(len(timeseries[0][2]))
		]
	
	return render_to_response("trafficanalysis/funnel.html", {
		"data": data,
		"x": [x[0].strftime("%Y-%m-%d") for x in timeseries],
		"xmax": len(timeseries)-1
		})
	
@login_required
def report(request):
	if not request.user.is_superuser:
		return HttpResponseForbidden()

	if not "start-date" in request.GET:
		data_startdate = datetime.datetime.now() - datetime.timedelta(30)
	else:
		data_startdate = datetime.datetime.strptime(request.GET["start-date"], "%Y-%m-%d")
	
	if not "path" in request.GET:
		return report_sunburst(request, data_startdate)
		
	return report_path(request, data_startdate)

