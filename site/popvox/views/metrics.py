from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import connection, transaction
from django.db.models import Count
from django.contrib.auth.models import User
from django.conf import settings
from django.core.urlresolvers import reverse

from popvox.models import UserComment, Org, OrgContact, UserLegStaffRole

from math import log, exp
from datetime import datetime, timedelta
import calendar
import csv
from scipy import stats
from collections import OrderedDict
import urllib

@user_passes_test(lambda u : u.is_authenticated() and (u.is_staff | u.is_superuser))
def metrics_by_period(request):
	
	def get_stats(field, fields, table, period="day", growth=False):
		c = connection.cursor()
		fixdate = lambda x : x
		if period == "day":
			group = ("date(%s)" % (field,))
		elif period == "week":
			group = ("yearweek(%s)" % (field,)) # year plus sunday and zero-based week number
			def fixdate(x): # normalize each date row to the first day of the week
				return x - timedelta(days=(x.weekday() + 1) % 7) # weekday() returns 0 for Monday, but we actually want to subtract 1 day to get back to sunday
		elif period == "month":
			group = ("year(%s), month(%s)" % (field, field))
			def fixdate(x): # normalize each date row to the first day of the month
				return x.replace(day=1)
		c.execute("select date(%s), %s from %s group by %s" % (field, fields, table, group))
		
		rows = [{"date": fixdate(r[0]), "count": r[1] } for r in c.fetchall()]
		
		if growth:
			# add cumulative counts
			for i in xrange(len(rows)):
				rows[i]["cumulative"] = rows[i]["count"] + (0 if i==0 else rows[i-1]["cumulative"])
			
			# compute percent changes from row to row
			for i in xrange(1, len(rows)):
				rows[i]["percent_change"] = round(100.0 * rows[i]["count"] / rows[i-1]["cumulative"], 1)
		
		return rows
	
	def merge_by_day(inf):
		# take separate rows of results and merge them into one list.
		ret = {}
		for key, val in inf.items():
			for row in val:
				if row["date"] < datetime(2010, 11, 1).date(): continue
				if not row["date"] in ret: ret[row["date"]] = {} # date
				ret[row["date"]][key] = row
				del row["date"]
		ret = ret.items()
		ret.sort(key = lambda x : x[0])
		
		# for the sake of drawing graphs, we need to fill in the cumulative value for
		# each day, since the record will be missing if there were no items on that
		# day.
		last_rec = {}
		for date, stats in ret: # for the same of graphs, fill in values
			for k in inf:
				if not k in stats and k in last_rec:
					stats[k] = { "count": 0, "cumulative": last_rec[k]["cumulative"] }
				elif k in stats:
					last_rec[k] = stats[k]
		
		ret.reverse()
		
		return ret
		
	general_stats = OrderedDict()
	for period, dateformat in (("month", "Y-m"), ("week", "Y-m-d"), ("day", "Y-m-d")):
		new_users = get_stats("date_joined", "count(*)", "auth_user", period=period, growth=True)
		new_positions = get_stats("created", "count(*)", "popvox_usercomment", period=period, growth=True)
		new_comments = get_stats("created", "count(*)", "popvox_usercomment where message is not null", period=period, growth=True)
		new_widget_users = get_stats("date_joined", "count(*)", "auth_user where exists(select * from popvox_usercomment where auth_user.id=user_id and method=%d) and not exists(select * from popvox_usercomment where auth_user.id=user_id and method<>%d)" % (UserComment.METHOD_WIDGET, UserComment.METHOD_WIDGET), period=period, growth=True)
		new_widget_positions = get_stats("created", "count(*)", "popvox_usercomment where method=%d" % UserComment.METHOD_WIDGET, period=period, growth=True)
		general_stats[period] = merge_by_day({
				"new_users": new_users,
				"new_positions": new_positions,
				"new_comments": new_comments,
				"new_widget_users": new_widget_users,
				"new_widget_positions": new_widget_positions,
			})
		for c in general_stats[period]:
			c[1]["dateformat"] = dateformat
	
	# # update user profiles to flag whether a user is a widget-only user or not
	# c = connection.cursor()
	# c.execute("update popvox_userprofile set is_widget_user = true;")
	# c.execute("update popvox_userprofile set is_widget_user = false where exists (select * from popvox_usercomment where popvox_userprofile.user_id=popvox_usercomment.user_id and method<>%d);" % UserComment.METHOD_WIDGET)
