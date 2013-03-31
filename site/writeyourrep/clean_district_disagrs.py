#!runscript

import re, sys
from datetime import datetime, timedelta

from popvox.models import UserComment
from writeyourrep.models import DeliveryRecord
from writeyourrep.district_lookup import district_lookup_zipcode_housedotgov, district_lookup_coordinate, district_lookup_address

seen_addrs = set()

dd = DeliveryRecord.objects.filter(next_attempt__isnull=True, failure_reason=DeliveryRecord.FAILURE_DISTRICT_DISAGREEMENT, created__gt=datetime.now()-timedelta(days=3))

if len(sys.argv) == 2:
    dd = dd.filter(id=sys.argv[1])

for d in dd:
    m = re.search(r"^comment #(\d+) ", d.trace)
    if not m: continue
    
    try:
        comment = UserComment.objects.filter(id=m.group(1)).select_related("address").get()
    except UserComment.DoesNotExist:
        continue
    addr = comment.address

    # When we fix this address and re-run it, the old delivery record remains in the
    # system because the new delivery attempt probably went to a different office.
    # So that we don't flag it again, check that we still have pending deliveries for
    # the office targetted by the record.
    recips = comment.get_recipients()
    if not recips or not d.target.govtrackid in [r["id"] for r in recips]:
        continue

    if addr.id in seen_addrs: continue
    seen_addrs.add(addr.id)
    
    ret_house = district_lookup_zipcode_housedotgov(addr.zipcode)
    if not ret_house: continue # no hope for this zip code getting through
    
    ret_cdynegis = district_lookup_coordinate(addr.longitude, addr.latitude)
    ret_googlegis = district_lookup_address(addr.address1 + ", " + addr.city + ", " + addr.state + " " + addr.zipcode)
    if ret_googlegis: ret_googlegis = (ret_googlegis[2], ret_googlegis[3])
    
    if ret_house and ret_googlegis and addr.state == ret_house[0] and addr.congressionaldistrict != ret_house[1] \
        and ret_house == ret_googlegis:
        # If the House puts the zipcode in the same district as Google+GIS puts
        # the address, that seems like a safe way to update the district.
        print "ADDR="+str(addr.id), (addr.state, addr.congressionaldistrict), addr.zipcode, "=>", ret_house, (ret_cdynegis == ret_house)
        addr.congressionaldistrict = ret_house[1]
        addr.save()
    else:
        #print "?? ADDR="+str(addr.id), (addr.state, addr.congressionaldistrict), addr.zipcode, "vs", ret_house, ret_googlegis, ret_cdynegis
        pass
