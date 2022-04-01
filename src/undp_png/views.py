# -*- coding: utf-8 -*-
"""Custom views for UNDP PNG.

@Date : 2022-01-15
@Author : CPoole
"""
import gzip
import io
import logging
import re
from distutils.version import StrictVersion
from json import JSONDecodeError
from urllib.parse import urljoin, urlparse, urlsplit

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http.request import validate_host
from django.shortcuts import render
from django.views.decorators.csrf import requires_csrf_token
from geonode.base.models import (
    ResourceBase
)

from .forms import CuratedThumbnailForm

try:
    import json
except ImportError:
    from django.utils import simplejson as json
from hyperlink import URL

from geonode import geoserver  # noqa
from geonode.proxy.views import TIMEOUT, ows_regexp, fetch_response_headers
from geonode.utils import (
    check_ogc_backend,
    get_headers,
    http_client,
    resolve_object,
)


logger = logging.getLogger(__name__)


@requires_csrf_token
def proxy(request, url=None, response_callback=None,
          sec_chk_hosts=True, sec_chk_rules=True, timeout=None,
          allowed_hosts=[], **kwargs):
    # Request default timeout
    if not timeout:
        timeout = TIMEOUT

    # Security rules and settings
    PROXY_ALLOWED_HOSTS = getattr(settings, 'PROXY_ALLOWED_HOSTS', ())

    # Sanity url checks
    if 'url' not in request.GET and not url:
        return HttpResponse("The proxy service requires a URL-encoded URL as a parameter.",
                            status=400,
                            content_type="text/plain"
                            )

    raw_url = url or request.GET['url']
    raw_url = urljoin(
        settings.SITEURL,
        raw_url) if raw_url.startswith("/") else raw_url
    url = urlsplit(raw_url)
    scheme = str(url.scheme)
    locator = str(url.path)
    if url.query != "":
        locator += f"?{url.query}"
    if url.fragment != "":
        locator += f"#{url.fragment}"

    # White-Black Listing Hosts
    site_url = urlsplit(settings.SITEURL)
    if sec_chk_hosts and not settings.DEBUG:

        # Attach current SITEURL
        if site_url.hostname not in PROXY_ALLOWED_HOSTS:
            PROXY_ALLOWED_HOSTS += (site_url.hostname,)

        # Attach current hostname
        if check_ogc_backend(geoserver.BACKEND_PACKAGE):
            from geonode.geoserver.helpers import ogc_server_settings
            hostname = (
                ogc_server_settings.hostname,
            ) if ogc_server_settings else ()
            if hostname not in PROXY_ALLOWED_HOSTS:
                PROXY_ALLOWED_HOSTS += hostname

        # Check OWS regexp
        if url.query and ows_regexp.match(url.query):
            ows_tokens = ows_regexp.match(url.query).groups()
            if len(ows_tokens) == 4 and 'version' == ows_tokens[0] and StrictVersion(
                    ows_tokens[1]) >= StrictVersion("1.0.0") and StrictVersion(
                ows_tokens[1]) <= StrictVersion("3.0.0") and ows_tokens[2].lower() in (
                    'getcapabilities') and ows_tokens[3].upper() in ('OWS', 'WCS', 'WFS', 'WMS', 'WPS', 'CSW'):
                if url.hostname not in PROXY_ALLOWED_HOSTS:
                    PROXY_ALLOWED_HOSTS += (url.hostname,)

        # Check Remote Services base_urls
        from geonode.services.models import Service
        for _s in Service.objects.all():
            _remote_host = urlsplit(_s.base_url).hostname
            PROXY_ALLOWED_HOSTS += (_remote_host,)

        if not validate_host(
                url.hostname, PROXY_ALLOWED_HOSTS):
            return HttpResponse("DEBUG is set to False but the host of the path provided to the proxy service"
                                " is not in the PROXY_ALLOWED_HOSTS setting.",
                                status=403,
                                content_type="text/plain"
                                )

    # Security checks based on rules; allow only specific requests
    if sec_chk_rules:
        # TODO: Not yet implemented
        pass

    # Collecting headers and cookies
    headers, access_token = get_headers(request, url, raw_url, allowed_hosts=allowed_hosts)

    # Inject access_token if necessary
    parsed = urlparse(raw_url)
    parsed._replace(path=locator.encode('utf8'))
    if parsed.netloc == site_url.netloc and scheme != site_url.scheme:
        parsed = parsed._replace(scheme=site_url.scheme)

    _url = parsed.geturl()

    # Some clients / JS libraries generate URLs with relative URL paths, e.g.
    # "http://host/path/path/../file.css", which the requests library cannot
    # currently handle (https://github.com/kennethreitz/requests/issues/2982).
    # We parse and normalise such URLs into absolute paths before attempting
    # to proxy the request.
    _url = URL.from_text(_url).normalize().to_text()

    if request.method == "GET" and access_token and 'access_token' not in _url:
        query_separator = '&' if '?' in _url else '?'
        _url = f'{_url}{query_separator}access_token={access_token}'

    _data = request.body.decode('utf-8')
    print_re = re.compile(r'/pdf/create.json', re.I)
    if print_re.search(_url):
        try:
            json_data = json.loads(_data)
            logger.debug(json_data)
            print(json_data)
            # check for all requests first and layer['type'].lower() == "wmts"
            contains_mapbox_req = 'layers' in json.loads(_data) and any(['mapbox' in layer.get('baseURL',"")
                                                                         for layer in json_data.get('layers', []) if 'baseURL' in layer])
            # Add Mapbox access token to customParams on any WMTS requests to mapbox
            if request.method == "POST" and contains_mapbox_req:
                for layer in json_data.get('layers', []):
                    if 'mapbox' in layer.get('baseURL',""):
                        # Geonode is setting WMTS customParams with a space try adding both ??? :q!
                        if 'customParams ' in layer:
                            layer['customParams ']['access_token'] = settings.MAPBOX_ACCESS_TOKEN
                        else:
                            layer['customParams '] = {'access_token': settings.MAPBOX_ACCESS_TOKEN}
                            # remove typO from customParams
                            del layer['customParams ']
                        if 'customParams' in layer:
                            layer['customParams']['access_token'] = settings.MAPBOX_ACCESS_TOKEN
                        else:
                            layer['customParams'] = {'access_token': settings.MAPBOX_ACCESS_TOKEN}
                        if layer.get("type", "") == "xyz":
                            # remove mapbox token
                            layer["path_format"] = layer.get("path_format","").split("?")[0]
                _data = json.dumps(json_data)
                print("Changed data found mapbox layer")

            logger.debug(_data)
            print(_data)
        except JSONDecodeError as exc:
            logger.exception(exc)

    # Avoid translating local geoserver calls into external ones
    if check_ogc_backend(geoserver.BACKEND_PACKAGE):
        from geonode.geoserver.helpers import ogc_server_settings
        _url = _url.replace(
            f'{settings.SITEURL}geoserver',
            ogc_server_settings.LOCATION.rstrip('/'))
        _data = _data.replace(
            f'{settings.SITEURL}geoserver',
            ogc_server_settings.LOCATION.rstrip('/'))

    response, content = http_client.request(
        _url,
        method=request.method,
        data=_data.encode('utf-8'),
        headers=headers,
        timeout=timeout,
        user=request.user)
    if response is None:
        return HttpResponse(
            content=content,
            reason=content,
            status=500)
    content = response.content or response.reason
    status = response.status_code
    response_headers = response.headers
    content_type = response.headers.get('Content-Type')

    if status >= 400:
        _response = HttpResponse(
            content=content,
            reason=content,
            status=status,
            content_type=content_type)
        return fetch_response_headers(_response, response_headers)

    # decompress GZipped responses if not enabled
    # if content and response and response.getheader('Content-Encoding') == 'gzip':
    if content and content_type and content_type == 'gzip':
        buf = io.BytesIO(content)
        with gzip.GzipFile(fileobj=buf) as f:
            content = f.read()
        buf.close()

    PLAIN_CONTENT_TYPES = [
        'text',
        'plain',
        'html',
        'json',
        'xml',
        'gml'
    ]
    for _ct in PLAIN_CONTENT_TYPES:
        if content_type and _ct in content_type and not isinstance(content, str):
            try:
                content = content.decode()
                break
            except Exception:
                pass

    if response and response_callback:
        kwargs = {} if not kwargs else kwargs
        kwargs.update({
            'response': response,
            'content': content,
            'status': status,
            'response_headers': response_headers,
            'content_type': content_type
        })
        return response_callback(**kwargs)
    else:
        # If we get a redirect, let's add a useful message.
        if status and status in (301, 302, 303, 307):
            _response = HttpResponse((f"This proxy does not support redirects. The server in '{url}' "
                                      f"asked for a redirect to '{response.getheader('Location')}'"),
                                     status=status,
                                     content_type=content_type
                                     )
            _response['Location'] = response.getheader('Location')
            return fetch_response_headers(_response, response_headers)
        else:
            def _get_message(text):
                _s = text
                if isinstance(text, bytes):
                    _s = text.decode("utf-8", "replace")
                try:
                    found = re.search('<b>Message</b>(.+?)</p>', _s).group(1).strip()
                except Exception:
                    found = _s
                return found

            _response = HttpResponse(
                content=content,
                reason=_get_message(content) if status not in (200, 201) else None,
                status=status,
                content_type=content_type)
            return fetch_response_headers(_response, response_headers)


