"""
Модуль безопасности для Seal Playerok Bot.
Хэширование паролей с использованием SHA-256 + соль.
"""
import hashlib
import secrets
import os

# Импорт путей из центрального модуля
import paths


# Файл для хранения соли (создаётся один раз)
SALT_FILE = paths.SALT_FILE


def get_or_create_salt() -> bytes:
    """
    Получает или создаёт соль для хэширования.
    Соль хранится в отдельном файле и создаётся один раз.
    
    :return: соль в байтах
    """
    if os.path.exists(SALT_FILE):
        with open(SALT_FILE, "rb") as f:
            return f.read()
    
    # Создаём новую соль
    salt = secrets.token_bytes(32)
    
    # Убеждаемся что директория существует
    os.makedirs(os.path.dirname(SALT_FILE), exist_ok=True)
    
    with open(SALT_FILE, "wb") as f:
        f.write(salt)
    
    return salt


def hash_password(password: str) -> str:
    """
    Хэширует пароль с использованием SHA-256 + соль.
    
    :param password: пароль в открытом виде
    :return: хэш пароля в hex-формате
    """
    if not password:
        return ""
    
    salt = get_or_create_salt()
    # Комбинируем соль + пароль
    salted = salt + password.encode('utf-8')
    # Хэшируем
    return hashlib.sha256(salted).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """
    Проверяет соответствие пароля хэшу.
    
    :param password: пароль в открытом виде
    :param password_hash: сохранённый хэш пароля
    :return: True если пароль верный
    """
    if not password or not password_hash:
        return False
    
    return hash_password(password) == password_hash


def is_password_hashed(password: str) -> bool:
    """
    Проверяет, является ли строка хэшем (64 hex символа для SHA-256).
    
    :param password: строка для проверки
    :return: True если это хэш
    """
    if not password:
        return False
    
    # SHA-256 хэш = 64 hex символа
    if len(password) != 64:
        return False
    
    try:
        int(password, 16)
        return True
    except ValueError:
        return False
