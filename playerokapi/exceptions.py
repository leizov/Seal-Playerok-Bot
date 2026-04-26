import requests


class CloudflareDetectedException(Exception):
    """
    Ошибка обнаружения Cloudflare защиты при отправке запроса.

    :param response: Объект ответа.
    :type response: `Response`
    """

    def __init__(self, response: requests.Response):
        self.response = response
        self.status_code = self.response.status_code
        self.html_text = self.response.text
        lower_text = (self.html_text or "").lower()
        is_ddos_guard = "ddos-guard" in lower_text or "check.ddos-guard.net" in lower_text
        self.vendor = "ddos_guard" if is_ddos_guard else "cloudflare"
        self.vendor_title = "DDoS-Guard" if is_ddos_guard else "Cloudflare"

    def __str__(self):
        msg = (
            f"Ошибка: {self.vendor_title} заметил подозрительную активность при отправке запроса на сайт Playerok."
            f"\nКод ошибки: {self.status_code}"
            f"\nОтвет: {self.html_text}"
        )
        return msg


class RequestFailedError(Exception):
    """
    Ошибка, которая возбуждается, если код ответа не равен 200.

    :param response: Объект ответа.
    :type response: `Response`
    """

    def __init__(self, response: requests.Response):
        self.response = response
        self.status_code = self.response.status_code
        self.html_text = self.response.text

    def __str__(self):
        msg = (
            f"Ошибка запроса к {self.response.url}"
            f"\nКод ошибки: {self.status_code}"
            f"\nОтвет: {self.html_text}"
        )
        return msg


class RequestError(Exception):
    """
    Ошибка, которая возбуждается, если возникла ошибка при отправке запроса.

    :param response: Объект ответа.
    :type response: `Response`
    """

    def __init__(self, response: requests.Response):
        self.response = response
        self.json = response.json() or {}
        errors = self.json.get("errors", []) if isinstance(self.json, dict) else []
        first_error = errors[0] if errors and isinstance(errors[0], dict) else {}
        extensions = first_error.get("extensions", {}) if isinstance(first_error, dict) else {}

        raw_error_code = None
        if isinstance(extensions, dict):
            raw_error_code = extensions.get("code") or extensions.get("statusCode")
        if raw_error_code is None and isinstance(first_error, dict):
            raw_error_code = first_error.get("code")

        self.error_code = str(raw_error_code or "UNKNOWN_GRAPHQL_ERROR")
        self.error_message = str(first_error.get("message") if isinstance(first_error, dict) else "" or "Неизвестная GraphQL ошибка")

    def __str__(self):
        msg = (
            f"Ошибка запроса к {self.response.url}"
            f"\nКод ошибки: {self.error_code}"
            f"\nСообщение: {self.error_message}"
        )
        return msg


class UnauthorizedError(Exception):
    """
    Ошибка, которая возбуждается, если не удалось подключиться к аккаунту Playerok.
    """

    def __str__(self):
        return "Не удалось подключиться к аккаунту Playerok. Может вы указали неверный token?"


class CurlTimeoutError(Exception):
    """
    Ошибка timeout при запросе через curl_cffi.
    """

    def __init__(self, url: str, timeout_seconds: int, original_exception: Exception | None = None):
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.original_exception = original_exception

    def __str__(self):
        msg = (
            f"Ошибка timeout запроса к {self.url} (таймаут: {self.timeout_seconds} сек).\n"
            f"Ошибка на стророне сайта, если возникает часто попробуйте перезагрузиться."
        )
        if self.original_exception:
            msg += f"\nТехническая причина: {self.original_exception}"
        return msg
