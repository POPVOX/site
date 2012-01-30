from django.core.management.base import BaseCommand, CommandError
from optparse import make_option

import datetime

from trafficanalysis.models import Hit

class Command(BaseCommand):
	args = ''
	help = 'Displays the most recent hits to the website.'
	
	option_list = BaseCommand.option_list + (
		make_option('--user', help="Show hits for the given email address or username."),
		)
	
	def handle(self, *args, **options):
		records = Hit.objects.all()
		
		session_keys = None
		if options["user"] != None:
			records = records.filter(user__email=options["user"]) | records.filter(user__username=options["user"])
			session_keys = set()
		
		for hit in reversed(records):
			print hit.id, hit.ipaddr, hit.user, hit.time, hit.response_code, hit.path, hit.goal
			if session_keys != None: session_keys.add(hit.session_key)

		if session_keys:
			print
			print "session keys:"
			print "\n".join(session_keys)
