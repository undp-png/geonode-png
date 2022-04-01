# -*- coding: utf-8 -*-
"""UNDP Extra custom tags

@Date : 2022-01-03
@Author : CPoole
"""
import re

from django import template
from django.db.models import Count
from geonode.base.models import ResourceBase
from guardian.shortcuts import get_objects_for_user

register = template.Library()


@register.simple_tag
def regex_replace(value, pattern, replace, *args, **kwargs):
    return re.sub(pattern, replace, value)


@register.inclusion_tag(filename='base/iso_categories.html')
def get_visible_resources_custom(user):
    categories = get_objects_for_user(user, 'view_resourcebase', klass=ResourceBase, any_perm=False)\
        .filter(category__isnull=False).values('category__gn_description',
                                               'category__fa_class', 'category__description', 'category__identifier')\
        .order_by('category__identifier')\
        .annotate(count=Count('category'))

    return {
        'iso_formats': categories
    }