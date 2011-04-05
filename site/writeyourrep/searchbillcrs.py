#!runscript
import sys

from writeyourrep.models import Synonym, SynonymRequired
from popvox.models import Bill

mode = None
if len(sys.argv) > 1:
	mode = sys.argv[1]

seen = { }

for sr in SynonymRequired.objects.all():
	if sr.term1set == "" or sr.term2set == "":
		sr.delete()
		continue
	if sr.term1set.lower() in sr.term2set.split("\n"):
		sr.delete()
		continue
	if len(sr.term1set.strip().split("\n")) == 1 and len(sr.term2set.strip().split("\n")) == 1:
		s = Synonym()
		s.term1 = sr.term1set.strip()
		s.term2 = sr.term2set.strip()
		try:
			s.save()
		except:
			pass
		sr.delete()
		continue
	if SynonymRequired.objects.filter(term1set=sr.term1set, term2set=sr.term2set).exclude(id=sr.id).exists():
		sr.delete()
		continue
	if Synonym.objects.filter(term1__in=sr.term1set.split("\n"), term2__in=sr.term2set.split("\n")).exists():
		sr.delete()
		continue
	
	if sr.term1set[0] != "#": continue
	b = Bill.from_hashtag(sr.term1set.split("\n")[0])
	
	if b.topterm != None:
		print sr.term1set.split("\n")[0], b.topterm.name
		sr.term1set = b.topterm.name
		sr.save()
		continue
	
	#for t in sr.term2set.split("\n"):
	#	if t in sr.term1set.lower() and t.strip() != "" and t != "other":
	#		sr.term1set = sr.term1set.split("\n")[0]
	#		sr.term2set = t
	#		sr.save()
	#		break
	
print SynonymRequired.objects.all().count()

