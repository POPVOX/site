from django.core.paginator import Paginator
from django.http import HttpResponse, Http404, HttpResponseForbidden, HttpResponseBadRequest, HttpResponseRedirect
from django.contrib.auth import get_user
from django.contrib.auth.models import User, AnonymousUser
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django.utils.importlib import import_module
from django.views.decorators.cache import cache_page
from django.db.models import Q

from popvox.models import *
from popvox import govtrack
from popvox.govtrack import CURRENT_CONGRESS
from popvox.views.services import validate_widget_request

import re, base64, json, urlparse, urllib
from itertools import chain
from types import NoneType
from collections import OrderedDict

from sphinxapi import SphinxClient, SPH_MATCH_EXTENDED

import dataemitters

from django.conf import settings
from settings import SITE_ROOT_URL, DEBUG

api_endpoints = []

# The @api_handler decorator takes a class definition and replaces it
# by an instance of it, so that it is callable by the URL dispatch.
def api_handler(f):
    instance = f()
    instance.__name__ = f.__name__
    return instance

class BaseHandler(object):
    allow_empty_api_key = False
    allow_public_api_key = False
    
    def __init__(self):
        global api_endpoints
        api_endpoints.append(self)
        
    def has_read(self):
        return hasattr(self, "read")
    def has_post(self):
        return hasattr(self, "post")
    
    def __call__(self, request, *args, **kwargs):
        # Check the api_key query string parameter.
        auth_string = request.REQUEST.get('api_key', "").strip()
        if len(auth_string) == 0:
            # If the user is logged in and no api_key is specified and the API endpoint
            # allows for automatic creation of a ServiceAccount for the user, then
            # create a ServiceAccount if necessary for the user and use that.
            if self.allow_empty_api_key and request.user.is_authenticated():
                acct = request.user.userprofile.service_accounts(create=True)[0]
            else:
                return HttpResponseForbidden("Authorization Required. Missing api_key parameter.")
        else:
            try:
                acct = ServiceAccount.objects.filter(secret_key=auth_string)
                
                # only allow public api keys to be used on methods that don't return private information
                if self.allow_public_api_key:
                    acct |= ServiceAccount.objects.filter(api_key=auth_string)
                    
                acct = acct.get()
            except:
                return HttpResponseForbidden("Authorization Required. Invalid api_key parameter.")
        
        # If there was a session parameter, then the SessionFromFormMiddleware already
        # took care of it. Otherwise, clear the session state since we should not use
        # a cookie-based session.
        if "session" not in request.REQUEST or self.allow_public_api_key:
            # We have to set a valid session object or things that hit the session state like
            # user login will fail.
            session_engine = import_module(settings.SESSION_ENGINE)
            request.session = session_engine.SessionStore()
            
            # But if the account is associated with a user, then authorize access to that user,
            # unless the API method allows public keys in which case we should not need this.
            if acct.user and not self.allow_public_api_key:
                request.user = acct.user
                
            
        # Get the handler function for this HTTP method.
        f = None
        if request.method == "GET":
            f = getattr(self, "read", None)
        elif request.method == "POST":
            f = getattr(self, "post", None)
        if f == None:
            return HttpResponseBadRequest("Invalid operation: " + request.method)
            
        # Get the emitter for output.
        format = request.REQUEST.get("format", "json")
        try:
            emitter, mime_type = dataemitters.Emitter.get(format)
        except Exception as e:
            return HttpResponseBadRequest("Invalid format: " + format + ". " + str(e))

        # Call the handler function, adding the account argument.
        if not DEBUG:
            # let exceptions be caught higher up
            ret = f(request, acct, *args, **kwargs)
        else:
            try:
                ret = f(request, acct, *args, **kwargs)
            except:
                import traceback
                response = HttpResponse(traceback.format_exc())
                response.status_code = 500
                return response
            
        if isinstance(ret, HttpResponse):
            return ret
        
        cached_type_info = { }
        
        # Serialize the response.
        def typemapper(obj_class, request, acct):
            if obj_class in cached_type_info:
                return cached_type_info[obj_class]
            
            # Get the field mapping for the model class, which is a list of fields to serialize for the model.
            fieldlist = getattr(self, obj_class.__name__.lower() + "_fields", None)
            
            # Hide the "hidden" fields if no fields are requested specifically.
            if not callable(fieldlist) and not "fields" in request.REQUEST:
                hidden_fields = getattr(self, obj_class.__name__.lower() + "_hidden_fields", [])
                fieldlist = [f for f in fieldlist if not f in hidden_fields]
            
            if not fieldlist:
                cached_type_info[obj_class] = None
                return None
            if callable(fieldlist):
                fieldlist = fieldlist(request, acct)
                
            if "fields" in request.REQUEST:
                # Only return the specified fields. Check that the specified fields are valid field names.
                specified_fields = request.REQUEST["fields"].split(",")
                _fieldlist = []
                for field in specified_fields:
                    if field in fieldlist:
                        _fieldlist.append(field)
                fieldlist = _fieldlist
            
            # For each field, get the function that returns that value.
            def getvaluefunc(attrname):
                if hasattr(self, obj_class.__name__.lower() + "_" + attrname):
                    return getattr(self, obj_class.__name__.lower() + "_" + attrname)
                if hasattr(self, attrname):
                    return getattr(self, attrname)
                def simplevaluefunc(obj, request, acct):
                    return getattr(obj, attrname)
                return simplevaluefunc
            
            ret = [(f, getvaluefunc(f)) for f in fieldlist]
            cached_type_info[obj_class] = ret
            return ret
        
        ret = emitter(ret, typemapper, [request, acct]).render(request)
        return HttpResponse(ret, mimetype=mime_type)

