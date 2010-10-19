from django.core.management.base import BaseCommand, CommandError
from trafficanalysis.models import Session

class Command(BaseCommand):
	args = ''
	help = 'Displays the most recent sessions.'
	
	def handle(self, *args, **options):
		for session in reversed(Session.objects.all()[0:5]):
			print session.user, session.start, "to", session.end
			for pe in session.get_path():
				path = getattr(pe, "path", "")
				view = getattr(pe, "view", "")
				goal = getattr(pe, "goal", "")
				print "", pe.time, path, view, goal

