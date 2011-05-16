#! /usr/bin/python

# TODO:
# Assertions to check more page outputs (done)
# Randomize the bill. (done)
# Clean up code. (done)

import mechanize
import time
import re
import random

server_hostname = "10.252.243.223"

class Transaction(object):
    def __init__(self):
        self.custom_timers = {}
    
    def run(self):
        # create a Browser instance
        br = mechanize.Browser()
        # don't bother with robots.txt
        br.set_handle_robots(False)
        # add a custom header
        br.addheaders = [('User-agent', 'Mozilla/5.0 Compatible')]

        

        #-----FRONT PAGE-----#
        
        # open the front page, time it, verify response
        start_timer = time.time()
        clicky = br.open('https://%s/' % server_hostname)
        clicky.read()
        latency = time.time() - start_timer
        
        self.custom_timers['01. Front Page'] = latency
        
        assert (clicky.code == 200), 'Bad HTTP Response on front page'
        assert ("Your Message in the Language of Congress" in clicky.get_data()), 'Front Page Text Assertion Failed'
        


        #-----BILLS PAGE-----#
        
        # Click through to the Bills page, time it, verify response
        start_timer = time.time()
        clicky = br.open('https://%s/bills' % server_hostname)
        clicky.read()
        latency = time.time() - start_timer
        
        self.custom_timers['02. Bills Page'] = latency
        
        assert (clicky.code == 200), 'Bad HTTP Response on bills page'
        assert ("With POPVOX, you can voice your concerns on specific bills in a format that is tailored for Congress" in clicky.get_data()), 'Bills Page Text Assertion Failed'

        #choose a bill
        billpage = br.find_link(text_regex=re.compile("Act$"), nr=random.randint(0,7))
        


        #-----BILL PAGE-----#
        
        # click on bill, time it, verify response
        start_timer = time.time()
        clicky = br.follow_link(billpage)
        clicky.read()
        latency = time.time() - start_timer
        
        self.custom_timers['03. Bill Page'] = latency
        
        assert (clicky.code == 200), 'Bad HTTP Response on bill page'
        assert ('your position on' in clicky.get_data()), 'Bill page Text Assertion Failed'

        

        #-----WEIGH IN-----#
        
        #choose support or oppose
        position = random.randint(0,1)

        #Click on  Support or oppose, time it, verify response
        start_timer = time.time()
        if position == 0:
            billpage = billpage.url+"/comment/support"
            clicky = br.open(billpage)
        else:
            billpage = billpage.url+"/comment/oppose"
            clicky = br.open(billpage)
        clicky.read()
        latency = time.time() - start_timer
        
        self.custom_timers['04. Comment Start'] = latency

        assert (clicky.code == 200), 'Bad HTTP Response on Comment Start'
        assert ('Tell Congress Why You' in clicky.get_data()), 'Comment start Text Assertion Failed'



        #-----COMMENT-----#

        #choose whether or not to leave a comment
        comment = random.randint(0,3)

        #Leave a comment
        if comment == 1:
            br.select_form("yescomment")
            br.form["message"] = """The Babylon Project was our last, best hope for peace.
            
            A self-contained world five miles long, located in neutral territory. A place of commerce and diplomacy for a quarter of a million humans and aliens. A shining beacon in space--all alone in the night. 
            
            It was the dawn of the Third Age of Mankind. The year the Great War came upon us all.
            
            This is the story of the last of the Babylon stations. The year is 2259. The name of the place is Babylon 5. """
        
            # submit comment, time it
            start_timer = time.time()
            clicky = br.submit()
            clicky.read()
            latency = time.time() - start_timer
        
            self.custom_timers['05. Comment Preview (Msg)'] = latency

            
        #Go on without leaving a comment    
        else:
            br.select_form("nocomment")

            # submit, time it
            start_timer = time.time()
            clicky = br.submit()
            latency = time.time() - start_timer
            
            self.custom_timers['05. Comment Preview (No Msg)'] = latency

        #verify response
        assert (clicky.code == 200), 'Bad HTTP Response on Comment preview'
        assert ('not done until you register or sign in' in clicky.get_data()), 'comment preview Text Assertion Failed'


        #-----REGISTER-----#
        
        br.select_form("commentform")
        br.form.set_all_readonly(False)
        br.form["submitmode"] = "Create Account >"
        ca = "createacct_"
        
        #usernme
        username = ""
        for i in range(8):
            username += random.choice('abcdefghijklmnopqrstuvwxyz')
        br.form[ca+"username"] = username
        
        #email
        email = ""
        for i in range(5):
            email += random.choice('abcdefghijklmnopqrstuvwxyz')
        email += "@popvox.com"
        br.form[ca+"email"] = email
        
        #password
        password = ""
        for i in range(10):
            password += random.choice('abcdefghijklmnopqrstuvwxyz')
        br.form[ca+"password"] = password
        
        # submit registration, time it, verify
        start_timer = time.time()
        clicky = br.submit()
        clicky.read()
        latency = time.time() - start_timer
        
        self.custom_timers['06. Create Account (generates email)'] = latency


        #Get Account code link
        popcode = br.response().read()
        popurl = re.compile('http://www.popvox.com')
        testcode = popurl.sub('https://' + server_hostname, popcode)


        
        #-----CONFIRM REGISTRATION-----#
        
        start_timer = time.time()
        clicky = br.open(testcode)
        clicky.read()
        latency = time.time() - start_timer
        
        self.custom_timers['07. Follow Email Link'] = latency

        #verify response
        assert (clicky.code == 200), 'Bad HTTP Response on Email Link'
        assert ('Tell Congress Who You Are' in clicky.get_data()), 'email link Text Assertion Failed'


        
        ##-----SET ADDRESS-----#
        
        br.select_form("commentform")
        ua = "useraddress_"
        
        #prefix
        br.form[ua+"prefix"] = ["Dr."]
        
        #first name
        firstname = ""
        for i in range(5):
            firstname += random.choice('abcdefghijklmnopqrstuvwxyz')
        br.form[ua+"firstname"] = firstname
        
        #last name
        lastname = ""
        for i in range(8):
            lastname += random.choice('abcdefghijklmnopqrstuvwxyz')
        br.form[ua+"lastname"] = lastname
        
        #suffix
        br.form[ua+"suffix"] = ["III"]
        
        #address1
        address1 = ""
        for i in range(8):
            address1 += random.choice('abcdefghijklmnopqrstuvwxyz')
        address1 += " Street"
        br.form[ua+"address1"] = address1
        
        #address2
        address2 = "Apt. "
        address2 += str(random.randint(1,2000))
        br.form[ua+"address2"] = address2
        
        #city
        city = ""
        for i in range(8):
            city += random.choice('abcdefghijklmnopqrstuvwxyz')
        br.form[ua+"city"] = city
        
        #set state
        br.form[ua+"state"] = ["CA"]
        
        #zipcode
        zipcode = random.randint(10000,99999)
        br.form[ua+"zipcode"] = str(zipcode)
        
        #phone number
        br.form[ua+"phonenumber"] = "202-456-2121"
        
        # submit, time, verify
        start_timer = time.time()
        clicky = br.submit()
        clicky.read()
        latency = time.time() - start_timer
    
        self.custom_timers['08. Submit Address'] = latency

        #verify
        assert (clicky.code == 200), 'Bad HTTP Response on Submit Address'
        assert ('What Others Think' in clicky.get_data()), 'Submit Address Text Assertion Failed'

        

        #-----RETURN TO FRONTPAGE-----#
        
        # click, time, verify
        start_timer = time.time()
        clicky = br.open('https://%s/' % server_hostname)
        clicky.read()
        latency = time.time() - start_timer
        
        self.custom_timers['09. Return to Front Page'] = latency

        #verify
        assert (clicky.code == 200), 'Bad HTTP Response on Front Page 2'
        assert ("Your Message in the Language of Congress" in clicky.get_data()), 'Front Page 2 Text Assertion Failed'
