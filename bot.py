import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ============================================================
# Syria Store / Mays Online - Professional Foundation V2
# ظ‚ط§ط¹ط¯ط© طھط´ط؛ظٹظ„ + ظ„ظˆط­ط© ط¥ط¯ط§ط±ط© ط¯ط§ط®ظ„ Telegram
# ظ‡ط°ظ‡ ط§ظ„ظ†ط³ط®ط© ظ‡ظٹ ط§ظ„ط£ط³ط§ط³ ط§ظ„ط°ظٹ طھظڈط±ظƒظ‘ط¨ ظپظˆظ‚ظ‡ ط§ظ„ط®ط¯ظ…ط§طھ ط§ظ„ط£طµظ„ظٹط© ظ„ط§ط­ظ‚ط§ظ‹.
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_RAW = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN ط؛ظٹط± ظ…ظˆط¬ظˆط¯ ظپظٹ ظ…طھط؛ظٹط±ط§طھ ط§ظ„ط¨ظٹط¦ط©.")
if not ADMIN_ID_RAW:
    raise RuntimeError("ADMIN_ID ط؛ظٹط± ظ…ظˆط¬ظˆط¯ ظپظٹ ظ…طھط؛ظٹط±ط§طھ ط§ظ„ط¨ظٹط¦ط©.")
try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except ValueError as exc:
    raise RuntimeError("ADMIN_ID ظٹط¬ط¨ ط£ظ† ظٹظƒظˆظ† ط±ظ‚ظ… Telegram طµط­ظٹط­ط§ظ‹.") from exc

CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1004492385043"))
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/SyriaStore_ch")
DB_PATH = BASE_DIR / os.getenv("DB_NAME", "bot_store.db")

GROUPS = {
    "wallet": -1003984372814,
    "balance": -1003745247353,
    "games": -1004426615112,
    "accounts": -1003985654158,
    "social": -1004411774893,
    "support": -1004420804667,
}

GROUP_NAMES = {
    "wallet": "ط§ظ„ظ…ط­ظپط¸ط© ظˆط§ظ„ظ…ط§ظ„ظٹط©",
    "balance": "ط§ظ„ط±طµظٹط¯ ظˆط§ظ„ظƒط§ط´",
    "games": "ط§ظ„ط£ظ„ط¹ط§ط¨",
    "accounts": "ط§ظ„ط­ط³ط§ط¨ط§طھ ظˆط§ظ„ط§ط´طھط±ط§ظƒط§طھ",
    "social": "ط§ظ„ط³ظˆط´ظٹط§ظ„ ظˆط§ظ„ط¥ط¹ظ„ط§ظ†ط§طھ",
    "support": "ط§ظ„ط¯ط¹ظ… ط§ظ„ظپظ†ظٹ",
}

SHAM_NAME = "ط³ظƒظٹظ†ظ‡ ط­ظ…ظˆط¯ ط·ظ‡"
SHAM_ADDR = "be03739e320f3dfd318a1a7faebae16a"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("syria_store")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# ============================================================
# Helpers
# ============================================================

def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def money(value: int) -> str:
    return f"{int(value):,} ظ„.ط³"


def parse_money(value) -> int:
    try:
        amount = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        raise ValueError("ط§ظ„ظ…ط¨ظ„ط؛ ط؛ظٹط± طµط­ظٹط­.")
    if amount <= 0 or amount != amount.to_integral_value():
        raise ValueError("ط§ظ„ظ…ط¨ظ„ط؛ ظٹط¬ط¨ ط£ظ† ظٹظƒظˆظ† ط±ظ‚ظ…ط§ظ‹ طµط­ظٹط­ط§ظ‹ ظ…ظˆط¬ط¨ط§ظ‹.")
    return int(amount)


def esc(value) -> str:
    # aiogram HTML mode needs explicit escaping for user-supplied text.
    import html
    return html.escape(str(value or ""))


def new_order_no() -> str:
    return "ORD-" + uuid.uuid4().hex[:10].upper()


def new_payment_no() -> str:
    return "PAY-" + uuid.uuid4().hex[:10].upper()


# ============================================================
# Database
# ============================================================

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    balance INTEGER NOT NULL DEFAULT 0,
    is_vip INTEGER NOT NULL DEFAULT 0,
    is_blocked INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    section TEXT NOT NULL,
    service TEXT NOT NULL,
    target TEXT,
    quantity TEXT,
    price INTEGER,
    payment_method TEXT,
    status TEXT NOT NULL DEFAULT 'pending_payment',
    admin_group_id INTEGER,
    admin_message_id INTEGER,
    admin_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_group ON orders(admin_group_id);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_no TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    order_id INTEGER,
    amount INTEGER NOT NULL,
    method TEXT NOT NULL,
    reference TEXT,
    receipt_file_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    reviewed_by INTEGER,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(order_id) REFERENCES orders(id)
);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);
CREATE INDEX IF NOT EXISTS idx_payment_reference ON payments(method,reference);

CREATE TABLE IF NOT EXISTS wallet_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    order_id INTEGER,
    payment_id INTEGER,
    amount INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    type TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(payment_id, type)
);
CREATE INDEX IF NOT EXISTS idx_ledger_user ON wallet_ledger(user_id);

