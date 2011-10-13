#!runscript

# TODO:
#   Spot check results

# Look at who is posting on a Page for a Member of Congress
# and see what percent of the posts/posters are constituents
# based on what we know about the posting invidiauls from
# their Facebook login on POPVOX.

import csv, json, urllib, urlparse

from popvox.govtrack import stateabbrs, getMembersOfCongress
from popvox.views.utils import get_facebook_app_access_token
from registration.models import AuthRecord

def get_page_wall_poster_uids(pageid):
	global access_token
	
	url = "https://graph.facebook.com/" + str(pageid) + "/feed?" \
		+ urllib.urlencode({
			"limit": 500,
			"access_token": access_token
		})
		
	ret = urllib.urlopen(url)
	if ret.getcode() != 200:
		raise Exception("Failed to load wall for %s: %s" % (pageid, ret.read()))
	ret = json.loads(ret.read())
	
	uids = { "posts": [], "comments": [], "likes": [] }
	
	for entry in ret["data"]:
		uid = entry["from"]["id"]
		if int(uid) != int(pageid):
			uids["posts"].append(uid)
		if "comments" in entry and "data" in entry["comments"]:
			for comment in entry["comments"]["data"]:
				if int(comment["from"]["id"]) != int(pageid):
					uids["comments"].append(comment["from"]["id"])
		if "likes" in entry and "data" in entry["likes"]:
			for like in entry["likes"]["data"]:
				if int(like["id"]) != int(pageid):
					uids["likes"].append(like["id"])

	return uids

def get_uid_stats(uids, state, district, pageid):
	global logoutput

	authrecords = AuthRecord.objects.filter(provider="facebook", uid__in=set(uids))
	authrecords = dict([ (ar.uid, ar.user) for ar in authrecords ])
	
	in_district_total = [0,0,0] # unknown, no, yes
	in_district_unique = [0,0,0] # unknown, no, yes
	
	uid_info = { }
	for uid in uids:
		if not uid in uid_info:
			uid_info[uid] = {
				"count": 0,
				"pvuser": uid in authrecords,
				"has_district": False,
				"count_index": 0, # unknown
			}
		
			if uid in authrecords:
				addrs = authrecords[uid].postaladdress_set.all().order_by('-created')
				if len(addrs) > 0:
					addr = addrs[0]

					uid_info[uid]["has_district"] = True
					uid_info[uid]["constituent"] = (addr.state.lower() == state.lower() and (district==None or addr.congressionaldistrict==district))
					
					if not uid_info[uid]["constituent"]:
						uid_info[uid]["count_index"] = 1 # no
					else:
						uid_info[uid]["count_index"] = 2 # yes
						
			in_district_unique[uid_info[uid]["count_index"]] += 1

			logoutput.writerow([ pageid, uid, '' if not uid_info[uid]["has_district"] else addr.id, uid_info[uid]["count_index"]  ])
					
		uid_info[uid]["count"] += 1
		in_district_total[uid_info[uid]["count_index"]] += 1
		
	return {
		"total": [len(uids), in_district_total[1] + in_district_total[2], in_district_total[2]],
		"unique": [len(uid_info), in_district_unique[1] + in_district_unique[2], in_district_unique[2]]
	}

def get_page_stats(pageid, pid, pname, state, district, pagecategory):
	global output
	
	print pageid
	
	uidsets = get_page_wall_poster_uids(pageid)
	
	uniques = get_uid_stats(uidsets["posts"]+uidsets["comments"]+uidsets["likes"], state, district, pageid)
	posts = get_uid_stats(uidsets["posts"], state, district, pageid)
	comments = get_uid_stats(uidsets["comments"], state, district, pageid)
	postlikes = get_uid_stats(uidsets["likes"], state, district, pageid)
		
	output.writerow([pid, pageid, pagecategory, pname, state, district]
		+ uniques["unique"]
		+ posts["total"]
		+ comments["total"]
		+ postlikes["total"]
		)

#####################################################################

access_token = get_facebook_app_access_token()

output = csv.writer(open("popvox/analysis/output/facebook_constituents.csv", "w"))

output.writerow(["personid", "pageid", "name", "state", "district",
	"uniques_total", "uniques_known", "uniques_indistrict",
	"posts_total", "posts_known", "posts_indistrict",
	"comments_total", "comments_known", "comments_indistrict",
	"postlikes_total", "postlikes_known", "postlikes_indistrict"])

logoutput = csv.writer(open("popvox/analysis/output/facebook_constituents_log.csv", "w"))

for moc in getMembersOfCongress():
	if not moc["current"]: continue
	if not "facebookgraphid" in moc: continue
	
	# get meta info
	url = "https://graph.facebook.com/" + str(moc["facebookgraphid"])
	ret = urllib.urlopen(url)
	if ret.getcode() != 200:
		raise Exception("Failed to load meta info for %s: %s" % (pageid, ret.read()))
	ret = json.loads(ret.read())
		
	try:
		get_page_stats(moc["facebookgraphid"], moc["id"], moc["name"].encode("utf8"), moc["state"], moc["district"], ret["category"] if "category" in ret else "")
	except Exception as e:
		print e, moc

