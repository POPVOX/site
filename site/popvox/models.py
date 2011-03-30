from django.db import models
from django.contrib.auth.models import User
import django.db.models.signals
from django.core.mail import send_mail
from django.core.cache import cache
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.contrib.humanize.templatetags.humanize import ordinal

import sys
import os
from datetime import datetime, timedelta
from urllib import urlopen
from xml.dom import minidom
import re

from tinymce import models as tinymce_models
from picklefield import PickledObjectField

import settings

import govtrack

from writeyourrep.models import DeliveryRecord

class MailListUser(models.Model):
	email = models.EmailField(db_index=True, unique=True)
	def __unicode__(self):
		return self.email

class RawText(models.Model):
	name = models.SlugField(db_index=True, unique=True)
	format = models.IntegerField(choices=[(0, "Raw HTML"), (1, "Markdown")], default=0)
	text = models.TextField(blank=True)
	class Meta:
		ordering = ['name']
	def __unicode__(self):
		return self.name
	def html(self):
		if self.format == 0:
			return self.text
		if self.format == 1:
			import markdown
			return markdown.markdown(self.text, output_format='html4')

class IssueArea(models.Model):
	"""An issue area."""
	slug = models.SlugField(db_index=True, unique=True)
	name = models.CharField(max_length=100)
	shortname = models.CharField(max_length=16, blank=True, null=True)
	parent = models.ForeignKey('self', blank=True, null=True, db_index=True, related_name = "subissues")
	class Meta:
		ordering = ['name']
	def __unicode__(self):
		return self.name

	def orgs(self):
		return (Org.objects.filter(visible=True, issues=self) | Org.objects.filter(visible=True, issues__parent=self)).distinct()
		
class MemberOfCongress(models.Model):
	"""A Member of Congress or former member."""
	
	# The primary key is the GovTrack ID.
	
	documents = models.ManyToManyField("PositionDocument", blank=True, related_name="owner_memberofcongress")

	def __unicode__(self):
		return unicode(self.id) + u" " + self.name()
	def name(self):
		return govtrack.getMemberOfCongress(self.id)["name"]
	def lastname(self):
		return govtrack.getMemberOfCongress(self.id)["lastname"]
	def party(self):
		if "party" in govtrack.getMemberOfCongress(self.id):
			return govtrack.getMemberOfCongress(self.id)["party"]
		else:
			return "?"
	
	# Make sure there is a record for every Member of Congress.
	@classmethod
	def init_members(clz):
		#if not govtrack.govtrack_file_modified("us/people.xml"):
		#	return
		existing_id_set = [x["id"] for x in MemberOfCongress.objects.all().values("id")]
		for px in govtrack.getMembersOfCongress():
			if not px["id"] in existing_id_set:
				obj, new = MemberOfCongress.objects.get_or_create(id=px["id"])
				if new:
					sys.stderr.write("Initializing new Member of Congress: " + str(obj) + "\n")

class CongressionalCommittee(models.Model):
	"""A congressional committee or subcommittee."""
	code = models.CharField(max_length=8, unique=True, db_index=True)
	def __unicode__(self):
		return self.code + u" " + self.name()
	def name(self):
		return govtrack.getCommittee(self.code)["name"]
	def shortname(self):
		return govtrack.getCommittee(self.code)["shortname"]
	def abbrevname(self):
		return govtrack.getCommittee(self.code)["abbrevname"]
	def issubcommittee(self):
		return "parent" in govtrack.getCommittee(self.code)
		
	# Make sure there is a record for every committee.
	@classmethod
	def init_committees(clz):
		#if not govtrack.govtrack_file_modified("us/committees.xml"):
		#	return
		existing_id_set = [x["code"] for x in CongressionalCommittee.objects.all().values("code")]
		for cx in govtrack.getCommitteeList():
			if not cx["id"] in existing_id_set:
				obj, new = CongressionalCommittee.objects.get_or_create(code=cx["id"])
				if new:
					sys.stderr.write("Initializing new committee: " + str(obj) + "\n")

