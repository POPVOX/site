from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.views.generic.simple import direct_to_template
from django.contrib.auth.decorators import login_required
from django import forms
from django.contrib import messages
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.utils.html import strip_tags

from jquery.ajax import json_response, ajax_fieldupdate_request, sanitize_html, ajaxmultifieldupdate

import re
from xml.dom import minidom
import urllib
import cgi
from StringIO import StringIO
from datetime import datetime

from popvox.models import *
from popvox.views.bills import getissueareas
from popvox.views.main import strong_cache
from popvox.views.slate import orgpermission
from popvox.views.widgets import getpositions
from popvox import govtrack
from utils import csrf_protect_if_logged_in

from emailverification.utils import send_email_verification

from settings import SITE_ROOT_URL, EMAILVERIFICATION_FROMADDR

@strong_cache
def orgs(request):
    return render_to_response('popvox/org_list.html', {
        'issueareas': IssueArea.objects.filter(parent=None).order_by('name'),
        "states": ((state, name) for state, name in govtrack.statelist if Org.objects.filter(visible=True, homestate=state).exists()),
        "show_share_footer": True,
        #'recent': Org.objects.filter(visible=True).order_by('-updated')[0:30],
        }, context_instance=RequestContext(request))

@csrf_protect_if_logged_in
def org(request, orgslug):
    org = get_object_or_404(Org, slug=orgslug)
    if org.is_admin(request.user):
        cams = org.orgcampaign_set.all().order_by("-default", "name")
        slates = org.slates.all()
    elif not org.visible:
        raise Http404()
    else:
        cams = org.campaigns()
        slates = org.slates.filter(visible= True)
    
    positions = getpositions(cams)
    serviceacct = org.service_account(create=True)
    set_last_campaign_viewed(request, org)

    # quick fix in case the org twitter account hasn't been updated
    twitter_update = org.sync_external_members()
    
    
    return render_to_response('popvox/org.html', {
        'org': org,
        'admin': org.is_admin(request.user),
        'slates': slates,
        "cams": cams,
        "positions": positions,
        "embed": True, #this triggers css changes on the embedded leg-agenda template
        
        # list of orgs user admins that can join this org
        "coalition_can_join": Org.objects.filter(admins__user=request.user).exclude(id=org.id).exclude(ispartofcoalition=org)
            if request.user.is_authenticated() and org.admins.exists() and org.iscoalition else None,
        
        # list of orgs user admins that can invite this org
        "coalition_can_invite": Org.objects.filter(iscoalition=True, admins__user=request.user).exclude(id=org.id).exclude(coalitionmembers=org)
            if request.user.is_authenticated() and org.admins.exists() else None,
        
        # list of orgs user admins that can leave this org
        "coalition_can_leave": Org.objects.filter(admins__user=request.user).filter(ispartofcoalition=org)
            if request.user.is_authenticated() and org.admins.exists() and org.iscoalition else None,
        
        "show_share_footer": True,
        }, context_instance=RequestContext(request))

@csrf_protect
@login_required
def org_edit(request, orgslug):
    org = get_object_or_404(Org, slug=orgslug)
    if not org.is_admin(request.user):
        return HttpResponseForbidden("You do not have permission to view this page.")
    
    set_last_campaign_viewed(request, org)

    return render_to_response('popvox/org_edit.html', {
        'org': org,
        "states": govtrack.statelist,
        }, context_instance=RequestContext(request))
    
