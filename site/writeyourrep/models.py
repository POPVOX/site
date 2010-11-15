from django.db import models

class MemberOfCongressDeliveryInfo(models.Model):
	METHOD_NONE = 0
	METHOD_WEBFORM = 1
	
	govtrackid = models.IntegerField(db_index=True, unique=True)

	method = models.IntegerField(choices=[(METHOD_NONE, 'No Method Available'), (METHOD_WEBFORM, 'Webform')])
	
	webform = models.CharField(max_length=256, blank=True, null=True)
	webformresponse = models.CharField(max_length=256, blank=True, null=True)

	def __unicode__(self):
		return self.govtrackid + " " + str(self.method)

