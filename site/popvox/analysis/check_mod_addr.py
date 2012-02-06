#!runscript

from django.contrib.auth.models import User
from popvox.views.bills import user_may_change_address

D = { }

for u in User.objects.all():
	try:
		a = u.postaladdress_set.order_by("-created")[0]
		ret = user_may_change_address(None, a, u)
		if not ret in D: D[ret] = 0
		D[ret] += 1
	except IndexError:
		continue
		
D = sorted(D.items(), key = lambda x : -x[1])
for d in D:
	print d
	