@json_response
def org_search(request):
    ret = ""
    ix = None
    if "term" in request.REQUEST:
        limit = 15 # int(request.REQUEST["limit"])
        q = Org.objects.filter(visible = True, name__icontains=request.REQUEST["term"])[0:limit]
    elif "issue" in request.REQUEST:
        ix = IssueArea.objects.get(slug=request.REQUEST["issue"])
        q = ix.orgs()
    elif "state" in request.REQUEST:
        q = Org.objects.filter(visible=True, homestate=request.REQUEST["state"])
    else:
        return ret # googlebot

    def out_org(org):
        return { "label": org.name, "slug": org.slug, "url": org.url(), "createdbyus": org.createdbyus,
        "homestate": govtrack.statenames[org.homestate] if org.homestate != None else None,
        "fan_sort_order": org.fan_count_sort_order
        }
    def out_orgs(orglist):
        ret = [out_org(org) for org in orglist]
        ret.sort(key = lambda x : x["label"].replace("The ", ""))
        return ret
        
    if request.REQUEST.get("group", "") == "":
        ret = out_orgs(q)
    else:
        from utils import group_by_issue
        ret = group_by_issue(q, exclude_issues=[ix], other_title="Other Organizations")
        for group in ret:
            if isinstance(group["name"], IssueArea): group["name"] = group["name"].name
            group["objlist"] = out_orgs(group["objlist"])
    
    if "format" in request.REQUEST:
        ret = { "status": "success", "orgs":  ret }
        
    return ret
    
