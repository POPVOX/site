from django.db import models
from django.contrib.auth.models import User

class Photo(models.Model):
	"""A photo being tagged."""
	url = models.CharField(max_length=128)
	created = models.DateTimeField(auto_now_add=True)
	taggable = models.BooleanField(default=True)
	
	def __unicode__(self):
		return self.url
		
class Tag(models.Model):
	"""A thing tagged in a photo."""
	photo = models.ForeignKey(Photo, db_index=True)
	owner = models.ForeignKey(User, db_index=True)
	created = models.DateTimeField(auto_now_add=True)
	coord_x = models.FloatField()
	coord_y = models.FloatField()
	network = models.IntegerField(choices=[(0, "None"), (1, "Facebook")])
	uid = models.IntegerField(blank=True, null=True)
	name = models.CharField(max_length=128)
	
	def __unicode__(self):
		return unicode(self.photo) + ": " + self.name
		

