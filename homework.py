import logging
import os
import random
import sys
import time
import requests
import vk_api
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
VK_TOKEN = os.getenv('VK_TOKEN')
VK_USER_ID = os.getenv('VK_USER_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    level=logging.DEBUG,
    handlers=[logging.StreamHandler(sys.stdout)],
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяет доступность всех переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'VK_TOKEN': VK_TOKEN,
        'VK_USER_ID': VK_USER_ID
    }
    missing_tokens = [name for name, value in tokens.items() if not value]

    if missing_tokens:
        for token in missing_tokens:
            logger.critical(
                f"Отсутствует обязательная переменная окружения: '{token}'"
            )
        logger.critical("Программа принудительно остановлена.")
        return False
    return True


def send_message(vk, message):
    """Отправляет сообщение в VK пользователю VK_USER_ID."""
    try:
        vk.messages.send(
            user_id=int(VK_USER_ID),
            message=message,
            random_id=random.randint(-2147483648, 2147483647),
            v='5.131'
        )

        logger.debug(f'Бот отправил сообщение "{message}"')
        return True
    except Exception as error:

        logger.error(f"Сбой при отправке сообщения в VK: {error}")
        return False


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса Практикума."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except Exception as error:
        raise ConnectionError(
            f"Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен."
            f"Ошибка: {error}"
        )

    if response.status_code != 200:

        raise requests.exceptions.HTTPError(
            f"Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен."
            f"Код ответа API: {response.status_code}"
        )
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError("Ответ API должен быть словарем")

    if 'homeworks' not in response:
        raise KeyError("В ответе API отсутствует ожидаемый ключ 'homeworks'")

    if not isinstance(response['homeworks'], list):
        raise TypeError("Значение ключа 'homeworks' должно быть списком")

    return True


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе её статус."""
    if 'homework_name' not in homework:
        raise KeyError(
            "В данных домашней работы отсутствует ключ 'homework_name'"
        )
    if 'status' not in homework:
        raise KeyError("В данных домашней работы отсутствует ключ 'status'")

    homework_name = homework['homework_name']
    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f"Неожиданный статус домашней работы,"
                         f"обнаруженный в ответе API: {status}")

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit()

    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    timestamp = int(time.time())

    last_error_message = ""

    logger.info("Homework Bot успешно запущен!")

    while True:
        try:
            response = get_api_answer(timestamp)

            check_response(response)

            homeworks = response.get('homeworks')
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(vk, message)
            else:
                logger.debug("Отсутствие в ответе новых статусов.")
            timestamp = response.get('current_date', int(time.time()))
            last_error_message = ""

        except Exception as error:
            error_message = f"Сбой в работе программы: {error}"
            logger.error(error_message)
            if error_message != last_error_message:
                if send_message(vk, error_message):
                    last_error_message = error_message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
