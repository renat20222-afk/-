
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
CHANNEL_ID = -1001234567890  # СЮДА ВСТАВЬТЕ ID ВАШЕГО КАНАЛА (ДОЛЖЕН НАЧИНАТЬСЯ С -100)
CHANNEL_LINK = 'https://t.me/your_channel'  # СЮДА ВСТАВЬТЕ ССЫЛКУ НА КАНАЛ

ITEMS_PER_PAGE = 7
START_PHOTO_PATH = 'welcome.jpg'

# Жанры драм китов (двуязычные)
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
            "📖 Открыть меню всех команд: /menu или воспользуйся синей кнопкой «Меню» слева."
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
            "📖 Open command menu: /menu or use the blue 'Menu' button on the left."
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
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       name TEXT, link_google TEXT, link_yandex TEXT,
                       file_id TEXT, type TEXT, description TEXT, photo_id TEXT,
                       subcategory TEXT DEFAULT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, lang TEXT DEFAULT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings 
                      (key TEXT PRIMARY KEY, value TEXT)''')
    
    # Значение по умолчанию: бот включен
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('bot_enabled', '1')")
    
    try:
        cursor.execute("ALTER TABLE items ADD COLUMN subcategory TEXT DEFAULT NULL")
    except: pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN lang TEXT DEFAULT NULL")
    except: pass
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
    val = '1' if enabled else '0'
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('bot_enabled', ?)", (val,))
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

def get_all_users():
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def add_item_to_db(name, link_google, link_yandex, file_id, item_type, description, photo_id, subcategory):
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO items (name, link_google, link_yandex, file_id, type, description, photo_id, subcategory) 
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", 
                   (name, link_google, link_yandex, file_id, item_type, description, photo_id, subcategory))
    conn.commit()
    conn.close()

def update_item_in_db(item_id, name, link_google, link_yandex, file_id, description, photo_id, subcategory):
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute("""UPDATE items SET name=?, link_google=?, link_yandex=?, file_id=?, description=?, photo_id=?, subcategory=? 
                      WHERE id=?""", (name, link_google, link_yandex, file_id, description, photo_id, subcategory, item_id))
    conn.commit()
    conn.close()

def delete_item_from_db(item_id):
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

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
    if user_id == ADMIN_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ['member', 'creator', 'administrator']:
            return True
    except Exception as e:
        logging.error(f"Subscription check error: {e}")
        return True # Чтобы не блокировать пользователей в случае технических неполадок с правами бота
    return False

# --- MIDDLEWARE ДЛЯ БЛОКИРОВОК И ОГРАНИЧЕНИЙ ---
class MaintenanceAndSubMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get('event_from_user')
        if not user:
            return await handler(event, data)

        # 1. Админ всегда в обход ограничений
        if user.id == ADMIN_ID:
            return await handler(event, data)

        # 2. Проверка тех. обслуживания
        if not is_bot_enabled():
            lang = get_user_lang(user.id) or 'ru'
            if isinstance(event, types.Message):
                await event.answer(TEXTS[lang]["maintenance"])
            elif isinstance(event, types.CallbackQuery):
                await event.answer(TEXTS[lang]["maintenance"], show_alert=True)
            return

        # 3. Разрешаем проход без языков и подписок для базовых команд выбора
        is_start_or_menu = False
        if isinstance(event, types.Message) and event.text:
            is_start_or_menu = event.text.startswith("/start") or event.text.startswith("/menu")

        is_lang_callback = isinstance(event, types.CallbackQuery) and event.data.startswith("setlang_")
        is_sub_callback = isinstance(event, types.CallbackQuery) and event.data == "check_sub"

        if is_start_or_menu or is_lang_callback or is_sub_callback:
            return await handler(event, data)

        # 4. Проверка наличия выбранного языка
        lang = get_user_lang(user.id)
        if not lang:
            kb = InlineKeyboardBuilder()
            kb.row(
                types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru"),
                types.InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en")
            )
            if isinstance(event, types.Message):
                await event.answer("🌍 Выберите язык / Select language:", reply_markup=kb.as_markup())
            elif isinstance(event, types.CallbackQuery):
                await event.message.answer("🌍 Выберите язык / Select language:", reply_markup=kb.as_markup())
            return

        # 5. Проверка обязательной подписки
        subscribed = await check_subscription(data['bot'], user.id)
        if not subscribed:
            kb = InlineKeyboardBuilder()
            kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["sub_btn"], url=CHANNEL_LINK))
            kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["check_sub_btn"], callback_data="check_sub"))
            if isinstance(event, types.Message):
                await event.answer(TEXTS[lang]["sub_required"], reply_markup=kb.as_markup())
            elif isinstance(event, types.CallbackQuery):
                await event.message.answer(TEXTS[lang]["sub_required"], reply_markup=kb.as_markup())
            return

        return await handler(event, data)

# --- ИНИЦИАЛИЗАЦИЯ ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
dp.update.outer_middleware(MaintenanceAndSubMiddleware())

# --- КЛАВИАТУРЫ ---
def main_menu(lang):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=TEXTS[lang]["drumkits"], callback_data="drumkit_genres"))
    builder.row(types.InlineKeyboardButton(text=TEXTS[lang]["plugins"], callback_data="list_plugin_0"))
    builder.row(types.InlineKeyboardButton(text=TEXTS[lang]["daw"], callback_data="list_daw_0"))
    return builder.as_markup()

def admin_menu():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔌 Добавить Плагин", callback_data="admin_add_plugin"))
    builder.row(types.InlineKeyboardButton(text="🎹 Добавить Драм кит", callback_data="admin_add_drumkit"))
    builder.row(types.InlineKeyboardButton(text="🎚 Добавить DAW", callback_data="admin_add_daw"))
    builder.row(types.InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_close"))
    return builder.as_markup()

async def setup_bot_commands(bot: Bot):
    commands = [
        types.BotCommand(command="start", description="🏠 Начать / Start"),
        types.BotCommand(command="menu", description="📖 Главное меню / Main Menu"),
        types.BotCommand(command="admin", description="🛠️ Панель администратора"),
        types.BotCommand(command="post", description="📢 Сделать рассылку")
    ]
    await bot.set_my_commands(commands)

# --- ХЕНДЛЕРЫ ВЫБОРА ЯЗЫКА И ПОДПИСКИ ---

@dp.message(Command("start"))
@dp.message(Command("menu"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    
    if not lang:
        kb = InlineKeyboardBuilder()
        kb.row(
            types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru"),
            types.InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en")
        )
        await message.answer("🌍 Выберите язык / Select language:", reply_markup=kb.as_markup())
        return

    subscribed = await check_subscription(message.bot, user_id)
    if not subscribed:
        kb = InlineKeyboardBuilder()
        kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["sub_btn"], url=CHANNEL_LINK))
        kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["check_sub_btn"], callback_data="check_sub"))
        await message.answer(TEXTS[lang]["sub_required"], reply_markup=kb.as_markup())
        return

    text = TEXTS[lang]["welcome"].format(name=message.from_user.first_name)
    try:
        photo = FSInputFile(START_PHOTO_PATH)
        await message.answer_photo(photo, caption=text, parse_mode="HTML", reply_markup=main_menu(lang))
    except:
        await message.answer(text, parse_mode="HTML", reply_markup=main_menu(lang))

@dp.callback_query(F.data.startswith("setlang_"))
async def save_lang_choice(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    user_id = callback.from_user.id
    set_user_lang(user_id, lang)
    
    await callback.answer()
    await callback.message.delete()
    
    subscribed = await check_subscription(callback.bot, user_id)
    if not subscribed:
        kb = InlineKeyboardBuilder()
        kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["sub_btn"], url=CHANNEL_LINK))
        kb.row(types.InlineKeyboardButton(text=TEXTS[lang]["check_sub_btn"], callback_data="check_sub"))
        await callback.message.answer(TEXTS[lang]["sub_required"], reply_markup=kb.as_markup())
        return
        
    text = TEXTS[lang]["welcome"].format(name=callback.from_user.first_name)
    try:
        photo = FSInputFile(START_PHOTO_PATH)
        await callback.message.answer_photo(photo, caption=text, parse_mode="HTML", reply_markup=main_menu(lang))
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=main_menu(lang))

@dp.callback_query(F.data == "check_sub")
async def verify_sub(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_lang(user_id) or "ru"
    
    subscribed = await check_subscription(callback.bot, user_id)
    if subscribed:
        await callback.answer()
        await callback.message.delete()
        text = TEXTS[lang]["welcome"].format(name=callback.from_user.first_name)
        try:
            photo = FSInputFile(START_PHOTO_PATH)
            await callback.message.answer_photo(photo, caption=text, parse_mode="HTML", reply_markup=main_menu(lang))
        except:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=main_menu(lang))
    else:
        await callback.answer(TEXTS[lang]["not_subbed"], show_alert=True)

# --- ХЕНДЛЕРЫ МЕНЮ И ТОВАРОВ ---

@dp.callback_query(F.data == "main_menu")
async def back_to_menu(callback: types.CallbackQuery):
    lang = get_user_lang(callback.from_user.id) or "ru"
    await callback.message.delete()
    text = TEXTS[lang]["welcome"].format(name=callback.from_user.first_name)
    try:
        photo = FSInputFile(START_PHOTO_PATH)
        await callback.message.answer_photo(photo, caption=text, parse_mode="HTML", reply_markup=main_menu(lang))
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=main_menu(lang))

@dp.callback_query(F.data == "drumkit_genres")
async def show_drumkit_genres(callback: types.CallbackQuery):
    lang = get_user_lang(callback.from_user.id) or "ru"
    builder = InlineKeyboardBuilder()
    for key, names in DRUMKIT_GENRES.items():
        builder.row(types.InlineKeyboardButton(text=names[lang], callback_data=f"list_drumkit_{key}_0"))
    builder.row(types.InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="main_menu"))
    await callback.message.delete()
    await callback.message.answer(TEXTS[lang]["select_genre"], reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("list_"))
async def show_list(callback: types.CallbackQuery):
    lang = get_user_lang(callback.from_user.id) or "ru"
    data = callback.data.split("_")
    if len(data) == 4:
        _, item_type, subcategory, page = data
        page = int(page)
    else:
        _, item_type, page = data
        page = int(page)
        subcategory = None

    items = get_items_by_type(item_type, subcategory)
    if not items:
        await callback.answer(TEXTS[lang]["empty"], show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    start, end = page * ITEMS_PER_PAGE, (page + 1) * ITEMS_PER_PAGE
    for i_id, name in items[start:end]:
        builder.row(types.InlineKeyboardButton(text=name, callback_data=f"view_{i_id}_{page}"))
        
    nav = []
    if item_type == "drumkit":
        if page > 0: nav.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"list_drumkit_{subcategory}_{page-1}"))
        if end < len(items): nav.append(types.InlineKeyboardButton(text="➡️", callback_data=f"list_drumkit_{subcategory}_{page+1}"))
    else:
        if page > 0: nav.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"list_{item_type}_{page-1}"))
        if end < len(items): nav.append(types.InlineKeyboardButton(text="➡️", callback_data=f"list_{item_type}_{page+1}"))
    builder.row(*nav)
    
    if item_type == "drumkit":
        builder.row(types.InlineKeyboardButton(text=TEXTS[lang]["back_genres"], callback_data="drumkit_genres"))
    else:
        builder.row(types.InlineKeyboardButton(text=TEXTS[lang]["main_menu"], callback_data="main_menu"))
        
    await callback.message.delete()
    cat_name = DRUMKIT_GENRES.get(subcategory, {}).get(lang, subcategory) if subcategory else item_type.upper()
    await callback.message.answer(f"{TEXTS[lang]['category']} {cat_name}", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("view_"))
async def view_item(callback: types.CallbackQuery):
    lang = get_user_lang(callback.from_user.id) or "ru"
    _, item_id, page = callback.data.split("_")
    item_id, page = int(item_id), int(page)
    item = get_item_by_id(item_id)
    if not item: return
    name, g_link, y_link, f_id, desc, p_id, i_type, subcategory = item
    
    caption = f"<b>{name}</b>\n\n{desc or ''}"
    builder = InlineKeyboardBuilder()
    
    if f_id: builder.row(types.InlineKeyboardButton(text=TEXTS[lang]["download_direct"], callback_data=f"dl_{item_id}"))
    if g_link: builder.row(types.InlineKeyboardButton(text="🟢 Google Drive", url=g_link))
    if y_link: builder.row(types.InlineKeyboardButton(text="🔴 Yandex Disk", url=y_link))
    
    if callback.from_user.id == ADMIN_ID:
        builder.row(
            types.InlineKeyboardButton(text="✏️ Изменить", callback_data=f"adm_edit_{item_id}"),
            types.InlineKeyboardButton(text="🗑 Удалить", callback_data=f"adm_del_{item_id}")
        )
    
    if i_type == "drumkit" and subcategory:
        builder.row(types.InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data=f"list_drumkit_{subcategory}_{page}"))
    else:
        builder.row(types.InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data=f"list_{i_type}_{page}"))

    await callback.message.delete()
    if p_id:
        await callback.message.answer_photo(p_id, caption=caption, parse_mode="HTML", reply_markup=builder.as_markup())
    else:
        await callback.message.answer(caption, parse_mode="HTML", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("dl_"))
async def download_file(callback: types.CallbackQuery):
    lang = get_user_lang(callback.from_user.id) or "ru"
    item_id = int(callback.data.split("_")[1])
    item = get_item_by_id(item_id)
    await callback.answer(TEXTS[lang]["sending_file"])
    await callback.message.answer_document(item[3])

# --- АДМИНКА ---

@dp.message(Command("off"))
async def turn_off(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    set_bot_enabled(False)
    await message.answer("🔴 Бот временно выключен для обычных пользователей.")

@dp.message(Command("on"))
async def turn_on(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    set_bot_enabled(True)
    await message.answer("🟢 Бот успешно включен и доступен для всех.")

@dp.callback_query(F.data.startswith("adm_del_"))
async def confirm_delete(callback: types.CallbackQuery):
    item_id = callback.data.split("_")[2]
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="✅ ДА, УДАЛИТЬ", callback_data=f"conf_del_{item_id}"))
    builder.row(types.InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="main_menu"))
    await callback.message.answer("⚠️ Вы уверены, что хотите удалить этот элемент?", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("conf_del_"))
async def process_delete(callback: types.CallbackQuery):
    item_id = int(callback.data.split("_")[2])
    delete_item_from_db(item_id)
    await callback.answer("Удалено!")
    await callback.message.delete()
    await back_to_menu(callback)

@dp.callback_query(F.data.startswith("adm_edit_"))
async def start_edit(callback: types.CallbackQuery, state: FSMContext):
    item_id = int(callback.data.split("_")[2])
    item = get_item_by_id(item_id)
    await state.update_data(edit_id=item_id, item_type=item[6], subcategory=item[7])
    await callback.message.answer(f"📝 Меняем: {item[0]}\nВведите новое название:")
    await state.set_state(AdminStates.waiting_for_name)

@dp.message(Command("post"))
async def post_command(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("📝 Отправь сообщение для рассылки:")
    await state.set_state(AdminStates.waiting_for_post)

@dp.message(AdminStates.waiting_for_post)
async def perform_post(message: types.Message, state: FSMContext):
    await state.clear()
    users = get_all_users()
    if not users: return
    status_msg = await message.answer(f"📢 Рассылка пошла...")
    success = 0
    for user_id in users:
        try:
            await message.send_copy(chat_id=user_id)
            success += 1
            await asyncio.sleep(0.05)
        except: pass
    await status_msg.edit_text(f"📢 Рассылка завершена!\nДоставлено: {success}")

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("🛠️ Панель администратора:", reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_close")
async def close_adm(callback: types.CallbackQuery):
    await callback.message.delete()

@dp.callback_query(F.data.startswith("admin_add_"))
async def admin_add(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    i_type = callback.data.replace("admin_add_", "")
    await state.update_data(item_type=i_type, edit_id=None)
    await callback.message.delete()
    if i_type == "drumkit":
        builder = InlineKeyboardBuilder()
        for key, names in DRUMKIT_GENRES.items():
            builder.row(types.InlineKeyboardButton(text=names["ru"], callback_data=f"admin_genre_{key}"))
        await callback.message.answer("Выберите жанр:", reply_markup=builder.as_markup())
        await state.set_state(AdminStates.waiting_for_subcategory)
    else:
        await state.update_data(subcategory=None)
        await callback.message.answer(f"Введите название ({i_type}):")
        await state.set_state(AdminStates.waiting_for_name)

@dp.callback_query(AdminStates.waiting_for_subcategory, F.data.startswith("admin_genre_"))
async def admin_select_genre(callback: types.CallbackQuery, state: FSMContext):
    genre = callback.data.replace("admin_genre_", "")
    await state.update_data(subcategory=genre)
    await callback.message.delete()
    await callback.message.answer(f"Введите название ({DRUMKIT_GENRES[genre]['ru']}):")
    await state.set_state(AdminStates.waiting_for_name)

@dp.message(AdminStates.waiting_for_name)
async def adm_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📁 Шаг 1/3: Отправь ФАЙЛ напрямую боту (или /skip):")
    await state.set_state(AdminStates.waiting_for_file)

@dp.message(AdminStates.waiting_for_file)
async def adm_file(message: types.Message, state: FSMContext):
    if message.text == "/skip":
        await state.update_data(file_id=None)
    elif message.document:
        await state.update_data(file_id=message.document.file_id)
    else:
        await message.answer("⚠️ Отправьте файл как Документ или /skip:")
        return
    await message.answer("🟢 Шаг 2/3: Ссылка на Google Drive (или /skip):")
    await state.set_state(AdminStates.waiting_for_google)

@dp.message(AdminStates.waiting_for_google)
async def adm_google(message: types.Message, state: FSMContext):
    link = None if message.text == "/skip" else message.text
    await state.update_data(link_google=link)
    await message.answer("🔴 Шаг 3/3: Ссылка на Яндекс Диск (или /skip):")
    await state.set_state(AdminStates.waiting_for_yandex)

@dp.message(AdminStates.waiting_for_yandex)
async def adm_yandex(message: types.Message, state: FSMContext):
    link = None if message.text == "/skip" else message.text
    await state.update_data(link_yandex=link)
    await message.answer("📝 Описание (или /skip):")
    await state.set_state(AdminStates.waiting_for_desc)

@dp.message(AdminStates.waiting_for_desc)
async def adm_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc="" if message.text == "/skip" else message.text)
    await message.answer("🖼️ Превью-картинка (или /skip):")
    await state.set_state(AdminStates.waiting_for_photo)

@dp.message(AdminStates.waiting_for_photo)
async def adm_photo(message: types.Message, state: FSMContext):
    p_id = message.photo[-1].file_id if message.photo else None
    data = await state.get_data()
    
    if data.get('edit_id'):
        update_item_in_db(data['edit_id'], data['name'], data['link_google'], data['link_yandex'], data['file_id'], data['desc'], p_id, data.get('subcategory'))
        await message.answer("✅ Успешно обновлено!")
    else:
        add_item_to_db(data['name'], data['link_google'], data['link_yandex'], data['file_id'], data['item_type'], data['desc'], p_id, data.get('subcategory'))
        await message.answer("✅ Успешно добавлено!")
    await state.clear()

async def main():
    init_db()
    await setup_bot_commands(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
