#!runscript

import csv

from django.db.models import Count

from popvox.models import UserComment

out = csv.writer(open("top_comments.csv", "w"))
out.writerow(['appreciations', 'url', 'bill', 'message'])

for c in UserComment.objects\
	.annotate(count=Count('diggs'))\
	.order_by('-count')\
	.select_related("bill")\
	[0:1000]:
	out.writerow([str(c.count), c.url(), c.bill.title.encode("utf8"), c.message[0:256].encode("utf8") if c.message else ""])

