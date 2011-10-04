#!runscript

import apachelog, re, csv, glob, datetime

from popvox.models import ServiceAccount, ServiceAccountCampaignActionRecord

p = apachelog.parser(r'%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"')

widget_paths = re.compile(r'GET /services/widgets/w/account/(.*)/(.*)\?.*')

hits = { }

	# start/end-date logic depends on the access logs being read in chronological order
	# to scan all log files we could use:
	#   reversed(sorted(list(glob.glob('/home/www/logs/access.log*'))))
	# but if we're only interested in hits to widgets in the last month, just use the
	# current and previous log file (since the current could have just been rotated
	# and it may not have much data yet)
for fn in ('/home/www/logs/access.log.1', '/home/www/logs/access.log'):
	for line in open(fn):
		lp = p.parse(line)
		path = lp['%r']
		
		m = widget_paths.match(path)
		if not m: continue

		referrer = lp['%{Referer}i']
		date = datetime.datetime.strptime( apachelog.parse_date(lp["%t"])[0], "%Y%m%d%H%M%S" )

		api_key = m.group(1)
		widget = m.group(2)
		
		acct = ServiceAccount.objects.get(api_key=api_key)
		
		key = (acct, widget)
		if not key in hits: hits[key] = { "account": acct, "widget": widget, "count": 0, "start_date": date, "urls": { } }

		hits[key]["count"] += 1
		hits[key]["end_date"] = date 
		
		if not referrer in hits[key]["urls"]: hits[key]["urls"][referrer] = 0
		hits[key]["urls"][referrer] += 1
	
hits = list(hits.values())
hits.sort(key = lambda hit : hit["count"], reverse=True)

w = csv.writer(open("widget_urls.csv", "w"))
w.writerow(["account", "widget", "hits", "start_date", "end_date", "writecongress_start", "writecongress_finished"])
for hit in hits:
	acct = hit["account"]
	
	writecongress_start = ""
	writecongress_completions = ""

	if hit["widget"] == "writecongress":
		writecongress_start = ServiceAccountCampaignActionRecord.objects.filter(campaign__account=acct, created__gt=hit["start_date"], created__lt=hit["end_date"])
		writecongress_completions = writecongress_start.filter(completed_comment__isnull=False)
		
		writecongress_start = writecongress_start.count()
		writecongress_completions = writecongress_completions.count()
	
	if acct.org:
		acct = acct.org.slug
	else:
		acct = unicode(acct)
	
	w.writerow([acct.encode("utf8"), hit["widget"], hit["count"], hit["start_date"], hit["end_date"], writecongress_start, writecongress_completions])
	hit["urls"] = list(hit["urls"].items())
	hit["urls"].sort(key = lambda kv : kv[1], reverse=True)
	accounted_for = 0
	for url in hit["urls"]:
		w.writerow(["", "", url[1], url[0]])
		accounted_for += url[1]
		if accounted_for > .66 * hit["count"]: break # show the top URLs that account for 66% of the traffic
		if url[1] < hit["urls"][0][1]/10: break # but no URLs with less than 10% of the traffic of the top URL
