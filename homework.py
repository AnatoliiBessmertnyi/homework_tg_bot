import logging
import os
import sys
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    'my_logger.log',
    maxBytes=50000000,
    backupCount=5,
    encoding='utf-8'
)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logger.error(f'Ошибка отправки {message}: {error}')
    else:
        logger.debug(
            f'Сообщение "{message}" отправлено в чат: {TELEGRAM_CHAT_ID}!'
        )


def get_api_answer(timestamp):
    """Проверка запроса к API-сервиса."""
    logger.info('Начинаем делать запросы к API-сервису')
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except Exception as error:
        text = f'Ошибка при запросе к основному API: {error}'
        raise Exception(text)
    if response.status_code != HTTPStatus.OK.value:
        text = f'Ошибка запроса к API: {response.status_code}'
        raise Exception(text)
    return response.json()


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не словарь!')
    check_homeworks = response.get('homeworks')
    if check_homeworks is None:
        raise KeyError('Ключ "homeworks" не доступен!')
    if not isinstance(check_homeworks, list):
        raise TypeError('Ответ API не список!')

    try:
        # if not check_homeworks:
        #     return True
        # Но кажется логичнее было бы всю конструкцию изменить на if else!?

        if len(check_homeworks) == 0:
            return False
# Поэтому такая проверка тут кажется более к месту.

        # if len(check_homeworks) != 0:
        #     return True
# А вот такая инверсия выглядит проще для чтения, но она ломает pytest.
# Не понимаю почему:(

    except IndexError:
        raise IndexError('Список Д/З пуст.')
    return check_homeworks


def parse_status(homework):
    """Проверка наличия проверяемых домашних работ и их статусов."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствуют домашние работы по ключу "homework_name"!')
    if 'status' not in homework:
        raise KeyError('Отсутствует статус проверки домашней работы!')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise Exception(
            f'Неизвестный статус проверки домашней работы: {homework_status}!'
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_status = ''
    if not check_tokens():
        text = 'Отсутствуют одна или несколько переменных окружения'
        logging.critical(text)
        sys.exit(text)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date')
            message = parse_status(check_response(response)[0])
            if message != check_status:
                send_message(bot, message)
                check_status = message
            else:
                logger.info('Статус не изменился')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