def make_simple_endpoint(f):
    global api_endpoints
    api_endpoints.append(f)
    f.allow_public_api_key = True
    return f

def paginate_items(items, request):
    p = Paginator(items, int(request.REQUEST.get("count", "25")))
    pp = p.page(int(request.REQUEST.get("page", "1")))
    return OrderedDict([
        ("count", p.count),
        ("pages", p.num_pages),
        ("page", pp.number),
        ("has_next", pp.has_next()),
        ("has_prev", pp.has_previous()),
        ("items", pp.object_list)
    ])
    
def paginate(func):
    def g(self, request, *args, **kwargs):
        ret = func(self, request, *args, **kwargs)
        return paginate_items(ret, request)
    return g

class BillHandler(BaseHandler):
    bill_fields = ('id', 'congressnumber', 'billtype', 'billnumber', 'title', 'street_name', 'status', 'status_advanced', 'status_advanced_abbreviated', 'current_status_date', 'sponsor', 'topterm',  'num_cosponsors', 'notes', 'link', 'shorturl')
    bill_hidden_fields = ('shorturl',)
    issuearea_fields = ('id', 'name')
    memberofcongress_fields = ('id', 'name')

    @staticmethod
    def billtype(bill, request, acct):
        return bill.billtypeslug()

    @staticmethod
    def link(bill, request, acct):
        return SITE_ROOT_URL + bill.url()
        
    @staticmethod
    def shorturl(bill, request, acct):
        owner = acct.owner
        if request.user.is_authenticated():
            owner = request.user
        
        import shorturl
        surl, created = shorturl.models.Record.objects.get_or_create(owner=owner, target=bill)
        
        return surl.url()
        
@api_handler
class bill_suggestions(BillHandler):
    description = "Retreives suggested bills, including trending bills."
    qs_args = (
        ('can_comment', 'Optional. Set to "1" to restrict the output to bills that can be commented on.', None), )
    response_summary = "Returns groups of recommendations, i.e. a list of lists. Each group has a title, an identification code, and a list of bills. The list of bills may be ordered from most relevant to least relevant. For documentation of the returned bill metadata, see the bill metadata API method."
    response_fields = (
        ('name', 'the display name for the list'),
        ('type', 'a string code identifying the type of the list (currently just "trending")'),
        ('bills', 'a list of bills in the list'),
        )
    def read(self, request, account):
        from bills import get_popular_bills
        
        pop_bills = get_popular_bills()
        if request.GET.get("can_comment", '') == "1":
            pop_bills = [b for b in ret["popular"] if b.isAlive()]
        
        ret = [
            OrderedDict([
                ("name", "Trending Bills on POPVOX"),
                ("type", "trending"),
                ("bills", pop_bills),
            ]),
        ]
        
        if request.user.is_authenticated() and request.user.userprofile.is_leg_staff():
            from home import get_legstaff_suggested_bills
            for category in get_legstaff_suggested_bills(request.user, include_extras=False):
                if not category["count"]: continue
                bills = category["bills"]
                if category["id"] != "local":
                    bills = bills.order_by('-current_status_date')[0:10]
                ret.append(OrderedDict([
                    ("name", category["name"] if category["type"] != "committeereferral" else category["shortname"]),
                    ("type", category["id"]),
                    ("bills", bills),
                ]))
                
            list_order = ("sponsor", "local", "trending")
            ret.sort(key = lambda x : list_order.index(x["type"]) if x["type"] in list_order else len(list_order))
        
        return ret

@api_handler
class bill_similarity(BillHandler):
    description = "Retreives bills similar to other bills."
    qs_args = (
        ("similar_to", "A comma-separated list of bill IDs to get similar bills for.", "14402"),
        ('can_comment', 'Optional. Set to "1" to restrict the output to bills that can be commented on.', None))
    response_summary = "Returns a paginated list of similar bills, ordered from most similar to least similar. For documentation of the returned bill metadata, see the bill metadata API method."
    allow_public_api_key = True
    def read(self, request, account):
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
        return paginate_items([t[0] for t in targets], request, xml_tag_name="bill")

@api_handler
class bill_search(BillHandler):
    description = "Search bills by bill number, keywords in bill titles, or bill full text."
    qs_args = (
        ('q', 'The search query.', 'H.R. 3'),
        ('mode', 'Optional. The search mode: "titles" to search bill titles only, "text" to search bill full text. Default: "titles"', None),
        )
    response_summary = "Returns a paginated list of bills matching the search. When mode is \"titles\" and the search query looks like a bill number, that bill is returned alone without searching bill titles. For documentation for the returned fields, see the bill metadata API method."
    response_fields = (
        ('context', 'When the search mode is "text", an additional field is available on each matching bill called context which is a string containing the context of the match search terms within the full text of the bill.'),
        )
    allow_public_api_key = True
    
    def bill_fields(self, request, account):
        f = BillHandler.bill_fields
        if request.GET.get('mode', 'titles') == "text":
            f = list(f) + ["context"]
        return f
    
    @paginate
    def read(self, request, account):
        q = request.GET.get("q", "").strip()
        mode = request.GET.get('mode', 'titles')
        
        if mode == 'titles':
            from bills import billsearch_internal
            bills, status, error = billsearch_internal(q)
            return bills
        elif mode == 'text':
            c = SphinxClient()
            c.SetServer("localhost" if not "REMOTEDB" in os.environ else os.environ["REMOTEDB"], 3312)
            c.SetMatchMode(SPH_MATCH_EXTENDED)
            c.SetFilter("doctype", [100])
            matches = c.Query(q, "doc_text")
            if not matches:
                return []
                
            ret = []
            seen_bills = set()
            
            for m in matches["matches"]:
                doc = PositionDocument.objects.get(id=m["attrs"]["document_id"])
                if doc.bill_id in seen_bills: continue
                
                seen_bills.add(doc.bill_id)
                bill = doc.bill
                
                # compute context
                text = doc.pages.filter(page=m["attrs"]["page"]).values("text")[0]["text"]
                text = re.sub(r"\s+", " ", text) # clean up whitespace
                context = " ".join(c.BuildExcerpts([text], "doc_text", q, { "before_match": "", "after_match": ""}))
                context = re.sub(r"^\s*\.\.\.\s*|\s*\.\.\.\s*$", "", context) # clean up whitespace
                bill.context = context
                
                ret.append(bill)
            
            return ret
        else:
            raise ValueError("Invalid value for 'mode' parameter.")
            
