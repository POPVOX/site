#!runscript

# Fetches new bill text documents from GPO and pre-generates page
# images for our iPad app.

import sys, base64, re, urllib, urllib2, json
from lxml import etree
from django.template.defaultfilters import truncatewords

from settings import DATADIR

from popvox.govtrack import CURRENT_CONGRESS

from popvox.models import Bill, PositionDocument, DocumentPage
	
def fetch_page(url, args=None, method="GET"):
	if method == "GET" and args != None:
		url += "?" + urllib.urlencode(args).encode("utf8")
	req = urllib2.Request(url)
	resp = urllib2.urlopen(req)
	if resp.getcode() != 200:
		raise Exception("Failed to load page: " + url)
	return resp.read()

def pull_text(congressnumber):
	bill_list = fetch_page("http://frwebgate.access.gpo.gov/cgi-bin/BillBrowse.cgi",
		{	"dbname": str(congressnumber) + "_cong_bills",
			"wrapperTemplate": "all" + str(congressnumber) + "bills_wrapper.html",
			"billtype": "all" })
	
	for m in re.findall(r"cong_bills&docid=f:([a-z]+)(\d+)([a-z][a-z0-9]+)\.txt\s*", bill_list):
		billtype, billnumber, billstatus = m
		
		pull_bill_text(congressnumber, billtype, billnumber, billstatus)
		
def pull_bill_text(congressnumber, billtype, billnumber, billstatus):
	m = (congressnumber, billtype, billnumber, billstatus)
	
	# our bill status codes match the GPO Access status codes
	try:
		bill = Bill.objects.get(congressnumber=congressnumber, billtype=billtype, billnumber=billnumber, vehicle_for=None)
	except Bill.DoesNotExist:
		print "invalid bill", m
		return
		
	# check if we have this document already
	if PositionDocument.objects.filter(bill=bill, doctype=100, key=billstatus).exists():
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
		print "no bill text", m
		return
		
	pdf_url = n.group(1)

	mods = fetch_page(re.sub("/pdf.*", "/mods.xml", pdf_url))
	mods = etree.fromstring(mods)
	
	ns = { "m": "http://www.loc.gov/mods/v3" }
	
	title = mods.xpath('string(m:titleInfo[@type="alternative"]/m:title)', namespaces=ns)
	if not title:
		title = mods.xpath('string(m:extension/m:searchTitle)', namespaces=ns)
	if not title:
		print "bill title not found in MODS", m
		return
		
	date = mods.xpath('string(m:originInfo/m:dateIssued)', namespaces=ns)

	pdf = fetch_page(pdf_url)
	
	text = fetch_page(pdf_url.replace("/pdf/", "/html/").replace(".pdf", ".htm"))
	text = text.replace("<html><body><pre>\n", "").replace("</pre></body></html>", "").decode("utf8")
	text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

	xml = fetch_page(pdf_url.replace("/pdf/", "/xml/").replace(".pdf", ".xml"))
	
	d = PositionDocument.objects.create(
		bill=bill,
		doctype=100,
		key=billstatus,
		title=title,
		pdf=base64.encodestring(pdf),
		txt=text,
		xml=base64.encodestring(xml)
		)
	d.created = date
	d.updated = date
	d.save()
	
	print "fetched", m, "PDF size:", len(pdf), "document id:", d.id, "bill id:", bill.id

	break_pages(d)
		
def break_pages(document):
	# Generate PNG, text, and HTML representations of the pages in the PDF for
	# fast access by the iPad app.
	if document.pdf == None: raise ValueError("I don't have PDF data.")
	
	document.pages.all().delete()
	
	document.toc = None
	document.save()
	
	import base64, tempfile, subprocess, shutil, glob
	path = tempfile.mkdtemp()
	try:
		pdf = open(path + "/document.pdf", "w")
		pdf.write(base64.decodestring(document.pdf))
		pdf.close()
		
		#subprocess.call(["perl", "/usr/bin/pdfcrop", path + "/document.pdf"], cwd=path) # latex package
			# if we do this, then the output size (scale-to-x/y) needs to be
			# adjusted because of an arbitrary aspect ratio that might come out,
			# also the filename shifts
		
		# generate PNGs
		
		subprocess.call(["pdftoppm", "-scale-to-x", "768", "-scale-to-y", "994", "-png", path + "/document.pdf", path + "/page"], cwd=path) # poppler-utils package
		
		for fn in glob.glob(path + "/page-*.png"):
			pagenum = int(fn[len(path)+6:-4])
			
			pngfile = open(fn)
			png = pngfile.read()
			pngfile.close()
			
			DocumentPage.objects.create(
				document = document,
				page = pagenum,
				png = base64.encodestring(png))
		
		# generate text
		
		# While the GPO text file has good layout, it doesn't indicate page boundaries.
		# To get page boundaries, we compare the text to the result of pdftext on the PDF
		# and look for \x0C new page characters.
		
		subprocess.call(["pdftotext", "-layout", "-enc", "UTF-8", path + "/document.pdf"], cwd=path) # poppler-utils package
		f = open(path + "/document.txt")
		text = f.read() # utf-8, binary string
		f.close()
		
		dtext = document.txt.encode("utf8")
		
		import diff_match_patch
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
			
		# generate table of contents
		
		# To make a table of contents, we look at the XML document structure and match that
		# against the page-by-page text.
			
		if document.xml:
			from lxml import etree
			from StringIO import StringIO
			tree = etree.parse(StringIO(base64.decodestring(document.xml))).getroot()
			
			def serialize_node(node, level, info):
				label = None
				if node.tag in ('chapter','division','header', 'part', 'section','subchapter', 'subdivision', 'subheader', 'subpart', 'subsection', 'subtitle', 'title'):
					label = ""
					for child in node.iterdescendants():
						if child.text:
							label = truncatewords(label + (" " if len(label) > 0 else "") + child.text, 10)
							if "..." in label or len(label) > 64:
								break
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
				while next_section < len(info["section_headings"]) and (lctr <= info["section_headings"][next_section][0] < (lctr+length)):
					s = info["section_headings"][next_section]
					sections.append( { "page": pagenum, "indentation": s[1], "label": s[2] } )
					next_section += 1
				if next_section == len(info["section_headings"]):
					break
				
				if op in ("-", "="):
					lctr += length
				if op in ("+", "="):
					pagenum += text.count("\x0C", rctr, rctr+length)
					rctr += length
			
			document.toc = json.dumps(sections)
			document.save()
			
	finally:
		shutil.rmtree(path)
		

if __name__ == "__main__":
	if len(sys.argv) == 1: # no args
		pull_text(CURRENT_CONGRESS)

	if len(sys.argv) == 2:
		break_pages(PositionDocument.objects.get(id=sys.argv[-1]))
	
