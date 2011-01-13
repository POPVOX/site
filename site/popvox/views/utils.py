from datetime import datetime, timedelta

def formatDateTime(d, withtime=True):
	if (datetime.now().date() == d.date()):
		if withtime:
			return d.strftime("Today at %I:%M %p").replace(" 0", " ")
		else:
			return "Today"
	elif ((datetime.now() - timedelta(.5)).date() == d.date()):
		if withtime:
			return d.strftime("Yesterday at %I:%M %p").replace(" 0", " ")
		else:
			return "Yesterday"
	elif (datetime.now() - d).days < 7:
		if withtime:
			return d.strftime("%A at %I:%M %p").replace(" 0", " ")
		else:
			return d.strftime("%A")
	elif (datetime.now() - d).days < 120:
		return d.strftime("%B %d").replace(" 0", " ")
	else:
		return d.strftime("%b %d, %Y").replace(" 0", " ")
		