@api_handler
class bill_metadata(BillHandler):
    url_pattern_args = [("000", "BILL_ID")]
    url_example_args = (14113,)
    description = "Retreives metadata for a bill."
    response_summary = "Returns metadata for a bill."
    response_fields = (
        ('id', 'numeric identifier for a bill'),
        ('congressnumber', 'the "Congress" in which the bill was introduced, identifying a two-year Congressional session (currently %d)' % CURRENT_CONGRESS),
        ('billtype', 'a short identifier for the type of bill, one of: ' + ", ".join([x[1] for x in Bill.BILL_TYPE_SLUGS])),
        ('billnumber', 'the number of the bill, normally unique to a congressnumber and billtype, but non-unique in cases of "vehicles"'),
        ('title', 'the display title for the bill'),
        ('street_name', 'an alternative display name for a bill, without a number, and with an initial lowercase letter for short words (like a, an, the); optional'),
        ('status', 'description of bill status for a general audience'),
        ('status_advanced', 'description of bill status for a professional audience'),
        ('status_advanced_abbreviated', 'description of bill status for a professional audience with abbreviated committee names'),
        ('current_status_state', 'the date corresponding to the status, i.e. the date of the last major action'),
        ('sponsor', 'the sponsor of a bill; optional'),
        ('sponsor/id', 'the sponsor\'s numeric id'),
        ('sponsor/name', 'the display name of the sponsor'),
        ('topterm', 'the top-level CRS category for the bill; optional'),
        ('topterm/id', 'the category numeric id'),
        ('topterm/name', 'the display name of the category'),
        ('num_cosponsors', 'the number of cosponsors for the bill (not including the bill\'s primary sponsor)'),
        ('notes', 'special notes to indicate any procedural oddities about the bill; HTML formatted; optional'),
        ('link', 'absolute URL to the primary page for the bill on POPVOX'),
        ('shorturl', 'a "pvox.co" short URL to the primary page for the bill on POPVOX. the short URL is owned by the user specified in a session token, if provided, otherwise by the owner of the API key used in the request. this field is only returned if explicitly requested with fields=shorturl.'),
        )
    allow_public_api_key = True
    def read(self, request, account, billid):
        return Bill.objects.get(id=billid)

@api_handler
class bill_positions(BaseHandler):
    orgcampaignposition_fields = ['id', 'organization', 'position', 'comment', 'created']
    org_fields = ["id", "name", "link"]
    url_pattern_args = [("000", "BILL_ID")]
    url_example_args = (14113,)
    qs_args = (('position', 'Optional. Restricts positions to supporting (+), opposing (-), and neutral comments (0).', '+'),)
    description = "Returns organization endorsements and other positions related to a bill."
    response_summary = " Returns a paginated list of organization positions. It is possible for an organization to be listed more than once, although it is uncommon."
    response_fields = (
        ('id', 'a numeric identifier for the position record'),
        ('organization', 'the organization leaving the position'),
        ('organization/id', 'a numeric identifier for the organization'),
        ('organization/name', 'the display name for the organization'),
        ('organization/link', 'a link to the primary page on POPVOX for the organization'),
        ('position', 'the position of the organization on the bill, one of + for endorse, - for oppose, and 0 (zero) for a neutral position, usually with a comment set'),
        ('comment', 'a comment on the bill from the organization; plain text format; optional'),
        ('created', 'the date and time when the position record was entered into POPVOX'),
        )
    allow_public_api_key = True
    
    @paginate
    def read(self, request, acount, billid):
        return Bill.objects.get(id=billid).campaign_positions(position=request.GET.get("position", None))

    @staticmethod
    def organization(obj, request, account):
        return obj.campaign.org

    @staticmethod
    def link(obj, request, acct):
        return SITE_ROOT_URL + obj.url()
        
