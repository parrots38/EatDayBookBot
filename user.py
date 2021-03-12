"""
    Порядок работы с ботом:
    1. Пользователь первый отправляет сообщение - приветственное.
    Бот в ответ сообщает порядок работы с ним.
    2. Чтобы использовать любую команду, сначала необходимо
    установить часовой пояс пользователя. Поэтому первая
    валидная команда пользователя: set time (кроме start, help,
    которые просто посылают заранее определенные сообщения, и stop).
    3. Затем есть 2 пути использования бота:
    - не используя напоминания, а просто записывая в него потраченные
    калории; тогда команда set eating может быть не вызвана ни разу,
    при этом это никак не влияет на все остальные функции бота: give,
    add, sub, stop, help, start, error вызываются спокойно, а вот
    reminder не будет вызвана никогда.
    - используя напоминания, тогда нужно вызвать команду set eating и
    записать время для напоминаний; которое тем не менее никак не влияет
    на работу других функций, кроме reminder, которая непосредственно
    зависит от времени напоминаний.
    4. На данный момент сбросить время напоминаний можно заново переустановив
    новое время, либо, если нужно совсем перестать напоминать, вызвав
    stop.
    5. Вызов stop польностью прекращает работу бота для этого пользователя,
    удаляя файл с id пользователя и стирая его id из словаря с временами
    напоминания.
"""


import os
import time
import collections
import vk_api
from vk_api.utils import get_random_id
from Work import texts


