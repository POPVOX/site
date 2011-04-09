from models import *
from django.contrib import admin

class RecordAdmin(admin.ModelAdmin):
	readonly_fields = ("email", "code", "searchkey", "action")
	search_fields = ["email"]
	list_display = ["created", "email", "code"]

	actions = ['get_url']
	def get_url(self, request, queryset):
		from django.http import HttpResponse
		r = HttpResponse(mimetype="text/plain")
		for obj in queryset:
			r.write(obj.email + "\t" + obj.url() + "\n")
		return r
	get_url.short_description = "Get Link URL"

admin.site.register(Record, RecordAdmin)
