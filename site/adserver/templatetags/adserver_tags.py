from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django.utils import simplejson
from django.template import Context, Template, Variable
from django.db.models import F

import cgi

from adserver.models import *
from adserver.adselection import select_banner

from adserver.uasparser import UASparser  
uas_parser = UASparser(update_interval = None)

from datetime import datetime, date, timedelta

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
			
			# Don't show ads when the user agent is a bot. Requires RequestContext.
			if not "request" in context or not "HTTP_USER_AGENT" in context["request"].META:
				return Template(format.fallbackhtml).render(context)
			ua = uas_parser.parse(context["request"].META["HTTP_USER_AGENT"])
			if ua == None or ua["typ"] == "Robot": # if we can't tell, or if we know it's a bot
				return Template(format.fallbackhtml).render(context)

			# Prepare the list of ads we've served to this user recently.
			if hasattr(context["request"], "session"):
				if not "adserver_trail" in context["request"].session:
					context["request"].session["adserver_trail"] = []
				context["request"].session["adserver_trail"] = [t for t in context["request"].session["adserver_trail"]
					if datetime.now() - t[1] < timedelta(seconds=20)]
			
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
			if hasattr(context["request"], "session") and "adserver-targets" in context["request"].session:
				targets += [make_target2(t) for t in context["request"].session["adserver-targets"]]
			if "adserver-targets" in  context:
				targets += [make_target2(t) for t in context["adserver-targets"]]
			
			# Find the best banner to run here.
			selection = select_banner(format, targets, [t[0] for t in context["request"].session["adserver_trail"]] if hasattr(context["request"], "session") else None)
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

			# Atomically update the rest.
			ImpressionBlock.objects.filter(id=im.id).update(
				# update the amortized CPM on the impression object
				cpmcost = (F('cpmcost')*F('impressions') + cpm) / (F('impressions') + 1),
			
				# update the next CPC cost
				cpccost = cpc,
			
				# add an impression
				impressions = F('impressions') + 1
				)

			# Record that this ad was shown.
			if hasattr(context["request"], "session") and not b.order.advertiser.remnant:
				context["request"].session["adserver_trail"].append( (b.id, datetime.now()) )
			
			# Parse the template. If the banner has HTML override code, use that instead.
			if b.html != None and b.html.strip() != "":
				t = Template(b.html)
			else:
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

