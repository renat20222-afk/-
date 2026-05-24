
import asyncio
import sqlite3
import logging
import html
from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile

# --- НАСТРОЙКИ ---
API_TOKEN = '8989268578:AAEEnVwlFoqQ1rjsxyO8dXLQMLTO3tXfloc'
ADMIN_ID = 1753037099 

# Данные канала
CHANNEL_LINK = 'https://t.me/soundroid'
CHANNEL_ID = -1001552554703 

# Путь к фото приветствия
START_PHOTO_PATH = 'welcome.jpg'

# Глобальный кэш для предотвращения багов с дублированием сообщений
user_last_message = {}

# --- ЛОКАЛИЗАЦИЯ ---
TEXTS = {
    "ru": {
        "maintenance": "⚠️ Бот на техническом обслуживании.",
        "select_lang": "🌍 Выберите язык / Select language:",
        "sub_required": "⚠️ Чтобы пользоваться ботом, подпишись на наш канал!",
        "sub_btn": "📢 Подписаться на канал",
        "check_sub_btn": "✅ Я подписался",
        "not_subbed": "❌ Вы еще не подписались на канал!",
        "welcome": (
            "Привет, {name}! 👋\n\n"
            "🔥 <b>Я твой музыкальный помощник!</b>\n"
            "Я помогу тебе найти лучший стафф для творчества.\n\n"
            "🎹 <b>Драм киты</b> — по жанрам.\n"
            "🔌 <b>Плагины</b> — VST софт.\n"
            "🎚 <b>DAW</b> — программы.\n\n"
            "🌍 Сменить язык: /eng"
        ),
        "drumkits": "🎹 Драм киты",
        "plugins": "🔌 Плагины",
        "daw": "🎚 DAW",
        "select_genre": "Выберите жанр драм-кита:",
        "category": "Категория:",
        "back": "⬅️ Назад",
        "main_menu": "🏠 Меню",
        "download_direct": "📥 Скачать файл",
        "sending_file": "Отправляю файл, подождите...",
        "empty": "В этом разделе пока пусто."
    },
    "en": {
        "maintenance": "⚠️ Maintenance mode.",
        "select_lang": "🌍 Select language / Выберите язык:",
        "sub_required": "⚠️ Please subscribe to our channel to use the bot!",
        "sub_btn": "📢 Subscribe to Channel",
        "check_sub_btn": "✅ I subscribed",
        "not_subbed": "❌ You are not subscribed yet!",
        "welcome": (
            "Hello, {name}! 👋\n\n"
            "🔥 <b>I am your music assistant!</b>\n"
            "I'll help you find the best music production gear.\n\n"
            "🎹 <b>Drumkits</b> — by genres.\n"
            "🔌 <b>Plugins</b> — VST software.\n"
            "🎚 <b>DAW</b> — workstations.\n\n"
            "🌍 Change language: /eng"
        ),
        "drumkits": "🎹 Drumkits",
        "plugins": "🔌 Plugins",
        "daw": "🎚 DAW",
        "select_genre": "Choose drumkit genre:",
        "category": "Category:",
        "back": "⬅️ Back",
        "main_menu": "🏠 Menu",
        "download_direct": "📥 Download file",
        "sending_file": "Sending file, please wait...",
        "empty": "This section is empty for now."
    }
}

DRUMKIT_GENRES = {
    "brazil": {"ru": "Brazil Funk 🇧🇷", "en": "Brazil Funk 🇧🇷"},
    "ambient": {"ru": "Ambient ☁️", "en": "Ambient ☁️"},
    "phonk": {"ru": "Phonk 💀", "en": "Phonk 💀"},
    "trap": {"ru": "Trap ⚡", "en": "Trap ⚡"},
    "boombap": {"ru": "Boom Bap 🥁", "en": "Boom Bap 🥁"},
    "other": {"ru": "Другое 📦", "en": "Other 📦"}
}

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS items 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, link_google TEXT, 
                       link_yandex TEXT, file_id TEXT, type TEXT, description TEXT, 
                       photo_id TEXT, subcategory TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, lang TEXT, last_msg_id INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('bot_enabled', '1')")
    conn.commit()
    conn.close()

def db_query(query, params=(), fetchone=False, fetchall=False):
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute(query, params)
    res = None
    if fetchone: res = cursor.fetchone()
    elif fetchall: res = cursor.fetchall()
    conn.commit()
    conn.close()
    return res

