from django.db import models
from django.contrib.auth.models import User
import django.db.models.signals
from django.core.mail import send_mail
from django.core.cache import cache
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.contrib.humanize.templatetags.humanize import ordinal
from django.template.defaultfilters import truncatewords

import sys
import os, os.path
from datetime import datetime, timedelta
from urllib import urlopen
from xml.dom import minidom
import re
import hashlib

from tinymce import models as tinymce_models
from picklefield import PickledObjectField

import settings

import govtrack

from writeyourrep.models import DeliveryRecord

from popvox import http_rest_json

# GENERAL METADATA #

class MailListUser(models.Model):
	email = models.EmailField(db_index=True, unique=True)
	def __unicode__(self):
		return self.email

class RawText(models.Model):
	name = models.SlugField(db_index=True, unique=True)
	format = models.IntegerField(choices=[(0, "Raw HTML"), (1, "Markdown"), (2, "Email Message Source (MIME)")], default=0)
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
		raise Exception("Invalid for MIME type messages.")
	def is_mime(self):
		return self.format == 2

class IssueArea(models.Model):
	"""An issue area."""
	slug = models.SlugField(db_index=True, unique=True)
	name = models.CharField(max_length=100, db_index=True, unique=True)# uniqueness is crucial for parsing LoC data, assumed by scrapers
	shortname = models.CharField(max_length=16, blank=True, null=True)
	parent = models.ForeignKey('self', blank=True, null=True, db_index=True, related_name = "subissues", on_delete=models.SET_NULL)
	class Meta:
		ordering = ['name']
	def __unicode__(self):
		return self.name

	def orgs(self):
		return (Org.objects.filter(visible=True, issues=self) | Org.objects.filter(visible=True, issues__parent=self)).distinct()
		