@csrf_protect
@ajaxmultifieldupdate(["org"])
def org_update_fields(request, field, value, validate_only):
    org = get_object_or_404(Org, slug=request.POST["org"])
    if not org.is_admin(request.user) :
        return HttpResponseForbidden("You do not have permission to view this page.")
    
    org.updated = datetime.datetime.now() # update on save
    
    if field == "slug":
        value = forms.SlugField().clean(value) # raises ValidationException
        if value == org.slug:
            return { "status": "fail", "msg": "That's already your slug." }
        if len(Org.objects.filter(slug=value)) > 0:
            return { "status": "fail", "msg": "That slug is in use by another organization." }
        if value != value.lower():
            return { "status": "fail", "msg": "Slugs must be all lowercase." }
        if not validate_only and value != org.slug:
            org.slug = value
            org.save()
        return { "status": "success", "value": value, "newslug": value }
    elif field == "name":
        value = forms.CharField(min_length=5, error_messages = {'min_length': "That's too short."}).clean(value) # raises ValidationException
        if not validate_only and value != org.name:
            org.name = value
            org.save()
        return { "status": "success", "value": value }
    elif field == "website":
        if value != "" and value[0:7] != "http://":
            value = "http://" + value
        value = forms.URLField(required=False).clean(value)
        if not validate_only and value != org.website:
            org.website = value
            org.save()
        return { "status": "success", "value": value }
    elif field == "description":
        value = forms.CharField(min_length=5, max_length=2000, error_messages = {'min_length': "You must provide a concise description of your organization."}).clean(value) # raises ValidationException
        if not validate_only and value != org.description:
            org.description = value
            org.save()
        return { "status": "success", "value": value }
    elif field == "postaladdress":
        if not validate_only and value != org.postaladdress:
            org.postaladdress = value
            org.save()
        return { "status": "success", "value": value }
    elif field == "phonenumber":
        from django.contrib.localflavor.us.forms import USPhoneNumberField
        if value != "":
            value = USPhoneNumberField().clean(value)
        if not validate_only and value != org.phonenumber:
            org.phonenumber = value
            org.save()
        return { "status": "success", "value": value }
    elif field == "homestate":
        if value == "":
            value = None
        elif not value in govtrack.statenames:
            return { "status": "fail", "msg": "Invalid state." }
        if not validate_only and value != org.homestate:
            org.homestate = value
            org.save()
        return { "status": "success", "value": value }
    elif field == "twittername":
        if value == "":
            if not validate_only and org.twittername != None:
                org.twittername = None
                org.save()
                try:
                    org.sync_external_members()
                except:
                    pass
            return { "status": "success", "value": value }
        else:
            org.twittername = value
            org.save()
            return { "status": "success", "value": value }
            #twitter name verification is broken. The t variable isn't being set right.
            #for now, just pulling that out and accepting what users enter.
            '''from urllib import urlopen, quote_plus
            from xml.dom import minidom
            try:
                t = minidom.parse(urlopen("http://api.twitter.com/1/users/show.xml?screen_name=" + quote_plus(value.encode('utf-8'))))
                sys.stderr.write('line 213\n')
                er = t.getElementsByTagName('error')
                sys.stderr.write('line 215\n')
                if len(er) > 0 and "Rate limit exceeded." in er[0].firstChild.data:
                    if not validate_only and value != org.twittername:
                        org.twittername = value
                        org.save()
                    return { "status": "success", "value": value }
                sys.stderr.write('line 221\n')
                value = t.getElementsByTagName('screen_name')[0].firstChild.data
                sys.stderr.write('line 223\n')
                if not validate_only and value != org.twittername:
                    org.twittername = value
                    org.save()
                    try:
                        org.sync_external_members()
                    except:
                        pass
                return { "status": "success", "value": value }
                sys.stderr.write('line 232\n')
            except Exception, e:
                raise ValueError("That is not a Twitter name.")'''
    elif field == "gplusurl":
        if value == "":
            if not validate_only and org.gplusurl != None:
                org.gplusurl = None
                org.save()
                try:
                    org.sync_external_members()
                except:
                    pass
            return { "status": "success", "value": value }
        else:
            from urllib2 import urlopen
            try:
                urlopen(value)
                org.gplusurl = value
                org.save()
                return { "status": "success", "value": value }
            except urllib2.HTTPError:
                raise ValueError("That is not a valid Google+ account.")

    elif field == "facebookurl":
        if value == "":
            if not validate_only and org.facebookurl != None:
                org.facebookurl = None
                org.save()
                try:
                    org.sync_external_members()
                except:
                    pass
            return { "status": "success", "value": value }
        
        gid = None
        
        import re
        m = re.search(r"/pages/[^/]+/(\d+)", value)
        if m != None:
            gid = m.group(1)

        m = re.match(r"^https?://(www.)?facebook.com/([^/ ]+)$", value)
        if m != None:
            gid = m.group(2)

        m = re.match(r"^https?://(www.)?facebook.com/group.php\?gid=(\d+)$", value)
        if m != None:
            gid = m.group(2)

        m = re.match(r"^https?://(www.)?facebook.com/home.php\?sk=group_(\d+)$", value)
        if m != None:
            gid = m.group(2)
            
        if gid == None:
            gid = value
            value = "http://www.facebook.com/" + value
        
        from urllib import urlopen, quote_plus
        import json
        fb = json.load(urlopen("http://graph.facebook.com/" + gid))
        if type(fb) == dict:
            if "error" in fb:
                raise ValueError("That is not a Facebook Page or Group address.")
            if "link" in fb and "http://www.facebook.com" in fb["link"] : # normalize value to what Facebook says, FB Group link values are to an external website...
                value = fb["link"]
        if not validate_only and value != org.facebookurl:
            org.facebookurl = value
            
            # If no logo is set, grab it from Facebook, if set in the picture property.
            if not org.logo and type(fb) == dict and "picture" in fb:
                try:
                    data = urlopen(fb["picture"])
                    org_update_logo_2(org, StringIO(data.read()))
                except:
                    import traceback
                    traceback.print_exc()
                    pass
            # or try the graph.facebook.com/.../picture URL.
            elif not org.logo and type(fb) == dict and "id" in fb:
                try:
                    data = urlopen("http://graph.facebook.com/" + fb["id"] + "/picture?type=large")
                    org_update_logo_2(org, StringIO(data.read()))
                except:
                    pass
            org.save()

            try:
                org.sync_external_members()
            except:
                pass

        return { "status": "success", "value": value }
    else:
        raise Exception("Bad request: Invalid field: " + field)
    
