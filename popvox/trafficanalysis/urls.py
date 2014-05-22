from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^report$', 'trafficanalysis.views.report'),
    (r'^report/data$', 'trafficanalysis.views.report_data'),
)

