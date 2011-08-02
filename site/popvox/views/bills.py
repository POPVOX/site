from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.views.generic.simple import direct_to_template
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.contrib.auth.decorators import login_required
from django import forms
from django.core.urlresolvers import reverse
from django.views.decorators.cache import cache_page
from django.template.defaultfilters import truncatewords
from django.utils.html import strip_tags
from django.db.models import Count
from django.core.cache import cache

from jquery.ajax import json_response, ajax_fieldupdate_request, sanitize_html, validation_error_message

import os
import re
from xml.dom import minidom
import urllib
import datetime
import json
import urllib2

from popvox.models import *
from registration.helpers import captcha_html, validate_captcha
from popvox.govtrack import CURRENT_CONGRESS, getMembersOfCongressForDistrict, open_govtrack_file, statenames, getStateReps
from emailverification.utils import send_email_verification
from utils import formatDateTime, cache_page_postkeyed, csrf_protect_if_logged_in

from settings import DEBUG, SERVER_EMAIL, TWITTER_OAUTH_TOKEN, TWITTER_OAUTH_TOKEN_SECRET, SITE_ROOT_URL

popular_bills_cache = None
popular_bills_cache_2 = None
issue_areas = None

def getissueareas():
	# Gets the issue areas in batch.
	global issue_areas
	if issue_areas != None:
		return issue_areas
	all_issues = IssueArea.objects.all()
	issues = { }
	for ix in all_issues:
		if ix.parent_id == None:
			issues[ix.id] = { "object": ix, "subissues": [] }
	for ix in all_issues:
		if ix.parent_id != None and ix.parent.id in issues:
			issues[ix.parent_id]["subissues"].append(ix)
	issues = issues.values()
	issues.sort(key = lambda x : x["object"].name)
	issue_areas = issues
	return issues

@cache_page(60 * 60 * 2) # two hours
def issuearea_chooser_list(request):
	return render_to_response('popvox/issueareachooser_list.html', {'issues': getissueareas()}, context_instance=RequestContext(request))	

def get_popular_bills():
	global popular_bills_cache

	if popular_bills_cache != None and (datetime.now() - popular_bills_cache[0] < timedelta(minutes=30)):
		return popular_bills_cache[1]
		
	popular_bills = []

	# Select bills with the most number of recent comments.
	# TODO: Is this SQL fast enough? Well, it's not run often.
	for b in Bill.objects.filter(usercomments__created__gt=datetime.now()-timedelta(days=7)).annotate(Count('usercomments')).order_by('-usercomments__count').select_related("sponsor")[0:12]:
		if b.usercomments__count == 0:
			break
		if not b in popular_bills:
			popular_bills.append(b)
			if len(popular_bills) > 12:
				break
	
	popular_bills_cache = (datetime.now(), popular_bills)
	
	return popular_bills

def get_popular_bills2():
	global popular_bills_cache_2

	if popular_bills_cache_2 != None and (datetime.now() - popular_bills_cache_2[0] < timedelta(minutes=30)):
		return popular_bills_cache_2[1]

	popular_bills = get_popular_bills()

	# Get the campaigns that support or oppose any of the bills, in batch.
	cams = OrgCampaign.objects.filter(positions__bill__in = popular_bills, visible=True, org__visible=True).select_related() # note recursive SQL which goes from OrgCampaign to Org
	
	# Annotate the list of popular bills with the org information.
	popular_bills2 = [ ]
	bmap = { }
	for bill in popular_bills:
		b = { }
		popular_bills2.append(b)
		b["bill"] = bill
		b["orgs"] = {}
		bmap[bill.govtrack_code()] = b
	for cam in cams:
		for pos in cam.positions.all().select_related(): # note recursive SQL which goes from OrgCampaignPosition to Bill
			if pos.position == "0": # not showing neutral positions in hot bills list
				continue
			if not pos.bill.govtrack_code() in bmap:
				continue
			b = bmap[pos.bill.govtrack_code()]
			if not cam.org.slug in b["orgs"]:
				b["orgs"][cam.org.slug] = {
					"name": cam.org.name,
					"url": cam.org.url(),
					"object": cam.org,
					"position": pos.position,
					"campaigns": []
				}
			if not cam.default:
				b["orgs"][cam.org.slug]["campaigns"].append(
					{ "name": cam.name,
						 "url": cam.url(),
						 "position": pos.position,
						 "description": cam.description,
						 "message": cam.message
						 })
			
	# For each bill, sort the organizations by fan count.
	# Get the fan counts in batch and store in a dict.
	org_fan_count = { }
	for cam in cams:
			org_fan_count[cam.org.slug] = { }
			for s in OrgExternalMemberCount.SOURCE_TYPES:
				org_fan_count[cam.org.slug][s] = 0
	for ofc in OrgExternalMemberCount.objects.filter(org__in = [cam.org for cam in cams]):
		org_fan_count[ofc.org.slug][ofc.source] = ofc.count
	# Do the sorting.
	for billrec in popular_bills2:
		# Sort orgs by fan counts.
		orgs = list(billrec["orgs"].values())
		orgs.sort(key = lambda org : -(
			org_fan_count[org["object"].slug][OrgExternalMemberCount.FACEBOOK_FANS]
			+ org_fan_count[org["object"].slug][OrgExternalMemberCount.TWITTER_FOLLOWERS]
			))
		billrec["orgs"] = orgs[0:4]
		
	popular_bills_cache_2 = (datetime.now(), popular_bills2)
	
	return popular_bills2
		
def bills(request):
	popular_bills2 = get_popular_bills2()
	
	# Annotate a copy of the popular_bills dict with whether the user
	# or the user on behalf of an org has taken a position on each
	# bill.
	# TODO: Simplify SQL calls. This does a lot of SQL.
	for b in popular_bills2:
		b["pos"] = ""
		if request.user.is_authenticated() and request.user.userprofile.is_org_admin():
			for orgrole in request.user.orgroles.all():
				for cam in orgrole.org.orgcampaign_set.all():
					for pos in cam.positions.all():
						if pos.bill.id == b["bill"].id:
							if b["pos"] == "" or b["pos"] == pos.position:
								b["pos"] = pos.position
							else:
								b["pos"] = "CONFLICT"
		elif request.user.is_authenticated():
			c = request.user.comments.filter(bill = b["bill"])
			if len(c) > 0:
				b["pos"] = c[0].position
	
	return render_to_response('popvox/bill_list.html', {
		'trending_bills': popular_bills2,
		}, context_instance=RequestContext(request))

@csrf_protect_if_logged_in
def billsearch(request):
	if not "q" in request.GET or request.GET["q"].strip() == "":
		return HttpResponseRedirect("/bills")
	q = request.GET["q"].strip()

	bill_number_re = re.compile(r"(hr|s|hconres|sconres|hjres|sjres|hres|sres)(\d+)(/(\d+))?", re.I)
	m = bill_number_re.match(q.replace(" ", "").replace(".", "").replace("-", ""))
	if m != None:
		cn = CURRENT_CONGRESS
		if "congressnumber" in request.GET and request.GET["congressnumber"].isdigit():
			cn = int(request.GET["congressnumber"])
		if m.group(3) != None:
			cn = int(m.group(4))
		try:
			b = bill_from_url("/bills/us/%d/%s%d" % (cn, m.group(1).lower(), int(m.group(2))))
			if request.user.is_authenticated() and request.user.userprofile.is_leg_staff():
				return HttpResponseRedirect(b.url() + "/report")
			else:
				return HttpResponseRedirect(b.url())
		except:
			pass
			

	from sphinxapi import SphinxClient, SPH_MATCH_EXTENDED
	c = SphinxClient()
	c.SetServer("localhost" if not "REMOTEDB" in os.environ else os.environ["REMOTEDB"], 3312)
	c.SetMatchMode(SPH_MATCH_EXTENDED)
	if "congressnumber" in request.GET and request.GET["congressnumber"].isdigit():
		c.SetFilter("congressnumber", [int(request.GET["congressnumber"])])
	else:
		c.SetFilter("congressnumber", [CURRENT_CONGRESS])
	ret = c.Query(q)
	bills = []
	status = "ok"
	error = None
	if ret == None:
		error = c.GetLastError()
		search_response = []
		status = "callfail"
	else:
		for b in ret["matches"]:
			bills.append(b["id"])
			if len(bills) == 100:
				status = "overflow"
				break

	bills = Bill.objects.filter(id__in=bills)
	if request.user.is_authenticated():
		import home
		home.annotate_track_status(request.user.userprofile, bills)

	if len(bills) == 1:
		if request.user.is_authenticated() and request.user.userprofile.is_leg_staff():
			return HttpResponseRedirect(bills[0].url() + "/report")
		else:
			return HttpResponseRedirect(bills[0].url())
	return render_to_response('popvox/billsearch.html', {'bills': bills, "q": request.GET["q"].strip(), "congressnumber": request.GET.get("congressnumber", ""), "status": status, "errormsg": error}, context_instance=RequestContext(request))

