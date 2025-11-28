import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett

from .. import callback_datas as calls


def settings_watermark_text():
    config = sett.get("config")
    watermark_enabled = "🟢 Включено" if config["playerok"]["watermark"]["enabled"] else "🔴 Выключено"
    watermark_value = config["playerok"]["watermark"]["value"] or "❌ Не задано"
    
    txt = textwrap.dedent(f"""
        ⚙️ <b>Настройки → ©️ Водяной знак</b>

        ©️ <b>Водяной знак под сообщениями:</b> {watermark_enabled}
        ✍️©️ <b>Текст водяного знака:</b> {watermark_value}

        <b>Что такое водяной знак?</b>
        Водяной знак - это текст, который автоматически добавляется в конец всех отправляемых сообщений. Это может быть полезно для брендирования или добавления дополнительной информации.

        Выберите параметр для изменения ↓
    """)
    return txt


def settings_watermark_kb():
    config = sett.get("config")
    watermark_enabled = "🟢 Включено" if config["playerok"]["watermark"]["enabled"] else "🔴 Выключено"
    watermark_value = config["playerok"]["watermark"]["value"] or "❌ Не задано"
    
    rows = [
        [InlineKeyboardButton(text=f"©️ Водяной знак: {watermark_enabled}", callback_data="switch_watermark_enabled")],
        [InlineKeyboardButton(text=f"✍️©️ Изменить текст", callback_data="enter_watermark_value")],
        [InlineKeyboardButton(text=f"🎨 Выбрать шаблон", callback_data="watermark_presets")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def settings_watermark_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        ⚙️ <b>Настройки → ©️ Водяной знак</b>
        \n{placeholder}
    """)
    return txt


def watermark_presets_text():
    config = sett.get("config")
    current_watermark = config["playerok"]["watermark"]["value"] or "❌ Не задано"
    
    txt = textwrap.dedent(f"""
        🎨 <b>Настройки → ©️ Водяной знак → Шаблоны</b>

        Текущий водяной знак: <code>{current_watermark}</code>

        Выберите один из готовых шаблонов ниже:
    """)
    return txt


def watermark_presets_kb():
    # Различные варианты Seal Playerok с разными шрифтами и эмодзи
    presets = [
        ("🦭 𝗦𝗲𝗮𝗹 𝗣𝗹𝗮𝘆𝗲𝗿𝗼𝗸 (жирный)", "🦭 𝗦𝗲𝗮𝗹 𝗣𝗹𝗮𝘆𝗲𝗿𝗼𝗸"),
        ("🦭 Seal Playerok (обычный)", "🦭 Seal Playerok"),
        ("🌊 𝗦𝗲𝗮𝗹 𝗣𝗹𝗮𝘆𝗲𝗿𝗼𝗸 (жирный)", "🌊 𝗦𝗲𝗮𝗹 𝗣𝗹𝗮𝘆𝗲𝗿𝗼𝗸"),
        ("🌊 Seal Playerok (обычный)", "🌊 Seal Playerok"),
        ("💙 𝗦𝗲𝗮𝗹 𝗣𝗹𝗮𝘆𝗲𝗿𝗼𝗸 (жирный)", "💙 𝗦𝗲𝗮𝗹 𝗣𝗹𝗮𝘆𝗲𝗿𝗼𝗸"),
        ("💙 Seal Playerok (обычный)", "💙 Seal Playerok"),
        ("✨ 𝗦𝗲𝗮𝗹 𝗣𝗹𝗮𝘆𝗲𝗿𝗼𝗸 (жирный)", "✨ 𝗦𝗲𝗮𝗹 𝗣𝗹𝗮𝘆𝗲𝗿𝗼𝗸"),
        ("✨ 𝗦𝗲𝗮𝗹 𝗣𝗹𝗮𝘆𝗲𝗿𝗼𝗸", "✨ 𝗦𝗲𝗮𝗹 𝗣𝗹𝗮𝘆𝗲𝗿𝗼𝗸"),
        ("🦭 𝑺𝒆𝒂𝒍 𝑷𝒍𝒂𝒚𝒆𝒓𝒐𝒌", "🦭 𝑺𝒆𝒂𝒍 𝑷𝒍𝒂𝒚𝒆𝒓𝒐𝒌"),
        ("🌊 𝑺𝒆𝒂𝒍 𝑷𝒍𝒂𝒚𝒆𝒓𝒐𝒌", "🌊 𝑺𝒆𝒂𝒍 𝑷𝒍𝒂𝒚𝒆𝒓𝒐𝒌"),
        ("💙 𝑺𝒆𝒂𝒍 𝑷𝒍𝒂𝒚𝒆𝒓𝒐𝒌", "💙 𝑺𝒆𝒂𝒍 𝑷𝒍𝒂𝒚𝒆𝒓𝒐𝒌"),
        ("✨ 𝑺𝒆𝒂𝒍 𝑷𝒍𝒂𝒚𝒆𝒓𝒐𝒌", "✨ 𝑺𝒆𝒂𝒍 𝑷𝒍𝒂𝒚𝒆𝒓𝒐𝒌"),
        ("🦭 𝚂𝚎𝚊𝚕 𝙿𝚕𝚊𝚢𝚎𝚛𝚘𝚔", "🦭 𝚂𝚎𝚊𝚕 𝙿𝚕𝚊𝚢𝚎𝚛𝚘𝚔"),
        ("🌊 𝚂𝚎𝚊𝚕 𝙿𝚕𝚊𝚢𝚎𝚛𝚘𝚔", "🌊 𝚂𝚎𝚊𝚕 𝙿𝚕𝚊𝚢𝚎𝚛𝚘𝚔"),
        ("💙 𝚂𝚎𝚊𝚕 𝙿𝚕𝚊𝚢𝚎𝚛𝚘𝚔", "💙 𝚂𝚎𝚊𝚕 𝙿𝚕𝚊𝚢𝚎𝚛𝚘𝚔"),
        ("✨ 𝚂𝚎𝚊𝚕 𝙿𝚕𝚊𝚢𝚎𝚛𝚘𝚔", "✨ 𝚂𝚎𝚊𝚕 𝙿𝚕𝚊𝚢𝚎𝚛𝚘𝚔")
    ]
    
    rows = []
    for label, value in presets:
        rows.append([InlineKeyboardButton(text=label, callback_data=calls.SetWatermark(value=value).pack())])
    
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.SettingsNavigation(to="watermark").pack())])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb
