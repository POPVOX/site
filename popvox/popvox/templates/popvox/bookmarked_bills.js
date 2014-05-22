	var last_expando = null;
	function expandbill(billid, elemid) {
		if (last_expando) {
			$('#bill_' + last_expando + '_details').hide();
			$('#bill_' + last_expando + '_expando').removeClass("active");
			$('#bill_' + last_expando + '_row1').removeClass("active");
			$('#bill_' + last_expando + '_row2').removeClass("active");
		}
		if (last_expando == elemid) {
			last_expando = null;
			return false;
		}
		
		$('#bill_' + elemid + '_details').fadeIn();
		$('#bill_' + elemid + '_expando').addClass("active");
		$('#bill_' + elemid + '_row1').addClass("active");
		$('#bill_' + elemid + '_row2').addClass("active");
		
		$.ajax({
			type:"POST",
			url: "/ajax/activity",
			data: {
				"default-locale": true,
				"bill": billid,
				"count": 1
			},
			complete: function(res, status) {
				$('#bill_' + elemid + '_details_dynamic').html(res.responseText);
			}
		});
		
		last_expando = elemid;
		return false; // cancel click
	}
	{% include "popvox/track.js" %}
