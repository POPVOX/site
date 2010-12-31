from models import *

import random
from datetime import datetime

def select_banner(adformat, targets):
	# Select a banner to show and return the banner and the display CPM and CPC prices.
	
	banners = adformat.banners.filter(active=True, order__active=True) \
		.select_related("order") \
		.order_by() # clear default ordering which loads up the Advertiser object
		
	# Sort the banners by their bids. For CPM orders, the CPM bid divided by 1000
	# is its bid. CPC orders, the bid is the banner's recent CTR times its CPC bid. If
	# both a CPM and CPC are specified, the higher of the two are taken.
	def get_bid(banner):
		bid = 0.0
		
		if banner.order.cpmbid != None:
			bid = banner.order.cpmbid / 1000.0
			
		if banner.order.cpcbid != None:
			ctr = banner.recentctr
			if ctr == None:
				ctr, too_few_to_save = banner.compute_ctr()
				if too_few_to_save and bid > 0.0: # prefer cpm to a guestimate based on cpc
					return bid
			
			cpcbid = ctr * banner.order.cpcbid
			if bid == 0.0 or cpcbid > bid:
				bid = cpcbid
				
		return bid
		
	# Make a list of pairs of banners and their proposed bid and sort.
	banners = [(b, get_bid(b)) for b in banners]
	banners.sort(key = lambda x : -x[1])
	
	# Because of rate limiting, we can't just take the top banner.
	banner = None
	while len(banners) > 0:
		banner, bid = banners.pop(0)
		
		# Apply rate limiting based on the max cost per day.
		# Remnant advertisers and 0 max cost orders have no limit.
		if banner.order.advertiser.remnant or banner.order.maxcostperday == 0:
			break
			
		# To perform rate limiting, we look at the last (up to) 2 ImpressionBlocks.
		imprs = ImpressionBlock.objects.filter(banner__in=banner.order.banners.all()).order_by('-date')[0:2]
		if len(imprs) == 0:
			# If there are no impressions yet, obviously there is nothing to limit.
			break
		
		# And get the total cost of the impressions per day from the earliest
		# impression (the start of its day) till now.
		d = imprs[len(imprs)-1].date
		td = datetime.now() - datetime(d.year, d.month, d.day)
		td = float(td.seconds)/float(24 * 3600) + float(td.days)
		costperday = sum([im.cost() for im in imprs]) / td
		
		# Now we compare that to the rate limit. The closer to the rate limit we
		# get, the more we penalize the bid. When the realized cost hits the
		# rate limit, we allow no new impressions.
		if costperday >= banner.order.maxcostperday:
			banner = None
			
		# Otherwise we randomly drop impressions with a probability proportional
		# to how close we are to the rate limit.
		elif random.uniform(0.0, 1.0) < costperday/banner.order.maxcostperday:
			banner = None
		
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
		
	# Since there are two bid types, we have to handle the case where the next bidder
	# used a different bid type.
	
	cpmcost = 0.0
	if banner.order.cpmbid != None:
		# If the bidder specifies a CPM bid, then we price him against the next
		# equivalent CPM bid (which might be actual CPM or an equivalent CPM
		# based on a predicted CTR and a CPC).
		cpmcost = nextbid * 1000.0

	cpccost = 0.0
	if banner.order.cpcbid != None:
		# If the bidder specifies a CPC bid, then we price him against the next bidder's
		# CPC bid if it is a CPC bid...
		if nextbanner.order.cpcbid != None:
			cpccost = nextbanner.order.cpcbid
		else:
			# Bidder uses CPC but next bidder uses CPM, so choose an equivalent CPC.
			# We're sort of fudging this by factoring the bidder's actual CPC bid by the
			# ratio of the bidder's *predicted* CPM to the next bidder's actual CPM.
			cpccost = banner.order.cpcbid * nextbid/bid
	
	return banner, cpmcost, cpccost

