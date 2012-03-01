#!runscript

from django.core import serializers
from lxml import etree

def write(queryset, filename):
	dom = etree.fromstring( serializers.serialize("xml", queryset) )
	
	f = open("data_testing/fixtures/%s.xml" % filename, "w")
	f.write(etree.tostring(dom, encoding="UTF8", pretty_print=True))
	f.close()

from popvox.models import *
write(RawText.objects.all(), "rawtexts")
write(IssueArea.objects.all(), "issueareas")
write(Bill.objects.filter(id__in=(19986,21285)), "bills")

# TODO
# adserver: adserver.Format adserver.Target adserver.TargetGroup adserver.Advertiser adserver.Order adserver.Banner

