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


class LoginView(TemplateView):
    template_name = 'login.html'

    def __init__(self, **kwargs):
        super(LoginView, self).__init__(**kwargs)
        self.errors = []

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated():
            return HttpResponseRedirect(reverse('chat'))
        return super(LoginView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated():
            logout(request)

        user = request.POST.get('username')
        password = request.POST.get('pass')

        if not user or not password:
            self.errors.append('Username or password not sent.')
            return self.get(request, *args, **kwargs)

        user = authenticate(username=user, password=password)

        if user is None:
            self.errors.append('Wrong username or password')
            return self.get(request, *args, **kwargs)

        login(request, user)
        return HttpResponseRedirect(reverse('chat'))

    def get_context_data(self, **kwargs):
        context = super(LoginView, self).get_context_data(**kwargs)
        context['errors'] = self.errors
        return context


class LogoutView(View):

    def get(self, request):
        logout(request)
        return HttpResponseRedirect(reverse('login'))

    def post(self, request):
        return self.get(request)


class ChatroomView(TemplateView):
    template_name = 'chat.html'