CREATE TABLE IF NOT EXISTS admin_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    order_id INTEGER,
    payment_id INTEGER,
    details TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS staff (
    user_id INTEGER PRIMARY KEY,
    role TEXT NOT NULL DEFAULT 'staff',
    active INTEGER NOT NULL DEFAULT 1,
    added_by INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_staff_active ON staff(active);
"""

DEFAULT_SETTINGS = {
    "dollar_rate": "150",
    "num_whatsapp": "400",
    "num_telegram": "300",
}


async def db_connect():
    db = await aiosqlite.connect(DB_PATH, timeout=10)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=10000")
    return db


async def fetchone(db, sql, params=()):
    cursor = await db.execute(sql, params)
    try:
        return await cursor.fetchone()
    finally:
        await cursor.close()


async def fetchall(db, sql, params=()):
    cursor = await db.execute(sql, params)
    try:
        return await cursor.fetchall()
    finally:
        await cursor.close()


async def init_db():
    async with await db_connect() as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.executescript(SCHEMA)
        for key, value in DEFAULT_SETTINGS.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings(key,value,updated_at) VALUES(?,?,?)",
                (key, value, now_utc()),
            )
        # ط§ظ„ظ…ط¯ظٹط± ط§ظ„ط±ط¦ظٹط³ظٹ ط¯ط§ط¦ظ…ط§ظ‹ ظ…ظˆط¬ظˆط¯ ظپظٹ ط¬ط¯ظˆظ„ ط§ظ„ظ…ظˆط¸ظپظٹظ† ط¨طµظ„ط§ط­ظٹط© owner.
        await db.execute(
            """
            INSERT INTO staff(user_id,role,active,added_by,created_at,updated_at)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET role='owner', active=1, updated_at=excluded.updated_at
            """,
            (ADMIN_ID, "owner", 1, ADMIN_ID, now_utc(), now_utc()),
        )
        await db.commit()
    logger.info("Database ready: %s", DB_PATH)


# ============================================================
# Users / staff / permissions
# ============================================================

async def ensure_user(user_id: int, username: str | None = None, first_name: str | None = None):
    async with await db_connect() as db:
        row = await fetchone(db, "SELECT user_id FROM users WHERE user_id=?", (user_id,))
        timestamp = now_utc()
        if row is None:
            await db.execute(
                """INSERT INTO users(user_id,username,first_name,balance,is_vip,is_blocked,created_at,updated_at)
                   VALUES(?,?,?,0,0,0,?,?)""",
                (user_id, username, first_name, timestamp, timestamp),
            )
        else:
            await db.execute(
                "UPDATE users SET username=?, first_name=?, updated_at=? WHERE user_id=?",
                (username, first_name, timestamp, user_id),
            )
        await db.commit()


async def get_user(user_id: int):
    async with await db_connect() as db:
        return await fetchone(db, "SELECT * FROM users WHERE user_id=?", (user_id,))


async def set_blocked(user_id: int, blocked: bool):
    async with await db_connect() as db:
        await db.execute(
            "UPDATE users SET is_blocked=?, updated_at=? WHERE user_id=?",
            (1 if blocked else 0, now_utc(), user_id),
        )
        await db.commit()


async def get_staff_role(user_id: int):
    if user_id == ADMIN_ID:
        return "owner"
    async with await db_connect() as db:
        row = await fetchone(db, "SELECT role FROM staff WHERE user_id=? AND active=1", (user_id,))
        return row["role"] if row else None


async def is_staff(user_id: int) -> bool:
    return (await get_staff_role(user_id)) is not None


async def staff_can_section(user_id: int, section: str) -> bool:
    role = await get_staff_role(user_id)
    if role in {"owner", "staff"}:
        return role is not None
    return role == section


async def is_owner(user_id: int) -> bool:
    return user_id == ADMIN_ID


async def add_staff(user_id: int, role: str, added_by: int):
    if user_id == ADMIN_ID:
        return False
    async with await db_connect() as db:
        await db.execute(
            """
            INSERT INTO staff(user_id,role,active,added_by,created_at,updated_at)
            VALUES(?,?,1,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET role=excluded.role,active=1,updated_at=excluded.updated_at
            """,
            (user_id, role, added_by, now_utc(), now_utc()),
        )
        await db.commit()
    return True


async def remove_staff(user_id: int):
    if user_id == ADMIN_ID:
        return False
    async with await db_connect() as db:
        await db.execute("UPDATE staff SET active=0, updated_at=? WHERE user_id=?", (now_utc(), user_id))
        await db.commit()
    return True


async def get_staff():
    async with await db_connect() as db:
        return await fetchall(
            db,
            "SELECT user_id,role,active,created_at FROM staff ORDER BY active DESC, created_at DESC",
        )


async def can_manage_panel(user_id: int) -> bool:
    return await is_staff(user_id)


# ============================================================
# Settings
# ============================================================

async def get_setting(key: str, default=None):
    async with await db_connect() as db:
        row = await fetchone(db, "SELECT value FROM settings WHERE key=?", (key,))
    return row["value"] if row else default


async def set_setting(key: str, value):
    async with await db_connect() as db:
        await db.execute(
            """
            INSERT INTO settings(key,value,updated_at) VALUES(?,?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at
            """,
            (key, str(value), now_utc()),
        )
        await db.commit()


# ============================================================
# Wallet - all balance changes are atomic and logged
# ============================================================

async def wallet_credit(user_id: int, amount: int, movement_type: str, note: str = "", payment_id=None, order_id=None):
    if amount <= 0:
        return False
    async with await db_connect() as db:
        await db.execute("BEGIN IMMEDIATE")
        user = await fetchone(db, "SELECT balance FROM users WHERE user_id=?", (user_id,))
        if not user:
            await db.rollback()
            return False
        if payment_id is not None:
            duplicate = await fetchone(
                db,
                "SELECT id FROM wallet_ledger WHERE payment_id=? AND type=?",
                (payment_id, movement_type),
            )
            if duplicate:
                await db.rollback()
                return False
        new_balance = int(user["balance"]) + amount
        await db.execute(
            "UPDATE users SET balance=?,updated_at=? WHERE user_id=?",
            (new_balance, now_utc(), user_id),
        )
        await db.execute(
            """INSERT INTO wallet_ledger(user_id,order_id,payment_id,amount,balance_after,type,note,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (user_id, order_id, payment_id, amount, new_balance, movement_type, note, now_utc()),
        )
        await db.commit()
        return True


async def wallet_debit(user_id: int, amount: int, movement_type: str, note: str = "", order_id=None):
    if amount <= 0:
        return False
    async with await db_connect() as db:
        await db.execute("BEGIN IMMEDIATE")
        user = await fetchone(db, "SELECT balance FROM users WHERE user_id=?", (user_id,))
        if not user or int(user["balance"]) < amount:
            await db.rollback()
            return False
        new_balance = int(user["balance"]) - amount
        cursor = await db.execute(
            "UPDATE users SET balance=?,updated_at=? WHERE user_id=? AND balance>=?",
            (new_balance, now_utc(), user_id, amount),
        )
        if cursor.rowcount != 1:
            await db.rollback()
            return False
        await db.execute(
            """INSERT INTO wallet_ledger(user_id,order_id,amount,balance_after,type,note,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (user_id, order_id, -amount, new_balance, movement_type, note, now_utc()),
        )
        await db.commit()
        return True


# ============================================================
# Orders / payments
# ============================================================

ORDER_STATUSES = {
    "pending_payment": "ط¨ط§ظ†طھط¸ط§ط± ط§ظ„ط¯ظپط¹",
    "payment_review": "ظ…ط±ط§ط¬ط¹ط© ط§ظ„ط¯ظپط¹",
    "paid": "طھظ… ط§ظ„ط¯ظپط¹",
    "processing": "ظ‚ظٹط¯ ط§ظ„طھظ†ظپظٹط°",
    "completed": "ظ…ظƒطھظ…ظ„",
    "rejected": "ظ…ط±ظپظˆط¶",
    "cancelled": "ظ…ظ„ط؛ظٹ",
    "refunded": "ظ…ط³طھط±ط¬ط¹",
}


async def create_order(user_id: int, section: str, service: str, target="", quantity="", price=0):
    user = await get_user(user_id)
    if not user:
        raise ValueError("ط§ظ„ظ…ط³طھط®ط¯ظ… ط؛ظٹط± ظ…ظˆط¬ظˆط¯.")
    if int(user["is_blocked"]) == 1:
        raise PermissionError("ط§ظ„ظ…ط³طھط®ط¯ظ… ظ…ظˆظ‚ظˆظپ.")
    if price <= 0:
        raise ValueError("ط³ط¹ط± ط§ظ„ط·ظ„ط¨ ط؛ظٹط± طµط­ظٹط­.")
    group_id = GROUPS.get(section)
    if group_id is None:
        raise ValueError("ط§ظ„ظ‚ط³ظ… ط؛ظٹط± ظ…ط±طھط¨ط· ط¨ظ…ط¬ظ…ظˆط¹ط© ط¥ط¯ط§ط±ط©.")
    order_no = new_order_no()
    async with await db_connect() as db:
        cursor = await db.execute(
            """INSERT INTO orders(order_no,user_id,section,service,target,quantity,price,status,admin_group_id,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,'pending_payment',?,?,?)""",
            (order_no, user_id, section, service, target, quantity, price, group_id, now_utc(), now_utc()),
        )
        order_id = cursor.lastrowid
        await db.commit()
    return int(order_id), order_no


async def get_order(order_id: int):
    async with await db_connect() as db:
        return await fetchone(db, "SELECT * FROM orders WHERE id=?", (order_id,))


async def get_order_by_no(order_no: str):
    async with await db_connect() as db:
        return await fetchone(db, "SELECT * FROM orders WHERE order_no=?", (order_no,))


async def set_order_status(order_id: int, status: str, note=None):
    if status not in ORDER_STATUSES:
        raise ValueError("ط­ط§ظ„ط© ط؛ظٹط± طµط­ظٹط­ط©.")
    async with await db_connect() as db:
        await db.execute(
            "UPDATE orders SET status=?,admin_note=COALESCE(?,admin_note),updated_at=? WHERE id=?",
            (status, note, now_utc(), order_id),
        )
        await db.commit()


async def attach_admin_message(order_id: int, group_id: int, message_id: int):
    async with await db_connect() as db:
        await db.execute(
            "UPDATE orders SET admin_group_id=?,admin_message_id=?,updated_at=? WHERE id=?",
            (group_id, message_id, now_utc(), order_id),
        )
        await db.commit()


async def create_payment(user_id: int, order_id: int, amount: int, method: str, reference="", receipt_file_id=""):
    payment_no = new_payment_no()
    async with await db_connect() as db:
        order = await fetchone(db, "SELECT * FROM orders WHERE id=?", (order_id,))
        if not order or int(order["user_id"]) != user_id:
            raise ValueError("ط§ظ„ط·ظ„ط¨ ط؛ظٹط± طµط§ظ„ط­.")
        if order["status"] in {"cancelled", "rejected", "completed", "refunded"}:
            raise ValueError("ظ„ط§ ظٹظ…ظƒظ† ط§ظ„ط¯ظپط¹ ظ„ظ‡ط°ط§ ط§ظ„ط·ظ„ط¨.")
        if reference:
            duplicate_reference = await fetchone(
                db,
                "SELECT id FROM payments WHERE method=? AND reference=? LIMIT 1",
                (method, reference),
            )
            if duplicate_reference:
                raise ValueError("ط±ظ‚ظ… ط¹ظ…ظ„ظٹط© ط§ظ„ط¯ظپط¹ ظ…ط³طھط®ط¯ظ… ظ…ط³ط¨ظ‚ط§ظ‹.")
        cursor = await db.execute(
            """INSERT INTO payments(payment_no,user_id,order_id,amount,method,reference,receipt_file_id,status,created_at)
               VALUES(?,?,?,?,?,?,?,'pending',?)""",
            (payment_no, user_id, order_id, amount, method, reference, receipt_file_id, now_utc()),
        )
        payment_id = cursor.lastrowid
        await db.execute("UPDATE orders SET status='payment_review',payment_method=?,updated_at=? WHERE id=?", (method, now_utc(), order_id))
        await db.commit()
    return int(payment_id), payment_no


async def get_payment(payment_id: int):
    async with await db_connect() as db:
        return await fetchone(db, "SELECT * FROM payments WHERE id=?", (payment_id,))


async def review_payment(payment_id: int, admin_id: int, approve: bool):
    async with await db_connect() as db:
        await db.execute("BEGIN IMMEDIATE")
        payment = await fetchone(db, "SELECT * FROM payments WHERE id=?", (payment_id,))
        if not payment:
            await db.rollback()
            return False, "payment_not_found", None
        if payment["status"] != "pending":
            await db.rollback()
            return False, "already_reviewed", payment

        order = await fetchone(db, "SELECT * FROM orders WHERE id=?", (payment["order_id"],))
        if not order:
            await db.rollback()
            return False, "order_not_found", payment

        new_payment_status = "approved" if approve else "rejected"
        await db.execute(
            "UPDATE payments SET status=?,reviewed_by=?,reviewed_at=? WHERE id=? AND status='pending'",
            (new_payment_status, admin_id, now_utc(), payment_id),
        )

        if approve:
            if order["section"] == "wallet":
                user = await fetchone(db, "SELECT balance FROM users WHERE user_id=?", (payment["user_id"],))
                if not user:
                    await db.rollback()
                    return False, "user_not_found", payment
                new_balance = int(user["balance"]) + int(payment["amount"])
                await db.execute(
                    "UPDATE users SET balance=?,is_vip=1,updated_at=? WHERE user_id=?",
                    (new_balance, now_utc(), payment["user_id"]),
                )
                await db.execute(
                    """INSERT INTO wallet_ledger(user_id,order_id,payment_id,amount,balance_after,type,note,created_at)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (payment["user_id"], payment["order_id"], payment_id, int(payment["amount"]), new_balance, "deposit", "طھط£ظƒظٹط¯ ط¥ظٹط¯ط§ط¹ ظ…ط­ظپط¸ط©", now_utc()),
                )
            await db.execute("UPDATE orders SET status='paid',updated_at=? WHERE id=?", (now_utc(), payment["order_id"]))
        else:
            await db.execute("UPDATE orders SET status='rejected',updated_at=? WHERE id=?", (now_utc(), payment["order_id"]))

        await db.execute(
            "INSERT INTO admin_actions(admin_id,action,order_id,payment_id,details,created_at) VALUES(?,?,?,?,?,?)",
            (admin_id, new_payment_status, payment["order_id"], payment_id, "ظ…ط±ط§ط¬ط¹ط© ط¯ظپط¹ط©", now_utc()),
        )
        await db.commit()
        return True, new_payment_status, payment


async def mark_order_processing(order_id: int, admin_id: int):
    async with await db_connect() as db:
        await db.execute("BEGIN IMMEDIATE")
        order = await fetchone(db, "SELECT * FROM orders WHERE id=?", (order_id,))
        if not order:
            await db.rollback()
            return False, None
        if order["status"] not in {"paid", "processing"}:
            await db.rollback()
            return False, order
        await db.execute("UPDATE orders SET status='processing',updated_at=? WHERE id=?", (now_utc(), order_id))
        await db.execute(
            "INSERT INTO admin_actions(admin_id,action,order_id,details,created_at) VALUES(?,?,?,?,?)",
            (admin_id, "processing", order_id, "ط¨ط¯ط، طھظ†ظپظٹط° ط§ظ„ط·ظ„ط¨", now_utc()),
        )
        await db.commit()
        return True, order


async def finish_order(order_id: int, admin_id: int):
    async with await db_connect() as db:
        await db.execute("BEGIN IMMEDIATE")
        order = await fetchone(db, "SELECT * FROM orders WHERE id=?", (order_id,))
        if not order or order["status"] not in {"paid", "processing"}:
            await db.rollback()
            return False, order
        await db.execute("UPDATE orders SET status='completed',updated_at=? WHERE id=?", (now_utc(), order_id))
        await db.execute(
            "INSERT INTO admin_actions(admin_id,action,order_id,details,created_at) VALUES(?,?,?,?,?)",
            (admin_id, "completed", order_id, "ط¥ظƒظ…ط§ظ„ ط§ظ„ط·ظ„ط¨", now_utc()),
        )
        await db.commit()
        return True, order


async def cancel_order(order_id: int, user_id: int):
    async with await db_connect() as db:
        await db.execute("BEGIN IMMEDIATE")
        order = await fetchone(db, "SELECT * FROM orders WHERE id=?", (order_id,))
        if not order or int(order["user_id"]) != user_id or order["status"] != "pending_payment":
            await db.rollback()
            return False
        await db.execute("UPDATE orders SET status='cancelled',updated_at=? WHERE id=?", (now_utc(), order_id))
        await db.commit()
        return True


# ============================================================
# Subscription / user UI
# ============================================================

async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status not in {"left", "kicked"}
    except Exception:
        logger.exception("Subscription check failed")
        return False


def subscription_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ًں“¢ ط§ظ„ط§ط´طھط±ط§ظƒ ظپظٹ ط§ظ„ظ‚ظ†ط§ط©", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="ًں”„ طھط­ظ‚ظ‚ ظ…ظ† ط§ظ„ط§ط´طھط±ط§ظƒ", callback_data="check_subscription")],
    ])


def user_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ًں“‍ ط§ظ„ط±طµظٹط¯ ظˆط§ظ„ظƒط§ط´", callback_data="sec_balance")],
        [InlineKeyboardButton(text="ًںژ® ط´ط­ظ† ط§ظ„ط£ظ„ط¹ط§ط¨", callback_data="sec_games")],
        [InlineKeyboardButton(text="ًں’¬ طھط·ط¨ظٹظ‚ط§طھ ط§ظ„ط´ط§طھ", callback_data="sec_chat")],
        [InlineKeyboardButton(text="ًں“¦ ط§ظ„ط­ط³ط§ط¨ط§طھ ظˆط§ظ„ط§ط´طھط±ط§ظƒط§طھ", callback_data="sec_accounts")],
        [InlineKeyboardButton(text="ًںڑ€ ط§ظ„ط³ظˆط´ظٹط§ظ„ ظˆط§ظ„ط¥ط¹ظ„ط§ظ†ط§طھ", callback_data="sec_social")],
        [InlineKeyboardButton(text="ًں“± ط£ط±ظ‚ط§ظ… ط§ظ„طھظپط¹ظٹظ„", callback_data="sec_numbers")],
        [InlineKeyboardButton(text="ًں’³ ظ…ط­ظپط¸طھظٹ", callback_data="sec_wallet")],
        [InlineKeyboardButton(text="ًں›  ط§ظ„ط¯ط¹ظ… ط§ظ„ظپظ†ظٹ", callback_data="sec_support")],
    ])


