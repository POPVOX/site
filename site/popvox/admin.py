from models import *
from django.contrib import admin
from django.db.models import Count
from django.forms import ModelForm

class PositionDocumentInline(admin.StackedInline):
    model = PositionDocument
    extra = 1

class BillAdmin(admin.ModelAdmin):
    list_display = ("congressnumber", "billtype", "billnumber", "title", "street_name")
    list_display_links = ("title",)
    search_fields = ("title", "street_name")
    raw_id_fields = ('vehicle_for','sponsor','reintroduced_as', 'migrate_to')
    filter_horizontal = ("cosponsors", 'committees', 'issues')
    exclude = ('srcfilehash',)
    fieldsets = (
        ("Primary Key", { "fields": ('congressnumber', 'billtype', 'billnumber', 'vehicle_for')}),
        ("Required Metadata", { "fields": ('title', 'introduced_date', 'current_status', 'current_status_date', 'num_cosponsors')}),
        ("Usual Metadata", { "fields": ('description', 'street_name', 'ask', 'notes', 'hashtags', 'topterm', 'comments_to_chamber')}),
        ("Optional Metadata", { "fields": ('sponsor', 'cosponsors', 'committees', 'issues', 'latest_action', 'reintroduced_as', 'migrate_to', 'hold_metadata')}),
        ("Upcoming Event", { "fields": ( 'upcoming_event_post_date', 'upcoming_event' ) }),
        )
    
    #inlines = [PositionDocumentInline]
    
class RegulationAdmin(admin.ModelAdmin):
    list_display = ("agency", "regnumber", "topterm", "street_name", "title")
    search_fields = ("title", "street_name")
    filter_horizontal = ['issues']

class BillEventInline(admin.StackedInline):
    model = BillEvent
    raw_id_fields = ['bill']
    extra = 3
        
class BillListAdmin(admin.ModelAdmin):
    list_display = ("title", "type", "description")
    list_display_links = ("title",)
    search_fields = ("title", "description")
    
    inlines = [BillEventInline]
    
    def save_model(self, request, obj, form, change):
        obj.set_default_slug()
        obj.save()
    
class BillEventAdmin(admin.ModelAdmin):
    list_display = ["shortname", "listname"]
    raw_id_fields = ["list"]

class UserProfileAdmin(admin.ModelAdmin):
    raw_id_fields = ("user",)
    readonly_fields = ("user","tracked_bills","antitracked_bills", "usertags")
    search_fields = ["user__username", "user__email", "fullname"]
    list_display = ["user", "fullname", "staff_info"]

class UserOrgRoleAdmin(admin.ModelAdmin):
    raw_id_fields = ("user","org")
    #readonly_fields = ("user",)
    search_fields = ["user__username", "user__email", "user__userprofile__fullname"]

class UserLegStaffRoleAdmin(admin.ModelAdmin):
    raw_id_fields = ("user",)
    #readonly_fields = ("user",)
    search_fields = ["user__username", "user__email", "user__userprofile__fullname"]
    list_display = ["user", "member", "committee", "position", "verified"]

class UserCommentAdmin(admin.ModelAdmin):
    raw_id_fields = ("user", "bill", "address")
    readonly_fields = ("user","bill","address", "delivery_attempts", "created", "updated")
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
    
class PositionDocumentAdmin(admin.ModelAdmin):
    list_display = ["bill", "title", "doctype"]
    search_fields = ["title"]

class PostalAddressAdmin(admin.ModelAdmin):
    search_fields = ("user__username","user__email","firstname","lastname","address1", "zipcode")
    raw_id_fields = ('user',)

class OrgCampaignInline(admin.TabularInline):
    model = OrgCampaign
    extra = 1
    
class OrgAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    inlines = [OrgCampaignInline]
    filter_horizontal = ("issues", )
    readonly_fields = ('logo', 'documents')
    raw_id_fields = ('coalitionmembers',)
    
class OrgCampaignPositionInline(admin.TabularInline):
    model = OrgCampaignPosition
    extra = 1
    
class OrgCampaignAdmin(admin.ModelAdmin):
    search_fields = ["name", "org__name"]
    list_display = ["org", "name"]
    
    #inlines = [OrgCampaignPositionInline] #takes way too long to load
    
class OrgCampaignPositionAdmin(admin.ModelAdmin):
    search_fields = ["campaign", "bill", "regulation"]
    list_display = ["campaign_name", "bill_shortname"]
    raw_id_fields = ['campaign', "bill", "regulation"]

