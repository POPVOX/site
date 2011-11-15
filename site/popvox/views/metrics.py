from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import connection, transaction
from django.db.models import Count
from django.contrib.auth.models import User
from django.conf import settings

from popvox.models import UserComment, Org, OrgContact, UserLegStaffRole

from math import log, exp
from datetime import datetime, timedelta
import csv
from scipy import stats

@user_passes_test(lambda u : u.is_authenticated() and (u.is_staff | u.is_superuser))
def metrics_by_period(request):
	
	def get_stats(field, fields, table, period="day", growth=False):
		c = connection.cursor()
		fixdate = lambda x : x
		if period == "day":
			group = ("date(%s)" % (field,))
		elif period == "week":
			group = ("yearweek(%s)" % (field,))
			# select the date of the sunday of the week - each day needs to map to something
			# consistently. double escape the mysql format string first for the interpolation happening
			# on this line, and second for the interpolation that happens in the Django db layer.
			#
			# this causes problems when DEBUG=True.
			field = "STR_TO_DATE(CONCAT(YEARWEEK(%s),'0'),CONCAT('%%','X%%','V%%','w'))" % (field,) # between the Python string interpolation and the Django db layer %s parameters, percents just get confused
		elif period == "month":
			def fixdate(x):
				return x.replace(day=1)
			group = ("year(%s), month(%s)" % (field, field))
		c.execute("select date(%s), %s from %s group by %s" % (field, fields, table, group))
		
		rows = [{"date": fixdate(r[0]), "count": r[1] } for r in c.fetchall()]
		
		if growth:
			# add cumulative counts
			for i in xrange(len(rows)):
				rows[i]["cumulative"] = rows[i]["count"] + (0 if i==0 else rows[i-1]["cumulative"])
			
			# compute growth rates with a backward-looking sliding window
			window = {"day": 21, "week": 6, "month": 3 }[period]
			for i in xrange(window, len(rows)):
				x = [(row["date"]-rows[0]["date"]).days for row in rows[i-window+1 : i+1]]
				y = [log(row["cumulative"]) for row in rows[i-window+1 : i+1]]
				gradient, intercept, r_value, p_value, std_err = stats.linregress(x,y)
				rows[i]["growth_daily"] = int(10000*(exp(gradient) - 1.0))/100.0 # percent growth by day
				rows[i]["growth_weekly"] = int(100*(pow(exp(gradient), 7) - 1.0)) # percent growth by week
				rows[i]["growth_monthly"] = int(100*(pow(exp(gradient), 30.5) - 1.0)) # percent growth by month
				days_to_double = log(2.0) / gradient
				if days_to_double < 30:
					rows[i]["double_life"] = ("%d days" % days_to_double)
				elif days_to_double < 30.5 * 24:
					rows[i]["double_life"] = ("%.1f mo." % round(days_to_double/30.5, 1))
				else:
					rows[i]["double_life"] = ("%.1f yr." % round(days_to_double/365.25, 1))
		
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
		
	general_stats = {}
	for period in ("day", "week", "month"):
		new_users = get_stats("date_joined", "count(*)", "auth_user", period=period, growth=True)
		new_positions = get_stats("created", "count(*)", "popvox_usercomment", period=period, growth=True)
		new_comments = get_stats("created", "count(*)", "popvox_usercomment where message is not null", period=period, growth=True)
		new_positions_with_referrer = get_stats("created", "count(*)", "popvox_usercomment where exists(select * from popvox_usercommentreferral where popvox_usercomment.id=comment_id)", period=period, growth=True)
		general_stats[period] = merge_by_day({
				"new_users": new_users,
				"new_positions": new_positions,
				"new_comments": new_comments,
				"new_positions_with_referrer": new_positions_with_referrer,
			})
		

	cohort_sizes = get_stats("date_joined", "count(*)", "auth_user", period="month")
	cohort_sizes2 = dict(((c["date"], c["count"]) for c in cohort_sizes))
	
	cohort_num_positions = get_stats("date_joined", "count(*)", "auth_user left join popvox_usercomment on auth_user.id=popvox_usercomment.user_id", period="month")
	for c in cohort_num_positions: c["count"] = round(float(c["count"]) / float(cohort_sizes2[c["date"]]), 1)
	
	cohort_num_comments = get_stats("date_joined", "count(*)", "auth_user left join popvox_usercomment on auth_user.id=popvox_usercomment.user_id where popvox_usercomment.message is not null", period="month")
	for c in cohort_num_comments: c["count"] = round(float(c["count"]) / float(cohort_sizes2[c["date"]]), 1)
	
	cohort_login_types = {}
	c = connection.cursor()
	c.execute("select min(date(date_joined)), provider, count(*) from auth_user left join registration_authrecord on auth_user.id=registration_authrecord.user_id group by year(date_joined), month(date_joined), provider")
	for dt, provider, count in c.fetchall():
		dt = dt.replace(day=1)
		if not dt in cohort_login_types: cohort_login_types[dt] = { "date": dt }
		cohort_login_types[dt][provider] = 100*count/cohort_sizes2[dt]
	c.execute("select min(date(date_joined)), count(*) from auth_user where not exists(select * from registration_authrecord where auth_user.id=registration_authrecord.user_id) group by year(date_joined), month(date_joined)")
	for dt, count in c.fetchall():
		dt = dt.replace(day=1)
		if not dt in cohort_login_types: cohort_login_types[dt] = { "date": dt }
		cohort_login_types[dt]["password"] = 100*count/cohort_sizes2[dt]
	cohort_login_types = cohort_login_types.values()

	def median(nums):
		nums.sort()
		if len(nums) == 0:
			return None
		elif len(nums) == 1:
			return nums[0]
		elif len(nums) % 2 == 0:
			return (float(nums[len(nums)/2]) + float(nums[len(nums)/2+1]))/2.0
		else:
			return float(nums[len(nums)/2+1])
			
	def mean(nums):
		if len(nums) == 0:
			return None
		return round(float(sum(nums))/float(len(nums)), 1)
		
	def pctile(nums, num):
		if len(nums) == 0:
			return None
		return 100 * len([n for n in nums if n >= num]) / len(nums)
	
	cohort_retention = []
	c = connection.cursor()
	for cohort in cohort_sizes2.keys():
		c.execute("select min(created), max(created) from popvox_usercomment left join auth_user on popvox_usercomment.user_id=auth_user.id where year(auth_user.date_joined)=%d and month(auth_user.date_joined) = %d group by auth_user.id" % (cohort.year, cohort.month))
		retention = [(row[1] - row[0]).days for row in c.fetchall()]
		cohort_retention.append({ "date": cohort, "median": median(retention), "mean": mean(retention), "pctile_1day": pctile(retention, 1), "pctile_7days": pctile(retention, 7), "pctile_30days": pctile(retention, 30) })
	
	by_cohort = merge_by_day({
			"size": cohort_sizes,
			"positions_per_user": cohort_num_positions,
			"comments_per_user": cohort_num_comments,
			"retention": cohort_retention,
			"login_types": cohort_login_types,
		})

	return render_to_response("popvox/metrics.html", {
		"count_users": User.objects.all().count(),
		"count_legstaff": UserLegStaffRole.objects.all().count() - 1, # minus one for our demo acct
		"count_comments": UserComment.objects.all().count(),
		"count_comments_messages": UserComment.objects.filter(message__isnull=False).count(),
		"count_orgs_selfreg": Org.objects.filter(createdbyus=False).count(),
		"count_orgs_all": Org.objects.filter(visible=True).count(),
		
		"general_stats": general_stats,
		"by_cohort": by_cohort,
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
	
	if sheet == "orgs":
		header = ['id', 'slug', 'name', 'website']
		qs = Org.objects.all()
		
	elif sheet == "orgcontacts":
		header = ['id', 'org__slug', 'org__name', 'org__website', 'name', 'email', 'org__issues', 'registered']
		qs = OrgContact.objects.all().order_by('org__slug', 'name')
		extra_fields = {
			"registered": lambda obj : "yes" if User.objects.filter(email=obj.email).exists() else "no"
		}

	elif sheet == "powerusers":
		header = ['id', 'email', 'positions_count', 'firstname', 'lastname']
		qs = User.objects.all().annotate(positions_count=Count("comments")).order_by('-positions_count')
		qs = qs[0:2000]
		extra_fields = {
			"firstname": lambda obj : obj.postaladdress_set.order_by('-created')[0].firstname,
			"lastname": lambda obj : obj.postaladdress_set.order_by('-created')[0].lastname
		}
		
	elif sheet == "supercommittee":
		header = ["title"]
		nweeks = 3
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

	else:
		raise Http404()
	
	def getfield(obj, f):
		ret = obj
		for ff in f.split("__"):
			ret = getattr(ret, ff, "")
		
		if str(type(ret)) == "<class 'django.db.models.fields.related.ManyRelatedManager'>":
			ret = ", ".join(unicode(r) for r in ret.all())
			
		return ret
	
	writer.writerow(header)
	for obj in qs:
		for k, v in extra_fields.items():
			setattr(obj, k, v(obj))
			
		writer.writerow([unicode(getfield(obj, h)).encode("utf8") for h in header])
	
	return response
	
