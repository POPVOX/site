function getshorturl(billposid) {
	$('#getshorturl_' + billposid).html("<em>Loading...</em>");
	ajax(
		"/ajax/orgs/getbillshorturl",
		{ billposid: billposid},
		{
			success: function(res) {
				$('#getshorturl_' + billposid).html("Use this special tracking URL <tt>" + res.url + "</tt> to send your membership to this bill. We will later be providing analytics on your campaign.");
			},
		}
	);
	return false;
}