class ServiceAccountAdmin(admin.ModelAdmin):
    raw_id_fields = ("user", "org")
    readonly_fields = ("api_key", "secret_key")
    search_fields = ["user__username", "user__email", "org__name", "api_key", "secret_key", "name", "notes"]
    filter_horizontal = ["permissions"]

class ServiceAccountCampaignAdmin(admin.ModelAdmin):
    raw_id_fields = ("account", "bill")
    readonly_fields = ("account", "bill")

class ServiceAccountCampaignActionRecordAdmin(admin.ModelAdmin):
    raw_id_fields = ("campaign","completed_comment")
    readonly_fields = ("campaign","completed_comment")
    search_fields = ["firstname", "lastname", "zipcode", "email"]
    list_display = ["created", "info", "zipcode", "email", "share_record"]

    def info(self, obj):
        return obj.campaign.bill.displaynumber()
        
class SlateBillForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(SlateBillForm,self).__init__(*args, **kwargs)
        bills = Bill.objects.annotate(roll_count=Count('rolls')).filter(roll_count__gt=0,congressnumber=112)
        widget_support = self.fields['bills_support'].widget
        widget_oppose = self.fields['bills_oppose'].widget
        widget_neutral = self.fields['bills_neutral'].widget
        choices = []
        for bill in bills:
            choices.append((bill.id, bill.title))
        widget_support.choices = choices
        widget_oppose.choices = choices
        widget_neutral.choices = choices

class SlateAdmin(admin.ModelAdmin):
    raw_id_fields = ["org"]
    list_display = ("name", "org")
    search_fields = ["name", "org"]
    fields = ("name", "org", "visible", "description","bills_support", "bills_oppose", "bills_neutral", "slug")
    filter_horizontal = ("bills_support", "bills_oppose", "bills_neutral")
    form = SlateBillForm
    
class SlateCommentAdmin(admin.ModelAdmin):
    raw_id_fields = ["slate"]
    list_display = ("slate", "bill")
    fields = ("slate", "bill", "comment", "slug")

class BillRecommendationAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    list_display = ["created", "name", "because"]
    
class MemberOfCongressAdmin(admin.ModelAdmin):
    search_fields = ["lastname", "id"]
    list_display = ['id', 'lastname', 'firstname']
    readonly_fields = ["id"]

class MemberBioAdmin(admin.ModelAdmin):
    def name (self,obj):
        member = MemberOfCongress.objects.get(id=obj.id)
        print member
        return member.name()

    list_display = ['id','name', 'pvurl']
    exclude = ('documents',)

class UserTagAdmin(admin.ModelAdmin):
    list_display = ("org","label","value")
    search_fields = ["org","label","value"]

admin.site.register(MailListUser)
admin.site.register(IssueArea)
admin.site.register(Org, OrgAdmin)
admin.site.register(OrgCampaign, OrgCampaignAdmin)
admin.site.register(OrgCampaignPosition, OrgCampaignPositionAdmin)
admin.site.register(OrgContact)
admin.site.register(MemberOfCongress, MemberOfCongressAdmin)
admin.site.register(Bill, BillAdmin)
admin.site.register(Regulation, RegulationAdmin)
admin.site.register(Slate, SlateAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(UserComment, UserCommentAdmin)
admin.site.register(UserCommentDigg, UserCommentDiggAdmin)
admin.site.register(UserOrgRole, UserOrgRoleAdmin)
admin.site.register(UserLegStaffRole, UserLegStaffRoleAdmin)
admin.site.register(PostalAddress, PostalAddressAdmin)
admin.site.register(PositionDocument, PositionDocumentAdmin)
admin.site.register(ServiceAccount, ServiceAccountAdmin)
admin.site.register(ServiceAccountPermission)
admin.site.register(ServiceAccountCampaign, ServiceAccountCampaignAdmin)
admin.site.register(ServiceAccountCampaignActionRecord, ServiceAccountCampaignActionRecordAdmin)
admin.site.register(BillRecommendation, BillRecommendationAdmin)
admin.site.register(MemberBio, MemberBioAdmin)
admin.site.register(UserTag, UserTagAdmin)
admin.site.register(SlateComment, SlateCommentAdmin)
admin.site.register(BillEvent, BillEventAdmin)
admin.site.register(BillList, BillListAdmin)

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
