from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist

from popvox.models import *
from popvox.govtrack import statelist, CURRENT_CONGRESS

from widgets import do_not_track_compliance

def widget_config(request):
	# Collect all of the ServiceAccounts that the user has access to.
	
	return render_to_response('popvox/services_widget_config.html', {
		'accounts': request.user.userprofile.service_accounts() if request.user.is_authenticated() else [],
		
		'issueareas': IssueArea.objects.filter(parent__isnull=True),
		"states": statelist,
		"current_congress": CURRENT_CONGRESS,
		}, context_instance=RequestContext(request))

def widget_render(request, widgettype, account_key=None, widgetconfig_id=None):
	comments = UserComment.objects.filter(message__isnull=False, status__in=(UserComment.COMMENT_NOT_REVIEWED, UserComment.COMMENT_ACCEPTED)).order_by("-created")
	
	title = ["Recent Comments"]
	show_bill_number = True
	
	if "state" in request.GET:
		comments = comments.filter(state=request.GET["state"])
		title.append("in " + request.GET["state"])

	cx = []
	
	if "bills" in request.GET:
		for b in request.GET["bills"].split(","):
			position = None
			if b.endswith(":supporting"):
				position = "+"
				b = b[0:-len(":supporting")]
			if b.endswith(":opposing"):
				position = "-"
				b = b[0:-len(":opposing")]
			b = bill_from_url("/bills/" + b)
			
			if not position:
				cx.append(comments.filter(bill=b))
			else:
				cx.append(comments.filter(bill=b, position=position))
			
		if len(cx) == 1: # the bills have to be processed first
			show_bill_number = False
			title[0] = "Comments on " + b.displaynumber()

	if "issue" in request.GET:
		cx.append(comments.filter(bill__topterm__id=request.GET["issue"]))
		title[0] = "Comments on " + IssueArea.objects.get(id=request.GET["issue"]).name

	if len(cx) > 0:
		comments = cx[0]
		for c in cx[1:]:
			comments |= c
				
	comments = comments[0:25]
	
	return render_to_response('popvox/widgets/' + widgettype + '.html', {
		'title': " ".join(title),
		'comments': comments,
		"show_bill_number": show_bill_number,
		}, context_instance=RequestContext(request))