async def user_home_text(user_id: int):
    user = await get_user(user_id)
    balance = int(user["balance"]) if user else 0
    vip = bool(user and int(user["is_vip"]) == 1)
    return (
        "ًں‘‹ <b>ط£ظ‡ظ„ط§ظ‹ ط¨ظƒ ظپظٹ Syria Store</b>\n"
        "â”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
        f"ًںڈ· <b>ط§ظ„ط±طھط¨ط©:</b> {'ًںŒں ط²ط¨ظˆظ† ط¯ط§ط¦ظ… (VIP)' if vip else 'ًں‘¤ ط²ط¨ظˆظ† ط¹ط§ط¯ظٹ'}\n"
        f"ًں’³ <b>ط§ظ„ط±طµظٹط¯:</b> {money(balance)}\n"
        "â”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
        "ط§ط®طھط± ط§ظ„ظ‚ط³ظ… ط§ظ„ظ…ط·ظ„ظˆط¨:"
    )


@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await ensure_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    user = await get_user(message.from_user.id)
    if user and int(user["is_blocked"]) == 1:
        await message.answer("â›” ط­ط³ط§ط¨ظƒ ظ…ظˆظ‚ظˆظپ ط­ط§ظ„ظٹط§ظ‹. طھظˆط§طµظ„ ظ…ط¹ ط§ظ„ط¥ط¯ط§ط±ط©.")
        return
    if not await is_subscribed(message.from_user.id):
        await message.answer("âڑ ï¸ڈ ظٹط¬ط¨ ط§ظ„ط§ط´طھط±ط§ظƒ ظپظٹ ط§ظ„ظ‚ظ†ط§ط© ط§ظ„ط±ط³ظ…ظٹط© ط£ظˆظ„ط§ظ‹.", reply_markup=subscription_keyboard())
        return
    await message.answer(await user_home_text(message.from_user.id), reply_markup=user_main_keyboard())


@dp.callback_query(F.data == "check_subscription")
async def check_subscription(callback: types.CallbackQuery):
    if not await is_subscribed(callback.from_user.id):
        await callback.answer("â‌Œ ظ„ظ… ظٹطھظ… ط§ظ„ط¹ط«ظˆط± ط¹ظ„ظ‰ ط§ط´طھط±ط§ظƒظƒ ط¨ط¹ط¯.", show_alert=True)
        return
    await callback.answer("âœ… طھظ… ط§ظ„طھط­ظ‚ظ‚.")
    await callback.message.edit_text(await user_home_text(callback.from_user.id), reply_markup=user_main_keyboard())


@dp.callback_query(F.data == "back_main")
async def back_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(await user_home_text(callback.from_user.id), reply_markup=user_main_keyboard())


# ============================================================
# Admin Panel
# ============================================================

class AdminState(StatesGroup):
    search_user = State()
    set_setting = State()
    add_staff_id = State()
    add_staff_role = State()
    broadcast_text = State()
    order_lookup = State()
    balance_user_id = State()
    balance_amount = State()
    block_user_id = State()


def admin_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ًں“¦ ط§ظ„ط·ظ„ط¨ط§طھ", callback_data="adm:orders"), InlineKeyboardButton(text="ًں’³ ط§ظ„ظ…ط¯ظپظˆط¹ط§طھ", callback_data="adm:payments")],
        [InlineKeyboardButton(text="ًں‘¥ ط§ظ„ظ…ط³طھط®ط¯ظ…ظˆظ†", callback_data="adm:users"), InlineKeyboardButton(text="ًں“ٹ ط§ظ„ط¥ط­طµط§ط¦ظٹط§طھ", callback_data="adm:stats")],
        [InlineKeyboardButton(text="ًں’° ط¥ط¯ط§ط±ط© ط§ظ„ط£ط±طµط¯ط©", callback_data="adm:balance"), InlineKeyboardButton(text="ًں’µ ط§ظ„ط£ط³ط¹ط§ط± ظˆط§ظ„ط¥ط¹ط¯ط§ط¯ط§طھ", callback_data="adm:settings")],
        [InlineKeyboardButton(text="ًں‘¨â€چًں’¼ ط§ظ„ظ…ظˆط¸ظپظˆظ†", callback_data="adm:staff"), InlineKeyboardButton(text="ًں“¢ ط¥ط¹ظ„ط§ظ† ط¬ظ…ط§ط¹ظٹ", callback_data="adm:broadcast")],
        [InlineKeyboardButton(text="ًںڈ¢ ظ…ط¬ظ…ظˆط¹ط§طھ ط§ظ„ط£ظ‚ط³ط§ظ…", callback_data="adm:groups"), InlineKeyboardButton(text="ًں“‹ ط³ط¬ظ„ ط§ظ„ط¥ط¯ط§ط±ط©", callback_data="adm:logs")],
    ])


def admin_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="ًں”™ ظ„ظˆط­ط© ط§ظ„ط¥ط¯ط§ط±ط©", callback_data="adm:home")]])


async def require_owner_callback(callback: types.CallbackQuery) -> bool:
    if not await is_owner(callback.from_user.id):
        await callback.answer("â›” ظ‡ط°ط§ ط§ظ„ط¥ط¬ط±ط§ط، ظ„ظ„ظ…ط¯ظٹط± ط§ظ„ط±ط¦ظٹط³ظٹ ظپظ‚ط·.", show_alert=True)
        return False
    return True


async def require_staff_callback(callback: types.CallbackQuery) -> bool:
    if not await can_manage_panel(callback.from_user.id):
        await callback.answer("â›” ظ„ط§ طھظ…ظ„ظƒ طµظ„ط§ط­ظٹط© ظ„ظˆط­ط© ط§ظ„ط¥ط¯ط§ط±ط©.", show_alert=True)
        return False
    return True


async def require_order_access(user_id: int, order) -> bool:
    return await staff_can_section(user_id, str(order["section"]))


async def require_payment_access(user_id: int, payment) -> bool:
    if payment is None:
        return False
    order = await get_order(int(payment["order_id"]))
    return bool(order and await require_order_access(user_id, order))


async def admin_panel_message(user_id: int):
    return (
        "ًں”گ <b>ظ„ظˆط­ط© ط¥ط¯ط§ط±ط© Syria Store</b>\n"
        "â”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
        "ظ…ظ† ظ‡ظ†ط§ طھطھظ… ط¥ط¯ط§ط±ط© ط§ظ„ط·ظ„ط¨ط§طھ ظˆط§ظ„ظ…ط¯ظپظˆط¹ط§طھ ظˆط§ظ„ظ…ط³طھط®ط¯ظ…ظٹظ† ظˆط§ظ„ط£ط³ط¹ط§ط± ظˆط§ظ„ظ…ظˆط¸ظپظٹظ†.\n\n"
        "âڑ ï¸ڈ ظƒظ„ ط¥ط¬ط±ط§ط، ظ…ط§ظ„ظٹ ط£ظˆ ط¥ط¯ط§ط±ظٹ ظ…ظ‡ظ… ظٹطھظ… طھط³ط¬ظٹظ„ظ‡ ظپظٹ ط³ط¬ظ„ ط§ظ„ط¥ط¯ط§ط±ط©."
    )


@dp.message(Command("admin"))
async def admin_command(message: types.Message, state: FSMContext):
    await state.clear()
    if not await can_manage_panel(message.from_user.id):
        await message.answer("â›” ظ„ط§ طھظ…ظ„ظƒ طµظ„ط§ط­ظٹط© ط§ظ„ط¯ط®ظˆظ„ ط¥ظ„ظ‰ ظ„ظˆط­ط© ط§ظ„ط¥ط¯ط§ط±ط©.")
        return
    await message.answer(await admin_panel_message(message.from_user.id), reply_markup=admin_main_keyboard())


