#!runscript

# Takes all of the batched UserCommentOfflineDeliveryRecord objects
# and generates a PDF of comments to be delivered to Members of Congress.
# It first generates a LaTeX file and then runs xelatex to make the PDF.

# At the bottom of each page, a footer "cover letter" is embedded. On
# one occassion when I embedded the PDF directly, something with the font
# got messed up and FedEx printed garbage. So now the cover letter footer
# is rasterized to a PNG first with:
# pdftoppm -png -cropbox -r 300 popvox/wyr/coverletter.pdf > popvox/wyr/coverletter.png

from django.db.models import Max
from django.core.mail import EmailMultiAlternatives

import datetime, re, shutil, subprocess, sys, tempfile, os.path

from popvox.models import UserCommentOfflineDeliveryRecord, Bill, Org, OrgCampaign
from popvox.govtrack import getMemberOfCongress
from writeyourrep.models import DeliveryRecord, Endpoint
from settings import SERVER_EMAIL

buildings = {
	"cannon": "house",
	"dirksen": "senate",
	"hart": "senate",
	"longworth": "house",
	"rayburn": "house",
	"russell": "senate"
	}

def create_tex(tex, serial):
	batch_max = 0

	outfile_ = open(tex, "w")
	
	class O:
		pass

	outfile = O()
	outfile.write = lambda x : outfile_.write(x.encode("utf8", "replace"))
	def escape_latex(x):
		if not isinstance(x, (str, unicode)): raise ValueError(type(x))
		# Break up long sequences of otherwise unbreakable characters with soft hyphens,
		# which just show up as hyphens so we replace then with LaTeX discretionary breaks below.
		# First try to break after non-word characters, but then break anywhere.
		# We do this first because we don't want to break up any LaTeX commands.
		x = re.sub(r"(\S{15}\W)(\S{15})", r"\1" + u"\u00AD" + r"\2", x)
		x = re.sub(r"(\S{15})(\S{15})", r"\1" + u"\u00AD" + r"\2", x)
		
		# Escape special characters.
		x = x.replace("\\", r"\\").replace("#", r"\#").replace("$", r"\$").replace("%", r"\%").replace("&", r"\&").replace("~", r"\~{}").replace("_", r"\_").replace("^", r"\^").replace("{", r"\{").replace("}", r"\}").replace(u"\u00AD", r"\discretionary{}{}{}")
		
		# Smart quotes.
		x = re.sub(r'(\s)"', r'\1' + u"\u201C", x)
		x = re.sub(r"(\s)'", r'\1' + u"\u2018", x)
		x = re.sub(r'"', u"\u201D", x)
		x = re.sub(r"'", u"\u2019", x)
		
		return x
		
	outfile.write_esc = lambda x : outfile.write(escape_latex(x))
	
	outfile.write(r"\documentclass[twocolumn,notitlepage]{report}" + "\n")
	outfile.write(r"\usepackage[top=1in, bottom=3.20in, left=.85in, right=.85in]{geometry}" + "\n")
	outfile.write(r"\pagestyle{myheadings}" + "\n")
	outfile.write(r"\usepackage{fontspec}" + "\n")
	outfile.write(r"\setromanfont[BoldFont={* Bold}]{Linux Libertine O}" + "\n")
	outfile.write(r"\usepackage{pdfpages}")
	
	outfile.write(r"\usepackage{graphicx}" + "\n")
	outfile.write(r"\makeatletter" + "\n")
	outfile.write(r"\AddToShipoutPicture{" + "\n")
	outfile.write(r"            \setlength{\@tempdimb}{0in}" + "\n")
	outfile.write(r"            \setlength{\@tempdimc}{0in}" + "\n")
	outfile.write(r"            \setlength{\unitlength}{1pt}" + "\n")
	outfile.write(r"            \put(\strip@pt\@tempdimb,\strip@pt\@tempdimc){" + "\n")
	outfile.write(r"        \includegraphics[width=8.5in]{" + os.path.abspath(os.path.dirname(__file__) + "/coverletter.png") + r"}" + "\n")
	outfile.write(r"            }" + "\n")
	outfile.write(r"}" + "\n")
	outfile.write(r"\makeatother" + "\n")
	
	outfile.write(r"\begin{document}" + "\n")
	
	targets = []
	for t in UserCommentOfflineDeliveryRecord.objects.values('target', 'batch').distinct():
		targets.append((t["target"], t["batch"]))
	def get_address_sort(id_batch):
		addr = getMemberOfCongress(id_batch[0])["address"]
		addr = addr.split(" ")
		return (buildings[addr[1].lower()], addr[1], addr[0].zfill(5))
	targets.sort(key = get_address_sort)
	
	targets2 = []
	
	for govtrack_id, batch in targets:
		topics_in_batch = UserCommentOfflineDeliveryRecord.objects.filter(target=govtrack_id, batch=batch).values("comment__bill", "comment__position").distinct()
		
		if batch != None:
			batch_no = batch
		else:
			# if there are only comments without messages, skip this office
			if not topics_in_batch.filter(comment__message__isnull=False).exists():
				continue
			
			batch_max += 1
			batch_no = serial + ":" + str(batch_max)
			
		target_errors = {}
		targets2.append( (govtrack_id, batch_no, target_errors) )
		
		#if getMemberOfCongress(govtrack_id)["type"] == "sen":
		#	hs = "senate"
		#elif getMemberOfCongress(govtrack_id)["type"] == "rep":
		#	hs = "house"
		#else:
		#	raise ValueError()
		###outfile.write(r"\includepdf[noautoscale]{" + os.path.abspath(os.path.dirname(__file__) + "/coverletter_" + hs + ".pdf") + r"}" + "\n")
		
		header = getMemberOfCongress(govtrack_id)["name"] + "\t" + "(batch " + batch_no + ")"
		outfile.write(r"\markboth{")
		outfile.write_esc(header)
		outfile.write(r"}{")
		outfile.write_esc(header)
		outfile.write(r"}" + "\n")

		outfile.write(r"{\Large \bf \noindent ")
		outfile.write_esc(getMemberOfCongress(govtrack_id)["name"])
		outfile.write(r"} \bigskip" + "\n\n" + r"\noindent ")

		outfile.write_esc(getMemberOfCongress(govtrack_id)["address"])
		outfile.write(r"\bigskip" + "\n\n" + r"\noindent ")

		outfile.write(r"\bigskip" + "\n\n")
		
		use_pagebreaks = topics_in_batch.count() < 10
		
		for t2 in topics_in_batch.order_by("comment__bill", "comment__position"):
			position = t2["comment__position"]
			bill = Bill.objects.get(id=t2["comment__bill"])

			comments_in_topic = UserCommentOfflineDeliveryRecord.objects.filter(target=govtrack_id, batch=batch, comment__bill=bill, comment__position=position).select_related("comment")
			
			# if there are only comments without messages, skip this group
			if not comments_in_topic.filter(comment__message__isnull=False).exists():
				continue

			outfile.write(r"\hrule\bigskip" + "\n\n")
			outfile.write(r"{\large \bf \noindent ")
			if position == "+": outfile.write_esc("Support: ")
			if position == "-": outfile.write_esc("Oppose: ")
			outfile.write_esc(bill.title)
			outfile.write(r"}")
			
			outfile.write(r"\\ {\small ")
			outfile.write_esc("http://popvox.com" + bill.url() + "/report")
			outfile.write("}\n\n\\bigskip")
			
			for t3 in comments_in_topic:
				# Move this into the new batch number if it's not in a numbered batch.
				if batch == None:
					t3.batch = batch_no
					t3.save()
				
				comment = t3.comment
				address = comment.address

				fr = t3.failure_reason
				if fr == "bad-webform": # get our comment from the Endpoint notes field
					endpoints = Endpoint.objects.filter(govtrackid=govtrack_id, office=getMemberOfCongress(govtrack_id)["office_id"], method=Endpoint.METHOD_NONE)
					if len(endpoints) > 0:
						fr = endpoints[0].notes
				target_errors[fr] = True
				
				#outfile.write("\n\n" + r"\hspace{.75in}\rule{1.75in}{.075mm}" + "\n\n" + r"\bigskip" + "\n\n")
				outfile.write(r"\noindent ")
				outfile.write_esc(address.nameprefix + " " + address.firstname + " " + address.lastname + " " + address.namesuffix)
				outfile.write(r"\hfill ")
				outfile.write_esc(comment.user.email)
				outfile.write(r"\\\nopagebreak" + "\n")
				outfile.write_esc(address.address1)
				outfile.write(r"\hfill ")
				outfile.write_esc(address.phonenumber)
				outfile.write(r"\\\nopagebreak" + "\n")
				if address.address2 != "":
					outfile.write_esc(address.address2)
					outfile.write(r"\\\nopagebreak" + "\n")
				outfile.write_esc(address.city + ", " + address.state + " " + address.zipcode)
				outfile.write(r"\hfill ")
				outfile.write_esc(comment.updated.strftime("%x"))
				#outfile.write(r"\\\nopagebreak" + "\n")
				#outfile.write_esc(comment.updated.strftime("%x"))
				outfile.write(r"\\\nopagebreak" + "\n\n" + r"\nopagebreak { \small ")
			
				if comment.message:
					outfile.write_esc(comment.message)
					outfile.write("\n\n")
				else:
					outfile.write(r"(no comment)")
					outfile.write("} \n\n\\bigskip")
					continue # don't show referring org info
				
				for referrer in comment.referrers():
					if isinstance(referrer, Org):
						outfile.write(r"{\it ")
						outfile.write_esc("(This individual was referred by " + referrer.name + ", ")
						if referrer.website == None:
							outfile.write_esc("http://popvox.com" + referrer.url())
						else:
							outfile.write_esc(referrer.website)
						outfile.write_esc(")")
						outfile.write(r"}")
						outfile.write("\n\n\\bigskip")
					elif isinstance(referrer, OrgCampaign):
						outfile.write(r"{\it ")
						outfile.write_esc("(This individual was referred by " + referrer.org.name + ", ")
						if referrer.website_or_orgsite() == None:
							outfile.write_esc("http://popvox.com" + referrer.url())
						else:
							outfile.write_esc(referrer.website_or_orgsite())
						outfile.write_esc(")")
						outfile.write(r"}")
						outfile.write("\n\n\\bigskip")
				
				outfile.write("} \n\n\\bigskip")
				
			# clear page after each "topic", i.e. bill and support oppose
			if use_pagebreaks:
				outfile.write(r"\clearpage" + "\n")
			else:
				outfile.write(r"\bigskip" + "\n\n")
				
		if not use_pagebreaks: # pagebreak before next office
			outfile.write(r"\clearpage" + "\n")

	outfile.write(r"\clearpage" + "\n")
	outfile.write(r"\markboth{Hit Sheet " + serial + "r}{Hit Sheet " + serial + r"}" + "\n")
	outfile.write(r"\noindent ")
	for govtrack_id, batch_no, target_errors in targets2:
		p = getMemberOfCongress(govtrack_id)
		outfile.write_esc("#" + batch_no[len(serial)+1:])
		outfile.write(r" --- ")
		outfile.write_esc(p["lastname"] + " " + p["state"] + (str(p["district"]) if p["district"]!=None else ""))
		outfile.write(r"  --- ")
		outfile.write_esc(" ".join(p["address"][0:10].split(" ")[0:2]))
		outfile.write(r"  --- ")
		outfile.write_esc(str(UserCommentOfflineDeliveryRecord.objects.filter(target=govtrack_id, batch=batch_no).count()) + " ")
		outfile.write_esc(", ".join([k for k in target_errors if k not in ("no-method",)]))
		outfile.write(r" \\" + "\n")
	
	outfile.write(r"\end{document}" + "\n")
	
	outfile_.close()
	
