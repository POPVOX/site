#!runscript

import glob
import urllib

for name in glob.glob('media/js/jquery-*'):
    print name
    

current = urllib.urlopen('media/js/jquery.js')
current = current.read()

recent = urllib.urlopen('http://ajax.googleapis.com/ajax/libs/jquery/1/jquery.min.js')
recent = recent.read()

if recent == current:
  print "jquery is up-to-date."
else:
  print "there may be a new version of jquery."