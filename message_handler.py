"""
    Пакет функций для обработки поступающих к боту сообщений.
    Проверяет сообщения на валидность и адекватность, но
    никак не обрабатывает их - не изменяет.

    Возможные команды:
    add [value] - добавление калорий к общему количеству калорий в этот день
    sub [value] - вычитание из общего количества калорий в этот день

    give [value, 'all', 'today'] - возвращает количество калорий

    set time [value] - устанавливает время пользователя в данный момент
    set eating [values] - устанавливает время опросов пользователя
    stop - удаляет данные о пользователе из бота
    start, /start - начальное сообщение
    help - информационное сообщение
"""

COMMANDS = {'add': None,
            'sub': None,
            'give': ['all', 'today'],
            'set': ['time', 'eating'],
            'stop': None,
            'start': None,
            '/start': None,
            'help': None}


def message_to_words(message: str):
    """
        Возвращает список слов из сообщения пользователя.
    """
    words = message.replace(',', ' ').split(' ')
    words = [value.lower() for value in words if value]
    return words


def words_check(words) -> '2-tuple (bool, error_message)':
    """
        Проверяет допустимость слов в сообщении.
    """

    def check_for_date(value_words):
        """
            Проверяет, указана ли дата в формате DD.MM.YY.
        """
        if not value_words:
            return False, 'не указана дата'
        elif len(value_words) != 1:
            return False, 'неверное количество значений даты'

        date = value_words[0]
        list_date = date.split('.')
        if not (len(list_date) in (2, 3)):
            return False, 'неверный формат даты'

        for value in list_date:
            try:
                int(value)
            except ValueError:
                return False, 'неверный формат даты'

        return True, None

    def check_for_time(value_words):
        """
            Проверяет, указано ли время в формате HH:MM или HH:MM:SS.
        """
        if not value_words:
            return False, 'не указано время'

        for word in value_words:
            list_time = word.split(':')
            if not (len(list_time) in (2, 3)):
                return False, 'неверный формат времени'

            for value in list_time:
                try:
                    int(value)
                except ValueError:
                    return False, 'неверный формат времени'

        return True, None

    def check_for_int(value_words):
        """
            Проверяет, целочисленные ли значения переданы.
        """
        if not value_words:
            return False, 'не указано значение'

        for value in value_words:
            try:
                int(value)
            except ValueError:
                return False, 'значение - не целое число'

        return True, None

    # Проверка, указана ли команда первым словом в сообщении
    if words[0] not in COMMANDS:
        return False, 'указана неверная команда первым словом сообщения'

    # Проверка, являются ли значения команд допустимыми
    general_command = words[0]
    if general_command == 'give' and words[1] not in COMMANDS['give']:
        flag, error_text = check_for_date(words[1:])
        if not flag:
            return False, error_text

    elif general_command == 'set':
        if words[1] not in COMMANDS['set']:
            return False, 'не указан тип команды set'
        else:
            flag, error_text = check_for_time(words[2:])
            if not flag:
                return False, error_text

    elif general_command in ('add', 'sub'):
        flag, error_text = check_for_int(words[1:])
        if not flag:
            return False, error_text

    return True, None


def what_doing(message_words) -> '2-tuple (status, data)':
    """
        Возвращает кортеж из 2-ух значений (status, data):
            status может быть ['add', 'sub', 'give', 'set time', 'set eating',
                               'stop', 'start', 'help']
            data - список значений
    """
    general_command = message_words[0]

    if general_command == 'add':
        return 'add', message_words[1:]

    elif general_command == 'sub':
        return 'sub', ['-'+value for value in message_words[1:]]

    elif general_command == 'give':
        return 'give', message_words[1:]

    elif general_command == 'set':
        return ' '.join(('set', message_words[1])), message_words[2:]

    elif general_command == 'stop':
        return 'stop', [None]

    elif general_command in ('start', '/start'):
        return 'start', [None]

    elif general_command == 'help':
        return 'help', [None]


def check_values(status, data):
    """
        Проверяет валидность введенных значений.
        Возвращает те же объекты, если все в порядке,
        иначе возвращает ('error', [error_text]),
        error_text - текст ошибки.
    """

    def check_date(dates):
        """
            Проверка даты на валидность
        """
        # Если указан год:
        if len(dates) > 2:
            # Если дата указана без указания тысячелетия
            if len(dates[2]) <= 2:
                dates[2] = '20'+dates[2]

            list_date = [int(d) for d in dates]

            # Если год указан больше 2038 или месяц больше 12
            if list_date[2] > 2038 or list_date[1] > 12:
                return 'error', ['невалидная дата']
            # Если год високосный, месяц - февраль и число больше 29
            elif (list_date[2] % 4 == 0 and list_date[1] == 2 and
                  list_date[0] > 29):
                return 'error', ['невалидная дата']
            # Если месяц нечетный и дата больше 31
            elif list_date[1] % 2 == 1 and list_date[0] > 31:
                return 'error', ['невалидная дата']
            # Если месяц четный и дата больше 30
            elif list_date[1] % 2 == 0 and list_date[0] > 30:
                return 'error', ['невалидная дата']
            return 'give', ['.'.join(dates)]
        elif len(dates) <= 2:
            list_date = [int(d) for d in dates]

            # Если год указан больше 2038 или месяц больше 12
            if list_date[1] > 12:
                return 'error', ['невалидная дата']
            # Если месяц - февраль и число больше 29
            elif list_date[1] == 2 and list_date[0] > 29:
                return 'error', ['невалидная дата']
            # Если месяц нечетный и дата больше 30
            elif list_date[1] % 2 == 1 and list_date[0] > 31:
                return 'error', ['невалидная дата']
            # Если месяц четный и дата больше 30
            elif list_date[1] % 2 == 0 and list_date[0] > 30:
                return 'error', ['невалидная дата']
            return 'give', ['.'.join(dates)]

    if status in ('add', 'sub'):
        for value in data:
            if abs(int(value)) > 9999:
                return 'error', ['значение больше 9999']
            elif abs(int(value)) < 50:
                return 'error', ['значение меньше 50']

    elif status in ('set time', 'set eating'):
        for date in data:
            list_time = [int(value) for value in date.split(':')]
            if list_time[0] >= 24 or list_time[1] >= 60:
                return 'error', ['неправильный формат времени']
            if len(list_time) > 2:
                if list_time[2] >= 60:
                    return 'error', ['неправильный формат времени']

    elif status == 'give':
        list_date = data[0].split('.')
        if list_date[0] in ('all', 'today'):
            return status, data
        return check_date(list_date)

    return status, data


def task(message: str):
    """
        Возвращает кортеж из двух значений: (status, data),
        status - строка с названием команды, либо 'error',
        data - список из одного или нескольких значений,
        переданных пользователем, либо список с элементом
        None (для команды 'stop').
    """
    message_words = message_to_words(message)
    is_good, error_text = words_check(message_words)
    if not is_good:
        return 'error', [error_text]

    status, answer_message = what_doing(message_words)
    return check_values(status, answer_message)


"""
    Задача: сделать сообщения об ошибках более информативными. 
    Добавить сообщения о рекомендациях к правильному выполнению 
    команды.
"""
