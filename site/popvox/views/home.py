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
from popvox.views.bills import bill_statistics
import popvox.govtrack

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
		d["count"] = d["count"] \
			- len(localaddresses) * float(bill_statistics(d["bill"], None, None)["total"]) / float(len(nationaladdresses))
	bills.sort(key = lambda x : -x["count"])
	
	for d in bills:
		d["stats"] = bill_statistics(d["bill"], None, None,  address__state=f["state"], address__congressionaldistrict=f["congressionaldistrict"] if "congressionaldistrict" in f else None)
		
	return bills

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
			{ 'user': request.user,
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

