from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum

from adserver.models import *

from datetime import datetime, date, timedelta

class Command(BaseCommand):
	args = '[startdate [enddate [path-prefix]]]'
	help = 'Reports ad server statistics.'
	
	def handle(self, *args, **options):
		startdate = (datetime.now() - timedelta(days=7)).date()
		enddate = datetime.now().date()
		pathprefix = ""
		
		if len(args) >= 1 and args[0] not in ("", "."):
			startdate = args[0]
		if len(args) >= 2 and args[1] not in ("", "."):
			enddate = args[1]
		if len(args) >= 3:
			pathprefix = args[2]
		
		print "Start Date:", startdate
		print "End Date:", enddate
		print
		
		# Start by finding all ImpressionBlock records in the given time range and
		# total by order, path, and date.
		orders = { }
		paths = { }
		dates = { }
		for imb in ImpressionBlock.objects.filter(date__gte=startdate, date__lte=enddate, path__path__startswith=pathprefix).select_related():
			for tally_key, tally_list in ((imb.banner.order, orders), (imb.path, paths), (imb.date, dates)):
				if not tally_key in tally_list:
					tally_list[tally_key] = { "impressions": 0, "clicks": 0, "cost": 0.0 }
				tally_list[tally_key]["impressions"] += imb.impressions
				tally_list[tally_key]["clicks"] += imb.clicks
				tally_list[tally_key]["cost"] += imb.cost()
				
		print "Orders"
		print "======"
		orders = list(orders.items())
		orders.sort(key = lambda x : -x[1]["cost"])
		for order, info in orders:
			print order
			print "\tImpressions:", info["impressions"]
			print "\tClicks:", info["clicks"], "(CTR: ", str(round(10000*info["clicks"]/info["impressions"])/100.0) + "%)"
			print "\tSale:", "$" + str(round(info["cost"]*100)/100.0)
			
			# Status of rate limiting...
			if not order.advertiser.remnant and order.maxcostperday != None and order.maxcostperday > 0:
				totalcost, td, impressions, recent_drop_rate = order.rate_limit_info()
				print "\tCurrent Daily Rate:", "$" + str(round(totalcost/td*100.0)/100.0) + "/day", "($" + str(round(totalcost*100.0)/100.0), "in", round(td*10.0)/10.0, "days)", "of", "$" + str(order.maxcostperday) + "/day max"
				
				# Compute the ad drop rate according to the formulation in adselection.py.
				drop_rate = 1.0 - order.maxcostperday * ((td / totalcost) * (1.0 - recent_drop_rate))
				if drop_rate < 0.0: drop_rate = 0.0
				drop_rate_2 = ((totalcost/td) / (order.maxcostperday)) ** 2
				if drop_rate_2 > 1.0: drop_rate_2 = 1.0
				if drop_rate > drop_rate_2: drop_rate = drop_rate_2
				print "\tDrop Rate:", round(drop_rate, 2)
		
		print
		print "Paths"
		print "====="
		paths = list(paths.items())
		paths.sort(key = lambda x : -x[1]["cost"])
		for path, info in paths[0:20]:
			print path.path.ljust(SitePath.MAX_PATH_LENGTH), "impr:", info["impressions"], "clicks:", info["clicks"], "ctr:", str(round(10000*info["clicks"]/info["impressions"])/100.0) + "%", "$" + str(round(info["cost"]*100)/100.0)
			
		print
		print "Dates"
		print "====="
		dates = list(dates.items())
		dates.sort(key = lambda x : x[0])
		for date, info in dates:
			print date.strftime("%x"), "\timpr:", info["impressions"], "clicks:", info["clicks"], "ctr:", str(round(10000*info["clicks"]/info["impressions"])/100.0) + "%", "$" + str(round(info["cost"]*100)/100.0)

		

