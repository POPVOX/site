from django.core.paginator import Paginator
from django.http import HttpResponse, Http404
from django.contrib.auth.models import User, AnonymousUser
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.core.urlresolvers import reverse

from piston.resource import Resource
from piston.handler import BaseHandler

from popvox.models import *

import re, base64, json, urlparse
from itertools import chain

from sphinxapi import SphinxClient, SPH_MATCH_EXTENDED

from settings import SITE_ROOT_URL

api_endpoints = []

class ServiceKeyAuthentication(object):
	def is_authenticated(self, request):
		if not "api_key" in request.GET:
			try:
				host = urlparse.urlparse(request.META.get("HTTP_REFERER", "")).hostname.lower()
				if host.startswith("www."):
					host = host[4:]
				if host in ('popvox.com', 'josh.popvox.com'):
					return True
			except:
				pass
		
		auth_string = request.GET.get('api_key', "").strip()

		if len(auth_string) == 0:
			return False

		try:
			acct = ServiceAccount.objects.get(secret_key=auth_string)
		except:
			return False
		
		request.user = acct.user or AnonymousUser()

		return True

	def challenge(self):
		resp = HttpResponse("Authorization Required. Missing or invalid api_key. Include your service account private API key in the api_key parameter.")
		resp.status_code = 401
		return resp

def make_endpoint(f):
	global api_endpoints
	api_endpoints.append(f)
	return Resource(f, ServiceKeyAuthentication())

def make_simple_endpoint(f):
	global api_endpoints
	api_endpoints.append(f)
	return f

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
		
@make_endpoint
class bill_suggestions(BillHandler):
	description = "Retreives suggested bills, including popular bills and bills similar to other bills."
	qs_args = (
		('can_comment', 'Optional. Set to "1" to restrict the output to bills that can be commented on.'),
		("similar_to", "Optional. A comma-separated list of bill IDs. Adds a 'similarity' key to the output with related bills."))
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

@make_endpoint
class bill_search(BillHandler):
	description = "Search bills by bill number or keywords in bill title. Returns a paginated list of bills."
	url_example_qs = "?q=H.R.3"
	qs_args = (('q', 'The search query.'),)
	
	@paginate
	def read(self, request):
		from bills import billsearch_internal
		bills, status = billsearch_internal(request.GET.get("q", "").strip())
		return bills

class DocumentHandler(BaseHandler):
	@classmethod
	def pages(api, item):
		return item.pages.count()

	@classmethod
	def formats(api, item):
		has_text = item.pages.filter(text__isnull=False).exists()
		has_html = item.pages.filter(html__isnull=False).exists()
		has_png = item.pages.filter(png__isnull=False).exists()
		return { "text": has_text, "html": has_html, "png": has_png }


@make_endpoint
class bill_documents(DocumentHandler):
	model = PositionDocument
	fields = ['id', 'title', 'created', 'doctype', 'pages', 'formats']
	url_pattern_args = [("000", "BILL_ID")]
	url_example_args = (16412,)
	description = "Returns documents associated with a bill, including bill text."
	
	def read(self, request, billid):
		bill = Bill.objects.get(id=billid)
		return bill.documents.all()

@make_endpoint
class document_info(DocumentHandler):
	model = PositionDocument
	fields = ['id', 'bill', 'title', 'created', 'doctype', 'pages', 'formats', 'toc']
	url_pattern_args = [("000", "DOCUMENT_ID")]
	url_example_args = (248,)
	description = "Returns metadata about a document (such as bill text)."
	
	def read(self, request, docid):
		try:
			return PositionDocument.objects.get(id=docid)
		except PositionDocument.DoesNotExist:
			raise Http404("Invalid document ID.")
		
	@classmethod
	def toc(api, item):
		return json.loads(item.toc) if item.toc else None

@make_simple_endpoint
def document_page(request, docid, pagenum, format):
	try:
		doc = PositionDocument.objects.get(id=docid)
		page = doc.pages.get(page=pagenum)
		if format == "png":
			return HttpResponse(base64.decodestring(page.png), "image/png")
		elif format == "html":
			return HttpResponse(page.html, "text/html")
		elif format == "txt":
			return HttpResponse(page.text, "text/plain")
		else:
			raise Http404("Invalid page format.")
	except PositionDocument.DoesNotExist:
		raise Http404("Invalid document ID.")
	except DocumentPage.DoesNotExist:
		raise Http404("Page number out of range.")
