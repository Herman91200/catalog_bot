# main.py
# Основной код бота: команды админа, каталог, оформление заказа.
# При заказе бот НЕ спрашивает имя и телефон —
# берёт @username из Telegram или просит ввести контакт вручную.

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import BOT_TOKEN, CHANNEL_ID, ADMIN_ID, LOG_PATH
import database as db


# ---------- Логирование ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# ---------- FSM: состояния диалогов ----------
class AddItem(StatesGroup):
    """Состояния при добавлении товара админом."""
    waiting_name = State()
    waiting_description = State()
    waiting_price = State()
    waiting_photo = State()


class BuyItem(StatesGroup):
    """Состояния при оформлении заказа клиентом."""
    waiting_username = State()   # ждём username, если его нет в Telegram


# ---------- Проверка админа ----------
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ---------- /start ----------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    if is_admin(message.from_user.id):
        await message.answer(
            "👑 <b>Привет, админ!</b>\n\n"
            "<b>Управление каталогом:</b>\n"
            "/add_item — добавить товар\n"
            "/list_items — список товаров\n"
            "/delete_item [id] — удалить товар\n\n"
            "<b>Для клиентов:</b>\n"
            "/catalog — открыть каталог\n"
        )
    else:
        await message.answer(
            "👋 Привет!\n\n"
            "Я — каталог товаров. Нажми /catalog, чтобы посмотреть, "
            "что у нас есть.\n\n"
            "Выбирай товар → жми «Купить» — мы свяжемся с тобой в Telegram."
        )


# =========================================================
#                     АДМИН: ТОВАРЫ
# =========================================================

# ---------- /add_item ----------
@dp.message(Command("add_item"))
async def cmd_add_item(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AddItem.waiting_name)
    await message.answer("✏️ Введи <b>название</b> товара:")


@dp.message(AddItem.waiting_name)
async def add_item_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddItem.waiting_description)
    await message.answer("📝 Введи <b>описание</b> товара:")


@dp.message(AddItem.waiting_description)
async def add_item_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(AddItem.waiting_price)
    await message.answer("💰 Введи <b>цену</b> (например, 1500 ₽):")


@dp.message(AddItem.waiting_price)
async def add_item_price(message: Message, state: FSMContext):
    await state.update_data(price=message.text.strip())
    await state.set_state(AddItem.waiting_photo)
    await message.answer(
        "🖼 Пришли <b>фото</b> товара — или напиши <b>нет</b>, если фото нет:"
    )


@dp.message(AddItem.waiting_photo)
async def add_item_photo(message: Message, state: FSMContext):
    # Если фото — сохраняем file_id. Если «нет» — пусто.
    if message.photo:
        photo_url = message.photo[-1].file_id
    elif message.text and message.text.strip().lower() in ("нет", "no", "-"):
        photo_url = None
    else:
        await message.answer("⚠️ Пришли фото или напиши <b>нет</b>:")
        return

    data = await state.get_data()
    item_id = await db.add_item(
        name=data["name"],
        description=data["description"],
        price=data["price"],
        photo_url=photo_url,
    )
    await state.clear()
    await message.answer(
        f"✅ Товар добавлен!\n\n"
        f"ID: <b>{item_id}</b>\n"
        f"Название: <b>{data['name']}</b>\n"
        f"Цена: <b>{data['price']}</b>"
    )
    logger.info(f"Добавлен товар ID={item_id}: {data['name']}")


# ---------- /list_items ----------
@dp.message(Command("list_items"))
async def cmd_list_items(message: Message):
    if not is_admin(message.from_user.id):
        return
    items = await db.get_all_items()
    if not items:
        await message.answer("📭 Каталог пуст. Добавь товар через /add_item.")
        return

    lines = ["📋 <b>Товары в каталоге:</b>\n"]
    for item_id, name, _, price, photo in items:
        img = "🖼" if photo else "—"
        lines.append(f"<b>ID {item_id}</b> | {name} | {price} | {img}")
    await message.answer("\n".join(lines))


