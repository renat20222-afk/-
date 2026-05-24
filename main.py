
import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile

# --- НАСТРОЙКИ ---
API_TOKEN = '8989268578:AAEEnVwlFoqQ1rjsxyO8dXLQMLTO3tXfloc'
ADMIN_ID = 1753037099 

# Ссылка на ваш канал
CHANNEL_LINK = 'https://t.me/soundroid'
# СЮДА ВСТАВЬТЕ ЦИФРОВОЙ ID КАНАЛА (начинается на -100)
# Узнать его можно через @getmyid_bot, переслав пост из канала
CHANNEL_ID = -1001552554703 

ITEMS_PER_PAGE = 7
START_PHOTO_PATH = 'welcome.jpg'

# Жанры драм китов
DRUMKIT_GENRES = {
    "brazil": {"ru": "Brazil Funk 🇧🇷", "en": "Brazil Funk 🇧🇷"},
    "ambient": {"ru": "Ambient ☁️", "en": "Ambient ☁️"},
    "phonk": {"ru": "Phonk 💀", "en": "Phonk 💀"},
    "trap": {"ru": "Trap ⚡", "en": "Trap ⚡"},
    "boombap": {"ru": "Boom Bap 🥁", "en": "Boom Bap 🥁"},
    "other": {"ru": "Другое 📦", "en": "Other 📦"}
}

# --- ЛОКАЛИЗАЦИЯ ---
TEXTS = {
    "ru": {
        "maintenance": "⚠️ Бот временно отключен на техническое обслуживание. Пожалуйста, зайдите позже!",
        "select_lang": "🌍 Выберите язык / Select language:",
        "sub_required": "⚠️ Для использования бота необходимо подписаться на наш канал!",
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
            "📖 Меню команд: /menu или кнопка «Меню».\n"
            "🌍 Сменить язык: /eng"
        ),
        "drumkits": "🎹 Драм киты",
        "plugins": "🔌 Плагины",
        "daw": "🎚 DAW",
        "select_genre": "Какой драм-кит хотите скачать? Выберите жанр:",
        "category": "Категория:",
        "back": "⬅️ Назад",
        "back_genres": "⬅️ К жанрам",
        "main_menu": "🏠 Меню",
        "download_direct": "📥 Скачать напрямую",
        "sending_file": "Отправляю файл...",
        "empty": "Здесь пока ничего нет."
    },
    "en": {
        "maintenance": "⚠️ The bot is temporarily offline for maintenance. Please check back later!",
        "select_lang": "🌍 Выберите язык / Select language:",
        "sub_required": "⚠️ You must subscribe to our channel to use this bot!",
        "sub_btn": "📢 Subscribe to Channel",
        "check_sub_btn": "✅ I subscribed",
        "not_subbed": "❌ You haven't subscribed to the channel yet!",
        "welcome": (
            "Hello, {name}! 👋\n\n"
            "🔥 <b>I am your music assistant!</b>\n"
            "I will help you find the best stuff for your creativity. Here is what I have:\n\n"
            "🎹 <b>Drumkits</b> — sorted by genres.\n"
            "🔌 <b>Plugins</b> — VST synths and effects.\n"
            "🎚 <b>DAW</b> — software for music production.\n\n"
            "Choose the section below and let's get started! 👇\n\n"
            "📖 Command menu: /menu or 'Menu' button.\n"
            "🌍 Change language: /eng"
        ),
        "drumkits": "🎹 Drumkits",
        "plugins": "🔌 Plugins",
        "daw": "🎚 DAW",
        "select_genre": "Which drumkit do you want to download? Choose a genre:",
        "category": "Category:",
        "back": "⬅️ Back",
        "back_genres": "⬅️ To genres",
        "main_menu": "🏠 Menu",
        "download_direct": "📥 Download directly",
        "sending_file": "Sending file...",
        "empty": "There is nothing here yet."
    }
}

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS items 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, link_google TEXT, 
                       link_yandex TEXT, file_id TEXT, type TEXT, description TEXT, 
                       photo_id TEXT, subcategory TEXT DEFAULT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, lang TEXT DEFAULT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('bot_enabled', '1')")
    conn.commit()
    conn.close()

def is_bot_enabled():
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'bot_enabled'")
    row = cursor.fetchone()
    conn.close()
    return row[0] == '1' if row else True

def set_bot_enabled(enabled: bool):
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('bot_enabled', ?)", ('1' if enabled else '0',))
    conn.commit()
    conn.close()

def set_user_lang(user_id, lang):
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (user_id, lang) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET lang=?", (user_id, lang, lang))
    conn.commit()
    conn.close()

