#!runscript
from django.core import serializers
from popvox.models import *
output = open("test_sbills.json", "w")
senate112 = serializers.serialize('json', Bill.objects.filter(congressnumber=112, billtype='s'))
output.write(senate112)
output.close()

output = open("test_orgs.json", "w")
orgs = serializers.serialize('json', Org.objects.filter(name__contains="save"))
output.write(orgs)
output.close()
