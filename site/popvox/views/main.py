from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.views.generic.simple import direct_to_template
from django.core.cache import cache
from django.contrib.auth.decorators import login_required, user_passes_test
from django import forms
from django.contrib.auth.models import User

from jquery.ajax import json_response, ajax_fieldupdate_request, sanitize_html

import re
from xml.dom import minidom
from datetime import datetime, timedelta

from popvox.models import *

def staticpage(request, page):
	news = None
	
	if page == "":
		page = "homepage"
		if request.user.is_authenticated() and request.user.userprofile.is_leg_staff():
			return HttpResponseRedirect("/home")
		news = get_news()
			
	page = page.replace("/", "_") # map URL structure to static files
			
	try:
		return render_to_response("static/%s.html" % page, {
				"page": page,
				"news": news,
			}, context_instance=RequestContext(request))
	except TemplateDoesNotExist:
		raise Http404()

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


_news_items = None
_news_updated = None
def get_news():
	global _news_items
	global _news_updated
	# Load the blog RSS feed for items tagged frontpage.
	if _news_items == None or datetime.now() - _news_updated > timedelta(minutes=60):
		
		# c/o http://stackoverflow.com/questions/1208916/decoding-html-entities-with-python
		import re
		def _callback(matches):
		    id = matches.group(1)
		    try:
			   return unichr(int(id))
		    except:
			   return id
		def decode_unicode_references(data):
		    return re.sub("&#(\d+)(;|(?=\s))", _callback, data)

		import feedparser
		feed = feedparser.parse("http://www.popvox.com/blog/atom")
		_news_items = [{"link":entry.link, "title":decode_unicode_references(entry.title), "date":datetime(*entry.updated_parsed[0:6]), "content":decode_unicode_references(entry.content[0].value)} for entry in feed["entries"][0:4]]
		_news_updated = datetime.now()
	return _news_items

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
	
