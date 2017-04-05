# encoding: utf-8

import uuid

from django.conf import settings
from django.db import models

from .utils import datetime_aware_to_str


class Message(models.Model):
    """
    Represents a message posted by a user.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='messages',
                             verbose_name='User who posted the message.')
    date_posted = models.DateTimeField('Posted date')
    text = models.TextField('Message text')

    def __str__(self):
        return 'Message from {0} at {1:%Y%-m-%d %H:%M:%S}'.format(self.user, self.date_posted)

    def to_json_safe_object(self):
        """
        Returns data of this object as a json-safe dictionary
        """
        return {'text': self.text, 'user': {'id': self.user_id, 'username': self.user.username},
                'timestamp': datetime_aware_to_str(self.date_posted), 'type': 'message'}

    class Meta:
        ordering = ['-date_posted']
        verbose_name = 'mensaje'
        verbose_name_plural = 'mensajes'


class CommandMessage(models.Model):
    """
    Saves the data of a command and its answer. It serves as a temporary storage for command results
    until they are requested by the user.
    """
    # This field holds the correlation_id of the message to match it against the received response.
    uuid = models.UUIDField('message identifier', primary_key=True, default=uuid.uuid4, editable=False)
    date_posted = models.DateTimeField('posted date')
    date_answered = models.DateTimeField('response date', null=True, blank=True)
    request = models.TextField('the contents of the message sent')
    response = models.TextField('the contents of the message received', null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+',
                             verbose_name='user who sent the command.')
    read = models.BooleanField('indicates whether the message was sent to the user.', default=False)

    def __str__(self):
        return 'Command {0} from {1}'.format(self.uuid, self.user.username)

    class Meta:
        ordering = ['-date_posted']
        verbose_name = 'command message'
        verbose_name_plural = 'command messages'
