# encoding: utf-8

import threading

from django.apps import AppConfig

from .receiver import BotReceiver


class ChatroomConfig(AppConfig):
    name = 'chatroom'

    verbose_name = 'Salón de Chat Asíncrono'

    initialized = False

    lock = threading.Lock()

    def ready(self):
        # Levantar el hilo que recibe mensajes.
        with self.lock:
            if not self.initialized:
                t = threading.Thread(target=BotReceiver, name='bot-receiver-thread', daemon=True)
                t.start()
                self.initialized = True