function share_open_popup(url1, url2) {
	// url1 is what we should open in a popup, url2 is what we should open in a new full window/tab
	if (!url2) url2 = url1;
	a = function() {
		if (!window.open(url1,"sharer","toolbar=0,status=0,resizable=1,width=626,height=436"))
			if (!window.open(url2,"_blank"))
				document.location.href=url2;
	}
	if (/Firefox/.test(navigator.userAgent))
		setTimeout(a,0);
	else
		a();
	return false;
}
function share_link(method, text, url, hashtag) {
	if (method == "facebook") {
		// based on share bookmarklet: http://www.facebook.com/share_options.php
		var f="http://www.facebook.com/share";
		var p=".php?src=bm&v=4&i=1299162093&u=" + encodeURIComponent(url) + (text ? "&t=" + encodeURIComponent(text) : "");
		share_open_popup(f+"r"+p, f+p);
	} else if (method == "twitter") {
		var p1 = "http://twitter.com/intent/tweet?via=POPVOX&related=POPVOX&hashtags=" + (hashtag ? encodeURIComponent(hashtag.replace("#", "")) : "") + "&url=" + encodeURIComponent(url) + (text ? "&text=" + encodeURIComponent(text) : "");
		var p2 = "http://twitter.com/home?status=" + encodeURIComponent((text ? text : "") + (hashtag ? " " + hashtag : "") + " " + url + " via @POPVOX");
		share_open_popup(p1, p2);
	} else if (method == "reddit") {
		window.location = 'http://www.reddit.com/submit?url=' + encodeURIComponent(url);
	} else if (method == "tumblr") {
		share_open_popup('https://www.tumblr.com/share/link?url=' + encodeURIComponent(url) + (text ? "&name=" + encodeURIComponent(text) : ""), null);
	}
}

