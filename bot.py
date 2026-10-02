import asyncio
import html
import logging
import os
import re
from pathlib import Path
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

# ----------------- ط§ظ„ط¥ط¹ط¯ط§ط¯ط§طھ ظˆط§ظ„ظ…ط¬ظ…ظˆط¹ط§طھ -----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("âڑ ï¸ڈ ظ„ظ… ظٹطھظ… ط§ظ„ط¹ط«ظˆط± ط¹ظ„ظ‰ BOT_TOKEN ظپظٹ ظ…طھط؛ظٹط±ط§طھ ط§ظ„ط¨ظٹط¦ط©! ظٹط±ط¬ظ‰ طھط¹ظٹظٹظ†ظ‡ ط£ظˆظ„ط§ظ‹.")

ADMIN_ID_RAW = os.getenv("ADMIN_ID")
if not ADMIN_ID_RAW:
    raise ValueError("âڑ ï¸ڈ ظ„ظ… ظٹطھظ… ط§ظ„ط¹ط«ظˆط± ط¹ظ„ظ‰ ADMIN_ID ظپظٹ ظ…طھط؛ظٹط±ط§طھ ط§ظ„ط¨ظٹط¦ط©!")
ADMIN_ID = int(ADMIN_ID_RAW)

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

SHAM_NAME = "ط³ظƒظٹظ†ظ‡ ط­ظ…ظˆط¯ ط·ظ‡"
SHAM_ADDR = "be03739e320f3dfd318a1a7faebae16a"
BASE_DIR = Path(__file__).resolve().parent
QR_IMAGE_PATH = str(BASE_DIR / "qr_sham.jpg")
DB_PATH = str(BASE_DIR / "bot_store.db")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ----------------- ط¥ط¯ط§ط±ط© ظ‚ط§ط¹ط¯ط© ط§ظ„ط¨ظٹط§ظ†ط§طھ -----------------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
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
        CREATE TABLE IF NOT EXISTS admin_actions (
            message_key TEXT PRIMARY KEY,
            action TEXT NOT NULL,
            actor_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        await db.execute("INSERT OR IGNORE INTO settings (key, val) VALUES ('dollar_rate', 150.0)")
        await db.execute("INSERT OR IGNORE INTO settings (key, val) VALUES ('num_whatsapp', 400.0)")
        await db.execute("INSERT OR IGNORE INTO settings (key, val) VALUES ('num_telegram', 300.0)")
        await db.commit()

async def get_user(user_id: int, username: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id, username, balance, is_vip FROM users WHERE user_id=?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            await db.execute("INSERT INTO users (user_id, username, balance, is_vip) VALUES (?, ?, 0.0, 0)", (user_id, username))
            await db.commit()
            return (user_id, username, 0.0, 0)
        if username and row[1] != username:
            await db.execute("UPDATE users SET username=? WHERE user_id=?", (username, user_id))
            await db.commit()
            row = (row[0], username, row[2], row[3])
        return row

async def add_user_balance(user_id: int, delta: float, set_vip: bool = False):
    """ط¥ط¶ط§ظپط© ط±طµظٹط¯ ط¨ط´ظƒظ„ ط¢ظ…ظ†طŒ ظ…ط¹ ط¥ظ†ط´ط§ط، ط§ظ„ظ…ط³طھط®ط¯ظ… ط¥ط°ط§ ظ„ظ… ظٹظƒظ† ظ…ظˆط¬ظˆط¯ط§ظ‹."""
    if delta == 0:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, balance, is_vip) VALUES (?, '', 0.0, 0)",
            (user_id,)
        )
        if set_vip:
            cursor = await db.execute(
                "UPDATE users SET balance = balance + ?, is_vip = 1 WHERE user_id=?",
                (delta, user_id)
            )
        else:
            cursor = await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id=?",
                (delta, user_id)
            )
        await db.commit()
        return cursor.rowcount > 0

async def claim_admin_action(chat_id: int, message_id: int, action: str, actor_id: int) -> bool:
    """ظٹط¶ظ…ظ† طھظ†ظپظٹط° ط²ط± ط§ظ„ط¥ط¯ط§ط±ط© ظ…ط±ط© ظˆط§ط­ط¯ط© ظپظ‚ط· ط¹ظ„ظ‰ ظ†ظپط³ ط±ط³ط§ظ„ط© ط§ظ„ط·ظ„ط¨."""
    key = f"{chat_id}:{message_id}"
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO admin_actions (message_key, action, actor_id) VALUES (?, ?, ?)",
                (key, action, actor_id)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def try_deduct_balance(user_id: int, amount: float) -> bool:
    """ط®طµظ… ط°ط±ظٹ (Atomic) ظٹظ…ظ†ط¹ طھط­ظˆظ„ ط§ظ„ط±طµظٹط¯ ط¥ظ„ظ‰ ط³ط§ظ„ط¨ ظپظٹ ط­ط§ظ„ ط§ظ„طھط²ط§ظ…ظ†"""
    if amount <= 0:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
            (amount, user_id, amount)
        )
        await db.commit()
        return cursor.rowcount > 0

async def get_setting(key: str) -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT val FROM settings WHERE key=?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else 0.0

async def update_setting(key: str, val: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, val) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET val=excluded.val",
            (key, val)
        )
        await db.commit()

def persistent_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="ًں“‹ ط§ظ„ظ‚ط§ط¦ظ…ط© ط§ظ„ط±ط¦ظٹط³ظٹط©")]],
        resize_keyboard=True,
        persistent=True
    )

# ----------------- ط§ظ„طھط­ظ‚ظ‚ ظ…ظ† ط§ظ„ط§ط´طھط±ط§ظƒ -----------------
async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status not in ["left", "kicked"]
    except Exception as e:
        logging.error(f"ط®ط·ط£ ط£ط«ظ†ط§ط، ط§ظ„طھط­ظ‚ظ‚ ظ…ظ† ط§ظ„ط§ط´طھط±ط§ظƒ: {e}")
        return False

def sub_check_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ًں“¢ ط§ط´طھط±ظƒ ظپظٹ ط§ظ„ظ‚ظ†ط§ط© ط£ظˆظ„ط§ظ‹", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="ًں”„ طھظ… ط§ظ„ط§ط´طھط±ط§ظƒ (طھط£ظƒظٹط¯)", callback_data="check_subscription")]
    ])

def is_admin_or_group(user_id: int, chat_id: int) -> bool:
    return user_id == ADMIN_ID or chat_id in ALL_ADMIN_GROUPS

# ----------------- ط§ظ„ظƒطھط§ظ„ظˆط¬ ظˆط§ظ„ط¨ظٹط§ظ†ط§طھ -----------------
GOVERNORATES = [
    "ط¯ظ…ط´ظ‚", "ط±ظٹظپ ط¯ظ…ط´ظ‚", "ط­ظ…طµ", "ط±ظٹظپ ط­ظ…طµ", "ط­ظ…ط§ط©", "ط±ظٹظپ ط­ظ…ط§ط©",
    "ط·ط±ط·ظˆط³", "ط¯ط±ط¹ط§", "ط§ظ„ظ„ط§ط°ظ‚ظٹط©", "ط±ظٹظپ ط§ظ„ظ„ط§ط°ظ‚ظٹط©", "ط­ظ„ط¨", "ط§ظ„ظ‚ط§ظ…ط´ظ„ظٹ",
    "ط§ظ„ط±ظ‚ط©", "ط¯ظٹط± ط§ظ„ط²ظˆط±", "ط§ظ„ط¨ظˆظƒظ…ط§ظ„", "ط§ظ„ط­ط³ظƒط©", "ط§ظ„ط³ظˆظٹط¯ط§ط،", "ط§ظ„ظ‚ظ†ظٹط·ط±ط©",
    "ط¥ط¯ظ„ط¨", "ط¬ط¨ظ„ط©", "ط§ظ„ظ‚ظ„ظ…ظˆظ†"
]

FAST_ACCOUNTS = {
    "1": ("ChatGPT ط¹ط§ط¯ظٹ (ط´ظ‡ط±)", 1700),
    "2": ("ChatGPT Go (ط¶ظ…ط§ظ†)", 2000),
    "3": ("ChatGPT Plus ط´ظ‡ط±", 3500),
    "4": ("Netflix ط´ظ‡ط± ط¬ظ‡ط§ط² ظˆط§ط­ط¯", 800),
    "5": ("Netflix ط³ظ†ط© ط¬ظ‡ط§ط² ظˆط§ط­ط¯", 5000),
}

SOCIAL_PACKS = {
    "fb_view": ("ظ…ط´ط§ظ‡ط¯ط§طھ 10k", 500, "fb"),
    "fb_like": ("ظ„ط§ظٹظƒط§طھ ظ…ظ†ط´ظˆط± 5k", 700, "fb"),
    "fb_sub": ("ظ…طھط§ط¨ط¹ظٹظ† 1k", 150, "fb"),
    "fb_comm": ("طھط¹ظ„ظٹظ‚ط§طھ ط¹ط±ط¨ظٹط© 200", 250, "fb"),
    "ig_view": ("ظ…ط´ط§ظ‡ط¯ط§طھ 500k", 300, "ig"),
    "ig_like": ("ظ„ط§ظٹظƒط§طھ 5k", 700, "ig"),
    "ig_sub_f": ("ظ…طھط§ط¨ط¹ظٹظ† ط£ط¬ظ†ط¨ظٹ 1k", 700, "ig"),
    "ig_sub_a": ("ظ…طھط§ط¨ط¹ظٹظ† ط¹ط±ط¨ظٹ 1k", 1350, "ig"),
    "tg_sub": ("ط£ط¹ط¶ط§ط، ظ‚ظ†ظˆط§طھ 1k", 400, "tg"),
    "tg_react": ("طھظپط§ط¹ظ„ط§طھ 1k", 150, "tg"),
    "tg_view": ("ظ…ط´ط§ظ‡ط¯ط§طھ 5k", 200, "tg"),
}

ACCOUNTS_LIST = [
    "Shahid VIP", "Watch It", "OSN+", "TOD TV", "Disney+", "Amazon Prime Video",
    "Apple TV+", "IPTV ط³ظ†ط©", "IPTV 6 ط£ط´ظ‡ط±", "Spotify Premium", "YouTube Premium",
    "Anghami Plus", "SoundCloud Pro", "Deezer Premium", "Canva Pro ط³ظ†ط©",
    "Canva Pro ط´ظ‡ط±", "Adobe Cloud", "TradingView Pro", "Duolingo Plus",
    "LinkedIn Premium", "Telegram Premium", "NordVPN", "ExpressVPN", "Surfshark VPN",
    "Crunchyroll Fan", "Mega Cloud", "Google One"
]

SYR_UNITS = [
    (9.61, 12), (20.19, 25), (30.76, 40), (40.38, 50), (52.88, 65),
    (62.50, 75), (77.88, 95), (81.73, 100), (100.96, 125), (125, 150),
    (160.57, 200), (192.3, 240), (211.53, 265), (240.38, 300), (288.46, 360),
    (317.3, 400), (370.19, 450), (432.69, 530), (480.76, 600), (576.92, 720),
    (625, 780), (721.15, 895), (769.23, 950), (951.92, 1180), (1057.69, 1300),
    (1923.07, 2380), (2403.84, 3000), (3846.15, 4770)
]

MTN_UNITS = [
    (10, 12), (12, 15), (15, 20), (20, 25), (25, 30), (30, 40), (35, 45),
    (40, 50), (50, 60), (60, 75), (85, 105), (100, 125), (170, 210), (200, 250),
    (280, 350), (360, 450), (400, 500), (600, 750), (750, 930), (1000, 1250),
    (1500, 1860), (2000, 2500), (2500, 3010), (3000, 3750), (5000, 6200)
]

STATION_VALS = [
    (500, 535), (1000, 1070), (1500, 1605), (2000, 2140), (2500, 2675),
    (3000, 3210), (4000, 4280), (5000, 5350), (10000, 10700)
]

GAME_PACKS = {
    "pubg": [("60 UC", 1.0), ("325 UC", 5.0), ("660 UC", 10.0), ("1800 UC", 25.0), ("3850 UC", 50.0), ("8100 UC", 100.0)],
    "ff": [("100 ط¬ظˆظ‡ط±ط©", 1.0), ("210 ط¬ظˆظ‡ط±ط©", 2.0), ("530 ط¬ظˆظ‡ط±ط©", 5.0), ("1080 ط¬ظˆظ‡ط±ط©", 10.0), ("2200 ط¬ظˆظ‡ط±ط©", 20.0), ("5600 ط¬ظˆظ‡ط±ط©", 50.0)],
    "jawaker": [("15,000 طھظˆظƒظ†ط²", 1.5), ("50,000 طھظˆظƒظ†ط²", 4.0), ("150,000 طھظˆظƒظ†ط²", 10.0), ("ط¨ط§ط´ط§ (ط´ظ‡ط±)", 6.0)],
    "coc": [("500 ط¬ظˆظ‡ط±ط©", 5.0), ("1200 ط¬ظˆظ‡ط±ط©", 10.0), ("2500 ط¬ظˆظ‡ط±ط©", 20.0), ("6500 ط¬ظˆظ‡ط±ط©", 50.0), ("14000 ط¬ظˆظ‡ط±ط©", 100.0)]
}