class Bill(models.Model):
	"""A bill in Congress."""
	BILL_TYPE_CHOICES = [ ('h', 'H.R.'), ('s', 'S.'), ('hr', 'H.Res.'), ('sr', 'S.Res.'), ('hc', 'H.Con.Res.'), ('sc', 'S.Con.Res.'), ('hj', 'H.J.Res.'), ('sj', 'S.J.Res.') ]
	BILL_TYPE_SLUGS = [ ('h', 'hr'), ('s', 's'), ('hr', 'hres'), ('sr', 'sres'), ('hc', 'hconres'), ('sc', 'sconres'), ('hj', 'hjres'), ('sj', 'sjres') ]
	congressnumber = models.IntegerField()
	billtype = models.CharField(max_length=2, choices=BILL_TYPE_CHOICES)
	billnumber = models.IntegerField()
	sponsor = models.ForeignKey(MemberOfCongress, blank=True, null=True, db_index=True, related_name = "sponsoredbills")
	committees = models.ManyToManyField(CongressionalCommittee, related_name="bills")
	topterm = models.ForeignKey(IssueArea, db_index=True, blank=True, null=True, related_name="toptermbills")
	issues = models.ManyToManyField(IssueArea, related_name="bills")
	title = models.TextField()
	current_status = models.TextField()
	current_status_date = models.DateTimeField()
	num_cosponsors = models.IntegerField()
	latest_action = models.TextField()
	
	class Meta:
			ordering = ['congressnumber', 'billtype', 'billnumber']
			unique_together = (("congressnumber", "billtype", "billnumber"),)

	_govtrack_metadata = None
	
	def __unicode__(self):
		return self.title[0:30]
	def get_absolute_url(self):
		return self.url()

	def url(self):
		return "/bills/us/" + str(self.congressnumber) + "/" + [x[1] for x in Bill.BILL_TYPE_SLUGS if x[0]==self.billtype][0] + str(self.billnumber)

	def govtrack_metadata(self):
		if self._govtrack_metadata == None :
			self._govtrack_metadata = govtrack.getBillMetadata(self)
		return self._govtrack_metadata
		
	def govtrack_code(self):
		return self.billtype + str(self.congressnumber) + "-" + str(self.billnumber)
	def govtrack_link(self):
		return "http://www.govtrack.us/congress/bill.xpd?bill=" + self.govtrack_code()
		
	def displaynumber(self):
		return govtrack.getBillNumber(self)
	def displaynumber_nosession(self):
		return govtrack.getBillNumber(self, False)
	def title_no_number(self):
		return self.title[self.title.index(":")+2:]
	def shorttitle(self):
		return govtrack.getBillTitle(self, self.govtrack_metadata(), "short")
	def officialtitle(self):
		return govtrack.getBillTitle(self, self.govtrack_metadata(), "official")
	def populartitle(self):
		return govtrack.getBillTitle(self, self.govtrack_metadata(), "popular")
	def status(self):
		return govtrack.getBillStatus(self)
	def status_advanced(self):
		return govtrack.getBillStatusAdvanced(self, False)
	def status_advanced_abbreviated(self):
		return govtrack.getBillStatusAdvanced(self, True)
	def cosponsors(self):
		return govtrack.getBillCosponsors(self.govtrack_metadata())
	def isAlive(self):
		# alive = pending further Congressional action
		return govtrack.billFinalStatus(self) == None
	def getDeadReason(self):
		# dead = no longer pending action because it passed, failed, or died in a previous session
		return govtrack.billFinalStatus(self)
	def died(self):
		# died is the specific state of having failed to be passed in a previous session
		return govtrack.billFinalStatus(self, "died") == "died"
	def getChamberOfNextVote(self):
		# bill must be alive
		return govtrack.getChamberOfNextVote(self)
		
	def latest_action_formatted(self):
		def parse_line(line):
			from popvox.views.utils import formatDateTime
			if line == "": return ""
			date, text = line.split("\t")
			return (formatDateTime(govtrack.parse_govtrack_date(date), withtime=False), text)
			
		return [parse_line(rec) for rec in self.latest_action.split("\n")]
		
	def campaign_positions(self):
		return self.orgcampaignposition_set.filter(campaign__visible=True, campaign__org__visible=True).select_related("campaign", "campaign__org")
	
	def hashtag(self, always_include_session=False):
		bt = ""
		if self.billtype == "h":
			bt = "hr"
		elif self.billtype == "hr":
			bt = "hres"
		elif self.billtype == "hj":
			bt = "hjres"
		elif self.billtype == "hc":
			bt = "hconres"
		elif self.billtype == "s":
			bt = "s"
		elif self.billtype == "sr":
			bt = "sres"
		elif self.billtype == "sj":
			bt = "sjres"
		elif self.billtype == "sc":
			bt = "sconres"
		bs = ""
		if self.congressnumber < govtrack.CURRENT_CONGRESS or always_include_session:
			bs = "/" + str(self.congressnumber)
		return "#" + bt + str(self.billnumber) + bs
		
	@classmethod
	def from_hashtag(cls, hashtag):
		m = re.match(r"\#([a-z]+)(\d+)/(\d+)", hashtag)
		return Bill.objects.get(
			congressnumber = m.group(3),
			billtype = {"hr":"h", "hres":"hr", "hjres":"hj", "hconres":"hc", "s":"s", "sres":"sr", "sjres":"sj", "sconres":"sc"}[m.group(1)],
			billnumber = m.group(2))

def bill_from_url(url):
	fields = url.split("/")
	if fields[0] != "":
		raise Exception("Invalid bill id.")
	if fields[1] != "bills":
		raise Exception("Invalid bill id.")
	if fields[2] != "us":
		raise Exception("Invalid bill id.")
	try :
		congressnumber = int(fields[3])
		m = re.match(r"([a-z]+)(\d+)", fields[4])
		billtype = [x[0] for x in Bill.BILL_TYPE_SLUGS if x[1]==m.group(1)][0]
		billnumber = int(m.group(2))
	except :
		raise Exception("Invalid bill id.")
	bill = Bill.objects.filter(congressnumber=congressnumber, billtype=billtype, billnumber=billnumber)
	if len(bill) == 0:
		raise Exception("No bill with that number exists.")
	else:
		return bill[0]
		
def getbillsfromhash(bills):
	# Group by congress number, then by bill type, and then
	# fetch many bills at once for that pair. We don't usually
	# query across sessions so this makes sure we don't
	# execute more than eight queries (for the eight types
	# of bills). Then return the Bill objects in the same order
	# as in the list we were passed in.
	
	# group bills into sets we can query in batch
	groups = { }
	for b in bills:
		if not b["congressnumber"] in groups:
			groups[b["congressnumber"]] = { }
		if not b["billtype"] in groups[b["congressnumber"]]:
			groups[b["congressnumber"]][b["billtype"]] = { }
		if not b["billnumber"] in groups[b["congressnumber"]][b["billtype"]]:
			groups[b["congressnumber"]][b["billtype"]][b["billnumber"]] = True
	
	# get bill objects in batch and map from a string code to the object
	objs = { }
	for congressnumber in groups:
		for billtype in groups[congressnumber]:
			for bill in Bill.objects.filter(congressnumber=congressnumber, billtype=billtype, billnumber__in=groups[congressnumber][billtype]).select_related('sponsor'):
				objs[bill.govtrack_code()] = bill

	# form the output array
	ret = []
	for bill in bills:
		code = bill["billtype"] + str(bill["congressnumber"]) + "-" + str(bill["billnumber"])
		if code in objs:
			ret.append(objs[code])

	return ret

