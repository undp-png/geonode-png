# -*- coding: utf-8 -*-
"""Custom models for UNDP PNG.

@Date : 2022-01-15
@Author : CPoole
"""
import logging
import os

from django.conf import settings
from django.core.files.storage import default_storage as storage
from django.db import models
from geonode.base.models import ResourceBase
from imagekit.cachefiles.backends import Simple
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill

logger = logging.getLogger(__name__)


class CuratedThumbnailLarge(models.Model):
    resource = models.OneToOneField(ResourceBase, on_delete=models.CASCADE)
    img = models.ImageField(upload_to='curated_thumbs')
    # TOD read thumb size from settings
    img_thumbnail = ImageSpecField(source='img',
                                   processors=[ResizeToFill(settings.THUMBNAIL_GENERATOR_DEFAULT_SIZE.get("width", 420),
                                                            settings.THUMBNAIL_GENERATOR_DEFAULT_SIZE.get("height",
                                                                                                          350))],
                                   format='PNG',
                                   options={'quality': 60})

    @property
    def thumbnail_url(self):
        try:
            if not Simple()._exists(self.img_thumbnail):
                Simple().generate(self.img_thumbnail, force=True)
            upload_path = storage.path(self.img_thumbnail.name)
            actual_name = os.path.basename(storage.url(upload_path))
            _upload_path = os.path.join(os.path.dirname(upload_path), actual_name)
            if not os.path.exists(_upload_path):
                os.rename(upload_path, _upload_path)
            return self.img_thumbnail.url
        except Exception as e:
            logger.exception(e)
        return ''
