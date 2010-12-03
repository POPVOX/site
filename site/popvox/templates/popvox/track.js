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
						$(".bill[billid='" + billid + "']").hide(); //fadeOut is nice but only seems to work for instances of the bill that are currently on the screen
					} else {
						antitracked_bills_removed = true;
						elems.removeClass("active");
						elems.text("Hide From Suggestions");
						elems.attr("title", "Hide From Suggestions");
						$(".bill[billid='" + billid + "']").show();
					}
				}
			},
		}
	);
}