# ----------------- ط§ظ„ط­ط§ظ„ط§طھ FSM -----------------
class OrderState(StatesGroup):
    syr_units_phone = State()
    syr_station_code = State()
    syr_station_gov = State()
    syr_invoice_num = State()
    syr_invoice_amt = State()
    syr_cash_amt = State()
    syr_cash_id = State()

    mtn_units_phone = State()
    mtn_station_code = State()
    mtn_station_num = State()
    mtn_station_gov = State()
    mtn_invoice_num = State()
    mtn_invoice_amt = State()
    mtn_cash_amt = State()
    mtn_cash_num = State()

    entering_game_data = State()
    entering_chat_qty = State()

    entering_social_link = State()
    entering_ad_phone = State()
    entering_custom_ad_days = State()

    waiting_receipt = State()
    support_ticket = State()

    wallet_deposit_amt = State()
    wallet_deposit_receipt = State()

class QuoteState(StatesGroup):
    entering_quote_text = State()

# ----------------- ط¨ظ†ط§ط، ط§ظ„ظ‚ظˆط§ط¦ظ… -----------------
async def main_menu_text_and_kb(user_id: int, username: str):
    u = await get_user(user_id, username)
    rank = "ًںŒں ط²ط¨ظˆظ† ط¯ط§ط¦ظ… (VIP)" if u[3] == 1 else "ًں‘¤ ط²ط¨ظˆظ† ط¹ط§ط¯ظٹ"
    text = (
        f"ًں‘‹ <b>ط£ظ‡ظ„ط§ظ‹ ط¨ظƒ ظپظٹ ظ…طھط¬ط± Syria Store</b>\n"
        f"â”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
        f"ًںڈ· <b>ط§ظ„ط±طھط¨ط©:</b> {rank}\n"
        f"ًں’³ <b>ط±طµظٹط¯ ظ…ط­ظپط¸طھظƒ:</b> <code>{u[2]:,.2f} ظ„.ط³</code>\n"
        f"â”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
        f"ط§ط®طھط± ط§ظ„ظ‚ط³ظ… ط§ظ„ظ…ط·ظ„ظˆط¨ ظ„طھطµظپط­ ط§ظ„ط®ط¯ظ…ط§طھ:"
    )
    kb = [
        [InlineKeyboardButton(text="ًں“‍ ظ‚ط³ظ… ط§ظ„ط±طµظٹط¯ ظˆط§ظ„ظƒط§ط´", callback_data="sec_balance")],
        [InlineKeyboardButton(text="ًںژ® ظ‚ط³ظ… ط´ط­ظ† ط§ظ„ط£ظ„ط¹ط§ط¨", callback_data="sec_games")],
        [InlineKeyboardButton(text="ًں’¬ ظ‚ط³ظ… طھط·ط¨ظٹظ‚ط§طھ ط§ظ„ط´ط§طھ", callback_data="sec_chat")],
        [InlineKeyboardButton(text="ًں“¦ ظ‚ط³ظ… ط§ظ„ط­ط³ط§ط¨ط§طھ ظˆط§ظ„ط§ط´طھط±ط§ظƒط§طھ", callback_data="sec_accounts")],
        [InlineKeyboardButton(text="ًںڑ€ ظ‚ط³ظ… ط§ظ„ط³ظˆط´ظٹط§ظ„ ظ…ظٹط¯ظٹط§ ظˆط§ظ„ط¥ط¹ظ„ط§ظ†ط§طھ", callback_data="sec_social")],
        [InlineKeyboardButton(text="ًں“± ظ‚ط³ظ… ط£ط±ظ‚ط§ظ… ط§ظ„طھظپط¹ظٹظ„", callback_data="sec_numbers")],
        [InlineKeyboardButton(text="ًں’³ ظ…ط­ظپط¸طھظٹ ظˆط´ط­ظ† ط§ظ„ط±طµظٹط¯", callback_data="sec_wallet")],
        [InlineKeyboardButton(text="ًں›  ط§ظ„ط¯ط¹ظ… ط§ظ„ظپظ†ظٹ ظˆط§ظ„ط´ظƒط§ظˆظ‰", callback_data="sec_support")]
    ]
    return text, InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(F.text == "ًں“‹ ط§ظ„ظ‚ط§ط¦ظ…ط© ط§ظ„ط±ط¦ظٹط³ظٹط©")
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    if not await is_subscribed(message.from_user.id):
        await message.answer(
            "âڑ ï¸ڈ ط¹ط°ط±ط§ظ‹ ط¹ط²ظٹط²ظٹطŒ ظٹط¬ط¨ ط¹ظ„ظٹظƒ ط§ظ„ط§ط´طھط±ط§ظƒ ظپظٹ ظ‚ظ†ط§ط© ط§ظ„ط¨ظˆطھ ط§ظ„ط±ط³ظ…ظٹط© ط£ظˆظ„ط§ظ‹ ظ„طھطھظ…ظƒظ† ظ…ظ† ط§ط³طھط®ط¯ط§ظ… ط§ظ„ط®ط¯ظ…ط§طھ:\n\n"
            "ط§ط¶ط؛ط· ط¹ظ„ظ‰ ط§ظ„ط²ط± ط¨ط§ظ„ط£ط³ظپظ„ ظ„ظ„ط§ط´طھط±ط§ظƒطŒ ط«ظ… ط§ط¶ط؛ط· ط¹ظ„ظ‰ ط²ط± (طھظ… ط§ظ„ط§ط´طھط±ط§ظƒ).",
            reply_markup=sub_check_keyboard()
        )
        return
    text, kb = await main_menu_text_and_kb(message.from_user.id, message.from_user.username or "")
    await message.answer(text, reply_markup=kb)
    await message.answer("ًں’، ط§ط³طھط®ط¯ظ… ط§ظ„ط²ط± ط§ظ„ط«ط§ط¨طھ ط¨ط§ظ„ط£ط³ظپظ„ ظ„ظ„ط¹ظˆط¯ط© ظ„ظ„ظ‚ط§ط¦ظ…ط© ط¯ط§ط¦ظ…ط§ظ‹.", reply_markup=persistent_keyboard())

@dp.callback_query(F.data == "check_subscription")
async def check_sub_cb(cb: types.CallbackQuery):
    if await is_subscribed(cb.from_user.id):
        try:
            await cb.message.delete()
        except Exception:
            pass
        text, kb = await main_menu_text_and_kb(cb.from_user.id, cb.from_user.username or "")
        await cb.message.answer(text, reply_markup=kb)
    else:
        await cb.answer("â‌Œ ظ„ظ… طھظ‚ظ… ط¨ط§ظ„ط§ط´طھط±ط§ظƒ ظپظٹ ط§ظ„ظ‚ظ†ط§ط© ط¨ط¹ط¯! ط§ط´طھط±ظƒ ط«ظ… ط§ط¶ط؛ط· طھط£ظƒظٹط¯.", show_alert=True)

@dp.callback_query(F.data == "back_main")
async def back_to_main(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = await main_menu_text_and_kb(cb.from_user.id, cb.from_user.username or "")
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)

# ----------------- ظ‚ط³ظ… ط§ظ„ظ…ط­ظپط¸ط© ظˆط§ظ„ظ…ط§ظ„ظٹط© -----------------
@dp.callback_query(F.data == "sec_wallet")
async def wallet_home(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    u = await get_user(cb.from_user.id, cb.from_user.username or "")
    rank = "ًںŒں ط²ط¨ظˆظ† ط¯ط§ط¦ظ… (VIP)" if u[3] == 1 else "ًں‘¤ ط²ط¨ظˆظ† ط¹ط§ط¯ظٹ"
    txt = (
        f"ًں’³ <b>ظ…ط­ظپط¸ط© ط³ظˆط±ظٹط§ ط³طھظˆط± ط§ظ„ط¥ظ„ظƒطھط±ظˆظ†ظٹط©:</b>\n"
        f"â”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
        f"ًںڈ· <b>ط±طھط¨ط© ط­ط³ط§ط¨ظƒ:</b> {rank}\n"
        f"ًں’° <b>ط±طµظٹط¯ظƒ ط§ظ„ط­ط§ظ„ظٹ:</b> <code>{u[2]:,.2f} ظ„ظٹط±ط© ط³ظˆط±ظٹط©</code>\n\n"
        f"ًں’، <b>ظ…ط²ط§ظٹط§ ط´ط­ظ† ط§ظ„ظ…ط­ظپط¸ط© (ط§ظ„ط²ط¨ظˆظ† ط§ظ„ط¯ط§ط¦ظ…):</b>\n"
        f"â€¢ ط´ط±ط§ط، ظپظˆط±ظٹ ظ„ط£ظٹ ط®ط¯ظ…ط© ط¨ط¶ط؛ط·ط© ط²ط± ط¯ظˆظ† ط¥ط±ط³ط§ظ„ ط¥ط´ط¹ط§ط±ط§طھ ظپظٹ ظƒظ„ ظ…ط±ط©.\n"
        f"â€¢ ط£ظˆظ„ظˆظٹط© ظˆط³ط±ط¹ط© ظپط§ط¦ظ‚ط© ظپظٹ ط§ظ„طھظ†ظپظٹط°.\n"
        f"â€¢ ط§ظ„طھط±ظ‚ظٹط© ط§ظ„طھظ„ظ‚ط§ط¦ظٹط© ظ„ط­ط³ط§ط¨ VIP.\n"
    )
    kb = [
        [InlineKeyboardButton(text="â‍• ط´ط­ظ† ط±طµظٹط¯ ط§ظ„ظ…ط­ظپط¸ط©", callback_data="wallet_deposit")],
        [InlineKeyboardButton(text="ًں”™ ط§ظ„ظ‚ط§ط¦ظ…ط© ط§ظ„ط±ط¦ظٹط³ظٹط©", callback_data="back_main")]
    ]
    await cb.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "wallet_deposit")
async def wallet_dep_start(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.wallet_deposit_amt)
    await cb.message.edit_text(
        "ًں’µ ط£ط¯ط®ظ„ ط§ظ„ظ…ط¨ظ„ط؛ ط§ظ„ط°ظٹ طھط±ط؛ط¨ ظپظٹ ط¥ظٹط¯ط§ط¹ظ‡ ط¨ظ…ط­ظپط¸طھظƒ ط¨ط§ظ„ظ„ظٹط±ط© ط§ظ„ط³ظˆط±ظٹط©:\n"
        "(ظ…ط«ط§ظ„: <code>50000</code> ط£ظˆ <code>100000</code>):"
    )

@dp.message(OrderState.wallet_deposit_amt)
async def wallet_dep_amt_receive(message: types.Message, state: FSMContext):
    try:
        amt = float(message.text.strip().replace(",", ""))
        if amt < 500:
            await message.reply("âڑ ï¸ڈ ط£ظ‚ظ„ ظ…ط¨ظ„ط؛ ظ„ظ„ط´ط­ظ† ظ‡ظˆ 500 ظ„ظٹط±ط© ط³ظˆط±ظٹط©:")
            return
        await state.update_data(dep_amt=amt)
        await state.set_state(OrderState.wallet_deposit_receipt)
        txt = (
            f"ًں§¾ <b>ط·ظ„ط¨ ط´ط­ظ† ظ…ط­ظپط¸ط©:</b>\n"
            f"â€¢ ط§ظ„ظ…ط¨ظ„ط؛ ط§ظ„ظ…ط±ط§ط¯ ط¥ظٹط¯ط§ط¹ظ‡: <b>{amt:,.2f} ظ„.ط³</b>\n\n"
            f"ًں’³ <b>ط¨ظٹط§ظ†ط§طھ ط§ظ„طھط­ظˆظٹظ„ ط¹ط¨ط± ط´ط§ظ… ظƒط§ط´:</b>\n"
            f"ًں‘¤ ط§ظ„ط§ط³ظ…: <code>{html.escape(SHAM_NAME)}</code>\n"
            f"ًں”— ط§ظ„ط¹ظ†ظˆط§ظ†: <code>{html.escape(SHAM_ADDR)}</code>\n\n"
            f"âڑ ï¸ڈ ظٹط±ط¬ظ‰ طھط­ظˆظٹظ„ ط§ظ„ظ…ط¨ظ„ط؛ ط«ظ… <b>ط±ظپط¹ طµظˆط±ط© ط¥ط´ط¹ط§ط± ط§ظ„طھط­ظˆظٹظ„ ظ‡ظ†ط§ ظپظˆط±ط§ظ‹</b>."
        )
        if os.path.exists(QR_IMAGE_PATH):
            photo = FSInputFile(QR_IMAGE_PATH)
            await message.answer_photo(photo, caption=txt)
        else:
            await message.answer(txt)
    except Exception:
        await message.reply("âڑ ï¸ڈ ظٹط±ط¬ظ‰ ط¥ط¯ط®ط§ظ„ ظ…ط¨ظ„ط؛ طµط­ظٹط­ ط¨ط§ظ„ط£ط±ظ‚ط§ظ…:")

