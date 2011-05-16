#! /usr/bin/python


import mechanize
import time
import re
import random
import urllib

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


    #-----SET BENCHMARKING SERVER-----#
        server_hostname = 'ec2-184-72-179-30.compute-1.amazonaws.com'


    #-----LOAD IFRAME-----#
    
        # open the iframe, time it, verify response
        start_timer = time.time()
        clicky = br.open('https://%s/services/widgets/w/writecongress?iframe=1&bill=us/112/hr730&position=support' % server_hostname)
        clicky.read()
        latency = time.time() - start_timer
        
        self.custom_timers['01. iframe'] = latency
        
        assert (clicky.code == 200), 'Bad HTTP Response'
        assert ("Tell Congress that you" in clicky.get_data()), 'iFrame Text Assertion Failed'
        


    #-----EMAIL CHECK-----#

        #generate email
        email = ""
        for i in range(5):
            email += random.choice('abcdefghijklmnopqrstuvwxyz')
        email += "@popvox.com"
        
        # submit
        checkemail = {
            'action': 'check-email',
            'bill': '16216',
            'email': email,
       }
       
        start_timer = time.time()
        clicky = br.open('https://%s/services/widgets/w/writecongress' % server_hostname, data=urllib.urlencode(checkemail))
        clicky.read()
        latency = time.time() - start_timer
        
        self.custom_timers['02. Email Check'] = latency
        
        assert (clicky.code == 200), 'Bad HTTP Response'
        assert ("""status": "not-registered""" in clicky.get_data()), 'Check-Email Text Assertion Failed'
        


    #-----NEW USER INFO-----#

        #firstname
        firstname = ""
        for i in range(5):
            firstname += random.choice('abcdefghijklmnopqrstuvwxyz')

        #lastname
        lastname = ""
        for i in range(8):
            lastname += random.choice('abcdefghijklmnopqrstuvwxyz')

        #zip
        zipcode = str(20910)

        
        # submit
        newuserinfo = {
            'action': 'newuser',
            'email': email,
            'firstname': firstname,
            'lastname': lastname,
            'zipcode':  zipcode,
       }

        start_timer = time.time()
        clicky = br.open('https://%s/services/widgets/w/writecongress' % server_hostname, data=urllib.urlencode(newuserinfo))
        clicky.read()
        latency = time.time() - start_timer

        self.custom_timers['03. New User Info'] = latency

        assert (clicky.code == 200), 'Bad HTTP Response'
        assert ("""status": "success""" in clicky.get_data()), 'New User Text Assertion Failed'



        #-----ADDRESS INFO-----#

        #address1
        address1 = ""
        for i in range(8):
            address1 += random.choice('abcdefghijklmnopqrstuvwxyz')
        address1 += " Street"

        #address2
        address2 = "Apt. "
        address2 += str(random.randint(1,2000))

        #city
        city = ""
        for i in range(8):
            city += random.choice('abcdefghijklmnopqrstuvwxyz')

        #state
        state = 'MD'

        # submit
        addressinfo = {
            'action':                  'address',
            'bill':                    '16216',
            'email':                   email,
            'useraddress_address1':           address1,
            'useraddress_address2':           address2,
            'useraddress_city':        city,
            'useraddress_firstname':   firstname,
            'useraddress_lastname':    lastname,
            'useraddress_phonenumber': '202-456-2121',
            'useraddress_prefix':      'Dr.',
            'useraddress_state':       state,
            'useraddress_suffix':      '',
            'useraddress_zipcode':     zipcode,
       }

        start_timer = time.time()
        clicky = br.open('https://%s/services/widgets/w/writecongress' % server_hostname, data=urllib.urlencode(addressinfo))
        clicky.read()
        latency = time.time() - start_timer

        self.custom_timers['04. Address'] = latency

        assert (clicky.code == 200), 'Bad HTTP Response'
        assert ("""status": "success""" in clicky.get_data()), 'Address Text Assertion Failed'



        #-----SUBMIT FINAL-----#
        
        submit = {
            'action':                  'submit',
            'bill':                    '16216',
            'cdyne_response':          """  {"ReturnCode": 100, "MultipleMatches": null, "LegislativeInfo": {"StateLegislativeUpper": "020", "StateLegislativeLower": "020", "CongressionalDistrictNumber": "04"}, "ZipCode": "20912-7309", "Urbanization": "", "CensusInfo": null, "PrimaryLow": "701", "StateAbbreviation": "MD", "FinanceNumber": "238478", "PrimaryDeliveryLine": "711 LUDLOW ST", "CityName": "TAKOMA PARK", "IntelligentMailBarcodeKey": "5tBymtCMybGdyXeB/Do8WA==", "CountyNum": "031", "SecondaryDeliveryLine": "", "SecondaryEO": "", "MailingIndustryInfo": null, "PostnetBarcode": "f209127309115f", "SecondaryHigh": "", "PreDirectional": "", "Country": "USA", "FirmOrRecipient": "", "PreferredCityName": "TAKOMA PARK", "ResidentialDeliveryIndicator": "Y", "PMBNumber": "", "SecondaryLow": "", "GeoLocationInfo": {"AvgLatitude": "38.994308", "HasDaylightSavings": true, "AreaCode": "301", "ToLatitude": "38.994499", "FromLongitude": "-76.997924", "AvgLongitude": "-76.9968715", "TimeZone": "EST", "FromLatitude": "38.994117", "ToLongitude": "-76.995819"}, "PMBDesignator": "", "Suffix": "ST", "Primary": "711", "County": "MONTGOMERY", "PrimaryHigh": "799", "PrimaryEO": "O", "PostDirectional": "", "Secondary": "", "StreetName": "LUDLOW", "SecondaryAbbreviation": ""}""",
            'email':                   email,
            'message':                 "730 is 7 15x2. F is the seventh letter in the alphabet, and O is the fifteenth. I support HR FOO. Do you?",
            'password':                '',
            'position':                '+',
            'useraddress_address1':           address1,
            'useraddress_address2':           address2,
            'useraddress_city':        city,
            'useraddress_firstname':   firstname,
            'useraddress_lastname':    lastname,
            'useraddress_phonenumber': '202-456-2121',
            'useraddress_prefix':      'Dr.',
            'useraddress_state':       state,
            'useraddress_suffix':      '',
            'useraddress_zipcode':     zipcode,
       }

        start_timer = time.time()
        clicky = br.open('https://%s/services/widgets/w/writecongress' % server_hostname, data=urllib.urlencode(submit))
        clicky.read()
        latency = time.time() - start_timer

        self.custom_timers['05. Submit Comment'] = latency

        assert (clicky.code == 200), 'Bad HTTP Response'



    #-----OPEN EMAIL VERIFICATION LINK-----#
        popcode = br.response().read()
        popurl = re.compile('http://www.popvox.com')
        testcode = popurl.sub('https://' + server_hostname, popcode)
    
        start_timer = time.time()
        clicky = br.open(testcode)
        clicky.read()
        latency = time.time() - start_timer

        self.custom_timers['06. Email Verification Link'] = latency

        assert (clicky.code == 200), 'Bad HTTP Response'
        assert ("Finish Your Letter to Congress" in clicky.get_data()), 'Email Verification Link Text Assertion Failed'
    


    #-----RETURN TO FRONTPAGE-----#
        
        # click, time, verify
        start_timer = time.time()
        clicky = br.open('https://%s/' % server_hostname)
        clicky.read()
        latency = time.time() - start_timer
        
        self.custom_timers['07. Return to Front Page'] = latency

        print "done"
