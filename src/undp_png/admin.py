# -*- coding: utf-8 -*-
"""Admin customisations for UNDP PNG.

@Date : 2022-01-15
@Author : CPoole
"""
from django.contrib import admin
from django.contrib import messages
from django.utils.translation import ngettext
from geonode.people.signals import _add_user_to_registered_members
from undp_png.models import CuratedThumbnailLarge


class CuratedThumbnailLargeAdmin(admin.ModelAdmin):
    model = CuratedThumbnailLarge
    list_display = ('id', 'resource', 'img', 'img_thumbnail')


admin.site.register(CuratedThumbnailLarge, CuratedThumbnailLargeAdmin)


def make_user_active(modeladmin, request, queryset):
    updated = queryset.update(is_active=True)
    modeladmin.message_user(request, ngettext(
        '%d user was successfully marked as active.',
        '%d users were successfully marked as active.',
        updated,
    ) % updated, messages.SUCCESS)
    for user in queryset:
        _add_user_to_registered_members(user)


make_user_active.short_description = "Mark selected users as active"
make_user_active.allowed_permissions = ('change',)
make_user_active.__name__ = "make_user_active"
