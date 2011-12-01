#!runscript

import apt
from popvox.govtrack import CURRENT_CONGRESS
from popvox.models import *
import re
import subprocess
from UpdateManager.Core.MyCache import MyCache
from UpdateManager.Core.UpdateList import UpdateList
import urllib

urgent = []
other = []

#status of printed messages:
printed = UserCommentOfflineDeliveryRecord.objects.filter(batch__isnull=False).count()

printmessage = "There are "+str(printed)+" printed messages awaiting delivery."
if printed > 0:
  urgent.append(printmessage)
else:
  other.append(printmessage)


#current pending messages:
pending = len([c for c in UserComment.objects.filter(bill__congressnumber=CURRENT_CONGRESS, message__isnull=False).exclude(delivery_attempts__id__isnull=False).exclude(usercommentofflinedeliveryrecord__batch__isnull=False) if type(c.get_recipients()) == list])

pendmessage = "There are "+str(pending)+" digital messages awaiting delivery."
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
    scrapercheck = "The Thomas Bill Scraper appears to be working. "+lastlink+" lists "+latestbill+" as the latest bill, which is "+billurl+" on POPVOX."
    broken = False
  else:
    scrapercheck = "There may be something wrong with the Thomas Bill Scraper. "+lastlink+" lists "+latestbill+" as the latest bill, but "+billurl+" doesn't exist."
    broken = True
  return [scrapercheck, broken]

scraperchecked = scrapercheck()
scraper = scraperchecked[0]

if scraperchecked[1]: #checks if broken is true
  urgent.append(scraper)
else:
  other.append(scraper)
  

#How many updates are available for Ubuntu?
ubuntupdates = subprocess.check_output(['/usr/lib/update-notifier/apt-check', '--human-readable'])

secpattern = re.compile(r'\d+(?= updates)')
security = re.search(secpattern, ubuntupdates)

if security:
  security = security.group()
  secmessage = "There are "+str(security)+" security updates for ubuntu."
  if int(security) > 0:
    urgent.append(secmessage)
else:
  urgent.append("something's wrong with the ubuntu update checker.")

print "Good Morning, Josh."
if urgent == []:
  print "There are no urgent updates at this time."
else:
  print "The following updates are urgent:"
  for x in urgent:
    print x

print "The following updates are not urgent:"
for x in other:
  print x
print "Ubuntu updates:"
print ubuntupdates