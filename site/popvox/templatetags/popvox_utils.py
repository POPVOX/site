from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django.utils import simplejson
from django.template import Context, Template, Variable

import cgi
import re

from popvox.models import Bill, RawText
import popvox.views.utils
import popvox.views.bills
import popvox.govtrack

register = template.Library()

@register.filter
def pythontype(value):
	return ((type(value).__module__  + ".") if type(value).__module__ != None else "") + type(value).__name__

@register.filter(name="range")
@stringfilter
def getrange(value):
    """Counts 0, 1, 2, ..."""
    return xrange(int(value))
  
@register.filter
@stringfilter
def wraplines(value, arg):
    """Splits value on newline characters and then wraps each line
    with <arg>...</arg> tags."""
    return mark_safe("".join(["<" + arg + ">" + cgi.escape(line) + "</" + arg + ">" for line in value.split("\n")]))

@register.filter
@stringfilter
def parse_feed_time(date):
	# feedparser converts times to UTC without giving us timezone info (which
	# is hard to find for any given date because of DST), so we format it ourself.
	# We're only getting feeds from GovTrack so we know how they are formatted.
	date = date.strip()
	if date.endswith(" -0400") or date.endswith(" -0500"):
		date = date[0:-5].strip()
	if date.endswith(" 00:00:00"):
		date = date[0:-9].strip()
	return date

@register.filter
@stringfilter
def translate_govtrack_link(href):
	href_bill = "http://www.govtrack.us/congress/bill.xpd?bill="
	if href.startswith(href_bill):
		m = re.match(r"([hs][rjc]?)(\d+)-(\d+)", href[len(href_bill):])
		if m != None:
			b = Bill()
			b.congressnumber = int(m.group(2))
			b.billtype = m.group(1)
			b.billnumber = int(m.group(3))
			return b.url()
	return href

@register.filter
def split_in_two(items):
	if len(items) <= 1:
		return [items]
	return [items[0:len(items)/2], items[len(items)/2:]]

@register.filter
def split_at(items, count):
	if len(items) <= count:
		return [items]
	else:
		return [items[0:int(count)], items[int(count):]]

@register.filter
def date2(date):
	return popvox.views.utils.formatDateTime(date)
	
@register.filter
def json(data):
	return mark_safe(simplejson.dumps(data))

@register.filter
def niceurl(data):
	data = data.replace("http://", "")
	data = data.replace("www.", "")
	if data[-1] == "/":
		data = data[:-1]
	if len(data) > 30:
		data = data[:14] + "..." + data[-14:]
	return data

@register.tag
def more(parser, token):
	class MoreNode(template.Node):
		blockid = None
		nodelist = None
		def __init__(self, blockid, nodelist):
			self.blockid = blockid
			self.nodelist = nodelist
		def render(self, context):
			return "<div id='" + self.blockid + "' style='display: none; clear: both'>" \
				+ self.nodelist.render(context) \
				+ "</div>" \
				+ """<script>$(function(){ """ \
				+ """$('#%s_more').click( function() { $('#%s_more').hide(); $('#%s_less').show(); $('#%s').fadeIn(); return false; } );"""  % (blockid, blockid, blockid, blockid) \
				+ """$('#%s_less').click( function() { $('#%s_more').show(); $('#%s_less').hide(); $('#%s').fadeOut(); return false; } );"""  % (blockid, blockid, blockid, blockid) \
				+ """});</script>"""
			
	tag_name, blockid = token.split_contents()
	nodelist = parser.parse(('endmore',))
	parser.delete_first_token()
		
	return MoreNode(blockid, nodelist)

@register.tag
def bill_statistics(parser, token):
	class BillStatisticsNode(template.Node):
		bill = None
		varname = None
		options = None
		def __init__(self, bill, varname, options):
			self.bill = bill
			self.varname = varname
			self.options = options
		def render(self, context):
			# Get the statistics for a bill, for the default population segment for
			# the user context.

			default_state, default_district = popvox.views.bills.get_default_statistics_context(context["request"].user)

			stats = None
			if default_district != None and default_district != 0:
				stats = popvox.views.bills.bill_statistics(self.bill.resolve(context),
					default_state + "-" + str(default_district),
					default_state + "-" + str(default_district),
					address__state=default_state,
					address__congressionaldistrict=default_district)
				if options == "local":
					context[self.varname] = stats
					return ""
					
			# If no district data, fall back to state data.
			if stats == None and default_state != None:
				stats = popvox.views.bills.bill_statistics(self.bill.resolve(context),
					default_state,
					popvox.govtrack.statenames[default_state],
					address__state=default_state)
				if options == "local":
					context[self.varname] = stats
					return ""
				
			# If no state data, fall back to all data.
			if stats == None:
				stats = popvox.views.bills.bill_statistics(self.bill.resolve(context),
					"POPVOX Nation",
					"POPVOX Nation")
					
			context[self.varname] = stats
		
			return ''
			
	fields = token.split_contents()
	
	options = None
	if len(fields) == 4:
		tag_name, bill, _as_, varname = fields
	elif len(fields) == 5:
		tag_name, bill, _as_, varname, options = fields
	else:
		raise Exception("Wrong number of parameters to billstatistics")
		
	return BillStatisticsNode(template.Variable(bill), varname, options)

@register.simple_tag #takes_context=True)
def rawtext(key):
	t = Template(RawText.objects.get(name=key).html())
	context = Context()
	context.push()
	try:
		context.update({})
		return t.render(context)
	finally:
		context.pop()

