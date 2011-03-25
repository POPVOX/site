from django.db import models

import popvox.govtrack

from settings import SITE_ROOT_URL

class Endpoint(models.Model):
	METHOD_NONE = 0 # send_message expects this to be 0
	METHOD_WEBFORM = 1
	METHOD_SMTP = 2
	METHOD_HOUSE_WRITEREP = 3
	METHOD_INPERSON = 4
	
	METHOD_CHOICES = [(METHOD_NONE, 'No Method Available'), (METHOD_WEBFORM, 'Webform'), (METHOD_HOUSE_WRITEREP, "WriteRep.House.Gov"), (METHOD_SMTP, "Email/SMTP"), (METHOD_INPERSON, "In-Person Delivery")]
	
	govtrackid = models.IntegerField(db_index=True, unique=True)

	method = models.IntegerField(choices=METHOD_CHOICES)
	
	webform = models.CharField(max_length=256, blank=True, null=True)
	webformresponse = models.CharField(max_length=256, blank=True, null=True)
	
	tested = models.BooleanField(default=False)
	
	template = models.TextField(blank=True, null=True)

	def __unicode__(self):
		ret = str(self.id) + " " + str(self.govtrackid) + " " + popvox.govtrack.getMemberOfCongress(self.govtrackid)["name"] + " " + self.get_method_display()
		if self.method == Endpoint.METHOD_NONE and self.tested:
			ret += " (Tested)"
		return ret

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
	term1 = models.CharField(max_length=64, db_index=True)
	term2 = models.CharField(max_length=64)
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
	created = models.DateTimeField(auto_now_add=True)
	def __unicode__(self):
		return self.term1set + " => " + self.term2set
	class Meta:
		ordering = ('-term1set',)

