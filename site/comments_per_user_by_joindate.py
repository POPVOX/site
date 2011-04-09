#!runscript

from datetime import timedelta
from django.contrib.auth.models import User
from popvox.models import UserComment

data = {}

for user in User.objects.all():
	comments = user.comments.count()
	if comments == 0: continue

	dt = user.date_joined.isocalendar()[0:2] # iso year, iso week
	if not dt in data: data[dt] = [0,0,0,timedelta()]

	data[dt][0] += 1 		# number of users
	data[dt][1] += comments		# number of comments
	data[dt][2] += user.comments.filter(message__isnull=False).count()
	data[dt][3] += user.last_login - user.date_joined # stickiness

data = list(data.items())
data.sort()

print "year", "week", "users", "comments/user", "meessages/comment", "stickiness days"
for w, c in data:
	print w[0], w[1], c[0], round(float(c[1])/float(c[0]) * 10.0)/10.0, str(round(float(c[2])/float(c[1])*100.0)) + "%", c[3].days/c[0]
