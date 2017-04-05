# encoding: utf-8

"""
JSON Views that implement a tiny REST API to get and post messages.
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
        posted_message = request.POST.get('message', None)

        if not posted_message:
            response_obj = {'error': True, 'code': 'CH01',
                            'message': 'Parameter "message" was not send or was empty.'}
            return JsonResponse(response_obj, status=400)

        # If message starts with "/", it is taken as a command.
        command_match = self.COMMAND_REGEX.search(posted_message)
        if command_match:
            command, arg = command_match.group(1, 2)
            return self._process_command(command, arg, request.user)

        # It didn't matched the regex. Save message in database and return it to the browser to show it.
        message_obj = Message(user=request.user, date_posted=timezone.now())
        message_obj.text = posted_message

        try:
            message_obj.save()
        except DatabaseError as e:
            logger.error('Error saving message in database.')
            logger.exception(e)
            return self.create_error_response('Error saving message in database', code='DB01')

        return JsonResponse(message_obj.to_json_safe_object())

    def _process_command(self, command, arg, user):
        handler = getattr(self, command, None)

        if not handler:
            return self.create_error_response('Command "{0}" not recognized.'.format(command))

        response = None

        try:
            response = handler(arg, user)
        except Exception as e:
            msg = 'Error executing command {0}'.format(command)
            logger.error(msg)
            logger.exception(e)
            return self.create_error_response(msg, code='CH02')

        return response

    def stock(self, arg, user):
        # Save a record of the message to the database. The message's UUID is used as a correlation id
        # in RabbitMQ to match it with its answer.
        request = json.dumps({'type': 'stock', 'arg': arg})
        command_rec = CommandMessage(date_posted=timezone.now(), request=request, user=user)
        command_rec.save()

        self._send_request(str(command_rec.uuid), request)

        response_obj = {'type': 'command', 'status': 'queued', 'error': False}
        return JsonResponse(response_obj)

    def day_range(self, arg, user):
        # This command allows to query data from various companies at once.
        # Check to see if many company ids were sent:
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

            logger.debug('Sending message (corr_id={0}) to queue bot_requests: {1}'.format(
                correlation_id, request))
            channel.basic_publish(exchange='', routing_key='bot_requests', body=request,
                                  properties=pika.BasicProperties(correlation_id=correlation_id))
        finally:
            connection.close()


class GetLastMessages(AjaxView):

    def get(self, request, *args, **kwargs):
        """Returns the n last messages saved in the database from all users."""
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
            logger.error('Error reading messages from database.')
            logger.exception(e)
            return self.create_error_response('Could not get messages from database.', code='DB01')

        message_list = [m.to_json_safe_object() for m in messages]
        return JsonResponse(message_list, safe=False)


class GetUpdates(AjaxView):
    """
    Returns to the browser messages stored in the database since a given timestamp. This allows to get
    the messages in an incremental fashion, without having to query the last n messages and repainting
    everything in the browser. It also returns the responses from the bot.
    """

    def get(self, request, *args, **kwargs):
        last_timestamp_str = request.GET.get('last_t', None)
        message_list = []

        try:
            if last_timestamp_str:
                try:
                    last_timestamp = str_to_datetime_aware(last_timestamp_str)
                    # Avoid attacks. If the database is big and a very old timestamp is sent, like
                    # 1900-01-01, return a maximum of 100 last messages.
                    qs = Message.objects.filter(date_posted__gt=last_timestamp).order_by('-date_posted')[:100]
                    messages = reversed(list(qs))
                    message_list.extend([m.to_json_safe_object() for m in messages])
                except ValueError as e:
                    logger.error('Error parsing date')
                    logger.exception(e)
                    return self.create_error_response('Invalid date: ' + last_timestamp_str, status=400)

            # Get pending messages for the current user.
            bot_messages = (CommandMessage.objects.filter(user=request.user, date_answered__isnull=False)
                            .order_by('-date_posted'))
            bot_messages = reversed(list(bot_messages))

            for message in bot_messages:
                try:
                    message_list.extend(self._convert_response_to_message(message))
                except (ValueError, TypeError, KeyError) as e:
                    logger.error('Error converting message to json.')
                    logger.error(e)
                    message_list.append({'text': 'Error getting response from bot.',
                                         'user': {'id': 0, 'username': 'Bot'}, 'type': 'command',
                    'timestamp': datetime_aware_to_str(message.date_answered)})

            CommandMessage.objects.filter(user=request.user, date_answered__isnull=False).delete()
        except Exception as e:
            logger.error('Error getting pending messages for the user.')
            logger.exception(e)
            return self.create_error_response('Error getting messages from database. Contact system '
                                              'administrator for more information.', status=500)

        return JsonResponse(message_list, safe=False)

    def _convert_response_to_message(self, command_message):
        if command_message.response is None:
            raise ValueError('Message sent to bot must contain an answer.')

        response_json = json.loads(command_message.response)
        if not isinstance(response_json, dict):
            raise ValueError('Message {0} has answer in wrong format!'.format(command_message.uuid))

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
            return [self.create_error_response('Response to command {0} not implemented.'
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
