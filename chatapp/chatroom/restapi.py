# encoding: utf-8

"""
Vistas JSON que implementan una mini API REST para obtener y postear mensajes.
"""

import json, pika, re

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import DatabaseError
from django.http import JsonResponse
from django.utils import timezone

from .models import Message, CommandMessage
from .utils import logger
from .views import AjaxView
from .utils import datetime_aware_to_str, str_to_datetime_aware


class PostMessage(AjaxView):

    COMMAND_REGEX = re.compile(r'^/(\w+)(?:=(.*))?$', re.UNICODE)

    def post(self, request, *args, **kwargs):
        """ Recibir mensaje enviado desde el navegador, y guardarlo en la base. En caso de que sea
         un comando, enviar un mensaje al bot para que consulte los datos financieros."""
        # El mensaje se espera en la petición bajo el parámetro message.
        posted_message = request.POST.get('message', None)

        if not posted_message:
            # Devolver respuesta de error: parámetro no enviado o mensaje vacío.
            response_obj = {'error': True, 'code': 'CH01',
                            'message': 'No se envió parámetro "message" o mensaje vacío.'}
            return JsonResponse(response_obj, status=400)

        # Si el mensaje empieza con "/", se toma como un comando.
        command_match = self.COMMAND_REGEX.search(posted_message)
        if command_match:
            command, arg = command_match.group(1, 2)
            return self._process_command(command, arg, request.user)

        # No es un comando, entonces guardar el mensaje en la base y devolverlo al navegador para mostrarlo.
        message_obj = Message(user=request.user, date_posted=timezone.now())
        message_obj.text = posted_message

        try:
            message_obj.save()
        except DatabaseError as e:
            logger.exception('Error al guardar mensaje en base de datos.')
            return self.create_error_response('Error al guardar mensaje', code='DB01')

        return JsonResponse(message_obj.to_json_safe_object())

    def _process_command(self, command, arg, user):
        # TODO: Implementar un mecanismo de registro de manejadores de comandos.
        # Por ahora, los manejadores son métodos de esta clase.
        handler = getattr(self, command, None)

        if not handler:
            return self.create_error_response('Comando "{0}" no reconocido.'.format(command))

        response = None

        try:
            response = handler(arg, user)
        except Exception as e:
            msg = 'Error al ejecutar comando {0}'.format(command)
            logger.exception(msg)
            return self.create_error_response(msg, code='CH02')

        return response

    def stock(self, arg, user):
        # Guardar un registro del mensaje que se va a enviar en la base de datos. El uuid del mensaje
        # se usará como id de correlación en RabbitMQ para poder determinar cuando se reciba su respuesta.
        request = json.dumps({'type': 'stock', 'arg': arg})
        command_rec = CommandMessage(date_posted=timezone.now(), request=request, user=user)
        command_rec.save()

        self._send_request(str(command_rec.uuid), request)

        response_obj = {'type': 'command', 'status': 'queued', 'error': False}
        return JsonResponse(response_obj)

    def day_range(self, arg, user):
        # Este comando permite consultar los datos de varias compañías. Determinar si se enviaron varios
        # nombres a consultar.
        if arg.find(',') != -1:
            companies = arg.split(',')
            companies = [c.strip() for c in companies]
        else:
            companies = arg
        request = json.dumps({'type': 'day_range', 'arg': companies})
        command_rec = CommandMessage(date_posted=timezone.now(), request=request, user=user)
        command_rec.save()

        self._send_request(str(command_rec.uuid), request)

        response_obj = {'type': 'command', 'status': 'queued', 'error': False}
        return JsonResponse(response_obj)

    def _send_request(self, correlation_id, request):
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))

        try:
            channel = connection.channel()
            channel.queue_declare(queue='bot_requests')

            logger.debug('Enviando mensaje (corr_id={0}) a cola bot_requests: {1}'.format(
                correlation_id, request))
            channel.basic_publish(exchange='', routing_key='bot_requests', body=request,
                                  properties=pika.BasicProperties(correlation_id=correlation_id))
        finally:
            connection.close()


class GetLastMessages(AjaxView):

    def get(self, request, *args, **kwargs):
        """Devuelve los n últimos mensajes guardados en la base de datos de todos los usuarios."""
        number_records = request.GET.get('count', None)

        if number_records:
            try:
                number_records = int(number_records)
            except (ValueError, TypeError):
                number_records = 50
        else:
            number_records = 50

        messages = Message.objects.order_by('-date_posted')[:number_records]

        try:
            messages = reversed(list(messages))
        except DatabaseError as e:
            logger.exception('Error al leer mensajes.')
            return self.create_error_response('No se pudo obtener mensajes de la base de datos.', code='DB01')

        message_list = [m.to_json_safe_object() for m in messages]
        return JsonResponse(message_list, safe=False)


