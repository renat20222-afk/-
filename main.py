
import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile

# --- НАСТРОЙКИ ---
API_TOKEN = '8989268578:AAEEnVwlFoqQ1rjsxyO8dXLQMLTO3tXfloc'
ADMIN_ID = 1753037099 
ITEMS_PER_PAGE = 7
START_PHOTO_PATH = 'welcome.jpg'

# Жанры драм китов
DRUMKIT_GENRES = {
    "brazil": "Brazil Funk 🇧🇷",
    "ambient": "Ambient ☁️",
    "phonk": "Phonk 💀",
    "trap": "Trap ⚡",
    "boombap": "Boom Bap 🥁",
    "other": "Другое 📦"
}

def get_welcome_text(user_name):
    return (
        f"Привет, {user_name}! 👋\n\n"
        f"🔥 <b>Я твой музыкальный помощник!</b>\n"
        f"Я помогу тебе найти лучший стафф для творчества. "
        f"Вот что у меня есть:\n\n"
        f"🎹 <b>Драм киты</b> — рассортированы по жанрам.\n"
        f"🔌 <b>Плагины</b> — VST синтезаторы и эффекты.\n"
        f"🎚 <b>DAW</b> — программы для написания музыки.\n\n"
        f"Выбирай нужный раздел ниже и приступай! 👇"
    )

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS items 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       name TEXT, link_google TEXT, link_yandex TEXT,
                       file_id TEXT, type TEXT, description TEXT, photo_id TEXT,
                       subcategory TEXT DEFAULT NULL)''')
    try:
        cursor.execute("ALTER TABLE items ADD COLUMN subcategory TEXT DEFAULT NULL")
    except:
        pass
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
    conn.commit()
    conn.close()

def add_user_to_db(user_id):
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

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
    waiting_for_file = State()       # Шаг 1: Файл напрямую
    waiting_for_google = State()     # Шаг 2: Google диск
    waiting_for_yandex = State()     # Шаг 3: Яндекс диск
    waiting_for_desc = State()
    waiting_for_photo = State()
    waiting_for_post = State()

# --- ИНИЦИАЛИЗАЦИЯ ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- КЛАВИАТУРЫ ---
def main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🎹 Драм киты", callback_data="drumkit_genres"))
    builder.row(types.InlineKeyboardButton(text="🔌 Плагины", callback_data="list_plugin_0"))
    builder.row(types.InlineKeyboardButton(text="🎚 DAW", callback_data="list_daw_0"))
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
        types.BotCommand(command="start", description="🏠 Главное меню"),
        types.BotCommand(command="admin", description="🛠️ Панель администратора"),
        types.BotCommand(command="post", description="📢 Сделать рассылку")
    ]
    await bot.set_my_commands(commands)

# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    add_user_to_db(message.from_user.id)
    text = get_welcome_text(message.from_user.first_name)
    try:
        photo = FSInputFile(START_PHOTO_PATH)
        await message.answer_photo(photo, caption=text, parse_mode="HTML", reply_markup=main_menu())
    except:
        await message.answer(text, parse_mode="HTML", reply_markup=main_menu())

@dp.callback_query(F.data == "main_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await callback.message.delete()
    text = get_welcome_text(callback.from_user.first_name)
    try:
        photo = FSInputFile(START_PHOTO_PATH)
        await callback.message.answer_photo(photo, caption=text, parse_mode="HTML", reply_markup=main_menu())
    except:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=main_menu())

@dp.callback_query(F.data == "drumkit_genres")
async def show_drumkit_genres(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    for key, name in DRUMKIT_GENRES.items():
        builder.row(types.InlineKeyboardButton(text=name, callback_data=f"list_drumkit_{key}_0"))
    builder.row(types.InlineKeyboardButton(text="🏠 Назад", callback_data="main_menu"))
    await callback.message.delete()
    await callback.message.answer("Какой драм-кит хотите скачать? Выберите жанр:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("list_"))
async def show_list(callback: types.CallbackQuery):
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
        await callback.answer("Здесь пока ничего нет", show_alert=True)
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
        builder.row(types.InlineKeyboardButton(text="⬅️ К жанрам", callback_data="drumkit_genres"))
    else:
        builder.row(types.InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"))
        
    await callback.message.delete()
    cat_name = DRUMKIT_GENRES.get(subcategory) if subcategory else item_type.upper()
    await callback.message.answer(f"Категория: {cat_name}", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("view_"))
async def view_item(callback: types.CallbackQuery):
    _, item_id, page = callback.data.split("_")
    item_id, page = int(item_id), int(page)
    item = get_item_by_id(item_id)
    if not item: return
    name, g_link, y_link, f_id, desc, p_id, i_type, subcategory = item
    
    caption = f"<b>{name}</b>\n\n{desc or ''}"
    builder = InlineKeyboardBuilder()
    
    # Кнопки скачивания — отображаются только те, что не пустые
    if f_id: builder.row(types.InlineKeyboardButton(text="📥 Скачать напрямую", callback_data=f"dl_{item_id}"))
    if g_link: builder.row(types.InlineKeyboardButton(text="🟢 Google Drive", url=g_link))
    if y_link: builder.row(types.InlineKeyboardButton(text="🔴 Yandex Disk", url=y_link))
    
    if callback.from_user.id == ADMIN_ID:
        builder.row(
            types.InlineKeyboardButton(text="✏️ Изменить", callback_data=f"adm_edit_{item_id}"),
            types.InlineKeyboardButton(text="🗑 Удалить", callback_data=f"adm_del_{item_id}")
        )
    
    if i_type == "drumkit" and subcategory:
        builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"list_drumkit_{subcategory}_{page}"))
    else:
        builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"list_{i_type}_{page}"))

    await callback.message.delete()
    if p_id:
        await callback.message.answer_photo(p_id, caption=caption, parse_mode="HTML", reply_markup=builder.as_markup())
    else:
        await callback.message.answer(caption, parse_mode="HTML", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("dl_"))
async def download_file(callback: types.CallbackQuery):
    item_id = int(callback.data.split("_")[1])
    item = get_item_by_id(item_id)
    await callback.answer("Отправляю файл...")
    await callback.message.answer_document(item[3])

# --- АДМИНКА ---

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
        except:
            pass
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
        for key, name in DRUMKIT_GENRES.items():
            builder.row(types.InlineKeyboardButton(text=name, callback_data=f"admin_genre_{key}"))
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
    await callback.message.answer(f"Введите название ({DRUMKIT_GENRES[genre]}):")
    await state.set_state(AdminStates.waiting_for_name)

# --- НОВАЯ СЕКЦИЯ ДОБАВЛЕНИЯ ФАЙЛОВ / ССЫЛОК ---

@dp.message(AdminStates.waiting_for_name)
async def adm_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📁 Шаг 1/3: Отправь ФАЙЛ (документ) напрямую боту (или напиши /skip чтобы пропустить этот шаг):")
    await state.set_state(AdminStates.waiting_for_file)

@dp.message(AdminStates.waiting_for_file)
async def adm_file(message: types.Message, state: FSMContext):
    if message.text == "/skip":
        await state.update_data(file_id=None)
    elif message.document:
        await state.update_data(file_id=message.document.file_id)
    else:
        await message.answer("⚠️ Пожалуйста, отправь именно ФАЙЛ (как документ) или введи /skip:")
        return
        
    await message.answer("🟢 Шаг 2/3: Отправь ссылку на Google Drive (или /skip):")
    await state.set_state(AdminStates.waiting_for_google)

@dp.message(AdminStates.waiting_for_google)
async def adm_google(message: types.Message, state: FSMContext):
    link = None if message.text == "/skip" else message.text
    await state.update_data(link_google=link)
    await message.answer("🔴 Шаг 3/3: Отправь ссылку на Яндекс Диск (или /skip):")
    await state.set_state(AdminStates.waiting_for_yandex)

@dp.message(AdminStates.waiting_for_yandex)
async def adm_yandex(message: types.Message, state: FSMContext):
    link = None if message.text == "/skip" else message.text
    await state.update_data(link_yandex=link)
    await message.answer("📝 Введи описание (или /skip):")
    await state.set_state(AdminStates.waiting_for_desc)

@dp.message(AdminStates.waiting_for_desc)
async def adm_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc="" if message.text == "/skip" else message.text)
    await message.answer("🖼️ Отправь превью-картинку для этого товара (или /skip):")
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
