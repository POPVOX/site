{% load popvox_utils %}

{% if bill and request.GET.stats != "0" %}
	{% bill_statistics bill as stats %}
{% endif %}

document.write('<style>');
document.write('.popvoxwidget.small { width: 162px; height: 47px; cursor: pointer; }\n');
document.write('.popvoxwidget.wide { width: 259px; height: 51px; cursor: pointer; text-align: left; }\n');
document.write('.popvoxwidget.small .procon { color: #fff; font: 12px/19px helvetica, sans-serif; float: left; margin: 4px 0 0 25px; width: 25px; }\n');
document.write('.popvoxwidget.wide .procon { color: #fff; font: 13px/21px helvetica, sans-serif; float: left; margin: 5px 0 0 29px; width: 30px; }\n');
document.write('.popvoxwidget.wide .billtitle { color: #75747c; font: normal 10px/11px helvetica, sans-serif; font-weight: bold; background: none; margin: 0 0 3px 0; padding: 0; height: 22px; overflow: hidden; }\n');
document.write('.popvoxwidget.wide .speakup { color: #CC6A11; font: bold 10px/14px helvetica,sans-serif; }\n');
document.write('</style>');
document.write('<div class="popvoxwidget {% if request.GET.title == "1" %}wide{% else %}small{% endif %}" onclick="document.location=\'{{siteroot|escapejs}}{% if bill %}{{bill.url|escapejs}}{% endif %}\'"'
	+ ' style="background: url(https://www.popvox.com/media/icons/speak_up_{% if bill and stats %}ext{% else %}bubble{% endif %}{% if request.GET.title == "1" %}_wide{% endif %}.png) left top no-repeat;"'
	+ '><div class="procon">{% if stats %}{{stats.pro_pct}}%<br/>{{stats.con_pct}}%{% endif %}</div>' +
{% if request.GET.title == "1" %}'<div style="display: block; float: left; width: 180px; padding: 7px 0 0 14px;"><p class="billtitle">{{bill.title|truncatewords:15}}</p><p class="speakup"><a href="{{siteroot}}{% if bill %}{{bill.url}}{% endif %}">SPEAK UP at POPVOX</a></p></div>' +{% endif %}
'</div>')

