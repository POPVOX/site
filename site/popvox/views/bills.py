from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.views.generic.simple import direct_to_template
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from django import forms
from django.core.urlresolvers import reverse

from jquery.ajax import json_response, ajax_fieldupdate_request, sanitize_html, validation_error_message

import re
from xml.dom import minidom
import urllib
import datetime
import json

from popvox.models import *
from registration.helpers import captcha_html, validate_captcha
from popvox.govtrack import CURRENT_CONGRESS, getMembersOfCongressForDistrict, open_govtrack_file
from emailverification.utils import send_email_verification
from utils import formatDateTime

from settings import TWITTER_OAUTH_TOKEN, TWITTER_OAUTH_TOKEN_SECRET

popular_bills = None
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

def issuearea_chooser_list(request):
	# TODO: Cache.
	return render_to_response('popvox/issueareachooser_list.html', {'issues': getissueareas()}, context_instance=RequestContext(request))	

def bills(request):
	global popular_bills

	# Get popular bills from GovTrack.
	if popular_bills == None:
		popular_bills = []
		popular_bills_xml = minidom.parse(open_govtrack_file("misc/popularbills.xml"))
		for billxml in popular_bills_xml.getElementsByTagName("bill"):
			try:
				m = re.match(r"([a-z]+)(\d+)-(\d+)", billxml.attributes["id"].value)
				bill = Bill()
				bill.congressnumber = int(m.group(2))
				bill.billtype = m.group(1)
				bill.billnumber = int(m.group(3))
				if not bill.isAlive():
					continue
				
				popular_bills.append({"congressnumber": int(m.group(2)), "billtype": m.group(1), "billnumber": int(m.group(3))})
				
				if len(popular_bills) == 15:
					break
			except:
				# Ignore invalid data from the API, skip this bill.
				pass
		
		# convert the hash objects to Bill objects
		popular_bills = getbillsfromhash(popular_bills)
		
	# Get the campaigns that support or oppose any of the bills, in batch.
	cams = OrgCampaign.objects.filter(positions__bill__in = popular_bills).select_related() # note recursive SQL which goes from OrgCampaign to Org
	
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
		billrec["orgs"] = orgs
		
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
		'popular_bills': popular_bills2,
		'hotbills': popular_bills[0:5], 
		}, context_instance=RequestContext(request))
	
def billsearch(request):
	if not "q" in request.GET or request.GET["q"].strip() == "":
		return HttpResponseRedirect("/bills")
	q = request.GET["q"].strip()
	# TODO: Cache this?
	bills = []
	status = None
	try:
		search_response = minidom.parse(urlopen("http://www.govtrack.us/congress/billsearch_api.xpd?q=" + urllib.quote(q)))
		search_response = search_response.getElementsByTagName("result")
	except:
		search_response = []
		status = "callfail"
	for billxml in search_response:
		if len(bills) == 100:
			status = "overflow"
			break
		try:
			bill = Bill()
			bill.congressnumber = int(billxml.getElementsByTagName("congress")[0].firstChild.data)
			bill.billtype = billxml.getElementsByTagName("bill-type")[0].firstChild.data
			bill.billnumber = int(billxml.getElementsByTagName("bill-number")[0].firstChild.data)
			bill.title = billxml.getElementsByTagName("title")[0].firstChild.data
			bills.append(bill)
		except:
			# Ignore invalid data from the API.
			pass
	if len(bills) == 1:
		return HttpResponseRedirect(bills[0].url())
	return render_to_response('popvox/billsearch.html', {'bills': bills, "q": q, "status": status}, context_instance=RequestContext(request))

def getbill(congressnumber, billtype, billnumber):
	# If the user requests a bill that we don't have in our database, we will still display a page for it if it's
	# actually a bill in Congress. It's just that no org has a position on it (yet).
	if int(congressnumber) < 1 or int(congressnumber) > 1000: 
		raise Http404("Invalid bill number. \"" + congressnumber + "\" is not valid.")
	try:
		billtype = [x[0] for x in Bill.BILL_TYPE_SLUGS if x[1] == billtype][0]
	except:
		raise Http404("Invalid bill number. \"" + billtype + "\" is not valid.")
	bill = Bill.objects.filter(congressnumber=congressnumber, billtype=billtype, billnumber=billnumber)
	if len(bill) == 0:
		bill = Bill()
		bill.congressnumber = int(congressnumber)
		bill.billtype = billtype
		bill.billnumber = int(billnumber)
		if not bill.is_bill():
			raise Http404("Bill does not exist.")
	else:
		bill = bill[0]
	return bill
	
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
		"title": bill.title(),
		"billstatus": bill.status_advanced(),
		"sponsor": bill.sponsor(),
		}
	
