from django.core.cache import cache
from django.db import connection
from django.views.decorators.csrf import csrf_protect

import urllib, re, math
from datetime import datetime, timedelta, time
import hashlib, numpy

def formatDateTime(d, withtime=True, tz="EST"):
	if d.time() == time.min:
		# midnight usually means we have no time info
		withtime = False

	if (datetime.now().date() == d.date()):
		if withtime:
			return "Today at" + d.strftime(" %I:%M%p").replace(" 0", " ").lower() #+ " " + tz
		else:
			return "Today"
	elif ((datetime.now() - timedelta(.5)).date() == d.date()):
		if withtime:
			return "Yesterday at" + d.strftime(" %I:%M%p").replace(" 0", " ").lower() #+ " " + tz
		else:
			return "Yesterday"
	elif (datetime.now() - d).days < 7:
		if withtime:
			return d.strftime("%a") + " at" + d.strftime(" %I:%M%p").replace(" 0", " ").lower() #+ " " + tz
		else:
			return d.strftime("%A")
	elif (datetime.now() - d).days < 120:
		return d.strftime("%B %d").replace(" 0", " ")
	else:
		return d.strftime("%b %d, %Y").replace(" 0", " ")
		
def cache_page_postkeyed(duration, vary_by_user=False):
	def f(func):
		def g(request, *args, **kwargs):
			if vary_by_user and request.user.is_authenticated():
				return func(request, *args, **kwargs)

			key = "cache_page_postkeyed::" + request.path + "?"
			
			reqkeys = list(request.REQUEST.keys())
			reqkeys.sort()
			for k in reqkeys:
				key += "&" + urllib.quote(k) + "=" + urllib.quote(request.REQUEST[k])
			
			key = hashlib.md5(key).hexdigest()
			
			ret = cache.get(key)
			if ret == None:
				ret = func(request, *args, **kwargs)
				cache.set(key, ret, duration)
			
			return ret
		return g
	return f


def require_lock(*tables):
	def _lock(func):
		def _do_lock(*args, **kwargs):
			cursor = connection.cursor()
			cursor.execute("LOCK TABLES %s" %', '.join([t + " WRITE" for t in tables]))
			try:
				return func(*args, **kwargs)
			finally:
				cursor.execute("UNLOCK TABLES")
				cursor.close()
		return _do_lock
	return _lock
	
def csrf_protect_if_logged_in(f):
	f_protected = csrf_protect(f)
	
	def g(request, *args, **kwargs):
		if request.user.is_authenticated():
			return f_protected(request, *args, **kwargs)
		else:
			return f(request, *args, **kwargs)
			
	return g

def get_facebook_app_access_token():
	key = "popvox_facebook_app_access_token"
	token = cache.get(key)
	if token: return token
	
	import csv, json, urllib, urlparse
	from settings import FACEBOOK_APP_ID, FACEBOOK_APP_SECRET
				
	url = "https://graph.facebook.com/oauth/access_token?" \
		+ urllib.urlencode({
			"client_id": FACEBOOK_APP_ID,
			"client_secret": FACEBOOK_APP_SECRET,
			"grant_type": "client_credentials"
		})
	
	ret = urllib.urlopen(url)
	if ret.getcode() != 200:
		raise Exception("Failed to get a Facebook App access_token: " + ret.read())
	
	ret = dict(urlparse.parse_qsl(ret.read()))

	token = ret["access_token"]
	if "expires" in ret:
		expires = int(ret["expires"])
	else:
		expires = 60*60*4 # four hours
	
	cache.set(key, token, expires/2)
	
	return token

def compute_frequencies(text, stop_list=[]):
	# split the text on non-word characters
	words = [w for w in re.split(r"[\s,-]+", text) if not "." in w]
	if len(words) == 0: return None
	
	# get frequency totals
	freq = { }
	for word in words:
		if word.lower() in stop_list: continue
		if not word in freq: freq[word] = 0
		freq[word] += 1

	return freq