def getbill(congressnumber, billtype, billnumber, vehicleid=None):
	if vehicleid != None:
		try:
			vehicleid = int(vehicleid[1:])
		except:
			raise "Invalid bill number. Invalid vehicle id \"" + vehicleid + "\"."
		b = [getbill(congressnumber, billtype, billnumber)]
		while b[0].replaced_vehicle.exists():
			x = b[0].replaced_vehicle.all()[0]
			b.insert(0, x)
		if vehicleid < 1 or vehicleid > len(b):
			raise "Invalid bill number. Invalid vehicle id \"" + vehicleid + "\"."
		return b[vehicleid-1]

	if int(congressnumber) < 1 or int(congressnumber) > 1000: 
		raise Http404("Invalid bill number. \"" + congressnumber + "\" is not valid.")
	try:
		billtype = [x[0] for x in Bill.BILL_TYPE_SLUGS if x[1] == billtype][0]
	except:
		raise Http404("Invalid bill number. \"" + billtype + "\" is not valid.")
	try:
		return Bill.objects.filter(congressnumber=congressnumber, billtype=billtype, billnumber=billnumber, vehicle_for=None).select_related("sponsor")[0]
	except:
		raise Http404("Invalid bill number. There is no bill by that number.")
	
@json_response
def billsearch_ajax(request):
	bill = getbill(
		request.POST["congressnumber"] if request.POST["congressnumber"] != "0" else CURRENT_CONGRESS,
		request.POST["billtype"].lower(),
		request.POST["billnumber"])
	return {
		"status": "success",
		"congressnumber": bill.congressnumber,
		"billtype": bill.billtype,
		"billnumber": bill.billnumber,
		"url": bill.url(),
		"title": bill.title,
		"billstatus": bill.status_advanced(),
		"sponsor": { "id": bill.sponsor.id, "name": bill.sponsor.name() } if bill.sponsor != None else None,
		}
	
def bill_comments(bill, **filterargs):
	def filter_null_args(kv):
		ret = { }
		for k, v in kv.items():
			if v != None:
				ret[k] = v
		return ret
	
	return bill.usercomments.filter(**filter_null_args(filterargs))\
		.select_related("user")

def bill_statistics_cache(f):
	def g(bill, shortdescription, longdescription, want_timeseries=False, **filterargs):
		cache_key = ("bill_statistics_cache:%d,%s,%s" % (bill.id, shortdescription.replace(" ", ""), want_timeseries)) 
		
		ret = cache.get(cache_key)
		if ret != None and want_timeseries:
			return ret
		
		ret = f(bill, shortdescription, longdescription, want_timeseries, **filterargs)
		
		cache.set(cache_key, ret, 60*60*2) # two hours

		return ret
	return g

@bill_statistics_cache # the arguments must match in the decorator!
def bill_statistics(bill, shortdescription, longdescription, want_timeseries=False, **filterargs):
	# If any of the filters is None, meaning it is based on demographic info
	# that the user has not set, return None for the whole statistic group.
	for key in filterargs:
		if filterargs[key] == None:
			return None
			
	# Get comments that were left only before the session ended.
	enddate = govtrack.getCongressDates(bill.congressnumber)[1] + timedelta(days=1)
	
	# Get all counts at once, where stage = 0 if the comment was before the end of
	# the session, 1 if after the end of the session.
	counts = bill_comments(bill, **filterargs).order_by().extra(select={"stage": "popvox_usercomment.created > '" + enddate.strftime("%Y-%m-%d") + "'"}).values("position", "stage").annotate(count=Count("id"))
	
	pro = 0
	con = 0
	pro_reintro = 0
	for item in counts:
		if item["position"] == "+" and item["stage"] == 0:
			pro = item["count"]
		if item["position"] == "-" and item["stage"] == 0:
			con = item["count"]
		if item["position"] == "+" and item["stage"] == 1:
			pro_reintro = item["count"]
		
	# Don't display statistics when there's very little data,
	# and definitely not when pro+con == 0 since that'll gen
	# an error down below.
	if pro+con+pro_reintro < 10:
		return None

	if pro+con < 10:
		return {
			"shortdescription": shortdescription,
			"longdescription": longdescription,
			"total": 0, "pro":0, "con":0,
			"pro_pct": 0, "con_pct": 0,
			"timeseries": None,
			"pro_reintro": pro_reintro
			}
	
	time_series = None
	if want_timeseries:
		all_comments = bill_comments(bill, **filterargs).exclude(created__gt=enddate).defer("message")
	
		# Get a time-series. Get the time bounds --- use the national data for the
		# time bounds so that if we display multiple charts together they line up.
		firstcommentdate = bill.usercomments.filter(created__lte=enddate).defer("message").order_by('created')[0].created.date()
		lastcommentdate = bill.usercomments.filter(created__lte=enddate).defer("message").order_by('-created')[0].updated.date()
		
		# Compute a bin size (i.e. number of days per point). Try to have 30 bins,
		# unless that subdivides a day into multiple bins, which would be weird.
		binsize = 1
		if firstcommentdate < lastcommentdate:
			binsize = int((lastcommentdate - firstcommentdate).days / 30)
		if binsize < 1:
			binsize = 1
		
		# Bin the observations.
		bins = { }
		for c in all_comments:
			days = int(round((c.created.date() - firstcommentdate).days / binsize) * binsize)
			if not days in bins:
				bins[days] = { "+": 0, "-": 0 }
			bins[days][c.position] += 1
		ndays = (lastcommentdate - firstcommentdate).days + 1
		days = sorted(bins.keys())
		time_series = {
			"xaxis": [(firstcommentdate + timedelta(x)).strftime("%x") for x in days],
			"pro": [sum([bins[y]["+"] for y in xrange(0, ndays) if y <= x and y in bins]) for x in days],
			"con": [sum([bins[y]["-"] for y in xrange(0, ndays) if y <= x and y in bins]) for x in days],
			}
			
	return {
		"shortdescription": shortdescription,
		"longdescription": longdescription,
		"total": pro+con, "pro":pro, "con":con,
		"pro_pct": int(round(100.0*pro/float(pro+con))), "con_pct": int(round(100.0*con/float(pro+con))),
		"timeseries": time_series,
		"pro_reintro": pro_reintro}
	
