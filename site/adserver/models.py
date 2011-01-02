from django.db import models

from datetime import datetime, timedelta

class Format(models.Model):
	"""A Format represents different types of banners, such as text ads,
	or different image ad sizes, plus the corresponding HTML code template
	(evaluated as a Django template) to display such an ad."""
	key = models.SlugField(db_index=True, unique=True, help_text="Assign a unique, slug-style name to this ad format which will serve as the name of the format in your website's HTML code.")
	name = models.CharField(max_length=128, help_text="The display name of this ad format.")
	html = models.TextField(verbose_name="HTML Code", help_text="Django template HTML for this ad format.")
	fallbackhtml = models.TextField(verbose_name="Fallback HTML", help_text="Django template HTML to use when no banners are available.", blank=True)
	imagewidth = models.IntegerField(blank=True, null=True, help_text="If this format is for an image ad, the required image width.")
	imageheight = models.IntegerField(blank=True, null=True, help_text="If this format is for an image ad, the required image height.")
	created = models.DateTimeField(auto_now_add=True)
	updated = models.DateTimeField(auto_now=True)
	def __unicode__(self):
		return self.key + ": " + self.name
	class Meta:
		ordering = ('name',)

class Target(models.Model):
	"""A Target represents a publisher-defined subset of impressions which
	is provided to advertisers to target ads to. Targets can be pages or sets
	of pages, or properties of the visitor."""
	key = models.SlugField(db_index=True, unique=True)
	name = models.CharField(max_length=128)
	disclosure = models.CharField(max_length=32, blank=True, null=True, help_text="This field is a very short description of the type of information implicitly revealed about the user to the advertiser from the nature of the targetting. An example would be 'Age' or 'Location'.")
	created = models.DateTimeField(auto_now_add=True)
	updated = models.DateTimeField(auto_now=True)
	def __unicode__(self):
		return self.name
	class Meta:
		ordering = ('name',)

class TargetGroup(models.Model):
	"""A TargetGroup is a group of Target objects."""
	name = models.CharField(max_length=128)
	targets = models.ManyToManyField(Target, blank=True)
	created = models.DateTimeField(auto_now_add=True)
	updated = models.DateTimeField(auto_now=True)
	def __unicode__(self):
		return self.name
	class Meta:
		ordering = ('name',)

class Advertiser(models.Model):
	"""An Advertiser is an organization placing advertisements on the website."""
	name = models.CharField(max_length=128, help_text="The name of the advertising organization.")
	contact_name = models.CharField(max_length=128, help_text="The name of the person who is the advertising contact at the organization.")
	contact_email = models.EmailField(max_length=128, help_text="The email address of the contact person at the organization.")
	notes = models.TextField(blank=True)
	remnant = models.BooleanField(default=False, help_text="Turn this on if this organization is YOU or if it represents other remnant or house advertising.")
	created = models.DateTimeField(auto_now_add=True)
	updated = models.DateTimeField(auto_now=True)
	def __unicode__(self):
		return self.name
	class Meta:
		ordering = ('name',)

class Order(models.Model):
	"""An Order is a group of banners with a starting and ending date, a bid price,
	a maximum cost per day, and targetting criteria."""
	advertiser = models.ForeignKey(Advertiser, db_index=True, related_name = "orders", help_text="The advertiser placing the order.")
	notes = models.TextField(blank=True)
	starttime = models.DateTimeField(null=True, blank=True, verbose_name="Start Date", help_text="The date the advertising will begin. Leave blank to start immediately.")
	endtime = models.DateTimeField(null=True, blank=True, verbose_name="End Date", help_text="The date the advertising will end. Leave blank to continue indefinitely.")
	cpmbid = models.FloatField(null=True, blank=True, verbose_name="CPM Bid", help_text="The cost-per-thousand impressions bid price in dollars. If both the CPM bid and the CPC bid are used, the higher of the two is used.")
	cpcbid = models.FloatField(null=True, blank=True, verbose_name="CPC Bid", help_text="The cost-per-click bid price in dollars. If both the CPM bid and the CPC bid are used, the higher of the two is used.")
	maxcostperday = models.FloatField(default=0, verbose_name="Max Cost/Day", help_text="The maximum dollar amount the advertiser wants to spend on this order per day. This field is ignored for remnant advertisers.")
	targets = models.TextField(blank=True, help_text="Criteria to target the advertisement to. Separate target keys by spaces or new lines. One target must match on each line. Leave blank for run-of-site advertising.")
	created = models.DateTimeField(auto_now_add=True)
	updated = models.DateTimeField(auto_now=True)
	
	# set on save
	active = models.BooleanField(default=False)
	
	class Meta:
		ordering = ('-updated',)

	def __unicode__(self):
		return self.advertiser.name + " " + str(self.id)
		
	def save(self):
		# Set the active flag based on the run dates.
		now = datetime.now()
		self.active = (self.starttime == None or self.starttime <= now) and (self.endtime == None or self.endtime >= now)
		
		# Reformat the targetting so that the target IDs are specified
		# rather than strings.
		targetting = "\n".join([
				" ".join([
						str(target) + "::" + Target.objects.get(id=target).key
						for target in targetgroup
					]) + "\n"
				for targetgroup in self.targets_parsed()
			])
		if targetting.strip() == "":
			self.targets = None
		else:
			self.targets = targetting
		
		super(Order, self).save()
		
	def targets_parsed(self):
		# The targetting pattern of an order is essentially in conjunctive normal
		# form. Return a list of lists of target IDs.
		if self.targets == None or self.targets.strip() == "":
			return []
		ret = []
		for line in self.targets.split("\n"):
			if line.strip() == "":
				continue
			dis = []
			ret.append(dis)
			for target in line.split():
				if "::" in target:
					target_id, target_name = target.split("::")
					dis.append(int(target_id))
				else:
					dis.append(Target.objects.get(key=target).id)
		return ret
	
	def disclosure(self):
		ret = set()
		for targetgroup in self.targets_parsed():
			for target in targetgroup:
				t = Target.objects.get(id=target)
				if t.disclosure != None and t.disclosure.strip() != "":
					ret.add(t.disclosure)
		ret = list(ret)
		ret.sort()
		return ", ".join(ret)
	
