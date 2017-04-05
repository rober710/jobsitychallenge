# encoding: utf-8

"""Module which processes responses received from the bot."""

import pika

from django.db import DatabaseError
from django.db.models import ObjectDoesNotExist
from django.utils import timezone

from .utils import logger


class BotReceiver(object):

    def __init__(self):
        # TODO: Add connection parameters like hostname, queue name, etc to settings.py
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue='bot_responses')
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.process_response, queue='bot_responses', no_ack=True)

        logger.info('Bot receiver started. Waiting for incomming messages...')
        self.channel.start_consuming()

    def process_response(self, ch, method, props, body):
        """
        Receives the response from the bot, and saves it in the commands table, so a user can retrieve them
        later.
        """
        logger.debug('Response message received (corr_id=%s): %r', props.correlation_id, body)

        try:
            # Import is needed here to avoid error "Apps arent't loaded yet at Django startup."
            from .models import CommandMessage
            command_rec = CommandMessage.objects.get(uuid=props.correlation_id)
            command_rec.date_answered = timezone.now()
            command_rec.response = body.decode()
            command_rec.save(force_update=True, update_fields=['date_answered', 'response'])
        except ObjectDoesNotExist:
            logger.error('Message with uuid %s not found in the database!', props.correlation_id)
        except Exception as e:
            logger.error('Error when updating response record!')
            logger.exception(e)
