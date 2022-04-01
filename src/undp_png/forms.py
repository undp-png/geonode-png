# -*- coding: utf-8 -*-
"""Custom forms for UNDP PNG.

@Date : 2022-01-15
@Author : CPoole
"""
import logging

from django.forms import ModelForm

from .models import CuratedThumbnailLarge

logger = logging.getLogger(__name__)


class CuratedThumbnailForm(ModelForm):
    class Meta:
        model = CuratedThumbnailLarge
        fields = ['img']
