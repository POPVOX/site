#!runscript
import re
import urllib

termsearch = re.compile(r'(?P<ip>\d+([.]\d+){3}) - - (?P<date>\[\d{2}/\w{3}/\d{4})(:\d\d){3} \+\d{4}\] "GET /bills/search\?q=(?P<term>\S+)')


termlist = {} #dict of search terms to see how many times each one is used

with open('searches.tsv', 'w') as log:
  with open('/home/www/logs/access.log', 'r') as l:
    for line in l:
      search = re.search(termsearch, line)
      if search:
	  ip   = search.group('ip')
	  date = search.group('date')
	  term = search.group('term')
	  #cleaning up the search terms:
	  term = re.sub('&congressnumber=\d*', '', term)
	  term = urllib.unquote_plus(term) #replaces %xx and + with English
	  log.write(date+'\t'+ip+'\t'+term+'\n')
	  #adding each term and counting how many times searched:
	  term = str.lower(term)
	  term = str.strip(term)
	  if termlist.has_key(term):
	    termlist[term] += 1
	  else:
	    termlist[term] = 1
      else:
	continue

with open('searchterms.tsv', 'w') as st:
  for x in termlist:
    if termlist[x] > 1:
      #checking if the search term produced results, to add that to the csv
      searchpage = urllib.urlopen('https://www.popvox.com/bills/search?q='+urllib.quote_plus(x))
      searchpage = searchpage.read()
      if 'no bills matched' in searchpage:
	result = 'no'
      else:
	result = 'yes'
      #and writing it in:
      st.write(str(x)+'\t'+str(termlist[x])+'\t'+result+'\n')


  
