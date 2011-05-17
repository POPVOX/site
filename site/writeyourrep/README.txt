Here's some information about configuring and using this module.

Configuring Endpoints
============

An endpoint corresponds to a GovTrack Member of Congress ID.

There are three delivery methods and four options that can be set:

	METHOD_NONE
	-----------------------
	No electronic delivery method is available for this Member of Congress. We'll be
	printing out the messages. Set "tested" to True also so that the sending really
	skips this Member.
	
	METHOD_WEBFORM
	------------------------------
	Use the Member's contact webform.
	
	The webform field should be set to:
	
		The URL of the contact form containing the form to fill in. If the form is
		loaded within an iframe, it should be the iframe's URL.
		
		Plus a # mark.
		
		Plus a set of comma-delimeted options in the following order. All of
		the options are *OPTIONAL* except the form name.
		
		delay:SECONDS
		Enforces a delay of the given duration between submissions to
		this endpoint.
		
		post:name1=val2&name2=val2&...
		Loads the web form from the URL using a POST with the given URL-encoded
		data rather than a GET.
		
		zipstage:FORMSPEC
		Indicates that the first stage in the webform fill-in process is to submit a zipcode
		(and possibly other info, but not the message). For FORMSPEC, see next.
		
		FORMSPEC
		The name of the primary form to submit the whole comment into. This is the only
		REQUIRED option to follow the hash.
		
			FORMSPEC can be one of:
			* The "id" or "name" attribute of the form (e.g. "custom_form").
			* A period followed by the name of a CSS class assigned to the form (e.g. ".wsbform").
			* An at-sign followed by some text in the "action" attribute of the form (e.g. "@thank_you").
			* "@@empty" to match a form with no or an empty "action" attribute. Make sure there is
			  only one such form on the page. Use with caution!
			* "@@" to match the first form on the page. Use with caution!
			
		verifystage:FORMSPEC
		Some forms repeat-back the submitted fields and then have yet another form
		that actually submits the information. Usually that form is submitted automatically
		after a few seconds. Use verifystage to indicate that another form submit is needed.
		For FORMSPEC, see above.
		
		A complete webform entry might look like:
		http://personname.house.gov/contactform#zipstage:.wsbform,contactForm
		
	The webformresponse field should be set to some text to search in the final webform output
	to check that the submission was successful. If this field is not set or the text is not found in
	the webform output, the delivery is marked as UNEXPECTED_RESPONSE which requires us to
	check whether the submission was successful or not. This text should be set to something that
	occurs only on a successful submission, such as "The following information has been submitted".
	
	The tested and template fields are not used.
	
	METHOD_SMTP
	-----------------------
	Deliver the message via email.
	
	The message is formatted according to a hard-coded template and is sent to the email address
	entered into the webform field.
	
	The webformresponse, tested, and template fields are not used.
	
	
	METHOD_HOUSE_WRITEREP
	------------------------------------------
	Deliver the message using the House Write Your Rep common form.
	
	No other fields are used.
	
	
	METHOD_INPERSON
	METHOD_STAFFDOWNLOAD
	------------------------------------------
	These are not used for Endpoint configuration. They are only used to report the method of
	an actual delivery in a DeliveryRecord.
	
Running Message Delivery
===============

To start delivery of messages, run:

	cd sources/site
	popvox/wyr/send_comments.py send
	
Some environment variable settings can help with debugging:

	COMMENT=XXXXXXX popvox/wyr/send_comments.py send
	send only messages for the given comment ID (might send to two senators, for instance)

	TARGET=XXXXXXX popvox/wyr/send_comments.py send
	send only messages to the given target by GovTrack Member of Congress ID (not the Endpoint ID).
	
	ADDR=XXXXXXX popvox/wyr/send_comments.py send
	send only messages with the given PostalAddress ID
	
	LAST_ERR_SR=1 popvox/wyr/send_comments.py send
	send only messages that had a previous synonym required failure
	
Field Name Configuration
==============

The mapping from form field names and label text to the Message class attributes is given
in several Python dicts in send_message.py.

common_fieldnames:
	Maps a form field name or label in all lowercase to the Message class attribute name. For
	the Message class attributes, see the construction of the Message object in 
	popvox/wyr/send_comments.py
	
	The form field name can be appended with an underscore and the field type (i.e. text, select,
	ratio) to limit the mapping to that type of form field.
	
skippable_fields:
	A list of form field names or labels that do not need to be filled in because they are generally
	optional. A field that is not found in any of the dictionaries will generate an error, so commonly
	optional fields go here.
	
radio_choices:
	Maps form field names or labels for radio buttons to values to use for that button, to be used
	across all webforms.
	
custom_mapping:
	Maps a form field to a Message class attribute for a particular webform. The key in this dict is
	of the form endpointID_fieldname_fieldtype, and the value is the Message attribute name.
	
custom_overrides:
	Maps a form field to a particular value for a particular webform. The key in this dict is as in
	custom_mapping, and the value is the exact value to send in the POST data.
	
custom_additional_fields:
	Adds extra data into the POST that didn't seem to be evident from the form itself, probably
	because the form uses Javascript. This dict maps from an endpoint ID to a another dict from
	a form field name to a Message class attribute name. In other words, "a": "b" will cause the
	POST data to include an entry with key "a" whose value is the value of the Message class
	attribute "b".

