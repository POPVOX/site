import os

from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

import settings

urlpatterns = patterns('',
    (r'^$', 'obal.views.main'),
    (r'^post$', 'obal.views.post'),
    (r'^approve$', 'obal.views.approve'),
    (r'^ev/', include('emailverification.urls')),
)

if settings.DEBUG:
    urlpatterns += patterns('',
	    (r'^admin/', include(admin.site.urls)),
	    )
    urlpatterns += patterns('',
	    # for debug only, since we will configure Apache to handle these directly...  (I hope)
	    (r'^static/(?P<path>.*)$', 'django.views.static.serve', {'document_root': os.path.dirname(__file__) + "/static"}),
	)