@api_handler
class org_positions(BillHandler):
    orgcampaignposition_fields = ['id', 'bill', 'organization', 'position', 'comment', 'created', 'updated'] 
    bill_fields = ['id', 'congressnumber','billtype', 'billnumber']
    org_fields = ["id", "name", "link"]
    example = (datetime.today() - timedelta(days=7)).strftime("%Y-%m-%d-%H:%M:%S") #for example purposes, org statements from the past seven days 
    url_pattern_args = [("000","TIMESTAMP")]
    url_example_args = (example,)
    description = "Returns all organization positions, with an optional argument to restrict by time (so you can just get the positions since your last query)."
    response_summary = " Returns a paginated list of organization positions. It is possible for an organization to be listed more than once, although it is uncommon."
    response_fields = (
        ('id', 'a numeric identifier for the position record'),
        ('bill/id', 'the popvox id of the bill the position refers to'),
        ('bill/congressnumber', 'the "Congress" in which the bill was introduced, identifying a two-year Congressional session (currently %d)' % CURRENT_CONGRESS),
        ('bill/billtype', 'a short identifier for the type of bill, one of: ' + ", ".join([x[1] for x in Bill.BILL_TYPE_SLUGS])),
        ('bill/billnumber', 'the number of the bill, normally unique to a congressnumber and billtype, but non-unique in cases of "vehicles"'),
        ('organization', 'the organization leaving the position'),
        ('organization/id', 'a numeric identifier for the organization'),
        ('organization/name', 'the display name for the organization'),
        ('organization/link', 'a link to the primary page on POPVOX for the organization'),
        ('position', 'the position of the organization on the bill, one of + for endorse, - for oppose, and 0 (zero) for a neutral position, usually with a comment set'),
        ('comment', 'a comment on the bill from the organization; plain text format; optional'),
        ('created', 'the date and time when the position record was entered into POPVOX'),
        ('updated', 'the date and time when the position record was last modified on POPVOX'),
        )
    allow_public_api_key = False

    
    @paginate
    def read(self, request, acct, inputdate=None):
        account, permissions = validate_widget_request(request, request.GET["api_key"],False)
        #permissions = ['api_congress']
        if not 'api_congress' in permissions:
            return HttpResponseBadRequest("This API key is not authorized for access to this API.")
        if inputdate:   
            dt = datetime.strptime(inputdate, "%Y-%m-%d-%H:%M:%S")
            return OrgCampaignPosition.objects.filter(Q(created__gte=dt) | Q(updated__gte=dt))
        else:
            return OrgCampaignPosition.objects.all()

    @staticmethod
    def organization(obj, request, account):
        return obj.campaign.org

    @staticmethod
    def link(obj, request, acct):
        return SITE_ROOT_URL + obj.url()
        
class DocumentHandler(BaseHandler):
    @staticmethod
    def pages(item, request, acct):
        return item.pages.count()

    @staticmethod
    def formats(item, request, acct):
        has_text = item.pages.filter(text__isnull=False).exists()
        has_html = item.pages.filter(html__isnull=False).exists()
        has_png = item.pages.exclude(png_file="").exclude(png_file=None).exists() # uninitialized documents have NULL in the database, but in other cases an un-set FileField is the empty string (?) 
        has_pdf = item.pages.exclude(pdf_file="").exclude(pdf_file=None).exists()
        return { "text": has_text, "pdf": has_pdf, "png": has_png }

@api_handler
class bill_documents(DocumentHandler):
    positiondocument_fields = ['id', 'title', 'created', 'doctype', 'pages', 'formats', 'pdf_url']
    url_pattern_args = [("000", "BILL_ID")]
    url_example_args = (16412,)
    qs_args = (('type', 'The document type. See the document metadata API method for type numbers.', '100'),)
    description = "Returns documents associated with a bill, including bill text (type 100)."
    response_summary = "This API method returns two sorts of documents: position documents uploaded by advocacy organizations and other entities, and the text of a bill. Note that bills may have more than one text document associated with it as bill text changes through the legislative process. Each bill text version remains on file as the bill changes. See the document metadata API method for documentation for the returned fields."
    allow_public_api_key = True
    
    def read(self, request, acount, billid):
        bill = Bill.objects.get(id=billid)
        # The iPad app relies on the latest bill text version being listed first.
        docs = bill.documents.all().order_by("-created")
        if "type"  in request.GET:
            docs = docs.filter(doctype=request.GET["type"])
        return docs

@api_handler
class document_metadata(DocumentHandler):
    bill_fields = ["id", "title", "link"]
    positiondocument_fields = ['id', 'bill', 'title', 'created', 'doctype', 'pdf_url', 'pages', 'formats', 'toc']
    url_pattern_args = [("000", "DOCUMENT_ID")]
    url_example_args = (248,)
    description = "Returns metadata about a document."
    response_summary = "Metadata about a document."
    response_fields = (
        ('id', 'a numeric identifier for the document'),
        ('title', 'the display title for the document'),
        ('created', 'for position documents, this is the date the document was uploaded. for bill text, this is the date the bill text was published.'),
        ('doctype', 'the type of the document: ' + ", ".join(str(kv[0]) + ": " + kv[1] for kv in PositionDocument.DOCTYPES)),
        ('pdf_url', 'the URL from which a PDF file can be downloaded of the whole document, probably not residing on popvox.com; may be null'),
        ('pages', 'the number of pages in the document, zero if the page content is not available'),
        ('formats', 'the formats available for page content'),
        ('toc', 'an auto-generated table of contents for the document, available for bill text documents only and this field is only returned in the document metadata API method. a flat list of TOC entries.'),
        ('toc/indentation', 'a zero-based indentation level for the TOC entry'),
        ('toc/label', 'the text label of the TOC entry'),
        ('toc/page', 'the one-based page number for the TOC entry'),
        )
    allow_public_api_key = True
    
    def read(self, request, acct, docid):
        try:
            return PositionDocument.objects.get(id=docid)
        except PositionDocument.DoesNotExist:
            raise Http404("Invalid document ID.")
        
    @staticmethod
    def toc(item, request, acct):
        return json.loads(item.toc) if item.toc else None
        
    @staticmethod
    def link(bill, request, acct):
        return SITE_ROOT_URL + bill.url()
        
