from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django.utils import simplejson

import random

register = template.Library()

@register.tag
def abtest(parser, token):
	class abtestnode(template.Node):
		testname = None
		testvalues = None
		def __init__(self, testname, testvalues):
			self.testname = testname
			self.testvalues = testvalues
		def render(self, context):
			condition = random.choice(testvalues)
			context["request"].goal = { testname: condition }
			return condition
			
	x = token.split_contents()
	tag_name = x.pop(0)
	testname = x.pop(0)
	testvalues = x
	
	return abtestnode(testname, testvalues)

@register.filter
def json(data):
	return mark_safe(simplejson.dumps(data))

