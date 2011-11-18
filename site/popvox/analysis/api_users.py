#!runscript

import apachelog, re, csv, glob, datetime, urlparse

from popvox.models import ServiceAccount
from django.contrib.sessions.models import Session
from django.contrib.auth.models import User

p = apachelog.parser(r'%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"')

hits = { }
last_session = (None, None)

	# start/end-date logic depends on the access logs being read in chronological order
	# to scan all log files we could use:
	#   reversed(sorted(list(glob.glob('/home/www/logs/access.log*'))))
	# but if we're only interested in hits to the api in the last month, just use the
	# current and previous log file (since the current could have just been rotated
	# and it may not have much data yet)
for fn in ('/home/www/logs/access.log.1', '/home/www/logs/access.log'):
	for line in open(fn):
		lp = p.parse(line)
		
		if lp["%r"] == "-": continue # ?
		try:
			method, path, protocol = lp["%r"].split(" ")
		except ValueError:
			continue
		if not path.startswith("/api"): continue
		
		url = urlparse.urlparse(path)
		args = urlparse.parse_qs(url.query)
		
		if not "api_key" in args: continue
		
		api_key = args["api_key"][0]
		
		date = datetime.datetime.strptime( apachelog.parse_date(lp["%t"])[0], "%Y%m%d%H%M%S" )
	
		if not api_key in hits:
			hits[api_key] = { "api_key": api_key, "count": 0, "start_date": date, "users": { } }

		h = hits[api_key]
		h["count"] += 1
		h["end_date"] = date 
		
		if "session" in args:
			session = args["session"][0]
			
			if last_session[0] == session:
				user = last_session[1]
			else:
				# turn a session into a user here because users may have multiple
				# session ids, so we want to collapse before keying them the same.
				try:
					s = Session.objects.get(pk=session).get_decoded()
					user = User.objects.get(pk=s["_auth_user_id"]).username
				except Session.DoesNotExist:
					user = "<expired-session>"
				except User.DoesNotExist:
					user = "<invalid-user>"
				except KeyError:
					user = "<not-logged-in>"
				last_session = (session, user)
			
			if not user in h["users"]:
				h["users"][user] = { "user": user, "count": 0, "start_date": date }
			hh = h["users"][user]
			hh["count"] += 1
			hh["end_date"] = date
			
hits = list(hits.values())
hits.sort(key = lambda hit : hit["count"], reverse=True)

w = csv.writer(open("api_users.csv", "w"))
w.writerow(["api_key owner", "user", "hits", "start_date", "end_date"])
for hit in hits:
	acct = ("<%s>" % hit["api_key"])
	try:
		acct = (ServiceAccount.objects.filter(api_key=hit["api_key"]) | ServiceAccount.objects.filter(secret_key=hit["api_key"])).get().shortname
	except ServiceAccount.DoesNotExist:
		pass
	
	w.writerow([acct.encode("utf8"), "", hit["count"], hit["start_date"], hit["end_date"]])
	
	hit["users"] = list(hit["users"].values())
	hit["users"].sort(key = lambda v : v["count"], reverse=True)
	for rec in hit["users"]:
		w.writerow(["", rec["user"].encode("utf8"), rec["count"], rec["start_date"], rec["end_date"]])

