#!runscript

import sys

from popvox.models import *

ok = 0

for line in sys.stdin:
	if line.strip() == "": continue
	try:
		prof = UserProfile.objects.get(user__email=line.strip())
		prof.allow_mass_mails = False
		prof.save()
		ok += 1
	except UserProfile.DoesNotExist:
		print "invalid email address", line.strip()
		
print ok