if len(sys.argv) == 2 and sys.argv[1] == "resetbatchnumbers":
	UserCommentOfflineDeliveryRecord.objects.all().update(batch=None)
elif len(sys.argv) == 3 and sys.argv[1] == "kill":
	if sys.argv[2] == "all":
		UserCommentOfflineDeliveryRecord.objects.all().delete()
	else:
		UserCommentOfflineDeliveryRecord.objects.filter(batch = sys.argv[2]).delete()
elif len(sys.argv) >= 3 and sys.argv[1] == "delivered":
	recs = UserCommentOfflineDeliveryRecord.objects.filter(batch__isnull = False)
	if sys.argv[2] != "all":
		b = []
		for c in sys.argv[2:]:
			b.extend(re.split(r"\s+", c))
		b = [c for c in b if c.strip() != ""]
		recs = recs.filter(batch__in = b)
	for ucodr in recs:
		dr = DeliveryRecord()
		dr.target = Endpoint.objects.get(govtrackid=ucodr.target.id, office=getMemberOfCongress(ucodr.target.id)["office_id"])
		dr.trace = "comment #" + unicode(ucodr.comment.id) + " delivered via paper copy\nbatch " + ucodr.batch + "\n"
		dr.success = True
		dr.failure_reason = DeliveryRecord.FAILURE_NO_FAILURE
		dr.method = Endpoint.METHOD_INPERSON
		dr.save()
		
		try:
			prev_dr = ucodr.comment.delivery_attempts.get(target__govtrackid = ucodr.target.id, next_attempt__isnull = True)
			prev_dr.next_attempt = dr
			prev_dr.save()
		except DeliveryRecord.DoesNotExist:
			pass
		
		ucodr.comment.delivery_attempts.add(dr)
		print ucodr.comment

		ucodr.delete()
		
