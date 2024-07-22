import logging
import sys
import time
from http import HTTPStatus
from os import getenv

import requests
from telebot import TeleBot
from telebot.apihelper import ApiTelegramException
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = getenv('PRACTICUM_TOKEN')
TELEGRAM_BOT_TOKEN = getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
TIMESTAMP = int(time.time())

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': '<b>Работа проверена:</b> ревьюеру всё понравилось. Ура!',
    'reviewing': '<b>Работа взята на проверку ревьюером.</b>',
    'rejected': '<b>Работа проверена:</b> у ревьюера есть замечания.'
}


def check_tokens():
    """Check if all essential tokens are present."""
    source = ('PRACTICUM_TOKEN', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID')
    absence_tokens = []

    for token in source:
        if not globals()[token]:
            absence_tokens.append(token)

    if absence_tokens:
        logging.critical(
            'Отсутствие обязательных переменных окружения: '
            f'{absence_tokens}')
        raise ValueError


def get_api_answer(timestamp):
    """Send a YaCumHomework API request and checks common HTTP errors."""
    params = {'from_date': timestamp}
    logging.debug(f'Запрос к API, эндпоинт: {ENDPOINT}, параметры: {params}')
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        logging.debug('API успешно вернул ответ')
    except requests.RequestException as error:
        raise ValueError(f'Ошибка при запросе к API: {error}; '
                         f'эндпоинт: {ENDPOINT}; параметры: {params}')

    if response.status_code != HTTPStatus.OK:
        raise ValueError('Ошибка при запросе к API, '
                         f'код: {response.status_code, response.reason}.')

    return response.json()


def check_response(response):
    """Validate YaCumHomework API response according to documentation."""
    logging.debug('Старт проверки ответа API')

    if not isinstance(response, dict):
        raise TypeError('В ответе API данные приведены не как словарь, '
                        f'а как {type(response)}')
    elif 'homeworks' not in response:
        raise KeyError('В ответе API домашки нет ключа "homeworks"')
    elif 'current_date' not in response:
        raise KeyError('В ответе API домашки нет ключа "current_date"')
    elif not isinstance(response['homeworks'], list):
        raise TypeError('В ответе API данные под ключом "homeworks" приведены'
                        f' не как список, а как {type(response["homeworks"])}')

    logging.debug('Ответ API соответствует документации')
    return response['homeworks']


def parse_status(homework):
    """Prepare current Homework status for sending to user."""
    logging.debug('Старт парсинга ответа API')

    if 'status' not in homework:
        raise KeyError('В ответе API домашки нет ключа "status"')
    elif 'homework_name' not in homework:
        raise KeyError('В ответе API домашки нет ключа "homework_name"')

    homework_name = homework['homework_name']
    homework_status = homework['status']
    reviewer_comment = homework['reviewer_comment']

    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(f'В ответе API домашки статус ДЗ: {homework_status} '
                       '- не соответствует ГОСТу')

    logging.debug(f'Новый статус по ДЗ: {homework_name}')
    return ('<b>Изменился статус проверки работы:</b> '
            f'\n\n"{homework_name}".\n\n{HOMEWORK_VERDICTS[homework_status]}'
            f'\n\n<b>Комментарий ревьюера:</b> \n\n<i>{reviewer_comment}</i>')


def send_message(bot, message):
    """Send current Homework status for sending to user."""
    logging.debug('Старт отправки ответа API пользователю')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode='html')
        logging.debug('Бот отправил сообщение, текст: '
                      f'{message}')
    except ApiTelegramException as error:
        logging.error('При отправке сообщения пользователю '
                      f'произошла ошибка: {error}')


def main():
    """Main bot logic body."""
    check_tokens()

    bot = TeleBot(TELEGRAM_BOT_TOKEN)
    last_error = None

    while True:
        try:
            response = get_api_answer(TIMESTAMP)
            homeworks = check_response(response)
            if homeworks:
                homework_info = parse_status(homeworks[0])
                send_message(bot, homework_info)
            else:
                logging.debug('Ответ API не вернул новой информации/статусов')
            last_error = None
        except Exception as error:
            logging.error(f'Сбой в работе Бота: {error}')
            if last_error != error:
                last_error = error
                send_message(bot, f'Сбой в работе Бота: {error}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    log_filename = 'main.log'

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s (%(levelname)s) %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_filename)
        ]
    )
    logging.Formatter.converter = time.gmtime
    main()