@csrf_protect_if_logged_in
def bill(request, congressnumber, billtype, billnumber, vehicleid):
	bill = getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)
	
	# Get the organization that the user is an admin of, if any, so he can
	# have the org take a position on it.
	user_org = None
	existing_org_positions = []
	if request.user.is_authenticated() and request.user.get_profile() != None:
		import home
		home.annotate_track_status(request.user.userprofile, [bill])
	
		user_org = request.user.orgroles.all()
		if len(user_org) == 0: # TODO down the road
			user_org = None
		else:
			posdescr = {"+": "endorsed", "-": "opposed", "0": "listed neutral with a statement" }
			user_org = user_org[0].org
			for cam in user_org.orgcampaign_set.all():
				for p in cam.positions.filter(bill = bill):
					existing_org_positions.append({"bill": bill, "campaign": cam, "position": posdescr[p.position], "comment": p.comment, "id": p.id, "documents": p.documents()})
		
	user_position = None
	mocs = []
	ch = bill.getChamberOfNextVote()

	if request.user.is_authenticated():
		# Get the user's current position on the bill.
		# In principle by the data model, a user might take multiple positions
		# on a single bill. But we try to prevent that.
		for c in request.user.comments.filter(bill=bill):
			user_position = c
		
		# Get the list of Members of Congress who could vote on this bill
		# based on the user's most recent comment's congressional district.
		district = request.user.userprofile.most_recent_comment_district()
		if district != None:
			if ch != None:
				if ch == "s":
					mocs = getMembersOfCongressForDistrict(district, moctype="sen")
				else:
					mocs = getMembersOfCongressForDistrict(district, moctype="rep")
			
	# Get the orgs who support or oppose the bill, and the relevant campaigns
	# within the orgs.
	orgs = [ ["support", {}], ["oppose", {}], ["neutral", {}], ["administration", {}] ]
	for p in bill.campaign_positions():
		cam = p.campaign

		grp = {"+":"support","-":"oppose","0":"neutral"}[p.position]
		if cam.org.id == 2123: grp = "administration" # The Administration
		grp = [g[1] for g in orgs if g[0] == grp][0]

		if not cam.org.slug in grp:
			grp[cam.org.slug] = {
				"id": cam.org.id,
				"name": cam.org.name,
				"url": cam.org.url(),
				"object": cam.org,
				"campaigns": [],
				"comment": None,
				"documents": cam.org.documents.filter(bill=bill).defer("text"),
			}
		if cam.default or grp[cam.org.slug]["comment"] == None:
			grp[cam.org.slug]["comment"] = p.comment
		if not cam.default:
			grp[cam.org.slug]["campaigns"].append(
				{ "name": cam.name,
					 "url": cam.url(),
					 "description": cam.description,
					 "message": cam.message,
					 "comment": p.comment
					 })
	# Sort orgs by fan counts.
	def sort_orgs(orgs):
		orgs = list(orgs)
		orgs.sort(key = lambda org : -(org["object"].facebook_fan_count() + org["object"].twitter_follower_count()))
		return orgs
	for grp in orgs:
		grp[1] = sort_orgs(grp[1].values())
	
	# Welcome message?
	welcome = None
	welcome_tabname = None
	referral_orgposition = None
	
	if "shorturl" in request.session and request.session["shorturl"].target == bill:
		# Referral to this bill. If the link owner left a comment on the bill,
		# then we can use that comment as the basis of the welcome
		# message.
		request.session["comment-referrer"] = {"bill": bill.id, "referrer": request.session["shorturl"].owner, "shorturl": request.session["shorturl"].id }
		if isinstance(request.session["shorturl"].owner, Org):
			welcome = "Hello! " + request.session["shorturl"].owner.name + " wants to tell you about " + bill.displaynumber() + " on POPVOX.  Learn more about the issue and let POPVOX amplify your voice to Congress."
			try:
				welcome_tabname = "Organization's Position"
				referral_orgposition = OrgCampaignPosition.objects.filter(campaign__org=request.session["shorturl"].owner, bill=bill)[0]
				if referral_orgposition.position in ("+", "-"):
					welcome = "Hello! " + request.session["shorturl"].owner.name + " wants you to " + ("support" if referral_orgposition.position == "+" else "oppose") + " " + bill.displaynumber() + ".  Learn more about the issue and let POPVOX amplify your voice to Congress."
			except:
				pass
			
			# If an org admin follows their own link, let them see it from the
			# user's perspective.
			if user_org == request.session["shorturl"].owner:
				user_org = None
				
		del request.session["shorturl"]
	
	users_tracking_this_bill = None
	users_commented_on_this_bill = None
	if request.user.is_authenticated() and (request.user.is_staff or request.user.is_superuser):
		users_tracking_this_bill = bill.trackedby.filter(allow_mass_mails=True, user__orgroles__isnull = True, user__legstaffrole__isnull = True).distinct().select_related("user")
		users_commented_on_this_bill = UserProfile.objects.filter(allow_mass_mails=True, user__comments__bill=bill).distinct().select_related("user")
	
	return render_to_response('popvox/bill.html', {
			'bill': bill,
			"canvote": (request.user.is_anonymous() or (not request.user.userprofile.is_leg_staff() and not request.user.userprofile.is_org_admin())),
			"deadbox": not bill.isAlive() and user_position == None,
			
			"user_org": user_org,
			"existing_org_positions": existing_org_positions,
			"lastviewedcampaign": request.session["popvox_lastviewedcampaign"] if "popvox_lastviewedcampaign" in request.session and not OrgCampaign.objects.get(id=request.session["popvox_lastviewedcampaign"]).default  else "",
			
			"user_position": user_position,
			"mocs": mocs,
			"nextchamber": ch,
			
			"orgs": orgs,
			
			"welcome": welcome,
			"welcome_tabname": welcome_tabname,
			"referral_orgposition": referral_orgposition,
			
			"users": { "tracking": users_tracking_this_bill, "commented": users_commented_on_this_bill },
		}, context_instance=RequestContext(request))

pending_comment_session_key = "popvox.views.bills.billcomment__pendingcomment"

# This is an email verification callback.
class DelayedCommentAction:
	registrationinfo = None # a RegisterUserAction object
	bill = None
	comment_session_state = None
	
	def email_subject(self):
		return "POPVOX: One More Step to Submit Your Comment"
		
	def email_body(self):
		return """Thanks for coming to POPVOX and commenting on legislation. To
finish creating your account so that your comment can be submitted,
just follow this link:

<URL>

If the link is not clickable, please copy and paste it into your web browser.

All the best,

POPVOX

(We'll send this email again soon in case you miss it the first time.
If you do not wish to complete the action and do not want to get
a reminder, please follow this link instead to stop future reminders:
<KILL_URL>)"""

	def email_should_resend(self):
		return not User.objects.filter(email = self.registrationinfo.email).exists()

	def get_response(self, request, vrec):
		# Create the user and log the user in.
		self.registrationinfo.finish(request)
		
		# Set the session state.
		request.session[pending_comment_session_key] = self.comment_session_state
		
		# Redirect to the comment form to continue.
		request.goal = { "goal": "comment-register-registered" }
		return HttpResponseRedirect(Bill.objects.get(id=self.bill).url() + "/comment/finish")

