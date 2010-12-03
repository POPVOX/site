from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.views.generic.simple import direct_to_template
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django import forms
from django.db.models import Count

from jquery.ajax import json_response, ajax_fieldupdate_request, sanitize_html

import re
from xml.dom import minidom
import urllib

from popvox.models import *
from popvox.views.bills import bill_statistics, get_default_statistics_context
import popvox.govtrack
from utils import formatDateTime

def annotate_track_status(profile, bills):
	tracked_bills = profile.tracked_bills.all()
	antitracked_bills = profile.antitracked_bills.all()
	for b in bills:
		if b in tracked_bills:
			b.trackstatus = True
		if b in antitracked_bills:
			b.antitrackstatus = True
	return bills

def get_legstaff_suggested_bills(user, counts_only=False):
	prof = user.userprofile
	
	suggestions = [  ]
	
	def select_bills(**kwargs):
		return Bill.objects.filter(
			congressnumber=popvox.govtrack.CURRENT_CONGRESS,
			**kwargs) \
			.exclude(antitrackedby=prof) \
			.order_by("billtype", "billnumber") \
			.select_related("sponsor", "topterm")
			
	boss = user.legstaffrole.member
	if boss != None:
		bossname = popvox.govtrack.getMemberOfCongress(boss)["name"]
	else:
		bossname = ""
	
	if boss != None:
		suggestions.append({
			"id": "sponsor",
			"type": "sponsor",
			"name": "Sponsored by " + bossname,
			"shortname": popvox.govtrack.getMemberOfCongress(boss)["lastname"],
			"bills": select_bills(sponsor = boss)
			})

	if user.legstaffrole.committee != None:
		cx = None
		try:
			cx = CongressionalCommittee.objects.get(code=user.legstaffrole.committee)
		except:
			pass
		if cx != None:
			name = popvox.govtrack.getCommittee(user.legstaffrole.committee)["name"]
			shortname = popvox.govtrack.getCommittee(user.legstaffrole.committee)["shortname"]

			suggestions.append({
				"id": "committeereferral",
				"type": "committeereferral",
				"name": "Referred to the " + name,
				"shortname": shortname + " (Referral)",
				"bills": select_bills(committees = cx)
				})

			suggestions.append({
				"id": "committeemember",
				"type": "committeemember",
				"name": "Introduced by a Member of the " + name,
				"shortname": shortname + " (Member)",
				"bills": select_bills(sponsor__in = govtrack.getCommittee(user.legstaffrole.committee)["members"])
				})

	for ix in prof.issues.all():
		suggestions.append({
			"id": "issue_" + str(ix.id),
			"type": "issue",
			"issue": ix,
			"name": "Issue Area: " + ix.name,
			"shortname": ix.name,
			"bills": select_bills(issues=ix)
			})
		
	if counts_only:
		return [
				{ "id": s["id"], "shortname": s["shortname"], "count": s["bills"].count() }
				for s in suggestions if s["bills"].count() > 0
			]

	# Clear out any groups with no bills. We can call .count() if we just want
	# a count, but since we are going to evaluate later it's better to evaluate
	# it once here so the result is cached.
	suggestions = [s for s in suggestions if len(s["bills"]) > 0]

	def concat(lists):
		ret = []
		for lst in lists:
			ret.extend(lst)
		return ret
	all_bills = concat([s["bills"] for s in suggestions])

	# Pre-fetch all of the committee assignments of all of the bills, in bulk.
	if len(suggestions) > 0:
		# Load the committee assignments and put into a hash.
		committee_assignments = { }
		for b in Bill.objects.raw("SELECT popvox_bill.id AS id, popvox_congressionalcommittee.id AS committee_id, popvox_congressionalcommittee.code AS committee_code FROM popvox_bill LEFT JOIN popvox_bill_committees ON popvox_bill.id=popvox_bill_committees.bill_id LEFT JOIN popvox_congressionalcommittee ON popvox_congressionalcommittee.id=popvox_bill_committees.congressionalcommittee_id WHERE popvox_bill.id IN (%s)" % ",".join([str(b.id) for b in all_bills])):
			if not b.id in committee_assignments:
				committee_assignments[b.id] = []
			if b.committee_code == None: # ??
				continue
			c = CongressionalCommittee()
			c.id = b.committee_id
			c.code = b.committee_code
			committee_assignments[b.id].append(c)
			
		# We can't replace the 'committees' field on each bill object with the list because
		# access to the field seems to be protected (i.e. setattr overridden??) so we set
		# a secondary field. In govtrack.py, we check for the presence of that field when
		# getting committee assignments.
		for b in all_bills:
			b.committees_cached = committee_assignments[b.id]
			
	# Preset the tracked and antitracked status.
	annotate_track_status(prof, all_bills)
	
	# Group any of the suggestion groups that have too many bills in them.
	# This is the only part of this routine that actually iterates through the
	# bills. We can report the categories and total counts of suggestions
	# without this.
	myissues = [ix.name for ix in prof.issues.all()]
	counter = 0
	for s in suggestions:
		s["count"] = s["bills"].count()
		
		if len(s["bills"]) <= 15:
			s["subgroups"] = [ {"bills": s["bills"], "id": counter } ]
			counter += 1
		else:
			ixd = { }
			for b in s["bills"]:
				if s["type"] != "sponsor" and b.sponsor_id != None and b.sponsor_id == boss:
					ix = "Sponsored by " + bossname
				elif (s["type"] != "issue" or s["issue"].parent != None) and b.topterm != None:
					ix = b.topterm.name
				else:
					ix = "Other"
				if not ix in ixd:
					ixd[ix] = { "name": ix, "bills": [], "id": counter }
					counter += 1
				ixd[ix]["bills"].append(b)
			s["subgroups"] = ixd.values()
			s["subgroups"].sort(key = lambda x : (x["name"] == "Other", x["name"] != "Sponsored by " + bossname, x["name"] not in myissues, x["name"]))
	
	return suggestions

