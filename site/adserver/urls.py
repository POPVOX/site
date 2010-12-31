from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^click$', 'adserver.views.click'),
)

