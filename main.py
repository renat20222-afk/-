
import asyncio
import sqlite3
import logging
import html
import os
from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile

# --- НАСТРОЙКИ ---
API_TOKEN = '8989268578:AAGojXTDA3S-SxhveZ8wL1vqkmBodx2j0mc'
ADMIN_ID = 1753037099 
CHANNEL_LINK = 'https://t.me/soundroid'
CHANNEL_USERNAME = '@soundroid' 

START_PHOTO_RU = 'welcome.jpg'
START_PHOTO_EN = 'welcome2.png'

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
        "select_genre": "Какой жанр драм-кита вы хотите скачать? 👇",
        "select_daw": "Какую программу (DAW) вы хотите скачать? 👇",
        "back": "⬅️ Назад",
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
        "select_genre": "Which genre of drum kit do you want to download? 👇",
        "select_daw": "Which DAW (program) do you want to download? 👇",
        "back": "⬅️ Back",
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
                      (user_id INTEGER PRIMARY KEY, lang TEXT, welcome_id INTEGER, sub_id INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('bot_enabled', '1')")
    cursor.execute('''CREATE TABLE IF NOT EXISTS subcategories 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, key TEXT UNIQUE, name_ru TEXT, name_en TEXT)''')
    
    # Дефолтные разделы, если их нет
    defaults = [
        ("drumkit", "brazil", "Brazil Funk 🇧🇷", "Brazil Funk 🇧🇷"),
        ("drumkit", "ambient", "Ambient ☁️", "Ambient ☁️"),
        ("drumkit", "phonk", "Phonk 💀", "Phonk 💀")
    ]
    for t, k, ru, en in defaults:
        cursor.execute("INSERT OR IGNORE INTO subcategories (type, key, name_ru, name_en) VALUES (?,?,?,?)", (t, k, ru, en))
    
    # Безопасное обновление структуры старой БД (если столбцов не было)
    try: cursor.execute("ALTER TABLE users ADD COLUMN welcome_id INTEGER")
    except: pass
    try: cursor.execute("ALTER TABLE users ADD COLUMN sub_id INTEGER")
    except: pass
    
    conn.commit()
    conn.close()

def db_query(query, params=(), fetchone=False, fetchall=False):
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute(query, params)
    res = cursor.fetchone() if fetchone else cursor.fetchall() if fetchall else None
    conn.commit()
    conn.close()
    return res

async def is_subscribed(bot: Bot, user_id: int) -> bool:
    if user_id == ADMIN_ID: return True 
    try:
        m = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return m.status in ['member', 'creator', 'administrator']
    except: return False 

# --- УПРАВЛЕНИЕ ОКНАМИ (ПРИВЕТСТВИЕ СВЕРХУ, МЕНЮ СНИЗУ) ---
async def send_welcome_msg(bot: Bot, user_id: int, text: str, kb=None, photo_path=None, user_msg_id=None):
    if user_msg_id:
        try: await bot.delete_message(user_id, user_msg_id)
        except: pass
        
    row = db_query("SELECT welcome_id, sub_id FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if row:
        w_id, s_id = row
        if w_id: 
            try: await bot.delete_message(user_id, w_id)
            except: pass
        if s_id:
            try: await bot.delete_message(user_id, s_id)
            except: pass

    if photo_path and os.path.exists(photo_path):
        msg = await bot.send_photo(user_id, photo=FSInputFile(photo_path), caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        msg = await bot.send_message(user_id, text=text, reply_markup=kb, parse_mode="HTML")
    
    db_query("INSERT INTO users (user_id, welcome_id, sub_id) VALUES (?, ?, NULL) ON CONFLICT(user_id) DO UPDATE SET welcome_id=?", (user_id, msg.message_id, msg.message_id))

async def send_sub_msg(bot: Bot, user_id: int, text: str, kb=None, photo_id=None):
    row = db_query("SELECT sub_id FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if row and row[0]:
        try: await bot.delete_message(user_id, row[0])
        except: pass

    if photo_id:
        msg = await bot.send_photo(user_id, photo=photo_id, caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        msg = await bot.send_message(user_id, text=text, reply_markup=kb, parse_mode="HTML")
    
    db_query("UPDATE users SET sub_id = ? WHERE user_id = ?", (msg.message_id, user_id))

# --- MIDDLEWARE (СТРОГАЯ ПРОВЕРКА ПОДПИСКИ) ---
class MainMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = event.from_user
        if not user: return await handler(event, data)
        if isinstance(event, types.Message) and event.text and event.text.startswith(("/admin", "/on", "/off")):
            return await handler(event, data)

        status = db_query("SELECT value FROM settings WHERE key = 'bot_enabled'", fetchone=True)
        if status and status[0] == '0' and user.id != ADMIN_ID:
            return

        row = db_query("SELECT lang FROM users WHERE user_id = ?", (user.id,), fetchone=True)
        lang = row[0] if row else None

        is_start_or_eng = isinstance(event, types.Message) and event.text in ["/start", "/eng"]
        is_setlang = isinstance(event, types.CallbackQuery) and event.data.startswith("setlang_")

        # 1. Если язык еще не выбран, принудительно даем его выбрать
        if not lang:
            if is_start_or_eng or is_setlang:
                return await handler(event, data)
            kb = InlineKeyboardBuilder()
            kb.row(types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru"),
                   types.InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en"))
            await send_welcome_msg(data['bot'], user.id, TEXTS["ru"]["select_lang"], kb.as_markup())
            return

        # 2. Если язык выбран, проверяем подписку
        is_subbed = await is_subscribed(data['bot'], user.id)
        is_checking_sub = isinstance(event, types.CallbackQuery) and event.data == "check_sub"

        # Если не подписан и это не проверка подписки
        if not is_subbed and not is_checking_sub:
            kb = InlineKeyboardBuilder()
            kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["sub_btn"], url=CHANNEL_LINK))
            kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["check_sub_btn"], callback_data="check_sub"))
            
            # Если юзер отправил команду (например, /start), удаляем ее сообщение и шлем требование подписки
            user_msg_id = event.message_id if isinstance(event, types.Message) else None
            await send_welcome_msg(data['bot'], user.id, TEXTS[lang]["sub_required"], kb.as_markup(), user_msg_id=user_msg_id)
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
async def cmd_start(m: types.Message):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (m.from_user.id,), fetchone=True)
    lang = row[0] if row else None
    if not lang:
        kb = InlineKeyboardBuilder()
        kb.row(types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru"),
               types.InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en"))
        await send_welcome_msg(bot, m.from_user.id, TEXTS["ru"]["select_lang"], kb.as_markup(), user_msg_id=m.message_id)
    else:
        await show_main_menu(m.from_user.id, lang, m.message_id)

@dp.message(Command("eng"))
async def cmd_eng(m: types.Message):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru"),
           types.InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en"))
    await send_welcome_msg(bot, m.from_user.id, TEXTS["ru"]["select_lang"], kb.as_markup(), user_msg_id=m.message_id)

@dp.callback_query(F.data.startswith("setlang_"))
async def set_lang(c: types.CallbackQuery):
    lang = c.data.split("_")[1]
    db_query("INSERT INTO users (user_id, lang) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET lang=?", (c.from_user.id, lang, lang))
    
    # Сразу после выбора языка проверяем подписку
    if await is_subscribed(bot, c.from_user.id):
        await show_main_menu(c.from_user.id, lang)
    else:
        kb = InlineKeyboardBuilder()
        kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["sub_btn"], url=CHANNEL_LINK))
        kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["check_sub_btn"], callback_data="check_sub"))
        await send_welcome_msg(bot, c.from_user.id, TEXTS[lang]["sub_required"], kb.as_markup())