def get_legstaff_district_bills(user):
	if user.legstaffrole.member == None:
		return []

	member = govtrack.getMemberOfCongress(user.legstaffrole.member)
	if not member["current"]:
		return []
	
	# Create some filters for the district.
	f1 = { "state": member["state"] }
	if member["type"] == "rep":
		f1["congressionaldistrict"] = member["district"]
	
	f2 = { }
	for k, v in f1.items():
		f2["usercomments__address__" + k] = v
		
	# Get the approximate total number of users in the district which
	# we will use to cut off aggregate results.
	localusers = PostalAddress.objects.filter(
		usercomment__updated__gt = datetime.now() - timedelta(days=365),
		**f1).count()
	
	# Get the approximate total number of users in the nation.
	globalusers = PostalAddress.objects.filter(usercomment__updated__gt = datetime.now() - timedelta(days=365)).count()
	
	# Now run an aggregate query to find the total number of comments
	# by bill w/in this district, reporting only bills that at least 1% of the
	# district has commented on.
	localbills = Bill.objects.filter(**f2) \
		.annotate(num_comments=Count("usercomments")) \
		.filter(num_comments__gt = localusers / 100) \
		.order_by("-num_comments")
	
	# Get the number of global comments on each of those bills.
	globalcomments = { }
	for bill in Bill.objects.filter(
		id__in = [b.id for b in localbills]) \
		.annotate(num_comments=Count("usercomments")):
		globalcomments[bill.id] =  bill.num_comments
	
	# Now filter out the local bills that have less activity than the national mean.
	localbills = [b for b in localbills if localusers/b.num_comments < globalusers/globalcomments[b.id]]
	
	return localbills
	