class MemberOfCongress(models.Model):
	"""A Member of Congress or former member."""
	
	# The primary key is the GovTrack ID.
	pvurl = models.CharField(max_length=100,blank=True,null=True)
	documents = models.ManyToManyField("PositionDocument", blank=True, related_name="owner_memberofcongress")


	def __unicode__(self):
		return unicode(self.id) + u" " + self.name()
	def name(self):
		return self.info()["name"]
	def lastname(self):
		return self.info()["lastname"]
	def party(self):
		if "party" in self.info():
			return self.info()["party"]
		else:
			return "?"
			
	def state_district(self):
		x = self.info()
		return x["state"] + ("-" + str(x["district"]) if x["type"] == "rep" else "")
			
	def info(self):
		return govtrack.getMemberOfCongress(self.id)
	
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
	
	BILL_TYPE_CHOICES = [ ('h', 'H.R.'), ('s', 'S.'), ('hr', 'H.Res.'), ('sr', 'S.Res.'), ('hc', 'H.Con.Res.'), ('sc', 'S.Con.Res.'), ('hj', 'H.J.Res.'), ('sj', 'S.J.Res.'), ('ha', 'House Amendment'), ('sa', 'Senate Amendment'), ('dh', 'House Draft'), ('ds', 'Senate Draft'), ('x', 'Generic Proposal') ]

	# the iPad app relies on the House/Senate distinction being made in the first character of the slug (h/s)
	BILL_TYPE_SLUGS = [ ('h', 'hr'), ('s', 's'), ('hr', 'hres'), ('sr', 'sres'), ('hc', 'hconres'), ('sc', 'sconres'), ('hj', 'hjres'), ('sj', 'sjres'), ('ha', 'hamdt'), ('sa', 'samdt'), ('dh', 'hdraft'), ('ds', 'sdraft'), ('x', 'x') ]
		# when adding a type, see getChamberOfNextVote
	
	slug_to_type = {}
	for t, s in BILL_TYPE_SLUGS:
		slug_to_type[s] = t
	
	congressnumber = models.IntegerField()
	billtype = models.CharField(max_length=2, choices=BILL_TYPE_CHOICES)
	billnumber = models.IntegerField(help_text="For House Draft/Senate Draft/Proposal-type bills, just number them sequentially starting with 1. For bills, resolutions, and amendments, this must be the official number.")
	vehicle_for = models.ForeignKey('Bill', related_name='replaced_vehicle', blank=True, null=True, on_delete=models.SET_NULL)
	sponsor = models.ForeignKey(MemberOfCongress, blank=True, null=True, db_index=True, related_name = "sponsoredbills", on_delete=models.PROTECT)
	cosponsors = models.ManyToManyField(MemberOfCongress, blank=True, related_name="cosponsoredbills")
	committees = models.ManyToManyField(CongressionalCommittee, blank=True, related_name="bills")
	topterm = models.ForeignKey(IssueArea, db_index=True, blank=True, null=True, related_name="toptermbills", on_delete=models.SET_NULL)
	issues = models.ManyToManyField(IssueArea, blank=True, related_name="bills")
	title = models.TextField()
	description = models.TextField(blank=True, null=True)
	introduced_date = models.DateField()
	current_status = models.TextField(help_text="For non-bill actions, enter DRAFT.")
	current_status_date = models.DateTimeField(help_text="For non-bill actions, just choose today.", db_index=True)
	num_cosponsors = models.IntegerField()
	latest_action = models.TextField(blank=True)
	reintroduced_as = models.ForeignKey('Bill', related_name='reintroduced_from', blank=True, null=True, db_index=True, on_delete=models.SET_NULL)
	migrate_to = models.ForeignKey('Bill', related_name='migrate_from', blank=True, null=True, on_delete=models.SET_NULL)
	
	street_name = models.CharField(max_length=128, blank=True, null=True, help_text="Give a 'street name' for the bill. Enter it in a format that completes the sentence 'What do you think of....', so if it needs to start with 'the', include 'the' in lowercase. For non-bill actions, this is an alternate short name for the action.")
	ask = models.CharField(max_length=100, blank=True, null=True, help_text="Use for Non-Bill Actions only. This field changes the 'how should your member of congress vote' text on the bill page.")
	notes = models.TextField(blank=True, null=True, help_text="Special notes to display with the bill. Enter HTML.")
	hashtags = models.CharField(max_length=128, blank=True, null=True, help_text="List relevant hashtags for the bill. Separate hashtags with spaces. Include the #-sign.")
	hold_metadata = models.BooleanField(default=False)
	comments_to_chamber = models.CharField(max_length=1, choices=[('s', 'Senate'), ('h', 'House',), ('c', 'Congress House+Senate')], blank=True, null=True, help_text="This is required for Generic Proposal-type bill actions to route messages to the right place.")
	
	upcoming_event_post_date = models.DateTimeField(help_text="When adding an upcoming event, set this date to the date you are posting the information (i.e. now).", blank=True, null=True, db_index=True)
	upcoming_event = models.CharField(max_length=64, blank=True, null=True, help_text="The text of an upcoming event. Start with a verb that would follow the bill number, e.g. \"is coming up for a vote on Aug. 1\". Do not end with a period.")

	srcfilehash = models.CharField(max_length=32, blank=True)
	
	class Meta:
			ordering = ['-congressnumber', '-billtype', '-billnumber']
			unique_together = (("congressnumber", "billtype", "billnumber", "vehicle_for"),)

	_govtrack_metadata = None
	
	def __unicode__(self):
		return self.title[0:30]
	def get_absolute_url(self):
		return self.url()

	def url(self):
		vehicleid = ""
		if self.vehicle_for_id != None:
			vehicleid = 1
			b = self
			while b.replaced_vehicle.exists():
				vehicleid += 1
				b = b.replaced_vehicle.all()[0]
			vehicleid = "-" + str(vehicleid)
		return "/bills/us/" + str(self.congressnumber) + "/" + self.billtypeslug() + str(self.billnumber) + vehicleid
	def billtypeslug(self):
		return [x[1] for x in Bill.BILL_TYPE_SLUGS if x[0]==self.billtype][0]

	def is_bill(self):
		return self.billtype in ('h', 's', 'hr', 'sr', 'hj', 'sj', 'hc', 'sc')
	def is_officially_numbered(self):
		return self.billtype in ('h', 's', 'hr', 'sr', 'hj', 'sj', 'hc', 'sc', 'ha', 'sa')

	def proposition_type(self):
		if self.billtype in ('h', 's'): return "bill"
		if self.billtype in ('hr', 'sr', 'hj', 'sj', 'hc', 'sc'): return "resolution"
		if self.billtype in ('ha', 'sa'): return "amendment"
		if self.billtype in ('dh', 'ds'): return "draft"
		return "proposal"

	def govtrack_metadata(self):
		if not self.is_bill(): raise Exception("Invalid call on non-bill.")
		if self._govtrack_metadata == None :
			self._govtrack_metadata = govtrack.getBillMetadata(self)
		return self._govtrack_metadata
		
	def govtrack_code(self):
		if not self.is_bill(): raise Exception("Invalid call on non-bill.")
		return self.billtype + str(self.congressnumber) + "-" + str(self.billnumber)
	def govtrack_link(self):
		if not self.is_bill(): raise Exception("Invalid call on non-bill.")
		return "http://www.govtrack.us/congress/bill.xpd?bill=" + self.govtrack_code()
	
	@property
	def nicename(self):
		# The nice name of a bill is how a bill is referred to on first
		# reference in a non-official context. It is the street name, if
		# one is set, with the bill number, if the bill has one, otherwise
		# the title.
		if self.street_name:
			if self.is_officially_numbered():
				return self.displaynumber() + ": " + self.street_name[0].upper() + self.street_name[1:]
			else:
				return self.street_name[0].upper() + self.street_name[1:]
		return self.title
				
	@property
	def shortname(self):
		# The short name of a bill is how a bill is normally referred to on
		# second reference. For actual bills, it is the bill number. For
		# non-bill items, it is the street name if one is assigned, otherwise
		# the title.
		if self.is_officially_numbered():
			return self.displaynumber()
		else:
			if not self.street_name:
				return self.title
			else:
				return self.street_name[0].upper() + self.street_name[1:]
	
	# The display number returns the official number of a bill for display in a separate
	# column from the bill title, or a hyphen if the bill item has no official number.
	def displaynumber(self):
		if not self.is_officially_numbered(): return u"\u2015"
		ret = self.displaynumber_nosession()
		if self.congressnumber != govtrack.CURRENT_CONGRESS :
			ret += " (" + str(self.congressnumber) + govtrack.ordinate(self.congressnumber) + ")"
		return ret
	def displaynumber_nosession(self):
		if not self.is_officially_numbered(): return u"\u2015"
		return self.get_billtype_display() + " " + str(self.billnumber)
		
	def title_no_number(self):
		if self.billtype in ('dh', 'ds', 'x'): # these don't have numbered titles
			return self.title
		return self.title[self.title.index(":")+2:]
	def title_parens_if_too_long(self):
		# this is used for pre-populating a comment on a bill
		if not self.is_officially_numbered():
			return self.title
		title = truncatewords(self.title, 15)
		if "..." not in title:
			return title
		title = re.sub(r"To amend (section [^ ]+ of )?title [^ ,]+, United States Code, ", "", self.title_no_number())
		return self.displaynumber() + " (\"" + truncatewords(title, 15).replace(" ...", "") + "\")"
	
	def status(self):
		if self.is_bill():
			return govtrack.getBillStatus(self)
		else:
			return "Status information is only available for introduced bills."
	def status_advanced(self):
		if self.is_bill():
			return govtrack.getBillStatusAdvanced(self, False)
		else:
			return "N/A"
	def status_advanced_abbreviated(self):
		if self.is_bill():
			return govtrack.getBillStatusAdvanced(self, True)
		else:
			return "N/A"
	def status_sentence(self):
		if self.is_bill():
			return govtrack.getBillStatusSentence(self)
		else:
			return "N/A"
	def isAlive(self):
		# alive = pending further Congressional action
		if not self.is_bill(): return self.congressnumber == govtrack.CURRENT_CONGRESS
		return govtrack.billFinalStatus(self) == None
	def getDeadReason(self):
		# dead = no longer pending action because it passed, failed, or died in a previous session
		if not self.is_bill():
			if self.congressnumber != govtrack.CURRENT_CONGRESS:
				return "was proposed in a previous session of Congress"
			return None
		return govtrack.billFinalStatus(self)
	def died(self):
		# died is the specific state of having failed to be passed in a previous session
		if not self.is_bill(): return False
		return govtrack.billFinalStatus(self, "died") == "died"
	def getChamberOfNextVote(self):
		# bill must be alive
		if self.comments_to_chamber and self.comments_to_chamber in ('h', 's'): return self.comments_to_chamber # for x-type bills and to override
		if self.billtype in ('ha', 'dh'): return 'h' # house drafts, amendments
		if self.billtype in ('sa', 'ds'): return 's' # senate drafts, amendments
		if self.billtype in ('x', ): return None # not applicable
		return govtrack.getChamberOfNextVote(self)
	def reintroduced_from_all(self):
		ret = []
		br = (self,)
		while True:
			rein = list(Bill.objects.filter(reintroduced_as__in=br))
			if len(rein) == 0: break
			ret.extend(rein)
			br = rein
		return ret
		
	def latest_action_formatted(self):
		def parse_line(line):
			from popvox.views.utils import formatDateTime
			if line == "": return ""
			date, text = line.split("\t")
			return (formatDateTime(govtrack.parse_govtrack_date(date), withtime=False), text)
			
		return [parse_line(rec) for rec in self.latest_action.split("\n")]
		
	def campaign_positions(self, position=None):
		qs = self.orgcampaignposition_set.filter(campaign__visible=True, campaign__org__visible=True).select_related("campaign", "campaign__org")
		if position:
			qs = qs.filter(position=position)
		return qs
	
	def hashtag(self, always_include_session=False):
		if self.hashtags not in (None, ""):
			return self.hashtags
		bt = self.billtypeslug()
		bs = ""
		if self.congressnumber < govtrack.CURRENT_CONGRESS or always_include_session:
			bs = "/" + str(self.congressnumber)
		return "#" + bt + str(self.billnumber) + bs
		
	@classmethod
	def from_hashtag(cls, hashtag):
		m = re.match(r"^\#([a-z]+)(\d+)(/(\d+))?$", hashtag)
		if not m: raise ValueError()
		return Bill.objects.get(
			congressnumber = m.group(4) if m.group(4) else govtrack.CURRENT_CONGRESS,
			billtype = Bill.slug_to_type[m.group(1)],
			billnumber = m.group(2),
			vehicle_for = None)
		
	def current_text(self):
		try:
			return self.documents.filter(doctype=100).order_by('-created')[0]
		except IndexError:
			return None

	def make_vehicle(self):
		import copy
		newbill = copy.copy(self)
		newbill.id = None
		newbill.billnumber = -1 # cant have identical number at first
		newbill.save()

		self.vehicle_for = newbill
		self.save()

		newbill.billnumber = self.billnumber
		newbill.save()

		return newbill

	def migrate(self):
		if not self.migrate_to: raise ValueError("Set migrate_to.")
		OrgCampaignPosition.objects.filter(bill=self).update(bill=self.migrate_to)
		PositionDocument.objects.filter(bill=self).exclude(doctype=100).update(bill=self.migrate_to)
		UserComment.objects.filter(bill=self).update(bill=self.migrate_to)

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
		m = re.match(r"([a-z]+)(\d+)(-\d+)?", fields[4])
		billtype = Bill.slug_to_type[m.group(1)]
		billnumber = int(m.group(2))
		vehicle_number = m.group(3)
	except :
		raise Exception("Invalid bill id.")
	bill = Bill.objects.filter(congressnumber=congressnumber, billtype=billtype, billnumber=billnumber, vehicle_for=None)
	if len(bill) == 0:
		raise Exception("No bill with that number exists.")
	else:
		return bill[0]
		
