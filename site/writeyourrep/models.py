from django.db import models

from settings import SITE_ROOT_URL

class Endpoint(models.Model):
	METHOD_NONE = 0
	METHOD_WEBFORM = 1
	METHOD_SMTP = 2
	
	govtrackid = models.IntegerField(db_index=True, unique=True)

	method = models.IntegerField(choices=[(METHOD_NONE, 'No Method Available'), (METHOD_WEBFORM, 'Webform'), (METHOD_SMTP, "Email/SMTP")])
	
	webform = models.CharField(max_length=256, blank=True, null=True)
	webformresponse = models.CharField(max_length=256, blank=True, null=True)
	
	tested = models.BooleanField()

	def __unicode__(self):
		return str(self.govtrackid) + " " + self.webform

	def admin_url(self):
		return "%s/admin/writeyourrep/endpoint/%s/" % (SITE_ROOT_URL, str(self.id))
