from django.core.management.base import BaseCommand, CommandError
from optparse import make_option

from trafficanalysis.models import LiveRecord, Hit

class Command(BaseCommand):
	args = ''
	help = 'Indexes recent hits.'
	
	def handle(self, *args, **options):
		# Mark a set of hits as in-progress.
		LiveRecord.objects.update(batch=1)
		
		# Convert to Hit objects. Preserve monotonic order of id.
		for r in LiveRecord.objects.filter(batch=1).order_by('id'):
			hit = Hit()
			for field in ('time', 'session_key', 'user', 'path', 'view', 'goal', 'referrer', 'ipaddr', 'response_code', 'properties'):
				setattr(hit, field, getattr(r, field))
			hit.save()

		# Clear out processed records.
		LiveRecord.objects.filter(batch=1).delete()
	
