#!runscript
from popvox.models import UserComment
from numpy import median, percentile

source = UserComment.objects.filter(created__gt="2011-11-01").order_by('created')
num_comments = source.count()
batch_size = 2000

values = []
for batch in range(0, num_comments, batch_size):
	print batch, "/", num_comments
	for c in source[batch:min(batch+batch_size, num_comments)]:
		da = c.delivery_attempts.filter(success=True).order_by('created')
		try:
			d = da[0]
		except IndexError:
			continue
		values.append((d.created - c.created).total_seconds())

	if len(values) > 10:
		print c.created
		print "median:", median(values)/60/60/24, "days"
		print "10th percentile:", percentile(values, 10)/60/60/24, "days"
		print "90th percentile:", percentile(values, 90)/60/60/24, "days"
		print "95th percentile:", percentile(values, 95)/60/60/24, "days"