def get_user_lang(user_id):
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_items_by_type(item_type, subcategory=None):
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    if item_type == 'drumkit' and subcategory:
        cursor.execute("SELECT id, name FROM items WHERE type = ? AND subcategory = ?", (item_type, subcategory))
    else:
        cursor.execute("SELECT id, name FROM items WHERE type = ?", (item_type,))
    res = cursor.fetchall()
    conn.close()
    return res

def get_item_by_id(item_id):
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, link_google, link_yandex, file_id, description, photo_id, type, subcategory FROM items WHERE id = ?", (item_id,))
    res = cursor.fetchone()
    conn.close()
    return res

# --- СОСТОЯНИЯ ---
class AdminStates(StatesGroup):
    waiting_for_subcategory = State()
    waiting_for_name = State()
    waiting_for_file = State()
    waiting_for_google = State()
    waiting_for_yandex = State()
    waiting_for_desc = State()
    waiting_for_photo = State()
    waiting_for_post = State()

# --- ПРОВЕРКА ПОДПИСКИ ---
async def check_subscription(bot: Bot, user_id: int) -> bool:
    if user_id == ADMIN_ID: return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'creator', 'administrator']
    except Exception as e:
        logging.error(f"Subscription error check: {e}")
        return True

# --- MIDDLEWARE ---
class MaintenanceAndSubMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get('event_from_user')
        if not user or user.id == ADMIN_ID: return await handler(event, data)

        if not is_bot_enabled():
            lang = get_user_lang(user.id) or 'ru'
            if isinstance(event, types.Message): await event.answer(TEXTS[lang]["maintenance"])
            return

        # Разрешаем команды старта, смены языка и меню без проверки подписок
        is_basic = False
        if isinstance(event, types.Message) and event.text:
            is_basic = event.text.startswith("/start") or event.text.startswith("/eng") or event.text.startswith("/menu")
        
        is_cb = isinstance(event, types.CallbackQuery) and (event.data.startswith("setlang_") or event.data == "check_sub")

        if is_basic or is_cb: return await handler(event, data)

        lang = get_user_lang(user.id)
        if not lang:
            kb = InlineKeyboardBuilder()
            kb.row(types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru"),
                   types.InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en"))
            await (event.answer if isinstance(event, types.Message) else event.message.answer)(TEXTS["ru"]["select_lang"], reply_markup=kb.as_markup())
            return

        if not await check_subscription(data['bot'], user.id):
            kb = InlineKeyboardBuilder()
            kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["sub_btn"], url=CHANNEL_LINK))
            kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["check_sub_btn"], callback_data="check_sub"))
            await (event.answer if isinstance(event, types.Message) else event.message.answer)(TEXTS[lang]["sub_required"], reply_markup=kb.as_markup())
            return

        return await handler(event, data)

# --- ИНИЦИАЛИЗАЦИЯ ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
dp.update.outer_middleware(MaintenanceAndSubMiddleware())

# --- КЛАВИАТУРЫ ---
def main_menu_kb(lang):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=TEXTS[lang]["drumkits"], callback_data="drumkit_genres"))
    builder.row(types.InlineKeyboardButton(text=TEXTS[lang]["plugins"], callback_data="list_plugin_0"))
    builder.row(types.InlineKeyboardButton(text=TEXTS[lang]["daw"], callback_data="list_daw_0"))
    return builder.as_markup()

# --- ХЕНДЛЕРЫ ---

# ИСПРАВЛЕНО: Объединено в один фильтр Command
@dp.message(Command("start", "eng"))
async def cmd_start_lang(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru"),
           types.InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en"))
    await message.answer(TEXTS["ru"]["select_lang"], reply_markup=kb.as_markup())

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    lang = get_user_lang(message.from_user.id) or "ru"
    text = TEXTS[lang]["welcome"].format(name=message.from_user.first_name)
    try:
        await message.answer_photo(FSInputFile(START_PHOTO_PATH), caption=text, parse_mode="HTML", reply_markup=main_menu_kb(lang))
    except:
        await message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb(lang))

@dp.callback_query(F.data.startswith("setlang_"))
async def save_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    set_user_lang(callback.from_user.id, lang)
    await callback.answer()
    await callback.message.delete()
    
    if not await check_subscription(callback.bot, callback.from_user.id):
        kb = InlineKeyboardBuilder()
        kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["sub_btn"], url=CHANNEL_LINK))
        kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["check_sub_btn"], callback_data="check_sub"))
        await callback.message.answer(TEXTS[lang]["sub_required"], reply_markup=kb.as_markup())
    else:
        text = TEXTS[lang]["welcome"].format(name=callback.from_user.first_name)
        try:
            await callback.message.answer_photo(FSInputFile(START_PHOTO_PATH), caption=text, parse_mode="HTML", reply_markup=main_menu_kb(lang))
        except:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb(lang))