@csrf_protect
def billcomment(request, congressnumber, billtype, billnumber, vehicleid, position):
	from settings import BENCHMARKING

	position_original = position
	if position_original == None:
		position_original = ""
	
	bill = getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)
	
	address_record = None
	address_record_fixed = None
	
	# Clear out the session state for a pending comment (set e.g. if
	# user has to go away to do oauth login) if the pending comment
	# is for a different bill, or if the bill is not set (old cookie).
	if pending_comment_session_key in request.session and (not "bill" in request.session[pending_comment_session_key] or request.session[pending_comment_session_key]["bill"] != bill.url()):
		del request.session[pending_comment_session_key]
	
	# the user chooses the position on the main bill page and it gets
	# stored in the URL, or if the user is editing an existing comment
	# on the bill he can skip that part of the URL.
	if position == "/clear":
		position = "0"
	elif position == "/support":
		position = "+"
	elif position == "/oppose":
		position = "-"
	elif position == "/finish":
			# Get position from saved session, if any.
			if pending_comment_session_key in request.session:
				position = request.session[pending_comment_session_key]["position"]
			else:
				# Ruh-row.
				return HttpResponseRedirect(bill.url())
	elif position == None:
		if request.user.is_authenticated():
			# Get position from user's existing comment, if any.
			comments = request.user.comments.filter(bill = bill)
			if len(comments) == 0:
				return HttpResponseRedirect(bill.url())
			else:
				position = comments[0].position
				address_record = comments[0].address
				if (address_record.phonenumber != None and address_record.phonenumber != ""):
					address_record_fixed = "(You cannot change the address on a comment you have already submitted.)"
		else:
			return HttpResponseRedirect(bill.url())
	else:
		raise Http404()
		
	if address_record == None and request.user.is_authenticated():
		# Get the most recent address record created by the user.
		addresses = request.user.postaladdress_set.order_by("-created")
		if len(addresses) > 0:
			address_record = addresses[0]
			if address_record.created and (datetime.now() - address_record.created).days < 60:
				address_record_fixed = "You cannot change your address for two months after entering your address."
				
	# Allow (actually require) the user to revise an address that does not have a prefix or phone number.
	if address_record != None and address_record_fixed != None and (
		address_record.nameprefix == "" or address_record.phonenumber == "" or request.user.username == "POPVOXTweets"):
		address_record_fixed = None
	
	# We will require a captcha for this comment if the user is creating many comments
	# in a short period of time and if we are not editing an existing comment.
	require_captcha = False
	#if not request.user.is_anonymous() and request.user.id not in (1, 59):
	#	require_captcha = request.user.comments.filter(created__gt = datetime.now()-timedelta(days=20)).count() > 20 \
	#	and not request.user.comments.filter(bill = bill).exists()
	
	try:
		if len(request.POST) > 0: request.session.delete_test_cookie()
	except:
		pass
	
	if not "submitmode" in request.POST and position_original != "/finish":
		message = None
		has_been_delivered = False
		message_is_new = True

		request.goal = { "goal": "comment-begin" }
			
		# If the user has already saved a comment on this bill, load it up
		# as default values for the form.
		if position != "0" and request.user.is_authenticated():
			for c in request.user.comments.filter(bill = bill):
				request.goal = { "goal": "comment-edit-begin" }
				message = c.message
				has_been_delivered = c.has_been_delivered()
				message_is_new = False
				break
				
		# If we have a saved session, load the saved message.
		if pending_comment_session_key in request.session:
			message = request.session[pending_comment_session_key]["message"]
			
		# If we're coming from a customized org action page...
		if "orgcampaignposition" in request.POST:
			billpos = get_object_or_404(OrgCampaignPosition, id=request.POST["orgcampaignposition"], bill=bill)
			request.session["comment-referrer"] = {"bill": bill.id, "referrer": billpos.campaign }
			request.session["comment-default-address"] = (request.POST["name_first"], request.POST["name_last"], request.POST["zip"], request.POST["email"])
			if request.POST.get("share_with_org", "") == "1":
				request.session["comment-referrer"]["campaign"] = billpos.get_service_account_campaign().id
				billpos.get_service_account_campaign().add_action_record(
					email = request.POST["email"],
					firstname = request.POST["name_first"],
					lastname = request.POST["name_last"],
					zipcode = request.POST["zip"] )
	
		request.session.set_test_cookie() # tested in on the client side
		return render_to_response('popvox/billcomment_start.html', {
				'bill': bill,
				"position": position,
				"message": message,
				"has_been_delivered": has_been_delivered,
				"message_is_new": message_is_new,
			}, context_instance=RequestContext(request))
	
	elif ("submitmode" in request.POST and request.POST["submitmode"] == "Preview >") or (not "submitmode" in request.POST and position_original == "/finish" and not request.user.is_authenticated()):
		# The user clicks preview to get a preview page.
		# Or the user returns from a failed login.
		
		if "submitmode" in request.POST:
			# TODO: Validate that a message has been provided and that messages are
			# not too long or too short.
			message = request.POST.get("message", None)
			if message != None and (message.strip() == "" or message == "None"):
				message = None
		else:
			message = request.session[pending_comment_session_key]["message"]
		
		# If the user has to log in (via oauth etc), they will get redirected away, so
		# we will put the comment into a session variable which we handle when
		# they return here.
		#
		# This is also set in DelayedCommentAction.
		request.session[pending_comment_session_key] = {
			"bill": bill.url(),
			"position": position,
			"message": message
			}
		
		if message != None:
			request.goal = { "goal": "comment-preview" }
		else:
			request.goal = { "goal": "comment-nomessage" }

		return render_to_response('popvox/billcomment_preview.html', {
				'bill': bill,
				"position": position,
				"message": message,
				"email": request.session["comment-default-address"][3] if "comment-default-address" in request.session and type(request.session["comment-default-address"]) == tuple else "",
				"singlesignon_next": reverse(billcomment, args=[congressnumber, billtype, billnumber, "/finish"])
			}, context_instance=RequestContext(request))
		
	elif "submitmode" in request.POST and request.POST["submitmode"] == "< Go Back":
		# After clicking Preview, the user can go back and edit.
		request.goal = { "goal": "comment-revise" }
		return render_to_response('popvox/billcomment_start.html', {
				'bill': bill,
				"position": position,
				"message": request.POST["message"],
			}, context_instance=RequestContext(request))
		
	elif ("submitmode" in request.POST and request.POST["submitmode"] == "Next >") or (not "submitmode" in request.POST and position_original == "/finish"):
		if "submitmode" in request.POST:
			# User was already logged in and is just clicking to continue.
			message = request.POST.get("message", None)
		else:
			# User is returning from a login. Get the message info from the saved session.
			# OR user is coming from the last stage of the write congress widget
			message = request.session[pending_comment_session_key]["message"]

		request.goal = { "goal": "comment-addressform" }
		
		if address_record == None and "comment-default-address" in request.session:
			if type(request.session["comment-default-address"]) == PostalAddress:
				address_record = request.session["comment-default-address"]
			else:
				import writeyourrep.district_lookup
				address_record = PostalAddress()
				address_record.firstname = request.session["comment-default-address"][0]
				address_record.lastname = request.session["comment-default-address"][1]
				address_record.zipcode = request.session["comment-default-address"][2]
				address_record.state = writeyourrep.district_lookup.get_state_for_zipcode(address_record.zipcode)
			del request.session["comment-default-address"]
			
		return render_to_response('popvox/billcomment_address.html', {
				'bill': bill,
				"position": position,
				"message": message,
				"useraddress": address_record,
				"useraddress_fixed": address_record_fixed,
				"useraddress_prefixes": PostalAddress.PREFIXES,
				"useraddress_suffixes": PostalAddress.SUFFIXES,
				"useraddress_states": govtrack.statelist,
				"captcha": captcha_html() if require_captcha else "",
			}, context_instance=RequestContext(request))

	elif request.POST["submitmode"] == "Use a Map >":
		request.goal = { "goal": "comment-address-map" }
		
		address_record = PostalAddress()
		address_record.user = request.user
		address_record.load_from_form(request.POST, validate=False)
		
		from writeyourrep.district_metadata import get_viewport
		bounds = get_viewport(address_record)
        
		return render_to_response('popvox/billcomment_address_map.html', {
			'bill': bill,
			"position": position,
			"message": request.POST["message"],
			"useraddress": address_record,
			"useraddress_prefixes": PostalAddress.PREFIXES,
			"useraddress_suffixes": PostalAddress.SUFFIXES,
			"useraddress_states": govtrack.statelist,
			"bounds": bounds,
			}, context_instance=RequestContext(request))
			
	elif request.POST["submitmode"] == "Submit Comment >" or request.POST["submitmode"] == "Clear Comment >":
		if position == "0":
			# Clear the user's comment on this bill.
			request.goal = { "goal": "comment-clear" }
			request.user.comments.filter(bill = bill).delete()
			return HttpResponseRedirect("/home")
		
		request.goal = { "goal": "comment-submit-error" }
		
		message = request.POST["message"].strip()
		if message == "":
			message = None
		
		# Validation.
		
		if not request.user.is_authenticated():
			raise Http404()
		if request.user.userprofile.is_leg_staff():
			return HttpResponse("Legislative staff cannot post comments on legislation.")
		if request.user.userprofile.is_org_admin():
			return HttpResponse("Organization staff cannot post comments on legislation.")
		
		# More validation.
		from writeyourrep.addressnorm import verify_adddress, AddressVerificationError
		try:
			# If we didn't lock the address, load it and validate it from the form.
			if address_record_fixed == None:
				address_record = PostalAddress()
				address_record.user = request.user
				address_record.load_from_form(request.POST) # throws ValueError, KeyError
				
			# We don't display a captcha when we are editing an existing comment
			# or if the user has not left many comments yet.
			if require_captcha and not "latitude" in request.POST and not DEBUG:
				validate_captcha(request) # throws ValidationException and sets recaptcha_error attribute on the exception object
				
			if request.POST.get("latitude", "") != "":
				# If the user went to the map and specified a coordinate, skip address normalization.
				address_record.latitude = float(request.POST["latitude"])
				address_record.longitude = float(request.POST["longitude"])
				
				# But we have to convert the coordinate to a district...
				from writeyourrep.district_lookup import district_lookup_coordinate
				ret = district_lookup_coordinate(address_record.longitude, address_record.latitude,)
				if ret == None or ret[0] != address_record.state:
					raise ValueError("You moved the marker to a location outside of the state indicated in your address.")
				address_record.congressionaldistrict = ret[1]
				
			elif BENCHMARKING:
				address_record.congressionaldistrict = -1

			elif address_record_fixed == None:
				# Now do verification against CDYNE to get congressional district.
				# Do this after the CAPTCHA to prevent any abuse.

				# if the address matches a previously entered address, don't recompute the district
				# (especially if we manually overrode it) --- it was probably a resubmission of
				# their last address that we provided as default values.
				for other in request.user.postaladdress_set.all():
					if address_record.nameprefix == other.nameprefix and address_record.firstname == other.firstname and address_record.lastname == other.lastname and address_record.namesuffix == other.namesuffix and address_record.address1.lower() == other.address1.lower() and address_record.address2.lower() == other.address2.lower() and address_record.city.lower() == other.city.lower() and address_record.state == other.state and address_record.zipcode == other.zipcode and address_record.phonenumber == other.phonenumber:
						address_record = other
						break
				else:
					verify_adddress(address_record)
		
		except Exception, e:
			import sys
			sys.stderr.write("leaving comment failed> " + unicode(e) + "\n")
			request.goal = { "goal": "comment-address-error" }
			return render_to_response('popvox/billcomment_address.html', {
				'bill': bill,
				"position": position,
				"message": request.POST["message"],
				"useraddress": address_record,
				"useraddress_fixed": address_record_fixed,
				"useraddress_prefixes": PostalAddress.PREFIXES,
				"useraddress_suffixes": PostalAddress.SUFFIXES,
				"useraddress_states": govtrack.statelist,
				"captcha": captcha_html(getattr(e, "recaptcha_error", None)) if require_captcha else "",
				"error": validation_error_message(e), # accepts ValidationError, KeyError, ValueError
				"error_is_validation": isinstance(e, AddressVerificationError),
				}, context_instance=RequestContext(request))
		
			
		# Set the user's comment on this bill.
		
		request.goal = { "goal": "comment-submit" }

		# If the user came by a short URL to this bill, store the owner of
		# the short URL as the referrer on the comment.
		referrer = None
		campaign = None
		if "comment-referrer" in request.session and type(request.session["comment-referrer"]) == dict and request.session["comment-referrer"]["bill"] == bill.id:
			rx = request.session["comment-referrer"]
			
			referrer = rx.get("referrer", None)
			
			if "shorturl" in rx:
				import shorturl.models
				surl = shorturl.models.Record.objects.get(id=rx["shorturl"])
				surl.increment_completions()
				
			if "campaign" in rx:
				try: # sac/bill mismatch, ocp deleted?
					campaign = ServiceAccountCampaign.objects.get(id=rx["campaign"], bill=bill)
				except:
					pass
				
			del request.session["comment-referrer"]

		save_user_comment(request.user, bill, position, referrer, message, address_record, campaign, UserComment.METHOD_SITE)
			
		# Clear the session state set in the preview. Don't clear until the end
		# because if the user is redirected back to ../finish we need the session
		# state to get the position.
		try:
			del request.session[pending_comment_session_key]
		except:
			pass
		
		return HttpResponseRedirect(bill.url() + "/comment/share")
			
	elif request.POST["submitmode"] == "Create Account >":
		# The user is creating an account.
			
		from registration.helpers import validate_username, validate_password, validate_email
		from profile import RegisterUserAction
		
		errors = { }
		username = validate_username(request.POST["createacct_username"], fielderrors = errors)
		password = validate_password(request.POST["createacct_password"], fielderrors = errors)
		email = validate_email(request.POST["createacct_email"], fielderrors = errors)

		if len(errors) > 0:
			request.goal = { "goal": "comment-register-error" }
			return render_to_response('popvox/billcomment_preview.html', {
					'bill': bill,
					"position": position,
					"message": request.POST["message"],
					"singlesignon_next": reverse(billcomment, args=[congressnumber, billtype, billnumber, "/finish"]),
					"username": request.POST["createacct_username"],
					"password": request.POST["createacct_password"],
					"email": request.POST["createacct_email"],
					"newaccount_error": errors,
				}, context_instance=RequestContext(request))
			
		else:
			# If no errors, begin the email verification process which will
			# delay the comment.

			axn = DelayedCommentAction()
			axn.registrationinfo = RegisterUserAction()
			axn.registrationinfo.email = email
			axn.registrationinfo.username = username
			axn.registrationinfo.password = password
			axn.bill = bill.id
			axn.comment_session_state = {
				"bill": bill.url(),
				"position": position,
				"message": request.POST["message"]
				}
			
			r = send_email_verification(email, None, axn, send_email=not BENCHMARKING)
			
			request.goal = { "goal": "comment-register-start" }

			# for BENCHMARKING, we want to get the activation link directly
			if BENCHMARKING:
				return HttpResponse(r.url(), mimetype="text/plain")

			return HttpResponseRedirect("/accounts/register/check_inbox?email=" + urllib.quote(email))
	
	else:
		raise Http404()

