function capscount(txt) {
	var ret = 0;
	var last_was_caps = 0;
	for (var i = 0; i < txt.length; i++) {
		if (txt.charAt(i).toLowerCase() != txt.charAt(i).toUpperCase() && txt.charAt(i) == txt.charAt(i).toUpperCase()) {
			if (last_was_caps)
				ret++;
			last_was_caps = 1;
		} else if (txt.charAt(i) != " ") {
			last_was_caps = 0;
		}
	}
	return ret;
}
function bangcount(txt) {
	var ret = 0;
	for (var i = 0; i < txt.length; i++) {
		if (txt.charAt(i) == "!")
			ret++;
	}
	return ret;
}
function validate(box) {
	var v = $('#' + box).val();
	var billnum = bill_display_number.replace(/ /g, " *").replace(/\./g, "[\\. ]*").replace(/\(/g, "\\(").replace(/\)/g, "\\)")
	var charlimit = 2400;
	
	// checks for validity
	$('#' + box + "error").text('');
	$('#' + box + "tip").text('');
	if (v == "")
		$('#' + box + "error").text("This field is required.");
	else if (v.length > charlimit)
		$('#' + box + "error").text("That's too long. Reduce your message by " + (v.length-charlimit) + " characters.");
	
	// suggestions and tips
	else if (v.match(/(\d{3}|\D)\d{3}\W?\d{4}(\D|$)/))
		$('#' + box + "tip").text("Don't include your phone number here! Your comment will be public. We'll ask for your personal information separately.");
	else if (capscount(v) > 10 && capscount(v) < .75*v.length)
		$('#' + box + "tip").text("Capital letters are often understood as shouting. Try using fewer capital letters.");
	else if (bangcount(v) > 4)
		$('#' + box + "tip").text("Exclamation points might be a little excessive. Try using fewer exclamation points.");
	else if (v.search(billnum) == -1)
		$('#' + box + "tip").text("You should include the bill's name or number (" + bill_display_number + "), in your message, and the word 'support' or 'oppose'.");
	else if (v.search("support") == -1 && v.search("oppose") == -1)
		$('#' + box + "tip").text("You should include the word 'support' or 'oppose' in your message to make your position clear.");
	else if (v.length < .3 * charlimit && v.search(" my ") == -1)
		$('#' + box + "tip").text("Be personal. Write about how it affects your life or your community.");
	else if (bangcount(v) > 1)
		$('#' + box + "tip").text("Exclamation points might be a little excessive. Try using fewer exclamation points.");
	else if (v.length < .15 * charlimit)
		$('#' + box + "tip").text("Try to write a little more.");
	else if (capscount(v) > 10)
		$('#' + box + "tip").text("Capital letters are often understood as shouting. Try using fewer capital letters.");
	else if (v.length > .75 * charlimit)
		$('#' + box + "tip").text("You have " + (charlimit-v.length) + " characters left.");

	if (!$('#' + box + "tip").text())
		$('#' + box + "tipcontainer").fadeOut();
	else
		$('#' + box + "tipcontainer").fadeIn();
}

