# encoding: utf-8

import threading

from django.apps import AppConfig
from .receiver import BotReceiver


class ChatroomConfig(AppConfig):
    name = 'chatroom'

    verbose_name = 'Async Chatroom'

    initialized = False

    lock = threading.Lock()

    def ready(self):
        # Start thread that listens for responses.
        with self.lock:
            if not self.initialized:
                t = threading.Thread(target=BotReceiver, name='bot-receiver-thread', daemon=True)
                t.start()
                self.initialized = True
