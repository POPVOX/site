# PYTHONPATH=..:../.. DJANGO_SETTINGS_MODULE=settings python import_advocacy_database.py

from popvox.models import *

import cgi
import csv

Org.objects.filter(createdbyus=True).delete()

reader = csv.DictReader(open('advocacy_directory.csv'), delimiter=',', quotechar='"')
for row in reader:
	#print row

	o = Org.objects.filter(name = row["Organization"])
	if len(o) == 1:
		o = o[0]
	else:
		o = Org()
	o.approved = True
	o.visible = True
	o.name = row["Organization"]
	o.description = row["About the Organization / Organization Mission"]
	if o.description == None:
		o.description = ""
	if row["Website"] != None:
		o.website = "http://" + row["Website"]
	o.set_default_slug()
	o.createdbyus = True
	o.save()

	c = OrgContact()
	c.org = o
	c.name = row["Contact"]
	c.title = row["Title"]
	c.phonenumber = row["Phone"]
	c.email = row["Email"]
	c.save()

	for keywordcol in ("THOMAS Top Term 1", "THOMAS Top Term 1 Keywords 1", "THOMAS Top Term 1 Keywords 2", "THOMAS Top Term 1 Keywords 3", "THOMAS Top Term 1 Keywords 4", "THOMAS Top Term 2", "THOMAS Top Term 2 Keywords 1", "THOMAS Top Term 2 Keywords 2", "THOMAS Top Term 2 Keywords 3"):
		issue = row[keywordcol]
		if issue == None or issue.strip() == "":
			continue
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

		if "THOMAS Top Term 1 Keywords" in keywordcol:
			isx.parent = IssueArea.objects.get(name = row["THOMAS Top Term 1"].strip())
		if "THOMAS Top Term 2 Keywords" in keywordcol:
			isx.parent = IssueArea.objects.get(name = row["THOMAS Top Term 2"].strip())

		isx.save()

		o.issues.add(isx)
	o.save()
