#!runscript

# Fetches bill text documents from GPO's Fdsys and prepares them
# for display in various environments.

import os, sys, base64, re, urllib, urllib2, json, math, glob
from lxml import etree
from StringIO import StringIO
from django.template.defaultfilters import truncatewords

from settings import DATADIR

from popvox.govtrack import CURRENT_CONGRESS

from popvox.models import Bill, PositionDocument, DocumentPage

bill_status_names = {
"as": "Senate Amendment Ordered to be Printed",
"ash": "House Sponsors or Cosponsors Added or Withdrawn",
"ath": "Agreed to by House",
"ats": "Agreed to by Senate",
"cdh": "House Committee Discharged from Further Consideration",
"cds": "Senate Committee Discharged from Further Consideration",
"cph": "Considered and Passed House",
"cps": "Considered and Passed by Senate",
"eah": "Engrossed by House (Amendment)",
"eas": "Engrossed by Senate (Amendment)",
"eh": "Engrossed by House",
"eph": "Engrossed and Deemed Passed by House",
"enr": "Enrolled Bill (Passed Both House & Senate)",
"es": "Engrossed by Senate",
"fah": "Failed Amendment House",
"fph": "Failed Passage in House",
"fps": "Failed Passage in Senate",
"hdh": "Ordered Held at House Desk",
"hds": "Ordered Held at Senate Desk",
"ih": "Introduced in House",
"iph": "Indefinitely Postponed in House",
"ips": "Indefinitely Postponed in Senate",
"is": "Introduced in Senate",
"lth": "Laid on Table in House",
"lts": "Laid on Table in Senate",
"oph": "Ordered to be Printed by House",
"ops": "Ordered to be Printed by Senate",
"pav": "Previous Action Vitiated",
"pch": "Placed on Calendar by House",
"pcs": "Placed on Calendar by Senate",
"pp": "Public Print",
"pap": "Printed as Passed",
"pwah": "Ordered to be Printed with House Amendment",
"rah": "Referred with Amendments in House",
"ras": "Referred with Amendments in Senate",
"rch": "Referred to Different or Additional House Committee",
"rcs": "Referred to Different or Additional Senate Committee",
"rdh": "Received in House from Senate",
"rds": "Received in Senate from House",
"reah": "Re-engrossed Amendment in House",
"res": "Re-engrossed Amendment in Senate",
"renr": "Re-enrolled Bill",
"rfh": "Received from Senate-Referred to House Committee",
"rfs": "Received from House-Referred to Senate Committee",
"rh": "Reported by House Committee",
"rih": "Referred to House Committee with Instructions",
"ris": "Referred to Senate Committee with Instructions",
"rs": "Reported by Senate Committee",
"rth": "Referred to House Committee",
"rts": "Referred to Senate Committee",
"sas": "Senate Sponsors or Cosponsors Added or Withdrawn",
"sc": "Sponsor Change",
}

def fetch_page(url, args=None, method="GET", decode=False):
	if method == "GET" and args != None:
		url += "?" + urllib.urlencode(args).encode("utf8")
	print url, "..."
	req = urllib2.Request(url)
	resp = urllib2.urlopen(req)
	if resp.getcode() != 200:
		raise Exception("Failed to load page: " + url)
	ret = resp.read()
	if "Content Unavailable" in ret:
		raise Exception("Failed to load page ('Content Unavailable'): " + url)
	if decode:
		encoding = resp.info().getparam("charset")
		ret = ret.decode(encoding)
	return ret

def pull_text(congressnumber, thread_index=None, thread_count=None, path=None):
	if path == None: path = str(congressnumber)

	url = "http://www.gpo.gov/fdsys/browse/collection.action?collectionCode=BILLS&browsePath=" + path

	bill_list = fetch_page(url)

	# recursively scan through the collection
	for m in re.findall(r"goWithVars\('/fdsys/browse/collection.action.*collectionCode=BILLS&amp;browsePath=(" + re.escape(path) + "[^&]+)", bill_list):
		pull_text(congressnumber, thread_index=thread_index, thread_count=thread_count, path=m)
	
	# and on leaf nodes of the collection, look for each bill version
	for m in re.findall(r"(http://www.gpo.gov:80/fdsys/pkg/BILLS-" + str(congressnumber) + "([a-z]+)(\d+)([a-z]\w*)/pdf/[^\"']+.pdf)", bill_list):
		url, billtype, billnumber, billstatus = m
		billnumber = int(billnumber)

		if thread_count != None:
			if int(billnumber) % thread_count != thread_index:
				continue

		try:
			pull_bill_text(congressnumber, billtype, billnumber, billstatus, url, thread_index=thread_index)
		except Exception as e:
			print "error in ", thread_index, m, e
		
