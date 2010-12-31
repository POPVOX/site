from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django.utils import simplejson
from django.template import Context, Template, Variable

import cgi

from adserver.models import *
from adserver.adselection import select_banner

from datetime import date

register = template.Library()

@register.tag
def show_ad(parser, token):
	class Node(template.Node):
		fields = None
		def __init__(self, fields):
			self.fields = fields
		def render(self, context):
			# This is the main ad-serving code!
			if len(fields) == 0:
				raise Exception("Usage: show_ad formatkey [target1 target2 . . .]")
			
			# Find the requested ad format.
			formatname = fields.pop(0)
			try:
				format = Format.objects.get(key=formatname)
			except:
				raise Exception("There is no ad format by the name of " + formatname)
			
			# The remaining arguments are target contexts matched by this
			# ad impression. The targets are either surrounded in double quotes
			# for literals or are names of context variables. The variable can
			# resolve to either a Target directly or to a string key.
			def make_target(field):
				if field[0] == '"' and field[-1] == '"':
					field = field[1:-1]
				else:
					field = Variable(field).resolve(context)
					if type(field) == Target:
						return field
				try:
					return Target.objects.get(key=field)
				except:
					raise Exception("There is no ad target with the key " + field)
				
			targets = [make_target(f) for f in fields]
			
			# Besides the targets specified in the template tag, additionally apply
			# templates stored in the session key and context variable
			# "adserver-targets", which must be string or Target instances.
			def make_target2(field):
				if type(field) == str:
					try:
						return Target.objects.get(key=field)
					except:
						raise Exception("There is no ad target with the key " + field)
				else:
					return field
			if "request" in context and hasattr(context["request"], "session") and "adserver-targets" in  context["request"].session:
				targets += [make_target2(t) for t in context["request"].session["adserver-targets"]]
			if "adserver-targets" in  context:
				targets += [make_target2(t) for t in context["adserver-targets"]]
			
			# Find the best banner to run here.
			selection = select_banner(format, targets)
			if selection == None:
				return Template(format.fallbackhtml).render(context)
			
			b, cpm, cpc = selection
			
			# Create a SitePath object.
			sp, isnew = SitePath.objects.get_or_create(path=context["request"].path)
									
			# Create an ImpressionBlock.
			im, isnew = ImpressionBlock.objects.get_or_create(
				banner = b,
				path = sp,
				date = datetime.now().date,
				)
			
			# update the amortized CPM on the impression object
			im.cpmcost = (im.cpmcost*im.impressions + cpm) / (im.impressions + 1)
			
			# update the next CPC cost
			im.cpccost = cpc
			
			# add an impression
			im.impressions += 1
			
			im.save()
			
			# Parse the template.
			t = Template(format.html)
			
			# Apply the template to the banner and return the code.
			context.push()
			try:
				context.update({
					"banner": b,
					"impression": im,
					"cpm": cpm,
					"cpc": cpc,
					})
				return t.render(context)
			finally:
				context.pop()
			
	fields = token.split_contents()[1:]
	
	return Node(fields)

