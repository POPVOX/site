from django.test import TestCase
from django.test.client import Client
from django.conf import settings

import json

settings.IS_TESTING = True # don't import this module unless setting this flag is OK
c = Client()

from popvox.models import *

#-------------------Functions----------------#

def login(email, password, login, page, self):

    success = True

    response = c.post('/accounts/login?next=/home', {'email': email, 'password': password},  follow=True)
    status = response.status_code
    pagecontents = response.content
    
    if login == 'good':
        if int(status) != 200:
            success = False
            print "status code failed on login on ", page
        elif "<title>Home - POPVOX.com</title>" not in pagecontents:
            success = False
            print page, "did not redirect to home."
        elif 'Welcome, <a href="/accounts/profile">kosh</a>' not in pagecontents:
            success = False
            print page, "is not showing user as logged in."
            
    else:
        if int(status) != 200:
            success = False
            print "status code failed on login on ", page
        elif "<title>Sign In - POPVOX.com</title>" not in pagecontents:
            success = False
            print page, "did not reload login page."
        elif 'Your email and password were incorrect' not in pagecontents:
            success = False
            print page, "did not inform user of bad login."

    self.assertEqual(success, True)
    return success
        
def comment(congress, bill, position, self):
    
    success = login('kosh@vorlons.gov', '3edgedsword', 'good', 'login', self)
    
    response = c.post('/bills/us/'+congress+'/'+bill+'/comment/'+position, {
            "message":                  "I support "+bill+" because I'm the testing robot.",
            "submitmode":               "Submit Comment >",
            "useraddress_address1":     "711 Ludlow St",
            "useraddress_address2":     "",
            "useraddress_city":         "Takoma Park",
            "useraddress_firstname":    "Ambassador",
            "useraddress_lastname":     "Kosh",
            "useraddress_phonenumber":  "240-688-6685",
            "useraddress_prefix":       "Mr.",
            "useraddress_state":        "MD",
            "useraddress_suffix":       "",
            "useraddress_zipcode":      "20912-7309",
            },  follow=True)
    status = response.status_code
    pagecontents = response.content
    page = "leave comment"
                
    if int(status) != 200:
        success = False
        print "status code failed on ", page
        print status
    elif "<title>Share Your Comment" not in pagecontents:
        success = False
        print page, "did not redirect to share."
    elif "What Others Think" not in pagecontents:
        success = False
        print page, "is not showing what others think."
        
    self.assertEqual(success, True)
    return success
    
#-------------------Site Tests----------------#

class SampleTest(TestCase):
    
    def testTrue(self):
        a = 1
        self.assertEqual(1, a)


class StaticPageTest(TestCase):
    fixtures = ['test_adserver']
    
    def testStatic(self):
        statics = [
            '/congress',
            '/about',
            '/about/team',
            '/about/principles',
            '/about/whyitworks',
            '/about/contact',
            '/legal',
            '/press',
            '/jobs',
            '/advertising',
            '/faq']
	
        success = True
	
        for x in statics:
            response = c.get(x)
            status = response.status_code
            pagecontents = response.content
        
            if int(status) != 200:
                success = False
                print "problem loading ", x
            elif "<html" not in pagecontents:
                success = False
                print "content problem in ", x
            else:
                print x, " is good."
	    
        self.assertEqual(success, True)

class SearchTest(TestCase):
    fixtures = ['test_adserver', 'test_pvgeneral', 'test_sbills', 'test_orgs']

    def testBillSearchFail(self):
        
        response = c.get('/bills/search', {'q': 'winnie the pooh'})
        status = response.status_code
        pagecontents = response.content
        success = True
        page = 'search for Pooh' 

        if int(status) != 200:
            success = False
            print "problem loading ", page
        elif "no bills matched your search" not in pagecontents:
            success = False
            print "term not found in ", page
        else:
            print page, " is good--returned 'no bills matched your search.'"

        self.assertEqual(success, True)

    def testBillSearchResults(self):

        response = c.get('/bills/search', {'q': 'Internal Revenue Code'})
        status = response.status_code
        pagecontents = response.content
        success = True
        page = 'search for tax legislation'

        if int(status) != 200:
            success = False
            print "problem loading ", page
        elif "amend the Internal Revenue Code" not in pagecontents:
            success = False
            print "term not found in ", page
        else:
            print page, " is good--search results found and loaded."

        self.assertEqual(success, True)
        

    def testBillSearchRedirect(self):
        
        #tests that the search redirects to the bill if a search term returns only one bill.

        response = c.get('/bills/search', {'q': 's 12'}, follow=True)
        status = response.status_code
        pagecontents = response.content
        success = True
        page = 'S 12 search'

        if int(status) != 200:
            success = False
            print "problem loading ", page
        elif "your position on" not in pagecontents:
            success = False
            print "term not found in ", page
        else:
            print page, " redirected successfully to S12 page."

        self.assertEqual(success, True)
    
    def TestOrgsearch(self):
        
        #Org search returns a json file, not an html document. Test checks that search produces exactly one result for "save the martians."

        response = c.get('https://www.popvox.com/ajax/orgs/search', {'term': 'Save The M'}, follow=True)
        status = response.status_code
        pagecontents = response.content
        success = True
        page = 'Martian orgs'

        if "Save the M" in pagecontents:
            import json
            output = json.loads(pagecontents)
          
            if len(output) != 1:
                success = False
                print page, " not equal to one (is bad)"
            
            elif output[0]["url"] != "/orgs/demo":
                success = False
                print page, " not pointing to orgs/demo (is bad)"
          
            else:
                print page, " search is good."
                
        else:
            success = False
            print "'search results not loading in ", page, " search."
                
        self.assertEqual(success, True)
       
