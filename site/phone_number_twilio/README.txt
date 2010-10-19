Phone Number Verification with Twilio

This is a Django app which provides a convenient interface to allow a
logged-in user to verify his phone number using Twilio. The number
is saved in a model included with this app.

INSTALL
-----------

You'll need my jquery app also installed.

In settings.py, add 'phone_number_twilio' to the list of INSTALLED_APPS and set the following variables:

SITE_ROOT_URL = "http://www.yourdomain.com"
	# must not have a trailing slash

TWILIO_ACCOUNT_SID = " ... "
TWILIO_ACCOUNT_TOKEN = " ... "
TWILIO_OUTGOING_CALLERID = "1234567890"
TWILIO_INCOMING_RESPONSE = "Thank you for calling. Goodbye."
TWILIO_STORE_HASHED_NUMBERS = True

In urls.py, add to your URL configuraration:

	(r'^ajax/phone_number_twilio/', include('phone_number_twilio.urls')),

If TWILIO_STORE_HASHED_NUMBERS is True, then the module stores SHA1 hashes of the phone numbers in the database. This is useful if the app is used to verify that users create only one account and the number itself is not important (so for privacy reasons you want to throw it away).
	
If you want to enable people to dial your Twilio phone number and have it play back a simple text response set in TWILIO_INCOMING_RESPONSE, set the URL in Twilio to:

	http://www.yourdomain.com/ajax/phone_number_twilio/incoming
	
Run python manage.py syncdb to create the initial tables.
	
TO USE
----------

On the page that will contain the UI, add in the HTML <head> tag:

<script type="text/javascript" src="http://ajax.googleapis.com/ajax/libs/jquery/1.4.2/jquery.min.js"></script>

<script>
	function phone_number_twilio_callback() {
	}
</script>

The callback function will be called when the user's phone number has been verified. The number is stored in the model database for this app and is associated with the logged in user.

At the location in the page where the interface is to be displayed, put:

{% include "phone_number_twilio/verify.html" %}

You can get the phone number of a user by:

p = user.phonenumber.filter(verified=True)
if len(p) > 0:
	print p.phonenumber
else:
	print "No verified number."

Note that the model contains both verified numbers and also unverified numbers that the user has entered but failed to verify. This is to prevent the user from making too many verification attempts and from preventing a collection of users from making a DDOS attack on a phone number. See MAX_TRIES and LOCKED_DAYS in models.py.

