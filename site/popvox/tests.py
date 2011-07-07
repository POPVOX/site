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
    def testStatic(self):
	statics = ['/congres', '/about', '/about/team', '/about/principles', '/about/whyitworks', '/about/contact', '/legal', '/advertising', '/press', '/jobs', '/faq', '/blog']
        response = c.get('/press')
        status = response.status_code
        self.assertEqual(int(status), 200)



