import os, os.path

from django.conf.urls.defaults import *
from django.views.generic import list_detail

from sitemaps import *

from django.contrib import admin
admin.autodiscover()

import settings

import popvox.views.api

sitemaps = {
    'bills':BillSitemap,
    'billreports':BillReportSitemap,
    'orgs':OrgSitemap,
    'memberpages':MemberpageSitemap
}

urlpatterns = patterns('',
	(r'site-down', 'popvox.views.main.sitedown'),
	
	(r'sitemap\.xml', 'django.contrib.sitemaps.views.index', {'sitemaps':sitemaps}),
	(r'^sitemap-(?P<section>.+)\.xml$', 'django.contrib.sitemaps.views.sitemap', {'sitemaps': sitemaps}),
	
	(r'ajax/master-state', 'popvox.views.main.master_state'),
	(r'ajax/get-short-url', 'popvox.views.main.get_short_url'),
	
	(r'^(|congress|congress/letters|organization|about|about/team|about/principles|about/whyitworks|about/contact|about/testimonials|advertising|faq|blog_template|features/opendataday2011|testing)$', 'popvox.views.main.staticpage'), # maps arg to a template file name without checking for safety, so options must be defined in the regex explicitly
	(r'^press$', 'popvox.views.main.press_page'),
	(r'^legal$', 'popvox.views.main.legal_page'),
	(r'^testing$', 'popvox.views.home.testing'),

	(r'^post/home/subscribe$', 'popvox.views.main.subscribe_to_mail_list'),
	
	(r'^delete_account.html$', 'popvox.views.home.delete_account'),
	(r'^delete_account_confirmed.html$', 'popvox.views.home.delete_account_confirmed'),
	
	(r'^home$', 'popvox.views.home.home'),
	(r'^home/match$', 'popvox.views.home.congress_match'),
	(r'^home/history$', 'popvox.views.home.history'),
	(r'^gettoknow$', 'popvox.views.home.gettoknow'),
	(r'^state/(?P<searchstate>[a-zA-Z]{2})/$', 'popvox.views.home.district_info'),
	(r'^district/(?P<searchstate>[a-zA-Z]{2})/$', 'popvox.views.home.district_info'),
	(r'^district/(?P<searchstate>[a-zA-Z]{2})/(?P<searchdistrict>\d+)/$', 'popvox.views.home.district_info'),
	(r'^member/(?P<membername>[a-zA-Z\-]+)/$', 'popvox.views.home.member_page'),
	(r'^docket$', 'popvox.views.home.docket'),
	(r'^ajax/docket/bill_categories$', 'popvox.views.home.legstaff_bill_categories'),
	(r'^ajax/docket/bill_category_panel$', 'popvox.views.home.legstaff_bill_category_panel'),
	(r'^home/constituent-messages$', 'popvox.views.home.legstaff_download_messages'),
	(r'^congress/facebook$', 'popvox.views.features.legstaff_facebook_report'),
	(r'^ajax/congress/facebook$', 'popvox.views.features.legstaff_facebook_report_getinfo'),
	
	(r'^activity$', 'popvox.views.home.activity'),
	(r'^ajax/activity$', 'popvox.views.home.activity_getinfo'),
	
	# internal pages
	(r'^waiting-for-reintroduction$', 'popvox.views.home.waiting_for_reintroduction'),
	(r'^delivery-status-report$', 'popvox.views.home.delivery_status_report'),
	(r'^delivery-status-chart$', 'popvox.views.metrics.delivery_status_chart'),
	(r'^metrics$', 'popvox.views.metrics.metrics_by_period'),
	(r'^reports/(\w+)$', 'popvox.views.metrics.metrics_report_spreadsheet'),
	(r'^segments$', 'popvox.views.segmentation.segmentation_builder'),
	(r'^segments/parse$', 'popvox.views.segmentation.segmentation_parse'),
	(r'^segments/table$', 'popvox.views.segmentation.segmentation_table'),
	(r'^segments/create_conversion$', 'popvox.views.segmentation.segmentation_create_conversion'),
	
	(r'^calendar$', 'popvox.views.home.calendar'),
	
	(r'^bills$', "popvox.views.bills.bills"),
	(r'^ajax/bills/issue-area$', "popvox.views.bills.bills_issues_bills"),	
	(r'^orgs$', 'popvox.views.org.orgs'),
	
	(r'^bills/us/(\d+)/([a-z]+)(\d+)(-\d+)?$', "popvox.views.bills.bill"),
	(r'^bills/us/(\d+)/([a-z]+)(\d+)(-\d+)?/comment(/clear|/support|/oppose|/finish)?$', "popvox.views.bills.billcomment"),# Google Analytics funnel page
	(r'^bills/us/(\d+)/([a-z]+)(\d+)(-\d+)?/comment/(\d+)$', "popvox.views.bills.billshare"),
	(r'^ajax/bills/share$', "popvox.views.bills.billshare_share"),
	(r'^bills/us/(\d+)/([a-z]+)(\d+)(-\d+)?/upload$', "popvox.views.bills.uploaddoc"),
	(r'^ajax/bills/upload$', "popvox.views.bills.uploaddoc2"),
	(r'^ajax/bills/getdoc$', "popvox.views.bills.getdoc"),
	(r'^ajax/bills/getshorturl$', 'popvox.views.bills.getbillshorturl'),
	(r'^moderate/bills/comment/moderate/(\d+)/([a-z\-]+)$', 'popvox.views.bills.billcomment_moderate'),
	
	(r'^bills/us/(\d+)/([a-z]+)(\d+)(-\d+)?/report$', "popvox.views.bills.billreport"),
	(r'^ajax/bills/us/(\d+)/([a-z]+)(\d+)(-\d+)?/report/getinfo$', "popvox.views.bills.billreport_getinfo"),
	(r'^ajax/bills/comment/digg$', "popvox.views.bills.comment_digg"),
	(r'^bills/us/(\d+)/([a-z]+)(\d+)(-\d+)?/docs/([\w\-]+)/(\d+)$', "popvox.views.bills.billdoc"),
	
	(r'^bills/search$', "popvox.views.bills.billsearch"),
	(r'^ajax/bills/search$', "popvox.views.bills.billsearch_ajax"),
	(r'^ajax/bills/recommend_from_text$', "popvox.views.home.recommend_from_text"),
	
	(r'^ajax/bills/by-sponsor$', "popvox.views.home.getsponsoredbills"),
	(r'^ajax/bills/by-cosponsor$', "popvox.views.home.getcosponsoredbills"),
	
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
	
	(r'^accounts/unsubscribe', 'popvox.views.home.unsubscribe_me'),
	
	(r'^ajax/accounts/register$', 'popvox.views.profile.register_validation'),
	(r'^ajax/accounts/profile/updatefields$', 'popvox.views.profile.account_profile_update'),
	(r'^ajax/accounts/profile/updatefield$', 'popvox.views.profile.account_profile_update2'),
	(r'^ajax/accounts/profile/trackbill$', 'popvox.views.profile.trackbill'),
	
	#widgets
	(r'^widgets/js/bill.html$', 'popvox.views.widgets.bill_iframe'),
	(r'^widgets/js/bill.js$', 'popvox.views.widgets.bill_js'),
	(r'^widgets/bill-comment-map$', "popvox.views.widgets.commentmapus"),
	(r'^widgets/top-bills$', "popvox.views.widgets.top_bills"),
	(r'^widgets/minimap$', "popvox.views.widgets.minimap"),
	(r'^widgets/bill-text.js$', "popvox.views.widgets.bill_text_js"),
	(r'^widgets/bill-text$', "popvox.views.widgets.bill_text"),
	(r'^widgets/bill-inline$', "popvox.views.widgets.bill_inline"),
		
	(r'^services/widgets$', "popvox.views.services.widget_config"),
	(r'^services/analytics$', 'popvox.views.services.analytics'),
	(r'^services/widgets/w/(?P<widgettype>commentstream|writecongress)$', "popvox.views.services.widget_render"),
	(r'^services/widgets/w/account/(?P<api_key>.{16})/(?P<widgettype>commentstream|writecongress)$', "popvox.views.services.widget_render"), # separate URL prefix aids caching vary by referrer for API key validation
	(r'^services/widgets/img/([\w/\-]+)$', "popvox.views.services.image"),
	(r'^ajax/services/setopt$', "popvox.views.services.service_account_set_option"),
	(r'^services/api/campaign/(\d+)/supporters/(csv|json)$', "popvox.views.services.download_supporters"),
	
	(r'^supercommittee$', 'popvox.views.features.supercommittee'),
	#(r'^grading-congress$', 'popvox.views.features.grade_reps'),

	(r'^ajax/district-lookup$', 'writeyourrep.district_lookup.district_lookup'),

	(r'^embed/check_api_key', 'popvox.views.embed.check_api_key'),
	(r'^embed/get_writecongress_bills', 'popvox.views.embed.get_writecongress_bills'),
	(r'^embed/salsa/legagenda', 'popvox.views.embed.salsa_legagenda'),
	(r'^embed/salsa/action', 'popvox.views.embed.salsa_action'),
	(r'^embed/fb_page', 'popvox.views.embed.facebook_page'),

	# API
	(r'^api/docs$', 'popvox.views.api.documentation'),
	(r'^api/v1/bills/suggestions$', 'popvox.views.api.bill_suggestions'),
	(r'^api/v1/bills/similarity$', 'popvox.views.api.bill_similarity'),
	(r'^api/v1/bills/search$', 'popvox.views.api.bill_search'),
	(r'^api/v1/bill/(\d+)$', 'popvox.views.api.bill_metadata'),
	(r'^api/v1/bill/(\d+)/documents$', 'popvox.views.api.bill_documents'),
	(r'^api/v1/bill/(\d+)/positions$', 'popvox.views.api.bill_positions'),
	(r'^api/v1/document/(\d+)$', 'popvox.views.api.document_metadata'),
	(r'^api/v1/document/(\d+)/pages$', 'popvox.views.api.document_pages'),
	(r'^api/v1/document/(\d+)/page/(\d+).([a-z]+)$', 'popvox.views.api.document_page'),
	(r'^api/v1/document/(\d+)/search$', 'popvox.views.api.document_search'),
	(r'^api/v1/comments$', 'popvox.views.api.comments'),
	(r'^api/v1/org/(\d+)$', 'popvox.views.api.org_get_info'),
	(r'^api/v1/org/positions/(\d{4}-\d{2}-\d{2}-\d{2}:\d{2}:\d{2})$', 'popvox.views.api.org_positions'),
	(r'^api/v1/org/positions', 'popvox.views.api.org_positions'),
	(r'^api/v1/users/login$', 'popvox.views.api.user_login'),
	(r'^api/v1/users/logout$', 'popvox.views.api.user_logout'),
	(r'^api/v1/users/me$', 'popvox.views.api.user_get_info'),
	(r'^api/v1/users/registration/fields$', 'popvox.views.api.user_registration_fields'),
	(r'^api/v1/users/registration$', 'popvox.views.api.user_registration'),
	
	# Support Pages for Mobile Apps
	(r'redirect/markup_appstore$', 'popvox.views.mobileapps.ipad_billreader_appstoreredirect'),
	(r'^(ipad|ipad/registration/welcome)$', 'popvox.views.main.staticpage'),
	(r'^mobileapps/ipad_billreader/welcome$', 'popvox.views.mobileapps.ipad_billreader_welcome'),
	(r'^mobileapps/ipad_billreader/report$', 'popvox.views.mobileapps.ipad_billreader_report'),

	# external-ish apps
	(r'^wyr/', include('writeyourrep.urls')),
	(r'^emailverif/', include('emailverification.urls')),
	(r'^registration/', include('registration.urls')),
	(r'^shorturl/', include('shorturl.urls')),
	(r'^trafficanalysis/', include('trafficanalysis.urls')),
	(r'^feedback/', include('feedback.urls')),
	(r'^adserver/', include('adserver.urls')),

	#(r'^about/photos/', include('stockphoto.urls')),

	(r'^admin/', include(admin.site.urls)),

	(r"^error$", "popvox.views.main.raise_error"),

	#(r'^dowser/', include('django_dowser.urls')),
)

if not "LOCAL" in os.environ:
	# dependency to articles app is not available locally, see settings.py
	urlpatterns += patterns('',
		(r'^blog/', include('articles.urls')),
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

