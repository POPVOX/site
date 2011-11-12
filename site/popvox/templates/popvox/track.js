var tracked_bills_changed = false;
var antitracked_bills_added = false;
var antitracked_bills_removed = false;
function track(billid, track) {
	ajax(
		"/ajax/accounts/profile/trackbill",
		{
			bill: billid,
			track: track
		},
		{
			success: function(ret) {
				track_setstate(billid, track, ret.value);
				
				{% if leg_staff_home_tabs %}
				update_tabs();
				{% endif %}
			}
		}
	);
}
function track_setstate(billid, track, state) {
	var elems = $(".bill" + (track == "+" ? "track" : "antitrack") + "[billid='" + billid + "']");
	if (track == "+") {
		tracked_bills_changed = true;
		if (state == "+"  || state == true) {
			elems.addClass("active");
			elems.text("Remove Bookmark");
			elems.attr("title", "Remove Bookmark");
			
			$('#tracked_tab')
				.animate({"background-color": "#E47816"})
				.delay(3000)
				.animate({"background-color": "#434247"});
		} else {
			elems.removeClass("active");
			elems.text("Bookmark");
			elems.attr("title", "Bookmark");
			$(".billbeingtracked[billid='" + billid + "']").fadeOut();
		}
	} else if (track == "-") {
		if (state == "-" || state == false) {
			antitracked_bills_added = true;
			elems.addClass("active");
			elems.text("Add Back to Automatic Tracking");
			elems.attr("title", "Add Back to Suggestions");
			$(".bill[billid='" + billid + "']").fadeOut(); //fadeOut is nice but only seems to work for instances of the bill that are currently on the screen. hide() takes care of all instances, but it is so hard to understand an instantaneously disappearing element.
		} else {
			antitracked_bills_removed = true;
			elems.removeClass("active");
			elems.text("Hide From Automatic Tracking");
			elems.attr("title", "Hide From Automatic Tracking");
			$(".bill[billid='" + billid + "']").show();
			$(".billhidden[billid='" + billid + "']").fadeOut();
		}
	}
}
