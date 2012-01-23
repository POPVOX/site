#!runscript

from popvox.models import UserComment

import csv

bill_name = { 19858: "SOPA", 17081: "PIPA" }
w = csv.writer(open("sopa_pipa_actions.csv", "w"))
for c in UserComment.objects.filter(created__gt="2012-01-17", created__lt="2012-01-20", bill__in=(19858, 17081)).select_related("address").order_by("created"):
	w.writerow([c.created.isoformat(), bill_name[c.bill_id], c.verb(), c.address.zipcode[0:5]])