@api_handler
class document_pages(BaseHandler):
    documentpage_fields = ['page', 'text']
    description = "Retreives complete data for all pages of a document, except binary data associated with a page (such as its image)."
    url_pattern_args = (("000",'DOCUMENT_ID'),)
    url_example_args = (248,)
    response_summary = "Returns a paginated list of pages."
    response_fields = (
        ('page', 'the one-based page number'),
        ('text', 'the plain text content of the page'),
        )
    allow_public_api_key = True
    
    @paginate
    def read(self, request, acct, docid):
        try:
            doc = PositionDocument.objects.get(id=docid)
            return doc.pages.order_by('page').only("page", "text")
        except PositionDocument.DoesNotExist:
            raise Http404("Invalid document ID.")

@make_simple_endpoint
@cache_page(60*60*2)
def document_page(request, docid, pagenum, format):
    try:
        doc = PositionDocument.objects.get(id=docid)
        page = doc.pages.only("id").get(page=pagenum) # defer fields
        if format == "png":
            if page.png_file:
                return HttpResponseRedirect(page.png_file.url)
            else:
                raise Http404("PNG not available for this page.")
        elif format == "html":
            return HttpResponse(page.html, "text/html")
        elif format == "txt":
            return HttpResponse(page.text, "text/plain")
        elif format == "pdf":
            if page.pdf_file:
                return HttpResponseRedirect(page.pdf_file.url)
            else:
                raise Http404("PDF not available for this page.")
        else:
            raise Http404("Invalid page format.")
    except PositionDocument.DoesNotExist:
        raise Http404("Invalid document ID.")
    except DocumentPage.DoesNotExist:
        raise Http404("Page number out of range.")
document_page.description = "Retreives one page of a document as either a PNG, a single-page PDF, or in plain text. Result is either image/png, application/pdf, or text/plain. The formats available for a document are given in the document metadata API method."
document_page.url_pattern_args = (("000",'DOCUMENT_ID'), ("001",'PAGE_NUMBER'), ('aaa', '{png|pdf|txt}'))
document_page.url_example_args = (248,20,'png')
document_page.has_read = True
document_page.has_post = False

@api_handler
class document_search(BaseHandler):
    DocumentPage = ['page']
    description = "Searches a document for text, returning a list of matching pages and context."
    response_summary = "Returns a list of matching pages and context within each page."
    response_fields = (
        ('keywords', 'a list of tokens in the search string'),
        ('results', 'a list of matching pages and context'),
        ('results/page', 'the page number of the match'),
        ('results/context', 'text surrounding the match'),
        )
    url_pattern_args = (("000",'DOCUMENT_ID'),)
    url_example_args = (248,)
    qs_args = (('q', 'The search query.', 'budget authority'),)
    allow_public_api_key = True
    
    def read(self, request, acct, docid):
        q = request.GET.get("q", "").strip()
        
        c = SphinxClient()
        c.SetServer("localhost" if not "REMOTEDB" in os.environ else os.environ["REMOTEDB"], 3312)
        c.SetMatchMode(SPH_MATCH_EXTENDED)
        c.SetFilter("document_id", [int(docid)])
        ret = None
        if q != "":
            ret = c.Query(q, "doc_text")
        if ret == None:
            ret = { "matches": [] }
            
        pages = []
        
        for page in (m["attrs"]["page"] for m in ret["matches"]):
            # compute context for this search result...
            
            # get the page content
            text = DocumentPage.objects.filter(document = docid, page = page).values("text")[0]["text"]
            text = re.sub(r"\s+", " ", text) # clean up whitespace
            context = " ".join(c.BuildExcerpts([text], "doc_text", q, { "before_match": "", "after_match": ""}))
            context = re.sub(r"^\s*\.\.\.\s*|\s*\.\.\.\s*$", "", context) # clean up whitespace
                
            pages.append(OrderedDict([
                ("page", page),
                ("context", context)]))
        
        pages.sort(key = lambda p : p["page"])
        
        return {
            "keywords": [k["tokenized"] for k in c.BuildKeywords(q.encode("utf8"), "doc_text", 0)],
            "results": pages,
        }
    
