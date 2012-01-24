from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django.utils import simplejson
from django.template import Context, Template, Variable, TemplateSyntaxError, Library

import cgi
import re
import random
from datetime import timedelta

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
	with <arg>...</arg> tags. Also transforms URLs into links."""
	def trunc(text):
		if len(text) < 40:
			return text
		return text[0:19] + "..." + text[-19:]
	
	def urlify(url):
		if "links='false'" in arg: return url
		r1 = r"(\b(http|https)://([-A-Za-z0-9+&@#/%?=~_()|!:,.;]*[-A-Za-z0-9+&@#/%=~_()|]))"
		return re.sub(r1,
			lambda m : r'<a rel="nofollow" target="_blank" href="' + m.group(1) + '" style="font-weight: normal; color: #A62">'
			+ trunc(m.group(1)) + '</a>',
			url)
	
	arg0 = re.sub(r" .*", "", arg)
	
	return mark_safe("".join(["<" + arg + ">" + urlify(cgi.escape(line)) + "</" + arg0 + ">" for line in value.replace("\r", "\n").split("\n") if line.strip() != ""]))

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

@register.tag
def display_date(parser, token):
	class DisplayDateNode(template.Node):
		def __init__(self, dv):
			self.dv = dv
		def render(self, context):
			d = self.dv.resolve(context)
			tz_name, tz_offset = "ET", -5 # database time zone
			
			if "request" in context and hasattr(context["request"], "user"):
				user = context["request"].user
				if user.is_authenticated():
					try:
						pa = user.postaladdress_set.all().order_by("-created")[0]
						tz = pa.timezone
						
						# UTC offsets of timezones we know. Some of the time zone abbreviations are
						# made up, see PostalAddress.set_timezone.
						tzd = { "AKST": -9, "SAST": -11, "CHST": +10, "HAST": -10, "AST": -4,
							"EST": -5, "CST": -6, "MST": -7, "PST": -8 }
						
						# Since times are stored in Eastern Time, UTC-4/5, just shift by the number
						# of hours indicated, assuming daylight savings occurs simultaneously
						# everywhere. TODO.
						if tz in tzd:
							tz_name = tz
							tz_offset = tzd[tz]
						
					except IndexError:
						pass

			d = d + timedelta(hours=5 + tz_offset) 

			return popvox.views.utils.formatDateTime(d, tz=tz_name)
	
	try:
		# split_contents() knows not to split quoted strings.
		tag_name, date_var = token.split_contents()
	except ValueError:
		raise TemplateSyntaxError("%r tag requires a single argument" % token.contents.split()[0])
	return DisplayDateNode(Variable(date_var))

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
					state=default_state,
					congressionaldistrict=default_district)
				if options == "local":
					context[self.varname] = stats
					return ""
					
			# If no district data, fall back to state data.
			if stats == None and default_state != None:
				stats = popvox.views.bills.bill_statistics(self.bill.resolve(context),
					default_state,
					popvox.govtrack.statenames[default_state],
					state=default_state)
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

@register.filter
def ordinal_html(num):
	num = int(num)
	if num % 100 >= 11 and num % 100 <= 13:
		suffix = "th"
	elif num % 10 == 1:
		suffix = "st"
	elif num % 10 == 2:
		suffix = "nd"
	elif num % 10 == 3:
		suffix = "rd"
	else:
		suffix = "th"
	
	return mark_safe(str(num) + "<sup>" + suffix + "</sup>")

# based on http://djangosnippets.org/snippets/1907/
class ObfuscatedEmailNode(template.Node):
	character_set = '+-.0123456789@ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz'
	def __init__(self, context_var):
		self.char_list = list(self.character_set)
		random.shuffle(self.char_list)
		self.key = ''.join(self.char_list)
		self.context_var = template.Variable(context_var)# context_var
	def render(self, context):
		email_address = self.context_var.resolve(context)
		
		cipher_text = ''
		id = 'e' + str(random.randrange(1,999999999))
		
		for a in email_address:
			cipher_text += self.key[ self.character_set.find(a) ] if a in self.character_set else a
			
		script = 'var a="'+self.key+'";var b=a.split("").sort().join("");var c="'+cipher_text+'";var d="";'
		script += 'for(var e=0;e<c.length;e++){if(a.indexOf(c.charAt(e))>=0) d+=b.charAt(a.indexOf(c.charAt(e))); else d+=c.charAt(e);}'
		script += 'document.write("<a href=\\"mailto:"+d+"\\">"+d+"</a>")'
		
		script = "eval(\""+ script.replace("\\","\\\\").replace('"','\\"') + "\")"
		script = '<script type="text/javascript">/*<![CDATA[*/'+script+'/*]]>*/</script>'
		
		return '<noscript>[javascript protected email address]</noscript>'+ script
def obfuscated_email(parser, token):
	"""{% obfuscated_email user.email %}"""
	tokens = token.contents.split()
	if len(tokens)!=2:
		raise template.TemplateSyntaxError("%r tag accept one argument, the email address" % tokens[0])
	return ObfuscatedEmailNode(tokens[1])
register.tag('obfuscated_email', obfuscated_email)

@register.filter
@stringfilter
def truncate(value, arg):
	"""Truncates value to arg character-widths, cutting only at word boundaries if possible."""
	
	if value == "": return value
	
	arg = int(arg)
	
	# Compute the widths using this JavaScript code.
	"""
	<div id="test_container"></div>
	<div id="output_container"></div>
	<script>
	var output = "{";
	for (var i = 0; i < 128; i++) {
		var chr;
		if (i == 0) chr = "..."; // our truncation mark
		else if (i == 32) chr = "&nbsp;";
		else chr = String.fromCharCode(i);
		$('#test_container').html("<span class='start'/>" + chr + "<span class='end'/>");
		var width = ($('#test_container span.end').position().left-$('#test_container span.start').position().left);
		if (width > 0) output += i + ": " + width + ", ";
	}
	output += "}";
	$('#output_container').html(output);
	</script>
	"""
	
	# Character widths for our standard body text font: 14px Helvetica, Arial, sans-serif.
	# Character zero stores the width of "...".
	char_widths = {0: 12, 32: 4, 33: 4, 34: 5, 35: 8, 36: 8, 37: 12, 38: 9, 39: 3, 40: 5, 41: 5, 42: 5, 43: 8, 44: 4, 45: 5, 46: 4, 47: 4, 48: 8, 49: 8, 50: 8, 51: 8, 52: 8, 53: 8, 54: 8, 55: 8, 56: 8, 57: 8, 58: 4, 59: 4, 60: 8, 61: 8, 62: 8, 63: 8, 64: 14, 65: 9, 66: 9, 67: 10, 68: 10, 69: 9, 70: 9, 71: 11, 72: 10, 73: 4, 74: 7, 75: 9, 76: 8, 77: 12, 78: 10, 79: 11, 80: 9, 81: 11, 82: 10, 83: 9, 84: 9, 85: 10, 86: 9, 87: 13, 88: 9, 89: 9, 90: 9, 91: 4, 92: 4, 93: 4, 94: 7, 95: 8, 96: 5, 97: 8, 98: 8, 99: 7, 100: 8, 101: 8, 102: 4, 103: 8, 104: 8, 105: 3, 106: 3, 107: 7, 108: 3, 109: 12, 110: 8, 111: 8, 112: 8, 113: 8, 114: 5, 115: 7, 116: 4, 117: 8, 118: 7, 119: 10, 120: 7, 121: 7, 122: 7, 123: 5, 124: 4, 125: 5, 126: 8, }
	mean_char_width = sum([v for v in char_widths.values()])/len(char_widths)
	arg *= mean_char_width
	
	# Convert value to ASCII in order to compute pixel width of characters.
	# http://stackoverflow.com/questions/816285/where-is-pythons-best-ascii-for-this-unicode-database.
	import unicodedata
	punctuation = { 0x2018:0x27, 0x2019:0x27, 0x201C:0x22, 0x201D:0x22 }
	value_ascii = unicodedata.normalize('NFKD', value.translate(punctuation)).encode('ascii', 'replace')	
	
	if len(value_ascii) != len(value): raise ValueError("Hmm.")
		
	# Compute the pixel length if we truncated at....
	length_at = []
	for i in xrange(len(value_ascii)):
		length_at.append(char_widths.get(value_ascii[i], mean_char_width) + (length_at[-1] if i > 0 else 0))
		
	# If the text fits unchanged, use it.
	if length_at[-1] <= arg: return value
	
	# Split the text into words and compute the pixel length if we truncate at the end of each word.
	words = re.split(r"(\W+)", value)
	wc = 0
	length_at_word = []
	for i in xrange(len(words)):
		wc += len(words[i])
		length_at_word.append(length_at[wc-1])
	
	# Work backwards to find out the first word to chop that fits.
	for i in reversed(range(len(words))):
		if length_at_word[i] + char_widths[0] <= arg:
			return "".join(words[0:i+1]) + "..."
			
	# Work forwards to add as many characters as will fit.
	ret = ""
	for i in xrange(len(value_ascii)):
		if length_at[i] + char_widths[0] > arg: break
		ret += value[i]
	
	return ret + "..."

