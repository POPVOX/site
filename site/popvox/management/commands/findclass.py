from django.core.management.base import BaseCommand

import os, fnmatch
import re

class Command(BaseCommand):
	option_list = BaseCommand.option_list
	help = "Scans through all *.html files for a given class name or names."
	args = 'classname [classname ...]'
	requires_model_validation = False
	
	def handle(self, *findclassnames, **options):
		matches = []
		for root, dirnames, filenames in os.walk('.'):
			for filename in fnmatch.filter(filenames, '*.html'):
				with open(os.path.join(root, filename), "r") as f:
					html = f.read()
					for classattr in re.findall(r"class=['\"](.*?)['\"]", html):
						classnames = classattr
						
						# remove Django template expressions
						classnames = re.sub(r"{%\s*\S+\s*", " ", classnames)
						classnames = re.sub(r"\s*%}", " ", classnames)
				
						classnames = (f for f in re.split(r"\s+", classnames) if not f == "")
						for classname in classnames:
							if classname in findclassnames:
								print os.path.join(root, filename) + ":", classattr
