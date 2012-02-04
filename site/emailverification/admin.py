from models import *
from django.contrib import admin

class RecordAdmin(admin.ModelAdmin):
	readonly_fields = ("email", "code", "searchkey", "action")
	search_fields = ["email", "code"]
	list_display = ["created", "email", "link", "description"]
	actions = ['visit']

	def visit(self, request, queryset):
		from django.http import HttpResponseRedirect
		return HttpResponseRedirect(queryset[0].url())
	visit.short_description = "Visit Link"

	def link(self, obj):
		return obj.url()

	def description(self, obj):
		return unicode(obj.get_action())

admin.site.register(Record, RecordAdmin)