def thumbnail_upload(
        request,
        res_id,
        template='base/thumbnail_upload.html'):
    try:
        res = resolve_object(
            request, ResourceBase, {
                'id': res_id}, 'base.change_resourcebase')
    except PermissionDenied:
        return HttpResponse(
            'You are not allowed to change permissions for this resource',
            status=401,
            content_type='text/plain')

    form = CuratedThumbnailForm()

    if request.method == 'POST':
        if 'remove-thumb' in request.POST:
            if hasattr(res, 'curatedthumbnaillarge'):
                logger.info(f"Calling delete on {res.curatedthumbnaillarge}")
                res.curatedthumbnaillarge.delete()
        else:
            form = CuratedThumbnailForm(request.POST, request.FILES)
            if form.is_valid():
                ct = form.save(commit=False)
                # if hasattr(res, 'curatedthumbnail'):
                #     res.curatedthumbnail.delete()
                # remove existing thumbnail if any
                if hasattr(res, 'curatedthumbnaillarge'):
                    res.curatedthumbnaillarge.delete()
                else:
                    logger.error(f"{res} has no attribute curatedthumbnailarge.")
                ct.resource = res
                ct.save()
        return HttpResponseRedirect(request.path_info)

    return render(request, template, context={
        'resource': res,
        'form': form
    })