@dp.callback_query(F.data == "check_sub")
async def verify_sub(callback: types.CallbackQuery):
    lang = get_user_lang(callback.from_user.id) or "ru"
    if await check_subscription(callback.bot, callback.from_user.id):
        await callback.message.delete()
        text = TEXTS[lang]["welcome"].format(name=callback.from_user.first_name)
        try: 
            await callback.message.answer_photo(FSInputFile(START_PHOTO_PATH), caption=text, parse_mode="HTML", reply_markup=main_menu_kb(lang))
        except: 
            await callback.message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb(lang))
    else:
        await callback.answer(TEXTS[lang]["not_subbed"], show_alert=True)

@dp.callback_query(F.data == "main_menu")
async def back_to_menu_cb(callback: types.CallbackQuery):
    lang = get_user_lang(callback.from_user.id) or "ru"
    await callback.message.delete()
    text = TEXTS[lang]["welcome"].format(name=callback.from_user.first_name)
    try: 
        await callback.message.answer_photo(FSInputFile(START_PHOTO_PATH), caption=text, parse_mode="HTML", reply_markup=main_menu_kb(lang))
    except: 
        await callback.message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb(lang))

@dp.callback_query(F.data == "drumkit_genres")
async def drumkit_genres_cb(callback: types.CallbackQuery):
    lang = get_user_lang(callback.from_user.id) or "ru"
    kb = InlineKeyboardBuilder()
    for k, v in DRUMKIT_GENRES.items():
        kb.row(types.InlineKeyboardButton(text=v[lang], callback_data=f"list_drumkit_{k}_0"))
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="main_menu"))
    await callback.message.edit_caption(caption=TEXTS[lang]["select_genre"], reply_markup=kb.as_markup()) if callback.message.photo else await callback.message.edit_text(TEXTS[lang]["select_genre"], reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("list_"))
async def list_items_cb(callback: types.CallbackQuery):
    lang = get_user_lang(callback.from_user.id) or "ru"
    d = callback.data.split("_")
    it_type, sub, pg = (d[1], d[2], int(d[3])) if len(d)==4 else (d[1], None, int(d[2]))
    items = get_items_by_type(it_type, sub)
    if not items: return await callback.answer(TEXTS[lang]["empty"], show_alert=True)
    
    kb = InlineKeyboardBuilder()
    for i_id, name in items[pg*7:(pg+1)*7]: kb.row(types.InlineKeyboardButton(text=name, callback_data=f"view_{i_id}_{pg}"))
    nav = []
    if pg > 0: nav.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"list_{it_type}_{f'{sub}_' if sub else ''}{pg-1}"))
    if (pg+1)*7 < len(items): nav.append(types.InlineKeyboardButton(text="➡️", callback_data=f"list_{it_type}_{f'{sub}_' if sub else ''}{pg+1}"))
    kb.row(*nav)
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="drumkit_genres" if it_type=="drumkit" else "main_menu"))
    
    txt = f"{TEXTS[lang]['category']} {DRUMKIT_GENRES[sub][lang] if sub else it_type.upper()}"
    await callback.message.delete()
    await callback.message.answer(txt, reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("view_"))
async def view_item_cb(callback: types.CallbackQuery):
    lang = get_user_lang(callback.from_user.id) or "ru"
    _, i_id, pg = callback.data.split("_")
    item = get_item_by_id(int(i_id))
    if not item: return
    name, g_l, y_l, f_id, desc, p_id, it_t, sub = item
    kb = InlineKeyboardBuilder()
    if f_id: kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["download_direct"], callback_data=f"dl_{i_id}"))
    if g_l: kb.row(types.InlineKeyboardButton(text="🟢 Google Drive", url=g_l))
    if y_l: kb.row(types.InlineKeyboardButton(text="🔴 Yandex Disk", url=y_l))
    if callback.from_user.id == ADMIN_ID:
        kb.row(types.InlineKeyboardButton(text="🗑 Удалить", callback_data=f"adm_del_{i_id}"))
    kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data=f"list_{it_t}_{f'{sub}_' if sub else ''}{pg}"))
    
    await callback.message.delete()
    cap = f"<b>{name}</b>\n\n{desc}"
    if p_id: await callback.message.answer_photo(p_id, caption=cap, parse_mode="HTML", reply_markup=kb.as_markup())
    else: await callback.message.answer(cap, parse_mode="HTML", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("dl_"))
