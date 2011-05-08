#! /usr/bin/python
import mechanize
import time
import re
import random


class Transaction(object):
    def __init__(self):
        self.custom_timers = {}
    
    def run(self):
        # create a Browser instance
        br = mechanize.Browser()
        # don't bother with robots.txt
        br.set_handle_robots(False)
        # add a custom header so that sites allow the request
        br.addheaders = [('User-agent', 'Mozilla/5.0 Compatible')]
        
        # start the timer
        start_timer = time.time()
        # open the front page
        resp = br.open('https://ec2-50-17-164-57.compute-1.amazonaws.com/')
        resp.read()
        # stop the timer
        latency = time.time() - start_timer
        
        # store the custom timer
        self.custom_timers['Load_Front_Page2'] = latency
        
        # verify responses are valid
        assert (resp.code == 200), 'Bad HTTP Response'
        assert ("Your Message in the Language of Congress" in resp.get_data()), 'Front Page Text Assertion Failed'

        # think-time
        #time.sleep(1)
        
        # start the timer
        start_timer = time.time()
        # click on bills page
        clicky = br.open('https://ec2-50-17-164-57.compute-1.amazonaws.com/bills')
        clicky.read()
        #stop the timer
        latency = time.time() - start_timer

        # store the custom timer
        self.custom_timers['Load_Bills_Page'] = latency
        
        assert (clicky.code == 200), 'Bad HTTP Response'
        assert ("With POPVOX, you can voice your concerns on specific bills in a format that is tailored for Congress" in clicky.get_data()), 'Bills Page Text Assertion Failed'
        
        # think-time
        #time.sleep(2)
        
        #choose a bill
        billpage = br.find_link(text_regex=re.compile("Act$"), nr=random.randint(0,7))
        # start the timer
        start_timer = time.time()
        #click on bill
        clicky = br.follow_link(billpage)
        clicky.read()
        #stop the timer
        latency = time.time() - start_timer
        
        # store the custom timer
        self.custom_timers['Load_Bill_Page'] = latency
        
        assert (clicky.code == 200), 'Bad HTTP Response'
        assert ('your position on' in clicky.get_data()), 'Text Assertion Failed'
        
        # think-time
        #time.sleep(2)
        
        #choose support or oppose
        position = random.randint(0,1)
        # start the timer
        start_timer = time.time()
        #click on bill
        if position == 0:
            clicky = br.open('https://ec2-50-17-164-57.compute-1.amazonaws.com/bills/us/112/hr1380/comment/support')
        else:
            clicky = br.open('https://ec2-50-17-164-57.compute-1.amazonaws.com/bills/us/112/hr1380/comment/oppose')
        clicky.read()
        #stop the timer
        latency = time.time() - start_timer
        
        # store the custom timer
        self.custom_timers['Load_Comment_Page'] = latency
        
        #choose whether or not to leave a comment
        comment = random.randint(0,3)
        #select the appropriate radio button
        #br.click("writemessage"+str(comment))

        #Leave a comment
        if comment == 1:
            br.select_form("yescomment")
            br.form["message"] = """The Babylon Project was our last, best hope for peace.
            
            A self-contained world five miles long, located in neutral territory. A place of commerce and diplomacy for a quarter of a million humans and aliens. A shining beacon in space--all alone in the night. 
            
            It was the dawn of the Third Age of Mankind. The year the Great War came upon us all.
            
            This is the story of the last of the Babylon stations. The year is 2259. The name of the place is Babylon 5. """
            
            # think-time
            #time.sleep(2)
        
            # start the timer
            start_timer = time.time()
            clicky = br.submit()
            clicky.read()
            #stop the timer
            latency = time.time() - start_timer
        
            # store the custom timer
            self.custom_timers['Leave_Comment'] = latency
            
        #Go on without leaving a comment    
        else:
            br.select_form("nocomment")
            # start the timer
            start_timer = time.time()
            clicky = br.submit()
            #clicky.read()
            #stop the timer
            latency = time.time() - start_timer
        
            # store the custom timer
            self.custom_timers['Leave_No_Comment'] = latency
            
        # think-time
        time.sleep(2)
        
        #Register
        br.select_form("commentform")
        br.form.set_all_readonly(False)
        br.form["submitmode"] = "Create Account >"
        ca = "createacct_"
        
        #generate usernme
        username = ""
        for i in range(8):
            username += random.choice('abcdefghijklmnopqrstuvwxyz')
        #set username
        br.form[ca+"username"] = username
        
        #generate email
        email = ""
        for i in range(5):
            email += random.choice('abcdefghijklmnopqrstuvwxyz')
        email += "@popvox.com"
        #set email
        br.form[ca+"email"] = email
        
        #generate password
        password = ""
        for i in range(10):
            password += random.choice('abcdefghijklmnopqrstuvwxyz')
        #set password
        br.form[ca+"password"] = password
        
        # think-time
        time.sleep(2)
        
        # start the timer
        start_timer = time.time()
        #submit form
        clicky = br.submit()
        clicky.read()
        # stop the timer
        latency = time.time() - start_timer
        
        # store the custom timer
        self.custom_timers['Create_Account'] = latency

        #Get Account code link
        popcode = br.response().read()
        #br.find_link(text_regex=re.compile("^http://www.popvox.com/emailverif/code/"), nr=0)
        #replace popvox link with test site link
        popurl = re.compile('http://www.popvox.com')
        testcode = popurl.sub('https://ec2-50-17-164-57.compute-1.amazonaws.com', popcode)
        
        # think-time
        #time.sleep(2)
        
        # start the timer
        start_timer = time.time()
        #open testcode url
        clicky = br.open(testcode)
        clicky.read()
        # stop the timer
        latency = time.time() - start_timer
        
        # store the custom timer
        self.custom_timers['Account_Gencode'] = latency
        
        #Fill out the address form
        br.select_form("commentform")
        ua = "useraddress_"
        
        #set prefix
        br.form[ua+"prefix"] = ["Dr."]
        
        #generate first name
        firstname = ""
        for i in range(5):
            firstname += random.choice('abcdefghijklmnopqrstuvwxyz')
        #set firstname
        br.form[ua+"firstname"] = firstname
        
        #generate last name
        lastname = ""
        for i in range(8):
            lastname += random.choice('abcdefghijklmnopqrstuvwxyz')
        #set lastname
        br.form[ua+"lastname"] = lastname
        
        #set suffix
        br.form[ua+"suffix"] = ["III"]
        
        #generate address1
        address1 = ""
        for i in range(8):
            address1 += random.choice('abcdefghijklmnopqrstuvwxyz')
        address1 += " Street"
        #set address1
        br.form[ua+"address1"] = address1
        
        #generate address2
        address2 = "Apt. "
        address2 += str(random.randint(1,2000))
        #set address2
        br.form[ua+"address2"] = address2
        
        #generate city
        city = ""
        for i in range(8):
            city += random.choice('abcdefghijklmnopqrstuvwxyz')
        #set city
        br.form[ua+"city"] = city
        
        #set state
        br.form[ua+"state"] = ["CA"]
        
        #set zipcode
        zipcode = random.randint(10000,99999)
        br.form[ua+"zipcode"] = str(zipcode)
        
        #set phone number
        br.form[ua+"phonenumber"] = "202-456-2121"
        
        # think-time
        #time.sleep(2)
        
        # start the timer
        start_timer = time.time()
        #submit form
        clicky = br.submit()
        clicky.read()
        # stop the timer
        latency = time.time() - start_timer
        
        # store the custom timer
        self.custom_timers['Load_Finish'] = latency
        
        # think-time
        #time.sleep(1)
        
        # start the timer
        start_timer = time.time()
        # open the front page
        resp = br.open('https://ec2-50-17-164-57.compute-1.amazonaws.com/')
        resp.read()
        # stop the timer
        latency = time.time() - start_timer
        
        # store the custom timer
        self.custom_timers['Load_Front_Page3'] = latency

        print "done"