def save_user_comment(user, bill, position, referrer, message, address_record, campaign, method):
	# If a comment exists, update that record.
	comment = None
	for c in user.comments.filter(bill = bill):
		if comment == None:
			comment = c
		else:
			# If we see more than one, we'll update the first and delete the rest.
			c.delete()
	
	# If we're not updating an existing comment record, then create a new one.
	if comment == None:
		comment = UserComment()
		comment.user = user
		comment.bill = bill
		comment.position = position
		comment.method = method
	
	# We're updating an existing record.
	else:
		if comment.position != position:
			comment.position = position
			# When the user switches sides, any comment diggs he previously left on the
			# other side must be cleared.
			comment.my_diggs.all().delete()
		
	comment.message = message

	if address_record.id == None: # (parsed from form, not from a fixed record)
		# If the user gives the same address as one on file for the user,
		# reuse the record.... but overwrite it with new info because
		# the user might have updated something non-meaningful or
		# we might have gotten new address info from the address
		# normalization.
		for addr in user.postaladdress_set.all():
			if address_record.equals(addr):
				address_record.id = addr.id
				break
		
		address_record.user = user
		if getattr(address_record, "created", None) == None: # I think because of pickling in the write congress
			address_record.created = datetime.now()                 # widget this gets set as null which causes exception
		address_record.save()
		
	comment.address = address_record
	comment.updated = datetime.now()
	comment.state = address_record.state
	comment.congressionaldistrict = address_record.congressionaldistrict

	if user.email.endswith("@popvox.com") or user.email.endswith(".popvox.com"):
		comment.status = UserComment.COMMENT_HOLD
	elif comment.status in (UserComment.COMMENT_REJECTED, UserComment.COMMENT_REJECTED_STOP_DELIVERY):
		comment.status = UserComment.COMMENT_REJECTED_REVISED
	else:
		comment.status = UserComment.COMMENT_NOT_REVIEWED

	comment.save()
	
	if referrer != None:
		UserCommentReferral.create(comment, referrer)
	
	if campaign != None:
		campaign.add_action_record(
			email = user.email,
			firstname = address_record.firstname,
			lastname = address_record.lastname,
			zipcode = address_record.zipcode,
			completed_comment = comment,
			completed_stage = "finished")
		
	return comment
				
@csrf_protect_if_logged_in
def billshare(request, congressnumber, billtype, billnumber, vehicleid, commentid = None):
	bill = getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)
	
	# Get the user's comment.
	user_position = None
	if commentid != None:
		comment = get_object_or_404(UserComment, id=int(commentid))
		if request.user.is_authenticated():
			try:
				user_position = request.user.comments.get(bill=bill)
			except:
				pass
	else:
		if not request.user.is_authenticated():
			return HttpResponseRedirect(bill.url())
		comment = request.user.comments.filter(bill = bill)
		if len(comment) == 0:
			return HttpResponseRedirect(bill.url())
		comment = comment[0]

	# Default message text from saved session state.
	message = None
	includecomment = True
	try:
		message, includecomment = request.session["billshare_share.state"]
		del request.session["billshare_share.state"]
	except:
		pass

	# What social auth is available?
	
	twitter = None
	try:
		twitter = request.user.singlesignon.get(provider="twitter")
	except:
		pass
	
	facebook = None
	try:
		facebook = request.user.singlesignon.get(provider="facebook")
	except:
		pass
	
	# Referral?
	
	welcome = None
	if "shorturl" in request.session and request.session["shorturl"].target == comment:
		surl = request.session["shorturl"]
		request.session["comment-referrer"] = {"bill": bill.id, "referrer": surl.owner, "shorturl": surl.id}
		welcome = comment.user.username + " is using POPVOX to send their message to Congress. He or she left this comment on " + bill.displaynumber() + "."
		del request.session["shorturl"] # so that we don't indefinitely display the message

	comment_rejected = False
	if comment.status > UserComment.COMMENT_ACCEPTED and (not request.user.is_authenticated() or (not request.user.is_staff and not request.user.is_superuser)):
		comment_rejected = True

	# ADD ME IN
	#if "follow_up" in request.session:
	#	del request.session["follow_up"]

	return render_to_response(
			'popvox/billcomment_share.html' if commentid == None else 'popvox/billcomment_view.html', {
			'bill': bill,
			"comment": comment,
			"message": message,
			"includecomment": includecomment,
			"twitter": twitter,
			"facebook": facebook,
			"user_position": user_position,
			"welcome": welcome,
			"SITE_ROOT_URL": SITE_ROOT_URL,
		}, context_instance=RequestContext(request))

