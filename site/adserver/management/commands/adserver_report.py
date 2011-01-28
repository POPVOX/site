from django.core.management.base import BaseCommand, CommandError

from adserver.models import *

from datetime import datetime, date, timedelta

class Command(BaseCommand):
	args = '[startdate [enddate [path-prefix]]]'
	help = 'Reports ad server statistics.'
	
	def handle(self, *args, **options):
		startdate = (datetime.now() - timedelta(days=7)).date()
		enddate = datetime.now().date()
		pathprefix = ""
		
		if len(args) >= 1:
			startdate = args[0]
		if len(args) >= 2:
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

		print
		print "Paths"
		print "====="
		paths = list(paths.items())
		paths.sort(key = lambda x : -x[1]["cost"])
		for path, info in paths[0:20]:
			print path.path.ljust(30), "\timpr:", info["impressions"], "clicks:", info["clicks"], "ctr:", str(round(10000*info["clicks"]/info["impressions"])/100.0) + "%", "$" + str(round(info["cost"]*100)/100.0)
			
		print
		print "Dates"
		print "====="
		dates = list(dates.items())
		dates.sort(key = lambda x : x[0])
		for date, info in dates:
			print date.strftime("%x"), "\timpr:", info["impressions"], "clicks:", info["clicks"], "ctr:", str(round(10000*info["clicks"]/info["impressions"])/100.0) + "%", "$" + str(round(info["cost"]*100)/100.0)

		

