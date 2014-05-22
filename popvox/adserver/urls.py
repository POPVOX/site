from django.conf.urls.defaults import *

urlpatterns = patterns('',
	(r'^showad/(\d+)\.(html|js)$', 'adserver.views.banner'),
	(r'^click$', 'adserver.views.click'),
)

