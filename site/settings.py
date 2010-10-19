import sys
sys.path.insert(0, "libs")

import os
import os.path

DEBUG = ("DEBUG" in os.environ)
TEMPLATE_DEBUG = DEBUG
INTERNAL_IPS = ('127.0.0.1') # used by django.core.context_processors.debug

if not DEBUG:
	# If the site is accessed from multiple domains, then this is going to be
	# a problem since we filter redirects to this path to make sure we aren't
	# redirecting just anywhere.
	SITE_ROOT_URL = "http://www.popvox.com"
	SITE_SHORT_ROOT_URL = "http://popvox.com"
else:
	SITE_ROOT_URL = "http://localhost:8000"
	SITE_SHORT_ROOT_URL = SITE_ROOT_URL
	EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

APP_NICE_SHORT_NAME = "POPVOX"
EMAIL_SUBJECT_PREFIX = "[POPVOX] "
SERVER_EMAIL = "info@popvox.com"
ADMINS = [ ('POPVOX Admin', 'josh@popvox.com') ]
MANAGERS = [ ('POPVOX Team', 'team@popvox.com') ]

SEND_BROKEN_LINK_EMAILS = False

if not DEBUG or "REMOTEDB" in os.environ:
	DATABASES = {
	    'default': {
	        'NAME': 'popvox',
	        'ENGINE': 'django.db.backends.mysql',
	        'USER': 'popvox',
	        'PASSWORD': 'qsg;5TtC',
	        'HOST': '127.0.0.1' if "REMOTEDB" in os.environ else "localhost", # tcp or unix domain
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
AWS_STORAGE_BUCKET_NAME = "static.popvox.com" # VANITY calling format means this resoves via a CNAME to the real bucket subdomain, which is static.popvox.com.s3.amazonaws.com
import S3
AWS_CALLING_FORMAT = S3.CallingFormat.VANITY

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
#CACHE_BACKEND = "locmem://"

AUTH_PROFILE_MODULE = 'popvox.UserProfile'
LOGIN_URL = "/accounts/login"
LOGIN_REDIRECT_URL = "/home"

TEMPLATE_LOADERS = (
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    )
# not working!
#if not DEBUG:
#	TEMPLATE_LOADERS = (
#      ('django.template.loaders.cached.Loader', TEMPLATE_LOADERS)
#      )


MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'trafficanalysis.middleware.TrafficAnalysisMiddleware',
)

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
    'jquery',
    'congressional_district',
    'phone_number_twilio',
    'emailverification',
    'shorturl',
    'registration',
    'trafficanalysis',
    'popvox',
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

# phone_number_twilio app
TWILIO_ACCOUNT_SID = "ACdef6c89a3285e10de7af748f678df7c6"
TWILIO_ACCOUNT_TOKEN = "0ed66a495abc5e8c99b9d7f4059ab25f"
TWILIO_OUTGOING_CALLERID = "+12026847872"
TWILIO_INCOMING_RESPONSE = "Thank you for calling pop vox. For more information, please see pop vox dot com. Goodbye."
TWILIO_STORE_HASHED_NUMBERS = True

# emailverification and default email address
EMAILVERIFICATION_FROMADDR = "POPVOX <info@popvox.com>"

# associated with popvox.com domain and subdomains
RECAPTCHA_PUBLIC_KEY = "6LdJrbwSAAAAADCh7jpzE4kLiLB0lAvpZbU8EmI1"
RECAPTCHA_PRIVATE_KEY = "6LdJrbwSAAAAAFdrOJz0acpEk-1CEwtR4y7_t-tM"

# Registration.
#GOOGLE_OAUTH_TOKEN = "popvox.com"
#GOOGLE_OAUTH_TOKEN_SECRET = "Mnd7PqW+KmIhuqyvwlOIiqc4"
#GOOGLE_OAUTH_SCOPE = "http://www.google.com/m8/feeds/contacts/default/full"
TWITTER_OAUTH_TOKEN = "nHW7QjeTXTUxW7Pbww"
TWITTER_OAUTH_TOKEN_SECRET = "e8ky2OCVvW8uhrTcCwJqa1jyRHMsoRRLfPubCZSFs"
LINKEDIN_API_KEY = "KdiWIOZyqU_z34KzN6io1yLpJ19MqLn65LGQl4vVmvH8e0wBzMCRLxPlIFEtgj_g"
LINKEDIN_SECRET_KEY = "OrfNdzdEkbp_ysto9C8pceeTnR-DquFThUskQJNyT6gNqIQR-auZVwdrAR_fTWN0"
FACEBOOK_APP_ID = "150910028257528"
FACEBOOK_APP_SECRET = "736f9da5e1218854f9fb638336ad7c17"
FACEBOOK_AUTH_SCOPE = "email,offline_access,publish_stream,user_location"

