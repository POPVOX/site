#!runscript
from popvox.models import Bill, Roll
from popvox import govtrack

import re

bills = Bill.objects.all()

for bill in bills:
    try:
        dom1 = govtrack.getBillMetadata(bill)
    except:
        # not sure why the file might be missing or invalid, but just in case
        continue

    #checking to see if there's been a roll call vote on the bill
    #a bill can be voted on multiple times in the same chamber
    #(e.g. ping pong or conference reports). For these purposes, we're taking all rolls
    allvotes = dom1.getElementsByTagName("vote")
    had_vote = False
    for vote in allvotes:
        if vote.getAttribute("how") != "roll":
            continue

        had_vote = True
        
        #pulling the roll:
        roll = vote.getAttribute("roll")
        where = vote.getAttribute("where")
        date =  vote.getAttribute("datetime")
        yearre = re.compile(r'^\d{4}')
        year = re.match(yearre, date).group(0)
        rollxml = where+year+"-"+roll
        newroll = Roll()
        newroll.number = rollxml
        print rollxml
        newroll.bill = bill
        newroll.save()
        
    
    