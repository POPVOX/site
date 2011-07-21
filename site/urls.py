import os, os.path

from django.conf.urls.defaults import *
from django.views.generic import list_detail

from django.contrib import admin
admin.autodiscover()

import settings

urlpatterns = patterns('',
	(r'^(|congress|organization|about|about/team|about/principles|about/whyitworks|about/contact|legal|advertising|press(?:/\d\d\d\d-\d\d-\d\d/[a-z_]+)?|jobs|faq|blog_template)$', 'popvox.views.main.staticpage'), # maps arg to a template file name without checking for safety, so options must be defined in the regex explicitly
	
	(r'^post/home/subscribe$', 'popvox.views.main.subscribe_to_mail_list'),
	
	(r'^home$', 'popvox.views.home.home'),
	(r'^home/suggestions$', 'popvox.views.home.home_suggestions'),
	(r'^docket$', 'popvox.views.home.docket'),
	(r'^ajax/docket/bill_categories$', 'popvox.views.home.legstaff_bill_categories'),
	(r'^ajax/docket/bill_category_panel$', 'popvox.views.home.legstaff_bill_category_panel'),
	(r'^home/constituent-messages$', 'popvox.views.home.legstaff_download_messages'),
	
	(r'^activity$', 'popvox.views.home.activity'),
	(r'^ajax/activity$', 'popvox.views.home.activity_getinfo'),
	(r'^waiting-for-reintroduction$', 'popvox.views.home.waiting_for_reintroduction'),
	(r'^delivery-status-report$', 'popvox.views.home.delivery_status_report'),
	(r'^metrics$', 'popvox.views.main.metrics'),
	
	(r'^calendar$', 'popvox.views.home.calendar'),
	
	(r'^bills$', "popvox.views.bills.bills"),
	(r'^orgs$', 'popvox.views.org.orgs'),
	
	(r'^bills/us/(\d+)/([a-z]+)(\d+)$', "popvox.views.bills.bill"),
	(r'^bills/us/(\d+)/([a-z]+)(\d+)/comment/share$', "popvox.views.bills.billshare"), # Google Analytics goal
	(r'^bills/us/(\d+)/([a-z]+)(\d+)/comment(/clear|/support|/oppose|/finish)?$', "popvox.views.bills.billcomment"),# Google Analytics funnel page
	(r'^bills/us/(\d+)/([a-z]+)(\d+)/comment/(\d+)$', "popvox.views.bills.billshare"),
	(r'^ajax/bills/share$', "popvox.views.bills.billshare_share"),
	(r'^bills/us/(\d+)/([a-z]+)(\d+)/upload$', "popvox.views.bills.uploaddoc"),
	(r'^ajax/bills/upload$', "popvox.views.bills.uploaddoc2"),
	(r'^ajax/bills/getdoc$', "popvox.views.bills.getdoc"),
	(r'^ajax/bills/getshorturl$', 'popvox.views.bills.getbillshorturl'),
	(r'^moderate/bills/comment/moderate/(\d+)/([a-z\-]+)$', 'popvox.views.bills.billcomment_moderate'),
	
	(r'^bills/us/(\d+)/([a-z]+)(\d+)/report$', "popvox.views.bills.billreport"),
	(r'^ajax/bills/us/(\d+)/([a-z]+)(\d+)/report/getinfo$', "popvox.views.bills.billreport_getinfo"),
	(r'^ajax/bills/comment/digg$', "popvox.views.bills.comment_digg"),
	(r'^bills/us/(\d+)/([a-z]+)(\d+)/docs/([\w\-]+)/(\d+)$', "popvox.views.bills.billdoc"),
	
	(r'^bills/search$', "popvox.views.bills.billsearch"),
	(r'^ajax/bills/search$', "popvox.views.bills.billsearch_ajax"),
	
	(r'^ajax/issues/chooser_list$', "popvox.views.bills.issuearea_chooser_list"),
	
	(r'^orgs/([\w\-]+)$', "popvox.views.org.org"),
	(r'^orgs/([\w\-]+)/_edit$', "popvox.views.org.org_edit"),
	(r'^orgs/([\w\-]+)/_newcampaign$', "popvox.views.org.org_newcampaign"),
	(r'^orgs/([\w\-]+)/([\w\-]+)$', "popvox.views.org.orgcampaign"),
	(r'^orgs/([\w\-]+)/([\w\-]+)/_edit$', "popvox.views.org.orgcampaign_edit"),
	(r'^orgs/([\w\-]+)/_action/(\d+)$', "popvox.views.org.action"),
	(r'^ajax/orgs/search$', 'popvox.views.org.org_search'),
	(r'^ajax/orgs/updatefield$', 'popvox.views.org.org_update_field'),
	(r'^ajax/orgs/updatefields$', 'popvox.views.org.org_update_fields'),
	(r'^ajax/orgs/updatelogo/([\w\-]+)$', 'popvox.views.org.org_update_logo'),
	(r'^ajax/orgs/add_staff_contact$', 'popvox.views.org.org_add_staff_contact'),
	(r'^ajax/orgs/cam/updatefield$', 'popvox.views.org.orgcampaign_updatefield'),
	(r'^ajax/orgs/cam/updatefields$', 'popvox.views.org.orgcampaign_updatefields'),
	(r'^post/org_support_oppose$', "popvox.views.org.org_support_oppose"),
	(r'^ajax/orgs/updateaction$', 'popvox.views.org.orgcampaignpositionactionupdate'),
	(r'^ajax/orgs/coalition/(join|invite|delete|leave)$', 'popvox.views.org.coalitionrequest'),
	
	(r'^accounts/login$', 'registration.views.loginform'),
	(r'^accounts/logout$', 'django.contrib.auth.views.logout'),
	
	(r'^accounts/profile$', 'popvox.views.profile.account_profile'),
	(r'^accounts/profile/change_password$', 'registration.views.password_change'),

	(r'^accounts/register(/orgstaff|/legstaff)?$', 'popvox.views.profile.register'),
	(r'^accounts/register/(check_inbox|needs_approval)$', 'popvox.views.profile.register_response'),
	(r'^accounts/switchuser/([A-Za-z0-9_]+)', 'popvox.views.profile.switch_to_demo_account'),
	
	(r'^ajax/accounts/register$', 'popvox.views.profile.register_validation'),
	(r'^ajax/accounts/profile/updatefields$', 'popvox.views.profile.account_profile_update'),
	(r'^ajax/accounts/profile/updatefield$', 'popvox.views.profile.account_profile_update2'),
	(r'^ajax/accounts/profile/trackbill$', 'popvox.views.profile.trackbill'),
	
	(r'^widgets/js/bill.js$', 'popvox.views.widgets.bill_js'),
	(r'^widgets/bill-comment-map$', "popvox.views.widgets.commentmapus"),
	(r'^widgets/top-bills$', "popvox.views.widgets.top_bills"),
		
	(r'^services/widgets$', "popvox.views.services.widget_config"),
	(r'^services/analytics$', 'popvox.views.services.analytics'),
	(r'^services/widgets/w/(?P<widgettype>commentstream|writecongress)$', "popvox.views.services.widget_render"),
	(r'^services/widgets/w/account/(?P<api_key>.{16})/(?P<widgettype>commentstream|writecongress)$', "popvox.views.services.widget_render"), # separate URL prefix aids caching vary by referrer for API key validation
	(r'^services/widgets/img/([\w/\-]+)$', "popvox.views.services.image"),
	(r'^ajax/services/setopt$', "popvox.views.services.service_account_set_option"),
	(r'^services/api/campaign/(\d+)/supporters/(csv|json)$', "popvox.views.services.download_supporters"),
	

	(r'^ajax/district-lookup$', 'writeyourrep.district_lookup.district_lookup'),

	(r'^embed/check_api_key', 'popvox.views.embed.check_api_key'),
	(r'^embed/get_writecongress_bills', 'popvox.views.embed.get_writecongress_bills'),
	(r'^embed/salsa/legagenda', 'popvox.views.embed.salsa_legagenda'),
	(r'^embed/salsa/action', 'popvox.views.embed.salsa_action'),
	(r'^embed/fb_page', 'popvox.views.embed.facebook_page'),
	
	(r'^wyr/', include('writeyourrep.urls')),
	(r'^ajax/phone_number_twilio/', include('phone_number_twilio.urls')),
	(r'^emailverif/', include('emailverification.urls')),
	(r'^registration/', include('registration.urls')),
	(r'^shorturl/', include('shorturl.urls')),
	(r'^trafficanalysis/', include('trafficanalysis.urls')),
	(r'^feedback/', include('feedback.urls')),
	(r'^adserver/', include('adserver.urls')),

	#(r'^about/photos/', include('stockphoto.urls')),

	(r'^admin/ses', include('django_ses.urls')),
	(r'^admin/', include(admin.site.urls)),
)

# for running a site that handles the admin interface only
if "ADMIN_SITE" in os.environ and os.environ["ADMIN_SITE"] == "1":
     urlpatterns = patterns('',
		(r'', include(admin.site.urls)),
	)

if settings.DEBUG:
    urlpatterns += patterns('',
	    # for debug only, since we will configure Apache to handle these directly...  (I hope)
	    (r'^media/(?P<path>.*)$', 'django.views.static.serve', {'document_root': os.path.dirname(__file__) + "/media"}),
	)

if "SITE_DOWN" in os.environ and os.environ["SITE_DOWN"] == "1":
     urlpatterns = patterns('',
		(r'^.*', 'views.sitedown'),
	)

