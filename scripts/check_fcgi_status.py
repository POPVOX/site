#!runscript

# run this as the www user....
# su $user -c "/home/$user/sources/site/fcgi";

import urllib, socket, os, subprocess

# this is only used if we want to check the status of
# one of the dev environments
class C(urllib.FancyURLopener):
	def prompt_user_passwd(self, host, realm):
		return ("demo", "avocado")

socket.setdefaulttimeout(30)
ret = C().open("https://%s.popvox.com/?nocache=1" % os.environ["USER"])
if ret.getcode() != 200:
	print os.environ["USER"], "returned status code", ret.getcode()

	#if ret.getcode() == 502:
	#	subprocess.call(["./fcgi"], shell=True)
