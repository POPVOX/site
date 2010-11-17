from models import *
from django.contrib import admin

class UserProfileAdmin(admin.ModelAdmin):
	raw_id_fields = ("user",)
	readonly_fields = ("user",)
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

class UserCommentAdmin(admin.ModelAdmin):
	raw_id_fields = ("bill","address")
	readonly_fields = ("user","bill","address")

class OrgCampaignInline(admin.TabularInline):
    model = OrgCampaign
    extra = 1
    
class OrgAdmin(admin.ModelAdmin):
	search_fields = ["name"]
	inlines = [OrgCampaignInline]
	filter_horizontal = ("issues", )

admin.site.register(MailListUser)
admin.site.register(IssueArea)
admin.site.register(Org, OrgAdmin)
admin.site.register(OrgCampaign)
admin.site.register(OrgCampaignPosition)
admin.site.register(OrgCampaignPositionActionRecord)
admin.site.register(OrgContact)
admin.site.register(Bill)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(UserComment, UserCommentAdmin)
admin.site.register(UserOrgRole, UserOrgRoleAdmin)
admin.site.register(UserLegStaffRole, UserLegStaffRoleAdmin)
admin.site.register(PostalAddress)

