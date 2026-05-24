
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
API_TOKEN = '8989268578:AAGojXTDA3S-SxhveZ8wL1vqkmBodx2j0mc'
ADMIN_ID = 1753037099 

# Ссылка и Username канала (Бот должен быть админом в нем!)
CHANNEL_LINK = 'https://t.me/soundroid'
CHANNEL_USERNAME = '@soundroid' 

# Пути к фото приветствия для разных языков
START_PHOTO_RU = 'welcome.jpg'
START_PHOTO_EN = 'welcome2.png'

# Глобальный кэш для предотвращения дублирования сообщений
user_last_message = {}

# --- ЛОКАЛИЗАЦИЯ ---
TEXTS = {
    "ru": {
        "maintenance": "⚠️ Бот временно отключен на техническое обслуживание.",
        "select_lang": "🌍 Выберите язык / Select language:",
        "sub_required": "⚠️ Чтобы пользоваться ботом, подпишись на наш канал!",
        "sub_btn": "📢 Подписаться на канал",
        "check_sub_btn": "✅ Я подписался",
        "not_subbed": "❌ Вы еще не подписались на канал!",
        "welcome": (
            "Привет, {name}! 👋\n\n"
            "🔥 <b>Я твой музыкальный помощник!</b>\n"
            "Я помогу тебе найти лучший стафф для творчества. Вот что у меня есть:\n\n"
            "🎹 <b>Драм киты</b> — рассортированы по жанрам.\n"
            "🔌 <b>Плагины</b> — VST синтезаторы и эффекты.\n"
            "🎚 <b>DAW</b> — программы для написания музыки.\n\n"
            "Выбирай нужный раздел ниже и приступай! 👇\n\n"
            "🌍 Сменить язык: /eng"
        ),
        "drumkits": "🎹 Драм киты",
        "plugins": "🔌 Плагины",
        "daw": "🎚 DAW",
        "select_genre": "Выберите жанр драм-кита:",
        "category": "Категория:",
        "back": "⬅️ Назад",
        "main_menu": "🏠 Меню",
        "download_direct": "📥 Скачать напрямую",
        "sending_file": "Отправляю файл...",
        "empty": "Здесь пока ничего нет."
    },
    "en": {
        "maintenance": "⚠️ The bot is offline for maintenance.",
        "select_lang": "🌍 Выберите язык / Select language:",
        "sub_required": "⚠️ You must subscribe to our channel to use this bot!",
        "sub_btn": "📢 Subscribe to Channel",
        "check_sub_btn": "✅ I subscribed",
        "not_subbed": "❌ You haven't subscribed yet!",
        "welcome": (
            "Hello, {name}! 👋\n\n"
            "🔥 <b>I am your music assistant!</b>\n"
            "I will help you find the best stuff for your creativity.\n\n"
            "🎹 <b>Drumkits</b> | 🔌 <b>Plugins</b> | 🎚 <b>DAW</b>\n\n"
            "🌍 Change language: /eng"
        ),
        "drumkits": "🎹 Drumkits",
        "plugins": "🔌 Plugins",
        "daw": "🎚 DAW",
        "select_genre": "Choose genre:",
        "category": "Category:",
        "back": "⬅️ Back",
        "main_menu": "🏠 Menu",
        "download_direct": "📥 Download directly",
        "sending_file": "Sending file...",
        "empty": "Empty here."
    }
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
    
    # Таблица для динамических разделов (подкатегорий)
    cursor.execute('''CREATE TABLE IF NOT EXISTS subcategories 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, key TEXT UNIQUE, name_ru TEXT, name_en TEXT)''')
    
    # Заполнение дефолтных разделов для драм-китов, если таблица пуста
    default_drumkits = [
        ("drumkit", "brazil", "Brazil Funk 🇧🇷", "Brazil Funk 🇧🇷"),
        ("drumkit", "ambient", "Ambient ☁️", "Ambient ☁️"),
        ("drumkit", "phonk", "Phonk 💀", "Phonk 💀"),
        ("drumkit", "trap", "Trap ⚡", "Trap ⚡"),
        ("drumkit", "boombap", "Boom Bap 🥁", "Boom Bap 🥁")
    ]
    for dtype, dkey, dru, den in default_drumkits:
        cursor.execute("INSERT OR IGNORE INTO subcategories (type, key, name_ru, name_en) VALUES (?, ?, ?, ?)", 
                       (dtype, dkey, dru, den))
                       
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

# --- ПРОВЕРКА ПОДПИСКИ ---
async def is_subscribed(bot: Bot, user_id: int) -> bool:
    if user_id == ADMIN_ID: return True 
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['member', 'creator', 'administrator']
    except Exception as e:
        logging.error(f"ОШИБКА ПРОВЕРКИ ПОДПИСКИ: {e}")
        return False 

# --- СИСТЕМА ОДНОГО ОКНА ---
async def send_interface(bot: Bot, user_id: int, text: str, kb=None, photo=None):
    old_msg_id = user_last_message.get(user_id)
    if not old_msg_id:
        row = db_query("SELECT last_msg_id FROM users WHERE user_id = ?", (user_id,), fetchone=True)
        if row: old_msg_id = row[0]

    if old_msg_id:
        try: await bot.delete_message(user_id, old_msg_id)
        except: pass

    try:
        if photo:
            new_msg = await bot.send_photo(user_id, photo=photo, caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            new_msg = await bot.send_message(user_id, text=text, reply_markup=kb, parse_mode="HTML")
        
        user_last_message[user_id] = new_msg.message_id
        db_query("INSERT INTO users (user_id, last_msg_id) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_msg_id=?", (user_id, new_msg.message_id, new_msg.message_id))
    except Exception as e:
        logging.error(f"Ошибка интерфейса: {e}")

# --- MIDDLEWARE ---
class MainMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = event.from_user
        if not user: return await handler(event, data)

        # Команды админа
        if isinstance(event, types.Message) and event.text and event.text.startswith(("/admin", "/on", "/off")):
            return await handler(event, data)

        # 1. Технические работы
        status = db_query("SELECT value FROM settings WHERE key = 'bot_enabled'", fetchone=True)
        if status and status[0] == '0' and user.id != ADMIN_ID:
            msg = TEXTS["ru"]["maintenance"]
            await (event.answer(msg) if isinstance(event, types.Message) else event.answer(msg, show_alert=True))
            return

        # 2. Пропуск команд выбора языка
        is_lang_action = False
        if isinstance(event, types.Message) and event.text and (event.text.startswith("/start") or event.text.startswith("/eng")):
            is_lang_action = True
        elif isinstance(event, types.CallbackQuery) and event.data.startswith("setlang_"):
            is_lang_action = True

        if is_lang_action:
            return await handler(event, data)

        # 3. Проверка языка
        row = db_query("SELECT lang FROM users WHERE user_id = ?", (user.id,), fetchone=True)
        lang = row[0] if row else None

        if not lang:
            kb = InlineKeyboardBuilder()
            kb.row(types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru"),
                   types.InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en"))
            await send_interface(data['bot'], user.id, TEXTS["ru"]["select_lang"], kb.as_markup())
            return

        # 4. Проверка подписки
        if isinstance(event, types.CallbackQuery) and event.data == "check_sub":
            return await handler(event, data)

        if not await is_subscribed(data['bot'], user.id):
            kb = InlineKeyboardBuilder()
            kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["sub_btn"], url=CHANNEL_LINK))
            kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["check_sub_btn"], callback_data="check_sub"))
            await send_interface(data['bot'], user.id, TEXTS[lang]["sub_required"], kb.as_markup())
            return

        return await handler(event, data)

