"""
    Задача:
    Бот - персональный дневник счета съеденных калорий.

    Напоминает выбранное количество раз и в выбранное время
    присылать ему  количество съеденных калорий до этого времени
    в этот день.
    Позволяет суммировать калории за день, вычесть из суммы значение
    на случай ошибки.
    Хранит данные, и в выбранную дату присылает статистику за прошедший
    период ведения дневника.
    Реализует некоторое управление при помощи встроенной клавиатуры.
"""

import threading
import queue
import time
import vk_api
from vk_api.bot_longpoll import *
from Work import message_handler, config, user


class BotLongPollTimeoutHandled(VkBotLongPoll):
    def listen(self):
        while True:
            try:
                for event in self.check():
                    yield event
            except Exception as err:
                with open('errors.txt', 'a') as file:
                    t = time.localtime()
                    text = f"{err.__repr__()} time={t.tm_hour}:{t.tm_min}\n"

                    file.write(text)


class UserHandler(threading.Thread):
    def __init__(self, q):
        super().__init__()
        self.q = q

        self.daemon = True

    def run(self):
        while True:
            client = self.q.get()
            try:
                client.task_handler()
            except Exception as err:
                with open('errors.txt', 'a') as file:
                    t = time.localtime()
                    text = f"{err.__repr__()} time={t.tm_hour}:{t.tm_min}\n"

                    file.write(text)
            finally:
                self.q.task_done()


class Reminder(threading.Thread):
    def __init__(self, vk: vk_api.vk_api.VkApiMethod, q):
        super().__init__()
        self.vk = vk
        self.client = user.User
        self.q = q
        self.times_min = []

        self.daemon = True

        self._task = ('reminder', [None])

    def _set_times(self):
        """
            Создает список минут для проверки.
            Возвращает список из целых чисел от текущего
            времени до полуночи с шагом в 5 минут, время в этом
            списке - в минутах от полуночи.
        """
        now_min = self.time_to_min()

        min_aliquot5 = now_min//5 * 5 + 5
        if min_aliquot5 == 1440:
            min_aliquot5 = 0

        self.times_min = [i for i in range(min_aliquot5, 24*60, 5)]

    def time_to_min(self):
        """
            Возвращает время в минутах от полуночи.
        """
        now = time.localtime()
        return now.tm_hour * 60 + now.tm_min

    def time_to_hour_min(self, time_in_min):
        hour = time_in_min//60
        minutes = time_in_min - hour*60

        return f"{hour if hour > 9 else '0' + str(hour)}:" \
               f"{minutes if minutes > 9 else '0' + str(minutes)}"

    def sleeper(self, delay=5):
        """
            Спит с шагом в delay секунд до тех пор, пока не
            подойдет следующее время.
        """
        if not len(self.times_min):
            self._set_times()

        while True:
            step = self.times_min[0] or 24*60
            if self.time_to_min() < step:
                time.sleep(delay)
            else:
                break

        return self.times_min.pop(0)

    def run(self):
        while True:
            # блокирует, пока не подойдет время для опроса
            clock = self.sleeper()

            time_check = self.time_to_hour_min(clock)

            try:
                for person in self.client.users[time_check]:
                    self.q.put(self.client(self.vk, person, self._task))
            except Exception as err:
                with open('errors.txt', 'a') as file:
                    t = time.localtime()
                    text = f"{err.__repr__()} time={t.tm_hour}:{t.tm_min}\n"

                    file.write(text)


def start_threads(turn, vk, threads_count=4):
    threads = []
    for _ in range(threads_count):
        thr = UserHandler(turn)
        thr.start()

        threads.append(thr)

    rem = Reminder(vk, turn)
    rem.start()

    return threads, rem


def main():
    vk_session = vk_api.VkApi(token=config.group_token)
    vk = vk_session.get_api()
    longpoll = BotLongPollTimeoutHandled(vk_session, config.group_id)

    users_queue = queue.Queue(20)
    start_threads(users_queue, vk)

    for event in longpoll.listen():

        if event.type == VkBotEventType.MESSAGE_NEW:
            user_id = event.obj.message['from_id']
            task = message_handler.task(event.obj.message['text'])

            users_queue.put(user.User(vk, user_id, task))


if __name__ == '__main__':
    main()
