# -*- coding: utf-8 -*-
#########################################################################
#
# Copyright (C) 2017 OSGeo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

import ast
# Django settings for the GeoNode project.
import os

try:
    from urllib.parse import urlparse, urlunparse
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request
    from urlparse import urlparse, urlunparse
# Load more settings from a file called local_settings.py if it exists
try:
    from undp_png.local_settings import *
#    from geonode.local_settings import *
except ImportError:
    from geonode.settings import *

#
# General Django development settings
#
PROJECT_NAME = 'undp_png'

# add trailing slash to site url. geoserver url will be relative to this
if not SITEURL.endswith('/'):
    SITEURL = '{}/'.format(SITEURL)

SITENAME = os.getenv("SITENAME", 'undp_png')

# Allow proxy host now that we have switched debug off
PROXY_HOST = os.getenv("HTTPS_HOST", 'png-geoportal.org')
PROXY_ALLOWED_HOSTS = [PROXY_HOST, f'www.{PROXY_HOST}', 'geoserver']

# Defines the directory that contains the settings file as the LOCAL_ROOT
# It is used for relative settings elsewhere.
LOCAL_ROOT = os.path.abspath(os.path.dirname(__file__))

WSGI_APPLICATION = "{}.wsgi.application".format(PROJECT_NAME)

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = os.getenv('LANGUAGE_CODE', "en")

if PROJECT_NAME not in INSTALLED_APPS:
    INSTALLED_APPS += (PROJECT_NAME,)

# Location of url mappings
ROOT_URLCONF = os.getenv('ROOT_URLCONF', '{}.urls'.format(PROJECT_NAME))

# Additional directories which hold static files
# - Give priority to local geonode-project ones
STATICFILES_DIRS = [os.path.join(LOCAL_ROOT, "static"), ] + STATICFILES_DIRS

# Location of locale files
LOCALE_PATHS = (
    os.path.join(LOCAL_ROOT, 'locale'),
) + LOCALE_PATHS

TEMPLATES[0]['DIRS'].insert(0, os.path.join(LOCAL_ROOT, "templates"))
loaders = TEMPLATES[0]['OPTIONS'].get('loaders') or [
    'django.template.loaders.filesystem.Loader', 'django.template.loaders.app_directories.Loader']
# loaders.insert(0, 'apptemplates.Loader')
TEMPLATES[0]['OPTIONS']['loaders'] = loaders
TEMPLATES[0].pop('APP_DIRS', None)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d '
                      '%(thread)d %(message)s'
        },
        'simple': {
            'format': '%(message)s',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'console': {
            'level': 'ERROR',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
        }
    },
    "loggers": {
        "django": {
            "handlers": ["console"], "level": "ERROR", },
        "geonode": {
            "handlers": ["console"], "level": "INFO", },
        "geoserver-restconfig.catalog": {
            "handlers": ["console"], "level": "ERROR", },
        "owslib": {
            "handlers": ["console"], "level": "ERROR", },
        "pycsw": {
            "handlers": ["console"], "level": "ERROR", },
        "celery": {
            "handlers": ["console"], "level": "DEBUG", },
        "mapstore2_adapter.plugins.serializers": {
            "handlers": ["console"], "level": "DEBUG", },
        "geonode_logstash.logstash": {
            "handlers": ["console"], "level": "DEBUG", },
    },
}

CENTRALIZED_DASHBOARD_ENABLED = ast.literal_eval(
    os.getenv('CENTRALIZED_DASHBOARD_ENABLED', 'False'))
if CENTRALIZED_DASHBOARD_ENABLED and USER_ANALYTICS_ENABLED and 'geonode_logstash' not in INSTALLED_APPS:
    INSTALLED_APPS += ('geonode_logstash',)

    CELERY_BEAT_SCHEDULE['dispatch_metrics'] = {
        'task': 'geonode_logstash.tasks.dispatch_metrics',
        'schedule': 3600.0,
    }

LDAP_ENABLED = ast.literal_eval(os.getenv('LDAP_ENABLED', 'False'))
if LDAP_ENABLED and 'geonode_ldap' not in INSTALLED_APPS:
    INSTALLED_APPS += ('geonode_ldap',)

# Add your specific LDAP configuration after this comment:
# https://docs.geonode.org/en/master/advanced/contrib/#configuration

