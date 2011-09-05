import sys
sys.path.insert(0, "libs")

import os
import os.path

execfile("/mnt/persistent/config/tokens.py")

DEBUG = ("DEBUG" in os.environ)
TEMPLATE_DEBUG = DEBUG
INTERNAL_IPS = ('127.0.0.1') # used by django.core.context_processors.debug

if not DEBUG:
	# If the site is accessed from multiple domains, then this is going to be
	# a problem since we filter redirects to this path to make sure we aren't
	# redirecting just anywhere.
	SITE_ROOT_URL = "http://www.popvox.com" # doubles as openid2 authentication realm, which means if we change it, then people's Google logins will invalidate
	SITE_SHORT_ROOT_URL = "http://pvox.co"
	DATADIR = os.path.dirname(__file__) + "/data/"
	SESSION_COOKIE_SECURE = True
else:
	SITE_ROOT_URL = "http://localhost:8000"
	EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
	DATADIR = "/home/tauberer/data/popvox/data/"

APP_NICE_SHORT_NAME = "POPVOX"
EMAIL_SUBJECT_PREFIX = "[POPVOX] "

EMAILVERIFICATION_FROMADDR = "POPVOX <info@popvox.com>"
SERVER_EMAIL = "POPVOX <no.reply@popvox.com>"
ADMINS = [ ('POPVOX Admin', 'josh@popvox.com') ]
MANAGERS = [ ('POPVOX Team', 'info@popvox.com') ]

if DEBUG:
	# this is the default when DEBUG is true, but we'll be explicit.
	EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
elif os.environ.get("EMAIL_BACKEND") in ("", "AWS-SES"):
	# This is the default when DEBUG is not true.
	#
	# For AWS SES:
	#  The SERVER_EMAIL and EMAILVERIFICATION_FROMADDR must be 
	#  verified with ./ses-verify-email-address.pl.
	#  We must be approved for production use.
	#  The SPF record on the domain must include "include:amazonses.com".
	#  https://github.com/hmarr/django-ses:
	#   django_ses is added to installed apps for management commands.
	#   plus with django_ses.urls mapped to /admin/ses for the dash.
	#  We should really be monitoring the statistics.
	EMAIL_BACKEND = 'django_ses.SESBackend'
elif os.environ.get("EMAIL_BACKEND") == "SENDGRID":
	EMAIL_HOST = "smtp.sendgrid.net"
	EMAIL_HOST_USER = SENDGRID_USERNAME
	EMAIL_HOST_PASSWORD = SENDGRID_PASSWORD
	EMAIL_PORT = 587
	EMAIL_USE_TLS = True
else:
	EMAIL_HOST = "occams.info" # don't send from EC2 because our IP might be blacklisted
	EMAIL_HOST_USER = "popvox"
	EMAIL_HOST_PASSWORD = "qsg;5TtC"
	EMAIL_PORT = 587
	EMAIL_USE_TLS = True


SEND_BROKEN_LINK_EMAILS = False
CSRF_FAILURE_VIEW = 'views.csrf_failure_view'

if not DEBUG or "REMOTEDB" in os.environ:
	mysqlhost = "localhost" # unix domain
	mysqluser = "root"
	if "REMOTEDB" in os.environ and os.environ["REMOTEDB"] == "1":
		mysqlhost = "127.0.0.1"
	elif "REMOTEDB" in os.environ:
		mysqlhost = os.environ["REMOTEDB"]
		mysqluser = "slave"
	DATABASES = {
	    'default': {
	        'NAME': 'popvox',
	        'ENGINE': 'django.db.backends.mysql',
	        'USER': mysqluser,
	        'PASSWORD': 'qsg;5TtC',
	        'HOST': mysqlhost,
	        'PORT': 3306
	    }
	}
else:
	DATABASES = {
		'default': {
			'NAME': os.path.dirname(__file__) + '/database.sqlite',
			'ENGINE': 'django.db.backends.sqlite3',
		}
	}

