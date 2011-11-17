from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from django.db.models.fields.related import ManyToOneRel, OneToOneRel

from inspectobj import get_related_objects

class Command(BaseCommand):
	option_list = BaseCommand.option_list
	help = "Merges two objects in the database by updating references to the second to the first, and then deleting the second. Only makes changes if 'update' is specified."
	args = 'app model id1 id2 [update]'
	requires_model_validation = True
	
	def handle(self, *args, **options):
		if len(args) not in (4, 5):
			raise ValueError("Expected four arguments.")
			
		model = ContentType.objects.get(app_label=args[0], model=args[1]).model_class()

		obj1 = model.objects.get(pk=int(args[2]))
		obj2 = model.objects.get(pk=int(args[3]))
		
		print "object to merge into:", obj1
		print "object to delete:", obj2
		print
		
		for (model, field), objs in get_related_objects(model, obj2).items():
			if not field:
				print "DELETE", len(objs), "parent objects"
				for o in objs: print "\t", ob
			elif type(field.rel) == ManyToOneRel:
				# ForeignKey
				print "UPDATE", len(objs), model.__module__ + "." + model.__name__ + "->" + field.name
				for ob in objs:
					error = ""
					if args[-1] == "update":
						try:
							setattr(ob, field.name, obj1)
							ob.save()
						except Exception as e:
							error = unicode(e)
					if len(objs) < 15 or error != "":
						print "\t", ob, error
					
			elif type(field.rel) == OneToOneRel:
				# can't update one to one because presumably obj1 already has one
				print field.rel.on_delete.__name__, len(objs), "one-to-one relation to", model.__module__ + "." + model.__name__, "(" + field.name + ")"
				if len(objs) < 15:
					for ob in objs: print "\t", ob
			else:
				raise Exception("Unknown relation type.")

		if args[-1] == "update":
			print ""
			
			if raw_input("delete the second object? (y/N) ") == "y":
				obj2.delete()

