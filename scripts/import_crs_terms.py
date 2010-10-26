# PYTHONPATH=..:../.. DJANGO_SETTINGS_MODULE=settings python import_crs_terms.py

from xml.dom.minidom import parse

from popvox.models import *

def add_issue_area(issue, parent=None):
	issue = issue.strip()
	
	isx = IssueArea.objects.filter(name = issue)
	if len(isx) == 1:
		isx = isx[0]
	else:
		isx = IssueArea()
		isx.name = issue

		isx.slug = issue.lower().replace(" and ", "").replace(" ", "").replace("/", "").replace(",", "-")
		if len(isx.slug) > 25:
			isx.slug = isx.slug[0:25]

		if issue == "Housing and community development funding":
			isx.slug = "housingdevelopmentfunding"

		isx.parent = parent

		isx.save()

		print "Adding", isx.slug, isx.name, "(" + isx.parent.slug + ")" if isx.parent != None else ""

	return isx

dom = parse('../data/govtrack/us/liv111.xml')

for top_term in dom.getElementsByTagName('top-term'):
	ix = add_issue_area(top_term.getAttribute('value'))
	for sub_term in top_term.getElementsByTagName('term'):
		add_issue_area(sub_term.getAttribute('value'), ix)
	
