import traceback

def printexceptions(f):
	def g(*args, **kwargs):
		try:
			return f(*args, **kwargs)
		except Exception as e:
			traceback.print_exc()
			raise
	return g
