from models import *
from django.contrib import admin

class OrderAdmin(admin.ModelAdmin):
	raw_id_fields = ("advertiser",)
	readonly_fields = ("active",)
	search_fields = ["advertiser__name"]
	list_display = ["__unicode__", "active"]

class BannerAdmin(admin.ModelAdmin):
	raw_id_fields = ("order",)
	readonly_fields = ("recentctr",)

admin.site.register(Advertiser)
admin.site.register(Order, OrderAdmin)
admin.site.register(Banner, BannerAdmin)
admin.site.register(Format)
admin.site.register(Target)