def pull_bill_text(congressnumber, billtype, billnumber, billstatus, pdf_url, thread_index=None):
	m = (congressnumber, billtype, billnumber, billstatus)

	def printthread():
		if thread_index != None:
			print thread_index,
	
	# convert FDSys bill type codes to our bill type codes, which were based on GPOAccess
	bill_type_map = {
		"hr": "h",
		's': 's',
		'hjres': 'hj',
		'sjres': 'sj',
		'hconres': 'hc',
		'sconres': 'sc',
		'hres': 'hr',
		'sres': 'sr',
	}
	billtype = bill_type_map[billtype]	
	
	try:
		bill = Bill.objects.get(congressnumber=congressnumber, billtype=billtype, billnumber=billnumber, vehicle_for=None)
	except Bill.DoesNotExist:
		printthread()
		print "invalid bill", m
		return
		
	# check if we have this document already and have pages loaded
	if PositionDocument.objects.filter(bill=bill, doctype=100, key=billstatus, txt__isnull=False, pdf_url__isnull=False, updated__gt="2011-11-23 13:30").exists() and DocumentPage.objects.filter(document__bill=bill, document__doctype=100, document__key=billstatus, png__isnull=False, text__isnull=False).exists():
		if not "ALL" in os.environ:
			return
		
	existing_records = list(PositionDocument.objects.filter(bill = bill, doctype = 100, key = billstatus))
	for er in existing_records[1:]:
		er.delete()
	
	if len(existing_records) == 0:
		d = PositionDocument(
			bill = bill,
			doctype = 100,
			key = billstatus)
		isnew = True
	else:
		d = existing_records[0]
		isnew = False
		
	d.text = "[not available]" # HTML
	
	what_did_we_fetch = []
	
	d.pdf_url = pdf_url
	
	if isnew:
		mods = fetch_page(re.sub("/pdf.*", "/mods.xml", d.pdf_url))
		mods = etree.fromstring(mods)
		
		ns = { "m": "http://www.loc.gov/mods/v3" }
		
		#title = mods.xpath('string(m:titleInfo[@type="alternative"]/m:title)', namespaces=ns)
		#if not title: title = mods.xpath('string(m:extension/m:searchTitle)', namespaces=ns)
		#if not title:
		#	printthread()
		#	print "bill title not found in MODS", m
		#	return
		#title = unicode(title) # force lxml object to unicode, otherwise it isn't handled right in Django db layer
		
		# The bill title supplied by GPO is inconsistent.
		
		# Set the title of the document to the status name.
		bill_status_code = ""
		bill_status_sequence = ""
		for s in billstatus:
			if not s.isdigit(): bill_status_code += s
			if s.isdigit(): bill_status_sequence += s
		if bill_status_code not in bill_status_names:
			printthread()
			print "status code not recognized", billstatus
			return
		title = bill_status_names[bill_status_code]
		if bill_status_sequence != "": title += " (" + bill_status_sequence + ")"
		
		date = mods.xpath('string(m:originInfo/m:dateIssued)', namespaces=ns)

		d.title = title
		d.created = date # set if isnew
		
		what_did_we_fetch.append("mods")
	
	if not d.pdf:
		d.pdf = base64.encodestring(fetch_page(d.pdf_url))
		what_did_we_fetch.append("pdf")
	
	if not d.txt:
		text = fetch_page(d.pdf_url.replace("/pdf/", "/html/").replace(".pdf", ".htm"), decode=True)
		text = text.replace("<html><body><pre>\n", "").replace("</pre></body></html>", "").decode("utf8")
		text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
		d.txt = text
		what_did_we_fetch.append("txt")
		
	if not d.xml:
		try:
			d.xml = base64.encodestring(fetch_page(d.pdf_url.replace("/pdf/", "/xml/").replace(".pdf", ".xml")))
		except Exception as e:
			printthread()
			print m, "xml version not available", e
		what_did_we_fetch.append("xml")
		
	d.save()
	
	# print status
	
	def printstatus():
		printthread()
		print "fetched", m, " ".join(what_did_we_fetch), "document_id="+str(d.id), "bill_id="+str(bill.id)

	if len(what_did_we_fetch) > 0 or "THREADS" not in os.environ:
		printstatus()
		
	# generate page-by-page content

	if d.toc != None and DocumentPage.objects.filter(document=d, png__isnull=False, pdf__isnull=False, text__isnull=False).exists() and "ALL" not in os.environ:
		return

	if len(what_did_we_fetch) == 0 and "THREADS" in os.environ:
		printstatus()

	break_pages(d, thread_index=thread_index)
	
	# generate version comparisons --- check for any new
	# comparisons that can be generated for this bill.
	
	prev_p = None
	for p in PositionDocument.objects.filter(bill=bill, doctype=100).order_by('created'):
		if prev_p:
			compare_documents(prev_p, p)
		prev_p = p