def compute_prompts(user):
	# Compute prompts for action for users. We want to remain agnostic about
	# what action the user should take, although we probably could predict it,
	# but we suspect users will find that inappropriate.
	
	# To compute the prompts we will look at the actions the user took, find
	# similar actions by other users and orgs, and then tally up the bills that
	# those other things had taken action on. The sugs array is a dict from
	# recommended bill ids to a dict from recommendation reasons to counts.
	
	sugs = { }
	bill_org = { }
	
	for c in user.comments.all():
		bills = []
		
		# Find all orgs that had the same position.
		for p in OrgCampaignPosition.objects.filter(bill=c.bill, position=c.position):
			efc = p.campaign.org.estimated_fan_count()
			
			# Now find all bills endorsed/opposed by that org, except for the original
			# bill since there's no need to recommend something the user already did.
			for q in OrgCampaignPosition.objects.filter(campaign__org=p.campaign.org).exclude(bill=c.bill).exclude(position="0"):
				bills.append(q.bill)
				
				# find the org with the largest user base that has a statement on this bill to
				# represent the bill. Give preference to any org that has written a short message
				# about the bill.
				orec = (q.campaign, efc, None if q.comment == None or q.comment.strip() == "" else q.comment, q.position)
				if not q.bill.id in bill_org or bill_org[q.bill.id][1] < orec[1] or (bill_org[q.bill.id][2] == None and orec[2] != None):
					bill_org[q.bill.id] = orec
				
		# Find all other users that had the same position.
		for d in UserComment.objects.filter(bill=c.bill, position=c.position).exclude(user=user):
			# Now find all of the other positions this other user took...
			for q in d.user.comments.all().exclude(bill=c.bill):
				bills.append(q.bill)
				
		for bill in bills:
			if not bill.id in sugs:
				billsug = { "bill": bill, "count": 0, "bill_sources": {} }
				sugs[bill.id] = billsug
				
				if not q.bill.isAlive():
					billsug["skip"] = True
					continue
				if user.comments.filter(bill=bill).exists():
					billsug["skip"] = True
					continue
			else:
				billsug = sugs[bill.id]
				if "skip" in billsug:
					continue
				
			billsug["count"] += 1
				
			if not c.bill.id in billsug["bill_sources"]:
				billsug["bill_sources"][c.bill.id] = { "bill": c.bill, "position": c.position, "count": 0 }
			billsug["bill_sources"][c.bill.id]["count"] += 1
	
	# Add the popular bills to the list of suggestions if they are not already
	# suggested.
	from bills import get_popular_bills
	for bill in get_popular_bills():
		if bill.id in sugs:
			continue
		if bill.id != None and user.comments.filter(bill=bill).exists():
			continue
		sugs[bill.govtrack_code()] = { "bill": bill, "count": -1, "bill_sources": {} } # -1 is a flag for the HTML and also to sort them below the other bills
	
	sugs = list(sugs.values())
	
	# sort suggestions by the number of users recommending the bill first,
	# and then by the total comments left on each bill
	
	sugs.sort(key = lambda x : (-x["count"], -x["bill"].usercomments.count()))
	
	sugs = sugs[0:10] # max number of suggestions to return
	
	for s in sugs:
		if s["bill"].id in bill_org:
			s["org_sources"] = [ { "campaign": bill_org[s["bill"].id][0], "comment": bill_org[s["bill"].id][2], "position": bill_org[s["bill"].id][3] } ]
		s["bill_sources"] = list(s["bill_sources"].values())
		s["bill_sources"].sort(key = lambda x : -x["count"])
		s["bill_sources"] = s["bill_sources"][0:1]
	
	return sugs

