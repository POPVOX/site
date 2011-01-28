from django.conf.urls.defaults import *

urlpatterns = patterns('',
	(r'^banner/(\d+)$', 'adserver.views.banner'),
	(r'^click$', 'adserver.views.click'),
)

