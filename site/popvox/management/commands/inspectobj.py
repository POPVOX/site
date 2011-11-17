from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType

from django.db.models.fields.related import ManyToOneRel, OneToOneRel

class Command(BaseCommand):
	option_list = BaseCommand.option_list
	help = "Inspects an object for its relations to other objects in the database."
	args = 'app model id'
	requires_model_validation = True
	
	def handle(self, *args, **options):
		if len(args) != 3:
			raise ValueError("Expected three arguments.")
			
		model = ContentType.objects.get(app_label=args[0], model=args[1]).model_class()
		obj = model.objects.get(pk=int(args[2]))
		
		for (model, field), objs in get_related_objects(model, obj).items():
			if not field:
				print "parent objects", len(objs)
			else:
				if type(field.rel) in (ManyToOneRel, OneToOneRel):
					# These are essentially foreign keys, so no big deal.
					print model.__module__ + "." + model.__name__ + "->" + field.name, len(objs)
					if len(objs) < 15:
						for obj2 in objs:
							print "\t", obj2
				else:
					raise Exception("Unknown relation type.")
		
# based on django.db.models.deletion's Collector class
def get_related_objects(model, obj, collect_related=True):
	"""Returns a dict of related objects, mapping (model, field) tuples on the related
	objects to a list of objects of that type that refers back to obj. field is None for
	parent objects.
	
	When recursively investigating parent models, set collect_related to false because
	their related objects will seem to be attached to the base object."""
	
	ret = { }
	
	def add_item(model, field, obj2):
		key = (model, field)
		if not key in ret: ret[key] = []
		ret[key].append(obj2)
	
	# Recursively collect parent models, but not their related objects.
	# These will be found by meta.get_all_related_objects()
	for parent_model, ptr in model._meta.parents.iteritems():
		if ptr:
			add_item(parent_model, None, getattr(obj, ptr.name))

	if collect_related:
		for related in model._meta.get_all_related_objects(include_hidden=True):
			for obj2 in related.model._base_manager.filter(**{related.field.name: obj}):
				add_item(related.model, related.field, obj2)

	return ret

