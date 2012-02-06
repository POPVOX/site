#!runscript

from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.contrib.auth.decorators import login_required, user_passes_test

from django.contrib.auth.models import User
from django.db.models import Count

import pickle, base64, re

from jquery.ajax import json_response

from popvox.models import Bill, BillRecommendation, UserComment
from datetime import timedelta

class UserSegment(object):
	def describe(self):
		raise Exception("Not implemented.")
	
	def apply_filter(self, qs):
		# Takes a QuerySet over the Django User table and applies a filter
		# to apply the criteria expressed in this segment. Implement this,
		# unless search() and matches() are both overridden.
		raise Exception("Not implemented.")
		
	def search(self, scope=None):
		# Returns a set() of User ids matching the segment.
		# If scope is set, it is a set() of users that this segment is being
		# conjoined with, in case that is helpful for restricting the results
		# of this segment.
		qs = User.objects.all().exclude(legstaffrole__id__isnull=False).exclude(orgroles__id__isnull=False).values_list("id", flat=True).order_by()
		qs = self.apply_filter(qs)
		if scope and len(scope) < 512:
			qs = qs.filter(id__in=scope)
		return set(qs)
		
	def matches(self, user):
		# Returns a boolean indicating whether the particular user matches
		# the segment.
		return self.apply_filter(User.objects.filter(id=user.id)).exists()
	
	def conjunction_optimization_priority(self):
		# Help optimize conjunctions by determining where in a conjunction
		# to apply this segment. Higher numbers come earlier.
		return None

	def save(self):
		return base64.b64encode(pickle.dumps(self))
		
	@staticmethod
	def load(encoded_segment):
		return pickle.loads(base64.b64decode(encoded_segment))

class SegmentAllUsers(UserSegment):
	def describe(self):
		return "{everyone}"
	def apply_filter(self, qs):
		return qs

class EmptySegment(UserSegment):
	def describe(self):
		return "{no one}"
	def search(self, scope=None):
		return set()
	def matches(self, user):
		return False

class SegmentCommentedOnIssue(UserSegment):
	issue_area_id = None
	def __init__(self, issue_area_id):
		self.issue_area_id = issue_area_id
	def describe(self):
		from popvox.models import IssueArea
		return "weighed in on %s" % IssueArea.objects.get(id=self.issue_area_id).name
	def apply_filter(self, qs):
		return qs.filter(comments__bill__issues__id=self.issue_area_id)
	def conjunction_optimization_priority(self):
		return 2
		
class SegmentCommentedOnBill(UserSegment):
	bill_id = None
	def __init__(self, bill_id):
		self.bill_id = bill_id
	def describe(self):
		from popvox.models import Bill
		return "weighed in on %s" % Bill.objects.get(id=self.bill_id).nicename
	def apply_filter(self, qs):
		return qs.filter(comments__bill__id=self.bill_id, comments__method=UserComment.METHOD_SITE)
	def conjunction_optimization_priority(self):
		return 3
		
class SegmentCommentedAtLeastNTimes(UserSegment):
	n = None
	def __init__(self, n):
		self.n = n
	def describe(self):
		return "weighed in at least %d times" % self.n
	def apply_filter(self, qs):
		from django.db.models import Count
		return qs.annotate(count=Count('comments')).filter(count__gte=self.n)
	def conjunction_optimization_priority(self):
		return 1

class SegmentCommentedAtMostNTimes(UserSegment):
	n = None
	def __init__(self, n):
		self.n = n
	def describe(self):
		return "weighed in up to %d times" % self.n
	def apply_filter(self, qs):
		from django.db.models import Count
		return qs.annotate(count=Count('comments')).filter(count__lte=self.n)
	def conjunction_optimization_priority(self):
		return 1

class InverseSegment(UserSegment):
	segment = None
	def __init__(self, segment):
		self.segment = segment
	def describe(self):
		return "not (%s)" % self.segment.describe()
	def search(self, scope=None):
		if scope == None:
			scope = SegmentAllUsers.search()
		return scope - self.segment.search()
	def matches(self, user):
		return not self.segment.matches(user)

class ConjunctiveSegment(UserSegment):
	conjuncts = None
	def __init__(self, conjuncts):
		self.conjuncts = conjuncts
	def describe(self):
		return " and ".join([("(%s)" % s.describe()) for s in self.conjuncts])
	def search(self, scope=None):
		# Normally one can just chain filters to make them conjunctive, but because
		# we select on the same tables for different purposes, they would conflict.
		# It's the filter versus annotate problem.
		self.conjuncts = sorted(self.conjuncts, key = lambda s : s.conjunction_optimization_priority(), reverse=True)
		ret = None
		for segment in self.conjuncts:
			if ret == None:
				ret = segment.search()
			else:
				ret &= segment.search(scope=ret)
		return ret
	def matches(self, user):
		for conjunct in self.conjuncts:
			if not conjunct.matches(user):
				return False
		return True
	def conjunction_optimization_priority(self):
		return max([s.conjunction_optimization_priority() for s in self.conjuncts])
		
