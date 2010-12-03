var tracked_bills_changed = false;
var antitracked_bills_added = false;
var antitracked_bills_removed = false;
function track(billid, track) {
	ajax(
		"/ajax/accounts/profile/trackbill",
		{
			bill: billid,
			track: track,
		},
		{
			success: function(ret) {
				var elems = $(".bill" + (track == "+" ? "track" : "antitrack") + "[billid='" + billid + "']");
				if (track == "+") {
					tracked_bills_changed = true;
					if (ret.value == "+") {
						elems.addClass("active");
						elems.text("Un-Track This Bill");
						elems.attr("title", "Un-Track This Bill");
						
						$('#tracked_tab')
							.animate({"background-color": "#E47816"})
							.delay(3000)
							.animate({"background-color": "#434247"});
					} else {
						elems.removeClass("active");
						elems.text("Track This Bill");
						elems.attr("title", "Track This Bill");
					}
				} else if (track == "-") {
					if (ret.value == "-") {
						antitracked_bills_added = true;
						elems.addClass("active");
						elems.text("Add Back to Suggestions");
						elems.attr("title", "Add Back to Suggestions");
						$(".bill[billid='" + billid + "']").fadeOut(); //fadeOut is nice but only seems to work for instances of the bill that are currently on the screen. hide() takes care of all instances, but it is so hard to understand an instantaneously disappearing element.
					} else {
						antitracked_bills_removed = true;
						elems.removeClass("active");
						elems.text("Hide From Suggestions");
						elems.attr("title", "Hide From Suggestions");
						$(".bill[billid='" + billid + "']").show();
					}
				}
				
				{% if leg_staff_home_tabs %}
				update_tabs();
				{% endif %}
			},
		}
	);
}

