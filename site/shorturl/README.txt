Short URLs App for Django
================

By POPVOX.com

This is a generic app for creating shorturls on your own domain.

It has commonalities and differences from django-shorturls by Jacobian (http://github.com/jacobian/django-shorturls). Similar to Jacobian's app, the
targets of the links are tied to your Django object model structure. However,
rather than defining a mapping between shorturl prefixes and Django models,
each link is associated with an arbitrary model using Django's generic
foreign keys. In addition, rather than exposing the internal object ID (in
Jacobian's the shorturl is the "base62" of the object ID) in this app the shorturls
are random strings which are mapped to object IDs in the database.

The app also tracks the number of hits to the shorturl and provides an integer
field to track "conversions" based on the shorturl, which you can use however
you want. It also has a field which can store any Django object, which is pickled
in the database.

Finally, the app also allows you to optionally set an owner for each shorturl.
This lets you track hits by referrer.

Installation:
--------------

Symlink this directory as "shorturl" in your PYTHONPATH somewhere.

In your settings.py:

	* Add 'shorturl' in your apps list.
	* Add 'shorturl.middleware.ShorturlMiddleware' to your middleware (which cleans out
	  the shorturl session key on the first request after the key is set, which
	  means on the view the user is redirected to immediately after hitting
	  the shorturl).
	* In your urls.py, add: (r'^w/', include('shorturl.urls')),

"w/" specifies a prefix of your choosing on your site where the shorturls live. (I
think of "w" as a short mnemonic of "www".)

Back in settings.py, your settings must have set either SITE_ROOT_URL or
SITE_SHORT_ROOT_URL, e.g.:

	SITE_ROOT_URL = "http://www.djangoproject.com"
		or
	SITE_SHORT_ROOT_URL = "http://djangoproject.com/w"

Neither should not end in a slash. Note that SITE_SHORT_ROOT_URL has
precedence and if you use it, you must include the "w" in the path. That let's
you override the URL root in case you want to generate links at another
address and forward them to your Django site from some other location
(e.g. if you want to make the URL even shorter than is otherwise possible).
For instance, if you set up a redirect in Apache on the domain shortdomain.com
as:

	Redirect / http://www.djangoproject.com/w/

then you would set: 

	SITE_SHORT_ROOT_URL = "http://short.com"

so that the shorturl app knows how to generate the proper URLs.

The default number of characters in the short url random code is 6. If you want
to adjust that, set SHORTURL_LENGTH in settings.py.

Run python manage.py syncdb to create the necessary database table.

Usage:
---------

To create a shorturl:

	import shorturl
	
	rec, created = shorturl.models.Record.objects.get_or_create(
		target=modelobject,
		owner=request.user if request.user.is_authenticated() else None
		)
	
	shorturl = rec.url()

modelobject is some object instance of a Django model. If your site is a blog, this might
be a Post instance. The target argument is required and it must support the
get_absolute_url() method which is used elsewhere in Django. The method was poorly
named by Django. It is actually supposed to return an absolute path aka a URL relative
to the base of the project, so something like "/posts/2010-10-01/mypost".

The owner argument is optional. It is similarly some model object instance. Here it's the
request user if the user is logged in, else None.

As with get_or_create, rec is the new shorturl record object and created is a boolean
indicating whether this is a new instance or if it was already in the database.

rec.url() gives the fully qualified absolute short URL. It would be:

  "http://www.djangoproject.com/w/ABCDEF"
     if you used SITE_ROOT_URL, or

   "http://short.com/ABCDEF"
     if you used SITE_SHORT_ROOT_URL

When someone visits a shorturl, the hits field (rec.hits) on the object is incremented. If
the session management middleware is installed, then the "shorturl" session key
is set to the shorturl.Record object rec.

The user is then redirected to the value of rec.target.get_absolute_url().

At that point, the view might want to check if session["shorturl"] is set and (if the
target of the shorturl matches the object being viewed, just in case) if it wants to display
and special message based on the owner of the shorturl record (session["shorturl"].owner).
If it does so, it should clear the session state (del session["shorturl"]) so that the
message doesn't get displayed indefinitely for that user on that page.

Later on you might do:

	req.increment_completions()
	
to increment the completions field (rec.completions) on the record. It is better to use this 
method than to increment the field yourself and then save the record --- this does the
update in one SQL statement to make sure there are no race conditions. What you do
with completions, if anything, is up to you.

Note that on shorturl.Record.objects, get_or_create() will fill in owner=None if
not set.

SimpleRedirect
----------------------

The normal use of this app is to create a redirect to a model object, which knows its
own URL via get_absolute_url(). The SimpleRedirect model can be used to create
arbitrary redirects. To use this model:

	import shorturl
	
	rec = shorturl.models.Record.objects.create(
		target=shorturl.models.SimpleRedirect.objects.create(url=destination_url)
		)
	
	shorturl = rec.url()

(The owner field of the Record instance is still available.)

The SimpleRedirect model includes the ability to store arbitrary metadata in pickled form.
Use sr.set_meta(obj) and obj will be pickled and stored in the record in the database,
and can be retrieved with sr.meta(). For instance:

	sr = shorturl.models.SimpleRedirect(url=destination_url)
	sr.set_meta({ "mixpanel_event": "url_opened", "mixpanel_properties": { "myproperty": "myvalue" }})
	sr.save()
	rec = shorturl.models.Record.objects.create(target=sr)
	shorturl = rec.url()

The only chance you'll have to inspect the metadata is on the request that occurs following
the redirect to sr.url. At that point, the "shorturl" session key should be set and will refer to
the shorturl.models.Record instance. So then:

	if hasattr(request, "session") and "shorturl" in request.session:
		target = request.session["shorturl"].target
		if type(target) == shorturl.models.SimpleRedirect:
			print target.meta()
	
Because you may want to use metadata with a redirect to a model, a model target
is also supported on the SimpleRedirect:

	sr = shorturl.models.SimpleRedirect(target=my_model_instance)

As previously, my_model_instance must have get_absolute_url() defined.


