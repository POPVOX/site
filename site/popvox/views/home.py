from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.views.generic.simple import direct_to_template
from django.contrib.auth.decorators import login_required, user_passes_test
from django import forms
from django.db import transaction
from django.db.models import Count
from django.db.models.query import QuerySet
from django.views.decorators.csrf import csrf_protect, csrf_exempt

from jquery.ajax import json_response, ajax_fieldupdate_request, sanitize_html

import re
from xml.dom import minidom
from itertools import chain, izip, cycle

from popvox.models import *
from popvox.views.bills import bill_statistics, get_default_statistics_context
import popvox.govtrack

from settings import MIXPANEL_API_KEY

import csv
import urllib
from xml.dom.minidom import parse, parseString

def annotate_track_status(profile, bills):
	tracked_bills = profile.tracked_bills.all()
	antitracked_bills = profile.antitracked_bills.all()
	for b in bills:
		if b in tracked_bills:
			b.trackstatus = True
		if b in antitracked_bills:
			b.antitrackstatus = True
	return bills

def get_legstaff_suggested_bills(user, counts_only=False, id=None, include_extras=True):
	prof = user.userprofile
	
	suggestions = [  ]
	
	#from settings import DEBUG
	#if DEBUG:
	#	from django.db import connection, transaction
	#	connection.cursor().execute("RESET QUERY CACHE;")
	
	def select_bills(**kwargs):
		return Bill.objects.filter(
			congressnumber=popvox.govtrack.CURRENT_CONGRESS,
			vehicle_for=None,
			**kwargs) \
			.exclude(antitrackedby=prof) \
			.order_by()
			
	boss = user.legstaffrole.member
	if boss != None:
		bossname = boss.name()
	else:
		bossname = ""
	
	suggestions.append({
		"id": "tracked",
		"type": "tracked",
		"name": "Bookmarked Legislation",
		"shortname": "Bookmarked",
		"bills": prof.tracked_bills.all()
		})
	
	if boss != None:
		moc = popvox.govtrack.getMemberOfCongress(boss.id)
		suggestions.append({
			"id": "sponsor",
			"type": "sponsor",
			"name": "Sponsored by " + bossname,
			"shortname": boss.lastname(),
			"bills": select_bills(sponsor = boss)
			})
		
		if "committees" in moc and user.legstaffrole.committee == None:
			for cid in sorted(moc["committees"]):
				try:
					cx = CongressionalCommittee.objects.get(code=cid)
				except:
					continue
				name = cx.name()
				shortname = cx.abbrevname()
				committeename = cx.shortname()
				suggestions.append({
					"id": "committee_" + cid,
					"type": "committeereferral",
					"name": "Referred to the " + name,
					"shortname": shortname + " (Referral)",
					"bills": select_bills(committees = cx)
					})
				

	localbills = get_legstaff_district_bills(user)
	if localbills != None and len(localbills) > 0:
		d = moc["state"] + ("" if moc["type"] == "sen" else "-" + str(moc["district"]))
		suggestions.append({
			"id": "local",
			"type": "local",
			"name": "Hot Bills In Your " + ("State" if moc["type"] == "sen" else "District") + ": " + d,
			"shortname": "Hot in " + d,
			"bills": localbills
			})
		
	committeename = ""
	if user.legstaffrole.committee != None:
		cx = user.legstaffrole.committee
		name = cx.name()
		shortname = cx.abbrevname()
		committeename = cx.shortname()

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
			"bills": select_bills(sponsor__in = govtrack.getCommittee(user.legstaffrole.committee.code)["members"])
			})
		
	

	for ix in prof.issues.all():
		suggestions.append({
			"id": "issue_" + str(ix.id),
			"type": "issue",
			"issue": ix,
			"name": "Issue Area: " + ix.name,
			"shortname": ix.shortname if ix.shortname != None else ix.name,
			"bills": select_bills(issues__id__in=[ix.id] + list(ix.subissues.all().values_list('id', flat=True))) # the disjunction was slow: select_bills(issues=ix) | select_bills(issues__parent=ix)
			})

	if include_extras:
		#suggestions.append({
		#	"id": "allbills",
		#	"type": "allbills",
		#	"name": "All Bills",
		#	"shortname": "All",
		#	"bills": select_bills()
		#	})
		
		suggestions.append({
			"id": "hidden",
			"type": "hidden",
			"name": "Legislation You Have Hidden",
			"shortname": "Hidden",
			"bills": prof.antitracked_bills.all()
			})

	# If id != None, then we're requesting just one group. We can do this now
	# since the queries are lazy-loaded.
	if id != None:
		suggestions = [s for s in suggestions if s["id"] == id]

	# If the user wants to filter out only bills relevant to a particular chamber, then
	# we have to filter by status. Note that PROV_KILL:PINGPONGFAIL is included in
	# both H and S bills because we don't know what chamber is next.
	chamber_of_next_vote = prof.getopt("home_legstaff_filter_nextvote", None)
	ext_filter = None
	if chamber_of_next_vote == "h":
		ext_filter = lambda q : \
			q.filter(billtype__in = ('h', 'hr', 'hc', 'hj'), current_status__in = ("INTRODUCED", "REFERRED", "REPORTED", "PROV_KILL:VETO")) |\
			q.filter(current_status__in = ("PASS_OVER:SENATE", "PASS_BACK:SENATE", "OVERRIDE_PASS_OVER:SENATE", "PROV_KILL:SUSPENSIONFAILED", "PROV_KILL:PINGPONGFAIL"))
	elif chamber_of_next_vote == "s":
		ext_filter = lambda q : \
			q.filter(billtype__in = ('s', 'sr', 'sc', 'sj'), current_status__in = ("INTRODUCED", "REFERRED", "REPORTED", "PROV_KILL:VETO")) |\
			q.filter(current_status__in = ("PASS_OVER:HOUSE", "PASS_BACK:HOUSE", "OVERRIDE_PASS_OVER:HOUSE", "PROV_KILL:CLOTUREFAILED", "PROV_KILL:PINGPONGFAIL"))
	if ext_filter != None:
		for s in suggestions:
			if s["type"] not in ("tracked", "sponsor") and isinstance(s["bills"], QuerySet):
				try:
					s["bills"] = ext_filter(s["bills"])
				except: # can't filter hot-in-your-district because it's got a slice
					pass
		
	if counts_only:
		def count(x):
			if isinstance(x, QuerySet):
				return x.count()
			else:
				return len(x)
		for s in suggestions:
			s["count"] = count(s["bills"])
		return [{"id": s["id"], "type": s["type"], "shortname": s["shortname"], "count": s["count"] } for s in suggestions if s["count"] > 0 or s["id"] == "tracked"]

	# Clear out any groups with no bills. We can call .count() if we just want
	# a count, but since we are going to evaluate later it's better to evaluate
	# it once here so the result is cached.
	suggestions = [s for s in suggestions if len(s["bills"]) > 0 or s["id"] == "tracked"]

	def concat(lists):
		ret = []
		for lst in lists:
			ret.extend(lst)
		return ret
	all_bills = concat([s["bills"] for s in suggestions])

	# Pre-fetch all of the committee assignments of all of the bills, in bulk.
	if len(all_bills) > 0:
		# Load the committee assignments and put into a hash.
		committee_assignments = { }
		for b in Bill.objects.raw("SELECT popvox_bill.id AS id, popvox_congressionalcommittee.id AS committee_id, popvox_congressionalcommittee.code AS committee_code FROM popvox_bill LEFT JOIN popvox_bill_committees ON popvox_bill.id=popvox_bill_committees.bill_id LEFT JOIN popvox_congressionalcommittee ON popvox_congressionalcommittee.id=popvox_bill_committees.congressionalcommittee_id WHERE popvox_bill.id IN (%s)" % ",".join([str(b.id) for b in all_bills])):
			if not b.id in committee_assignments:
				committee_assignments[b.id] = []
			if b.committee_code in (None, ""): # ??
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
			
		# Pre-create MemberOfCongress objects because they don't have any info...
		for b in all_bills:
			b.sponsor = MemberOfCongress(id=b.sponsor_id)
			
	# Preset the tracked and antitracked status.
	annotate_track_status(prof, all_bills)
	
	# Pre-fetch all of the top terms for categorization.
	top_terms = {}
	for ix in IssueArea.objects.filter(parent__isnull=True):
		top_terms[ix.id] = ix
	
	# Group any of the suggestion groups that have too many bills in them.
	# This is the only part of this routine that actually iterates through the
	# bills. We can report the categories and total counts of suggestions
	# without this.
	myissues = [ix.name for ix in prof.issues.all()]
	counter = 0
	for s in suggestions:
		s["count"] = len(s["bills"])
		
		if s["count"] <= 15:
			s["subgroups"] = [ {"bills": s["bills"], "id": counter } ]
			counter += 1
		else:
			ixd = { }
			for b in s["bills"]:
				if b.congressnumber != popvox.govtrack.CURRENT_CONGRESS:
					ix = str(b.congressnumber) + popvox.govtrack.ordinate(b.congressnumber) +  " Congress"
				elif s["type"] != "sponsor" and boss != None and b.sponsor_id != None and b.sponsor_id == boss.id:
					ix = "Sponsored by " + bossname
				elif (s["type"] != "issue" or s["issue"].parent != None) and b.topterm_id != None:
					ix = top_terms[b.topterm_id].name
				elif s["type"] != "committeereferral" and len(b.committees_cached) > 0 and b.committees_cached[0].shortname() != "":
					ix = b.committees_cached[0].shortname()
				else:
					ix = "Other"
				if not ix in ixd:
					ixd[ix] = { "name": ix, "bills": [], "id": counter }
					counter += 1
				ixd[ix]["bills"].append(b)
			s["subgroups"] = ixd.values()
			s["subgroups"].sort(key = lambda x : (
				x["name"] == "Other",
				x["name"] != "Sponsored by " + bossname,
				x["name"] != committeename,
				x["name"] not in myissues,
				x["name"]))
			
		for g in s["subgroups"]:
			g["bills"] = list(g["bills"])
			g["bills"].sort(key = lambda b : b.current_status_date, reverse = True)
	
	return suggestions

