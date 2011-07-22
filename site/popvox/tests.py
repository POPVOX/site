
from django.test import TestCase
from django.test.client import Client

c = Client()

'''
class SampleTest(TestCase):
    
    def testTrue(self):
        a = 1
        self.assertEqual(1, a)
        '''

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
            print page, " is good--no bears here."

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
       