class DisjunctiveSegment(UserSegment):
	disjuncts = None
	def __init__(self, disjuncts):
		self.disjuncts = disjuncts
	def describe(self):
		return " or ".join([("(%s)" % s.describe()) for s in self.disjuncts])
	def search(self, scope=None):
		ret = set()
		for segment in self.disjuncts:
			ret |= segment.search(scope)
		return ret
	def matches(self, user):
		for disjunct in self.disjuncts:
			if disjunct.matches(user):
				return True
		return False

@user_passes_test(lambda u : u.is_authenticated() and (u.is_staff | u.is_superuser))
def segmentation_builder(request):
	return render_to_response("popvox/segmentation_builder.html")

@json_response
@user_passes_test(lambda u : u.is_authenticated() and (u.is_staff | u.is_superuser))
def segmentation_parse(request):
	s = request.REQUEST.get("segment", "")
	if s.strip() == "":
		s = SegmentAllUsers()
	else:
		s = parse_segment_description(s)
	if isinstance(s, UserSegment):
		return {
			"description": s.describe(),
			"count": len(s.search()),
			"segment": s.save(),
		}
	else:
		return {
			"error": s[1],
			"location": s[0],
		}


def parse_segment_description(descr, top_level=True):
	# Parses descr into a UserSegment object, returning either
	#   the UserSegment object it parsed, or
	#   a tuple of the character position where an error ocurred and a string describing the parse error
	
	# Look for the start of the expression.
	
	if not top_level:
		m1 = re.search(r"^\s*(NOT\s*)?\(", descr)
		if not m1:
			return (0, "A segment must begin with an open parenthesis, optionally preceded by NOT. \"%s\" doesn't look right." % descr)
		
		m2 = re.search("\)\s*$", descr)
		if not m2:
			return (len(descr), "A segment must end with a close parenthesis. \"%s\" doesn't look right." % descr)
			
		inside = descr[m1.end():m2.start()]
	else:
		inside = descr
		
	if "(" in inside or top_level:
		# This thing has subexpressions, so parse as a conjunction or disjunction.
		# Break up the subexpression by the balanced parenthesis and spaces.
		parts = [""]
		parens = 0
		for c in inside:
			if c == "(":
				if parens == 0:
					parts.append(c)
				else:
					parts[-1] += (c)
				parens += 1
			elif c == ")":
				parts[-1] += (c)
				parens -= 1
				if parens == 0:
					parts.append("")
			elif c == " " and parens == 0:
				if parts[-1] != "":
					parts.append("")
			else:
				parts[-1] += c
				
		# Collapse any occurrence of NOT onto the next item.
		newparts = []
		for part in parts:
			if len(newparts) > 0 and newparts[-1].strip() == "NOT":
				newparts[-1] += part
			elif part.strip() != "":
				newparts.append(part)
		parts = newparts
				
		operator = None
		operands = []
		charpos = 0
		for i, op in enumerate(parts):
			if i % 2 == 1:
				if not op.strip() in ("AND", "OR"):
					return charpos, "Separate segments with AND or OR, not \"%s\"." % op
				if operator == None:
					operator = op.strip()
				elif operator != op.strip():
					return charpos, "These segments must all be separated by AND or all by OR, not mixed. Add additional parentheses to use both AND and OR."
			else:
				op_ret = parse_segment_description(op, top_level=False)
				if type(op_ret) == tuple:
					# return the error by add the character offset into our current character position
					return (charpos + op_ret[0], op_ret[1])
				else:
					operands.append(op_ret)
			charpos += len(op)
		
		if len(operands) == 1:
			return operands[0]
		
		if operator == "AND":
			c = ConjunctiveSegment(operands)
		elif operator == "OR":
			c = DisjunctiveSegment(operands)
		else:
			raise Exception()
			
		if not top_level and m1.group(1):
			c = InverseSegment(c)
			
		return c
		
	else:
		from popvox.models import IssueArea, Bill
		patterns = {
			r"weighed in on issue (\w+)": lambda m : SegmentCommentedOnIssue(IssueArea.objects.get(slug=m.group(1)).id),
			r"weighed in on bill ([\w/]+)": lambda m : SegmentCommentedOnBill(Bill.from_hashtag("#"+m.group(1)).id),
			r"weighed in on proposal (\d+)": lambda m : SegmentCommentedOnBill(Bill.objects.get(id=int(m.group(1))).id),
			r"weighed in at least (\d+) times": lambda m : SegmentCommentedAtLeastNTimes(int(m.group(1))),
			r"weighed in at most (\d+) times": lambda m : SegmentCommentedAtMostNTimes(int(m.group(1))),
		}
		
		from django.core.exceptions import ObjectDoesNotExist
		
		for pattern, constructor in patterns.items():
			m = re.match("^" + pattern + "$", inside)
			if m:
				try:
					c =  constructor(m)
					if m1.group(1):
						c = InverseSegment(c)
					return c
				except ValueError:
					return (m1.end(), "I didn't understand what you meant by %s." % ", ".join(m.groups()))
				except ObjectDoesNotExist:
					return (m1.end(), "I didn't understand what you meant by %s." % ", ".join(m.groups()))
		
		return (m1.end(), "I didn't understand what you meant by \"%s\"." % inside)

