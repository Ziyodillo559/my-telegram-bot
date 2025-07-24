import asyncio
import aiosqlite

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton, InlineKeyboardMarkup

from aiogram.client.default import DefaultBotProperties

# 🔷 Config
TOKEN = "8144692354:AAE2rVgqS88IPWdBQih12IqsE0qz7HCLY_I"
CARD_NUMBER = "9860 1606 2312 1748" 
ADMIN_ID = 7664675013  # Admin Telegram ID

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# 🔷 FSM
class OrderFSM(StatesGroup):
    waiting_for_target_user = State()
    waiting_for_battle_link = State()


# 🔷 Database
async def init_db():
    async with aiosqlite.connect("orders.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                sum INTEGER,
                status TEXT,
                target_user TEXT,
                file_id TEXT,
                file_type TEXT,
                order_type TEXT
            )
        """)
        await db.commit()


# 🔷 Keyboards
def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⭐ Yulduz sotib olish", callback_data="buy_stars")
    kb.button(text="🎁 Gift sotib olish", callback_data="buy_gift")
    kb.button(text="🪖 Battle uchun", callback_data="buy_battle")
    kb.adjust(1)
    return kb.as_markup()


def stars_keyboard(order_type: str, page: int = 1) -> InlineKeyboardMarkup:
    amounts = {
        "stars": list(range(50, 5001, 50)),
        "battle": list(range(5, 101, 2)),
    }[order_type]
    price_per_star = 13000 / 50 if order_type == "stars" else 240

    per_page = 10
    total_pages = (len(amounts) + per_page - 1) // per_page
    page = max(1, min(page, total_pages))
    start, end = (page-1)*per_page, page*per_page

    kb = InlineKeyboardBuilder()
    for amount in amounts[start:end]:
        som = int(amount * price_per_star)
        kb.button(text=f"{amount}⭐ - {som:,} so‘m", callback_data=f"{order_type}_{amount}")
    kb.adjust(2)

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"{order_type}_page_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"{order_type}_page_{page+1}"))

    markup = kb.as_markup()
    if nav:
        markup.inline_keyboard.append(nav)
    return markup


def gifts_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    gifts = [
        (15, "🧸"), (15, "💝"),
        (25, "🌹"), (25, "🎁"),
        (50, "💐"), (50, "🎂"),
        (100, "💎"), (100, "💍"),
    ]
    for amount, emoji in gifts:
        kb.button(text=f"{amount}⭐ {emoji}", callback_data=f"gift_{amount}_{emoji}")
    kb.adjust(1)
    return kb.as_markup()


def admin_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{order_id}"),
            InlineKeyboardButton(text="🚫 Rad etish", callback_data=f"reject_{order_id}")
        ]
    ])


# 🔷 Handlers

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Kerakli bo‘limni tanlang va starslar sotib oling!", reply_markup=main_menu())


@dp.callback_query(F.data == "buy_stars")
async def stars(callback: types.CallbackQuery):
    await callback.message.edit_text("⭐ Miqdorni tanlang:", reply_markup=stars_keyboard("stars"))
    await callback.answer()


@dp.callback_query(F.data == "buy_battle")
async def battle(callback: types.CallbackQuery):
    await callback.message.edit_text("🪖 Miqdorni tanlang:", reply_markup=stars_keyboard("battle"))
    await callback.answer()


@dp.callback_query(F.data == "buy_gift")
async def gift(callback: types.CallbackQuery):
    await callback.message.edit_text("🎁 Gift tanlang:", reply_markup=gifts_keyboard())
    await callback.answer()


@dp.callback_query(F.data.regexp(r"^(stars|battle)_page_\d+$"))
async def paginate(callback: types.CallbackQuery):
    order_type, _, page = callback.data.partition("_page_")
    await callback.message.edit_reply_markup(reply_markup=stars_keyboard(order_type, int(page)))
    await callback.answer()


@dp.callback_query(F.data.regexp(r"^(stars|battle)_\d+$"))
async def select_stars_or_battle(callback: types.CallbackQuery):
    order_type, amount = callback.data.split("_")
    amount = int(amount)
    price = int((amount/50)*13000) if order_type == "stars" else int(amount*240)

    await callback.message.answer(
        f"✅ {amount}⭐ tanladingiz.\n"
        f"💰 {price:,} so‘m\n\n"
        f"💳 Karta: <code>{CARD_NUMBER}</code>\n\n"
        f"Chekni yuboring chek tekshiriladi va stars va giftlar yuboriladi!."
    )

    async with aiosqlite.connect("orders.db") as db:
        await db.execute(
            "INSERT INTO orders (user_id, amount, sum, status, order_type) VALUES (?, ?, ?, 'pending', ?)",
            (callback.from_user.id, amount, price, order_type)
        )
        await db.commit()

    await callback.answer()


@dp.callback_query(F.data.regexp(r"^gift_\d+_.+"))
async def select_gift(callback: types.CallbackQuery):
    _, amount, emoji = callback.data.split("_", 2)
    amount = int(amount)
    price = int((amount/50)*13000)

    await callback.message.answer(
        f"✅ {amount}⭐ {emoji} tanladingiz.\n"
        f"💰 {price:,} so‘m\n\n"
        f"💳 Karta: <code>{CARD_NUMBER}</code>\n\n"
        f"Chekni yuboring chek tekshiriladi va stars va giftlar yuboriladi!."
    )

    async with aiosqlite.connect("orders.db") as db:
        await db.execute(
            "INSERT INTO orders (user_id, amount, sum, status, order_type) VALUES (?, ?, ?, 'pending', 'gift')",
            (callback.from_user.id, amount, price)
        )
        await db.commit()

    await callback.answer()


@dp.message(F.content_type.in_({"photo", "document"}))
async def receive_receipt(message: types.Message, state: FSMContext):
    async with aiosqlite.connect("orders.db") as db:
        row = await db.execute(
            "SELECT id, order_type FROM orders WHERE user_id=? AND status='pending' ORDER BY id DESC LIMIT 1",
            (message.from_user.id,))
        order = await row.fetchone()

    if not order:
        await message.reply("⛔ Avval buyurtma qiling.")
        return

    order_id, order_type = order
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    file_type = "photo" if message.photo else "document"

    async with aiosqlite.connect("orders.db") as db:
        await db.execute("UPDATE orders SET file_id=?, file_type=? WHERE id=?", (file_id, file_type, order_id))
        await db.commit()

    await state.update_data(order_id=order_id)

    if order_type == "battle":
        await state.set_state(OrderFSM.waiting_for_battle_link)
        await message.answer("🔗 Battle linkini yuboring.")
    else:
        await state.set_state(OrderFSM.waiting_for_target_user)
        await message.answer("🎯 Target userni yuboring yani qaysi user uchun yuboriladi @.")


@dp.message(OrderFSM.waiting_for_target_user)
async def target_user(message: types.Message, state: FSMContext):
    await send_to_admin(message, state, "🎯 Target")
    await message.answer("✅ Ma’lumotlar yuborildi iltimos sabr qling.")
    await state.clear()


@dp.message(OrderFSM.waiting_for_battle_link)
async def battle_link(message: types.Message, state: FSMContext):
    await send_to_admin(message, state, "🔗 Battle")
    await message.answer("✅ Ma’lumotlar yuborildi iltimo sabr qiling.")
    await state.clear()


async def send_to_admin(message: types.Message, state: FSMContext, label: str):
    data = await state.get_data()
    order_id = data["order_id"]

    async with aiosqlite.connect("orders.db") as db:
        await db.execute("UPDATE orders SET target_user=? WHERE id=?", (message.text, order_id))
        row = await db.execute("SELECT file_id, file_type FROM orders WHERE id=?", (order_id,))
        file_id, file_type = await row.fetchone()
        await db.commit()

    caption = (
        f"📥 Yangi buyurtma\n"
        f"ID: {order_id}\n"
        f"👤 User: <code>{message.from_user.id}</code>\n"
        f"{label}: {message.text}"
    )

    if file_type == "photo":
        await bot.send_photo(ADMIN_ID, file_id, caption=caption, reply_markup=admin_kb(order_id))
    else:
        await bot.send_document(ADMIN_ID, file_id, caption=caption, reply_markup=admin_kb(order_id))


@dp.callback_query(F.data.regexp(r"approve_\d+"))
async def approve(callback: types.CallbackQuery):
    await update_order(callback, "approved", "✅ Buyurtmangiz tasdiqlandi stars muvaffaqiyat yetkzildi tekshiring .")


@dp.callback_query(F.data.regexp(r"reject_\d+"))
async def reject(callback: types.CallbackQuery):
    await update_order(callback, "rejected", "🚫 Buyurtmangiz rad etildi chunki chek soxta!.")


async def update_order(callback: types.CallbackQuery, status: str, message_text: str):
    order_id = int(callback.data.split("_")[1])

    async with aiosqlite.connect("orders.db") as db:
        await db.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
        row = await db.execute("SELECT user_id FROM orders WHERE id=?", (order_id,))
        user_id = (await row.fetchone())[0]
        await db.commit()

    await bot.send_message(user_id, message_text)
    await callback.answer()


# 🔷 Main
async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
