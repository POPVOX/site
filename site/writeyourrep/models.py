from django.db import models

from settings import SITE_ROOT_URL

class Endpoint(models.Model):
	METHOD_NONE = 0 # send_message expects this to be 0
	METHOD_WEBFORM = 1
	METHOD_SMTP = 2
	METHOD_HOUSE_WRITEREP = 3
	
	govtrackid = models.IntegerField(db_index=True, unique=True)

	method = models.IntegerField(choices=[(METHOD_NONE, 'No Method Available'), (METHOD_WEBFORM, 'Webform'), (METHOD_HOUSE_WRITEREP, "WriteRep.House.Gov"), (METHOD_SMTP, "Email/SMTP")])
	
	webform = models.CharField(max_length=256, blank=True, null=True)
	webformresponse = models.CharField(max_length=256, blank=True, null=True)
	
	tested = models.BooleanField(default=False)

	def __unicode__(self):
		return str(self.govtrackid) + " " + self.webform

	def admin_url(self):
		return "%s/admin/writeyourrep/endpoint/%s/" % (SITE_ROOT_URL, str(self.id))
		
class DeliveryRecord(models.Model):
	FAILURE_NOFAILURE = -2
	FAILURE_UNHANDLED_EXCEPTION = -1
	FAILURE_HTTP_ERROR = 0
	FAILURE_FORM_PARSE_FAILURE = 1
	FAILURE_SELECT_OPTION_NOT_MAPPABLE = 2
	FAILURE_UNEXPECTED_RESPONSE = 10
	
	target = models.ForeignKey(Endpoint)
	trace = models.TextField()
	success = models.BooleanField()
	failure_reason = models.IntegerField(choices=[(FAILURE_NOFAILURE, "Not A Failure"), (FAILURE_UNHANDLED_EXCEPTION, "Unhandled Exception"), (FAILURE_HTTP_ERROR, "HTTP Error"), (FAILURE_FORM_PARSE_FAILURE, "Form Parse Fail"), (FAILURE_SELECT_OPTION_NOT_MAPPABLE, "Select Option Not Mappable"), (FAILURE_UNEXPECTED_RESPONSE, "Unexpected Response")])
	next_attempt = models.ForeignKey("DeliveryRecord", blank=True, null=True)
	created = models.DateTimeField(auto_now_add=True)
	
class Synonym(models.Model):
	term1 = models.CharField(max_length=64, db_index=True)
	term2 = models.CharField(max_length=64)
	created = models.DateTimeField(auto_now_add=True)
	class Meta:
		unique_together = [('term1', 'term2')]

class SynonymRequired(models.Model):
	term1set = models.TextField()
	term2set = models.TextField()
	created = models.DateTimeField(auto_now_add=True)