@csrf_protect
@json_response
@ajax_fieldupdate_request
def org_update_field(request, field, value, validate_only):
    org = get_object_or_404(Org, slug=request.POST["org"])
    if not org.is_admin(request.user) :
        return HttpResponseForbidden("You do not have permission to view this page.")
        
    org.updated = datetime.datetime.now() # update on save
        
    if field == "visible":
        if not org.approved:
            return { "status": "fail", "msg": "An organization must be approved before it can be published." }
        value = (value == "true")
        if not validate_only and value != org.visible:
            org.visible = value
            org.save()
            return { "status": "success", "msg": "Your organization is now visible." if org.visible else "Your organization is now hidden." }
        return { "status": "success" }
    elif field == "issue-add":
        ix = get_object_or_404(IssueArea, id=value)
        if validate_only:
            return { "status": "success" }
        org.issues.add(ix)
        org.save()
        return { "status": "success" }
    elif field == "issue-remove":
        ix = get_object_or_404(IssueArea, id=value)
        if validate_only:
            return { "status": "success" }
        org.issues.remove(ix)
        org.save()
        return { "status": "success" }
    elif field == "admin-add":
        try:
            user = get_object_or_404(User, email=value)
        except:
            return { "status": "fail", "msg": "There is no user with that email address." }
        if validate_only:
            return { "status": "success" }
        if len(user.orgroles.filter(org=org)) > 0: # can't add twice
            return { "status": "fail", "msg": "That user is already listed on staff." }
        role = UserOrgRole()
        role.user = user
        role.org = org
        role.title = "Staff"
        role.save()
        return { "status": "success", "username": user.username, "id": user.id, "fullname": user.userprofile.fullname }
        # TODO: Set the user an email with instructions on adding their title and phone number.
    elif field == "admin-remove":
        if request.user.id == int(value):
            return { "status": "fail", "msg": "You cannot remove yourself as an administrator for this organization." }
        if validate_only:
            return { "status": "success" }
        get_object_or_404(User, id=value).orgroles.filter(org=org).delete()
        return { "status": "success" }
    elif field == "contact-remove":
        c = get_object_or_404(OrgContact, id=value)
        if c.org != org:
            return { "status": "fail" }
        if not validate_only:
            c.delete()
        return { "status": "success" }
    else:
        raise Exception("Bad request: Invalid field: " + field)

@csrf_exempt # problem
@json_response
def org_update_logo(request, orgslug):
    org = get_object_or_404(Org, slug=orgslug)
    if not org.is_admin(request.user) :
        return HttpResponseForbidden("You do not have permission to view this page.")
    
    # Get the image byte data.
    datafile = None
    for k, f in request.FILES.items():
        datafile = f
        break
    else:
        datafile = StringIO(request.raw_post_data)
    
    imgdata = org_update_logo_2(org, datafile)
    
    # In order to ensure the web browser updates the image when the URL
    # doesn't change, append an ignored hash to the url.
    import hashlib
    m = hashlib.md5()
    m.update(imgdata)
    
    return { "success": True, "url": org.logo.url + "?" + m.hexdigest() }
    
def org_update_logo_2(org, imagedata):
    # Load the image and resize it to the right dimensions preserving aspect ratio.
    from PIL import Image
    dims = (220, 166)
    imx = Image.open(imagedata)
    if imx.mode != "RGB":
        imx = imx.convert("RGB") # convert out of pallette image
    topleftcolor = imx.getpixel((0,0))
    (w, h) = imx.size
    if w > h*dims[0]/dims[1]:
        dims2 = (dims[0], int(float(dims[0])*h/w))
    else:
        dims2 = (int(float(dims[1])*w/h), dims[1])
    imx = imx.resize(dims2, Image.BICUBIC)

    # Because we don't know the color of the padding, create a new
    # image with the right background color and then paste in the
    # uploaded+resized image at the center.
    im = Image.new(imx.mode, dims, topleftcolor) # fill w/ top-left color
    im.paste(imx, (im.size[0]/2 - imx.size[0]/2, im.size[1]/2 - imx.size[1]/2))

    # Get out the binary jpeg data.
    buf = StringIO()
    im.save(buf, "JPEG")
    
    try:
        org.logo.delete()
    except:
        pass
    
    buf.size = len(buf.getvalue())
    buf.name = "unnamed"
    buf.seek(0)
        
    from django.core.files import File
    org.logo.save(str(org.id) + ".jpeg", File(buf))
    
    return buf.getvalue()