async def show_main_menu(user_id, lang, user_msg_id=None):
    safe_name = html.escape((await bot.get_chat(user_id)).first_name or "User")
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["drumkits"], callback_data="cat_drumkit"))
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["plugins"], callback_data="list_plugin_0"))
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["daw"], callback_data="cat_daw"))
    photo = START_PHOTO_RU if lang == "ru" else START_PHOTO_EN
    await send_welcome_msg(bot, user_id, TEXTS[lang]["welcome"].format(name=safe_name), kb.as_markup(), photo, user_msg_id)

@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(c: types.CallbackQuery):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (c.from_user.id,), fetchone=True)
    lang = row[0] if row else "ru"
    if await is_subscribed(bot, c.from_user.id):
        await c.answer("✅")
        await show_main_menu(c.from_user.id, lang)
    else:
        await c.answer(TEXTS[lang]["not_subbed"], show_alert=True)

@dp.callback_query(F.data.startswith("cat_"))
async def show_category(c: types.CallbackQuery):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (c.from_user.id,), fetchone=True)
    lang = row[0] if row else "ru"
    ctype = c.data.split("_")[1]
    sections = db_query("SELECT key, name_ru, name_en FROM subcategories WHERE type = ?", (ctype,), fetchall=True)
    kb = InlineKeyboardBuilder()
    for k, ru, en in sections:
        kb.row(types.InlineKeyboardButton(text=ru if lang=="ru" else en, callback_data=f"list_{ctype}_{k}_0"))
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="close_sub"))
    
    prompt_text = TEXTS[lang]["select_genre"] if ctype == "drumkit" else TEXTS[lang]["select_daw"]
    await send_sub_msg(bot, c.from_user.id, prompt_text, kb.as_markup())
    await c.answer()

