class ShorturlMiddleware:
	def process_response(self, request, response):
		if not getattr(request, "just_added_shorturl", False) and getattr(request, "session", None) != None:
			if "shorturl" in request.session:
				del request.session["shorturl"]
		return response

