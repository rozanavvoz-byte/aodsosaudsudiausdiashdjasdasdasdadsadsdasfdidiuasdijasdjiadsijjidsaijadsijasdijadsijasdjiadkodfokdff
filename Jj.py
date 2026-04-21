import asyncio
import logging
import sqlite3
import requests
import json
import os
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from pyrogram import Client
from pyrogram.errors import FloodWait, PeerIdInvalid
from pyrogram.raw import functions, types

BOT_TOKEN = "8375545371:AAHC2iw0DaY-RfclNM_a_cozSrd8Kds6YCo"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
SESSION_DIR = "sintsession"

API_ID = 33676371
API_HASH = '11f7ef1b3c5438260169a080b48e2f9e'

if not os.path.exists(SESSION_DIR):
    os.makedirs(SESSION_DIR)

def get_session_files():
    sessions = []
    if os.path.exists(SESSION_DIR):
        for file in os.listdir(SESSION_DIR):
            if file.endswith(".session"):
                sessions.append(file.replace(".session", ""))
    return sessions

CUSTOM_EMOJI = {
    "warning_gear": "5904258298764334001",
    "link_lock": "5776078972659962594",
    "check_mark": "5774022692642492953",
    "info": "5935757052042285202",
    "rules_icon": "6030563507299160824",
    "shield": "6032636795387121097",
    "unlock": "6037496202990194718",
    "package": "5884479287171485878",
    "pencil": "6039614175917903752",
    "location": "6030418144131026917",
    "back": "6039519841256214245",
    "keyboard": "6039404727542747508",
    "folder": "6039348811363520645",
    "info_icon": "6028435952299413210",
}

REPORT_TEXT = """Бот выкладывает ИНН, СНИЛС, прописку и телефоны людей. Это создаёт угрозу мошенничества и шантажа. Запрещено ToS → https://telegram.org/tos

Требую немедленной блокировки за массовый доксинг → https://telegram.org/tos

Открытый доксинг по номеру телефона: выдаёт ФИО, паспорт, прописку. Нарушение ToS → https://telegram.org/tos

Публикация адресов, телефонов и фото документов. Опасно → https://telegram.org/tos

Бот выдает конфиденциальные данные по запросу. Запрещено → https://telegram.org/tos

Бот сливает адреса регистрации и фактического проживания, паспортные данные → https://telegram.org/tos

Систематическое разглашение ИНН, СНИЛС, ФИО, телефонов → https://telegram.org/tos

Открытый доксинг по ФИО и номеру телефона. Запрещено → https://telegram.org/tos

Открытый слив личных данных: ФИО + дата рождения + номер паспорта + адрес. Прошу срочную блокировку так как нарушает ToS → https://telegram.org/tos

Слив баз: ФИО + ИНН + СНИЛС + адрес + телефон → https://telegram.org/tos"""

DB_NAME = "wiklsn_users.db"
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        accepted_rules BOOLEAN DEFAULT FALSE,
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()

def user_exists(user_id: int) -> bool:
    cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone() is not None

def add_user(user_id: int, username: str = None, first_name: str = None):
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (user_id, username, first_name)
    )
    conn.commit()

def accept_rules_db(user_id: int):
    cursor.execute("UPDATE users SET accepted_rules = TRUE WHERE user_id = ?", (user_id,))
    conn.commit()

