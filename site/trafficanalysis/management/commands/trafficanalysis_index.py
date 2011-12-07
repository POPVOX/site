from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from optparse import make_option

from trafficanalysis.models import LiveRecord, Hit

class Command(BaseCommand):
	args = ''
	help = 'Indexes recent hits.'
	
	def handle(self, *args, **options):
		# Mark a set of LiveRecord hits as in-progress.
		LiveRecord.objects.update(batch=1)

		# Copy the LiveRecord hits into the Hit table, where they will get indexed.
		c = connection.cursor()
		c.execute("INSERT INTO trafficanalysis_hit SELECT * FROM trafficanalysis_liverecord WHERE batch = 1")
		
		# Clear out processed LiveRecord rows.
		LiveRecord.objects.filter(batch=1).delete()