@csrf_protect
@json_response
def org_add_staff_contact(request):
    org = get_object_or_404(Org, slug=request.POST["org"])
    if not org.is_admin(request.user) :
        return HttpResponseForbidden("You do not have permission to view this page.")
    
    name = request.POST["name"].strip()
    title = request.POST["title"].strip()
    email = request.POST["email"].strip()
    phone = request.POST["phone"].strip()
    
    if name == "" or title == "" or email == "" or phone == "":
        return { "status": "fail", "msg": "All fields are required." }
    
    if request.POST["id"] != "":
        contact = OrgContact.objects.get(id=int(request.POST["id"]), org=org)
    else:
        contact = OrgContact()
    contact.org = org
    contact.name = name
    contact.title = title
    contact.email = email
    contact.phonenumber = phone
    try:
        contact.save()
    except Exception, e:
        return { "status": "fail", "msg": unicode(e) }
    
    return { "status": "success", "id": contact.id }

def create_new_campaign(org):
    # Find a slug.
    slug = None
    for i in range(1, 1000):
        cams = OrgCampaign.objects.filter(org=org, slug="campaign" + str(i))
        if len(cams) == 0:
            slug = "campaign" + str(i)
            break
    if slug == None:
        raise Exception("Cant autogenerate a slug.")
    
    ncampaigns = len(OrgCampaign.objects.filter(org=org, default=False)) + 1
    
    # Make it.
    cam = OrgCampaign()
    cam.org = org
    cam.slug = slug
    cam.name = "Campaign " + str(ncampaigns)
    cam.website = None
    cam.description = ""
    cam.message = ""
    cam.visible = False
    cam.save()
    return cam

@csrf_protect
@login_required
@json_response
def org_support_oppose(request):
    if request.POST == None or not "org" in request.POST or not "bill" in request.POST or not "position" in request.POST or request.POST["position"] not in ("+", "-", "0"):
        raise Exception("Bad request: Missing/invalid field.")
    
    org = get_object_or_404(Org, slug=request.POST["org"])
    if not org.is_admin(request.user) :
        return HttpResponseForbidden("Not authorized.")

    newcam = False
    if "cam" in request.POST and request.POST["cam"] == "_default_":
        # Create the _default_ campaign if it doesn't exist.
        try:
            cam = OrgCampaign.objects.get(org__slug=request.POST["org"], slug=request.POST["cam"])
        except:
            cam = create_new_campaign(org)
            cam.default = True
            cam.slug = "_default_"
            cam.visible = True
            cam.save()
    elif "cam" in request.POST and request.POST["cam"] != "_new_":
        # Adding bill to existing campaign. Error if campaign doesn't exist.
        cam = get_object_or_404(OrgCampaign, org__slug=request.POST["org"], slug=request.POST["cam"])
    else:
        # Create a new campaign.
        cam = create_new_campaign(org)
        newcam = True
    
    # Get a bill object.
    bill = bill_from_url(request.POST["bill"])
    
    # Add the position to the campaign. Don't delete an existing position
    # because it will delete any associated org custom action page info.
    try:
        p = cam.positions.get(bill = bill)
    except:
        p = OrgCampaignPosition()
        p.campaign = cam
        p.bill = bill

    p.position = request.POST["position"]
    if request.POST["comment"].strip() != "":
        p.comment = request.POST["comment"].strip()    
    p.save()

    if p.position == "+":
        support = "Endorse"
    elif p.position == "-":
        support = "Oppose"
    elif p.position == "0":
        support = "Neutral"

    if cam.slug == "_default_":
        message = "%s (%s) has been added to %s's legislative agenda. (%s)" % (p.bill.shortname, support, org.name, p.bill.title)
    elif not newcam:
        message = "%s (%s) has been added to the %s campaign. (%s)" % (p.bill.shortname, support, cam.name, p.bill.title)
    else:
        message = "A new campaign named %s was created and %s (%s) was added to its legislative agenda. (%s)" % (cam.name, p.bill.shortname, support, p.bill.title)

    # Send an email to all of the org's administrators.
    send_mail("POPVOX: Legislative Agenda Changed: " + org.name,
"""This is an automated email to confirm the following change to the
legislative agenda of %s. The following action was taken:

   %s

For more information please see your organization profile:
%s

Thanks for participating!

POPVOX
""" % (org.name, message, SITE_ROOT_URL + org.url() + "/_edit"),
        EMAILVERIFICATION_FROMADDR, [admin.user.email for admin in org.admins.all()], fail_silently=True)
    
    # Add a session message to be displayed on the next page.
    messages.success(request, message)

    return { "status": "success", "camurl": cam.url() }
        
