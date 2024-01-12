"""
Django settings for your TOM project.

Originally generated by 'django-admin startproject' using Django 2.1.1.
Generated by ./manage.py tom_setup on April 25, 2022, 9:38 p.m.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

from .settings_local import *
import os
import tempfile


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

ALLOWED_HOSTS = [ALLOWED_HOST, 'localhost', '127.0.0.1']


# Application definition

TOM_NAME = 'SAGUARO'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django_extensions',
    'guardian',
    'tom_common',
    'django_comments',
    'bootstrap4',
    'crispy_forms',
    'crispy_bootstrap4',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'django_gravatar',
    'tom_targets',
    'tom_alerts',
    'tom_catalogs',
    'tom_observations',
    'tom_dataproducts',
    'tom_alertstreams',
    'tom_nonlocalizedevents',
    'webpack_loader',
    'custom_code',
    'tom_surveys',
    'tom_treasuremap',
    'phonenumber_field',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'tom_common.middleware.Raise403Middleware',
    'tom_common.middleware.ExternalServiceMiddleware',
    'tom_common.middleware.AuthStrategyMiddleware',
]

ROOT_URLCONF = 'saguaro_tom.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap4"
CRISPY_TEMPLATE_PACK = 'bootstrap4'

WSGI_APPLICATION = 'saguaro_tom.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.getenv('POSTGRES_DB', POSTGRES_DB),
        'USER': os.getenv('POSTGRES_USER', POSTGRES_USER),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', POSTGRES_PASSWORD),
        'HOST': os.getenv('POSTGRES_HOST', POSTGRES_HOST),
        'PORT': os.getenv('POSTGRES_PORT', int(POSTGRES_PORT)),
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LOGIN_URL = FORCE_SCRIPT_NAME + '/accounts/login/'
LOGIN_REDIRECT_URL = FORCE_SCRIPT_NAME + '/'
LOGOUT_REDIRECT_URL = FORCE_SCRIPT_NAME + '/'

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
)

# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = False

USE_TZ = True

DATETIME_FORMAT = 'Y-m-d H:i:s'
DATE_FORMAT = 'Y-m-d'


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

WHITENOISE_STATIC_PREFIX = '/static/'  # TODO: delete this when whitenoise Issue #271 is resolved
STATIC_URL = FORCE_SCRIPT_NAME + '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, '_static')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
MEDIA_ROOT = os.path.join(BASE_DIR, 'data')
MEDIA_URL = FORCE_SCRIPT_NAME + '/data/'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        }
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'INFO'
        }
    }
}

# Caching
# https://docs.djangoproject.com/en/dev/topics/cache/#filesystem-caching

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': tempfile.gettempdir()
    }
}

# TOM Specific configuration
TARGET_TYPE = 'SIDEREAL'

FACILITIES = {
    'LCO': {
        'portal_url': 'https://observe.lco.global',
        'api_key': LCO_API_KEY,
    },
    'GEM': {
        'portal_url': {
            'GS': 'https://139.229.34.15:8443',
            'GN': 'https://128.171.88.221:8443',
        },
        'api_key': {
            'GS': GEM_S_API_KEY,
            'GN': GEM_N_API_KEY,
        },
        'user_email': '',
        'programs': {
            'GS-YYYYS-T-NNN': {
                'MM': 'Std: Some descriptive text',
                'NN': 'Rap: Some descriptive text'
            },
            'GN-YYYYS-T-NNN': {
                'QQ': 'Std: Some descriptive text',
                'PP': 'Rap: Some descriptive text',
            },
        },
    },
    'MMT': {
        'programs': {
            'Binospec': MMT_BINOSPEC_PROGRAMS,
            'MMIRS': MMT_MMIRS_PROGRAMS,
        },
    },
    'SWIFT': {
        'SWIFT_USERNAME': SWIFT_USERNAME,
        'SWIFT_SHARED_SECRET': SWIFT_SHARED_SECRET,
    },
}

# Define the valid data product types for your TOM. Be careful when removing items, as previously valid types will no
# longer be valid, and may cause issues unless the offending records are modified.
DATA_PRODUCT_TYPES = {
    'photometry': ('photometry', 'Photometry'),
    'fits_file': ('fits_file', 'FITS File'),
    'spectroscopy': ('spectroscopy', 'Spectroscopy'),
    'image_file': ('image_file', 'Image File'),
    'MMT': ('MMT', 'MMT File'),
}

DATA_PROCESSORS = {
    'photometry': 'tom_dataproducts.processors.photometry_processor.PhotometryProcessor',
    'spectroscopy': 'custom_code.processors.spectroscopy_processor.SpectroscopyProcessor',
    'MMT': 'tom_mmt.mmt.MMTDataProcessor',
}

TOM_FACILITY_CLASSES = [
    'tom_observations.facilities.lco.LCOFacility',
    'tom_observations.facilities.gemini.GEMFacility',
    'tom_observations.facilities.soar.SOARFacility',
    'tom_observations.facilities.lt.LTFacility',
    'custom_code.facilities.CustomMMTFacility',
    'tom_swift.swift.SwiftFacility',
]

TOM_ALERT_CLASSES = [
    'tom_alerts.brokers.alerce.ALeRCEBroker',
    'tom_alerts.brokers.antares.ANTARESBroker',
    'tom_alerts.brokers.gaia.GaiaBroker',
    'tom_alerts.brokers.hermes.HermesBroker',
    'tom_alerts.brokers.lasair.LasairBroker',
    'tom_alerts.brokers.scout.ScoutBroker',
    'tom_alerts.brokers.tns.TNSBroker',
    'tom_alerts.brokers.fink.FinkBroker',
]

BROKERS = {
    'TNS': {
        'api_key': TNS_API_KEY,
        'bot_id': '60911',
        'bot_name': 'SAGUARO_Bot1',
    }
}

TOM_HARVESTER_CLASSES = [
    'tom_catalogs.harvesters.simbad.SimbadHarvester',
    'tom_catalogs.harvesters.ned.NEDHarvester',
    'tom_catalogs.harvesters.jplhorizons.JPLHorizonsHarvester',
    'tom_catalogs.harvesters.tns.TNSHarvester',
]

HARVESTERS = {
    'TNS': {
        'api_key': TNS_API_KEY,
    }
}

# Define extra target fields here. Types can be any of "number", "string", "boolean" or "datetime"
# See https://tomtoolkit.github.io/docs/target_fields for documentation on this feature
# For example:
# EXTRA_FIELDS = [
#     {'name': 'redshift', 'type': 'number'},
#     {'name': 'discoverer', 'type': 'string'}
#     {'name': 'eligible', 'type': 'boolean'},
#     {'name': 'dicovery_date', 'type': 'datetime'}
# ]
EXTRA_FIELDS = [
    {'name': 'Classification', 'type': 'string'},
    {'name': 'Redshift', 'type': 'number'},
]

# Authentication strategy can either be LOCKED (required login for all views)
# or READ_ONLY (read only access to views)
AUTH_STRATEGY = 'READ_ONLY'

# Row-level data permissions restrict users from viewing certain objects unless they are a member of the group to which
# the object belongs. Setting this value to True will allow all `ObservationRecord`, `DataProduct`, and `ReducedDatum`
# objects to be seen by everyone. Setting it to False will allow users to specify which groups can access
# `ObservationRecord`, `DataProduct`, and `ReducedDatum` objects.
TARGET_PERMISSIONS_ONLY = True

# URLs that should be allowed access even with AUTH_STRATEGY = LOCKED
# for example: OPEN_URLS = ['/', '/about']
OPEN_URLS = []

MATCH_MANAGERS = {'Target': 'custom_code.managers.StrictTargetMatchManager'}

HOOKS = {
    'target_post_save': 'custom_code.hooks.target_post_save',
    'observation_change_state': 'tom_common.hooks.observation_change_state',
    'data_product_post_upload': 'tom_dataproducts.hooks.data_product_post_upload',
    'data_product_post_save': 'tom_dataproducts.hooks.data_product_post_save',
    'multiple_data_products_post_save': 'tom_dataproducts.hooks.multiple_data_products_post_save',
}

DATA_SHARING = {
    'tom-demo': {
        'DISPLAY_NAME': os.getenv('TOM_DEMO_DISPLAY_NAME', 'TOM Demo'),
        'BASE_URL': os.getenv('TOM_DEMO_BASE_URL', 'https://tom-demo.lco.global/'),
        'USERNAME': os.getenv('TOM_DEMO_USERNAME', 'guest'),
        'PASSWORD': os.getenv('TOM_DEMO_PASSWORD', 'guest'),
    },
}

AUTO_THUMBNAILS = False

THUMBNAIL_MAX_SIZE = (0, 0)

THUMBNAIL_DEFAULT_SIZE = (200, 200)

HINTS_ENABLED = True
HINT_LEVEL = 20

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
    ],
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 100
}

ALERT_STREAMS = [
    {
        'ACTIVE': True,
        'NAME': 'tom_alertstreams.alertstreams.hopskotch.HopskotchAlertStream',
        'OPTIONS': {
            'URL': 'kafka://kafka.scimma.org/',
            'GROUP_ID': os.getenv('SCIMMA_AUTH_USERNAME', SCIMMA_AUTH_USERNAME)
                        + '-' + os.getenv('HOPSKOTCH_GROUP_ID', HOPSKOTCH_GROUP_ID),
            'USERNAME': os.getenv('SCIMMA_AUTH_USERNAME', SCIMMA_AUTH_USERNAME),
            'PASSWORD': os.getenv('SCIMMA_AUTH_PASSWORD', SCIMMA_AUTH_PASSWORD),
            'TOPIC_HANDLERS': {
                'igwn.gwalert': 'custom_code.alertstream_handlers.handle_message_and_send_alerts'
            },
        },
    },
    {
        'ACTIVE': False,
        'NAME': 'tom_alertstreams.alertstreams.gcn.GCNClassicAlertStream',
        # The keys of the OPTIONS dictionary become (lower-case) properties of the AlertStream instance.
        'OPTIONS': {
            # see https://github.com/nasa-gcn/gcn-kafka-python#to-use for configuration details.
            'GCN_CLASSIC_CLIENT_ID': os.getenv('GCN_CLASSIC_CLIENT_ID', GCN_CLIENT_ID),
            'GCN_CLASSIC_CLIENT_SECRET': os.getenv('GCN_CLASSIC_CLIENT_SECRET', GCN_CLIENT_SECRET),
            'DOMAIN': 'gcn.nasa.gov',  # optional, defaults to 'gcn.nasa.gov'
            'CONFIG': {  # optional
                # 'group.id': 'tom_alertstreams - llindstrom@lco.global',
                # 'auto.offset.reset': 'earliest',
                # 'enable.auto.commit': False
            },
            'TOPIC_HANDLERS': {
                'gcn.classic.text.LVC_PRELIMINARY': 'tom_nonlocalizedevents.alertstream_handlers.gcn_event_handler.handle_message',
                'gcn.classic.text.LVC_INITIAL': 'tom_nonlocalizedevents.alertstream_handlers.gcn_event_handler.handle_message',
                'gcn.classic.text.LVC_RETRACTION': 'tom_nonlocalizedevents.alertstream_handlers.gcn_event_handler.handle_retraction',
            },
        },
    }
]

VUE_FRONTEND_DIR_TOM_NONLOCAL = os.path.join(STATIC_ROOT, 'tom_nonlocalizedevents/vue')
WEBPACK_LOADER = {
    'TOM_NONLOCALIZEDEVENTS': {
        'CACHE': not DEBUG,
        'BUNDLE_DIR_NAME': 'tom_nonlocalizedevents/vue/',  # must end with slash
        'STATS_FILE': os.path.join(VUE_FRONTEND_DIR_TOM_NONLOCAL, 'webpack-stats.json'),
        'POLL_INTERVAL': 0.1,
        'TIMEOUT': None,
        'IGNORE': [r'.+\.hot-update.js', r'.+\.map']
    }
}
TOM_API_URL = os.getenv('TOM_API_URL', os.path.join(ALLOWED_HOST, FORCE_SCRIPT_NAME))
HERMES_API_URL = os.getenv('HERMES_API_URL', 'https://hermes.lco.global')
CREDIBLE_REGION_PROBABILITIES = '[0.25, 0.5, 0.75, 0.9, 0.95]'