elif len(sys.argv) == 2 and sys.argv[1] == "pdf":
	# delete UCDOR objects for mail that has since been delivered
	for uc in UserCommentOfflineDeliveryRecord.objects.all():
		if uc.comment.delivery_attempts.filter(target__govtrackid=uc.target.id, success=True).exists():
			uc.delete()
	
	# delete UCDOR objects for mail that has since had an address marked not to deliver
	for uc in UserCommentOfflineDeliveryRecord.objects.filter(comment__address__flagged_hold_mail=True):
		uc.delete()
		
	# delete UCDOR objects that are targetting reps that we no longer need to target because
	# e.g. the district changed because of a district disagreement.
	for uc in UserCommentOfflineDeliveryRecord.objects.all().select_related("comment", "comment__address", "target"):
		recips = uc.comment.get_recipients()
		if not recips or not uc.target.id in [r["id"] for r in recips]:
			uc.delete()
			
	# generate and email the pdf
	serial = datetime.datetime.now().strftime("%Y-%m-%dT%H%M")
	path = tempfile.mkdtemp()
	try:
		tex = path + '/comments.tex'
		create_tex(tex, serial)
		
		subprocess.call(["xelatex", tex], cwd=path)
		
		# don't make this file publicly accessible!
		#subprocess.call(["cp", tex.replace(".tex", ".pdf"), 'httproot/files/messages_' + serial + '.pdf'])
		
		with open(tex.replace(".tex", ".pdf"), 'rb') as f:
			msg = EmailMultiAlternatives("User Messages Delivery PDF",
				"",
				SERVER_EMAIL,
				["josh@popvox.com"])
			msg.attach('messages_' + serial + '.pdf', f.read(), "application/pdf")
			msg.send()
			
		#print "Done."
		#sys.stdin.readline()
	finally:
		#print path
		shutil.rmtree(path)

else:
	print UserCommentOfflineDeliveryRecord.objects.filter(batch__isnull = False).count(), "messages printed"
	
	batches = UserCommentOfflineDeliveryRecord.objects.filter(batch__isnull = False).values_list("batch", flat=True).distinct()
	batches = list(batches)
	batches.sort(key = lambda x : (x.split(":")[0], int(x.split(":")[1])))
	for b in batches:
		print b
		