class Org(models.Model):
	"""An advocacy group."""

	ORG_TYPE_NOT_SET = 0
	ORG_TYPE_501C3 = 1
	ORG_TYPE_501C4 = 2
	ORG_TYPE_501C5 = 3
	ORG_TYPE_501C6 = 4
	ORG_TYPE_501C7 = 5
	ORG_TYPE_527_OR_PAC = 6
	ORG_TYPE_COMMUNITY_GROUP = 7
	ORG_TYPE_ISSUE_ASSOC = 8
	ORG_TYPE_RESEARCH_ORG = 9
	ORG_TYPES = (
		(ORG_TYPE_NOT_SET, "Not Set"),
		(ORG_TYPE_501C3, "501(c)(3) organization (e.g. charitable, religious, educational, research or scientific organization)"),
		(ORG_TYPE_501C4, "501(c)(4) organization (e.g. civic leagues, lobbying or other social welfare organization)"),
		(ORG_TYPE_501C5, "501(c)(5) organization (e.g. labor union or allied group)"),
		(ORG_TYPE_501C6, "501(c)(6) organization (e.g. business league or associations)"),
		(ORG_TYPE_501C7, "501(c)(7) organization (e.g. social and recreation clubs)"),
		(ORG_TYPE_527_OR_PAC, "527 or PAC (e.g. groups primarily created to influence election of candidates for public office)"),
		(ORG_TYPE_COMMUNITY_GROUP, "Community group not classified as tax-exempt, but with a not-for-profit mission"),
		(ORG_TYPE_ISSUE_ASSOC, "Issues-based association not classified as tax-exempt, but with a not-for-profit mission"),
		(ORG_TYPE_RESEARCH_ORG, "Research or services organization not classified as tax-exempt, but with a not-for-profit orientation"),
		)

	ORG_CLAIMEDMEMBERSHIP_CHOICES = [
		("Not Set", "Not Set"),
		("Fewer than 1,000", "Fewer than 1,000"),
		("1,000-10,000", "1,000-10,000"),
		("10,000-100,000", "10,000-100,000"),
		("100,000-500,000", "100,000-500,000"),
		("More than 500,000", "More than 500,000"),
		]

	slug = models.SlugField(db_index=True, unique=True)
	name = models.CharField(max_length=100)
	type = models.IntegerField(choices=ORG_TYPES, default=ORG_TYPE_NOT_SET)
	website = models.URLField(blank=True, db_index=True, unique=True)
	description = models.TextField(blank=True)
	claimedmembership = models.CharField(choices=ORG_CLAIMEDMEMBERSHIP_CHOICES, default="Not Set", max_length=max([len(x[0]) for x in ORG_CLAIMEDMEMBERSHIP_CHOICES]), verbose_name="Claimed membership")
	iscoalition = models.BooleanField(default=False, verbose_name="Is this a coalition?")
	postaladdress = models.TextField(blank=True)
	phonenumber = models.TextField(blank=True)
	homestate = models.CharField(choices=govtrack.statelist, max_length=2, blank=True, null=True, db_index=True)
	twittername = models.TextField(blank=True, null=True)
	facebookurl = models.URLField(blank=True, null=True)
	issues = models.ManyToManyField(IssueArea, blank=True)
	logo = models.ImageField(upload_to="submitted/org/profilelogo", blank=True, null=True)
	created = models.DateTimeField(auto_now_add=True)
	updated = models.DateTimeField(auto_now=True)
	visible = models.BooleanField(default=False)
	createdbyus = models.BooleanField(default=False)
	approved = models.BooleanField(default=False)
	
	documents = models.ManyToManyField("PositionDocument", blank=True, related_name="owner_org")
	
	coalitionmembers = models.ManyToManyField("Org", blank=True, related_name="ispartofcoalition", verbose_name="Coalition members")
	
	class Meta:
			verbose_name = "organization"
			ordering = ['name']
	def __unicode__(self):
		return self.name
	def get_absolute_url(self):
		return self.url()
	def url(self):
		return "/orgs/" + self.slug

	def campaigns(self):
		return self.orgcampaign_set.filter(visible=True).order_by("-default", "name")
	def all_campaigns(self):
		return self.orgcampaign_set.order_by("-default", "name")
	def is_admin(self, user):
		if user.is_anonymous():
			return False
		return user.is_superuser or len(UserOrgRole.objects.filter(user=user, org=self)) > 0
 
	def set_default_slug(self):
		import string
		# generate slug from website address's letter characters
		if self.website != None:
			m = re.match(r"^(http://)?(www\.)?([^/]*)\.(com|net|org|us|int)", self.website)
			if m != None:
				self.slug = ""
				for c in str(m.group(3)):
					if c in string.letters+string.digits:
						self.slug += c.lower()
				if self.slug != "":
					return
		# else, generate slug from all uppercase letters in name except letters within parenthesis
		self.slug = ""
		for c in re.sub(r"\(.*?\)", "", self.name):
			if c == c.upper() and c != c.lower():
				self.slug += c.lower()
		if self.slug != "":
			return
			
		self.slug = "org"
			
		# check if it's in use, and if so add a numeric suffix to make it distinct
		suffix = ""
		while True:
			orgs = Org.objects.filter(slug = self.slug + str(suffix))
			if len(orgs) == 0:
				self.slug = self.slug + str(suffix)
				break # found a good one
			if suffix == "":
				suffix = 0
			suffix += 1
			
	def sync_external_members(self):
		# Update the OrgExternalMemberCount records for this org
		# by querying Facebook and Twitter.
		
		def updateRecord(source, count):
			# Get existing record if any.
			rec = None
			try:
				rec = OrgExternalMemberCount.objects.get(org=self, source=source)
				# If this source is no longer valid (count==None) and a record exists,
				# delete it.
				if count == None and rec != None:
					rec.delete()
			except:
				pass
			
			if count == None:
				return
		
			if rec == None:
				rec = OrgExternalMemberCount()
				rec.org = self
				rec.source = source
			elif rec.count != count:
				# only update prev entry if count changed
				rec.prev_count = rec.count
				rec.prev_updated = rec.updated
			rec.count = count
			
			# Compute a growth rate as the number of changed users per day divided
			# by the total number of users.
			if rec.prev_count != None:
				if count == 0:
					rec.growth = None
				elif (datetime.now() - rec.prev_updated).days > 0:
					rec.growth = float(count-rec.prev_count) / float((datetime.now() - rec.prev_updated).days) / float(count)
			
			rec.save()

		# Facebook Fans.
		if self.facebookurl == None: # clear record
			updateRecord(OrgExternalMemberCount.FACEBOOK_FANS, None)
		else: # add/update record
			try: # ignore network errors, etc.
				fbid = None
				
				import re
				m = re.search(r"^http://www.facebook.com/([^/]+)$", self.facebookurl)
				if m != None:
					fbid = m.group(1)
				m = re.search(r"/pages/[^/]+/(\d+)", self.facebookurl)
				if m != None:
					fbid = m.group(1)
				if fbid != None:
					from urllib import urlopen, quote_plus
					import json
					fbdata = json.load(urlopen("http://graph.facebook.com/" + fbid))
					if type(fbdata) == dict and "likes" in fbdata:
						updateRecord(OrgExternalMemberCount.FACEBOOK_FANS, int(fbdata["likes"])) # if no likes key, just skip by raising Exception, catching it, and passing on
			except Exception, e:
				print e
				pass
		
		# Twitter Followers.
		if self.twittername == None: # clear record
			updateRecord(OrgExternalMemberCount.TWITTER_FOLLOWERS, None)
		else: # add/update record
			try: # ignore network errors, etc.
				from urllib import urlopen, quote_plus
				from xml.dom import minidom
				t = minidom.parse(urlopen("http://api.twitter.com/1/users/show.xml?screen_name=" + quote_plus(self.twittername.encode('utf-8'))))
				count = int(t.getElementsByTagName('followers_count')[0].firstChild.data)
				updateRecord(OrgExternalMemberCount.TWITTER_FOLLOWERS, count)
			except Exception, e:
				print e
				pass
			
 	def facebook_fan_count(self):
		try:
			return OrgExternalMemberCount.objects.get(org=self, source=OrgExternalMemberCount.FACEBOOK_FANS).count
		except:
			return 0
 	def twitter_follower_count(self):
		try:
			return OrgExternalMemberCount.objects.get(org=self, source=OrgExternalMemberCount.TWITTER_FOLLOWERS).count
		except:
			return 0
	def estimated_fan_count(self):
		return self.facebook_fan_count() + self.twitter_follower_count()
 
