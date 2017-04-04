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
    Clase que contiene código genérico para procesar peticiones AJAX. Forza a que las respuestas se envíen
    como JSON.
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
        except Exception:
            # Si ocurre cualquier excepción no controlada, enviar una respuesta json de error al navegador.
            logger.exception('Error al procesar petición ajax')
            return AjaxView.create_error_response('Error al procesar la solicitud. Consulte el log de la '
                                                  'aplicación para obtener más detalles del problema.')

        # Asegurarse que la respuesta sea json. Si no lo es, tratar de convertirla a json.
        if response is None:
            logger.warn('Respuesta nula para "{0} {1}", en clase {2}'.format(request.method, request.path,
                                                                             self.__class__.__name__))
            response = JsonResponse('', safe=False)
        elif not isinstance(response, JsonResponse):
            try:
                response = JsonResponse(response, safe=False)
            except Exception:
                logger.exception('Error al convertir la respuesta a json.')
                response = AjaxView.create_error_response('Error al convertir la respuesta a json')

        return response

    @staticmethod
    def _create_forbidden_response():
        json_response = json.dumps({'error': True, 'message': 'Acceso denegado'})
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
            self.errors.append('No se envió usuario o contraseña')
            return self.get(request, *args, **kwargs)

        user = authenticate(username=user, password=password)

        if user is None:
            self.errors.append('Usuario o contraseña incorrectos')
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