@api_handler
class comments(BaseHandler):
    bill_fields = ('id', 'title')
    description = "Retrieves constituent comments on bills. Returns a paginated list of comments."
    qs_args = (
        ('bill', 'Optional. Restrict comments to a single bill, given by bill ID.', None),
        ('has_message', 'Optional. Set to "1" to only return comments with messages.', '1'),
        ('state', 'Optional. Restrict comments to users from a state. Set to a USPS state abbreviation.', 'NY'),
        ('district', 'Optional. Restrict comments to users from a congressional district. Set this parameter to an integer, the Congressional district, and also set the state parameter.', '2'),
        ('position', 'Optional. Restrict comments to either supporting (+) or opposing (-) comments. Be sure to URL-encode the argument.', '+'),)
    response_summary = "Returns a paginated list of comments on bills left by users."
    response_fields = (
        ('id', 'a numeric identifier for the comment'),
        ('bill', 'the bill to which the comment refers'),
        ('bill/id', 'the numeric identifier of the bill'),
        ('bill/title', 'the display title of the bill'),
        ('position', 'the comment\'s position: + for support or - for oppose. (there is no neutral option for comments)'),
        ('position_text', 'the comment\'s position as an English verb'),
        ('screenname', 'the screen name of the individual leaving the comment'),
        ('message', 'the personal message left with the comment; optional'),
        ('created', 'the date the message was first written'),
        ('state', 'the two-letter USPS state abbreviation for the physical address where the individual votes'),
        ('congressionaldistrict', 'the congressional district (within the indicated state) where the individual votes'),
        ('link', 'an absolute URL to the page to view the comment on POPVOX (if message is null, this is a URL to the bill instead as there is no view page)'),
        ('address', 'constituent address information provided when a legislative staff API key or session token is used and the legislative staff account is in the office of a Member of Congress representing the state and, for congressmen, the district specified in the query string filter arguments'),
        ('address/name', 'when authorized as above, the constituent\'s full name'),
        ('address/address', 'when authorized as above, the constituent\'s postal address, which can be two or three lines separated by newline (\\n) characters'),
        ('address/phonenumber', 'when authorized as above, the constituent\'s phone number'),
        ('address/latitude', 'when authorized as above, the constituent\'s postal address\'s latitude'),
        ('address/longitude', 'when authorized as above, the constituent\'s postal address\'s longitude'),
        ('address/email', 'when authorized as above, the constituent\'s email address'),
        )
        
    @paginate
    def read(self, request, acct):
        items = UserComment.objects.all().select_related("user", "bill", "bill_sponsor")
        if "bill" in request.GET: items = items.filter(bill=int(request.GET["bill"]))
        if request.GET.get("has_message", "0") == "1": items = items.filter(message__isnull=False)
        if "state" in request.GET:
            items = items.filter(state=request.GET["state"])
            if "district" in request.GET: items = items.filter(congressionaldistrict=request.GET["district"])
        if "position" in request.GET: items = items.filter(position=request.GET["position"])
        return items

    @staticmethod
    def screenname(item, request, acct):
        return item.user.username
        
    @staticmethod
    def link(item, request, acct):
        if item.message:
            return SITE_ROOT_URL + item.url()
        else:
            return None
            
    @staticmethod
    def position_text(item, request, acct):
        return item.verb()
    
    @staticmethod
    def referral(item, request, acct):
        return [str(r) for r in item.referrers()]
        
    @staticmethod
    def usercomment_fields(request, acct):
        fields = ['id', 'bill', 'position', 'position_text', 'screenname', 'message', 'created', 'state', 'congressionaldistrict', 'link']

        if request.user.is_authenticated() and request.user.userprofile.is_leg_staff() and request.user.legstaffrole.member != None:
            member = govtrack.getMemberOfCongress(request.user.legstaffrole.member_id)
            if member != None and member["current"]:
                if member["state"] == request.GET.get("state", "").upper() and (member["district"] == None or member["district"] == int(request.GET.get("district", "-1"))):
                    request.is_leg_staff = True
                    fields.append('address')
                    comments.postaladdress_fields = ('name', 'address', 'phonenumber', 'latitude', 'longitude', 'email')
            
        return fields
        
    @staticmethod
    def postaladdress_name(item, request, acct):
        return item.name_string()
        
    @staticmethod
    def postaladdress_address(item, request, acct):
        return item.address_string()

    @staticmethod
    def postaladdress_email(item, request, acct):
        return item.user.email
        
@api_handler
class user_login(BaseHandler):
    description = "Creates a session token for a POPVOX user."
    post_args = (
        ('email', 'User\'s email address.'),
        ('password', 'User\'s POPVOX password.'),
        )
    response_summary = "Returns a session token, or an error."
    response_fields = (
        ('status', '"success" or "fail"'),
        ('msg', 'on failure, a descriptive error message of the login failure'),
        ('session', 'on success, a session token (a string)'),
        )
    def post(self, request, acct):
        from registration.helpers import validate_email, validate_password
        from django.contrib.auth import login, authenticate
        try:
            email = validate_email(request.POST.get("email", ""), for_login=True)
            password = validate_password(request.POST.get("password", ""))
        except:
            return { "status": "fail", "msg": "Invalid username or password." }
        user = authenticate(email=email, password=password)
        if user == None:
            return { "status": "fail", "msg": "That's not an email and password combination we have on file.", "info": (email, password) }
        elif not user.is_active:
            return { "status": "fail", "msg": "Your account has been disabled." }
        else:
            login(request, user)
            return { "status": "success", "session": request.session.session_key }

@api_handler
class user_logout(BaseHandler):
    description = "Clears a session token so that it is no longer usable. This request must be sent as a POST."
    response_summary = "This API is always successful and has no useful response."
    def post(self, request, acct):
        from django.contrib.auth import logout
        logout(request)
        return { "status": "success" }

@api_handler
class user_get_info(BaseHandler):
    description = "Gets basic information about the logged in user, either based on a session token parameter or on the user account associated with the API key."
    qs_args = (
        ('session', 'Optional. A session token returned by the user login API method. If the session token is not provided, your API key must be associated with a user account. If not, an error occurs.', None),
        )
    response_fields = (
        ('email', 'your email address'),
        ('name', 'the full name associated with organization and legislative staff accounts'),
        ('screenname', 'the screen name associated with your account (only applicable for individual accounts)'),
        ('locality', 'locality information if known for the user (optional)'),
        ('locality/state', 'the two-letter USPS state abbreviation for the user\'s state'),
        ('locality/district', 'the user\'s congressional district'),
        ('locality/is_leg_staff', 'true if the user is a legislative staffer for this district and will be able to access the private information of her or her constituents in this state or district, false or not set otherwise'),
        )
    allow_empty_api_key = True
    
    def read(self, request, acct):
        if not request.user.is_authenticated():
            return HttpResponseBadRequest("No valid session token was specified and your API key is not associated with a user account.")
        ret = {
            "screenname": request.user.username,
            "email": request.user.email,
            "name": request.user.get_profile().fullname,
            "secret_api_key": acct.secret_key,
            "public_api_key": acct.api_key,
        }

        if request.user.userprofile.is_leg_staff() and request.user.legstaffrole.member != None:
            member = govtrack.getMemberOfCongress(request.user.legstaffrole.member_id)
            if member != None and member["current"]:
                ret["locality"] = {
                    "state": member["state"],
                    "district": member["district"],
                    "is_leg_staff": True
                }

        return ret
        
        
