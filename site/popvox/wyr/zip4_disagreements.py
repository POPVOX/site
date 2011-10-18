#!runscript

import sys

from popvox.models import PostalAddress
from writeyourrep.models import DeliveryRecord

from writeyourrep.district_lookup import district_lookup_zipcode_housedotgov

for addr in PostalAddress.objects.filter(
	usercomments__delivery_attempts__next_attempt__isnull=True,
	usercomments__delivery_attempts__failure_reason=DeliveryRecord.FAILURE_DISTRICT_DISAGREEMENT,
	zipcode__contains="-")\
	.distinct().order_by('-created'):

	print addr.created, addr.usercomments.all()[0].id, addr.zipcode, addr.state, addr.congressionaldistrict, district_lookup_zipcode_housedotgov(addr.zipcode)

