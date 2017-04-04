# encoding: utf-8

"""Funciones utilitarias."""

import logging

from django.utils import dateparse, formats

logger = logging.getLogger('chatroom')


def datetime_aware_to_str(timestamp):
    """Devuelve un datetime con zona horaria convertido a string, en formato ISO 8601"""
    if timestamp is None:
        return None
    # FIXME: Tomar en cuenta información de zona horaria.
    return formats.date_format(timestamp, 'c')


def str_to_datetime_aware(timestamp_str):
    if timestamp_str is None:
        return None
    return dateparse.parse_datetime(timestamp_str)