class OrgContact(models.Model):
	"""A contact record for an Org displayed to legislative staff."""
	
	org = models.ForeignKey(Org, related_name="contacts", db_index=True)
	name = models.CharField(max_length=100)
	title = models.CharField(max_length=100, blank=True, null=True)
	phonenumber = models.TextField(blank=True, null=True)
	email = models.EmailField(blank=True, null=True)
	issues = models.ManyToManyField(IssueArea, blank=True)
	created = models.DateTimeField(auto_now_add=True)
	updated = models.DateTimeField(auto_now=True)
	
	class Meta:
		verbose_name = "organization contact"
		order_with_respect_to = 'org'
		ordering = ['name']
	def __unicode__(self):
		return self.org.name + " - " + self.name

class OrgCampaign(models.Model):
	"""An organization's campaign."""
	org = models.ForeignKey(Org)
	slug = models.SlugField()
	name = models.CharField(max_length=100)
	website = models.URLField(blank=True, null=True)
	description = models.TextField(blank=True)
	message = tinymce_models.HTMLField(blank=True) #models.TextField()
	default = models.BooleanField(default=False)
	visible = models.BooleanField(default=False)
	created = models.DateTimeField(auto_now_add=True)
	updated = models.DateTimeField(auto_now=True)
	class Meta:
			verbose_name = "organization campaign"
			order_with_respect_to = 'org'
			ordering = ['default', 'name']
			unique_together = (("org", "slug"),)
	def __unicode__(self):
		return self.org.name + (" -- " + self.name if not self.default else "")
	def get_absolute_url(self):
		return self.url()
	def url(self):
		return "/orgs/" + self.org.slug + "/" + self.slug
	def website_or_orgsite(self):
		if self.website:
			return self.website
		else:
			return self.org.website

class OrgExternalMemberCount(models.Model):
	"""An external count of a size of an organization, e.g. as reported by the org or from Facebook or Twitter."""
	AS_REPORTED = 0
	FACEBOOK_FANS = 1
	TWITTER_FOLLOWERS = 2
	SOURCE_TYPES = [0, 1, 2]
	org = models.ForeignKey(Org)
	source = models.IntegerField(choices=[(AS_REPORTED, 'As Reported'), (FACEBOOK_FANS, 'Facebook Fans'), (TWITTER_FOLLOWERS, 'Twitter Followers')])
	count = models.IntegerField()
	updated = models.DateTimeField(auto_now=True)
	prev_count = models.IntegerField(null=True, blank=True)
	prev_updated = models.DateTimeField(null=True, blank=True)
	growth = models.FloatField(null=True, blank=True, db_index=True)
	class Meta:
			verbose_name = "organization external count of members"
			order_with_respect_to = 'org'
			ordering = ['source']
			unique_together = (("org", "source"),)
	def __unicode__(self):
		return self.org.name + " -- " + str(self.source)