@dp.callback_query(F.data == "close_sub")
async def close_sub(c: types.CallbackQuery):
    row = db_query("SELECT sub_id FROM users WHERE user_id = ?", (c.from_user.id,), fetchone=True)
    if row and row[0]:
        try: await bot.delete_message(c.from_user.id, row[0])
        except: pass
        db_query("UPDATE users SET sub_id = NULL WHERE user_id = ?", (c.from_user.id,))
    await c.answer()

@dp.callback_query(F.data.startswith("list_"))
async def list_items(c: types.CallbackQuery):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (c.from_user.id,), fetchone=True)
    lang = row[0] if row else "ru"
    data = c.data.split("_")
    it_type, sub, pg = (data[1], data[2], int(data[3])) if len(data) == 4 else (data[1], None, int(data[2]))
    items = db_query(f"SELECT id, name FROM items WHERE type = ? {'AND subcategory = ?' if sub else ''}", (it_type, sub) if sub else (it_type,), fetchall=True)
    
    if not items: return await c.answer(TEXTS[lang]["empty"], show_alert=True)
    
    kb = InlineKeyboardBuilder()
    for i_id, name in items[pg*7:(pg+1)*7]:
        kb.row(types.InlineKeyboardButton(text=name, callback_data=f"view_{i_id}_{pg}"))
    
    nav = []
    if pg > 0: nav.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"list_{it_type}_{f'{sub}_' if sub else ''}{pg-1}"))
    if (pg+1)*7 < len(items): nav.append(types.InlineKeyboardButton(text="➡️", callback_data=f"list_{it_type}_{f'{sub}_' if sub else ''}{pg+1}"))
    kb.row(*nav)
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data=f"cat_{it_type}" if it_type in ["drumkit", "daw"] else "close_sub"))
    
    type_label = TEXTS[lang]["drumkits"] if it_type == "drumkit" else TEXTS[lang]["plugins"] if it_type == "plugin" else TEXTS[lang]["daw"]
    await send_sub_msg(bot, c.from_user.id, f"<b>Категория: {type_label}</b>", kb.as_markup())
    await c.answer()