async def dl_cb(callback: types.CallbackQuery):
    item = get_item_by_id(int(callback.data.split("_")[1]))
    await callback.answer(TEXTS[get_user_lang(callback.from_user.id) or "ru"]["sending_file"])
    await callback.message.answer_document(item[3])

# --- АДМИН КОМАНДЫ ---
@dp.message(Command("off"))
async def turn_off(m: types.Message):
    if m.from_user.id == ADMIN_ID: set_bot_enabled(False); await m.answer("🔴 OFF")

@dp.message(Command("on"))
async def turn_on(m: types.Message):
    if m.from_user.id == ADMIN_ID: set_bot_enabled(True); await m.answer("🟢 ON")

@dp.message(Command("admin"))
async def adm_p(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🎹 + Драм кит", callback_data="admin_add_drumkit"))
    kb.row(types.InlineKeyboardButton(text="🔌 + Плагин", callback_data="admin_add_plugin"))
    kb.row(types.InlineKeyboardButton(text="🎚 + DAW", callback_data="admin_add_daw"))
    await m.answer("Админка:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("admin_add_"))
async def adm_add_start(c: types.CallbackQuery, state: FSMContext):
    t = c.data.replace("admin_add_", "")
    await state.update_data(item_type=t)
    if t == "drumkit":
        kb = InlineKeyboardBuilder()
        for k,v in DRUMKIT_GENRES.items(): kb.row(types.InlineKeyboardButton(text=v["ru"], callback_data=f"adm_genre_{k}"))
        await c.message.answer("Жанр:", reply_markup=kb.as_markup()); await state.set_state(AdminStates.waiting_for_subcategory)
    else:
        await state.update_data(subcategory=None); await c.message.answer("Название:"); await state.set_state(AdminStates.waiting_for_name)

@dp.callback_query(F.data.startswith("adm_genre_"))
async def adm_genre_sel(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(subcategory=c.data.replace("adm_genre_", "")); await c.message.answer("Название:"); await state.set_state(AdminStates.waiting_for_name)

@dp.message(AdminStates.waiting_for_name)
async def adm_n(m: types.Message, state: FSMContext):
    await state.update_data(name=m.text); await m.answer("Файл (документ) или /skip:"); await state.set_state(AdminStates.waiting_for_file)

@dp.message(AdminStates.waiting_for_file)
async def adm_f(m: types.Message, state: FSMContext):
    await state.update_data(file_id=m.document.file_id if m.document else None); await m.answer("Google Link или /skip:"); await state.set_state(AdminStates.waiting_for_google)

@dp.message(AdminStates.waiting_for_google)
async def adm_g(m: types.Message, state: FSMContext):
    await state.update_data(link_google=None if m.text=="/skip" else m.text); await m.answer("Yandex Link или /skip:"); await state.set_state(AdminStates.waiting_for_yandex)

@dp.message(AdminStates.waiting_for_yandex)
async def adm_y(m: types.Message, state: FSMContext):
    await state.update_data(link_yandex=None if m.text=="/skip" else m.text); await m.answer("Описание или /skip:"); await state.set_state(AdminStates.waiting_for_desc)

@dp.message(AdminStates.waiting_for_desc)
async def adm_d(m: types.Message, state: FSMContext):
    await state.update_data(desc="" if m.text=="/skip" else m.text); await m.answer("Фото или /skip:"); await state.set_state(AdminStates.waiting_for_photo)

@dp.message(AdminStates.waiting_for_photo)
async def adm_ph(m: types.Message, state: FSMContext):
    d = await state.get_data()
    conn = sqlite3.connect('assets.db'); cursor = conn.cursor()
    cursor.execute("INSERT INTO items (name, link_google, link_yandex, file_id, type, description, photo_id, subcategory) VALUES (?,?,?,?,?,?,?,?)",
                   (d['name'], d['link_google'], d['link_yandex'], d['file_id'], d['item_type'], d['desc'], m.photo[-1].file_id if m.photo else None, d['subcategory']))
    conn.commit(); conn.close()
    await m.answer("✅ Добавлено!"); await state.clear()

async def main():
    init_db()
    
    # Настройка кнопок меню в интерфейсе Telegram
    async def setup_bot_commands(bot: Bot):
        commands = [
            types.BotCommand(command="start", description="🏠 Начать / Start"),
            types.BotCommand(command="menu", description="📖 Главное меню / Main Menu"),
            types.BotCommand(command="eng", description="🌍 Сменить язык / Change language"),
            types.BotCommand(command="admin", description="🛠️ Панель администратора"),
            types.BotCommand(command="post", description="📢 Сделать рассылку")
        ]
        await bot.set_my_commands(commands)
        
    await setup_bot_commands(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