def compare_lists(d1, d2, allow_squiggle_op=False, allow_recursive_compare=True):
	# Compares two lists of an arbitrary type of elements, except those
	# elements must be hashable and comparable.
	#
	# Reduces the elements each to a single byte, since diff_match_patch
	# can only compare byte strings. If there are more than 255 distinct
	# elements in the two lists (combined), multiple elements may map
	# to the same byte. That means that what diff_match_patch internally
	# thinks are parallel regions of the same items may actually be different.
	# We check for that. If the regions are different and if allow_squiggle_op
	# is False (the default), then those regions are returned as a sequence
	# of a - and a + op, as changes are treated by diff_match_patch normally.
	# If allow_squiggle_op is true, those regions are returned with a special
	# "~" op indicating parallel regions of an identical count of items but
	# the items are not pairwise equal.

	def build_encoding(seq):
		# Prepare to map each item of the sequence to a single byte. Since
		# there are probably more than 255 (can't have null) distinct items
		# in the document sequences, we have to strategize about how to map
		# items to bytes. Also note that the same encoding must be used for
		# both documents.
		#
		# I conjecture that the most frequently occurring items should
		# tend to be mapped to distinct bytes, while the least frequently
		# ocurring items should map to bytes mapped to more than one item.
		
		seq = list(seq) # if it is an iterable, make sure we get access
						# multiple times
		
		# Compute item frequencies.
		freqs = { }
		for item in seq:
			if item not in freqs:
				freqs[item] = 1
			else:
				freqs[item] += 1
		
		encoding = { }
		if len(freqs) <= 255:
			# If there are no more than 255 distinct items, map them
			# uniquely to bytes.
			for item in seq:
				if item not in encoding:
					encoding[item] = len(encoding) + 1 # start at 1 to avoid NULL byte
		
		else:
			# There are 256 or more unique items, so smartly map
			# the items to bytes from 1-255. Dole out the values
			# in order of frequency but on a punched curve.
			
			sorted_items = freqs.items()
			sorted_items.sort(key = lambda x : x[1], reverse=True)
			itemcount = len(sorted_items)
			for i, (item, freq) in enumerate(sorted_items):
				r = float(i)/float(itemcount) # range is [0, 1)
				r = pow(r, .5) # punch the curve
				r = int(255*r) # scale to [0, 254]
				encoding[item] = 1 + r

		return encoding
		
	import itertools
	enc = build_encoding(itertools.chain(d1, d2))

	def encode(seq, encoding):
		ret = ""
		for item in seq:
			ret += chr(encoding[item])
		return ret
	
	d1e = encode(d1, enc)
	d2e = encode(d2, enc)
	
	import diff_match_patch
	
	d1pos = 0
	d2pos = 0
	mindoclen = min(len(d1), len(d2))
	for op, oplen in diff_match_patch.diff(d1e, d2e):
		if op == "=":
			for i in xrange(oplen):
				if d1[d1pos+i] != d2[d2pos+i]:
					op = "~"
					break
					
			if op == "~" and allow_recursive_compare and oplen < mindoclen/10 and oplen > 1:
				# If there is actually a difference in a relatively small region
				# of the document, and allow_recursive_compare is true, then
				# compare the two sub-lists recursively, in the hopes that
				# there will be fewer unique items in the sublists so that items
				# are less clobbered into 255 bytes, and in turn the comparison
				# will be more likely to be correct and precise, rather than
				# having to issue a ~ or -/+ sequence for the whole of oplen.
				for op2, oplen2 in compare_lists(d1[d1pos:d1pos+oplen], d2[d2pos:d2pos+oplen], allow_squiggle_op=allow_squiggle_op, allow_recursive_compare=True):
					yield (op2, oplen2)
				
			elif op == "=" or allow_squiggle_op:
				# Pass on "="'s back to the caller, or if this is a sequence that has
				# a difference and the caller supports that, pass on the "~".
				yield (op, oplen)
				
			else:
				# The regions actually do not match, and caller doesn't support
				# "~"-ops, so yield a delete followed by an insert.
				yield ("-", oplen)
				yield ("+", oplen)
				
			d1pos += oplen
			d2pos += oplen
			
		elif op == "-":
			d1pos += oplen
			yield (op, oplen)
			
		elif op == "+":
			d2pos += oplen
			yield (op, oplen)
	
def diff_by_word(d1, d2):
	# Compares the text of d1 and d2 but does it by splitting the documents
	# into words and reducing each word to a byte, therefore hopefully making
	# the comparison much faster.
	
	import diff_match_patch
	
	def tokenize(d):
		# this has to be compatible with the way the text is put back together below.
		import re
		ret = []
		s = 0
		for m in re.findall(r"\S+\s?|\s\s+|.", d, re.DOTALL):
			ret.append(m)
			s += len(m)
		assert len(d) == s # did we capture all characters?
		return ret
		
	d1w = tokenize(d1)
	d2w = tokenize(d2)
	
	# Compute the difference on the lists.
	d1pos = 0
	d2pos = 0
	for op, oplen in compare_lists(d1w, d2w, allow_squiggle_op=True):
		# Map the oplen from 'words' back to characters in the original documents.
		
		d1pos_ = d1pos
		d2pos_ = d2pos
		
		oplen1 = 0
		oplen2 = 0
		
		for i in xrange(oplen):
			if op in ('-', '=', '~'):
				oplen1 += len(d1w[d1pos])
				d1pos += 1
			if op in ('+', '=', '~'):
				oplen2 += len(d2w[d2pos])
				d2pos += 1

		# check for mapping to no bytes, which shouldn't be possible
		if oplen1 == 0 and oplen2 == 0:
			continue
		
		# check for easy conditions of insertions and deletions
		if oplen1 == 0:
			assert op == "+"
			yield ('+', oplen2)
			continue
		if oplen2 == 0:
			assert op == "-"
			yield ('-', oplen1)
			continue
		
		# compare_lists has already checked that the words definitely
		# matched up, so they must have the same length.
		if op == "=":
			assert oplen1 == oplen2
			assert ''.join(d1w[d1pos_:d1pos]) == ''.join(d2w[d2pos_:d2pos])
			yield ("=", oplen1)
			continue
			
		# the only remaining case is two parallel regions that are reported
		# to us to have unequal content.
		assert op == "~"

		# turn this into +/-/= ops for the caller, by comparing the document
		# byte content.
		
		# get the text content
		opwords1 = ''.join(d1w[d1pos_:d1pos])
		opwords2 = ''.join(d2w[d2pos_:d2pos])
		
		# use diff_match_patch to compare the bytes, which are hopefully
		# mostly the same and hopefully the comparison will go fast...
		for dmp in diff_match_patch.diff(opwords1, opwords2):
			# yield exactly this back to the caller because it reports
			# lengths by character, which is exactly what the caller wants.
			yield dmp

