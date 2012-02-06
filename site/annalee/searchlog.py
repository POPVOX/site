#!runscript

import re
import urllib
from datetime import datetime, timedelta
from popvox.govtrack import parse_govtrack_date
from popvox.views.bills import billsearch_internal

termsearch = re.compile(r'(?P<ip>\d+([.]\d+){3}) - - (?P<date>\[\d{2}/\w{3}/\d{4})(:\d\d){3} \+\d{4}\] "GET /bills/search\?q=(?P<term>\S+)')


termlist = {} #dict of search terms to see how many times each one is used
cutoff   = datetime.today() - timedelta(days=7)

with open('searches.tsv', 'w') as log:
  with open('/home/www/logs/access.log', 'r') as l:
    for line in l:
      search = re.search(termsearch, line)
      if search:
        date = search.group('date')
        date = datetime.strptime(date, '[%d/%b/%Y')
        if cutoff <= date:
          ip   = search.group('ip')
          term = search.group('term')
          #cleaning up the search terms:
          term = re.sub('&congressnumber=\d*', '', term)
          term = urllib.unquote_plus(term) #replaces %xx and + with English
          log.write(str(date)+'\t'+ip+'\t'+term+'\n')
          #adding each term and counting how many times searched:
          term = str.lower(term)
          term = str.strip(term)
          if termlist.has_key(term):
            termlist[term] += 1
          else:
            termlist[term] = 1
        else:
          continue
      else:
	continue

#creating a list of search terms, how many searches for each term, and whether they produced results:
searchterms = []
for term in termlist:
  if termlist[term] > 2:
    bills, status, error = billsearch_internal(term)
    if len(bills) == 0: # returned nothing
    #checking if the search term produced results, to add that to the csv
    #searchpage = urllib.urlopen('https://www.popvox.com/bills/search?q='+urllib.quote_plus(x))
    #searchpage = searchpage.read()
    #if 'no bills matched' in searchpage:
      result = 'no'
    else:
      result = 'yes'
    #and writing it to a list:
    searchterms.append([term, termlist[term], result])
#sorting the list in descending order of how many times each term was searched:
searchterms.sort(key=lambda term: term[1], reverse=True)

#writing the list to a tsv:
with open('searchterms.tsv', 'w') as st:  
  for term in searchterms:
    st.write(str(term[0])+'\t'+str(term[1])+'\t'+term[2]+'\n')


  
