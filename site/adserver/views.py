from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.template.defaultfilters import escapejs

import re, random

from models import *
from adselection import show_banner

def banner(request, formatid, outputformat):
	# To comply with Do-Not-Track, we should not set a session cookie.
	# To prevent this, we'll clear the session state ahead of time.
	# But not if a DNT=0 query string parameter is set.
	if request.GET.get("DNT", "1") == "1" and \
		request.META.get("DNT", "0") == "1":
		delattr(request, "session")
		
	# Ad requests on a single page must be made synchronously so that
	# the ad trail cookie can be updated by one request before the next
	# ad request is made so that two banners don't show on the same page,
	# but browsers will execute script requests asynchronously (even if the
	# scripts are executed synchronously).
	#
	# Execute the ad in two stages to force synchronicity. In the first stage,
	# just write a new script tag that re-calls this view with an extra parameter
	# to skip this part in this second stage. Because browsers execute scripts
	# in page order, this guarantees synchronicity. It also slows down page
	# load time significantly because the requests will block later scripts on
	# the page --- unless we can get around that.
	#
	# If the ADSERVER_USE_JQUERY setting is True, then we can avoid
	# synchronous requests that block scripts by leaving a <div/> at the
	# point where the script executes and then asynchronously beginning
	# the second request --- but with the async option set to false so that
	# it is executed synchronously with respect to other jQuery ajax calls.
	# In the second stage, we pass the id of the div and fill it in with the
	# banner using jQuery.
	if outputformat == "js" and request.GET.get("jquery", "") == "1" and request.GET.get("ss", "") != "2":
		url = request.build_absolute_uri()
		if not "?" in url:
			url += "?"
		else:
			url += "&"
		url += "ss=2"
		divid = "adserver_placement_" + str(random.randint(0, 10000))
		url += "&div_id=" + divid
		js = ""
		js += "document.write(\"<div id='%s'> </div>\");\n" % divid
		js += "function %s() { $.ajax({dataType:'script',url:'%s',complete:function() { if (adserver_chain.length == 0) adserver_chain = null; else adserver_chain.pop()(); } } ); }\n" % (divid, escapejs(url))
		js += "if (typeof adserver_chain === 'undefined' || adserver_chain == null) { adserver_chain = []; %s(); }\n" % divid
		js += "else { adserver_chain.push(%s); }" % divid
		response = HttpResponse(js, mimetype="text/javascript")
		return response
		
	format = get_object_or_404(Format, id=formatid)
	
	targets = [get_object_or_404(Target, key=target)
		for target in request.GET.get("targets", "").split(",") if target != ""]
	
	# In the database, store the path where the banner is shown based
	# on the HTTP_REFERER, but to save space in the field translate
	# http://www.example.com/abc to example.com::abc.
	path = request.META.get('HTTP_REFERER', '-')
	path = re.sub(r"^https?://(www\.)?([^/:]+)(:\d+)?", r"\2::", path)

	html = show_banner(format, request, RequestContext(request), targets, path)
	
	if outputformat == "html":
		response = HttpResponse(html, mimetype="text/html")
	elif outputformat == "js":
		if request.GET.get("jquery", "") != "1":
			js = "document.write(\"" + escapejs(html) + "\");"
		else:
			js = "$('#" + escapejs(request.GET.get("div_id", "")) + "').html('" + escapejs(html) + "\');"
		response = HttpResponse(js, mimetype="text/javascript")
	else:
		raise Http404()
	response['Cache-Control'] = 'no-cache'

	response.goal = None
	
	return response

def click(request):
	try:
		impr = Impression.objects.get(code=request.GET.get("imx", ""))
	except Impression.DoesNotExist:
		# Can't count the click toward anything. Use the banner id as a backup
		# to at least complete the request.
		try:
			b = Banner.objects.get(id=request.GET.get("b", ""))
			return HttpResponseRedirect(b.targeturl)
		except ValueError:
			return HttpResponseBadRequest("Invalid request.")
		except Banner.DoesNotExist:
			return HttpResponseBadRequest("Invalid request.")

	ImpressionBlock.objects.filter(id=impr.block.id).update(clicks=F('clicks')+1, clickcost=F("clickcost")+impr.cpccost)

	request.goal = None
	
	return HttpResponseRedirect(impr.targeturl)

