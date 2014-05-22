#!runscript
import urllib
import re
from popvox.govtrack import CURRENT_CONGRESS

congress = CURRENT_CONGRESS
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
latestbill

billpage = urllib.urlopen("https://www.popvox.com/bills/search?q="+latestbill)
billpage = billpage.read()

#update this section to compare the status of the bill on Thomas to its status on pv?
checktext = latestbill.split('.')[-1] #pull just the number, not the chamber
if re.search(checktext, billpage):
  scrapercheck = "The Thomas Bill Scraper appears to be working."
else:
  scrapercheck = "There may be something wrong with the Thomas Bill Scraper."

print scrapercheck
  