@dp.message(OrderState.wallet_deposit_receipt, F.photo)
async def wallet_dep_receipt_proc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amt = data.get("dep_amt", 0)
    user_info = f"@{html.escape(message.from_user.username)}" if message.from_user.username else "ط¨ط¯ظˆظ† ظٹظˆط²ط±"

    group_text = (
        f"ًں’³ <b>ط¥ظٹط¯ط§ط¹ ط¬ط¯ظٹط¯ ظ„ظ„ظ…ط­ظپط¸ط© ظ‚ظٹط¯ ط§ظ„ظ…ط±ط§ط¬ط¹ط©:</b>\n"
        f"ًں‘¤ ط§ظ„ط²ط¨ظˆظ†: {user_info} (<code>{message.from_user.id}</code>)\n"
        f"ًں’° ط§ظ„ظ…ط¨ظ„ط؛ ط§ظ„ظ…ط·ظ„ظˆط¨ ط´ط­ظ†ظ‡: <b>{amt:,.2f} ظ„.ط³</b>\n"
    )
    sent_group = await bot.send_photo(
        chat_id=GROUPS["wallet"],
        photo=message.photo[-1].file_id,
        caption=group_text
    )
    kb = [
        [
            InlineKeyboardButton(text=f"âœ… طھط£ظƒظٹط¯ ط§ظ„ط¥ظٹط¯ط§ط¹ ({amt:,.0f} ظ„.ط³)", callback_data=f"wconf:{message.from_user.id}:{amt}:{sent_group.message_id}"),
            InlineKeyboardButton(text="â‌Œ ط±ظپط¶ ط§ظ„ط¥ظٹط¯ط§ط¹", callback_data=f"wrej:{message.from_user.id}:{sent_group.message_id}")
        ]
    ]
    await bot.edit_message_reply_markup(
        chat_id=GROUPS["wallet"],
        message_id=sent_group.message_id,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await state.clear()
    text, menu_kb = await main_menu_text_and_kb(message.from_user.id, message.from_user.username or "")
    await message.answer(
        "âœ… طھظ… ط§ط³طھظ„ط§ظ… ط¥ط´ط¹ط§ط± ط§ظ„ط¥ظٹط¯ط§ط¹ ط¨ظ†ط¬ط§ط­ ظˆط¥ط±ط³ط§ظ„ظ‡ ظ„ظ„ظ…ط§ظ„ظٹط©!\n"
        "ط³ظٹطھظ… ط´ط­ظ† ط§ظ„ظ…ط­ظپط¸ط© ظپظˆط± طھط¯ظ‚ظٹظ‚ ط§ظ„طھط­ظˆظٹظ„ ظˆط³طھطµظ„ظƒ ط±ط³ط§ظ„ط© طھط£ظƒظٹط¯.",
        reply_markup=menu_kb
    )

@dp.callback_query(F.data.startswith("wconf:"))
async def wallet_admin_confirm(cb: types.CallbackQuery):
    if not is_admin_or_group(cb.from_user.id, cb.message.chat.id):
        await cb.answer("â›” ظ„ط§ طھظ…ظ„ظƒ طµظ„ط§ط­ظٹط© طھظ†ظپظٹط° ظ‡ط°ط§ ط§ظ„ط¥ط¬ط±ط§ط،!", show_alert=True)
        return

    _, u_id, amt, msg_id = cb.data.split(":")
    u_id = int(u_id)
    amt = float(amt)
    msg_id = int(msg_id)
    if not await claim_admin_action(cb.message.chat.id, msg_id, "wallet_confirm", cb.from_user.id):
        await cb.answer("âڑ ï¸ڈ ظ‡ط°ط§ ط§ظ„ط¥ظٹط¯ط§ط¹ طھظ…طھ ظ…ط¹ط§ظ„ط¬طھظ‡ ظ…ط³ط¨ظ‚ط§ظ‹.", show_alert=True)
        return
    await add_user_balance(u_id, amt, set_vip=True)
    new_u = await get_user(u_id)
    try:
        await bot.send_message(
            u_id,
            f"ًںژ‰ <b>ظ…ط¨ط±ظˆظƒ! طھظ… طھط£ظƒظٹط¯ ط¥ظٹط¯ط§ط¹ظƒ ط¨ظ†ط¬ط§ط­!</b>\n\n"
            f"â‍• ط§ظ„ظ…ط¨ظ„ط؛ ط§ظ„ظ…ط¶ط§ظپ: <b>{amt:,.2f} ظ„.ط³</b>\n"
            f"ًں’³ ط±طµظٹط¯ ظ…ط­ظپط¸طھظƒ ط§ظ„ط­ط§ظ„ظٹ: <b>{new_u[2]:,.2f} ظ„.ط³</b>\n"
            f"ًںŒں طھظ… طھظپط¹ظٹظ„ ط±طھط¨ط© ط²ط¨ظˆظ† ط¯ط§ط¦ظ… (VIP).",
        )
        if cb.message.caption:
            await cb.message.edit_caption(caption=cb.message.caption + f"\n\nًںں¢ <b>طھظ… طھط£ظƒظٹط¯ ط§ظ„ط´ط­ظ† ط¨ظ†ط¬ط§ط­ ({amt:,.0f} ظ„.ط³)</b>", reply_markup=None)
    except Exception as e:
        await cb.answer(f"ط®ط·ط£: {e}", show_alert=True)

@dp.callback_query(F.data.startswith("wrej:"))
async def wallet_admin_reject(cb: types.CallbackQuery):
    if not is_admin_or_group(cb.from_user.id, cb.message.chat.id):
        await cb.answer("â›” ظ„ط§ طھظ…ظ„ظƒ طµظ„ط§ط­ظٹط© طھظ†ظپظٹط° ظ‡ط°ط§ ط§ظ„ط¥ط¬ط±ط§ط،!", show_alert=True)
        return

    _, u_id, msg_id = cb.data.split(":")
    u_id = int(u_id)
    msg_id = int(msg_id)
    if not await claim_admin_action(cb.message.chat.id, msg_id, "wallet_reject", cb.from_user.id):
        await cb.answer("âڑ ï¸ڈ ظ‡ط°ط§ ط§ظ„ط¥ظٹط¯ط§ط¹ طھظ…طھ ظ…ط¹ط§ظ„ط¬طھظ‡ ظ…ط³ط¨ظ‚ط§ظ‹.", show_alert=True)
        return
    try:
        await bot.send_message(u_id, "â‌Œ ظ†ط¹طھط°ط± ظ…ظ†ظƒطŒ طھظ… ط±ظپط¶ ط¥ط´ط¹ط§ط± ط§ظ„ط¥ظٹط¯ط§ط¹ ظ„ط¹ط¯ظ… طھط·ط§ط¨ظ‚ ط§ظ„طھط­ظˆظٹظ„.")
        if cb.message.caption:
            await cb.message.edit_caption(caption=cb.message.caption + "\n\nًں”´ <b>طھظ… ط±ظپط¶ ط§ظ„ط¥ظٹط¯ط§ط¹</b>", reply_markup=None)
    except Exception as e:
        await cb.answer(f"ط®ط·ط£: {e}", show_alert=True)

# ----------------- ط¢ظ„ظٹط© ط§ظ„ط¯ظپط¹ -----------------
async def prompt_payment(message: types.Message, state: FSMContext, user_id: int):
    data = await state.get_data()
    price = float(data.get("price", 0) or 0)
    service = data.get("service", "")
    target = data.get("target", "")

    if price <= 0 or not service:
        await message.answer("âڑ ï¸ڈ طھط¹ط°ط± طھط¬ظ‡ظٹط² ط§ظ„ط·ظ„ط¨. ظٹط±ط¬ظ‰ ط§ظ„ط¹ظˆط¯ط© ظ„ظ„ظ‚ط§ط¦ظ…ط© ظˆط¥ط¹ط§ط¯ط© ط§ط®طھظٹط§ط± ط§ظ„ط®ط¯ظ…ط©.")
        return

    user = await get_user(user_id)
    balance = user[2]

    kb = []
    if balance >= price:
        kb.append([InlineKeyboardButton(text=f"âڑ، ط®طµظ… ظپظˆط±ظٹ ظ…ظ† ط§ظ„ظ…ط­ظپط¸ط© ({price:,.0f} ظ„.ط³)", callback_data="pay_wallet")])
    kb.append([InlineKeyboardButton(text="ًں’³ ط¯ظپط¹ ظٹط¯ظˆظٹ ط¹ط¨ط± ط´ط§ظ… ظƒط§ط´", callback_data="pay_manual")])
    kb.append([InlineKeyboardButton(text="ًں”™ ط¥ظ„ط؛ط§ط، ظˆط§ظ„ط±ط¬ظˆط¹", callback_data="back_main")])

    summary_text = (
        f"ًں§¾ <b>ظ…ظ„ط®طµ طھظپط§طµظٹظ„ ط·ظ„ط¨ظƒ:</b>\n"
        f"â€¢ ط§ظ„ط®ط¯ظ…ط©: <b>{html.escape(service)}</b>\n"
        f"â€¢ ط§ظ„ط¨ظٹط§ظ†ط§طھ: <code>{html.escape(str(target))}</code>\n"
        f"â€¢ ط§ظ„ظ…ط¨ظ„ط؛ ط§ظ„ظ…ط·ظ„ظˆط¨: <b>{price:,.2f} ظ„.ط³</b>\n"
        f"â”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
        f"ًں’³ ط±طµظٹط¯ ظ…ط­ظپط¸طھظƒ ط§ظ„ط­ط§ظ„ظٹ: <b>{balance:,.2f} ظ„.ط³</b>\n\n"
        f"ط§ط®طھط± ظˆط³ظٹظ„ط© ط§ظ„ط¯ظپط¹ ط§ظ„طھظٹ طھظ†ط§ط³ط¨ظƒ ط£ط¯ظ†ط§ظ‡:"
    )
    await message.answer(summary_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def prompt_payment_cb(cb: types.CallbackQuery, state: FSMContext):
    await prompt_payment(cb.message, state, cb.from_user.id)

@dp.callback_query(F.data == "pay_wallet")
async def execute_wallet_pay(cb: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    price = data.get("price", 0)
    service = data.get("service", "")
    target = data.get("target", "")
    sec = data.get("sec", "balance")
    group_id = GROUPS.get(sec, GROUPS["balance"])

    # ط®طµظ… ط°ط±ظٹ ظ…ط¨ط§ط´ط± ظ„ظ…ظ†ط¹ ط§ظ„ط³ط¨ط§ظ‚ ط§ظ„ظ…ط§ظ„ظٹ
    success = await try_deduct_balance(cb.from_user.id, price)
    if not success:
        await cb.answer("âڑ ï¸ڈ ط±طµظٹط¯ ظ…ط­ظپط¸طھظƒ ط؛ظٹط± ظƒط§ظپظچ ط£ظˆ طھط؛ظٹط± ط£ط«ظ†ط§ط، ط§ظ„ط¹ظ…ظ„ظٹط©!", show_alert=True)
        return

    new_user = await get_user(cb.from_user.id)
    user_info = f"@{html.escape(cb.from_user.username)}" if cb.from_user.username else "ط¨ط¯ظˆظ† ظٹظˆط²ط±"
    order_info = (
        f"âڑ، <b>ط·ظ„ط¨ ظ…ط¯ظپظˆط¹ ظˆظ…ظ‚طھط·ط¹ ظ…ظ† ط§ظ„ظ…ط­ظپط¸ط© (ظپظˆط±ظٹ):</b>\n"
        f"ًں‘¤ ط§ظ„ط²ط¨ظˆظ†: {user_info} (<code>{cb.from_user.id}</code>)\n"
        f"ًںڈ· ط§ظ„ط®ط¯ظ…ط©: <b>{html.escape(service)}</b>\n"
        f"ًںژ¯ ط§ظ„ط¨ظٹط§ظ†ط§طھ: <code>{html.escape(str(target))}</code>\n"
        f"ًں’° ط§ظ„ظ…ط¨ظ„ط؛ ط§ظ„ظ…ط®طµظˆظ…: <b>{price:,.2f} ظ„.ط³</b>\n"
        f"ًں’³ ط±طµظٹط¯ ط§ظ„ظ…ط­ظپط¸ط© ط§ظ„ظ…طھط¨ظ‚ظٹ: <b>{new_user[2]:,.2f} ظ„.ط³</b>\n\n"
        f"ًں’، ظ„ظ„ط±ط¯ ط¹ظ„ظ‰ ط§ظ„ط²ط¨ظˆظ†طŒ ظ‚ظ… ط¨ط§ظ„ط±ط¯ ط§ظ„ظ…ط¨ط§ط´ط± (Reply) ط¹ظ„ظ‰ ظ‡ط°ظ‡ ط§ظ„ط±ط³ط§ظ„ط©."
    )
    sent_order = await bot.send_message(group_id, order_info)
    kb = [
        [
            InlineKeyboardButton(text="âœ… طھظ… ط§ظ„طھظ†ظپظٹط°", callback_data=f"done:{cb.from_user.id}:{sent_order.message_id}"),
            InlineKeyboardButton(text="â‌Œ ط¥ظ„ط؛ط§ط، ظˆط¥ط±ط¬ط§ط¹ ط§ظ„ط±طµظٹط¯", callback_data=f"refund:{cb.from_user.id}:{price}:{sent_order.message_id}")
        ]
    ]
    await bot.edit_message_reply_markup(
        chat_id=group_id,
        message_id=sent_order.message_id,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await state.clear()

    text, menu_kb = await main_menu_text_and_kb(cb.from_user.id, cb.from_user.username or "")
    await cb.message.edit_text(
        f"âœ… <b>طھظ… ط®طµظ… {price:,.2f} ظ„.ط³ ظ…ظ† ظ…ط­ظپط¸طھظƒ ط¨ظ†ط¬ط§ط­!</b>\n"
        f"طھظ… طھط­ظˆظٹظ„ ط·ظ„ط¨ظƒ ظ„ظ„ط¥ط¯ط§ط±ط© ظˆط¬ط§ط±ظچ ط§ظ„طھظ†ظپظٹط° ط¨ط£ظˆظ„ظˆظٹط© ظ‚طµظˆظ‰.\n"
        f"ًں’³ ط±طµظٹط¯ظƒ ط§ظ„ظ…طھط¨ظ‚ظٹ: <code>{new_user[2]:,.2f} ظ„.ط³</code>",
        reply_markup=menu_kb
    )

@dp.callback_query(F.data == "pay_manual")
async def manual_pay_prompt(cb: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    price = data.get("price", 0)
    pay_text = (
        f"ًں’³ <b>ط¨ظٹط§ظ†ط§طھ ط§ظ„طھط­ظˆظٹظ„ ط¹ط¨ط± ط´ط§ظ… ظƒط§ط´:</b>\n"
        f"ًں‘¤ ط§ظ„ط§ط³ظ…: <code>{html.escape(SHAM_NAME)}</code>\n"
        f"ًں”— ط§ظ„ط¹ظ†ظˆط§ظ†: <code>{html.escape(SHAM_ADDR)}</code>\n"
        f"ًں’° ط§ظ„ظ…ط·ظ„ظˆط¨: <b>{price:,.2f} ظ„ظٹط±ط© ط³ظˆط±ظٹط©</b>\n\n"
        f"âڑ ï¸ڈ ظٹط±ط¬ظ‰ طھط­ظˆظٹظ„ ط§ظ„ظ…ط¨ظ„ط؛ ط«ظ… <b>ط±ظپط¹ طµظˆط±ط© ط¥ط´ط¹ط§ط± ط§ظ„طھط­ظˆظٹظ„ ظ‡ظ†ط§ ظپظˆط±ط§ظ‹</b>."
    )
    await state.set_state(OrderState.waiting_receipt)
    if os.path.exists(QR_IMAGE_PATH):
        photo = FSInputFile(QR_IMAGE_PATH)
        await cb.message.answer_photo(photo, caption=pay_text)
    else:
        await cb.message.answer(pay_text)
    await cb.answer()

@dp.message(OrderState.waiting_receipt, F.photo)
async def receive_manual_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    sec = data.get("sec", "balance")
    group_id = GROUPS.get(sec, GROUPS["balance"])
    user_info = f"@{html.escape(message.from_user.username)}" if message.from_user.username else "ط¨ط¯ظˆظ† ظٹظˆط²ط±"

    order_info = (
        f"ًں”” <b>ط·ظ„ط¨ ظٹط¯ظˆظٹ ط¬ط¯ظٹط¯ ظ‚ظٹط¯ ط§ظ„ظ…ط±ط§ط¬ط¹ط©:</b>\n"
        f"ًں‘¤ ط§ظ„ط²ط¨ظˆظ†: {user_info} (<code>{message.from_user.id}</code>)\n"
        f"ًںڈ· ط§ظ„ط®ط¯ظ…ط©: {html.escape(str(data.get('service')))}\n"
        f"ًںژ¯ ط§ظ„ط¨ظٹط§ظ†ط§طھ: <code>{html.escape(str(data.get('target')))}</code>\n"
        f"ًں’° ط§ظ„ظ…ط¨ظ„ط؛ ط§ظ„ظ…ط·ظ„ظˆط¨: <b>{data.get('price')} ظ„.ط³</b>\n\n"
        f"ًں’، ظ„ظ„ط±ط¯ ط¹ظ„ظ‰ ط§ظ„ط²ط¨ظˆظ†طŒ ظ‚ظ… ط¨ط§ظ„ط±ط¯ ط§ظ„ظ…ط¨ط§ط´ط± (Reply) ط¹ظ„ظ‰ ظ‡ط°ظ‡ ط§ظ„ط±ط³ط§ظ„ط©."
    )
    sent_order = await bot.send_photo(
        chat_id=group_id,
        photo=message.photo[-1].file_id,
        caption=order_info
    )
    kb = [
        [
            InlineKeyboardButton(text="âœ… طھظ… ط§ظ„طھظ†ظپظٹط°", callback_data=f"done:{message.from_user.id}:{sent_order.message_id}"),
            InlineKeyboardButton(text="â‌Œ ط±ظپط¶ ط§ظ„ط·ظ„ط¨", callback_data=f"rej:{message.from_user.id}:{sent_order.message_id}")
        ]
    ]
    await bot.edit_message_reply_markup(
        chat_id=group_id,
        message_id=sent_order.message_id,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await state.clear()
    text, menu_kb = await main_menu_text_and_kb(message.from_user.id, message.from_user.username or "")
    await message.answer(
        "âœ… طھظ… ط§ط³طھظ„ط§ظ… ط¥ط´ط¹ط§ط± ط§ظ„ط¯ظپط¹ ظˆط¥ط±ط³ط§ظ„ظ‡ ظ„ظ„ط¥ط¯ط§ط±ط©. ط³ظٹطھظ… ط¥ط´ط¹ط§ط±ظƒ ظپظˆط± ط§ظƒطھظ…ط§ظ„ ط§ظ„طھظ†ظپظٹط°.",
        reply_markup=menu_kb
    )

@dp.message(OrderState.waiting_receipt)
async def receive_manual_receipt_invalid(message: types.Message):
    await message.reply("âڑ ï¸ڈ ظٹط±ط¬ظ‰ ط¥ط±ط³ط§ظ„ طµظˆط±ط© ظˆط§ط¶ط­ط© ظ„ط¥ط´ط¹ط§ط± ط§ظ„طھط­ظˆظٹظ„ ظپظ‚ط·.")

@dp.message(OrderState.wallet_deposit_receipt)
async def wallet_dep_receipt_invalid(message: types.Message):
    await message.reply("âڑ ï¸ڈ ظٹط±ط¬ظ‰ ط¥ط±ط³ط§ظ„ طµظˆط±ط© ظˆط§ط¶ط­ط© ظ„ط¥ط´ط¹ط§ط± ط§ظ„طھط­ظˆظٹظ„ ظپظ‚ط·.")

@dp.callback_query(F.data.startswith("refund:"))
async def refund_wallet(cb: types.CallbackQuery):
    if not is_admin_or_group(cb.from_user.id, cb.message.chat.id):
        await cb.answer("â›” ظ„ط§ طھظ…ظ„ظƒ طµظ„ط§ط­ظٹط©!", show_alert=True)
        return

    _, u_id, amt, msg_id = cb.data.split(":")
    u_id = int(u_id)
    amt = float(amt)
    msg_id = int(msg_id)
    if not await claim_admin_action(cb.message.chat.id, msg_id, "refund", cb.from_user.id):
        await cb.answer("âڑ ï¸ڈ ظ‡ط°ط§ ط§ظ„ط·ظ„ط¨ طھظ…طھ ظ…ط¹ط§ظ„ط¬طھظ‡ ظ…ط³ط¨ظ‚ط§ظ‹.", show_alert=True)
        return
    await add_user_balance(u_id, amt)
    try:
        await bot.send_message(u_id, f"â†©ï¸ڈ طھظ… ط¥ظ„ط؛ط§ط، ط§ظ„ط·ظ„ط¨ ظˆط¥ط±ط¬ط§ط¹ <b>{amt:,.2f} ظ„.ط³</b> ط¥ظ„ظ‰ ط±طµظٹط¯ ظ…ط­ظپط¸طھظƒ.")
        if cb.message.caption:
            await cb.message.edit_caption(caption=cb.message.caption + "\n\nًںں، <b>طھظ… ط§ظ„ط¥ظ„ط؛ط§ط، ظˆط§ط³طھط±ط¬ط§ط¹ ط§ظ„ظ…ط¨ظ„ط؛ ظ„ظ„ظ…ط­ظپط¸ط©</b>", reply_markup=None)
        elif cb.message.text:
            await cb.message.edit_text(text=cb.message.text + "\n\nًںں، <b>طھظ… ط§ظ„ط¥ظ„ط؛ط§ط، ظˆط§ط³طھط±ط¬ط§ط¹ ط§ظ„ظ…ط¨ظ„ط؛ ظ„ظ„ظ…ط­ظپط¸ط©</b>", reply_markup=None)
    except Exception as e:
        await cb.answer(f"ط®ط·ط£: {e}", show_alert=True)

# ----------------- ظ‚ط³ظ… ط§ظ„ط±طµظٹط¯ ظˆط§ظ„ظƒط§ط´ -----------------
@dp.callback_query(F.data == "sec_balance")
async def balance_menu(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="ًں”´ ط³ظٹط±ظٹطھظ„ (Syriatel)", callback_data="net:syr")],
        [InlineKeyboardButton(text="ًںں، ط¥ظ… طھظٹ ط¥ظ† (MTN)", callback_data="net:mtn")],
        [InlineKeyboardButton(text="ًں”™ ط§ظ„ظ‚ط§ط¦ظ…ط© ط§ظ„ط±ط¦ظٹط³ظٹط©", callback_data="back_main")]
    ]
    await cb.message.edit_text("ط§ط®طھط± ط§ظ„ط´ط¨ظƒط© ط§ظ„ظ…ط·ظ„ظˆط¨ط©:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("net:"))
async def net_menu(cb: types.CallbackQuery):
    net = cb.data.split(":")[1]
    name = "Syriatel" if net == "syr" else "MTN"
    kb = [
        [InlineKeyboardButton(text=f"ًں“² ظˆط­ط¯ط§طھ {name}", callback_data=f"bopt:{net}:units")],
        [InlineKeyboardButton(text=f"â›½ ط¬ظ…ظ„ط© {name} ظƒط§ط²ظٹط©", callback_data=f"bopt:{net}:station")],
        [InlineKeyboardButton(text=f"ًں§¾ ظپظˆط§طھظٹط± {name}", callback_data=f"bopt:{net}:invoice")],
        [InlineKeyboardButton(text=f"ًں’µ ظƒط§ط´ {name}", callback_data=f"bopt:{net}:cash")],
        [InlineKeyboardButton(text="ًں”™ ط±ط¬ظˆط¹", callback_data="sec_balance")]
    ]
    await cb.message.edit_text(f"ط®ط¯ظ…ط§طھ ط´ط¨ظƒط© {name}:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("bopt:"))
async def handle_bopt(cb: types.CallbackQuery, state: FSMContext):
    _, net, opt = cb.data.split(":")
    net_name = "Syriatel" if net == "syr" else "MTN"

    if opt == "units":
        items = SYR_UNITS if net == "syr" else MTN_UNITS
        buttons = []
        for idx, (u, p) in enumerate(items):
            buttons.append(InlineKeyboardButton(text=f"{u} â¬… {p}ظ„.ط³", callback_data=f"u_{net}_{idx}"))
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        rows.append([InlineKeyboardButton(text="ًں”™ ط±ط¬ظˆط¹", callback_data=f"net:{net}")])
        await cb.message.edit_text(f"ط§ط®طھط± ظپط¦ط© ظˆط­ط¯ط§طھ {net_name}:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

    elif opt == "station":
        buttons = []
        for idx, (a, p) in enumerate(STATION_VALS):
            buttons.append(InlineKeyboardButton(text=f"ظپط¦ط© {a} â¬… {p}ظ„.ط³", callback_data=f"s_{net}_{idx}"))
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        rows.append([InlineKeyboardButton(text="ًں”™ ط±ط¬ظˆط¹", callback_data=f"net:{net}")])
        await cb.message.edit_text(f"ط§ط®طھط± ظپط¦ط© ظƒط§ط²ظٹط© {net_name}:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

    elif opt == "invoice":
        await state.update_data(sec="balance", service=f"ظپظˆط§طھظٹط± {net_name}", net=net)
        if net == "syr":
            await state.set_state(OrderState.syr_invoice_num)
            await cb.message.edit_text("ط£ط¯ط®ظ„ ط±ظ‚ظ… ظپط§طھظˆط±ط© Syriatel:")
        else:
            await state.set_state(OrderState.mtn_invoice_num)
            await cb.message.edit_text("ط£ط¯ط®ظ„ ط±ظ‚ظ… ظپط§طھظˆط±ط© MTN:")

    elif opt == "cash":
        await state.update_data(sec="balance", service=f"ظƒط§ط´ {net_name}", net=net)
        if net == "syr":
            await state.set_state(OrderState.syr_cash_amt)
            await cb.message.edit_text("ط£ط¯ط®ظ„ ظƒظ…ظٹط© ظƒط§ط´ Syriatel ط§ظ„ظ…ط·ظ„ظˆط¨ط© (ط£ظ‚ظ„ ظƒظ…ظٹط© 1,000 ظ„.ط³):")
        else:
            await state.set_state(OrderState.mtn_cash_amt)
            await cb.message.edit_text("ط£ط¯ط®ظ„ ظƒظ…ظٹط© ظƒط§ط´ MTN ط§ظ„ظ…ط·ظ„ظˆط¨ط© (ط£ظ‚ظ„ ظƒظ…ظٹط© 1,000 ظ„.ط³):")

@dp.callback_query(F.data.startswith("u_"))
async def select_unit(cb: types.CallbackQuery, state: FSMContext):
    _, net, idx = cb.data.split("_")
    items = SYR_UNITS if net == "syr" else MTN_UNITS
    u, p = items[int(idx)]
    await state.update_data(sec="balance", service=f"ظˆط­ط¯ط§طھ {net.upper()}", unit=u, price=float(p), net=net)
    if net == "syr":
        await state.set_state(OrderState.syr_units_phone)
        await cb.message.edit_text("ط£ط¯ط®ظ„ ط±ظ‚ظ… ط³ظٹط±ظٹطھظ„ ط§ظ„ظ…ط·ظ„ظˆط¨ ط§ظ„طھط­ظˆظٹظ„ ط¥ظ„ظٹظ‡ (10 ط®ط§ظ†ط§طھ طھط¨ط¯ط£ ط¨ظ€ 09):")
    else:
        await state.set_state(OrderState.mtn_units_phone)
        await cb.message.edit_text("ط£ط¯ط®ظ„ ط±ظ‚ظ… MTN ط§ظ„ظ…ط·ظ„ظˆط¨ ط§ظ„طھط­ظˆظٹظ„ ط¥ظ„ظٹظ‡ (10 ط®ط§ظ†ط§طھ طھط¨ط¯ط£ ط¨ظ€ 09):")

@dp.message(OrderState.syr_units_phone)
async def proc_syr_u_phone(message: types.Message, state: FSMContext):
    p = message.text.strip()
    if not (p.isdigit() and len(p) == 10 and p.startswith("09")):
        await message.reply("âڑ ï¸ڈ ط±ظ‚ظ… ط³ظٹط±ظٹطھظ„ ظٹط¬ط¨ ط£ظ† ظٹظƒظˆظ† ظ…ط¤ظ„ظپط§ظ‹ ظ…ظ† 10 ط®ط§ظ†ط§طھ ظˆظٹط¨ط¯ط£ ط¨ظ€ 09:")
        return
    await state.update_data(target=f"ط±ظ‚ظ… ط³ظٹط±ظٹطھظ„: {p}")
    await prompt_payment(message, state, message.from_user.id)

@dp.message(OrderState.mtn_units_phone)
async def proc_mtn_u_phone(message: types.Message, state: FSMContext):
    p = message.text.strip()
    if not (p.isdigit() and len(p) == 10 and p.startswith("09")):
        await message.reply("âڑ ï¸ڈï¸ڈ ط±ظ‚ظ… MTN ظٹط¬ط¨ ط£ظ† ظٹظƒظˆظ† ظ…ط¤ظ„ظپط§ظ‹ ظ…ظ† 10 ط®ط§ظ†ط§طھ ظˆظٹط¨ط¯ط£ ط¨ظ€ 09:")
        return
    await state.update_data(target=f"ط±ظ‚ظ… MTN: {p}")
    await prompt_payment(message, state, message.from_user.id)

@dp.callback_query(F.data.startswith("s_"))
async def select_station(cb: types.CallbackQuery, state: FSMContext):
    _, net, idx = cb.data.split("_")
    a, p = STATION_VALS[int(idx)]
    await state.update_data(sec="balance", service=f"ط¬ظ…ظ„ط© ظƒط§ط²ظٹط© {net.upper()}", amount=a, price=float(p), net=net)
    if net == "syr":
        await state.set_state(OrderState.syr_station_code)
        await cb.message.edit_text("ط£ط¯ط®ظ„ ظƒظˆط¯ ظƒط§ط²ظٹط© Syriatel (ظ…ط¤ظ„ظپ ظ…ظ† 6 ط£ط±ظ‚ط§ظ…):")
    else:
        await state.set_state(OrderState.mtn_station_code)
        await cb.message.edit_text("ط£ط¯ط®ظ„ ظƒظˆط¯ ظƒط§ط²ظٹط© MTN:")

@dp.message(OrderState.syr_station_code)
async def proc_syr_st_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if not (code.isdigit() and len(code) == 6):
        await message.reply("âڑ ï¸ڈ ظƒظˆط¯ ظƒط§ط²ظٹط© ط³ظٹط±ظٹطھظ„ ظٹط¬ط¨ ط£ظ† ظٹطھظƒظˆظ† ظ…ظ† 6 ط£ط±ظ‚ط§ظ… ط­طµط±ط§ظ‹:")
        return
    await state.update_data(st_code=code)
    await state.set_state(OrderState.syr_station_gov)
    buttons = [InlineKeyboardButton(text=g, callback_data=f"gov_syr:{g}") for g in GOVERNORATES]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    await message.answer("ط§ط®طھط± ط§ظ„ظ…ط­ط§ظپط¸ط©:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("gov_syr:"), OrderState.syr_station_gov)
async def proc_syr_st_gov(cb: types.CallbackQuery, state: FSMContext):
    gov = cb.data.split(":")[1]
    data = await state.get_data()
    target_info = f"ظƒظˆط¯ ظƒط§ط²ظٹط©: {data.get('st_code')} | ط§ظ„ظ…ط­ط§ظپط¸ط©: {gov}"
    await state.update_data(target=target_info)
    await prompt_payment_cb(cb, state)

@dp.message(OrderState.mtn_station_code)
async def proc_mtn_st_code(message: types.Message, state: FSMContext):
    await state.update_data(st_code=message.text.strip())
    await state.set_state(OrderState.mtn_station_num)
    await message.answer("ط£ط¯ط®ظ„ ط±ظ‚ظ… ظƒط§ط²ظٹط© MTN:")

@dp.message(OrderState.mtn_station_num)
async def proc_mtn_st_num(message: types.Message, state: FSMContext):
    await state.update_data(st_num=message.text.strip())
    await state.set_state(OrderState.mtn_station_gov)
    buttons = [InlineKeyboardButton(text=g, callback_data=f"gov_mtn:{g}") for g in GOVERNORATES]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    await message.answer("ط§ط®طھط± ط§ظ„ظ…ط­ط§ظپط¸ط©:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("gov_mtn:"), OrderState.mtn_station_gov)
async def proc_mtn_st_gov(cb: types.CallbackQuery, state: FSMContext):
    gov = cb.data.split(":")[1]
    data = await state.get_data()
    target_info = f"ظƒظˆط¯: {data.get('st_code')} | ط±ظ‚ظ…: {data.get('st_num')} | ط§ظ„ظ…ط­ط§ظپط¸ط©: {gov}"
    await state.update_data(target=target_info)
    await prompt_payment_cb(cb, state)

@dp.message(OrderState.syr_invoice_num)
async def proc_syr_inv_num(message: types.Message, state: FSMContext):
    await state.update_data(inv_num=message.text.strip())
    await state.set_state(OrderState.syr_invoice_amt)
    await message.answer("ط£ط¯ط®ظ„ ظ‚ظٹظ…ط© ط§ظ„ظپط§طھظˆط±ط© ط¨ط§ظ„ظ„ظٹط±ط© ط§ظ„ط³ظˆط±ظٹط©:")

@dp.message(OrderState.syr_invoice_amt)
async def proc_syr_inv_amt(message: types.Message, state: FSMContext):
    try:
        amt = float(message.text.strip())
        if amt <= 0:
            await message.reply("âڑ ï¸ڈ ظٹط¬ط¨ ط£ظ† طھظƒظˆظ† ط§ظ„ظ‚ظٹظ…ط© ط£ظƒط¨ط± ظ…ظ† طµظپط±:")
            return
        final_price = round(amt * 1.05)
        data = await state.get_data()
        await state.update_data(target=f"ظپط§طھظˆط±ط© ط³ظٹط±ظٹطھظ„: {data.get('inv_num')} | ط§ظ„ظ‚ظٹظ…ط©: {amt}", price=final_price)
        await prompt_payment(message, state, message.from_user.id)
    except Exception:
        await message.reply("âڑ ï¸ڈ ط£ط¯ط®ظ„ ظ‚ظٹظ…ط© طµط­ظٹط­ط© ط¨ط§ظ„ط£ط±ظ‚ط§ظ…:")

@dp.message(OrderState.mtn_invoice_num)
async def proc_mtn_inv_num(message: types.Message, state: FSMContext):
    await state.update_data(inv_num=message.text.strip())
    await state.set_state(OrderState.mtn_invoice_amt)
    await message.answer("ط£ط¯ط®ظ„ ظ‚ظٹظ…ط© ط§ظ„ظپط§طھظˆط±ط© ط¨ط§ظ„ظ„ظٹط±ط© ط§ظ„ط³ظˆط±ظٹط©:")

@dp.message(OrderState.mtn_invoice_amt)
async def proc_mtn_inv_amt(message: types.Message, state: FSMContext):
    try:
        amt = float(message.text.strip())
        if amt <= 0:
            await message.reply("âڑ ï¸ڈ ظٹط¬ط¨ ط£ظ† طھظƒظˆظ† ط§ظ„ظ‚ظٹظ…ط© ط£ظƒط¨ط± ظ…ظ† طµظپط±:")
            return
        final_price = round(amt * 1.05)
        data = await state.get_data()
        await state.update_data(target=f"ظپط§طھظˆط±ط© MTN: {data.get('inv_num')} | ط§ظ„ظ‚ظٹظ…ط©: {amt}", price=final_price)
        await prompt_payment(message, state, message.from_user.id)
    except Exception:
        await message.reply("âڑ ï¸ڈ ط£ط¯ط®ظ„ ظ‚ظٹظ…ط© طµط­ظٹط­ط© ط¨ط§ظ„ط£ط±ظ‚ط§ظ…:")

@dp.message(OrderState.syr_cash_amt)
async def proc_syr_cash_amt(message: types.Message, state: FSMContext):
    try:
        amt = float(message.text.strip())
        if amt < 1000:
            await message.reply("âڑ ï¸ڈ ط£ظ‚ظ„ ظƒظ…ظٹط© ظ‡ظٹ 1,000 ظ„.ط³:")
            return
        final_price = round(amt * 1.05)
        await state.update_data(price=final_price, amount=amt)
        await state.set_state(OrderState.syr_cash_id)
        await message.answer("ط£ط¯ط®ظ„ ظ…ط¹ط±ظ‘ظپ Player-ID ظ„ط§ط³طھظ„ط§ظ… ظƒط§ط´ Syriatel:")
    except Exception:
        await message.reply("âڑ ï¸ڈ ط£ط¯ط®ظ„ ظ‚ظٹظ…ط© طµط­ظٹط­ط© ط¨ط§ظ„ط£ط±ظ‚ط§ظ…:")

@dp.message(OrderState.syr_cash_id)
async def proc_syr_cash_id(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(target=f"Player-ID: {message.text.strip()} | ط§ظ„ظƒظ…ظٹط©: {data.get('amount')}")
    await prompt_payment(message, state, message.from_user.id)

@dp.message(OrderState.mtn_cash_amt)
async def proc_mtn_cash_amt(message: types.Message, state: FSMContext):
    try:
        amt = float(message.text.strip())
        if amt < 1000:
            await message.reply("âڑ ï¸ڈ ط£ظ‚ظ„ ظƒظ…ظٹط© ظ‡ظٹ 1,000 ظ„.ط³:")
            return
        final_price = round(amt * 1.05)
        await state.update_data(price=final_price, amount=amt)
        await state.set_state(OrderState.mtn_cash_num)
        await message.answer("ط£ط¯ط®ظ„ ط±ظ‚ظ… ظƒط§ط´ MTN ط§ظ„ظ…ط·ظ„ظˆط¨ ط§ظ„طھط­ظˆظٹظ„ ط¥ظ„ظٹظ‡:")
    except Exception:
        await message.reply("âڑ ï¸ڈ ط£ط¯ط®ظ„ ظ‚ظٹظ…ط© طµط­ظٹط­ط© ط¨ط§ظ„ط£ط±ظ‚ط§ظ…:")

@dp.message(OrderState.mtn_cash_num)
async def proc_mtn_cash_num(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(target=f"ط±ظ‚ظ… ظƒط§ط´ MTN: {message.text.strip()} | ط§ظ„ظƒظ…ظٹط©: {data.get('amount')}")
    await prompt_payment(message, state, message.from_user.id)

# ----------------- ظ‚ط³ظ… ط´ط­ظ† ط§ظ„ط£ظ„ط¹ط§ط¨ -----------------
@dp.callback_query(F.data == "sec_games")
async def games_menu(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="ًں”« ط¨ط¨ط¬ظٹ (PUBG)", callback_data="game:pubg")],
        [InlineKeyboardButton(text="ًں”¥ ظپط±ظٹ ظپط§ظٹط± (Free Fire)", callback_data="game:ff")],
        [InlineKeyboardButton(text="ًںƒڈ ط¬ظˆط§ظƒط± (Jawaker)", callback_data="game:jawaker")],
        [InlineKeyboardButton(text="âڑ”ï¸ڈ ظƒظ„ط§ط´ ط£ظˆظپ ظƒظ„ط§ظ†ط³ (CoC)", callback_data="game:coc")],
        [InlineKeyboardButton(text="ًںژ® ط¨ط§ظ‚ظٹ ط§ظ„ط£ظ„ط¹ط§ط¨ (31 ظ„ط¹ط¨ط©) [ط·ظ„ط¨ طھط³ط¹ظٹط±]", callback_data="quote:game")],
        [InlineKeyboardButton(text="ًں”™ ط§ظ„ظ‚ط§ط¦ظ…ط© ط§ظ„ط±ط¦ظٹط³ظٹط©", callback_data="back_main")]
    ]
    await cb.message.edit_text("ط§ط®طھط± ط§ظ„ظ„ط¹ط¨ط© ط§ظ„ظ…ط·ظ„ظˆط¨ط©:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("game:"))
async def game_packs_view(cb: types.CallbackQuery):
    g_key = cb.data.split(":")[1]
    rate = await get_setting("dollar_rate")
    buttons = []
    for idx, (p_name, p_usd) in enumerate(GAME_PACKS[g_key]):
        price_syr = round(p_usd * rate)
        buttons.append([InlineKeyboardButton(text=f"{p_name} â¬… {price_syr} ظ„.ط³", callback_data=f"buyg:{g_key}:{idx}")])
    buttons.append([InlineKeyboardButton(text="ًں”™ ط±ط¬ظˆط¹ ظ„ظ„ط£ظ„ط¹ط§ط¨", callback_data="sec_games")])
    await cb.message.edit_text("ط§ط®طھط± ط§ظ„ط¨ط§ظ‚ط© ط§ظ„ظ…ط·ظ„ظˆط¨ط©:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("buyg:"))
async def buy_game_pack(cb: types.CallbackQuery, state: FSMContext):
    _, g_key, idx = cb.data.split(":")
    p_name, p_usd = GAME_PACKS[g_key][int(idx)]
    rate = await get_setting("dollar_rate")
    price_syr = round(p_usd * rate)
    await state.update_data(sec="games", service=f"ط´ط­ظ† {g_key.upper()} ({p_name})", price=price_syr)
    await state.set_state(OrderState.entering_game_data)
    await cb.message.edit_text("ط£ط¯ط®ظ„ ط§ظ„ط¢ظٹط¯ظٹ (Player ID) ظˆط§ط³ظ… ط­ط³ط§ط¨ظƒ ظپظٹ ط§ظ„ظ„ط¹ط¨ط©:")

@dp.message(OrderState.entering_game_data)
async def proc_game_data(message: types.Message, state: FSMContext):
    await state.update_data(target=f"ط¢ظٹط¯ظٹ ط§ظ„ظ„ط¹ط¨ط©: {message.text.strip()}")
    await prompt_payment(message, state, message.from_user.id)

# ----------------- ظ‚ط³ظ… طھط·ط¨ظٹظ‚ط§طھ ط§ظ„ط´ط§طھ -----------------
@dp.callback_query(F.data == "sec_chat")
async def chat_menu(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="ًںŒں Soul Star (ظƒظˆظٹظ†ط² أ— 0.025)", callback_data="chat:soulstar")],
        [InlineKeyboardButton(text="â‌„ï¸ڈ Soulchill (ظƒط±ظٹط³طھط§ظ„ أ— 0.30)", callback_data="chat:soulchill")],
        [InlineKeyboardButton(text="ًں’¬ IMO (ط£ظ„ظ…ط§ط³ أ— 0.50)", callback_data="chat:imo")],
        [InlineKeyboardButton(text="ًں—£ Talsa chat (ظƒظˆظٹظ†ط² أ— 0.02)", callback_data="chat:talsa")],
        [InlineKeyboardButton(text="ًں”چ ط¨ط§ظ‚ظٹ ط§ظ„طھط·ط¨ظٹظ‚ط§طھ (186 طھط·ط¨ظٹظ‚) [طھط³ط¹ظٹط±]", callback_data="quote:chat")],
        [InlineKeyboardButton(text="ًں”™ ط§ظ„ظ‚ط§ط¦ظ…ط© ط§ظ„ط±ط¦ظٹط³ظٹط©", callback_data="back_main")]
    ]
    await cb.message.edit_text("ط§ط®طھط± طھط·ط¨ظٹظ‚ ط§ظ„ط´ط§طھ ط§ظ„ظ…ط·ظ„ظˆط¨:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("chat:"))
async def chat_calc_prompt(cb: types.CallbackQuery, state: FSMContext):
    c_key = cb.data.split(":")[1]
    await state.update_data(sec="games", chat_app=c_key)
    await state.set_state(OrderState.entering_chat_qty)
    await cb.message.edit_text("ط£ط¯ط®ظ„ (ط§ظ„ط¢ظٹط¯ظٹ) ظ…طھط¨ظˆط¹ط§ظ‹ ط¨ظ€ (ط§ظ„ظƒظ…ظٹط© ط§ظ„ظ…ط·ظ„ظˆط¨ط©):\nظ…ط«ط§ظ„: <code>123456 5000</code>")

@dp.message(OrderState.entering_chat_qty)
async def proc_chat_calc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    c_key = data.get("chat_app")
    try:
        parts = message.text.strip().split()
        u_id = parts[0]
        qty = float(parts[1])
        if qty <= 0:
            await message.reply("âڑ ï¸ڈ ط§ظ„ظƒظ…ظٹط© ظٹط¬ط¨ ط£ظ† طھظƒظˆظ† ط£ظƒط¨ط± ظ…ظ† طµظپط±.")
            return

        if c_key == "soulstar":
            price = round(qty * 0.025)
            s_name = "Soul Star"
        elif c_key == "soulchill":
            price = round(qty * 0.30)
            s_name = "Soulchill"
        elif c_key == "talsa":
            price = round(qty * 0.02)
            s_name = "Talsa chat"
        else:
            price = round(qty * 0.50)
            s_name = "IMO"

        await state.update_data(service=f"ط´ط­ظ† {s_name}", target=f"ط§ظ„ط¢ظٹط¯ظٹ: {u_id} | ط§ظ„ظƒظ…ظٹط©: {qty}", price=price)
        await prompt_payment(message, state, message.from_user.id)
    except Exception:
        await message.reply("âڑ ï¸ڈ ط£ط±ط³ظ„ ط§ظ„ط¢ظٹط¯ظٹ ط«ظ… ط§ظ„ظƒظ…ظٹط© ظˆط¨ظٹظ†ظ‡ظ…ط§ ظ…ط³ط§ظپط© ط¨ط´ظƒظ„ طµط­ظٹط­.")

# ----------------- ظ‚ط³ظ… ط§ظ„ط­ط³ط§ط¨ط§طھ ظˆط§ظ„ط§ط´طھط±ط§ظƒط§طھ -----------------
@dp.callback_query(F.data == "sec_accounts")
async def accounts_menu(cb: types.CallbackQuery):
    kb = []
    for k, (name, price) in FAST_ACCOUNTS.items():
        kb.append([InlineKeyboardButton(text=f"ًں”¹ {name} ({price:,} ظ„.ط³)", callback_data=f"facc:{k}")])
    kb.append([InlineKeyboardButton(text="ًں“‹ ط¨ط§ظ‚ظٹ ط§ظ„ط­ط³ط§ط¨ط§طھ (27 ط®ط¯ظ…ط©) [طھطµظپط­]", callback_data="acc_page:0")])
    kb.append([InlineKeyboardButton(text="ًں”™ ط§ظ„ظ‚ط§ط¦ظ…ط© ط§ظ„ط±ط¦ظٹط³ظٹط©", callback_data="back_main")])
    await cb.message.edit_text("ط§ط®طھط± ط§ظ„ط­ط³ط§ط¨ ط§ظ„ط¬ط§ظ‡ط² ط§ظ„ظ…ط·ظ„ظˆط¨:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("facc:"))
async def acc_fast_confirm(cb: types.CallbackQuery, state: FSMContext):
    k = cb.data.split(":")[1]
    name, price = FAST_ACCOUNTS[k]
    await state.update_data(sec="accounts", service=f"ط­ط³ط§ط¨ {name}", price=float(price), target="ط­ط³ط§ط¨ ط±ط³ظ…ظٹ ظ…ط¹ ط§ظ„ط¶ظ…ط§ظ†")
    await prompt_payment_cb(cb, state)

@dp.callback_query(F.data.startswith("acc_page:"))
async def extra_accounts_pages(cb: types.CallbackQuery):
    page = int(cb.data.split(":")[1])
    per_page = 6
    start = page * per_page
    end = start + per_page
    items = ACCOUNTS_LIST[start:end]

    buttons = []
    for idx, item in enumerate(items):
        real_idx = start + idx
        buttons.append([InlineKeyboardButton(text=f"ًں”¹ {item}", callback_data=f"sel_acc:{real_idx}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="â¬…ï¸ڈ ط§ظ„ط³ط§ط¨ظ‚", callback_data=f"acc_page:{page-1}"))
    if end < len(ACCOUNTS_LIST):
        nav.append(InlineKeyboardButton(text="ط§ظ„طھط§ظ„ظٹ â‍،ï¸ڈ", callback_data=f"acc_page:{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="ًں”™ ط±ط¬ظˆط¹ ظ„ظ„ط­ط³ط§ط¨ط§طھ", callback_data="sec_accounts")])
    await cb.message.edit_text(f"ط§ط®طھط± ط§ظ„ط­ط³ط§ط¨ ط§ظ„ظ…ط·ظ„ظˆط¨ (طµظپط­ط© {page+1} ظ…ظ† {(len(ACCOUNTS_LIST) + per_page - 1) // per_page}):", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("sel_acc:"))
async def account_select_duration(cb: types.CallbackQuery, state: FSMContext):
    idx = int(cb.data.split(":")[1])
    acc_name = ACCOUNTS_LIST[idx]
    await state.update_data(selected_acc_name=acc_name)

    kb = [
        [InlineKeyboardButton(text="âڈ³ ط§ط´طھط±ط§ظƒ ط´ظ‡ط±", callback_data="acc_dur:ط´ظ‡ط±")],
        [InlineKeyboardButton(text="âڈ³ ط§ط´طھط±ط§ظƒ 3 ط£ط´ظ‡ط±", callback_data="acc_dur:3 ط£ط´ظ‡ط±")],
        [InlineKeyboardButton(text="âڈ³ ط§ط´طھط±ط§ظƒ ط³ظ†ط©", callback_data="acc_dur:ط³ظ†ط©")],
        [InlineKeyboardButton(text="ًں”™ ط±ط¬ظˆط¹ ظ„ظ„ظ‚ط§ط¦ظ…ط©", callback_data="acc_page:0")]
    ]
    await cb.message.edit_text(
        f"ظ„ظ‚ط¯ ط§ط®طھط±طھ: <b>{html.escape(acc_name)}</b>\n\nط§ط®طھط± ط§ظ„ظ…ط¯ط© ط§ظ„ظ…ط·ظ„ظˆط¨ط© ط¨ط§ظ„ط¶ط؛ط· ط¹ظ„ظ‰ ط§ظ„ط²ط± ط£ط¯ظ†ط§ظ‡:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

@dp.callback_query(F.data.startswith("acc_dur:"))
async def account_duration_finish(cb: types.CallbackQuery, state: FSMContext):
    dur = cb.data.split(":")[1]
    data = await state.get_data()
    acc_name = data.get("selected_acc_name", "ط­ط³ط§ط¨ ظ…ظ…ظٹط²")

    group_id = GROUPS["accounts"]
    user_info = f"@{html.escape(cb.from_user.username)}" if cb.from_user.username else "ط¨ط¯ظˆظ† ظٹظˆط²ط±"
    text_to_group = (
        f"ًں“© <b>ط·ظ„ط¨ ط­ط³ط§ط¨ ط¬ط§ظ‡ط²:</b>\n"
        f"ًں‘¤ ط§ظ„ط²ط¨ظˆظ†: {user_info} (<code>{cb.from_user.id}</code>)\n"
        f"ًںڈ· ط§ظ„ط­ط³ط§ط¨: <b>{html.escape(acc_name)}</b>\n"
        f"âڈ³ ط§ظ„ظ…ط¯ط©: <b>{html.escape(dur)}</b>\n\n"
        f"ًں’، ظ„طھط³ط¹ظٹط± ط§ظ„ط·ظ„ط¨ ظˆط§ظ„ط±ط¯ ط¹ظ„ظ‰ ط§ظ„ط²ط¨ظˆظ†طŒ ظ‚ظ… ط¨ط¹ظ…ظ„ ط±ط¯ (Reply) ظ…ط¨ط§ط´ط± ط¹ظ„ظ‰ ظ‡ط°ظ‡ ط§ظ„ط±ط³ط§ظ„ط©."
    )
    await bot.send_message(group_id, text_to_group)
    text, menu_kb = await main_menu_text_and_kb(cb.from_user.id, cb.from_user.username or "")
    await cb.message.edit_text(
        f"âœ… طھظ… ط¥ط±ط³ط§ظ„ ط·ظ„ط¨ظƒ ظ„ط­ط³ط§ط¨ <b>{html.escape(acc_name)}</b> ({dur}) ظ„ظ„ط¥ط¯ط§ط±ط© ط¨ظ†ط¬ط§ط­.\n"
        f"ط³ظٹطھظ… ط§ظ„ط±ط¯ ط¹ظ„ظٹظƒ ظ‡ظ†ط§ ط¨ط§ظ„طھظپط§طµظٹظ„ ظˆط§ظ„ط³ط¹ط± ظ‚ط±ظٹط¨ط§ظ‹.",
        reply_markup=menu_kb
    )

# ----------------- ظ‚ط³ظ… ط§ظ„ط³ظˆط´ظٹط§ظ„ ظ…ظٹط¯ظٹط§ -----------------
@dp.callback_query(F.data == "sec_social")
async def social_menu(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="ًں“ک ط®ط¯ظ…ط§طھ ظپظٹط³ط¨ظˆظƒ", callback_data="soc:fb")],
        [InlineKeyboardButton(text="ًں“¸ ط®ط¯ظ…ط§طھ ط¥ظ†ط³طھط؛ط±ط§ظ…", callback_data="soc:ig")],
        [InlineKeyboardButton(text="âœˆ ط®ط¯ظ…ط§طھ طھظ„ط؛ط±ط§ظ…", callback_data="soc:tg")],
        [InlineKeyboardButton(text="ًں“¢ ط¥ط¹ظ„ط§ظ†ط§طھ ظ…ظ…ظˆظ„ط© ظپظٹط³ط¨ظˆظƒ", callback_data="soc:ads")],
        [InlineKeyboardButton(text="ًں”™ ط§ظ„ظ‚ط§ط¦ظ…ط© ط§ظ„ط±ط¦ظٹط³ظٹط©", callback_data="back_main")]
    ]
    await cb.message.edit_text("ط§ط®طھط± ظ…ظ†طµط© ط§ظ„ط³ظˆط´ظٹط§ظ„ ظ…ظٹط¯ظٹط§:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("soc:"))
async def soc_platforms(cb: types.CallbackQuery):
    plat = cb.data.split(":")[1]
    if plat in ["fb", "ig", "tg"]:
        kb = []
        for code, (title, price, p_type) in SOCIAL_PACKS.items():
            if p_type == plat:
                kb.append([InlineKeyboardButton(text=f"ًں”¹ {title} ({price:,} ظ„.ط³)", callback_data=f"spk:{code}")])
        kb.append([InlineKeyboardButton(text="ًں”™ ط±ط¬ظˆط¹", callback_data="sec_social")])
        await cb.message.edit_text("ط§ط®طھط± ط§ظ„ط¨ط§ظ‚ط© ط§ظ„ظ…ط·ظ„ظˆط¨ط©:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    elif plat == "ads":
        buttons = []
        for d, p in [
            (1, 600), (2, 1100), (3, 1500), (4, 2000), (5, 2500),
            (6, 3000), (7, 3600), (10, 5000)
        ]:
            buttons.append(InlineKeyboardButton(text=f"ط¥ط¹ظ„ط§ظ† {d} ط£ظٹط§ظ… â¬… {p}ظ„.ط³", callback_data=f"ad_f:{d}:{p}"))
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        rows.append([InlineKeyboardButton(text="âڑ™ ظ…ط¯ط© ظ…ط®طµطµط© (200 ظ„.ط³/ظٹظˆظ…)", callback_data="ad_c")])
        rows.append([InlineKeyboardButton(text="ًں”™ ط±ط¬ظˆط¹", callback_data="sec_social")])
        await cb.message.edit_text("ط§ط®طھط± ظ…ط¯ط© ط§ظ„ط¥ط¹ظ„ط§ظ† ط§ظ„ظ…ظ…ظˆظ„:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("spk:"))
async def soc_buy(cb: types.CallbackQuery, state: FSMContext):
    code = cb.data.split(":")[1]
    title, price, plat = SOCIAL_PACKS[code]
    await state.update_data(sec="social", service=f"{plat.upper()} - {title}", price=float(price))
    await state.set_state(OrderState.entering_social_link)
    await cb.message.edit_text("ط£ط±ط³ظ„ ط§ظ„ط¢ظ† ط±ط§ط¨ط· ط§ظ„ط­ط³ط§ط¨ ط£ظˆ ط§ظ„ظ…ظ†ط´ظˆط± ط§ظ„ظ…ط·ظ„ظˆط¨:")

@dp.message(OrderState.entering_social_link)
async def proc_soc_link(message: types.Message, state: FSMContext):
    await state.update_data(target=message.text.strip())
    await prompt_payment(message, state, message.from_user.id)

@dp.callback_query(F.data.startswith("ad_f:"))
async def ad_f_click(cb: types.CallbackQuery, state: FSMContext):
    _, d, p = cb.data.split(":")
    await state.update_data(sec="social", service=f"ط¥ط¹ظ„ط§ظ† ظ…ظ…ظˆظ„ ({d} ط£ظٹط§ظ…)", price=float(p))
    await state.set_state(OrderState.entering_ad_phone)
    await cb.message.edit_text("ط£ط¯ط®ظ„ ط±ظ‚ظ… ظ‡ط§طھظپظƒ ظ„ظ„طھظˆط§طµظ„ ظˆطھط¬ظ‡ظٹط² طھظپط§طµظٹظ„ ط§ظ„ط¥ط¹ظ„ط§ظ†:")

@dp.callback_query(F.data == "ad_c")
async def ad_c_click(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.entering_custom_ad_days)
    await cb.message.edit_text("ط£ط¯ط®ظ„ ط¹ط¯ط¯ ط§ظ„ط£ظٹط§ظ… ط§ظ„ظ…ط·ظ„ظˆط¨ط© (ط§ظ„ظٹظˆظ… = 200 ظ„.ط³):")

@dp.message(OrderState.entering_custom_ad_days)
async def proc_c_ad(message: types.Message, state: FSMContext):
    try:
        days = int(message.text.strip())
        if days <= 0:
            await message.reply("âڑ ï¸ڈ ط¹ط¯ط¯ ط§ظ„ط£ظٹط§ظ… ظٹط¬ط¨ ط£ظ† ظٹظƒظˆظ† ط£ظƒط¨ط± ظ…ظ† طµظپط±:")
            return
        price = days * 200
        await state.update_data(sec="social", service=f"ط¥ط¹ظ„ط§ظ† ظ…ط®طµطµ ({days} ط£ظٹط§ظ…)", price=float(price))
        await state.set_state(OrderState.entering_ad_phone)
        await message.answer("ط£ط¯ط®ظ„ ط±ظ‚ظ… ظ‡ط§طھظپظƒ ظ„ظ„طھظˆط§طµظ„:")
    except Exception:
        await message.reply("âڑ ï¸ڈï¸ڈ ط£ط¯ط®ظ„ ط¹ط¯ط¯ط§ظ‹ طµط­ظٹط­ط§ظ‹ ط¨ط§ظ„ط£ط±ظ‚ط§ظ…:")

@dp.message(OrderState.entering_ad_phone)
async def proc_ad_phone(message: types.Message, state: FSMContext):
    await state.update_data(target=f"ط±ظ‚ظ… طھظˆط§طµظ„ ط§ظ„ط¥ط¹ظ„ط§ظ†: {message.text.strip()}")
    await prompt_payment(message, state, message.from_user.id)

@dp.callback_query(F.data == "sec_numbers")
async def numbers_menu(cb: types.CallbackQuery):
    p_wa = await get_setting("num_whatsapp")
    p_tg = await get_setting("num_telegram")
    kb = [
        [InlineKeyboardButton(text=f"ًںں¢ ط±ظ‚ظ… ظˆط§طھط³ط§ط¨ ط£ط¬ظ†ط¨ظٹ ({p_wa} ظ„.ط³)", callback_data="buyn:whatsapp")],
        [InlineKeyboardButton(text=f"ًں”µ ط±ظ‚ظ… طھظ„ط؛ط±ط§ظ… ط£ظ…ط±ظٹظƒظٹ ({p_tg} ظ„.ط³)", callback_data="buyn:telegram")],
        [InlineKeyboardButton(text="ًں“± ط±ظ‚ظ… طھظٹظƒ طھظˆظƒ [ط·ظ„ط¨ طھط³ط¹ظٹط±]", callback_data="quote:num_tiktok")],
        [InlineKeyboardButton(text="ًںŒگ طھظپط¹ظٹظ„ ط؛ظˆط؛ظ„ [ط·ظ„ط¨ طھط³ط¹ظٹط±]", callback_data="quote:num_google")],
        [InlineKeyboardButton(text="ًںچژ طھظپط¹ظٹظ„ ط¢ط¨ظ„ [ط·ظ„ط¨ طھط³ط¹ظٹط±]", callback_data="quote:num_apple")],
        [InlineKeyboardButton(text="ًں”™ ط§ظ„ظ‚ط§ط¦ظ…ط© ط§ظ„ط±ط¦ظٹط³ظٹط©", callback_data="back_main")]
    ]
    await cb.message.edit_text("ظ‚ط³ظ… ط£ط±ظ‚ط§ظ… ط§ظ„طھظپط¹ظٹظ„:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("buyn:"))
async def buy_num_fast(cb: types.CallbackQuery, state: FSMContext):
    target = cb.data.split(":")[1]
    price = await get_setting(f"num_{target}")
    name = "ظˆط§طھط³ط§ط¨ ط£ط¬ظ†ط¨ظٹ" if target == "whatsapp" else "طھظ„ط؛ط±ط§ظ… ط£ظ…ط±ظٹظƒظٹ"
    await state.update_data(sec="social", service=f"ط±ظ‚ظ… {name}", price=price, target="ط±ط§ط¨ط· طھظپط¹ظٹظ„")
    await prompt_payment_cb(cb, state)

# ----------------- ط·ظ„ط¨ط§طھ ط§ظ„طھط³ط¹ظٹط± -----------------
@dp.callback_query(F.data.startswith("quote:"))
async def generic_quote_start(cb: types.CallbackQuery, state: FSMContext):
    q_type = cb.data.split(":")[1]
    g_map = {
        "game": ("games", "ًںژ® ط·ظ„ط¨ طھط³ط¹ظٹط± ظ„ط¹ط¨ط©"),
        "chat": ("games", "ًں’¬ ط·ظ„ط¨ طھط³ط¹ظٹط± طھط·ط¨ظٹظ‚ ط´ط§طھ"),
        "num_tiktok": ("social", "ًں“± ط·ظ„ط¨ ط±ظ‚ظ… طھظٹظƒ طھظˆظƒ"),
        "num_google": ("social", "ًںŒگ ط·ظ„ط¨ طھظپط¹ظٹظ„ ط؛ظˆط؛ظ„"),
        "num_apple": ("social", "ًںچژ ط·ظ„ط¨ طھظپط¹ظٹظ„ ط¢ط¨ظ„")
    }
    sec, label = g_map.get(q_type, ("games", "ط·ظ„ط¨ ط¹ط§ظ…"))
    await state.update_data(q_sec=sec, q_label=label)
    await state.set_state(QuoteState.entering_quote_text)
    await cb.message.answer(
        "âœچï¸ڈ ظٹط±ط¬ظ‰ ظƒطھط§ط¨ط© طھظپط§طµظٹظ„ ط·ظ„ط¨ظƒ ط§ظ„ط¢ظ† ط¨ط§ظ„طھظپطµظٹظ„:\n"
        "(ط§ط³ظ… ط§ظ„ط®ط¯ظ…ط© ط£ظˆ ط§ظ„ظ„ط¹ط¨ط© + ط§ظ„ط¢ظٹط¯ظٹ + ط§ظ„ظƒظ…ظٹط© ط§ظ„ظ…ط·ظ„ظˆط¨ط©):"
    )
    await cb.answer()

@dp.message(QuoteState.entering_quote_text)
async def generic_quote_receive(message: types.Message, state: FSMContext):
    if not message.text:
        await message.reply("âڑ ï¸ڈ ظٹط±ط¬ظ‰ ط¥ط±ط³ط§ظ„ طھظپط§طµظٹظ„ ط§ظ„ط·ظ„ط¨ ظƒظ†طµ:")
        return

    data = await state.get_data()
    sec = data.get("q_sec", "games")
    label = data.get("q_label", "ط·ظ„ط¨ طھط³ط¹ظٹط±")
    group_id = GROUPS.get(sec, GROUPS["games"])

    user_info = f"@{html.escape(message.from_user.username)}" if message.from_user.username else "ط¨ط¯ظˆظ† ظٹظˆط²ط±"
    text_to_group = (
        f"ًں“© <b>{html.escape(label)}:</b>\n"
        f"ًں‘¤ ط§ظ„ط²ط¨ظˆظ†: {user_info} (<code>{message.from_user.id}</code>)\n"
        f"ًں“‌ <b>ط§ظ„طھظپط§طµظٹظ„:</b>\n{html.escape(message.text)}\n\n"
        f"ًں’، ظ„طھط³ط¹ظٹط± ط§ظ„ط·ظ„ط¨ ظˆط§ظ„ط±ط¯ ط¹ظ„ظ‰ ط§ظ„ط²ط¨ظˆظ†طŒ ظ‚ظ… ط¨ط¹ظ…ظ„ ط±ط¯ (Reply) ظ…ط¨ط§ط´ط± ط¹ظ„ظ‰ ظ‡ط°ظ‡ ط§ظ„ط±ط³ط§ظ„ط© ظˆط§ظƒطھط¨ ط§ظ„ط³ط¹ط± ظˆط§ظ„طھظپط§طµظٹظ„."
    )
    await bot.send_message(group_id, text_to_group)
    await state.clear()
    text, menu_kb = await main_menu_text_and_kb(message.from_user.id, message.from_user.username or "")
    await message.answer(
        "âœ… طھظ… ط§ط³طھظ„ط§ظ… ط·ظ„ط¨ظƒ ظˆط¥ط±ط³ط§ظ„ظ‡ ظ„ظ„ط¥ط¯ط§ط±ط© ط¨ظ†ط¬ط§ط­. ط³ظٹطھظ… ظ…ط±ط§ط¬ط¹طھظ‡ ظˆط§ظ„ط±ط¯ ط¹ظ„ظٹظƒ ظ‡ظ†ط§ ظ‚ط±ظٹط¨ط§ظ‹ ط¨ط§ظ„ط³ط¹ط±.",
        reply_markup=menu_kb
    )

# ----------------- ظ…ط¹ط§ظ„ط¬ط© ط§ظ„ط±ط¯ظˆط¯ ظ…ظ† ط§ظ„ط¥ط¯ط§ط±ط© -----------------
@dp.message(F.chat.id.in_(ALL_ADMIN_GROUPS), F.reply_to_message)
async def admin_group_reply_handler(message: types.Message):
    # ط§ظ„طھط­ظ‚ظ‚ ظ…ظ† ط£ظ† ط§ظ„ط±ط³ط§ظ„ط© ط§ظ„ط£طµظ„ظٹط© طھط®طµ ط§ظ„ط¨ظˆطھ
    if not message.reply_to_message.from_user.is_bot:
        return

    admin_reply_text = message.text or message.caption
    if not admin_reply_text:
        return

    orig = message.reply_to_message.text or message.reply_to_message.caption or ""
    match = re.search(r"\(<code>(\d+)</code>\)", orig)
    if not match:
        match = re.search(r"\(`(\d+)`\)", orig)

    if match:
        try:
            cust_id = int(match.group(1))
            text, menu_kb = await main_menu_text_and_kb(cust_id, "")
            await bot.send_message(
                cust_id,
                f"ًں’¬ <b>ط¥ط´ط¹ط§ط± ظ…ظ† ط§ظ„ط¥ط¯ط§ط±ط© ط¨ط®طµظˆطµ ط·ظ„ط¨ظƒ:</b>\n\n{html.escape(admin_reply_text)}",
                reply_markup=menu_kb
            )
            await message.reply("âœ… طھظ… ط¥ظٹطµط§ظ„ ط±ط³ط§ظ„طھظƒ ط¥ظ„ظ‰ ط§ظ„ط²ط¨ظˆظ† ط¨ظ†ط¬ط§ط­.")
        except Exception as e:
            await message.reply(f"âڑ ï¸ڈ ظپط´ظ„ ط¥ط±ط³ط§ظ„ ط§ظ„ط±ط¯ ظ„ظ„ط²ط¨ظˆظ†: {e}")

# ----------------- ط¥ط¯ط§ط±ط© ط§ظ„ط·ظ„ط¨ط§طھ ظˆط§ظ„ط¯ط¹ظ… -----------------
@dp.callback_query(F.data.startswith("done:"))
async def order_done(cb: types.CallbackQuery):
    if not is_admin_or_group(cb.from_user.id, cb.message.chat.id):
        await cb.answer("â›” ظ„ط§ طھظ…ظ„ظƒ طµظ„ط§ط­ظٹط©!", show_alert=True)
        return

    _, u_id, msg_id = cb.data.split(":")
    u_id = int(u_id)
    msg_id = int(msg_id)
    if not await claim_admin_action(cb.message.chat.id, msg_id, "done", cb.from_user.id):
        await cb.answer("âڑ ï¸ڈ ظ‡ط°ط§ ط§ظ„ط·ظ„ط¨ طھظ…طھ ظ…ط¹ط§ظ„ط¬طھظ‡ ظ…ط³ط¨ظ‚ط§ظ‹.", show_alert=True)
        return
    try:
        text, menu_kb = await main_menu_text_and_kb(u_id, "")
        await bot.send_message(u_id, "âœ… طھظ… طھظ†ظپظٹط° ط·ظ„ط¨ظƒ ط¨ظ†ط¬ط§ط­! ط´ظƒط±ط§ظ‹ ظ„طھط¹ط§ظ…ظ„ظƒ ظ…ط¹ظ†ط§.", reply_markup=menu_kb)
        if cb.message.caption:
            await cb.message.edit_caption(caption=cb.message.caption + "\n\nًںں¢ <b>طھظ… ط§ظ„طھظ†ظپظٹط°</b>", reply_markup=None)
        elif cb.message.text:
            await cb.message.edit_text(text=cb.message.text + "\n\nًںں¢ <b>طھظ… ط§ظ„طھظ†ظپظٹط°</b>", reply_markup=None)
    except Exception as e:
        await cb.answer(f"ط®ط·ط£: {e}", show_alert=True)

@dp.callback_query(F.data.startswith("rej:"))
async def order_reject(cb: types.CallbackQuery):
    if not is_admin_or_group(cb.from_user.id, cb.message.chat.id):
        await cb.answer("â›” ظ„ط§ طھظ…ظ„ظƒ طµظ„ط§ط­ظٹط©!", show_alert=True)
        return

    _, u_id, msg_id = cb.data.split(":")
    u_id = int(u_id)
    msg_id = int(msg_id)
    if not await claim_admin_action(cb.message.chat.id, msg_id, "reject", cb.from_user.id):
        await cb.answer("âڑ ï¸ڈ ظ‡ط°ط§ ط§ظ„ط·ظ„ط¨ طھظ…طھ ظ…ط¹ط§ظ„ط¬طھظ‡ ظ…ط³ط¨ظ‚ط§ظ‹.", show_alert=True)
        return
    try:
        text, menu_kb = await main_menu_text_and_kb(u_id, "")
        await bot.send_message(u_id, "â‌Œ ظ†ط¹طھط°ط± ظ…ظ†ظƒطŒ طھظ… ط±ظپط¶ ط§ظ„ط·ظ„ط¨ ظ„ظˆط¬ظˆط¯ ط®ط·ط£ ظپظٹ ط§ظ„ط¥ط´ط¹ط§ط± ط£ظˆ ط§ظ„ط¨ظٹط§ظ†ط§طھ.", reply_markup=menu_kb)
        if cb.message.caption:
            await cb.message.edit_caption(caption=cb.message.caption + "\n\nًں”´ <b>طھظ… ط§ظ„ط±ظپط¶</b>", reply_markup=None)
        elif cb.message.text:
            await cb.message.edit_text(text=cb.message.text + "\n\nًں”´ <b>طھظ… ط§ظ„ط±ظپط¶</b>", reply_markup=None)
    except Exception as e:
        await cb.answer(f"ط®ط·ط£: {e}", show_alert=True)

@dp.callback_query(F.data == "sec_support")
async def support_start(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.support_ticket)
    await cb.message.edit_text("ط§ظƒطھط¨ ط§ط³طھظپط³ط§ط±ظƒ ط£ظˆ ظ…ط´ظƒظ„طھظƒ ط¨ط§ظ„طھظپطµظٹظ„ ظˆط³ظٹظ‚ظˆظ… ظپط±ظٹظ‚ ط§ظ„ط¯ط¹ظ… ط¨ط§ظ„ط±ط¯ ط¹ظ„ظٹظƒ ظ‡ظ†ط§:")

@dp.message(OrderState.support_ticket)
async def support_forward(message: types.Message, state: FSMContext):
    if not message.text:
        await message.reply("âڑ ï¸ڈ ظٹط±ط¬ظ‰ ظƒطھط§ط¨ط© ط§ظ„ط§ط³طھظپط³ط§ط± ظƒظ†طµ:")
        return

    user_info = f"@{html.escape(message.from_user.username)}" if message.from_user.username else "ط¨ط¯ظˆظ† ظٹظˆط²ط±"
    txt = (
        f"ًں“© <b>طھط°ظƒط±ط© ط¯ط¹ظ… ظپظ†ظٹ ط¬ط¯ظٹط¯ط©:</b>\n"
        f"ًں‘¤ ط§ظ„ط²ط¨ظˆظ†: {user_info} (<code>{message.from_user.id}</code>)\n\n"
        f"ًں“‌ ط§ظ„ط±ط³ط§ظ„ط©:\n{html.escape(message.text)}\n\n"
        f"ًں’، ظ„ظ„ط±ط¯ ط¹ظ„ظ‰ ط§ظ„ط²ط¨ظˆظ†طŒ ظ‚ظ… ط¨ط¹ظ…ظ„ ط±ط¯ (Reply) ظ…ط¨ط§ط´ط± ط¹ظ„ظ‰ ظ‡ط°ظ‡ ط§ظ„ط±ط³ط§ظ„ط©."
    )
    await bot.send_message(GROUPS["support"], txt)
    await state.clear()
    text, menu_kb = await main_menu_text_and_kb(message.from_user.id, message.from_user.username or "")
    await message.answer(
        "âœ… طھظ… ط¥ط±ط³ط§ظ„ ط±ط³ط§ظ„طھظƒ ظ„ظ„ط¯ط¹ظ… ط§ظ„ظپظ†ظٹطŒ ط³ظ†ط±ط¯ ط¹ظ„ظٹظƒ ظ‡ظ†ط§ ط¨ط£ظ‚ط±ط¨ ظˆظ‚طھ.",
        reply_markup=menu_kb
    )

# ----------------- ط£ظˆط§ظ…ط± ط§ظ„ط£ط¯ظ…ظ† -----------------
@dp.message(Command("add_balance"))
async def admin_add_bal(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, u_id, amt = message.text.split()
        amount = float(amt)
        if amount <= 0:
            await message.reply("âڑ ï¸ڈ ظٹط¬ط¨ ط£ظ† ظٹظƒظˆظ† ط§ظ„ظ…ط¨ظ„ط؛ ط§ظ„ظ…ط¶ط§ظپ ط£ظƒط¨ط± ظ…ظ† ط§ظ„طµظپط±.")
            return
        await add_user_balance(int(u_id), amount)
        await message.reply(f"âœ… طھظ… ط¥ط¶ط§ظپط© {amount:,.2f} ظ„.ط³ ط¥ظ„ظ‰ ط­ط³ط§ط¨ ط§ظ„ظ…ط³طھط®ط¯ظ… {u_id}")
    except Exception:
        await message.reply("âڑ ï¸ڈ ط§ظ„ط§ط³طھط®ط¯ط§ظ…: <code>/add_balance [user_id] [amount]</code>")

@dp.message(Command("rate"))
async def set_dollar(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        val = float(message.text.split()[1])
        if val <= 0:
            await message.reply("âڑ ï¸ڈ ط³ط¹ط± ط§ظ„طµط±ظپ ظٹط¬ط¨ ط£ظ† ظٹظƒظˆظ† ط£ظƒط¨ط± ظ…ظ† ط§ظ„طµظپط±.")
            return
        await update_setting("dollar_rate", val)
        await message.reply(f"âœ… طھظ… طھط­ط¯ظٹط« ط³ط¹ط± طµط±ظپ ط§ظ„ط¯ظˆظ„ط§ط±: {val:,.2f} ظ„.ط³")
    except Exception:
        await message.reply("âڑ ï¸ڈ ط§ظ„ط§ط³طھط®ط¯ط§ظ…: <code>/rate 150</code>")

# ----------------- ظ†ظ‚ط·ط© ط§ظ„ط¯ط®ظˆظ„ -----------------
async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