SEARCH_FILTERS = {
    'TEXT_ENABLED': True,
    'TYPE_ENABLED': True,
    'CATEGORIES_ENABLED': True,
    'OWNERS_ENABLED': True,
    'KEYWORDS_ENABLED': True,
    'H_KEYWORDS_ENABLED': True,
    'T_KEYWORDS_ENABLED': True,
    'DATE_ENABLED': True,
    'REGION_ENABLED': True,
    'EXTENT_ENABLED': True,
    'GROUPS_ENABLED': False,
    'GROUP_CATEGORIES_ENABLED': False,
}

TWITTER_CARD = ast.literal_eval(os.getenv('TWITTER_CARD', 'False'))

SOCIAL_ORIGINS = [{
    "label": "Share link",
    "url": "{url}",
    "css_class": "link"
}]

DISPLAY_RATINGS = ast.literal_eval(os.getenv('DISPLAY_RATINGS', 'False'))
DISPLAY_COMMENTS = ast.literal_eval(os.getenv('DISPLAY_COMMENTS', 'False'))

FAVORITE_ENABLED = ast.literal_eval(os.getenv('FAVORITE_ENABLED', 'False'))

AUTH_EXEMPT_URLS += ('/maps/*',
                     '/layers/*',
                     '/apps/*',
                     '/about/*',
                     '/faqs/*',
                     '/training/*',
                     '/services/*',
                     '/documents/*',
                     '/search/*',
                     '/account/*',
                     '/api/*',
                     '/base/autocomplete_hierachical_keyword/*',
                     '/base/autocomplete_region/*',
                     '/base/autocomplete_response/*',
                     '/base/groups/autocomplete/*',
                     '/base/people/autocomplete/*'
                     )

# thumbnail settings
THUMBNAIL_GENERATOR_DEFAULT_SIZE = {"width": 420, "height": 350}
THUMBNAIL_GENERATOR_DEFAULT_SIZE_WIDTH = 420
THUMBNAIL_GENERATOR_DEFAULT_SIZE_HEIGHT = 350

DEFAULT_MAP_CENTER = (float(os.environ.get('DEFAULT_MAP_CENTER_X', 147.00)),
                      float(os.environ.get('DEFAULT_MAP_CENTER_Y', -9.5)))

# How tightly zoomed should newly created maps be?
# 0 = entire world;
# maximum zoom is between 12 and 15 (for Google Maps, coverage varies by area)
DEFAULT_MAP_ZOOM = int(os.environ.get('DEFAULT_MAP_ZOOM', 8))

UI_DEFAULT_MANDATORY_FIELDS = [
    'id_resource-title',
    'id_resource-abstract',
    'id_resource-language',
    'id_resource-license',
    'id_resource-regions',
    'id_resource-date_type',
    'id_resource-date',
    'category_form',
    'id_resource-attribution',
]