@api_handler
class org_get_info(BaseHandler):
    description = "Returns contact and social media information about an organization on POPVOX. Because this call includes private information, sich as contact information for the organization's legislative relations contact, it is restricted to congressional staff. If you're a congressional staffer seeking to use this API call, please contact info@popvox.com."
    url_pattern_args = [("000", "ORG_ID")]
    url_example_args = (1434,)
    response_fields = (
        ('address', 'the organization\'s mailing address'),
        #('contact', 'the organization\'s legislative relations contact'), It doesn't look like we have this yet.
        #('email', 'email address for the organization\'s legislative relations contact'), It doesn't look like we have this yet.
        ('facebook', 'the organization\'s facebook account'),
        ('facebook_count', 'number of facebook fans the org has'),
        #('gplus', 'the organization\'s google plus account'),
        ('name', 'full name of organization associated with org id'),
        ('phone', 'phone number for the organization\'s legislative relations contact'),
        ('twitter', 'the organization\'s twitter account'),
        ('twitter_count', 'number of twitter followers the org has'),
        ('url', 'the organization\'s website'),
        )
    allow_empty_api_key = False
    allow_public_api_key = False
    
    def read(self, request, acct, orgid):
        account, permissions = validate_widget_request(request, request.GET["api_key"],False)
        print request.GET["api_key"]
        #permissions = ['api_congress']
        print permissions
        if not 'api_congress' in permissions:
            return HttpResponseBadRequest("This API key is not authorized for access to this API.")
        org = Org.objects.get(id=orgid)
            
        ret = {
            "address": org.postaladdress,
            #"contact":, uncomment when we have this in the org model
            #"email": , uncomment when we have this in the org model
            "facebook": org.facebookurl,
            "facebook_count": org.facebook_fan_count(),
            #"gplus": org.gplus #TODO: fix this once gplus is committed.
            "name": org.name,
            "phone": org.phonenumber,
            "twitter": org.twittername,
            "twitter_count": org.twitter_follower_count(),
            "url": org.website,
        }

        return ret
        
@api_handler
class user_registration_fields(BaseHandler):
    description = "Gets field options for implementing the user registration API method."
    response_fields = (
        ('legislative_staff', 'registration options for legislative staff'),
        ('legislative_staff/committee', 'a list of congressional committees in sorted order appropriate for showing the shortname field in a list'),
        ('legislative_staff/committee/id', 'the identifier for the committee. House members serve on committees whose id\'s start with H and J; Senate members serve on committees whose id\'s start with S and also J.'),
        ('legislative_staff/committee/name', 'the full name of the committee'),
        ('legislative_staff/committee/shortname', 'the short display name of the committee'),
        ('legislative_staff/office', 'a list of congressional member offices in sorted order appropriate for showing the listname field in a list'),
        ('legislative_staff/office/id', 'the identifier for the Member of Congress'),
        ('legislative_staff/office/name', 'the full name of the Member of Congress'),
        ('legislative_staff/office/listname', 'the name of the Member of Congress suitable for display in a sorted list'),
        ('legislative_staff/office/type', '"sen" for senators, "rep" for congressmen and House delegates'),
        ('legislative_staff/position', 'a list of choices for legislative staff position')
        )
    
    # static field initialization
    
    # build committee list
    committees = [
    { "id": c["id"], "name": c["name"], "shortname": c["shortname"] }
    for c in govtrack.getCommitteeList() if not "parent" in c]
    
    # sort, putting joint committees at the end, then by shortname
    committees.sort(key = lambda c : (c["id"][0] == "J", c["shortname"]))
    
    # build member list
    members = [
        { "id": m["id"], "name": m["name"], "listname": m["sortkey"], "type": m["type"] }
        for m in govtrack.getMembersOfCongress()]
    members.sort(key = lambda m : m["listname"])
    
    # build position list
    staff_positions = ('Legislative Assistant', 'Legislative Counsel', 'Other Legislative/Policy Staff', 'Legislative Correspondent', 'Press Secretary', 'Other Communications Staff', 'System Administrator / IT', 'Intern', 'Senator / Congressman/woman', 'Other')
    
    def read(self, request, acct):
        return {
            "legislative_staff": {
                "office": self.members,
                "committee": self.committees,
                "position": self.staff_positions,
            }
        }

