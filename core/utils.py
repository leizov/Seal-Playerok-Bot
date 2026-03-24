import os
import re
import sys
import ctypes
import logging
import pkg_resources
import subprocess
import requests
import random
import time
import asyncio
from colorlog import ColoredFormatter
from colorama import Fore
from threading import Thread
from logging import getLogger

# Импорт путей из центрального модуля
import paths


logger = getLogger("seal.utils")
_main_loop = None


def init_main_loop(loop):
    """Инициализирует основной loop событий."""
    global _main_loop 
    _main_loop = loop


def get_main_loop():
    """Получает основной loop событий."""
    return _main_loop


def shutdown():
    """Завершает работу программы (завершает все задачи основного loop`а)."""
    for task in asyncio.all_tasks(_main_loop):
        task.cancel()
    _main_loop.call_soon_threadsafe(_main_loop.stop)


def restart():
    """Перезагружает программу."""
    try:
        from logging import getLogger
        logger = getLogger("seal.restart")
        logger.info("Перезапуск бота...")

        bot_entry = paths.get_path("bot.py")
        python = sys.executable
        os.chdir(paths.ROOT_DIR)
        if sys.platform == "win32":
            os.system("cls")
            # На Windows execv иногда некорректно обрабатывает окружение запуска.
            # Запускаем новый процесс явно и завершаем текущий.
            subprocess.Popen([python, bot_entry], cwd=paths.ROOT_DIR)
            os._exit(0)
        os.execv(python, [python, bot_entry])
    except Exception as e:
        from logging import getLogger
        from colorama import Fore
        logger = getLogger("seal.restart")
        logger.error(f"{Fore.LIGHTRED_EX}Ошибка при перезапуске: {Fore.WHITE}{e}")
        logger.info(f"{Fore.YELLOW}Пожалуйста, перезапустите бота вручную.")
        # Не падаем, просто логируем ошибку
        import traceback
        logger.debug(traceback.format_exc())


def set_title(title: str):
    """
    Устанавливает заголовок консоли.

    :param title: Заголовок.
    :type title: `str`
    """
    try:
        if sys.platform == "win32":
            ctypes.windll.kernel32.SetConsoleTitleW(title)
        elif sys.platform.startswith("linux") or sys.platform == "darwin":
            # Проверяем что stdout это терминал (не systemd/pipe)
            if sys.stdout.isatty():
                escape = "\x1b]2;" if sys.platform.startswith("linux") else "\x1b]0;"
                sys.stdout.write(f"{escape}{title}\x07")
                sys.stdout.flush()
    except Exception:
        # Игнорируем ошибки (нет терминала, systemd и т.д.)
        pass


def trim_log_file(log_file: str, max_lines: int = 5000, keep_lines: int = 3000):
    """
    Очищает лог-файл по количеству строк.
    Если строк больше max_lines, оставляет только последние keep_lines.
    """
    try:
        if not log_file or not os.path.exists(log_file):
            return

        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        if len(lines) <= max_lines:
            return

        tail = lines[-keep_lines:]
        with open(log_file, "w", encoding="utf-8", errors="replace") as f:
            f.writelines(tail)
    except Exception as e:
        # Здесь нельзя ронять инициализацию логгера.
        print(f"[WARN] Не удалось обрезать лог-файл {log_file}: {e}")


