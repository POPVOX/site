from django.db import models
		
class Tag(models.Model):
	text = models.CharField(max_length=32)
	class Meta:
		ordering = ["text"]
	def __unicode__(self):
		return self.text

class Law(models.Model):
	NOT_REVIEWED = 0
	APPROVED = 1
	REJECTED = 2

	created = models.DateTimeField(auto_now_add=True)
	text = models.CharField(max_length=200)
	author = models.CharField(max_length=200, blank=True)
	tags = models.ManyToManyField(Tag, blank=True)
	
	status = models.IntegerField(choices=[(NOT_REVIEWED, 'Not Reviewed'), (APPROVED, 'Approved'), (REJECTED, 'Rejected')], default=NOT_REVIEWED)

	class Meta:
		ordering = ["status", "-created"]
		
	def __unicode__(self):
		return self.get_status_display() + " " + self.created.strftime("%x %X") + " " + self.text

