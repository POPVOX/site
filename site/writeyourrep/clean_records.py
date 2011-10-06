#!runscript

from datetime import datetime, timedelta

from popvox.govtrack import CURRENT_CONGRESS, getCongressDates
from writeyourrep.models import DeliveryRecord

# For privacy and space reasons, clear out old delivery records.

def delete(descr, **filters):
	objs = DeliveryRecord.objects.filter(**filters)
	if objs.count() == 0:
		return
	def fmt(v):
		if type(v) == datetime:
			return v.strftime("%x")
		if type(v) == tuple:
			return "(" + ", ".join([fmt(x) for x in v]) + ")"
		return str(v)
	print "Deleting", objs.count(), descr, "where", ", ".join([str(k)+"="+fmt(v) for k,v in filters.items()])
	objs.delete()

# General cleanup.

delete("old superseded failed records",
	success=False,
	next_attempt__isnull=False,
	created__lt=datetime.now()-timedelta(days=60)
	)
	
# Privacy-related cleanup.

# Delete logs that are no longer attached to comments no sooner than two months
# after after the Congressional session in which they were submitted.
# Since we didn't do any submission in the 111th Congress, this won't come up until 2013.
#last_end_of_session = getCongressDates(CURRENT_CONGRESS-1)[1]
#if last_end_of_session < datetime.now()-timedelta(days=60):
#	delete("expired records",
#		not_tied_to_a_comment_record,
#		created__lt=last_end_of_session+timedelta(days=1))
#		)