def bill_comments(bill, plusminus, **filterargs):
	def filter_null_args(kv):
		ret = { }
		for k, v in kv.items():
			if v != None:
				ret[k] = v
		return ret
	
	cc = bill.usercomments.filter(position=plusminus, **filter_null_args(filterargs))
	if len(cc) > 0:
		return cc, False
	
	# Make up comments for testing.
	import random
	lorem = []
	last_time = datetime.now()
	for i in xrange(random.randint(15, 40)):
		c = UserComment()
		c.user = User()
		c.user.username = "testuser"
		c.bill = bill
		c.position = plusminus
		c.message = plusminus + "Ut wisi enim ad minim veniam quis nostrud exerci tation ullamcorper suscipit lobortis nisl ut aliquip ex ea commodo consequat duis autem vel eum iriure dolor.\n\nIn hendrerit in vulputate velit esse molestie consequat.\n\nVel illum dolore eu feugiat nulla facilisis at vero eros et accumsan et iusto odio dignissim qui blandit praesent luptatum zzril delenit augue duis dolore te feugait nulla facilisi"
		c.created = last_time - timedelta(seconds=random.randint(0, 2*60*60)*24)
		last_time = c.created
		c.updated = c.created 
		c.status = UserComment.COMMENT_NOT_REVIEWED
		c.address = PostalAddress()
		c.address.city = "Sioux City"
		c.address.state = "XX"
		lorem.append(c)
	return lorem, True

def bill_statistics(bill, shortdescription, longdescription, **filterargs):
	# If any of the filters is None, meaning it is based on demographic info
	# that the user has not set, return None for the whole statistic group.
	for key in filterargs:
		if filterargs[key] == None:
			return None
	
	pro_comments, pro_is_random = bill_comments(bill, "+", **filterargs)
	con_comments, con_is_random = bill_comments(bill, "-", **filterargs)
	
	if pro_is_random or con_is_random:
		shortdescription += " (Simulated)"
		longdescription += " (Simulated)"
	
	pro = len(pro_comments)
	con = len(con_comments)
	if pro+con == 0:
		return None
		
	# Don't display statistics when there's very little data.
	#if pro+con < 10:
	#	return None
	
	# Get a time-series.
	firstcommentdate = None
	lastcommentdate = None
	for c in list(pro_comments) + list(con_comments):
		if firstcommentdate == None or c.updated < firstcommentdate:
			firstcommentdate = c.updated
		if lastcommentdate == None or c.updated > lastcommentdate:
			lastcommentdate = c.updated
	
	# Compute a bin size (i.e. number of days per point) that approximates
	# ten comments per day, but with a minimum size of one day.
	binsize = 1.0
	if firstcommentdate < lastcommentdate:
		binsize = (lastcommentdate - firstcommentdate).days / float(len(pro_comments)+len(con_comments)) * 10.0
	if binsize < 1.0:
		binsize = 1.0
	
	# Bin the observations.
	bins = { }
	for c in list(pro_comments) + list(con_comments):
		days = round((c.updated - firstcommentdate).days / binsize) * binsize
		if not days in bins:
			bins[days] = { "+": 0, "-": 0 }
		bins[days][c.position] += 1
	bin_keys = list(bins.keys())
	bin_keys.sort()
	time_series = {
		"xaxis": [(firstcommentdate + timedelta(x)).strftime("%x") for x in bin_keys],
		"pro": [bins[x]["+"] for x in bin_keys],
		"con": [bins[x]["-"] for x in bin_keys]
		}

	return {"shortdescription": shortdescription, "longdescription": longdescription, "total": pro+con, "pro":pro, "con":con, "pro_pct": 100*pro/(pro+con), "con_pct": 100*con/(pro+con), "timeseries": time_series}
	
