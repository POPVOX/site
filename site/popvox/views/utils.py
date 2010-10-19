from datetime import datetime, timedelta

def formatDateTime(d):
	if (datetime.now().date() == d.date()):
		return d.strftime("Today at %I:%M %p")
	elif ((datetime.now() - timedelta(.5)).date() == d.date()):
		return d.strftime("Yesterday at %I:%M %p")
	elif (datetime.now() - d).days < 7:
		return d.strftime("%A at %I:%M %p")
	elif (datetime.now() - d).days < 120:
		return d.strftime("%B %d")
	else:
		return d.strftime("%b %d, %Y")
		

