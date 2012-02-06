#!runscript

import pprint

from popvox.views.home import user_activity_feed
from popvox.models import UserComment
from django.contrib.auth.models import User
from django.db.models import Count

top_users = UserComment.objects.values("user").annotate(count=Count("user")).order_by('-count')

user = top_users[900]
user = User.objects.get(id=user["user"])
print user, user.comments.count()

feed = user_activity_feed(user)
for item in feed:
	pprint.pprint(item)
