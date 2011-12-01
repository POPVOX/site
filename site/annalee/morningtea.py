#!runscript

import apt
from popvox.govtrack import CURRENT_CONGRESS
from popvox.models import *
import re
import subprocess
import urllib

urgent = []
other = []

#status of printed messages:
printed = UserCommentOfflineDeliveryRecord.objects.filter(batch__isnull=False).count()

printmessage = "Printed Messages: " + str(printed)
if printed > 0:
  urgent.append(printmessage)
else:
  other.append(printmessage)


#current pending messages:
pending = len([c for c in UserComment.objects.filter(bill__congressnumber=CURRENT_CONGRESS, message__isnull=False).exclude(delivery_attempts__id__isnull=False).exclude(usercommentofflinedeliveryrecord__batch__isnull=False) if type(c.get_recipients()) == list])

pendmessage = "Undelivered Comments: " + str(pending)
if pending > 500:
  urgent.append(pendmessage)
else:
  other.append(pendmessage)


#are the Thomas scrapers running?
def scrapercheck():
  congress = str(CURRENT_CONGRESS)
  index = urllib.urlopen('http://thomas.loc.gov/home/Browse.php?n=bills&c='+congress)
  index = index.read()
  linkre = r'/cgi-bin/query/L\?c'+congress+':./list/c'+congress+'[hs].lst:\d+'
  indexlink = re.compile(linkre)

  linklist = re.findall(indexlink, index)
  lastlink = linklist[len(linklist) -1]
  lastlink = 'http://thomas.loc.gov'+lastlink

  latestbills = urllib.urlopen(lastlink)
  latestbills = latestbills.read()
  billre = re.compile(r'H\.R\.\d+|S\.\d+')

  billslist = re.findall(billre, latestbills)
  latestbill = billslist[len(billslist) -1]
  latestbill = re.sub(r'\.', '', latestbill)
  latestbill = str.lower(latestbill)

  billurl="https://www.popvox.com/bills/us/"+congress+"/"+latestbill
  billpage = urllib.urlopen(billurl)
  bpcode = billpage.getcode()

  if bpcode == 200:
    scrapercheck = "OK [" + latestbill + " => " + billurl + "]"
    broken = False
  else:
    scrapercheck = "Problem? " + lastlink + " lists " + latestbill + " as the latest bill, but " + billurl + " doesn't exist."
    broken = True
  return ["THOMAS Scraper: " + scrapercheck, broken]

scraperchecked = scrapercheck()
scraper = scraperchecked[0]

if scraperchecked[1]: #checks if broken is true
  urgent.append(scraper)
else:
  other.append(scraper)
  

#How many updates are available for Ubuntu?
ubuntupdates = subprocess.check_output(['/usr/lib/update-notifier/apt-check', '--human-readable'])
security = re.search(r'\d+(?= updates)', ubuntupdates)
packages = re.search(r'\d+(?= packages)', ubuntupdates)
if security and packages:
  ubuntupdates = ("%s packages, %s are security" % (security.group(), packages.group()))
  if int(security.group()) > 0:
    urgent.append("Software Packages: " + security.group() + " security updates.")
else:
  urgent.append("Software Packages: Something's wrong with the checker.")

if urgent == []:
  print "Good Morning, Josh."
  print
  print "There are no urgent updates at this time."
else:
  print "Rainy morning, Josh." # when Thunderbird alerts new mail I see the first few words so having the first few words indiate the presence of an urgent notice is helpful
  print
  print "URGENT"
  print
  for x in urgent:
    print x
print
print "STATUS"
print
for x in other:
  print x
print "Software Packages: " + ubuntupdates
