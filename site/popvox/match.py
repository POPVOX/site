from django.contrib.auth.models import User

import re
from xml.dom import minidom
from itertools import chain, izip, cycle

from popvox.models import *
from popvox.views.bills import bill_statistics, get_default_statistics_context
from popvox.views.bills import get_popular_bills, get_popular_bills2
import popvox.govtrack

from settings import SITE_ROOT_URL

import csv
import urllib
from xml.dom.minidom import parse, parseString


_congress_match_attendance_data = None

def membermatch(memberids, user):
    
    def get_attendance_data():
        attendance_data = { }
        with open('/mnt/persistent/data/analysis/attendance.csv', 'rb') as f: # TODO: we should move this file
            reader = csv.reader(f)
            for row in reader:
                row = list(row)
                id = int(row[0])       # member ID
                row[1] = float(row[1]) # percent missed votes
                row[2] = float(row[2]) # percentile
                if row[1] < 10: # format the percent missed votes
                    row[1] = "%.1f" % row[1]
                else:
                    row[1] = str(int(row[1]))
                if row[2] < 40:
                    row[2] = "better than %.0f%% of Members of Congress" % (100.0-row[2])
                elif row[2] > 60:
                    row[2] = "worse than %.0f%% of Members of Congress" % row[2]
                else:
                    row[2] = "that's about average"
                attendance_data[id] = (row[1], row[2])
            return attendance_data
    
    def attendancecheck(memberid):
        global _congress_match_attendance_data
        if _congress_match_attendance_data == None:
            _congress_match_attendance_data = get_attendance_data()
        return _congress_match_attendance_data.get(memberid, None)
        
    #grab the user's bills and positions:
    usercomments = UserComment.objects.filter(user=user)
    
    billvotes = []

    for comment in usercomments:
        #turning bill ids into bill numbers:
        if not comment.bill.is_bill(): continue
        
        #grabbing bill info
        try:
            dom1 = popvox.govtrack.getBillMetadata(comment.bill)
        except:
            # not sure why the file might be missing or invalid, but just in case
            continue
        
        #checking to see if there's been a roll call vote on the bill
        #since a bill can be voted on more than once (usually once
        #per chamber!), loop through the votes and aggregate everyone's
        #votes into a single dict.
        #a bill can be voted on multiple times in the same chamber
        #(e.g. ping pong or conference reports), and we'll take the
        #last vote encountered in the file, which is the most recent.
        allvotes = dom1.getElementsByTagName("vote")
        allvoters = { }
        had_vote = False
        for vote in allvotes:
            if vote.getAttribute("how") != "roll": continue
            
            had_vote = True
            
            #pulling the roll:
            roll = vote.getAttribute("roll")
            where = vote.getAttribute("where")
            date =  vote.getAttribute("datetime")
            yearre = re.compile(r'^\d{4}')
            year = re.match(yearre, date).group(0)
            votexml = "/mnt/persistent/data/govtrack/us/" + str(comment.bill.congressnumber) + "/rolls/"+where+year+"-"+roll+".xml"
            
            #parsing the voters for that roll"
            try:
                voteinfo = open(votexml)
                voteinfo = voteinfo.read()
                dom2 = parseString(voteinfo)
            except:
                # not sure why the file might be missing or invalid, but just in case
                continue
            voters = dom2.getElementsByTagName("voter")
            for voter in voters:
                voterid = int(voter.getAttribute("id"))
                votervote = voter.getAttribute("vote")
                allvoters[voterid] = (votervote, where+year+"-"+roll)
            
        #if there was no vote on this bill, output something a little different
        #(note that this is different from a vote but none of the user's reps
        #actually cast a vote)
        voters_votes = []
        if len(memberids) > 1:
            if not had_vote:
                billvotes.append( (comment, None) )
                continue
                
            #creating an array of the votes. if a Member wasn't in any
            #roll call, mark with NR for no roll. For each Member, record
            # a tuple of how the Member voted ("+" etc.) and a string giving
            # a reference to the vote (already put inside allvoters).
            for member in memberids:
                voters_votes.append( allvoters.get(member, ("NR", None)) )
            billvotes.append( (comment, voters_votes) )
            
        else:
            voters_votes.append( allvoters.get(memberids[0], ("NR", None)) )
            if had_vote and memberids[0] in allvoters:
                billvotes.append( (comment, voters_votes) )
            
                
        
    # put all comments that have had votes first and votes cast first,
    # then comments with votes but no reps were elligible to vote,
    # and then comments without votes, each group sorted by comment
    # creation date reverse chronologically.
    billvotes.sort(key = lambda x : (
        x[1] != None, #There's something in vote
        x[1] != None and len([y for y in x[1] if y[0] =="NR"]) != len(x[1]), #There's a vote or cosponsor
        x[1] != None and len([y for y in x[1] if y[0] in ("CS", "NR")]) != len(x[1]), #There's a vote
        x[0].created #created date
        ), reverse=True)
        

    
    # get overall stats by member
    stats = []
    had_abstain = False
    for id in memberids: # init each member to zeroes
        stats.append({ "agree": 0, "disagree": 0, "0": 0, "P": 0, "_TOTAL_": 0 })
    for comment, votes in billvotes: # for each vote...
        if not votes: continue # no vote on this bill
        for i, (vote, ref) in enumerate(votes): # and each member...
            if vote in ("+", "-"): # increment the stats
                if vote == comment.position:
                    stats[i]["agree"] += 1
                else:
                    stats[i]["disagree"] += 1
                stats[i]["_TOTAL_"] += 1
            elif vote in ("0", "P"): # also increment the stats
                stats[i][vote] += 1
                stats[i]["_TOTAL_"] += 1
                if vote == "P":
                    had_abstain = True
            elif vote == "NR":
                pass # member did not have opportunity to vote
    for i, memstat in enumerate(stats):
        for key in ('agree', 'disagree', '0', 'P'):
            if memstat["_TOTAL_"] > 0:
                memstat[key+"_percent"] = ("%.0f" % (100.0*memstat[key]/memstat["_TOTAL_"]))
            else:
                memstat[key+"_percent"] = 0
        memstat["attendance"] = attendancecheck(memberids[i])
    
    return billvotes, stats, had_abstain