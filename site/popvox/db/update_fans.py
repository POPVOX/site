#!runscript

import random, sys

import settings
from popvox.models import Org

# because Twitter rate-limits to 150 per hour and we don't want to
# spend more than an hour on this, randomly select only as many as we
# can update. if we did more than an hour's worth we'd have to also
# slow down the requests to make sure they were spread over multiple
# hours.
twitterers = Org.objects.filter(twittername__isnull=False).count()
drop_rate = 150.0 / float(twitterers)

orgs_to_update = Org.objects.filter(visible=True)

if len(sys.argv) == 2:
	drop_rate = 1
	orgs_to_update = Org.objects.filter(slug=sys.argv[1])
else:
	print "updating", drop_rate, "of orgs"

fb_tw_ratio = []
for org in orgs_to_update:
    print "now updating: " + org.twittername
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
	if random.random() <= drop_rate:
		org.sync_external_members()

	ft = (org.facebook_fan_count(), org.twitter_follower_count())
	if not 0 in ft:
		fb_tw_ratio.append( float(ft[0])/float(ft[1]) )

if len(orgs_to_update) < 5:
	sys.exit()

# Compute the median of the facebook-to-twitter ratios. Better than the
# mean which is thrown off by outliers. Probably more accurate than
# the ratio of the means. And a least squares fit isn't giving sensible results.
import numpy
fb_tw_ratio = numpy.median(fb_tw_ratio)

# Update the fan_count_sort_order based on a single number that takes into
# account this ratio.
for org in Org.objects.filter(visible=True):
	org.fan_count_sort_order = org.facebook_fan_count() + fb_tw_ratio * org.twitter_follower_count()
	org.save()
	
