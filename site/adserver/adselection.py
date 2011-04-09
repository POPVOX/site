from django.template import Context, Template
from django.db.models import F
from django.db import IntegrityError

import random
from datetime import datetime, date, timedelta
from time import time

from models import *
import cache

from adserver.uasparser import UASparser  
uas_parser = UASparser(update_interval = None)

from settings import SITE_ROOT_URL, DEBUG

last_impression_clear_time = None

def select_banner(adformat, targets, ad_trail, request):
	# Select a banner to show and return the banner and the display CPM and CPC prices.
	
	now = datetime.now()

	banners = adformat.banners.filter(active=True, order__active=True) \
		.select_related("order", "order__advertiser") \
		.order_by() # clear default ordering which loads up the Advertiser object
		
	target_ids = [t.id for t in targets]

	# Remove banners that do not match the targetting.
	def matches_targets(banner):
		for targetgroup in banner.order.targets_parsed():
			for target in targetgroup:
				if target in target_ids:
					break # match
			else:
				# No target matched on this line, so the banner fails to match.
				return False
		return True
		
	banners = [b for b in banners if matches_targets(b)]
	
	# Sort the banners by their bids. For CPM orders, the CPM bid divided by 1000
	# is its bid. For CPC orders, the bid is the banner's recent CTR times its CPC bid. If
	# both a CPM and CPC are specified, the higher of the two are taken.
	def get_bid(banner):
		bid = 0.0
		
		cpmbid = banner.order.cpmbid
		cpcbid = banner.order.cpcbid
		
		# Call a banner plugin.
		extra_info = None
		pl = banner.order.plugin
		if pl != None:
			path = pl.split(".")
			tmp = __import__(".".join(path[:-1]), globals(), fromlist = [path[-1]])
			plobj = getattr(tmp, path[-1])
			
			if not DEBUG:
				try:
					extra_info = plobj(banner, request)
				except:
					# trap all errors
					extra_info = None
			else:
				# do not trap errors when debugging
				extra_info = plobj(banner, request)
			
			if extra_info == None or not isinstance(extra_info, dict):
				return None # do not display this banner
			if "cpm" in extra_info:
				cpmbid = extra_info["cpm"]
			if "cpc" in extra_info:
				cpcbid = extra_info["cpc"]
		
		if cpmbid != None:
			bid = cpmbid / 1000.0
			
		if cpcbid != None:
			ctr = banner.recentctr
			if ctr == None:
				ctr, too_few_to_save = banner.compute_ctr()
				if not too_few_to_save:
					banner.recentctr = ctr
					banner.save()
				elif bid > 0.0: # prefer cpm to a guestimate based on cpc
					return banner, bid, extra_info
			
			cpcbid = ctr * cpcbid
			if bid == 0.0 or cpcbid > bid:
				bid = cpcbid
				
		return banner, bid, extra_info
		
	# Make a list of pairs of banners and their proposed bid, and sort them first by
	# bid, and if there are ties prefer ones with higher max cost per day, which means
	# ones without a max cost (usually remnant ads) are ordered last.
	banners = [get_bid(b) for b in banners]
	banners = [b for b in banners if b != None] # filter out banners that plugin says do not display
	banners.sort(key = lambda x : (-x[1], -x[0].order.maxcostperday))
	
	# Because of rate limiting, we can't just take the top banner.
	banner = None
	drop_rate = 0.0
	while len(banners) > 0:
		banner, bid, extra_info = banners.pop(0)
		
		# Check the ad frequency against the time of the last display.
		if banner.id in ad_trail and (banner.order.period == None or banner.order.period != 0):
			if banner.order.period != None:
				period = timedelta(hours=banner.order.period)
			else:
				period = timedelta(seconds=20)
			if now - ad_trail[banner.id] < period:
				# clear field and continue looking for a banner
				banner = None
				continue
		
		# Apply rate limiting based on the max cost per day.
		if banner.order.maxcostperday == None or banner.order.maxcostperday == 0:
			break
		
		# Determine the recent expenditure over about the last two days. Note
		# that these values could come back all 0.0 if we haven't had any impressions
		# yet, or if the ad is CPC based and we haven't had a click. We're getting:
		#   totalcost = total cost of impressions over about the last two days
		#   td = the actual amount of time over which the totalcost was spread, in days
		#   impressions = the number of impressions in this time
		#   recent_drop_rate = the average drop_rate for all of those impressions
		totalcost, td, impressions, recent_drop_rate = banner.order.rate_limit_info()
		
		# If we haven't had any spend yet, accept the ad.
		if totalcost == 0.0:
			break
			
		# Otherwise we randomly accept this ad for potential impressions according to
		# some probability accept_rate. The accept_rate would ideally be precisely the
		# ratio of the order's maxcostperday to the total daily cost if we filled all
		# impressions with this ad (bounded at 1.0, of course, if the order wants more
		# ads than we can fill). Obviously we don't know how many relevant impressions
		# are going to come, so we have to predict something appropriate.
		#
		# The simplest approach would be to accept this ad with a probability of
		#     accept_rate = 1.0 - ((totalcost/td)/maxcostperday)^2
		#     [in python: accept_rate = 1.0 - ((totalcost/td)/banner.order.maxcostperday)**2 ]
		# i.e. based on the ratio of recent ad spend to the spending target. The closer
		# we are to the target, the fewer ads we accept going forward.
		#
		# This formulation always under-estimates the right accept_rate, but it comes
		# close in the extremes: when the order's maxcostperday is either very
		# small (< 1/5th of the inventory available), or much larger (i.e. the order
		# has specified a rate limit 5x times what we can fulfill). But when the order's
		# limit is not extreme, the computed probability falls short of what is needed
		# to actually fulfill the budget. The worst case is when the budget is equal to the
		# inventory, at which point we'd actually sell only 62% of the inventory even
		# though the advertiser would pay for all of it! This is determined by setting
		# (totalcost/td) to accept_rate*inventory*CPI and then solving for accept_rate.
		#
		# If only we knew what the available inventory is! Each time we display an
		# ad we save the 1.0 - accept_rate that we used when selecting that ad,.
		# which we've just gotten back as recent_drop_rate. Using the number of actual
		# impressions we can infer the daily inventory that had recently been available:
		#     recent_inventory = impressions / (1 - recent_drop_rate)
		#     daily_inventory = recent_inventory / td
		# Then we can determine the total cost if we filled this ad for the entire daily
		# inventory (i.e. daily_inventory * CPI, where CPI = totalcost/impressions):
		#    total_daily_inventory_cost = (totalcost/(1 - recent_drop_rate))/td
		# Finally the accept_rate is the ratio as indicated at the start, maxcostperday
		# to the total daily inventory cost, and the drop_rate is one minus that.
		
		drop_rate = 1.0 - banner.order.maxcostperday * ((td / totalcost) * (1.0 - recent_drop_rate))
		
		# What if the order wants more than we can fill? drop_rate will be less than zero.
		# For our sanity, let's set a lower bound of drop_rate on zero. This won't affect
		# what we do with it here, but it will affect what we store for later, and then later
		# we will get back 0.0 for recent_drop rate. The effect will be that we estimate
		# the daily inventory to be exactly the recent inventory...
		if drop_rate < 0.0: drop_rate = 0.0
		
		# There is a small chance the drop_rate could reach and be sustained at 1.0. Once
		# the recent_drop_rate reaches 1.0, drop_rate will be equal to 1.0 and there is no
		# hope to ever display this ad again. To prevent this, we will upper-bound the drop
		# rate with the "simple" drop_rate calculation discussed above which always over-
		# estimates the ideal drop_rate but is not susceptible to getting stuck because
		# it will always be less than 1.0 so long as the recent ad spend rate is less than
		# the order's maximum.
		drop_rate_2 = ((totalcost/td) / (banner.order.maxcostperday)) ** 2
		if drop_rate_2 > 1.0: drop_rate_2 = 1.0
		if drop_rate > drop_rate_2:
			drop_rate = drop_rate_2
		
		if drop_rate > 0.0 and random.uniform(0.0, 1.0) < drop_rate:
			banner = None # clear field and continue looking for a banner
			continue
		
		# If we got this far, accept the banner.
		break
	
	if banner == None:
		return None

	# We now have the banner that we are going to display.
	
	# To get the actual cost of this banner, we look to the next-highest bidder excluding
	# additional banners from the same advertiser.
	while len(banners) > 0:
		nextbanner, nextbid, nextextrainfo = banners[0]
		if nextbanner.order.advertiser_id != banner.order.advertiser_id:
			break
		banners.pop(0)
	
	# If there are no additional bidders then there is no cost because there is no competition.
	if len(banners) == 0:
		return banner, 0.0, 0.0, drop_rate, extra_info
		
	# There are two bid types and this leads to some complications on how to charge
	# the advertiser. First, we only charge based on the bid type(s) actually placed.
	# Since we determine the sale price based on the next-higest bidder, these two
	# bidders may have different types of bids and so we have to do a conversion
	# of some sort in that case.
	#
	# And if the advertiser makes two types of bids, we should not charge both for the
	# impression and for potential clicks --- we should choose the lower projected
	# cost of the two.
	
	cpmcost = 0.0
	if banner.order.cpmbid != None and banner.order.cpmbid > 0:
		# If the bidder specifies a CPM bid, then we price him against the next
		# equivalent CPM bid (which might be actual CPM or an equivalent CPM
		# based on a predicted CTR and a CPC).
		cpmcost = nextbid * 1000.0

	cpccost = 0.0
	if banner.order.cpcbid != None and banner.order.cpcbid > 0:
		# If the bidder specifies a CPC bid, then we price him against the next bidder's
		# CPC bid if it is a CPC bid...
		if nextbanner.order.cpcbid != None:
			cpccost = nextbanner.order.cpcbid
		else:
			# Bidder uses CPC but next bidder uses CPM, so choose an equivalent CPC.
			# We're sort of fudging this by factoring the bidder's actual CPC bid by the
			# ratio of the bidder's *predicted* CPM to the next bidder's actual CPM.
			cpccost = banner.order.cpcbid * nextbid/bid
	
	if cpmcost > 0 and cpccost > 0:
		# We can't charge both CPM and CPC for the same impression. Choose the
		# one that has the *greater* predicted cost. This is for two reasons. First,
		# we might consider the next-highest bidder as having placed two bids, one
		# CPM and one CPC, and in that model we should be pricing this impression
		# against the true next-highest bid, which is the higher of those two. Secondly,
		# since we can only project a cost for CPC bids we do not want to allow an
		# advertiser to win an auction based on a high CPM bid but then price him
		# at a CPC rate when his CTR might be, in the extreme, zero, thus giving him
		# free advertising!
		ctr = banner.recentctr
		if ctr == None:
			ctr, too_few_to_save = banner.compute_ctr()
		if cpmcost/1000.0 < ctr*cpccost:
			cpmcost = 0.0
		else:
			cpccost = 0.0
	
	return banner, cpmcost, cpccost, drop_rate, extra_info

