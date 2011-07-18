#!runscript

import random

import settings
from popvox.models import Org

# because Twitter rate-limits to 150 per hour and we don't want to
# spend more than an hour on this, randomly select only as many as we
# can update. if we did more than an hour's worth we'd have to also
# slow down the requests to make sure they were spread over multiple
# hours.
twitterers = Org.objects.filter(twittername__isnull=False).count()
drop_rate = 150.0 / float(twitterers)
print "updating", drop_rate, "of orgs"

for org in Org.objects.filter(visible=True):
	if org.twittername == "":
		org.twittername = None
	if org.facebookurl == "":
		org.facebookurl = None
	
	# TODO: We don't really want this because if an org goes from
	# having a page to not having a page, then we want to clear
	# the count record. But it makes it go faster when run remotely.
	if settings.DEBUG and org.twittername == None and org.facebookurl == None:
		continue

	# twitter rate limiting
	if random.random() > drop_rate: continue
		
	org.sync_external_members()

