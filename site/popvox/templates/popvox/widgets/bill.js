{% load popvox_utils %}

{% if bill %}
	{% bill_statistics bill as stats %}
{% endif %}

document.write('<style>.popvoxwidget { width: 162px; height: 47px; background-image: url({{siteroot|escapejs}}/media/icons/speak_up_{% if bill %}ext{% else %}bubble{% endif %}.png); cursor: pointer } {% if not bill %}.popvoxwidget:hover { background-position: left bottom }{% endif %}</style>');
document.write('<div class="popvoxwidget" onclick="document.location=\'{{siteroot|escapejs}}{% if bill %}{{bill.url|escapejs}}{% endif %}\'"><div style="position: relative; top: 6px; left: 25px; color: white; font-family: sans-serif; font-size: 13px; width: 50px">{% if stats %}<div>{{stats.pro_pct}}%</div><div style="padding-top: 2px">{{stats.con_pct}}%</div>{% endif %}{% if bill and not stats %}<div style="padding-top: 1px">Go<br/>first.</div>{% endif %}</div></div>')