# ---------- /delete_item ----------
@dp.message(Command("delete_item"))
async def cmd_delete_item(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: <code>/delete_item ID</code>")
        return
    item_id = int(parts[1])
    deleted = await db.delete_item(item_id)
    if deleted:
        await message.answer(f"🗑 Товар ID {item_id} удалён.")
        logger.info(f"Удалён товар ID={item_id}")
    else:
        await message.answer(f"❌ Товар ID {item_id} не найден.")


# =========================================================
#                     КЛИЕНТ: КАТАЛОГ
# =========================================================

# ---------- /catalog ----------
@dp.message(Command("catalog"))
async def cmd_catalog(message: Message):
    items = await db.get_all_items()
    if not items:
        await message.answer("📭 Каталог пока пуст.")
        return

    # Кнопки по 1 в ряд: «Название — Цена»
    buttons = []
    for item_id, name, _, price, _ in items:
        buttons.append([
            InlineKeyboardButton(
                text=f"{name} — {price}",
                callback_data=f"item:{item_id}",
            )
        ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer("🛒 <b>Наш каталог:</b>\nВыбери товар:", reply_markup=keyboard)


# ---------- Показ товара ----------
@dp.callback_query(F.data.startswith("item:"))
async def show_item(callback: CallbackQuery):
    item_id = int(callback.data.split(":")[1])
    item = await db.get_item(item_id)
    if not item:
        await callback.answer("Товар не найден", show_alert=True)
        return

    _, name, description, price, photo_url = item

    text = (
        f"<b>{name}</b>\n\n"
        f"{description}\n\n"
        f"💰 Цена: <b>{price}</b>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Купить", callback_data=f"buy:{item_id}")],
        [InlineKeyboardButton(text="◀️ Назад в каталог", callback_data="back_catalog")],
    ])

    try:
        if photo_url:
            await callback.message.answer_photo(
                photo=photo_url, caption=text, reply_markup=keyboard
            )
        else:
            await callback.message.answer(text=text, reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка показа товара {item_id}: {e}")
        await callback.answer("Ошибка показа", show_alert=True)


# ---------- Назад в каталог ----------
@dp.callback_query(F.data == "back_catalog")
async def back_to_catalog(callback: CallbackQuery):
    items = await db.get_all_items()
    if not items:
        await callback.message.answer("📭 Каталог пуст.")
        await callback.answer()
        return

    buttons = [
        [InlineKeyboardButton(text=f"{name} — {price}", callback_data=f"item:{item_id}")]
        for item_id, name, _, price, _ in items
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    try:
        await callback.message.answer("🛒 <b>Наш каталог:</b>\nВыбери товар:", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка возврата в каталог: {e}")
    await callback.answer()


# ---------- Кнопка «Купить» ----------
@dp.callback_query(F.data.startswith("buy:"))
async def buy_item(callback: CallbackQuery, state: FSMContext):
    item_id = int(callback.data.split(":")[1])
    item = await db.get_item(item_id)
    if not item:
        await callback.answer("Товар не найден", show_alert=True)
        return

    # Запоминаем, какой товар покупают
    await state.update_data(item_id=item_id)

    # Если у клиента есть username в Telegram — сразу оформляем заказ.
    tg_username = callback.from_user.username
    if tg_username:
        await state.update_data(client_username=f"@{tg_username}")
        await callback.answer()
        await finalize_order(callback.message, state)
    else:
        # Username нет — просим ввести
        await state.set_state(BuyItem.waiting_username)
        await callback.message.answer(
            f"🛒 Оформляем заказ: <b>{item[1]}</b>\n\n"
            "У тебя не установлен username в Telegram.\n"
            "Напиши свой <b>юзернейм</b> (например, <code>@ivan_petrov</code>) "
            "или другой контакт для связи:"
        )
        await callback.answer()


# ---------- Ввод username вручную ----------
@dp.message(BuyItem.waiting_username)
async def buy_username(message: Message, state: FSMContext):
    """Клиент вводит username вручную (если не установлен в Telegram)."""
    username = message.text.strip()

    # Минимальная проверка
    if not username or len(username) > 64:
        await message.answer("⚠️ Введи корректный юзернейм или контакт:")
        return

    # Добавляем @, если это не телефон и не email
    is_phone = username.replace("+", "").replace("-", "").replace(" ", "").isdigit()
    is_email = "@" in username and "." in username
    if not is_phone and not is_email and not username.startswith("@"):
        username = "@" + username.lstrip("@")

    await state.update_data(client_username=username)

    # Сразу отправляем заявку — без дополнительных вопросов
    await finalize_order(message, state)


# ---------- Финальная отправка заявки ----------
async def finalize_order(message: Message, state: FSMContext):
    """Отправляет заявку админу и подтверждение клиенту."""
    data = await state.get_data()
    item_id = data.get("item_id")
    client_username = data.get("client_username")

    if not item_id or not client_username:
        await state.clear()
        await message.answer("❌ Что-то пошло не так. Попробуй снова через /catalog.")
        return

    item = await db.get_item(item_id)
    if not item:
        await state.clear()
        await message.answer("❌ Товар больше не доступен.")
        return

    _, name, _, price, _ = item

    # Сохраняем заявку (поле client_phone оставляем пустым, чтобы не ломать БД)
    order_id = await db.add_order(
        item_id=item_id,
        client_name=client_username,
        client_phone="",
    )

    # Отправляем заявку админу
    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🔔 <b>Новый заказ!</b>\n\n"
                f"📦 Товар: <b>{name}</b>\n"
                f"💰 Цена: <b>{price}</b>\n"
                f"💬 Клиент: <b>{client_username}</b>\n\n"
                f"🆔 Заказ №{order_id}"
            ),
        )
    except Exception as e:
        logger.error(f"Не смог отправить заявку админу: {e}")

    await state.clear()
    await message.answer(
        f"✅ Заявка отправлена!\n\n"
        f"Товар: <b>{name}</b>\n"
        f"Мы свяжемся с тобой в Telegram: <b>{client_username}</b>."
    )
    logger.info(f"Новый заказ №{order_id}: {name}, клиент {client_username}")


# ---------- Запуск ----------
async def main():
    await db.init_db()
    logger.info("Бот запущен.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")