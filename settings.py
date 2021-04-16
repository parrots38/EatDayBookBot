import logging


class WarnFilter(logging.Filter):
    """Отсекает все записи от WARNING и выше."""

    def filter(self, record):
        return record.levelno < logging.WARNING


logging_config = {
    'version': 1,
    'formatters': {
        'err_formatter': {
            'format': (
                "%(asctime)s %(filename)s %(funcName)s %(name)s "
                "%(threadName)s %(levelname)s [%(lineno)d] %(message)s"
            )
        },
        'std_formatter': {
            'format': (
                "%(asctime)s %(filename)-10s %(funcName)-15s "
                "%(threadName)-14s %(levelname)-5s [line%(lineno)d] "
                "%(message)s"
            )
        }
    },
    'filters': {
        'WarnFilter': {
            '()': WarnFilter,
            'name': 'bot'
        }
    },
    'handlers': {
        'std_handler': {
            'class': 'logging.FileHandler',
            'level': logging.DEBUG,
            'filename': 'logs/bot.log',  # 'Work/logs/bot.log'
            'formatter': 'std_formatter',
            'filters': ['WarnFilter']
        },
        'err_handler': {
            'class': 'logging.FileHandler',
            'level': logging.WARNING,
            'filename': 'logs/err_bot.log',  # 'Work/logs/err_bot.log'
            'formatter': 'err_formatter'
        }
    },
    'loggers': {
        'bot': {
            'level': logging.DEBUG,
            'propagate': False,
            'handlers': ['std_handler', 'err_handler']
        },
        'bot.main': {},
        'bot.main.start_threads': {},
        'bot.main.Reminder': {},
        'bot.main.UserHandler': {},
        'bot.main.longPolling': {},
        'bot.user': {}
    }
}