# --- ИНИЦИАЛИЗАЦИЯ ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
dp.message.outer_middleware(MainMiddleware())
dp.callback_query.outer_middleware(MainMiddleware())

# --- ХЕНДЛЕРЫ КЛИЕНТА ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (message.from_user.id,), fetchone=True)
    lang = row[0] if row else None
    if lang:
        if await is_subscribed(message.bot, message.from_user.id):
            await show_menu(message.from_user.id, lang)
        else:
            kb = InlineKeyboardBuilder()
            kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["sub_btn"], url=CHANNEL_LINK))
            kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["check_sub_btn"], callback_data="check_sub"))
            await send_interface(message.bot, message.from_user.id, TEXTS[lang]["sub_required"], kb.as_markup())
    else:
        kb = InlineKeyboardBuilder()
        kb.row(types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru"),
               types.InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en"))
        await send_interface(message.bot, message.from_user.id, TEXTS["ru"]["select_lang"], kb.as_markup())

@dp.message(Command("eng"))
async def cmd_eng(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru"),
           types.InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en"))
    await send_interface(message.bot, message.from_user.id, TEXTS["ru"]["select_lang"], kb.as_markup())

@dp.callback_query(F.data.startswith("setlang_"))
async def set_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    db_query("INSERT INTO users (user_id, lang) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET lang=?", (callback.from_user.id, lang, lang))
    await callback.answer()
    if await is_subscribed(callback.bot, callback.from_user.id):
        await show_menu(callback.from_user.id, lang)
    else:
        kb = InlineKeyboardBuilder()
        kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["sub_btn"], url=CHANNEL_LINK))
        kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["check_sub_btn"], callback_data="check_sub"))
        await send_interface(callback.bot, callback.from_user.id, TEXTS[lang]["sub_required"], kb.as_markup())

