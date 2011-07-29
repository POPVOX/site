{% load popvox_utils %}

{% if bill %}
	{% bill_statistics bill as stats %}
{% endif %}

document.write('<style>.popvoxwidget { width: 162px; height: 47px; background-image: url(https://www.popvox.com/media/icons/speak_up_{% if bill and stats %}ext{% else %}bubble{% endif %}.png); cursor: pointer; text-align: left } {% if not bill %}.popvoxwidget:hover { background-position: left bottom }{% endif %}</style>');
document.write('<div class="popvoxwidget" onclick="document.location=\'{{siteroot|escapejs}}{% if bill %}{{bill.url|escapejs}}{% endif %}\'"><div style="position: relative; line-height: 17px; top: 6px; left: 26px; color: white; font-family: sans-serif; font-size: 12px; width: 50px">{% if stats %}{{stats.pro_pct}}%<br/>{{stats.con_pct}}%{% endif %}</div></div>')

