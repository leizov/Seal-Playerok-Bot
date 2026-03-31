import io
import os
import shutil
import zipfile
from logging import getLogger
from typing import Any

import requests
from colorama import Fore

# Импорт путей из центрального модуля
import paths

from __init__ import SKIP_UPDATES, VERSION
from core.utils import restart


REPO = "leizov/Seal-Playerok-Bot"
logger = getLogger("seal.updater")


def _fetch_releases() -> list[dict]:
    headers = {"User-Agent": "SealPlayerokBot-Updater"}
    response = requests.get(
        f"https://api.github.com/repos/{REPO}/releases",
        headers=headers,
        timeout=15,
    )

    try:
        releases = response.json()
    except Exception:
        raise Exception(f"Ошибка запроса к GitHub API: {response.status_code}")

    if isinstance(releases, dict) and releases.get("message"):
        raise Exception(f"GitHub API: {releases.get('message')}")

    if not isinstance(releases, list):
        raise Exception("GitHub API вернул неожиданный формат ответа")

    return releases


def get_update_status() -> dict[str, Any]:
    """
    Проверяет, доступно ли обновление, но не устанавливает его.

    Возвращаемые статусы:
    - no_releases
    - version_not_found
    - up_to_date
    - update_available
    - error
    """
    result: dict[str, Any] = {
        "status": "error",
        "current_version": VERSION,
        "latest_version": None,
        "latest_release": None,
        "error": None,
    }

    try:
        releases = _fetch_releases()

        if not releases:
            logger.info("В репозитории пока нет релизов.")
            result["status"] = "no_releases"
            return result

        latest_release = releases[0]
        latest_version = latest_release.get("tag_name")
        versions = [release.get("tag_name") for release in releases if isinstance(release, dict)]

        result["latest_release"] = latest_release
        result["latest_version"] = latest_version

        if VERSION not in versions:
            logger.info(
                f"Вашей версии {Fore.LIGHTWHITE_EX}{VERSION} {Fore.WHITE}нету в релизах репозитория. "
                f"Последняя версия: {Fore.LIGHTWHITE_EX}{latest_version}"
            )
            result["status"] = "version_not_found"
            return result

        if VERSION == latest_version:
            logger.info(f"У вас установлена последняя версия: {Fore.LIGHTWHITE_EX}{VERSION}")
            result["status"] = "up_to_date"
            return result

        logger.info(f"{Fore.YELLOW}Доступна новая версия: {Fore.LIGHTWHITE_EX}{latest_version}")
        result["status"] = "update_available"
        return result
    except Exception as e:
        logger.error(
            f"{Fore.LIGHTRED_EX}При проверке на наличие обновлений произошла ошибка: {Fore.WHITE}{e}"
        )
        logger.info(f"{Fore.YELLOW}Бот продолжит работу без обновления.")
        result["status"] = "error"
        result["error"] = str(e)
        return result


def install_release_update(release_info: dict, restart_on_success: bool = True) -> dict[str, Any]:
    """
    Скачивает и устанавливает конкретный релиз обновления.

    Возвращаемые статусы:
    - updated
    - download_failed
    - install_failed
    - error
    """
    latest_version = release_info.get("tag_name")
    result: dict[str, Any] = {
        "status": "error",
        "latest_version": latest_version,
        "latest_release": release_info,
        "error": None,
    }

    try:
        logger.info(
            f"Скачиваю обновление: {Fore.LIGHTWHITE_EX}{release_info.get('html_url', latest_version)}"
        )
        update_bytes = download_update(release_info)
        if not update_bytes:
            result["status"] = "download_failed"
            return result

        if not install_update(release_info, update_bytes):
            result["status"] = "install_failed"
            return result

        logger.info(
            f"{Fore.YELLOW}Обновление {Fore.LIGHTWHITE_EX}{latest_version} "
            f"{Fore.YELLOW}было успешно установлено."
        )
        result["status"] = "updated"

        if restart_on_success:
            restart()

        return result
    except Exception as e:
        logger.error(f"{Fore.LIGHTRED_EX}Ошибка установки обновления: {Fore.WHITE}{e}")
        result["status"] = "error"
        result["error"] = str(e)
        return result


def check_for_updates() -> dict[str, Any]:
    """
    Проверяет проект GitHub на наличие новых обновлений.
    Если вышел новый релиз — скачивает и устанавливает обновление.
    """
    status = get_update_status()
    if status["status"] != "update_available":
        return status

    if SKIP_UPDATES:
        logger.info(
            f"Пропускаю установку обновления. Если вы хотите автоматически скачивать обновления, "
            f"измените значение {Fore.LIGHTWHITE_EX}SKIP_UPDATES{Fore.WHITE} на {Fore.YELLOW}False "
            f"{Fore.WHITE}в файле инициализации {Fore.LIGHTWHITE_EX}(__init__.py)"
        )
        return {**status, "status": "skip_updates"}

    return install_release_update(status["latest_release"], restart_on_success=True)


def download_update(release_info: dict) -> bytes:
    """
    Получает файлы обновления.

    :param release_info: Информация о GitHub релизе.
    :type release_info: `dict`

    :return: Содержимое файлов.
    :rtype: `bytes`
    """
    try:
        logger.info(f"Загружаю обновление {release_info['tag_name']}...")
        zip_url = release_info['zipball_url']
        zip_response = requests.get(zip_url, timeout=60)
        if zip_response.status_code != 200:
            raise Exception(f"При скачивании архива обновления произошла ошибка: {zip_response.status_code}")
        return zip_response.content
    except Exception as e:
        logger.error(f"{Fore.LIGHTRED_EX}При скачивании обновления произошла ошибка: {Fore.WHITE}{e}")
        return None


def install_update(release_info: dict, content: bytes) -> bool:
    """
    Устанавливает файлы обновления в текущий проект.

    :param release_info: Информация о GitHub релизе.
    :type release_info: `dict`

    :param content: Содержимое файлов.
    :type content: `bytes`
    """
    temp_dir = ".temp_update"
    try:
        logger.info(f"Устанавливаю обновление {release_info['tag_name']}...")
        with zipfile.ZipFile(io.BytesIO(content), 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
            archive_root = None
            for item in os.listdir(temp_dir):
                if os.path.isdir(os.path.join(temp_dir, item)):
                    archive_root = os.path.join(temp_dir, item)
                    break
            if not archive_root:
                raise Exception("В архиве нет корневой папки!")
            for root, _, files in os.walk(archive_root):
                for file in files:
                    src = os.path.join(root, file)
                    dst = os.path.join(paths.ROOT_DIR, os.path.relpath(src, archive_root))
                    os.makedirs(os.path.dirname(dst), exist_ok=True)

                    # Если файл существует, удаляем его перед копированием
                    # Это позволяет перезаписывать даже работающие файлы на Linux
                    if os.path.exists(dst):
                        try:
                            os.remove(dst)
                        except PermissionError as e:
                            logger.warning(f"Не удалось удалить {dst}: {e}")
                            # Пробуем изменить права и удалить еще раз
                            try:
                                os.chmod(dst, 0o644)
                                os.remove(dst)
                            except Exception:
                                logger.error(f"Не удалось перезаписать файл {dst} из-за прав доступа")
                                continue

                    shutil.copy2(src, dst)
            return True
    except Exception as e:
        logger.error(f"{Fore.LIGHTRED_EX}При установке обновления произошла ошибка: {Fore.WHITE}{e}")
        return False
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
