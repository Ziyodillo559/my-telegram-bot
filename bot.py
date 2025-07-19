import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8111567992:AAFVVOT55iGvIBS6BQNKtoz25NAZPJOaMIw"
TON_WALLET = "UQB-dqoWUd7ea5c_N3sAvfOUA6-WnjpGIM2fmpaM9ZoQ2bDh" 
CARD_NUMBER = "9860 1606 2312 1748" 
ADMIN_ID = 7664675013  # Admin Telegram ID

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


class OrderFSM(StatesGroup):
    waiting_for_target_user = State()


async def init_db():
    async with aiosqlite.connect("orders.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                ton REAL,
                sum INTEGER,
                status TEXT,
                target_user TEXT,
                file_id TEXT,
                file_type TEXT
            )
        """)
        await db.commit()


def generate_star_keyboard(page=1) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    amounts = list(range(50, 5001, 50))
    per_page = 10
    total_pages = (len(amounts) + per_page - 1) // per_page

    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page

    for amount in amounts[start:end]:
        ton = round((amount / 50) * 0.34, 2)
        sum_so_m = int((amount / 50) * 13000)
        builder.button(
            text=f"{amount}⭐ - {ton}TON / {sum_so_m:,} so‘m",
            callback_data=f"order_{amount}"
        )

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"page_{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"page_{page+1}"))

    builder.adjust(1)
    markup = builder.as_markup()
    if nav_buttons:
        markup.inline_keyboard.append(nav_buttons)

    return markup


def admin_order_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{order_id}"),
            InlineKeyboardButton(text="🚫 Rad etish", callback_data=f"reject_{order_id}")
        ]
    ])


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "⭐ Kerakli stars miqdorini tanlang:",
        reply_markup=generate_star_keyboard(1)
    )


@dp.callback_query(F.data.startswith("page_"))
async def pagination(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[1])
    await callback.message.edit_reply_markup(reply_markup=generate_star_keyboard(page))
    await callback.answer()


@dp.callback_query(F.data.startswith("order_"))
async def stars_selected(callback: types.CallbackQuery):
    amount = int(callback.data.split("_")[1])
    ton_amount = round((amount / 50) * 0.34, 2)
    sum_so_m = int((amount / 50) * 13000)

    await callback.message.answer(
        f"✅ Siz <b>{amount}⭐</b> tanladingiz.\n"

        f"💰 Narx: <b>{ton_amount} TON</b> yoki <b>{sum_so_m:,} so‘m</b>\n\n"

        f"💳 To‘lov uchun:\n\n"

        f"📌 TON Wallet: <code>{TON_WALLET}</code>\n\n"

        f"📌 UzCard/Humo: <code>{CARD_NUMBER}</code>\n\n"

        f"✅ To‘lovni amalga oshirgach, chekni shu yerga yuboring chek soxta bo'lmasa stars yuboriladi!"
    )

    async with aiosqlite.connect("orders.db") as db:
        await db.execute("""
            INSERT INTO orders (user_id, amount, ton, sum, status) VALUES (?, ?, ?, ?, ?)
        """, (callback.from_user.id, amount, ton_amount, sum_so_m, "pending"))
        await db.commit()

    await callback.answer()


@dp.message(F.content_type.in_({"photo", "document"}))
async def handle_receipt(message: types.Message, state: FSMContext):
    async with aiosqlite.connect("orders.db") as db:
        async with db.execute("""
            SELECT id, amount FROM orders 
            WHERE user_id = ? AND status = 'pending' 
            ORDER BY id DESC LIMIT 1
        """, (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()

    if row:
        order_id, amount = row
        file_id = message.photo[-1].file_id if message.photo else message.document.file_id
        file_type = "photo" if message.photo else "document"

        async with aiosqlite.connect("orders.db") as db:
            await db.execute("""
                UPDATE orders SET file_id=?, file_type=? WHERE id=?
            """, (file_id, file_type, order_id))
            await db.commit()

        await state.update_data(order_id=order_id, amount=amount)
        await message.answer("📌 Stars qaysi user uchun yuburiladi iltimos yozib qoldiring @:")
        await state.set_state(OrderFSM.waiting_for_target_user)
    else:
        await message.reply(
            "⛔ Sizda hali buyurtma yo‘q. Iltimos, /start dan boshlang va kerakli yulduz miqdorini tanlang."
        )


@dp.message(OrderFSM.waiting_for_target_user)
async def handle_target_user(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    amount = data["amount"]
    target_user = message.text

    async with aiosqlite.connect("orders.db") as db:
        await db.execute("""
            UPDATE orders SET target_user=? WHERE id=?
        """, (target_user, order_id))
        await db.commit()

        async with db.execute("""
            SELECT file_id, file_type FROM orders WHERE id=?
        """, (order_id,)) as cursor:
            row = await cursor.fetchone()

    file_id, file_type = row

    caption = (
        f"📥 stars tasha o'!\n"
        f"👤 Buyurtmachi: <code>{message.from_user.id}</code>\n"
        f"🆔 Telegram ID: <b>{order_id}</b>\n"
        f"⭐ Miqdori: <b>{amount}</b>\n"
        f"🎯 Stars qabul qiluvchi: <b>{target_user}</b>\n"
        f"✅ Status: odam"
    )

    markup = admin_order_keyboard(order_id)

    if file_type == "photo":
        await bot.send_photo(ADMIN_ID, file_id, caption=caption, reply_markup=markup)
    else:
        await bot.send_document(ADMIN_ID, file_id, caption=caption, reply_markup=markup)

    await message.answer(
        f"✅ Ma’lumot qabul qilindi. Buyurtma ID: <b>{order_id}</b>\n6 soat ichida yulduzlaringiz yetkazib beriladi."
    )
    await state.clear()


@dp.callback_query(F.data.startswith("approve_"))
async def approve_callback(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])

    async with aiosqlite.connect("orders.db") as db:
        await db.execute("""
            UPDATE orders SET status='approved' WHERE id=?
        """, (order_id,))
        await db.commit()

        async with db.execute("""
            SELECT user_id FROM orders WHERE id=?
        """, (order_id,)) as cursor:
            row = await cursor.fetchone()

    if row:
        user_id = row[0]
        await bot.send_message(
            user_id,
            "✅ <b>Yulduzlaringiz yetkazib berildi iltimos tekshiring!</b>\nRahmat!"
        )

        await callback.message.edit_caption(
            callback.message.caption + "\n\n✅ <b>Tasdiqlandi.</b>",
            reply_markup=None
        )

    await callback.answer("✅ Tasdiqlandi")


@dp.callback_query(F.data.startswith("reject_"))
async def reject_callback(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])

    async with aiosqlite.connect("orders.db") as db:
        await db.execute("""
            UPDATE orders SET status='rejected' WHERE id=?
        """, (order_id,))
        await db.commit()

        async with db.execute("""
            SELECT user_id FROM orders WHERE id=?
        """, (order_id,)) as cursor:
            row = await cursor.fetchone()

    if row:
        user_id = row[0]
        await bot.send_message(
            user_id,
            "🚫 <b>Chekingiz tasdiqlanmadi.</b>\nChekingiz soxta bo‘lishi mumkin. Iltimos, tekshirib qayta urinib ko‘ring. Agar xatolik bo'lsa @ikromjonovv_15"
        )

        await callback.message.edit_caption(
            callback.message.caption + "\n\n🚫 <b>Rad etildi.</b>",
            reply_markup=None
        )

    await callback.answer("🚫 Rad etildi")


async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
