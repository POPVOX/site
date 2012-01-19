from django.conf.urls.defaults import *

urlpatterns = patterns('',
	(r'^ajaxreq$', 'tagfriends.views.ajaxreq'),
)

