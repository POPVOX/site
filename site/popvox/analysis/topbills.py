#!runscript

import csv

from django.db.models import Count

from popvox.models import Bill
from popvox.govtrack import CURRENT_CONGRESS

out = csv.writer(open("top_bills.csv", "w"))
out.writerow(['comments', 'bill', 'issue'])

for b in Bill.objects.filter(congressnumber=CURRENT_CONGRESS)\
	.annotate(count=Count('usercomments'))\
	.order_by('-count')\
	.select_related("topterm")\
	[0:100]:
	out.writerow([str(b.count), b.title.encode("utf8"), unicode(b.topterm)])