def get_legstaff_district_bills(user):
	if user.legstaffrole.member == None:
		return []

	member = govtrack.getMemberOfCongress(user.legstaffrole.member_id)
	if not member["current"]:
		return []
	
	# Create some filters for the district.
	f1 = { "usercomments__state": member["state"] }
	cache_key = "get_legstaff_district_bills#" + member["state"]
	if member["type"] == "rep":
		cache_key += "," + str(member["district"])
		f1["usercomments__congressionaldistrict"] = member["district"]
	
	localbills = cache.get(cache_key)
	if localbills != None:
		return localbills
	
	# Now run an aggregate query to find the total number of comments
	# by bill w/in this district.
	localbills = Bill.objects.filter(**f1) \
		.annotate(num_comments=Count("usercomments")) \
		.filter(num_comments__gt = 2) \
		.order_by("-num_comments") \
		[0:15]
	
	cache.set(cache_key, localbills, 60*60*6) # six hours
	
	return localbills
	
def compute_prompts(user):
	# Compute prompts for action for users by looking at the bills he has commented
	# on, plus trending bills (with a weight).
	
		
	# For each source bill, find similar target bills. Remember the similarity
	# and source for each target.
	targets = {}
	max_sim = 0
	for c in user.comments.all().select_related("bill"):
		source_bill = c.bill
		for target_bill, similarity in chain(( (s.bill2, s.similarity) for s in source_bill.similar_bills_one.all().select_related("bill2")), ( (s.bill1, s.similarity) for s in source_bill.similar_bills_two.all().select_related("bill1"))):
			if not target_bill.isAlive():
				continue
			if not target_bill in targets: targets[target_bill] = []
			targets[target_bill].append( (source_bill, similarity) )
			max_sim = max(similarity, max_sim)
	
	from bills import get_popular_bills
	for bill in get_popular_bills():
		if bill.isAlive() and bill not in targets:
			targets[bill] = [(None, max_sim/10.0)]
	
	# Put the targets in descending weighted similarity order.
	targets = list(targets.items()) # (target_bill, [list of (source,similarity) pairs]), where source can be null if it is coming from the tending bills list
	targets.sort(key = lambda x : -sum([y[1] for y in x[1]]))
	
	# Remove the recommendations that the user has anti-tracked or commented on.
	hidden_bills = set(user.userprofile.antitracked_bills.all()) | set(Bill.objects.filter(usercomments__user=user))
	targets = filter(lambda x : not x[0] in hidden_bills, targets)
	
	# Take the top reccomendations.
	targets = targets[:15]
	
	# Replace the list of target sources with just the highest-weighted source for each target.
	for i in xrange(len(targets)):
		targets[i][1].sort(key = lambda x : -x[1])
		targets[i] = { "bill": targets[i][0], "source": targets[i][1][0][0] }
	
	# targets is now a list of (target, source) pairs.
	
	return targets

