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
			n.css({ 'left': $(this).find('.small').position().left - 5 });
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

	var showModal = function()
	{
		$('.fire_modal').click(function()
		{
			var targetURL = $(this).attr('href');

			$.fancybox.open(targetURL,
			{
				maxWidth	: 460,
				maxHeight	: 730,
				fitToView	: false,
				width		: '460',
				height		: '700',
				autoSize	: false,
				closeClick	: false,
				openEffect	: 'none',
				closeEffect	: 'none',
				type		: 'iframe'
			});
			return false;
		});
	};

	var showTooltip = function()
	{
		$('.oppose, .support').not('.inactive').qtip({
			style: {
				classes: 'qtip-dark qtip-shadow'
			},
			position: {
				my: 'center right',
				at: 'center left'
			}
		});
		$('.inactive').qtip({
			style: {
				classes: 'qtip-dark qtip-shadow'
			},
			position: {
				my: 'center right',
				at: 'center left'
			},
			content: {
				text: 'You have already taken action.'
			}
		});
	};

	var makeInactive = function(billID)
	{
		$('div[bill_id="'+billID+'"]').find('div.action_buttons a').addClass('inactive');
	};

	var init = function()
	{
		showDetail();
		showTooltip();
		showModal();
	};

	return {
		init:init,
		makeInactive:makeInactive
	};

} ();

jQuery(document).ready(function($)
{
    POP.init();
});