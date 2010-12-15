function getorgshorturl(billposid) {
	$('#getorgshorturl_' + billposid).html("<em>Loading...</em>");
	ajax(
		"/ajax/bills/getshorturl",
		{ billposid: billposid},
		{
			success: function(res) {
				$('#getorgshorturl_' + billposid).html("Use this special tracking URL <tt>" + res.url + "</tt> to send your membership to this bill. We will later be providing analytics on your campaign.");
			}
		}
	);
	return false;
}