# ORGANIZATIONS #

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
	updated = models.DateTimeField(auto_now_add=True)
	visible = models.BooleanField(default=False)
	createdbyus = models.BooleanField(default=False)
	approved = models.BooleanField(default=False)
	fan_count_sort_order = models.IntegerField(default=0, db_index=True)
	
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
		
	def positions(self):
		return OrgCampaignPosition.objects.filter(campaign__visible=True, campaign__org=self).order_by("-campaign__default", "campaign__name", "order", "-updated")
	def positions_can_comment(self):
		return [p for p in self.positions() if p.bill.isAlive() or p.bill.died()]
		
	def is_admin(self, user):
		if user.is_anonymous():
			return False
		return user.is_superuser or user.is_staff or len(UserOrgRole.objects.filter(user=user, org=self)) > 0
 
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
				if self.slug != "" and not Org.objects.filter(slug=self.slug).exists():
					return

		# else, generate slug from all uppercase letters in name except letters within parenthesis
		self.slug = ""
		for c in re.sub(r"\(.*?\)", "", self.name):
			if c == c.upper() and c != c.lower():
				self.slug += c.lower()
		if self.slug != "" and not Org.objects.filter(slug=self.slug).exists():
			return
		
		if self.slug == "": self.slug = "org"
			
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
					fbdata = json.load(urlopen("http://graph.facebook.com/" + fbid + "?metadata=1"))
					if type(fbdata) != dict:
						pass
					elif "likes" in fbdata:
						updateRecord(OrgExternalMemberCount.FACEBOOK_FANS, int(fbdata["likes"]))
					elif fbdata.get("type", "") == "user":
						# look for an org administrator who has a Facebook login for the user
						# so that we can count the number of friends....
						from registration.models import AuthRecord
						for ar in AuthRecord.objects.filter(provider="facebook", uid=fbdata.get("id", ""),
							user__orgroles__org=self):
							frienddata = json.load(urlopen("https://graph.facebook.com/" + fbid + "/friends?access_token=" + quote_plus(ar.auth_token["access_token"])))
							updateRecord(OrgExternalMemberCount.FACEBOOK_FANS,  len(frienddata["data"]))
							break
						else:
							print "facebook person page without auth", self
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
				er = t.getElementsByTagName('error')
				if len(er) > 0:
					print self.twittername.encode("utf8"), er[0].firstChild.data.encode("utf8")
				else:
					fc = t.getElementsByTagName('followers_count')
					count = int(fc[0].firstChild.data)
					updateRecord(OrgExternalMemberCount.TWITTER_FOLLOWERS, count)
			except Exception, e:
				print self.twittername.encode("utf8"), e
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

	def service_account(self, create=False):
		if not create:
			return ServiceAccount.objects.get(org=self)
		else:
			return ServiceAccount.get_or_create(org=self)
			
	def partisan_points(self):
		# Count up the number of endorsed/opposed bills for which the sponsor's party is known,
		# and a "net Democrat" score that adds 1 for each Democratic bill endorsed or each
		# Republican bill opposed, and -1 for the reverse.
		count = 0
		net_dem = 0
		for p in OrgCampaignPosition.objects.filter(campaign__org=self).exclude(position="0").select_related("bill", "sponsor"):
			m = p.bill.sponsor
			if m == None: continue
			count += 1
			s = 0
			if m.party() == "D": s = 1
			if m.party() == "R": s = -1
			if p.position == "-": s *= -1
			net_dem += s
			
		# A low total count means we don't have enough data.
		if count < 3: return ("nodata", "This organization's legislative agenda on POPVOX does not have enough bills to judge its partisanship.", count)
		
		net_dem = float(net_dem) / float(count)
		if net_dem < -.5:
			return ("republican", "Organization tends to endorse Republican bills.", count)
		elif net_dem < .5:
			return ("independent", "Organization's legislative agenda is split between Democratic and Republican bills.", count)
		else:
			return ("democrat", "Organization tends to endorse Democratic bills.", count)
 
class OrgContact(models.Model):
	"""A contact record for an Org displayed to legislative staff."""
	
	org = models.ForeignKey(Org, related_name="contacts", db_index=True, on_delete=models.CASCADE)
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
	org = models.ForeignKey(Org, on_delete=models.CASCADE) # implicitly indexed by the unique-together
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
	def visible_state(self):
		if not self.org.approved: return "org-needs-approval"
		if not self.org.visible: return "org-not-published"
		if not self.visible: return "campaign-not-published"
		return "visible"

class OrgExternalMemberCount(models.Model):
	"""An external count of a size of an organization, e.g. as reported by the org or from Facebook or Twitter."""
	AS_REPORTED = 0
	FACEBOOK_FANS = 1
	TWITTER_FOLLOWERS = 2
	SOURCE_TYPES = [0, 1, 2]
	org = models.ForeignKey(Org, on_delete=models.CASCADE) # implicitly indexed by the unique_together
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
	campaign = models.ForeignKey(OrgCampaign, related_name="positions", on_delete=models.CASCADE) # implicitly indexed by the unique_together
	bill = models.ForeignKey(Bill, on_delete=models.PROTECT)
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
	def get_service_account_campaign(self, create=True):
		if create:
			acct = self.campaign.org.service_account(create=True)
			campaign, is_new = ServiceAccountCampaign.objects.get_or_create(
				account = acct,
				bill = self.bill,
				position = self.position)
		else:
			acct = self.campaign.org.service_account(create=False)
			campaign = acct.campaigns.get(
				bill = self.bill,
				position = self.position)
		return campaign
	def has_service_account_campaign(self):
		try:
			return self.get_service_account_campaign(create=False) != None
		except:
			return False
	def verb(self):
		if self.position == "+": return "endorsed"
		if self.position == "-": return "opposed"
		if self.position == "0": return "posted a statement on"

# POSITION DOCUMENTS and BILL TEXT (for iPad App) #

class PositionDocument(models.Model):
	DOCTYPES = [(0, 'Press Release'), (1, 'Floor Introductory Statement'), (2, 'Dear Colleague Letter'), (3, "Report"), (4, "Letter to Congress"), (5, "Coalition Letter"), (99, 'Other'), (100, 'Bill Text'), (101, 'Bill Text Comparison')]
	bill = models.ForeignKey(Bill, related_name="documents", db_index=True, on_delete=models.PROTECT)
	doctype = models.IntegerField(choices=DOCTYPES)
	title = models.CharField(max_length=128)
	text = tinymce_models.HTMLField(blank=True) #models.TextField() # HTML document body
	link = models.URLField(blank=True, null=True)
	pdf_url = models.CharField(max_length=128, blank=True, null=True)
	created = models.DateTimeField()
	updated = models.DateTimeField(auto_now=True, db_index=True)
	key = models.CharField(max_length=16, blank=True, null=True)
	pdf = models.TextField(blank=True, null=True) # base64 encoded
	txt = models.TextField(blank=True, null=True) # document plain text
	xml = models.TextField(blank=True, null=True) # base64 encoded
	toc = models.TextField(blank=True, null=True) # json encoded
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
		
class DocumentPage(models.Model):
	document = models.ForeignKey(PositionDocument, related_name="pages", on_delete=models.CASCADE)
	page = models.IntegerField()
	text = models.TextField(blank=True, null=True) # base64 encoded utf-8
	html = models.TextField(blank=True, null=True) # base64 encoded utf-8
	
	png_file = models.FileField(upload_to="submitted/documentpage/binary", blank=True, null=True)
	pdf_file = models.FileField(upload_to="submitted/documentpage/binary", blank=True, null=True)
	
	class Meta:
		unique_together = (('document', 'page'),)
		
		
# USER PROFILES AND COMMENTS #