async def show_menu(user_id, lang):
    safe_name = html.escape((await bot.get_chat(user_id)).first_name)
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["drumkits"], callback_data="drumkit_genres"))
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["plugins"], callback_data="list_plugin_0"))
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["daw"], callback_data="daw_sections"))
    
    photo_path = START_PHOTO_RU if lang == "ru" else START_PHOTO_EN
    await send_interface(bot, user_id, TEXTS[lang]["welcome"].format(name=safe_name), kb.as_markup(), photo=FSInputFile(photo_path))

@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(callback: types.CallbackQuery):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (callback.from_user.id,), fetchone=True)
    lang = row[0] or "ru"
    if await is_subscribed(bot, callback.from_user.id):
        await callback.answer("✅")
        await show_menu(callback.from_user.id, lang)
    else:
        await callback.answer(TEXTS[lang]["not_subbed"], show_alert=True)

@dp.callback_query(F.data == "main_menu")
async def back_menu(callback: types.CallbackQuery):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (callback.from_user.id,), fetchone=True)
    await show_menu(callback.from_user.id, row[0] if row else "ru")

@dp.callback_query(F.data == "drumkit_genres")
async def drum_genres(callback: types.CallbackQuery):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (callback.from_user.id,), fetchone=True)
    lang = row[0] or "ru"
    sections = db_query("SELECT key, name_ru, name_en FROM subcategories WHERE type = 'drumkit'", fetchall=True)
    kb = InlineKeyboardBuilder()
    for key, name_ru, name_en in sections:
        name = name_ru if lang == "ru" else name_en
        kb.row(types.InlineKeyboardButton(text=name, callback_data=f"list_drumkit_{key}_0"))
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="main_menu"))
    
    photo_path = START_PHOTO_RU if lang == "ru" else START_PHOTO_EN
    await send_interface(bot, callback.from_user.id, TEXTS[lang]["select_genre"], kb.as_markup(), photo=FSInputFile(photo_path))

@dp.callback_query(F.data == "daw_sections")
async def daw_sections_cb(callback: types.CallbackQuery):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (callback.from_user.id,), fetchone=True)
    lang = row[0] or "ru"
    sections = db_query("SELECT key, name_ru, name_en FROM subcategories WHERE type = 'daw'", fetchall=True)
    kb = InlineKeyboardBuilder()
    
    if not sections:
        kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="main_menu"))
        photo_path = START_PHOTO_RU if lang == "ru" else START_PHOTO_EN
        await send_interface(bot, callback.from_user.id, TEXTS[lang]["empty"], kb.as_markup(), photo=FSInputFile(photo_path))
        return

    for key, name_ru, name_en in sections:
        name = name_ru if lang == "ru" else name_en
        kb.row(types.InlineKeyboardButton(text=name, callback_data=f"list_daw_{key}_0"))
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="main_menu"))
    
    photo_path = START_PHOTO_RU if lang == "ru" else START_PHOTO_EN
    title = "Выберите программу:" if lang == "ru" else "Choose DAW:"
    await send_interface(bot, callback.from_user.id, title, kb.as_markup(), photo=FSInputFile(photo_path))

