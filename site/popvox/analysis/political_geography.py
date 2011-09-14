#!runscript

# Compute a political geography of the United States, based on my favorite
# data analysis technique, the SVD dimensionality reduction.
#
# The rows of the data matrix are congressional districts. The columns are
# attributes of each district: the number of supporters minus the number
# of opposers for each bill for which we have data.

import csv
import numpy
import urllib

from popvox.govtrack import CURRENT_CONGRESS, getMembersOfCongressForDistrict
from popvox.models import UserComment, Bill

spectrum_score = { }
for row in csv.reader(urllib.urlopen("http://www.govtrack.us/data/us/%d/stats/sponsorshipanalysis_h.txt" % CURRENT_CONGRESS)):
	if row[0] == "ID": continue
	spectrum_score[int(row[0])] = float(row[1]) # id = score, score is in the rnage [0, 1]

def get_num(mapping, invmapping, item):
	if not item in mapping:
		value = len(mapping)
		mapping[item] = value
		invmapping[value] = item
		return value
	else:
		return mapping[item]

def get_comments():
	# Return the comments, but only return the first few comments for a user so that
	# a district cannot revolve around a few prolific users.
	seen_uids = {}
	for  c in UserComment.objects.all().iterator():
		if not c.user_id in seen_uids: seen_uids[c.user_id] = 0
		if seen_uids[c.user_id] < 5:
			yield c
		seen_uids[c.user_id] += 1

# Count up the observations for each row to remove rows with too few observations.
cd_obs = {}
for uc in get_comments():
	cd = str(uc.state) + str(uc.congressionaldistrict)
	if not cd in cd_obs: cd_obs[cd] = 0
	cd_obs[cd] += 1
cd_exclude = sorted(cd_obs.keys(), key=lambda x : cd_obs[x])[0:len(cd_obs)/20]
	
# Form the sparse data matrix.

cd_to_row = {}
row_to_cd = {}
bill_to_column = {}
column_to_bill = {}
matrix = {} # sparse, dict of dicts

for uc in get_comments():
	cd = str(uc.state) + str(uc.congressionaldistrict)
	if cd in cd_exclude: continue

	row = get_num(cd_to_row, row_to_cd, cd)
	col = get_num(bill_to_column, column_to_bill, uc.bill_id)
	
	if not row in matrix: matrix[row] = {}
	if not col in matrix[row]: matrix[row][col] = 0
	
	if uc.position == "+":
		matrix[row][col] += 1.0/float(cd_obs[cd]) #* (1.0 if not ucs.message else 2.0)

# Form the dense data matrix.

nrows = len(cd_to_row)
ncols = len(bill_to_column)
M = numpy.zeros( (nrows , ncols) )
for i in xrange(nrows):
	for j in xrange(ncols):
		if i in matrix:
			if j in matrix[i]:
				M[i,j] = matrix[i][j]
		
# Perform SVD.

u, s, vh = numpy.linalg.svd(M)

print "S", s[0:5], "..." # print first few singular values

# Sort congressional districts by their values on the 1st principal dimension.
# We could likewise infer something about the bills by looking at the columns of vh.

districts = list(cd_to_row.keys())
districts.sort(key = lambda cd : u[cd_to_row[cd], 0])

# write out the two sets of scores, re-scaling the cd scores to be on the most close
# scale to the moc scores.
output = csv.writer(open("political_geography.csv", "wb"))
output.writerow(["cd", "cd_score1", "cd_score2", "cd_obs", "rep_score"])
for district in districts:
	mocs = getMembersOfCongressForDistrict(district, "rep")
	if len(mocs) == 1:
		rep_score = spectrum_score[mocs[0]["id"]]
	else:
		rep_score = "NA"
	output.writerow([district, u[cd_to_row[district], 0], u[cd_to_row[district], 1], cd_obs[district], rep_score])

# The first two dimensions are sort of like "eigenbills": imaginary bills that happen
# to correspond to particular sorts of sentiment among the districts. What bills do
# these eigenbills actually correspond to? They correspond with the first two
# "eigendistricts" (rows of vh). (This can be seen by creating an imaginary district
# which is a vector that has a single value 1 in some dimension and zeroes elsewhere
# and then multiplying through s and vh.)

import csv, os.path
f_clust = os.path.dirname(__file__) + "/cd_clusters.txt"
if not os.path.exists(f_clust): f_clust = None

for d in xrange(2): # first two dimensions
	bills = [(column_to_bill[i], vh[d,i]) for i in xrange(ncols) if UserComment.objects.filter(bill=column_to_bill[i]).count() > 300]
	bills.sort(key = lambda x : x[1])
	for i in range(7) + range(len(bills)-7, len(bills)):
		print d, bills[i][1], Bill.objects.get(id=bills[i][0]).title

		# Compute support/opposing percent totals across individuals
		# in an entire cluster, for each cluster.
		if f_clust:
			totals = [{"+":0, "-":0}, {"+":0, "-":0}, {"+":0, "-":0}]
			for row in csv.reader(open(f_clust)):
				if row[0] == "cd": continue
				totals[int(row[1])-1]["+"] += UserComment.objects.filter(bill__id=bills[i][0], state=row[0][0:2], congressionaldistrict=int(row[0][2:]), position="+").count()
				totals[int(row[1])-1]["-"] += UserComment.objects.filter(bill__id=bills[i][0], state=row[0][0:2], congressionaldistrict=int(row[0][2:]), position="-").count()
			print "\t", totals
			