class UserProfile(models.Model):
	"""A user profile extends the basic user model provided by Django."""
	
	# NOTE: When adding required fields, make sure to update the
	# user_saved_callback to initialize the fields on new user profiles
	# or put in a default value.
	
	user = models.OneToOneField(User, on_delete=models.CASCADE)
	
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
		for c in self.user.comments.order_by("-created").select_related("address"):
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
			
	def service_accounts(self, create=False):
		if create:
			# Create a service account for this user. If the user is an org admin,
			# create a service account for each org the user admins. Otherwise,
			# create a user-specific service account.
			
			orgs = Org.objects.filter(admins__user = self.user)
			if orgs.count() > 0:
				for org in orgs:
					ServiceAccount.get_or_create(org=org)
			else:
				ServiceAccount.get_or_create(user=self.user)
		
		return ServiceAccount.objects.filter(user = self.user) \
			| ServiceAccount.objects.filter(org__admins__user = self.user)
	
	def has_active_service_account(self):
		return ServiceAccountCampaignActionRecord.objects.filter(campaign__account__in=self.service_accounts()).exists()

	def matching_sacar_orgs(self):
		orgs = set()
		for sacar in ServiceAccountCampaignActionRecord.objects.filter(email=self.user.email):
			orgs.add(sacar.campaign.account)
		return orgs
	
def user_saved_callback(sender, instance, created, **kwargs):
	if created:
		p = UserProfile()
		p.user = instance
		p.save()

		send_mail('New account: ' + instance.username, 'New account created: ' + instance.username + " (" + instance.email + ")", "info@popvox.com", ["marci@popvox.com", "rachna@popvox.com"], fail_silently=True)
if not "LOADING_FIXTURE" in os.environ:
	# When we're loading from a fixture, we get the UserProfile record later so we cannot
	# create it now or we get a duplicate value for index error.
	django.db.models.signals.post_save.connect(user_saved_callback, sender=User)

class UserOrgRole(models.Model):
	user = models.ForeignKey(User, related_name="orgroles", on_delete=models.CASCADE) # implicitly indexed by the unique_together
	org = models.ForeignKey(Org, related_name="admins", db_index=True, on_delete=models.CASCADE)
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
	user = models.OneToOneField(User, related_name="legstaffrole", db_index=True, on_delete=models.CASCADE)
	member = models.ForeignKey(MemberOfCongress, blank=True, null=True, db_index=True, db_column="member", on_delete=models.PROTECT)
	committee = models.ForeignKey(CongressionalCommittee, blank=True, null=True, db_index=True, to_field="code", db_column="committee", on_delete=models.PROTECT)
	position = models.CharField(max_length=50)
	verified = models.BooleanField(default=False)
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
		
class PostalAddress(models.Model):
	"""A postal address."""
	
	# We need to put an index over state,congressionaldistrict so we can quickly
	# find comments within a district.

	# An address is tied to a user so that if we delete a user account, we also
	# delete any addresses they have entered.
	user = models.ForeignKey(User, db_index=True, on_delete=models.CASCADE)

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
	county = models.CharField(max_length=64, blank=True, null=True)
	cdyne_response = models.TextField(blank=True, null=True)

	flagged_hold_mail = models.BooleanField(default=False)

	#class Meta:
	#		ordering = ["nameprefix"]

	PREFIXES = 	('', 'Mr.', 'Mrs.', 'Ms.', 'Dr.', 'Reverend', 'Sister', 'Pastor')
	SUFFIXES = 	('', 'Jr.', 'Sr.', 'I', 'II', 'III')
	
	def __unicode__(self):
		try:
			user = unicode(self.user) + ": "
		except:
			user = "" # un-initialized, raises DoesNotExist
		return user + self.firstname +  " " + self.lastname + "\n" + self.address1 + ("\n" + self.address2 if self.address2 != "" else "") + "\n" + self.city + ", " + self.state + " " + self.zipcode + " (CD" + str(self.congressionaldistrict) + ")"
	
	def save(self, *args, **kwargs):
		# After saving a PostalAddress, update the state and district of any related
		# UserComments.
		super(PostalAddress, self).save(*args, **kwargs)
		self.usercomments.all().update(state=self.state, congressionaldistrict=self.congressionaldistrict)
		
	def load_from_form(self, fields, validate=True):
		self.nameprefix = fields["useraddress_prefix"]
		self.firstname = fields["useraddress_firstname"]
		self.lastname = fields["useraddress_lastname"]
		self.namesuffix = fields["useraddress_suffix"]
		self.address1 = fields["useraddress_address1"]
		self.address2 = fields["useraddress_address2"]
		self.city = fields["useraddress_city"]
		self.state = fields["useraddress_state"].upper()
		self.zipcode = fields["useraddress_zipcode"]
		self.phonenumber = fields["useraddress_phonenumber"]
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
		
	def name_string(self):
		return self.nameprefix + " " + self.firstname + " " + self.lastname + (", " + self.namesuffix if self.namesuffix else "")
		
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
		
	def normalize(self):
		from writeyourrep.addressnorm import verify_adddress
		verify_adddress(self, validate=False)
		self.save()
		