@dp.callback_query(F.data.startswith("list_"))
async def list_items(callback: types.CallbackQuery):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (callback.from_user.id,), fetchone=True)
    lang = row[0] or "ru"
    data = callback.data.split("_")
    it_type, sub, pg = (data[1], data[2], int(data[3])) if len(data) == 4 else (data[1], None, int(data[2]))
    items = db_query(f"SELECT id, name FROM items WHERE type = ? {'AND subcategory = ?' if sub else ''}", (it_type, sub) if sub else (it_type,), fetchall=True)
    if not items: return await callback.answer(TEXTS[lang]["empty"], show_alert=True)
    await callback.answer(); kb = InlineKeyboardBuilder()
    for i_id, name in items[pg*7:(pg+1)*7]: kb.row(types.InlineKeyboardButton(text=name, callback_data=f"view_{i_id}_{pg}"))
    nav = []
    if pg > 0: nav.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"list_{it_type}_{f'{sub}_' if sub else ''}{pg-1}"))
    if (pg+1)*7 < len(items): nav.append(types.InlineKeyboardButton(text="➡️", callback_data=f"list_{it_type}_{f'{sub}_' if sub else ''}{pg+1}"))
    kb.row(*nav)
    
    back_target = "main_menu"
    if it_type == "drumkit":
        back_target = "drumkit_genres"
    elif it_type == "daw":
        back_target = "daw_sections"
        
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data=back_target))
    await send_interface(bot, callback.from_user.id, f"<b>Категория: {it_type}</b>", kb.as_markup())

@dp.callback_query(F.data.startswith("view_"))
async def view_item(callback: types.CallbackQuery):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (callback.from_user.id,), fetchone=True)
    lang = row[0] or "ru"
    _, i_id, pg = callback.data.split("_")
    item = db_query("SELECT name, link_google, link_yandex, file_id, description, photo_id, type, subcategory FROM items WHERE id = ?", (i_id,), fetchone=True)
    if not item: return
    await callback.answer(); name, gl, yx, fid, desc, pid, it_t, sub = item
    kb = InlineKeyboardBuilder()
    if fid: kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["download_direct"], callback_data=f"dl_{i_id}"))
    if gl: kb.row(types.InlineKeyboardButton(text="Google Drive", url=gl))
    if yx: kb.row(types.InlineKeyboardButton(text="Yandex Disk", url=yx))
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data=f"list_{it_t}_{f'{sub}_' if sub else ''}{pg}"))
    if callback.from_user.id == ADMIN_ID: kb.row(types.InlineKeyboardButton(text="🗑 Удалить (Admin)", callback_data=f"del_{i_id}"))
    await send_interface(bot, callback.from_user.id, f"<b>{name}</b>\n\n{desc}", kb.as_markup(), photo=pid)

@dp.callback_query(F.data.startswith("dl_"))
async def dl_file(callback: types.CallbackQuery):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (callback.from_user.id,), fetchone=True)
    f = db_query("SELECT file_id FROM items WHERE id = ?", (callback.data.split("_")[1],), fetchone=True)
    if f: await callback.answer(TEXTS[row[0] or "ru"]["sending_file"]); await bot.send_document(callback.from_user.id, f[0])

# --- АДМИН ПАНЕЛЬ ---
class AdminStates(StatesGroup):
    wait_name = State(); wait_file = State(); wait_google = State(); wait_yandex = State(); wait_desc = State(); wait_photo = State()
    wait_sub_type = State(); wait_sub_key = State(); wait_sub_name_ru = State(); wait_sub_name_en = State()

@dp.message(Command("off"))
async def turn_off(m: types.Message):
    if m.from_user.id == ADMIN_ID:
        db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('bot_enabled', '0')")
        await m.answer("🔴 Бот временно отключен на техническое обслуживание.")

@dp.message(Command("on"))
async def turn_on(m: types.Message):
    if m.from_user.id == ADMIN_ID:
        db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('bot_enabled', '1')")
        await m.answer("🟢 Бот успешно запущен и работает в штатном режиме.")