class Banner(models.Model):
	"""A Banner is text or an image provided by an advertiser."""
	order = models.ForeignKey(Order, db_index=True, related_name = "banners", help_text="The advertisement order that this banner is a part of.")
	format = models.ForeignKey(Format, db_index=True, related_name = "banners", help_text="The ad format for this banner.")
	name = models.CharField(max_length=128, help_text="A name for this banner.")
	active = models.BooleanField(default=True, help_text="Whether this banner is currently running")
	notes = models.TextField(blank=True)
	textline1 = models.CharField(max_length=128, blank=True, null=True, verbose_name="Text Line 1", help_text="The first line of text for text-format ads or alternate text for image-format ads.")
	textline2 = models.CharField(max_length=128, blank=True, null=True, verbose_name="Text Line 2", help_text="The second line of text for text-format ads.")
	image = models.ImageField(upload_to="adserver/banners", blank=True, null=True, help_text="The image, for image-format ads.")
	targeturl = models.URLField(verbose_name="Target URL", help_text="The destination URL for the ad.")
	created = models.DateTimeField(auto_now_add=True)
	updated = models.DateTimeField(auto_now=True)
	recentctr = models.FloatField(blank=True, null=True, verbose_name="Recent CTR", help_text="The most recently computed click-through ratio.")
	
	class Meta:
		ordering = ('order__advertiser__name', 'active')
		
	def __unicode__(self):
		return self.order.advertiser.name + " - " + self.name
		
	def compute_ctr(self):
		# For new banners, we have to make up a CTR. In order to give new
		# banners a chance at establishing their true CTR and at the same
		# time not giving an advantage to long-running poor-CTR banners,
		# we'll do an interpolation of sorts between the established CTR
		# (or zero if none exists) and a normal CTR (0.1%) based on the
		# number of impressions generated so far. A normal CTR is about
		# 0.1%, meaning it will take 1,000 impressions before we have a
		# single expected click, or closer to 10,000 before we have an
		# accurage gauge on the true CTR.
		
		# Only look at impressions in the last two weeks.
		impressions = self.impressions.filter(date__gt = datetime.now() - timedelta(days=14)).count()
		
		# compute the actual realized CTR so far
		ctr = float(self.impressions.filter(date__gt = datetime.now() - timedelta(days=14), clicks__gt=0).count()) / (float(impressions) if impressions > 0 else 1)
		
		if impressions > 10000:
			return ctr, False

		# Since there have been so few impressions, don't take it
		# at face value. The closer to 0 impressions, the more we
		# artificially inflate/defalate the CTR toward to 0.01.
		ctr += (0.01-ctr) * (1.0 - float(impressions)/10000.0)
		return ctr, True

	def setimage(self, imagedata, dims=None):
		if self.id == None:
			raise Exception("Save the Banner object before setting its image.")
		
		# Load the image and resize it to the right dimensions preserving aspect ratio.
		from PIL import Image
		imx = Image.open(imagedata)
		if dims != None:
			topleftcolor = imx.getpixel((0,0))
			(w, h) = imx.size
			if w > h*dims[0]/dims[1]:
				dims2 = (dims[0], int(float(dims[0])*h/w))
			else:
				dims2 = (int(float(dims[1])*w/h), dims[1])
			imx = imx.resize(dims2, Image.BICUBIC)
		
			# Because we don't know the color of the padding, create a new
			# image with the right background color and then paste in the
			# uploaded+resized image at the center.
			im = Image.new(imx.mode, dims, topleftcolor) # fill w/ top-left color
			im.paste(imx, (im.size[0]/2 - imx.size[0]/2, im.size[1]/2 - imx.size[1]/2))
		else:
			im = imx
	
		try:
			self.image.delete()
		except:
			pass
		
		# Get out the binary jpeg data.
		buf = StringIO()
		im.save(buf, "JPEG")
		buf.size = len(buf.getvalue())
		buf.name = "unnamed"
		buf.seek(0)
			
		from django.core.files import File
		self.image.save(str(self.id) + ".jpeg", File(buf))

class SitePath(models.Model):
	"""A SitePath is a local address on the website, used to aggregate impressions
	for statistical purposes."""
	path = models.CharField(max_length=32)
	def __unicode__(self):
		return self.path

class ImpressionBlock(models.Model):
	"""An Impression is a display of a particular banner at a given time.
	An ImpressionBlock tracks the number of impressions, clicks, and the
	cost for a given banner, path, date combination."""
	
	banner = models.ForeignKey(Banner, db_index=True, related_name="impressions")
	path = models.ForeignKey(SitePath, db_index=True, related_name="impressions")
	date = models.DateField(auto_now_add=True)
	cpmcost = models.FloatField(default=0) # average cpm cost over all impressions
	cpccost = models.FloatField(default=0) # current cpc cost for the next click
	impressions = models.IntegerField(default=0) # total number of impressions
	clickcost = models.FloatField(default=0) # total cost attributed to clicks (not per click)
	clicks = models.IntegerField(default=0)
	class Meta:
		unique_together = (("banner", "path", "date"),)
	
	def __unicode__(self):
		return str(self.banner) + " " + str(self.path) + " " + str(self.date)
	
	def cost(self):
		return self.impressions*self.cpmcost/1000.0 + self.clickcost
	