# 
	# cohort_where = "(select is_widget_user from popvox_userprofile where auth_user.id=user_id)=0"
# 
	# cohort_sizes = get_stats("date_joined", "count(*)", "auth_user WHERE " + cohort_where, period="month")
	# cohort_sizes2 = dict(((c["date"], c["count"]) for c in cohort_sizes))
	# 
	# cohort_num_positions = get_stats("date_joined", "count(*)", "auth_user left join popvox_usercomment on auth_user.id=popvox_usercomment.user_id WHERE " + cohort_where + " AND method<>%d" % UserComment.METHOD_WIDGET, period="month")
	# for co in cohort_num_positions: co["count"] = round(float(co["count"]) / float(cohort_sizes2[co["date"]]), 1)
	# 
	# cohort_num_comments = get_stats("date_joined", "count(*)", "auth_user left join popvox_usercomment on auth_user.id=popvox_usercomment.user_id where " + cohort_where + " AND method<>%d AND popvox_usercomment.message is not null" % UserComment.METHOD_WIDGET, period="month")
	# for co in cohort_num_comments: co["count"] = round(float(co["count"]) / float(cohort_sizes2[co["date"]]), 1)
	# 
	# cohort_login_types = {}
	# c.execute("select min(date(date_joined)), provider, count(*) from auth_user left join registration_authrecord on auth_user.id=registration_authrecord.user_id WHERE " + cohort_where + " group by year(date_joined), month(date_joined), provider")
	# for dt, provider, count in c.fetchall():
		# dt = dt.replace(day=1)
		# if not dt in cohort_login_types: cohort_login_types[dt] = { "date": dt }
		# cohort_login_types[dt][provider] = 100*count/cohort_sizes2[dt]
	# c.execute("select min(date(date_joined)), count(*) from auth_user where " + cohort_where + " AND not exists(select * from registration_authrecord where auth_user.id=registration_authrecord.user_id) group by year(date_joined), month(date_joined)")
	# for dt, count in c.fetchall():
		# dt = dt.replace(day=1)
		# if not dt in cohort_login_types: cohort_login_types[dt] = { "date": dt }
		# cohort_login_types[dt]["password"] = 100*count/cohort_sizes2[dt]
	# cohort_login_types = cohort_login_types.values()
# 
	# def median(nums):
		# nums.sort()
		# if len(nums) == 0:
			# return None
		# elif len(nums) == 1:
			# return nums[0]
		# elif len(nums) % 2 == 0:
			# return (float(nums[len(nums)/2]) + float(nums[len(nums)/2+1]))/2.0
		# else:
			# return float(nums[len(nums)/2+1])
			# 
	# def mean(nums):
		# if len(nums) == 0:
			# return None
		# return round(float(sum(nums))/float(len(nums)), 1)
		# 
	# def pctile(nums, num):
		# if len(nums) == 0:
			# return None
		# return 100 * len([n for n in nums if n >= num]) / len(nums)
	# 
	# cohort_retention = []
	# c = connection.cursor()
	# for cohort in cohort_sizes2.keys():
		# c.execute(("select min(created), max(created) from popvox_usercomment left join auth_user on popvox_usercomment.user_id=auth_user.id where year(auth_user.date_joined)=%d and month(auth_user.date_joined)=%d AND " + cohort_where + " group by auth_user.id") % (cohort.year, cohort.month))
		# retention = [(row[1] - row[0]).days for row in c.fetchall()]
		# cohort_retention.append({ "date": cohort, "median": median(retention), "mean": mean(retention), "pctile_1day": pctile(retention, 1), "pctile_7days": pctile(retention, 7), "pctile_30days": pctile(retention, 30) })
	# 
	# by_cohort = merge_by_day({
			# "size": cohort_sizes,
			# "positions_per_user": cohort_num_positions,
			# "comments_per_user": cohort_num_comments,
			# "retention": cohort_retention,
			# "login_types": cohort_login_types,
		# })

	return render_to_response("popvox/metrics.html", {
		"count_users": User.objects.all().count(),
		"count_legstaff": UserLegStaffRole.objects.all().count() - 1, # minus one for our demo acct
		"count_comments": UserComment.objects.all().count(),
		"count_comments_messages": UserComment.objects.filter(message__isnull=False).count(),
		"count_orgs_selfreg": Org.objects.filter(createdbyus=False).count(),
		"count_orgs_all": Org.objects.filter(visible=True).count(),
		
		"general_stats": general_stats,
		#"by_cohort": by_cohort,
		}, context_instance=RequestContext(request))