@login_required
def home(request):
	prof = request.user.get_profile()
	if prof == None:
		return Http404()
		
	if prof.is_leg_staff():
		member = None
		if request.user.legstaffrole.member != None:
			member = govtrack.getMemberOfCongress(request.user.legstaffrole.member)
		return render_to_response('popvox/home_legstaff.html',
			{
				"districtstr":
						"" if member == None or not member["current"] else (
							"State" if member["type"] == "sen" else "District"
							),
				"tracked_bills": annotate_track_status(prof, prof.tracked_bills.all()),
				"antitracked_bills": annotate_track_status(prof, prof.antitracked_bills.all()),
				"suggestions": get_legstaff_suggested_bills(request.user),
				"district_bills": get_legstaff_district_bills(request.user)
			},
			context_instance=RequestContext(request))
		
	elif prof.is_org_admin():
		# Get a list of all campaigns in all orgs that the user is an admin
		# of, where the campaign has at least one bill position. Also get
		# a list of all issue areas relevant to the user and all bills.
		cams = []
		bills = []
		issues = []
		for role in prof.user.orgroles.all():
			for ix in role.org.issues.all():
				if not ix in issues:
					issues.append(ix)
			for cam in role.org.orgcampaign_set.all():
				for p in cam.positions.all():
					bills.append(p.bill)
					if not cam in cams:
						cams.append(cam)
		
		feed = ["bill:"+b.govtrack_code() for b in bills] + ["crs:"+ix.name for ix in issues]
		
		return render_to_response('popvox/home_orgadmin.html',
			{
			   'cams': cams,
			   'feed': govtrack.loadfeed(feed) },
			context_instance=RequestContext(request))
	else:
		return render_to_response('popvox/homefeed.html',
			{ 
			"suggestions": compute_prompts(request.user)[0:4]
			    },
			context_instance=RequestContext(request))

@login_required
@json_response
def legstaff_bill_categories(request):
	prof = request.user.get_profile()
	if prof == None or not prof.is_leg_staff():
		return Http404()
	return {
		"status": "success",
		"tabs": get_legstaff_suggested_bills(request.user, counts_only=True)
		}

@login_required
def home_suggestions(request):
	prof = request.user.get_profile()
	if prof == None:
		return Http404()
		
	if prof.is_leg_staff() or prof.is_org_admin():
		return HttpResponseRedirect("/home")

	return render_to_response('popvox/home_suggestions.html',
		{ 
		"suggestions": compute_prompts(request.user)
		    },
		context_instance=RequestContext(request))

@login_required
def reports(request):
	if request.user.userprofile.is_leg_staff():
		return render_to_response('popvox/reports_legstaff.html',
			context_instance=RequestContext(request))
	elif request.user.userprofile.is_org_admin():
		return render_to_response('popvox/reports_orgstaff.html',
			context_instance=RequestContext(request))
	else:
		raise Http404()

def activity(request):
	default_state, default_district = get_default_statistics_context(request.user)
	
	import phone_number_twilio
	pntv = phone_number_twilio.models.PhoneNumber.objects.filter(verified=True).count()
		
	return render_to_response('popvox/activity.html', {
			"default_state": default_state if default_state != None else "",
			"default_district": default_district if default_district != None else "",
			"stateabbrs": 
				[ (abbr, govtrack.statenames[abbr], govtrack.stateapportionment[abbr]) for abbr in govtrack.stateabbrs],
			"count_users": User.objects.all().count(),
			"count_users_verified": pntv,
			"count_comments": UserComment.objects.all().count(),
			"count_orgs": Org.objects.filter(createdbyus=False).count(),
		}, context_instance=RequestContext(request))
	
def activity_getinfo(request):
	state = request.REQUEST["state"] if "state" in request.REQUEST and request.REQUEST["state"].strip() != "" else None
	
	district = int(request.REQUEST["district"]) if state != None and "district" in request.REQUEST and request.REQUEST["district"].strip() != "" else None
	
	if "default_district" in request.POST:
		state, district = get_default_statistics_context(request.user)
	
	filters = { }
	if state != None:
		filters["address__state"] = state
		if district != None:
			filters["address__congressionaldistrict"] = district
	
	items = []
	items.extend( UserComment.objects.filter(**filters).order_by('-updated')[0:30] )
	
	if state == None and district == None:
		items.extend( Org.objects.filter(visible=True).order_by('-updated')[0:30] )
		items.extend( OrgCampaign.objects.filter(visible=True,default=False, org__visible=True).order_by('-updated')[0:30] )
		items.extend( OrgCampaignPosition.objects.filter(campaign__visible=True, campaign__org__visible=True).order_by('-updated')[0:30] )
		
		items.sort(key = lambda x : x.updated, reverse=True)
		items = items[0:30]

	return render_to_response('popvox/activity_items.html', { "items": items })