@csrf_protect
@login_required
def home(request):
	user = request.user
	prof = user.get_profile()
	if prof == None:
		raise Http404()
		
	if prof.is_leg_staff():
		msgs = get_legstaff_undelivered_messages(user)
		if msgs != None: msgs = msgs.count()
		
		return render_to_response('popvox/home_legstaff_dashboard.html',
			{
				"docket": get_legstaff_suggested_bills(request.user, counts_only=True, include_extras=False),
				"calendar": get_calendar_agenda(user),
				"message_count": msgs,
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
		
		return render_to_response('popvox/home_orgadmin.html',
			{
			   'cams': cams,
			   "tracked_bills": annotate_track_status(prof, prof.tracked_bills.all()),
			   "adserver_targets": ["org_admin_home"],
			   },
			context_instance=RequestContext(request))
	else:
		return render_to_response('popvox/homefeed.html',
			{ 
			"suggestions": compute_prompts(user)[0:4],
			"tracked_bills": annotate_track_status(prof, prof.tracked_bills.all()),
		     "adserver_targets": ["user_home"],
			    },
			context_instance=RequestContext(request))

@csrf_protect
@login_required
def docket(request):
	prof = request.user.get_profile()
	if prof == None:
		raise Http404()
		
	if not prof.is_leg_staff():
		raise Http404()

	member = None
	if request.user.legstaffrole.member != None:
		member = govtrack.getMemberOfCongress(request.user.legstaffrole.member_id)
	return render_to_response('popvox/home_legstaff.html',
		{
			"districtstr":
					"" if member == None or not member["current"] else (
						"State" if member["type"] == "sen" else "District"
						),
			"suggestions": get_legstaff_suggested_bills(request.user, counts_only=True),
			"filternextvotechamber": prof.getopt("home_legstaff_filter_nextvote", ""),
			"adserver_targets": ["leg_staff_home"],
		},
		context_instance=RequestContext(request))

@login_required
@json_response
def legstaff_bill_categories(request):
	prof = request.user.get_profile()
	if prof == None or not prof.is_leg_staff():
		raise Http404()
		
	if "filternextvotechamber" in request.POST and request.POST["filternextvotechamber"] in ("", "h", "s"):
		val = request.POST["filternextvotechamber"]
		if val == "":
			val = None
		request.user.userprofile.setopt("home_legstaff_filter_nextvote", val)
		
	return {
		"status": "success",
		"tabs": get_legstaff_suggested_bills(request.user, counts_only=True)
		}
		
@login_required
def legstaff_bill_category_panel(request):
	return render_to_response('popvox/home_legstaff_panel.html',
		{
			"group": get_legstaff_suggested_bills(request.user, id=request.POST["id"])[0],
		},
		context_instance=RequestContext(request))
	
@csrf_protect
@login_required
def home_suggestions(request):
	prof = request.user.get_profile()
	if prof == None:
		raise Http404()
		
	if prof.is_leg_staff() or prof.is_org_admin():
		return HttpResponseRedirect("/home")

	return render_to_response('popvox/home_suggestions.html',
		{ 
		"suggestions": compute_prompts(request.user)
		    },
		context_instance=RequestContext(request))

def activity(request):
	default_state, default_district = get_default_statistics_context(request.user)
	
	msgs = None
	if request.user.is_authenticated() and request.user.userprofile.is_leg_staff():
		msgs = get_legstaff_undelivered_messages(request.user)
		if msgs != None: msgs = msgs.count()
		
	return render_to_response('popvox/activity.html', {
			"default_state": default_state if default_state != None else "",
			"default_district": default_district if default_district != None else "",
			
			"stateabbrs": 
				[ (abbr, govtrack.statenames[abbr]) for abbr in govtrack.stateabbrs],
			"statereps": govtrack.getStateReps(),
			
			# for leg staff only...
			"message_count": msgs,
		}, context_instance=RequestContext(request))

def activity_getinfo(request):
	format = ""
	
	state = request.REQUEST["state"] if "state" in request.REQUEST and request.REQUEST["state"].strip() != "" else None
	
	district = int(request.REQUEST["district"]) if state != None and "district" in request.REQUEST and request.REQUEST["district"].strip() != "" else None

	if "default-locale" in request.REQUEST:
		def_state, def_district = get_default_statistics_context(request.user)
		state, district = def_state, def_district

	can_see_user_details = False
	if request.user.is_authenticated() and request.user.userprofile.is_leg_staff():
		if request.user.legstaffrole.member != None:
			member = govtrack.getMemberOfCongress(request.user.legstaffrole.member_id)
			if member != None and member["current"]:
				if state == member["state"] and (member["type"] == "sen" or district == member["district"]):
					can_see_user_details = True
	
	count = 80
	if "count" in request.REQUEST:
		count = int(request.REQUEST["count"])
	
	items = []
	total_count = None
	bill = None

	if request.REQUEST.get("comments", "true") != "false":
		filters = { }
		if state != None:
			filters["state"] = state
			if district != None:
				filters["congressionaldistrict"] = district
		
		if "bill" in request.REQUEST:
			bill = Bill.objects.get(id = request.REQUEST["bill"])
			filters["bill"] = bill
			format = "_bill"
		
		q = UserComment.objects.filter(
			message__isnull=False, 
			status__in=(UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED),
			**filters) \
			.select_related("user", "bill", "address") \
			.order_by('-created')

		if format == "_bill":
			total_count = q.count()
	
		q = q[0:count]

		# batch load all of the appreciations
		c_id = {}
		for c in q:
			c_id[c.id] = c
			c.appreciates = 0 # in case comment has none, see next comment
		for c in UserComment.objects.filter(
			id__in=c_id.keys(), # putting a filter on diggs eliminates comments without any diggs
			diggs__diggtype=UserCommentDigg.DIGG_TYPE_APPRECIATE) \
			.annotate(appreciates=Count('diggs')):
			c_id[c.id].appreciates = c.appreciates
		
		items.extend(q)
	
	if state == None and district == None and format != "_bill":
		items.extend( Org.objects.filter(visible=True, createdbyus=False).exclude(slug="demo").order_by('-updated')[0:count] )
		items.extend( OrgCampaign.objects.filter(visible=True, default=False, org__visible=True, org__createdbyus=False).exclude(org__slug="demo").order_by('-updated')[0:count] )
		items.extend( OrgCampaignPosition.objects.filter(campaign__visible=True, campaign__org__visible=True, campaign__org__createdbyus=False).exclude(campaign__org__slug="demo").order_by('-updated')[0:count] )
		items.extend( PositionDocument.objects.filter(owner_org__visible=True, owner_org__createdbyus=False).exclude(owner_org__slug="demo").order_by('-updated')[0:count] )
		
		items.sort(key = lambda x : x.updated, reverse=True)
		items = items[0:count]
		
	if request.user.is_authenticated():
		annotate_track_status(request.user.userprofile,
			[item.bill for item in items if type(item)==UserComment])
		
	from popvox.views.bills import can_appreciate 
	for item in items:
		if isinstance(item, UserComment):
			item.can_appreciate = can_appreciate(request, item.bill)

	return render_to_response('popvox/activity_items' + format + '.html', {
		"items": items,
		"can_see_user_details": can_see_user_details,
		"bill": bill,
		"total_count": total_count,
		}, context_instance=RequestContext(request))

def calendar(request):
	return render_to_response('popvox/legcalendar.html', {
		}, context_instance=RequestContext(request))

def get_calendar_agenda(user):
	chamber = user.legstaffrole.chamber()
	if chamber in ("H", "S"):
		agenda = get_calendar_agenda2(chamber)
	else:
		agenda = get_calendar_agenda2("H", prefix="House")
		agenda = get_calendar_agenda2("S", agenda=agenda, prefix="Senate")

	agenda = [(date, date.strftime("%A"), date.strftime("%b %d").replace(" 0", " "), items) for date, items in agenda.items()]
	agenda.sort(key = lambda x : x[0])
	
	return agenda

def get_calendar_agenda2(chamber, agenda=None, prefix=None):
	if chamber == "H":
		url = "http://www.google.com/calendar/ical/g.popvox.com_a29i4neivhp0ocsrkcd6jf2n30%40group.calendar.google.com/public/basic.ics"
	elif chamber == "S":
		url = "http://www.google.com/calendar/ical/g.popvox.com_dn12o3dcj27brhi8hk4v1ov09o%40group.calendar.google.com/public/basic.ics"
			
	cal = cache.get(url)
	if cal == None:
		import urllib2
		cal = urllib2.urlopen(url).read()
		cache.set(url, cal, 60*60*3) # 3 hours

	from datetime import datetime, date, timedelta
	
	# weird data bug from Google?
	cal = cal.replace("CREATED:00001231T000000Z\r\n", "")
	
	from icalendar import Calendar, Event
	cal = Calendar.from_string(cal)
	
	if agenda == None:
		agenda = { }
	
	for component in cal.walk():
		if "summary" in component:
			descr = component["summary"]
		elif "description" in component:
			descr = component["description"]
		else:
			continue
		if not "dtstart" in component or not "dtend" in component:
			continue
		dstart = component.decoded("dtstart")
		dend = component.decoded("dtend")
		
		if prefix != None:
			descr = prefix + ": " + descr
		
		# We're not interested in times right now...
		
		if isinstance(dstart, datetime): dstart = dstart.date()
		if isinstance(dend, datetime): dend = dend.date()
		
		if dend < datetime.now().date():
			continue
		
		while dstart < dend: # end date is exclusive
			if dstart >= datetime.now().date() and dstart <= datetime.now().date()+timedelta(days=5):
				if dstart not in agenda:
					agenda[dstart] = []
				agenda[dstart].append({"description": descr})
			dstart = dstart + timedelta(days=1)
		
	return agenda

@user_passes_test(lambda u : u.is_authenticated() and (u.is_staff | u.is_superuser))
def waiting_for_reintroduction(request):
	bills = { }
	
	# Quickly find non-staff users tracking any bill introduced in a previous congress.
	for user in UserProfile.objects.filter(allow_mass_mails=True, tracked_bills__congressnumber__lt = popvox.govtrack.CURRENT_CONGRESS, user__orgroles__isnull = True, user__legstaffrole__isnull = True).distinct(): # weird that we need a distinct here
		for bill in user.tracked_bills.filter(congressnumber__lt = popvox.govtrack.CURRENT_CONGRESS).distinct():
			if not bill in bills:
				bills[bill] = []
			bills[bill].append(user)
	
	bills = list(bills.items())
	bills.sort(key = lambda kv : len(kv[1]), reverse = True)
	
	return render_to_response('popvox/waiting_for_reintroduction.html', {
		"bills": bills,
		}, context_instance=RequestContext(request))
	
@user_passes_test(lambda u : u.is_authenticated() and (u.is_staff | u.is_superuser))
def delivery_status_report(request):
	from writeyourrep.models import Endpoint, DeliveryRecord
	report = []
	totals = [0, 0, 0]
	for moc in sorted(popvox.govtrack.getMembersOfCongress(), key = lambda m : m["type"] == "rep"):
		moc = dict(moc) # clone
		report.append(moc)
		
		try:
			ep = Endpoint.objects.get(govtrackid=moc["id"], office=moc["office_id"])
		except Endpoint.DoesNotExist:
			moc["delivery_status"] = "No Endpoint Defined"
			continue
			
		moc["endpoint"] = ep.id
			
		d = DeliveryRecord.objects.filter(target=ep, next_attempt__isnull=True)
		d_delivered = d.filter(success=True)
		d_delivered_electronically = d_delivered.exclude(method=Endpoint.METHOD_INPERSON)
			
		d = d.count()
		if d == 0:
			moc["delivery_status"] = "No messages/No method?"
		else:
			d_delivered = d_delivered.count()
			d_delivered_electronically = d_delivered_electronically.count()
			
			ratio = float(d_delivered_electronically) / float(d)
			ratio = int(100.0*(1.0-ratio))
			
			if ratio <= 1:
				moc["delivery_status"] = "OK!"
			elif ratio < 5:
				moc["delivery_status"] = "OK! (Mostly)"
			else:
				moc["delivery_status"] = "%s%% fail" % ratio
	
			moc["breaks"]  = " %d electronically/%d delivered/%d written" % (d_delivered_electronically, d_delivered, d)
		
			totals[0] += d_delivered_electronically
			totals[1] += d_delivered
			totals[2] += d

		if ep.method == Endpoint.METHOD_NONE and ep.tested:
			moc["delivery_status"] = "No Electronic Method"
			
	return render_to_response('popvox/delivery_status_report.html', {
		"report": report,
		"delivered_pct": int(float(totals[1])/float(totals[2])*100.0),
		"delivered_electronically_pct": int(float(totals[0])/float(totals[1])*100.0),
		"total_count": totals[2],
		}, context_instance=RequestContext(request))
	
def get_legstaff_undelivered_messages(user):
	# Return None if the account does not have access to download messages.
	# Otherwise return a QuerySet of the messages in this person's office's
	# district that have not been successfully delivered to the office (and are
	# not in an offline batch).
	
	return None # TOO DAMN SLOW
		
	role = user.legstaffrole
	if not role.verified or role.member == None:
		return None

	member = role.member.info()
	if not member["current"]:
		return None
	
	filters = { }	
	filters["state"] = member["state"]
	if member["type"] == "rep":
		filters["congressionaldistrict"] = member["district"]
		
	# Return undelivered messages that are also not queued for off-line delivery.
	return UserComment.objects.filter(
			created__gt = datetime.now() - timedelta(days=60),
			**filters
		).exclude(
			delivery_attempts__success=True,
			delivery_attempts__target__govtrackid=role.member.id,
		).exclude(
			usercommentofflinedeliveryrecord__target=role.member,
			usercommentofflinedeliveryrecord__batch__isnull=False
		)
		
@csrf_protect
@user_passes_test(lambda u : u.is_authenticated() and u.userprofile.is_leg_staff())
def legstaff_download_messages(request):
	msgs = get_legstaff_undelivered_messages(request.user)
	if msgs == None: # no access to messages
		return render_to_response('popvox/legstaff_download_messages.html', {
			"access": "denied",
			}, context_instance=RequestContext(request))
		
	from writeyourrep.models import Endpoint, DeliveryRecord
	from datetime import datetime

	member_id = request.user.legstaffrole.member.id
	office_id = govtrack.getMemberOfCongress(member_id)["office_id"]
	
	date_format = "%Y-%m-%d %H:%M:%S.%f"
	
	if request.POST.get("clear", "") == "Return to Queue":
		# On the previous attempt record, reset the next attempt field.
		DeliveryRecord.objects.filter(
				next_attempt__success=True,
				next_attempt__target__govtrackid=member_id,
				next_attempt__target__office=office_id,
				next_attempt__method=Endpoint.METHOD_STAFFDOWNLOAD,
				next_attempt__created = request.POST["date"]
				).update(next_attempt=None)
		
		# And delete the actual download record.
		DeliveryRecord.objects.filter(
				success=True,
				target__govtrackid=member_id,
				target__office=office_id,
				method=Endpoint.METHOD_STAFFDOWNLOAD,
				created = request.POST["date"]
				).delete()
	
	elif "date" in request.POST:
		if request.POST["date"] == "new":
			# we already queried above
			is_new = True
			download_date = datetime.now()
		else:
			msgs = UserComment.objects.filter(
				delivery_attempts__success=True,
				delivery_attempts__target__govtrackid=member_id,
				delivery_attempts__target__office=office_id,
				delivery_attempts__method=Endpoint.METHOD_STAFFDOWNLOAD,
				delivery_attempts__created = request.POST["date"]
				).select_related("address")
			is_new = False
			download_date = datetime.strptime(request.POST["date"], date_format)
			
		msgs = msgs.order_by('created')
			
		import csv
		from django.http import HttpResponse
		
		response = HttpResponse(mimetype='text/csv')
		response['Content-Disposition'] = 'attachment; filename=constituent_messages_' + download_date.strftime("%Y-%m-%d_%H%M").strip() + '.csv'
	
		writer = csv.writer(response)
		writer.writerow(['pvcid', 'date', 'subject', 'topic_code', 'prefix', 'firstname', 'lastname', 'suffix', 'address1', 'address2', 'city', 'state', 'zipcode', 'phonenumber', 'district', 'email', 'message', 'referrer'])
		for comment in msgs:
			
			topic_code = "http://popvox.com" + comment.bill.url() + "#" + ("support" if comment.position == "+" else "oppose")
			campaign_id = ""
			
			# take the first referrer
			comment.referrer = None
			for ref in comment.referrers():
				comment.referrer = ref
				break
			if comment.referrer != None and isinstance(comment.referrer, Org):
				if comment.referrer.website == None:
					campaign_id = "http://popvox.com" + comment.referrer.url()
				else:
					campaign_id = comment.referrer.website
			elif comment.referrer != None and isinstance(comment.referrer, OrgCampaign):
				if comment.referrer.website_or_orgsite() == None:
					campaign_id = "http://popvox.com" + comment.referrer.url()
				else:
					campaign_id = comment.referrer.website_or_orgsite()
			
			writer.writerow([
				comment.id,
				comment.updated,
				comment.bill.hashtag() + " " + ("support" if comment.position=="+" else "oppose"),
				topic_code,
				
				comment.address.nameprefix.encode("utf8"),
				comment.address.firstname.encode("utf8"),
				comment.address.lastname.encode("utf8"),
				comment.address.namesuffix.encode("utf8"),
				comment.address.address1.encode("utf8"),
				comment.address.address2.encode("utf8"),
				comment.address.city.encode("utf8"),
				comment.address.state.encode("utf8"),
				comment.address.zipcode.encode("utf8"),
				comment.address.phonenumber.encode("utf8"),
				comment.address.congressionaldistrict,

				comment.user.email.encode("utf8"),
				comment.message.encode("utf8") if comment.message != None else "(This user chose not to write a personal message.)",
				campaign_id,
				])

			if is_new:
				dr = DeliveryRecord()
				dr.target = Endpoint.objects.get(govtrackid=member_id, office=office_id)
				dr.trace = """comment #%d delivered via staff download by %s
				
email: %s
IP: %s
UA: %s
""" % (comment.id, request.user.username, request.user.email, request.META.get("REMOTE_ADDR", ""), request.META.get("HTTP_USER_AGENT", ""))
				
				
				dr.success = True
				dr.failure_reason = DeliveryRecord.FAILURE_NO_FAILURE
				dr.method = Endpoint.METHOD_STAFFDOWNLOAD
				dr.save()

				# explicitly set all of the records to the same date to group the batch
				dr.created = download_date
				dr.save()

				try:
					prev_dr = comment.delivery_attempts.get(target__govtrackid = member_id, next_attempt__isnull = True)
					prev_dr.next_attempt = dr
					prev_dr.save()
				except DeliveryRecord.DoesNotExist:
					pass
				
				comment.delivery_attempts.add(dr)

		return response
	
	delivered_message_dates = DeliveryRecord.objects.filter(
				success=True,
				target__govtrackid=member_id,
				target__office=office_id,
				method=Endpoint.METHOD_STAFFDOWNLOAD).values_list("created", flat=True).distinct().order_by('-created')
	delivered_message_dates = [(d, d.strftime(date_format)) for d in delivered_message_dates]

	return render_to_response('popvox/legstaff_download_messages.html', {
		"new_messages": msgs.count(),
		"delivered_message_dates": delivered_message_dates,
		}, context_instance=RequestContext(request))

@login_required
def who_members(request): #this page doesn't exist, but we could do some cool stuff with it.
    user = request.user
    prof = user.get_profile()
        
    if prof.is_leg_staff():
        raise Http404()
        
    elif prof.is_org_admin():
        raise Http404()
    
    else:
      address = PostalAddress.objects.get(user=request.user.id)
      userstate = address.state
      userdist  = address.congressionaldistrict
      usersd    = userstate+str(userdist)

      #find the govtrack ids corresponding to the user's members (note: can't assume number of reps):
      members = popvox.govtrack.getMembersOfCongressForDistrict(usersd)
      membernames = []

      for member in members:
        membernames.append(member['name'])
      return render_to_response('popvox/who_members.html', {'membernames': membernames},
        
    context_instance=RequestContext(request))

_congress_match_attendance_data = None
@login_required
def congress_match(request):

	def get_attendance_data():
		attendance_data = { }
		with open('/mnt/persistent/data/analysis/attendance.csv', 'rb') as f: # TODO: we should move this file
			reader = csv.reader(f)
			for row in reader:
				row = list(row)
				id = int(row[0])       # member ID
				row[1] = float(row[1]) # percent missed votes
				row[2] = float(row[2]) # percentile
				if row[1] < 10: # format the percent missed votes
					row[1] = "%.1f" % row[1]
				else:
					row[1] = str(int(row[1]))
				if row[2] < 40:
					row[2] = "better than %.0f%% of Members of Congress" % (100.0-row[2])
				elif row[2] > 60:
					row[2] = "worse than %.0f%% of Members of Congress" % row[2]
				else:
					row[2] = "that's about average"
				attendance_data[id] = (row[1], row[2])
			return attendance_data
	
	def attendancecheck(memberid):
		global _congress_match_attendance_data
		if _congress_match_attendance_data == None:
			_congress_match_attendance_data = get_attendance_data()
		return _congress_match_attendance_data.get(memberid, None)
	
	def getmemberids(address):
		#select the user's state and district:
		userstate = address.state
		userdist  = address.congressionaldistrict
		usersd    = userstate+str(userdist)
		
		#find the govtrack ids corresponding to the user's members (note: can't assume number of reps):
		members = popvox.govtrack.getMembersOfCongressForDistrict(usersd)
		memberids = []
		
		for member in members:
			memberids.append(member['id'])
		return memberids
	
	congress = popvox.govtrack.CURRENT_CONGRESS
	
	try:
		most_recent_address = PostalAddress.objects.filter(user=request.user).order_by('-created')[0]
	except IndexError:
		# user has no address! therefore no comments either!
		return render_to_response('popvox/home_match.html', {'billvotes': [], 'members': []},
			context_instance=RequestContext(request))
	
	memberids = getmemberids(most_recent_address)
	
	#grab the user's bills and positions:
	usercomments = UserComment.objects.filter(user=request.user)
	
	billvotes = []

	for comment in usercomments:
		#turning bill ids into bill numbers:
		if not comment.bill.is_bill(): continue
		
		#grabbing bill info
		bill_type = comment.bill.billtype
		bill_num  = str(comment.bill.billnumber)
		billstr = bill_type+bill_num
		try:
			billinfo = open('/mnt/persistent/data/govtrack/us/'+str(congress)+'/bills/'+billstr+'.xml')
			billinfo = billinfo.read()
			dom1 = parseString(billinfo)
		except:
			# not sure why the file might be missing or invalid, but just in case
			continue
		
		#checking to see if there's been a roll call vote on the bill
		#since a bill can be voted on more than once (usually once
		#per chamber!), loop through the votes and aggregate everyone's
		#votes into a single dict.
		#a bill can be voted on multiple times in the same chamber
		#(e.g. ping pong or conference reports), and we'll take the
		#last vote encountered in the file, which is the most recent.
		allvotes = dom1.getElementsByTagName("vote")
		allvoters = { }
		had_vote = False
		for vote in allvotes:
			if vote.getAttribute("how") != "roll": continue
			
			had_vote = True
			
			#pulling the roll:
			roll = vote.getAttribute("roll")
			where = vote.getAttribute("where")
			date =  vote.getAttribute("datetime")
			yearre = re.compile(r'^\d{4}')
			year = re.match(yearre, date).group(0)
			votexml = "/mnt/persistent/data/govtrack/us/" + str(congress) + "/rolls/"+where+year+"-"+roll+".xml"
			
			#parsing the voters for that roll"
			try:
				voteinfo = open(votexml)
				voteinfo = voteinfo.read()
				dom2 = parseString(voteinfo)
			except:
				# not sure why the file might be missing or invalid, but just in case
				continue
			voters = dom2.getElementsByTagName("voter")
			for voter in voters:
				voterid = int(voter.getAttribute("id"))
				votervote = voter.getAttribute("vote")
				allvoters[voterid] = (votervote, where+year+"-"+roll)
			
		#if there was no vote on this bill, output something a little different
		#(note that this is different from a vote but none of the user's reps
		#actually cast a vote)
		if not had_vote:
			billvotes.append( (comment, None) )
			continue
			
		#creating an array of the votes. if a Member wasn't in any
		#roll call, mark with NR for no roll. For each Member, record
		# a tuple of how the Member voted ("+" etc.) and a string giving
		# a reference to the vote (already put inside allvoters).
		voters_votes = []
		for member in memberids:
			voters_votes.append( allvoters.get(member, ("NR", None)) )
		billvotes.append( (comment, voters_votes) )
		
	# put all comments that have had votes first and votes cast first,
	# then comments with votes but no reps were elligible to vote,
	# and then comments without votes, each group sorted by comment
	# creation date reverse chronologically.
	billvotes.sort(key = lambda x : (
		x[1] != None,
		x[1] != None and len([y for y in x[1] if y[0] == "NR"]) != len(x[1]),
		x[0].created
		), reverse=True)
		
	# get member info for column header
	members = []
	for id in memberids:
		members.append(popvox.govtrack.getMemberOfCongress(id))
	
	# get overall stats by member
	stats = []
	had_abstain = False
	for id in memberids: # init each member to zeroes
		stats.append({ "agree": 0, "disagree": 0, "0": 0, "P": 0, "_TOTAL_": 0 })
	for comment, votes in billvotes: # for each vote...
		if not votes: continue # no vote on this bill
		for i, (vote, ref) in enumerate(votes): # and each member...
			if vote in ("+", "-"): # increment the stats
				if vote == comment.position:
					stats[i]["agree"] += 1
				else:
					stats[i]["disagree"] += 1
				stats[i]["_TOTAL_"] += 1
			elif vote in ("0", "P"): # also increment the stats
				stats[i][vote] += 1
				stats[i]["_TOTAL_"] += 1
				if vote == "P":
					had_abstain = True
			elif vote == "NR":
				pass # member did not have opportunity to vote
	for i, memstat in enumerate(stats):
		for key in ('agree', 'disagree', '0', 'P'):
			if memstat["_TOTAL_"] > 0:
				memstat[key+"_percent"] = ("%.0f" % (100.0*memstat[key]/memstat["_TOTAL_"]))
			else:
				memstat[key+"_percent"] = 0
		memstat["attendance"] = attendancecheck(memberids[i])

	return render_to_response('popvox/home_match.html', {'billvotes': billvotes, 'members': members, 'most_recent_address': most_recent_address, 'stats': stats, 'had_abstain': had_abstain},
		context_instance=RequestContext(request))

@login_required
def delete_account(request):
    user = request.user
    prof = user.get_profile()
        
    if prof.is_leg_staff():
        raise Http404()
        
    elif prof.is_org_admin():
        raise Http404()
    
    else:
        return render_to_response('popvox/delete_account.html', {},
        
    context_instance=RequestContext(request))

def unsubscribe_me_makehash(email):
	from settings import SECRET_KEY, SITE_ROOT_URL
	import hashlib
	sha = hashlib.sha1()
	sha.update(SECRET_KEY)
	sha.update(email)
	return sha.hexdigest()
	
def unsubscribe_me(request):
	email = request.GET.get("email", "---invalid---")
	key = request.GET.get("key", "")
	
	if key != unsubscribe_me_makehash(email):
		return HttpResponse("You have followed an invalid link.")
	
	try:
		u = User.objects.get(email=email)
	except User.DoesNotExist:
		return HttpResponse("You have followed an invalid link.")
		
	p = u.userprofile
	p.allow_mass_mails = False
	p.save()
	
	return HttpResponse("You have been unsubscribed.")

@login_required
def delete_account_confirmed(request):
    user = request.user
    prof = user.get_profile()
        
    if prof.is_leg_staff():
        raise Http404()
        
    elif prof.is_org_admin():
        raise Http404()
    
    else:
        return render_to_response('popvox/delete_account_confirmed.html', {},
        
    context_instance=RequestContext(request))
    
@json_response	
def recommend_from_text(request):
	q = request.GET.get("q", "").strip()
	if q == "": return { "autocomplete": None, "bills": [] }
	
	q = re.sub(r"\s+", " ", q)
	
	# Recommend bills based on a short English phrase like "I lost my job."
	
	from sphinxapi import SphinxClient, SPH_MATCH_PHRASE, SPH_MATCH_ANY
	from django.template.defaultfilters import truncatewords, escape

	c = SphinxClient()
	c.SetServer("localhost" if not "REMOTEDB" in os.environ else os.environ["REMOTEDB"], 3312)
	c.SetFilter("congressnumber", [popvox.govtrack.CURRENT_CONGRESS])
	
	def fetch_dict(model, ids, only=[]):
		objs = model.objects.filter(id__in=ids)
		if only:
			objs = objs.only(*only)
		if model == Bill: # count up total comments
			objs = objs.annotate(comment_count=Count('usercomments'))
		return dict((obj.id, obj) for obj in objs)
	
	def pull_bills(bill_list):
		# bulk transform the bill ids into url and title, prune bills
		# that are not alive for commenting, and sort by total comments
		# left on the bill.
		bills = fetch_dict(Bill, [b["bill"] for b in bill_list])
		for b in bill_list:
			if b["bill"] in bills:
				bill = bills[b["bill"]]
				if bill.isAlive() or True:
					b["url"] = bill.url()
					b["name"] = bill.nicename
					b["comment_count"] = bill.comment_count
					continue
			b["bill"] = None
		bills = [b for b in bill_list if b["bill"] != None]
		bills.sort(key = lambda x : (-x["sort_group"], x["hit_count"], x["comment_count"]), reverse=True)
		return bills
	
	autocomplete = None
	prompts = []
	bills = { }

	# First try to match exact strings against the index of user comments.
	# Use the string match to fill an autocomplete.
	
	for sort_group, match_mode in [(0, SPH_MATCH_PHRASE), (1, SPH_MATCH_ANY)]:
		c.SetMatchMode(match_mode) # exact phrase
		ret = c.Query(q, "comments")
		if ret == None:
			return { "error": c.GetLastError() }
		
		# batch retrieve matching comments
		comments = fetch_dict(UserComment, [match["id"] for match in ret["matches"]])
		users = fetch_dict(User, [comment.user_id for comment in comments.values()])
		
		for match in ret["matches"]:
			if match["id"] not in comments: continue
			comment = comments[match["id"]]
			if comment.status not in (UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED): continue
			
			message = re.sub(r"\s+", " ", comment.message.lower())
			if not autocomplete and q in message:
				i = message.lower().index(q.lower())
				autocomplete = truncatewords(message[i:], 5).replace(" ...", "")
			
			if match["attrs"]["bill_id"] not in bills:
				# generate context
				text = re.sub(r"\s+", " ", message) # clean up whitespace
				text = escape(text) # turn into HTML before <b></b> is added by context generator, hopefully won't get in the way
				context = " ".join(c.BuildExcerpts([text], "comments", q, { "before_match": "<b>", "after_match": "</b>", "exact_phrase": True, "single_passage": True})).decode("utf8")
				context = re.sub(r"^\s*\.\.\.\s*|\s*\.\.\.\s*$", "", context) # clean up whitespace
				if comment.user_id in users:
					context = escape(users[comment.user_id].username + " wrote: ") + context
				
				entry = {"bill": match["attrs"]["bill_id"], "context": context, "sort_group": sort_group, "hit_count": 0}
				bills[match["attrs"]["bill_id"]] = entry
				prompts.append(entry)
				if len(bills) == 10:
					break
			else:
				bills[match["attrs"]["bill_id"]]["hit_count"] += 1
				
		if len(bills) > 10:
			return { "autocomplete": autocomplete, "bills": pull_bills(prompts) }
		
	# Add additional bills by searching bill text.
	
	c.SetMatchMode(SPH_MATCH_ANY) # any words
	c.SetFilter("doctype", [100]) # clear this in any future searches....
	ret = c.Query(q, "doc_text")
	if ret == None:
		return { "error": c.GetLastError() }

	# batch retrieve matching documents
	docs = fetch_dict(PositionDocument, [match["attrs"]["document_id"] for match in ret["matches"]], only=["bill"])

	for match in ret["matches"]:
		if match["attrs"]["document_id"] not in docs: continue
		doc = docs[match["attrs"]["document_id"]]
		bill_id = doc.bill_id
		if bill_id not in bills:
			entry = {"bill": bill_id, "sort_group": 2, "hit_count": 0}
			prompts.append(entry)
			bills[bill_id] = entry
		else:
			bills[bill_id]["hit_count"] += 1
		if len(bills) == 10:
			break
	
	return { "autocomplete": autocomplete, "bills": pull_bills(prompts) }

def user_activity_feed(user):
	# Gets the user activity feed which is a list of feed items, each item
	# a dict with fields:
	#  ....
	
	# Define generators that iterate over feed items in reverse chronological
	# order for different sorts of events that go into your feed.
	#
	# CTA: primary call to action
	# AUX: auxiliary call to action
	# GFX: graphic/media to go along with item
	
	def your_comments(limit):
		# the positions you left
		#  CTA: share
		#  AUX: view bill
		#  GFX: preview?
		for c in user.comments.all().order_by('-updated')[0:limit]:
			yield {
				"date": c.updated,
				"name": "You " + c.verb(tense="past") + " " + c.bill.shortname + ".",
				"description": "",
			}

	def your_deliveries(limit):
		# deliveries of your comments
		#  CTA: share
		#  AUX: view bill
		#  GFX: ?
		from writeyourrep.models import DeliveryRecord
		from popvox.govtrack import getMemberOfCongress
		for d in DeliveryRecord.objects.filter(comments__user=user, success=True)[0:limit]:
			c = d.comments.all()[0]
			yield {
				"date": d.created,
				"name": "Your position on " + c.bill.shortname + " was delivered to " + getMemberOfCongress(d.target.govtrackid)["name"],
				"description": "",
			}
			
	def your_commented_bills_status(limit):
		# status of bills you have commented on
		#  CTA: share
		#  AUX: view bill
		#  GFX: ?
		for b in Bill.objects.filter(usercomments__user=user).order_by('-current_status_date'):
			c = UserComment.objects.get(user=user, bill=b)
			yield {
				"date": b.current_status_date,
				"name": b.shortname + ": " + b.status_advanced(),
				"description": "You " + c.verb(tense="past") + " the " + b.proposition_type() + " on " + str(c.created) + ".",
				"mutually_exclusive_with": ("status", b), # used by your_bookmarked_bills_status
			}
	
	def your_bookmarked_bills_status(limit):
		# status of bills you have bookmarked but not commented on
		#  CTA: weigh in
		#  AUX: share
		#  GFX: ?
		for b in Bill.objects.filter(trackedby__user=user).order_by('-current_status_date'):
			yield {
				"date": b.current_status_date,
				"name": b.shortname + ": " + b.status_advanced(),
				"description": "You bookmarked this bill.",
				"mutually_exclusive_with": ("status", b), # your_commented_bills_status must be processed first
			}
			
	def your_bills_now(limit):
		# for each bill you have weighed in on, every time the number of people weighing
		# in doubles, include it in the feed.
		#  CTA: share
		#  AUX: view report
		#  GFX: pie chart
		import math
		from popvox.views.bills import bill_statistics
		ret = []
		for c in user.comments.all():
			# I suspect that people will want to see updates more for bills they
			# actually wrote something about.
			if c.message:
				doubling = 1.5
			else:
				doubling = 1.95
			
			# how many comments were left at the time you weighed in?
			nc1 = c.bill.usercomments.filter(created__lt=c.created).count() + 1
			
			# how many comments are left now?
			nc2 = c.bill.usercomments.count()
			
			# how many times has it doubled since then? i.e. 2^x = nc2/nc1
			x = (math.log(nc2) - math.log(nc1)) / math.log(doubling)
			
			# find the time of the most recent doubling, i.e. the time of the
			# nc1*2^[x]'th comment where [x] is x rounded down to the nearest integer.
			x = math.floor(x)
			if x <= 0.0: continue # has not doubled yet, or maybe it has gone down!
			try:
				c2 = c.bill.usercomments.order_by('created')[int(doubling**x * nc1)]
			except IndexError:
				# weird?
				continue
			
			# get the statistics as of that date
			stats = bill_statistics(c.bill, "POPVOX", "POPVOX Nation", as_of = c2.created)
			if not stats: continue
			
			ret.append({
				"date": c2.created,
				"name": str(stats["total"]) + " people have now weighed in on " + c.bill.shortname + ".",
				"description": "You were individual number " + str(nc1) + ". Here is how the " + c.bill.proposition_type() + " is doing now....",
			})
			
		# We can't efficiently query these events in date order, so we pull them all
		# and return the most recent in date order.
		ret.sort(key = lambda item : item["date"], reverse=True)
		for item in ret[0:limit]:
			yield item
			
	def new_bills(limit):
		# What newly introduced bills do we think you might be interested in?
		#  CTA: weigh in (if you haven't already)
		#  AUX: share
		#  GFX: ?
		
		limit /= 5 # these can be overwhelming, don't deliver so many
		
		# Get the issue areas that the user is interested in.
		top_issues = IssueArea.objects.all().annotate(count=Count("id")).filter(bills__usercomments__user=user).order_by('-count')
		count = 0
		for i, ix in enumerate(top_issues):
			count2 = 0
			for bill in Bill.objects.filter(topterm=ix, current_status__in=('INTRODUCED', 'REFERRED')).order_by('-current_status_date'):
				yield {
					"date": bill.current_status_date,
					"name": "New " + bill.proposition_type() + ": " + bill.nicename,
					"description": "We thought you might be interested in this because you have weighed in on " + ix.name + " bills.",
				}
				
				count += 1
				if count == limit: return
				
				# spread out the returned items across the user's top issue areas, with
				# more for the first issue area, and a little less for the second, and on.
				count2 += 1
				if count2 > limit/(i+3): break

	def new_org_positions(limit):
		# What new organization position statements do we think you might be interested in?
		#  CTA: view position statement
		#  AUX: weigh in or share?
		#  GFX: ?
		
		limit /= 5 # these can be overwhelming, don't deliver so many
		
		# Get the issue areas that the user is interested in.
		top_issues = IssueArea.objects.all().annotate(count=Count("id")).filter(bills__usercomments__user=user).order_by('-count')
		count = 0
		for i, ix in enumerate(top_issues):
			count2 = 0
			for ocp in OrgCampaignPosition.objects.filter(bill__topterm=ix).order_by('-created').select_related("campaign", "campaign__org", "bill"):
				yield {
					"date": ocp.created,
					"name": ocp.campaign.org.name + " " + ocp.verb() + " " + ocp.bill.nicename,
					"description": "We thought you might be interested in this because you have weighed in on " + ix.name + " bills.",
				}
				
				count += 1
				if count == limit: return
				
				# spread out the returned items across the user's top issue areas, with
				# more for the first issue area, and a little less for the second, and on.
				count2 += 1
				if count2 > limit/(i+3): break

	#upcoming votes - haven't commented: weigh in [ share] | pie
	#upcoming votes - already commented: share [ bill report ] | your position

	feed_size = 25
	sources = (your_comments, your_deliveries, your_commented_bills_status, your_bookmarked_bills_status, your_bills_now, new_bills, new_org_positions)
	exclusions = set()
	feed = []
	for source in sources:
		for item in source(feed_size):
			# allow feed items to be hidden if some other particular feed item has
			# already been included.
			if item.get("mutually_exclusive_with", None) in exclusions:
				continue
				
			feed.append(item)
			
			# mark what this feed item is about if it is used to hide other types
			# of similar feed items.
			if "mutually_exclusive_with" in item:
				exclusions.add(item["mutually_exclusive_with"])
			
	
	feed.sort(key = lambda item : item["date"], reverse=True)
	feed = feed[0:feed_size]
	
	return feed
	

