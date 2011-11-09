from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponsePermanentRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist, Context, loader
from django.views.generic.simple import direct_to_template
from django.core.cache import cache
from django.contrib.auth.models import AnonymousUser
from django import forms

from jquery.ajax import json_response, ajax_fieldupdate_request, sanitize_html

import json
import re
from xml.dom import minidom
from datetime import datetime, timedelta

from popvox.models import *

def master_state(request):
	response = HttpResponse(json.dumps({
		"user": {
			"id": request.user.id,
			"screenname": request.user.username,
			"fullname": request.user.userprofile.fullname,
			"email": request.user.email,
			"admin": request.user.is_superuser or request.user.is_staff,
			"orgs": [{
					"name": orgrole.org.name,
					"url": orgrole.org.url(),
					"title": orgrole.title,
				} for orgrole in request.user.orgroles.all()],
			"legstaffrole": {
					"membername": request.user.legstaffrole.member.name() if request.user.legstaffrole.member else None,
					"committeename": request.user.legstaffrole.committee.name() if request.user.legstaffrole.committee else None,
					"position": request.user.legstaffrole.position,
				} if request.user.userprofile.is_leg_staff() else None,
			"serviceaccounts": [{
					"name": unicode(acct),
				} for acct in request.user.userprofile.service_accounts()],
		} if request.user.is_authenticated() else None
	}), mimetype="text/json")
	response['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
	return response

def strong_cache(f):
	# Marks a view as being strongly cached, meaning that all
	# user state is acquired through the AJAX call to master-state.
	# A strongly cached view has no access to Django session
	# state and is marked for upstream caching.
	def g(request, *args, **kwargs):
		request.strong_cache = True
		request.session = None
		request.user = AnonymousUser()
		return f(request, *args, **kwargs)
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
			}, context_instance=RequestContext(request))
	except TemplateDoesNotExist:
		raise Http404()
    
def raise_error(request):
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
    return render_to_response("popvox/legal.html", context_instance=RequestContext(request))

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
	