@csrf_protect
@login_required
def org_newcampaign(request, orgslug):
    org = get_object_or_404(Org, slug=orgslug)
    if not org.is_admin(request.user) :
        return HttpResponseForbidden("Not authorized.")
    cam = create_new_campaign(org)
    return HttpResponseRedirect(cam.url() + "/_edit")

@csrf_protect_if_logged_in
def orgcampaign(request, orgslug, campaignslug):
    cam = get_object_or_404(OrgCampaign, org__slug=orgslug, slug=campaignslug)
    if not cam.org.is_admin(request.user):
        if not cam.org.visible or not cam.visible:
            raise Http404()
            
    set_last_campaign_viewed(request, cam)
    
    return render_to_response('popvox/campaign.html', {'cam': cam, 'admin': cam.org.is_admin(request.user),         "show_share_footer": True }, context_instance=RequestContext(request))

@csrf_protect
@login_required
def orgcampaign_edit(request, orgslug, camslug):
    cam = get_object_or_404(OrgCampaign, org__slug=orgslug, slug=camslug)
    if not cam.org.is_admin(request.user):
        return HttpResponseForbidden("You do not have permission to view this page.")
    set_last_campaign_viewed(request, cam)
    return render_to_response('popvox/campaign_edit.html', {'cam': cam}, context_instance=RequestContext(request))

@csrf_protect
@ajaxmultifieldupdate(["org", "cam"])
def orgcampaign_updatefields(request, field, value, validate_only):
    cam = get_object_or_404(OrgCampaign, org__slug=request.POST["org"], slug=request.POST["cam"])
    if not cam.org.is_admin(request.user) :
        return HttpResponseForbidden("Not authorized.")
    
    if field == "name":
        value = forms.CharField(min_length=5, error_messages = {'min_length': "That's too short."}).clean(value) # raises ValidationException
        if not validate_only:
            cam.name = value
            cam.save()
        return { "status": "success", "value": value }
    elif field == "website":
        if value != "" and not value[0:7] == "http://":
            value = "http://" + value
        value = forms.URLField(required=False, verify_exists = True).clean(value) # raises ValidationException
        if not validate_only:
            cam.website = value
            cam.save()
        return { "status": "success", "value": value }
    elif field == "description":
        if not validate_only:
            cam.description = sanitize_html(value)
            cam.save()
        return { "status": "success" }
    elif field == "message":
        try:
            value = sanitize_html(value)
        except:
            return { "status": "fail", "msg": "It looks like you have entered forbidden HTML into the text." }
        if not validate_only:
            cam.message = value
            cam.save()
        return { "status": "success" }
    elif field == "slug":
        value = forms.SlugField().clean(value) # raises ValidationException
        if len(OrgCampaign.objects.filter(org=cam.org, slug=value)) > 0:
            return { "status": "fail", "msg": "That slug is in use by another one of your campaigns." }
        if value != value.lower():
            return { "status": "fail", "msg": "Slugs must be all lowercase." }
        if not validate_only:
            cam.slug = value
            cam.save()
        return { "status": "success", "value": value, "newslug": value }
    else:
        raise Exception("Bad request: Invalid field.")

@csrf_protect
@json_response
@ajax_fieldupdate_request
def orgcampaign_updatefield(request, field, value, validate_only):
    cam = get_object_or_404(OrgCampaign, org__slug=request.POST["org"], slug=request.POST["cam"])
    if not cam.org.is_admin(request.user) :
        return HttpResponseForbidden("Not authorized.")

    if field == "visible":
        if not validate_only:
            cam.visible = (value == "true")
            cam.save()
        return { "status": "success" }
    elif field == "billposition-remove":
        if not validate_only:
            OrgCampaignPosition.objects.get(campaign=cam, id = value).delete()
            if cam.default and len(cam.positions.all()) == 0:
                cam.delete()
            else:
                cam.save()
        return { "status": "success" }
    elif field.startswith("billposition-comment-"):
        id = int(field[len("billposition-comment-"):])
        p = OrgCampaignPosition.objects.get(campaign=cam, id=id)
        if not validate_only:
            p.comment = value
            p.save()
        if value == "":
            html = "<em>No comment.</em>"
        else:
            html = "\n".join(["<p>" + cgi.escape(line) + "</p>" for line in value.split("\n")])
        return { "status": "success", "html":html}
    elif field == "action" and value == "delete-campaign":
        cam.delete()
        return { "status": "success" }
    elif field == "position_order":
        index = 0
        for pid in value.split(","):
            p = OrgCampaignPosition.objects.get(campaign=cam, id=pid)
            p.order = index
            p.save()
            index += 1
        return { "status": "success" }