@dp.message(Command("admin"))
async def adm_panel(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🎹 + Драм кит", callback_data="add_drumkit"))
    kb.row(types.InlineKeyboardButton(text="🔌 + Плагин", callback_data="add_plugin"))
    kb.row(types.InlineKeyboardButton(text="🎚 + DAW", callback_data="add_daw"))
    kb.row(types.InlineKeyboardButton(text="📁 Управление разделами", callback_data="manage_sections"))
    await m.answer("Панель администратора:", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "admin_menu_back")
async def admin_menu_back(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🎹 + Драм кит", callback_data="add_drumkit"))
    kb.row(types.InlineKeyboardButton(text="🔌 + Плагин", callback_data="add_plugin"))
    kb.row(types.InlineKeyboardButton(text="🎚 + DAW", callback_data="add_daw"))
    kb.row(types.InlineKeyboardButton(text="📁 Управление разделами", callback_data="manage_sections"))
    await send_interface(bot, c.from_user.id, "Панель администратора:", kb.as_markup())

# --- Управление разделами (Подкатегориями) ---
@dp.callback_query(F.data == "manage_sections")
async def manage_sections(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="➕ Добавить раздел", callback_data="add_section_start"))
    kb.row(types.InlineKeyboardButton(text="🗑 Удалить раздел", callback_data="del_section_list"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_menu_back"))
    await send_interface(bot, c.from_user.id, "Управление разделами для Драм-китов и DAW:", kb.as_markup())

@dp.callback_query(F.data == "add_section_start")
async def add_section_start(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🎹 Драм кит", callback_data="set_sub_type_drumkit"))
    kb.row(types.InlineKeyboardButton(text="🎚 DAW", callback_data="set_sub_type_daw"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Отмена", callback_data="manage_sections"))
    await send_interface(bot, c.from_user.id, "Выберите тип раздела, который хотите создать:", kb.as_markup())

@dp.callback_query(F.data.startswith("set_sub_type_"))
async def set_sub_type(c: types.CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID: return
    sub_type = c.data.split("_")[3]
    await state.update_data(sub_type=sub_type)
    await c.message.answer("Введите уникальный ID (только маленькие латинские буквы без пробелов, например: phonk, logic, flstudio):")
    await state.set_state(AdminStates.wait_sub_key)

@dp.message(AdminStates.wait_sub_key)
async def wait_sub_key(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    key = m.text.strip().lower()
    if not key.isalnum():
        await m.answer("ID должен состоять только из букв и цифр. Попробуйте еще раз:")
        return
    await state.update_data(sub_key=key)
    await m.answer("Введите название раздела на русском (например: Phonk 💀 или Ableton Live 🎚):")
    await state.set_state(AdminStates.wait_sub_name_ru)

@dp.message(AdminStates.wait_sub_name_ru)
async def wait_sub_name_ru(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    await state.update_data(name_ru=m.text.strip())
    await m.answer("Введите название раздела на английском (например: Phonk 💀 или Ableton Live 🎚):")
    await state.set_state(AdminStates.wait_sub_name_en)

@dp.message(AdminStates.wait_sub_name_en)
async def wait_sub_name_en(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    name_en = m.text.strip()
    data = await state.get_data()
    db_query("INSERT INTO subcategories (type, key, name_ru, name_en) VALUES (?, ?, ?, ?)",
             (data['sub_type'], data['sub_key'], data['name_ru'], name_en))
    await m.answer("✅ Новый раздел успешно добавлен!")
    await state.clear()
    
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="📁 Управление разделами", callback_data="manage_sections"))
    await m.answer("Желаете продолжить?", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "del_section_list")
async def del_section_list(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    sections = db_query("SELECT id, type, name_ru FROM subcategories", fetchall=True)
    if not sections:
        return await c.answer("У вас еще нет созданных разделов!", show_alert=True)
    
    kb = InlineKeyboardBuilder()
    for s_id, s_type, name_ru in sections:
        category_label = "ДРАМ" if s_type == "drumkit" else "DAW"
        kb.row(types.InlineKeyboardButton(text=f"[{category_label}] {name_ru}", callback_data=f"del_sec_conf_{s_id}"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_sections"))
    await send_interface(bot, c.from_user.id, "Выберите раздел для удаления (внимание: файлы останутся в БД, но перестанут показываться пользователям):", kb.as_markup())

@dp.callback_query(F.data.startswith("del_sec_conf_"))
async def del_sec_conf(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    s_id = c.data.split("_")[3]
    db_query("DELETE FROM subcategories WHERE id = ?", (s_id,))
    await c.answer("Раздел удален!")
    await del_section_list(c)

# --- Добавление товара ---
@dp.callback_query(F.data.startswith("add_"))
async def add_start(c: types.CallbackQuery, state: FSMContext):
    t = c.data.split("_")[1]; await state.update_data(itype=t)
    if t in ["drumkit", "daw"]:
        sections = db_query("SELECT key, name_ru FROM subcategories WHERE type = ?", (t,), fetchall=True)
        if not sections:
            await c.answer("Сначала создайте хотя бы один подраздел в '📁 Управление разделами'!", show_alert=True)
            return
        kb = InlineKeyboardBuilder()
        for key, name_ru in sections:
            kb.row(types.InlineKeyboardButton(text=name_ru, callback_data=f"agenre_{key}"))
        await c.message.answer(f"Выберите подраздел для размещения ({t}):", reply_markup=kb.as_markup())
    else:
        await state.update_data(sub=None); await c.message.answer("Название:"); await state.set_state(AdminStates.wait_name)

@dp.callback_query(F.data.startswith("agenre_"))
async def add_genre(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(sub=c.data.split("_")[1]); await c.message.answer("Название:"); await state.set_state(AdminStates.wait_name)

@dp.message(AdminStates.wait_name)
async def adm_name(m: types.Message, state: FSMContext):
    await state.update_data(name=m.text); await m.answer("Файл или /skip:"); await state.set_state(AdminStates.wait_file)

@dp.message(AdminStates.wait_file)
async def adm_file(m: types.Message, state: FSMContext):
    await state.update_data(fid=m.document.file_id if m.document else None); await m.answer("Google или /skip:"); await state.set_state(AdminStates.wait_google)

@dp.message(AdminStates.wait_google)
async def adm_google(m: types.Message, state: FSMContext):
    await state.update_data(gl=None if m.text=="/skip" else m.text); await m.answer("Yandex или /skip:"); await state.set_state(AdminStates.wait_yandex)

@dp.message(AdminStates.wait_yandex)
async def adm_yandex(m: types.Message, state: FSMContext):
    await state.update_data(yx=None if m.text=="/skip" else m.text); await m.answer("Описание:"); await state.set_state(AdminStates.wait_desc)

@dp.message(AdminStates.wait_desc)
async def adm_desc(m: types.Message, state: FSMContext):
    await state.update_data(desc=m.text); await m.answer("Фото или /skip:"); await state.set_state(AdminStates.wait_photo)

@dp.message(AdminStates.wait_photo)
async def adm_photo(m: types.Message, state: FSMContext):
    d = await state.get_data(); pid = m.photo[-1].file_id if m.photo else None
    db_query("INSERT INTO items (name, link_google, link_yandex, file_id, type, description, photo_id, subcategory) VALUES (?,?,?,?,?,?,?,?)",
             (d['name'], d['gl'], d['yx'], d['fid'], d['itype'], d['desc'], pid, d['sub']))
    await m.answer("✅ Добавлено!"); await state.clear()

@dp.callback_query(F.data.startswith("del_"))
async def adm_del(c: types.CallbackQuery):
    db_query("DELETE FROM items WHERE id = ?", (c.data.split("_")[1],)); await c.answer("Удалено"); await back_menu(c)

# --- ЗАПУСК ---
async def main():
    init_db()
    
    # Меню команд для пользователей (без /menu)
    await bot.set_my_commands([
        types.BotCommand(command="start", description="Запуск бота"),
        types.BotCommand(command="eng", description="Language / Сменить язык")
    ])
    
    # Меню команд для админа (без /menu)
    try:
        await bot.set_my_commands(
            commands=[
                types.BotCommand(command="start", description="Запуск бота"),
                types.BotCommand(command="eng", description="Language / Сменить язык"),
                types.BotCommand(command="admin", description="Админ панель"),
                types.BotCommand(command="on", description="Включить бота"),
                types.BotCommand(command="off", description="Отключить бота")
            ],
            scope=types.BotCommandScopeChat(chat_id=ADMIN_ID)
        )
    except: pass

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
