from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django.utils import simplejson
from django.template import Variable

import cgi

from adserver.models import *
from adserver.adselection import show_banner

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
			
			# Requires RequestContext...
			return show_banner(format, context["request"], context, targets, context["request"].path)

	fields = token.split_contents()[1:]
	
	return Node(fields)

@register.tag
def banner_stats(parser, token):
	class Node(template.Node):
		fields = None
		def __init__(self, fields):
			self.fields = fields
		def render(self, context):
			if len(fields) == 0:
				raise Exception("Usage: banner_stats object_id")
				
			obj_id = Variable(fields[0]).resolve(context)
			
			impressions = 0
			clicks = 0
			cost = 0
			for im in ImpressionBlock.objects.filter(banner__id = obj_id):
				impressions += im.impressions
				clicks += im.clicks
				cost += im.cost()
				
			return "$%g for %d impressions/%d clicks" % (cost, impressions, clicks)

	fields = token.split_contents()[1:]
	
	return Node(fields)