class OrgCampaignPosition(models.Model):
	"""A position on a bill within an OrgCampaign."""
	POSITION_CHOICES = [ ('+', 'Support'), ('-', 'Oppose'), ('0', 'Neutral') ]
	campaign = models.ForeignKey(OrgCampaign, related_name="positions")
	bill = models.ForeignKey(Bill)
	position = models.CharField(max_length=1, choices=POSITION_CHOICES)
	comment = models.TextField(blank=True, null=True)
	action_headline = models.CharField(max_length=128, blank=True, null=True)
	action_body = tinymce_models.HTMLField(blank=True, null=True) #models.TextField()
	created = models.DateTimeField(auto_now_add=True)
	updated = models.DateTimeField(auto_now=True)
	order = models.IntegerField(default=0)
	class Meta:
		ordering = ['campaign', 'order', '-updated']
		unique_together = (("campaign", "bill"),)
	def __unicode__(self):
		return unicode(self.campaign) + " -- " + unicode(self.bill) + " -- " + self.position
	def get_absolute_url(self):
		return "/orgs/" + self.campaign.org.slug + "/_action/" + str(self.id)
	def documents(self):
		return self.campaign.org.documents.filter(bill=self.bill).defer("text")

class OrgCampaignPositionActionRecord(models.Model):
	# This is used for org-customized landing pages
	# for bills when the user accepts to send their
	# info back to the org.
	ocp = models.ForeignKey(OrgCampaignPosition, related_name="actionrecords")
	firstname = models.CharField(max_length=64)
	lastname = models.CharField(max_length=64)
	zipcode = models.CharField(max_length=16)
	email = models.EmailField()
	created = models.DateTimeField(auto_now_add=True)
	class Meta:
		ordering = ['created']

class UserProfile(models.Model):
	"""A user profile extends the basic user model provided by Django."""
	
	# NOTE: When adding required fields, make sure to update the
	# user_saved_callback to initialize the fields on new user profiles
	# or put in a default value.
	
	user = models.OneToOneField(User)
	
	referrer_content_type = models.ForeignKey(ContentType, db_index=True, blank=True, null=True, related_name="usersrefferedby")
	referrer_object_id = models.PositiveIntegerField(blank=True, null=True, db_index=True)
	referrer = generic.GenericForeignKey('referrer_content_type', 'referrer_object_id')

	fullname = models.CharField(max_length=100, blank=True, null=True)
	
	# we're not using these now but I figure we will at some point.
	state = models.CharField(choices=[(x,x) for x in govtrack.stateabbrs], max_length=2, blank=True, null=True) # USPS state abbreviation, or None if not set
	district = models.IntegerField(blank=True, null=True) # None if not set, 0 for at-large, otherwise cong. district number

	allow_mass_mails = models.BooleanField(default=True)
	registration_followup_sent = models.BooleanField(default=False)
	registration_welcome_sent = models.BooleanField(default=False)
	
	issues = models.ManyToManyField(IssueArea, blank=True)
	tracked_bills = models.ManyToManyField(Bill, blank=True, related_name="trackedby")
	antitracked_bills = models.ManyToManyField(Bill, blank=True, related_name="antitrackedby")
	
	options = PickledObjectField(default={})
	
	def __unicode__(self):
		ret = self.user.username
		if self.fullname != None:
			ret += " " + self.fullname
		staff = self.staff_info()
		if staff != "":
			ret += ", " + staff
		return ret
		
	def delete(self, *args, **kwargs):
		# Override the delete method so that when we delete a profile we also
		# delete the underlying user, so that we don't leave profile-less users
		# in the database. Also helpful in the Django admin so we can delete
		# users from the UserProfile page. Not that we should be doing that.
		super(UserProfile, self).delete(*args, **kwargs)
		self.user.delete()
		
	def most_recent_comment_district(self):
		for c in self.user.comments.order_by("-created"):
			return c.address.state + str(c.address.congressionaldistrict)
		return None

	_is_org_admin = None # cache because of the frequency we call from templates; but dangerous?
	def is_org_admin(self):
		# is_leg_staff overrides is_org_admin in the improper case that
		# a leg staff ends up with an org role
		if self._is_org_admin == None:
			self._is_org_admin = not self.is_leg_staff() and len(self.user.orgroles.all()) > 0
		return self._is_org_admin
		
	_is_leg_staff = None # cache because of the frequency we call from templates; but dangerous?
	def is_leg_staff(self):
		if self._is_leg_staff == None:
			try:
				self._is_leg_staff = (self.user.legstaffrole != None)
			except UserLegStaffRole.DoesNotExist:
				self._is_leg_staff = None
		return self._is_leg_staff
		
	def staff_info(self):
		legstaff = []
		try:
			legstaff = [self.user.legstaffrole]
		except:
			pass
		return "; ".join([x.as_string() for x in legstaff + list(self.user.orgroles.all())])
		
	def getopt(self, key, default=None):
		if self.options == None or type(self.options) == str: # not initialized (null or empty string)
			return default
		if key in self.options:
			return self.options[key]
		else:
			return default
	def setopt(self, key, value, save=True):
		if self.options == None or type(self.options) == str: # not initialized (null or empty string)
			self.options = { }
		if value != None:
			self.options[key] = value
		elif key in self.options:
			del self.options[key]
		if save:
			self.save()
	
def user_saved_callback(sender, instance, created, **kwargs):
	if created:
		p = UserProfile()
		p.user = instance
		p.save()

		send_mail('New account: ' + instance.username, 'New account created: ' + instance.username + " (" + instance.email + ")", "info@popvox.com", ["marci@popvox.com", "rachna@popvox.com"], fail_silently=True)
if not "LOADING_DUMP_DATA" in os.environ:
	# When we're loading from a fixture, we get the UserProfile record later so we cannot
	# create it now or we get a duplicate value for index error.
	django.db.models.signals.post_save.connect(user_saved_callback, sender=User)

class UserOrgRole(models.Model):
	user = models.ForeignKey(User, related_name="orgroles", db_index=True)
	org = models.ForeignKey(Org, related_name="admins", db_index=True)
	title = models.CharField(max_length=50)
	class Meta:
		verbose_name = "organization administrator"
		order_with_respect_to = 'org'
		unique_together = (("user", "org"),)
	def __unicode__(self):
		return self.user.username + " @ " + self.org.slug
	def as_string(self):
		return self.org.name

