# encoding: utf-8

import uuid

from django.conf import settings
from django.db import models

from .utils import datetime_aware_to_str


class Message(models.Model):
    """
    Representa un mensaje posteado por un usuario.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='messages',
                             verbose_name='Usuario que posteó el mensaje')

    date_posted = models.DateTimeField('Fecha de posteo')

    text = models.TextField('Texto del mensaje')

    def __str__(self):
        return 'Mensaje de {0} en {1:%Y%-m-%d %H:%M:%S}'.format(self.user, self.date_posted)

    def to_json_safe_object(self):
        """
        Devuelve los datos de este objeto como un diccionario que es seguro para ser convertido a JSON.
        """
        return {'text': self.text, 'user': {'id': self.user_id, 'username': self.user.username},
                'timestamp': datetime_aware_to_str(self.date_posted), 'type': 'message'}

    class Meta:
        ordering = ['-date_posted']
        verbose_name = 'mensaje'
        verbose_name_plural = 'mensajes'


class CommandMessage(models.Model):
    """
    Guarda los datos de un comando y su respuesta. Sirve como almacenamiento temporal de los resultados
    de los comandos hasta que sean consultados por el usuario.
    """
    # Este campo sirve como correlation_id al enviar el mensaje por las colas de RabbitMQ
    uuid = models.UUIDField('identificador del mensaje', primary_key=True, default=uuid.uuid4, editable=False)

    date_posted = models.DateTimeField('fecha de posteo')

    date_answered = models.DateTimeField('fecha de respuesta', null=True, blank=True)

    request = models.TextField('mensaje enviado')

    response = models.TextField('mensaje recibido', null=True, blank=True)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+',
                             verbose_name='usuario que envió el comando.')

    def __str__(self):
        return 'Comando {0} de {1}'.format(self.uuid, self.user.username)

    class Meta:
        ordering = ['-date_posted']
        verbose_name = 'mensaje de comando'
        verbose_name_plural = 'mensajes de comandos'
