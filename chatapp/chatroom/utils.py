# encoding: utf-8

"""Utility functions."""

import logging

from django.utils import dateparse, formats

logger = logging.getLogger('chatroom')


def datetime_aware_to_str(timestamp):
    """Returns an aware datatime converted to string, in ISO 8601 format."""
    if timestamp is None:
        return None
    # FIXME: Take into account timezone information.
    return formats.date_format(timestamp, 'c')


def str_to_datetime_aware(timestamp_str):
    if timestamp_str is None:
        return None
    return dateparse.parse_datetime(timestamp_str)