@api_handler
class user_registration(BaseHandler):
    description = "Begins the registration process for a new POPVOX user."
    post_args = (
        ('mode', 'the type of user being registered: "individual", "legislative_staff", or "member_of_congress"'),
        ('email', 'the user\'s email address'),
        ('password', 'the user\'s chosen POPVOX password'),
        ('username', 'for individual registrations, the user\'s chosen screen name'),
        ('fullname', 'for legislative_staff registrations, the user\'s full real name'),
        ('position', 'for legislative_staff registrations, the user\'s staff position, from the set of position choices given by the user registration fields API method'),
        ('member', 'for legislative_staff registrations the office the user works for, and for member_of_congress registrations the ID of the Member of Congress, from the "id" field of one of the entries in the office list given by the user registration fields API method; optional for legislative_staff registrations only (i.e. can be blank or missing)'),
        ('committee', 'for legislative_staff registrations, the committee the user works for, from the "id" field of one of the entries in the committee list given by the user registration fields API method; optional (i.e. can be blank or missing)'),
        ('next', 'a page on POPVOX to redirect the user to after confirming his or her email address, given as a relative URL starting with the "/" that comes after the popvox.com domain; optional'),
        )
    response_summary = "All user registrations require the user to confirm his or her email address before the registration is complete. A successful call to this method results \"success\" and a message instructing the user to check his email."
    response_fields = (
        ('status', 'either "success" or "fail"'),
        ('message', 'a message to display to the user; always present when status is "success", sometimes present when status is "fail"'),
        ('errors', 'if present, a set of validation errors'),
        ('errors/email', 'if present, an error message corresponding to the email field'),
        ('errors/password', 'if present, an error message corresponding to the password field'),
        ('errors/username', 'if present, an error message corresponding to the username field'),
        ('errors/fullname', 'if present, an error message corresponding to the fullname field'),
        ('errors/position', 'if present, an error message corresponding to the position field'),
        )
    
    def post(self, request, acct):
        status = { }
        
        from registration.helpers import validate_email, validate_password, validate_username
        from profile import legstaffemailcheck, test_field_provided, RegisterUserAction
        
        if not request.POST.get("mode", "") in ("individual", "legislative_staff", "member_of_congress"):
            return { "status": "fail", "message": "missing or invalid parameter 'mode'" }
        
        email = validate_email(request.POST.get("email", ""), fielderrors = status)
        password = validate_password(request.POST.get("password", ""), fielderrors = status)
        
        if request.POST["mode"] == "individual":
            username = validate_username(request.POST.get("username", ""), fielderrors = status)
            if legstaffemailcheck(email):
                status["email"] = "Congressional staff should register in the House/Senate legislative staff section."
        else:
            # for leg staff and org staff, we'll use the email address for the username
            # too, since we never actually use it for anything but Django needs it.
            # TODO: The username field is quite a bit shorter than the email field
            # which could result in a uniqueness clash. Also truncate to length
            # of User.username field or risk a truncation warning.
            username = email[0:30]
            
        axn = RegisterUserAction()
        axn.email = email
        axn.username = username
        axn.password = password

        if "next" in request.POST:
            axn.next = request.POST["next"]
        elif acct.id == 1191: # special redirect for the ipad application
            axn.next = "/ipad/registration/welcome"

        if request.POST["mode"] in ("legislative_staff", "member_of_congress"):
            if not legstaffemailcheck(axn.email):
                 status["email"] = "Provide a mail.house.gov or senate.gov email address."
    
            axn.mode = "legstaff"
            if request.POST["mode"] == "legislative_staff":
                axn.fullname = test_field_provided(request, "fullname", fielderrors = status)
                axn.member = int(request.POST["member"]) if request.POST.get("member", "") != "" else None
                axn.committee = request.POST["committee"] if request.POST.get("committee", "") != "" else None
                axn.position = test_field_provided(request, "position", fielderrors = status)
            else:
                try:
                    member = int(request.POST["member"])
                    axn.fullname = govtrack.getMemberOfCongress(member)["name"]
                except:
                    return { "status": "fail", "message": "missing or invalid parameter 'member'" }                    
                axn.member = member
                axn.committee = None
                axn.position = "Senator / Congressman/woman"
            
        if len(status) != 0:
            return { "status": "fail", "errors": status }

        success_message = { "status": "success", "message": "Check your email. We need to confirm your email address before you can continue." }

        try:
            from emailverification.utils import send_email_verification
            r = send_email_verification(email, None, axn)
            if getattr(settings, "IS_TESTING", False):
                success_message["testing_email_link"] = r.url()
        except Exception, e:
            return { "status": "fail", "message": "There was a problem sending you an email: " + unicode(e) }
            
        return success_message

#####################################################################

def documentation(request):
    api_keys = list(request.user.userprofile.service_accounts(create=True)) if request.user.is_authenticated() else []
    
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
    
    def prepare_documentation(f):
        if len(api_keys) > 0:
            api_key = api_keys[0].secret_key
            if f.allow_public_api_key:
                api_key = api_keys[0].api_key
        
        ret = {
            "api_display_name": f.__name__.replace("_", " "),
            "description": getattr(f, "description", "(no description)"),
            "has_read": f.has_read,
            "qs_args": getattr(f, "qs_args", []),
            "has_post": f.has_post,
            "post_args": getattr(f, "post_args", []),
            "response_summary": getattr(f, "response_summary", ""),
            "response_fields": getattr(f, "response_fields", []),
            "allow_public_api_key": f.allow_public_api_key,
        }
        
        try:
            args = getattr(f, "url_pattern_args", [])
            ret["url_pattern"] = reformat_args_2(reverse('popvox.views.api.' + f.__name__, args=reformat_args_1(args)), args)
            ret["url_pattern"] += getattr(f, "url_pattern_qs", "")
        except Exception as e:
            ret["url_pattern"] =  str(e)

        try:
            ret["url_example"] = reverse('popvox.views.api.' + f.__name__, args=getattr(f, "url_example_args", []))
            
            additional_args = []
            for name, descr, example in getattr(f, "qs_args", []):
                if example:
                    additional_args.append( (name, example) )
            if len(api_keys) > 0:
                additional_args.append( ('api_key', api_key) )
            if len(additional_args) > 0:
                ret["url_example"] += "?" + urllib.urlencode(additional_args)
            
        except Exception as e:
            ret["url_example"] = str(e)
            
        return ret
            
    return render_to_response('popvox/apidoc.html', {
        'accounts': api_keys,
        'methods': [prepare_documentation(f) for f in api_endpoints],
        }, context_instance=RequestContext(request))