@dp.callback_query(F.data.startswith("view_"))
async def view_item(c: types.CallbackQuery):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (c.from_user.id,), fetchone=True)
    lang = row[0] if row else "ru"
    _, i_id, pg = c.data.split("_")
    item = db_query("SELECT name, link_google, link_yandex, file_id, description, photo_id, type, subcategory FROM items WHERE id = ?", (i_id,), fetchone=True)
    if not item: return
    name, gl, yx, fid, desc, pid, it_t, sub = item
    kb = InlineKeyboardBuilder()
    if fid: kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["download_direct"], callback_data=f"dl_{i_id}"))
    if gl: kb.row(types.InlineKeyboardButton(text="Google Drive", url=gl))
    if yx: kb.row(types.InlineKeyboardButton(text="Yandex Disk", url=yx))
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data=f"list_{it_t}_{f'{sub}_' if sub else ''}{pg}"))
    if c.from_user.id == ADMIN_ID: kb.row(types.InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_{i_id}"))
    
    await send_sub_msg(bot, c.from_user.id, f"<b>{name}</b>\n\n{desc}", kb.as_markup(), photo_id=pid)
    await c.answer()

@dp.callback_query(F.data.startswith("dl_"))
async def dl_file(c: types.CallbackQuery):
    row = db_query("SELECT lang FROM users WHERE user_id = ?", (c.from_user.id,), fetchone=True)
    lang = row[0] if row else "ru"
    f = db_query("SELECT file_id FROM items WHERE id = ?", (c.data.split("_")[1],), fetchone=True)
    if f: await c.answer(TEXTS[lang]["sending_file"]); await bot.send_document(c.from_user.id, f[0])

# --- АДМИН ПАНЕЛЬ ---
class AdminStates(StatesGroup):
    wait_name = State(); wait_file = State(); wait_google = State(); wait_yandex = State(); wait_desc = State(); wait_photo = State()
    wait_sec_key = State(); wait_sec_ru = State(); wait_sec_en = State()

@dp.message(Command("admin"))
async def adm_panel(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🎹 + Драм кит", callback_data="add_drumkit"))
    kb.row(types.InlineKeyboardButton(text="🔌 + Плагин", callback_data="add_plugin"))
    kb.row(types.InlineKeyboardButton(text="🎚 + DAW", callback_data="add_daw"))
    kb.row(types.InlineKeyboardButton(text="📁 Управление разделами", callback_data="adm_sections"))
    await m.answer("Панель администратора:", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "adm_sections")
async def adm_sections(c: types.CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="➕ Добавить раздел", callback_data="sec_add_start"))
    kb.row(types.InlineKeyboardButton(text="🗑 Удалить раздел", callback_data="sec_del_list"))
    await c.message.edit_text("Управление разделами:", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "sec_add_start")
async def sec_add_start(c: types.CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="Драм киты", callback_data="setsectype_drumkit"))
    kb.row(types.InlineKeyboardButton(text="DAW", callback_data="setsectype_daw"))
    await c.message.edit_text("Выберите тип раздела, который создаете:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("setsectype_"))
async def set_sec_type(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(stype=c.data.split("_")[1])
    await c.message.answer("Введите уникальный ID (только латиница, напр: phonk, logic, flstudio):")
    await state.set_state(AdminStates.wait_sec_key)

@dp.message(AdminStates.wait_sec_key)
async def wait_sec_key(m: types.Message, state: FSMContext):
    await state.update_data(skey=m.text.strip().lower())
    await m.answer("Введите название раздела на РУССКОМ:")
    await state.set_state(AdminStates.wait_sec_ru)

@dp.message(AdminStates.wait_sec_ru)
async def wait_sec_ru(m: types.Message, state: FSMContext):
    await state.update_data(sru=m.text.strip())
    await m.answer("Введите название раздела на АНГЛИЙСКОМ:")
    await state.set_state(AdminStates.wait_sec_en)

@dp.message(AdminStates.wait_sec_en)
async def wait_sec_en(m: types.Message, state: FSMContext):
    d = await state.get_data()
    db_query("INSERT INTO subcategories (type, key, name_ru, name_en) VALUES (?,?,?,?)", (d['stype'], d['skey'], d['sru'], m.text.strip()))
    await m.answer("✅ Новый раздел успешно создан!")
    await state.clear()

@dp.callback_query(F.data == "sec_del_list")
async def sec_del_list(c: types.CallbackQuery):
    secs = db_query("SELECT id, type, name_ru FROM subcategories", fetchall=True)
    kb = InlineKeyboardBuilder()
    for sid, stype, sru in secs: 
        kb.row(types.InlineKeyboardButton(text=f"[{stype.upper()}] {sru}", callback_data=f"delsec_{sid}"))
    await c.message.edit_text("Выберите раздел для удаления:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("delsec_"))
async def del_sec_confirm(c: types.CallbackQuery):
    db_query("DELETE FROM subcategories WHERE id = ?", (c.data.split("_")[1],))
    await c.answer("Раздел удален")
    await adm_panel(c.message)

@dp.callback_query(F.data.startswith("add_"))
async def add_item_start(c: types.CallbackQuery, state: FSMContext):
    t = c.data.split("_")[1]
    await state.update_data(itype=t)
    if t in ["drumkit", "daw"]:
        secs = db_query("SELECT key, name_ru FROM subcategories WHERE type = ?", (t,), fetchall=True)
        if not secs:
            await c.answer("Сначала создайте категорию в управлении разделами!", show_alert=True)
            return
        kb = InlineKeyboardBuilder()
        for k, ru in secs: 
            kb.row(types.InlineKeyboardButton(text=ru, callback_data=f"asub_{k}"))
        await c.message.answer("Выберите подраздел:", reply_markup=kb.as_markup())
    else:
        await state.update_data(sub=None)
        await c.message.answer("Введите название:")
        await state.set_state(AdminStates.wait_name)

@dp.callback_query(F.data.startswith("asub_"))
async def add_sub_confirm(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(sub=c.data.split("_")[1])
    await c.message.answer("Введите название товара:")
    await state.set_state(AdminStates.wait_name)

@dp.message(AdminStates.wait_name)
async def adm_name(m: types.Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("Отправьте Файл (документ) или напишите /skip:")
    await state.set_state(AdminStates.wait_file)

@dp.message(AdminStates.wait_file)
async def adm_file(m: types.Message, state: FSMContext):
    await state.update_data(fid=m.document.file_id if m.document else None)
    await m.answer("Ссылка на Google Drive или /skip:")
    await state.set_state(AdminStates.wait_google)

@dp.message(AdminStates.wait_google)
async def adm_google(m: types.Message, state: FSMContext):
    await state.update_data(gl=None if m.text=="/skip" else m.text)
    await m.answer("Ссылка на Yandex Disk или /skip:")
    await state.set_state(AdminStates.wait_yandex)

@dp.message(AdminStates.wait_yandex)
async def adm_yandex(m: types.Message, state: FSMContext):
    await state.update_data(yx=None if m.text=="/skip" else m.text)
    await m.answer("Введите описание:")
    await state.set_state(AdminStates.wait_desc)

@dp.message(AdminStates.wait_desc)
async def adm_desc(m: types.Message, state: FSMContext):
    await state.update_data(desc=m.text)
    await m.answer("Отправьте фото товара или напишите /skip:")
    await state.set_state(AdminStates.wait_photo)

@dp.message(AdminStates.wait_photo)
async def adm_photo(m: types.Message, state: FSMContext):
    d = await state.get_data()
    pid = m.photo[-1].file_id if m.photo else None
    db_query("INSERT INTO items (name, link_google, link_yandex, file_id, type, description, photo_id, subcategory) VALUES (?,?,?,?,?,?,?,?)",
             (d['name'], d['gl'], d['yx'], d['fid'], d['itype'], d['desc'], pid, d['sub']))
    await m.answer("✅ Успешно добавлено!")
    await state.clear()

@dp.callback_query(F.data.startswith("del_"))
async def adm_del_item(c: types.CallbackQuery):
    db_query("DELETE FROM items WHERE id = ?", (c.data.split("_")[1],))
    await c.answer("Товар удален")
    await close_sub(c)

@dp.message(Command("on"))
async def turn_on(m: types.Message):
    if m.from_user.id == ADMIN_ID:
        db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('bot_enabled', '1')")
        await m.answer("🟢 Бот успешно включен.")

@dp.message(Command("off"))
async def turn_off(m: types.Message):
    if m.from_user.id == ADMIN_ID:
        db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('bot_enabled', '0')")
        await m.answer("🔴 Бот временно отключен на техническое обслуживание.")

async def main():
    init_db()
    await bot.set_my_commands([
        types.BotCommand(command="start", description="Запуск бота"),
        types.BotCommand(command="eng", description="Language / Сменить язык")
    ])
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
