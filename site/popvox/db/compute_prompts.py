#!runscript

# Computes bill-to-bill similarity in an offline database.

import math
import itertools

from django.db.models import Count

from popvox.models import Bill, UserComment, BillSimilarity
from popvox.govtrack import CURRENT_CONGRESS

# Create a bill-user matrix, using our top N users.

num_bills = Bill.objects.all().count()
matrix = { }
bill_is_current = set()
num_users = 0
for rec in UserComment.objects.values("user").annotate(count=Count("user")).filter(count__lt=num_bills/100).order_by('-count')[0:num_bills]:
	user = rec["user"]
	for billid, billcongress in UserComment.objects.filter(user=user).values_list("bill", "bill__congressnumber"):
		if not billid in matrix: matrix[billid] = set()
		matrix[billid].add(user)
		if billcongress == CURRENT_CONGRESS: bill_is_current.add(billid)
	num_users += 1

#print num_bills, num_users

def dot(v1, v2):
	# Compute dot product of two binary vectors, each stored in a sparse form as a set.
	if v1 == v2: return len(v1)
	ret = 0.0
	for k in v1:
		if k in v2:
			ret += 1
	return ret

def cosine(v1, v2):
	# Compute cosine similarity between two vectors, each stored
	# in a sparse form as a dict.
	return dot(v1, v2) / math.sqrt(dot(v1,v1) * dot(v2,v2))

# Compute cosine similarity between each row.
for b1 in matrix:
	# Compute similarity scores between this bill and all bills with a greater id.
	if len(matrix[b1]) < 5: continue
	sim = {}
	b1_is_current = (b1 in bill_is_current)
	for b2 in matrix:
		if b1 >= b2: continue # for any pair, we only need to do similarity score once
		if not b1_is_current and b2 not in bill_is_current: continue # at least one must be current
		
		if len(matrix[b2]) < 5: continue
		
		v = cosine(matrix[b1], matrix[b2])
		if v < .66: continue # not similar enough to matter
		sim[b2] = v

	# Sort the similarity scores in descending order.
	sim = list(sim.items()) # make it a (k,v) list
	sim.sort(key = lambda x : -x[1])
	
	if len(sim) == 0:
		continue
		
	#print Bill.objects.get(id=b1).title.encode("utf8")
	#print Bill.objects.get(id=sim[0][0]).title.encode("utf8")
	#print
	
	# Store the top scores.
	BillSimilarity.objects.filter(bill1 = b1).delete()
	for b2, score in sim[0:5]:
		bs = BillSimilarity()
		bs.bill1_id = b1
		bs.bill2_id = b2
		bs.similarity = score
		bs.save()

