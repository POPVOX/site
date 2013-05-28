var POP = {};

POP = function()
{
	var showDetail = function()
	{
		var last_pro = null;

		$('.proposal .description').mouseenter(function()
		{
			if (last_pro) {
				last_pro.parents('.proposal').removeClass('active');
				last_pro.hide();
			}
			var n = $(this).find('.large');
			n.css({ 'left': $(this).find('.small').position().left });
			n.css({ 'top': $(this).find('.small').position().top });
			n.show();
			last_pro = n;
			n.parents('.proposal').addClass('active');
		});
		$('.proposal .description .large').mouseleave(function()
		{
			if (!last_pro) return;
			last_pro.parents('.proposal').removeClass('active');
			last_pro.hide();
			last_pro = null;
		});
	};

	var init = function()
	{
		showDetail();
	};

	return {
		init:init
	};

} ();

jQuery(document).ready(function($)
{
    POP.init();
});