def has_accepted_rules(user_id: int) -> bool:
    cursor.execute("SELECT accepted_rules FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result[0] == 1 if result else False

def send_message(chat_id: int, text: str, reply_markup: dict = None, parse_mode: str = "HTML"):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    response = requests.post(f"{API_URL}/sendMessage", json=payload)
    return response.json()

def edit_message(chat_id: int, message_id: int, text: str, reply_markup: dict = None, parse_mode: str = "HTML"):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    response = requests.post(f"{API_URL}/editMessageText", json=payload)
    return response.json()

def send_sticker(chat_id: int, sticker: str):
    payload = {"chat_id": chat_id, "sticker": sticker}
    response = requests.post(f"{API_URL}/sendSticker", json=payload)
    return response.json()

def answer_callback(callback_id: str, text: str = None, show_alert: bool = False):
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = show_alert
    requests.post(f"{API_URL}/answerCallbackQuery", json=payload)

async def report_bot_with_session(session_name: str, bot_username: str) -> tuple:
    client = None
    try:
        session_path = os.path.join(SESSION_DIR, session_name)
        
        session_file = f"{session_path}.session"
        if not os.path.exists(session_file):
            return False, f"❌ Файл {session_name}.session не найден"
        
        client = Client(
            name=session_name,
            api_id=API_ID,
            api_hash=API_HASH,
            workdir=SESSION_DIR
        )
        
        await client.start()
        
        me = await client.get_me()
        
        try:
            bot = await client.get_users(bot_username)
        except Exception as e:
            return False, f"❌ Бот не найден: {str(e)[:50]}"
        
        await client.send_message(bot.id, "/start")
        
        await asyncio.sleep(3)
        
        target_message = None
        async for message in client.get_chat_history(bot.id, limit=15):
            if message.text and message.text.startswith("ℹ️"):
                target_message = message
                break
        
        if not target_message:
            return False, f"❌ Сообщение с ℹ️ не найдено"
        
        report_reason = types.InputReportReasonPersonalDetails()
        
        await client.invoke(
            functions.messages.Report(
                peer=await client.resolve_peer(bot_username),
                id=[target_message.id],
                reason=report_reason,
                message=REPORT_TEXT
            )
        )
        
        await client.stop()
        return True, f"✅ Жалоба отправлена"
        
    except FloodWait as e:
        if client:
            await client.stop()
        return False, f"⏳ FloodWait: {e.value} сек"
    except Exception as e:
        if client:
            try:
                await client.stop()
            except:
                pass
        return False, f"❌ Ошибка: {str(e)[:80]}"

async def run_reports_on_all_sessions(bot_username: str, progress_callback=None):
    session_files = get_session_files()
    
    if not session_files:
        return [], 0
    
    results = []
    success_count = 0
    total = len(session_files)
    
    for i, session_name in enumerate(session_files, 1):
        if progress_callback:
            await progress_callback(f"🔄 {i}/{total}: {session_name}")
        
        success, message = await report_bot_with_session(session_name, bot_username)
        results.append({"session": session_name, "success": success, "message": message})
        if success:
            success_count += 1
        
        await asyncio.sleep(2)
    
    return results, success_count

def get_main_menu_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "правила", "callback_data": "show_rules_from_menu", "style": "primary", "icon_custom_emoji_id": CUSTOM_EMOJI["pencil"]},
                {"text": "shakalizator", "callback_data": "shakalizator", "style": "primary", "icon_custom_emoji_id": CUSTOM_EMOJI["location"]}
            ]
        ]
    }

def get_rules_accept_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "Правила", "callback_data": "show_rules", "style": "primary", "icon_custom_emoji_id": CUSTOM_EMOJI["rules_icon"]},
                {"text": "Ознакомлен/а", "callback_data": "accept_rules", "style": "success", "icon_custom_emoji_id": CUSTOM_EMOJI["check_mark"]}
            ]
        ]
    }

def get_back_keyboard(back_callback: str, button_text: str = "Назад"):
    return {
        "inline_keyboard": [
            [{"text": button_text, "callback_data": back_callback, "style": "primary", "icon_custom_emoji_id": CUSTOM_EMOJI["back"]}]
        ]
    }

def get_fix_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "исправить", "callback_data": "fix_account", "style": "success", "icon_custom_emoji_id": CUSTOM_EMOJI["unlock"]}]
        ]
    }

def get_cancel_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "Отмена", "callback_data": "cancel_shakalizator", "style": "danger", "icon_custom_emoji_id": CUSTOM_EMOJI["back"]}]
        ]
    }

def ce(emoji_id: str, fallback: str = "⬜") -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

def get_rules_text() -> str:
    return (
        f"{ce(CUSTOM_EMOJI['warning_gear'], '⚙️')}бот создан интарком!\n\n"
        f"{ce(CUSTOM_EMOJI['link_lock'], '🔗')}ваши данные полностью защищены\n"
        f"{ce(CUSTOM_EMOJI['check_mark'], '✅')}бот удаляет лишь запрещённых ботов нарушающих TOS\n"
        f"{ce(CUSTOM_EMOJI['info'], '👁')}не несём ответственность за ошибки"
    )

waiting_for_username = {}