def setup_logger(log_file: str = None, show_seal_art: bool = True, seal_variant: int = 1):
    """
    Настраивает логгер с морским стилем.

    :param log_file: Путь к файлу логов.
    :type log_file: `str`
    :param show_seal_art: Показывать ли ASCII-арт тюленя при запуске.
    :type show_seal_art: `bool`
    """
    class ShortLevelFormatter(ColoredFormatter):
        def format(self, record):
            record.shortLevel = record.levelname[0]
            return super().format(record)

    # Используем абсолютные пути из модуля paths
    if log_file is None:
        log_file = paths.LATEST_LOG_FILE
    os.makedirs(paths.LOGS_DIR, exist_ok=True)
    trim_log_file(log_file, max_lines=5000, keep_lines=3000)
    
    # Морская цветовая палитра для логов
    LOG_FORMAT = "%(light_black)s%(asctime)s%(reset)s %(cyan)s•%(reset)s %(log_color)s%(shortLevel)s%(reset)s %(white)s%(message)s"
    formatter = ShortLevelFormatter(
        LOG_FORMAT,
        datefmt="%H:%M:%S",
        reset=True,
        log_colors={
            'DEBUG': 'cyan',  # Голубой для дебага
            'INFO': 'light_cyan',  # Светло-голубой для инфо
            'WARNING': 'light_purple',  # Фиолетовый для предупреждений (контраст)
            'ERROR': 'light_red',  # Светло-красный для ошибок
            'CRITICAL': 'bold_red',  # Жирный красный для критических
        },
        style='%'
    )
    
    # Выводим ASCII-арт тюленя при запуске
    # if show_seal_art:
    #     _print_seal_art(1)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    class StripColorFormatter(logging.Formatter):
        ansi_escape = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
        def format(self, record):
            message = super().format(record)
            return self.ansi_escape.sub('', message)
        
    file_handler.setFormatter(StripColorFormatter(
        "[%(asctime)s] %(levelname)-1s · %(name)-20s %(message)s",
        datefmt="%d.%m.%Y %H:%M:%S",
    ))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    for handler in root_logger.handlers[:]:
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
        root_logger.removeHandler(handler)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    return root_logger


