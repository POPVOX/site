#runscript
import csv
from popvox.models import *
w = csv.writer(open("comments.csv", "w"))
for c in UserComment.objects.all().order_by().select_related("bill__sponsor").iterator():
  w.writerow([c.user_id, c.bill_id, c.position, c.bill.sponsor.party() if c.bill.sponsor else ""])

