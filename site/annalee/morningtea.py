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

#How much disk space do we have free?
diskspace = subprocess.check_output(['df', '-h'])
disks = diskspace.split("\n")
disks = disks[:-1] #remove empty list at the end of this list
fulldisks = []
gooddisks = []
for disk in disks[1:]: #skip the title line
  diskinfo = disk.split()
  name = diskinfo[0]
  devdisk = re.search(r'/dev', name)
  if devdisk:
    fullspace = diskinfo[4]
    fullspacenum = int(fullspace[:-1])
    if fullspacenum >= 70:
      fulldisks.append([name, fullspace])
    else:
      gooddisks.append([name, fullspace])
#sort by percent full:
if fulldisks:
  fulldisks.sort(key=lambda disk: disk[1], reverse=True)
  fdwarn = "The following disks are getting full:\n"
  for disk in fulldisks:
    fdiskmessage = disk[0]+" is "+disk[1]+" percent full.\n"
    fdwarn += fdiskmessage
  urgent.append(fdwarn)

if gooddisks:
  gooddisks.sort(key=lambda disk: disk[1], reverse=True)
  gdinfo = "Here's how much disk space we're using:\n"
  for disk in gooddisks:
    gdiskmessage = disk[0]+" is "+disk[1]+" percent full.\n"
    gdinfo += gdiskmessage
  other.append(gdinfo)
  


#Are we still running the latest version of jquery?
current = urllib.urlopen('media/js/jquery.js')
current = current.read()

recent = urllib.urlopen('http://ajax.googleapis.com/ajax/libs/jquery/1/jquery.min.js')
recent = recent.read()

if recent == current:
  other.append("jquery is up-to-date.")
else:
  urgent.append("There appears to be a new version of jquery.")

#Reporting all the answers:
if urgent == []:
  print "Good Morning, Angels."
  print
  print "There are no urgent updates at this time."
else:
  print "Trouble this morning, Angels." # when Thunderbird alerts new mail I see the first few words so having the first few words indicate the presence of an urgent notice is helpful
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
