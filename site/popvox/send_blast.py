#!runscript
from django.contrib.auth.models import User
from django.core.mail import EmailMessage

from popvox.models import RawText

import email
import sys
import random
import datetime
import os

# get a list of target addresses from the command line, or if no
# addresses are given mail a test message.
targets = sys.stdin.readlines()
targets = [t.strip() for t in targets if t.strip() != ""]
if len(targets) == 0:
	targets.append("josh@popvox.com")

# get the message alternatives
if len(sys.argv) <= 1: raise Exception("Specify the RawText name (or multiple names for alternatives) on the command line.")
message_alternatives = [RawText.objects.get(name=a) for a in sys.argv[1:]]

try:
	os.mkdir("blast_log")
except:
	pass
logs = [open("blast_log/" + rt.name + ".txt", "a", 0) for rt in message_alternatives]
choices = zip(message_alternatives, logs)

error_log = open("blast_log/errors.txt", "a", 0)

class RawMessage(EmailMessage):
	def message(self):
		return self.raw_message

for target in targets:
	msgobj, logfile = random.choice(choices)
	
	mimeobj = email.message_from_string(msgobj.text.encode("utf8")) # MIME is bytes
	rawm = RawMessage(None, None, "bounces@popvox.com", [target]) # envelope address
	rawm.raw_message = mimeobj
	
	try:
		rawm.send()
	except Exception, e:
		print target, str(e)
		error_log.write(datetime.datetime.now().isoformat() + "\t" + msgobj.name + "\t" + target + "\t" + str(e) + "\n")
		continue
	
	logfile.write(datetime.datetime.now().isoformat() + "\t" + target + "\n")