class UserComment(models.Model):
	"""A comment by a user on a bill."""
	
	POSITION_CHOICES = [ ('+', 'Support'), ('-', 'Oppose') ]

	COMMENT_NOT_REVIEWED = 0 # note that these values are hard-coded in several templates
	COMMENT_ACCEPTED = 1
	COMMENT_REJECTED = 2
	COMMENT_REJECTED_STOP_DELIVERY = 3
	COMMENT_REJECTED_REVISED = 4
	COMMENT_HOLD = 5
	
	METHOD_SITE = 0
	METHOD_CUSTOMIZED_PAGE = 1
	METHOD_WIDGET = 2
	METHOD_NAMES = { METHOD_SITE: "POPVOX.com", METHOD_CUSTOMIZED_PAGE: "PV.com Customized Landing Page", METHOD_WIDGET: "Write Congress Widget" }

	user = models.ForeignKey(User, related_name="comments", db_index=True, on_delete=models.CASCADE) # user authoring the comment
	bill = models.ForeignKey(Bill, related_name="usercomments", db_index=True, on_delete=models.PROTECT)
	
	# if this value changes, we should delete the UserCommentDiggs the user left on
	# this bill.
	position = models.CharField(max_length=1, choices=POSITION_CHOICES)
	
	message = models.TextField(blank=True, null=True)

	address = models.ForeignKey(PostalAddress, db_index=True, related_name="usercomments", on_delete=models.PROTECT) # current address at time of writing

	created = models.DateTimeField(auto_now_add=True)
	updated = models.DateTimeField(auto_now_add=True)
	status = models.IntegerField(choices=[(COMMENT_NOT_REVIEWED, 'Not Reviewed (Default)'), (COMMENT_ACCEPTED, 'Reviewed & Accepted'), (COMMENT_REJECTED, 'Rejected -- Still Deliver'), (COMMENT_REJECTED_STOP_DELIVERY, 'Rejected -- Stop Delivery'), (COMMENT_REJECTED_REVISED, 'Rejected-then-Revised - Waiting Approval'), (COMMENT_HOLD, 'Hold Delivery')], default=COMMENT_NOT_REVIEWED)
	method = models.IntegerField(choices=[(METHOD_SITE, 'Site'), (METHOD_CUSTOMIZED_PAGE, 'Customized Landing Page'), (METHOD_WIDGET, 'Widget')])

	# an approximate zero-based sequence number of this comment on the bill, so each comment knows if it was the 1st, 2nd, etc.
	seq = models.IntegerField()
		# to initialize this column:
		# for b in Bill.objects.all():
		#  seq = 0
		#  for c in b.usercomments.order_by("created"):
		#   c.seq = seq
		#   c.save()
		#   seq += 1
		#  print b

	# repeated from the address for better indexing
	state = models.CharField(max_length=2)
	congressionaldistrict = models.IntegerField() # 0 for at-large, otherwise cong. district number

	# links to the user's outgoing shares
	tweet_id = models.BigIntegerField(blank=True, null=True)
	fb_linkid = models.CharField(max_length=32, blank=True, null=True)

	# records any private notes about how we are moderating the comment
	moderation_log = models.TextField(blank=True, null=True)
	
	# This holds all delivery attempts at this comment. some of the
	# delivery attempts have been superceded by their re-send
	# attempts. Also when we send letters to senators we may
	# send it to both senators, so this records all delivery attempts
	# for all of the individuals the message gets sent to.
	delivery_attempts = models.ManyToManyField(DeliveryRecord, blank=True, related_name="comments")
	
	class Meta:
			verbose_name = "user comment"
			ordering = ["-created"]
			unique_together = (("user", "bill"), ("bill", "seq"))
	def __unicode__(self):
		return self.user.username + " -- " + self.bill.displaynumber() + " -- " + (self.message[0:40] if self.message != None else "NONE") + " | " + self.delivery_status()

	def get_absolute_url(self):
		return self.bill.url() + "/comment/" + str(self.id)

	def url(self):
		return self.get_absolute_url()
	
	def verb(self, tense="present"):
		# the verb used to describe the comment depends on when the comment
		# was left in the stages of a bill's progress.
		if self.created.date() <= govtrack.getCongressDates(self.bill.congressnumber)[1]:
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
	def verb_imp(self):
		return self.verb(tense="imp")
	def verb_ing(self):
		return self.verb(tense="ing")
	def verb_past(self):
		return self.verb(tense="past")

	def shares(self):
		import shorturl
		return shorturl.models.Record.objects.filter(target=self)

	def share_hits(self):
		return self.shares().aggregate(models.Sum("hits"))["hits__sum"]

	def get_recipients(self):
		if self.bill.comments_to_chamber:
			ch = self.bill.comments_to_chamber # s, h, or c to direct message to both chambers of Congress
		else:
			ch = self.bill.getChamberOfNextVote()
			if ch == None:
				return "The comment will not be delivered because the bill is not pending a vote in Congress."
			
		d = self.address.state + str(self.address.congressionaldistrict)
		
		# Get the recipients according to the user's current representation in the House or
		# Senate, depending on where the next action for the bill is.
		govtrackrecipients = []
		if ch == "s":
			# send to all of the senators for the state
			govtrackrecipients = govtrack.getMembersOfCongressForDistrict(d, moctype="sen")
			if len(govtrackrecipients) == 0:
				# state has no senators, fall back to representative
				govtrackrecipients = govtrack.getMembersOfCongressForDistrict(d, moctype="rep")
		elif ch == "h":
			govtrackrecipients = govtrack.getMembersOfCongressForDistrict(d, moctype="rep")
		else: # ch == "c", direct messages to all reps
			govtrackrecipients = govtrack.getMembersOfCongressForDistrict(d)
			
		# Remove recipients for whom we've already delivered to another Member in the same
		# office, because of e.g. a resignation followed by a replacement. This would raise a M2M
		# error if the user comment isn't stored in the database yet, but happens when we're just
		# testing for delivery of a hypothetical comment.
		if self.id != None:
			govtrackrecipients = [g for g in govtrackrecipients if
				not self.delivery_attempts.exclude(target__govtrackid=g["id"]).filter(success = True, target__office=g["office_id"]).exists()]
			
		return govtrackrecipients
		
	def get_recipients_display(self):
		recips = self.get_recipients()
		if not type(recips) == list:
			# Normally, show recipients that we would deliver to now.
			# But if the bill is dead, show who we delivered to already, if any.
			delivered_recips = self.delivery_attempts.filter(success=True, next_attempt__isnull=True)
			if delivered_recips.count():
				recips = [govtrack.getMemberOfCongress(d.target.govtrackid) for d in delivered_recips]
			else:
				return "[" + recips + "]"
		def nicename(name):
			import re
			return re.sub(r"\s*\[.*\]", "", name)
		recips = [nicename(m["name"]) for m in recips]
		if len(recips) > 1:
			recips[-1] = "and " + recips[-1]
		if len(recips) <= 2:
			return " ".join(recips)
		else:
			return ", ".join(recips)
	
	def delivery_status(self, ref1="Your message", ref2="you"):
		from writeyourrep.models import Endpoint
		
		recips_ = self.get_recipients()
		recips = [g["id"] for g in recips_] if type(recips_) == list else []
		
		# Group successful deliveries by date and method, and unsuccessful deliveries uniquely by target.
		retd = { }
		for d in self.delivery_attempts.filter(next_attempt__isnull = True):
			if d.success:
				key = (d.created.strftime("%x"), d.method)
				if not key in retd:
					retd[key] = []
				retd[key].append(d.target.govtrackid)
				
			# don't talk about failures when the user didn't write a message, or
			# if we are no longer targetting that office as a recipient.
			elif self.message != None and d.target.govtrackid in recips:
				retd[govtrack.getMemberOfCongress(d.target.govtrackid)["sortkey"]] = "We had trouble delivering " + ref1.lower() + " to " + govtrack.getMemberOfCongress(d.target.govtrackid)["name"] + " but we will try again. "

			# remove from list so we know who we haven't attempted yet
			if d.target.govtrackid in recips:
				recips.remove(d.target.govtrackid)

		# Serialize into text for the user.
		retk = list(retd.keys())
		retk.sort(key = lambda x : (type(x) != tuple, x))
		ret = ""
		for k in retk:
			if type(k) == tuple:
				if k[1] != Endpoint.METHOD_OFFSITE_DELIVERY:
					verb = "delivered"
				else:
					verb = "sent"
				ret += ref1 + " was " + verb + " to " + " and ".join([govtrack.getMemberOfCongress(g)["name"] for g in retd[k]]) + " on " + k[0] + ". "
			else:
				ret += retd[k]
				
		# If we had nothing
		if ret == "" and len(recips) == 0:
			if type(recips_) == str:
				return recips_
			return "The comment cannot be delivered at this time because the Congressional office(s) that represents " + ref2 + " is/are currently vacant."
			
		# Don't pre-sage these deliveries because if we can't deliver electronically we don't bother.
		# But we can report what was delivered.
		if self.message == None:
			return ret
		
		if len(recips) > 0:
			ret += ref1 + " is pending delivery to " + " and ".join([govtrack.getMemberOfCongress(g)["name"] for g in recips]) + "."
			
		return ret

	def delivery_status_public(self):
		return self.delivery_status(ref1="This letter", ref2=self.user.username)
		
	def has_been_delivered(self):
		return self.delivery_attempts.filter(success=True).exists()
		
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
		if self.status == UserComment.COMMENT_HOLD:
			return "Your comment is being held. We've probably informed you via email."
		return None

	def appreciates_count(self):
		return UserCommentDigg.objects.filter(comment=self, diggtype=UserCommentDigg.DIGG_TYPE_APPRECIATE).count()
		
	def referrers(self):
		return [ucr.referrer for ucr in self.usercommentreferral_set.all()]
		
	# these are used for generating text for sharing
	@property
	def nicename(self):
		return self.user.username + " " + self.verb() + " " + self.bill.nicename
	def hashtag(self):
		return self.bill.hashtag()

class UserCommentReferral(models.Model):
	# This class is used to avoid cascaded deletes on UserComment objects
	# if a referring object is deleted.
	comment = models.ForeignKey(UserComment, on_delete=models.CASCADE) # implicitly indexed by the unique_together
	referrer_content_type = models.ForeignKey(ContentType, db_index=True, on_delete=models.CASCADE)
	referrer_object_id = models.PositiveIntegerField(db_index=True)
	referrer = generic.GenericForeignKey('referrer_content_type', 'referrer_object_id')
	class Meta:
		unique_together = (("comment", "referrer_content_type", "referrer_object_id"),)

	def __unicode__(self):
		return "UserCommentReferral(%s,%s)" % (unicode(self.comment), unicode(self.referrer))
		
	@staticmethod
	def create(comment, referrer):
		for ucr in UserCommentReferral.objects.filter(comment=comment):
			if ucr.referrer == referrer:
				break
		else:
			ucr = UserCommentReferral()
			ucr.comment = comment
			ucr.referrer = referrer
			try:
				ucr.save()
			except:
				# race condition on uniqueness
				pass
			
	@staticmethod
	def for_referrer(referrer):
		from django.contrib.contenttypes.models import ContentType
		return UserCommentReferral.objects.filter(
			referrer_content_type=ContentType.objects.get_for_model(referrer),
			referrer_object_id=referrer.id)
		

