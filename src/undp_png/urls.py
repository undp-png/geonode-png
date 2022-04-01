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

from django.conf.urls import url
from django.views.generic import TemplateView
from geonode.base import register_url_event
from geonode.urls import urlpatterns
from undp_png.views import thumbnail_upload, proxy

urlpatterns += [
    ## include your urls here
    url(r'^faqs/$',
        TemplateView.as_view(template_name='faq.html'),
        name='faqs'),
    url(r'^training/$',
        TemplateView.as_view(template_name='training.html'),
        name='training'),
    # Curated Thumbnail Large
    url(r'^base/(?P<res_id>[^/]+)/thumbnail_upload_large$', thumbnail_upload,
        name='thumbnail_upload_large'),

]

homepage = register_url_event()(TemplateView.as_view(template_name='site_index.html'))

urlpatterns = [
                  url(r'^/?$',
                      homepage,
                      name='home'),
              ] + urlpatterns

# drop proxy from url patterns replace with our own proxy view
urlpatterns = [_ for _ in urlpatterns if not hasattr(_, 'name') or ( hasattr(_, 'name') and _.name != "proxy")] + [
    url(r'^proxy/', proxy, name='proxy'), ]
