#!runscript
import sys

from writeyourrep.models import Synonym, SynonymRequired
from popvox.models import Bill

seen = { }

for sr in SynonymRequired.objects.all():
	if sr.term1set.strip() == "" or sr.term2set.strip() == "":
		sr.delete()
		continue
	if sr.term1set.lower() in sr.term2set.split("\n"):
		sr.delete()
		continue
	if SynonymRequired.objects.filter(term1set=sr.term1set, term2set=sr.term2set).exclude(id=sr.id).exists():
		sr.delete()
		continue
	if sr.term1set.endswith("\nlegislation") and len(sr.term2set.strip().split("\n")) == 1:
		sr.term1set = sr.term1set.replace("\nlegislation", "")
	if sr.term1set.startswith("#") and len(sr.term2set.strip().split("\n")) == 1:
		sr.term1set = sr.term1set.strip().split("\n")[0]
	if len(sr.term1set.strip().split("\n")) == 1 and len(sr.term2set.strip().split("\n")) == 1:
		s = Synonym()
		s.term1 = sr.term1set.strip()
		s.term2 = sr.term2set.strip()
		s.last_resort = sr.last_resort
		try:
			s.save()
		except:
			pass
		sr.delete()
		continue
	if Synonym.objects.filter(term1__in=sr.term1set.split("\n"), term2__in=sr.term2set.split("\n"), last_resort=False).exists():
		sr.delete()
		continue
	
	if sr.term1set[0] != "#": continue
	b = Bill.from_hashtag(sr.term1set.split("\n")[0])
	
	if b.topterm != None and b.topterm.name != "Private Legislation" and b.topterm.name != "Native Americans":
		print sr.term1set.split("\n")[0], b.topterm.name
		sr.term1set = b.topterm.name
		sr.save()
		continue
	elif b.issues.count() > 0:
		print b, b.issues.all()[0]

print SynonymRequired.objects.all().count()