# --- СИСТЕМА ОДНОГО ОКНА (УДАЛЕНИЕ СТАРЫХ СООБЩЕНИЙ) ---
async def send_interface(bot: Bot, user_id: int, text: str, kb=None, photo=None):
    # Пытаемся достать ID старого сообщения из памяти
    old_msg_id = user_last_message.get(user_id)
    if not old_msg_id:
        row = db_query("SELECT last_msg_id FROM users WHERE user_id = ?", (user_id,), fetchone=True)
        if row: old_msg_id = row[0]

    # Удаляем старое сообщение бота
    if old_msg_id:
        try: await bot.delete_message(user_id, old_msg_id)
        except: pass

    # Отправляем новое сообщение
    try:
        if photo:
            new_msg = await bot.send_photo(user_id, photo=photo, caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            new_msg = await bot.send_message(user_id, text=text, reply_markup=kb, parse_mode="HTML")
        
        # Сохраняем новый ID
        user_last_message[user_id] = new_msg.message_id
        db_query("INSERT INTO users (user_id, last_msg_id) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_msg_id=?", (user_id, new_msg.message_id, new_msg.message_id))
    except Exception as e:
        logging.error(f"Error sending message: {e}")

# --- MIDDLEWARE ---
class MainMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = event.from_user
        if not user: return await handler(event, data)

        # 1. Удаляем команду пользователя (чистим чат)
        if isinstance(event, types.Message):
            try: await event.delete()
            except: pass

        if user.id == ADMIN_ID: return await handler(event, data)

        # 2. Проверка тех. работ
        status = db_query("SELECT value FROM settings WHERE key = 'bot_enabled'", fetchone=True)
        if status and status[0] == '0':
            await event.answer(TEXTS["ru"]["maintenance"]) if isinstance(event, types.Message) else await event.answer(TEXTS["ru"]["maintenance"], show_alert=True)
            return

        # 3. Проверка языка
        row = db_query("SELECT lang FROM users WHERE user_id = ?", (user.id,), fetchone=True)
        lang = row[0] if row else None

        # Разрешаем выбор языка
        if isinstance(event, types.Message) and event.text and (event.text.startswith("/start") or event.text.startswith("/eng")):
            return await handler(event, data)
        if isinstance(event, types.CallbackQuery) and event.data.startswith("setlang_"):
            return await handler(event, data)

        if not lang:
            kb = InlineKeyboardBuilder()
            kb.row(types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru"),
                   types.InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en"))
            await send_interface(data['bot'], user.id, TEXTS["ru"]["select_lang"], kb.as_markup())
            return

        # 4. Проверка подписки (кроме кнопок подписки)
        if isinstance(event, types.CallbackQuery) and event.data == "check_sub":
            return await handler(event, data)

        try:
            m = await data['bot'].get_chat_member(CHANNEL_ID, user.id)
            if m.status not in ['member', 'creator', 'administrator']:
                kb = InlineKeyboardBuilder()
                kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["sub_btn"], url=CHANNEL_LINK))
                kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["check_sub_btn"], callback_data="check_sub"))
                await send_interface(data['bot'], user.id, TEXTS[lang]["sub_required"], kb.as_markup())
                return
        except: pass

        return await handler(event, data)

# --- ХЕНДЛЕРЫ ---

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
dp.message.outer_middleware(MainMiddleware())
dp.callback_query.outer_middleware(MainMiddleware())

@dp.message(Command("start", "eng"))
async def cmd_lang(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru"),
           types.InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en"))
    await send_interface(message.bot, message.from_user.id, TEXTS["ru"]["select_lang"], kb.as_markup())

@dp.callback_query(F.data.startswith("setlang_"))
async def set_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    db_query("INSERT INTO users (user_id, lang) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET lang=?", (callback.from_user.id, lang, lang))
    await callback.answer()
    await show_menu(callback.from_user.id, lang)

async def show_menu(user_id, lang):
    safe_name = html.escape((await bot.get_chat(user_id)).first_name)
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["drumkits"], callback_data="drumkit_genres"))
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["plugins"], callback_data="list_plugin_0"))
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["daw"], callback_data="list_daw_0"))
    await send_interface(bot, user_id, TEXTS[lang]["welcome"].format(name=safe_name), kb.as_markup(), photo=FSInputFile(START_PHOTO_PATH))

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (message.from_user.id,), fetchone=True)
    await show_menu(message.from_user.id, row[0] if row else "ru")

