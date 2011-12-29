#!runscript

from django.db import connection
from popvox.govtrack import CURRENT_CONGRESS, getMemberOfCongress, getMembersOfCongressForDistrict
from popvox.models import UserComment, PostalAddress
from writeyourrep.models import Endpoint
import csv
import re
from xml.dom.minidom import parse, parseString
import os

rolls = os.listdir('/mnt/persistent/data/govtrack/us/112/rolls/')

totalvotes= {}
missedvotes = {} #"0"
members = []
percent_missed = {}
percent_attended = {}

for roll in rolls:
  #pulling the roll:
  rollxml = "/mnt/persistent/data/govtrack/us/112/rolls/"+roll

  #parsing the voters for that roll"
  voteinfo = open(rollxml)
  voteinfo = voteinfo.read()
  dom2 = parseString(voteinfo)
  voters = dom2.getElementsByTagName("voter")
  
  for voter in voters:
    voterid = voter.getAttribute("id")
    vote = voter.getAttribute("vote")

    if voterid != '0':
      if voterid not in members:
        members.append(voterid)

      if voterid not in missedvotes:
        missedvotes[voterid] = 0
      if vote == "0":
        missedvotes[voterid] +=1

      if voterid not in totalvotes:
        totalvotes[voterid] = 0
      totalvotes[voterid] += 1
        

percentages = []
for member in members:
  percent_missed[member] = 100.00*missedvotes[member]/totalvotes[member]
  percentages.append(percent_missed[member])

percentages.sort()

percentile_missed = {}

with open('/tmp/attendance.csv', 'wb') as f:
    for member in members:
      rank = percentages.index(percent_missed[member])
      percentile_missed[member] = 100*rank/float(len(percentages))
      
      writer = csv.writer(f)
      writer.writerow([member, percent_missed[member], percentile_missed[member]])



