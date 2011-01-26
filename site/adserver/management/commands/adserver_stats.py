from django.core.management.base import BaseCommand, CommandError
from adserver.models import *

class Command(BaseCommand):
	args = ''
	help = 'Runs statistics on the adserver data.'
	
	def handle(self, *args, **options):
		for b in Banner.objects.all():
			print b
			print b.compute_ctr()
			print
			

