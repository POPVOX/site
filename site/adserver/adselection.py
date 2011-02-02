from django.template import Context, Template
from django.db.models import F

import random
from datetime import datetime, date, timedelta
from time import time

from models import *

from adserver.uasparser import UASparser  
uas_parser = UASparser(update_interval = None)

from settings import SITE_ROOT_URL

def select_banner(adformat, targets, ad_trail):
	# Select a banner to show and return the banner and the display CPM and CPC prices.
	
	banners = adformat.banners.filter(active=True, order__active=True) \
		.select_related("order") \
		.order_by() # clear default ordering which loads up the Advertiser object
		
	target_ids = [t.id for t in targets]

	ad_trail_dict = { }
	if ad_trail != None:
		for banner_id, last_display_time in ad_trail:
			ad_trail_dict[banner_id] = last_display_time
	
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
		
		if banner.order.cpmbid != None:
			bid = banner.order.cpmbid / 1000.0
			
		if banner.order.cpcbid != None:
			ctr = banner.recentctr
			if ctr == None:
				ctr, too_few_to_save = banner.compute_ctr()
				if not too_few_to_save:
					banner.recentctr = ctr
					banner.save()
				elif bid > 0.0: # prefer cpm to a guestimate based on cpc
					return bid
			
			cpcbid = ctr * banner.order.cpcbid
			if bid == 0.0 or cpcbid > bid:
				bid = cpcbid
				
		return bid
		
	# Make a list of pairs of banners and their proposed bid, and sort them first by
	# bid, and if there are ties prefer non-remnant advertisers.
	banners = [(b, get_bid(b)) for b in banners]
	banners.sort(key = lambda x : (-x[1], 1 if b.order.advertiser.remnant else 0))
	
	# Because of rate limiting, we can't just take the top banner.
	banner = None
	while len(banners) > 0:
		banner, bid = banners.pop(0)
		remnant = banner.order.advertiser.remnant
		
		# Check the ad frequency against the time of the last display.
		# Remnant ads should never appear in ad_trail_dict but we'll check anyway.
		if banner.id in ad_trail_dict and not remnant:
			if banner.order.period != None:
				period = timedelta(hours=banner.order.period)
			else:
				period = timedelta(seconds=20)
			if datetime.now() - ad_trail_dict[banner.id] < period:
				# clear field and continue looking for a banner
				banner = None
				continue
		
		# Apply rate limiting based on the max cost per day.
		# Remnant advertisers and 0 max cost orders have no limit.
		if remnant or banner.order.maxcostperday == None or banner.order.maxcostperday == 0:
			break
		
		costperday, totalcost, td = banner.order.rate_limit_info() # note that these could come back all 0.0
		
		# When the recent realized cost hits the rate limit, we allow no new impressions.
		if costperday >= banner.order.maxcostperday:
			banner = None # clear field and continue looking for a banner
			
		# Otherwise we randomly drop impressions with a probability proportional
		# to how close we are to the rate limit. This should spread out the ad
		# impressions. Square the probability so that when we are far from the
		# rate limit we drop fewer ads.
		elif random.uniform(0.0, 1.0) < (costperday/banner.order.maxcostperday)**2:
			banner = None # clear field and continue looking for a banner
		
		else:		
			# If we got this far, accept the banner.
			break
	
	if banner == None:
		return None

	# We now have the banner that we are going to display.
	
	# To get the actual cost of this banner, we look to the next-highest bidder excluding
	# additional banners from the same advertiser.
	while len(banners) > 0:
		nextbanner, nextbid = banners[0]
		if nextbanner.order.advertiser_id != banner.order.advertiser_id:
			break
		banners.pop(0)
	
	# If there are no additional bidders then there is no cost because there is no competition.
	if len(banners) == 0:
		return banner, 0.0, 0.0
		
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
	
	return banner, cpmcost, cpccost

def show_banner(format, request, context, targets, path):
	# Select a banner to show and return the HTML code.
	
	# Don't show ads when the user agent is a bot.
	if not "HTTP_USER_AGENT" in request.META:
		return Template(format.fallbackhtml).render(context)
	ua = uas_parser.parse(request.META["HTTP_USER_AGENT"])
	if ua == None or ua["typ"] == "Robot": # if we can't tell, or if we know it's a bot
		return Template(format.fallbackhtml).render(context)
		
	# Prepare the list of ads we've served to this user recently. Prune the list
	# of ads not seen in two days, which is the maximum.
	if hasattr(request, "session"):
		if not "adserver_trail" in request.session:
			request.session["adserver_trail"] = []
		request.session["adserver_trail"] = [t for t in request.session["adserver_trail"]
			if datetime.now() - t[1] < timedelta(days=2)]
	
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
	
	# Find the best banner to run here.
	selection = select_banner(format, targets, request.session["adserver_trail"] if hasattr(request, "session") else None)
	if selection == None:
		return Template(format.fallbackhtml).render(context)
	
	b, cpm, cpc = selection
	
	# Create a SitePath object.
	path = path[0:SitePath.MAX_PATH_LENGTH] # truncate before get_or_create or it will create duplicates if it gets truncated by mysql
	sp, isnew = SitePath.objects.get_or_create(path=path)
							
	# Create an ImpressionBlock.
	imb, isnew = ImpressionBlock.objects.get_or_create(
		banner = b,
		path = sp,
		date = datetime.now().date,
		)

	# Atomically update the rest.
	ImpressionBlock.objects.filter(id=imb.id).update(
		# update the amortized CPM on the impression object
		cpmcost = (F('cpmcost')*F('impressions') + cpm) / (F('impressions') + 1),
	
		# add an impression
		impressions = F('impressions') + 1
		)
	
	# Create a unique object for this impression.
	timestamp = str(int(time()))
	im = Impression()
	im.set_code()
	im.block = imb
	im.cpccost = cpc
	im.targeturl = b.get_target_url(timestamp)
	im.save()
	
	# Clear out old impressions (maybe do this not quite so frequently?).
	Impression.objects.filter(created__lt = datetime.now()-timedelta(minutes=30)).delete()
	
	# Record that this ad was shown.
	if hasattr(request, "session") and not b.order.advertiser.remnant:
		request.session["adserver_trail"].append( (b.id, datetime.now()) )
	
	# Parse the template. If the banner has HTML override code, use that instead.
	if b.html != None and b.html.strip() != "":
		t = Template(b.html)
	else:
		t = Template(format.html)
	
	# Apply the template to the banner and return the code.
	context.push()
	try:
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
	