def setup_handlers(dp: Dispatcher):
    router = Router()

    @router.message(Command("start"))
    async def cmd_start(message: Message):
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        
        if not user_exists(user_id):
            add_user(user_id, username, first_name)
        
        if not has_accepted_rules(user_id):
            send_sticker(user_id, "CAACAgUAAxkBAAEdK1Zp32yFklfyDRh3HdieDhLiYVyG6QACXhQAArP_iVVdQXtnlQYGRTsE")
            send_message(
                user_id,
                f"{ce(CUSTOM_EMOJI['rules_icon'], '❗️')} для продолжения вы должны знать правила бота!",
                reply_markup=get_rules_accept_keyboard()
            )
        else:
            send_message(
                user_id,
                f"{ce(CUSTOM_EMOJI['package'], '📦')}добро пожаловать в wiklsn, выберите функцию:",
                reply_markup=get_main_menu_keyboard()
            )

    @router.callback_query(F.data == "show_rules")
    async def show_rules(callback: CallbackQuery):
        edit_message(
            callback.message.chat.id,
            callback.message.message_id,
            get_rules_text(),
            reply_markup=get_back_keyboard("back_to_accept", "Назад")
        )
        answer_callback(callback.id)

    @router.callback_query(F.data == "back_to_accept")
    async def back_to_accept(callback: CallbackQuery):
        edit_message(
            callback.message.chat.id,
            callback.message.message_id,
            f"{ce(CUSTOM_EMOJI['rules_icon'], '❗️')} для продолжения вы должны знать правила бота!",
            reply_markup=get_rules_accept_keyboard()
        )
        answer_callback(callback.id)

    @router.callback_query(F.data == "accept_rules")
    async def accept_rules(callback: CallbackQuery):
        user_id = callback.from_user.id
        if not user_exists(user_id):
            add_user(user_id, callback.from_user.username, callback.from_user.first_name)
        
        edit_message(
            callback.message.chat.id,
            callback.message.message_id,
            f"{ce(CUSTOM_EMOJI['shield'], '🛡️')}внимание вы не найдены в системе!",
            reply_markup=get_fix_keyboard()
        )
        answer_callback(callback.id)

    @router.callback_query(F.data == "fix_account")
    async def fix_account(callback: CallbackQuery):
        user_id = callback.from_user.id
        accept_rules_db(user_id)
        
        edit_message(
            callback.message.chat.id,
            callback.message.message_id,
            f"{ce(CUSTOM_EMOJI['package'], '📦')}добро пожаловать в wiklsn, выберите функцию:",
            reply_markup=get_main_menu_keyboard()
        )
        answer_callback(callback.id)

    @router.callback_query(F.data == "show_rules_from_menu")
    async def show_rules_from_menu(callback: CallbackQuery):
        edit_message(
            callback.message.chat.id,
            callback.message.message_id,
            get_rules_text(),
            reply_markup=get_back_keyboard("back_to_main_menu", "Назад")
        )
        answer_callback(callback.id)

    @router.callback_query(F.data == "shakalizator")
    async def shakalizator(callback: CallbackQuery):
        user_id = callback.from_user.id
        waiting_for_username[user_id] = True
        
        edit_message(
            callback.message.chat.id,
            callback.message.message_id,
            f"{ce(CUSTOM_EMOJI['keyboard'], '⌨')}Введите юзернейм бота Sherlock",
            reply_markup=get_cancel_keyboard()
        )
        answer_callback(callback.id)

    @router.callback_query(F.data == "cancel_shakalizator")
    async def cancel_shakalizator(callback: CallbackQuery):
        user_id = callback.from_user.id
        if user_id in waiting_for_username:
            del waiting_for_username[user_id]
        
        edit_message(
            callback.message.chat.id,
            callback.message.message_id,
            f"{ce(CUSTOM_EMOJI['package'], '📦')}добро пожаловать в wiklsn, выберите функцию:",
            reply_markup=get_main_menu_keyboard()
        )
        answer_callback(callback.id)

    @router.message(F.text)
    async def handle_username_input(message: Message):
        user_id = message.from_user.id
        
        if user_id not in waiting_for_username:
            return
        
        del waiting_for_username[user_id]
        bot_username = message.text.strip()
        
        if bot_username.startswith("@"):
            bot_username = bot_username[1:]
        
        status_msg = send_message(
            user_id,
            f"{ce(CUSTOM_EMOJI['folder'], '📂')}цель: @{bot_username}\n🔄 Запуск...",
            parse_mode="HTML"
        )
        
        message_id = status_msg.get('result', {}).get('message_id')
        
        async def update_progress(progress_text):
            edit_message(
                user_id,
                message_id,
                f"{ce(CUSTOM_EMOJI['folder'], '📂')}цель: @{bot_username}\n{progress_text}",
                parse_mode="HTML"
            )
        
        results, success_count = await run_reports_on_all_sessions(bot_username, update_progress)
        total = len(results)
        
        final_text = f"{ce(CUSTOM_EMOJI['folder'], '📂')}цель: @{bot_username}\n{ce(CUSTOM_EMOJI['info_icon'], 'ℹ')}жалоб {success_count}/{total}"
        
        edit_message(
            user_id,
            message_id,
            final_text,
            parse_mode="HTML",
            reply_markup=get_back_keyboard("back_to_main_menu", "Назад")
        )

    @router.callback_query(F.data == "back_to_main_menu")
    async def back_to_main_menu(callback: CallbackQuery):
        edit_message(
            callback.message.chat.id,
            callback.message.message_id,
            f"{ce(CUSTOM_EMOJI['package'], '📦')}добро пожаловать в wiklsn, выберите функцию:",
            reply_markup=get_main_menu_keyboard()
        )
        answer_callback(callback.id)

    return router

async def main():
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("pyrogram").setLevel(logging.WARNING)
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    router = setup_handlers(dp)
    dp.include_router(router)
    
    sessions = get_session_files()
    print(f"📁 Найдено сессий в {SESSION_DIR}: {len(sessions)}")
    for s in sessions:
        session_file = os.path.join(SESSION_DIR, f"{s}.session")
        if os.path.exists(session_file):
            size = os.path.getsize(session_file)
            print(f"   - {s} ({size} байт)")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())