class UserCommentOfflineDeliveryRecord(models.Model):
	comment = models.ForeignKey(UserComment, db_index=True, on_delete=models.CASCADE)
	target = models.ForeignKey(MemberOfCongress, on_delete=models.PROTECT) # implicitly indexed by the unique_together
	failure_reason = models.CharField(max_length=16)
	batch = models.CharField(max_length=20, blank=True, null=True)
	class Meta:
		unique_together = (("target", "comment"),)

class UserCommentDigg(models.Model):
	"""A digg by a user on a comment."""
	
	DIGG_TYPE_APPRECIATE = 0
	
	DIGG_TYPES = [ (DIGG_TYPE_APPRECIATE, 'Appreciate') ]

	comment = models.ForeignKey(UserComment, related_name="diggs", db_index=True, on_delete=models.CASCADE)
	diggtype = models.IntegerField(choices=DIGG_TYPES)
	user = models.ForeignKey(User, related_name="commentdiggs", db_index=True, on_delete=models.CASCADE)
	
	# the source_comment track's the user's position on the same bill: a user can only digg
	# a comment if he expressed the same position on the bill. by using a ForeignKey, we
	# ensure that if the user deletes his comment, his diggs on that bill also disappear.
	# we allow leg staff to appreciate all comments, so this can be null
	source_comment = models.ForeignKey(UserComment, related_name="my_diggs", db_index=True, blank=True, null=True, on_delete=models.CASCADE)

	created = models.DateTimeField(auto_now_add=True)

# BILL SIMILARITY #

class BillSimilarity(models.Model):
	"""Stores a similarity value between two bills, where bill1.id < bill2.id."""
	bill1 = models.ForeignKey(Bill, related_name="similar_bills_one", db_index=True, on_delete=models.CASCADE)
	bill2 = models.ForeignKey(Bill, related_name="similar_bills_two", db_index=True, on_delete=models.CASCADE)
	similarity = models.FloatField()
	class Meta:
		unique_together = (("bill1", "bill2"),)

# SERVICE ACCOUNTS #

class ServiceAccountPermission(models.Model):
	name = models.CharField(max_length=20, unique=True)
	notes = models.TextField(blank=True, null=True)
	def __unicode__(self):
		return self.name

