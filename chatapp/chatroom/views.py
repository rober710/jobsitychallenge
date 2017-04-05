# encoding: utf-8

import json

from django.http import HttpResponseForbidden, HttpResponseRedirect, JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.core.urlresolvers import reverse
from django.views.generic import TemplateView
from django.views.generic import View

from chatroom.utils import logger


class AjaxView(View):
    """
    Generic class to process AJAX requests. Forces responses to be sent in JSON format.
    """
    requires_authentication = True

    def dispatch(self, request, *args, **kwargs):
        if self.requires_authentication and not request.user.is_authenticated():
            return AjaxView._create_forbidden_response()

        if request.method.lower() in self.http_method_names:
            handler = getattr(self, request.method.lower(), self.http_method_not_allowed)
        else:
            handler = self.http_method_not_allowed

        response = None

        try:
            response = handler(request, *args, **kwargs)
        except Exception as e:
            # Catches unhandled exceptions.
            logger.error('Error processing ajax request.')
            logger.exception(e)
            return AjaxView.create_error_response('Error processing request. Please take a look at the '
                                                  'application log for more details.')

        # Make sure the response is in json format. If not, try to convert it to json.
        if response is None:
            logger.warn('Null response for "{0} {1}", class {2}'.format(request.method, request.path,
                                                                        self.__class__.__name__))
            response = JsonResponse('', safe=False)
        elif not isinstance(response, JsonResponse):
            try:
                response = JsonResponse(response, safe=False)
            except Exception as e:
                logger.error('Error serializing answer to json.')
                logger.exception(e)
                response = AjaxView.create_error_response('Error serializing answer to json.')

        return response

    @staticmethod
    def _create_forbidden_response():
        json_response = json.dumps({'error': True, 'message': 'Forbidden'})
        return HttpResponseForbidden(json_response, content_type='application/json; charset=utf-8')

    @staticmethod
    def create_error_response(message, code=None, status=500):
        response_content = {'error': True, 'message': message}

        if code:
            response_content['code'] = code

        return JsonResponse(response_content, status=status)


class HomeView(View):

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated():
            return HttpResponseRedirect(reverse('chat'))
        return HttpResponseRedirect(reverse('login'))

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)


class ChatroomView(TemplateView):
    template_name = 'chat.html'
