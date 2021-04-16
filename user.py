"""
Модуль предоставляет класс User, который содержит всю информацию
для обработки и выполнения задачи, которую поставил пользователь.

"""


import os
import time
import collections
import logging

import vk_api
from vk_api.utils import get_random_id

from Work import texts


class User:
    """Класс, реализующий задачу от пользователя.

    Attributes:
        user_id - целочисленный id пользователя;
        vk - объект vk_api.vk_api.VkApiMethod;
        status - строка, представляющая поступившую задачу;
        values - список значений, поступивших с задачей;
        zone - целочисленное значение, представляющее разницу
            между временем сервера и временем пользователя в
            минутах;
        users - словарь вида {'HH:MM': {12441, 15238}, }, в
            котором ключами является строка с временем напоминания
            (в локальном времени сервера), а значением - множество
            id пользователей, которым нужно напоминание.

    Methods:
        task_handler - для поступившей задачи и значений запускет
            соответствующей метод класса, выполняющий задачу.

    """

    users = collections.defaultdict(set)
    catalog_path = os.path.abspath('users')  # 'Work/users'
    # вернет путь для папки users в той же папке, где находится
    # вызывающая программа (eat_bot.py).

    _logger = logging.getLogger('bot.user')

    def __init__(self, vk: vk_api.vk_api.VkApiMethod, user_id, task):
        """
        Args:
            vk - объект vk_api.vk_api.VkApiMethod;
            user_id - целочисленный id пользователя;
            task - кортеж из задачи и списка значений для задачи.

        Вызывает метод _start() для подготовки данных о клиенте.

        """

        self.user_id = user_id
        self.vk = vk
        self.status = task[0]
        self.values = task[1]

        self.zone = None

        self._start()

    def _start(self):
        """
        Вызывается при инициализации объекта класса.
        Проверяет, существует ли папка users и есть ли в ней
        файл с id пользователя.  Если нет - создает
        'users/<user_id>.txt' и записывает туда первую строку.
        Если есть - считывает часовой пояс и время напоминаний.

        """

        self.user_filename = self.catalog_path + f'/{self.user_id}.txt'

        if not os.path.exists(self.catalog_path):
            os.mkdir(self.catalog_path)

        if not os.path.isfile(self.user_filename):
            text = f"zone=None eating_times=None"
            with open(self.user_filename, 'w') as file:
                file.write(text)

        else:
            data = self._load()

            # Установка часового пояса из файла
            try:
                self.zone = int(data[0][0])
            except ValueError:
                self.zone = None

            for t in data[0][1]:
                if t != 'None':
                    self.users[t].add(self.user_id)
            # Установка времен напоминания из файла

            self._logger.debug(
                '[Task: %s] [client ID: %i] [Timezone: %s] [EatTimes: %s]',
                self.status, self.user_id, self.zone, data[0][1]
            )

    def _send(self, message):
        """Отправляет сформированное сообщение пользователю."""
        self.vk.messages.send(user_id=self.user_id, random_id=get_random_id(),
                              message=message)

    def _load(self):
        """Читает данные из файла пользователя.

        Возвращает список формата:
        [
         [zone: str, [*eatstimes: str]],
         [date: str, [*calories: str]],
         [date: str, [*calories: str]],
        ]

        """

        with open(self.user_filename, 'r') as file:

            first_line = file.readline().strip().split(' ')
            zone = first_line[0].split('=')[1]
            # 'None' или смещение времени в минутах в виде str
            times_to_eat = first_line[1].split('=')[1].split(',')
            # ['None'] or ['HH:MM', 'HH:MM', ...]

            lines = [[zone, times_to_eat]]

            for line in file.readlines():
                string = line.strip().split(' ')
                date = string[0].split('=')[1]
                calories = string[1].split('=')[1].split(',')

                lines.append([date, calories])
                # ['DD.MM', [str, str, str]]

        return lines

    def _save(self, text):
        """
        Сохраняет текст в файл пользователя, польностью
        перезаписывая его.

        """

        with open(self.user_filename, 'w') as file:
            file.write(text)

    def _save_with_data(self, data):
        """Сохраняет сформированные данные.

        Args:
            data - список в формате:
            [
             [zone: str, [*eatstimes: str]],
             [date: str, [*calories: str]],
             [date: str, [*calories: str]],
            ]
             , где первый элемент - первая строка файла
             с часовым поясом и временем опроса пользователя,
             последующие строки - дата и калории в эту дату
             (могут отсутствовать).

        """

        text = f"zone={data[0][0]} times_to_eat={','.join(data[0][1])}"
        if len(data) > 1:
            for date, calories in data[1:]:
                text += f"\ndate={date} calories={','.join(calories)}"

        self._save(text)

    def _user_clock(self):
        """
        Возвращает объект time.struct_time для времени
        пользователя.

        """

        server_time = time.time()
        user_time = server_time - self.zone*60

        return time.localtime(user_time)

    def _user_date(self):
        """Возвращает дату пользователя в формате DD.MM ."""

        date_obj = self._user_clock()
        day = str(date_obj.tm_mday)
        month = str(date_obj.tm_mon)
        date = (
            f"{day if len(day) > 1 else '0' + day}."
            f"{month if len(month) > 1 else '0' + month}"
        )

        return date

    def _save_timezone(self):
        """Сохраняет установленное значение часового пояса."""

        data = self._load()
        data[0][0] = str(self.zone)

        self._save_with_data(data)

    def set_timezone(self):
        """
        Устанавливает в zone значение разности часовых поясов сервера
        и пользователя.  Сохраняет разность в файл пользователя.

        Return:
            кортеж (status: bool, err_message: str or None).

        """

        server_time = time.localtime()  # time.struct_time
        user_input = self.values[0]  # 'HH:MM' or 'HH:MM:SS'

        if len(user_input.split(':')) > 2:
            user_time = time.strptime(user_input, '%H:%M:%S')
        else:
            user_time = time.strptime(user_input, '%H:%M')

        serv_in_min = server_time.tm_hour * 60 + server_time.tm_min
        us_in_min = user_time.tm_hour * 60 + user_time.tm_min

        while (serv_in_min - us_in_min) % 5 != 0:
            serv_in_min -= 1
        # Отнимает от времени сервера по единице, пока разность
        # между временем сервера и клиента не будет кратна пяти.
        # Отнимаем, т.к. время сервера запаздывает по сравнению с
        # клиентским.

        offset = serv_in_min - us_in_min
        if offset > 12 * 60:
            offset -= 24 * 60
        elif offset < -12 * 60:
            offset += 24 * 60
        # учитываем, что может быть разное время суток

        self.zone = offset
        self._save_timezone()

        return True, None

    def _save_calories(self, date, values):
        """
        Записывает в файл введенные калории по текущей дате
        пользователя.

        Args:
            date - строка с датой формата DD.MM ;
            values - список из строк со значениями добавляемых
            калорий.

        """

        data = self._load()
        date_in_file = data[-1][0]

        if date_in_file == date:
            data[-1][1].extend(values)
        else:
            data.append([date, values])

        self._save_with_data(data)

    def add_calories(self):
        """Добавляет введенные калории к списку за день.

        Return:
            кортеж (status: bool, err_message: str or None).

        """

        if self.zone is None:
            return False, 'не установлен часовой пояс'

        self._save_calories(self._user_date(), self.values)

        return True, None

    def sub_calories(self):
        """
        Добавляет введенные значения калорий к списку за день с знаком
        минус.

        Return:
            кортеж (status: bool, err_message: str or None).

        """

        sub_sum = sum([int(values) for values in self.values])  # < 0

        date = self._user_date()  # 'DD.MM'
        eaten_sum = sum(int(cal) for cal in self._give(date)[date])

        if eaten_sum + sub_sum < 0:
            return (
                False,
                'количество вычитаемых калорий меньше '
                'суммы записанных калорий'
            )
        self.add_calories()

        return True, None

    def _give(self, date):
        """Загружает из файла список калорий за указанную дату.

        Args:
            date - это дата в формате 'DD.MM.YYYY' или 'DD.MM',
            либо 'all', либо 'today'.

        Return:
            словарь вида:
            {
             date: [v1, v2, v3],
             date: [v1, v2, v3],
            }
            , в котором date - дата в формате 'DD.MM',
            а значения ключей - список из калорий (в str);
            словарь может быть пустым.

        """

        all_date = True if date == 'all' else False

        if date == 'today':
            date = self._user_date()  # 'DD.MM'
        else:
            temp = date.split('.')
            if len(temp) > 2:
                date = '.'.join(temp[:2])

        data = self._load()

        if all_date:
            calories = {line[0]: line[1] for line in data[1:]}
        else:
            calories = {line[0]: line[1] for line in data[1:] if
                        date == line[0]}

        return calories

    def send_calories(self):
        """
        Отправляет сумму калорий за указанный период пользователю.

        Return:
            кортеж (status: bool, err_message: str or None).

        """

        if self.zone is None:
            return False, 'не установлен часовой пояс'

        date = self.values[0]
        calories = self._give(date)

        if not calories:
            return False, 'нет внесенных значений калорий за указанную дату'

        text = ''
        for day, cals in calories.items():
            text += (f"Дата: {day}. "
                     f"Сумма калорий: {sum([int(cal) for cal in cals])}.\n")

        self._send(text)

        return True, None

    def _save_times_to_eat(self, times):
        """Сохраняет в файл время напоминаний.

        Args:
            times - список времен в формате 'HH:MM'.

        """

        data = self._load()

        # Добавление в файл введенных калорий
        if data[0][1] == ['None']:
            data[0][1] = times
        else:
            data[0][1].extend(times)

        self._save_with_data(data)

    def set_times_to_eat(self):
        """Устанавливает время для напоминаний.

        Переводит локальное время пользователя в локальное
        время сервера. По ключу времени сервера добавляет
        в множество словаря user.users id пользователя, которому
        нужно прислать напоминание в это время.
        Сохраняет это время в файл пользователя.

        Return:
            кортеж (status: bool, err_message: str or None).

        """

        if self.zone is None:
            return False, 'не установлен часовой пояс'

        server_times = []
        for t in self.values:
            temp = t.split(':')
            time_in_min = int(temp[0])*60 + int(temp[1])  # время клиента

            if time_in_min % 5 != 0:
                return False, 'время не кратно 5'
            # Минуты во времени должны быть кратны 5

            server_in_min = time_in_min + self.zone

            hour = str(int(server_in_min/60))
            minute = str(server_in_min - int(hour)*60)
            clock = (f"{hour if len(hour) > 1 else '0' + hour}:"
                     f"{minute if len(minute) > 1 else '0' + minute}")

            server_times.append(clock)

        for t in server_times:
            self.users[t].add(self.user_id)

        self._save_times_to_eat(server_times)

        return True, None

    def error(self, err_text=None):
        """Отправляет пользователю сообщение с ошибкой.

        Args:
            Параметр err_texts - строка с описанием ошибки.

        Return:
            кортеж (True, None) в соответствии с API модуля.

        """

        err_texts = err_text or self.values[0]
        text = (f"Ошибка: {err_texts}. \n"
                f"Команда <help> - информация о пользовании ботом.")
        self._send(text)

        return True, None

    def stop(self):
        """Завершает работу бота для пользователя.

        Удаляет id пользователя из списка для отправки напоминаний,
        удаляет файл пользователя.

        Return:
            кортеж (True, None) в соответствии с API модуля.

        """

        data = self._load()
        for t in data[0][1]:
            if t != 'None':
                self.users[t].remove(self.user_id)

        os.remove(self.user_filename)
        self._send(texts.goodbye_text)

        return True, None

    def reminder(self):
        """Отправляет напоминание пользователю.

        Return:
            кортеж (status: bool, err_message: str or None).

        """

        if self.zone is None:
            return False, 'не установлен часовой пояс'

        text = texts.reminder_text
        self._send(text)

        return True, None

    def help(self):
        """Отправляет информационное сообщение о работе бота.

        Return:
            кортеж (status: bool, err_message: str or None).

        """

        text = texts.help_text
        self._send(text)

        return True, None

    def start(self):
        """Отправляет приветственное сообщение пользователю.

        Return:
            кортеж (status: bool, err_message: str or None).

        """

        text = texts.start_text
        self._send(text)

        return True, None

    def task_handler(self):
        """
        Метод обрабатывает задачи, поступающие от пользователя
        или от класса напоминания.
        Типы возможных задач: 'add', 'sub', 'set time', 'set eating',
        'give', 'reminder', 'stop', 'error', 'start', 'help'.

        """

        tasks = {'add': self.add_calories,
                 'sub': self.sub_calories,
                 'set time': self.set_timezone,
                 'set eating': self.set_times_to_eat,
                 'give': self.send_calories,
                 'stop': self.stop,
                 'error': self.error,
                 'reminder': self.reminder,
                 'start': self.start,
                 'help': self.help}

        is_good, err_text = tasks[self.status]()
        if not is_good:
            self.error(err_text)

        if is_good and self.status in ('add', 'sub', 'set time',
                                       'set eating'):
            self._send('Принято.')
