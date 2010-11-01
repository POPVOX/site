# Django settings for oughttabealaw project.

import os
import os.path

DEBUG = ("DEBUG" in os.environ)
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

if not DEBUG or "REMOTEDB" in os.environ:
	DATABASES = {
	    'default': {
	        'NAME': 'oughttabealaw',
	        'ENGINE': 'django.db.backends.mysql',
	        'USER': 'root',
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

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
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

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = os.path.dirname(__file__) + "/media/"

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/media/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = '1!b1j0mmjm&c2gxo(wp!1r#1#yu_z&1@@4l%)1*j$1+c$p-4^b'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

ROOT_URLCONF = 'urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
	os.path.dirname(__file__) + "/templates/"
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.admin',
    'emailverification',
    'obal',
)


EMAIL_SUBJECT_PREFIX = "[POPVOX] "
SERVER_EMAIL = "POPVOX <no.reply@popvox.com>"
EMAIL_HOST = "occams.info" # because our EC2 IP was formerly used for spam
EMAIL_HOST_USER = "popvox"
EMAIL_HOST_PASSWORD = "qsg;5TtC"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
ADMINS = [ ('POPVOX Admin', 'josh@popvox.com') ]
MANAGERS = [ ('POPVOX Team', 'team@popvox.com') ]
if DEBUG:
	SITE_ROOT_URL = "http://localhost:8000"

