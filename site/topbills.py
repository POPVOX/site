#!runscript

from django.db.models import Count
from popvox.models import Bill

for b in Bill.objects.annotate(c=Count("usercomments")).filter(c__gt=0).order_by("-c")[0:50]:
	print b.c, b.title

