#!runscript

import sys

from popvox.models import PostalAddress
from writeyourrep.models import DeliveryRecord

for addr in PostalAddress.objects.filter(
	usercomment__delivery_attempts__next_attempt__isnull=True,
	usercomment__delivery_attempts__failure_reason=DeliveryRecord.FAILURE_DISTRICT_DISAGREEMENT,
	zipcode__contains="-")\
	.distinct():

	print addr.zipcode, addr.state, addr.congressionaldistrict,
	if sys.argv[-1] == "full":
		print addr.address1, addr.city, addr.state, addr.zipcode,

	print

