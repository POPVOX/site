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

class ResponseCodeTest(TestCase):
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
	
	success = 1
	
	for x in statics:
	  response = c.get(x)
	  status = response.status_code
	  if int(status) == 200:
	    print x, " is good."
	  else:
	    success = 0
	    print "problem loading ", x
	    
	self.assertEqual(success, 1)



