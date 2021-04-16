"""Бот - персональный дневник счета съеденных калорий во Вконтакте.
    Общий функционал бота:
        - хранит записанные калории в базе и возвращает суммы калорий
        за указанные дни;
        - присылает напоминания о необходимости заполнить дневник с
        учетом часового пояса пользователя.

    Описание работы бота:
        - пользователь присылает боту сообщение с использованием
        одной из возможных команд;
        - текст сообщения обрабатывается функцией message_handler.task
        модуля message_handler;
        - команда и значения передаются классу user.User модуля
        user и кладутся в очередь users_queue;
        - очередь users_queue обрабатывается потоками UserHandler,
        которые извлекаются объекты из очереди и вызывают их метод
        task_handler, который выполняет введенную пользователем
        команду;
        - поток Reminder отправляет пользователю напоминания.

    Порядок работы с ботом:
        1. Пользователь первый отправляет сообщение - приветственное.
        Бот в ответ сообщает порядок работы с ним.
        2. Чтобы использовать любую команду, сначала необходимо
        установить часовой пояс пользователя. Поэтому первая
        валидная команда пользователя: set time (кроме start, help,
        которые просто посылают заранее определенные сообщения, и
        stop).
        3. Затем есть 2 пути использования бота:
            - не используя напоминания, а просто записывая в него
            потраченные калории; тогда команда set eating может быть
            не вызвана ни разу, при этом это никак не влияет на все
            остальные функции бота: give, add, sub, stop, help, start,
            error вызываются спокойно, а вот reminder не будет вызвана
            никогда.
             - используя напоминания, тогда нужно вызвать команду set
            eating и записать время для напоминаний; которое тем не
            менее никак не влияет на работу других функций, кроме
            reminder, которая непосредственно зависит от времени
            напоминаний.
        4. На данный момент сбросить время напоминаний можно только
        полным сбросом настроек бота - командой stop.
        5. Вызов stop польностью прекращает работу бота для этого
        пользователя, удаляя файл с id пользователя и стирая его id из
        словаря с временами напоминания.

    Модули:
        message_handler - обрабатывает сообщения пользователя
        user - содержит класс для задачи от конкретного пользователя
        texts - содержит тексты посылаемых ботом сообщений
        config - конфигурация бота

"""


import os
import threading
import queue
import time
import logging.config

import vk_api
from vk_api.bot_longpoll import *

from Work import message_handler, config, user, settings


class BotLongPollTimeoutHandled(VkBotLongPoll):
    """Класс для прослушивания событий от VK API.

    Переопределяет класс VkBotLongPoll, чтобы ловить возникающие
    ошибки.

    """

    logger = logging.getLogger('bot.main.longPolling')

    def listen(self):
        while True:
            try:
                for event in self.check():
                    yield event
            except requests.exceptions.ConnectionError:
                self.logger.exception(
                    'Connection interrupted from server/PC.')
                time.sleep(15)
                self.logger.error('Before sleeping.')
            except requests.exceptions.ReadTimeout:
                self.logger.exception('Read timeout error from VK.')
                time.sleep(15)
                self.logger.error('Before sleeping.')
            except Exception:
                self.logger.exception('Unknown exception.')
                time.sleep(15)
                self.logger.error('Before sleeping.')


class UserHandler(threading.Thread):
    """Класс потока для обработки задач из очереди задач клиентов.

    Является подклассом класса threading.Thread, наследует его
    API, изменяет метод run для реализации обработки задач.

    Attributes:
        q - очередь queue.Queue из задач;

    """

    logger = logging.getLogger('bot.main.UserHandler')

    def __init__(self, q):
        """
        Args:
            q - очередь queue.Queue для задач;

        """
        super().__init__()
        self.q = q
        self.daemon = True

    def run(self):
        """
        Забирает задачу из очереди и вызывает метод объекта задачи для
        выполнения действий.

        """

        while True:
            client = self.q.get()  # user.User()
            self.logger.debug(
                "Take task: '%s' with data: %s", client.status, client.values)
            try:
                client.task_handler()
            except Exception:
                self.logger.exception('Some exception in UserHandler')
            finally:
                self.q.task_done()


