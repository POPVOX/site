from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.views.generic.simple import direct_to_template
from django.core.cache import cache
from django.contrib.auth.decorators import login_required, user_passes_test
from django import forms
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
		suggestions.append({
			"id": "sponsor",
			"type": "sponsor",
			"name": "Sponsored by " + bossname,
			"shortname": boss.lastname(),
			"bills": select_bills(sponsor = boss)
			})

	localbills = get_legstaff_district_bills(user)
	if localbills != None and len(localbills) > 0:
		moc = popvox.govtrack.getMemberOfCongress(boss.id)
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
				s["bills"] = ext_filter(s["bills"])
		
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
	f1 = { "state": member["state"] }
	cache_key = "get_legstaff_district_bills#" + member["state"]
	if member["type"] == "rep":
		cache_key += "," + str(member["district"])
		f1["congressionaldistrict"] = member["district"]
	
	localbills = cache.get(cache_key)
	if localbills != None:
		return localbills
	
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
			if not target_bill in targets: targets[target_bill] = []
			targets[target_bill].append( (source_bill, similarity) )
			max_sim = max(similarity, max_sim)
	
	from bills import get_popular_bills
	for bill in get_popular_bills():
		if bill not in targets:
			targets[bill] = [(None, max_sim/10.0)]
	
	# Put the targets in descending weighted similarity order.
	targets = list(targets.items()) # (target_bill, [list of (source,similarity) pairs]), where source can be null if it is coming from the tending bills list
	targets.sort(key = lambda x : -sum([y[1] for y in x[1]]))
	
	# Remove the recommendations that the user has anti-tracked or commented on.
	antitracked_bills = set(user.userprofile.antitracked_bills.all())
	commented_bills = set(Bill.objects.filter(usercomments__user=user))
	targets = filter(lambda x : not x[0] in antitracked_bills|commented_bills, targets)
	
	# Take the top reccomendations.
	targets = targets[:15]
	
	# Replace the list of target sources with just the highest-weighted source for each target.
	for i in xrange(len(targets)):
		targets[i][1].sort(key = lambda x : -x[1])
		targets[i] = { "bill": targets[i][0], "source": targets[i][1][0][0] }
	
	# targets is now a list of (target, source) pairs.
	
	return targets

@login_required
def home(request):
	user = request.user
	prof = user.get_profile()
	if prof == None:
		raise Http404()
		
	if prof.is_leg_staff():
		return render_to_response('popvox/home_legstaff_dashboard.html',
			{
				"docket": get_legstaff_suggested_bills(request.user, counts_only=True, include_extras=False),
				"calendar": get_calendar_agenda(user)
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
			   'feed': govtrack.loadfeed(feed),
			   "tracked_bills": annotate_track_status(prof, prof.tracked_bills.all()),
			   "adserver-targets": ["org_admin_home"],
			   },
			context_instance=RequestContext(request))
	else:
		return render_to_response('popvox/homefeed.html',
			{ 
			"suggestions": compute_prompts(user)[0:4],
			"tracked_bills": annotate_track_status(prof, prof.tracked_bills.all()),
		     "adserver-targets": ["user_home"],
			    },
			context_instance=RequestContext(request))

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
			"suggestions": get_legstaff_suggested_bills(request.user),
			"filternextvotechamber": prof.getopt("home_legstaff_filter_nextvote", ""),
			"adserver-targets": ["leg_staff_home"],
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
				[ (abbr, govtrack.statenames[abbr]) for abbr in govtrack.stateabbrs],
			"statereps": govtrack.getStateReps(),
			
			# for admins only....
			"count_users": User.objects.all().count(),
			"count_legstaff": UserLegStaffRole.objects.all().count() - 1, # minus one for our demo acct
			"count_users_verified": pntv,
			"count_comments": UserComment.objects.all().count(),
			"count_comments_messages": UserComment.objects.filter(message__isnull=False).count(),
			"count_orgs": Org.objects.filter(createdbyus=False).count(),
		}, context_instance=RequestContext(request))

@csrf_exempt	
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

	if request.POST.get("comments", "true") != "false":
		filters = { }
		if state != None:
			filters["address__state"] = state
			if district != None:
				filters["address__congressionaldistrict"] = district
		
		if "bill" in request.REQUEST:
			bill = Bill.objects.get(id = request.REQUEST["bill"])
			filters["bill"] = bill
			format = "_bill"
		
		q = UserComment.objects.filter(message__isnull=False, status__in=(UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED), **filters).order_by('-created')

		if format == "_bill":
			total_count = q.count()
	
		q = q[0:count]
	
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
	for moc in popvox.govtrack.getMembersOfCongress():
		moc = dict(moc)
		report.append(moc)
		
		try:
			ep = Endpoint.objects.get(govtrackid=moc["id"])
		except Endpoint.DoesNotExist:
			ep = None
			
		if ep == None or (ep.method == Endpoint.METHOD_NONE and ep.tested):
			moc["delivery_status"] = "Cannot Deliver Messages"
			continue
			
		d = DeliveryRecord.objects.filter(target=ep, next_attempt__isnull=True)
		d_success = d.filter(failure_reason__in=(
			DeliveryRecord.FAILURE_NO_FAILURE,
			DeliveryRecord.FAILURE_SELECT_OPTION_NOT_MAPPABLE
			)).exclude(method=Endpoint.METHOD_INPERSON)
		d_delivered = d.filter(success=True)
			
		d = d.count()
		if d == 0:
			moc["delivery_status"] = "Either no messages or no delivery method...."
			continue
		
		ratio = float(d_success.count()) / float(d)
		ratio = int(100.0*(1.0-ratio))
		
		if ratio <= 1:
			moc["delivery_status"] = "OK!"
		elif ratio < 5:
			moc["delivery_status"] = "OK! (Mostly)"
		else:
			moc["delivery_status"] = "%s%% of Messages Failing (are hand-delivered)" % ratio

		moc["delivery_status"] += " %d/%d/%d" % (d_success.count(), d_delivered.count(), d)

	return render_to_response('popvox/delivery_status_report.html', {
		"report": report,
		}, context_instance=RequestContext(request))
	

