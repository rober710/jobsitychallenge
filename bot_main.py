# encoding: utf-8

"""Script para lanzar el bot."""

import logging.config, sys

from bot.server import Bot


def start_bot():
    bot_instance = Bot()
    bot_instance.start()


if __name__ == '__main__':
    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'stream': sys.stdout,
            }
        },
        'loggers': {
            'chat-bot': {
                'handlers': ['console'],
                'level': 'DEBUG',
                'propagate': True
            }
        }
    })

    start_bot()