def set_last_campaign_viewed(request, cam):
    # If we're passed an org, take its default camaign if it
    # has one. Otherwise clear the session state.
    if type(cam) == Org:
        try:
            cam = cam.campaigns.get(default = True)
        except:
            cam = None

    # Clear session state.
    if cam == None:
        try:
            del request.session["popvox_lastviewedcampaign"]
        except:
            pass
        return
    
    # Otherwise, set it.
    request.session["popvox_lastviewedcampaign"] = cam.id

def action_defs(billpos):
    if billpos.action_headline == None or billpos.action_headline.strip() == "":
        billpos.action_headline = "Edit This Headline - Click Here"
    if billpos.action_body == None or strip_tags(billpos.action_body).strip() == "":
        billpos.action_body = "<p><strong>Take Action</strong></p><p>Edit message &mdash; click here to edit the text.</p> <p>Use this space to tell your members why they should take action.</p>"

@csrf_protect
def action(request, orgslug, billposid):
    org = get_object_or_404(Org, slug=orgslug)
    admin = org.is_admin(request.user)
    
    if not admin and not org.visible:
        raise Http404()
    
    billpos = get_object_or_404(OrgCampaignPosition, id=billposid, campaign__org = org)

    set_last_campaign_viewed(request, billpos.campaign)

    action_defs(billpos)
    
    url = None
    num = None
    campaign = None
    if admin:
        import shorturl
        surl, created = shorturl.models.Record.objects.get_or_create(target=billpos)
        url = surl.url()
    
        # If the admin is following his own link, make him not an admin for the
        # moment so he can see how it looks to others.
        if "shorturl" in request.session and request.session["shorturl"] == surl:
            admin = False
            del request.session["shorturl"]
        
        try:
            campaign = billpos.get_service_account_campaign(create=False)
            num = campaign.actionrecords.count()
        except:
            num = 0

    # create a Comment instance to get the appropriate verb to display
    # to the user
    cx = UserComment()
    cx.created = datetime.datetime.now()
    cx.bill = billpos.bill
    cx.position = billpos.position
    
    return render_to_response('popvox/org_action.html', {
        'position': billpos,
        "verb": cx.verb(tense="imp"),
        'admin': admin,
        "shorturl": url,
        "num": num,
        "campaign": campaign,
        }, context_instance=RequestContext(request))

@csrf_protect
@json_response
def orgcampaignpositionactionupdate(request):
    billpos = get_object_or_404(OrgCampaignPosition, id=request.POST["id"])
    if not billpos.campaign.org.is_admin(request.user) :
        return HttpResponseForbidden("Not authorized.")

    if "action_headline" in request.POST:
        billpos.action_headline = request.POST["action_headline"]
    if "action_body" in request.POST:
        billpos.action_body = sanitize_html(request.POST["action_body"])
    billpos.save()
    
    action_defs(billpos)
    
    return {"status": "success", "action_headline": billpos.action_headline, "action_body": billpos.action_body }

