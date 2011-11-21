#!runscript

# Fetches new bill text documents from GPO and pre-generates page
# images for our iPad app.

import os, sys, base64, re, urllib, urllib2, json, math
from lxml import etree
from StringIO import StringIO
from django.template.defaultfilters import truncatewords

from settings import DATADIR

from popvox.govtrack import CURRENT_CONGRESS

from popvox.models import Bill, PositionDocument, DocumentPage
	
def fetch_page(url, args=None, method="GET", decode=False):
	if method == "GET" and args != None:
		url += "?" + urllib.urlencode(args).encode("utf8")
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
	if DocumentPage.objects.filter(document__bill=bill, document__doctype=100, document__key=billstatus, document__txt__isnull=False, document__pdf_url__isnull=False, document__pages__png__isnull=False).exists():
		return
		
	existing_records = list(PositionDocument.objects.filter(bill = bill, doctype = 100, key = billstatus))
	while len(existing_records) > 1:
		existing_records[0].delete()
	
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
	
	if isnew or not d.title:
		mods = fetch_page(re.sub("/pdf.*", "/mods.xml", d.pdf_url))
		mods = etree.fromstring(mods)
		
		ns = { "m": "http://www.loc.gov/mods/v3" }
		
		title = mods.xpath('string(m:titleInfo[@type="alternative"]/m:title)', namespaces=ns)
		if not title:
			title = mods.xpath('string(m:extension/m:searchTitle)', namespaces=ns)
		if not title:
			printthread()
			print "bill title not found in MODS", m
			return
		title = unicode(title) # force lxml object to unicode, otherwise it isn't handled right in Django db layer
		
		date = mods.xpath('string(m:originInfo/m:dateIssued)', namespaces=ns)

		d.title = title
		d.created = date # set if isnew
		d.updated = date # set if isnew
		
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
	
	def printstatus():
		printthread()
		print "fetched", m, " ".join(what_did_we_fetch), "document_id="+str(d.id), "bill_id="+str(bill.id)

	if len(what_did_we_fetch) > 0 or "THREADS" not in os.environ:
		printstatus()

	if d.toc != None and DocumentPage.objects.filter(document=d, png__isnull=False, pdf__isnull=False, text__isnull=False).exists():
		return

	if len(what_did_we_fetch) == 0 and "THREADS" in os.environ:
		printstatus()

	break_pages(d, thread_index=thread_index)
		
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
			
			diff = diff_match_patch.diff(dtext, text)
			
			pages = [""]
			lctr = 0
			rctr = 0
			for (op, length) in diff:
				if op in ("-", "="):
					pages[-1] += dtext[lctr:lctr+length]
					lctr+=length
				if op in ("+","="):
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
			text = f.read() # utf-8, binary string
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
					info["tree_serialized"] += node.text.encode("utf8") + " "
				for child in node:
					serialize_node(child, level+(1 if label else 0), info)
				
			info = { "section_headings": [], "tree_serialized": "" }
			serialize_node(tree, 0, info)
			
			diff = diff_match_patch.diff(info["tree_serialized"], text)
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
	# Creates a comparison of two documents, from d1's perspective
	# where it matters (including filing it under d1's bill).
	
	doc, isnew = PositionDocument.objects.get_or_create(
		bill = d1.bill,
		doctype = 101,
		key = "cmp:" + d1.key + "," + d2.key)
	
	doc.title = "Comparison: " + d1.title + " and " + d2.title
	doc.save()
	
	print doc.id, doc.key, d1.id, d2.id
	
	doc.pages.all().delete()
	
	# compare the texts of the two documents
	
	# serialize the text content, keeping track of page numbers
	def serialize_pages(d):
		pages = []
		text = ""
		for p in d.pages.order_by('page'):
			if not p.text: raise ValueError("Text is not available for document " + unicode(d) + ".")
			pages.append(len(text))
			text += p.text.encode("utf8")
		return text, pages
	d1text, d1pages = serialize_pages(d1)
	d2text, d2pages = serialize_pages(d2)
	
	# split the output so that the pages have approximately
	# the same number of characters per page as the input
	chars_per_page = (len(d1text) + len(d2text)) / (len(d1pages) + len(d2pages))

	# do the comparison
	import diff_match_patch
	diff = diff_match_patch.diff(d1text, d2text)

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
	
	# Generate text output.
	leftloc = 0
	rightloc = 0
	for op, leftlen, rightlen in opseq:
		if op == None: continue # range was absorbed into a previous op
		width = 35
		leftlines = fixed_width(d1text[leftloc:leftloc+leftlen], width)
		rightlines = fixed_width(d2text[rightloc:rightloc+rightlen], width)
		for i in xrange(max(len(leftlines), len(rightlines))):
			#print \
			#	(leftlines[i] if i < len(leftlines) else " "*width), \
			#	op, \
			#	(rightlines[i] if i < len(rightlines) else " "*width)
			pass
		leftloc += leftlen
		rightloc += rightlen

	# Generate image output. (With a PDF modifying tool, this could
	# be adapted to generate PDF output.)
	
	# Serialize the documents layout information.
	import base64, tempfile, subprocess, shutil
	path = tempfile.mkdtemp()
	doclayout = [None, None]
	try:
		for d, dd in ((d1, 0), (d2, 1)):
			# use pdftotext to get the coordinates of bounding boxes
			# around each word in the document.
			
			pdf = open(path + ("/document%d.pdf" % dd), "w")
			pdf.write(base64.decodestring(d.pdf))
			pdf.close()
			
			subprocess.call(["pdftotext", "-bbox", "-enc", "UTF-8", path + ("/document%d.pdf" % dd)], cwd=path) # poppler-utils package
			f = open(path + ("/document%d.html" % dd))
			xhtml = f.read() # utf-8, binary string
			f.close()
			
			# read in the coordinates and serialize the information
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
				
				for node2 in node.xpath("xhtml:word", namespaces=ns):
					startchar.append(len(text))
					wordcoord.append( (pagenum, (float(node2.attrib["xMin"])/page_width, float(node2.attrib["yMin"])/page_height), (float(node2.attrib["xMax"])/page_width, float(node2.attrib["yMax"])/page_height)) )
						# remove hyphens because it causes a change
						# at any word that changes in line wrapping
					t = node2.text
					if t.endswith("-"):
						t = t[0:-1]
					else:
						t += " "
					text += t.encode("utf8")
				pagenum += 1
			doclayout[dd] = (startchar, wordcoord, text)
	finally:
		shutil.rmtree(path)

	# align the two text outputs
	diff = diff_match_patch.diff(doclayout[0][2], doclayout[1][2])
	opseq = simplify_diff(diff)
	
	# construct output
	output_width = 512
	output_height = int(output_width * 11/8.5)
	path = tempfile.mkdtemp()
	pgfn = {}
	try:
		for d, dd in ((d1, 0), (d2, 1)):
			# extract images from each source PDF
			pdf = open(path + ("/document%d.pdf" % dd), "w")
			pdf.write(base64.decodestring(d.pdf))
			pdf.close()
			subprocess.call(["pdftoppm", "-scale-to-x", str(output_width), "-scale-to-y", str(int(output_width*11/8.5)), "-png", path + ("/document%d.pdf" % dd), path + ("/page-%d" % dd)], cwd=path) # poppler-utils package

			# map page numbers to file names
			import glob
			for fn in glob.glob(path + ("/page-%d-*.png" % dd)):
				pagenum = int(fn[len(path)+8:-4])
				pgfn[str(dd) + ":" + str(pagenum)] = fn
			
		# construct a new image that shows the documents side by
		# side with their alignment.
		
		from PIL import Image, ImageDraw
		imcombined = Image.new("RGB", (output_width*2, output_height))
		imcombined_draw = ImageDraw.Draw(imcombined)
		imcombined_draw.rectangle( (0,0)+imcombined.size, fill=(255,255,255) )
		
		ylast = [0, 0]
		ylast2 = [0, 0]
		yoffset = [0, 0]
		char_index = [0, 0]
		word_index = [0, 0]
		chars_since_break = 0
		im = [None, None]
		im_page = [None, None]
		lines = []
		output_page = 1
		def save_page():
			dp, isnew = DocumentPage.objects.get_or_create(document=doc, page=output_page)
			buf = StringIO()
			imcombined.save(buf, "png")
			dp.png = base64.encodestring(buf.getvalue())
			dp.save()
			print doc.id, output_page

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
					
					if pagenum > 2: break
					
					# open the page image containing the word
					if im_page[dd] != pagenum:
						im[dd] = Image.open(pgfn[str(dd) + ":" + str(pagenum)])
						im_page[dd] = pagenum
						
						# force a re-alignment
						ylast2 = list(ylast) # clone
						yoffset[dd] += 20 # space out
					
					# get an image instance cropped to that word
					bbox = [int(bbox_min[0]*im[dd].size[0]), int(bbox_min[1]*im[dd].size[1]), int(bbox_max[0]*im[dd].size[0]), int(bbox_max[1]*im[dd].size[1])]
					im_word = im[dd].crop(bbox)
					
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
		for p in PositionDocument.objects.filter(bill=sys.argv[2]).order_by('created'):
			if prev_p:
				compare_documents(prev_p, p)
				break
			prev_p = p
				
	elif len(sys.argv) == 2:
		break_pages(PositionDocument.objects.get(id=sys.argv[-1]), force="png")
	