class CredentialsTest(TestCase):
    fixtures = ['test_adserver', 'test_users']
    
    def testLogin(self):

        success = login('kosh@vorlons.gov', '3edgedsword', 'good', 'login', self)
        page = 'login'
        
        self.assertEqual(success, True)
        
        print page, " is good."
        
    def testBadLogin(self):
        
        success = login('kosh@vorlons.gov', 'WhatDoYouWant', 'bad', 'bad login', self)
        page = 'bad login'
                
        self.assertEqual(success, True)
        
        print page, " is good."
        
class CommentTest(TestCase):
    fixtures = ['test_adserver', 'test_users', 'test_sbills']
    
    def testComment(self):

        success = comment('112', 's12', 'support', self)
        page = 'leave a comment'
        
        self.assertEqual(success, True)
        
        print page, " is good--comment completed successfully."
    
    def testCommentReport(self):
        
        #test that comments left appear on bill report

        success = comment('112', 's12', 'support', self)
        response = c.get('/ajax/bills/us/112/s12/report/getinfo')
        status = response.status_code
        pagecontents = response.content
        page = 'bill report'
        
        if int(status) != 200:
            success = False
            print "problem loading ", page
        elif "the testing robot" not in pagecontents:
            success = False
            print "comment not found on ", page
        else:
            print page, " is good--comment appears."
        
        self.assertEqual(success, True)
        
class BillReportTest(TestCase):
    fixtures = ['test_adserver', 'test_users', 'test_sbills']
    
    def testPiechart(self):
        #test that the pie charts are showing the right numbers
        
        #current error: need a fixture of bill comments, so that there's numbers to pull
        
        success = comment('112', 's12', 'support', self)
        response = c.get('/ajax/bills/us/112/s12/report/getinfo')
        status = response.status_code
        pagecontents = response.content
        parseddata = json.loads(pagecontents)
        stats = parseddata["stats"]
        page = 'bill report'
        
        print stats["overall"].keys()
        
        """if int(status) != 200:
            success = False
            print "problem loading ", page
        elif "the testing robot" not in pagecontents:
            success = False
            print "comment not found on ", page
        else:
            print page, " is good--comment appears."
        
        self.assertEqual(success, True)"""
        
#-------------------API Tests----------------#        
       
class APIRegistrationTest(TestCase):
	fixtures = ['test_api', 'test_pvgeneral.json']
	
	def test_individual_fail(self):
		response = c.post('/api/v1/users/registration', {
				"api_key": "AJ2651BKQOD1RGNY",
				"mode": "individual",
				"email": "xxx@",
			})
		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			json.loads(response.content),
			{
				"errors": {
					"email": "Enter a valid e-mail address.", 
					"password": "This field is required.", 
					"username": "This field is required."
				}, 
				"status": "fail"
			})

	def do_test(self, args):
		# registration
		response = c.post('/api/v1/users/registration', args)
		self.assertEqual(response.status_code, 200)
		#print response.content
		resp = json.loads(response.content)
		self.assertEqual(resp["status"], "success")
		assert("testing_email_link" in resp)
		assert(resp["testing_email_link"].startswith("http://www.popvox.com"))
		
		# verification email link
		url = resp["testing_email_link"][len("http://www.popvox.com"):]
		response = c.get(url, follow=True)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.content, "Welcome!")
		
		# check user was created
		assert(UserProfile.objects.filter(user__email=args["email"]).exists())
		if "username" in args:
			self.assertEqual(UserProfile.objects.get(user__email=args["email"]).user.username, args["username"])
			
		# login
		response = c.post('/api/v1/users/login', {
			"api_key": "AJ2651BKQOD1RGNY",
			"email": args["email"],
			"password": args["password"]})
		self.assertEqual(response.status_code, 200)
		resp = json.loads(response.content)
		self.assertEqual(resp["status"], "success")
		assert(resp["session"] != "")
		session = resp["session"]

		# logout
		response = c.post('/api/v1/users/logout', {
			"api_key": "AJ2651BKQOD1RGNY",
			"session": session})
		self.assertEqual(response.status_code, 200)
		resp = json.loads(response.content)
		self.assertEqual(resp["status"], "success")

	def test_individual_success(self):
		self.do_test({
			"api_key": "AJ2651BKQOD1RGNY",
			"mode": "individual",
			"email": "test_individual@popvox.com",
			"password": "dummypassword",
			"username": "TestUser1",
			"next": "/mobileapps/ipad_billreader/welcome",
			})

	def test_legstaff_success(self):
		e = "test_legstaff@popvox.com"
		resp = self.do_test({
			"api_key": "AJ2651BKQOD1RGNY",
			"mode": "legislative_staff",
			"email": e,
			"password": "dummypassword",
			"fullname": "Mr. Test Johnson",
			"position": "Test Staff",
			"member": "400284",
			"next": "/mobileapps/ipad_billreader/welcome",
			})
		userprof = UserProfile.objects.get(user__email=e)
		assert(userprof.is_leg_staff())
		assert(userprof.user.legstaffrole.member.id==400284)
		assert(userprof.user.legstaffrole.position=="Test Staff")
		
	def test_member_success(self):
		e = "test_legstaff@popvox.com"
		resp = self.do_test({
			"api_key": "AJ2651BKQOD1RGNY",
			"mode": "member_of_congress",
			"email": e,
			"password": "dummypassword",
			"member": "400284",
			"next": "/mobileapps/ipad_billreader/welcome",
			})
		userprof = UserProfile.objects.get(user__email=e)
		assert(userprof.is_leg_staff())
		assert(userprof.user.legstaffrole.member.id==400284)
		assert(userprof.user.legstaffrole.position=="Senator / Congressman/woman")