@json_response
@user_passes_test(lambda u : u.is_authenticated() and (u.is_staff | u.is_superuser))
def segmentation_table(request):
	seg = request.POST.get("segment", "")
	if seg == "":
		segment = SegmentAllUsers()
	else:
		segment = UserSegment.load(seg)

	start = int(request.POST.get("iDisplayStart"))
	length = int(request.POST.get("iDisplayLength"))
	
	segment = segment.search()
	total_count = len(segment)
	
	segment = sorted(segment)[start:start+length]
	
	
	def get_user_row(uid):
		user = User.objects.get(id=uid)
		return (user.username, user.email)
	
	return {
		"iTotalRecords": total_count,
		"iTotalDisplayRecords": total_count,
		
		"aaData": [get_user_row(user) for user in segment]
	}

@json_response
@user_passes_test(lambda u : u.is_authenticated() and (u.is_staff | u.is_superuser))
def segmentation_create_conversion(request):
	br = BillRecommendation()
	br.name = request.POST["name"]
	
	bills = []
	for b in request.POST["bills"].replace(" ", "").split(","):
		try:
			b = Bill.from_hashtag("#" + b)
		except:
			return { "error": "invalid bill: " + b }
		bills.append(b)
	br.recommendations = ",".join([str(b.id) for b in bills])
	
	br.because = request.POST["because"]
	
	br.usersegment = parse_segment_description(request.POST["segment"])
	if isinstance(br.usersegment, tuple):
		return { "error": "Something is wrong with your segment. Try the Update button." }
	else:
		br.usersegment = br.usersegment.save()
	
	from datetime import datetime # REMOVE
	br.created = datetime.now() # REMOVE
	
	try:
		br.save()
	except Exception as e:
		return { "error": unicode(e) }
	
	return { "redirect_url": "/admin/popvox/billrecommendation/%d" % br.id }

#print parse_segment_description("(weighed in at least 6 times)")

def compute_rachna_conversion_rate():
	all_total = 0
	all_converted = 0
	for br in BillRecommendation.objects.all():
		s = UserSegment.load(br.usersegment)
		
		# how many people who joined before the B2B date that matched
		# the user segment (though the match may involve things they did
		# later) took action on any of the recs.
		
		print br.id, br.name
		print br.created
		
		recs = [int(b) for b in br.recommendations.split(",")]
		print [Bill.objects.get(id=r).title for r in recs]
		
		base = User.objects.filter(id__in=s.search(), date_joined__lt=br.created, userprofile__allow_mass_mails=True)
		
		if br.id == 17:
			print "using email list file"
			base = User.objects.filter(email__in=open("/home/josh/b2b_hr822_emails.txt").read().split("\n"))
			base = User.objects.filter(id__in=set(u.id for u in base))
		else:
			continue
		
		total = len(base)
		converted = base.filter(comments__bill__in=recs, comments__created__gt=br.created.date(), comments__created__lt=br.created+timedelta(days=4), comments__method=UserComment.METHOD_SITE).only("id").distinct().count()
		
		actions = UserComment.objects.filter(user__in=base, bill__in=recs, created__gt=br.created.date(), created__lt=br.created+timedelta(days=4), method=UserComment.METHOD_SITE).count()
		
		print converted, "(" + str(int(round(100.0*converted/total))) + "%) of", total, "users took action;", actions, "positions in all"
		print
		
		all_total += total
		all_converted += converted
		
	print 100*all_converted/all_total, "%"
	

