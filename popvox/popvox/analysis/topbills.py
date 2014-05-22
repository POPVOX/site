#!runscript

import csv

from django.db.models import Count

from popvox.models import Bill, UserComment
from popvox.govtrack import CURRENT_CONGRESS

out = csv.writer(open("top_bills.csv", "w"))
out.writerow(['comments', 'bill', 'sponsor', 'issue', 'supporting', 'opposing'])

for b in Bill.objects.filter(congressnumber=CURRENT_CONGRESS)\
	.annotate(count=Count('usercomments'))\
	.order_by('-count')\
	.select_related("topterm")\
	[0:100]:
	csup = UserComment.objects.filter(bill=b, position="+").count()
	copp = UserComment.objects.filter(bill=b, position="-").count()
	out.writerow([str(b.count), b.title.encode("utf8"), b.sponsor.name().encode("utf8") if b.sponsor else "", b.topterm.name.encode("utf8") if b.topterm else "", csup, copp])

