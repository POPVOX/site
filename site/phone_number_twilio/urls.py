from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^initiate$', 'phone_number_twilio.views.initiate'),
    (r'^status$', 'phone_number_twilio.views.status'),
    (r'^pickup/([a-f0-9]*)$', 'phone_number_twilio.views.pickup'),
    (r'^digits/([a-f0-9]*)$', 'phone_number_twilio.views.digits'),
    (r'^hangup/([a-f0-9]*)$', 'phone_number_twilio.views.hangup'),
    (r'^incoming$', 'phone_number_twilio.views.incoming'),
)