def break_pages(document, thread_index=None, force=None):
	# Generate PNG and text representations of the pages.
	if document.pdf == None: raise ValueError("I don't have PDF data.")

	def status(txt):
		print "   " + (str(thread_index) + " " if thread_index != None else "") + txt
	
	import base64, tempfile, subprocess, shutil, glob
	import diff_match_patch

	path = tempfile.mkdtemp()
	try:
		pdf = open(path + "/document.pdf", "w")
		pdf.write(base64.decodestring(document.pdf))
		pdf.close()
		
		needs_png = (not document.pages.exists() or document.pages.filter(png__isnull=True).exists()) or force in ("all", "png")
		needs_pdf = (not document.pages.exists() or document.pages.filter(pdf__isnull=True).exists()) or force in ("all", "pdf")
		
		if needs_png or needs_pdf:
			status("bursting...")
			
			#subprocess.call(["perl", "/usr/bin/pdfcrop", path + "/document.pdf"], cwd=path) # latex package
				# if we do this, then the output size (scale-to-x/y) needs to be
				# adjusted because of an arbitrary aspect ratio that might come out,
				# also the filename shifts
			
			if needs_png:
				# generate PNGs for each page
				
				subprocess.call(["pdftoppm", "-scale-to-x", "1024", "-scale-to-y", "1325", "-png", path + "/document.pdf", path + "/page"], cwd=path) # poppler-utils package
				
				# the first page has an an "authenticated GPO document" seal, which we want to overwrite
				# with a white rectangle for legal purposes. and we want to do this before we determine
				# the crop rectangle so we don't crop with the assumption it is there. hopefully the
				# seal is in the same place on page 1 of every bill.
				for fn in glob.glob(path + "/page-*.png"):
					pagenum = int(fn[len(path)+6:-4])
					if pagenum == 1:
						subprocess.call(["gm", "mogrify", "-fill", "white", "-draw", "rectangle 20,5,200,60", fn])
				
				# zealously crop the resulting images, but crop each page the same way. so, we have to
				# scan each image to see the minimum of the zealous crops.
				extents = [None, None, None, None]
				from PIL import Image, ImageChops
				for fn in glob.glob(path + "/page-*.png"):
					im = Image.open(fn)
					im = ImageChops.invert(im) # make white black (i.e zeroes)
					bb = im.getbbox() # returns bounding box that excludes zero pixels
					if bb:
						for i in (0, 1):
							if extents[i] == None or bb[i] < extents[i]: extents[i] = bb[i]
						for i in (2, 3):
							if extents[i] == None or bb[i] > extents[i]: extents[i] = bb[i]
			
			if needs_pdf:
				# generate PDFs for each page
				
				subprocess.call(["pdftk", path + "/document.pdf", "burst", "compress"], cwd=path) # pdftk package
	
			# load each PNG/PDF into the database
	
			max_page = 0
	
			for fn in glob.glob(path + "/page-*.p*"):
				pagenum = int(fn[len(path)+6:-4])
				
				dp, isnew = DocumentPage.objects.get_or_create(document = document, page = pagenum)
				
				if needs_png:
					# use graphicsmagick mogrify to crop, convert the PNG to greyscale (to reduce file size),
					# overwriting the file in place.
					subprocess.call(["gm", "mogrify"] + (["-crop", "%dx%d+%d+%d" % (extents[2]-extents[0], extents[3]-extents[1], extents[0], extents[1])] if extents else []) + ["-type", "Grayscale", fn])
					
					pngfile = open(fn)
					png = pngfile.read()
					pngfile.close()
				
					dp.png = base64.encodestring(png)
					
				if needs_pdf:
					ppdffile = open(path + "/pg_%04d.pdf" % pagenum)
					ppdf = ppdffile.read()
					ppdffile.close()
	
					dp.pdf = base64.encodestring(ppdf)
				
				dp.save()
				
				if pagenum > max_page: max_page = pagenum
	
			# clear out any unused page objects
			document.pages.filter(page__gt = max_page).delete()
		
		if not document.pages.filter(text__isnull=False).exists() or force in ("all", "txt"):
			# generate text
			
			# While the GPO text file has good layout, it doesn't indicate page boundaries.
			# To get page boundaries, we compare the text to the result of pdftext on the PDF
			# and look for \x0C new page characters.
			
			status("page-by-page text format...")
			
			subprocess.call(["pdftotext", "-layout", "-enc", "UTF-8", path + "/document.pdf"], cwd=path) # poppler-utils package
			f = open(path + "/document.txt")
			text = f.read().replace("\x00", "") # utf-8, binary string... we're getting some null bytes somewhere
			f.close()
			
			dtext = document.txt.encode("utf8").replace("\x00", "") # we're getting some null bytes somewhere
			
			# move to lowercase to make documents more similar, and since it does not
			# change document length we can do it here.
			diff = diff_by_word(dtext.lower(), text.lower())
			
			pages = [""]
			lctr = 0
			rctr = 0
			for (op, length) in diff:
				if op in ("-", "="):
					#print op, dtext[lctr:lctr+length]
					pages[-1] += dtext[lctr:lctr+length]
					lctr+=length
				if op in ("+", "="):
					#print op, text[rctr:rctr+length]
					for i in xrange(text.count("\x0C", rctr, rctr+length)):
						pages.append("")
					rctr+=length
			for i in xrange(len(pages)):
				try:
					p = DocumentPage.objects.get(document=document, page=i+1)
				except:
					break
				p.text = pages[i].decode("utf8", "replace")
				p.save()
			
		if document.xml and (not document.toc or force in ("all", "toc")):
			# generate table of contents
			
			# To make a table of contents, we look at the XML document structure and match that
			# against the page-by-page text.
		
			status("table of contents...")
			
			subprocess.call(["pdftotext", "-layout", "-enc", "UTF-8", path + "/document.pdf"], cwd=path) # poppler-utils package
			f = open(path + "/document.txt")
			text = f.read().lower() # utf-8, binary string
			f.close()
			
			xml = base64.decodestring(document.xml)
			xml = xml.replace("&nbsp;", " ") # hmm
			
			try:
				tree = etree.parse(StringIO(xml)).getroot()
			except Exception as e:
				print e
				return
				
			header_levels = {
				'chapter': 'Chapter',
				'division': 'Division',
				'part': 'Part',
				'subchapter': 'Subchater',
				'subdivision': 'Subdivision',
				'subpart': 'Subpart',
				'subtitle': 'Subtitle',
				'title': 'Title',
				'section': None,
				'subsection': None,
				'header': None,
				'subheader': None,
			}
			def serialize_node(node, level, info):
				label = None
				if node.tag in header_levels:
					label = ""
					if header_levels[node.tag] != None:
						label += header_levels[node.tag] + " "
					for child in node.iterdescendants():
						if child.text:
							label = truncatewords(label + (" " if len(label) > 0 else "") + child.text, 10)
							if child.tag == "header" or "..." in label or len(label) > 64:
								break
							if child.tag == "enum" and not label.endswith("."):
								label += "."
					if label != "":
						info["section_headings"].append( (len(info["tree_serialized"]), level, label) )
				if node.text:
					info["tree_serialized"] += node.text.lower().encode("utf8") + " "
				for child in node:
					serialize_node(child, level+(1 if label else 0), info)
				
			info = { "section_headings": [], "tree_serialized": "" }
			serialize_node(tree, 0, info)
			
			diff = diff_by_word(info["tree_serialized"], text)
			pagenum = 1
			sections = []
			next_section = 0
			lctr = 0
			rctr = 0
			for (op, length) in diff:
				for i in xrange(length):
					if op in ("+", "="):
						pagenum += text.count("\x0C", rctr, rctr+1)
						rctr += 1
					if op in ("-", "="):
						while next_section < len(info["section_headings"]) and (lctr <= info["section_headings"][next_section][0] < (lctr+1)):
							s = info["section_headings"][next_section]
							sections.append( { "page": pagenum, "indentation": s[1], "label": s[2] } )
							next_section += 1
						if next_section == len(info["section_headings"]):
							break
					
						lctr += 1
						
			# remove indentation levels when the average page separation is less than one
			# i.e., roughly, most section headings at that level fall multiple per page
			last_page = { }
			pagediffs = { }
			for section in sections:
				if section["indentation"] in last_page and section["indentation"] > 0:
					if section["indentation"] not in pagediffs:
						pagediffs[section["indentation"]] = [0, 0]
					pagediffs[section["indentation"]][0] += 1
					pagediffs[section["indentation"]][1] += (section["page"] - last_page[section["indentation"]])
				last_page[section["indentation"]] = section["page"]
			kill_levels = []
			for k, v in pagediffs.items():
				if float(v[1])/float(v[0]) < 1.0:
					kill_levels.append(k)
			while max(rec["indentation"] for rec in sections) in kill_levels:
				max_indent = max(rec["indentation"] for rec in sections)
				sections = [s for s in sections if s["indentation"] < max_indent]
			
			# don't let the toc be so darn long. if so, chop off innermost indentation level.
			# if it's too long, it gets truncated in the db and causes errors in json.loads.
			toc = json.dumps(sections)
			while len(toc) > 10000:
				max_indent = max(rec["indentation"] for rec in sections)
				sections = [s for s in sections if s["indentation"] < max_indent]
				toc = json.dumps(sections)
			
			document.toc = toc
			document.save()
			
	finally:
		shutil.rmtree(path)

