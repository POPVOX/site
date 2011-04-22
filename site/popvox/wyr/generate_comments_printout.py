#!runscript

# Takes all of the batched UserCommentOfflineDeliveryRecord objects
# and generates a PDF of comments to be delivered to Members of Congress.
# It first generates a LaTeX file.

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
		x = re.sub(r"(\S{15})(\S{15})", r"\1" + u"\u00AD" + r"\2", x) # break up long sequences of otherwise unbreakable characters with soft hyphens, which just show up as hyphens so we replace then with LaTeX discretionary breaks below 
		x = x.replace("\\", r"\\").replace("#", r"\#").replace("$", r"\$").replace("%", r"\%").replace("&", r"\&").replace("~", r"\~").replace("_", r"\_").replace("^", r"\^").replace("{", r"\{").replace("}", r"\}").replace(u"\u00AD", r"\discretionary{}{}{}")
		x = re.sub(r'(\s)"', r'\1' + u"\u201C", x)
		x = re.sub(r"(\s)'", r'\1' + u"\u2018", x)
		x = re.sub(r'"', u"\u201D", x)
		x = re.sub(r"'", u"\u2019", x)
		return x
		
	outfile.write_esc = lambda x : outfile.write(escape_latex(x))
	
	outfile.write(r"\documentclass[twocolumn,notitlepage]{report}" + "\n")
	outfile.write(r"\usepackage[top=1in, bottom=1in, left=1in, right=1in]{geometry}" + "\n")
	outfile.write(r"\pagestyle{myheadings}" + "\n")
	outfile.write(r"\usepackage{fontspec}" + "\n")
	outfile.write(r"\setromanfont{Linux Libertine O}" + "\n")
	outfile.write(r"\usepackage{pdfpages}")
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
		if batch != None:
			batch_no = batch
		else:
			# Don't create a new batch for this target if there are fewer than three messages to
			# deliver and they were all written in the last two weeks.
			#if UserCommentOfflineDeliveryRecord.objects.filter(target=govtrack_id, batch_number=batch).count() < 3 and UserCommentOfflineDeliveryRecord.objects.filter(target=govtrack_id, batch_number=batch, comment__created__lt=datetime.datetime.now() - datetime.timedelta(days=14)).count() == 0:
			#	continue
			
			batch_max += 1
			batch_no = serial + ":" + str(batch_max)
			
		target_errors = {}
		targets2.append( (govtrack_id, batch_no, target_errors) )
		
		if getMemberOfCongress(govtrack_id)["type"] == "sen":
			hs = "senate"
		elif getMemberOfCongress(govtrack_id)["type"] == "rep":
			hs = "house"
		else:
			raise ValueError()
		###outfile.write(r"\includepdf[noautoscale]{" + os.path.abspath(os.path.dirname(__file__) + "/coverletter_" + hs + ".pdf") + r"}" + "\n")
		
		header = getMemberOfCongress(govtrack_id)["name"] + "\t" + "(batch " + batch_no + ")"
		outfile.write(r"\markboth{")
		outfile.write_esc(header)
		outfile.write(r"}{")
		outfile.write_esc(header)
		outfile.write(r"}" + "\n")

		outfile.write(r"{\Large \noindent ")
		outfile.write_esc(getMemberOfCongress(govtrack_id)["name"])
		outfile.write(r"} \bigskip" + "\n\n" + r"\noindent ")

		outfile.write_esc(getMemberOfCongress(govtrack_id)["address"])
		outfile.write(r"\bigskip" + "\n\n" + r"\noindent ")

		outfile.write(r"\bigskip" + "\n\n")
		
		for t2 in UserCommentOfflineDeliveryRecord.objects.filter(target=govtrack_id, batch=batch).values("comment__bill", "comment__position").order_by("comment__bill", "comment__position").distinct():
			position = t2["comment__position"]
			bill = Bill.objects.get(id=t2["comment__bill"])
			
			outfile.write(r"{\large \noindent ")
			if position == "+": outfile.write_esc("Support: ")
			if position == "-": outfile.write_esc("Oppose: ")
			outfile.write_esc(bill.title)
			outfile.write(r"}\nopagebreak\bigskip" + "\n\n\n")
			
			outfile.write("\\noindent (see http://popvox.com" + bill.url() + "/report)\n\n\n\\bigskip")
			
			for t3 in UserCommentOfflineDeliveryRecord.objects.filter(target=govtrack_id, batch=batch, comment__bill=bill, comment__position=position):
				# Move this into the new batch number if it's not in a numbered batch.
				if batch == None:
					t3.batch = batch_no
					t3.save()
				
				comment = t3.comment
				address = comment.address
				target_errors[t3.failure_reason] = True
				
				outfile.write(r"\hrule\bigskip" + "\n\n")
				outfile.write(r"\noindent ")
				outfile.write_esc(address.nameprefix + " " + address.firstname + " " + address.lastname + " " + address.namesuffix)
				outfile.write(r"\\\nopagebreak" + "\n")
				outfile.write_esc(address.address1)
				outfile.write(r"\\\nopagebreak" + "\n")
				if address.address2 != "":
					outfile.write_esc(address.address2)
					outfile.write(r"\\\nopagebreak" + "\n")
				outfile.write_esc(address.city + ", " + address.state + " " + address.zipcode)
				outfile.write(r"\\\nopagebreak" + "\n")
				if address.phonenumber != "":
					outfile.write_esc(address.phonenumber)
					outfile.write(r"\\\nopagebreak" + "\n")
				outfile.write_esc(comment.user.email)
				outfile.write(r"\\\nopagebreak" + "\n")
				outfile.write_esc(comment.updated.strftime("%x"))
				outfile.write(r"\\\nopagebreak" + "\n\n" + r"\nopagebreak ")
			
				outfile.write_esc(comment.message)
				outfile.write("\n\n\\bigskip")
				
				if comment.referrer != None and isinstance(comment.referrer, Org):
					outfile.write(r"{\it ")
					outfile.write_esc("(This individual was referred by " + comment.referrer.name + ", ")
					if comment.referrer.website == None:
						outfile.write_esc("http://popvox.com" + comment.referrer.url())
					else:
						outfile.write_esc(comment.referrer.website)
					outfile.write_esc(")")
					outfile.write(r"}")
					outfile.write("\n\n\\bigskip")
				elif comment.referrer != None and isinstance(comment.referrer, OrgCampaign):
					outfile.write(r"{\it ")
					outfile.write_esc("(This individual was referred by " + comment.referrer.org.name + ", ")
					if comment.referrer.website_or_orgsite() == None:
						outfile.write_esc("http://popvox.com" + comment.referrer.url())
					else:
						outfile.write_esc(comment.referrer.website_or_orgsite())
					outfile.write_esc(")")
					outfile.write(r"}")
					outfile.write("\n\n\\bigskip")
				
			# clear page after each "topic", i.e. bill and support oppose
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
		outfile.write_esc(" ".join(p["address"].split(" ")[0:2]))
		outfile.write(r"  --- ")
		#outfile.write_esc(str(UserCommentOfflineDeliveryRecord.objects.filter(target=govtrack_id, batch=batch_no).count()))
		#outfile.write_esc(", ".join([k for k in target_errors if k not in ("no-method", "missing-info", "failure-oops")]))
		outfile.write_esc(", ".join([k for k in target_errors if k not in ("no-method",)]))
		outfile.write(r" \\" + "\n")
	
	outfile.write(r"\end{document}" + "\n")
	
	outfile_.close()
	
if len(sys.argv) == 2 and sys.argv[1] == "resetbatchnumbers":
	UserCommentOfflineDeliveryRecord.objects.all().delete()
elif len(sys.argv) == 3 and sys.argv[1] == "kill":
	UserCommentOfflineDeliveryRecord.objects.filter(batch = sys.argv[2]).delete()
elif len(sys.argv) >= 3 and sys.argv[1] == "delivered":
	recs = UserCommentOfflineDeliveryRecord.objects.filter(batch__isnull = False)
	if sys.argv[2] != "all":
		b = []
		for c in sys.argv[2:]:
			b.extend(re.split(r"\s+", c))
		b = [int(c) for c in b if c.strip() != ""]
		recs = recs.filter(batch__in = b)
	for ucodr in recs:
		dr = DeliveryRecord()
		dr.target = Endpoint.objects.get(govtrackid=ucodr.target.id)
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
		