def send_mail2(subject, message, from_email, recipient_list, fail_silently=False):
	from django.core.mail import EmailMessage
	msg = EmailMessage(
		subject = subject,
		body = message,
		from_email = SERVER_EMAIL,
		to = recipient_list,
		headers = {"From": from_email})
	msg.send(fail_silently=fail_silently)

@csrf_protect_if_logged_in # getting a link doesn't require being logged in
@json_response
def billshare_share(request):
	try:
		comment = UserComment.objects.get(id = int(request.POST["comment"]))
		if comment.status not in (UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED):
			return { "status": "fail", "msg": "This comment cannot be shared." }
	except:
		return { "status": "fail", "msg": "Invalid call." }
	
	bill = comment.bill
	
	# There are three factors that affect how we share this comment:
	#
	# 1. a) The comment has no message.
	#     b) This is the user's own comment but he has chosen to share it anonymously
	#          (via includecomment=0), which works similarly to (a).
	#     c) The user is sharing his own comment.
	#     d) The user is sharing someone else's comment.
	#
	# 2. a) The comment was written during the normal bill commenting period.
	#     b) The comment was written in support of reintroduction of the bill.
	#     (These only apply to 1c/d.)
	#
	# 3. a) The bill is still alive, so it is a call for normal action.
	#     b) The bill is dead and the comment is in support, so it is a call to reintroduce.
	#     c) The bill is dead and the comment was against, so it is not a call for action.
		
	if comment.message == None or (request.user == comment.user and request.POST["includecomment"] == "0"): # 1a/b
		includecomment = False
		target = comment.bill
		
		if comment.bill.isAlive(): # 3a
			if comment.position == "+":
				subject = "Support"
			elif comment.position == "-":
				subject = "Oppose"
		elif comment.bill.died() and comment.position == "+":  # 3b
			subject = "Support the reintroduction of"
		else: # 3c
			subject = "Take a look at"
		
		message = comment.bill.title
		
	else: # 1c/d
		includecomment = True
		target = comment
		
		if request.user == comment.user: # 2
			subject = "I " + comment.verb(tense="past")
			message = comment.message
		else:
			subject = "Check out this message " + comment.verb(tense="ing")
			message = comment.user.username + " wrote:\n\n" + comment.message
	
	subject += " " + truncatewords(comment.bill.title, 10) + " at POPVOX"
	
	import shorturl
	if not request.user.is_authenticated():
		surlrec, created = shorturl.models.Record.objects.get_or_create(target=target)
	else:
		surlrec, created = shorturl.models.Record.objects.get_or_create(owner=request.user, target=target)
	url = surlrec.url()
	
	if request.POST["method"] == "email":
		# validate and clean the email addresses
		from django.forms import EmailField
		emails = []
		for em in re.split("[\s,]+", request.POST["emails"]):
			if em.strip() == "":
				continue
			try:
				emails.append( EmailField().clean(em) )
			except:
				return { "status": "fail", "msg": "Email address(es) don't look right." }
		
		if len(emails) > 10:
			return { "status": "fail", "msg": "You can only share your message with 10 recipients at a time." }
		
		###
		body = """Hi!
	
%s

%s

Go to %s to have your voice be heard!""" % (
			request.POST["message"],
			message,
			url)
		###

		for em in emails:
			send_mail2(
				subject = subject,
				message = body,
				from_email = request.user.email,
				recipient_list = [em],
				fail_silently = True)

		return { "status": "success", "msg": "Message sent." }

	elif request.POST["method"] == "twitter":
		tweet = ""
		if not bill.hashtag() in request.POST["message"]:
			tweet += " " + bill.hashtag()
		tweet += " " + url
		if request.user == comment.user and includecomment:
			tweet += " #" + comment.address.state + str(comment.address.congressionaldistrict)
		tweet = request.POST["message"][0:140-len(tweet)] + tweet # trim msg so total <= 140 but we don't cut off the important bits at the end, like the url
		
		tok = request.user.singlesignon.get(provider="twitter").auth_token
		
		import oauthtwitter
		twitter = oauthtwitter.OAuthApi(
			TWITTER_OAUTH_TOKEN, TWITTER_OAUTH_TOKEN_SECRET,
			token = tok["oauth_token"], token_secret = tok["oauth_token_secret"])
		
		# TODO: we might want to set in_reply_to_status_id in the call to something interesting, like if this comment's referrer is a user and the user commented on the same bill, and tweeted, then that tweet_id.
		ret = twitter.UpdateStatus(tweet.encode('utf-8'))
		if type(ret) == urllib2.HTTPError and ret.code == 401:
			request.session["billshare_share.state"] = request.POST["message"], includecomment
			return { "status": "fail", "error": "not-authorized" }
		if type(ret) != dict:
			return { "status": "fail", "msg": unicode(ret) }
		if "error" in ret:
			return { "status": "fail", "msg": ret["error"] }
		
		if request.user == comment.user:
			comment.tweet_id = ret["id"]
			comment.save()
		
		return { "status": "success", "msg": "Tweet sent: " + tweet, "url": url }

	elif request.POST["method"] == "facebook":
		fb = request.user.singlesignon.get(provider="facebook")
		
		ret = urllib.urlopen("https://graph.facebook.com/" + str(fb.uid) + "/feed",
			urllib.urlencode({
				"access_token": fb.auth_token["access_token"],
				"link": url,
				"name": subject.encode('utf-8'),
				"caption": "Voice your opinion on this bill at POPVOX.com",
				"description": message.encode('utf-8'),
				"message": request.POST["message"].encode('utf-8')
				}))
		
		if ret.getcode() in (400, 403):
			request.session["billshare_share.state"] = request.POST["message"], includecomment
			return { "status": "fail", "error": "not-authorized", "scope": "publish_stream" }
		if ret.getcode() != 200:
			import sys
			sys.stderr.write("post failed> " + ret.read() + "\n")
			return { "status": "success", "msg": "Post failed (" + str(ret.getcode()) + ")" }
		ret = json.loads(ret.read())
		
		if request.user == comment.user:
			comment.fb_linkid = ret["id"]
			comment.save()

		return { "status": "success", "msg": "A link has been posted on your Wall.", "url": url }

	elif request.POST["method"] == "link":
		return { "status": "success", "msg": "Here is a link.", "url": url }