def compare_documents(d1, d2):
	# Creates a comparison of two bill versions of the same bill by
	# aligning the text content of the two PDFs and creating a visual
	# output that aligns the PDFs side by side and marks changes with
	# underlines.
	
	# set up the new document
	doc, isnew = PositionDocument.objects.get_or_create(
		bill = d1.bill,
		doctype = 101,
		key = "cmp:" + d1.key + "," + d2.key,
		defaults = { "created": d1.created})
	doc.title = "Comparison: " + d1.title + " and " + d2.title
	doc.save()
	doc.pages.all().delete()
	print d1.bill.id, d1.bill, ":", d1.id, d1.key, "vs", d2.id, d2.key, "=>", doc.id, doc.key
	
	# extract the text layer of the PDF in -bbox mode which yields
	# a list of words in the PDF in document order and for each the
	# page number and bounding box of each word.
	import base64, tempfile, subprocess, shutil
	path = tempfile.mkdtemp()
	doclayout = [None, None] # [(startchar, wordcoord, text), (startchar, wordcoord, text)]
	try:
		# for each of the two documents....
		for d, dd in ((d1, 0), (d2, 1)):
			
			# use pdftotext to get the coordinates of bounding boxes
			# around each word in the document.
			
			# save PDF to disk
			pdf = open(path + ("/document%d.pdf" % dd), "w")
			pdf.write(base64.decodestring(d.pdf))
			pdf.close()
			
			# execute pdftotext and read back the XHTML file
			subprocess.call(["pdftotext", "-bbox", "-enc", "UTF-8", path + ("/document%d.pdf" % dd)], cwd=path) # poppler-utils package
			f = open(path + ("/document%d.html" % dd))
			xhtml = f.read() # utf-8, binary string
			f.close()
			
			# read in the coordinates and serialize the information so that
			# we can compare the text of the two documents, but remember
			# the starting byte position of each word in the concatenated text
			# string, and the bounding box for each word.
			startchar = []
			text = ""
			wordcoord = []
			tree = etree.parse(StringIO(xhtml)).getroot()
			ns = { "xhtml": "http://www.w3.org/1999/xhtml" }
			pagenum = 1
			for node in tree.xpath("xhtml:body/xhtml:doc/xhtml:page", namespaces=ns):
				page_width, page_height = node.attrib["width"], node.attrib["height"]
				
				page_width = float(page_width)
				page_height = float(page_height)
				
				# look for line numbers as digits that appear at the same xMax
				# and no non-digits appear at that xMax.
				possible_left_margin = { }
				for node2 in node.xpath("xhtml:word", namespaces=ns):
					rm = int(float(node2.attrib["xMax"]))
					if not (100 < rm < 200): continue # I see line numbers at 140 in one example
					if node2.text.isdigit():
						if not rm in possible_left_margin: possible_left_margin[rm] = 0
						if possible_left_margin[rm] == -1: continue
						possible_left_margin[rm] += 1 # count up detected line numbers
					else:
						possible_left_margin[rm] = -1
				possible_left_margin = possible_left_margin.items()
				possible_left_margin.sort(key = lambda kv : -kv[1])
				left_margin = None
				if len(possible_left_margin) > 0 and possible_left_margin[0][1] > 5:
					left_margin = possible_left_margin[0][0]

				for node2 in node.xpath("xhtml:word", namespaces=ns):
					# for each word, note its starting byte position in the text,
					# its page number, and its bounding box in normalized
					# coordinates relative to the page dimensions, and then
					# append the text content into the text variable.
					
					# remove hyphens because it causes a change at any word that
					# changes in line wrapping
					t = node2.text
					if t.endswith("-"):
						t = t[0:-1]
					else:
						t += " "
						
					if int(float(node2.attrib["xMax"])) == left_margin:
						# This is most likely a line number. We must include
						# it in the doclayout array so that we actually copy
						# this into the output document, but clear out the
						# text so it does not affect the comparison.
						t = ""
						
					startchar.append(len(text))
					wordcoord.append( (pagenum,
						(float(node2.attrib["xMin"])/page_width, float(node2.attrib["yMin"])/page_height), (float(node2.attrib["xMax"])/page_width, float(node2.attrib["yMax"])/page_height)) )
					text += t.encode("utf8")
				pagenum += 1
			doclayout[dd] = (startchar, wordcoord, text)
	finally:
		shutil.rmtree(path)

	# Amendments in the nature of a substitute are commonly
	# printed with the original text struck out. In the text layer
	# stream, it just appears as plain text, followed by the new
	# text, and that messes up the alignment since the original
	# document only has the bill once. Remove the struck-out
	# text by aligning the text with the GPO plain text document
	# which indicates struck-out text as <DELETED>...</DELETED>
	# and then replacing the characters in the text layer stream
	# with spaces so it doesn't mess up indices but won't line
	# up with the other document.
	for d, dd in ((d1, 0), (d2, 1)):
		if "<DELETED>" in d.txt:
			alg = diff_by_word(d.txt.lower().encode("utf8"), doclayout[dd][2].lower())
			dtext = list(doclayout[dd][2])
			pos_left = 0
			pos_right = 0
			idx = 0
			for m in re.finditer("<DELETED>(.*?)</DELETED>", d.txt, re.DOTALL):
				# advance so that idx points to the last op that
				# starts at or before this deleted region.
				while (pos_left + alg[idx][1] <= m.start()) or (pos_left < m.start() and alg[idx][0] == "+"):
					if alg[idx][0] != "+": pos_left += alg[idx][1]
					if alg[idx][0] != "-": pos_right += alg[idx][1]
					idx += 1
				# clear out ops from there until the last op that starts
				# within this region. don't update idx for the next iteration
				# because the last op might overlap with the next <DELETED>
				# group.
				midx = idx
				mpos_left = pos_left
				mpos_right = pos_right
				while mpos_left < m.end():
					# if this op is an equal or insertion, clear out the
					# corresponding characters on the right side.
					# if the op is an = op, then we can be more careful
					# because the op probably doesn't line up exactly
					# with the <DELETED>...</DELETED> match.
					if alg[midx][0] != "-":
						for i in xrange(alg[midx][1]):
							if alg[midx][0] != "=" or (m.start() <= (mpos_left + i) < m.end()):
								dtext[mpos_right+i] = " "
					
					if alg[midx][0] != "+": mpos_left += alg[midx][1]
					if alg[midx][0] != "-": mpos_right += alg[midx][1]
					midx += 1
			doclayout[dd] = (doclayout[dd][0], doclayout[dd][1], "".join(dtext))

	# Align the serialized text of the text layers of the two PDFs, and
	# then simplify the diff to minimize reported changes so it is
	# more readable.
	diff = diff_by_word(doclayout[0][2], doclayout[1][2])
	
	def simplify_diff(diff):
		# re-flow the comparison so that insertions followed by deletions
		# or vice versa are collapsed together
		opseq = [] # list of list of [=, #], left length, right length
		for (op, length) in diff:
			if op == "-":
				if len(opseq) > 0 and opseq[-1][0] == "#":
					opseq[-1][1] += length
				else:
					opseq.append( ["#", length, 0] )
			elif op == "+":
				if len(opseq) > 0 and opseq[-1][0] == "#":
					opseq[-1][2] += length
				else:
					opseq.append( ["#", 0, length] )
			elif op == "=":
				if len(opseq) > 0 and opseq[-1][0] == "=":
					# should not really occur....
					opseq[-1][1] += length
					opseq[-1][2] += length
				else:
					opseq.append( ["=", length, length] )
		
		# collapse pairs of nearby changes when they are separated
		# by fewer identical characters than the total number of characters
		# changed.
		for i in xrange(len(opseq)-2):
			if opseq[i][0] != "#": continue
			j = i
			while j < len(opseq) - 2:
				if opseq[j+1][0] != "=": break
				if opseq[j+2][0] != "#": break
				
				ch_chars = opseq[i][1]+opseq[i][2]+opseq[j+2][1]+opseq[j+2][2]
				same_chars = opseq[j+1][1]+opseq[j+1][2]
				if ch_chars < 16   and same_chars > ch_chars: break
				if ch_chars >= 16 and same_chars > math.sqrt(ch_chars)*4: break
				
				opseq[i][1] += opseq[j+1][1] # extend the original op with these ranges
				opseq[i][2] += opseq[j+1][2]
				opseq[i][1] += opseq[j+2][1]
				opseq[i][2] += opseq[j+2][2]
				opseq[j+1][0] = None # kill these ranges
				opseq[j+2][0] = None
				j += 2
		
		return opseq
	
	opseq = simplify_diff(diff)
	
	# Construct the output that visually aligns the two documents side
	# by side and highlights the changes with underlining.
	output_width = 512
	output_height = int(output_width * 11/8.5)
	path = tempfile.mkdtemp()
	pgfn = {}
	try:
		# extract images from each source PDF with pdftoppm and
		# make a dict of the filenames.
		for d, dd in ((d1, 0), (d2, 1)):
			pdf = open(path + ("/document%d.pdf" % dd), "w")
			pdf.write(base64.decodestring(d.pdf))
			pdf.close()
			subprocess.call(["pdftoppm", "-scale-to-x", str(output_width), "-scale-to-y", str(int(output_width*11/8.5)), "-png", path + ("/document%d.pdf" % dd), path + ("/page-%d" % dd)], cwd=path) # poppler-utils package
			for fn in glob.glob(path + ("/page-%d-*.png" % dd)):
				pagenum = int(fn[len(path)+8:-4])
				pgfn[str(dd) + ":" + str(pagenum)] = fn
		
		# the alignment isn't going to fit into the same pagination
		# of the original documents because they are probably
		# paginated differently, so we have to re-flow the comparison
		# into a new set of pages.
			
		# initialize the first output page image.
		from PIL import Image, ImageDraw, ImageChops
		imcombined = Image.new("RGB", (output_width*2, output_height))
		imcombined_draw = ImageDraw.Draw(imcombined)
		imcombined_draw.rectangle( (0,0)+imcombined.size, fill=(255,255,255) )
		
		# keep track of state for the left and right documents....
		ylast = [0, 0] # last y-coordinate of output
		ylast2 = [0, 0] # last y-coordinate of output at the last point of alignment
		yoffset = [0, 0] # current offset to apply to output blocks
		char_index = [0, 0] # current position in the text layer serialization
		word_index = [0, 0] # current word in the text layer serialization
		chars_since_break = 0 # number of characters since the last point of alignment
		im = [None, None] # source images of current page in each document
		im_page = [None, None] # page numbers of the source images currently loaded
		output_page = 1 # current page number of output
		output_pagination = [(0,0)] # char offset in the text layout serialization at the start of each output page
		
		def save_page():
			dp, isnew = DocumentPage.objects.get_or_create(document=doc, page=output_page)
			buf = StringIO()
			imcombined.save(buf, "png")
			dp.png = base64.encodestring(buf.getvalue())
			dp.save()
			output_pagination.append( tuple(char_index) ) # clone the variable

		for op, leftlen, rightlen in opseq:
			if op == None: continue
			oplen = (leftlen, rightlen)

			# keep a running count of how many characters out of
			# sync we are, and re-align the yoffsets when we start a
			# new hunk of matching characters and we are sufficiently
			# out of sync
			chars_since_break += abs(leftlen-rightlen)
			if op == "=" and chars_since_break > 25:
				# force alignment after large changes
				ylast2 = list(ylast) # clone
				chars_since_break = 0

			for dd in (0, 1):
				# for same-hunks, copy over any word that occurs intersecting the
				# start and entirely within this region, but not intersecting the end
				# so that a change to part of the word definitely causes an underline
				# on the whole word.
				while word_index[dd] < len(doclayout[dd][0]):
					if op == "=" and word_index[dd] < len(doclayout[dd][0])-1  and doclayout[dd][0][word_index[dd]+1] > char_index[dd] + oplen[dd]: break
					if op == "#" and doclayout[dd][0][word_index[dd]] >= char_index[dd] + oplen[dd]: break
						
					pagenum, bbox_min, bbox_max = doclayout[dd][1][word_index[dd]]
					
					# because we delete text enclosed by <DELETED>, we should
					# remove it from the output entirely!
					word_start = doclayout[dd][0][word_index[dd]]
					if word_index[dd] < len(doclayout[dd][0])-1:
						word_end = doclayout[dd][0][word_index[dd]+1]
					else:
						word_end = len(doclayout[dd][2])
					word_text = doclayout[dd][2][word_start:word_end]
					if word_text.strip() == "":
						word_index[dd] += 1
						continue
										
					# open the page image containing the word
					if im_page[dd] != pagenum:
						im[dd] = Image.open(pgfn[str(dd) + ":" + str(pagenum)])
						im_page[dd] = pagenum
						
						ylast2[dd] = ylast[dd] # make sure not to go backwards
						yoffset[dd] += 20 # space out
					
					# get an image instance cropped to that word
					bbox = [int(bbox_min[0]*im[dd].size[0]), int(bbox_min[1]*im[dd].size[1]), int(bbox_max[0]*im[dd].size[0]), int(bbox_max[1]*im[dd].size[1])]
					im_word = im[dd].crop(bbox)
					
					# don't bother pasting, underlining, or adjusting the ylast
					# values for hidden text
					if ImageChops.invert(im_word).getbbox() == None:
						word_index[dd] += 1
						continue
					
					# determine the output location
					if dd == 1:
						bbox[0] += output_width
						bbox[2] += output_width
						
					# make sure that words are vertically not parallel to
					# words from a previous same hunk.
					if bbox[1] + yoffset[dd] < max(ylast2):
						yoffset[dd] += max(ylast2) - (bbox[1] + yoffset[dd])

					bbox[1] += yoffset[dd]
					bbox[3] += yoffset[dd]
					
					# if we're at the end of a page, start a new page
					if bbox[3] > output_height:
						save_page()
						output_page += 1
						imcombined = Image.new("RGB", (output_width*2, output_height))
						imcombined_draw = ImageDraw.Draw(imcombined)
						imcombined_draw.rectangle( (0,0)+imcombined.size, fill=(255,255,255) )
						yoffset = [-bbox[1], -bbox[1]]
						ylast = [0, 0]
						ylast2 = [0, 0]
						bbox[1] += yoffset[dd]
						bbox[3] += yoffset[dd]
					elif word_index[dd] == 0:
						yoffset[dd] = -bbox[1]
						bbox[1] += yoffset[dd]
						bbox[3] += yoffset[dd]
					
					# write into the new image
					imcombined.paste(im_word, bbox)
					
					# for changed words, draw an underline
					if op == "#":
						imcombined_draw.line((bbox[0], bbox[3], bbox[2], bbox[3]), fill=(255,0,0))
						
					ylast[dd] = max(ylast[dd], bbox[3])
					
					word_index[dd] += 1
			
				char_index[dd] += oplen[dd]

		save_page()
						
	finally:
		shutil.rmtree(path)
	
	# In order to create a plain-text version of the document, we have
	# to go back to the separate plain-text document content which
	# comes from a different upstream source. The text layer of the
	# PDF produces content that is pretty unreadable because of
	# line numbering in the document.
	
	# load in the plain text
	textcontent = [None, None]
	for d, dd in ((d1, 0), (d2, 1)):
		textcontent[dd] = d.txt
		textcontent[dd] = re.sub("<DELETED>(.*?)</DELETED>", "", textcontent[dd], re.DOTALL)
		textcontent[dd] = textcontent[dd].lower().encode("utf8")
		
	# since the page numbering changed, align the plain text with the
	# PDF text layer's text in order to break up the plain text into the
	# same pagination.
	textcontentpaged = [[], []]
	for dd in (0, 1):
		pos = [0, 0]
		pg = 0
		for op, oplen in diff_by_word(textcontent[dd], doclayout[dd][2].lower()):
			for i in xrange(oplen):
				if pg < len(output_pagination) and output_pagination[pg][dd] == pos[1]:
					textcontentpaged[dd].append("")
					pg += 1
				if op in ("-", "="):
					textcontentpaged[dd][-1] += textcontent[dd][pos[0]]
					pos[0] += 1
				if op in ("+", "="):
					pos[1] += 1

	# now with the plain text of the two documents broken up into the same
	# pagination, compare the plain text of each page separately and created
	# an independent side-by-side representation.
	def fixed_width(txt, width):
		ret = []
		i = 0
		while i < len(txt):
			lf = txt.find("\n", i)
			lf2 = txt.find("\r", i)
			if lf2 >=0 and lf2 < lf: lf = lf2
			if lf >= 0 and lf-i <= width:
				ret.append(txt[i:lf].ljust(width))
				i = lf + 1
			else:
				ret.append(txt[i:i+width].ljust(width))
				i += width
		return ret 
	for pg in xrange(len(output_pagination)-1): # array always has one extra
		text = ""
		lefttext = textcontentpaged[0][pg] if pg < len(textcontentpaged[0]) else ""
		righttext = textcontentpaged[1][pg] if pg < len(textcontentpaged[1]) else ""
		opseq = diff_by_word(lefttext, righttext)
		leftloc = 0
		rightloc = 0
		for op, leftlen, rightlen in simplify_diff(opseq):
			if op == None: continue # range was absorbed into a previous op
			text_cols = 45
			leftlines = fixed_width(lefttext[leftloc:leftloc+leftlen], text_cols)
			rightlines = fixed_width(righttext[rightloc:rightloc+rightlen], text_cols)
			for i in xrange(max(len(leftlines), len(rightlines))):
				text += \
					(leftlines[i] if i < len(leftlines) else " "*text_cols) \
					+ (" %s " % ("|" if op == "=" else "~")) + \
					(rightlines[i] if i < len(rightlines) else " "*text_cols) \
					+ "\n"
			leftloc += leftlen
			rightloc += rightlen
		doc.pages.filter(page=pg+1).update(text=text)

if __name__ == "__main__":
	if len(sys.argv) == 1: # no args
		if not "THREADS" in os.environ:
			pull_text(CURRENT_CONGRESS)
		else:
			threads = int(os.environ["THREADS"])
			from multiprocessing import Process
			procs = []
			for i in range(threads):
				p = Process(target=pull_text, args=[CURRENT_CONGRESS],
					kwargs={"thread_index": i, "thread_count": threads})
				p.start()
			for p in procs:
				p.join()
	
	elif sys.argv[-1] == "validate-toc":
		for p in PositionDocument.objects.filter(toc__isnull=False).only("id", "toc"):
			try:
				json.loads(p.toc)
			except:
				print p.id, p.title
				break_pages(p, force="toc")

	elif sys.argv[1] == "compare":
		prev_p = None
		for p in PositionDocument.objects.filter(bill=sys.argv[2], doctype=100).order_by('created'):
			if prev_p:
				compare_documents(prev_p, p)
			prev_p = p
				
	elif len(sys.argv) == 2:
		break_pages(PositionDocument.objects.get(id=sys.argv[-1]), force="txt")
	
