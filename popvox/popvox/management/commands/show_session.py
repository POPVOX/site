from django.core.management.base import BaseCommand
from django.contrib.sessions.models import Session

from pprint import pprint

class Command(BaseCommand):
	option_list = BaseCommand.option_list
	help = "Show a session record."
	args = 'session id'
	requires_model_validation = True
	
	def handle(self, *args, **options):
		if len(args) != 1:
			raise ValueError("Expected one argument.")

		sess = Session.objects.get(pk=args[0])
		pprint(sess.get_decoded())

