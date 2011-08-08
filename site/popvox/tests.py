
from django.test import TestCase
from django.test.client import Client

c = Client()


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

class SearchingTest(TestCase):
    fixtures = ['test_adserver', 'test_pvgeneral', 'test_sbills', 'test_orgs']

    def BillWordsearchFail(self):
        
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
            print page, " is good--the honey is safe."

        self.assertEqual(success, True)

    def BillWordsearchResults(self):

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
            print page, " loaded successfully."

        self.assertEqual(success, True)
        

    def BillSearchRedirect(self):
        
        #tests that the search redirects to the bill if a search term returns only one bill.

        response = c.get('/bills/search', {'q': 's 12'}, follow=True)
        status = response.status_code
        pagecontents = response.content
        success = True
        page = 'S 12 page'

        if int(status) != 200:
            success = False
            print "problem loading ", page
        elif "your position on" not in pagecontents:
            success = False
            print "term not found in ", page
        else:
            print page, " loaded successfully."

        self.assertEqual(success, True)
    
    def OrgSearch(self):
        
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

        success = True

        response = c.post('/accounts/login?next=/home', {'email': 'kosh@vorlons.gov', 'password': '3edgedsword'},  follow=True)
        status = response.status_code
        pagecontents = response.content
        page = "login"
                
        if int(status) != 200:
            success = False
            print "status code failed on ", page
        elif "<title>Home - POPVOX.com</title>" not in pagecontents:
            success = False
            print page, "did not redirect to home."
        elif 'Welcome, <a href="/accounts/profile">kosh</a>' not in pagecontents:
            success = False
            print page, "is not showing user as logged in."
        else:
            print page, " is good."
        
        self.assertEqual(success, True)
        
    def testBadLogin(self):

        success = True

        response = c.post('/accounts/login?next=/home', {'email': 'kosh@vorlons.gov', 'password': 'WhatDoYouWant'},  follow=True)
        status = response.status_code
        pagecontents = response.content
        page = "bad login"
        
        if int(status) != 200:
            success = False
            print "status code failed on ", page
        elif "<title>Sign In - POPVOX.com</title>" not in pagecontents:
            success = False
            print page, "did not reload login page."
        elif 'Your email and password were incorrect' not in pagecontents:
            success = False
            print page, "did not inform user of bad login."
        else:
            print page, " is good."
        
        self.assertEqual(success, True)
        
class CommentTest(TestCase):
    fixtures = ['test_adserver', 'test_users']
    
    def testComment(self):

        success = True
        CredentialsTest().testLogin()

        response = c.post('/bills/us/112/hr200/comment/support', {
            "message":                  "I support H.R. 200 because it is a good http response.",
            "submitmode":               "Submit Comment >",
            "useraddress_address1":     "1220 East-West Highway",
            "useraddress_address2":     "Apt 1716",
            "useraddress_city":         "Silver Spring",
            "useraddress_firstname":    "Ambassador",
            "useraddress_lastname":     "Kosh",
            "useraddress_phonenumber":  "240-688-6685",
            "useraddress_prefix":       "Mr.",
            "useraddress_state":        "MD",
            "useraddress_suffix":       "",
            "useraddress_zipcode":      "20910",
            },  follow=True)
        status = response.status_code
        pagecontents = response.content
        page = "send comment"
                
        if int(status) != 200:
            success = False
            print "status code failed on ", page
        elif "<title>Share Your Comment" not in pagecontents:
            success = False
            print page, "did not redirect to share."
        elif "What Others Think" not in pagecontents:
            success = False
            print page, "is not showing what others think."
        else:
            print page, " is good."
        
        self.assertEqual(success, True)