@csrf_protect
def bill(request, congressnumber, billtype, billnumber, commentid=None):
	bill = getbill(congressnumber, billtype, billnumber)
	
	# Get the organization that the user is an admin of, if any, so he can
	# have the org take a position on it.
	user_org = None
	existing_org_positions = []
	if request.user.is_authenticated() and request.user.get_profile() != None:
		user_org = request.user.orgroles.all()
		if len(user_org) == 0: # TODO down the road
			user_org = None
		else:
			user_org = user_org[0].org
			for cam in user_org.orgcampaign_set.all():
				for p in cam.positions.filter(bill = bill):
					existing_org_positions.append({"cam": cam, "position": "endorsed" if p.position == "+" else "opposed", "comment": p.comment})
		
	user_position = None
	mocs = []
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
			if bill.billtype[0] == "s":
				mocs = getMembersOfCongressForDistrict(district, moctype="sen")
			else:
				mocs = getMembersOfCongressForDistrict(district, moctype="rep")
			
	# Get the orgs who support or oppose the bill, and the relevant campaigns
	# within the orgs.
	orgs = { "+": {}, "-": {} }
	for p in bill.campaign_positions():
		cam = p.campaign
		if not cam.org.slug in orgs[p.position]:
			orgs[p.position][cam.org.slug] = {
				"name": cam.org.name,
				"url": cam.org.url(),
				"object": cam.org,
				"campaigns": [],
				"comment": None,
			}
		if cam.default or orgs[p.position][cam.org.slug]["comment"] == None:
			orgs[p.position][cam.org.slug]["comment"] = p.comment				
		if not cam.default:
			orgs[p.position][cam.org.slug]["campaigns"].append(
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
	orgs["+"] = sort_orgs(orgs["+"].values())
	orgs["-"] = sort_orgs(orgs["-"].values())
	
	# Welcome message?
	welcome = None
	welcome_tabname = None
	referral_comment = None
	referral_orgposition = None
	
	# for testing
	#from shorturl.models import Record
	#r = Record()
	#r.target = bill
	#r.owner = Org.objects.get(slug="demo")
	#request.session["shorturl"] = r
	
	if "shorturl" in request.session and request.session["shorturl"].target == bill:
		# Referral to this bill. If the link owner left a comment on the bill,
		# then we can use that comment as the basis of the welcome
		# message.
		if isinstance(request.session["shorturl"].owner, User):
			welcome = request.session["shorturl"].owner.username + " has shared with you a link to this bill that you might want to weigh in on."
			try:
				referral_comment = request.session["shorturl"].owner.comments.get(bill=bill)
				welcome_tabname = referral_comment.user.username + "'s Comment"
				welcome = referral_comment.user.username + " has shared with you a comment they left on " + bill.displaynumber() + "."
			except:
				pass
		elif isinstance(request.session["shorturl"].owner, Org):
			welcome = "Hello! " + request.session["shorturl"].owner.name + " wants to tell you about " + bill.displaynumber() + " on POPVOX.  Learn more about the issue and let POPVOX amplify your voice to Congress."
			try:
				welcome_tabname = "Organization's Position"
				referral_orgposition = OrgCampaignPosition.objects.filter(campaign__org=request.session["shorturl"].owner, bill=bill)[0]
				welcome = "Hello! " + request.session["shorturl"].owner.name + " wants you to " + ("support" if referral_orgposition.position == "+" else "oppose") + " " + bill.displaynumber() + ".  Learn more about the issue and let POPVOX amplify your voice to Congress."
			except:
				pass

	elif "shorturl" in request.session and isinstance(request.session["shorturl"].target, UserComment) and request.session["shorturl"].target.bill == bill:
		# Referral to a comment on this bill. The owner might or might not have
		# written the comment.
		referral_comment = request.session["shorturl"].target
		welcome_tabname = referral_comment.user.username + "'s Comment"
		if isinstance(request.session["shorturl"].owner, User):
			if request.session["shorturl"].owner == referral_comment.user:
				welcome = referral_comment.user.username + " has shared with you a comment they left on " + bill.displaynumber() + "."
			else:
				welcome = request.session["shorturl"].owner.username + " has shared with you a comment that user " + referral_comment.user.username + " left on " + bill.displaynumber() + "."
		elif isinstance(request.session["shorturl"].owner, Org):
			welcome = request.session["shorturl"].owner.name + " has shared with you a comment that user " + referral_comment.user.username + " left on " + bill.displaynumber() + "."
	
	elif commentid != None:
		referral_comment = UserComment.objects.get(id=int(commentid))
		welcome_tabname = referral_comment.user.username + "'s Comment"
		
	return render_to_response('popvox/bill.html', {
			'bill': bill,
			"canvote": (request.user.is_anonymous() or (not request.user.userprofile.is_leg_staff() and not request.user.userprofile.is_org_admin())),
			
			"user_org": user_org,
			"existing_org_positions": existing_org_positions,
			"lastviewedcampaign": request.session["popvox_lastviewedcampaign"] if "popvox_lastviewedcampaign" in request.session and not OrgCampaign.objects.get(id=request.session["popvox_lastviewedcampaign"]).default  else "",
			
			"user_position": user_position,
			"mocs": mocs,
			
			"stats": {
				"overall": bill_statistics(bill, "POPVOX", "POPVOX Nation"),
			},
			
			"orgs": { "support": orgs["+"], "oppose": orgs["-"] },
			
			"welcome": welcome,
			"welcome_tabname": welcome_tabname,
			"referral_comment": referral_comment,
			"referral_orgposition": referral_orgposition,
			
		}, context_instance=RequestContext(request))

pending_comment_session_key = "popvox.views.bills.billcomment__pendingcomment"

# This is an email verification callback.
class DelayedCommentAction:
	registrationinfo = None # a RegisterUserAction object
	bill = None
	position = None
	comment_session_state = None
	
	def email_subject(self):
		return "POPVOX: One More Step to Submit Your Comment"
		
	def email_body(self):
		return """Thanks for coming to POPVOX and commenting on legislation. To
finish creating your account so that your comment can be submitted,
just follow this link:

<URL>

All the best,

POPVOX"""
	
	def get_response(self, request, vrec):
		# Create the user and log the user in.
		self.registrationinfo.finish(request)
		
		# Set the session state.
		request.session[pending_comment_session_key] = self.comment_session_state
		
		# Redirect to the comment form to continue.
		request.goal = { "goal": "comment-register-registered" }
		return HttpResponseRedirect(self.bill.url() + "/comment" + self.position)

@csrf_protect
def billcomment(request, congressnumber, billtype, billnumber, position):
	position_original = position
	if position_original == None:
		position_original = ""
	
	bill = getbill(congressnumber, billtype, billnumber)
	
	address_record = None
	address_record_fixed = None
	
	# Clear out the session state for a pending comment (set e.g. if
	# user has to go away to do oauth login) if the pending comment
	# is for a different bill, or if this request is not in the finish state.
	if pending_comment_session_key in request.session and request.session[pending_comment_session_key]["bill"] != bill.url():
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
			if (datetime.now() - address_record.created).days < 60:
				address_record_fixed = "You cannot change your address for two months after entering your address."
	
	if not "submitmode" in request.POST and position_original != "/finish":
		message = ""

		request.goal = { "goal": "comment-begin" }
			
		# If the user has already saved a comment on this bill, load it up
		# as default values for the form.
		if position != "0" and request.user.is_authenticated():
			for c in request.user.comments.filter(bill = bill):
				request.goal = { "goal": "comment-edit-begin" }
				message = c.message
				break
				
		# If we have a saved session, load the saved message.
		if pending_comment_session_key in request.session:
			message = request.session[pending_comment_session_key]["message"]
	
		return render_to_response('popvox/billcomment_start.html', {
				'bill': bill,
				"position": position,
				"message": message,
			}, context_instance=RequestContext(request))
	
	elif "submitmode" in request.POST and request.POST["submitmode"] == "Preview >":
		# The user clicks preview to get a preview page, or they are returning after login.
		
		# TODO: Validate that a message has been provided and that messages are
		# not too long or too short.
		message = request.POST["message"]
		
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
			
		request.goal = { "goal": "comment-preview" }
		
		return render_to_response('popvox/billcomment_preview.html', {
				'bill': bill,
				"position": position,
				"message": message,
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
			message = request.POST["message"]
		else:
			# User is returning from a login. Get the message info from the saved session.
			message = request.session[pending_comment_session_key]["message"]
		
		return render_to_response('popvox/billcomment_address.html', {
				'bill': bill,
				"position": position,
				"message": message,
				"useraddress": address_record,
				"useraddress_fixed": address_record_fixed,
				"useraddress_prefixes": PostalAddress.PREFIXES,
				"useraddress_suffixes": PostalAddress.SUFFIXES,
				"useraddress_states": govtrack.statenamelist,
				"captcha": captcha_html() if request.user.is_anonymous() or len(request.user.comments.filter(bill = bill)) == 0 else "",
			}, context_instance=RequestContext(request))

	elif request.POST["submitmode"] == "Submit Comment >" or request.POST["submitmode"] == "Clear Comment >":
		# Clear the session state set in the preview.
		try:
			del request.session[pending_comment_session_key]
		except:
			pass
		
		if position == "0":
			# Clear the user's comment on this bill.
			request.goal = { "goal": "comment-submit" }
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
			return HttpResponse("Advocacy organization staff cannot post comments on legislation.")
		
		# More validation.
		try:
			# If we didn't lock the address, load it and validate it from the form.
			if address_record_fixed == None:
				address_record = PostalAddress()
				address_record.user = request.user
				address_record.load_from_form(request) # throws ValueError
				
			# We don't display a captcha when we are editing an existing comment.
			if len(request.user.comments.filter(bill = bill)) == 0:
				validate_captcha(request) # throws ValidationException and sets recaptcha_error attribute on the exception object
		except Exception, e:
			return render_to_response('popvox/billcomment_address.html', {
				'bill': bill,
				"position": position,
				"message": request.POST["message"],
				"useraddress": address_record,
				"useraddress_fixed": address_record_fixed,
				"useraddress_prefixes": PostalAddress.PREFIXES,
				"useraddress_suffixes": PostalAddress.SUFFIXES,
				"useraddress_states": govtrack.statenamelist,
				"captcha": captcha_html(getattr(e, "recaptcha_error", None)) if request.user.is_anonymous() or len(request.user.comments.filter(bill = bill)) == 0 else "",
				"error": validation_error_message(e)
				}, context_instance=RequestContext(request))
		
			
		# Set the user's comment on this bill.
		
		request.goal = { "goal": "comment-submit" }
		
		# If a comment exists, update that record.
		comment = None
		for c in request.user.comments.filter(bill = bill):
			if comment == None:
				comment = c
			else:
				# If we see more than one, we'll update the first and delete the rest.
				c.delete()
		
		bill.save() # make sure it is in the database
		
		# If we're not updating an existing comment record, then create a new one.
		if comment == None:
			comment = UserComment()
			comment.user = request.user
			comment.bill = bill
			comment.position = position
			
			# If the user came by a short URL to *this* bill, store the owner of
			# the short URL as the referrer on the comment.
			if "shorturl" in request.session and (request.session["shorturl"].target == bill or (hasattr(request.session["shorturl"].target, "bill") and request.session["shorturl"].target.bill == bill)) and request.session["shorturl"].owner != None:
				comment.referrer = request.session["shorturl"].owner
				request.session["shorturl"].increment_completions()
			
		comment.message = message

		if address_record.id == None: # (parsed from form, not from a fixed record)
			# If the user gives the same address as one on file for the user,
			# reuse the record.
			for addr in request.user.postaladdress_set.all():
				if address_record.equals(addr):
					address_record = addr
					break
			
			if address_record.id == None: # don't modify an existing record
				address_record.save()
			
		comment.address = address_record
		comment.save()
			
		return HttpResponseRedirect(bill.url() + "/comment/share")
			
	elif request.POST["submitmode"] == "Create Account >":
		# The user is creating an account. If the user succeeds, we
		# display the same page again under the Preview mode so the
		# user can enter their address.
			
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
			axn.bill = bill	
			axn.position = position_original
			axn.comment_session_state = {
				"bill": bill.url(),
				"position": position,
				"message": request.POST["message"]
				}
			
			send_email_verification(email, None, axn)
			
			request.goal = { "goal": "comment-register-start" }
			return HttpResponseRedirect("/accounts/register/check_inbox?email=" + urllib.quote(email))
	
	else:
		raise Http404()

@login_required
def billshare(request, congressnumber, billtype, billnumber, commentid = None):
	bill = getbill(congressnumber, billtype, billnumber)
	
	if commentid != None:
		comment = UserComment.objects.get(id=int(commentid))
	else:
		# Get the user's comment.
		if not request.user.is_authenticated():
			return HttpResponseRedirect(bill.url())
		comment = request.user.comments.filter(bill = bill)
		if len(comment) == 0:
			return HttpResponseRedirect(bill.url())
		comment = comment[0]

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
	
	return render_to_response('popvox/billcomment_share.html', {
			"mode": "post" if commentid == None else "share",
			'bill': bill,
			"comment": comment,
			"twitter": twitter,
			"facebook": facebook,
		}, context_instance=RequestContext(request))

@json_response
def billshare_share(request):
	try:
		bill = Bill.objects.get(id=request.POST["bill"])
		comment = UserComment.objects.get(id = int(request.POST["comment"]))
	except:
		return { "status": "fail", "msg": "Invalid call." }
		
	support_oppose = "support" if comment.position == "+"  else "oppose"
	support_oppose2 = "support of" if comment.position == "+"  else "opposition to"
		
	import shorturl
	surlrec, created = shorturl.models.Record.objects.get_or_create(owner=request.user, target=comment)
	url = surlrec.url()
	
	if request.POST["method"] == "email":
		emails = re.split("[\s,]+", request.POST["emails"])
		
		# validate and clean the email addresses
		from django.forms import EmailField
		for i in range(len(emails)):
			try:
				emails[i] = EmailField().clean(emails[i])
			except:
				return { "status": "fail", "msg": "Email address(es) don't look right." }
		
		if len(emails) > 10:
			return { "status": "fail", "msg": "You can only share your message with 10 recipients at a time." }
		
		# and send...
		from django.core.mail import send_mail
		for em in emails:
			if request.user == comment.user:
				send_mail(
					subject = request.user.username + " wants you to " + support_oppose + " " + bill.displaynumber() + " at POPVOX",
					message = """Hi!
		
%s

I just left this comment in %s bill %s:

%s

Go to %s to have your voice be heard!

%s""" % (request.POST["message"], support_oppose2, bill.title(), comment.message, url, request.user.username),
					from_email = '"' + request.user.username + '" <' + request.user.email + ">",
					recipient_list = [em],
					fail_silently = True)
			else:
				send_mail(
					subject = request.user.username + " suggests " + comment.user.username + "'s comment on " + bill.displaynumber() + " at POPVOX",
					message = """Hi!
				
%s

I found this comment by %s in %s bill %s:

%s

Go to %s to have your voice be heard!

%s""" % (request.POST["message"], comment.user.username, support_oppose2, bill.title(), comment.message, url, request.user.username),
					from_email = '"' + request.user.username + '" <' + request.user.email + ">",
					recipient_list = [em],
					fail_silently = True)
	
		return { "status": "success", "msg": "Message sent." }

	elif request.POST["method"] == "twitter":
		tweet = " " + bill.hashtag() + " " + url + " #" + comment.address.state + str(comment.address.congressionaldistrict)
		tweet = request.POST["message"][0:140-len(tweet)] + tweet # trim msg so total <= 140 but we don't cut off the important bits at the end, like the url
		
		tok = request.user.singlesignon.get(provider="twitter").auth_token
		
		import oauthtwitter
		twitter = oauthtwitter.OAuthApi(
			TWITTER_OAUTH_TOKEN, TWITTER_OAUTH_TOKEN_SECRET,
			token = tok["oauth_token"], token_secret = tok["oauth_token_secret"])
		
		# TODO: we might want to set in_reply_to_status_id in the call to something interesting, like if this comment's referrer is a user and the user commented on the same bill, and tweeted, then that tweet_id.
		ret = twitter.UpdateStatus(tweet)
		if type(ret) != dict:
			return { "status": "fail", "msg": unicode(ret) }
		if "error" in ret:
			return { "status": "fail", "msg": ret["error"] }
		
		comment.tweet_id = ret["id"]
		comment.save()
		
		return { "status": "success", "msg": "Tweet sent: " + tweet }

	elif request.POST["method"] == "facebook":
		fb = request.user.singlesignon.get(provider="facebook")
		
		ret = urllib.urlopen("https://graph.facebook.com/" + str(fb.uid) + "/feed",
			urllib.urlencode({
				"access_token": fb.auth_token["access_token"],
				"link": url,
				"name": bill.title(),
				"caption": "Voice your opinion on this bill at POPVOX.com",
				"description": bill.officialtitle(),
				"message": request.POST["message"]
				}))
		if ret.getcode() != 200:
			return { "status": "success", "msg": "Post failed." }
		ret = json.loads(ret.read())
		
		comment.fb_linkid = ret["id"]
		comment.save()

		return { "status": "success", "msg": "A link has been posted on your Wall." }

def get_default_statistics_context(user):
	default_state = None
	default_district = None
	if user.is_authenticated():
		if user.userprofile.is_leg_staff():
			member = govtrack.getMemberOfCongress(user.legstaffrole.member)
			if member["current"]:
				default_state = member["state"]
				if member["type"] == "rep":
					default_district = member["district"]
		else:
			addresses = user.postaladdress_set.order_by("-created")
			if len(addresses) > 0:
				default_state = addresses[0].state
				default_district = addresses[0].congressionaldistrict
	return default_state, default_district

def billreport(request, congressnumber, billtype, billnumber):
	bill = getbill(congressnumber, billtype, billnumber)

	default_state, default_district = get_default_statistics_context(request.user)
					
	orgs_support = []
	orgs_oppose = []
	for pos in bill.campaign_positions():
		lst = orgs_support if pos.position == "+" else orgs_oppose
		if not pos.campaign.org in lst:
			lst.append(pos.campaign.org)
		
	return render_to_response('popvox/bill_report.html', {
			'bill': bill,
			"orgs_supporting": orgs_support,
			"orgs_opposing": orgs_oppose,
			"default_state": default_state if default_state != None else "",
			"default_district": default_district if default_district != None else "",
			"stateabbrs": 
				[ (abbr, govtrack.statenames[abbr], govtrack.stateapportionment[abbr]) for abbr in govtrack.stateabbrs],
		}, context_instance=RequestContext(request))
	
@json_response
def billreport_getinfo(request, congressnumber, billtype, billnumber):
	bill = getbill(congressnumber, billtype, billnumber)
	
	state = request.REQUEST["state"] if "state" in request.REQUEST else ""
	district = int(request.REQUEST["district"]) if request.REQUEST["district"] != "" else None
	
	pro_comments, pro_is_random = bill_comments(bill, "+", address__state=state, address__congressionaldistrict=district)
	con_comments, con_is_random = bill_comments(bill, "-", address__state=state, address__congressionaldistrict=district)
	
	comments = list(pro_comments) + list(con_comments)
	comments.sort(key = lambda x : x.updated, reverse=True)
		
	if state == "":
		reporttitle = "Legislative Report for POPVOX Nation"
	elif district == None or district == 0:
		reporttitle = "Legislative Report for " +  govtrack.statenames[state]
	else:
		reporttitle = "District Report for " + state + "-" + str(district)
	
	reportsubtitle = ""
	if state != "":
		reportsubtitle = \
			"Represented by " \
			+ re.sub(r"\[[^\]]*\]", "", 
				" and ".join(
					[p["name"] for p in 
						getMembersOfCongressForDistrict(state + str(district),
							moctype="rep" if district != None else "sen")]
					)
				)
			
	return {
		"reporttitle": reporttitle,
		"reportsubtitle": reportsubtitle,
	
		"shortmessages": [],
		"longmessages":
			[ {
				"user":c.user.username,
				"msg": c.message,
				"location": c.address.city + ("" if state != "" else ", " + c.address.state),
				"date": formatDateTime(c.updated),
				"pos": c.position,
				"share": c.get_absolute_url() + "/share",
				} for c in comments ],
		"stats": {
			"overall": bill_statistics(bill, "POPVOX", "POPVOX Nation"),
			"state": bill_statistics(bill,
				state,
				govtrack.statenames[state] if state != "" else None,
				address__state=state if state != "" else None),
			"district": bill_statistics(bill,
				state + "-" + str(district),
				state + "-" + str(district),
				address__state=state if state != "" else None,
				address__congressionaldistrict=district if district not in (None, 0) else None)
		}
	}

