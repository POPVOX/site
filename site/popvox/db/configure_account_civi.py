#!runscript

from popvox.models import *

sa_id = int(raw_input("Service account id: "))

acct = ServiceAccount.objects.get(id=sa_id)
print unicode(acct).encode("utf8")

existing_info = acct.getopt("civicrm", { })
def my_input(prompt, field):
	if not field in existing_info:
		return raw_input(prompt + ": ").strip()
	else:
		ret = raw_input("%s (%s):" % (prompt, existing_info[field]))
		if ret == "":
			return existing_info[field]
		else:
			return ret.strip()

if raw_input("Is this correct? (y/n): ") == "y":
	print "For the website base URL, there should be no trailing slash. It is everything up to /civicrm. Or enter 'clear' to clear the connection to CiviCRM."
	civi_info = { }
	civi_info["url_root"] = my_input("Website base URL", "url_root")
	if civi_info["url_root"] == "clear":
		acct.setopt("civicrm", None)
		print "CiviCRM credentials cleared from account."
	else:
		civi_info["username"] = my_input("Username", "username")
		civi_info["password"] = my_input("Password", "password")
		acct.setopt("civicrm", civi_info)

		print "Credentials set. Checking..."

		# Check the credientials with dummy information.
		
		cam = ServiceAccountCampaign()
		cam.id = 999
		cam.bill = Bill()
		cam.bill.title = "<test bill>"
		
		rec = ServiceAccountCampaignActionRecord()
		rec.firstname = "Test"
		rec.lastname = "User"
		rec.zipcode = "00000"
		rec.email = "test@popvox.com"
		rec.created = datetime.now()
		rec.updated = datetime.now()
		
		scar_save_civicrm(acct, cam, rec)
		
		print "A test Campaign ('POPVOX Widget...'), Contact ('test@popvox.com'/'Test User'), and Activity was entered into the CiviCRM site."
		