class UserLegStaffRole(models.Model):
	user = models.OneToOneField(User, related_name="legstaffrole", db_index=True)
	member = models.ForeignKey(MemberOfCongress, blank=True, null=True, db_index=True, db_column="member")
	committee = models.ForeignKey(CongressionalCommittee, blank=True, null=True, db_index=True, to_field="code", db_column="committee")
	position = models.CharField(max_length=50)
	class Meta:
		verbose_name = "legislative staff role"
	def __unicode__(self):
		return self.user.username + " - " + (self.member.name() if self.member != None else "n/a") + " - " + (self.committee.name() if self.committee != None else "n/a") + ", " + self.position
	def as_string(self):
		ret = []
		if self.member != None:
			ret.append( self.member.name() )
		if self.committee != None:
			ret.append( self.committee.shortname() )
		ret.append( self.position )
		return ", ".join(ret)
	def bossname(self):
		return self.member.name()
	def chamber(self):
		if self.member != None:
			member = govtrack.getMemberOfCongress(self.member_id)
			if not member["current"]:
				return None
			elif member["type"] == "rep":
				return "H"
			else:
				return "S"
		elif self.committee != None:
			if self.committee.code[0] in ("H", "S"): # but not J
				return self.committee.code[0]
		return None
		
class PositionDocument(models.Model):
	bill = models.ForeignKey(Bill, related_name="documents", db_index=True)
	doctype = models.IntegerField(choices=[(0, 'Press Release'), (1, 'Floor Introductory Statement'), (2, 'Dear Colleague Letter'), (3, "Report"), (4, "Letter of Support"), (5, "Coalition Letter"), (99, 'Other')])
	title = models.CharField(max_length=128)
	text = tinymce_models.HTMLField(blank=True) #models.TextField()
	link = models.URLField(blank=True, null=True)
	created = models.DateTimeField(auto_now_add=True)
	updated = models.DateTimeField(auto_now=True, db_index=True)
	def __unicode__(self):
		owner = ""
		if self.owner_memberofcongress.all().exists():
			owner = unicode(self.owner_memberofcongress.all()[0]) + ": "
		if self.owner_org.all().exists():
			owner = unicode(self.owner_org.all()[0]) + ": "
		return owner + self.bill.title + " [" + self.get_doctype_display() + "]"
	def get_absolute_url(self):
		if self.owner_org.all().exists():
			return self.bill.url() + "/docs/" + self.owner_org.all()[0].slug + "/" + str(self.doctype)
		if self.owner_memberofcongress.all().exists():
			return self.bill.url() + "/docs/" + self.owner_memberofcongress.all()[0].id + "/" + str(self.doctype)
		return self.bill.url() # !!

	def url(self):
		return self.get_absolute_url()
		
