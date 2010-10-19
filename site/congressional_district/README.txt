US Congressional District Lookup Django App

This is a Django app which provides a convenient interface to allow a
user to look up what congressional district they are in. You are
responsible for saving that information if you want to keep it with
the user's profile.

INSTALL
-----------

You'll need my jquery app also installed.

In settings.py, add 'congressional_district' to the list of INSTALLED_APPS.

In urls.py, add to your URL configuraration:

	(r'^ajax/district-lookup$', 'congressional_district.views.district_lookup'),


TO USE
----------

On the page that will contain the interface, add in the HTML <head> tag:

<script type="text/javascript" src="http://maps.google.com/maps/api/js?sensor=false"></script>

<script type="text/javascript" src="http://ajax.googleapis.com/ajax/libs/jquery/1.4.2/jquery.min.js"></script>

<script>
	function congressional_district_callback(state, district) {
	}
</script>

The callback function will be called when the user has found his congressional district. Change the path to jquery.js as appropriate.

At the location in the page where the interface is to be displayed, put:

{% include "congressional_district/choosecongressionaldistrict.html" %}