def billcomment_moderate(request, commentid, action):
	if not request.user.is_authenticated() or (not request.user.is_staff and not request.user.is_superuser):
		raise Http404()
		
	from django.core.mail import EmailMessage
	
	comment = UserComment.objects.get(id = commentid)

	if comment.moderation_log == None:
		comment.moderation_log = ""
	comment.moderation_log = \
		unicode(datetime.now()) + " " + request.user.username \
		+ " set status to " +action + "\n" \
		+ request.GET.get("log", "") + "\n\n" \
		+ (comment.message if comment.message != None else "[no message]") \
		+ "\n\n" + comment.moderation_log
		
	if comment.status == UserComment.COMMENT_NOT_REVIEWED:
		if action in ("reject", "reject-stop-delivery"):
			if action == "reject":
				comment.status = UserComment.COMMENT_REJECTED
			elif action == "reject-stop-delivery":
				comment.status = UserComment.COMMENT_REJECTED_STOP_DELIVERY
				
			comment.save()
			
			msg = EmailMessage(
				subject = "Your comment on " + comment.bill.displaynumber() + " at POPVOX needs to be revised",
				body = """Dear %s,

After reviewing the comment you left on POPVOX about the bill %s, we have
decided that it violates our guidelines for acceptable language. Comments
may not be profane, harassing, or threatening to others and may not include the
personal, private information of others. For our full guidelines, please see:

  https://www.popvox.com/legal

At this time, your comment has been hidden from the legislative reports that other
users see, and it may not be delivered to Congress.

We encourage you to revise your comment so that it meets our guidelines. After
you revise your comment, we will review it and hope to post it back on POPVOX.
You can revise your comment by following this link:

  https://www.popvox.com/home

Thank you,

POPVOX

(Please note that our decision is final.) 
""" % (comment.user.username, comment.bill.displaynumber()),
				from_email = SERVER_EMAIL,
				to = [comment.user.email])
			msg.send(fail_silently=True)
	
	if comment.status == UserComment.COMMENT_REJECTED_REVISED:
		if action == "accept":
			comment.status = UserComment.COMMENT_ACCEPTED
			comment.save()
			msg = EmailMessage(
				subject = "Your revised comment on " + comment.bill.displaynumber() + " at POPVOX has been accepted",
				body = """Dear %s,

After reviewing the revisions you made to the comment you left on POPVOX
about the bill %s, we have decided to restore your comment. Thank you
for taking the time to follow our language guidelines. Your comment now
appears on bill reports and other pages of POPVOX.

Thank you,

POPVOX
""" % (comment.user.username, comment.bill.displaynumber()),
				from_email = SERVER_EMAIL,
				to = [comment.user.email])
			msg.send(fail_silently=True)
			
	return HttpResponseRedirect(comment.url())

def get_default_statistics_context(user, individuals=True):
	default_state = None
	default_district = None
	if user.is_authenticated():
		if user.userprofile.is_leg_staff():
			member = govtrack.getMemberOfCongress(user.legstaffrole.member_id)
			if member["current"]:
				default_state = member["state"]
				if member["type"] == "rep":
					default_district = member["district"]
		elif individuals:
			addresses = user.postaladdress_set.order_by("-created")
			if len(addresses) > 0:
				default_state = addresses[0].state
				default_district = addresses[0].congressionaldistrict
	return default_state, default_district

@csrf_protect_if_logged_in
def billreport(request, congressnumber, billtype, billnumber, vehicleid):
	bill = getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)

	if not request.user.is_anonymous():
		import home
		home.annotate_track_status(request.user.userprofile, [bill])

	default_state, default_district = get_default_statistics_context(request.user, individuals=False)
					
	orgs_support = { }
	orgs_oppose = { }
	orgs_neutral = { }
	orgs_other = { }
	for pos in bill.campaign_positions():
		if pos.campaign.org.id == 2123:
			lst = orgs_other
		elif pos.position == "+":
			lst = orgs_support
		elif pos.position == "-":
			lst = orgs_oppose
		else:
			lst = orgs_neutral
		if not pos.campaign.org in lst:
			lst[pos.campaign.org] = {
				"has_document": pos.campaign.org.documents.filter(bill=bill).exists(),
				}
	orgs_support = list(orgs_support.items())
	orgs_oppose = list(orgs_oppose.items())
	orgs_neutral = list(orgs_neutral.items())
	orgs_other = list(orgs_other.items())
	for lst in orgs_support, orgs_oppose, orgs_neutral, orgs_other:
		lst.sort(key = lambda x : x[0].name.replace("The ", ""))

	bot_comments = []
	if hasattr(request, "ua") and (request.ua["typ"] in "Robot" or request.ua["ua_family"] in "cURL"):
		limit = 50
		pro_comments = bill_comments(bill, position="+").filter(message__isnull = False, status__in=(UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED))[0:limit]
		con_comments = bill_comments(bill, position="-").filter(message__isnull = False, status__in=(UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED))[0:limit]
		bot_comments = list(pro_comments) + list(con_comments)

	return render_to_response('popvox/bill_report.html', {
			'bill': bill,
			"orgs_supporting": orgs_support,
			"orgs_opposing": orgs_oppose,
			"orgs_neutral": orgs_neutral,
			"orgs_other": orgs_other,
			"default_state": default_state if default_state != None else "",
			"default_district": default_district if default_district != None else "",
			"stateabbrs": 
				[ (abbr, govtrack.statenames[abbr]) for abbr in govtrack.stateabbrs],
			"statereps": getStateReps(),
			"bot_comments": bot_comments,
		}, context_instance=RequestContext(request))

def can_appreciate(request, bill):
	# Can I appreciate comments? Only if I've weighed in on this bill and
	# then only on the side I've weighed in on, or if I'm leg staff. Returns
	# None if the user cannot appreciate any comments, True if the user
	# can appreciate all comments, or the user's comment if he is restricted
	# to commenting on the same side.
	if request.user.is_authenticated():
		if request.user.userprofile.is_leg_staff():
			return True
		comments = request.user.comments.filter(bill = bill)
		if len(comments) > 0:
			return comments[0]
	return False

@json_response
def billreport_getinfo(request, congressnumber, billtype, billnumber, vehicleid):
	# Get report information.
	
	bill = getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)
	
	state = request.REQUEST["state"] if "state" in request.REQUEST and request.REQUEST["state"].strip() != "" else None
	
	district = int(request.REQUEST["district"]) if state != None and "district" in request.REQUEST and request.REQUEST["district"].strip() != "" else None
	
	start = int(request.REQUEST.get("start", "0"))
	limit = int(request.REQUEST.get("count", "50"))
	
	def fetch(p):
		cache_key = ("billreport_getinfo_%d,%s,%s,%s,%d,%d" % (bill.id, p, state, str(district), start, limit))
		ret = cache.get(cache_key)
		if ret != None: return ret
		
		q = bill_comments(bill, position=p, state=state, congressionaldistrict=district)\
			.filter(message__isnull = False, status__in=(UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED))\
			.only("id", "created", "updated", "message", "position", "state", "congressionaldistrict", "bill__id", "bill__congressnumber", "bill__billtype", "bill__billnumber", "user__username")\
			.order_by("-created")
		limited = False
		if q.count() > limit:
			q = q[start:limit]
			limited = True
		else:
			q = q[start:]
			
		cache.set(cache_key, (q,limited), 60*2) # cache results for two minutes
			
		return q, limited
	
	pro_comments, pro_limited = fetch("+")
	con_comments, con_limited = fetch("-")
	
	comments = list(pro_comments) + list(con_comments)
	comments.sort(key = lambda x : x.updated, reverse=True)
	
	if state == None:
		reporttitle = "Legislative Report for POPVOX Nation"
	elif district == None or district == 0:
		reporttitle = "Legislative Report for " +  govtrack.statenames[state]
	else:
		reporttitle = "District Report for " + state + "-" + str(district)
	
	reportsubtitle = ""
	if state != None:
		reportsubtitle = \
			"Represented by " \
			+ re.sub(r"\[[^\]]*\]", "", 
				" and ".join(
					[p["name"] for p in 
						getMembersOfCongressForDistrict(state + str(district),
							moctype="rep" if district != None else "sen")]
					)
				)
			
	# Functions for formatting comments.
	
	t = re.escape(bill.title).replace(":", ":?")
	re_because = re.compile(r"I (support|oppose) " + t + r" because[\s\.:]*(\S)") # remove common text
	re_because_repl = lambda x : x.group(2).upper()
	re_whitespace = re.compile(r"\n+\W*$") # remove trailing non-textual characters
	def msg(m):
		m = re_because.sub(re_because_repl, m)
		m = re_whitespace.sub("", m)
		return m

	from django.contrib.humanize.templatetags.humanize import ordinal
	def location(c):
		if district != None:
			return None
		if state != None:
			return "Congressional District " + str(c.congressionaldistrict)
		if c.congressionaldistrict > 0:
			return statenames[c.state] + "'s " + ordinal(c.congressionaldistrict) + " District"
		return statenames[c.state] + " At Large"

	bill_end_congress = govtrack.getCongressDates(bill.congressnumber)[1]
	def verb(c):
		if c.created.date() <= bill_end_congress:
			if c.position == "+": return "supported"
			return "opposed"
		else:
			if c.position == "+": return "supported the reintroduction of"
			return "opposed the reintroduction of"

	# Appreciation

	# Can the user appreciate comments?
	appreciate = can_appreciate(request, bill)
	if type(appreciate) == UserComment:
		appreciate = appreciate.position
	elif appreciate:
		appreciate = "both"
	else:
		appreciate = "none"

	# Get the user's current set of appreciated comments, rather than query on each comment
	# if the user appreciated it.
	user_appreciated = set()
	if request.user.is_authenticated():
		for c in UserComment.objects.filter(diggs__diggtype=UserCommentDigg.DIGG_TYPE_APPRECIATE, diggs__user=request.user):
			user_appreciated.add(c.id)
	
	# Pre-load the count of num_appreciations.
	num_appreciations = {}
	q = UserCommentDigg.objects.filter(
		comment__id__in = [c.id for c in comments],
		diggtype = UserCommentDigg.DIGG_TYPE_APPRECIATE)\
		.values("comment")\
		.annotate(num_diggs=Count("id"))\
		.values("comment_id", "num_diggs")
	for c in q:
		num_appreciations[c["comment_id"]] = c["num_diggs"]
			
	# Return.
	
	bill_url = bill.url()
	
	debug_info = None
	if DEBUG:
		from django.db import connection
		debug_info = "".join(["%s: %s\n" % (q["time"], q["sql"]) for q in connection.queries])

	return {
		"reporttitle": reporttitle,
		"reportsubtitle": reportsubtitle,
		
		"can_appreciate": appreciate,
		
		"pro_more": pro_limited,
		"con_more": con_limited,
		
		"debug_info": debug_info,
	
		"comments":
			[ {
				"id": c.id,
				"user": c.user.username,
				"msg": msg(c.message),
				"location": location(c),
				"date": formatDateTime(c.updated),
				"pos": c.position,
				"share": bill_url + "/comment/" + str(c.id), #c.url(),
				"verb": verb(c), #c.verb(tense="past"),
				"appreciates": num_appreciations[c.id] if c.id in num_appreciations else 0,
				"appreciated": c.id in user_appreciated,
				} for c in comments ],
		"stats": {
			"overall": bill_statistics(bill, "POPVOX", "POPVOX Nation", want_timeseries=True),
			"state": bill_statistics(bill,
				state,
				govtrack.statenames[state],
				want_timeseries=True,
				state=state)
					if state != None else None,
			"district": bill_statistics(bill,
				state + "-" + str(district),
				state + "-" + str(district),
				want_timeseries=True,
				state=state,
				congressionaldistrict=district)
					if state != None and district not in (None, 0) else None
		}
	}