class PostalAddress(models.Model):
	"""A postal address."""
	
	# We need to put an index over state,congressionaldistrict so we can quickly
	# find comments within a district.

	# An address is tied to a user so that if we delete a user account, we also
	# delete any addresses they have entered.
	user = models.ForeignKey(User, db_index=True)

	nameprefix = models.CharField(max_length=32, blank=True)
	firstname = models.CharField(max_length=64)
	lastname = models.CharField(max_length=64)
	namesuffix = models.CharField(max_length=32, blank=True)
	address1 = models.CharField(max_length=128)
	address2 = models.CharField(max_length=128, blank=True)
	city = models.CharField(max_length=64)
	state = models.CharField(max_length=2)
	zipcode = models.CharField(max_length=10)
	phonenumber = models.CharField(max_length=18, blank=True)
	congressionaldistrict = models.IntegerField() # 0 for at-large, otherwise cong. district number
	state_legis_upper = models.TextField(blank=True, null=True)
	state_legis_lower = models.TextField(blank=True, null=True)
	latitude = models.FloatField(blank=True, null=True)
	longitude = models.FloatField(blank=True, null=True)
	cdyne_return_code = models.IntegerField(blank=True, null=True)
	created = models.DateTimeField(auto_now_add=True)
	timezone = models.CharField(max_length=4, blank=True, null=True)

	#class Meta:
	#		ordering = ["nameprefix"]

	PREFIXES = 	('', 'Mr.', 'Mrs.', 'Ms.', 'Dr.', 'Reverend', 'Sister', 'Pastor')
	SUFFIXES = 	('', 'Jr.', 'Sr.', 'I', 'II', 'III')
	
	def __unicode__(self):
		return unicode(self.user) + ": " + self.firstname +  " " + self.lastname + "\n" + self.address1 + ("\n" + self.address2 if self.address2 != "" else "") + "\n" + self.city + ", " + self.state + " " + self.zipcode + " (CD" + str(self.congressionaldistrict) + ")"
	
	def load_from_form(self, request, validate=True):
		self.nameprefix = request.POST["useraddress_prefix"]
		self.firstname = request.POST["useraddress_firstname"]
		self.lastname = request.POST["useraddress_lastname"]
		self.namesuffix = request.POST["useraddress_suffix"]
		self.address1 = request.POST["useraddress_address1"]
		self.address2 = request.POST["useraddress_address2"]
		self.city = request.POST["useraddress_city"]
		self.state = request.POST["useraddress_state"].upper()
		self.zipcode = request.POST["useraddress_zipcode"]
		self.phonenumber = request.POST["useraddress_phonenumber"]
		if not validate:
			return
		if self.nameprefix.strip() == "":
			raise ValueError("Please select your title (Mr., Ms., etc.).")
		if self.firstname.strip() == "":
			raise ValueError("Please enter your first name.")
		if self.lastname.strip() == "":
			raise ValueError("Please enter your last name.")
		if self.address1.strip() == "":
			raise ValueError("Please enter your address.")
		if self.city.strip() == "":
			raise ValueError("Please enter your city.")
		if self.state.strip() == "":
			raise ValueError("Please select your state.")
		if self.state not in govtrack.stateabbrs:
			raise ValueError("Invalid state abbreviation.")
		if self.zipcode.strip() == "":
			raise ValueError("Please enter your zipcode.")
		if len("".join([ d for d in self.phonenumber if d in ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9') ])) < 10:
			raise ValueError("Please enter your phone number.")

	def equals(self, other):
		return self.nameprefix == other.nameprefix and self.firstname == other.firstname and self.lastname == other.lastname and self.namesuffix == other.namesuffix and self.address1 == other.address1 and self.address2 == other.address2 and self.city == other.city and self.state == other.state and self.zipcode == other.zipcode and self.congressionaldistrict == other.congressionaldistrict and self.phonenumber == other.phonenumber
		
	def heshe(self):
		if self.nameprefix in ('Mr.',):
			return "he"
		elif self.nameprefix in ('Mrs.', 'Ms.', 'Sister'):
			return "she"
		else:
			return "he or she"

	def statename(self):
		return govtrack.statenames[self.state]
		
	def address_string(self):
		return self.address1 + ("\n" + self.address2 if self.address2 != "" else "") + "\n" + self.city + ", " + self.state + " " + self.zipcode

	def nicelocation(self):
		ret = govtrack.statenames[self.state]
		if self.congressionaldistrict > 0:
			 ret += "'s " + ordinal(self.congressionaldistrict) + " District"
		else:
			ret += " At Large"
		ret += ", represented by " + ", ".join(
			[x["name"] for x in govtrack.getMembersOfCongressForDistrict(self.state + str(self.congressionaldistrict))]
			)
		return ret
		
	def set_timezone(self):
		# This is correct only to the majority of a state. Some states split timezones.
		# http://en.wikipedia.org/wiki/List_of_U.S._states_by_time_zone
		if self.state in ("AK", ):
			self.timezone = "AKST"  # UTC-9
		if self.state in ("AS", ):
			self.timezone = "SAST" # Samoa Standard Time,  UTC-11, made-up abbreviation
		if self.state in ("GU", "MP"):
			self.timezone = "CHST" # Chamorro Standard Time, UTC+10, made-up abbreviation
		if self.state in ("HI", ):
			self.timezone = "HAST" # Hawaii time, UTC-10, made-up abbreviation
		if self.state in ("PR", "VI"):
			self.timezone = "AST" # Atlantic Standard Time, UTC-4
		if self.state in ("CT", "DC", "DE", "FL", "GA", "IN", "ME", "MD", "MA", "MI", "NH", "NJ", "NY", "NC", "OH", "PA", "RI", "SC", "VT", "VA", "WV"):
			self.timezone = "EST" # UTC-5
		if self.state in ("AL", "AR", "IL", "IA", "KS", "KY", "LA", "MN", "MS", "MO", "NE", "ND", "OK", "SD", "TN", "TX", "WI"):
			self.timezone = "CST" # UTC-6
		if self.state in ("AZ", "CO", "ID", "MT", "NM", "UT", "WY"):
			self.timezone = "MST" # UTC-7
		if self.state in ("CA", "NV", "OR", "WA"):
			self.timezone = "PST" # UTC-8
		self.save()
		
class UserComment(models.Model):
	"""A comment by a user on a bill."""
	
	POSITION_CHOICES = [ ('+', 'Support'), ('-', 'Oppose') ]

	COMMENT_NOT_REVIEWED = 0 # note that these values are hard-coded in several templates
	COMMENT_ACCEPTED = 1
	COMMENT_REJECTED = 2
	COMMENT_REJECTED_STOP_DELIVERY = 3
	COMMENT_REJECTED_REVISED = 4

	user = models.ForeignKey(User, related_name="comments", db_index=True) # user authoring the comment
	bill = models.ForeignKey(Bill, related_name="usercomments", db_index=True)
	position = models.CharField(max_length=1, choices=POSITION_CHOICES)
	
	message = models.TextField(blank=True, null=True)

	address = models.ForeignKey(PostalAddress, db_index=True) # current address at time of writing

	created = models.DateTimeField(auto_now_add=True)
	updated = models.DateTimeField(auto_now_add=True)
	status = models.IntegerField(choices=[(COMMENT_NOT_REVIEWED, 'Not Reviewed -- Displayed'), (COMMENT_ACCEPTED, 'Reviewed & Accepted -- Displayed'), (COMMENT_REJECTED, 'Rejected -- Not Displayed'), (COMMENT_REJECTED_STOP_DELIVERY, 'Rejected -- Not Displayed / Not Deliverable'), (COMMENT_REJECTED_REVISED, 'Rejected+Revised by User - Not Displayed')], default=COMMENT_NOT_REVIEWED)
	
	tweet_id = models.BigIntegerField(blank=True, null=True)
	fb_linkid = models.CharField(max_length=32, blank=True, null=True)

	referrer_content_type = models.ForeignKey(ContentType, blank=True, null=True, db_index=True, related_name="commentsrefferedby")
	referrer_object_id = models.PositiveIntegerField(blank=True, null=True, db_index=True)
	referrer = generic.GenericForeignKey('referrer_content_type', 'referrer_object_id')
	
	moderation_log = models.TextField(blank=True, null=True)
	
	# This holds all delivery attempts at this comment. some of the
	# delivery attempts have been superceded by their re-send
	# attempts. Also when we send letters to senators we may
	# send it to both senators, so this records all delivery attempts
	# for all of the individuals the message gets sent to.
	delivery_attempts = models.ManyToManyField(DeliveryRecord, blank=True, related_name="comments")
	
	class Meta:
			verbose_name = "user comment"
			ordering = ["-updated"]
			unique_together = (("user", "bill"),)
	def __unicode__(self):
		return self.user.username + " -- " + (self.message[0:40] if self.message != None else "NONE") + " | " + self.delivery_status()

	def get_absolute_url(self):
		return self.bill.url() + "/comment/" + str(self.id)

	def url(self):
		return self.get_absolute_url()
	
	def verb(self, tense="present"):
		# the verb used to describe the comment depends on when the comment
		# was left in the stages of a bill's progress.
		if self.created.date() <= govtrack.getCongressDates(self.bill.congressnumber)[1].date():
			# comment was (first) left before the end of the Congress in which the
			# bill was introduced
			if self.position == "+":
				if tense=="present":
					return "supports"
				elif tense=="past":
					return "supported"
				elif tense=="ing":
					return "supporting"
				elif tense=="imp":
					return "support"
			else:
				if tense=="present":
					return "opposes"
				elif tense=="past":
					return "opposed"
				elif tense=="ing":
					return "opposing"
				elif tense=="imp":
					return "oppose"
		else:
			# comment was left after Congress recessed, and the comment now
			# is about reintroduction
			if self.position == "+":
				if tense=="present":
					return "supports the reintroduction of"
				elif tense=="past":
					return "supported the reintroduction of"
				elif tense=="ing":
					return "supporting the reintroduction of"
				elif tense=="imp":
					return "support the reintroduction of"
			else:
				if tense=="present":
					return "opposes the reintroduction of" # we have no interface for users to leave a negative comment
				elif tense=="past":
					return "opposed the reintroduction of"
				elif tense=="ing":
					return "opposing the reintroduction of"
				elif tense=="imp":
					return "oppose the reintroduction of"

	def shares(self):
		import shorturl
		return shorturl.models.Record.objects.filter(target=self)

	def share_hits(self):
		return self.shares().aggregate(models.Sum("hits"))["hits__sum"]

	def get_recipients(self):
		if "@popvox.com" in self.user.email: return "Delivery is blocked for @popvox.com accounts."
		
		ch = self.bill.getChamberOfNextVote()
		if ch == None:
			return "The comment will not be delivered because the bill is not pending a vote in Congress."
			
		d = self.address.state + str(self.address.congressionaldistrict)
		
		govtrackrecipients = []
		if ch == "s":
			# send to all of the senators for the state
			govtrackrecipients = govtrack.getMembersOfCongressForDistrict(d, moctype="sen")
			if len(govtrackrecipients) == 0:
				# state has no senators, fall back to representative
				govtrackrecipients = govtrack.getMembersOfCongressForDistrict(d, moctype="rep")
		else:
			govtrackrecipients = govtrack.getMembersOfCongressForDistrict(d, moctype="rep")
			
		return govtrackrecipients
	
	def delivery_status(self):
		recips = self.get_recipients()
		if not type(recips) == list:
			return recips
			
		if len(recips) == 0:
			return "The comment cannot be delivered at this time because the Congressional office(s) that represents you is/are currently vacant."
			
		recips = [g["id"] for g in recips]
		
		retd = { }
		for d in self.delivery_attempts.filter(next_attempt__isnull = True):
			if d.target.govtrackid in recips:
				recips.remove(d.target.govtrackid)
			if d.success:
				if not d.created.strftime("%x") in retd:
					retd[d.created.strftime("%x")] = []
				retd[d.created.strftime("%x")].append(d.target.govtrackid)
			else:
				retd[d.target.govtrackid] = "We had trouble delivering your message to " + govtrack.getMemberOfCongress(d.target.govtrackid)["name"] + " but we will try again. "
				
		retk = list(retd.keys())
		retk.sort()
		
		ret = ""
		for k in retk:
			if type(k) == str:
				ret += "Your comment was delivered to " + " and ".join([govtrack.getMemberOfCongress(g)["name"] for g in retd[k]]) + " on " + k + ". "
			else:
				ret += retd[k]
				
		if self.message == None:
			return ""
		
		if len(recips) > 0:
			ret += "Your comment is pending delivery to " + " and ".join([govtrack.getMemberOfCongress(g)["name"] for g in recips]) + "."
			
		return ret
		
	def review_status(self):
		if self.status == UserComment.COMMENT_NOT_REVIEWED:
			return None
		if self.status == UserComment.COMMENT_ACCEPTED:
			return "This comment was initially rejected by POPVOX staff for violating our acceptable language policy, but after your changes the comment has been restored."
		if self.status == UserComment.COMMENT_REJECTED:
			return "This comment has been rejected by POPVOX staff for violating our acceptable language policy. We encourage you to revise your comment so that it keeps a civil tone. We will review your comment after it has been revised."
		if self.status == UserComment.COMMENT_REJECTED_STOP_DELIVERY:
			return "This comment has been rejected by POPVOX staff for violating our acceptable language policy and it will not be delivered to Congress. We encourage you to revise your comment so that it keeps a civil tone. We will review your comment after it has been revised."
		if self.status == UserComment.COMMENT_REJECTED_REVISED:
			return "This comment was rejected by POPVOX staff for violating our acceptable language policy. You have revised the comment, and POPVOX staff will review it soon."
		return None

class UserCommentOfflineDeliveryRecord(models.Model):
	comment = models.ForeignKey(UserComment)
	target = models.ForeignKey(MemberOfCongress, db_index=True)
	batch = models.IntegerField(blank=True, null=True)
	failure_reason = models.CharField(max_length=16)
	class Meta:
		unique_together = (("target", "comment"),)

class BillSimilarity(models.Model):
	"""Stores a similarity value between two bills, where bill1.id < bill2.id."""
	bill1 = models.ForeignKey(Bill, related_name="similar_bills_one", db_index=True)
	bill2 = models.ForeignKey(Bill, related_name="similar_bills_two", db_index=True)
	similarity = models.FloatField()
	class Meta:
		unique_together = (("bill1", "bill2"),)

if not "LOADING_DUMP_DATA" in os.environ:
	# Make sure that we have MoC and CC records for all people
	# and committees that exist in Congress. Accessing these
	# models now prevents any further ManyToMany relationships
	# that reference these models from working and yields a
	# "Can't resolve keyword ... into field" error on querying
	# the M2M field.
	MemberOfCongress.init_members()
	CongressionalCommittee.init_committees()

