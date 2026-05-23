
import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

# --- НАСТРОЙКИ ---
API_TOKEN = '8993580254:AAFylwzSqWGb-kzRHlAgyaiG50o1n4af30o'
ADMIN_ID = 1753037099 
ITEMS_PER_PAGE = 7

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    # Изменили структуру: вместо одной link теперь link_google и link_yandex
    cursor.execute('''CREATE TABLE IF NOT EXISTS items 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       name TEXT, 
                       link_google TEXT, 
                       link_yandex TEXT,
                       file_id TEXT,
                       type TEXT, 
                       description TEXT, 
                       photo_id TEXT)''')
    conn.commit()
    conn.close()

def add_item_to_db(name, link_google, link_yandex, file_id, item_type, description, photo_id):
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO items (name, link_google, link_yandex, file_id, type, description, photo_id) 
                      VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                   (name, link_google, link_yandex, file_id, item_type, description, photo_id))
    conn.commit()
    conn.close()

def get_items_by_type(item_type):
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM items WHERE type = ?", (item_type,))
    items = cursor.fetchall()
    conn.close()
    return items

def get_item_by_id(item_id):
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, link_google, link_yandex, file_id, description, photo_id, type FROM items WHERE id = ?", (item_id,))
    return cursor.fetchone()

# --- СОСТОЯНИЯ ---
class AdminStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_google = State()  # Файл или ссылка на Google
    waiting_for_yandex = State()  # Ссылка на Yandex
    waiting_for_desc = State()
    waiting_for_photo = State()

# --- ИНИЦИАЛИЗАЦИЯ ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- КЛАВИАТУРЫ ---
def main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🎹 Драм киты", callback_data="list_drumkit_0"))
    builder.row(types.InlineKeyboardButton(text="🔌 Плагины", callback_data="list_plugin_0"))
    return builder.as_markup()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(f"Привет, {message.from_user.first_name}! 👋\nВыбирай контент ниже:", reply_markup=main_menu())

@dp.callback_query(F.data == "main_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Выбери категорию:", reply_markup=main_menu())

@dp.callback_query(F.data.startswith("list_"))
async def show_list(callback: types.CallbackQuery):
    data = callback.data.split("_")
    item_type, page = data[1], int(data[2])
    items = get_items_by_type(item_type)
    
    if not items:
        await callback.answer("Пусто...", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    start, end = page * ITEMS_PER_PAGE, (page + 1) * ITEMS_PER_PAGE
    for i_id, name in items[start:end]:
        builder.row(types.InlineKeyboardButton(text=name, callback_data=f"view_{i_id}_{page}"))

    nav = []
    if page > 0: nav.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"list_{item_type}_{page-1}"))
    if end < len(items): nav.append(types.InlineKeyboardButton(text="➡️", callback_data=f"list_{item_type}_{page+1}"))
    builder.row(*nav)
    builder.row(types.InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu"))

    await callback.message.delete()
    await callback.message.answer(f"Список:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("view_"))
async def view_item(callback: types.CallbackQuery):
    data = callback.data.split("_")
    item_id, page = int(data[1]), int(data[2])
    name, link_google, link_yandex, file_id, desc, photo_id, item_type = get_item_by_id(item_id)
    
    caption = f"<b>{name}</b>\n\n{desc or ''}"
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопку скачивания файла, если он есть
    if file_id:
        builder.row(types.InlineKeyboardButton(text="📥 Скачать напрямую", callback_data=f"dl_{item_id}"))
    
    # Добавляем кнопку Google Диска, если ссылка есть
    if link_google:
        builder.row(types.InlineKeyboardButton(text="🟢 Google Диск", url=link_google))
        
    # Добавляем кнопку Яндекс Диска, если ссылка есть
    if link_yandex:
        builder.row(types.InlineKeyboardButton(text="🔴 Яндекс Диск", url=link_yandex))
        
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"list_{item_type}_{page}"))

    await callback.message.delete()
    if photo_id:
        await callback.message.answer_photo(photo_id, caption=caption, parse_mode="HTML", reply_markup=builder.as_markup())
    else:
        await callback.message.answer(caption, parse_mode="HTML", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("dl_"))
async def download_file(callback: types.CallbackQuery):
    item_id = int(callback.data.split("_")[1])
    _, _, _, file_id, _, _, _ = get_item_by_id(item_id)
    await callback.answer("Отправляю файл...")
    await callback.message.answer_document(file_id)

# --- АДМИНКА ---
@dp.message(Command("plugin", "drumkit"))
async def admin_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.update_data(item_type="plugin" if "plugin" in message.text else "drumkit")
    await message.answer("Название?")
    await state.set_state(AdminStates.waiting_for_name)

@dp.message(AdminStates.waiting_for_name)
async def admin_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Отправь ФАЙЛ или ССЫЛКУ на Google Диск (или /skip):")
    await state.set_state(AdminStates.waiting_for_google)

@dp.message(AdminStates.waiting_for_google)
async def admin_google(message: types.Message, state: FSMContext):
    if message.text == "/skip":
        await state.update_data(file_id=None, link_google=None)
    elif message.document:
        await state.update_data(file_id=message.document.file_id, link_google=None)
    else:
        await state.update_data(link_google=message.text, file_id=None)
        
    await message.answer("Отправь ССЫЛКУ на Яндекс Диск (или /skip):")
    await state.set_state(AdminStates.waiting_for_yandex)

@dp.message(AdminStates.waiting_for_yandex)
async def admin_yandex(message: types.Message, state: FSMContext):
    link_yandex = None if message.text == "/skip" else message.text
    await state.update_data(link_yandex=link_yandex)
    
    await message.answer("Описание? (или /skip)")
    await state.set_state(AdminStates.waiting_for_desc)

@dp.message(AdminStates.waiting_for_desc)
async def admin_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc="" if message.text == "/skip" else message.text)
    await message.answer("Фото? (или /skip)")
    await state.set_state(AdminStates.waiting_for_photo)

@dp.message(AdminStates.waiting_for_photo)
async def admin_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id if message.photo else None
    data = await state.get_data()
    
    add_item_to_db(
        name=data['name'], 
        link_google=data.get('link_google'), 
        link_yandex=data.get('link_yandex'), 
        file_id=data.get('file_id'), 
        item_type=data['item_type'], 
        description=data['desc'], 
        photo_id=photo_id
    )
    await message.answer("✅ Добавлено!")
    await state.clear()

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