document_page.description = "Retreives one page of a document as either a PNG or in plain text. Result is either image/png or text/plain."
document_page.url_pattern_args = (("000",'DOCUMENT_ID'), ("001",'PAGE_NUMBER'), ('aaa', '{png|html|txt}'))
document_page.url_example_args = (248,20,'png')

@make_endpoint
class document_pages(BaseHandler):
	fields = ['page', 'text']
	description = "Retreives all pages of a document."
	url_pattern_args = (("000",'DOCUMENT_ID'),)
	url_example_args = (248,)
	@paginate
	def read(self, request, docid):
		try:
			doc = PositionDocument.objects.get(id=docid)
			return doc.pages.order_by('page')
		except PositionDocument.DoesNotExist:
			raise Http404("Invalid document ID.")

@make_endpoint
class document_search(BaseHandler):
	#model = DocumentPage
	fields = ['page']
	description = "Searches a document for text returning a list of page numbers."
	url_pattern_args = (("000",'DOCUMENT_ID'),)
	url_example_args = (248,)
	url_example_qs = "?q=budget%20authority"
	qs_args = (('q', 'The search query.'),)
	
	def read(self, request, docid):
		q = request.GET.get("q", "").strip()
		if q == "":
			return []
		
		c = SphinxClient()
		c.SetServer("localhost" if not "REMOTEDB" in os.environ else os.environ["REMOTEDB"], 3312)
		c.SetMatchMode(SPH_MATCH_EXTENDED)
		c.SetFilter("document_id", [int(docid)])
		ret = c.Query(q)
		if ret == None:
			return []
		
		return sorted([m["attrs"]["page"] for m in ret["matches"]])
	
@make_endpoint
class comments(BaseHandler):
	allowed_methods = ('GET',)
	model = UserComment
	exclude = []
	fields = ('id', 'bill', 'position', 'position_text', 'screenname', 'message', 'created', 'state', 'congressionaldistrict', 'referral', 'link')
	description = "Retrieves constituent comments on bills. Returns a paginated list of comments."
	qs_args = (
		('bill', 'Optional. Restrict comments to a single bill, given by bill ID.'),
		('has_message', 'Optional. Set to "1" to only return comments with messages.'),
		('state', 'Optional. Restrict comments to users from a state. Set to a USPS state abbreviation.'),
		('district', 'Optional. Restrict comments to users from a congressional district. Set this parameter to an integer, the Congressional district, and also set the state parameter.'),)
	url_example_qs = "?state=NY&district=2&has_message=1"		
	
	@paginate
	def read(self, request):
		items = UserComment.objects.all().select_related("user", "bill", "bill_sponsor")
		if "bill" in request.GET: items = items.filter(bill=int(request.GET["bill"]))
		if request.GET.get("has_message", "0") == "1": items = items.filter(message__isnull=False)
		if "state" in request.GET:
			items = items.filter(state=request.GET["state"])
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

def documentation(request):
	def reformat_args_1(args):
		# Because the Django URL reverse mechanism only lets us put in numbers in \d+ spots,
		# and we want to give a more helpful pattern, for args specified as a tuple (NUM, STR),
		# call the resolver with NUM and then replace it with STR later.
		return [a if type(a) != tuple else a[0] for a in args]
	def reformat_args_2(url, args):
		for a in args:
			if type(a) == tuple:
				url = url.replace(a[0], a[1])
		return url
	
	def update(f):
		f.name = f.__name__

		try:
			args = getattr(f, "url_pattern_args", [])
			f.url_pattern = SITE_ROOT_URL + reformat_args_2(reverse('popvox.views.api.' + f.__name__, args=reformat_args_1(args)), args) 
		except Exception as e:
			f.url_pattern =  str(e)

		try:
			f.url_example = SITE_ROOT_URL + reverse('popvox.views.api.' + f.__name__, args=getattr(f, "url_example_args", [])) + getattr(f, "url_example_qs", "")
		except Exception as e:
			f.url_example = str(e)
			
		return f
			
	return render_to_response('popvox/apidoc.html', {
		'accounts': request.user.userprofile.service_accounts(create=True) if request.user.is_authenticated() else [],
		'methods': [update(f) for f in api_endpoints],
		}, context_instance=RequestContext(request))

