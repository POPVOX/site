#!runscript

import csv
import popvox.models
import re

f = csv.writer(open('annalee/phonecomments.csv', 'wb'), delimiter='\t',
quotechar='|', lineterminator='XYZXYZ', quoting=csv.QUOTE_ALL)
comments = popvox.models.UserComment.objects.all()
phone = re.compile(r'\d{3}\W?\d{4}')
n = 0

for comment in comments:
  message = comment.message
  if message == None:
    continue
  else:
    p = phone.search(message)
    if p:
      number = p.group()
      user = str(comment.user)
      
      print number
      
      f.writerow( (user.encode("utf8"), number.encode("utf8"), message.encode("utf8")) )
      n += 1
    else:
        continue
print n