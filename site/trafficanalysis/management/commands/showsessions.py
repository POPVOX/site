from django.core.management.base import BaseCommand, CommandError
from optparse import make_option

import datetime

from trafficanalysis.models import Session

class Command(BaseCommand):
	args = ''
	help = 'Displays the most recent sessions.'
	
	option_list = BaseCommand.option_list + (
		make_option('--date', help="Show sessions that extend around a given time."),
		)
	
	def handle(self, *args, **options):
		filter = { }
		
		if len(args) == 0:
			if options["date"] != None:
				options["date"] = options["date"].replace("T", " ")
				filter["start__lte"] = options["date"]
				filter["end__gte"] = options["date"]
		
			for session in reversed(Session.objects.filter(**filter)):
				print session.user if session.user != None else "#"+str(session.id), session.start, "to", session.end
				for pe in session.get_path():
					path = getattr(pe, "path", "")
					view = getattr(pe, "view", "")
					goal = getattr(pe, "goal", "")
					print "", pe.time, path, view, goal

		else:
			
			session = Session.objects.get(id=args[0])
			print session.user if session.user != None else "#"+str(session.id), session.start, "to", session.end
			print session.get_ua()
			for pe in session.get_path():
				path = getattr(pe, "path", "")
				view = getattr(pe, "view", "")
				goal = getattr(pe, "goal", "")
				rcode = getattr(pe, "rcode", "")
				print "", pe.time, path, view, goal, rcode
