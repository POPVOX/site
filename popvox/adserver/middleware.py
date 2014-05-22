from signedpickle import dumps, loads

class Middleware:
	def process_request(self, request):
		try:
			request.adserver_trail = loads(request.COOKIES["adserver_trail"])
		except:
			pass
		return None

	def process_response(self, request, response):
		if hasattr(request, "adserver_trail"):
			if len(request.adserver_trail) == 0:
				val = None
			else:
				val = dumps(request.adserver_trail)
			if val != request.COOKIES.get("adserver_trail", None):
				response.set_cookie("adserver_trail", val)
		return response
