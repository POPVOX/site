"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

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

class BillSearchTest(TestCase):
    fixtures = ['test_adserver', 'test_pvgeneral', 'test_bill']

    def testWordsearchFail(self):
        
        response = c.get('/bills/search', {'q': 'winnie the pooh'})
        status = response.status_code
        pagecontents = response.content
        success = True
        page = '/bills/search/' 

        if int(status) != 200:
            success = False
            print "problem loading ", page
        elif "no bills matched your search" not in pagecontents:
            success = False
            print "term not found in ", page
        else:
            print page, " reports that Pooh stuck his head in a honey jar and can't be found (is good)."

        self.assertEqual(success, True)

    def testWordsearchResults(self):

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
        

    def testSearchRedirect(self):

        response = c.get('/bills/search', {'q': 'hr 2110'}, follow=True)
        status = response.status_code
        pagecontents = response.content
        success = True
        page = 'HR 2110 page'

        if int(status) != 200:
            success = False
            print "problem loading ", page
        elif "your position on" not in pagecontents:
            success = False
            print "term not found in ", page
            print pagecontents
        else:
            print page, " loaded successfully."

        self.assertEqual(success, True)

        



