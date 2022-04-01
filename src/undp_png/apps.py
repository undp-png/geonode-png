# -*- coding: utf-8 -*-
#########################################################################
#
# Copyright (C) 2018 OSGeo
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
from __future__ import absolute_import, unicode_literals

import os

from django.apps import AppConfig as BaseAppConfig
from django.conf import settings
from django.contrib.staticfiles.templatetags import staticfiles
from django.forms import model_to_dict, HiddenInput
from django.utils.translation import ugettext_lazy as _


def run_setup_hooks(*args, **kwargs):
    from django.conf import settings
    from .celeryapp import app as celeryapp

    LOCAL_ROOT = os.path.abspath(os.path.dirname(__file__))
    settings.TEMPLATES[0]["DIRS"].insert(0, os.path.join(LOCAL_ROOT, "templates"))

    if celeryapp not in settings.INSTALLED_APPS:
        settings.INSTALLED_APPS += (celeryapp,)


class AppConfig(BaseAppConfig):
    name = "undp_png"
    label = "undp_png"

    def _get_logger(self):
        import logging
        return logging.getLogger(self.__class__.__module__)

    def hidden_metadata_fields(self):
        """A list of metadata fields to hide """
        return (
            "data_quality_statement",
            "restriction_code_type",
            "doi",
            "edition"
        )

    def ready(self):
        super(AppConfig, self).ready()
        run_setup_hooks()
        from geonode.documents.forms import DocumentForm
        from geonode.geoapps.forms import GeoAppForm
        from geonode.layers.forms import LayerForm
        from geonode.maps.forms import MapForm

        from geonode.base.api.serializers import ThumbnailUrlField
        from geonode.api.resourcebase_api import CommonModelApi, LayerResource, MapResource, GeoAppResource, \
            DocumentResource
        from geonode.invitations.views import GeoNodeSendInvite
        from mapstore2_adapter.plugins.geonode import GeoNodeMapStore2ConfigConverter

        for app_form in [DocumentForm, GeoAppForm, LayerForm, MapForm]:
            self.patch_resource_base(app_form)
        self.patch_resourcemodel_api(CommonModelApi)
        self.patch_document_resource_model_api(DocumentResource)
        self.patch_layer_resource_model_api(LayerResource)
        self.patch_geoapps_resource_model_api(GeoAppResource)
        self.patch_map_resource_model_api(MapResource)
        self.patch_thumb_serializer(ThumbnailUrlField)
        self.patch_invite_function(GeoNodeSendInvite)
        self.add_mapbox_wmts_sources(GeoNodeMapStore2ConfigConverter)

    def patch_resource_base(self, form):
        self._get_logger().info("Patching Resource Base")

        form.Meta.exclude = [*form.Meta.exclude, *self.hidden_metadata_fields()]

        def __init__(kls, *args, **kwargs):

            super(form, kls).__init__(*args, **kwargs)
            cols_to_exclude = [f for f in kls.fields.keys() if f in kls.Meta.exclude]
            [kls.fields.pop(_) for _ in cols_to_exclude]
            abstract = kls.fields.get("abstract")
            if abstract:
                abstract.label = _('Description')

            attribution = kls.fields.get("attribution")
            attribution_help_text = _('Who created the dataset?')
            if attribution:
                attribution.label = _('Source')
                attribution.help_text = attribution_help_text
            for field in self.hidden_metadata_fields():
                hide_field = kls.fields.get(field)
                if hide_field:
                    hide_field.hidden = True
                    hide_field.widget = HiddenInput()

            group_help_text = _('Who should have access to the data?')
            group = kls.fields.get("group")
            if group:
                group.help_text = group_help_text
            constraints_other = kls.fields.get("constraints_other")
            if constraints_other:
                constraints_other.label = _('Constraints / Caveats')

            for field in kls.fields:
                help_text = kls.fields[field].help_text
                if help_text != '':
                    kls.fields[field].widget.attrs.update(
                        {
                            'class': 'has-external-popover',
                            'data-content': help_text,
                            'data-placement': 'right',
                            'data-container': 'body',
                            'data-html': 'true'})

        form.__init__ = __init__

    def patch_thumbnail(self, thumbnail_class):
        """Attempt to patch geonode default thumbnail sizing

        https://github.com/GeoNode/geonode/blob/3fd76478bb6200d837a648ce2b1207b435efc509/geonode/base/views.py
        https://github.com/GeoNode/geonode/blob/master/geonode/thumbs/utils.py
        https://github.com/GeoNode/geonode/blob/42f5405bb1839910a6800ece8d31028049f90296/geonode/base/models.py#L1984

        """
        from imagekit.models import ImageSpecField
        from imagekit import ImageSpec, register
        from imagekit.exceptions import AlreadyRegistered
        from imagekit.processors import ResizeToFill
        from imagekit.cachefiles.backends import Simple
        from django.core.files.storage import default_storage as storage
        import os

        class LargeThumbnail(ImageSpec):
            processors = [ResizeToFill(420, 350)]
            format = 'JPEG'
            options = {'quality': 60}

        try:
            register.generator('base:curatedthumbnail:img_thumbnail_2', LargeThumbnail)
        except AlreadyRegistered as exc:
            pass
        except Exception as exc:
            self._get_logger().exception(exc)
            pass

        img_thumbnail = ImageSpecField(source='img',
                                       processors=[ResizeToFill(420, 350)],
                                       format='PNG',
                                       options={'quality': 60})
        self._get_logger().info("Patching Thumbnail")

        @property
        def thumbnail_url(kls):
            try:
                if not Simple()._exists(kls.img_thumbnail):
                    Simple().generate(kls.img_thumbnail, force=True)
                upload_path = storage.path(kls.img_thumbnail.name)
                actual_name = os.path.basename(storage.url(upload_path))
                _upload_path = os.path.join(os.path.dirname(upload_path), actual_name)
                if not os.path.exists(_upload_path):
                    os.rename(upload_path, _upload_path)
                return kls.img_thumbnail.url
            except Exception as e:
                print(e)
            return ''

        thumbnail_class.add_to_class("img_thumbnail", img_thumbnail)
        thumbnail_class.add_to_class("thumbnail_url", thumbnail_url)

    def patch_resourcemodel_api(self, commonmodel):

        def format_objects(kls, objects):
            """
            Format the objects for output in a response.
            """
            for key in ('site_url', 'has_time'):
                if key in kls.VALUES:
                    idx = kls.VALUES.index(key)
                    del kls.VALUES[idx]

            # hack needed because dehydrate does not seem to work in CommonModelApi
            formatted_objects = []
            for obj in objects:
                formatted_obj = model_to_dict(obj, fields=kls.VALUES)
                if 'site_url' not in formatted_obj or len(formatted_obj['site_url']) == 0:
                    formatted_obj['site_url'] = settings.SITEURL

                if formatted_obj['thumbnail_url'] and len(formatted_obj['thumbnail_url']) == 0:
                    formatted_obj['thumbnail_url'] = staticfiles.static(settings.MISSING_THUMBNAIL)

                formatted_obj['owner__username'] = obj.owner.username
                formatted_obj['owner_name'] = obj.owner.get_full_name() or obj.owner.username

                if hasattr(obj, 'curatedthumbnail'):
                    try:
                        if hasattr(obj.curatedthumbnail.img_thumbnail, 'url'):
                            formatted_obj['thumbnail_url'] = obj.curatedthumbnail.thumbnail_url
                        # Overwrite with large thumb instead
                    except Exception as e:
                        self._get_logger().exception(e)
                # replace thumbnail_url with curated_thumbs
                if hasattr(obj, 'curatedthumbnaillarge'):
                    try:
                        # Overwrite with large thumb instead
                        if hasattr(obj.curatedthumbnaillarge.img_thumbnail, 'url'):
                            formatted_obj['thumbnail_url'] = obj.curatedthumbnaillarge.thumbnail_url
                    except Exception as e:
                        self._get_logger().exception(e)

                formatted_objects.append(formatted_obj)

            return formatted_objects

        commonmodel.format_objects = format_objects

    def patch_geoapps_resource_model_api(self, geoappsmodel):
        from geonode.groups.models import GroupProfile
        def format_objects(kls, objects):
            """
            Formats the objects and provides reference to list of layers in GeoApp
            resources.

            :param objects: GeoApp objects
            """
            formatted_objects = []
            for obj in objects:
                # convert the object to a dict using the standard values.
                formatted_obj = model_to_dict(obj, fields=kls.VALUES)
                username = obj.owner.get_username()
                full_name = (obj.owner.get_full_name() or username)
                formatted_obj['owner__username'] = username
                formatted_obj['owner_name'] = full_name
                if obj.category:
                    formatted_obj['category__gn_description'] = obj.category.gn_description
                if obj.group:
                    formatted_obj['group'] = obj.group
                    try:
                        formatted_obj['group_name'] = GroupProfile.objects.get(slug=obj.group.name)
                    except GroupProfile.DoesNotExist:
                        formatted_obj['group_name'] = obj.group

                formatted_obj['keywords'] = [k.name for k in obj.keywords.all()] if obj.keywords else []
                formatted_obj['regions'] = [r.name for r in obj.regions.all()] if obj.regions else []

                if 'site_url' not in formatted_obj or len(formatted_obj['site_url']) == 0:
                    formatted_obj['site_url'] = settings.SITEURL

                # Probe Remote Services
                formatted_obj['store_type'] = 'geoapp'
                formatted_obj['online'] = True

                # replace thumbnail_url with curated_thumbs
                if hasattr(obj, 'curatedthumbnail'):
                    try:
                        if hasattr(obj.curatedthumbnail.img_thumbnail, 'url'):
                            formatted_obj['thumbnail_url'] = obj.curatedthumbnail.thumbnail_url
                    except Exception as e:
                        self._get_logger().exception(e)
                        # replace thumbnail_url with curated_thumbs
                if hasattr(obj, 'curatedthumbnaillarge'):
                    try:
                        # Overwrite with large thumb instead
                        if hasattr(obj.curatedthumbnaillarge.img_thumbnail, 'url'):
                            formatted_obj['thumbnail_url'] = obj.curatedthumbnaillarge.thumbnail_url
                    except Exception as e:
                        self._get_logger().exception(e)

                formatted_objects.append(formatted_obj)
            return formatted_objects

        geoappsmodel.format_objects = format_objects

    def patch_document_resource_model_api(self, document_model):
        from geonode.groups.models import GroupProfile
        def format_objects(kls, objects):
            """
            Formats the objects and provides reference to list of layers in map
            resources.

            :param objects: Map objects
            """
            formatted_objects = []
            for obj in objects:
                # convert the object to a dict using the standard values.
                formatted_obj = model_to_dict(obj, fields=kls.VALUES)
                username = obj.owner.get_username()
                full_name = (obj.owner.get_full_name() or username)
                formatted_obj['owner__username'] = username
                formatted_obj['owner_name'] = full_name
                if obj.category:
                    formatted_obj['category__gn_description'] = _(obj.category.gn_description)
                if obj.group:
                    formatted_obj['group'] = obj.group
                    try:
                        formatted_obj['group_name'] = GroupProfile.objects.get(slug=obj.group.name)
                    except GroupProfile.DoesNotExist:
                        formatted_obj['group_name'] = obj.group

                formatted_obj['keywords'] = [k.name for k in obj.keywords.all()] if obj.keywords else []
                formatted_obj['regions'] = [r.name for r in obj.regions.all()] if obj.regions else []

                if 'site_url' not in formatted_obj or len(formatted_obj['site_url']) == 0:
                    formatted_obj['site_url'] = settings.SITEURL

                # Probe Remote Services
                formatted_obj['store_type'] = 'dataset'
                formatted_obj['online'] = True

                # replace thumbnail_url with curated_thumbs
                if hasattr(obj, 'curatedthumbnail'):
                    try:
                        if hasattr(obj.curatedthumbnail.img_thumbnail, 'url'):
                            formatted_obj['thumbnail_url'] = obj.curatedthumbnail.thumbnail_url
                    except Exception as e:
                        self._get_logger().exception(e)
                if hasattr(obj, 'curatedthumbnaillarge'):
                    try:
                        # Overwrite with large thumb instead
                        if hasattr(obj.curatedthumbnaillarge.img_thumbnail, 'url'):
                            formatted_obj['thumbnail_url'] = obj.curatedthumbnaillarge.thumbnail_url
                    except Exception as e:
                        self._get_logger().exception(e)

                formatted_objects.append(formatted_obj)
            return formatted_objects

        document_model.format_objects = format_objects

    def patch_layer_resource_model_api(self, layer_model):
        from geonode.groups.models import GroupProfile
        def format_objects(kls, objects):
            """
            Formats the object.
            """
            formatted_objects = []
            for obj in objects:
                # convert the object to a dict using the standard values.
                # includes other values
                values = kls.VALUES + [
                    'alternate',
                    'name'
                ]
                formatted_obj = model_to_dict(obj, fields=values)
                username = obj.owner.get_username()
                full_name = (obj.owner.get_full_name() or username)
                formatted_obj['owner__username'] = username
                formatted_obj['owner_name'] = full_name
                if obj.category:
                    formatted_obj['category__gn_description'] = _(obj.category.gn_description)
                if obj.group:
                    formatted_obj['group'] = obj.group
                    try:
                        formatted_obj['group_name'] = GroupProfile.objects.get(slug=obj.group.name)
                    except GroupProfile.DoesNotExist:
                        formatted_obj['group_name'] = obj.group

                formatted_obj['keywords'] = [k.name for k in obj.keywords.all()] if obj.keywords else []
                formatted_obj['regions'] = [r.name for r in obj.regions.all()] if obj.regions else []

                # provide style information
                bundle = kls.build_bundle(obj=obj)
                formatted_obj['default_style'] = kls.default_style.dehydrate(
                    bundle, for_list=True)

                # Add resource uri
                formatted_obj['resource_uri'] = kls.get_resource_uri(bundle)

                formatted_obj['links'] = kls.dehydrate_ogc_links(bundle)

                if 'site_url' not in formatted_obj or len(formatted_obj['site_url']) == 0:
                    formatted_obj['site_url'] = settings.SITEURL

                # Probe Remote Services
                formatted_obj['store_type'] = 'dataset'
                formatted_obj['online'] = True
                if hasattr(obj, 'storeType'):
                    formatted_obj['store_type'] = obj.storeType
                    if obj.storeType == 'remoteStore' and hasattr(obj, 'remote_service'):
                        if obj.remote_service:
                            formatted_obj['online'] = (obj.remote_service.probe == 200)
                        else:
                            formatted_obj['online'] = False

                formatted_obj['gtype'] = kls.dehydrate_gtype(bundle)

                # replace thumbnail_url with curated_thumbs
                if hasattr(obj, 'curatedthumbnail'):
                    try:
                        if hasattr(obj.curatedthumbnail.img_thumbnail, 'url'):
                            formatted_obj['thumbnail_url'] = obj.curatedthumbnail.thumbnail_url
                    except Exception as e:
                        self._get_logger().exception(e)
                if hasattr(obj, 'curatedthumbnaillarge'):
                    try:
                        # Overwrite with large thumb instead
                        if hasattr(obj.curatedthumbnaillarge.img_thumbnail, 'url'):
                            formatted_obj['thumbnail_url'] = obj.curatedthumbnaillarge.thumbnail_url
                    except Exception as e:
                        self._get_logger().exception(e)

                formatted_obj['processed'] = obj.instance_is_processed
                # put the object on the response stack
                formatted_objects.append(formatted_obj)
            return formatted_objects

        layer_model.format_objects = format_objects

    def patch_map_resource_model_api(self, map_model):
        from geonode.groups.models import GroupProfile
        def format_objects(kls, objects):
            """
            Formats the objects and provides reference to list of layers in map
            resources.

            :param objects: Map objects
            """
            formatted_objects = []
            for obj in objects:
                # convert the object to a dict using the standard values.
                formatted_obj = model_to_dict(obj, fields=kls.VALUES)
                username = obj.owner.get_username()
                full_name = (obj.owner.get_full_name() or username)
                formatted_obj['owner__username'] = username
                formatted_obj['owner_name'] = full_name
                if obj.category:
                    formatted_obj['category__gn_description'] = _(obj.category.gn_description)
                if obj.group:
                    formatted_obj['group'] = obj.group
                    try:
                        formatted_obj['group_name'] = GroupProfile.objects.get(slug=obj.group.name)
                    except GroupProfile.DoesNotExist:
                        formatted_obj['group_name'] = obj.group

                formatted_obj['keywords'] = [k.name for k in obj.keywords.all()] if obj.keywords else []
                formatted_obj['regions'] = [r.name for r in obj.regions.all()] if obj.regions else []

                if 'site_url' not in formatted_obj or len(formatted_obj['site_url']) == 0:
                    formatted_obj['site_url'] = settings.SITEURL

                # Probe Remote Services
                formatted_obj['store_type'] = 'map'
                formatted_obj['online'] = True

                # get map layers
                map_layers = obj.layers
                formatted_layers = []
                map_layer_fields = [
                    'id',
                    'stack_order',
                    'format',
                    'name',
                    'opacity',
                    'group',
                    'visibility',
                    'transparent',
                    'ows_url',
                    'layer_params',
                    'source_params',
                    'local'
                ]
                for layer in map_layers:
                    formatted_map_layer = model_to_dict(
                        layer, fields=map_layer_fields)
                    formatted_layers.append(formatted_map_layer)
                formatted_obj['layers'] = formatted_layers

                # replace thumbnail_url with curated_thumbs
                if hasattr(obj, 'curatedthumbnail'):
                    try:
                        if hasattr(obj.curatedthumbnail.img_thumbnail, 'url'):
                            formatted_obj['thumbnail_url'] = obj.curatedthumbnail.thumbnail_url
                    except Exception as e:
                        self._get_logger().exception(e)
                if hasattr(obj, 'curatedthumbnaillarge'):
                    try:
                        # Overwrite with large thumb instead
                        if hasattr(obj.curatedthumbnaillarge.img_thumbnail, 'url'):
                            formatted_obj['thumbnail_url'] = obj.curatedthumbnaillarge.thumbnail_url
                    except Exception as e:
                        self._get_logger().exception(e)

                formatted_objects.append(formatted_obj)
            return formatted_objects

        map_model.format_objects = format_objects

    def patch_thumb_serializer(self, thumbnailserializer):
        from geonode.base.utils import build_absolute_uri
        def get_attribute(kls, instance):
            thumbnail_url = instance.thumbnail_url
            if hasattr(instance, 'curatedthumbnail'):
                try:
                    if hasattr(instance.curatedthumbnail.img_thumbnail, 'url'):
                        thumbnail_url = instance.curatedthumbnail.thumbnail_url
                except Exception as e:
                    self._get_logger().exception(e)
            # curated thumbnail large overwrites
            if hasattr(instance, 'curatedthumbnaillarge'):
                try:
                    if hasattr(instance.curatedthumbnaillarge.img_thumbnail, 'url'):
                        thumbnail_url = instance.curatedthumbnaillarge.thumbnail_url
                except Exception as e:
                    self._get_logger().exception(e)

            return build_absolute_uri(thumbnail_url)

        thumbnailserializer.get_attribute = get_attribute

    def patch_invite_function(self, invite_view):

        def geonode_invite_form_invalid(kls, form, emails=None, e=None):
            if e:
                return kls.render_to_response(
                    kls.get_context_data(
                        error_message=_("Sorry, it was not possible to invite '%(email)s'"
                                        " due to the following issue: %(error)s (%(type)s)") % {
                                          "email": emails, "error": str(e), "type": type(e)}))
            else:
                return kls.render_to_response(
                    kls.get_context_data(form=form))

        def geonode_invite_form_valid(kls, form):
            emails = form.cleaned_data["email"]
            invited = []

            invite = None
            try:
                invites = form.save(emails)
                for invite_obj in invites:
                    invite = invite_obj
                    invite.inviter = kls.request.user
                    invite.save()
                    # invite.send_invitation(self.request)
                    kls.send_invitation(invite, kls.request)
                    invited.append(invite_obj.email)
            except Exception as e:
                if invite:
                    invite.delete()
                return kls.form_invalid(form, emails, e)

            return kls.render_to_response(
                kls.get_context_data(
                    success_message=_("Invitation successfully sent to '%(email)s'") % {
                        "email": ', '.join(invited)}))

        invite_view.form_valid = geonode_invite_form_valid
        invite_view.form_invalid = geonode_invite_form_invalid

    def add_mapbox_wmts_sources(self, ms2_config):
        """This is a hack to add MapBox as a WMTS source to MapStore2.
        """
        from six import string_types

        try:
            import json
        except ImportError:
            from django.utils import simplejson as json

        import traceback

        from mapstore2_adapter.utils import (
            get_valid_number)
        from mapstore2_adapter.settings import (
            MAP_BASELAYERS,
            CATALOGUE_SERVICES,
            CATALOGUE_SELECTED_SERVICE)

        from django.core.serializers.json import DjangoJSONEncoder
        from django.conf import settings
        from mapstore2_adapter.plugins.geonode import unsafe_chars

        def convert(kls, viewer, request):
            """
                input: GeoNode JSON Gxp Config
                output: MapStore2 compliant str(config)
            """
            # Initialization
            viewer_obj = json.loads(viewer)

            map_id = None
            if 'id' in viewer_obj and viewer_obj['id']:
                try:
                    map_id = int(viewer_obj['id'])
                except Exception:
                    pass

            data = {}
            data['version'] = 2

            # Map Definition
            try:
                # Map Definition
                ms2_map = {}
                ms2_map['projection'] = viewer_obj['map']['projection']
                ms2_map['units'] = viewer_obj['map']['units']
                ms2_map['zoom'] = viewer_obj['map']['zoom'] if viewer_obj['map']['zoom'] > 0 else 2
                ms2_map['maxExtent'] = viewer_obj['map']['maxExtent']
                ms2_map['maxResolution'] = viewer_obj['map']['maxResolution']

                # Backgrounds
                backgrounds = kls.getBackgrounds(viewer, MAP_BASELAYERS)
                if backgrounds:
                    ms2_map['layers'] = backgrounds
                else:
                    ms2_map['layers'] = MAP_BASELAYERS

                # add mapbox sources
                ms2_map['sources'] = {
                    f"https://api.mapbox.com/styles/v1/mapbox/streets-v11/wmts?access_token={settings.MAPBOX_ACCESS_TOKEN}": {
                        "tileMatrixSet": {
                            "google3857": {
                                'ows:Identifier': 'google3857',
                                'ows:BoundingBox': {
                                    "$": {
                                        "crs": 'urn:ogc:def:crs:EPSG:6.18.3:3857'
                                    },
                                    'ows:LowerCorner': '977650 5838030',
                                    'ows:UpperCorner': '1913530 6281290'
                                },
                                'ows:SupportedCRS': 'urn:ogc:def:crs:EPSG:6.18.3:3857',
                                "WellKnownScaleSet": 'urn:ogc:def:wkss:OGC:1.0:GoogleMapsCompatible',
                                "TileMatrix": [{'MatrixHeight': '1',
                                                'MatrixWidth': '1',
                                                'ScaleDenominator': '559082264.029',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '0'},
                                               {'MatrixHeight': '2',
                                                'MatrixWidth': '2',
                                                'ScaleDenominator': '279541132.014',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '1'},
                                               {'MatrixHeight': '4',
                                                'MatrixWidth': '4',
                                                'ScaleDenominator': '139770566.007',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '2'},
                                               {'MatrixHeight': '8',
                                                'MatrixWidth': '8',
                                                'ScaleDenominator': '69885283.0036',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '3'},
                                               {'MatrixHeight': '16',
                                                'MatrixWidth': '16',
                                                'ScaleDenominator': '34942641.5018',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '4'},
                                               {'MatrixHeight': '32',
                                                'MatrixWidth': '32',
                                                'ScaleDenominator': '17471320.7509',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '5'},
                                               {'MatrixHeight': '64',
                                                'MatrixWidth': '64',
                                                'ScaleDenominator': '8735660.37545',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '6'},
                                               {'MatrixHeight': '128',
                                                'MatrixWidth': '128',
                                                'ScaleDenominator': '4367830.18772',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '7'},
                                               {'MatrixHeight': '256',
                                                'MatrixWidth': '256',
                                                'ScaleDenominator': '2183915.09386',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '8'},
                                               {'MatrixHeight': '512',
                                                'MatrixWidth': '512',
                                                'ScaleDenominator': '1091957.54693',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '9'},
                                               {'MatrixHeight': '1024',
                                                'MatrixWidth': '1024',
                                                'ScaleDenominator': '545978.773466',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '10'},
                                               {'MatrixHeight': '2048',
                                                'MatrixWidth': '2048',
                                                'ScaleDenominator': '272989.386733',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '11'},
                                               {'MatrixHeight': '4096',
                                                'MatrixWidth': '4096',
                                                'ScaleDenominator': '136494.693366',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '12'},
                                               {'MatrixHeight': '8192',
                                                'MatrixWidth': '8192',
                                                'ScaleDenominator': '68247.3466832',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '13'},
                                               {'MatrixHeight': '16384',
                                                'MatrixWidth': '16384',
                                                'ScaleDenominator': '34123.6733416',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '14'},
                                               {'MatrixHeight': '32768',
                                                'MatrixWidth': '32768',
                                                'ScaleDenominator': '17061.8366708',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '15'},
                                               {'MatrixHeight': '65536',
                                                'MatrixWidth': '65536',
                                                'ScaleDenominator': '8530.9183354',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '16'},
                                               {'MatrixHeight': '131072',
                                                'MatrixWidth': '131072',
                                                'ScaleDenominator': '4265.4591677',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '17'},
                                               {'MatrixHeight': '262144',
                                                'MatrixWidth': '262144',
                                                'ScaleDenominator': '2132.72958385',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '18'},
                                               {'MatrixHeight': '524288',
                                                'MatrixWidth': '524288',
                                                'ScaleDenominator': '1066.36479192',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '19'},
                                               {'MatrixHeight': '1048576',
                                                'MatrixWidth': '1048576',
                                                'ScaleDenominator': '533.182395962',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '20'},
                                               {'MatrixHeight': '2097152',
                                                'MatrixWidth': '2097152',
                                                'ScaleDenominator': '266.591197981',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '21'},
                                               {'MatrixHeight': '4194304',
                                                'MatrixWidth': '4194304',
                                                'ScaleDenominator': '133.296',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '22'},
                                               {'MatrixHeight': '8388608',
                                                'MatrixWidth': '8388608',
                                                'ScaleDenominator': '66.648',
                                                'TileHeight': '256',
                                                'TileWidth': '256',
                                                'TopLeftCorner': '-20037508.3428 20037508.3428',
                                                'ows:Identifier': '23'}]
                            },

                        }}}
                if settings.BING_API_KEY:
                    ms2_map['bingApiKey'] = settings.BING_API_KEY

                # Security Info
                info = {}
                info['canDelete'] = False
                info['canEdit'] = False
                info['description'] = viewer_obj['about']['abstract']
                info['id'] = map_id
                info['name'] = viewer_obj['about']['title']
                ms2_map['info'] = info

                # Overlays
                overlays, selected = kls.get_overlays(viewer, request=request)
                if selected and 'name' in selected and selected['name'] and not map_id:
                    # We are generating a Layer Details View
                    center, zoom = kls.get_center_and_zoom(viewer_obj['map'], selected)
                    ms2_map['center'] = center
                    ms2_map['zoom'] = zoom

                    try:
                        # - extract from GeoNode guardian
                        from geonode.layers.views import (_resolve_layer,
                                                          _PERMISSION_MSG_MODIFY,
                                                          _PERMISSION_MSG_DELETE)
                        if _resolve_layer(request,
                                          selected['name'],
                                          'base.change_resourcebase',
                                          _PERMISSION_MSG_MODIFY):
                            info['canEdit'] = True

                        if _resolve_layer(request,
                                          selected['name'],
                                          'base.delete_resourcebase',
                                          _PERMISSION_MSG_DELETE):
                            info['canDelete'] = True
                    except Exception:
                        tb = traceback.format_exc()
                        self._get_logger().debug(tb)
                else:
                    # We are getting the configuration of a Map
                    # On GeoNode model the Map Center is always saved in 4326
                    _x = get_valid_number(viewer_obj['map']['center'][0])
                    _y = get_valid_number(viewer_obj['map']['center'][1])
                    _crs = 'EPSG:4326'
                    if _x > 360.0 or _x < -360.0:
                        _crs = viewer_obj['map']['projection']
                    ms2_map['center'] = {
                        'x': _x,
                        'y': _y,
                        'crs': _crs
                    }
                    try:
                        # - extract from GeoNode guardian
                        from geonode.maps.views import (_resolve_map,
                                                        _PERMISSION_MSG_SAVE,
                                                        _PERMISSION_MSG_DELETE)
                        if _resolve_map(request,
                                        str(map_id),
                                        'base.change_resourcebase',
                                        _PERMISSION_MSG_SAVE):
                            info['canEdit'] = True

                        if _resolve_map(request,
                                        str(map_id),
                                        'base.delete_resourcebase',
                                        _PERMISSION_MSG_DELETE):
                            info['canDelete'] = True
                    except Exception:
                        tb = traceback.format_exc()
                        self._get_logger().debug(tb)

                for overlay in overlays:
                    if 'name' in overlay and overlay['name']:
                        ms2_map['layers'].append(overlay)

                data['map'] = ms2_map
            except Exception:
                # traceback.print_exc()
                tb = traceback.format_exc()
                self._get_logger().debug(tb)

            # Additional Configurations
            if map_id:
                from mapstore2_adapter import fixup_map
                from mapstore2_adapter.api.models import MapStoreResource
                try:
                    fixup_map(map_id)
                    ms2_resource = MapStoreResource.objects.get(id=map_id)
                    ms2_map_data = ms2_resource.data.blob
                    if isinstance(ms2_map_data, string_types):
                        ms2_map_data = json.loads(ms2_map_data)
                    if 'map' in ms2_map_data:
                        for _k, _v in ms2_map_data['map'].items():
                            if _k not in data['map']:
                                data['map'][_k] = ms2_map_data['map'][_k]
                        del ms2_map_data['map']
                    data.update(ms2_map_data)
                except Exception:
                    # traceback.print_exc()
                    tb = traceback.format_exc()
                    self._get_logger().debug(tb)

            # Default Catalogue Services Definition
            try:
                ms2_catalogue = {}
                ms2_catalogue['selectedService'] = CATALOGUE_SELECTED_SERVICE
                ms2_catalogue['services'] = CATALOGUE_SERVICES
                data['catalogServices'] = ms2_catalogue
            except Exception:
                # traceback.print_exc()
                tb = traceback.format_exc()
                self._get_logger().debug(tb)

            json_str = json.dumps(data, cls=DjangoJSONEncoder, sort_keys=True)
            for (c, d) in unsafe_chars.items():
                json_str = json_str.replace(c, d)

            return json_str

        ms2_config.convert = convert
