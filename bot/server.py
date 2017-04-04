# encoding: utf-8

"""Clase principal del bot. Se encarga de procesar mensajes recibidos en la cola bot_requests de RabbitMQ"""

import json, logging, pika, requests, urllib.parse
import xml.etree.ElementTree as ET

logger = logging.getLogger('chat-bot')


class Bot(object):
    # Configuración del bot.
    BOT_STOCK_URL = 'http://finance.yahoo.com/webservice/v1/symbols/{0}/quote'

    BOT_RANGE_URL = ('http://query.yahooapis.com/v1/public/yql?q=select%20*%20from%20yahoo.finance'
                     '.quotes%20where%20symbol%20in%20({0})&env=store://datatables.org/alltableswithkeys')

    # Samsung Galaxy S6
    BOT_USER_AGENT_STR = ('Mozilla/5.0 (Linux; Android 6.0.1; SM-G920V Build/MMB29K) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/52.0.2743.98 Mobile Safari/537.36')

    _use_rabbitmq = True

    def __init__(self, use_rabbitmq=True):
        # El parámetro use_rabbitmq = False permite crear una instancia del bot sin inicializar las colas,
        # útil para realizar pruebas contra las APIs de Yahoo!.
        self._use_rabbitmq = use_rabbitmq

        if not self._use_rabbitmq:
            return

        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue='bot_requests')
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self._process_request, queue='bot_requests', no_ack=True)

    def start(self):
        if not self._use_rabbitmq:
            raise ValueError('Bot no puede iniciarse cuando se instancia con use_rabbitmq=False.')

        logger.info('Bot iniciado. Esperando peticiones...')
        self.channel.start_consuming()

    def _process_request(self, ch, method, props, body):
        # Se espera que el mensaje esté en formato JSON.
        logger.debug('Mensaje (corr_id=%s) recibido por el bot: %r', props.correlation_id, body)
        try:
            content = json.loads(body.decode(), 'utf-8')
        except:
            logger.exception('Error al parsear mensaje enviado a bot')
            self._send_response(Bot._create_error_response('Error al deserializar mensaje enviado al bot.',
                                                           code='BOT03'), props.correlation_id)
            return

        if not isinstance(content, dict):
            self._send_response(Bot._create_error_response('El mensaje no es un objeto json válido.',
                                                           code='BOT03'), props.correlation_id)
            return

        if content['type'] == 'stock':
            response_obj = self.query_stock(content.get('arg', None))
        elif content['type'] == 'day_range':
            response_obj = self.query_day_range(content.get('arg', None))
        else:
            response_obj = Bot._create_error_response('Servicio no implementado: {0}'
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
            except (TypeError, ValueError):
                logger.exception('Error al serializar respuesta del bot a json.')
                str_json = json.dumps(Bot._create_error_response('Respuesta no serializable.', code='BOT02'))

            logger.debug('Bot envía respuesta (corr_id=%s): %s', correlation_id, str_json)
            channel.basic_publish(exchange='', routing_key='bot_responses', body=str_json,
                                  properties=pika.BasicProperties(content_type='application/json',
                                                                  correlation_id=correlation_id))
        except Exception:
            logger.exception('GRAVE: No se pudo devolver la respuesta desde el bot.')
        finally:
            if connection:
                connection.close()

    @staticmethod
    def _create_error_response(message, code=None):
        response_obj = {'error': True, 'message': message}
        if code:
            response_obj['code'] = code
        return response_obj

    def query_stock(self, company_code):
        """Método que se encarga de consultar datos al API de stocks"""
        try:
            api_response = requests.get(self.BOT_STOCK_URL.format(urllib.parse.quote(company_code)),
                                        headers={'User-Agent': self.BOT_USER_AGENT_STR})
            api_response.raise_for_status()
            doc = ET.ElementTree(ET.fromstring(api_response.text))

            resource = doc.findall('.//resource')

            if not resource:
                # Si no se devuelven recursos, significa que no se encontró registros para la compañía dada.
                return self._create_error_response('No se encontró información para la compañía {0}'
                                                   .format(company_code))

            msg_pattern = "La cotización de {0} ({1}) es ${2} por acción."

            element = resource[0]
            name_fld = element.findall('field[@name="name"]')
            price_fld = element.findall('field[@name="price"]')

            if not name_fld or not price_fld:
                logger.error('API de Stock devolvió respuesta sin campos nombre o precio.')
                return self._create_error_response('Respuesta inesperada del API de stock.', code='BOT04')

            return {'companyCode': company_code, 'name': name_fld[0].text, 'price': float(price_fld[0].text),
                    'message': msg_pattern.format(company_code, name_fld[0].text, price_fld[0].text),
                    'error': False, 'lang': 'es'}
        except Exception:
            msg = 'Error al consultar del API de stocks para compañía {0}.'.format(company_code)
            logger.exception(msg)
            return self._create_error_response(msg, code='BOT03')

    def query_day_range(self, args):
        """Método que hace la consulta al API de Yahoo! Finance para obtener rangos de cotizaciones.
        :param args: Código de la compañía a consultar, o una lista de códigos de compañías.
        """
        if not args:
            return self._create_error_response('No se envió código de compañía a consultar.', code='BOT01')

        if isinstance(args, (list, tuple)):
            query_codes = ','.join(['"{0}"'.format(code) for code in args])
        else:
            query_codes = '"{0}"'.format(args)

        try:
            api_response = requests.get(self.BOT_RANGE_URL.format(urllib.parse.quote(query_codes)))
            api_response.raise_for_status()
            doc = ET.ElementTree(ET.fromstring(api_response.text))

            quotes = doc.findall('.//quote')

            if not quotes:
                # No debería pasar, pero por si se da el caso...
                logger.error('API Yahoo Ranges devolvió respuesta inesperada.', api_response.text)
                return self._create_error_response('Respuesta inesperada de API Yahoo Ranges.')

            # Esta API siempre devuelve un resultado, aunque el código no exista. Se puede verificar
            # si el código existe validando que los campos estén llenos. Campos vacíos indicarían error.
            msg_pattern = 'La cotización baja de {0} ({1}) es ${2} y la cotización alta es ${3}.'
            results = []

            for quote in quotes:
                try:
                    comp_name = quote.find('Name').text
                    days_low = quote.find('DaysLow').text
                    days_high = quote.find('DaysHigh').text
                    code = quote.attrib['symbol']

                    if not (comp_name and days_low and days_high and code):
                        logger.error('Error al obtener información de Yahoo Finance Ranges'
                                     + repr((code, comp_name, days_low, days_high)))
                        results.append({'error': True, 'message': 'No se encontró información '
                                                                  'para la compañía {0}'.format(code)})
                        continue

                    results.append({'companyCode': code, 'name': comp_name, 'error': False, 'lang': 'es',
                                    'daysLow': float(days_low), 'daysHigh': float(days_high),
                                    'message': msg_pattern.format(code, comp_name, days_low, days_high)})
                except (IndexError, TypeError, ValueError, AttributeError):
                    logger.exception('Error al obtener datos consultados de {0}'.format(
                        quote.attrib.get('symbol', '""')))

            return {'error': False, 'results': results}

        except Exception:
            msg = 'Error al consultar del API de Yahoo Finance Ranges para compañía {0}.'.format(query_codes)
            logger.exception(msg)
            return self._create_error_response(msg, code='BOT03')
