from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django.utils import simplejson
from django.template import Context, Template

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
			
			# Find the best banner to run here.
			selection = select_banner(format, [])
			if selection == None:
				return Template(format.fallbackhtml).render(context)
			
			b, cpm, cpc = selection
			
			# Create a SitePath object.
			sp, isnew = SitePath.objects.get_or_create(path=context["request"].path)
									
			# Create an Impression.
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
			c = Context({})
			c.update(context)
			c.update({
				"banner": b,
				"impression": im,
				})
			
			return t.render(c)
			
	fields = token.split_contents()[1:]
	
	return Node(fields)