def _print_seal_art(variant: int = 1):
    """
    Выводит большую ASCII-иконку тюленя.
    
    :param variant: Номер варианта иконки (1, 2)
    """
    # Вариант 1: Высококачественная детализированная иконка (FunPay Cardinal Style)
    seal_icon_1 = f"""
{Fore.CYAN}                    ～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～
{Fore.LIGHTCYAN_EX}                         ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
{Fore.LIGHTCYAN_EX}                      ░░░{Fore.CYAN}▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒{Fore.LIGHTCYAN_EX}░░░
{Fore.LIGHTCYAN_EX}                    ░░{Fore.CYAN}▒▒▒{Fore.WHITE}▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓{Fore.CYAN}▒▒▒{Fore.LIGHTCYAN_EX}░░
{Fore.LIGHTCYAN_EX}                  ░░{Fore.CYAN}▒▒{Fore.WHITE}▓▓▓{Fore.LIGHTWHITE_EX}█████████████████████████████████████████{Fore.WHITE}▓▓▓{Fore.CYAN}▒▒{Fore.LIGHTCYAN_EX}░░
{Fore.LIGHTCYAN_EX}                 ░{Fore.CYAN}▒▒{Fore.WHITE}▓▓{Fore.LIGHTWHITE_EX}████████{Fore.LIGHTBLACK_EX}▒▒▒▒{Fore.LIGHTWHITE_EX}████████████████████{Fore.LIGHTBLACK_EX}▒▒▒▒{Fore.LIGHTWHITE_EX}████████{Fore.WHITE}▓▓{Fore.CYAN}▒▒{Fore.LIGHTCYAN_EX}░
{Fore.LIGHTCYAN_EX}                ░{Fore.CYAN}▒{Fore.WHITE}▓▓{Fore.LIGHTWHITE_EX}████████{Fore.LIGHTBLACK_EX}▒{Fore.BLACK}██{Fore.LIGHTBLACK_EX}▒{Fore.LIGHTWHITE_EX}████████████████{Fore.LIGHTBLACK_EX}▒{Fore.BLACK}██{Fore.LIGHTBLACK_EX}▒{Fore.LIGHTWHITE_EX}████████{Fore.WHITE}▓▓{Fore.CYAN}▒{Fore.LIGHTCYAN_EX}░  {Fore.LIGHTMAGENTA_EX}🦭
{Fore.LIGHTCYAN_EX}               ░{Fore.CYAN}▒{Fore.WHITE}▓{Fore.LIGHTWHITE_EX}██████████{Fore.LIGHTBLACK_EX}▒{Fore.BLACK}█{Fore.WHITE}◉{Fore.BLACK}█{Fore.LIGHTBLACK_EX}▒{Fore.LIGHTWHITE_EX}██████████████{Fore.LIGHTBLACK_EX}▒{Fore.BLACK}█{Fore.WHITE}◉{Fore.BLACK}█{Fore.LIGHTBLACK_EX}▒{Fore.LIGHTWHITE_EX}██████████{Fore.WHITE}▓{Fore.CYAN}▒{Fore.LIGHTCYAN_EX}░
{Fore.LIGHTCYAN_EX}               ░{Fore.CYAN}▒{Fore.WHITE}▓{Fore.LIGHTWHITE_EX}███████████{Fore.LIGHTBLACK_EX}▒▒▒▒{Fore.LIGHTWHITE_EX}████{Fore.LIGHTBLACK_EX}▒{Fore.BLACK}░░{Fore.LIGHTBLACK_EX}▒{Fore.LIGHTWHITE_EX}████{Fore.LIGHTBLACK_EX}▒{Fore.BLACK}░░{Fore.LIGHTBLACK_EX}▒{Fore.LIGHTWHITE_EX}████{Fore.LIGHTBLACK_EX}▒▒▒▒{Fore.LIGHTWHITE_EX}███████████{Fore.WHITE}▓{Fore.CYAN}▒{Fore.LIGHTCYAN_EX}░
{Fore.LIGHTCYAN_EX}               ░{Fore.CYAN}▒{Fore.WHITE}▓{Fore.LIGHTWHITE_EX}██████████████████{Fore.LIGHTBLACK_EX}▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒{Fore.LIGHTWHITE_EX}██████████████████{Fore.WHITE}▓{Fore.CYAN}▒{Fore.LIGHTCYAN_EX}░
{Fore.LIGHTCYAN_EX}               ░{Fore.CYAN}▒{Fore.WHITE}▓{Fore.LIGHTWHITE_EX}████████████████████{Fore.LIGHTBLACK_EX}▒▒▒▒▒▒▒▒▒▒▒{Fore.LIGHTWHITE_EX}████████████████████{Fore.WHITE}▓{Fore.CYAN}▒{Fore.LIGHTCYAN_EX}░
{Fore.LIGHTCYAN_EX}                ░{Fore.CYAN}▒{Fore.WHITE}▓{Fore.LIGHTWHITE_EX}█████████████████████{Fore.LIGHTBLACK_EX}▒▒▒▒▒▒▒{Fore.LIGHTWHITE_EX}█████████████████████{Fore.WHITE}▓{Fore.CYAN}▒{Fore.LIGHTCYAN_EX}░
{Fore.LIGHTCYAN_EX}                ░{Fore.CYAN}▒{Fore.WHITE}▓▓{Fore.LIGHTWHITE_EX}███████████████████████████████████████████{Fore.WHITE}▓▓{Fore.CYAN}▒{Fore.LIGHTCYAN_EX}░
{Fore.LIGHTCYAN_EX}                 ░{Fore.CYAN}▒{Fore.WHITE}▓▓{Fore.LIGHTWHITE_EX}█████████████████████████████████████████{Fore.WHITE}▓▓{Fore.CYAN}▒{Fore.LIGHTCYAN_EX}░
{Fore.LIGHTCYAN_EX}                  ░{Fore.CYAN}▒▒{Fore.WHITE}▓▓{Fore.LIGHTWHITE_EX}███████████████████████████████████████{Fore.WHITE}▓▓{Fore.CYAN}▒▒{Fore.LIGHTCYAN_EX}░
{Fore.LIGHTCYAN_EX}                   ░░{Fore.CYAN}▒▒{Fore.WHITE}▓▓{Fore.LIGHTWHITE_EX}███████████████████████████████████{Fore.WHITE}▓▓{Fore.CYAN}▒▒{Fore.LIGHTCYAN_EX}░░
{Fore.LIGHTCYAN_EX}                     ░░{Fore.CYAN}▒▒▒{Fore.WHITE}▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓{Fore.CYAN}▒▒▒{Fore.LIGHTCYAN_EX}░░
{Fore.LIGHTCYAN_EX}                       ░░░{Fore.CYAN}▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒{Fore.LIGHTCYAN_EX}░░░
{Fore.LIGHTCYAN_EX}                          ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
{Fore.CYAN}                    ≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈{Fore.RESET}
    """
    
    # Вариант 2: Реалистичный тюлень с текстурой (High Detail)
    seal_icon_2 = f"""
{Fore.CYAN}                ～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～
{Fore.LIGHTCYAN_EX}                     ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
{Fore.LIGHTCYAN_EX}                  ░░░{Fore.CYAN}▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒{Fore.LIGHTCYAN_EX}░░░
{Fore.LIGHTCYAN_EX}                ░░{Fore.CYAN}▒▒▒{Fore.WHITE}▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓{Fore.CYAN}▒▒▒{Fore.LIGHTCYAN_EX}░░
{Fore.LIGHTCYAN_EX}              ░░{Fore.CYAN}▒▒{Fore.WHITE}▓▓▓{Fore.LIGHTWHITE_EX}███████████████████████████████████{Fore.WHITE}▓▓▓{Fore.CYAN}▒▒{Fore.LIGHTCYAN_EX}░░
{Fore.LIGHTCYAN_EX}             ░{Fore.CYAN}▒▒{Fore.WHITE}▓▓{Fore.LIGHTWHITE_EX}██████████{Fore.LIGHTBLACK_EX}░░░░{Fore.LIGHTWHITE_EX}█████████████{Fore.LIGHTBLACK_EX}░░░░{Fore.LIGHTWHITE_EX}██████████{Fore.WHITE}▓▓{Fore.CYAN}▒▒{Fore.LIGHTCYAN_EX}░
{Fore.LIGHTCYAN_EX}            ░{Fore.CYAN}▒{Fore.WHITE}▓▓{Fore.LIGHTWHITE_EX}███████████{Fore.LIGHTBLACK_EX}░▒▒░{Fore.LIGHTWHITE_EX}███████████{Fore.LIGHTBLACK_EX}░▒▒░{Fore.LIGHTWHITE_EX}███████████{Fore.WHITE}▓▓{Fore.CYAN}▒{Fore.LIGHTCYAN_EX}░  {Fore.LIGHTMAGENTA_EX}🦭
{Fore.LIGHTCYAN_EX}           ░{Fore.CYAN}▒{Fore.WHITE}▓{Fore.LIGHTWHITE_EX}████████████{Fore.LIGHTBLACK_EX}░{Fore.BLACK}█{Fore.WHITE}◉{Fore.BLACK}█{Fore.LIGHTBLACK_EX}░{Fore.LIGHTWHITE_EX}█████████{Fore.LIGHTBLACK_EX}░{Fore.BLACK}█{Fore.WHITE}◉{Fore.BLACK}█{Fore.LIGHTBLACK_EX}░{Fore.LIGHTWHITE_EX}████████████{Fore.WHITE}▓{Fore.CYAN}▒{Fore.LIGHTCYAN_EX}░
{Fore.LIGHTCYAN_EX}           ░{Fore.CYAN}▒{Fore.WHITE}▓{Fore.LIGHTWHITE_EX}███████████████{Fore.LIGHTBLACK_EX}░░░░{Fore.LIGHTWHITE_EX}█████{Fore.LIGHTBLACK_EX}░{Fore.BLACK}░{Fore.LIGHTBLACK_EX}░{Fore.LIGHTWHITE_EX}█████{Fore.LIGHTBLACK_EX}░░░░{Fore.LIGHTWHITE_EX}███████████████{Fore.WHITE}▓{Fore.CYAN}▒{Fore.LIGHTCYAN_EX}░
{Fore.LIGHTCYAN_EX}           ░{Fore.CYAN}▒{Fore.WHITE}▓{Fore.LIGHTWHITE_EX}████████████████████{Fore.LIGHTBLACK_EX}░░░░░░░░░░░{Fore.LIGHTWHITE_EX}████████████████████{Fore.WHITE}▓{Fore.CYAN}▒{Fore.LIGHTCYAN_EX}░
{Fore.LIGHTCYAN_EX}            ░{Fore.CYAN}▒{Fore.WHITE}▓{Fore.LIGHTWHITE_EX}██████████████████████{Fore.LIGHTBLACK_EX}░░░░░░░{Fore.LIGHTWHITE_EX}██████████████████████{Fore.WHITE}▓{Fore.CYAN}▒{Fore.LIGHTCYAN_EX}░
{Fore.LIGHTCYAN_EX}            ░{Fore.CYAN}▒{Fore.WHITE}▓▓{Fore.LIGHTWHITE_EX}███████████████████████████████████████████{Fore.WHITE}▓▓{Fore.CYAN}▒{Fore.LIGHTCYAN_EX}░
{Fore.LIGHTCYAN_EX}             ░{Fore.CYAN}▒{Fore.WHITE}▓▓{Fore.LIGHTWHITE_EX}█████████████████████████████████████████{Fore.WHITE}▓▓{Fore.CYAN}▒{Fore.LIGHTCYAN_EX}░
{Fore.LIGHTCYAN_EX}              ░{Fore.CYAN}▒▒{Fore.WHITE}▓▓{Fore.LIGHTWHITE_EX}███████████████████████████████████████{Fore.WHITE}▓▓{Fore.CYAN}▒▒{Fore.LIGHTCYAN_EX}░
{Fore.LIGHTCYAN_EX}               ░░{Fore.CYAN}▒▒{Fore.WHITE}▓▓▓{Fore.LIGHTWHITE_EX}█████████████████████████████████{Fore.WHITE}▓▓▓{Fore.CYAN}▒▒{Fore.LIGHTCYAN_EX}░░
{Fore.LIGHTCYAN_EX}                 ░░{Fore.CYAN}▒▒▒{Fore.WHITE}▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓{Fore.CYAN}▒▒▒{Fore.LIGHTCYAN_EX}░░
{Fore.LIGHTCYAN_EX}                   ░░░{Fore.CYAN}▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒{Fore.LIGHTCYAN_EX}░░░
{Fore.LIGHTCYAN_EX}                      ░░░░░░░░░░░░░░░░░░░░░░░░░░░
{Fore.CYAN}                ≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈{Fore.RESET}
    """

    
    # Выбор варианта иконки
    variants = {
        1: seal_icon_1,  # Классический (Cardinal)
        2: seal_icon_2,  # С усиками
    }
    
    selected = variants.get(variant, seal_icon_1)
    print(selected)

