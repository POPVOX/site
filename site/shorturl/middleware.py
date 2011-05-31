class ShorturlMiddleware:
	def process_response(self, request, response):
		if not getattr(request, "just_added_shorturl", False) and hasattr(request, "session"):
			if "shorturl" in request.session:
				del request.session["shorturl"]
		return response

