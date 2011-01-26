def printexceptions(f):
	def g(*args, **kwargs):
		try:
			return f(*args, **kwargs)
		except Exception as e:
			print e
			raise
	return g