if MAPBOX_ACCESS_TOKEN:
    DEFAULT_MS2_BACKGROUNDS = [
        {
            "type": "tileprovider",
            "title": "MapBox streets",
            "provider": "custom",
            "name": "MapBox streets",
            "source": "streets-v11",
            "url": f"https://api.mapbox.com/styles/v1/mapbox/streets-v11/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_ACCESS_TOKEN}",
            "thumbURL": f"https://api.mapbox.com/styles/v1/mapbox/streets-v11/tiles/256/6/58/33?access_token={MAPBOX_ACCESS_TOKEN}",
            "group": "background",
            "visibility": True,
            "options": {
                "attribution": 'Imagery from <a href="http://mapbox.com/about/maps/">MapBox</a>',
                "subdomains": ['a', 'b', 'c', 'd']
            }
        },
        {
            "type": "tileprovider",
            "title": "MapBox Outdoors",
            "provider": "custom",
            "name": "MapBox outdoors",
            "source": "outdoors-v11",
            "url": f"https://api.mapbox.com/styles/v1/mapbox/outdoors-v11/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_ACCESS_TOKEN}",
            "thumbURL": f"https://api.mapbox.com/styles/v1/mapbox/outdoors-v11/tiles/256/6/58/33?access_token={MAPBOX_ACCESS_TOKEN}",
            # noqa
            "group": "background",
            "visibility": False,
            "options": {
                "attribution": 'Imagery from <a href="http://mapbox.com/about/maps/">MapBox</a>',
                "subdomains": ['a', 'b', 'c', 'd']
            }
        },
        {
            "type": "tileprovider",
            "title": "MapBox Dark",
            "provider": "custom",
            "name": "MapBox dark",
            "source": "dark-v10",
            "url": f"https://api.mapbox.com/styles/v1/mapbox/dark-v10/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_ACCESS_TOKEN}",
            "thumbURL": f"https://api.mapbox.com/styles/v1/mapbox/dark-v10/tiles/256/6/58/33?access_token={MAPBOX_ACCESS_TOKEN}",
            # noqa
            "group": "background",
            "visibility": False,
            "options": {
                "attribution": 'Imagery from <a href="http://mapbox.com/about/maps/">MapBox</a>',
                "subdomains": ['a', 'b', 'c', 'd']
            }
        },
        {
            "type": "tileprovider",
            "title": "MapBox Satellite",
            "provider": "custom",
            "name": "MapBox satellite",
            "source": "satellite-v9",
            "url": f"https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_ACCESS_TOKEN}",
            "thumbURL": f"https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/256/6/58/33?access_token={MAPBOX_ACCESS_TOKEN}",
            # noqa
            "group": "background",
            "visibility": False,
            "options": {
                "attribution": 'Imagery from <a href="http://mapbox.com/about/maps/">MapBox</a>',
                "subdomains": ['a', 'b', 'c', 'd']
            }
        },
        {
            "type": "tileprovider",
            "title": "MapBox Light",
            "provider": "custom",
            "name": "MapBox light",
            "source": "light-v10",
            "url": f"https://api.mapbox.com/styles/v1/mapbox/light-v10/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_ACCESS_TOKEN}",
            "thumbURL": f"https://api.mapbox.com/styles/v1/mapbox/light-v10/tiles/256/6/58/33?access_token={MAPBOX_ACCESS_TOKEN}",
            # noqa
            "group": "background",
            "visibility": False,
            "options": {
                "attribution": 'Imagery from <a href="http://mapbox.com/about/maps/">MapBox</a>',
                "subdomains": ['a', 'b', 'c', 'd']
            }
        },
        {
            "type": "osm",
            "title": "Open Street Map",
            "name": "mapnik",
            "source": "osm",
            "group": "background",
            "visibility": False
        }, {
            "type": "tileprovider",
            "title": "OpenTopoMap",
            "provider": "OpenTopoMap",
            "name": "OpenTopoMap",
            "source": "OpenTopoMap",
            "group": "background",
            "visibility": False
        }, {
            "type": "wms",
            "title": "Sentinel-2 cloudless - https://s2maps.eu",
            "format": "image/jpeg",
            "id": "s2cloudless",
            "name": "s2cloudless:s2cloudless",
            "url": "https://maps.geo-solutions.it/geoserver/wms",
            "group": "background",
            "thumbURL": f"{SITEURL}static/mapstorestyle/img/s2cloudless-s2cloudless.png",
            "visibility": False
        }, {
            "source": "ol",
            "group": "background",
            "id": "none",
            "name": "empty",
            "title": "Empty Background",
            "type": "empty",
            "visibility": False,
            "args": ["Empty Background", {"visibility": False}]
        }
    ]

    MAPSTORE_BASELAYERS = DEFAULT_MS2_BACKGROUNDS

AVATAR_CACHE_ENABLED = False

SEARCH_FILTERS = {
    'TEXT_ENABLED': True,
    'TYPE_ENABLED': True,
    'CATEGORIES_ENABLED': True,
    'OWNERS_ENABLED': True,
    'KEYWORDS_ENABLED': True,
    'H_KEYWORDS_ENABLED': True,
    'T_KEYWORDS_ENABLED': True,
    'DATE_ENABLED': True,
    'REGION_ENABLED': True,
    'EXTENT_ENABLED': True,
    'GROUPS_ENABLED': False,
    'GROUP_CATEGORIES_ENABLED': False,
}

TWITTER_CARD = ast.literal_eval(os.getenv('TWITTER_CARD', 'False'))

SOCIAL_ORIGINS = [{
    "label": "Share link",
    "url": "{url}",
    "css_class": "link"
}]

AUTH_EXEMPT_URLS += ('/maps/*',
                     '/layers/*',
                     '/apps/*',
                     '/about/*',
                     '/faqs/*',
                     '/training/*',
                     '/services/*',
                     '/documents/*',
                     '/search/*',
                     '/account/*',
                     '/api/*',
                     '/base/autocomplete_hierachical_keyword/*',
                     '/base/autocomplete_region/*',
                     '/base/autocomplete_response/*',
                     '/base/groups/autocomplete/*',
                     '/base/people/autocomplete/*'
                     )

DEFAULT_MAP_ZOOM = int(os.environ.get('DEFAULT_MAP_ZOOM', 8))