def _gradient_text(text: str, start_color: tuple = (0, 191, 255), end_color: tuple = (255, 105, 180)) -> str:
    """
    Создаёт текст с градиентом от одного цвета к другому.
    
    :param text: Текст для применения градиента
    :param start_color: Начальный цвет RGB (по умолчанию синий)
    :param end_color: Конечный цвет RGB (по умолчанию розовый)
    :return: Текст с ANSI-кодами градиента
    """
    if not text:
        return text
    
    result = ""
    length = len(text)
    
    for i, char in enumerate(text):
        # Вычисляем текущий цвет на основе позиции
        ratio = i / max(length - 1, 1)
        r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
        
        # ANSI 24-bit True Color: \033[38;2;R;G;Bm
        result += f"\033[38;2;{r};{g};{b}m{char}"
    
    result += "\033[0m"  # Сброс цвета
    return result


def setup_gradient_logger(log_file: str = "logs/latest.log", show_seal_art: bool = True, seal_variant: int = 1):
    """
    Настраивает логгер с градиентом (от синего к розовому).
    Градиент применяется только к префиксу (время + уровень), не к сообщению.

    :param log_file: Путь к файлу логов.
    :param show_seal_art: Показывать ли ASCII-арт тюленя.
    """
    class GradientFormatter(logging.Formatter):
        def format(self, record):
            # Формируем префикс (время + уровень)
            timestamp = self.formatTime(record, "%H:%M:%S")
            levelname = record.levelname[0]  # Первая буква уровня
            
            # Применяем градиент к префиксу
            prefix = f"{timestamp} • {levelname}:"
            gradient_prefix = _gradient_text(
                prefix,
                start_color=(0, 191, 255),    # Светло-голубой
                end_color=(255, 105, 180)      # Розовый
            )
            
            # Сообщение остаётся белым
            message = f"{Fore.WHITE}{record.getMessage()}{Fore.RESET}"
            
            return f"{gradient_prefix} {message}"

    os.makedirs(paths.LOGS_DIR, exist_ok=True)
    trim_log_file(log_file, max_lines=5000, keep_lines=3000)
    
    # Выводим ASCII-арт тюленя при запуске
    if show_seal_art:
        _print_seal_art(seal_variant)
        
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(GradientFormatter())
    console_handler.setLevel(logging.INFO)
    
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    class StripColorFormatter(logging.Formatter):
        ansi_escape = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
        def format(self, record):
            message = super().format(record)
            return self.ansi_escape.sub('', message)
        
    file_handler.setFormatter(StripColorFormatter(
        "[%(asctime)s] %(levelname)-1s · %(name)-20s %(message)s",
        datefmt="%d.%m.%Y %H:%M:%S",
    ))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    for handler in root_logger.handlers[:]:
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
        root_logger.removeHandler(handler)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    return root_logger


