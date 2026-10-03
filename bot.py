"""
Syria Store Bot - Wallet-First (Production)
aiogram 3.x + aiosqlite

التشغيل:
    pip install -U aiogram aiosqlite
    export BOT_TOKEN=""        # إلزامي (لا تضعه داخل الكود أبداً)
    export ADMIN_ID="5346581925"   # اختياري
    python syria_store_bot.py
"""
import asyncio
import html
import json
import logging
import os
import random
import re
import string
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, Tuple

import aiosqlite
from aiogram import BaseMiddleware, Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey
from aiogram.types import (
    ErrorEvent,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# =====================================================================
# 1. الإعدادات
# =====================================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise SystemExit("❌ متغير البيئة BOT_TOKEN غير مضبوط. ضع التوكن في متغير بيئة ولا تكتبه في الكود.")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5346581925"))

GROUPS = {
    "wallet": -1003984372814,
    "balance": -1003745247353,
    "games": -1004426615112,
    "accounts": -1003985654158,
    "social": -1004411774893,
    "support": -1004420804667,
}
ALL_ADMIN_GROUPS = list(GROUPS.values())

SHAM_NAME = "سكينه حمود طه"
SHAM_ADDR = "be03739e320f3dfd318a1a7faebae16a"
QR_IMAGE_PATH = "qr_sham.jpg"
DB_PATH = os.getenv("DB_PATH", "syria_store_v2.db")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("syria_store")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
esc = html.escape


def generate_uid(prefix: str = "ORD") -> str:
    ts = hex(int(time.time()))[2:].upper()
    rnd = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"{prefix}-{ts}-{rnd}"


# =====================================================================
# 2. الكتالوج والأسعار (كما هي)
# =====================================================================
GOVERNORATES = [
    "دمشق", "ريف دمشق", "حمص", "ريف حمص", "حماة", "ريف حماة",
    "طرطوس", "درعا", "اللاذقية", "ريف اللاذقية", "حلب", "القامشلي",
    "الرقة", "دير الزور", "البوكمال", "الحسكة", "السويداء", "القنيطرة",
    "إدلب", "جبلة", "القلمون",
]

SYR_UNITS = [
    (9.61, 12), (20.19, 25), (30.76, 40), (40.38, 50), (52.88, 65),
    (62.50, 75), (77.88, 95), (81.73, 100), (100.96, 125), (125, 150),
    (160.57, 200), (192.3, 240), (211.53, 265), (240.38, 300), (288.46, 360),
    (317.3, 400), (370.19, 450), (432.69, 530), (480.76, 600), (576.92, 720),
    (625, 780), (721.15, 895), (769.23, 950), (951.92, 1180), (1057.69, 1300),
    (1923.07, 2380), (2403.84, 3000), (3846.15, 4770),
]

MTN_UNITS = [
    (10, 12), (12, 15), (15, 20), (20, 25), (25, 30), (30, 40), (35, 45),
    (40, 50), (50, 60), (60, 75), (85, 105), (100, 125), (170, 210), (200, 250),
    (280, 350), (360, 450), (400, 500), (600, 750), (750, 930), (1000, 1250),
    (1500, 1860), (2000, 2500), (2500, 3010), (3000, 3750), (5000, 6200),
]

STATION_VALS = [
    (500, 535), (1000, 1070), (1500, 1605), (2000, 2140), (2500, 2675),
    (3000, 3210), (4000, 4280), (5000, 5350), (10000, 10700),
]

GAME_PACKS = {
    "pubg": [("60 UC", 1.0), ("325 UC", 5.0), ("660 UC", 10.0), ("1800 UC", 25.0), ("3850 UC", 50.0), ("8100 UC", 100.0)],
    "ff": [("100 جوهرة", 1.0), ("210 جوهرة", 2.0), ("530 جوهرة", 5.0), ("1080 جوهرة", 10.0), ("2200 جوهرة", 20.0), ("5600 جوهرة", 50.0)],
    "jawaker": [("15,000 توكنز", 1.5), ("50,000 توكنز", 4.0), ("150,000 توكنز", 10.0), ("باشا (شهر)", 6.0)],
    "coc": [("500 جوهرة", 5.0), ("1200 جوهرة", 10.0), ("2500 جوهرة", 20.0), ("6500 جوهرة", 50.0), ("14000 جوهرة", 100.0)],
}

FAST_ACCOUNTS = {
    "1": ("ChatGPT عادي (شهر)", 1700),
    "2": ("ChatGPT Go (ضمان)", 2000),
    "3": ("ChatGPT Plus شهر", 3500),
    "4": ("Netflix شهر جهاز واحد", 800),
    "5": ("Netflix سنة جهاز واحد", 5000),
}

ACCOUNTS_LIST = [
    "Shahid VIP", "Watch It", "OSN+", "TOD TV", "Disney+", "Amazon Prime Video",
    "Apple TV+", "IPTV سنة", "IPTV 6 أشهر", "Spotify Premium", "YouTube Premium",
    "Anghami Plus", "SoundCloud Pro", "Deezer Premium", "Canva Pro سنة",
    "Canva Pro شهر", "Adobe Cloud", "TradingView Pro", "Duolingo Plus",
    "LinkedIn Premium", "Telegram Premium", "NordVPN", "ExpressVPN", "Surfshark VPN",
    "Crunchyroll Fan", "Mega Cloud", "Google One",
]

SOCIAL_PACKS = {
    "fb_view": ("مشاهدات 10k", 500, "fb"),
    "fb_like": ("لايكات منشور 5k", 700, "fb"),
    "fb_sub": ("متابعين 1k", 150, "fb"),
    "fb_comm": ("تعليقات عربية 200", 250, "fb"),
    "ig_view": ("مشاهدات 500k", 300, "ig"),
    "ig_like": ("لايكات 5k", 700, "ig"),
    "ig_sub_f": ("متابعين أجنبي 1k", 700, "ig"),
    "ig_sub_a": ("متابعين عربي 1k", 1350, "ig"),
    "tg_sub": ("أعضاء قنوات 1k", 400, "tg"),
    "tg_react": ("تفاعلات 1k", 150, "tg"),
    "tg_view": ("مشاهدات 5k", 200, "tg"),
}

AD_PACKS = {1: 600, 2: 1100, 3: 1500, 4: 2000, 5: 2500, 6: 3000, 7: 3600, 10: 5000}
AD_DAY_PRICE = 200
ACCOUNTS_PER_PAGE = 6
MIN_TOPUP = 1000


# =====================================================================
# 3. قاعدة البيانات (اتصالات آمنة ضد database is locked)
# =====================================================================
@asynccontextmanager
async def get_db():
    """اتصال جديد لكل عملية: وضع autocommit + مهلة انتظار 30 ثانية للقفل."""
    async with aiosqlite.connect(DB_PATH, timeout=30.0, isolation_level=None) as db:
        await db.execute("PRAGMA busy_timeout = 30000;")
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("PRAGMA synchronous = NORMAL;")
        yield db


@asynccontextmanager
async def write_tx():
    """معاملة ذرية: BEGIN IMMEDIATE ... COMMIT أو ROLLBACK عند أي استثناء."""
    async with get_db() as db:
        await db.execute("BEGIN IMMEDIATE;")
        try:
            yield db
            await db.execute("COMMIT;")
        except BaseException:
            try:
                await db.execute("ROLLBACK;")
            except Exception:
                pass
            raise


async def init_db():
    async with get_db() as db:
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            balance INTEGER DEFAULT 0 CHECK(balance >= 0),
            is_vip INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            role TEXT DEFAULT 'USER' CHECK(role IN ('USER', 'STAFF', 'ADMIN')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            department TEXT NOT NULL,
            service_name TEXT NOT NULL,
            target_data TEXT NOT NULL,
            price INTEGER NOT NULL CHECK(price >= 0),
            status TEXT DEFAULT 'PROCESSING' CHECK(status IN ('PROCESSING', 'COMPLETED', 'REJECTED', 'REFUNDED')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            method TEXT NOT NULL,
            amount INTEGER NOT NULL CHECK(amount > 0),
            sham_tx_id TEXT UNIQUE,
            receipt_file_id TEXT,
            status TEXT DEFAULT 'UNDER_REVIEW' CHECK(status IN ('UNDER_REVIEW', 'ACCEPTED', 'DECLINED')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS wallet_ledger (
            ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            reference_id TEXT NOT NULL,
            type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );""")
        await db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, val REAL);")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS fsm_storage (
            key TEXT PRIMARY KEY,
            state TEXT,
            data TEXT NOT NULL DEFAULT '{}'
        );""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders(user_id, status, created_at);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ledger_user ON wallet_ledger(user_id);")

        for k, v in (("dollar_rate", 150.0), ("num_whatsapp", 400.0), ("num_telegram", 300.0)):
            await db.execute("INSERT OR IGNORE INTO settings (key, val) VALUES (?, ?);", (k, v))
        await db.execute(
            "INSERT INTO users (user_id, username, full_name, role) VALUES (?, 'Admin', 'Admin', 'ADMIN') "
            "ON CONFLICT(user_id) DO UPDATE SET role = 'ADMIN';",
            (ADMIN_ID,),
        )


async def get_setting(key: str) -> float:
    async with get_db() as db:
        cur = await db.execute("SELECT val FROM settings WHERE key=?", (key,))
        row = await cur.fetchone()
        return row[0] if row else 0.0


async def update_setting(key: str, val: float):
    async with get_db() as db:
        await db.execute(
            "INSERT INTO settings (key, val) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET val=excluded.val",
            (key, val),
        )


# =====================================================================
# 4. تخزين FSM دائم في SQLite (لا تضيع الحالات عند إعادة التشغيل)
# =====================================================================
class SQLiteStorage(BaseStorage):
    @staticmethod
    def _k(key: StorageKey) -> str:
        return ":".join(str(x) for x in (
            key.bot_id, key.chat_id, key.user_id,
            getattr(key, "thread_id", None) or 0,
            getattr(key, "destination_id", None) or 0,
        ))

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        s = state.state if isinstance(state, State) else state
        async with get_db() as db:
            await db.execute(
                "INSERT INTO fsm_storage (key, state) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET state=excluded.state",
                (self._k(key), s),
            )

    async def get_state(self, key: StorageKey) -> Optional[str]:
        async with get_db() as db:
            cur = await db.execute("SELECT state FROM fsm_storage WHERE key=?", (self._k(key),))
            row = await cur.fetchone()
            return row[0] if row else None

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        payload = json.dumps(dict(data), ensure_ascii=False, default=str)
        async with get_db() as db:
            await db.execute(
                "INSERT INTO fsm_storage (key, data) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET data=excluded.data",
                (self._k(key), payload),
            )

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        async with get_db() as db:
            cur = await db.execute("SELECT data FROM fsm_storage WHERE key=?", (self._k(key),))
            row = await cur.fetchone()
        if not row or not row[0]:
            return {}
        try:
            return json.loads(row[0])
        except Exception:
            return {}

    async def close(self) -> None:
        return None


dp = Dispatcher(storage=SQLiteStorage())


# =====================================================================
# 5. محرك المحفظة (كل العمليات ذرية)
# =====================================================================
USER_COLS = "user_id, username, balance, is_vip, is_banned, role, full_name"


class WalletService:
    @staticmethod
    async def get_or_create_user(user_id: int, username: str = "", full_name: str = ""):
        async with get_db() as db:
            cur = await db.execute(f"SELECT {USER_COLS} FROM users WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            if not row:
                role = "ADMIN" if user_id == ADMIN_ID else "USER"
                await db.execute(
                    "INSERT OR IGNORE INTO users (user_id, username, full_name, role) VALUES (?, ?, ?, ?)",
                    (user_id, username or "", full_name or "", role),
                )
                cur = await db.execute(f"SELECT {USER_COLS} FROM users WHERE user_id=?", (user_id,))
                return await cur.fetchone()
            if (username and username != row[1]) or (full_name and full_name != row[6]):
                await db.execute(
                    "UPDATE users SET username=?, full_name=? WHERE user_id=?",
                    (username or row[1] or "", full_name or row[6] or "", user_id),
                )
                cur = await db.execute(f"SELECT {USER_COLS} FROM users WHERE user_id=?", (user_id,))
                row = await cur.fetchone()
            return row

    @staticmethod
    async def _credit(db, user_id: int, amount: int, ref_id: str, typ: str, note: str, vip: bool = False) -> Optional[int]:
        sql = "UPDATE users SET balance = balance + ?" + (", is_vip = 1" if vip else "") + " WHERE user_id = ?"
        cur = await db.execute(sql, (amount, user_id))
        if cur.rowcount == 0:
            return None
        cur = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        new_bal = (await cur.fetchone())[0]
        await db.execute(
            "INSERT INTO wallet_ledger (user_id, reference_id, type, amount, balance_after, note) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, ref_id, typ, amount, new_bal, note),
        )
        return new_bal

    @staticmethod
    async def deposit(user_id: int, amount: int, ref_id: str, note: str = "") -> bool:
        if amount <= 0:
            return False
        try:
            async with write_tx() as db:
                return await WalletService._credit(db, user_id, amount, ref_id, "DEPOSIT", note, vip=True) is not None
        except Exception as e:
            log.error("Deposit error: %s", e)
            return False

    @staticmethod
    async def create_order(user_id: int, order_id: str, dept: str, service: str, target: str, price: int) -> Tuple[str, int]:
        """خصم + إنشاء الطلب + قيد المحفظة في معاملة واحدة. يرجع (OK|NO_FUNDS|ERROR, الرصيد)."""
        if price <= 0:
            return "ERROR", 0
        try:
            async with write_tx() as db:
                cur = await db.execute(
                    "UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ? AND is_banned = 0",
                    (price, user_id, price),
                )
                if cur.rowcount == 0:
                    cur = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
                    r = await cur.fetchone()
                    return "NO_FUNDS", (r[0] if r else 0)
                cur = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
                new_bal = (await cur.fetchone())[0]
                await db.execute(
                    "INSERT INTO orders (order_id, user_id, department, service_name, target_data, price, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'PROCESSING')",
                    (order_id, user_id, dept, service, target, price),
                )
                await db.execute(
                    "INSERT INTO wallet_ledger (user_id, reference_id, type, amount, balance_after, note) "
                    "VALUES (?, ?, 'PURCHASE', ?, ?, ?)",
                    (user_id, order_id, -price, new_bal, f"شراء: {service}"),
                )
                return "OK", new_bal
        except Exception as e:
            log.error("create_order error: %s", e)
            return "ERROR", 0

    @staticmethod
    async def refund(order_id: str) -> Tuple[bool, int, int]:
        try:
            async with write_tx() as db:
                cur = await db.execute("SELECT user_id, price FROM orders WHERE order_id = ? AND status = 'PROCESSING'", (order_id,))
                order = await cur.fetchone()
                if not order:
                    return False, 0, 0
                cur = await db.execute(
                    "UPDATE orders SET status = 'REFUNDED' WHERE order_id = ? AND status = 'PROCESSING'", (order_id,)
                )
                if cur.rowcount == 0:
                    return False, 0, 0
                user_id, price = order
                nb = await WalletService._credit(db, user_id, price, order_id, "REFUND", "استرجاع قيمة طلب")
                if nb is None:
                    raise RuntimeError("user missing")
                return True, user_id, price
        except Exception as e:
            log.error("Refund error: %s", e)
            return False, 0, 0

    @staticmethod
    async def complete_order(order_id: str) -> Optional[Tuple[int, str]]:
        async with write_tx() as db:
            cur = await db.execute("SELECT user_id, service_name FROM orders WHERE order_id = ?", (order_id,))
            row = await cur.fetchone()
            if not row:
                return None
            cur = await db.execute(
                "UPDATE orders SET status = 'COMPLETED' WHERE order_id = ? AND status = 'PROCESSING'", (order_id,)
            )
            return (row[0], row[1]) if cur.rowcount else None

    @staticmethod
    async def approve_payment(pay_id: str) -> Optional[Tuple[int, int, int]]:
        """قبول الدفعة + إيداع الرصيد ذرياً. يرجع (user_id, amount, new_balance) أو None إن عولجت مسبقاً."""
        try:
            async with write_tx() as db:
                cur = await db.execute(
                    "UPDATE payments SET status = 'ACCEPTED' WHERE payment_id = ? AND status = 'UNDER_REVIEW'", (pay_id,)
                )
                if cur.rowcount == 0:
                    return None
                cur = await db.execute("SELECT user_id, amount FROM payments WHERE payment_id = ?", (pay_id,))
                uid, amt = await cur.fetchone()
                nb = await WalletService._credit(db, uid, amt, pay_id, "DEPOSIT", "شحن محفظة عبر شام كاش", vip=True)
                if nb is None:
                    raise RuntimeError("user missing")
                return uid, amt, nb
        except Exception as e:
            log.error("approve_payment error: %s", e)
            return None

    @staticmethod
    async def decline_payment(pay_id: str) -> Optional[int]:
        async with write_tx() as db:
            cur = await db.execute("SELECT user_id FROM payments WHERE payment_id = ?", (pay_id,))
            row = await cur.fetchone()
            if not row:
                return None
            cur = await db.execute(
                "UPDATE payments SET status = 'DECLINED' WHERE payment_id = ? AND status = 'UNDER_REVIEW'", (pay_id,)
            )
            return row[0] if cur.rowcount else None

    @staticmethod
    async def last_pending_order(user_id: int):
        async with get_db() as db:
            cur = await db.execute(
                "SELECT order_id, service_name, price FROM orders WHERE user_id = ? AND status = 'PROCESSING' "
                "ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (user_id,),
            )
            return await cur.fetchone()

    @staticmethod
    async def user_by_reference(ref: str) -> Optional[int]:
        table = "orders" if ref.startswith("ORD-") else "payments" if ref.startswith("PAY-") else None
        if not table:
            return None
        col = "order_id" if table == "orders" else "payment_id"
        async with get_db() as db:
            cur = await db.execute(f"SELECT user_id FROM {table} WHERE {col} = ?", (ref,))
            row = await cur.fetchone()
            return row[0] if row else None


# =====================================================================
# 6. الحالات
# =====================================================================
class GlobalOrderState(StatesGroup):
    input_data = State()
    support_msg = State()
    quote_text = State()


class BalanceState(StatesGroup):
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


class WalletFlow(StatesGroup):
    amount = State()
    tx_code = State()
    receipt = State()


class AdminActions(StatesGroup):
    add_bal_user = State()
    add_bal_amount = State()
    set_dollar_rate = State()
    broadcast_msg = State()


class ChatInput(StatesGroup):
    entering_data = State()


class CustomAd(StatesGroup):
    days = State()


# =====================================================================
# 7. أدوات مساعدة للواجهة
# =====================================================================
def B(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def KB(rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_kb(data: str = "back_home") -> InlineKeyboardMarkup:
    return KB([[B("🔙 إلغاء", data)]])


HOME_KB = KB([[B("🏠 العودة للرئيسية", "back_home")]])


def txt(m: types.Message) -> str:
    return (m.text or "").strip()


def to_int(s: str) -> Optional[int]:
    s = s.replace(",", "").replace("٬", "").strip()
    return int(s) if s.isdigit() else None


def user_tag(u: types.User) -> str:
    return f"@{esc(u.username)}" if u.username else "بدون"


def rows_of(buttons, n):
    return [buttons[i:i + n] for i in range(0, len(buttons), n)]


async def safe_edit(cb: types.CallbackQuery, text: str, kb: Optional[InlineKeyboardMarkup] = None):
    """تعديل آمن: يعالج رسائل الصور و'message is not modified'."""
    msg = cb.message
    if not isinstance(msg, types.Message):
        await bot.send_message(cb.from_user.id, text, reply_markup=kb)
        return
    if msg.text is None:  # رسالة صورة/وسائط
        try:
            await msg.delete()
        except Exception:
            pass
        await bot.send_message(msg.chat.id, text, reply_markup=kb)
        return
    try:
        await msg.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return
        await bot.send_message(msg.chat.id, text, reply_markup=kb)


async def respond(event, text: str, kb: Optional[InlineKeyboardMarkup] = None):
    if isinstance(event, types.CallbackQuery):
        await safe_edit(event, text, kb)
    else:
        await event.answer(text, reply_markup=kb)


async def append_status(message: types.Message, status_line: str):
    try:
        if message.caption is not None:
            await message.edit_caption(caption=message.html_text + f"\n\n{status_line}", reply_markup=None)
        else:
            await message.edit_text(text=message.html_text + f"\n\n{status_line}", reply_markup=None)
    except Exception as e:
        log.warning("append_status failed: %s", e)


async def send_to_staff(group_id: int, text: str, kb=None, photo: Optional[str] = None) -> bool:
    """يرسل للمجموعة؛ عند الفشل يُحوَّل للمدير العام كي لا يضيع الطلب."""
    for attempt in range(2):
        try:
            if photo:
                await bot.send_photo(group_id, photo=photo, caption=text, reply_markup=kb)
            else:
                await bot.send_message(group_id, text, reply_markup=kb)
            return True
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except Exception as e:
            log.error("send_to_staff group=%s failed: %s", group_id, e)
            break
    try:
        warn = f"⚠️ <b>تعذر الإرسال للمجموعة {group_id} — نسخة احتياطية:</b>\n\n{text}"
        if photo:
            await bot.send_photo(ADMIN_ID, photo=photo, caption=warn[:1024], reply_markup=kb)
        else:
            await bot.send_message(ADMIN_ID, warn, reply_markup=kb)
    except Exception as e:
        log.error("fallback to admin failed: %s", e)
    return False


def persistent_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🏠 الرئيسية")]], resize_keyboard=True, is_persistent=True)


def main_dashboard_kb():
    return KB([
        [B("➕ شحن رصيد المحفظة (شام كاش)", "wallet:topup")],
        [B("📞 الرصيد والكاش", "sec:balance"), B("🎮 شحن الألعاب", "sec:games")],
        [B("💬 برامج الشات", "sec:chat"), B("📦 الحسابات الرقمية", "sec:accounts")],
        [B("🚀 سوشيال ميديا", "sec:social"), B("📱 أرقام التفعيل", "sec:numbers")],
        [B("💳 كشف المحفظة", "client:wallet_info"), B("🛠 الدعم والشكاوى", "sec:support")],
    ])


def format_home_text(u) -> str:
    rank = "🌟 المدير العام" if u[0] == ADMIN_ID else ("⭐ زبون دائم (VIP)" if u[3] == 1 else "👤 زبون عادي")
    bal = u[2]
    status_icon = "🟢 جاهز للشراء الفوري" if bal > 0 else "⚠️ يرجى شحن الرصيد أولاً"
    name = u[6] or u[1] or "عزيزنا العميل"
    return (
        f"╭────────────────────────────╮\n"
        f"│   🛍 <b>SYRIA STORE | المتجر الإلكتروني</b>   │\n"
        f"╰────────────────────────────╯\n"
        f"👤 <b>الزبون:</b> {esc(name)}\n"
        f"🎖 <b>الرتبة:</b> {rank}\n"
        f"🆔 <b>المعرف:</b> <code>{u[0]}</code>\n"
        f"💰 <b>رصيد المحفظة:</b> <b>{bal:,} ل.س</b> ({status_icon})\n"
        f"──────────────────────────────\n"
        f"💡 <i>النظام يعمل بالشحن المسبق: اشحن محفظتك مرة واحدة واشترِ بضغطة زر فوري بدون انتظار!</i>\n"
        f"──────────────────────────────\n"
        f"اختر الخدمة أو اشحن رصيدك للبدء 👇"
    )


# =====================================================================
# 8. الـ Middlewares ومعالج الأخطاء
# =====================================================================
class UserGuardMiddleware(BaseMiddleware):
    """يسجّل المستخدم ويحدّث بياناته ويمنع المحظورين في المحادثات الخاصة."""

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        chat = data.get("event_chat")
        if user and not user.is_bot and chat and chat.type == "private":
            u = await WalletService.get_or_create_user(user.id, user.username or "", user.full_name or "")
            if u[4] == 1 and user.id != ADMIN_ID:
                try:
                    if isinstance(event, types.CallbackQuery):
                        await event.answer("⛔ حسابك محظور من استخدام البوت.", show_alert=True)
                    elif isinstance(event, types.Message):
                        await event.answer("⛔ حسابك محظور من استخدام البوت.")
                except Exception:
                    pass
                return None
        return await handler(event, data)


class AutoAnswerMiddleware(BaseMiddleware):
    """يوقف مؤشر التحميل على الأزرار بعد كل معالج."""

    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        finally:
            try:
                await event.answer()
            except Exception:
                pass


dp.message.outer_middleware(UserGuardMiddleware())
dp.callback_query.outer_middleware(UserGuardMiddleware())
dp.callback_query.middleware(AutoAnswerMiddleware())


@dp.error()
async def global_error_handler(event: ErrorEvent):
    log.exception("Unhandled error: %s", event.exception)
    upd = event.update
    try:
        if upd.callback_query:
            await upd.callback_query.answer("⚠️ حدث خطأ غير متوقع، حاول مجدداً.", show_alert=True)
        elif upd.message and upd.message.chat.type == "private":
            await upd.message.answer("⚠️ حدث خطأ غير متوقع، حاول مجدداً.", reply_markup=HOME_KB)
    except Exception:
        pass
    return True


# =====================================================================
# 9. البداية والرئيسية + أوامر المدير (مسجلة مبكراً لتسبق حالات FSM)
# =====================================================================
@dp.message(CommandStart(), F.chat.type == "private")
@dp.message(F.text == "🏠 الرئيسية", F.chat.type == "private")
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    u = await WalletService.get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.full_name or "")
    if u[4] == 1 and u[0] != ADMIN_ID:
        await message.answer("⛔ حسابك محظور من استخدام البوت.")
        return
    await message.answer(format_home_text(u), reply_markup=main_dashboard_kb())
    await message.answer("💡 زر القائمة متاح دائماً بالأسفل للعودة فوراً.", reply_markup=persistent_keyboard())


@dp.callback_query(F.data == "back_home")
async def back_to_home_cb(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    u = await WalletService.get_or_create_user(cb.from_user.id)
    await safe_edit(cb, format_home_text(u), main_dashboard_kb())


def admin_kb():
    return KB([
        [B("📊 إحصائيات النظام", "adm:stats")],
        [B("💵 تغذية رصيد مستخدم", "adm:add_bal"), B("💱 سعر صرف الدولار", "adm:set_rate")],
        [B("📢 إذاعة جماعية", "adm:broadcast")],
        [B("❌ إغلاق اللوحة", "adm:close")],
    ])


ADMIN_TITLE = "⚙️ <b>لوحة التحكم الرئيسية للمدير (V2 Wallet-Core):</b>"


@dp.message(Command("admin"), F.chat.type == "private")
async def admin_panel_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.reply("⛔ هذا الأمر مخصص للمدير العام فقط!")
        return
    await state.clear()
    await message.answer(ADMIN_TITLE, reply_markup=admin_kb())


@dp.message(Command("pending"), F.chat.type == "private")
async def admin_pending(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    async with get_db() as db:
        c1 = await db.execute(
            "SELECT order_id, user_id, service_name, price FROM orders WHERE status='PROCESSING' ORDER BY created_at DESC LIMIT 20"
        )
        orders = await c1.fetchall()
        c2 = await db.execute(
            "SELECT payment_id, user_id, amount FROM payments WHERE status='UNDER_REVIEW' ORDER BY created_at DESC LIMIT 20"
        )
        pays = await c2.fetchall()
    lines = ["📋 <b>الطلبات المعلقة:</b>"]
    lines += [f"• <code>{o[0]}</code> | {o[1]} | {esc(o[2])} | {o[3]:,}" for o in orders] or ["لا يوجد"]
    lines.append("\n💳 <b>الإيداعات قيد المراجعة:</b>")
    lines += [f"• <code>{p[0]}</code> | {p[1]} | {p[2]:,}" for p in pays] or ["لا يوجد"]
    await message.answer("\n".join(lines))


@dp.message(Command("ban", "unban"), F.chat.type == "private")
async def admin_ban(message: types.Message, command):
    if message.from_user.id != ADMIN_ID:
        return
    uid = to_int(command.args or "")
    if uid is None or uid == ADMIN_ID:
        await message.reply("الاستخدام: /ban 123456789 أو /unban 123456789")
        return
    flag = 1 if command.command == "ban" else 0
    async with get_db() as db:
        cur = await db.execute("UPDATE users SET is_banned=? WHERE user_id=?", (flag, uid))
    await message.reply("✅ تم." if cur.rowcount else "⚠️ المستخدم غير موجود.")


# =====================================================================
# 10. شحن المحفظة (شام كاش)
# =====================================================================
@dp.callback_query(F.data == "client:wallet_info")
async def wallet_info_view(cb: types.CallbackQuery):
    u = await WalletService.get_or_create_user(cb.from_user.id)
    text = (
        f"💳 <b>بيانات محفظتك الإلكترونية</b>\n"
        f"────────────────────────────\n"
        f"💰 الرصيد المتاح: <b>{u[2]:,} ل.س</b>\n"
        f"🆔 معرّف الحساب: <code>{u[0]}</code>\n\n"
        f"• يمكنك استخدام هذا الرصيد لشراء أي خدمة فورياً بضغطة زر دون الحاجة للتحويل في كل مرة."
    )
    await safe_edit(cb, text, KB([[B("➕ شحن رصيد إضافي", "wallet:topup")], [B("🔙 العودة للرئيسية", "back_home")]]))


@dp.callback_query(F.data == "wallet:topup")
async def wallet_topup_start(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(WalletFlow.amount)
    await safe_edit(
        cb,
        "💵 <b>شحن المحفظة الإلكترونية:</b>\n\n"
        f"أدخل المبلغ الذي ترغب بإيداعه بالليرة السورية (أقل مبلغ {MIN_TOPUP:,} ل.س):",
        cancel_kb(),
    )


@dp.message(WalletFlow.amount)
async def wallet_amt_rec(message: types.Message, state: FSMContext):
    amt = to_int(txt(message))
    if amt is None or amt < MIN_TOPUP:
        await message.reply(f"⚠️ يرجى إدخال مبلغ صحيح بالأرقام (الحد الأدنى {MIN_TOPUP:,} ل.س):")
        return
    await state.update_data(dep_amt=amt)
    await state.set_state(WalletFlow.tx_code)
    pay_text = (
        f"🧾 <b>طلب شحن رصيد بقيمة: {amt:,} ل.س</b>\n"
        f"────────────────────────────\n"
        f"👤 الاسم: <code>{esc(SHAM_NAME)}</code>\n"
        f"🔗 العنوان: <code>{esc(SHAM_ADDR)}</code>\n"
        f"────────────────────────────\n"
        f"⚠️ قم بالتحويل عبر شام كاش، ثم <b>أرسل رقم العملية (Transaction ID) هنا</b>:"
    )
    if os.path.exists(QR_IMAGE_PATH):
        await message.answer_photo(FSInputFile(QR_IMAGE_PATH), caption=pay_text, reply_markup=cancel_kb())
    else:
        await message.answer(pay_text, reply_markup=cancel_kb())


async def tx_exists(tx_code: str) -> bool:
    async with get_db() as db:
        cur = await db.execute("SELECT 1 FROM payments WHERE sham_tx_id = ?", (tx_code,))
        return await cur.fetchone() is not None


@dp.message(WalletFlow.tx_code)
async def wallet_tx_rec(message: types.Message, state: FSMContext):
    tx_code = re.sub(r"\s+", "", txt(message)).upper()
    if len(tx_code) < 3 or len(tx_code) > 64:
        await message.reply("⚠️ يرجى إدخال رقم عملية صحيح:")
        return
    if await tx_exists(tx_code):
        await message.reply("⛔ رقم العملية هذا مستخدم مسبقاً! يرجى إدخال رقم صحيح:")
        return
    await state.update_data(sham_tx=tx_code)
    await state.set_state(WalletFlow.receipt)
    await message.answer("📸 الآن أرسل صورة إشعار التحويل لتأكيد الشحن:", reply_markup=cancel_kb())


@dp.message(WalletFlow.receipt, F.photo)
async def wallet_receipt_rec(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amt = int(data.get("dep_amt", 0))
    tx_code = data.get("sham_tx", "")
    if amt <= 0 or not tx_code:
        await state.clear()
        await message.answer("⚠️ انتهت جلسة الشحن، يرجى البدء من جديد.", reply_markup=KB([[B("➕ شحن المحفظة", "wallet:topup")]]))
        return

    pay_id = generate_uid("PAY")
    file_id = message.photo[-1].file_id
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO payments (payment_id, user_id, method, amount, sham_tx_id, receipt_file_id) "
                "VALUES (?, ?, 'SHAM_CASH', ?, ?, ?)",
                (pay_id, message.from_user.id, amt, tx_code, file_id),
            )
    except aiosqlite.IntegrityError:
        await state.set_state(WalletFlow.tx_code)
        await message.reply("⛔ رقم العملية هذا مستخدم مسبقاً! أرسل رقم عملية صحيح:")
        return

    text_to_group = (
        f"💳 <b>طلب إيداع جديد قيد التدقيق المالي:</b>\n"
        f"🆔 رقم الدفعة: <code>{pay_id}</code>\n"
        f"👤 الزبون: {user_tag(message.from_user)} (<code>{message.from_user.id}</code>)\n"
        f"🔑 UID: <code>{message.from_user.id}</code>\n"
        f"💰 المبلغ المطلوب: <b>{amt:,} ل.س</b>\n"
        f"🧾 رقم العملية: <code>{esc(tx_code)}</code>\n"
    )
    kb = KB([[B("✅ قبول وتغذية الرصيد", f"adm_pay:ok:{pay_id}"), B("❌ رفض الإيداع", f"adm_pay:no:{pay_id}")]])
    await send_to_staff(GROUPS["wallet"], text_to_group, kb, photo=file_id)
    await state.clear()
    await message.answer(
        "✅ تم إرسال إشعار الإيداع للإدارة بنجاح! سيتم إشعارك وشحن محفظتك فوراً بعد التأكيد.",
        reply_markup=HOME_KB,
    )


@dp.message(WalletFlow.receipt)
async def wallet_receipt_not_photo(message: types.Message):
    await message.reply("⚠️ يرجى إرسال صورة إشعار التحويل (كصورة وليس كنص).")


# =====================================================================
# 11. محرك الشراء الموحد (خصم فوري ذري)
# =====================================================================
_recent_purchases: Dict[Tuple[int, str, str], float] = {}


async def process_wallet_purchase(event, user_id: int, dept: str, service: str, target: str, price: int, state: FSMContext):
    await state.clear()

    # حماية من الضغط المزدوج السريع
    sig = (user_id, service, target)
    now = time.monotonic()
    for k in [k for k, t in _recent_purchases.items() if now - t > 5]:
        _recent_purchases.pop(k, None)
    if sig in _recent_purchases:
        if isinstance(event, types.CallbackQuery):
            await event.answer("⏳ جارٍ معالجة طلبك...", show_alert=True)
        return
    _recent_purchases[sig] = now

    price = int(price)
    ord_id = generate_uid("ORD")
    status, balance = await WalletService.create_order(user_id, ord_id, dept, service, target, price)

    if status == "NO_FUNDS":
        _recent_purchases.pop(sig, None)
        diff = price - balance
        text_no_bal = (
            f"❌ <b>رصيدك غير كافٍ لإتمام الشراء!</b>\n"
            f"────────────────────────────\n"
            f"📦 الخدمة: <b>{esc(service)}</b>\n"
            f"💵 السعر المطلوب: <b>{price:,} ل.س</b>\n"
            f"💰 رصيدك الحالي: <b>{balance:,} ل.س</b>\n"
            f"⚠️ ينقصك: <b>{diff:,} ل.س</b>\n"
            f"────────────────────────────\n"
            f"💡 يرجى شحن محفظتك أولاً لتتمكن من الشراء بضغطة زر واحدة."
        )
        await respond(event, text_no_bal, KB([[B("➕ شحن المحفظة الآن", "wallet:topup")], [B("🔙 العودة للرئيسية", "back_home")]]))
        return
    if status != "OK":
        _recent_purchases.pop(sig, None)
        err = "⚠️ حدث خطأ أثناء إتمام الطلب (لم يُخصم أي مبلغ)، يرجى المحاولة لاحقاً."
        if isinstance(event, types.CallbackQuery):
            await event.answer(err, show_alert=True)
        else:
            await event.reply(err)
        return

    group_id = GROUPS.get(dept, GROUPS["balance"])
    group_card = (
        f"⚡ <b>طلب جديد مدفوع من المحفظة (جاهز للتنفيذ):</b>\n"
        f"🆔 رقم الطلب: <code>{ord_id}</code>\n"
        f"👤 الزبون: {user_tag(event.from_user)} (<code>{user_id}</code>)\n"
        f"🔑 UID: <code>{user_id}</code>\n"
        f"📦 الخدمة: <b>{esc(service)}</b>\n"
        f"🎯 البيانات: <code>{esc(target)}</code>\n"
        f"💰 المبلغ المخصوم: <b>{price:,} ل.س</b>\n\n"
        f"💡 للرد على الزبون، قم بعمل رد (Reply) مباشر على هذه الرسالة."
    )
    kb_group = KB([[B("✅ تم التنفيذ", f"ord_act:done:{ord_id}"), B("❌ إلغاء واسترجاع", f"ord_act:ref:{ord_id}")]])
    await send_to_staff(group_id, group_card, kb_group)

    success_card = (
        f"🎉 <b>تم شراء الخدمة بنجاح!</b>\n"
        f"────────────────────────────\n"
        f"🆔 رقم الطلب: <code>{ord_id}</code>\n"
        f"📦 الخدمة: <b>{esc(service)}</b>\n"
        f"🎯 البيانات: <code>{esc(target)}</code>\n"
        f"💵 المبلغ المخصوم: <b>{price:,} ل.س</b>\n"
        f"💰 رصيدك المتبقي: <b>{balance:,} ل.س</b>\n"
        f"────────────────────────────\n"
        f"⏳ تم تحويل طلبك لفريق التنفيذ فوراً وسيصلك إشعار بالانتهاء."
    )
    await respond(event, success_card, HOME_KB)


# =====================================================================
# 12. الرصيد والكاش (Syriatel & MTN)
# =====================================================================
def net_name_of(net: str) -> str:
    return "Syriatel" if net == "syr" else "MTN"


@dp.callback_query(F.data == "sec:balance")
async def balance_home(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(cb, "📞 <b>اختر شبكة الاتصال المطلوبة:</b>", KB([
        [B("🔴 سيريتل (Syriatel)", "net:syr")],
        [B("🟡 إم تي إن (MTN)", "net:mtn")],
        [B("🔙 العودة للرئيسية", "back_home")],
    ]))


@dp.callback_query(F.data.startswith("net:"))
async def net_menu_view(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    net = cb.data.split(":")[1]
    name = net_name_of(net)
    await safe_edit(cb, f"📞 <b>خدمات شبكة {name}:</b>", KB([
        [B(f"📲 وحدات {name}", f"bopt:{net}:units")],
        [B(f"⛽ جملة {name} كازية", f"bopt:{net}:station")],
        [B(f"🧾 فواتير {name}", f"bopt:{net}:invoice")],
        [B(f"💵 كاش {name}", f"bopt:{net}:cash")],
        [B("🔙 رجوع", "sec:balance")],
    ]))


@dp.callback_query(F.data.startswith("bopt:"))
async def handle_balance_options(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    _, net, opt = cb.data.split(":")
    name = net_name_of(net)

    if opt == "units":
        items = SYR_UNITS if net == "syr" else MTN_UNITS
        buttons = [B(f"{u} ⬅ {p:,} ل.س", f"bu_{net}_{i}") for i, (u, p) in enumerate(items)]
        rows = rows_of(buttons, 2) + [[B("🔙 رجوع", f"net:{net}")]]
        await safe_edit(cb, f"📲 <b>اختر فئة وحدات {name}:</b>", KB(rows))
    elif opt == "station":
        buttons = [B(f"فئة {a:,} ⬅ {p:,} ل.س", f"bs_{net}_{i}") for i, (a, p) in enumerate(STATION_VALS)]
        rows = rows_of(buttons, 2) + [[B("🔙 رجوع", f"net:{net}")]]
        await safe_edit(cb, f"⛽ <b>اختر فئة كازية {name}:</b>", KB(rows))
    elif opt == "invoice":
        await state.set_state(BalanceState.syr_invoice_num if net == "syr" else BalanceState.mtn_invoice_num)
        await safe_edit(cb, f"🧾 أدخل رقم فاتورة {name}:", cancel_kb(f"net:{net}"))
    elif opt == "cash":
        await state.set_state(BalanceState.syr_cash_amt if net == "syr" else BalanceState.mtn_cash_amt)
        await safe_edit(cb, f"💵 أدخل كمية كاش {name} المطلوبة (الحد الأدنى 1,000 ل.س):", cancel_kb(f"net:{net}"))


@dp.callback_query(F.data.startswith("bu_"))
async def sel_units_pack(cb: types.CallbackQuery, state: FSMContext):
    _, net, idx = cb.data.split("_")
    items = SYR_UNITS if net == "syr" else MTN_UNITS
    u, p = items[int(idx)]
    name = net_name_of(net)
    await state.update_data(s_title=f"وحدات {name} ({u} وحدة)", s_price=int(p))
    await state.set_state(BalanceState.syr_units_phone if net == "syr" else BalanceState.mtn_units_phone)
    await safe_edit(
        cb,
        f"📲 اخترت فئة <b>{u} وحدة</b> ({p:,} ل.س)\n\nأدخل رقم الهاتف المطلوب التحويل إليه (10 خانات تبدأ بـ 09):",
        cancel_kb(f"bopt:{net}:units"),
    )


def valid_phone(p: str) -> bool:
    return p.isdigit() and len(p) == 10 and p.startswith("09")


async def _units_phone(message: types.Message, state: FSMContext, label: str):
    p = txt(message)
    if not valid_phone(p):
        await message.reply(f"⚠️ رقم {label} يجب أن يتكون من 10 خانات ويبدأ بـ 09:")
        return
    data = await state.get_data()
    if "s_title" not in data:
        await state.clear()
        await message.answer("⚠️ انتهت الجلسة، يرجى الاختيار من جديد.", reply_markup=HOME_KB)
        return
    await process_wallet_purchase(message, message.from_user.id, "balance", data["s_title"], f"رقم {label}: {p}", data["s_price"], state)


@dp.message(BalanceState.syr_units_phone)
async def proc_syr_phone(message: types.Message, state: FSMContext):
    await _units_phone(message, state, "سيريتل")


@dp.message(BalanceState.mtn_units_phone)
async def proc_mtn_phone(message: types.Message, state: FSMContext):
    await _units_phone(message, state, "MTN")


@dp.callback_query(F.data.startswith("bs_"))
async def sel_station_pack(cb: types.CallbackQuery, state: FSMContext):
    _, net, idx = cb.data.split("_")
    a, p = STATION_VALS[int(idx)]
    name = net_name_of(net)
    await state.update_data(s_title=f"جملة كازية {name} (فئة {a:,})", s_price=int(p))
    await state.set_state(BalanceState.syr_station_code if net == "syr" else BalanceState.mtn_station_code)
    await safe_edit(cb, f"⛽ أدخل كود كازية {name}:", cancel_kb(f"bopt:{net}:station"))


def gov_kb(net: str) -> InlineKeyboardMarkup:
    buttons = [B(g, f"sgov_{net}:{i}") for i, g in enumerate(GOVERNORATES)]
    return KB(rows_of(buttons, 3))


@dp.message(BalanceState.syr_station_code)
async def proc_syr_st_code(message: types.Message, state: FSMContext):
    code = txt(message)
    if not (code.isdigit() and len(code) == 6):
        await message.reply("⚠️ كود كازية سيريتل يجب أن يتكون من 6 أرقام حصراً:")
        return
    await state.update_data(st_code=code)
    await state.set_state(BalanceState.syr_station_gov)
    await message.answer("📍 اختر المحافظة:", reply_markup=gov_kb("syr"))


@dp.callback_query(F.data.startswith("sgov_syr:"), BalanceState.syr_station_gov)
async def proc_syr_st_gov(cb: types.CallbackQuery, state: FSMContext):
    gov = GOVERNORATES[int(cb.data.split(":")[1])]
    data = await state.get_data()
    target = f"كود كازية: {data.get('st_code')} | المحافظة: {gov}"
    await process_wallet_purchase(cb, cb.from_user.id, "balance", data["s_title"], target, data["s_price"], state)


@dp.message(BalanceState.mtn_station_code)
async def proc_mtn_st_code(message: types.Message, state: FSMContext):
    if not txt(message):
        await message.reply("⚠️ أدخل كود الكازية كنص:")
        return
    await state.update_data(st_code=txt(message))
    await state.set_state(BalanceState.mtn_station_num)
    await message.answer("⛽ أدخل رقم كازية MTN:")


@dp.message(BalanceState.mtn_station_num)
async def proc_mtn_st_num(message: types.Message, state: FSMContext):
    if not txt(message):
        await message.reply("⚠️ أدخل رقم الكازية كنص:")
        return
    await state.update_data(st_num=txt(message))
    await state.set_state(BalanceState.mtn_station_gov)
    await message.answer("📍 اختر المحافظة:", reply_markup=gov_kb("mtn"))


@dp.callback_query(F.data.startswith("sgov_mtn:"), BalanceState.mtn_station_gov)
async def proc_mtn_st_gov(cb: types.CallbackQuery, state: FSMContext):
    gov = GOVERNORATES[int(cb.data.split(":")[1])]
    data = await state.get_data()
    target = f"كود: {data.get('st_code')} | رقم: {data.get('st_num')} | المحافظة: {gov}"
    await process_wallet_purchase(cb, cb.from_user.id, "balance", data["s_title"], target, data["s_price"], state)


def with_fee(amt: int) -> int:
    """المبلغ + 5% مع تقريب لأعلى بحساب صحيح (بدون أخطاء الفاصلة العائمة)."""
    return (amt * 105 + 99) // 100


async def _invoice_num(message: types.Message, state: FSMContext, nxt: State):
    if not txt(message):
        await message.reply("⚠️ أدخل رقم الفاتورة كنص:")
        return
    await state.update_data(inv_num=txt(message))
    await state.set_state(nxt)
    await message.answer("💵 أدخل قيمة الفاتورة بالليرة السورية:")


async def _invoice_amt(message: types.Message, state: FSMContext, name: str):
    amt = to_int(txt(message))
    if not amt or amt <= 0:
        await message.reply("⚠️ القيمة يجب أن تكون أكبر من صفر وصحيحة:")
        return
    data = await state.get_data()
    target = f"رقم فاتورة {name}: {data.get('inv_num')} | القيمة: {amt:,}"
    await process_wallet_purchase(message, message.from_user.id, "balance", f"فاتورة {name} ({amt:,} ل.س)", target, with_fee(amt), state)


@dp.message(BalanceState.syr_invoice_num)
async def proc_syr_inv_num(message: types.Message, state: FSMContext):
    await _invoice_num(message, state, BalanceState.syr_invoice_amt)


@dp.message(BalanceState.syr_invoice_amt)
async def proc_syr_inv_amt(message: types.Message, state: FSMContext):
    await _invoice_amt(message, state, "Syriatel")


@dp.message(BalanceState.mtn_invoice_num)
async def proc_mtn_inv_num(message: types.Message, state: FSMContext):
    await _invoice_num(message, state, BalanceState.mtn_invoice_amt)


@dp.message(BalanceState.mtn_invoice_amt)
async def proc_mtn_inv_amt(message: types.Message, state: FSMContext):
    await _invoice_amt(message, state, "MTN")


async def _cash_amt(message: types.Message, state: FSMContext, nxt: State, prompt: str):
    amt = to_int(txt(message))
    if not amt or amt < 1000:
        await message.reply("⚠️ الحد الأدنى للكاش هو 1,000 ل.س:")
        return
    await state.update_data(c_amt=amt, c_price=with_fee(amt))
    await state.set_state(nxt)
    await message.answer(prompt)


@dp.message(BalanceState.syr_cash_amt)
async def proc_syr_cash_amt(message: types.Message, state: FSMContext):
    await _cash_amt(message, state, BalanceState.syr_cash_id, "👤 أدخل معرّف Player-ID لاستلام كاش Syriatel:")


@dp.message(BalanceState.mtn_cash_amt)
async def proc_mtn_cash_amt(message: types.Message, state: FSMContext):
    await _cash_amt(message, state, BalanceState.mtn_cash_num, "📱 أدخل رقم كاش MTN المطلوب التحويل إليه:")


@dp.message(BalanceState.syr_cash_id)
async def proc_syr_cash_id(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if not txt(message) or "c_amt" not in data:
        await message.reply("⚠️ أدخل المعرّف كنص:")
        return
    target = f"Player-ID: {txt(message)} | الكمية: {data['c_amt']:,}"
    await process_wallet_purchase(message, message.from_user.id, "balance", f"كاش Syriatel ({data['c_amt']:,})", target, data["c_price"], state)


@dp.message(BalanceState.mtn_cash_num)
async def proc_mtn_cash_num(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if not txt(message) or "c_amt" not in data:
        await message.reply("⚠️ أدخل الرقم كنص:")
        return
    target = f"رقم كاش MTN: {txt(message)} | الكمية: {data['c_amt']:,}"
    await process_wallet_purchase(message, message.from_user.id, "balance", f"كاش MTN ({data['c_amt']:,})", target, data["c_price"], state)


# =====================================================================
# 13. شحن الألعاب
# =====================================================================
@dp.callback_query(F.data == "sec:games")
async def games_home(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(cb, "🎮 <b>اختر اللعبة المطلوبة:</b>", KB([
        [B("🔫 ببجي (PUBG)", "game:pubg")],
        [B("🔥 فري فاير (Free Fire)", "game:ff")],
        [B("🃏 جواكر (Jawaker)", "game:jawaker")],
        [B("⚔️ كلاش أوف كلانس (CoC)", "game:coc")],
        [B("🎮 باقي الألعاب [طلب تسعير]", "quote:game")],
        [B("🔙 العودة للرئيسية", "back_home")],
    ]))


@dp.callback_query(F.data.startswith("game:"))
async def game_packs_view(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    g_key = cb.data.split(":")[1]
    rate = await get_setting("dollar_rate")
    rows = [[B(f"{n} ⬅ {round(usd * rate):,} ل.س", f"buyg:{g_key}:{i}")] for i, (n, usd) in enumerate(GAME_PACKS[g_key])]
    rows.append([B("🔙 رجوع للألعاب", "sec:games")])
    await safe_edit(cb, "🎮 <b>اختر الباقة المطلوبة:</b>", KB(rows))


@dp.callback_query(F.data.startswith("buyg:"))
async def buy_game_pack(cb: types.CallbackQuery, state: FSMContext):
    _, g_key, idx = cb.data.split(":")
    p_name, p_usd = GAME_PACKS[g_key][int(idx)]
    price = round(p_usd * await get_setting("dollar_rate"))
    await state.update_data(g_dept="games", g_service=f"شحن {g_key.upper()} ({p_name})", g_price=price)
    await state.set_state(GlobalOrderState.input_data)
    await safe_edit(
        cb,
        f"🎮 لقد اخترت: <b>{g_key.upper()} - {esc(p_name)}</b> ({price:,} ل.س)\n\nأدخل الآيدي (Player ID) واسمك داخل اللعبة:",
        cancel_kb(f"game:{g_key}"),
    )


@dp.message(GlobalOrderState.input_data)
async def process_global_order_data(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target = txt(message)
    if not target:
        await message.reply("⚠️ يرجى إرسال البيانات المطلوبة كنص:")
        return
    if not data.get("g_price"):
        await state.clear()
        await message.answer("⚠️ انتهت الجلسة، يرجى الاختيار من جديد.", reply_markup=HOME_KB)
        return
    await process_wallet_purchase(
        message, message.from_user.id, data.get("g_dept", "games"), data.get("g_service", "خدمة عامة"),
        target[:500], data["g_price"], state,
    )


# =====================================================================
# 14. برامج الشات
# =====================================================================
CHAT_APPS = {
    # key: (اسم التطبيق, الوحدة, المعامل)
    "soulstar": ("Soul Star", "كوينز", 0.025),
    "soulchill": ("Soulchill", "كريستال", 0.30),
    "imo": ("IMO", "ألماس", 0.50),
    "talsa": ("Talsa chat", "كوينز", 0.02),
}


@dp.callback_query(F.data == "sec:chat")
async def chat_menu(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(cb, "💬 <b>اختر تطبيق الشات المطلوب:</b>", KB([
        [B("🌟 Soul Star (كوينز × 0.025)", "chat_calc:soulstar")],
        [B("❄️ Soulchill (كريستال × 0.30)", "chat_calc:soulchill")],
        [B("💬 IMO (ألماس × 0.50)", "chat_calc:imo")],
        [B("🗣 Talsa chat (كوينز × 0.02)", "chat_calc:talsa")],
        [B("🔍 باقي التطبيقات [طلب تسعير]", "quote:chat")],
        [B("🔙 العودة للرئيسية", "back_home")],
    ]))


@dp.callback_query(F.data.startswith("chat_calc:"))
async def chat_calc_prompt(cb: types.CallbackQuery, state: FSMContext):
    await state.update_data(c_app=cb.data.split(":")[1])
    await state.set_state(ChatInput.entering_data)
    await safe_edit(cb, "💬 أدخل (الآيدي) متبوعاً بـ (الكمية المطلوبة):\nمثال: <code>123456 5000</code>", cancel_kb("sec:chat"))


@dp.message(ChatInput.entering_data)
async def proc_chat_calc_receive(message: types.Message, state: FSMContext):
    data = await state.get_data()
    app = CHAT_APPS.get(data.get("c_app", ""))
    if not app:
        await state.clear()
        await message.answer("⚠️ انتهت الجلسة، يرجى الاختيار من جديد.", reply_markup=HOME_KB)
        return
    parts = txt(message).split()
    qty = to_int(parts[1]) if len(parts) >= 2 else None
    if qty is None:
        await message.reply("⚠️ أرسل الآيدي ثم الكمية (رقم صحيح) وبينهما مسافة:")
        return
    if qty <= 0 or qty > 1_000_000_000:
        await message.reply("⚠️ الكمية غير صالحة:")
        return
    name, unit, factor = app
    price = round(qty * factor)
    if price < 1:
        await message.reply("⚠️ الكمية قليلة جداً، يرجى زيادتها:")
        return
    await process_wallet_purchase(
        message, message.from_user.id, "games", f"{name} ({qty:,} {unit})", f"الآيدي: {parts[0][:100]}", price, state
    )


# =====================================================================
# 15. الحسابات الجاهزة
# =====================================================================
@dp.callback_query(F.data == "sec:accounts")
async def accounts_home(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    rows = [[B(f"🔹 {n} ({p:,} ل.س)", f"facc:{k}")] for k, (n, p) in FAST_ACCOUNTS.items()]
    rows.append([B(f"📋 باقي الحسابات ({len(ACCOUNTS_LIST)} خدمة)", "acc_page:0")])
    rows.append([B("🔙 العودة للرئيسية", "back_home")])
    await safe_edit(cb, "📦 <b>اختر الحساب الجاهز المطلوب:</b>", KB(rows))


@dp.callback_query(F.data.startswith("facc:"))
async def acc_fast_confirm(cb: types.CallbackQuery, state: FSMContext):
    name, price = FAST_ACCOUNTS[cb.data.split(":")[1]]
    await process_wallet_purchase(cb, cb.from_user.id, "accounts", f"حساب {name}", "حساب رسمي مع الضمان", price, state)


@dp.callback_query(F.data.startswith("acc_page:"))
async def extra_accounts_pages(cb: types.CallbackQuery):
    page = int(cb.data.split(":")[1])
    total_pages = (len(ACCOUNTS_LIST) + ACCOUNTS_PER_PAGE - 1) // ACCOUNTS_PER_PAGE
    start = page * ACCOUNTS_PER_PAGE
    end = start + ACCOUNTS_PER_PAGE
    rows = [[B(f"🔹 {item}", f"sel_acc:{start + i}")] for i, item in enumerate(ACCOUNTS_LIST[start:end])]
    nav = []
    if page > 0:
        nav.append(B("⬅️ السابق", f"acc_page:{page - 1}"))
    if end < len(ACCOUNTS_LIST):
        nav.append(B("التالي ➡️", f"acc_page:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([B("🔙 رجوع للحسابات", "sec:accounts")])
    await safe_edit(cb, f"📦 <b>اختر الحساب المطلوب (صفحة {page + 1} من {total_pages}):</b>", KB(rows))


@dp.callback_query(F.data.startswith("sel_acc:"))
async def account_select_duration(cb: types.CallbackQuery, state: FSMContext):
    acc_name = ACCOUNTS_LIST[int(cb.data.split(":")[1])]
    await state.update_data(selected_acc_name=acc_name)
    await safe_edit(cb, f"لقد اخترت: <b>{esc(acc_name)}</b>\n\nاختر المدة المطلوبة بالضغط على الزر أدناه:", KB([
        [B("⏳ اشتراك شهر", "acc_dur:شهر")],
        [B("⏳ اشتراك 3 أشهر", "acc_dur:3 أشهر")],
        [B("⏳ اشتراك سنة", "acc_dur:سنة")],
        [B("🔙 رجوع للقائمة", "acc_page:0")],
    ]))


@dp.callback_query(F.data.startswith("acc_dur:"))
async def account_duration_finish(cb: types.CallbackQuery, state: FSMContext):
    dur = cb.data.split(":", 1)[1]
    data = await state.get_data()
    acc_name = data.get("selected_acc_name")
    if not acc_name:
        await safe_edit(cb, "⚠️ انتهت الجلسة، يرجى اختيار الحساب من جديد.", KB([[B("📋 قائمة الحسابات", "acc_page:0")]]))
        return
    text_to_group = (
        f"📩 <b>طلب تسعير حساب جديد:</b>\n"
        f"👤 الزبون: {user_tag(cb.from_user)} (<code>{cb.from_user.id}</code>)\n"
        f"🔑 UID: <code>{cb.from_user.id}</code>\n"
        f"🏷 الحساب: <b>{esc(acc_name)}</b>\n"
        f"⏳ المدة: <b>{esc(dur)}</b>\n\n"
        f"💡 لتسعير الطلب والرد على الزبون، قم بعمل رد (Reply) مباشر على هذه الرسالة."
    )
    await send_to_staff(GROUPS["accounts"], text_to_group)
    await state.clear()
    await safe_edit(
        cb,
        f"✅ تم إرسال طلبك لحساب <b>{esc(acc_name)}</b> (مدة: {esc(dur)}) للإدارة بنجاح.\n"
        f"سيتم مراجعته والرد عليك هنا بالتفاصيل والسعر قريباً.",
        HOME_KB,
    )


# =====================================================================
# 16. السوشيال ميديا والإعلانات
# =====================================================================
@dp.callback_query(F.data == "sec:social")
async def social_menu(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(cb, "🚀 <b>اختر منصة السوشيال ميديا:</b>", KB([
        [B("📘 خدمات فيسبوك", "soc:fb")],
        [B("📸 خدمات إنستغرام", "soc:ig")],
        [B("✈ خدمات تلغرام", "soc:tg")],
        [B("📢 إعلانات ممولة فيسبوك", "soc:ads")],
        [B("🔙 العودة للرئيسية", "back_home")],
    ]))


@dp.callback_query(F.data.startswith("soc:"))
async def soc_platforms(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    plat = cb.data.split(":")[1]
    if plat in ("fb", "ig", "tg"):
        rows = [[B(f"🔹 {t} ({p:,} ل.س)", f"spk:{code}")] for code, (t, p, pt) in SOCIAL_PACKS.items() if pt == plat]
        rows.append([B("🔙 رجوع", "sec:social")])
        await safe_edit(cb, "🚀 <b>اختر الباقة المطلوبة:</b>", KB(rows))
    elif plat == "ads":
        buttons = [B(f"إعلان {d} أيام ⬅ {p:,} ل.س", f"ad_f:{d}") for d, p in AD_PACKS.items()]
        rows = rows_of(buttons, 2)
        rows.append([B(f"⚙ مدة مخصصة ({AD_DAY_PRICE} ل.س/يوم)", "ad_c")])
        rows.append([B("🔙 رجوع", "sec:social")])
        await safe_edit(cb, "📢 <b>اختر مدة الإعلان الممول:</b>", KB(rows))


@dp.callback_query(F.data.startswith("spk:"))
async def soc_buy_pack(cb: types.CallbackQuery, state: FSMContext):
    title, price, plat = SOCIAL_PACKS[cb.data.split(":")[1]]
    await state.update_data(g_dept="social", g_service=f"{plat.upper()} - {title}", g_price=int(price))
    await state.set_state(GlobalOrderState.input_data)
    await safe_edit(
        cb, f"🚀 لقد اخترت: <b>{plat.upper()} - {esc(title)}</b> ({price:,} ل.س)\n\nأرسل رابط الحساب أو المنشور المطلوب:",
        cancel_kb(f"soc:{plat}"),
    )


@dp.callback_query(F.data.startswith("ad_f:"))
async def ad_f_click(cb: types.CallbackQuery, state: FSMContext):
    d = int(cb.data.split(":")[1])
    price = AD_PACKS[d]  # السعر من الخادم وليس من بيانات الزر
    await state.update_data(g_dept="social", g_service=f"إعلان ممول فيسبوك ({d} أيام)", g_price=price)
    await state.set_state(GlobalOrderState.input_data)
    await safe_edit(
        cb, f"📢 لقد اخترت: <b>إعلان ممول ({d} أيام)</b> ({price:,} ل.س)\n\nأدخل رقم هاتفك للتواصل وتجهيز تفاصيل الإعلان:",
        cancel_kb("soc:ads"),
    )


@dp.callback_query(F.data == "ad_c")
async def ad_c_click(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(CustomAd.days)
    await safe_edit(cb, f"📢 أدخل عدد الأيام المطلوبة للإعلان (اليوم = {AD_DAY_PRICE} ل.س):", cancel_kb("soc:ads"))


@dp.message(CustomAd.days)
async def proc_custom_ad_days(message: types.Message, state: FSMContext):
    days = to_int(txt(message))
    if not days or days <= 0 or days > 365:
        await message.reply("⚠️ عدد الأيام يجب أن يكون رقماً صحيحاً بين 1 و 365:")
        return
    price = days * AD_DAY_PRICE
    await state.update_data(g_dept="social", g_service=f"إعلان مخصص فيسبوك ({days} أيام)", g_price=price)
    await state.set_state(GlobalOrderState.input_data)
    await message.answer(f"📢 الإجمالي: <b>{price:,} ل.س</b>\n\nأدخل رقم هاتفك للتواصل لتجهيز الإعلان:")


# =====================================================================
# 17. أرقام التفعيل
# =====================================================================
@dp.callback_query(F.data == "sec:numbers")
async def numbers_home(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    p_wa = int(await get_setting("num_whatsapp"))
    p_tg = int(await get_setting("num_telegram"))
    await safe_edit(cb, "📱 <b>قسم أرقام التفعيل:</b>", KB([
        [B(f"🟢 رقم واتساب أجنبي ({p_wa:,} ل.س)", "buyn:whatsapp")],
        [B(f"🔵 رقم تلغرام أمريكي ({p_tg:,} ل.س)", "buyn:telegram")],
        [B("📱 رقم تيك توك [طلب تسعير]", "quote:num_tiktok")],
        [B("🌐 تفعيل غوغل [طلب تسعير]", "quote:num_google")],
        [B("🍎 تفعيل آبل [طلب تسعير]", "quote:num_apple")],
        [B("🔙 العودة للرئيسية", "back_home")],
    ]))


@dp.callback_query(F.data.startswith("buyn:"))
async def buy_num_fast(cb: types.CallbackQuery, state: FSMContext):
    target = cb.data.split(":")[1]
    key = "num_whatsapp" if target == "whatsapp" else "num_telegram"
    name = "واتساب أجنبي" if target == "whatsapp" else "تلغرام أمريكي"
    price = int(await get_setting(key))
    await process_wallet_purchase(cb, cb.from_user.id, "social", f"رقم {name}", "تسليم كود تفعيل فوري", price, state)


# =====================================================================
# 18. طلبات التسعير والدعم الفني
# =====================================================================
@dp.callback_query(F.data.startswith("quote:"))
async def generic_quote_start(cb: types.CallbackQuery, state: FSMContext):
    g_map = {
        "game": ("games", "🎮 طلب تسعير لعبة"),
        "chat": ("games", "💬 طلب تسعير تطبيق شات"),
        "num_tiktok": ("social", "📱 طلب رقم تيك توك"),
        "num_google": ("social", "🌐 طلب تفعيل غوغل"),
        "num_apple": ("social", "🍎 طلب تفعيل آبل"),
    }
    sec, label = g_map.get(cb.data.split(":")[1], ("games", "طلب عام"))
    await state.update_data(q_sec=sec, q_label=label)
    await state.set_state(GlobalOrderState.quote_text)
    await safe_edit(cb, f"✍️ يرجى كتابة تفاصيل <b>{label}</b> بالتفصيل:\n(الاسم + المعرف أو الآيدي + الكمية المطلوبة):", cancel_kb())


@dp.message(GlobalOrderState.quote_text)
async def generic_quote_receive(message: types.Message, state: FSMContext):
    if not txt(message):
        await message.reply("⚠️ يرجى إرسال تفاصيل الطلب كنص:")
        return
    data = await state.get_data()
    group_id = GROUPS.get(data.get("q_sec", "games"), GROUPS["games"])
    label = data.get("q_label", "طلب تسعير")
    text_to_group = (
        f"📩 <b>{esc(label)}:</b>\n"
        f"👤 الزبون: {user_tag(message.from_user)} (<code>{message.from_user.id}</code>)\n"
        f"🔑 UID: <code>{message.from_user.id}</code>\n"
        f"📝 <b>التفاصيل:</b>\n{esc(txt(message)[:3000])}\n\n"
        f"💡 لتسعير الطلب والرد على الزبون، قم بعمل رد (Reply) مباشر على هذه الرسالة واكتب السعر والتفاصيل."
    )
    await send_to_staff(group_id, text_to_group)
    await state.clear()
    await message.answer("✅ تم استلام طلبك وإرساله للإدارة بنجاح. سيتم مراجعته والرد عليك هنا قريباً بالسعر.", reply_markup=HOME_KB)


@dp.callback_query(F.data == "sec:support")
async def support_start(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(GlobalOrderState.support_msg)
    await safe_edit(cb, "🛠 <b>اكتب استفسارك أو مشكلتك بالتفصيل وسيقوم فريق الدعم بالرد عليك هنا:</b>", cancel_kb())


@dp.message(GlobalOrderState.support_msg)
async def support_forward(message: types.Message, state: FSMContext):
    if not txt(message):
        await message.reply("⚠️ يرجى كتابة الاستفسار كنص:")
        return
    pending = await WalletService.last_pending_order(message.from_user.id)
    pend_line = f"📦 آخر طلب معلق: <code>{pending[0]}</code> ({esc(pending[1])})\n" if pending else ""
    text_to_group = (
        f"📩 <b>تذكرة دعم فني جديدة:</b>\n"
        f"👤 الزبون: {user_tag(message.from_user)} (<code>{message.from_user.id}</code>)\n"
        f"🔑 UID: <code>{message.from_user.id}</code>\n"
        f"{pend_line}\n"
        f"📝 <b>الرسالة:</b>\n{esc(txt(message)[:3000])}\n\n"
        f"💡 للرد على الزبون، قم بعمل رد (Reply) مباشر على هذه الرسالة."
    )
    await send_to_staff(GROUPS["support"], text_to_group)
    await state.clear()
    await message.answer("✅ تم إرسال رسالتك للدعم الفني، سنرد عليك هنا بأقرب وقت.", reply_markup=HOME_KB)


# =====================================================================
# 19. إجراءات المجموعات (المشرفون)
# =====================================================================
def in_staff_group(cb: types.CallbackQuery) -> bool:
    return isinstance(cb.message, types.Message) and cb.message.chat.id in ALL_ADMIN_GROUPS


@dp.callback_query(F.data.startswith("ord_act:"))
async def handle_staff_order_action(cb: types.CallbackQuery):
    if not in_staff_group(cb):
        await cb.answer("⛔ غير مصرح.", show_alert=True)
        return
    _, action, ord_id = cb.data.split(":")

    if action == "done":
        res = await WalletService.complete_order(ord_id)
        if not res:
            await cb.answer("⚠️ الطلب غير موجود أو تم اتخاذ إجراء عليه مسبقاً!", show_alert=True)
            return
        cust_id, s_name = res
        try:
            await bot.send_message(cust_id, f"🎉 <b>تم تنفيذ طلبك بنجاح!</b>\n📦 الخدمة: <b>{esc(s_name)}</b>\n🆔 رقم الطلب: <code>{ord_id}</code>")
        except Exception as e:
            log.warning("notify customer failed: %s", e)
        await append_status(cb.message, "🟢 <b>تم التنفيذ بنجاح</b>")

    elif action == "ref":
        ok, uid, amt = await WalletService.refund(ord_id)
        if not ok:
            await cb.answer("⚠️ تعذر الاسترجاع: الطلب معالج مسبقاً أو غير موجود.", show_alert=True)
            return
        try:
            await bot.send_message(uid, f"↩️ <b>تم إلغاء الطلب {ord_id}</b> وإعادة مبلغ <b>{amt:,} ل.س</b> إلى محفظتك.")
        except Exception as e:
            log.warning("notify customer failed: %s", e)
        await append_status(cb.message, "🟡 <b>تم الإلغاء واسترجاع الرصيد للمحفظة</b>")


@dp.callback_query(F.data.startswith("adm_pay:"))
async def handle_admin_payment_action(cb: types.CallbackQuery):
    if not in_staff_group(cb):
        await cb.answer("⛔ غير مصرح.", show_alert=True)
        return
    _, act, pay_id = cb.data.split(":")

    if act == "ok":
        res = await WalletService.approve_payment(pay_id)
        if not res:
            await cb.answer("⚠️ تمت معالجة هذه الدفعة مسبقاً أو حدث خطأ!", show_alert=True)
            return
        u_id, amt, new_bal = res
        try:
            await bot.send_message(
                u_id,
                f"🎉 <b>تم تأكيد إيداعك بنجاح!</b>\n➕ تمت إضافة: <b>{amt:,} ل.س</b>\n💳 رصيدك الحالي: <code>{new_bal:,} ل.س</code>\n\nيمكنك الآن الشراء الفوري بضغطة زر واحدة!",
            )
        except Exception as e:
            log.warning("notify customer failed: %s", e)
        await append_status(cb.message, f"🟢 <b>تم قبول الإيداع ({amt:,} ل.س)</b>")
    else:
        u_id = await WalletService.decline_payment(pay_id)
        if u_id is None:
            await cb.answer("⚠️ تمت معالجة هذه الدفعة مسبقاً!", show_alert=True)
            return
        try:
            await bot.send_message(u_id, f"❌ نعتذر منك، تم رفض إشعار الإيداع للدفعة <code>{pay_id}</code> لعدم تطابق التحويل.")
        except Exception as e:
            log.warning("notify customer failed: %s", e)
        await append_status(cb.message, "🔴 <b>تم رفض الإيداع</b>")


async def extract_customer_id(orig_text: str) -> Optional[int]:
    """استخراج آيدي الزبون: UID أولاً، ثم سطر الزبون، ثم رقم الطلب/الدفعة من قاعدة البيانات، ثم أي رقم بين قوسين."""
    m = re.search(r"UID:\s*(\d{5,15})", orig_text)
    if m:
        return int(m.group(1))
    m = re.search(r"الزبون:.*?\((\d{5,15})\)", orig_text)
    if m:
        return int(m.group(1))
    m = re.search(r"\b((?:ORD|PAY)-[0-9A-Z]+-[0-9A-Z]+)\b", orig_text)
    if m:
        uid = await WalletService.user_by_reference(m.group(1))
        if uid:
            return uid
    m = re.search(r"\((\d{6,15})\)", orig_text)
    return int(m.group(1)) if m else None


@dp.message(F.reply_to_message, F.chat.id.in_(ALL_ADMIN_GROUPS))
async def admin_group_direct_reply(message: types.Message):
    replied = message.reply_to_message
    if not replied.from_user or replied.from_user.id != bot.id:
        return
    admin_text = message.text or message.caption
    if not admin_text or admin_text.startswith("/"):
        return

    orig_text = replied.text or replied.caption or ""
    cust_id = await extract_customer_id(orig_text)
    if not cust_id:
        await message.reply("⚠️ تعذر استخراج آيدي الزبون من الرسالة التي رددت عليها.")
        return
    try:
        await bot.send_message(cust_id, f"💬 <b>إشعار من الإدارة بخصوص طلبك:</b>\n\n{esc(admin_text)}")
        await message.reply("✅ تم تسليم الرد للعميل بنجاح.")
    except TelegramForbiddenError:
        await message.reply("⚠️ تعذر الإرسال: قام العميل بحظر البوت.")
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        try:
            await bot.send_message(cust_id, f"💬 <b>إشعار من الإدارة بخصوص طلبك:</b>\n\n{esc(admin_text)}")
            await message.reply("✅ تم تسليم الرد للعميل بنجاح.")
        except Exception as e2:
            await message.reply(f"⚠️ فشل تسليم الرسالة: {esc(str(e2))}")
    except Exception as e:
        await message.reply(f"⚠️ فشل تسليم الرسالة: {esc(str(e))}")


# =====================================================================
# 20. لوحة المدير
# =====================================================================
@dp.callback_query(F.data == "adm:home")
async def adm_home_return(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID:
        return
    await state.clear()
    await safe_edit(cb, ADMIN_TITLE, admin_kb())


@dp.callback_query(F.data == "adm:stats")
async def adm_stats_view(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    async with get_db() as db:
        total_users = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        total_orders = (await (await db.execute("SELECT COUNT(*) FROM orders")).fetchone())[0]
        pending = (await (await db.execute("SELECT COUNT(*) FROM orders WHERE status='PROCESSING'")).fetchone())[0]
        done = (await (await db.execute("SELECT COUNT(*) FROM orders WHERE status='COMPLETED'")).fetchone())[0]
        income = (await (await db.execute("SELECT SUM(amount) FROM payments WHERE status='ACCEPTED'")).fetchone())[0] or 0
        liab = (await (await db.execute("SELECT SUM(balance) FROM users")).fetchone())[0] or 0
    rate = await get_setting("dollar_rate")
    text = (
        f"📊 <b>إحصائيات المنصة الشاملة:</b>\n"
        f"────────────────────────────\n"
        f"👥 إجمالي المستخدمين: <b>{total_users:,}</b>\n"
        f"📦 إجمالي الطلبات: <b>{total_orders:,}</b> (منفذ: {done:,} | معلق: {pending:,})\n"
        f"💰 إجمالي الإيداعات المقبولة: <b>{income:,} ل.س</b>\n"
        f"🏦 إجمالي أرصدة الزبائن: <b>{liab:,} ل.س</b>\n"
        f"💱 سعر صرف الدولار الحالي: <b>{rate:,.2f} ل.س</b>\n"
    )
    await safe_edit(cb, text, KB([[B("🔙 رجوع", "adm:home")]]))


@dp.callback_query(F.data == "adm:set_rate")
async def adm_set_rate_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminActions.set_dollar_rate)
    rate = await get_setting("dollar_rate")
    await safe_edit(cb, f"💱 سعر الصرف الحالي: <b>{rate:,.2f} ل.س</b>\n\nأدخل سعر صرف الدولار الجديد بالليرة السورية:", cancel_kb("adm:home"))


@dp.message(AdminActions.set_dollar_rate)
async def adm_set_rate_rec(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        val = float(txt(message).replace(",", ""))
        if not (0 < val < 1e9) or val != val:
            raise ValueError
    except ValueError:
        await message.reply("⚠️ أدخل قيمة صحيحة أكبر من صفر:")
        return
    await update_setting("dollar_rate", val)
    await state.clear()
    await message.reply(f"✅ تم تحديث سعر صرف الدولار إلى: <b>{val:,.2f} ل.س</b>")


@dp.callback_query(F.data == "adm:add_bal")
async def adm_add_bal_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminActions.add_bal_user)
    await safe_edit(cb, "👤 أدخل آيدي المستخدم (User ID) المراد تغذية رصيده:", cancel_kb("adm:home"))


@dp.message(AdminActions.add_bal_user)
async def adm_add_bal_user_rec(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    u_id = to_int(txt(message))
    if not u_id:
        await message.reply("⚠️ يرجى إدخال آيدي صحيح بالأرقام:")
        return
    await state.update_data(target_uid=u_id)
    await state.set_state(AdminActions.add_bal_amount)
    await message.answer(f"💵 أدخل المبلغ المراد إضافته لحساب <code>{u_id}</code>:")


@dp.message(AdminActions.add_bal_amount)
async def adm_add_bal_amt_rec(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    amt = to_int(txt(message))
    if not amt or amt <= 0:
        await message.reply("⚠️ المبلغ يجب أن يكون رقماً صحيحاً وأكبر من صفر:")
        return
    data = await state.get_data()
    u_id = data.get("target_uid")
    await state.clear()
    if not u_id:
        await message.reply("⚠️ انتهت الجلسة، أعد المحاولة من /admin")
        return
    await WalletService.get_or_create_user(u_id)
    ok = await WalletService.deposit(u_id, amt, generate_uid("ADM"), "تغذية إدارية مباشرة")
    if ok:
        await message.reply(f"✅ تم إضافة <b>{amt:,} ل.س</b> بنجاح للمستخدم <code>{u_id}</code>.")
        try:
            await bot.send_message(u_id, f"🎉 <b>تمت إضافة {amt:,} ل.س إلى رصيد محفظتك من الإدارة!</b>")
        except Exception:
            pass
    else:
        await message.reply("❌ تعذر إضافة الرصيد.")


@dp.callback_query(F.data == "adm:broadcast")
async def adm_broadcast_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminActions.broadcast_msg)
    await safe_edit(cb, "📢 أرسل نص الرسالة التي تريد إذاعتها لجميع المستخدمين:", cancel_kb("adm:home"))


@dp.message(AdminActions.broadcast_msg)
async def adm_broadcast_rec(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if not txt(message):
        await message.reply("⚠️ أرسل نصاً للإذاعة:")
        return
    body = f"📢 <b>إشعار عام من الإدارة:</b>\n\n{esc(txt(message))}"
    await state.clear()
    async with get_db() as db:
        cur = await db.execute("SELECT user_id FROM users WHERE is_banned = 0")
        users = await cur.fetchall()

    await message.reply(f"⏳ جارٍ الإرسال إلى {len(users)} مستخدم...")
    sent = failed = 0
    for (uid,) in users:
        for _ in range(2):
            try:
                await bot.send_message(uid, body)
                sent += 1
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
            except Exception:
                failed += 1
                break
        await asyncio.sleep(0.05)
    await message.answer(f"✅ اكتملت الإذاعة! تم التسليم: {sent} | فشل: {failed}")


@dp.callback_query(F.data == "adm:close")
async def adm_close(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    try:
        await cb.message.delete()
    except Exception:
        pass


# =====================================================================
# 21. خطوط الأمان (Fallback) — يجب أن تبقى في آخر الملف
# =====================================================================
@dp.message(StateFilter(None), F.chat.type == "private")
async def no_state_fallback(message: types.Message):
    """رسالة بلا حالة (مثلاً ضاعت الجلسة): نتعرف على آخر طلب معلق ونوجّه الزبون."""
    pending = await WalletService.last_pending_order(message.from_user.id)
    if pending:
        text = (
            f"ℹ️ لديك طلب قيد التنفيذ:\n🆔 <code>{pending[0]}</code>\n📦 {esc(pending[1])}\n"
            f"💵 {pending[2]:,} ل.س\n\nإذا أردت التواصل بخصوصه اضغط «الدعم والشكاوى»."
        )
        kb = KB([[B("🛠 الدعم والشكاوى", "sec:support")], [B("🏠 الرئيسية", "back_home")]])
    else:
        text = "👋 لا يوجد إجراء نشط حالياً. اختر من القائمة الرئيسية:"
        kb = HOME_KB
    await message.answer(text, reply_markup=kb)


@dp.callback_query()
async def stale_callback_fallback(cb: types.CallbackQuery, state: FSMContext):
    """زر قديم أو انتهت جلسته."""
    if cb.message and cb.message.chat.type != "private":
        return
    await state.clear()
    await safe_edit(cb, "⚠️ انتهت صلاحية هذه الخطوة. يرجى البدء من جديد:", HOME_KB)


# =====================================================================
# 22. الإقلاع
# =====================================================================
async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=False)
    log.info("🚀 Syria Store Wallet-First System is running...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped.")