@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(callback: types.CallbackQuery):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (callback.from_user.id,), fetchone=True)
    lang = row[0] if row else "ru"
    try:
        m = await bot.get_chat_member(CHANNEL_ID, callback.from_user.id)
        if m.status in ['member', 'creator', 'administrator']:
            await callback.answer("✅")
            await show_menu(callback.from_user.id, lang)
        else:
            await callback.answer(TEXTS[lang]["not_subbed"], show_alert=True)
    except:
        await show_menu(callback.from_user.id, lang)

@dp.callback_query(F.data == "main_menu")
async def back_menu(callback: types.CallbackQuery):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (callback.from_user.id,), fetchone=True)
    await show_menu(callback.from_user.id, row[0] if row else "ru")

@dp.callback_query(F.data == "drumkit_genres")
async def drum_genres(callback: types.CallbackQuery):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (callback.from_user.id,), fetchone=True)
    lang = row[0] or "ru"
    kb = InlineKeyboardBuilder()
    for k, v in DRUMKIT_GENRES.items():
        kb.row(types.InlineKeyboardButton(text=v[lang], callback_data=f"list_drumkit_{k}_0"))
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="main_menu"))
    await send_interface(bot, callback.from_user.id, TEXTS[lang]["select_genre"], kb.as_markup(), photo=FSInputFile(START_PHOTO_PATH))

@dp.callback_query(F.data.startswith("list_"))
async def list_items(callback: types.CallbackQuery):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (callback.from_user.id,), fetchone=True)
    lang = row[0] or "ru"
    data = callback.data.split("_")
    it_type, sub, pg = (data[1], data[2], int(data[3])) if len(data) == 4 else (data[1], None, int(data[2]))
    
    query = "SELECT id, name FROM items WHERE type = ?"
    params = (it_type,)
    if sub:
        query += " AND subcategory = ?"
        params = (it_type, sub)
    
    items = db_query(query, params, fetchall=True)
    if not items:
        await callback.answer(TEXTS[lang]["empty"], show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    for i_id, name in items[pg*7 : (pg+1)*7]:
        kb.row(types.InlineKeyboardButton(text=name, callback_data=f"view_{i_id}_{pg}"))
    
    nav = []
    if pg > 0: nav.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"list_{it_type}_{f'{sub}_' if sub else ''}{pg-1}"))
    if (pg+1)*7 < len(items): nav.append(types.InlineKeyboardButton(text="➡️", callback_data=f"list_{it_type}_{f'{sub}_' if sub else ''}{pg+1}"))
    kb.row(*nav)
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="drumkit_genres" if it_type=="drumkit" else "main_menu"))
    
    title = DRUMKIT_GENRES[sub][lang] if sub else it_type.upper()
    await send_interface(bot, callback.from_user.id, f"<b>{title}</b>", kb.as_markup())

@dp.callback_query(F.data.startswith("view_"))
async def view_item(callback: types.CallbackQuery):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (callback.from_user.id,), fetchone=True)
    lang = row[0] or "ru"
    _, i_id, pg = callback.data.split("_")
    item = db_query("SELECT name, link_google, link_yandex, file_id, description, photo_id, type, subcategory FROM items WHERE id = ?", (i_id,), fetchone=True)
    if not item: return

    name, gl, yx, fid, desc, pid, it_t, sub = item
    kb = InlineKeyboardBuilder()
    if fid: kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["download_direct"], callback_data=f"dl_{i_id}"))
    if gl: kb.row(types.InlineKeyboardButton(text="Google Drive", url=gl))
    if yx: kb.row(types.InlineKeyboardButton(text="Yandex Disk", url=yx))
    
    back_data = f"list_{it_t}_{f'{sub}_' if sub else ''}{pg}"
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data=back_data))
    
    if callback.from_user.id == ADMIN_ID:
        kb.row(types.InlineKeyboardButton(text="🗑 Удалить (Admin)", callback_data=f"del_{i_id}"))

    text = f"<b>{name}</b>\n\n{desc}"
    await send_interface(bot, callback.from_user.id, text, kb.as_markup(), photo=pid if pid else None)

