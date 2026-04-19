import html
import os
from pathlib import Path

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

import paths

from .. import callback_datas as calls
from .. import states
from .. import templates as templ
from ..helpful import throw_float_message


router = Router()

_COMMON_PLUGIN_EXTENSIONS = {
    ".py",
    ".pyd",
    ".so",
    ".dll",
    ".zip",
    ".whl",
}


def _sanitize_plugin_filename(file_name: str) -> str:
    cleaned_name = os.path.basename((file_name or "").strip())
    if not cleaned_name or cleaned_name in {".", ".."}:
        raise ValueError("Некорректное имя файла плагина")
    if "/" in cleaned_name or "\\" in cleaned_name:
        raise ValueError("Недопустимое имя файла")
    return cleaned_name


def _waiting_plugin_file_text() -> str:
    return templ.do_action_text(
        "📥 Отправьте файл плагина в чат.\n\n"
        "Поддерживаются любые файлы плагинов, включая <code>.py</code>, <code>.pyd</code>, <code>.so</code> и другие.\n"
        "Для отмены нажмите <b>Назад</b>."
    )


@router.message(states.PluginStates.waiting_for_plugin_file, F.document)
async def handler_waiting_for_plugin_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)

    try:
        file_name = _sanitize_plugin_filename(message.document.file_name or "")

        status_message = await throw_float_message(
            state=state,
            message=message,
            text=templ.do_action_text(
                f"📥 Загружаю плагин <code>{html.escape(file_name)}</code>, подождите..."
            ),
            reply_markup=templ.destroy_kb(),
        )

        file_info = await message.bot.get_file(message.document.file_id)
        downloaded_file = await message.bot.download_file(file_info.file_path)
        file_bytes = downloaded_file if isinstance(downloaded_file, bytes) else downloaded_file.read()

        plugins_dir = Path(paths.PLUGINS_DIR)
        plugins_dir.mkdir(parents=True, exist_ok=True)
        destination_path = plugins_dir / file_name

        if destination_path.exists() and destination_path.is_dir():
            raise ValueError("Невозможно перезаписать директорию файлом")

        with open(destination_path, "wb") as file:
            file.write(file_bytes)

        await state.set_state(None)

        suffix = destination_path.suffix.lower()
        extension_warning = ""
        if suffix and suffix not in _COMMON_PLUGIN_EXTENSIONS:
            extension_warning = (
                "\n⚠️ Расширение файла нестандартное для плагинов. "
                "Проверьте совместимость вручную."
            )

        await throw_float_message(
            state=state,
            message=status_message or message,
            text=templ.do_action_text(
                f"✅ Плагин <code>{html.escape(file_name)}</code> загружен в папку <code>plugins/</code>."
                f"{extension_warning}\n\n"
                "💡 Для подключения или обновления плагина используйте команду <code>/restart</code>."
            ),
            reply_markup=templ.back_kb(calls.PluginsPagination(page=last_page).pack()),
        )
    except Exception as e:
        await throw_float_message(
            state=state,
            message=message,
            text=templ.do_action_text(
                f"❌ Не удалось загрузить плагин: <code>{html.escape(str(e))}</code>"
            ),
            reply_markup=templ.back_kb(calls.PluginsPagination(page=last_page).pack()),
        )


@router.message(states.PluginStates.waiting_for_plugin_file)
async def handler_waiting_for_plugin_file_invalid_input(message: types.Message, state: FSMContext):
    data = await state.get_data()
    last_page = data.get("last_page", 0)
    await throw_float_message(
        state=state,
        message=message,
        text=_waiting_plugin_file_text(),
        reply_markup=templ.back_kb(calls.PluginsPagination(page=last_page).pack()),
    )