@user_passes_test(lambda u : u.is_authenticated() and (u.is_staff | u.is_superuser))
def metrics_report_spreadsheet(request, sheet):
	if not settings.DEBUG:
		response = HttpResponse(mimetype='text/csv')
		response['Content-Disposition'] = 'attachment; filename=' + sheet + "_" + datetime.now().strftime("%Y-%m-%d_%H%M").strip() + '.csv'
	else:
		response = HttpResponse(mimetype='text/plain')
	
	writer = csv.writer(response)
	
	extra_fields = { }
	notes = None
	
	if sheet == "orgs":
		header = ['id', 'slug', 'name', 'website']
		qs = Org.objects.all()
		
	elif sheet == "orgcontacts":
		header = ['id', 'org__slug', 'org__name', 'org__website', 'name', 'email', 'org__issues', 'registered']
		qs = OrgContact.objects.all().order_by('org__slug', 'name')
		extra_fields = {
			"registered": lambda obj : "yes" if User.objects.filter(email=obj.email).exists() else "no"
		}
		
	elif sheet == "topbills":
		from popvox.models import Bill, UserComment
		header = ['id', 'count', 'title', '#pro', '#con']
		filters = {}
		if "state" in request.GET:
			filters["state"] = request.GET["state"]
			if "district" in request.GET:
				filters["congressionaldistrict"] = request.GET["district"]
		if "days" in request.GET:
			filters["created__gt"] = datetime.now() - timedelta(days=float(request.GET["days"]))
		if filters:
			notes = ", ".join([ k+"="+str(v) for k,v in filters.items() ])
		qs = Bill.objects.all()\
			.filter(**dict( ("usercomments__"+k,v) for k,v in filters.items() ))\
			.annotate(count=Count('usercomments'))\
			.order_by('-count')\
			[0:50]
		extra_fields = {
			"#pro": lambda bill : UserComment.objects.filter(bill=bill, position="+", **filters).count(),
			"#con": lambda bill : UserComment.objects.filter(bill=bill, position="-", **filters).count(),
			}

	elif sheet == "powerusers":
		header = ['id', 'email', 'positions_count', 'firstname', 'lastname', 'unsubscribe_link']
		qs = User.objects.all().annotate(positions_count=Count("comments")).order_by('-positions_count')
		ct = 10000
		st = int(request.GET.get("page", "1")) - 1
		qs = qs[0+st*ct:st*ct+ct].iterator()

		from settings import SITE_ROOT_URL
		from home import unsubscribe_me_makehash, unsubscribe_me
		unsub_base_url = SITE_ROOT_URL + reverse(unsubscribe_me) + "?"
		def make_user_unsubscribe_link(obj):
			# create a link that the user can visit to one-click unsubscribe himself,
			# just take care to hash something so that people can't guess the URL
			# to unsubscribe someone else.
			return unsub_base_url + urllib.urlencode({"email": obj.email, "key": unsubscribe_me_makehash(obj.email)})
		extra_fields = {
			"firstname": lambda obj : obj.postaladdress_set.order_by('-created')[0].firstname,
			"lastname": lambda obj : obj.postaladdress_set.order_by('-created')[0].lastname,
			"unsubscribe_link": make_user_unsubscribe_link
		}
		
	elif sheet == "supercommittee":
		header = ["title"]
		nweeks = 4
		for i in range(nweeks):
			header.extend([str(i) + "_support", str(i) + "_oppose", str(i) + "_total", str(i) + "_sup_pct", str(i) + "_opp_pct"])
		header.extend(["total" + "_support", "total" + "_oppose", "total" + "_total", "total" + "_sup_pct", "total" + "_opp_pct"])
		qs = []
		from features import supercommittee_bill_list
		for b in supercommittee_bill_list:
			bill = b["bill"]
			bill.title = b["title"]
			
			for i in range(nweeks):
				d1 = datetime(2011, 10, 24) + timedelta(days=7*i)
				d2 = d1 + timedelta(days=7)
				q = bill.usercomments.filter(created__gte=d1, created__lt=d2)
				c_a = q.filter(position="+").count()
				c_b = q.filter(position="-").count()
				c_c = c_a + c_b
				setattr(bill, str(i) + "_support", c_a)
				setattr(bill, str(i) + "_oppose", c_b)
				setattr(bill, str(i) + "_total", c_c)
				setattr(bill, str(i) + "_sup_pct", round(100.0 * float(c_a) / float(c_c)) if c_c > 0 else "")
				setattr(bill, str(i) + "_opp_pct", round(100.0 * float(c_b) / float(c_c)) if c_c > 0 else "")
			q = bill.usercomments.filter(created__gte=datetime(2011, 10, 24))
			c_a = q.filter(position="+").count()
			c_b = q.filter(position="-").count()
			c_c = c_a + c_b
			setattr(bill, "total" + "_support", c_a)
			setattr(bill, "total" + "_oppose", c_b)
			setattr(bill, "total" + "_total", c_c)
			setattr(bill, "total" + "_sup_pct", round(100.0 * float(c_a) / float(c_c)) if c_c > 0 else "")
			setattr(bill, "total" + "_opp_pct", round(100.0 * float(c_b) / float(c_c)) if c_c > 0 else "")
			qs.append(bill)

	elif sheet == "bill":
		from popvox.models import Bill
		from popvox.govtrack import getMembersOfCongressForDistrict
		header = ["state", "district", "member", "percent_support", "percent_oppose", "number_support", "number_oppose", "total_positions"]
		bill = Bill.from_hashtag("#" + request.GET.get("bill", ""))
		notes = bill.title
		report = { }
		for rec in bill.usercomments.values("state", "congressionaldistrict", "position").annotate(count=Count("id")):
			for sd in ((rec["state"], None), (rec["state"], rec["congressionaldistrict"])):
				if not sd in report: report[sd] = { "state": sd[0], "district": sd[1], "+": 0, "-": 0 }
				report[sd][rec["position"]] += rec["count"]
		qs = sorted(report.values(), key = lambda v : (v["state"], v["district"]))
		for rec in qs:
			if rec["district"] == None:
				rec["district"] = "-"
				rec["member"] = ", ".join([m["name"] for m in getMembersOfCongressForDistrict(rec["state"], moctype="sen")])
			else:
				rec["member"] = ", ".join([m["name"] for m in getMembersOfCongressForDistrict(rec["state"] + str(rec["district"]), moctype="rep")])
			rec["number_support"] = rec["+"]
			rec["number_oppose"] = rec["-"]
			rec["total_positions"] = rec["+"] + rec["-"]
			if rec["total_positions"] > 0:
				rec["percent_support"] = int(round(100.0 * rec["number_support"] / rec["total_positions"]))
				rec["percent_oppose"] = int(round(100.0 * rec["number_oppose"] / rec["total_positions"]))
		
	else:
		raise Http404()
	
	def getfield(obj, f):
		if isinstance(obj, dict):
			return obj.get(f, "")
		
		ret = obj
		for ff in f.split("__"):
			ret = getattr(ret, ff, "")
		
		if str(type(ret)) == "<class 'django.db.models.fields.related.ManyRelatedManager'>":
			ret = ", ".join(unicode(r) for r in ret.all())
			
		return ret
	
	if notes:
		writer.writerow([notes.encode("utf8")])
	
	writer.writerow(header)
	for obj in qs:
		for k, v in extra_fields.items():
			setattr(obj, k, v(obj))
			
		writer.writerow([unicode(getfield(obj, h)).encode("utf8") for h in header])
	
	return response
	