class Reminder(threading.Thread):
    """Класс потока для отправки сообщений напоминаний пользователю.

    Является подклассом класса threading.Thread, наследует его
    API и добавляет свои для реализации отправки задач с напоминанием
    в очередь.

    Attributes:
        vk - объект vk_api.vk_api.VkApiMethod;
        client - ссылка на класс user.User;
        q - очередь queue.Queue для задач;
        times_min - список из целочисленных значений
            времени суток в минутах с шагом в 5 минут;
        _TASK - константа, кортеж, содержащий задачу и список
            передаваемых значений в класс client;
        _logger - регистратор записей.

    Methods:
        _set_times - создает список минут для проверки;
        time_to_min - возвращает текущее время в минутах от полуночи;
        time_to_hour_min - переводит время из минут в часы:минуты;
        sleeper - спит, пока не наступит время проверки.

    """

    _TASK = ('reminder', [None])
    _logger = logging.getLogger('bot.main.Reminder')

    def __init__(self, vk: vk_api.vk_api.VkApiMethod, q):
        """
        Args:
            vk - объект vk_api.vk_api.VkApiMethod;
            q - очередь queue.Queue для задач;

        """
        super().__init__()
        self.vk = vk
        self.client = user.User
        self.q = q
        self.times_min = []

        self.daemon = True

    def _set_times(self):
        """Создает список минут для проверки.

        Записывает в times_min список времени суток в минутах в виде
        целочисленных значений с интервалом в 5 минут от текущего
        времени до полуночи.

        """

        now_min = self.time_to_min()

        min_aliquot5 = now_min//5 * 5 + 5
        if min_aliquot5 == 1440:
            min_aliquot5 = 0

        self.times_min = [i for i in range(min_aliquot5, 24*60, 5)]

    def time_to_min(self):
        """Возвращает текущее целочисленное локальное время в минутах."""

        now = time.localtime()
        return now.tm_hour * 60 + now.tm_min

    def time_to_hour_min(self, time_in_min):
        """Преобразует время в минутах в время в часах-минутах.

        Args:
            time_in_min - целочисленное значение времени в минутах.

        Return:
            возвращает строку вида HH:MM

        """

        hour = time_in_min//60
        minutes = time_in_min - hour*60

        return f"{hour if hour > 9 else '0' + str(hour)}:" \
               f"{minutes if minutes > 9 else '0' + str(minutes)}"

    def sleeper(self, delay=5):
        """Спит, пока не придет время для проверки.

        Спит с шагом в delay секунд до тех пор, пока не
        подойдет следующее время.

        Args:
            delay - целочисленное значение, представлющее шаг сна.

        Return:
            возвращает целочисленное значение времени в минутах,
                которое наступило (элемент списка times_min).

        """

        if not len(self.times_min):
            self._set_times()

        self._logger.debug('Times list: %s', str(self.times_min))

        while True:
            step = self.times_min[0]
            now = self.time_to_min()

            if step - now < -5:
                step += 24*60

            if now < step:
                time.sleep(delay)
            else:
                break

        return self.times_min.pop(0)

    def run(self):
        """Помещает задачи напоминания в очередь."""

        while True:
            clock = self.sleeper()
            # блокирует, пока не подойдет время для опроса
            self._logger.debug('Reminder wake up.')

            time_check = self.time_to_hour_min(clock)
            try:
                persons = self.client.users[time_check]
                # {'14:55': {4112324, 234152}, }

                self._logger.debug(
                    'Reminder in %s has clients: %s.',
                    time_check, str(persons)
                )

                for person in persons:
                    self.q.put(self.client(self.vk, person, self._TASK))
            except Exception:
                self._logger.exception('Some exception in Reminder.')


def start_threads(turn, vk, threads_count=4):
    """Запускает потоки для обработки задач и поток для напоминаний.

    Args:
        turn - очередь queue.Queue, которую будут просматривать потоки;
        vk - объект vk_api.vk_api.VkApiMethod;
        threads_count - количество запускаемых потоков.

    Return:
        кортеж из двух значений (threads, rem):
            threads - список объектов запущенных потоков,
                обрабатывающих задачи от пользователя;
            rem - объект потока для отправки напоминаний пользователю.

    """

    logger = logging.getLogger('bot.main.start_threads')

    logger.debug('Start threads.')
    threads = []
    for _ in range(threads_count):
        thr = UserHandler(turn)
        thr.start()
        threads.append(thr)

        logger.debug('%s started.', thr.name)

    rem = Reminder(vk, turn)
    rem.name = 'ThreadReminder'
    rem.start()
    logger.debug('%s started.', rem.name)

    return threads, rem


def config_logging():
    """
    Настройка логирования:
        - в файл logs/bot.log записывает стандартные логи уровнем
            не выше logging.INFO;
        - в файл logs/bot.log записывает логи ошибок уровнем от
            logging.WARNING и выше.

    """

    fullpath = os.path.abspath('logs')
    if not os.path.exists(fullpath):
        os.mkdir(fullpath)
    # создает папку для хранения логов в директории с main-файлом.

    logging.config.dictConfig(settings.logging_config)


def main():
    """Запускает бота.

    Функция создает очередь и запускает потоки для обработки
    задач от пользователя.  Реализует процесс авторизации в VK API с
    указанным токеном сообщества и прослушивает события на предмет
    появления сообщений от пользователей.  Обрабатывает появившееся
    сообщение и создает объект задачи для этого сообщения.

    Исключения:
        будут дополнены при тестировании.

    """

    def start(vk):
        """
        Создает объекты user.User() для всех уже существующих в базе
        пользователей.

        Args:
            vk - объект vk_api.vk_api.VkApiMethod.

        Return:
            None

        """

        try:
            for client in os.listdir(user.User.catalog_path):
                if client.endswith('.txt'):
                    client_id = int(client.split('.')[0])
                    user.User(vk, client_id, (None, None))
        except FileNotFoundError:
            pass

    config_logging()
    logger = logging.getLogger('bot.main')

    logger.info('START BOT')
    vk_session = vk_api.VkApi(token=config.group_token)
    vk = vk_session.get_api()
    longpoll = BotLongPollTimeoutHandled(vk_session, config.group_id)

    users_queue = queue.Queue(20)
    start_threads(users_queue, vk)
    start(vk)

    for event in longpoll.listen():

        if event.type == VkBotEventType.MESSAGE_NEW:
            user_id = event.obj.message['from_id']
            message = event.obj.message['text']
            logger.info("New message '%s' from [%s].", message, user_id)

            task = message_handler.task(message)  # (status, [v1, v2...])
            logger.info(
                "Create task: '%s' with data: %s.", task[0], str(task[1]))

            users_queue.put(user.User(vk, user_id, task))


if __name__ == '__main__':
    main()
