from models import *
from django.contrib import admin

class DeliveryRecordAdmin(admin.ModelAdmin):
	raw_id_fields = ("target", "next_attempt")
	readonly_fields = ("created", "target", "next_attempt", "trace") #, "success", "failure_reason")
	date_hierarchy = "created"
	list_display = ("created", "target", "success", "failure_reason")
	list_filter = ("success", "failure_reason", "created")

class SynonymRequiredAdmin(admin.ModelAdmin):
	list_display = ("term1set", "term2set")
	def save_model(self, request, obj, form, change):
		t1 = form.cleaned_data["term1set"]
		t2 = form.cleaned_data["term2set"]
		if not "\n" in t1 and not "\n" in t2:
			s = Synonym()
			s.term1 = t1
			s.term2 = t2
			s.save()
			
			# Delete any SynonymRequired object that can
			# use this synonym too. This will include obj.
			for sr in SynonymRequired.objects.all():
				if t1 in sr.term1set.strip().split("\n") and t2 in sr.term2set.strip().split("\n"):
					sr.delete()

		else:
			obj.save()
		
admin.site.register(Endpoint)
admin.site.register(DeliveryRecord, DeliveryRecordAdmin)
admin.site.register(Synonym)
admin.site.register(SynonymRequired, SynonymRequiredAdmin)

