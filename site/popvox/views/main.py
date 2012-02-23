from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponsePermanentRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist, Context, loader
from django.views.generic.simple import direct_to_template
from django.views.decorators.csrf import csrf_protect
from django.core.cache import cache
from django.contrib.auth.models import AnonymousUser
from django.core.urlresolvers import resolve
from django import forms
from django.conf import settings

from jquery.ajax import json_response, ajax_fieldupdate_request, sanitize_html

import json
import re
from xml.dom import minidom
from datetime import datetime, timedelta

from popvox.models import *
import shorturl

@csrf_protect
def master_state(request):
	# Return basic user data common to all pages and used by the master page layout
	# and other page templates.
	data = {
		"user": {
			"id": request.user.id,
			"screenname": request.user.username,
			"fullname": request.user.userprofile.fullname,
			"email": request.user.email,
			"admin": request.user.is_superuser or request.user.is_staff,
			"orgs": [{
					"id": orgrole.org.id,
					"name": orgrole.org.name,
					"slug": orgrole.org.slug,
					"url": orgrole.org.url(),
					"title": orgrole.title,
					"campaigns": [{ "id": cam.id, "name": cam.name, "slug": cam.slug, "isdefault": cam.default } for cam in orgrole.org.all_campaigns()],
				} for orgrole in request.user.orgroles.all().select_related("org")],
			"legstaffrole": {
					"membername": request.user.legstaffrole.member.name() if request.user.legstaffrole.member else None,
					"committeename": request.user.legstaffrole.committee.name() if request.user.legstaffrole.committee else None,
					"position": request.user.legstaffrole.position,
				} if request.user.userprofile.is_leg_staff() else None,
			"serviceaccounts": [{
					"name": unicode(acct),
				} for acct in request.user.userprofile.service_accounts()],
		} if request.user.is_authenticated() else None
	}
	
	# If the view function for the page indicated in the url parameter has a user_state
	# attribute function, call that function with the same parameters as was called for
	# the main page view function and include the output, typically a dict, in the JSON
	# output of this request.
	try:
		m = resolve(request.GET["url"])
		if hasattr(m.func, "user_state"):
			data["page"] = m.func.user_state(request, *m.args, **m.kwargs)
	except Exception as e:
		data["error"] = str(e)
		
	# Pass back the CSRF token so that it can be included on AJAX posts from the calling page.
	# get_token() in combination with csrf_protect on this view causes the CSRF cookie to
	# be set on the response.
	from django.middleware.csrf import get_token
	data["csrf_token"] = get_token(request)
	
	# In debugging environment, include the SQL log.
	if settings.DEBUG:
		from django.db import connection
		data["debug"] = {
			"sql": connection.queries,
		}
	
	response = HttpResponse(json.dumps(data), mimetype="text/json")
	response['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
	return response

@csrf_protect
def get_short_url(request):
	# If the view function for the page indicated in the url parameter has a get_object
	# attribute function, call that function with the same parameters as was called for
	# the main page view function.
	#
	# The return value is an ORM object that we can use to generate a shorturl.
	obj = None
	m = None
	try:
		m = resolve(request.POST["url"])
		if hasattr(m.func, "get_object"):
			obj = m.func.get_object(request, *m.args, **m.kwargs)
	except:
		pass
	
	data = None
	
	if obj:
		rec, created = shorturl.models.Record.objects.get_or_create(
			target = obj,
			owner = request.user if request.user.is_authenticated() else None
			)
		
		data = {
			"shorturl": rec.url(),
			"title": obj.nicename[0:80] if hasattr(obj, "nicename") else None,
			"hashtag": obj.hashtag() if hasattr(obj, "hashtag") else None,
		}
	else:
		data = {
			"shorturl": settings.SITE_ROOT_URL + request.POST["url"],
		}
		
	if not m:
		data["view"] = "unknown"
	else:
		data["view"] = m.url_name

	response = HttpResponse(json.dumps(data), mimetype="text/json")
	response['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
	return response

def strong_cache(f):
	# Marks a view as being strongly cached, meaning that all
	# user state is acquired through the AJAX call to master-state.
	# A strongly cached view has no access to Django session
	# state and is marked for upstream caching.
	def g(request, *args, **kwargs):
		if "nocache" not in request.GET:
			request.strong_cache = True
			request.session = None
			request.user = AnonymousUser()
		return f(request, *args, **kwargs)
	g.__name__ = f.__name__
	if hasattr(f, "user_state"):
		g.user_state = f.user_state
	return g

@strong_cache
def staticpage(request, page):
	news = None
	
	if page == "":
		page = "homepage"

		import articles.models
		news = []
		has_bill_picks = False
		for art in articles.models.Article.objects.filter(status__is_live=True):
			if "Bill Picks" in art.title:
				if has_bill_picks: continue
				has_bill_picks = True
			news.append(art)
			if len(news) == 5: break
	
	page = page.replace("/", "_")
	
	from features import supercommittee_bill_list

	try:
		return render_to_response("static/%s.html" % page, {
				"page": page,
				"news": news,
				"supercommittee_bill_list": supercommittee_bill_list,
				"show_share_footer": True,
			}, context_instance=RequestContext(request))
	except TemplateDoesNotExist:
		raise Http404()
    
def raise_error(request):
	## dump memory state #
	#from meliae import scanner
	#scanner.dump_all_objects('meliae.json')
	## dump memory state #

	raise ValueError("Hmmph!")

def sitedown(request):
	request.session = None
	t = loader.get_template("static/site_down.html")
	response = HttpResponse(t.render(Context({})), status=503)
	response['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
	response.goal = None
	return response

@strong_cache
def press_page(request):
    import articles.models
    
    arts = articles.models.Article.objects.filter(tags__name__in=("release", "clip")).select_related("tags")
    arts = list(arts)
    for art in arts:
        art.article_type = art.tags.filter(name__in=('release', 'clip'))[0].name # grab name of tag
        description = re.sub(r'<p>', '', art.description)
        description = re.sub(r'</p>', '', description)
        art.description = description
        
    arts.sort(key = lambda art : (art.publish_date.year, art.publish_date.month, art.article_type), reverse = True)
    return render_to_response("popvox/press.html", { "press": arts }, context_instance=RequestContext(request))

def legal_page(request):
    return render_to_response("popvox/legal.html", { "show_share_footer": True }, context_instance=RequestContext(request))

@json_response
def subscribe_to_mail_list(request):
	email = request.POST["email"]

	from django import forms
	if not request.POST["validate"] == "validate":
		# dont raise silly errors on an on-line validation
		email = forms.EmailField(required=False).clean(email) # raises ValidationException on error
	
	u = MailListUser.objects.filter(email=email)
	if len(u) > 0:
		return { "status": "fail", "msg": "You are already on our list, but thanks!" }
	if request.POST["validate"] == "validate":
		return { "status": "success" }
	u = MailListUser()
	u.email = email
	u.save()
	return { "status": "success" }

def citygrid_ad_plugin(banner, request):
	if not request.user.is_authenticated():
		return None
	
	try:
		addr = PostalAddress.objects.filter(user=request.user, latitude__isnull=False).order_by("-created")[0]
	except IndexError:
		return None
	
	import urllib
	url = "http://api.citygridmedia.com/ads/custom/v2/latlon?" + urllib.urlencode({
			"what": "all",
			"lat": addr.latitude,
			"lon": addr.longitude,
			"radius": 50,
			"publisher": "test",
			"max": 2,
	})
	res = urllib.urlopen(url)
	
	from lxml import etree
	tree = etree.parse(res).getroot()
	ads = []
	for ad in tree.iter("ad"):
		dist = ad.xpath("string(distance)")
		try:
			dist = int(float(dist))
		except:
			dist = None
		
		ads.append({
				"name": ad.xpath("string(name)"),
				"tagline": ad.xpath("string(tagline)"),
				"destination_url": ad.xpath("string(ad_destination_url)"),
				"display_url": ad.xpath("string(ad_display_url)"),
				"city": ad.xpath("string(city)"),
				"state": ad.xpath("string(state)"),
				"distance": dist
		})
	
	if len(ads) == 0:
		return None
	
	return { "addr": addr, "ads": ads, "url": url }
	


