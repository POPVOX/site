from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.views.generic.simple import direct_to_template
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django import forms

from jquery.ajax import json_response, ajax_fieldupdate_request, sanitize_html

import re
from xml.dom import minidom
import urllib

from popvox.models import *
from popvox.views.bills import bill_statistics, get_default_statistics_context
import popvox.govtrack
from utils import formatDateTime

def get_legstaff_tracked_bills(user):
	# Sort by bill type (hr, s, hres, etc.) first so that we can SQL query over a larger
	# set of bill numbers.
	billgroups = { }
	billsource = { }
	
	for ix in user.userprofile.issues.all():
		for b in Bill.objects.filter(congressnumber=popvox.govtrack.CURRENT_CONGRESS, issues=ix):
			if not b.billtype in billgroups:
				billgroups[b.billtype] = []
			billgroups[b.billtype].append(b.billnumber)
			billsource[b.govtrack_code()] = "Issue area: " + ix.name
	
	# do this last so that it overrides the source
	if user.legstaffrole.member != None:
		spinfo = "Sponsored by " + popvox.govtrack.getMemberOfCongress(user.legstaffrole.member)["lastname"]
		for b in popvox.govtrack.getSponsoredBills(user.legstaffrole.member): # only this session
			if not b["billtype"] in billgroups:
				billgroups[b["billtype"]] = []
			billgroups[b["billtype"]].append(b["billnumber"])
			billsource[b["billtype"] + str(b["congressnumber"]) + "-" + str(b["billnumber"])] = spinfo
	
	bills = [ ]
	for bt in billgroups:
		for bill in Bill.objects.filter(congressnumber=popvox.govtrack.CURRENT_CONGRESS, billtype=bt, billnumber__in=billgroups[bt]):
			bills.append( { "bill": bill, "commentcount": len(bill.usercomments.all()), "source": billsource[bill.govtrack_code()] })
	bills.sort(key = lambda x : -x["commentcount"])
	return bills

def get_legstaff_district_bills(user):
	if user.legstaffrole.member == None:
		return []

	member = govtrack.getMemberOfCongress(user.legstaffrole.member)
	if not member["current"]:
		return []
	
	# Count up the number of comments on bills in this state or district.
	f = { "state": member["state"] }
	if member["type"] == "rep":
		f["congressionaldistrict"] = member["district"]
	bills = { }
	localaddresses = PostalAddress.objects.filter(**f)
	nationaladdresses = PostalAddress.objects.all() # we don't ever fetch the whole thing
	for addr in localaddresses:
		for c in addr.usercomment_set.all():
			if not c.bill.id in bills:
				bills[c.bill.id] = { "bill": c.bill, "count": 0 }
			bills[c.bill.id]["count"] += 1
	
	# Convert to array.	
	bills = bills.values()
	
	# We don't want just the most comments in the district, but the bills that are
	# most uniquely relevant to the district. So we subtract off the expected
	# number of comments in the district based on the rate of comments nationally.
	# This should be fairly robust.
	for d in bills:
		stats = bill_statistics(d["bill"], None, None)
		if stats != None:
			d["count"] = d["count"] \
				- len(localaddresses) * float(stats["total"]) / float(len(nationaladdresses))
	bills.sort(key = lambda x : -x["count"])
	
	for d in bills:
		d["stats"] = bill_statistics(d["bill"], None, None, address__state=f["state"], address__congressionaldistrict=f["congressionaldistrict"] if "congressionaldistrict" in f else None)
		
	return bills
	
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
				"tracked_bills": get_legstaff_tracked_bills(request.user),
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


