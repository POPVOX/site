#!runscript

# Computes bill-to-bill similarity in an offline database.

import math
import itertools

from popvox.models import UserComment, BillSimilarity

# Loop through the comments and collect in a list all of the bills commented on by
# each user, user by user. Then increment a cooccurrence matrix for each pair
# in the bill list. The traditional thing to do would be to build a bill-user matrix,
# but since bills come from a smaller set than users we'll build a bill-bill matrix.
matrix = { }
bills = []
last_user = None
for c in itertools.chain(UserComment.objects.order_by('user').iterator(), [None]):
	if c == None or c.user_id != last_user:
		# bills contains all of the bills commented on by the last user
		for b1 in bills:
			if not b1 in matrix: matrix[b1] = {}
			for b2 in bills:
				if not b2 in matrix[b1]: matrix[b1][b2] = 0 
				matrix[b1][b2] += 1.0/float(len(bills))
		
		# reset and continue with the next user
		bills = []
		if c == None: break # finished
		
	last_user = c.user_id
	bills.append(c.bill_id)

def dot(v1, v2):
	# Compute dot product of two vectors, each stored in a sparse form as a dict.
	ret = 0.0
	for k in v1:
		if k in v2:
			ret += v1[k] * v2[k]
	return ret

def cosine(v1, v2):
	# Compute cosine similarity between two vectors, each stored
	# in a sparse form as a dict.
	return dot(v1, v2) / math.sqrt(dot(v1,v1) * dot(v2,v2))

# Find the max value in the cooccurrence matrix.
max_val = None
for b1 in matrix:
	for b2 in matrix[b1]:
		max_val = max(max_val, matrix[b1][b2])

# Compute cosine similarity between each row.
for b1 in matrix:
	print b1
	
	# Compute similarity scores between this bill and all bills with a greater id.
	sim = {}
	for b2 in matrix[b1]: # limit the scoring to bills that at least one User commented on both
		if b1 < b2:
			sim[b2] = cosine(matrix[b1], matrix[b2])
			
			# weight the score by the highest cooccurrence rate in each
			sim[b2] *= max(matrix[b1].values())/max_val * max(matrix[b2].values())/max_val
	
	# Sort the similarity scores in descending order.
	sim = list(sim.items()) # make it a (k,v) list
	sim.sort(key = lambda x : -x[1])
	
	# Store the top scores.
	BillSimilarity.objects.filter(bill1 = b1).delete()
	for b2, score in sim[0:5]:
		print b1, b2, score
		bs = BillSimilarity()
		bs.bill1_id = b1
		bs.bill2_id = b2
		bs.similarity = score
		bs.save()

