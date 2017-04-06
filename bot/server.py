# encoding: utf-8

"""Bot's main class. It processes messages received from the bot_requests queue from RabbitMQ"""

import json, logging, pika

from bot.api_adapter import ApiException, YahooFinanceApiAdapter

logger = logging.getLogger('chat-bot')


class Bot(object):

    def __init__(self, configure_message_bus=True):
        # The parameter configure_message_bus = False allows to create a bot instance without connecting
        # to RabbitMQ, useful for testing Yahoo API calls.
        self._configure_message_bus = configure_message_bus

        if not self._configure_message_bus:
            return

        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue='bot_requests')
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self._process_request, queue='bot_requests', no_ack=True)

    def start(self):
        if not self._configure_message_bus:
            raise ValueError('Bot cannot start when instanciated with argument use_rabbitmq=False.')

        logger.info('Bot started. Waiting for incomming connections...')
        self.channel.start_consuming()

    def _process_request(self, ch, method, props, body):
        # Se espera que el mensaje esté en formato JSON.
        logger.debug('Message (corr_id=%s) received by the bot: %r', props.correlation_id, body)
        try:
            content = json.loads(body.decode(), 'utf-8')
        except Exception as e:
            logger.error('Error parsing message sent to bot.')
            logger.exception(e)
            self._send_response(Bot._create_error_response('Error when deserializing message received '
                                                           'by the bot.', code='BOT03'), props.correlation_id)
            return

        if not isinstance(content, dict):
            self._send_response(Bot._create_error_response('Message is not a valid JSON object.',
                                                           code='BOT03'), props.correlation_id)
            return

        api_adapter = YahooFinanceApiAdapter()

        if content['type'] == 'stock':
            try:
                response_obj = api_adapter.query_stock(content.get('arg', None))
            except ApiException as e:
                logger.exception(e)
                response_obj = self._create_error_response(e.message, e.code)
        elif content['type'] == 'day_range':
            try:
                response_obj = api_adapter.query_day_range(content.get('arg', None))
            except ApiException as e:
                logger.exception(e)
                response_obj = self._create_error_response(e.message, e.code)
        else:
            response_obj = Bot._create_error_response('Service not implemented: {0}'
                                                      .format(content['type']))

        self._send_response(response_obj, props.correlation_id)

    def _send_response(self, json_response, correlation_id):
        connection = None
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
            channel = connection.channel()
            channel.queue_declare(queue='bot_responses')

            try:
                str_json = json.dumps(json_response)
            except (TypeError, ValueError) as e:
                logger.error('Error serializing response to json.')
                logger.exception(e)
                str_json = json.dumps(Bot._create_error_response('Non serializable response.', code='BOT02'))

            logger.debug('Bot sends response (corr_id=%s): %s', correlation_id, str_json)
            channel.basic_publish(exchange='', routing_key='bot_responses', body=str_json,
                                  properties=pika.BasicProperties(content_type='application/json',
                                                                  correlation_id=correlation_id))
        except Exception as e:
            logger.error('FATAL: Cannot return answer from bot.')
            logger.exception(e)
        finally:
            if connection:
                connection.close()

    @staticmethod
    def _create_error_response(message, code=None):
        response_obj = {'error': True, 'message': message}
        if code:
            response_obj['code'] = code
        return response_obj
