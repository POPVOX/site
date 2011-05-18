#!runscript

from writeyourrep.send_message import Synonym, SynonymRequired

def do_test(term1set, term2set):
	# Find all existing mappings for the first term.
	counters = { }
	for s1 in Synonym.objects.filter(term1=term1set[0], last_resort=False, auto=False):
		# Find other terms that map to the same right-hand term, besides of course the original term.
		for s2 in Synonym.objects.filter(term2=s1.term2, last_resort=False, auto=False).exclude(term1=term1set[0]):
			# ...and see if any of those map to one of the right-hand-side options in this SynonymRequired.
			for s3 in Synonym.objects.filter(term1=s2.term1, last_resort=False, auto=False):
				if s3.term2 in term2set:
					if not s3.term2 in counters: counters[s3.term2] = 0
					counters[s3.term2] += 1
	if len(counters) > 0:
		value, mx = None, 0
		for k, v in counters.items():
			if v > mx and v > 5:
				value = k
				mx = v
		if value:
			print repr(term1set), value.encode("utf8")

# Do a test on each SynonymRequired...
for s in SynonymRequired.objects.all():
	term1set = s.term1set.strip().split("\n")
	term2set = s.term2set.strip().split("\n")
	do_test(term1set, term2set)


