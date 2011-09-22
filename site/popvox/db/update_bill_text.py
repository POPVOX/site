#!runscript

# Fetches new bill text documents from GPO and pre-generates page
# images for our iPad app.

import os, sys, base64, re, urllib, urllib2, json
from lxml import etree
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

def pull_text(congressnumber, thread_index=None, thread_count=None):
	bill_list = fetch_page("http://frwebgate.access.gpo.gov/cgi-bin/BillBrowse.cgi",
		{	"dbname": str(congressnumber) + "_cong_bills",
			"wrapperTemplate": "all" + str(congressnumber) + "bills_wrapper.html",
			"billtype": "all" })
	
	for m in re.findall(r"cong_bills&docid=f:([a-z]+)(\d+)([a-z][a-z0-9]+)\.txt\s*\"", bill_list):
		billtype, billnumber, billstatus = m

		if thread_count != None:
			if int(billnumber) % thread_count != thread_index:
				continue

		try:
			pull_bill_text(congressnumber, billtype, billnumber, billstatus, thread_index=thread_index)
		except Exception as e:
			print "error in ", thread_index, m, e
		
def pull_bill_text(congressnumber, billtype, billnumber, billstatus, thread_index=None):
	m = (congressnumber, billtype, billnumber, billstatus)

	def printthread():
		if thread_index != None:
			print thread_index,
	
	# our bill status codes match the GPO Access status codes
	try:
		bill = Bill.objects.get(congressnumber=congressnumber, billtype=billtype, billnumber=billnumber, vehicle_for=None)
	except Bill.DoesNotExist:
		printthread()
		print "invalid bill", m
		return
		
	# check if we have this document already and have pages loaded
	if DocumentPage.objects.filter(document__bill=bill, document__doctype=100, document__key=billstatus, document__txt__isnull=False, document__pdf_url__isnull=False, document__pages__png__isnull=False).exists():
		return
		
	bill_type_map = {
		"h": "HR",
		's': 'S',
		'hj': 'HJRES',
		'sj': 'SJRES',
		'hc': 'HCONRES',
		'sc': 'SCONRES',
		'hr': 'HRES',
		'sr': 'SRES',
	}
	
	billtype = bill_type_map[billtype] # map bill type to FDSys citationsearch
	
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
	
	if not d.pdf_url:
		pdf_info = fetch_page("http://www.gpo.gov/fdsys/search/citation2.result.CB.action",
			{	"congressionalBills.congress": congressnumber,
				"congressionalBills.billType": billtype,
				"congressionalBills.billNumber": billnumber,
				"congressionalBills.billVersion": billstatus.upper(),
				"publication": "BILLS",
				"action:citation2.result.CB": "Retrieve Document"
			})
		
		n = re.search(r'url = "(http://www.gpo.gov:80/fdsys/pkg/BILLS-[^/]*/pdf/BILLS-[^\.]*.pdf)";', pdf_info)
		if n == None:
			printthread()
			print "no bill text", m
			return
		d.pdf_url = n.group(1)
		what_did_we_fetch.append("url")
	
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
	# Generate PNG, text, and HTML representations of the pages in the PDF for
	# fast access by the iPad app.
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
		
		if (not document.pages.filter(png__isnull=False).exists() and not document.pages.filter(pdf__isnull=False).exists()) or force in ("all", "png", "pdf"):
			status("bursting...")
			
			#subprocess.call(["perl", "/usr/bin/pdfcrop", path + "/document.pdf"], cwd=path) # latex package
				# if we do this, then the output size (scale-to-x/y) needs to be
				# adjusted because of an arbitrary aspect ratio that might come out,
				# also the filename shifts
			
			# generate PNGs for each page
			
			subprocess.call(["pdftoppm", "-scale-to-x", "768", "-scale-to-y", "994", "-png", path + "/document.pdf", path + "/page"], cwd=path) # poppler-utils package
			
			# zealously crop the resulting images, but crop the images the same way. so, we have to
			# scan each image to see the minimum of the zealous crops.
			extents = [None, None, None, None]
			from PIL import Image, ImageChops
			for fn in glob.glob(path + "/page-*.png"):
				im = Image.open(fn)
				im = ImageChops.invert(im) # make white black (i.e zeroes)
				bb = im.getbbox() # returns bounding box that excludes zero pixels
				if bb:
					for i in xrange(4):
						if extents[i] == None or bb[i] < extents[i]: extents[i] = bb[i]
			
			# generate PDFs for each page
			
			subprocess.call(["pdftk", path + "/document.pdf", "burst", "compress"], cwd=path) # pdftk package
	
			# load each PNG/PDF into the database
	
			max_page = 0
	
			for fn in glob.glob(path + "/page-*.png"):
				pagenum = int(fn[len(path)+6:-4])
				
				# use graphicsmagick mogrify to crop convert the PNG to greyscale (to reduce file size),
				# overwriting the file in place.
				subprocess.call(["gm", "mogrify"] + (["-crop", "%dx%d+%d+%d" % (extents[2]-extents[0], extents[3]-extents[1], extents[0], extents[1])] if extents else []) + ["-type", "Grayscale", fn]) # "-trim", 
				
				pngfile = open(fn)
				png = pngfile.read()
				pngfile.close()
				
				ppdffile = open(path + "/pg_%04d.pdf" % pagenum)
				ppdf = ppdffile.read()
				ppdffile.close()
	
				dp, isnew = DocumentPage.objects.get_or_create(document = document, page = pagenum)
				dp.png = base64.encodestring(png)
				dp.pdf = base64.encodestring(ppdf)
				dp.save()
				
				if pagenum > max_page: max_page = pagenum
	
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
			
			from lxml import etree
			from StringIO import StringIO
			
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

	elif len(sys.argv) == 2:
		break_pages(PositionDocument.objects.get(id=sys.argv[-1]), force="png")
	
