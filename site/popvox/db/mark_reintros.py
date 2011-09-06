#!runscript

from popvox.models import Bill

for line in open("/home/annalee/bills_matched.tsv"):
	fields = line.strip().split("\t")

	a = Bill.objects.get(id=fields[0])
	b = Bill.objects.get(id=fields[4])

	assert(a.congressnumber == 112)
	assert(fields[2] == a.displaynumber())
	
	assert(b.congressnumber == 111)
	assert(fields[6] == b.displaynumber())
	
	b.reintroduced_as = a
	b.save()
	
