from django.db import models
from django.contrib.auth.models import User

import random
from datetime import datetime, timedelta

from settings import TWILIO_STORE_HASHED_NUMBERS

CODE_LENGTH = 4 # number of digits in the verification code the user must type in

MAX_TRIES = 5 # maximum number of times a user can try to verify any number
LOCKED_DAYS = 120
	# Number of days in which MAX_TRIES holds (after which the user can try to verify again)
	# The number of days after successfully verifying a number that you can't verify another.
	# The number of days after which a user attempts to verify a number that no other user
	#    can try to verify that same number.

class PhoneNumber(models.Model):
	"""Phone number information associated with a user."""
	user = models.ForeignKey(User, unique=True, related_name="phonenumber")
	date = models.DateTimeField()
	verified = models.BooleanField()
	phonenumber = models.CharField(max_length=40, db_index=True) # 40 is long enough for SHA1 hashes of phone numbers
	verificationcode = models.CharField(max_length=CODE_LENGTH)
	callinprogress = models.BooleanField()
	callstatus = models.CharField(max_length=100)
	callcount = models.IntegerField(default=0)

	def __unicode__(self):
		if self.verified:
			if not TWILIO_STORE_HASHED_NUMBERS:
				return self.user.username + " " + self.phonenumber
			else:
				return self.user.username + " verified"
		else:
			return self.user.username + " unverified"			
		
	def make_verification_code(self):
		self.verificationcode = ''.join(random.choice(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")) for x in range(CODE_LENGTH))

	def locked_until(self):
		if self.verified and (datetime.now() - self.date).days < LOCKED_DAYS:
			return (self.date + timedelta(LOCKED_DAYS)).strftime("%b %d, %Y")
		return None
