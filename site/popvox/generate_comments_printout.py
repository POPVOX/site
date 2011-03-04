#!runscript

# Takes all of the batched UserCommentOfflineDeliveryRecord objects
# and generates a PDF of comments to be delivered to Members of Congress.
# It first generates a LaTeX file.

from django.db.models import Max
from django.core.mail import EmailMultiAlternatives

import re, shutil, subprocess, sys, tempfile

from popvox.models import UserCommentOfflineDeliveryRecord, Bill
from popvox.govtrack import getMemberOfCongress
from settings import SERVER_EMAIL

buildings = {
	"cannon": "house",
	"dirksen": "senate",
	"hart": "senate",
	"longworth": "house",
	"rayburn": "house",
	"russell": "senate"
	}

def create_tex(tex):
	batch_max = UserCommentOfflineDeliveryRecord.objects.aggregate(Max("batch"))["batch__max"]
	if batch_max == None: batch_max = 0

	outfile_ = open(tex, "w")
	
	class O:
		pass

	outfile = O()
	outfile.write = lambda x : outfile_.write(x.encode("utf8", "replace"))
	def escape_latex(x):
		x = re.sub(r"(\S{15})(\S{15})", r"\1 \2", x)
		x = x.replace("\\", "\\\\").replace("#", "\\#").replace("$", "\\$").replace("%", "\\%").replace("&", "\\&").replace("~", "\\~").replace("_", "\\_").replace("^", "\\^").replace("{", "\\{").replace("}", "\\}")
		x = re.sub(r'(\s)"', r'\1' + u"\u201C", x)
		x = re.sub(r"(\s)'", r'\1' + u"\u2018", x)
		x = re.sub(r'"', u"\u201D", x)
		x = re.sub(r"'", u"\u2019", x)
		#x = re.sub(r'(\s)"', r'\1``', x)
		#x = re.sub(r"(\s)'", r'\1`', x)
		#x = x.replace(u"\u2018", "`")
		#x = x.replace(u"\u2019", "'")
		#x = x.replace(u"\u201C", "``")
		#x = x.replace(u"\u201D", "''")
		return x
		
	outfile.write_esc = lambda x : outfile.write(escape_latex(x))
	
	outfile.write(r"\documentclass[twocolumn,notitlepage]{report}" + "\n")
	outfile.write(r"\usepackage[top=1in, bottom=1in, left=1in, right=1in]{geometry}" + "\n")
	outfile.write(r"\pagestyle{myheadings}" + "\n")
	outfile.write(r"\usepackage{fontspec}" + "\n")
	outfile.write(r"\setromanfont{Linux Libertine O}" + "\n")
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
			batch_max += 1
			batch_no = batch_max
		targets2.append( (govtrack_id, batch_no) )
		
		header = getMemberOfCongress(govtrack_id)["name"] + "\t" + "(batch #" + str(batch_no) + ")"
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

		outfile.write(r"\bigskip" + "\n")
		
		for t2 in UserCommentOfflineDeliveryRecord.objects.filter(target=govtrack_id, batch=batch).values("comment__bill", "comment__position").order_by("comment__bill", "comment__position").distinct():
			position = t2["comment__position"]
			bill = Bill.objects.get(id=t2["comment__bill"])
			
			outfile.write(r"{\large \noindent ")
			if position == "+": outfile.write_esc(r"Support: ")
			if position == "-": outfile.write_esc(r"Oppose: ")
			outfile.write_esc(bill.title)
			outfile.write(r"}\nopagebreak\bigskip" + "\n\n\n")
			
			outfile.write("\\noindent (These messages and other information can be found at http://www.popvox.com" + bill.url() + "/report)\n\n\n\\bigskip")
			
			for t3 in UserCommentOfflineDeliveryRecord.objects.filter(target=govtrack_id, batch=batch, comment__bill=bill, comment__position=position):
				# Move this into the new batch number if it's not in a numbered batch.
				if batch == None:
					t3.batch = batch_no
					t3.save()
				
				comment = t3.comment
				address = comment.address
				
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
				
				outfile.write(r"\hrule\bigskip" + "\n\n")
				
		outfile.write(r"\clearpage" + "\n")

	outfile.write(r"\clearpage" + "\n")
	outfile.write(r"\markboth{Hit Sheet}{Hit Sheet}" + "\n")
	outfile.write(r"\noindent ")
	for govtrack_id, batch_no in targets2:
		p = getMemberOfCongress(govtrack_id)
		outfile.write_esc("#" + str(batch_no))
		outfile.write(r" --- ")
		outfile.write_esc(p["lastname"] + " " + p["state"] + (str(p["district"]) if p["district"]!=None else ""))
		outfile.write(r"  --- ")
		outfile.write_esc(" ".join(p["address"].split(" ")[0:2]))
		outfile.write(r"  --- ")
		outfile.write_esc(str(UserCommentOfflineDeliveryRecord.objects.filter(target=govtrack_id, batch=batch_no).count()))
		outfile.write(r" \\" + "\n")
	
	outfile.write(r"\end{document}" + "\n")
	
	outfile_.close()
	
if len(sys.argv) == 2 and sys.argv[1] == "resetbatchnumbers":
	UserCommentOfflineDeliveryRecord.objects.all().delete()
elif len(sys.argv) == 3 and sys.argv[1] == "undelivered":
	UserCommentOfflineDeliveryRecord.objects.filter(batch = sys.argv[2]).delete()
else:
	path = tempfile.mkdtemp()
	try:
		tex = path + '/comments.tex'
		create_tex(tex)
		
		subprocess.call(["xelatex", tex], cwd=path)
		subprocess.call(["cp", tex.replace(".tex", ".pdf"), "."])
		
		with open(tex.replace(".tex", ".pdf"), 'rb') as f:
			msg = EmailMultiAlternatives("User Messages Delivery PDF",
				"",
				SERVER_EMAIL,
				["josh@popvox.com"])
			msg.attach('messages.pdf', f.read(), "application/pdf")
			msg.send()
			
		#print "Done."
		#sys.stdin.readline()
	finally:
		#print path
		shutil.rmtree(path)
		