def show_banner(format, request, context, targets, path):
	# Select a banner to show and return the HTML code.
	
	global last_impression_clear_time

	now = datetime.now()
	
	# Don't show ads when the user agent is a bot.
	if not "HTTP_USER_AGENT" in request.META:
		return Template(format.fallbackhtml).render(context)
	ua = uas_parser.parse(request.META["HTTP_USER_AGENT"])
	if ua == None or ua["typ"] == "Robot": # if we can't tell, or if we know it's a bot
		return Template(format.fallbackhtml).render(context)
		
	# Prepare the list of ads we've served to this user recently. Prune the list
	# of ads not seen in two days, which is the maximum.
	adserver_trail = None
	if hasattr(request, "session"):
		if not "adserver_trail" in request.session or type(request.session["adserver_trail"]) == list:
			request.session["adserver_trail"] = { }
		adserver_trail = request.session["adserver_trail"]
		for bannerid, last_impression_date in adserver_trail.items():
			if now - last_impression_date > timedelta(days=2):
				del adserver_trail[bannerid]
	
	# Besides the targets specified in the template tag, additionally apply
	# templates stored in the session key and context variable
	# "adserver-targets", which must be string or Target instances.
	def make_target2(field):
		if type(field) == str:
			try:
				return Target.objects.get(key=field)
			except:
				raise Exception("There is no ad target with the key " + field)
		else:
			return field
	if hasattr(request, "session") and "adserver-targets" in request.session:
		targets += [make_target2(t) for t in request.session["adserver-targets"]]
	if "adserver-targets" in  context:
		targets += [make_target2(t) for t in context["adserver-targets"]]
	targets = set(targets)
	
	# Find the best banner to run here.
	selection = select_banner(format, targets, adserver_trail, request)
	if selection == None:
		return Template(format.fallbackhtml).render(context)
	
	b, cpm, cpc, r, extra_info = selection
	
	# Create a SitePath object.
	path = path[0:SitePath.MAX_PATH_LENGTH] # truncate before get_or_create or it will create duplicates if it gets truncated by mysql
	sp = cache.req_get(request, 'SitePath_path', path, lambda x :
			SitePath.objects.get_or_create(path=path)[0]) # [0] because get_or_create returns (objects, is_new).
							
	# Create an ImpressionBlock.
	imb, isnew = ImpressionBlock.objects.get_or_create(
		banner = b,
		path = sp,
		date = now.date)

	# Atomically update the rest.
	
	#ImpressionBlock.objects.filter(id=imb.id).update(
	#	cpmcost = (F('cpmcost')*F('impressions') + cpm) / (F('impressions') + 1), # update the amortized CPM on the impression object
	#	impressions = F('impressions') + 1, # add an impression
	#	ratelimit_sum = F('ratelimit_sum') + r,
	#	)

	imb.cpmcost = (imb.cpmcost * imb.impressions + cpm) / (imb.impressions + 1)
	imb.impressions += 1
	imb.ratelimit_sum += r
	imb.save()

	# Update the TargetImpressionBlock for each target.
	for target in targets:
		try:
			TargetImpressionBlock.objects.create(target = target, path = sp, date = now.date, impressions = 1)
		except IntegrityError:
			TargetImpressionBlock.objects.filter(target = target, path = sp, date = now.date).update(impressions = F('impressions') + 1)
		
	# Create a unique object for this impression.
	timestamp = str(int(time()))
	im = Impression()
	im.set_code()
	im.block = imb
	im.cpccost = cpc
	im.targeturl = b.get_target_url(timestamp)
	im.save()
	
	# Clear out old impressions every so often.
	if last_impression_clear_time == None or now-last_impression_clear_time>timedelta(minutes=30):
		Impression.objects.filter(created__lt = now-timedelta(minutes=30)).delete()
		last_impression_clear_time = now
	
	# Record that this ad was shown.
	if adserver_trail != None and (b.order.period == None or b.order.period != 0):
		adserver_trail[b.id] = now
	
	# Parse the template. If the banner has HTML override code, use that instead.
	if b.html != None and b.html.strip() != "":
		t = Template(b.html)
	else:
		t = Template(format.html)
	
	# Apply the template to the banner and return the code.
	context.push()
	try:
		if extra_info != None: # do this first so we overwrite with important keys
			context.update(extra_info)
		
		context.update({
			"SITE_ROOT_URL": SITE_ROOT_URL,
			"banner": b,
			"impression": im,
			"impressionblock": imb,
			"imageurl": b.get_image_url(timestamp),
			"cpm": cpm,
			"cpc": cpc,
			})
		return t.render(context)
	finally:
		context.pop()
	