DEFAULT_FILE_STORAGE = 'storages.backends.s3.S3Storage'
AWS_ACCESS_KEY_ID = 'AKIAJ5OQIIQPCIXZBPKQ'
AWS_SECRET_ACCESS_KEY = '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'
AWS_STORAGE_BUCKET_NAME = "static.popvox.com"
if DEBUG and not "REMOTEDB" in os.environ:
	AWS_STORAGE_BUCKET_NAME = "static-demo.popvox.com"
AWS_S3_SECURE_URLS = True
AWS_CALLING_FORMAT = 1 # we can't use vanity calling format (i.e. static.popvox.com => static.popvox.com.s3.amazonaws.com) under HTTPS for obvious reasons

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/New_York'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = __file__ + "/../media/"

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/media/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/admin_media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = '#hk(--a8dq@6$z%476=mmf7*rgg-x204xm5@t5^jcco6x#)u2r'

CACHE_BACKEND = 'memcached://127.0.0.1:11211/'

AUTH_PROFILE_MODULE = 'popvox.UserProfile'
LOGIN_URL = "/accounts/login"
LOGIN_REDIRECT_URL = "/home"

if os.path.exists(os.path.dirname(__file__) + "/debug"):
	DEBUG=True
	TEMPLATE_DEBUG=True

TEMPLATE_LOADERS = (
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    )
if not DEBUG:
    TEMPLATE_LOADERS = (
      ('django.template.loaders.cached.Loader', TEMPLATE_LOADERS),
      )


MIDDLEWARE_CLASSES = (
    'adserver.middleware.Middleware',
    'popvox.middleware.StandardCacheMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'popvox.middleware.SessionFromFormMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'trafficanalysis.middleware.TrafficAnalysisMiddleware',
    'popvox.middleware.IE6BlockMiddleware',
    'popvox.middleware.AdserverTargetsMiddleware',
    'shorturl.middleware.ShorturlMiddleware',
)
if DEBUG:
	MIDDLEWARE_CLASSES = [m for m in MIDDLEWARE_CLASSES if not "cache" in m]

TEMPLATE_CONTEXT_PROCESSORS = (
	"django.contrib.auth.context_processors.auth",
	"django.core.context_processors.debug",
	"django.core.context_processors.i18n",
	"django.core.context_processors.media",
	"django.contrib.messages.context_processors.messages",
	'django.core.context_processors.request',
	)

ROOT_URLCONF = 'urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.dirname(__file__) + "/templates"
)

if not DEBUG:
	SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.humanize',
    'django.contrib.messages',
    'tinymce',
    'feedback',
    'picklefield',
    'django_ses',
    #'stockphoto',
    'jquery',
    'writeyourrep',
    'phone_number_twilio',
    'emailverification',
    'shorturl',
    'registration',
    'trafficanalysis',
    'popvox',
    'adserver',
)

TINYMCE_JS_URL = '/media/tiny_mce/tiny_mce.js'
TINYMCE_DEFAULT_CONFIG = {
    #'plugins': "table,spellchecker,paste,searchreplace",
    'theme': "simple",
    'cleanup_on_startup': True,
    'content_css': "/media/admin.css",
    'width': '640px',
    'height': '300px'
}

# registration app
ACCOUNT_ACTIVATION_DAYS = 7 # One-week activation window; you may, of course, use a different value.
USERNAME_BLACKLIST_TERMS = ["admin", "popvox", "fuck"]

# phone_number_twilio app
TWILIO_INCOMING_RESPONSE = "Thank you for calling pop vox. For more information, please see pop vox dot com. Goodbye."
TWILIO_STORE_HASHED_NUMBERS = True

# Registration.
FACEBOOK_AUTH_SCOPE = "email" #,offline_access,publish_stream,user_location"

STOCKPHOTO_URL = "/about/photos"

BENCHMARKING = False



