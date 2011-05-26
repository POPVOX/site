#!runscript

from django.db.models import Count
from popvox.models import Bill

from popvox.govtrack import CURRENT_CONGRESS

for b in Bill.objects.filter(congressnumber=CURRENT_CONGRESS).annotate(c=Count("usercomments")).filter(c__gt=0).order_by("-c")[0:50]:
	print b.c, b.title

