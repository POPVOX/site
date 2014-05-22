#!runscript

# Measure user engagement as a matrix where the rows are
# cohorts (date_joined) and the columns are time periods, and
# the cells store various percentiles.

import csv
from datetime import datetime, timedelta
from scipy.stats import scoreatpercentile, percentileofscore

from popvox.models import UserComment

def make(store, key, value):
	if not key in store: store[key] = value
	return store[key]

# Count up total user actions by cohort, action time period, and user,
# for comments not made via a widget.
engagement = { }
for c in UserComment.objects.filter(method=UserComment.METHOD_SITE).select_related("user").order_by():
	user = c.user.id
	
	c_st_of_week = c.user.date_joined - timedelta(days=(c.user.date_joined.weekday() + 1) % 7) # bring back to Sunday of that week
	cohort = (c_st_of_week.year, c_st_of_week.month, c_st_of_week.day)
	
	p_st_of_week = c.created - timedelta(days=(c.created.weekday() + 1) % 7) # bring back to Sunday of that week
	period = (p_st_of_week.year, p_st_of_week.month, p_st_of_week.day)
	
	eng_cohort = make(engagement, cohort, { })
	eng_period = make(eng_cohort, period, { })
	make(eng_period, user, 0)
	eng_period[user] += 1

outp = csv.writer(open("engagement_matrix.csv", "w"))
outp.writerow( [ "cohort", "period", "weeks_since_joined", "cohort_size", "total_interactions", "50%", "10%", "5%", "2%", "1%", "%>=1", "%>=2", "%>=3", "%>=4", "%>=5", "%>=10", "%>=20" ] )

# For each cohort-period combination, compute the percentiles of engagement.
for cohort, cohort_periods in sorted(engagement.items()):
	cohort_date = datetime(*cohort)
	
	# Get a set of all users that interacted at any point in the cohort.
	# (If date_joined was always the date of the first interaction, we
	# could check just one period....)
	all_users = set()
	for period_users in cohort_periods.values():
		for user in period_users.keys():
			all_users.add(user)
			
	for period in cohort_periods.keys():
		# Revise the periods to be just lists of engagement counts rather
		# than dicts from user to count.
		cohort_periods[period] = list(cohort_periods[period].values())
			
		# Revise the periods to include zeroes for any missing user. We
		# only need to check the total count of users.
		cohort_periods[period].extend( (0,) * (len(all_users) - len(cohort_periods[period])) )
		
	# Revise the cell to contain statistical information.
	for period, period_counts in sorted(cohort_periods.items()):
		period_date = datetime(*period)
		
		stats = [
			int((period_date-cohort_date).total_seconds()/(60*60*24*7)),
			
			len(period_counts),
			sum(period_counts),
			
			# scoreatpercentile gives the score such that the percent of scores
			# below the returned value is the value given in the argument. our
			# interpretation is flipped, however, so in the output 05p means
			# the count of interactions that 5% of users reached.
			scoreatpercentile(period_counts, 50),
			scoreatpercentile(period_counts, 90),
			scoreatpercentile(period_counts, 95),
			scoreatpercentile(period_counts, 98),
			scoreatpercentile(period_counts, 99),
			
			# percentileofscore(kind=strict) returns percentage of scores
			# with a value less than the argument value. Subtract from 100
			# gives the percent of users who had that many actions or more.
			100.0-percentileofscore(period_counts, 1, kind="strict"),
			100.0-percentileofscore(period_counts, 2, kind="strict"),
			100.0-percentileofscore(period_counts, 3, kind="strict"),
			100.0-percentileofscore(period_counts, 4, kind="strict"),
			100.0-percentileofscore(period_counts, 5, kind="strict"),
			100.0-percentileofscore(period_counts, 10, kind="strict"),
			100.0-percentileofscore(period_counts, 20, kind="strict"),
		]
		
		outp.writerow( [ "%04d-%02d-%02d" % cohort, "%04d-%02d-%02d" % period ] + stats )