@user_passes_test(lambda u : u.is_authenticated() and (u.is_staff | u.is_superuser))
def metrics(request):
	from django.db import connection, transaction
	
	def get_stats(field, fields, table, period="day", growth=False):
		c = connection.cursor()
		fixdate = lambda x : x
		if period == "day":
			group = ("date(%s)" % (field,))
		elif period == "week":
			group = ("yearweek(%s)" % (field,))
			# select the date of the sunday of the week - each day needs to map to something
			# consistently. double escape the mysql format string first for the interpolation happening
			# on this line, and second for the interpolation that happens in the Django db layer.
			field = "STR_TO_DATE(CONCAT(YEARWEEK(%s),'0'),'%%%%X%%%%V%%%%w')" % (field,)			
		elif period == "month":
			def fixdate(x):
				return x.replace(day=1)
			group = ("year(%s), month(%s)" % (field, field))
		c.execute("select date(%s), %s from %s group by %s" % (field, fields, table, group))
		
		rows = [{"date": fixdate(r[0]), "count": r[1] } for r in c.fetchall()]
		
		if growth:
			# add cumulative counts
			for i in xrange(len(rows)):
				rows[i]["cumulative"] = rows[i]["count"] + (0 if i==0 else rows[i-1]["cumulative"])
			
			# compute growth rates with a backward-looking sliding window
			from scipy import stats
			from math import log, exp
			window = {"day": 21, "week": 6, "month": 3 }[period]
			for i in xrange(window, len(rows)):
				x = [(row["date"]-rows[0]["date"]).days for row in rows[i-window+1 : i+1]]
				y = [log(row["cumulative"]) for row in rows[i-window+1 : i+1]]
				gradient, intercept, r_value, p_value, std_err = stats.linregress(x,y)
				rows[i]["growth_daily"] = int(100*(exp(gradient) - 1.0)) # percent growth by day
				rows[i]["growth_weekly"] = int(100*(pow(exp(gradient), 7) - 1.0)) # percent growth by week
				rows[i]["growth_monthly"] = int(100*(pow(exp(gradient), 30.5) - 1.0)) # percent growth by month
				days_to_double = log(2.0) / gradient
				if days_to_double < 30:
					rows[i]["double_life"] = ("%d days" % days_to_double)
				elif days_to_double < 30.5 * 24:
					rows[i]["double_life"] = ("%.1f mo." % round(days_to_double/30.5, 1))
				else:
					rows[i]["double_life"] = ("%.1f yr." % round(days_to_double/365.25, 1))
		
		return rows
	
	def merge_by_day(inf):
		# take separate rows of results and merge them into one list.
		ret = {}
		for key, val in inf.items():
			for row in val:
				if row["date"] < datetime(2010, 11, 1).date(): continue
				if not row["date"] in ret: ret[row["date"]] = {} # date
				ret[row["date"]][key] = row
				del row["date"]
		ret = ret.items()
		ret.sort(key = lambda x : x[0])
		
		# for the sake of drawing graphs, we need to fill in the cumulative value for
		# each day, since the record will be missing if there were no items on that
		# day.
		last_rec = {}
		for date, stats in ret: # for the same of graphs, fill in values
			for k in inf:
				if not k in stats and k in last_rec:
					stats[k] = { "count": 0, "cumulative": last_rec[k]["cumulative"] }
				elif k in stats:
					last_rec[k] = stats[k]
		
		ret.reverse()
		
		return ret
		
	general_stats = {}
	for period in ("day", "week", "month"):
		new_users = get_stats("date_joined", "count(*)", "auth_user", period=period, growth=True)
		new_positions = get_stats("created", "count(*)", "popvox_usercomment", period=period, growth=True)
		new_comments = get_stats("created", "count(*)", "popvox_usercomment where message is not null", period=period, growth=True)
		new_comments_with_referrer = get_stats("created", "count(*)", "popvox_usercomment where message is not null and referrer_object_id is not null", period=period, growth=True)
		general_stats[period] = merge_by_day({
				"new_users": new_users,
				"new_positions": new_positions,
				"new_comments": new_comments,
				"new_comments_with_referrer": new_comments_with_referrer,
			})
		

	cohort_sizes = get_stats("date_joined", "count(*)", "auth_user", period="month")
	cohort_sizes2 = dict(((c["date"], c["count"]) for c in cohort_sizes))
	
	cohort_num_positions = get_stats("date_joined", "count(*)", "auth_user left join popvox_usercomment on auth_user.id=popvox_usercomment.user_id", period="month")
	for c in cohort_num_positions: c["count"] = round(float(c["count"]) / float(cohort_sizes2[c["date"]]), 1)
	
	cohort_num_comments = get_stats("date_joined", "count(*)", "auth_user left join popvox_usercomment on auth_user.id=popvox_usercomment.user_id where popvox_usercomment.message is not null", period="month")
	for c in cohort_num_comments: c["count"] = round(float(c["count"]) / float(cohort_sizes2[c["date"]]), 1)
	
	cohort_login_types = {}
	c = connection.cursor()
	c.execute("select min(date(date_joined)), provider, count(*) from auth_user left join registration_authrecord on auth_user.id=registration_authrecord.user_id group by year(date_joined), month(date_joined), provider")
	for dt, provider, count in c.fetchall():
		dt = dt.replace(day=1)
		if not dt in cohort_login_types: cohort_login_types[dt] = { "date": dt }
		cohort_login_types[dt][provider] = 100*count/cohort_sizes2[dt]
	c.execute("select min(date(date_joined)), count(*) from auth_user where not exists(select * from registration_authrecord where auth_user.id=registration_authrecord.user_id) group by year(date_joined), month(date_joined)")
	for dt, count in c.fetchall():
		dt = dt.replace(day=1)
		if not dt in cohort_login_types: cohort_login_types[dt] = { "date": dt }
		cohort_login_types[dt]["password"] = 100*count/cohort_sizes2[dt]
	cohort_login_types = cohort_login_types.values()

	def median(nums):
		nums.sort()
		if len(nums) == 0:
			return None
		elif len(nums) == 1:
			return nums[0]
		elif len(nums) % 2 == 0:
			return (float(nums[len(nums)/2]) + float(nums[len(nums)/2+1]))/2.0
		else:
			return float(nums[len(nums)/2+1])
			
	def mean(nums):
		if len(nums) == 0:
			return None
		return round(float(sum(nums))/float(len(nums)), 1)
		
	def pctile(nums, num):
		if len(nums) == 0:
			return None
		return 100 * len([n for n in nums if n >= num]) / len(nums)
	
	cohort_retention = []
	c = connection.cursor()
	for cohort in cohort_sizes2.keys():
		c.execute("select min(created), max(created) from popvox_usercomment left join auth_user on popvox_usercomment.user_id=auth_user.id where year(auth_user.date_joined)=%d and month(auth_user.date_joined) = %d group by auth_user.id" % (cohort.year, cohort.month))
		retention = [(row[1] - row[0]).days for row in c.fetchall()]
		cohort_retention.append({ "date": cohort, "median": median(retention), "mean": mean(retention), "pctile_1day": pctile(retention, 1), "pctile_7days": pctile(retention, 7), "pctile_30days": pctile(retention, 30) })
	
	by_cohort = merge_by_day({
			"size": cohort_sizes,
			"positions_per_user": cohort_num_positions,
			"comments_per_user": cohort_num_comments,
			"retention": cohort_retention,
			"login_types": cohort_login_types,
		})

	return render_to_response("popvox/metrics.html", {
		"count_users": User.objects.all().count(),
		"count_legstaff": UserLegStaffRole.objects.all().count() - 1, # minus one for our demo acct
		"count_comments": UserComment.objects.all().count(),
		"count_comments_messages": UserComment.objects.filter(message__isnull=False).count(),
		"count_orgs": Org.objects.filter(createdbyus=False).count(),
		
		"general_stats": general_stats,
		"by_cohort": by_cohort,
		}, context_instance=RequestContext(request))


