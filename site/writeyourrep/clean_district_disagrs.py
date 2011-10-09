#!runscript

import re

from popvox.models import UserComment
from writeyourrep.models import DeliveryRecord
from writeyourrep.district_lookup import district_lookup_zipcode_housedotgov

seen_addrs = set()

for d in DeliveryRecord.objects.filter(next_attempt__isnull=True, failure_reason=DeliveryRecord.FAILURE_DISTRICT_DISAGREEMENT):
	
	m = re.search(r"^comment #(\d+) ", d.trace)
	if m:
		comment = UserComment.objects.get(id=m.group(1))
		addr = comment.address
		
		if addr.id in seen_addrs: continue
		
		sd = district_lookup_zipcode_housedotgov(addr.zipcode)
		
		seen_addrs.add(addr.id)
		
		if sd:
			new_state, new_dist = sd
			if new_state != addr.state or new_dist != addr.congressionaldistrict:			
				print addr.id, addr.state, addr.congressionaldistrict, addr.zipcode, new_state, new_dist
				if new_state != addr.state:
					print "\tchanged state!"
				else:
					addr.congressionaldistrict = new_dist
					addr.save()
					
