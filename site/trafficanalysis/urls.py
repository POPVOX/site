from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^report$', 'trafficanalysis.views.report'),
)

