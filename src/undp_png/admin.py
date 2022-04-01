# -*- coding: utf-8 -*-
"""Admin customisations for UNDP PNG.

@Date : 2022-01-15
@Author : CPoole
"""
from django.contrib import admin

from undp_png.models import CuratedThumbnailLarge

class CuratedThumbnailLargeAdmin(admin.ModelAdmin):
    model = CuratedThumbnailLarge
    list_display = ('id', 'resource', 'img', 'img_thumbnail')

admin.site.register(CuratedThumbnailLarge, CuratedThumbnailLargeAdmin)