class GetUpdates(AjaxView):
    """
    Devuelve al navegador los mensajes almacenados en la base a partir de un timestamp dado. Esto permite
    obtener los mensajes de forma incremental, sin tener que consultar todos los n mensajes anteriores y
    repintar todo en el lado del cliente. También devuelve las respuestas recibidas del bot.
    """

    def get(self, request, *args, **kwargs):
        last_timestamp_str = request.GET.get('last_t', None)
        message_list = []

        try:
            if last_timestamp_str:
                try:
                    last_timestamp = str_to_datetime_aware(last_timestamp_str)
                    # Mitigar ataques. Si la base es grande y mandan una fecha muy antigua (como 1900-01-01)
                    # solo enviar como máximo los 100 últimos mensajes.
                    qs = Message.objects.filter(date_posted__gt=last_timestamp).order_by('-date_posted')[:100]
                    messages = reversed(list(qs))
                    message_list.extend([m.to_json_safe_object() for m in messages])
                except ValueError:
                    logger.exception('Error al convertir fecha')
                    return self.create_error_response('Fecha inválida: ' + last_timestamp_str, status=400)

            # Obtener mensajes pendientes de leer para el usuario actual.
            bot_messages = (CommandMessage.objects.filter(user=request.user, date_answered__isnull=False)
                            .order_by('-date_posted'))
            bot_messages = reversed(list(bot_messages))

            for message in bot_messages:
                try:
                    message_list.extend(self._convert_response_to_message(message))
                except (ValueError, TypeError, KeyError):
                    logger.exception('Error al convertir mensaje a json para enviar al usuario.')
                    message_list.append({'text': 'Error al obtener respuesta del bot.',
                                         'user': {'id': 0, 'username': 'Bot'}, 'type': 'command',
                    'timestamp': datetime_aware_to_str(message.date_answered)})

            CommandMessage.objects.filter(user=request.user, date_answered__isnull=False).delete()
        except Exception:
            logger.exception('Error al obtener los mensajes pendientes del usuario.')
            return self.create_error_response('Error al obtener mensajes. Contacte al administrador del '
                                              'sistema para más información.', status=500)

        return JsonResponse(message_list, safe=False)

    def _convert_response_to_message(self, command_message):
        if command_message.response is None:
            raise ValueError('El mensaje enviado al bot debe contener una respuesta.')

        response_json = json.loads(command_message.response)
        if not isinstance(response_json, dict):
            raise ValueError('Mensaje {0} con respuesta en formato incorrecto!'.format(command_message.uuid))

        if response_json['error']:
            return [self._create_message_error_response(response_json['message'], command_message)]

        # Determinar qué consulta se hizo para procesar la respuesta.
        request_json = json.loads(command_message.request)
        if request_json['type'] == 'stock':
            return [{'text': response_json['message'], 'user': {'id': 0, 'username': 'Bot'},
                     'type': 'command', 'error': False,
                     'timestamp': datetime_aware_to_str(command_message.date_answered)}]
        elif request_json['type'] == 'day_range':
            # Esta API devuelve un array de resultados.
            results = response_json['results']
            messages = []

            for result in results:
                if result['error']:
                    messages.append(self._create_message_error_response(result['message'], command_message))
                else:
                    messages.append({'text': result['message'], 'user': {'id': 0, 'username': 'Bot'},
                                     'type': 'command', 'error': False,
                                     'timestamp': datetime_aware_to_str(command_message.date_answered)})

            return messages
        else:
            return [self.create_error_response('Respuesta a comando {0} no implemetado.'
                                               .format(request_json['type']))]

    def _create_message_error_response(self, error_msg, command_message):
        res_obj = {'text': error_msg, 'user': {'id': 0, 'username': 'Bot'}, 'type': 'command',
                   'timestamp': datetime_aware_to_str(command_message.date_answered), 'error': True}
        return res_obj


class GetOnlineUsers(AjaxView):

    def get(self, request, *args, **kwargs):
        active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
        user_ids = []

        for session in active_sessions:
            data = session.get_decoded()
            uid = data.get('_auth_user_id', None)
            if uid and int(uid) != request.user.id:
                user_ids.append(uid)

        users = get_user_model().objects.filter(id__in=user_ids)
        res = []

        for user in users:
            res.append({'id': user.id, 'name': user.get_full_name()})

        return JsonResponse(res, safe=False)