class ServiceAccount(models.Model):
	"""A ServiceAccount contains billing information for an account holder. It may be associated
	with either a User for an individual account or an Org."""
	
	user = models.OneToOneField(User, blank=True, null=True, on_delete=models.PROTECT)
	org = models.OneToOneField(Org, blank=True, null=True, on_delete=models.PROTECT)
	name = models.CharField(max_length=100, blank=True, null=True)
	
	permissions = models.ManyToManyField(ServiceAccountPermission, blank=True)
	notes = models.TextField(blank=True)
	hosts = models.TextField(blank=True, help_text="Restrict the widget to appearing on sites at these domain names. Put domain names each on a separate line. You do not need to include the www. If this is blank, than by default we white-list the org's website's domain (for org accounts). However, if you put stuff here, you MUST include the org's website's domain if you want to include it.")
	fb_page_id = models.CharField(max_length=24, blank=True, null=True, db_index=True, help_text="The numeric ID of the Facebook Page that widgets may appear on for this account.") # ought to be unique but since it can be null it can't be set unique
	
	# this is a public key used in the URLs of widgets to identify this service account,
	# and it should be matched against a referrer URL to verify it is being used with
	# permission of the owner
	api_key = models.CharField(max_length=16, blank=True, unique=True, db_index=True)

	# this is a private key
	secret_key = models.CharField(max_length=16, blank=True, unique=True, db_index=True)

	# Track activity for billing.
	
	# this counter increments for each comment submitted by the Write Congress
	# widget tied to a service account with either the widget_theme or
	# writecongress_ocp permissions.
	beancounter_comments = models.IntegerField(default=0) # number of user messages to bill
	
	# other metadata
	created = models.DateTimeField(auto_now_add=True)

	options = PickledObjectField(default={})

	def __unicode__(self):
		if self.name: return self.name
		if self.user and self.org: return unicode(self.user) + "/" + unicode(self.org)
		if self.user: return unicode(self.user)
		if self.org: return unicode(self.org)
		return "Anonymous ServiceAccount"

	@property
	def shortname(self):
		if self.name: return self.name
		if self.user and self.org: return self.user.username + "/" + self.org.slug
		if self.user: return self.user.username
		if self.org: return self.org.slug
		return "anonymous"

	def save(self, *args, **kwargs):
		# initialize keys
		if not self.api_key:
			import random
			self.api_key = ''.join(random.choice(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z")) for x in range(16))
		if not self.secret_key:
			import random
			self.secret_key = ''.join(random.choice(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z")) for x in range(16))
		
		super(ServiceAccount, self).save(*args, **kwargs)

	@property
	def owner(self):
		if self.user: return self.user
		if self.org: return self.org
		return None

	def has_permission(self, name):
		return self.permissions.filter(name=name).exists()
		
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
	
	@staticmethod
	def get_or_create(**kwargs):
		acct, is_new = ServiceAccount.objects.get_or_create(**kwargs)
		if is_new:
			for perm in ("fb_page",): #"widget_theme", "salsa", "fb_page", "writecongress_ocp"):
				acct.permissions.add(ServiceAccountPermission.objects.get(name=perm))
		return acct
	
class ServiceAccountCampaign(models.Model):
	"""A position on a bill within a ServiceAccount."""
	POSITION_CHOICES = [ ('+', 'Support'), ('-', 'Oppose'), ('0', 'Neutral') ]
	account = models.ForeignKey(ServiceAccount, related_name="campaigns", on_delete=models.CASCADE) # implicitly indexed by the unique_together
	bill = models.ForeignKey(Bill, on_delete=models.PROTECT)
	position = models.CharField(max_length=1, choices=POSITION_CHOICES)
	created = models.DateTimeField(auto_now_add=True)
	mpbucket = models.CharField(max_length=16, blank=True, null=True)
	class Meta:
		ordering = ['account', '-created']
		unique_together = (("account", "bill", "position"),)
        permissions = (
				("can_snoop_service_analytics", "Can see anyone's widget analytics"),
			)
	def __unicode__(self):
		return unicode(self.account) + " -- " + unicode(self.bill) + " -- " + self.position
	def mixpanel_bucket(self):
		if self.mpbucket: return self.mpbucket
		return "sac_" + str(self.id)
	def mixpanel_bucket_secret(self):
		return hashlib.md5(settings.MIXPANEL_API_SECRET + self.mixpanel_bucket()).hexdigest()
	def mixpanel_stats(self):
		from mixpanel import Mixpanel
		import json
		api = Mixpanel(api_key=settings.MIXPANEL_API_KEY, api_secret=settings.MIXPANEL_API_SECRET)
		try:
			events = api.request(['events'], {
				'event' : ['widget_writecongress_hit', 'widget_writecongress_start', 'widget_writecongress_send', 'widget_writecongress_share'],
				'unit' : 'day',   # month+24 is useful just for getting totals
				'interval' : 365, # but when returning details need daily stats
				'type': 'unique', # 'general' would get total non-unique hits
				'bucket': self.mixpanel_bucket()
				})
		except:
			return { "ERROR": 1, "hit": 0, "share": 0, "events": [] }

		# trim the stats so they start on the first day of activity and end on last
		# day of activity.
		def trim_date(edge):
			if len(events["data"]["series"]) == 0: return False # no more to trim
			d = events["data"]["series"][edge]
			# check if any series has positive data for this date
			for v in events["data"]["values"].values():
				if v[d] > 0:
					return False # i.e. cannot trim
			# no series has positive data for this day, so remove the day and continue
			events["data"]["series"].pop(edge)
			for v in events["data"]["values"].values():
				del v[d]
			return True
		while trim_date(0): pass # trim from start
		while trim_date(-1): pass # trim from end

		try:
			hits = 0
			hits = sum(events["data"]["values"]["widget_writecongress_hit"].values())
		except:
			pass
		try:
			shares = 0
			shares = sum(events["data"]["values"]["widget_writecongress_share"].values())
		except:
			pass

		# replace series names
		series_names = { 'widget_writecongress_hit': 'Hits', 'widget_writecongress_start': 'Gave Name/Email', 'widget_writecongress_send': 'Finished Letter', 'widget_writecongress_share': 'Shared Link'}
		events["data"]["values"] = dict( (series_names.get(k,k),v) for k,v in events["data"]["values"].items() )

		return { "hit": hits, "share": shares, "events": json.dumps(events["data"]) }
	def first_action_date(self):
		try:
			return self.actionrecords.order_by('created')[0].created
		except:
			return None
	def last_action_date(self):
		try:
			return self.actionrecords.order_by('-created')[0].created
		except:
			return None
	def recent_comments(self):
		return self.actionrecords.filter(completed_comment__isnull=False).order_by('-created')[0:6]
	def total_widget_records(self):
		return self.actionrecords.filter(completed_stage__isnull=False).count()
	def add_action_record(self, **kwargs):
		email = kwargs.pop("email")
		rec, isnew = ServiceAccountCampaignActionRecord.objects.get_or_create(
			campaign=self,
			email=email,
			defaults = kwargs)
		if not isnew or "created" in kwargs:
			# Update the record with the new values.
			for k, v in kwargs.items():
				setattr(rec, k, v)
			rec.save()

class ServiceAccountCampaignActionRecord(models.Model):
	campaign = models.ForeignKey(ServiceAccountCampaign, related_name="actionrecords", on_delete=models.CASCADE) # implicitly indexed by the unique_together
	firstname = models.CharField(max_length=64, blank=True, db_index=True)
	lastname = models.CharField(max_length=64, blank=True, db_index=True)
	zipcode = models.CharField(max_length=16, blank=True, db_index=True)
	email = models.EmailField(db_index=True)
	created = models.DateTimeField(auto_now_add=True, db_index=True)
	updated = models.DateTimeField(auto_now=True)
	completed_comment = models.ForeignKey("UserComment", blank=True, null=True, db_index=True, related_name="actionrecord", on_delete=models.SET_NULL)
	completed_stage = models.CharField(max_length=16, blank=True, null=True)
	request_dump = models.TextField(blank=True, null=True)
	# various indexing above is for the data table sort on the analytics page
	class Meta:
		ordering = ['created']
		unique_together = [('campaign', 'email')]
def sacar_saved_callback(sender, instance, created, **kwargs):
	# Save data back to CRM.
	if "LOADING_FIXTURE" in os.environ: return
	try:
		campaign = instance.campaign
		acct = campaign.account
		
		if acct.getopt("salsa", None) != None:
			sacar_save_salsa(acct, campaign, instance)
			
		if acct.getopt("civicrm", None) != None:
			scar_save_civicrm(acct, campaign, instance)
		
	except Exception as e:
		import sys
		sys.stderr.write("sacar_saved_callback " + str(instance.id) + " " + str(instance) + ": " + unicode(e).encode("utf8") + " [" + unicode(getattr(e, "response_data", "")).encode("utf8") + "]\n")
django.db.models.signals.post_save.connect(sacar_saved_callback, sender=ServiceAccountCampaignActionRecord)

def sacar_save_salsa(acct, campaign, instance):
	url = "http://%s/o/%s/p/d/popvox/popvox/public/api/add_supporter.sjs" % (
		acct.getopt("salsa", None)["node"],
		acct.getopt("salsa", None)["org_id"])
	data = {
		"api_key": acct.secret_key,
		"action_id": "popvox_sac_" + str(campaign.id),
		"action_name": campaign.bill.title,
		"supporter_email": instance.email,
		"supporter_firstname": instance.firstname,
		"supporter_lastname": instance.lastname,
		"supporter_zip": instance.zipcode,
		"tracking_code": "popvox_sacar_" + str(instance.id),
		}
	if instance.completed_comment != None:
		data["supporter_zip"] = instance.completed_comment.address.zipcode
		data["supporter_state"] = instance.completed_comment.address.state
		data["supporter_district"] = instance.completed_comment.address.state + ("%02d" % instance.completed_comment.address.congressionaldistrict)
	ret = http_rest_json(url, data)
	
def scar_save_civicrm(acct, campaign, instance):
	# This requires CiviCRM 3.4 or 4.0.
	#
	# The API explorer is at /civicrm/ajax/docs/api/.
	# Docs: http://wiki.civicrm.org/confluence/display/CRMDOC40/CiviCRM+Public+APIs
	
	civi_info = acct.getopt("civicrm")
	
	import urllib, urllib2, json, re
	
	request_timeout = 10
	
	# Log in to get credentials cookie. Create a plain OpenerDirector
	# that does not include support for redirects so we can properly
	# detect if login worked.
	
	opener = urllib2.OpenerDirector()
	opener.add_handler(urllib2.HTTPHandler())
	opener.add_handler(urllib2.HTTPSHandler())
	ret = opener.open(civi_info["url_root"] + "/user/login?destination=admin/user/user", urllib.urlencode({"name": civi_info["username"], "pass": civi_info["password"], "form_id": "user_login", "op": "Log in", "form_build_id": "form-405bf5fb0fc8a0334c514952b1d87eea"}), request_timeout)
	if ret.getcode() != 302 or "/admin/user/user" not in ret.info()["Location"]:
		raise Exception("Login to CiviCRM site failed.")
	
	cookies = { }
	for cookie in ret.info().getallmatchingheaders("Set-Cookie"):
		m = re.match(r"Set-Cookie: ([^=]+)=([^;]+);.*", cookie)
		if m:
			cookies[m.group(1)] = m.group(2)
	
	def call_civi(raise_on_error=True, **params):
		req = urllib2.Request(civi_info["url_root"] + "/civicrm/ajax/rest?json=1&version=3&" + urllib.urlencode(params))
		for k, v in cookies.items():
			req.add_header("Cookie", k + "=" + v)
		data = opener.open(req, None, request_timeout).read()
		resp = json.loads(data)
		if resp.get("is_error", 0) != 0 and raise_on_error:
			raise Exception("CiviCRM API call returned an error: " + resp.get("error_message", ""))
		return resp
	
	def get_record(record_type, **query):
		#ret = call_civi(entity=record_type, action="getsingle", raise_on_error=False, **query)
		# There can always be duplicate records, so we should never really use getsingle which will
		# fail in that case. Instead, use get and select the first.
		ret = call_civi(entity=record_type, action="get", raise_on_error=False, **query)
		if ret.get("is_error", 0) != 0: return None
		if ret["count"] == 0: return None
		
		# For stability, choose the record with the lexicographically first key.
		key = sorted(ret["values"].keys())[0]
		
		return ret["values"][key]
	
	def get_constant(const_type, alteratives, raise_if_not_found=True):
		values = call_civi(entity="Constant", action="get", name=const_type)
		values = dict((v,k) for (k,v) in values["values"].items())
		for alt in alteratives:
			if alt in values:
				return values[alt]
		if raise_if_not_found:
			raise Exception("CiviCRM site does not have value for constant %s for value %s." % (const_type, repr(alternatives)))
		return None
		
	def create_or_update(record_type, existing_record_id, check_if_exists=False, **params):
		# Records can point to deleted records, and that causes problems
		# if we try to update a deleted record. For instance, an Email record
		# can have a contact_id that is deleted, which means it is in CiviCRM
		# but is not recognized by the API. When we do an update on it, we
		# get an error.
		if existing_record_id and check_if_exists:
			rec = get_record(record_type, id=existing_record_id)
			if not rec: # no such record
				existing_record_id = None # create a new one below
		
		if existing_record_id:
			params["id"] = existing_record_id
		ret = call_civi(
			entity=record_type,
			action="create" if not existing_record_id else "update",
			**params)
		return ret["values"][unicode(ret["id"])] 
	
	location_type = get_constant("locationType", ["Home", "Main", "Other"])
	
	email_record = get_record("Email", email=instance.email, location_type_id=location_type)
	
	# Create or update a Contact for this individual.
	contact_record = create_or_update(
		"Contact",
		email_record["contact_id"] if email_record else None,
		check_if_exists=True,
		
		contact_type = "Individual",
		first_name = instance.firstname if not instance.completed_comment else instance.completed_comment.address.firstname,
		last_name = instance.lastname if not instance.completed_comment else instance.completed_comment.address.lastname,
		prefix_id = get_constant("individualPrefix", [instance.completed_comment.address.nameprefix], raise_if_not_found=False) if instance.completed_comment else None,
		suffix_id = get_constant("individualSuffix", [instance.completed_comment.address.namesuffix], raise_if_not_found=False) if instance.completed_comment else None,
		source = "POPVOX")
	
	if not email_record or email_record.get("contact_id", None) != contact_record["id"]:
		# Create an Email record for the email address & contact if none exists.
		email_record = create_or_update(
			"Email",
			email_record["id"] if email_record else None,
			
			contact_id = contact_record["id"],
			email = instance.email,
			location_type_id = location_type,
			phone_type_id = get_constant("phoneType", ["Home", "Main", "Other"], raise_if_not_found=False),
			is_primary = 1)
		
	contact_id = email_record["contact_id"]
	
	if not instance.completed_comment:
		# Set the zip code for this individual if it is not set, but don't update
		# until we have ZIP+4 if a zip code is already set.
		address_record = get_record("Address", contact_id=contact_id, location_type_id=location_type)
		if not address_record:
			address_record = call_civi(
				entity="Address",
				action="create",
				contact_id = contact_id,
				location_type_id = location_type,
				postal_code = instance.zipcode[0:5],
				postal_code_suffix = instance.zipcode[6:10],
				country_id = 1228, # United States
				is_primary = 1,
				is_billing = 0,
				)
	else:
		# Update the home address for this individual.
		address_record = get_record("Address", contact_id=contact_id, location_type_id=location_type)
		address_record = create_or_update(
			"Address",
			address_record["id"] if address_record else None,
			contact_id = contact_id,
			location_type_id = location_type,
			postal_code = instance.completed_comment.address.zipcode[0:5],
			postal_code_suffix = instance.completed_comment.address.zipcode[6:10],
			country_id = 1228, # United States
			street_address = instance.completed_comment.address.address1,
			supplemental_address_1 = instance.completed_comment.address.address2,
			city = instance.completed_comment.address.city,
			state_province_id = get_constant("stateProvince", [govtrack.statenames[instance.completed_comment.address.state]]),
			timezone = instance.completed_comment.address.timezone,
			geo_code_1 = instance.completed_comment.address.latitude,
			geo_code_2 = instance.completed_comment.address.longitude,
			is_primary = 1,
			is_billing = 0,
			)
	
		# Update the home phone for this individual.
		phone_type_id = get_constant("phoneType", ["Phone", "Other"])
		phone_record = get_record("Phone", contact_id=contact_id, phone_type_id = phone_type_id)
		phone_record = create_or_update(
			"Phone",
			phone_record["id"] if phone_record else None,
			contact_id = contact_id,
			location_type_id = location_type,
			phone_type_id = phone_type_id,
			phone = instance.completed_comment.address.phonenumber,
			is_primary = 1,
			is_billing = 0)

	# Create or update the Campaign record. The Campaign external_identifier field only seems
	# to accept numbers, so we use the name field, which isn't displayed anywhere, to key
	# on our id for the campaign.
	ext_id = "popvox_sac_" + str(campaign.id)
	campaign_record = get_record("Campaign", name=ext_id)
	campaign_record = create_or_update(
		"Campaign",
		campaign_record["id"] if campaign_record else None,
		name=ext_id,
		title="POPVOX Widget for " + campaign.bill.nicename,
		)

	# Create or update an Activity record.
	activity_type_id = get_constant("ActivityType", ["Petition", "Webform Submission"])
	activity = get_record("Activity", source_contact_id=contact_id, campaign_id=campaign_record["id"])
	activity = create_or_update(
		"Activity",
		activity["id"] if activity else None,
		source_contact_id=contact_id,
		activity_type_id=activity_type_id,
		campaign_id=campaign_record["id"],
		activity_date_time=instance.updated.isoformat(),
		activity_subject="Took action on POPVOX widget on %s with result of '%s'." % (campaign.bill.shortname, instance.completed_stage),
		)

# USER SEGMENTATION AND BILL-TO-BILL RECOMMENDATIONS #

class BillRecommendation(models.Model):
	name = models.CharField(max_length=128)
	message = tinymce_models.HTMLField(blank=True)
	usersegment = models.TextField()
	recommendations = models.TextField()
	because = models.CharField(max_length=128)
	priority = models.PositiveIntegerField(default=0)
	created = models.DateTimeField()#auto_now_add=True, db_index=True)
	active = models.BooleanField(default=False)

	def __unicode__(self):
		return "BillRecommendation(" + str(self.created) + " " + self.name + ")"
		
class CensusData(models.Model):
    id = models.CharField(max_length=6, primary_key=True)
    population = models.PositiveIntegerField()
    male = models.DecimalField(max_digits=5,decimal_places=2)
    female = models.DecimalField(max_digits=5,decimal_places=2)
    age = models.DecimalField(verbose_name="Median age",max_digits=5,decimal_places=2)
    latino = models.DecimalField(max_digits=5,decimal_places=2)
    white = models.DecimalField(max_digits=5,decimal_places=2)
    black = models.DecimalField(max_digits=5,decimal_places=2)
    ai = models.DecimalField(verbose_name="American Indian",max_digits=5,decimal_places=2)
    asian = models.DecimalField(max_digits=5,decimal_places=2)
    hpi = models.DecimalField(verbose_name="Hawaiian / Pacific Islander",max_digits=5,decimal_places=2)
    other = models.DecimalField(verbose_name="Other races",max_digits=5,decimal_places=2)
    biracial = models.DecimalField(max_digits=5,decimal_places=2)
    hs = models.DecimalField(verbose_name="Highschool graduate",max_digits=5,decimal_places=2)
    bachelor = models.DecimalField(verbose_name="Bachelor's degree",max_digits=5,decimal_places=2)
    veteran = models.DecimalField(max_digits=5,decimal_places=2)
    income = models.PositiveIntegerField(verbose_name="Median household income")
    urban = models.DecimalField(max_digits=5,decimal_places=2)
    rural = models.DecimalField(max_digits=5,decimal_places=2)
    
class MemberBio(models.Model):
    id = models.IntegerField(primary_key=True)
    googleplus = models.URLField()
    flickr_id = models.CharField(max_length=100)
    		
if not "LOADING_FIXTURE" in os.environ and not os.path.exists("/home/www/slave"):
	# Make sure that we have MoC and CC records for all people
	# and committees that exist in Congress. Accessing these
	# models now prevents any further ManyToMany relationships
	# that reference these models from working and yields a
	# "Can't resolve keyword ... into field" error on querying
	# the M2M field.
	#MemberOfCongress.init_members()
	CongressionalCommittee.init_committees()