@dp.callback_query(F.data == "adm:home")
async def admin_home(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if not await require_staff_callback(callback):
        return
    await callback.answer()
    await callback.message.edit_text(await admin_panel_message(callback.from_user.id), reply_markup=admin_main_keyboard())


@dp.callback_query(F.data == "adm:stats")
async def admin_stats(callback: types.CallbackQuery):
    if not await require_staff_callback(callback):
        return
    async with await db_connect() as db:
        users = await fetchone(db, "SELECT COUNT(*) c FROM users")
        blocked = await fetchone(db, "SELECT COUNT(*) c FROM users WHERE is_blocked=1")
        orders = await fetchone(db, "SELECT COUNT(*) c FROM orders")
        pending_orders = await fetchone(db, "SELECT COUNT(*) c FROM orders WHERE status IN ('payment_review','paid','processing')")
        completed = await fetchone(db, "SELECT COUNT(*) c FROM orders WHERE status='completed'")
        pending_pay = await fetchone(db, "SELECT COUNT(*) c FROM payments WHERE status='pending'")
        turnover = await fetchone(db, "SELECT COALESCE(SUM(amount),0) total FROM payments WHERE status='approved'")
    text = (
        "ًں“ٹ <b>ط¥ط­طµط§ط¦ظٹط§طھ ط§ظ„ط¨ظˆطھ</b>\nâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
        f"ًں‘¥ ط§ظ„ظ…ط³طھط®ط¯ظ…ظˆظ†: <b>{users['c']}</b>\n"
        f"ًںڑ« ط§ظ„ظ…ط­ط¸ظˆط±ظˆظ†: <b>{blocked['c']}</b>\n"
        f"ًں“¦ ط¥ط¬ظ…ط§ظ„ظٹ ط§ظ„ط·ظ„ط¨ط§طھ: <b>{orders['c']}</b>\n"
        f"âڈ³ ط§ظ„ط·ظ„ط¨ط§طھ ط§ظ„ظ†ط´ط·ط©: <b>{pending_orders['c']}</b>\n"
        f"âœ… ط§ظ„ط·ظ„ط¨ط§طھ ط§ظ„ظ…ظƒطھظ…ظ„ط©: <b>{completed['c']}</b>\n"
        f"ًں’³ ط¯ظپط¹ط§طھ ط¨ط§ظ†طھط¸ط§ط± ط§ظ„ظ…ط±ط§ط¬ط¹ط©: <b>{pending_pay['c']}</b>\n"
        f"ًں’° ط¥ط¬ظ…ط§ظ„ظٹ ط§ظ„ط¯ظپط¹ط§طھ ط§ظ„ظ…ظ‚ط¨ظˆظ„ط©: <b>{money(int(turnover['total']))}</b>"
    )
    await callback.message.edit_text(text, reply_markup=admin_back_keyboard())


@dp.callback_query(F.data == "adm:orders")
async def admin_orders(callback: types.CallbackQuery):
    if not await require_staff_callback(callback):
        return
    role = await get_staff_role(callback.from_user.id)
    async with await db_connect() as db:
        if role in {"owner", "staff"}:
            rows = await fetchall(
                db,
                """SELECT id,order_no,user_id,section,service,price,status,created_at
                   FROM orders ORDER BY id DESC LIMIT 15""",
            )
        else:
            rows = await fetchall(
                db,
                """SELECT id,order_no,user_id,section,service,price,status,created_at
                   FROM orders WHERE section=? ORDER BY id DESC LIMIT 15""",
                (role,),
            )
    if not rows:
        text = "ًں“¦ ظ„ط§ طھظˆط¬ط¯ ط·ظ„ط¨ط§طھ ط­طھظ‰ ط§ظ„ط¢ظ†."
        kb = admin_back_keyboard()
    else:
        text = "ًں“¦ <b>ط¢ط®ط± ط§ظ„ط·ظ„ط¨ط§طھ</b>\nâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
        buttons = []
        for row in rows:
            text += f"<code>{esc(row['order_no'])}</code> â€” {esc(row['service'])} â€” {money(int(row['price'] or 0))} â€” <b>{ORDER_STATUSES.get(row['status'], row['status'])}</b>\n"
            buttons.append([InlineKeyboardButton(text=f"ًں”ژ {row['order_no']}", callback_data=f"adm:order:{row['id']}")])
        buttons.append([InlineKeyboardButton(text="ًں”™ ظ„ظˆط­ط© ط§ظ„ط¥ط¯ط§ط±ط©", callback_data="adm:home")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=kb)


async def order_admin_keyboard(order):
    oid = int(order["id"])
    status = order["status"]
    buttons = []
    if status == "paid":
        buttons.append([InlineKeyboardButton(text="â–¶ï¸ڈ ط¨ط¯ط، ط§ظ„طھظ†ظپظٹط°", callback_data=f"adm:processing:{oid}")])
    if status == "processing":
        buttons.append([InlineKeyboardButton(text="âœ… ط¥طھظ…ط§ظ… ط§ظ„ط·ظ„ط¨", callback_data=f"adm:complete:{oid}")])
    if status in {"paid", "processing"}:
        buttons.append([InlineKeyboardButton(text="â‌Œ ط±ظپط¶/ط¥ظ„ط؛ط§ط،", callback_data=f"adm:reject:{oid}")])
    buttons.append([InlineKeyboardButton(text="ًں”™ ط§ظ„ط·ظ„ط¨ط§طھ", callback_data="adm:orders")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def order_detail_text(order):
    user = await get_user(int(order["user_id"]))
    username = f"@{user['username']}" if user and user["username"] else "ط¨ط¯ظˆظ† ظٹظˆط²ط±"
    return (
        "ًں“¦ <b>طھظپط§طµظٹظ„ ط§ظ„ط·ظ„ط¨</b>\nâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
        f"ًں†” ط±ظ‚ظ… ط§ظ„ط·ظ„ط¨: <code>{esc(order['order_no'])}</code>\n"
        f"ًں‘¤ ط§ظ„ط¹ظ…ظٹظ„: {esc(username)} (<code>{order['user_id']}</code>)\n"
        f"ًںڈ· ط§ظ„ظ‚ط³ظ…: {esc(order['section'])}\n"
        f"ًں›چ ط§ظ„ط®ط¯ظ…ط©: {esc(order['service'])}\n"
        f"ًںژ¯ ط§ظ„ظ‡ط¯ظپ: {esc(order['target'])}\n"
        f"ًں“¦ ط§ظ„ظƒظ…ظٹط©: {esc(order['quantity'])}\n"
        f"ًں’° ط§ظ„ط³ط¹ط±: <b>{money(int(order['price'] or 0))}</b>\n"
        f"ًں’³ ط§ظ„ط¯ظپط¹: {esc(order['payment_method'] or 'ظ„ظ… ظٹط­ط¯ط¯')}\n"
        f"ًں“Œ ط§ظ„ط­ط§ظ„ط©: <b>{ORDER_STATUSES.get(order['status'], order['status'])}</b>\n"
        f"ًں•’ ط§ظ„ط¥ظ†ط´ط§ط،: {esc(order['created_at'])}"
    )


@dp.callback_query(F.data.startswith("adm:order:"))
async def admin_order_detail(callback: types.CallbackQuery):
    if not await require_staff_callback(callback):
        return
    order_id = int(callback.data.split(":")[-1])
    order = await get_order(order_id)
    if not order:
        await callback.answer("ط§ظ„ط·ظ„ط¨ ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", show_alert=True)
        return
    if not await require_order_access(callback.from_user.id, order):
        await callback.answer("â›” ظ„ط§ طھظ…ظ„ظƒ طµظ„ط§ط­ظٹط© ظ‡ط°ط§ ط§ظ„ظ‚ط³ظ….", show_alert=True)
        return
    await callback.message.edit_text(await order_detail_text(order), reply_markup=await order_admin_keyboard(order))


@dp.callback_query(F.data.startswith("adm:processing:"))
async def admin_processing(callback: types.CallbackQuery):
    if not await require_staff_callback(callback):
        return
    oid = int(callback.data.split(":")[-1])
    original = await get_order(oid)
    if not original or not await require_order_access(callback.from_user.id, original):
        await callback.answer("â›” ظ„ط§ طھظ…ظ„ظƒ طµظ„ط§ط­ظٹط© ظ‡ط°ط§ ط§ظ„ظ‚ط³ظ….", show_alert=True)
        return
    ok, order = await mark_order_processing(oid, callback.from_user.id)
    if not ok:
        await callback.answer("ظ„ط§ ظٹظ…ظƒظ† ط¨ط¯ط، طھظ†ظپظٹط° ظ‡ط°ط§ ط§ظ„ط·ظ„ط¨ ط¨ط§ظ„ط­ط§ظ„ط© ط§ظ„ط­ط§ظ„ظٹط©.", show_alert=True)
        return
    await callback.answer("â–¶ï¸ڈ ط¨ط¯ط£ ط§ظ„طھظ†ظپظٹط°.")
    await callback.message.edit_text(await order_detail_text(await get_order(oid)), reply_markup=await order_admin_keyboard(await get_order(oid)))
    try:
        await bot.send_message(int(order["user_id"]), f"â–¶ï¸ڈ ط¨ط¯ط£ طھظ†ظپظٹط° ط·ظ„ط¨ظƒ <code>{esc(order['order_no'])}</code>.")
    except Exception:
        logger.exception("Could not notify user about processing order")


@dp.callback_query(F.data.startswith("adm:complete:"))
async def admin_complete(callback: types.CallbackQuery):
    if not await require_staff_callback(callback):
        return
    oid = int(callback.data.split(":")[-1])
    original = await get_order(oid)
    if not original or not await require_order_access(callback.from_user.id, original):
        await callback.answer("â›” ظ„ط§ طھظ…ظ„ظƒ طµظ„ط§ط­ظٹط© ظ‡ط°ط§ ط§ظ„ظ‚ط³ظ….", show_alert=True)
        return
    ok, order = await finish_order(oid, callback.from_user.id)
    if not ok:
        await callback.answer("ظ„ط§ ظٹظ…ظƒظ† ط¥طھظ…ط§ظ… ظ‡ط°ط§ ط§ظ„ط·ظ„ط¨ ط¨ط§ظ„ط­ط§ظ„ط© ط§ظ„ط­ط§ظ„ظٹط©.", show_alert=True)
        return
    await callback.answer("âœ… طھظ… ط¥طھظ…ط§ظ… ط§ظ„ط·ظ„ط¨.")
    fresh = await get_order(oid)
    await callback.message.edit_text(await order_detail_text(fresh), reply_markup=await order_admin_keyboard(fresh))
    try:
        await bot.send_message(int(order["user_id"]), f"âœ… طھظ… ط¥طھظ…ط§ظ… ط·ظ„ط¨ظƒ <code>{esc(order['order_no'])}</code> ط¨ظ†ط¬ط§ط­.")
    except Exception:
        logger.exception("Could not notify user about completed order")


@dp.callback_query(F.data.startswith("adm:reject:"))
async def admin_reject(callback: types.CallbackQuery):
    if not await require_staff_callback(callback):
        return
    oid = int(callback.data.split(":")[-1])
    order = await get_order(oid)
    if order and not await require_order_access(callback.from_user.id, order):
        await callback.answer("â›” ظ„ط§ طھظ…ظ„ظƒ طµظ„ط§ط­ظٹط© ظ‡ط°ط§ ط§ظ„ظ‚ط³ظ….", show_alert=True)
        return
    if not order or order["status"] not in {"paid", "processing"}:
        await callback.answer("ظ„ط§ ظٹظ…ظƒظ† ط±ظپط¶ ط§ظ„ط·ظ„ط¨ ط¨ظ‡ط°ظ‡ ط§ظ„ط­ط§ظ„ط©.", show_alert=True)
        return
    await set_order_status(oid, "rejected", "طھظ… ط§ظ„ط±ظپط¶ ظ…ظ† ط§ظ„ط¥ط¯ط§ط±ط©")
    await callback.answer("طھظ… ط±ظپط¶ ط§ظ„ط·ظ„ط¨.")
    fresh = await get_order(oid)
    await callback.message.edit_text(await order_detail_text(fresh), reply_markup=await order_admin_keyboard(fresh))
    try:
        await bot.send_message(int(order["user_id"]), f"â‌Œ طھظ… ط±ظپط¶ ط·ظ„ط¨ظƒ <code>{esc(order['order_no'])}</code>. طھظˆط§طµظ„ ظ…ط¹ ط§ظ„ط¯ط¹ظ… ط¹ظ†ط¯ ط§ظ„ط­ط§ط¬ط©.")
    except Exception:
        logger.exception("Could not notify user about rejected order")


@dp.callback_query(F.data == "adm:payments")
async def admin_payments(callback: types.CallbackQuery):
    if not await require_staff_callback(callback):
        return
    role = await get_staff_role(callback.from_user.id)
    async with await db_connect() as db:
        if role in {"owner", "staff"}:
            rows = await fetchall(
                db,
                """SELECT p.id,p.payment_no,p.user_id,p.order_id,p.amount,p.method,p.reference,p.created_at
                   FROM payments p WHERE p.status='pending' ORDER BY p.id ASC LIMIT 20""",
            )
        else:
            rows = await fetchall(
                db,
                """SELECT p.id,p.payment_no,p.user_id,p.order_id,p.amount,p.method,p.reference,p.created_at
                   FROM payments p JOIN orders o ON o.id=p.order_id
                   WHERE p.status='pending' AND o.section=? ORDER BY p.id ASC LIMIT 20""",
                (role,),
            )
    if not rows:
        await callback.message.edit_text("ًں’³ ظ„ط§ طھظˆط¬ط¯ ط¯ظپط¹ط§طھ ط¨ط§ظ†طھط¸ط§ط± ط§ظ„ظ…ط±ط§ط¬ط¹ط©.", reply_markup=admin_back_keyboard())
        return
    text = "ًں’³ <b>ط¯ظپط¹ط§طھ ط¨ط§ظ†طھط¸ط§ط± ط§ظ„ظ…ط±ط§ط¬ط¹ط©</b>\nâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
    buttons = []
    for row in rows:
        text += f"<code>{row['payment_no']}</code> â€” {money(int(row['amount']))} â€” {esc(row['method'])}\n"
        buttons.append([InlineKeyboardButton(text=f"ًں”ژ {row['payment_no']}", callback_data=f"adm:payment:{row['id']}")])
    buttons.append([InlineKeyboardButton(text="ًں”™ ظ„ظˆط­ط© ط§ظ„ط¥ط¯ط§ط±ط©", callback_data="adm:home")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@dp.callback_query(F.data.startswith("adm:payment:"))
async def admin_payment_detail(callback: types.CallbackQuery):
    if not await require_staff_callback(callback):
        return
    pid = int(callback.data.split(":")[-1])
    payment = await get_payment(pid)
    if not payment:
        await callback.answer("ط§ظ„ط¯ظپط¹ط© ط؛ظٹط± ظ…ظˆط¬ظˆط¯ط©.", show_alert=True)
        return
    if not await require_payment_access(callback.from_user.id, payment):
        await callback.answer("â›” ظ„ط§ طھظ…ظ„ظƒ طµظ„ط§ط­ظٹط© ظ‡ط°ط§ ط§ظ„ظ‚ط³ظ….", show_alert=True)
        return
    text = (
        "ًں’³ <b>ظ…ط±ط§ط¬ط¹ط© ط¯ظپط¹ط©</b>\nâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
        f"ًں†” {esc(payment['payment_no'])}\n"
        f"ًں‘¤ ط§ظ„ظ…ط³طھط®ط¯ظ…: <code>{payment['user_id']}</code>\n"
        f"ًں“¦ ط§ظ„ط·ظ„ط¨: <code>{payment['order_id']}</code>\n"
        f"ًں’° ط§ظ„ظ…ط¨ظ„ط؛: <b>{money(int(payment['amount']))}</b>\n"
        f"ًں’³ ط§ظ„ط·ط±ظٹظ‚ط©: {esc(payment['method'])}\n"
        f"ًں§¾ ط§ظ„ظ…ط±ط¬ط¹: <code>{esc(payment['reference'] or 'ط؛ظٹط± ظ…ظˆط¬ظˆط¯')}</code>\n"
        f"ًں•’ {esc(payment['created_at'])}"
    )
    buttons = [
        [InlineKeyboardButton(text="âœ… ظ‚ط¨ظˆظ„", callback_data=f"adm:approve:{pid}"), InlineKeyboardButton(text="â‌Œ ط±ظپط¶", callback_data=f"adm:deny:{pid}")],
        [InlineKeyboardButton(text="ًں”™ ط§ظ„ظ…ط¯ظپظˆط¹ط§طھ", callback_data="adm:payments")],
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@dp.callback_query(F.data.startswith("adm:approve:"))
async def admin_approve_payment(callback: types.CallbackQuery):
    if not await require_staff_callback(callback):
        return
    pid = int(callback.data.split(":")[-1])
    payment_before = await get_payment(pid)
    if not payment_before or not await require_payment_access(callback.from_user.id, payment_before):
        await callback.answer("â›” ظ„ط§ طھظ…ظ„ظƒ طµظ„ط§ط­ظٹط© ظ‡ط°ط§ ط§ظ„ظ‚ط³ظ….", show_alert=True)
        return
    ok, status, payment = await review_payment(pid, callback.from_user.id, True)
    if not ok:
        await callback.answer("ط§ظ„ط¯ظپط¹ط© طھظ…طھ ظ…ط±ط§ط¬ط¹طھظ‡ط§ ظ…ط³ط¨ظ‚ط§ظ‹ ط£ظˆ ط؛ظٹط± ظ…ظˆط¬ظˆط¯ط©.", show_alert=True)
        return
    await callback.answer("âœ… طھظ… ظ‚ط¨ظˆظ„ ط§ظ„ط¯ظپط¹ط©.")
    await callback.message.edit_text("âœ… طھظ… ظ‚ط¨ظˆظ„ ط§ظ„ط¯ظپط¹ط© ظˆطھط³ط¬ظٹظ„ظ‡ط§ ظپظٹ ظ‚ط§ط¹ط¯ط© ط§ظ„ط¨ظٹط§ظ†ط§طھ.", reply_markup=admin_back_keyboard())
    if payment and payment["order_id"]:
        approved_order = await get_order(int(payment["order_id"]))
        if approved_order and approved_order["section"] != "wallet":
            try:
                await dispatch_order_to_group(int(payment["order_id"]))
            except Exception:
                logger.exception("Dispatch after payment approval failed")
    try:
        if payment:
            await bot.send_message(int(payment["user_id"]), f"âœ… طھظ… ظ‚ط¨ظˆظ„ ط¯ظپط¹طھظƒ <code>{esc(payment['payment_no'])}</code> ط¨ظ…ط¨ظ„ط؛ {money(int(payment['amount']))}.")
    except Exception:
        logger.exception("Payment approval notification failed")


@dp.callback_query(F.data.startswith("adm:deny:"))
async def admin_deny_payment(callback: types.CallbackQuery):
    if not await require_staff_callback(callback):
        return
    pid = int(callback.data.split(":")[-1])
    payment_before = await get_payment(pid)
    if not payment_before or not await require_payment_access(callback.from_user.id, payment_before):
        await callback.answer("â›” ظ„ط§ طھظ…ظ„ظƒ طµظ„ط§ط­ظٹط© ظ‡ط°ط§ ط§ظ„ظ‚ط³ظ….", show_alert=True)
        return
    ok, status, payment = await review_payment(pid, callback.from_user.id, False)
    if not ok:
        await callback.answer("ط§ظ„ط¯ظپط¹ط© طھظ…طھ ظ…ط±ط§ط¬ط¹طھظ‡ط§ ظ…ط³ط¨ظ‚ط§ظ‹ ط£ظˆ ط؛ظٹط± ظ…ظˆط¬ظˆط¯ط©.", show_alert=True)
        return
    await callback.answer("طھظ… ط±ظپط¶ ط§ظ„ط¯ظپط¹ط©.")
    await callback.message.edit_text("â‌Œ طھظ… ط±ظپط¶ ط§ظ„ط¯ظپط¹ط© ظˆطھط³ط¬ظٹظ„ ط§ظ„ظ‚ط±ط§ط±.", reply_markup=admin_back_keyboard())
    try:
        if payment:
            await bot.send_message(int(payment["user_id"]), f"â‌Œ طھظ… ط±ظپط¶ ط¯ظپط¹طھظƒ <code>{esc(payment['payment_no'])}</code>. طھظˆط§طµظ„ ظ…ط¹ ط§ظ„ط¯ط¹ظ… ط¥ط°ط§ ظƒط§ظ† ظ„ط¯ظٹظƒ ط¥ط«ط¨ط§طھ طھط­ظˆظٹظ„.")
    except Exception:
        logger.exception("Payment denial notification failed")


@dp.callback_query(F.data == "adm:users")
async def admin_users(callback: types.CallbackQuery, state: FSMContext):
    if not await require_staff_callback(callback):
        return
    await state.set_state(AdminState.search_user)
    await callback.message.edit_text(
        "ًں‘¥ <b>ط¨ط­ط« ط¹ظ† ظ…ط³طھط®ط¯ظ…</b>\n\nط£ط±ط³ظ„ Telegram ID ط£ظˆ @username ظ„ظ„ط¨ط­ط«.",
        reply_markup=admin_back_keyboard(),
    )


@dp.message(AdminState.search_user)
async def admin_search_user(message: types.Message, state: FSMContext):
    if not await is_staff(message.from_user.id):
        return
    query = message.text.strip()
    async with await db_connect() as db:
        if query.startswith("@"): query = query[1:]
        if query.isdigit():
            rows = await fetchall(db, "SELECT * FROM users WHERE user_id=?", (int(query),))
        else:
            rows = await fetchall(db, "SELECT * FROM users WHERE username LIKE ? LIMIT 10", (query,))
    if not rows:
        await message.answer("â‌Œ ظ„ظ… ظٹطھظ… ط§ظ„ط¹ط«ظˆط± ط¹ظ„ظ‰ ط§ظ„ظ…ط³طھط®ط¯ظ….", reply_markup=admin_back_keyboard())
        return
    buttons = []
    text = "ًں‘¥ <b>ظ†طھط§ط¦ط¬ ط§ظ„ط¨ط­ط«</b>\nâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
    for row in rows:
        text += f"<code>{row['user_id']}</code> â€” @{esc(row['username'] or 'ط¨ط¯ظˆظ†')} â€” {money(int(row['balance']))}\n"
        buttons.append([InlineKeyboardButton(text=f"ًں‘¤ {row['user_id']}", callback_data=f"adm:user:{row['user_id']}")])
    buttons.append([InlineKeyboardButton(text="ًں”™ ظ„ظˆط­ط© ط§ظ„ط¥ط¯ط§ط±ط©", callback_data="adm:home")])
    await state.clear()
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@dp.callback_query(F.data.startswith("adm:user:"))
async def admin_user_detail(callback: types.CallbackQuery):
    if not await require_staff_callback(callback):
        return
    uid = int(callback.data.split(":")[-1])
    user = await get_user(uid)
    if not user:
        await callback.answer("ط§ظ„ظ…ط³طھط®ط¯ظ… ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", show_alert=True)
        return
    text = (
        "ًں‘¤ <b>ظ…ظ„ظپ ط§ظ„ظ…ط³طھط®ط¯ظ…</b>\nâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
        f"ًں†” ID: <code>{user['user_id']}</code>\n"
        f"ًں‘¤ ط§ظ„ط§ط³ظ…: {esc(user['first_name'])}\n"
        f"ًں”— ط§ظ„ظٹظˆط²ط±: @{esc(user['username'] or 'ط¨ط¯ظˆظ†')}\n"
        f"ًں’° ط§ظ„ط±طµظٹط¯: <b>{money(int(user['balance']))}</b>\n"
        f"ًںŒں VIP: {'ظ†ط¹ظ…' if int(user['is_vip']) else 'ظ„ط§'}\n"
        f"ًںڑ« ط§ظ„ط­ط§ظ„ط©: {'ظ…ط­ط¸ظˆط±' if int(user['is_blocked']) else 'ظپط¹ط§ظ„'}"
    )
    buttons = [
        [InlineKeyboardButton(text="ًں’° طھط¹ط¯ظٹظ„ ط§ظ„ط±طµظٹط¯", callback_data=f"adm:balance_user:{uid}")],
        [InlineKeyboardButton(text="ًںڑ« ط­ط¸ط±" if not int(user['is_blocked']) else "âœ… ظپظƒ ط§ظ„ط­ط¸ط±", callback_data=f"adm:block:{uid}")],
        [InlineKeyboardButton(text="ًں”™ ط§ظ„ظ…ط³طھط®ط¯ظ…ظˆظ†", callback_data="adm:users")],
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@dp.callback_query(F.data.startswith("adm:block:"))
async def admin_block_user(callback: types.CallbackQuery):
    if not await require_owner_callback(callback):
        return
    uid = int(callback.data.split(":")[-1])
    if uid == ADMIN_ID:
        await callback.answer("ظ„ط§ ظٹظ…ظƒظ† ط­ط¸ط± ط§ظ„ظ…ط¯ظٹط± ط§ظ„ط±ط¦ظٹط³ظٹ.", show_alert=True)
        return
    user = await get_user(uid)
    if not user:
        await callback.answer("ط§ظ„ظ…ط³طھط®ط¯ظ… ط؛ظٹط± ظ…ظˆط¬ظˆط¯.", show_alert=True)
        return
    new_value = not bool(int(user["is_blocked"]))
    await set_blocked(uid, new_value)
    await callback.answer("طھظ… طھط­ط¯ظٹط« ط­ط§ظ„ط© ط§ظ„ظ…ط³طھط®ط¯ظ….")
    fresh = await get_user(uid)
    await callback.message.edit_text(
        "ًں‘¤ <b>ظ…ظ„ظپ ط§ظ„ظ…ط³طھط®ط¯ظ…</b>\nâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
        f"ًں†” ID: <code>{fresh['user_id']}</code>\n"
        f"ًں’° ط§ظ„ط±طµظٹط¯: <b>{money(int(fresh['balance']))}</b>\n"
        f"ًںڑ« ط§ظ„ط­ط§ظ„ط©: {'ظ…ط­ط¸ظˆط±' if int(fresh['is_blocked']) else 'ظپط¹ط§ظ„'}",
        reply_markup=admin_back_keyboard(),
    )


@dp.callback_query(F.data == "adm:balance")
async def admin_balance(callback: types.CallbackQuery, state: FSMContext):
    if not await require_owner_callback(callback):
        return
    await state.set_state(AdminState.balance_user_id)
    await callback.message.edit_text("ًں’° ط£ط±ط³ظ„ Telegram ID ظ„ظ„ظ…ط³طھط®ط¯ظ… ط§ظ„ط°ظٹ طھط±ظٹط¯ طھط¹ط¯ظٹظ„ ط±طµظٹط¯ظ‡.", reply_markup=admin_back_keyboard())


@dp.callback_query(F.data.startswith("adm:balance_user:"))
async def admin_balance_from_user(callback: types.CallbackQuery, state: FSMContext):
    if not await require_owner_callback(callback):
        return
    uid = int(callback.data.split(":")[-1])
    await state.update_data(balance_user_id=uid)
    await state.set_state(AdminState.balance_amount)
    await callback.message.edit_text(
        f"ًں’° ط§ظ„ظ…ط³طھط®ط¯ظ…: <code>{uid}</code>\nط£ط±ط³ظ„ ط§ظ„ظ…ط¨ظ„ط؛:\nط§ط³طھط®ط¯ظ… ط±ظ‚ظ… ظ…ظˆط¬ط¨ ظ„ظ„ط¥ط¶ط§ظپط© ط£ظˆ ط³ط§ظ„ط¨ ظ„ظ„ط®طµظ….\nظ…ط«ط§ظ„: <code>50000</code> ط£ظˆ <code>-10000</code>",
        reply_markup=admin_back_keyboard(),
    )


@dp.message(AdminState.balance_user_id)
async def admin_balance_user_id(message: types.Message, state: FSMContext):
    if not await is_owner(message.from_user.id): return
    if not message.text or not message.text.strip().lstrip("-").isdigit():
        await message.answer("â‌Œ ط£ط±ط³ظ„ Telegram ID طµط­ظٹط­ط§ظ‹.")
        return
    await state.update_data(balance_user_id=int(message.text.strip()))
    await state.set_state(AdminState.balance_amount)
    await message.answer("ط£ط±ط³ظ„ ط§ظ„ظ…ط¨ظ„ط؛. ظ…ظˆط¬ط¨ ظ„ظ„ط¥ط¶ط§ظپط© ظˆط³ط§ظ„ط¨ ظ„ظ„ط®طµظ….")


@dp.message(AdminState.balance_amount)
async def admin_balance_amount(message: types.Message, state: FSMContext):
    if not await is_owner(message.from_user.id): return
    raw = message.text.strip().replace(",", "")
    if not raw.lstrip("-").isdigit() or int(raw) == 0:
        await message.answer("â‌Œ ط£ط±ط³ظ„ ظ…ط¨ظ„ط؛ط§ظ‹ طµط­ظٹط­ط§ظ‹ ط؛ظٹط± طµظپط±ظٹ.")
        return
    amount = int(raw)
    data = await state.get_data()
    uid = int(data["balance_user_id"])
    user = await get_user(uid)
    if not user:
        await message.answer("â‌Œ ط§ظ„ظ…ط³طھط®ط¯ظ… ط؛ظٹط± ظ…ظˆط¬ظˆط¯.")
        await state.clear()
        return
    if amount > 0:
        ok = await wallet_credit(uid, amount, "admin_credit", "طھط¹ط¯ظٹظ„ ظٹط¯ظˆظٹ ظ…ظ† ط§ظ„ظ…ط¯ظٹط±")
    else:
        ok = await wallet_debit(uid, abs(amount), "admin_debit", "ط®طµظ… ظٹط¯ظˆظٹ ظ…ظ† ط§ظ„ظ…ط¯ظٹط±")
    await state.clear()
    await message.answer("âœ… طھظ… طھط¹ط¯ظٹظ„ ط§ظ„ط±طµظٹط¯." if ok else "â‌Œ طھط¹ط°ط± طھط¹ط¯ظٹظ„ ط§ظ„ط±طµظٹط¯.", reply_markup=admin_main_keyboard())
    try:
        if ok:
            await bot.send_message(uid, f"ًں’° طھظ… طھط­ط¯ظٹط« ط±طµظٹط¯ ظ…ط­ظپط¸طھظƒ ظ…ظ† ط§ظ„ط¥ط¯ط§ط±ط©. ط§ظ„ط±طµظٹط¯ ط§ظ„ط­ط§ظ„ظٹ: {money(await get_balance(uid))}")
    except Exception:
        logger.exception("Balance notification failed")


async def get_balance(user_id: int) -> int:
    user = await get_user(user_id)
    return int(user["balance"]) if user else 0


@dp.callback_query(F.data == "adm:settings")
async def admin_settings(callback: types.CallbackQuery):
    if not await require_owner_callback(callback):
        return
    dollar = await get_setting("dollar_rate", "150")
    wa = await get_setting("num_whatsapp", "400")
    tg = await get_setting("num_telegram", "300")
    text = (
        "ًں’µ <b>ط§ظ„ط¥ط¹ط¯ط§ط¯ط§طھ ظˆط§ظ„ط£ط³ط¹ط§ط±</b>\nâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
        f"ًں’± ط³ط¹ط± ط§ظ„ط¯ظˆظ„ط§ط±: <code>{esc(dollar)}</code>\n"
        f"ًں“± ط³ط¹ط± ط±ظ‚ظ… WhatsApp: <code>{esc(wa)}</code>\n"
        f"âœˆï¸ڈ ط³ط¹ط± ط±ظ‚ظ… Telegram: <code>{esc(tg)}</code>"
    )
    buttons = [
        [InlineKeyboardButton(text="ًں’± طھط¹ط¯ظٹظ„ ط³ط¹ط± ط§ظ„ط¯ظˆظ„ط§ط±", callback_data="adm:set:dollar_rate")],
        [InlineKeyboardButton(text="ًں“± طھط¹ط¯ظٹظ„ WhatsApp", callback_data="adm:set:num_whatsapp")],
        [InlineKeyboardButton(text="âœˆï¸ڈ طھط¹ط¯ظٹظ„ Telegram", callback_data="adm:set:num_telegram")],
        [InlineKeyboardButton(text="ًں”™ ظ„ظˆط­ط© ط§ظ„ط¥ط¯ط§ط±ط©", callback_data="adm:home")],
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@dp.callback_query(F.data.startswith("adm:set:"))
async def admin_setting_start(callback: types.CallbackQuery, state: FSMContext):
    if not await require_owner_callback(callback): return
    key = callback.data.split(":", 2)[2]
    await state.update_data(setting_key=key)
    await state.set_state(AdminState.set_setting)
    await callback.message.edit_text(f"âœڈï¸ڈ ط£ط±ط³ظ„ ط§ظ„ظ‚ظٹظ…ط© ط§ظ„ط¬ط¯ظٹط¯ط© ظ„ظ„ط¥ط¹ط¯ط§ط¯: <code>{esc(key)}</code>", reply_markup=admin_back_keyboard())


@dp.message(AdminState.set_setting)
async def admin_setting_save(message: types.Message, state: FSMContext):
    if not await is_owner(message.from_user.id): return
    value = message.text.strip().replace(",", "")
    if not value or len(value) > 30:
        await message.answer("â‌Œ ظ‚ظٹظ…ط© ط؛ظٹط± طµط§ظ„ط­ط©.")
        return
    data = await state.get_data()
    await set_setting(data["setting_key"], value)
    await state.clear()
    await message.answer("âœ… طھظ… ط­ظپط¸ ط§ظ„ط¥ط¹ط¯ط§ط¯.", reply_markup=admin_main_keyboard())


@dp.callback_query(F.data == "adm:staff")
async def admin_staff(callback: types.CallbackQuery):
    if not await require_owner_callback(callback): return
    rows = await get_staff()
    text = "ًں‘¨â€چًں’¼ <b>ط§ظ„ظ…ظˆط¸ظپظˆظ†</b>\nâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
    for row in rows:
        text += f"<code>{row['user_id']}</code> â€” {esc(row['role'])} â€” {'ظپط¹ط§ظ„' if row['active'] else 'ظ…طھظˆظ‚ظپ'}\n"
    buttons = [
        [InlineKeyboardButton(text="â‍• ط¥ط¶ط§ظپط© ظ…ظˆط¸ظپ", callback_data="adm:staff:add")],
        [InlineKeyboardButton(text="â‍– طھط¹ط·ظٹظ„ ظ…ظˆط¸ظپ", callback_data="adm:staff:remove")],
        [InlineKeyboardButton(text="ًں”™ ظ„ظˆط­ط© ط§ظ„ط¥ط¯ط§ط±ط©", callback_data="adm:home")],
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@dp.callback_query(F.data == "adm:staff:add")
async def admin_staff_add_start(callback: types.CallbackQuery, state: FSMContext):
    if not await require_owner_callback(callback): return
    await state.set_state(AdminState.add_staff_id)
    await callback.message.edit_text("â‍• ط£ط±ط³ظ„ Telegram ID ظ„ظ„ظ…ظˆط¸ظپ.", reply_markup=admin_back_keyboard())


@dp.message(AdminState.add_staff_id)
async def admin_staff_add_id(message: types.Message, state: FSMContext):
    if not await is_owner(message.from_user.id): return
    if not message.text or not message.text.isdigit():
        await message.answer("â‌Œ ط£ط±ط³ظ„ Telegram ID طµط­ظٹط­ط§ظ‹.")
        return
    await state.update_data(staff_id=int(message.text))
    await state.set_state(AdminState.add_staff_role)
    await message.answer("ط£ط±ط³ظ„ ط§ط³ظ… ط§ظ„طµظ„ط§ط­ظٹط©طŒ ظ…ط«ظ„ط§ظ‹: <code>games</code> ط£ظˆ <code>balance</code> ط£ظˆ <code>staff</code>.")


@dp.message(AdminState.add_staff_role)
async def admin_staff_add_role(message: types.Message, state: FSMContext):
    if not await is_owner(message.from_user.id): return
    role = message.text.strip().lower()
    allowed = {"staff", "wallet", "balance", "games", "accounts", "social", "support"}
    if role not in allowed:
        await message.answer("â‌Œ طµظ„ط§ط­ظٹط© ط؛ظٹط± طµط­ظٹط­ط©. ط§ط®طھط±: staff / wallet / balance / games / accounts / social / support")
        return
    data = await state.get_data()
    await add_staff(int(data["staff_id"]), role, message.from_user.id)
    await state.clear()
    await message.answer("âœ… طھظ…طھ ط¥ط¶ط§ظپط© ط§ظ„ظ…ظˆط¸ظپ.", reply_markup=admin_main_keyboard())


@dp.callback_query(F.data == "adm:staff:remove")
async def admin_staff_remove_start(callback: types.CallbackQuery, state: FSMContext):
    if not await require_owner_callback(callback): return
    await state.set_state(AdminState.block_user_id)
    await callback.message.edit_text("â‍– ط£ط±ط³ظ„ Telegram ID ظ„ظ„ظ…ظˆط¸ظپ ط§ظ„ط°ظٹ طھط±ظٹط¯ طھط¹ط·ظٹظ„ظ‡.", reply_markup=admin_back_keyboard())


@dp.message(AdminState.block_user_id)
async def admin_staff_remove(message: types.Message, state: FSMContext):
    if not await is_owner(message.from_user.id): return
    if not message.text or not message.text.isdigit():
        await message.answer("â‌Œ ط£ط±ط³ظ„ Telegram ID طµط­ظٹط­ط§ظ‹.")
        return
    uid = int(message.text)
    await remove_staff(uid)
    await state.clear()
    await message.answer("âœ… طھظ… طھط¹ط·ظٹظ„ ط§ظ„ظ…ظˆط¸ظپ.", reply_markup=admin_main_keyboard())


@dp.callback_query(F.data == "adm:groups")
async def admin_groups(callback: types.CallbackQuery):
    if not await require_staff_callback(callback): return
    text = "ًںڈ¢ <b>ظ…ط¬ظ…ظˆط¹ط§طھ ط§ظ„ط£ظ‚ط³ط§ظ… ط§ظ„ظ…ط±طھط¨ط·ط©</b>\nâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
    for key, group_id in GROUPS.items():
        text += f"â€¢ {esc(GROUP_NAMES.get(key,key))}: <code>{group_id}</code>\n"
    text += "\nظٹطھظ… ط±ط¨ط· ظƒظ„ ط·ظ„ط¨ ط¨ط§ظ„ظ…ط¬ظ…ظˆط¹ط© ط§ظ„ط®ط§طµط© ط¨ظ‚ط³ظ…ظ‡ ط¹ظ†ط¯ ط¥ظ†ط´ط§ط، ط§ظ„ط·ظ„ط¨."
    await callback.message.edit_text(text, reply_markup=admin_back_keyboard())


@dp.callback_query(F.data == "adm:logs")
async def admin_logs(callback: types.CallbackQuery):
    if not await require_owner_callback(callback): return
    async with await db_connect() as db:
        rows = await fetchall(db, "SELECT * FROM admin_actions ORDER BY id DESC LIMIT 20")
    text = "ًں“‹ <b>ط¢ط®ط± ط¹ظ…ظ„ظٹط§طھ ط§ظ„ط¥ط¯ط§ط±ط©</b>\nâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
    for row in rows:
        text += f"â€¢ <code>{row['admin_id']}</code> â€” {esc(row['action'])} â€” {esc(row['details'])}\n"
    await callback.message.edit_text(text, reply_markup=admin_back_keyboard())


@dp.callback_query(F.data == "adm:broadcast")
async def admin_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    if not await require_owner_callback(callback): return
    await state.set_state(AdminState.broadcast_text)
    await callback.message.edit_text("ًں“¢ ط£ط±ط³ظ„ ظ†طµ ط§ظ„ط¥ط¹ظ„ط§ظ† ط§ظ„ط°ظٹ طھط±ظٹط¯ ط¥ط±ط³ط§ظ„ظ‡ ظ„ظ„ظ…ط³طھط®ط¯ظ…ظٹظ†.", reply_markup=admin_back_keyboard())


@dp.message(AdminState.broadcast_text)
async def admin_broadcast_send(message: types.Message, state: FSMContext):
    if not await is_owner(message.from_user.id): return
    text = message.text or ""
    if not text.strip():
        await message.answer("â‌Œ ط§ظ„ط¥ط¹ظ„ط§ظ† ظپط§ط±ط؛.")
        return
    async with await db_connect() as db:
        rows = await fetchall(db, "SELECT user_id FROM users WHERE is_blocked=0")
    sent = 0
    failed = 0
    for row in rows:
        try:
            await bot.send_message(int(row["user_id"]), text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await state.clear()
    await message.answer(f"ًں“¢ ط§ظ†طھظ‡ظ‰ ط§ظ„ط¥ط±ط³ط§ظ„.\nâœ… ظ†ط¬ط­: {sent}\nâ‌Œ ظپط´ظ„: {failed}", reply_markup=admin_main_keyboard())


# ============================================================
# Example order/payment API for service modules
# ============================================================

async def create_service_order(user_id: int, section: str, service: str, target: str, price: int, quantity=""):
    return await create_order(user_id, section, service, target, quantity, price)


async def show_payment_options(message: types.Message, order_id: int):
    order = await get_order(order_id)
    if not order or int(order["user_id"]) != message.from_user.id:
        await message.answer("â‌Œ ط§ظ„ط·ظ„ط¨ ط؛ظٹط± طµط§ظ„ط­.")
        return
    price = int(order["price"] or 0)
    buttons = []
    if await get_balance(message.from_user.id) >= price:
        buttons.append([InlineKeyboardButton(text=f"âڑ، ط§ظ„ط¯ظپط¹ ظ…ظ† ط§ظ„ظ…ط­ظپط¸ط© â€” {money(price)}", callback_data=f"pay_wallet:{order_id}")])
    buttons.append([InlineKeyboardButton(text="ًں’³ ط§ظ„ط¯ظپط¹ ط¹ط¨ط± ط´ط§ظ… ظƒط§ط´", callback_data=f"pay_sham:{order_id}")])
    buttons.append([InlineKeyboardButton(text="â‌Œ ط¥ظ„ط؛ط§ط، ط§ظ„ط·ظ„ط¨", callback_data=f"cancel_order:{order_id}")])
    await message.answer(
        f"ًں§¾ <b>ط§ظ„ط·ظ„ط¨:</b> <code>{esc(order['order_no'])}</code>\n"
        f"ًں“¦ <b>ط§ظ„ط®ط¯ظ…ط©:</b> {esc(order['service'])}\n"
        f"ًں’° <b>ط§ظ„ظ…ط¨ظ„ط؛:</b> {money(price)}\n\nط§ط®طھط± ط·ط±ظٹظ‚ط© ط§ظ„ط¯ظپط¹:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@dp.callback_query(F.data.startswith("pay_wallet:"))
async def pay_wallet_handler(callback: types.CallbackQuery):
    order_id = int(callback.data.split(":")[-1])
    order = await get_order(order_id)
    if not order or int(order["user_id"]) != callback.from_user.id or order["status"] != "pending_payment":
        await callback.answer("â‌Œ ط§ظ„ط·ظ„ط¨ ط؛ظٹط± طµط§ظ„ط­ ط£ظˆ طھظ… ط§ظ„طھط¹ط§ظ…ظ„ ظ…ط¹ظ‡.", show_alert=True)
        return
    price = int(order["price"] or 0)
    if not await wallet_debit(callback.from_user.id, price, "order_payment", f"ط¯ظپط¹ ط§ظ„ط·ظ„ط¨ {order['order_no']}", order_id):
        await callback.answer("â‌Œ ط±طµظٹط¯ ط§ظ„ظ…ط­ظپط¸ط© ط؛ظٹط± ظƒط§ظپظچ.", show_alert=True)
        return
    await set_order_status(order_id, "paid", "wallet")
    await callback.answer("âœ… طھظ… ط§ظ„ط¯ظپط¹ ظ…ظ† ط§ظ„ظ…ط­ظپط¸ط©.")
    await dispatch_order_to_group(order_id)
    await callback.message.edit_text(f"âœ… طھظ… ط¯ظپط¹ ط§ظ„ط·ظ„ط¨ <code>{esc(order['order_no'])}</code> ظ…ظ† ط§ظ„ظ…ط­ظپط¸ط© ظˆط¥ط±ط³ط§ظ„ظ‡ ظ„ظ„ط¥ط¯ط§ط±ط©.")


@dp.callback_query(F.data.startswith("pay_sham:"))
async def pay_sham_handler(callback: types.CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[-1])
    order = await get_order(order_id)
    if not order or int(order["user_id"]) != callback.from_user.id or order["status"] != "pending_payment":
        await callback.answer("â‌Œ ط§ظ„ط·ظ„ط¨ ط؛ظٹط± طµط§ظ„ط­ ط£ظˆ طھظ… ط§ظ„طھط¹ط§ظ…ظ„ ظ…ط¹ظ‡.", show_alert=True)
        return
    await state.update_data(payment_order_id=order_id)
    await callback.message.edit_text(
        f"ًں’³ <b>ط§ظ„ط¯ظپط¹ ط¹ط¨ط± ط´ط§ظ… ظƒط§ط´</b>\n\n"
        f"ًں‘¤ ط§ظ„ط§ط³ظ…: <code>{esc(SHAM_NAME)}</code>\n"
        f"ًں”— ط§ظ„ط¹ظ†ظˆط§ظ†: <code>{esc(SHAM_ADDR)}</code>\n"
        f"ًں’° ط§ظ„ظ…ط¨ظ„ط؛: <b>{money(int(order['price']))}</b>\n\n"
        "ط¨ط¹ط¯ ط§ظ„طھط­ظˆظٹظ„ ط£ط±ط³ظ„ ط±ظ‚ظ… ط¹ظ…ظ„ظٹط© ط§ظ„طھط­ظˆظٹظ„ ظپظٹ ط±ط³ط§ظ„ط© ظˆط§ط­ط¯ط©."
    )
    await state.set_state(PaymentState.reference)


class PaymentState(StatesGroup):
    reference = State()


@dp.message(PaymentState.reference)
async def sham_reference_received(message: types.Message, state: FSMContext):
    if not message.text or len(message.text.strip()) > 100:
        await message.answer("â‌Œ ط£ط±ط³ظ„ ط±ظ‚ظ… ط¹ظ…ظ„ظٹط© ط§ظ„طھط­ظˆظٹظ„ ظپظ‚ط·.")
        return
    data = await state.get_data()
    order_id = int(data["payment_order_id"])
    order = await get_order(order_id)
    if not order or int(order["user_id"]) != message.from_user.id or order["status"] != "pending_payment":
        await state.clear()
        await message.answer("â‌Œ ط§ظ„ط·ظ„ط¨ ط؛ظٹط± طµط§ظ„ط­ ط£ظˆ طھظ… ط§ظ„طھط¹ط§ظ…ظ„ ظ…ط¹ظ‡ ظ…ط³ط¨ظ‚ط§ظ‹.")
        return
    try:
        payment_id, payment_no = await create_payment(
            message.from_user.id,
            order_id,
            int(order["price"]),
            "sham_cash",
            reference=message.text.strip(),
        )
        await state.clear()
        group_id = int(order["admin_group_id"] or GROUPS["wallet"])
        admin_message = await bot.send_message(
            group_id,
            "ًں’³ <b>ط·ظ„ط¨ ط¯ظپط¹ ط¬ط¯ظٹط¯ ط¨ط§ظ†طھط¸ط§ط± ط§ظ„ظ…ط±ط§ط¬ط¹ط©</b>\nâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
            f"ًں§¾ ط§ظ„ط¯ظپط¹: <code>{esc(payment_no)}</code>\n"
            f"ًں“¦ ط§ظ„ط·ظ„ط¨: <code>{esc(order['order_no'])}</code>\n"
            f"ًں‘¤ ط§ظ„ظ…ط³طھط®ط¯ظ…: <code>{message.from_user.id}</code>\n"
            f"ًں’° ط§ظ„ظ…ط¨ظ„ط؛: <b>{money(int(order['price']))}</b>\n"
            f"ًں”¢ ط±ظ‚ظ… ط§ظ„ط¹ظ…ظ„ظٹط©: <code>{esc(message.text.strip())}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="âœ… ظ‚ط¨ظˆظ„ ط§ظ„ط¯ظپط¹", callback_data=f"adm:approve:{payment_id}"), InlineKeyboardButton(text="â‌Œ ط±ظپط¶ ط§ظ„ط¯ظپط¹", callback_data=f"adm:deny:{payment_id}")]
            ]),
        )
        await attach_admin_message(order_id, group_id, admin_message.message_id)
        await message.answer(f"âœ… طھظ… ط¥ط±ط³ط§ظ„ ط§ظ„ط¯ظپط¹ط© ظ„ظ„ظ…ط±ط§ط¬ط¹ط©. ط±ظ‚ظ… ط§ظ„ط¯ظپط¹: <code>{esc(payment_no)}</code>")
    except Exception:
        logger.exception("Creating manual payment failed")
        await state.clear()
        await message.answer("â‌Œ ط­ط¯ط« ط®ط·ط£ ط£ط«ظ†ط§ط، طھط³ط¬ظٹظ„ ط§ظ„ط¯ظپط¹. ظ„ظ… ظٹطھظ… ط§ط¹طھظ…ط§ط¯ ط§ظ„ط·ظ„ط¨.")


@dp.callback_query(F.data.startswith("cancel_order:"))
async def cancel_order_handler(callback: types.CallbackQuery):
    order_id = int(callback.data.split(":")[-1])
    ok = await cancel_order(order_id, callback.from_user.id)
    if not ok:
        await callback.answer("ظ„ط§ ظٹظ…ظƒظ† ط¥ظ„ط؛ط§ط، ط§ظ„ط·ظ„ط¨ ط¨ظ‡ط°ظ‡ ط§ظ„ط­ط§ظ„ط©.", show_alert=True)
        return
    await callback.answer("طھظ… ط¥ظ„ط؛ط§ط، ط§ظ„ط·ظ„ط¨.")
    await callback.message.edit_text("â‌Œ طھظ… ط¥ظ„ط؛ط§ط، ط§ظ„ط·ظ„ط¨.")


async def dispatch_order_to_group(order_id: int):
    order = await get_order(order_id)
    if not order:
        return False
    group_id = int(order["admin_group_id"] or 0)
    if not group_id:
        return False
    text = (
        "ًں“¦ <b>ط·ظ„ط¨ ظ…ط¯ظپظˆط¹ ط¬ط¯ظٹط¯</b>\nâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پâ”پ\n"
        f"ًں†” <code>{esc(order['order_no'])}</code>\n"
        f"ًں‘¤ ط§ظ„ظ…ط³طھط®ط¯ظ…: <code>{order['user_id']}</code>\n"
        f"ًںڈ· ط§ظ„ظ‚ط³ظ…: {esc(order['section'])}\n"
        f"ًں›چ ط§ظ„ط®ط¯ظ…ط©: {esc(order['service'])}\n"
        f"ًںژ¯ ط§ظ„ظ‡ط¯ظپ: {esc(order['target'])}\n"
        f"ًں“¦ ط§ظ„ظƒظ…ظٹط©: {esc(order['quantity'])}\n"
        f"ًں’° ط§ظ„ط³ط¹ط±: <b>{money(int(order['price']))}</b>\n"
        f"ًں’³ ط§ظ„ط¯ظپط¹: {esc(order['payment_method'] or '')}\n"
        "ًں“Œ ط§ظ„ط­ط§ظ„ط©: <b>ظ…ط¯ظپظˆط¹ - ط¨ط§ظ†طھط¸ط§ط± ط§ظ„طھظ†ظپظٹط°</b>"
    )
    msg = await bot.send_message(group_id, text, reply_markup=await order_admin_keyboard(order))
    await attach_admin_message(order_id, group_id, msg.message_id)
    return True


# ============================================================
# Safety: block ordinary messages from reaching admin FSM handlers
# and startup
# ============================================================

@dp.message()
async def fallback_message(message: types.Message):
    user = await get_user(message.from_user.id)
    if user and int(user["is_blocked"]) == 1:
        return
    if await is_staff(message.from_user.id) and message.text == "ظ„ظˆط­ط© ط§ظ„ط¥ط¯ط§ط±ط©":
        await message.answer(await admin_panel_message(message.from_user.id), reply_markup=admin_main_keyboard())
        return
    await message.answer("ط§ط³طھط®ط¯ظ… /start ظ„ظ„ط¹ظˆط¯ط© ط¥ظ„ظ‰ ط§ظ„ظ‚ط§ط¦ظ…ط© ط§ظ„ط±ط¦ظٹط³ظٹط©.")


async def health_check():
    async with await db_connect() as db:
        await fetchone(db, "SELECT 1")
    await bot.get_me()


async def main():
    await init_db()
    await health_check()
    logger.info("Bot starting")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