class CoalitionRequestAction:
    coalition = None
    org = None
    sender = None
    message = None
    
    def email_from_address(self):
        return self.sender.email
        
    def get_response(self, request, vrec):
        if not self.coalition.coalitionmembers.filter(id=self.org.id).exists():
            messages.success(request, self.org.name + " has been added to the coalition " + self.coalition.name)
            self.coalition.coalitionmembers.add(self.org)
            
            send_mail("POPVOX: Coalition Changed: New Member: " + self.org.name,
"""This is an automated email to let you know that the organization

   %s
   <%s>
   
joined the coalition

   %s
   <%s>

Thank you for using POPVOX!

POPVOX
""" % (self.org.name, SITE_ROOT_URL + self.org.url(), self.coalition.name, SITE_ROOT_URL + self.coalition.url()),
                EMAILVERIFICATION_FROMADDR, [admin.user.email for admin in self.coalition.admins.all()], fail_silently=True)
            
            send_mail("POPVOX: Coalition Membership Changed: You Joined: " + self.coalition.name,
"""This is an automated email to let you know that the organization

   %s
   <%s>
   
joined the coalition

   %s
   <%s>

Thank you for using POPVOX!

POPVOX
""" % (self.org.name, SITE_ROOT_URL + self.org.url(), self.coalition.name, SITE_ROOT_URL + self.coalition.url()),
                EMAILVERIFICATION_FROMADDR, [admin.user.email for admin in self.org.admins.all()], fail_silently=True)
            
        else:
            messages.success(request, self.org.name + " had already been added to the coalition " + self.coalition.name)
        return HttpResponseRedirect(self.coalition.url())
    
class CoalitionInviteAction(CoalitionRequestAction):
    def email_subject(self):
        return "POPVOX: " + self.coalition.name + " invites you to join their coalition"
        
    def email_body(self):
        return """%s has sent your organization an invitation to join their coalition on POPVOX:

----------
From:
%s <%s>
%s

To:
%s

%s

----------

Joining a coalition means your organization will be listed among the coalition's members.
To have your organization accept the invitation, please follow the following link. By clicking on
the link your organization will be added to the coalition.

<URL>

If you do not want to join this coalition, just ignore this email.""" % (self.coalition.name, self.sender.userprofile.fullname, self.sender.email, self.coalition.name, self.org.name, self.message)
    
class CoalitionJoinAction(CoalitionRequestAction):
    def email_subject(self):
        return "POPVOX: " + self.org.name + " wants to join " + self.coalition.name
        
    def email_body(self):
        return """%s has sent a request to join your coalition on POPVOX:

----------
From:
%s <%s>
%s

To:
%s

%s

----------

To accept the request, please follow the following link. By clicking on the link
the request will be approved.

<URL>

To ignore the request, just ignore this email.""" % (self.org.name, self.sender.userprofile.fullname, self.sender.email, self.org.name, self.coalition.name, self.message)

@csrf_protect
@json_response
def coalitionrequest(request, join_or_invite):
    myorg = get_object_or_404(Org, id=request.POST["myorg"])
    theirorg = get_object_or_404(Org, id=request.POST["theirorg"])
    if not myorg.is_admin(request.user):
        return { "status": "fail", "msg": "You do not have permission to take this action." }
    
    axn = None
    toaddr = [admin.user.email for admin in theirorg.admins.all()]
    
    if join_or_invite == "join":
        if not theirorg.iscoalition or not theirorg.admins.exists():
            return { "status": "fail", "msg": "Organization cannot be joined." }
        if theirorg.coalitionmembers.filter(id=myorg.id).exists():
            return { "status": "fail", "msg": "Organization is already a member of the coalition." }
            
        axn = CoalitionJoinAction()
        axn.coalition = theirorg
        axn.org = myorg
            
    if join_or_invite == "invite":
        if not myorg.iscoalition or not theirorg.admins.exists():
            return { "status": "fail", "msg": "Organization cannot be invited." }
        if myorg.coalitionmembers.filter(id=theirorg.id).exists():
            return { "status": "fail", "msg": "Organization is already a member of the coalition." }
    
        axn = CoalitionInviteAction()
        axn.coalition = myorg
        axn.org = theirorg
    
    if join_or_invite == "delete":
        myorg.coalitionmembers.remove(theirorg)
    
    if join_or_invite == "leave":
        theirorg.coalitionmembers.remove(myorg)
        
    if axn != None:
        axn.sender = request.user
        axn.message = request.POST["message"]
        for email in toaddr:
            send_email_verification(email, None, axn)
    
    return { "status": "success" }

