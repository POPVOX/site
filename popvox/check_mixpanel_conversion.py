#!runscript

import numpy, scipy.stats, collections

import settings
from mixpanel import Mixpanel

funnel_name = "Commenting (w/ Preview)"
date_cutoff = "2011-08-25"
days_back = 16

api = Mixpanel(api_key=settings.MIXPANEL_API_KEY, api_secret=settings.MIXPANEL_API_SECRET)

ret = api.request(["funnels"], {
	"funnel": [funnel_name],
	"unit": "day", 
	"interval": days_back,
	})

goals = collections.OrderedDict()

for date, dateinfo in ret[funnel_name]["data"].items():
	if date == date_cutoff: continue
	print dateinfo
	for step in dateinfo["steps"]:
		x = step["goal"]
		y = step["step_conv_ratio"] # or, overall_conv_ratio
		if not x in goals:
			goals[x] = { "conversion_ratios": [[], []], "totals": [[0,0],[0,0]] }
		z = 0 if date < date_cutoff else 1
		goals[x]["conversion_ratios"][z].append(y)
		goals[x]["totals"][z][0] += int(y*step["count"])
		goals[x]["totals"][z][1] += int((1.0-y)*step["count"])

for goal, arrays in goals.items():
	a, b = arrays["conversion_ratios"]
	print "%s:\t before %5.3f (N=%d) | after %5.3f (N=%d) | p.value %5.3f" \
		% (goal, numpy.mean(a), len(a), numpy.mean(b), len(b), scipy.stats.ttest_ind(a, b)[1])

	print arrays["totals"]
