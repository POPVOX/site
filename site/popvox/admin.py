from models import *
from django.contrib import admin

class BillAdmin(admin.ModelAdmin):
	list_display = ("congressnumber", "billtype", "billnumber", "title", "street_name")
	list_display_links = ("title",)
	search_fields = ("title", "street_name")
	readonly_fields = ("congressnumber", "billtype", "billnumber", "sponsor", "committees", "topterm", "issues", "title", "current_status", "current_status_date", "num_cosponsors", "latest_action")

class UserProfileAdmin(admin.ModelAdmin):
	raw_id_fields = ("user",)
	readonly_fields = ("user","tracked_bills","antitracked_bills")
	search_fields = ["user__username", "user__email", "fullname"]
	list_display = ["user", "fullname", "staff_info"]

class UserOrgRoleAdmin(admin.ModelAdmin):
	raw_id_fields = ("user",)
	#readonly_fields = ("user",)
	search_fields = ["user__username", "user__email", "user__userprofile__fullname"]

class UserLegStaffRoleAdmin(admin.ModelAdmin):
	raw_id_fields = ("user",)
	#readonly_fields = ("user",)
	search_fields = ["user__username", "user__email", "user__userprofile__fullname"]
	list_display = ["user", "member", "committee", "position", "verified"]

class UserCommentAdmin(admin.ModelAdmin):
	raw_id_fields = ("user", "bill", "address")
	readonly_fields = ("user","bill","address", "delivery_attempts")
	search_fields = ("user__username", "user__email")
	list_display = ['created', 'user', 'position', 'bill', 'message_trunc', 'address', 'status_info']
	actions = ['set_status_hold']
	def message_trunc(self, obj):
		return obj.message[0:15] if obj.message != None else None
	def status_info(self, obj):
		if obj.status == UserComment.COMMENT_NOT_REVIEWED:
			return obj.delivery_status()
		else:
			return obj.review_status()
	def set_status_hold(self, request, queryset):
		queryset.update(status=UserComment.COMMENT_HOLD)
	set_status_hold.short_description = "Set Review Status to Hold Comments for Delivery"
		
class UserCommentDiggAdmin(admin.ModelAdmin):
	list_display = ['created', 'user', 'comment', 'diggtype']

class PostalAddressAdmin(admin.ModelAdmin):
	search_fields = ("user__username","user__email","firstname","lastname")

class OrgCampaignInline(admin.TabularInline):
    model = OrgCampaign
    extra = 1
    
class OrgAdmin(admin.ModelAdmin):
	search_fields = ["name"]
	#inlines = [OrgCampaignInline]
	filter_horizontal = ("issues", )
	readonly_fields = ('logo', 'issues', 'documents')

class ServiceAccountAdmin(admin.ModelAdmin):
	raw_id_fields = ("user", "org")
	readonly_fields = ("api_key", "secret_key")
	search_fields = ["user__username", "user__email", "org__name", "api_key", "secret_key"]

class ServiceAccountCampaignAdmin(admin.ModelAdmin):
	raw_id_fields = ("account", "bill")
	readonly_fields = ("account", "bill")

class ServiceAccountCampaignActionRecordAdmin(admin.ModelAdmin):
	raw_id_fields = ("campaign","completed_comment")
	readonly_fields = ("campaign","completed_comment")
	search_fields = ["firstname", "lastname", "zipcode", "email"]
	list_display = ["created", "info", "zipcode", "email"]

	def info(self, obj):
		return obj.campaign.bill.displaynumber()

admin.site.register(MailListUser)
admin.site.register(IssueArea)
admin.site.register(Org, OrgAdmin)
admin.site.register(OrgCampaign)
admin.site.register(OrgCampaignPosition)
admin.site.register(OrgContact)
admin.site.register(Bill, BillAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(UserComment, UserCommentAdmin)
admin.site.register(UserCommentDigg, UserCommentDiggAdmin)
admin.site.register(UserOrgRole, UserOrgRoleAdmin)
admin.site.register(UserLegStaffRole, UserLegStaffRoleAdmin)
admin.site.register(PostalAddress, PostalAddressAdmin)
admin.site.register(PositionDocument)
admin.site.register(ServiceAccount, ServiceAccountAdmin)
admin.site.register(ServiceAccountPermission)
admin.site.register(ServiceAccountCampaign, ServiceAccountCampaignAdmin)
admin.site.register(ServiceAccountCampaignActionRecord, ServiceAccountCampaignActionRecordAdmin)

class RawTextAdmin(admin.ModelAdmin):
	actions = ['view_html', 'make_short_urls', 'report_short_urls']
	
	def save_model(self, request, obj, form, change):
		if obj.is_mime():
			# Validate the MIME message and delete extraneous headers
			# that we don't want to propagate in outgoing emails. A MIME
			# message is bytes but we can only store unicode in the database,
			# so we assume we won't lose anything by encoding and then
			# decoding for storage as utf-8.
			import email
			if type(obj.text) == unicode: obj.text = obj.text.encode("utf8")
			msg = email.message_from_string(obj.text)
			for header in msg.keys():
				if not header.lower() in ('from', 'subject', 'content-type'):
					del msg[header]
			obj.text = msg.as_string().decode("utf8")
		obj.save()
	
	def view_html(self, request, queryset):
		from django.http import HttpResponse
		r = HttpResponse()
		for obj in queryset:
			r.write(obj.html())
		return r
	view_html.short_description = "Preview"
	
	def make_short_urls(self, request, queryset):
		def make_url(obj, target, cloj):
			cloj["num"] += 1
			
			import shorturl
			sr = shorturl.models.SimpleRedirect(url=target)
			sr.set_meta({ "mixpanel_event": obj.name, "mixpanel_properties": { "link_number": "%02d" % cloj["num"] }})
			sr.save()
			rec = shorturl.models.Record.objects.create(target=sr)
			return rec.url()
			
		import re
		for obj in queryset:
			cloj = { "num": 0 }
			obj.text = re.sub(
				r"https?://(www\.)?popvox.com(/[a-zA-Z0-9\-_/%+]+)?",
				lambda m : make_url(obj, m.group(0), cloj),
				obj.text)
			obj.save()
	make_short_urls.short_description = "Replace Links with Short URLs"
	
	def report_short_urls(self, request, queryset):
		from django.http import HttpResponse
		import re
		import shorturl.models
		r = HttpResponse(mimetype="text/plain")
		for obj in queryset:
			r.write(unicode(obj) + "\n")
			for m in re.finditer("http://pvox.co/([A-Za-z0-9]+)", obj.text):
				r.write(m.group(1) + "\t")
				rec = shorturl.models.Record.objects.get(code=m.group(1))
				r.write(str(rec.hits) + "\t")
				tg = rec.target
				r.write(unicode(tg) +"\t")
				if hasattr(tg, "meta"):
					r.write(repr(tg.meta()) + "\t")
				r.write("\n")
			r.write("------------------------------------------\n")
		return r
	report_short_urls.short_description = "Show Short URLs"

admin.site.register(RawText, RawTextAdmin)