class User:
    users = collections.defaultdict(set)

    # Сформирует путь для папки users в той же папке, где находится
    # вызывающая программа (то есть, где находится eat_bot.py)
    _catalog_path = os.path.abspath('users')

    def __init__(self, vk: vk_api.vk_api.VkApiMethod, user_id, task):
        self.user_id = user_id
        self.vk = vk
        self.status = task[0]
        self.values = task[1]

        self.zone = None
        self.eating_times = None

        self._start()

    def _start(self):
        """
            Вызывается при инициализации объекта класса.
            Проверяет, существует ли папка users и есть ли в ней
            файл с id пользователя. Если нет - создает 'users/<user_id>.txt'
            и записывает туда первую строку.
        """

        self.user_filename = self._catalog_path + f'/{self.user_id}.txt'

        if not os.path.exists(self._catalog_path):
            os.mkdir(self._catalog_path)

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

            # Установка времен напоминания из файла
            for t in data[0][1]:
                if t != 'None':
                    self.users[t].add(self.user_id)

    def _send(self, message):
        self.vk.messages.send(user_id=self.user_id, random_id=get_random_id(),
                              message=message)

    def _load(self):
        """
            Возвращает список формата
            [[zone: str, [*eatstimes: str]],
             [date: str, [*calories: str]],
             [date: str, [*calories: str]],
             ...]
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
            Сохраняет текст в файл пользователя,
            полностью перезаписывая его.
        """
        with open(self.user_filename, 'w') as file:
            file.write(text)

    def _save_with_data(self, data):
        """
            Принимает список data в формате:
            [[zone: str, [*eatstimes: str]],
             [date: str, [*calories: str]],
             [date: str, [*calories: str]],
             ...],
             где первый элемент - первая строка файла
             с часовым поясом и временем опроса пользователя,
             последующие строки - дата и калории в эту дату.
        """

        text = f"zone={data[0][0]} times_to_eat={','.join(data[0][1])}"
        if len(data) > 1:
            for date, calories in data[1:]:
                text += f"\ndate={date} calories={','.join(calories)}"

        self._save(text)

    # Функции, возвращающие локальное время и дату пользователя
    def _user_clock(self):
        """
            Возвращает объект time.struct_time для времени
            пользователя.
        """
        server_time = time.time()
        user_time = server_time - self.zone*60

        return time.localtime(user_time)

    def _user_date(self):
        """
            Возвращает локальную дату пользователя в формате
            "DD.MM".
        """
        date_obj = self._user_clock()
        day = str(date_obj.tm_mday)
        month = str(date_obj.tm_mon)
        date = (f"{day if len(day) > 1 else '0' + day}."
                f"{month if len(month) > 1 else '0' + month}")

        return date

    # Установка и запись в файл часового пояса пользователя
    def _save_timezone(self):
        """
            Сохраняет установленное значение часового пояса.
        """

        data = self._load()
        data[0][0] = str(self.zone)

        self._save_with_data(data)

    def set_timezone(self):
        """
            Устанавливает часовой пояс (его смещение) пользователя
            и сохраняет в файл пользователя.
            Возвращает значение типа int, указывающее разность
            между временем сервера и клиента в минутах.
        """
        server_time = time.localtime()  # time.struct_time
        user_input = self.values[0]  # 'HH:MM' or 'HH:MM:SS'

        if len(user_input.split(':')) > 2:
            user_time = time.strptime(user_input, '%H:%M:%S')
        else:
            user_time = time.strptime(user_input, '%H:%M')

        serv_in_min = server_time.tm_hour * 60 + server_time.tm_min
        us_in_min = user_time.tm_hour * 60 + user_time.tm_min

        # Отнимает от времени сервера по единице, пока разность
        # между временем сервера и клиента не будет кратна пяти.
        # Отнимаем по единице, т.к. время сервера запаздывает по
        # сравнению с клиентом.
        while (serv_in_min - us_in_min) % 5 != 0:
            serv_in_min -= 1

        offset = serv_in_min - us_in_min
        if offset > 12 * 60:
            offset -= 24 * 60
        elif offset < -12 * 60:
            offset += 24 * 60

        self.zone = offset
        self._save_timezone()

        return True, None

    # Запись в файл введенных калорий (add и sub) по датам
    def _save_calories(self, date, values):
        """
            date - дата формата 'DD.MM',
            values - список из добавляемых значений калорий
            (должны быть str).
        """

        data = self._load()
        date_in_file = data[-1][0]

        if date_in_file == date:
            data[-1][1].extend(values)
        else:
            data.append([date, values])

        self._save_with_data(data)

    def add_calories(self):
        if self.zone is None:
            return False, 'не установлен часовой пояс'

        self._save_calories(self._user_date(), self.values)

        return True, None

    def sub_calories(self):
        sub_sum = sum([int(values) for values in self.values])  # < 0

        date = self._user_date()  # 'DD.MM'
        eaten_sum = sum(int(cal) for cal in self._give(date)[date])

        if eaten_sum + sub_sum < 0:
            return False, ('количество вычитаемых калорий меньше '
                           'суммы записанных калорий')
        self.add_calories()

        return True, None

    # Загрузка из файла калорий и отправка пользователю
    def _give(self, date):
        """
            Параметр date - это дата в формате 'DD.MM.YYYY'
            или 'DD.MM', либо 'all', либо 'today'.
            Возвращает словарь:
            {date: [v1, v2, v3],
             date: [v1, v2, v3],
             ...}, в котором date - дата в формате 'DD.MM',
             а значение ключей - список из калорий (в str);
             либо {} - пустой словарь.
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
        """
        if self.zone is None:
            return False, 'не установлен часовой пояс'

        date = self.values[0]
        calories = self._give(date)

        if not calories:
            return False, 'нет внесенных значений калорий за указанную дату.'

        text = ''
        for day, cals in calories.items():
            text += (f"Дата: {day}. "
                     f"Сумма калорий: {sum([int(cal) for cal in cals])}.\n")

        self._send(text)

        return True, None

    # Установка времени для напоминаний и запись его в файл
    def _save_times_to_eat(self, times):
        """
            Аргумент times - список времен в формате 'HH:MM'.
        """

        data = self._load()

        # Добавление в файл введенных калорий
        if data[0][1] == ['None']:
            data[0][1] = times
        else:
            data[0][1].extend(times)

        self._save_with_data(data)

    def set_times_to_eat(self):
        """
            Переводит локальное время пользователя в локальное
            время сервера. По ключу времени сервера добавляет
            в список словаря user.USERS id пользователя, которому
            нужно прислать напоминание в это время.
            Сохраняет это время в файл пользователя.
        """
        if self.zone is None:
            return False, 'не установлен часовой пояс'

        server_times = []
        for t in self.values:
            temp = t.split(':')
            time_in_min = int(temp[0])*60 + int(temp[1])  # время клиента

            # Проверка времени на кратность 5
            if time_in_min % 5 != 0:
                return False, 'время не кратно 5'

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

    # Вывод ошибок
    def error(self, err_text=None):
        """
            Параметр err_texts - список с одним элементом, который
            является строкой с описанием ошибки.
        """
        err_texts = err_text or self.values[0]
        text = (f"Ошибка: {err_texts}. \n"
                f"Команда <help> - информация о пользовании ботом.")
        self._send(text)

        return True, None

    # Удаление информации о пользователе
    def stop(self):
        """
            Удаляет id пользователя из списка для отправки напоминаний,
            удаляет файл пользователя.
        """
        data = self._load()

        for t in data[0][1]:
            if t != 'None':
                self.users[t].remove(self.user_id)

        os.remove(self.user_filename)

        self._send(texts.goodbye_text)

        return True, None

    # Напоминание пользователю
    def reminder(self):
        if self.zone is None:
            return False, 'не установлен часовой пояс'

        text = texts.reminder_text
        self._send(text)

        return True, None

    # Отправка информационного сообщения о боте
    def help(self):
        text = texts.help_text
        self._send(text)

        return True, None

    # Отправка приветственного информационного сообщения о боте
    def start(self):
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