@csrf_protect
@json_response
def comment_digg(request):
	bill = get_object_or_404(Bill, id=request.POST.get("bill", -1))
	comment = get_object_or_404(UserComment, id=request.POST.get("comment", -1))
	
	appreciate = can_appreciate(request, bill)
	if not appreciate or (type(appreciate) == UserComment and appreciate.position != comment.position):
		return { "status": "fail", "msg": "invalid action" }
		
	d = UserCommentDigg.objects.filter(comment=comment, diggtype=UserCommentDigg.DIGG_TYPE_APPRECIATE, user=request.user)
	if request.POST["action"] == "-":
		d.delete()
		action = "-"
	else:
		if len(d) == 0:
			d = UserCommentDigg(
				comment=comment,
				diggtype=UserCommentDigg.DIGG_TYPE_APPRECIATE,
				user=request.user)
			if type(appreciate) == UserComment:
				d.source_comment = appreciate
			d.save()
		action = "+"
		
	return { "status": "success", "action": action, "count": UserCommentDigg.objects.filter(comment=comment, diggtype=UserCommentDigg.DIGG_TYPE_APPRECIATE).count() }

@json_response
def getbillshorturl(request):
	if "billposid" in request.POST:
		pos = get_object_or_404(OrgCampaignPosition, id=request.POST["billposid"])
		
		org = pos.campaign.org
		if not org.is_admin(request.user) :
			return HttpResponseForbidden("Not authorized.")
			
		owner = pos.campaign
		bill = pos.bill
	elif "billid" in request.POST:
		if request.user.is_authenticated():
			owner = request.user
		else:
			owner = None
		bill = get_object_or_404(Bill, id=request.POST["billid"])
	else:
		raise Http404()
	
	import shorturl
	surl, created = shorturl.models.Record.objects.get_or_create(owner=owner, target=bill)
	
	return { "status": "success", "url": surl.url(), "new": created }

def uploaddoc1(request):
	prof = request.user.userprofile
	
	if request.user.is_anonymous():
		raise Http404()
	elif prof.is_leg_staff() and request.user.legstaffrole.member != None:
		types = ((0, "Press Release"), (1, "Introductory Statement"), (2, "Dear Colleague"), (99, "Other Document"))
		whose = request.user.legstaffrole.bossname
		docs = request.user.legstaffrole.member.documents
	elif "org" in request.GET:
		org = Org.objects.get(slug=request.GET["org"])
		if not org.is_admin(request.user):
			raise Http404()
		types = ((0, "Press Release"), (3, "Report"), (4, "Letter to Congress"), (5, "Coalition Letter"), (99, "Other Document"))
		whose = org.name
		docs = org.documents
	else:
		raise Http404()
		
	return types, whose, docs

@csrf_protect
@login_required
def uploaddoc(request, congressnumber, billtype, billnumber, vehicleid):
	types, whose, docs = uploaddoc1(request)
		
	bill = getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)
	
	# check which documents are already uploaded
	types = [
		(typecode, typename, docs.filter(bill=bill, doctype=typecode).exists())
		for (typecode, typename) in types]
	
	return render_to_response('popvox/bill_uploaddoc.html', {
		'whose': whose,
		'types': types,
		'bill': bill,
		}, context_instance=RequestContext(request))

@login_required
@json_response
def getdoc(request):
	types, whose, docs = uploaddoc1(request)
		
	bill = get_object_or_404(Bill, id=request.POST["billid"])
	
	doctype = int(request.POST["doctype"])

	try:
		doc = docs.get(bill = bill, doctype = doctype)
		return { "title": doc.title, "text": doc.text, "link": doc.link, "updated": doc.updated.strftime("%x") }
	except:
		return { "status": "doesnotexist" }

@csrf_protect
@login_required
@json_response
def uploaddoc2(request):
	types, whose, docs = uploaddoc1(request)
	
	bill = get_object_or_404(Bill, id=request.POST["billid"])
	doctype = int(request.POST["doctype"])
	
	if request.POST.get("title", "").strip() == "" and strip_tags(request.POST.get("text", "").replace("&nbsp;", "")).strip() == "" and request.POST.get("link", "").strip() == "":
		try:
			doc = docs.get(bill = bill, doctype = doctype)
			doc.delete()
			return { "status": "success", "action": "delete" }
		except:
			# If there was no document to delete, then fall through because the user must be intenting to save...
			pass

	title = forms.CharField(min_length=5, max_length=128, error_messages = {'min_length': "The title is too short.", "max_length": "The title is too long.", "required": "The title is required."}).clean(request.POST.get("title", "")) # raises ValidationException
		
	text = forms.CharField(min_length=100, max_length=32767, error_messages = {'min_length': "The body text is too short.", "max_length": "The body text is too long.", "required": "The document text is required."}).clean(request.POST.get("text", "")) # raises ValidationException
	text = sanitize_html(text)
	
	link = request.POST.get("link", "")	
	if link != "" and link[0:7] != "http://":
		link = "http://" + link
	link = forms.URLField(required=False, verify_exists = True).clean(link) # raises
	
	if request.POST["validate"] != "validate":
		doc, is_new = docs.get_or_create(
			bill = bill,
			doctype = doctype)
		doc.title = title
		doc.text = text
		doc.link = link
		doc.save()
	
	return { "status": "success", "action": "upload" }

def billdoc(request, congressnumber, billtype, billnumber, vehicleid, orgslug, doctype):
	bill = getbill(congressnumber, billtype, billnumber, vehicleid=vehicleid)
	
	from org import set_last_campaign_viewed
	org = get_object_or_404(Org, slug=orgslug, visible=True)
	set_last_campaign_viewed(request, org)
	
	try:
		doc = org.documents.get(bill=bill, doctype=doctype)
	except:
		raise Http404()
		
	return render_to_response('popvox/bill_doc_org.html', {
		'org': org,
		'bill': bill,
		'doc': doc,
		'admin': org.is_admin(request.user),
		'docupdated': doc.updated.strftime("%b %d, %Y %I:%M %p"),
		}, context_instance=RequestContext(request))

