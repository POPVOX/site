from django.db import models

import popvox.govtrack

from settings import SITE_ROOT_URL

class Endpoint(models.Model):
	METHOD_NONE = 0 # send_message expects this to be 0
	METHOD_WEBFORM = 1
	METHOD_SMTP = 2
	METHOD_HOUSE_WRITEREP = 3
	METHOD_INPERSON = 4
	METHOD_STAFFDOWNLOAD = 5
	
	METHOD_CHOICES = [(METHOD_NONE, 'No Method Available'), (METHOD_WEBFORM, 'Webform'), (METHOD_HOUSE_WRITEREP, "WriteRep.House.Gov"), (METHOD_SMTP, "Email/SMTP"), (METHOD_INPERSON, "In-Person Delivery"), (METHOD_STAFFDOWNLOAD, "Staff Download")]
	
	govtrackid = models.IntegerField(help_text="Do not change the GovTrack ID, i.e. the person, once it is set. An Endpoint is for a particular person in a particular office.")
	office = models.CharField(max_length=6, help_text="Identify the office that this person is currently serving, e.g. CA-H01 for CA's 1st district congressman, TX-S3 for the Texas Senate office that is Class 3. The office identifier is used to prevent re-submission of a comment to the same office when the person serving in that office changes (i.e. resignation followed by replacement). Do not change the office field once it is set. An Endpoint is for a particular person in a particular office.")

	method = models.IntegerField(choices=METHOD_CHOICES)
	
	webform = models.CharField(max_length=256, blank=True, null=True)
	webformresponse = models.CharField(max_length=256, blank=True, null=True)
	
	send_report_to = models.CharField(max_length=256, blank=True, null=True, help_text="The email address to send a notice to of constituent messages that can be downloaded, along with a report. Setting this field prevents the letters from being included in a printout.")
	no_print = models.BooleanField(default=False)
	
	tested = models.BooleanField(default=False)
	
	template = models.TextField(blank=True, null=True)
	
	class Meta:
		unique_together = [('govtrackid', 'office')]

	def __unicode__(self):
		ret = str(self.id) + " " + str(self.govtrackid) + " " + self.office + " " + popvox.govtrack.getMemberOfCongress(self.govtrackid)["name"] + " " + self.get_method_display()
		if self.method == Endpoint.METHOD_NONE and self.tested:
			ret += " (Tested)"
		return ret

	def save(self, *args, **kwargs):
		import re
		if not re.match(r"[A-Z][A-Z]-(H\d\d|S\d)", self.office):
			raise ValueError("Invalid office.")
		super(Endpoint, self).save(*args, **kwargs)

	def mocname(self):
		return popvox.govtrack.getMemberOfCongress(self.govtrackid)["sortkey"]

	def admin_url(self):
		return "%s/admin/writeyourrep/endpoint/%s/" % (SITE_ROOT_URL, str(self.id))
		
class DeliveryRecord(models.Model):
	FAILURE_NO_FAILURE = 0
	FAILURE_UNHANDLED_EXCEPTION = 1
	FAILURE_HTTP_ERROR = 2
	FAILURE_FORM_PARSE_FAILURE = 3
	FAILURE_SELECT_OPTION_NOT_MAPPABLE = 4
	FAILURE_UNEXPECTED_RESPONSE = 5
	FAILURE_NO_DELIVERY_METHOD = 6
	FAILURE_DISTRICT_DISAGREEMENT = 7
	
	target = models.ForeignKey(Endpoint)
	trace = models.TextField()
	success = models.BooleanField()
	failure_reason = models.IntegerField(choices=[(FAILURE_NO_FAILURE, "Not A Failure"), (FAILURE_UNHANDLED_EXCEPTION, "Unhandled Exception"), (FAILURE_HTTP_ERROR, "HTTP Error"), (FAILURE_FORM_PARSE_FAILURE, "Form Parse Fail"), (FAILURE_SELECT_OPTION_NOT_MAPPABLE, "Select Option Not Mappable"), (FAILURE_UNEXPECTED_RESPONSE, "Unexpected Response"), (FAILURE_NO_DELIVERY_METHOD, "No Delivery Method Available"), (FAILURE_DISTRICT_DISAGREEMENT, "District Disagreement")])
	method = models.IntegerField(choices=Endpoint.METHOD_CHOICES)
	next_attempt = models.OneToOneField("DeliveryRecord", blank=True, null=True, related_name="previous_attempt")
	created = models.DateTimeField(auto_now_add=True)
	
	class Meta:
		ordering = ['-created']
	
	def __unicode__(self):
		return ("OK " if self.success else "FAIL ") + self.created.strftime("%x") + " " + unicode(self.get_failure_reason_display()) + " " + self.trace[0:30] + "..."
	
class Synonym(models.Model):
	term1 = models.CharField(max_length=128, db_index=True)
	term2 = models.CharField(max_length=128)
	last_resort = models.BooleanField(default=False)
	created = models.DateTimeField(auto_now_add=True)
	auto = models.BooleanField(default=False)
	class Meta:
		unique_together = [('term1', 'term2')]
		ordering = ('term1', 'term2')
	def __unicode__(self):
		return self.term1 + " => " + self.term2 + ("" if not self.auto else " | AUTO")

class SynonymRequired(models.Model):
	term1set = models.TextField(verbose_name="Keyword in Comment")
	term2set = models.TextField(verbose_name="Options in Webform")
	last_resort = models.BooleanField(default=False)
	created = models.DateTimeField(auto_now_add=True)
	def __unicode__(self):
		return self.term1set + " => " + self.term2set
	class Meta:
		ordering = ('-term1set',)