@dp.callback_query(F.data.startswith("dl_"))
async def download_file(callback: types.CallbackQuery):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (callback.from_user.id,), fetchone=True)
    lang = row[0] or "ru"
    item = db_query("SELECT file_id FROM items WHERE id = ?", (callback.data.split("_")[1],), fetchone=True)
    if item and item[0]:
        await callback.answer(TEXTS[lang]["sending_file"])
        await bot.send_document(callback.from_user.id, item[0])

# --- АДМИН ПАНЕЛЬ ---

class AdminStates(StatesGroup):
    wait_name = State()
    wait_file = State()
    wait_google = State()
    wait_yandex = State()
    wait_desc = State()
    wait_photo = State()

@dp.message(Command("admin"))
async def adm_panel(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🎹 + Драм кит", callback_data="add_drumkit"))
    kb.row(types.InlineKeyboardButton(text="🔌 + Плагин", callback_data="add_plugin"))
    kb.row(types.InlineKeyboardButton(text="🎚 + DAW", callback_data="add_daw"))
    await m.answer("Панель управления:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("add_"))
async def add_start(c: types.CallbackQuery, state: FSMContext):
    t = c.data.split("_")[1]
    await state.update_data(itype=t)
    if t == "drumkit":
        kb = InlineKeyboardBuilder()
        for k,v in DRUMKIT_GENRES.items(): kb.row(types.InlineKeyboardButton(text=v["ru"], callback_data=f"agenre_{k}"))
        await c.message.answer("Выберите жанр:", reply_markup=kb.as_markup())
    else:
        await state.update_data(sub=None)
        await c.message.answer("Введите название:")
        await state.set_state(AdminStates.wait_name)

@dp.callback_query(F.data.startswith("agenre_"))
async def add_genre(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(sub=c.data.split("_")[1])
    await c.message.answer("Введите название:")
    await state.set_state(AdminStates.wait_name)

@dp.message(AdminStates.wait_name)
async def adm_name(m: types.Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("Отправьте файл (как документ) или /skip:")
    await state.set_state(AdminStates.wait_file)

@dp.message(AdminStates.wait_file)
async def adm_file(m: types.Message, state: FSMContext):
    fid = m.document.file_id if m.document else None
    await state.update_data(fid=fid)
    await m.answer("Ссылка Google Drive или /skip:")
    await state.set_state(AdminStates.wait_google)

@dp.message(AdminStates.wait_google)
async def adm_google(m: types.Message, state: FSMContext):
    await state.update_data(gl=None if m.text=="/skip" else m.text)
    await m.answer("Ссылка Yandex Disk или /skip:")
    await state.set_state(AdminStates.wait_yandex)

@dp.message(AdminStates.wait_yandex)
async def adm_yandex(m: types.Message, state: FSMContext):
    await state.update_data(yx=None if m.text=="/skip" else m.text)
    await m.answer("Введите описание:")
    await state.set_state(AdminStates.wait_desc)

@dp.message(AdminStates.wait_desc)
async def adm_desc(m: types.Message, state: FSMContext):
    await state.update_data(desc=m.text)
    await m.answer("Отправьте фото или /skip:")
    await state.set_state(AdminStates.wait_photo)

@dp.message(AdminStates.wait_photo)
async def adm_photo(m: types.Message, state: FSMContext):
    pid = m.photo[-1].file_id if m.photo else None
    d = await state.get_data()
    db_query("INSERT INTO items (name, link_google, link_yandex, file_id, type, description, photo_id, subcategory) VALUES (?,?,?,?,?,?,?,?)",
             (d['name'], d['gl'], d['yx'], d['fid'], d['itype'], d['desc'], pid, d['sub']))
    await m.answer("✅ Добавлено!")
    await state.clear()

@dp.callback_query(F.data.startswith("del_"))
async def adm_del(c: types.CallbackQuery):
    db_query("DELETE FROM items WHERE id = ?", (c.data.split("_")[1],))
    await c.answer("Удалено")
    await back_menu(c)

# --- ЗАПУСК ---
async def main():
    init_db()
    await bot.set_my_commands([
        types.BotCommand(command="start", description="Запуск"),
        types.BotCommand(command="menu", description="Главное меню"),
        types.BotCommand(command="eng", description="Change language / Сменить язык"),
        types.BotCommand(command="admin", description="Админ панель")
    ])
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
