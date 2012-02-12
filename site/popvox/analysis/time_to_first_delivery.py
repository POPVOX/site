#!runscript
from popvox.models import UserComment, RawText
from numpy import median, percentile
from datetime import datetime, timedelta

source = UserComment.objects.filter(
	created__gt=datetime.now().date()-timedelta(days=31),
	created__lt=datetime.now().date()-timedelta(hours=20)
	).order_by()
count = source.count()
batch_size = 1000

buckets = { }

for batch in range(0, count, batch_size):
	for c in source[batch:min(batch+batch_size, count)]:
		# filter out messages that can no longer be delivered (esp. reintro messages)
		recips = c.get_recipients()
		if not isinstance(recips, (tuple,list)) or len(recips) == 0:
			continue
		
		date = c.created.date()
		if not date in buckets: buckets[date] = { "date": date, "delays": [], "delivered": 0, "count": 0, "comment_delivered": 0, "comment_count": 0 }
		bucket = buckets[date]
		
		bucket["count"] += 1
		if c.message:
			bucket["comment_count"] += 1
		
		da = c.delivery_attempts.filter(success=True).order_by('created')
		try:
			d = da[0]
		except IndexError:
			# use an arbitrarily long value: we don't know how long it will take, so guesstimate so that
			# the percentiles are a little closer to reality.
			bucket["delays"].append(40) # days
			continue
		
		bucket["delivered"] += 1
		bucket["delays"].append((d.created - c.created).total_seconds()/60.0/60.0/24.0) # days
		
		if c.message:
			bucket["comment_delivered"] += 1

buckets = buckets.values()
buckets.sort(key = lambda b : b["date"])

for bucket in buckets:
	if bucket["count"] > 0:
		bucket["delivered"] = round(100.0*bucket["delivered"]/bucket["count"], 1)
	else:
		bucket["delivered"] = 0
	
	if bucket["comment_count"] > 0:
		bucket["comment_delivered"] = round(100.0*bucket["comment_delivered"]/bucket["comment_count"], 1)
	else:
		bucket["comment_delivered"] = 0

	# it doesn't make sense to compute percentiles if the number of delivered comments isn't
	# high because the undelivered ones have an undetermined but large delay time.
	if len(bucket["delays"]) > 10 and bucket["delivered"] > 96:
		bucket["delays"] = { "median": round(median(bucket["delays"]), 1), "97p": round(percentile(bucket["delays"], 97), 1) }
	else:
		bucket["delays"] = None
		

rt = RawText.objects.get(name="delivery_status_chart_info")
rt.text = repr(buckets)
rt.save()


