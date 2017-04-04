# encoding: utf-8

"""Módulo receptor de mensajes enviados por el Bot"""

import pika

from django.db import DatabaseError
from django.db.models import ObjectDoesNotExist
from django.utils import timezone

from .utils import logger


class BotReceiver(object):

    def __init__(self):
        # TODO: Agregar los parámetros de conexión, como nombres de colas, host, etc en el archivo settings.py
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue='bot_responses')
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.process_response, queue='bot_responses', no_ack=True)

        logger.info('Receptor de respuestas iniciado. Esperando mensajes...')
        self.channel.start_consuming()

    def process_response(self, ch, method, props, body):
        """
        Recibe el mensaje de respuesta del bot, y lo guarda en la tabla de comandos para ser consultado
        luego por el usuario.
        """
        logger.debug('Mensaje de respuesta (corr_id=%s) de bot recibido: %r', props.correlation_id, body)

        try:
            # Se realiza el import aquí debido a que la clase se carga durante la inicialización de Django.
            # Si se importa a nivel de módulo, se produce un error al iniciar la
            # aplicación: Apps aren't loaded yet.
            from .models import CommandMessage
            command_rec = CommandMessage.objects.get(uuid=props.correlation_id)
            command_rec.date_answered = timezone.now()
            command_rec.response = body.decode()
            command_rec.save(force_update=True, update_fields=['date_answered', 'response'])
        except ObjectDoesNotExist:
            logger.error('Mensaje con uuid %s no encontrado en la base!', props.correlation_id)
        except Exception:
            logger.exception('Error al actualizar registro de respuesta del bot!')
