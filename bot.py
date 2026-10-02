import asyncio
import html
import logging
import os
import re
import aiosqlite

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    FSInputFile
)

# ----------------- الإعدادات والمجموعات -----------------

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError(
        "⚠️ لم يتم العثور على BOT_TOKEN في متغيرات البيئة! "
        "يرجى تعيينه أولاً."
    )

ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

CHANNEL_ID = -1004492385043
CHANNEL_LINK = "https://t.me/SyriaStore_ch"

GROUPS = {
    "wallet": -1003984372814,
    "balance": -1003745247353,
    "games": -1004426615112,
    "accounts": -1003985654158,
    "social": -1004411774893,
    "support": -1004420804667
}

ALL_ADMIN_GROUPS = list(GROUPS.values())

SHAM_NAME = "سكينه حمود طه"
SHAM_ADDR = "be03739e320f3dfd318a1a7faebae16a"

QR_IMAGE_PATH = "qr_sham.jpg"
DB_PATH = "bot_store.db"

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher(
    storage=MemoryStorage()
)


# ----------------- إدارة قاعدة البيانات -----------------

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.0,
            is_vip INTEGER DEFAULT 0
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            val REAL
        )
        """)

        await db.execute("""
        INSERT OR IGNORE INTO settings (key, val)
        VALUES ('dollar_rate', 150.0)
        """)

        await db.execute("""
        INSERT OR IGNORE INTO settings (key, val)
        VALUES ('num_whatsapp', 400.0)
        """)

        await db.execute("""
        INSERT OR IGNORE INTO settings (key, val)
        VALUES ('num_telegram', 300.0)
        """)

        await db.commit()


async def get_user(user_id: int, username: str = ""):

    async with aiosqlite.connect(DB_PATH) as db:

        cursor = await db.execute(
            """
            SELECT user_id, username, balance, is_vip
            FROM users
            WHERE user_id=?
            """,
            (user_id,)
        )

        row = await cursor.fetchone()

        if not row:

            await db.execute(
                """
                INSERT INTO users
                (user_id, username, balance, is_vip)
                VALUES (?, ?, 0.0, 0)
                """,
                (user_id, username)
            )

            await db.commit()

            return (
                user_id,
                username,
                0.0,
                0
            )

        # تحديث اسم المستخدم إذا تغيّر
        if username and row[1] != username:

            await db.execute(
                """
                UPDATE users
                SET username=?
                WHERE user_id=?
                """,
                (username, user_id)
            )

            await db.commit()

            row = (
                row[0],
                username,
                row[2],
                row[3]
            )

        return row


async def add_user_balance(
    user_id: int,
    amount: float,
    set_vip: bool = False
):

    if amount <= 0:
        return False

    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute(
            """
            INSERT OR IGNORE INTO users
            (user_id, username, balance, is_vip)
            VALUES (?, '', 0.0, 0)
            """,
            (user_id,)
        )

        if set_vip:

            await db.execute(
                """
                UPDATE users
                SET balance = balance + ?,
                    is_vip = 1
                WHERE user_id=?
                """,
                (amount, user_id)
            )

        else:

            await db.execute(
                """
                UPDATE users
                SET balance = balance + ?
                WHERE user_id=?
                """,
                (amount, user_id)
            )

        await db.commit()

    return True


async def try_deduct_balance(
    user_id: int,
    amount: float
):

    if amount <= 0:
        return False

    async with aiosqlite.connect(DB_PATH) as db:

        cursor = await db.execute(
            """
            UPDATE users
            SET balance = balance - ?
            WHERE user_id=?
            AND balance >= ?
            """,
            (
                amount,
                user_id,
                amount
            )
        )

        await db.commit()

        return cursor.rowcount == 1


async def get_setting(
    key: str,
    default: float = 0.0
):

    async with aiosqlite.connect(DB_PATH) as db:

        cursor = await db.execute(
            """
            SELECT val
            FROM settings
            WHERE key=?
            """,
            (key,)
        )

        row = await cursor.fetchone()

        if row is None:
            return default

        return float(row[0])


async def update_setting(
    key: str,
    value: float
):

    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute(
            """
            INSERT INTO settings (key, val)
            VALUES (?, ?)
            ON CONFLICT(key)
            DO UPDATE SET val=excluded.val
            """,
            (key, value)
        )

        await db.commit()


# ----------------- لوحة المفاتيح -----------------

def persistent_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📋 القائمة الرئيسية"
                )
            ]
        ],
        resize_keyboard=True
    )


# ----------------- التحقق من الاشتراك -----------------

async def is_subscribed(user_id: int):

    try:

        member = await bot.get_chat_member(
            CHANNEL_ID,
            user_id
        )

        status = getattr(
            member.status,
            "value",
            str(member.status)
        )

        if status in (
            "creator",
            "administrator",
            "member"
        ):
            return True

        if status == "restricted":
            return bool(
                getattr(
                    member,
                    "is_member",
                    False
                )
            )

        return False

    except Exception as e:

        logging.error(
            "Subscription check failed: %s",
            e
        )

        # لا نتجاوز شرط الاشتراك عند حدوث خطأ
        return False


# ----------------- التحقق من صلاحيات الإدارة -----------------

def is_admin_or_group(
    user_id: int,
    chat_id: int
):

    return (
        user_id == ADMIN_ID
        or chat_id in ALL_ADMIN_GROUPS
    )


# ----------------- القائمة الرئيسية -----------------

async def main_menu_text_and_kb(
    user_id: int,
    username: str = ""
):

    user = await get_user(
        user_id,
        username
    )

    balance = user[2]
    vip = user[3]

    vip_text = "🌟 VIP" if vip else "👤 عادي"

    text = (
        "🛍 <b>مرحباً بك في متجر الخدمات الرقمية</b>\n\n"
        f"👤 الحالة: <b>{vip_text}</b>\n"
        f"💳 رصيد المحفظة: "
        f"<b>{balance:,.2f} ل.س</b>\n\n"
        "اختر الخدمة المطلوبة:"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 المحفظة والشحن",
                    callback_data="sec_wallet"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📱 الرصيد والكاش",
                    callback_data="sec_balance"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎮 شحن الألعاب",
                    callback_data="sec_games"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 تطبيقات الشات",
                    callback_data="sec_chat"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👤 الحسابات والاشتراكات",
                    callback_data="sec_accounts"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 السوشيال ميديا والإعلانات",
                    callback_data="sec_social"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📞 أرقام التفعيل",
                    callback_data="sec_numbers"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎧 الدعم الفني",
                    callback_data="sec_support"
                )
            ]
        ]
    )

    return text, kb


# ----------------- /start -----------------

@dp.message(CommandStart())
async def start_command(
    message: types.Message,
    state: FSMContext
):

    await state.clear()

    user_id = message.from_user.id
    username = message.from_user.username or ""

    await get_user(
        user_id,
        username
    )

    if not await is_subscribed(user_id):

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📢 الاشتراك بالقناة",
                        url=CHANNEL_LINK
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✅ تحقق من الاشتراك",
                        callback_data="check_sub"
                    )
                ]
            ]
        )

        await message.answer(
            "🔒 <b>للدخول إلى البوت يجب الاشتراك بالقناة أولاً.</b>\n\n"
            "بعد الاشتراك اضغط على «تحقق من الاشتراك».",
            reply_markup=kb
        )

        return

    text, menu_kb = await main_menu_text_and_kb(
        user_id,
        username
    )

    await message.answer(
        text,
        reply_markup=menu_kb
    )

    await message.answer(
        "📋 يمكنك استخدام هذا الزر للعودة إلى القائمة الرئيسية في أي وقت.",
        reply_markup=persistent_keyboard()
    )


@dp.callback_query(F.data == "check_sub")
async def check_subscription_callback(
    cb: types.CallbackQuery
):

    if not await is_subscribed(
        cb.from_user.id
    ):

        await cb.answer(
            "❌ لم يتم العثور على اشتراكك بعد.",
            show_alert=True
        )

        return

    text, menu_kb = await main_menu_text_and_kb(
        cb.from_user.id,
        cb.from_user.username or ""
    )

    try:
        await cb.message.edit_text(
            text,
            reply_markup=menu_kb
        )
    except Exception:
        await cb.message.answer(
            text,
            reply_markup=menu_kb
        )

    await cb.answer(
        "✅ تم التحقق بنجاح."
    )


@dp.message(F.text == "📋 القائمة الرئيسية")
async def persistent_main_menu(
    message: types.Message,
    state: FSMContext
):

    await state.clear()

    if not await is_subscribed(
        message.from_user.id
    ):

        await message.answer(
            "🔒 يجب الاشتراك بالقناة أولاً."
        )

        return

    text, menu_kb = await main_menu_text_and_kb(
        message.from_user.id,
        message.from_user.username or ""
    )

    await message.answer(
        text,
        reply_markup=menu_kb
    )


@dp.callback_query(F.data == "back_main")
async def back_to_main(
    cb: types.CallbackQuery,
    state: FSMContext
):

    await state.clear()

    text, menu_kb = await main_menu_text_and_kb(
        cb.from_user.id,
        cb.from_user.username or ""
    )

    try:

        await cb.message.edit_text(
            text,
            reply_markup=menu_kb
        )

    except Exception:

        await cb.message.answer(
            text,
            reply_markup=menu_kb
        )

    await cb.answer()


# ----------------- حالات الطلبات -----------------

class OrderState(StatesGroup):

    wallet_deposit_amt = State()
    wallet_deposit_receipt = State()

    waiting_receipt = State()

    syr_units_phone = State()
    mtn_units_phone = State()

    syr_station_code = State()
    syr_station_gov = State()

    mtn_station_code = State()
    mtn_station_num = State()
    mtn_station_gov = State()

    syr_invoice_num = State()
    syr_invoice_amt = State()

    mtn_invoice_num = State()
    mtn_invoice_amt = State()

    syr_cash_amt = State()
    syr_cash_id = State()

    mtn_cash_amt = State()
    mtn_cash_num = State()

    entering_game_data = State()

    entering_chat_qty = State()

    entering_social_link = State()

    entering_ad_phone = State()
    entering_custom_ad_days = State()

    support_ticket = State()


class QuoteState(StatesGroup):

    entering_quote_text = State()


# ----------------- البيانات الأساسية للخدمات -----------------

GOVERNORATES = [
    "دمشق",
    "ريف دمشق",
    "حمص",
    "حماة",
    "اللاذقية",
    "طرطوس",
    "حلب",
    "إدلب",
    "درعا",
    "السويداء",
    "القنيطرة",
    "دير الزور",
    "الرقة",
    "الحسكة"
]


SYR_UNITS = [
    ("500 وحدة", 600),
    ("1000 وحدة", 1100),
    ("2000 وحدة", 2100),
    ("5000 وحدة", 5200)
]


MTN_UNITS = [
    ("500 وحدة", 600),
    ("1000 وحدة", 1100),
    ("2000 وحدة", 2100),
    ("5000 وحدة", 5200)
]


STATION_VALS = [
    (10000, 10500),
    (25000, 26250),
    (50000, 52500),
    (100000, 105000)
]


GAME_PACKS = {
    "pubg": [
        ("60 UC", 0.82),
        ("120 UC", 1.64),
        ("180 UC", 2.46),
        ("325 UC", 4.10),
        ("660 UC", 8.20)
    ],

    "ff": [
        ("100 Diamonds", 1.00),
        ("310 Diamonds", 3.00),
        ("520 Diamonds", 5.00),
        ("1060 Diamonds", 10.00)
    ],

    "jawaker": [
        ("1000 Chips", 1.00),
        ("5000 Chips", 4.50),
        ("10000 Chips", 8.00)
    ],

    "coc": [
        ("500 Gems", 5.00),
        ("1200 Gems", 10.00),
        ("2500 Gems", 20.00)
    ]
}


FAST_ACCOUNTS = {
    "netflix": ("Netflix", 5000),
    "shahid": ("Shahid", 4000),
    "spotify": ("Spotify", 4500),
    "youtube": ("YouTube Premium", 5000)
}


ACCOUNTS_LIST = [
    "Netflix",
    "Shahid",
    "Spotify",
    "YouTube Premium",
    "Disney+",
    "OSN+",
    "Amazon Prime",
    "Canva Pro",
    "ChatGPT Plus",
    "Microsoft 365",
    "Adobe",
    "Crunchyroll",
    "Tinder",
    "Telegram Premium",
    "Snapchat+",
    "Google One",
    "iCloud+",
    "Duolingo",
    "PicsArt",
    "CapCut Pro",
    "InShot Pro",
    "KineMaster",
    "NordVPN",
    "ExpressVPN",
    "Discord Nitro",
    "Xbox Game Pass",
    "PlayStation Plus"
]


SOCIAL_PACKS = {

    "fb_followers": (
        "متابعين فيسبوك",
        2500,
        "fb"
    ),

    "fb_likes": (
        "لايكات فيسبوك",
        1500,
        "fb"
    ),

    "ig_followers": (
        "متابعين إنستغرام",
        3000,
        "ig"
    ),

    "ig_likes": (
        "لايكات إنستغرام",
        1800,
        "ig"
    ),

    "ig_views": (
        "مشاهدات فيديو إنستغرام",
        1200,
        "ig"
    ),

    "tg_members": (
        "أعضاء تلغرام",
        3500,
        "tg"
    ),

    "tg_views": (
        "مشاهدات تلغرام",
        1200,
        "tg"
    )
]
