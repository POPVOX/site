import popvox.objects as pv
import unicodedata
with open("/tmp/userdata.csv",'w') as f:
    for userobj in users:
        datastr = unicodedata.normalize('NFKD',userobj.user.username).encode('ascii','ignore')+", "+ str(userobj.user.email)+", "+str(userobj.user.date_joined)
        comments = pv.UserComment.objects.filter(user=userobj)
        if comments:
            lastcomment = pv.UserComment.objects.filter(user=userobj).latest('created')
            state = lastcomment.state
            dist = lastcomment.congressionaldistrict
            statedist = state+"-"+str(dist)
            datastr += ", "+statedist
            for comment in comments:
                bill = pv.Bill.objects.get(id=comment.bill_id)
                billtype = bill.billtype
                billnumber = bill.billnumber
                billnum = billtype+"-"+str(billnumber)
                commentdate = comment.created
                datastr += ", "+billnum+", "+str(commentdate)
        f.write(datastr+"\n")