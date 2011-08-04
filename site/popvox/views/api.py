from django.core.paginator import Paginator

from piston.resource import Resource
from piston.handler import BaseHandler

from popvox.models import *

import re
from itertools import chain

from settings import SITE_ROOT_URL

def paginate_items(items, request):
	p = Paginator(items, int(request.GET.get("count", "25")))
	pp = p.page(int(request.GET.get("page", "1")))
	return {
		"count": p.count,
		"pages": p.num_pages,
		"page": pp.number,
		"has_next": pp.has_next(),
		"has_prev": pp.has_previous(),
		"items": pp.object_list
	}
	
def paginate(func):
	def g(self, request, *args, **kwargs):
		ret = func(self, request, *args, **kwargs)
		return paginate_items(ret, request)
	return g

class BillHandler(BaseHandler):
	allowed_methods = ('GET',)
	model = Bill
	exclude = []
	fields = ('id', 'congressnumber', 'billtype', 'billnumber', 'title', 'street_name', 'current_status', 'current_status_date', 'sponsor', 'topterm',  'num_cosponsors', 'notes', 'link')

	@classmethod
	def billtype(api, bill):
		return bill.billtype2()

	@classmethod
	def sponsor(api, bill):
		return { "id": bill.sponsor.id, "name": bill.sponsor.name() }
		
	@classmethod
	def topterm(api, bill):
		return bill.topterm.name if bill.topterm else None
		
	@classmethod
	def link(api, bill):
		return SITE_ROOT_URL + bill.url()
		
@Resource
class bill_suggestions(BillHandler):
	def read(self, request):
		from bills import get_popular_bills
		ret = {}
		
		ret["popular"] = get_popular_bills()
		if request.GET.get("can_comment", '') == "1":
			ret["popular"] = [b for b in ret["popular"] if b.isAlive()]
		
		if "similar_to" in request.GET:
			# Get related bills by similarity to a set of bills passed in by ID.
			
			targets = {}
			for source_bill in Bill.objects.filter(id__in=request.GET["similar_to"].split(",")):
				for target_bill, similarity in chain(( (s.bill2, s.similarity) for s in source_bill.similar_bills_one.all().select_related("bill2")), ( (s.bill1, s.similarity) for s in source_bill.similar_bills_two.all().select_related("bill1"))):
					if request.GET.get("can_comment", '') == "1" and not target_bill.isAlive():
						continue
					
					if not target_bill in targets: targets[target_bill] = []
					targets[target_bill].append( (source_bill, similarity) )
			
			targets = list(targets.items()) # (target_bill, [list of (source,similarity) pairs])
			targets.sort(key = lambda x : -sum([y[1] for y in x[1]]))
			
			# Take the top reccomendations.
			ret["similarity"] = [t[0] for t in targets[:15]]
		
		return ret

@Resource
class bill_search(BillHandler):
	@paginate
	def read(self, request):
		from bills import billsearch_internal
		bills, status = billsearch_internal(request.GET.get("q", "").strip())
		return bills
	
@Resource
class comments(BaseHandler):
	allowed_methods = ('GET',)
	model = UserComment
	exclude = []
	fields = ('id', 'bill', 'position', 'position_text', 'screenname', 'message', 'created', 'state', 'congressionaldistrict', 'referral', 'link')
	
	@paginate
	def read(self, request):
		items = UserComment.objects.all().select_related("user", "bill", "bill_sponsor")
		if "bill" in request.GET: items = items.filter(bill=int(request.GET["bill"]))
		if request.GET.get("has_message", "0") == "1": items = items.filter(message__isnull=False)
		if "state" in request.GET: items = items.filter(state=request.GET["state"])
		if "district" in request.GET: items = items.filter(congressionaldistrict=request.GET["district"])
		return items

	@classmethod
	def screenname(api, item):
		return item.user.username
		
	@classmethod
	def link(api, item):
		if item.message:
			return SITE_ROOT_URL + item.url()
		else:
			return None
			
	@classmethod
	def position_text(api, item):
		return item.verb()
	
	@classmethod
	def referral(api, item):
		return [str(r) for r in item.referrers()]
			
