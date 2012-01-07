#!runscript

from xml.dom.minidom import parseString
from xml.dom import Node
import re
import logging
import cssutils
from cssutils.css import CSSStyleRule

cssutils.log.setLevel(logging.FATAL)

def css_selectors_match(selector, context):
	# The parts of the selector must match elements of context
	# in order, possibly skipping elements in context, except
	# for the last one which must match the last element of
	# context.
	j = 0 # next element in context to match
	patterns = selector.split(" ")
	for i, pattern in enumerate(patterns):
		# does this part of the selector match any part of the context
		# starting with context[j]?
		
		# last selector part must match the current node
		if i == len(patterns)-1: j = len(context) - 1
		
		pattern = re.split("([#:.]?\w+)", pattern)
		while True:
			# all parts of pattern must match context[j]
			for part in pattern:
				if part == "": continue
				if part[0] == "#" and context[j]["id"] != part[1:]: break
				if part[0] == "." and part[1:] not in context[j]["classes"]: break
				if part[0] not in ("#", ":", ".") and context[j]["nodeName"] != part: break
			else:
				# no parts of this pattern failed to match, so the pattern matches
				if i == len(patterns)-1: return True # last pattern matched
				if j == len(context)-1: return False # overran the end of the context but not done
				j += 1
				break # stop evaluating this pattern against the context
				
			# the pattern does not match, try it on the next element in the context
			if j == len(context)-1: return False # overran the end of the context but not done
			j += 1

	return False
	
def apply_css_inline(node, css, context=[]):
	if node.nodeType != Node.ELEMENT_NODE:
		return

	# Append node information to a clone of the context.
	context2 = list(context)
	context2.append( { "nodeName": node.nodeName, "id": node.getAttribute("id"), "classes": set(node.getAttribute("class").split(" ")) })
	
	# Write all CSS properties that apply here to the style attribute
	# of this node.
	inline = ""
	
	for rule in css:
		if not isinstance(rule, CSSStyleRule): continue
		
		# Does this rule apply to this node? At least one Selector in
		# the SelectorList must match the context.
		for sel in rule.selectorList:
			if css_selectors_match(sel.selectorText, context2):
				inline += rule.style.getCssText("") + ";"
				break

	inline += node.getAttribute("style").strip()

	node.setAttribute("style", inline)
		
	for m in node.childNodes:
		apply_css_inline(m, css, context2)

def apply_css(htmldocument):
	from StringIO import StringIO
	
	doc = parseString(htmldocument)
	
	def getnodetext(n, w=None):
		if w == None: w = StringIO()
		if hasattr(n, "data"):
			w.write(n.data)
		else:
			for m in n.childNodes:
				getnodetext(m, w)
		return w
	
	maincss = None
	for n in doc.documentElement.childNodes:
		# Collect the CSS stylesheets.
		if n.nodeName == "head":
			for m in n.childNodes:
				if m.nodeName == "style" and m.getAttribute("inline") != "false":
					css = cssutils.parseString(getnodetext(m).getvalue())
					if maincss == None:
						maincss = css
					else:
						for r in css:
							maincss.add(r)
							
		# Apply the CSS stylesheets.
		if n.nodeName == "body" and maincss != None:
			apply_css_inline(n, maincss)

	return doc.toxml()

if __name__ == "__main__":
	import sys
	print apply_css(open(sys.argv[1]).read())

