#!runscript

from writeyourrep.send_message import Synonym, SynonymRequired

OTHER = ("other", "others", "miscellaneous", "other - not listed", "optionally select an issue", "general concerns")

# For each SynonymRequired...
for s in SynonymRequired.objects.all():
	term1 = s.term1set.strip()
	term2set = s.term2set.strip().split("\n")
	counters = { }
	# ...find all other left-hand-side terms that share a common right-hand-side term with this term...
	for s2 in Synonym.objects.filter(term1=term1).exclude(term2__in=OTHER):
		for s3 in Synonym.objects.filter(term2=s2.term2).exclude(term1=term1).exclude(term1__startswith="#"):
			# ...and see if any of those map to one of the right-hand-side options in this SynonymRequired.
			for s4 in Synonym.objects.filter(term1=s3.term1).exclude(term2__in=OTHER):
				if s4.term2 in term2set:
					if not s4.term2 in counters: counters[s4.term2] = 0
					counters[s4.term2] += 1
					#print term1, "(", s3, ")",  s4.term2
	if len(counters) > 0:
		print term1.encode("utf8"), unicode(counters).encode("utf8")