def make_tag_cloud(freq, base_freq, N, num_lines, min_font, max_font, count_by_chars=False, width=None, font_ar=.5):
	if base_freq != None:
		# if base frequencies are given, turn freq into TF/IDF
		freq = dict((term, freq[term] / (base_freq[term] if term in base_freq else 1.0)) for term in freq)
	
	# sort by frequency and take top N
	freq = list(freq.items()) 				# makes list of (word, frequency) tuples
	freq.sort(key = lambda w_f : -w_f[1])	# sorts by descending frequency
	if not count_by_chars:
		freq = freq[0:N] 					# take top N words
	else:
		freq2 = []							# take top words up to N characters
		ch = 0
		for item in freq:
			freq2.append(item)
			ch += len(item[0])
			if ch > N:
				break
		freq = freq2
	
	# convert frequencies to font sizes. to avoid the range being skewed by very popular
	# terms, don't base the font size on the frequency directly, but instead simply on
	# the index of the term in the top N, modified to make fewer big terms.
	for i in xrange(len(freq)):
		r = float(i)/(float(len(freq))-1) # 0.0 to 1.0
		r = r*r # punch the curve down
		freq[i] = (freq[i][0], min_font + (max_font-min_font)*r)

	freq.sort(key = lambda w_f : w_f[0].lower())	# sort the remainder alphabetically

	# divide words into num_lines lines so that each line has approximately the same
	# number of characters, weighted by their font size (i.e. larger characters take
	# up more space). solve using dynamic programming to minimize the standard deviation
	# of the characters per line.
	def solve_lines(words, n):
		total_chars = sum(len(w)*f for w,f in words)
			
		# find the optimal way to split words (w,f tuples) into n lines, returns
		# the lines and the weighted character count on each line.
		if n == 1:
			return ([words], [total_chars])
		
		# subproblem: find the optimal place to separate the first n-1 lines from
		# the last line. we don't have the time to find the exact solution, but we'll do
		# well to try a few approximate guesses of a good place to make the split.
		split_possibilities = []
		for i in xrange(n-1, len(words)): # start here because n-1 lines requires n-1 words 
			# how many characters would remain
			chars_on_right = sum(len(w)*f for w,f in words[i:])
			split_possibilities.append( (i, abs(float(chars_on_right) - float(total_chars)/float(n))) )
		split_possibilities.sort(key = lambda x : x[1])
		split_possibilities = [s[0] for s in split_possibilities]
			
		best_score = None
		best_solution = None
		for i in split_possibilities[0:3]: 
			# try putting the first line break after the i'th word
			words_on_left, chars_on_left = solve_lines(words[0:i], n-1)

			# how many characters remain, include "space" characters between words
			chars_on_right = sum(len(w)*f for w,f in words[i:])

			# the score for this split is the standard deviation of the character counts per line
			char_counts = chars_on_left + [chars_on_right]
			score = numpy.std(char_counts)
			if not best_score or score < best_score:
				best_score = score
				best_solution = (words_on_left + [words[i:]], char_counts)
		return best_solution
	
	if num_lines > len(freq):
		num_lines = len(freq)
	lines, chars = solve_lines(freq, num_lines)

	if len(lines) == 1:
		return lines

	# because the split is not exact, some lines will be longer than others. to fix
	# this in the display we'll tweak the left padding beside each word to add space
	# on lines that need the words to be more spread out.
	#
	# we've computed the sum of the font sizes in each of the characters on a line,
	# but how many pixels is that? it seems to be .68 times the font size in px for
	# Courier New.
	max_chars_per_line = max(chars) * 1.1 # add spacing even for the longest line
	if width and width > max_chars_per_line*font_ar: max_chars_per_line = width/font_ar
	for i in xrange(len(lines)):
		# divide the remaining character spaces among the word boundaries
		if len(lines[i]) == 1:
			extra_spacing = 0
		else:
			extra_spacing = (max_chars_per_line - chars[i]) / (len(lines[i]) - 1) * font_ar
		for j in xrange(len(lines[i])):
			if j == 0: # no left padding on the first word
				lines[i][j] = (lines[i][j][0], lines[i][j][1], 0)
			else:
				lines[i][j] = (lines[i][j][0], lines[i][j][1], extra_spacing)

	return lines

