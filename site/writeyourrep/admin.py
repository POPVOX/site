from models import *
from django.contrib import admin
from django.db import IntegrityError

class EndpointAdmin(admin.ModelAdmin):
	list_display = ("govtrackid", "method", "mocname", "webformresponse")
	list_filter = ("method", "tested")
	search_fields = ["govtrackid"]

class DeliveryRecordAdmin(admin.ModelAdmin):
	raw_id_fields = ("target", "next_attempt")
	readonly_fields = ("created", "target", "next_attempt", "method") #, "trace") #, "success", "failure_reason")
	date_hierarchy = "created"
	list_display = ("created", "target", "success", "failure_reason", "method")
	list_filter = ("success", "failure_reason", "created", "method")
	search_fields = ('trace',)
	actions = ['make_success', 'make_formparsefail']

	def queryset(self, request):
		qs = super(DeliveryRecordAdmin, self).queryset(request)
		return qs.filter(next_attempt__isnull=True)

	def make_success(self, request, queryset):
		queryset.update(success=True, failure_reason=DeliveryRecord.FAILURE_NO_FAILURE)
		return None
	make_success.short_description = "Mark as Success"
	
	def make_formparsefail(self, request, queryset):
		queryset.update(success=False, failure_reason=DeliveryRecord.FAILURE_FORM_PARSE_FAILURE)
		return None
	make_formparsefail.short_description = "Mark as Form Parse Fail"
	
class SynonymAdmin(admin.ModelAdmin):
	list_display = ("created", "term1", "term2", "last_resort", "auto")

class SynonymRequiredAdmin(admin.ModelAdmin):
	list_display = ("created", "term1set", "term2set")
	def save_model(self, request, obj, form, change):
		t1 = form.cleaned_data["term1set"].strip()
		t2 = form.cleaned_data["term2set"].strip()
		
		t1 = [t.strip() for t in t1.split("\n")]
		if len(t1) > 0 and t1[0].startswith("#"): t1 = [t1[0]] # no need for the rest
		if len(t1) > 0 and t1[-1] == "legislation": t1.pop() # no need for this one
		t1 = "\n".join(t1)
		
		if not "\n" in t1 and not "\n" in t2:
			try:
				s = Synonym()
				s.term1 = t1
				s.term2 = t2
				s.last_resort = obj.last_resort
				s.save()
			except IntegrityError:
				pass
			
			if not obj.last_resort:
				# Delete any SynonymRequired object that can
				# use this synonym too.
				for sr in SynonymRequired.objects.filter(term1set__contains=t1, term2set__contains=t2).exclude(id=obj.id):
					if t1 in sr.term1set.strip().split("\n") and t2 in sr.term2set.strip().split("\n"):
						sr.delete()
			
			obj.delete()

		else:
			obj.save()
		
admin.site.register(Endpoint, EndpointAdmin)
admin.site.register(DeliveryRecord, DeliveryRecordAdmin)
admin.site.register(Synonym, SynonymAdmin)
admin.site.register(SynonymRequired, SynonymRequiredAdmin)

