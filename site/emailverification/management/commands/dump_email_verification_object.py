from django.core.management.base import BaseCommand, CommandError

from emailverification.models import *

import pprint

class Command(BaseCommand):
	args = 'verifcode'
	help = 'Dumps the object associated with an email verification.'
	
	def handle(self, *args, **options):
		if len(args) == 0:
			return
		try:
			rec = Record.objects.get(code=args[0])
		except:
			print "not found"
			return
	
		axn = rec.get_action()

		pprint.pprint(axn)
		if hasattr(axn, "__dict__"):
			pprint.pprint(axn.__dict__)