def is_package_installed(requirement_string: str) -> bool:
    """
    Проверяет, установлена ли библиотека.

    :param requirement_string: Строка пакета из файла зависимостей.
    :type requirement_string: `str`
    """
    try:
        pkg_resources.require(requirement_string)
        return True
    except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict):
        return False


def install_requirements(requirements_path: str):
    """
    Устанавливает зависимости из файла.

    :param requirements_path: Путь к файлу зависимостей.
    :type requirements_path: `str`
    """
    try:
        if not os.path.exists(requirements_path):
            return
        with open(requirements_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        missing_packages = []
        for line in lines:
            pkg = line.strip()
            if not pkg or pkg.startswith("#") or pkg.startswith("-"):
                continue
            if not is_package_installed(pkg):
                missing_packages.append(pkg)
        if missing_packages:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing_packages])
    except:
        logger.error(f"{Fore.LIGHTRED_EX}Не удалось установить зависимости из файла \"{requirements_path}\"{Fore.RESET}")


def patch_requests():
    """Патчит стандартные requests на кастомные с обработкой ошибок."""
    _orig_request = requests.Session.request
    def _request(self, method, url, **kwargs):  # type: ignore
        for attempt in range(6):
            resp = _orig_request(self, method, url, **kwargs)
            try:
                text_head = (resp.text or "")[:1200]
            except Exception:
                text_head = ""
            statuses = {
                "429": "Too Many Requests",
                "502": "Bad Gateway",
                "503": "Service Unavailable"
            }
            if str(resp.status_code) not in statuses:
                for status in statuses.values():
                    if status in text_head:
                        break
                else: 
                    return resp
            retry_hdr = resp.headers.get("Retry-After")
            try:
                delay = float(retry_hdr) if retry_hdr else min(120.0, 5.0 * (2 ** attempt))
            except Exception:
                delay = min(120.0, 5.0 * (2 ** attempt))
            delay += random.uniform(0.2, 0.8)  # небольшой джиттер
            time.sleep(delay)
        return resp
    requests.Session.request = _request  # type: ignore


def run_async_in_thread(func: callable, args: list = [], kwargs: dict = {}):
    """ 
    Запускает функцию асинхронно в новом потоке и в новом лупе.

    :param func: Функция.
    :type func: `callable`

    :param args: Аргументы функции.
    :type args: `list`

    :param kwargs: Аргументы функции по ключам.
    :type kwargs: `dict`
    """
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(func(*args, **kwargs))
        finally:
            loop.close()

    Thread(target=run, daemon=True).start()


def run_forever_in_thread(func: callable, args: list = [], kwargs: dict = {}):
    """ 
    Запускает функцию в бесконечном лупе в новом потоке.

    :param func: Функция.
    :type func: `callable`

    :param args: Аргументы функции.
    :type args: `list`

    :param kwargs: Аргументы функции по ключам.
    :type kwargs: `dict`
    """
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(func(*args, **kwargs))
        try:
            loop.run_forever()
        finally:
            loop.close()

    Thread(target=run, daemon=True).start()
