import asyncio
import html
import logging
import os
import random
import re
import string
import time
from typing import Optional, Tuple

import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# =====================================================================
# 1. الإعدادات والمتغيرات
# =====================================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8774564171:AAE_kxJM-yZ97f52_dTGwnKTLyfvsARM5Ik")
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
DB_PATH = "syria_store_v2.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

def get_db():
    return aiosqlite.connect(DB_PATH, timeout=30.0)

def generate_uid(prefix: str = "ORD") -> str:
    timestamp_part = hex(int(time.time()))[2:].upper()
    random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{timestamp_part}-{random_part}"

# =====================================================================
# 2. كتالوج البيانات والأسعار (نفس الأسعار الأصلية المعتمدة لديك)
# =====================================================================
GOVERNORATES = [
    "دمشق", "ريف دمشق", "حمص", "ريف حمص", "حماة", "ريف حماة",
    "طرطوس", "درعا", "اللاذقية", "ريف اللاذقية", "حلب", "القامشلي",
    "الرقة", "دير الزور", "البوكمال", "الحسكة", "السويداء", "القنيطرة",
    "إدلب", "جبلة", "القلمون"
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
    "ff": [("100 جوهرة", 1.0), ("210 جوهرة", 2.0), ("530 جوهرة", 5.0), ("1080 جوهرة", 10.0), ("2200 جوهرة", 20.0), ("5600 جوهرة", 50.0)],
    "jawaker": [("15,000 توكنز", 1.5), ("50,000 توكنز", 4.0), ("150,000 توكنز", 10.0), ("باشا (شهر)", 6.0)],
    "coc": [("500 جوهرة", 5.0), ("1200 جوهرة", 10.0), ("2500 جوهرة", 20.0), ("6500 جوهرة", 50.0), ("14000 جوهرة", 100.0)]
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
    "Crunchyroll Fan", "Mega Cloud", "Google One"
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

# =====================================================================
# 3. إدارة قاعدة البيانات
# =====================================================================
async def init_db():
    async with get_db() as db:
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute("PRAGMA synchronous = NORMAL;")
        await db.execute("PRAGMA foreign_keys = ON;")

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
        );
        """)

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
        );
        """)

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
        );
        """)

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
        );
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            val REAL
        );
        """)
        await db.execute("INSERT OR IGNORE INTO settings (key, val) VALUES ('dollar_rate', 150.0);")
        await db.execute("INSERT OR IGNORE INTO settings (key, val) VALUES ('num_whatsapp', 400.0);")
        await db.execute("INSERT OR IGNORE INTO settings (key, val) VALUES ('num_telegram', 300.0);")

        await db.execute(
            "INSERT INTO users (user_id, username, full_name, role) VALUES (?, 'Admin', 'Admin', 'ADMIN') "
            "ON CONFLICT(user_id) DO UPDATE SET role = 'ADMIN';",
            (ADMIN_ID,)
        )
        await db.commit()

async def get_setting(key: str) -> float:
    async with get_db() as db:
        cursor = await db.execute("SELECT val FROM settings WHERE key=?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else 0.0

async def update_setting(key: str, val: float):
    async with get_db() as db:
        await db.execute("UPDATE settings SET val=? WHERE key=?", (val, key))
        await db.commit()

# =====================================================================
# 4. محرك المحفظة (الخصم والشحن الذري)
# =====================================================================
class WalletService:
    @staticmethod
    async def get_or_create_user(user_id: int, username: str = "", full_name: str = ""):
        async with get_db() as db:
            cursor = await db.execute("SELECT user_id, username, balance, is_vip, is_banned, role FROM users WHERE user_id=?", (user_id,))
            row = await cursor.fetchone()
            if not row:
                role = "ADMIN" if user_id == ADMIN_ID else "USER"
                await db.execute(
                    "INSERT INTO users (user_id, username, full_name, role) VALUES (?, ?, ?, ?)",
                    (user_id, username or "", full_name or "", role)
                )
                await db.commit()
                return (user_id, username, 0, 0, 0, role)
            return row

    @staticmethod
    async def deposit(user_id: int, amount: int, ref_id: str, note: str = "") -> bool:
        if amount <= 0:
            return False
        async with get_db() as db:
            await db.execute("BEGIN IMMEDIATE TRANSACTION;")
            try:
                await db.execute("UPDATE users SET balance = balance + ?, is_vip = 1 WHERE user_id = ?", (amount, user_id))
                cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
                new_bal = (await cursor.fetchone())[0]

                await db.execute(
                    "INSERT INTO wallet_ledger (user_id, reference_id, type, amount, balance_after, note) VALUES (?, ?, 'DEPOSIT', ?, ?, ?)",
                    (user_id, ref_id, amount, new_bal, note)
                )
                await db.commit()
                return True
            except Exception as e:
                await db.rollback()
                logging.error(f"Deposit error: {e}")
                return False

    @staticmethod
    async def deduct_for_order(user_id: int, order_id: str, amount: int, s_name: str) -> bool:
        if amount <= 0:
            return False
        async with get_db() as db:
            await db.execute("BEGIN IMMEDIATE TRANSACTION;")
            try:
                cursor = await db.execute(
                    "UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
                    (amount, user_id, amount)
                )
                if cursor.rowcount == 0:
                    await db.rollback()
                    return False

                cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
                new_bal = (await cursor.fetchone())[0]

                await db.execute(
                    "INSERT INTO wallet_ledger (user_id, reference_id, type, amount, balance_after, note) VALUES (?, ?, 'PURCHASE', ?, ?, ?)",
                    (user_id, order_id, -amount, new_bal, f"شراء: {s_name}")
                )
                await db.commit()
                return True
            except Exception as e:
                await db.rollback()
                logging.error(f"Deduct error: {e}")
                return False

    @staticmethod
    async def refund(order_id: str) -> Tuple[bool, int, int]:
        async with get_db() as db:
            await db.execute("BEGIN IMMEDIATE TRANSACTION;")
            try:
                cursor = await db.execute("SELECT user_id, price, status FROM orders WHERE order_id = ?", (order_id,))
                order = await cursor.fetchone()
                if not order or order[2] in ['REFUNDED', 'REJECTED']:
                    await db.rollback()
                    return False, 0, 0

                user_id, price = order[0], order[1]
                await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, user_id))
                cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
                new_bal = (await cursor.fetchone())[0]

                await db.execute(
                    "INSERT INTO wallet_ledger (user_id, reference_id, type, amount, balance_after, note) VALUES (?, ?, 'REFUND', ?, ?, 'استرجاع قيمة طلب')",
                    (user_id, order_id, price, new_bal)
                )
                await db.execute("UPDATE orders SET status = 'REFUNDED' WHERE order_id = ?", (order_id,))
                await db.commit()
                return True, user_id, price
            except Exception as e:
                await db.rollback()
                logging.error(f"Refund error: {e}")
                return False, 0, 0

# =====================================================================
# 5. الحالات ونماذج FSM
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
# 6. الواجهة العصرية الجديدة (Modern Single-Screen Dashboard)
# =====================================================================
def persistent_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 الرئيسية")]],
        resize_keyboard=True,
        persistent=True
    )

def main_dashboard_kb(user_balance: int):
    # ترتيب شبكي أنيق مع تمييز زر الشحن
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ شحن رصيد المحفظة (شام كاش)", callback_data="wallet:topup")],
        [
            InlineKeyboardButton(text="📞 الرصيد والكاش", callback_data="sec:balance"),
            InlineKeyboardButton(text="🎮 شحن الألعاب", callback_data="sec:games")
        ],
        [
            InlineKeyboardButton(text="💬 برامج الشات", callback_data="sec:chat"),
            InlineKeyboardButton(text="📦 الحسابات الرقمية", callback_data="sec:accounts")
        ],
        [
            InlineKeyboardButton(text="🚀 سوشيال ميديا", callback_data="sec:social"),
            InlineKeyboardButton(text="📱 أرقام التفعيل", callback_data="sec:numbers")
        ],
        [
            InlineKeyboardButton(text="💳 كشف المحفظة", callback_data="client:wallet_info"),
            InlineKeyboardButton(text="🛠 الدعم والشكاوى", callback_data="sec:support")
        ]
    ])

def format_home_text(u):
    rank = "🌟 المدير العام" if u[0] == ADMIN_ID else ("⭐ زبون دائم (VIP)" if u[3] == 1 else "👤 زبون عادي")
    bal = u[2]
    status_icon = "🟢 جاهز للشراء الفوري" if bal > 0 else "⚠️ يرجى شحن الرصيد أولاً"
    
    return (
        f"╭────────────────────────────╮\n"
        f"│   🛍 <b>SYRIA STORE | المتجر الإلكتروني</b>   │\n"
        f"╰────────────────────────────╯\n"
        f"👤 <b>الزبون:</b> {html.escape(u[1] or 'عزيزنا العميل')}\n"
        f"🎖 <b>الرتبة:</b> {rank}\n"
        f"🆔 <b>المعرف:</b> <code>{u[0]}</code>\n"
        f"💰 <b>رصيد المحفظة:</b> <b>{bal:,} ل.س</b> ({status_icon})\n"
        f"──────────────────────────────\n"
        f"💡 <i>النظام يعمل بالشحن المسبق: اشحن محفظتك مرة واحدة واشترِ بضغطة زر فوري بدون انتظار!</i>\n"
        f"──────────────────────────────\n"
        f"اختر الخدمة أو اشحن رصيدك للبدء 👇"
    )

@dp.message(CommandStart())
@dp.message(F.text == "🏠 الرئيسية")
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    u = await WalletService.get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    if u[4] == 1:
        await message.answer("⛔ حسابك محظور من استخدام البوت.")
        return

    await message.answer(format_home_text(u), reply_markup=main_dashboard_kb(u[2]))
    await message.answer("💡 زر القائمة متاح دائماً بالأسفل للعودة فوراً.", reply_markup=persistent_keyboard())

@dp.callback_query(F.data == "back_home")
async def back_to_home_cb(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    u = await WalletService.get_or_create_user(cb.from_user.id)
    await cb.message.edit_text(format_home_text(u), reply_markup=main_dashboard_kb(u[2]))

# =====================================================================
# 7. نظام الشحن المسبق للمحفظة (شام كاش)
# =====================================================================
@dp.callback_query(F.data == "client:wallet_info")
async def wallet_info_view(cb: types.CallbackQuery):
    u = await WalletService.get_or_create_user(cb.from_user.id)
    txt = (
        f"💳 <b>بيانات محفظتك الإلكترونية</b>\n"
        f"────────────────────────────\n"
        f"💰 الرصيد المتاح: <b>{u[2]:,} ل.س</b>\n"
        f"🆔 معرّف الحساب: <code>{u[0]}</code>\n\n"
        f"• يمكنك استخدام هذا الرصيد لشراء أي خدمة فورياً بضغطة زر دون الحاجة للتحويل في كل مرة."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ شحن رصيد إضافي", callback_data="wallet:topup")],
        [InlineKeyboardButton(text="🔙 العودة للرئيسية", callback_data="back_home")]
    ])
    await cb.message.edit_text(txt, reply_markup=kb)

@dp.callback_query(F.data == "wallet:topup")
async def wallet_topup_start(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(WalletFlow.amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 إلغاء", callback_data="back_home")]])
    await cb.message.edit_text(
        "💵 <b>شحن المحفظة الإلكترونية:</b>\n\n"
        "أدخل المبلغ الذي ترغب بإيداعه بالليرة السورية (أقل مبلغ 1,000 ل.س):",
        reply_markup=kb
    )

@dp.message(WalletFlow.amount)
async def wallet_amt_rec(message: types.Message, state: FSMContext):
    clean_txt = message.text.strip().replace(",", "")
    if not clean_txt.isdigit() or int(clean_txt) < 1000:
        await message.reply("⚠️ يرجى إدخال مبلغ صحيح بالأرقام (الحد الأدنى 1,000 ل.س):")
        return

    amt = int(clean_txt)
    await state.update_data(dep_amt=amt)
    await state.set_state(WalletFlow.tx_code)
    
    pay_text = (
        f"🧾 <b>طلب شحن رصيد بقيمة: {amt:,} ل.س</b>\n"
        f"────────────────────────────\n"
        f"👤 الاسم: <code>{html.escape(SHAM_NAME)}</code>\n"
        f"🔗 العنوان: <code>{html.escape(SHAM_ADDR)}</code>\n"
        f"────────────────────────────\n"
        f"⚠️ قم بالتحويل عبر شام كاش، ثم <b>أرسل رقم العملية (Transaction ID) هنا</b>:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 إلغاء", callback_data="back_home")]])
    if os.path.exists(QR_IMAGE_PATH):
        await message.answer_photo(FSInputFile(QR_IMAGE_PATH), caption=pay_text, reply_markup=kb)
    else:
        await message.answer(pay_text, reply_markup=kb)

@dp.message(WalletFlow.tx_code)
async def wallet_tx_rec(message: types.Message, state: FSMContext):
    tx_code = message.text.strip().upper()
    if len(tx_code) < 3:
        await message.reply("⚠️ يرجى إدخال رقم عملية صحيح:")
        return

    async with get_db() as db:
        cursor = await db.execute("SELECT payment_id FROM payments WHERE sham_tx_id = ?", (tx_code,))
        if await cursor.fetchone():
            await message.reply("⛔ رقم العملية هذا مستخدم مسبقاً! يرجى إدخال رقم صحيح:")
            return

    await state.update_data(sham_tx=tx_code)
    await state.set_state(WalletFlow.receipt)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 إلغاء", callback_data="back_home")]])
    await message.answer("📸 الآن أرسل صورة إشعار التحويل لتأكيد الشحن:", reply_markup=kb)

@dp.message(WalletFlow.receipt, F.photo)
async def wallet_receipt_rec(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amt = data.get("dep_amt", 0)
    tx_code = data.get("sham_tx", "")
    pay_id = generate_uid("PAY")

    async with get_db() as db:
        await db.execute(
            "INSERT INTO payments (payment_id, user_id, method, amount, sham_tx_id, receipt_file_id) VALUES (?, ?, 'SHAM_CASH', ?, ?, ?)",
            (pay_id, message.from_user.id, amt, tx_code, message.photo[-1].file_id)
        )
        await db.commit()

    u_info = f"@{html.escape(message.from_user.username)}" if message.from_user.username else "بدون"
    text_to_group = (
        f"💳 <b>طلب إيداع جديد قيد التدقيق المالي:</b>\n"
        f"🆔 رقم الدفعة: <code>{pay_id}</code>\n"
        f"👤 الزبون: {u_info} (<code>{message.from_user.id}</code>)\n"
        f"💰 المبلغ المطلوب: <b>{amt:,} ل.س</b>\n"
        f"🧾 رقم العملية: <code>{html.escape(tx_code)}</code>\n"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ قبول وتغذية الرصيد", callback_data=f"adm_pay:ok:{pay_id}"),
            InlineKeyboardButton(text="❌ رفض الإيداع", callback_data=f"adm_pay:no:{pay_id}")
        ]
    ])
    await bot.send_photo(GROUPS["wallet"], photo=message.photo[-1].file_id, caption=text_to_group, reply_markup=kb)
    await state.clear()
    await message.answer("✅ تم إرسال إشعار الإيداع للإدارة بنجاح! سيتم إشعارك وشحن محفظتك فوراً بعد التأكيد.")

# =====================================================================
# 8. محرك الشراء الذاتي الموحد (Wallet-First Purchase Engine)
# =====================================================================
async def process_wallet_purchase(cb_or_msg, user_id: int, dept: str, service: str, target: str, price: int, state: FSMContext):
    await state.clear()
    u = await WalletService.get_or_create_user(user_id)
    current_balance = u[2]

    # إذا كان الرصيد غير كافٍ، تظهر بطاقة تنبيهية مع توجيه فوري للشحن
    if current_balance < price:
        diff = price - current_balance
        text_no_bal = (
            f"❌ <b>رصيدك غير كافٍ لإتمام الشراء!</b>\n"
            f"────────────────────────────\n"
            f"📦 الخدمة: <b>{html.escape(service)}</b>\n"
            f"💵 السعر المطلوب: <b>{price:,} ل.س</b>\n"
            f"💰 رصيدك الحالي: <b>{current_balance:,} ل.س</b>\n"
            f"⚠️ ينقصك: <b>{diff:,} ل.س</b>\n"
            f"────────────────────────────\n"
            f"💡 يرجى شحن محفظتك أولاً لتتمكن من الشراء بضغطة زر واحدة."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"➕ شحن المحفظة الآن", callback_data="wallet:topup")],
            [InlineKeyboardButton(text="🔙 العودة للرئيسية", callback_data="back_home")]
        ])
        if isinstance(cb_or_msg, types.CallbackQuery):
            await cb_or_msg.message.edit_text(text_no_bal, reply_markup=kb)
        else:
            await cb_or_msg.answer(text_no_bal, reply_markup=kb)
        return

    # إذا كان الرصيد كافياً: خصم فوري وإنشاء الطلب وتوجيهه
    ord_id = generate_uid("ORD")
    deduct_ok = await WalletService.deduct_for_order(user_id, ord_id, price, service)
    if not deduct_ok:
        err_txt = "⚠️ حدث خطأ أثناء خصم الرصيد، يرجى المحاولة لاحقاً."
        if isinstance(cb_or_msg, types.CallbackQuery):
            await cb_or_msg.answer(err_txt, show_alert=True)
        else:
            await cb_or_msg.reply(err_txt)
        return

    # تسجيل الطلب كـ PROCESSING وتوجيهه فوراً للمجموعة
    async with get_db() as db:
        await db.execute(
            "INSERT INTO orders (order_id, user_id, department, service_name, target_data, price, status) VALUES (?, ?, ?, ?, ?, ?, 'PROCESSING')",
            (ord_id, user_id, dept, service, target, price)
        )
        await db.commit()

    group_id = GROUPS.get(dept, GROUPS["balance"])
    user_name = cb_or_msg.from_user.username
    u_info = f"@{html.escape(user_name)}" if user_name else "بدون"

    group_card = (
        f"⚡ <b>طلب جديد مدفوع من المحفظة (جاهز للتنفيذ):</b>\n"
        f"🆔 رقم الطلب: <code>{ord_id}</code>\n"
        f"👤 الزبون: {u_info} (<code>{user_id}</code>)\n"
        f"📦 الخدمة: <b>{html.escape(service)}</b>\n"
        f"🎯 البيانات: <code>{html.escape(target)}</code>\n"
        f"💰 المبلغ المخصوم: <b>{price:,} ل.س</b>\n\n"
        f"💡 للرد على الزبون، قم بعمل رد (Reply) مباشر على هذه الرسالة."
    )
    kb_group = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ تم التنفيذ", callback_data=f"ord_act:done:{ord_id}"),
            InlineKeyboardButton(text="❌ إلغاء واسترجاع", callback_data=f"ord_act:ref:{ord_id}")
        ]
    ])
    await bot.send_message(group_id, group_card, reply_markup=kb_group)

    # إشعار العميل بالنجاح المباشر
    success_card = (
        f"🎉 <b>تم شراء الخدمة بنجاح!</b>\n"
        f"────────────────────────────\n"
        f"🆔 رقم الطلب: <code>{ord_id}</code>\n"
        f"📦 الخدمة: <b>{html.escape(service)}</b>\n"
        f"🎯 البيانات: <code>{html.escape(target)}</code>\n"
        f"💵 المبلغ المخصوم: <b>{price:,} ل.س</b>\n"
        f"💰 رصيدك المتبقي: <b>{(current_balance - price):,} ل.س</b>\n"
        f"────────────────────────────\n"
        f"⏳ تم تحويل طلبك لفريق التنفيذ فوراً وسيصلك إشعار بالانتهاء."
    )
    kb_home = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 العودة للرئيسية", callback_data="back_home")]])
    if isinstance(cb_or_msg, types.CallbackQuery):
        await cb_or_msg.message.edit_text(success_card, reply_markup=kb_home)
    else:
        await cb_or_msg.answer(success_card, reply_markup=kb_home)

# =====================================================================
# 9. قسم الرصيد والكاش (Syriatel & MTN)
# =====================================================================
@dp.callback_query(F.data == "sec:balance")
async def balance_home(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="🔴 سيريتل (Syriatel)", callback_data="net:syr")],
        [InlineKeyboardButton(text="🟡 إم تي إن (MTN)", callback_data="net:mtn")],
        [InlineKeyboardButton(text="🔙 العودة للرئيسية", callback_data="back_home")]
    ]
    await cb.message.edit_text("📞 <b>اختر شبكة الاتصال المطلوبة:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("net:"))
async def net_menu_view(cb: types.CallbackQuery):
    net = cb.data.split(":")[1]
    name = "Syriatel" if net == "syr" else "MTN"
    kb = [
        [InlineKeyboardButton(text=f"📲 وحدات {name}", callback_data=f"bopt:{net}:units")],
        [InlineKeyboardButton(text=f"⛽ جملة {name} كازية", callback_data=f"bopt:{net}:station")],
        [InlineKeyboardButton(text=f"🧾 فواتير {name}", callback_data=f"bopt:{net}:invoice")],
        [InlineKeyboardButton(text=f"💵 كاش {name}", callback_data=f"bopt:{net}:cash")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="sec:balance")]
    ]
    await cb.message.edit_text(f"📞 <b>خدمات شبكة {name}:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("bopt:"))
async def handle_balance_options(cb: types.CallbackQuery, state: FSMContext):
    _, net, opt = cb.data.split(":")
    net_name = "Syriatel" if net == "syr" else "MTN"

    if opt == "units":
        items = SYR_UNITS if net == "syr" else MTN_UNITS
        buttons = []
        for idx, (u, p) in enumerate(items):
            buttons.append(InlineKeyboardButton(text=f"{u} ⬅ {p:,} ل.س", callback_data=f"bu_{net}_{idx}"))
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"net:{net}")])
        await cb.message.edit_text(f"📲 <b>اختر فئة وحدات {net_name}:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

    elif opt == "station":
        buttons = []
        for idx, (a, p) in enumerate(STATION_VALS):
            buttons.append(InlineKeyboardButton(text=f"فئة {a:,} ⬅ {p:,} ل.س", callback_data=f"bs_{net}_{idx}"))
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"net:{net}")])
        await cb.message.edit_text(f"⛽ <b>اختر فئة كازية {net_name}:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

    elif opt == "invoice":
        await state.update_data(net=net, s_title=f"فواتير {net_name}")
        st = BalanceState.syr_invoice_num if net == "syr" else BalanceState.mtn_invoice_num
        await state.set_state(st)
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 إلغاء", callback_data=f"net:{net}")]])
        await cb.message.edit_text(f"🧾 أدخل رقم فاتورة {net_name}:", reply_markup=kb)

    elif opt == "cash":
        await state.update_data(net=net, s_title=f"كاش {net_name}")
        st = BalanceState.syr_cash_amt if net == "syr" else BalanceState.mtn_cash_amt
        await state.set_state(st)
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 إلغاء", callback_data=f"net:{net}")]])
        await cb.message.edit_text(f"💵 أدخل كمية كاش {net_name} المطلوبة (الحد الأدنى 1,000 ل.س):", reply_markup=kb)

@dp.callback_query(F.data.startswith("bu_"))
async def sel_units_pack(cb: types.CallbackQuery, state: FSMContext):
    _, net, idx = cb.data.split("_")
    items = SYR_UNITS if net == "syr" else MTN_UNITS
    u, p = items[int(idx)]
    net_name = "Syriatel" if net == "syr" else "MTN"
    await state.update_data(s_title=f"وحدات {net_name} ({u} وحدة)", s_price=int(p))
    st = BalanceState.syr_units_phone if net == "syr" else BalanceState.mtn_units_phone
    await state.set_state(st)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 إلغاء", callback_data=f"bopt:{net}:units")]])
    await cb.message.edit_text(f"📲 اخترت فئة <b>{u} وحدة</b> ({p:,} ل.س)\n\nأدخل رقم الهاتف المطلوب التحويل إليه (10 خانات تبدأ بـ 09):", reply_markup=kb)

@dp.message(BalanceState.syr_units_phone)
async def proc_syr_phone(message: types.Message, state: FSMContext):
    p = message.text.strip()
    if not (p.isdigit() and len(p) == 10 and p.startswith("09")):
        await message.reply("⚠️ رقم سيريتل يجب أن يتكون من 10 خانات ويبدأ بـ 09:")
        return
    data = await state.get_data()
    await process_wallet_purchase(message, message.from_user.id, "balance", data["s_title"], f"رقم سيريتل: {p}", data["s_price"], state)

@dp.message(BalanceState.mtn_units_phone)
async def proc_mtn_phone(message: types.Message, state: FSMContext):
    p = message.text.strip()
    if not (p.isdigit() and len(p) == 10 and p.startswith("09")):
        await message.reply("⚠️️ رقم MTN يجب أن يتكون من 10 خانات ويبدأ بـ 09:")
        return
    data = await state.get_data()
    await process_wallet_purchase(message, message.from_user.id, "balance", data["s_title"], f"رقم MTN: {p}", data["s_price"], state)

@dp.callback_query(F.data.startswith("bs_"))
async def sel_station_pack(cb: types.CallbackQuery, state: FSMContext):
    _, net, idx = cb.data.split("_")
    a, p = STATION_VALS[int(idx)]
    net_name = "Syriatel" if net == "syr" else "MTN"
    await state.update_data(s_title=f"جملة كازية {net_name} (فئة {a:,})", s_price=int(p))
    st = BalanceState.syr_station_code if net == "syr" else BalanceState.mtn_station_code
    await state.set_state(st)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 إلغاء", callback_data=f"bopt:{net}:station")]])
    await cb.message.edit_text(f"⛽ أدخل كود كازية {net_name}:", reply_markup=kb)

@dp.message(BalanceState.syr_station_code)
async def proc_syr_st_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if not (code.isdigit() and len(code) == 6):
        await message.reply("⚠️ كود كازية سيريتل يجب أن يتكون من 6 أرقام حصراً:")
        return
    await state.update_data(st_code=code)
    await state.set_state(BalanceState.syr_station_gov)
    buttons = [InlineKeyboardButton(text=g, callback_data=f"sgov_syr:{g}") for g in GOVERNORATES]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    await message.answer("📍 اختر المحافظة:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("sgov_syr:"), BalanceState.syr_station_gov)
async def proc_syr_st_gov(cb: types.CallbackQuery, state: FSMContext):
    gov = cb.data.split(":")[1]
    data = await state.get_data()
    target_info = f"كود كازية: {data['st_code']} | المحافظة: {gov}"
    await process_wallet_purchase(cb, cb.from_user.id, "balance", data["s_title"], target_info, data["s_price"], state)

@dp.message(BalanceState.mtn_station_code)
async def proc_mtn_st_code(message: types.Message, state: FSMContext):
    await state.update_data(st_code=message.text.strip())
    await state.set_state(BalanceState.mtn_station_num)
    await message.answer("⛽ أدخل رقم كازية MTN:")

@dp.message(BalanceState.mtn_station_num)
async def proc_mtn_st_num(message: types.Message, state: FSMContext):
    await state.update_data(st_num=message.text.strip())
    await state.set_state(BalanceState.mtn_station_gov)
    buttons = [InlineKeyboardButton(text=g, callback_data=f"sgov_mtn:{g}") for g in GOVERNORATES]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    await message.answer("📍 اختر المحافظة:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("sgov_mtn:"), BalanceState.mtn_station_gov)
async def proc_mtn_st_gov(cb: types.CallbackQuery, state: FSMContext):
    gov = cb.data.split(":")[1]
    data = await state.get_data()
    target_info = f"كود: {data['st_code']} | رقم: {data['st_num']} | المحافظة: {gov}"
    await process_wallet_purchase(cb, cb.from_user.id, "balance", data["s_title"], target_info, data["s_price"], state)

@dp.message(BalanceState.syr_invoice_num)
async def proc_syr_inv_num(message: types.Message, state: FSMContext):
    await state.update_data(inv_num=message.text.strip())
    await state.set_state(BalanceState.syr_invoice_amt)
    await message.answer("💵 أدخل قيمة الفاتورة بالليرة السورية:")

@dp.message(BalanceState.syr_invoice_amt)
async def proc_syr_inv_amt(message: types.Message, state: FSMContext):
    val_txt = message.text.strip().replace(",", "")
    if not val_txt.isdigit() or int(val_txt) <= 0:
        await message.reply("⚠️ القيمة يجب أن تكون أكبر من صفر وصحيحة:")
        return
    amt = int(val_txt)
    final_price = round(amt * 1.05)
    data = await state.get_data()
    target_info = f"رقم فاتورة Syriatel: {data['inv_num']} | القيمة: {amt:,}"
    await process_wallet_purchase(message, message.from_user.id, "balance", f"فاتورة Syriatel ({amt:,} ل.س)", target_info, final_price, state)

@dp.message(BalanceState.mtn_invoice_num)
async def proc_mtn_inv_num(message: types.Message, state: FSMContext):
    await state.update_data(inv_num=message.text.strip())
    await state.set_state(BalanceState.mtn_invoice_amt)
    await message.answer("💵 أدخل قيمة الفاتورة بالليرة السورية:")

@dp.message(BalanceState.mtn_invoice_amt)
async def proc_mtn_inv_amt(message: types.Message, state: FSMContext):
    val_txt = message.text.strip().replace(",", "")
    if not val_txt.isdigit() or int(val_txt) <= 0:
        await message.reply("⚠️ القيمة يجب أن تكون أكبر من صفر وصحيحة:")
        return
    amt = int(val_txt)
    final_price = round(amt * 1.05)
    data = await state.get_data()
    target_info = f"رقم فاتورة MTN: {data['inv_num']} | القيمة: {amt:,}"
    await process_wallet_purchase(message, message.from_user.id, "balance", f"فاتورة MTN ({amt:,} ل.س)", target_info, final_price, state)

@dp.message(BalanceState.syr_cash_amt)
async def proc_syr_cash_amt(message: types.Message, state: FSMContext):
    val_txt = message.text.strip().replace(",", "")
    if not val_txt.isdigit() or int(val_txt) < 1000:
        await message.reply("⚠️ الحد الأدنى للكاش هو 1,000 ل.س:")
        return
    amt = int(val_txt)
    final_price = round(amt * 1.05)
    await state.update_data(c_amt=amt, c_price=final_price)
    await state.set_state(BalanceState.syr_cash_id)
    await message.answer("👤 أدخل معرّف Player-ID لاستلام كاش Syriatel:")

@dp.message(BalanceState.syr_cash_id)
async def proc_syr_cash_id(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_info = f"Player-ID: {message.text.strip()} | الكمية: {data['c_amt']:,}"
    await process_wallet_purchase(message, message.from_user.id, "balance", f"كاش Syriatel ({data['c_amt']:,})", target_info, data["c_price"], state)

@dp.message(BalanceState.mtn_cash_amt)
async def proc_mtn_cash_amt(message: types.Message, state: FSMContext):
    val_txt = message.text.strip().replace(",", "")
    if not val_txt.isdigit() or int(val_txt) < 1000:
        await message.reply("⚠️ الحد الأدنى للكاش هو 1,000 ل.س:")
        return
    amt = int(val_txt)
    final_price = round(amt * 1.05)
    await state.update_data(c_amt=amt, c_price=final_price)
    await state.set_state(BalanceState.mtn_cash_num)
    await message.answer("📱 أدخل رقم كاش MTN المطلوب التحويل إليه:")

@dp.message(BalanceState.mtn_cash_num)
async def proc_mtn_cash_num(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_info = f"رقم كاش MTN: {message.text.strip()} | الكمية: {data['c_amt']:,}"
    await process_wallet_purchase(message, message.from_user.id, "balance", f"كاش MTN ({data['c_amt']:,})", target_info, data["c_price"], state)

# =====================================================================
# 10. قسم شحن الألعاب
# =====================================================================
@dp.callback_query(F.data == "sec:games")
async def games_home(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="🔫 ببجي (PUBG)", callback_data="game:pubg")],
        [InlineKeyboardButton(text="🔥 فري فاير (Free Fire)", callback_data="game:ff")],
        [InlineKeyboardButton(text="🃏 جواكر (Jawaker)", callback_data="game:jawaker")],
        [InlineKeyboardButton(text="⚔️ كلاش أوف كلانس (CoC)", callback_data="game:coc")],
        [InlineKeyboardButton(text="🎮 باقي الألعاب [طلب تسعير]", callback_data="quote:game")],
        [InlineKeyboardButton(text="🔙 العودة للرئيسية", callback_data="back_home")]
    ]
    await cb.message.edit_text("🎮 <b>اختر اللعبة المطلوبة:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("game:"))
async def game_packs_view(cb: types.CallbackQuery):
    g_key = cb.data.split(":")[1]
    rate = await get_setting("dollar_rate")
    buttons = []
    for idx, (p_name, p_usd) in enumerate(GAME_PACKS[g_key]):
        price_syr = round(p_usd * rate)
        buttons.append([InlineKeyboardButton(text=f"{p_name} ⬅ {price_syr:,} ل.س", callback_data=f"buyg:{g_key}:{idx}")])
    buttons.append([InlineKeyboardButton(text="🔙 رجوع للألعاب", callback_data="sec:games")])
    await cb.message.edit_text("🎮 <b>اختر الباقة المطلوبة:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("buyg:"))
async def buy_game_pack(cb: types.CallbackQuery, state: FSMContext):
    _, g_key, idx = cb.data.split(":")
    p_name, p_usd = GAME_PACKS[g_key][int(idx)]
    rate = await get_setting("dollar_rate")
    price_syr = round(p_usd * rate)
    
    await state.update_data(g_dept="games", g_service=f"شحن {g_key.upper()} ({p_name})", g_price=price_syr)
    await state.set_state(GlobalOrderState.input_data)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 إلغاء", callback_data=f"game:{g_key}")]])
    await cb.message.edit_text(f"🎮 لقد اخترت: <b>{g_key.upper()} - {p_name}</b> ({price_syr:,} ل.س)\n\nأدخل الآيدي (Player ID) واسمك داخل اللعبة:", reply_markup=kb)

@dp.message(GlobalOrderState.input_data)
async def process_global_order_data(message: types.Message, state: FSMContext):
    data = await state.get_data()
    dept = data.get("g_dept", "games")
    service = data.get("g_service", "خدمة عامة")
    price = data.get("g_price", 0)
    target = message.text.strip()
    await process_wallet_purchase(message, message.from_user.id, dept, service, target, price, state)

# =====================================================================
# 11. قسم تطبيقات الشات
# =====================================================================
@dp.callback_query(F.data == "sec:chat")
async def chat_menu(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="🌟 Soul Star (كوينز × 0.025)", callback_data="chat_calc:soulstar")],
        [InlineKeyboardButton(text="❄️ Soulchill (كريستال × 0.30)", callback_data="chat_calc:soulchill")],
        [InlineKeyboardButton(text="💬 IMO (ألماس × 0.50)", callback_data="chat_calc:imo")],
        [InlineKeyboardButton(text="🗣 Talsa chat (كوينز × 0.02)", callback_data="chat_calc:talsa")],
        [InlineKeyboardButton(text="🔍 باقي التطبيقات [طلب تسعير]", callback_data="quote:chat")],
        [InlineKeyboardButton(text="🔙 العودة للرئيسية", callback_data="back_home")]
    ]
    await cb.message.edit_text("💬 <b>اختر تطبيق الشات المطلوب:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("chat_calc:"))
async def chat_calc_prompt(cb: types.CallbackQuery, state: FSMContext):
    c_key = cb.data.split(":")[1]
    await state.update_data(c_app=c_key)
    await state.set_state(ChatInput.entering_data)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 إلغاء", callback_data="sec:chat")]])
    await cb.message.edit_text("💬 أدخل (الآيدي) متبوعاً بـ (الكمية المطلوبة):\nمثال: <code>123456 5000</code>", reply_markup=kb)

@dp.message(ChatInput.entering_data)
async def proc_chat_calc_receive(message: types.Message, state: FSMContext):
    data = await state.get_data()
    c_key = data.get("c_app")
    try:
        parts = message.text.strip().split()
        if len(parts) < 2:
            raise ValueError()
        u_id = parts[0]
        qty = float(parts[1])
        if qty <= 0:
            await message.reply("⚠️ الكمية يجب أن تكون أكبر من صفر:")
            return

        if c_key == "soulstar":
            price = round(qty * 0.025)
            s_name = f"Soul Star ({int(qty):,} كوينز)"
        elif c_key == "soulchill":
            price = round(qty * 0.30)
            s_name = f"Soulchill ({int(qty):,} كريستال)"
        elif c_key == "talsa":
            price = round(qty * 0.02)
            s_name = f"Talsa chat ({int(qty):,} كوينز)"
        else:
            price = round(qty * 0.50)
            s_name = f"IMO ({int(qty):,} ألماس)"

        await process_wallet_purchase(message, message.from_user.id, "games", s_name, f"الآيدي: {u_id}", price, state)
    except Exception:
        await message.reply("⚠️ أرسل الآيدي ثم الكمية وبينهما مسافة بشكل صحيح:")

# =====================================================================
# 12. قسم الحسابات الجاهزة والاشتراكات
# =====================================================================
@dp.callback_query(F.data == "sec:accounts")
async def accounts_home(cb: types.CallbackQuery):
    kb = []
    for k, (name, price) in FAST_ACCOUNTS.items():
        kb.append([InlineKeyboardButton(text=f"🔹 {name} ({price:,} ل.س)", callback_data=f"facc:{k}")])
    kb.append([InlineKeyboardButton(text="📋 باقي الحسابات (27 خدمة)", callback_data="acc_page:0")])
    kb.append([InlineKeyboardButton(text="🔙 العودة للرئيسية", callback_data="back_home")])
    await cb.message.edit_text("📦 <b>اختر الحساب الجاهز المطلوب:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("facc:"))
async def acc_fast_confirm(cb: types.CallbackQuery, state: FSMContext):
    k = cb.data.split(":")[1]
    name, price = FAST_ACCOUNTS[k]
    await process_wallet_purchase(cb, cb.from_user.id, "accounts", f"حساب {name}", "حساب رسمي رسمي مع الضمان", price, state)

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
        buttons.append([InlineKeyboardButton(text=f"🔹 {item}", callback_data=f"sel_acc:{real_idx}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ السابق", callback_data=f"acc_page:{page-1}"))
    if end < len(ACCOUNTS_LIST):
        nav.append(InlineKeyboardButton(text="التالي ➡️", callback_data=f"acc_page:{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="🔙 رجوع للحسابات", callback_data="sec:accounts")])
    await cb.message.edit_text(f"📦 <b>اختر الحساب المطلوب (صفحة {page+1} من 5):</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("sel_acc:"))
async def account_select_duration(cb: types.CallbackQuery, state: FSMContext):
    idx = int(cb.data.split(":")[1])
    acc_name = ACCOUNTS_LIST[idx]
    await state.update_data(selected_acc_name=acc_name)

    kb = [
        [InlineKeyboardButton(text="⏳ اشتراك شهر", callback_data="acc_dur:شهر")],
        [InlineKeyboardButton(text="⏳ اشتراك 3 أشهر", callback_data="acc_dur:3 أشهر")],
        [InlineKeyboardButton(text="⏳ اشتراك سنة", callback_data="acc_dur:سنة")],
        [InlineKeyboardButton(text="🔙 رجوع للقائمة", callback_data="acc_page:0")]
    ]
    await cb.message.edit_text(f"لقد اخترت: <b>{html.escape(acc_name)}</b>\n\nاختر المدة المطلوبة بالضغط على الزر أدناه:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("acc_dur:"))
async def account_duration_finish(cb: types.CallbackQuery, state: FSMContext):
    dur = cb.data.split(":")[1]
    data = await state.get_data()
    acc_name = data.get("selected_acc_name", "حساب مميز")

    group_id = GROUPS["accounts"]
    user_info = f"@{html.escape(cb.from_user.username)}" if cb.from_user.username else "بدون"
    text_to_group = (
        f"📩 <b>طلب تسعير حساب جديد:</b>\n"
        f"👤 الزبون: {user_info} (<code>{cb.from_user.id}</code>)\n"
        f"🏷 الحساب: <b>{html.escape(acc_name)}</b>\n"
        f"⏳ المدة: <b>{html.escape(dur)}</b>\n\n"
        f"💡 لتسعير الطلب والرد على الزبون، قم بعمل رد (Reply) مباشر على هذه الرسالة."
    )
    await bot.send_message(group_id, text_to_group)
    await state.clear()
    await cb.message.edit_text(
        f"✅ تم إرسال طلبك لحساب <b>{html.escape(acc_name)}</b> (مدة: {dur}) للإدارة بنجاح.\n"
        f"سيتم مراجعته والرد عليك هنا بالتفاصيل والسعر قريباً.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 العودة للرئيسية", callback_data="back_home")]])
    )

# =====================================================================
# 13. قسم السوشيال ميديا والإعلانات
# =====================================================================
@dp.callback_query(F.data == "sec:social")
async def social_menu(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="📘 خدمات فيسبوك", callback_data="soc:fb")],
        [InlineKeyboardButton(text="📸 خدمات إنستغرام", callback_data="soc:ig")],
        [InlineKeyboardButton(text="✈ خدمات تلغرام", callback_data="soc:tg")],
        [InlineKeyboardButton(text="📢 إعلانات ممولة فيسبوك", callback_data="soc:ads")],
        [InlineKeyboardButton(text="🔙 العودة للرئيسية", callback_data="back_home")]
    ]
    await cb.message.edit_text("🚀 <b>اختر منصة السوشيال ميديا:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("soc:"))
async def soc_platforms(cb: types.CallbackQuery):
    plat = cb.data.split(":")[1]
    if plat in ["fb", "ig", "tg"]:
        kb = []
        for code, (title, price, p_type) in SOCIAL_PACKS.items():
            if p_type == plat:
                kb.append([InlineKeyboardButton(text=f"🔹 {title} ({price:,} ل.س)", callback_data=f"spk:{code}")])
        kb.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="sec:social")])
        await cb.message.edit_text("🚀 <b>اختر الباقة المطلوبة:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    elif plat == "ads":
        buttons = []
        for d, p in [(1, 600), (2, 1100), (3, 1500), (4, 2000), (5, 2500), (6, 3000), (7, 3600), (10, 5000)]:
            buttons.append(InlineKeyboardButton(text=f"إعلان {d} أيام ⬅ {p:,} ل.س", callback_data=f"ad_f:{d}:{p}"))
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        rows.append([InlineKeyboardButton(text="⚙ مدة مخصصة (200 ل.س/يوم)", callback_data="ad_c")])
        rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="sec:social")])
        await cb.message.edit_text("📢 <b>اختر مدة الإعلان الممول:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("spk:"))
async def soc_buy_pack(cb: types.CallbackQuery, state: FSMContext):
    code = cb.data.split(":")[1]
    title, price, plat = SOCIAL_PACKS[code]
    await state.update_data(g_dept="social", g_service=f"{plat.upper()} - {title}", g_price=int(price))
    await state.set_state(GlobalOrderState.input_data)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 إلغاء", callback_data=f"soc:{plat}")]])
    await cb.message.edit_text(f"🚀 لقد اخترت: <b>{plat.upper()} - {title}</b> ({price:,} ل.س)\n\nأرسل رابط الحساب أو المنشور المطلوب:", reply_markup=kb)

@dp.callback_query(F.data.startswith("ad_f:"))
async def ad_f_click(cb: types.CallbackQuery, state: FSMContext):
    _, d, p = cb.data.split(":")
    await state.update_data(g_dept="social", g_service=f"إعلان ممول فيسبوك ({d} أيام)", g_price=int(p))
    await state.set_state(GlobalOrderState.input_data)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 إلغاء", callback_data="soc:ads")]])
    await cb.message.edit_text(f"📢 لقد اخترت: <b>إعلان ممول ({d} أيام)</b> ({int(p):,} ل.س)\n\nأدخل رقم هاتفك للتواصل وتجهيز تفاصيل الإعلان:", reply_markup=kb)

@dp.callback_query(F.data == "ad_c")
async def ad_c_click(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(CustomAd.days)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 إلغاء", callback_data="soc:ads")]])
    await cb.message.edit_text("📢 أدخل عدد الأيام المطلوبة للإعلان (اليوم = 200 ل.س):", reply_markup=kb)

@dp.message(CustomAd.days)
async def proc_custom_ad_days(message: types.Message, state: FSMContext):
    val_txt = message.text.strip()
    if not val_txt.isdigit() or int(val_txt) <= 0:
        await message.reply("⚠️ عدد الأيام يجب أن يكون أكبر من صفر وصحيحاً:")
        return
    days = int(val_txt)
    price = days * 200
    await state.update_data(g_dept="social", g_service=f"إعلان مخصص فيسبوك ({days} أيام)", g_price=price)
    await state.set_state(GlobalOrderState.input_data)
    await message.answer(f"📢 الإجمالي: <b>{price:,} ل.س</b>\n\nأدخل رقم هاتفك للتواصل لتجهيز الإعلان:")

# =====================================================================
# 14. قسم أرقام التفعيل
# =====================================================================
@dp.callback_query(F.data == "sec:numbers")
async def numbers_home(cb: types.CallbackQuery):
    p_wa = int(await get_setting("num_whatsapp"))
    p_tg = int(await get_setting("num_telegram"))
    kb = [
        [InlineKeyboardButton(text=f"🟢 رقم واتساب أجنبي ({p_wa:,} ل.س)", callback_data=f"buyn:whatsapp:{p_wa}")],
        [InlineKeyboardButton(text=f"🔵 رقم تلغرام أمريكي ({p_tg:,} ل.س)", callback_data=f"buyn:telegram:{p_tg}")],
        [InlineKeyboardButton(text="📱 رقم تيك توك [طلب تسعير]", callback_data="quote:num_tiktok")],
        [InlineKeyboardButton(text="🌐 تفعيل غوغل [طلب تسعير]", callback_data="quote:num_google")],
        [InlineKeyboardButton(text="🍎 تفعيل آبل [طلب تسعير]", callback_data="quote:num_apple")],
        [InlineKeyboardButton(text="🔙 العودة للرئيسية", callback_data="back_home")]
    ]
    await cb.message.edit_text("📱 <b>قسم أرقام التفعيل:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("buyn:"))
async def buy_num_fast(cb: types.CallbackQuery, state: FSMContext):
    _, target, price = cb.data.split(":")
    name = "واتساب أجنبي" if target == "whatsapp" else "تلغرام أمريكي"
    await process_wallet_purchase(cb, cb.from_user.id, "social", f"رقم {name}", "تسليم كود تفعيل فوري", int(price), state)

# =====================================================================
# 15. طلبات التسعير التفاعلية والدعم الفني
# =====================================================================
@dp.callback_query(F.data.startswith("quote:"))
async def generic_quote_start(cb: types.CallbackQuery, state: FSMContext):
    q_type = cb.data.split(":")[1]
    g_map = {
        "game": ("games", "🎮 طلب تسعير لعبة"),
        "chat": ("games", "💬 طلب تسعير تطبيق شات"),
        "num_tiktok": ("social", "📱 طلب رقم تيك توك"),
        "num_google": ("social", "🌐 طلب تفعيل غوغل"),
        "num_apple": ("social", "🍎 طلب تفعيل آبل")
    }
    sec, label = g_map.get(q_type, ("games", "طلب عام"))
    await state.update_data(q_sec=sec, q_label=label)
    await state.set_state(GlobalOrderState.quote_text)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 إلغاء", callback_data="back_home")]])
    await cb.message.edit_text(f"✍️ يرجى كتابة تفاصيل <b>{label}</b> بالتفصيل:\n(الاسم + المعرف أو الآيدي + الكمية المطلوبة):", reply_markup=kb)

@dp.message(GlobalOrderState.quote_text)
async def generic_quote_receive(message: types.Message, state: FSMContext):
    if not message.text:
        await message.reply("⚠️ يرجى إرسال تفاصيل الطلب كنص:")
        return

    data = await state.get_data()
    sec = data.get("q_sec", "games")
    label = data.get("q_label", "طلب تسعير")
    group_id = GROUPS.get(sec, GROUPS["games"])

    user_info = f"@{html.escape(message.from_user.username)}" if message.from_user.username else "بدون"
    text_to_group = (
        f"📩 <b>{html.escape(label)}:</b>\n"
        f"👤 الزبون: {user_info} (<code>{message.from_user.id}</code>)\n"
        f"📝 <b>التفاصيل:</b>\n{html.escape(message.text)}\n\n"
        f"💡 لتسعير الطلب والرد على الزبون، قم بعمل رد (Reply) مباشر على هذه الرسالة واكتب السعر والتفاصيل."
    )
    await bot.send_message(group_id, text_to_group)
    await state.clear()
    await message.answer(
        "✅ تم استلام طلبك وإرساله للإدارة بنجاح. سيتم مراجعته والرد عليك هنا قريباً بالسعر.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 العودة للرئيسية", callback_data="back_home")]])
    )

@dp.callback_query(F.data == "sec:support")
async def support_start(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(GlobalOrderState.support_msg)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 إلغاء", callback_data="back_home")]])
    await cb.message.edit_text("🛠 <b>اكتب استفسارك أو مشكلتك بالتفصيل وسيقوم فريق الدعم بالرد عليك هنا:</b>", reply_markup=kb)

@dp.message(GlobalOrderState.support_msg)
async def support_forward(message: types.Message, state: FSMContext):
    if not message.text:
        await message.reply("⚠️ يرجى كتابة الاستفسار كنص:")
        return

    user_info = f"@{html.escape(message.from_user.username)}" if message.from_user.username else "بدون"
    txt = (
        f"📩 <b>تذكرة دعم فني جديدة:</b>\n"
        f"👤 الزبون: {user_info} (<code>{message.from_user.id}</code>)\n\n"
        f"📝 <b>الرسالة:</b>\n{html.escape(message.text)}\n\n"
        f"💡 للرد على الزبون، قم بعمل رد (Reply) مباشر على هذه الرسالة."
    )
    await bot.send_message(GROUPS["support"], txt)
    await state.clear()
    await message.answer(
        "✅ تم إرسال رسالتك للدعم الفني، سنرد عليك هنا بأقرب وقت.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 العودة للرئيسية", callback_data="back_home")]])
    )

# =====================================================================
# 16. إجراءات المجموعات وردود المشرفين المرنة
# =====================================================================
@dp.callback_query(F.data.startswith("ord_act:"))
async def handle_staff_order_action(cb: types.CallbackQuery):
    _, action, ord_id = cb.data.split(":")
    async with get_db() as db:
        cursor = await db.execute("SELECT user_id, service_name, status FROM orders WHERE order_id = ?", (ord_id,))
        order = await cursor.fetchone()

    if not order:
        await cb.answer("⚠️ الطلب غير موجود!", show_alert=True)
        return

    cust_id, s_name, current_status = order[0], order[1], order[2]
    if current_status in ["COMPLETED", "REJECTED", "REFUNDED"]:
        await cb.answer("⚠️ تم اتخاذ إجراء على هذا الطلب مسبقاً!", show_alert=True)
        return

    if action == "done":
        async with get_db() as db:
            await db.execute("UPDATE orders SET status = 'COMPLETED' WHERE order_id = ?", (ord_id,))
            await db.commit()

        try:
            await bot.send_message(cust_id, f"🎉 <b>تم تنفيذ طلبك بنجاح!</b>\n📦 الخدمة: <b>{html.escape(s_name)}</b>\n🆔 رقم الطلب: <code>{ord_id}</code>")
        except Exception:
            pass

        if cb.message.caption:
            await cb.message.edit_caption(caption=cb.message.caption + "\n\n🟢 <b>تم التنفيذ بنجاح</b>", reply_markup=None)
        else:
            await cb.message.edit_text(text=cb.message.text + "\n\n🟢 <b>تم التنفيذ بنجاح</b>", reply_markup=None)

    elif action == "ref":
        success, uid, refunded_amt = await WalletService.refund(ord_id)
        if success:
            try:
                await bot.send_message(uid, f"↩️ <b>تم إلغاء الطلب {ord_id}</b> وإعادة مبلغ <b>{refunded_amt:,} ل.س</b> إلى محفظتك.")
            except Exception:
                pass

            if cb.message.caption:
                await cb.message.edit_caption(caption=cb.message.caption + "\n\n🟡 <b>تم الإلغاء واسترجاع الرصيد للمحفظة</b>", reply_markup=None)
            else:
                await cb.message.edit_text(text=cb.message.text + "\n\n🟡 <b>تم الإلغاء واسترجاع الرصيد للمحفظة</b>", reply_markup=None)
        else:
            await cb.answer("تعذر استرجاع المبلغ!", show_alert=True)

@dp.callback_query(F.data.startswith("adm_pay:"))
async def handle_admin_payment_action(cb: types.CallbackQuery):
    _, act, pay_id = cb.data.split(":")
    async with get_db() as db:
        cursor = await db.execute("SELECT user_id, amount, status FROM payments WHERE payment_id = ?", (pay_id,))
        payment = await cursor.fetchone()

    if not payment or payment[2] != "UNDER_REVIEW":
        await cb.answer("⚠️ تمت معالجة هذه الدفعة مسبقاً!", show_alert=True)
        return

    u_id, amt = payment[0], payment[1]
    if act == "ok":
        await WalletService.deposit(u_id, amt, pay_id, "شحن محفظة عبر شام كاش")
        async with get_db() as db:
            await db.execute("UPDATE payments SET status = 'ACCEPTED' WHERE payment_id = ?", (pay_id,))
            await db.commit()
        u = await WalletService.get_or_create_user(u_id)
        try:
            await bot.send_message(u_id, f"🎉 <b>تم تأكيد إيداعك بنجاح!</b>\n➕ تمت إضافة: <b>{amt:,} ل.س</b>\n💳 رصيدك الحالي: <code>{u[2]:,} ل.س</code>\n\nيمكنك الآن الشراء الفوري بضغطة زر واحدة!")
        except Exception:
            pass
        await cb.message.edit_caption(caption=cb.message.caption + f"\n\n🟢 <b>تم قبول الإيداع ({amt:,} ل.س)</b>", reply_markup=None)
    else:
        async with get_db() as db:
            await db.execute("UPDATE payments SET status = 'DECLINED' WHERE payment_id = ?", (pay_id,))
            await db.commit()
        try:
            await bot.send_message(u_id, f"❌ نعتذر منك، تم رفض إشعار الإيداع للدفعة <code>{pay_id}</code> لعدم تطابق التحويل.")
        except Exception:
            pass
        await cb.message.edit_caption(caption=cb.message.caption + "\n\n🔴 <b>تم رفض الإيداع</b>", reply_markup=None)

# معالجة رد المشرف في المجموعات (مرنة جداً وتتعرف على المعرف بجميع الحالات)
@dp.message(F.reply_to_message)
async def admin_group_direct_reply(message: types.Message):
    if message.chat.id not in ALL_ADMIN_GROUPS or not message.reply_to_message.from_user.is_bot:
        return

    admin_text = message.text or message.caption
    if not admin_text:
        return

    orig_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    match = re.search(r"\((\d{6,15})\)", orig_text)
    if not match:
        match = re.search(r"<code>(\d{6,15})</code>", orig_text)

    if match:
        cust_id = int(match.group(1))
        try:
            await bot.send_message(cust_id, f"💬 <b>إشعار من الإدارة بخصوص طلبك:</b>\n\n{html.escape(admin_text)}")
            await message.reply("✅ تم تسليم الرد للعميل بنجاح.")
        except TelegramForbiddenError:
            await message.reply("⚠️ تعذر الإرسال: قام العميل بحظر البوت.")
        except Exception as e:
            await message.reply(f"⚠️ فشل تسليم الرسالة: {e}")

# =====================================================================
# 17. لوحة تحكم المدير العام (/admin)
# =====================================================================
@dp.message(Command("admin"))
async def admin_panel_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("⛔ هذا الأمر مخصص للمدير العام فقط!")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 إحصائيات النظام", callback_data="adm:stats")],
        [InlineKeyboardButton(text="💵 تغذية رصيد مستخدم", callback_data="adm:add_bal"), InlineKeyboardButton(text="💱 سعر صرف الدولار", callback_data="adm:set_rate")],
        [InlineKeyboardButton(text="📢 إذاعة جماعية", callback_data="adm:broadcast")],
        [InlineKeyboardButton(text="❌ إغلاق اللوحة", callback_data="adm:close")]
    ])
    await message.answer("⚙️ <b>لوحة التحكم الرئيسية للمدير (V2 Wallet-Core):</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm:stats")
async def adm_stats_view(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    async with get_db() as db:
        c1 = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await c1.fetchone())[0]
        c2 = await db.execute("SELECT COUNT(*) FROM orders")
        total_orders = (await c2.fetchone())[0]
        c3 = await db.execute("SELECT SUM(amount) FROM payments WHERE status = 'ACCEPTED'")
        total_income = (await c3.fetchone())[0] or 0
        rate = await get_setting("dollar_rate")

    txt = (
        f"📊 <b>إحصائيات المنصة الشاملة:</b>\n"
        f"────────────────────────────\n"
        f"👥 إجمالي المستخدمين: <b>{total_users:,}</b>\n"
        f"📦 إجمالي الطلبات المنفذة: <b>{total_orders:,}</b>\n"
        f"💰 إجمالي الإيداعات المقبولة: <b>{total_income:,} ل.س</b>\n"
        f"💱 سعر صرف الدولار الحالي: <b>{rate:,.2f} ل.س</b>\n"
    )
    await cb.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:home")]]))

@dp.callback_query(F.data == "adm:set_rate")
async def adm_set_rate_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminActions.set_dollar_rate)
    current_rate = await get_setting("dollar_rate")
    await cb.message.edit_text(f"💱 سعر الصرف الحالي: <b>{current_rate:,} ل.س</b>\n\nأدخل سعر صرف الدولار الجديد بالليرة السورية:")

@dp.message(AdminActions.set_dollar_rate)
async def adm_set_rate_rec(message: types.Message, state: FSMContext):
    try:
        val = float(message.text.strip())
        if val <= 0:
            await message.reply("⚠️ يجب أن يكون السعر أكبر من صفر:")
            return
        await update_setting("dollar_rate", val)
        await state.clear()
        await message.reply(f"✅ تم تحديث سعر صرف الدولار إلى: <b>{val:,} ل.س</b>")
    except Exception:
        await message.reply("⚠️ أدخل قيمة صحيحة بالأرقام:")

@dp.callback_query(F.data == "adm:add_bal")
async def adm_add_bal_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminActions.add_bal_user)
    await cb.message.edit_text("👤 أدخل آيدي المستخدم (User ID) المراد تغذية رصيده:")

@dp.message(AdminActions.add_bal_user)
async def adm_add_bal_user_rec(message: types.Message, state: FSMContext):
    clean_txt = message.text.strip()
    if not clean_txt.isdigit():
        await message.reply("⚠️ يرجى إدخال آيدي صحيح بالأرقام:")
        return
    u_id = int(clean_txt)
    await state.update_data(target_uid=u_id)
    await state.set_state(AdminActions.add_bal_amount)
    await message.answer(f"💵 أدخل المبلغ المراد إضافته لحساب <code>{u_id}</code>:")

@dp.message(AdminActions.add_bal_amount)
async def adm_add_bal_amt_rec(message: types.Message, state: FSMContext):
    clean_txt = message.text.strip().replace(",", "")
    if not clean_txt.isdigit() or int(clean_txt) <= 0:
        await message.reply("⚠️ المبلغ يجب أن يكون رقماً صحيحاً وأكبر من صفر:")
        return
    amt = int(clean_txt)
    data = await state.get_data()
    u_id = data["target_uid"]
    ref = generate_uid("ADM")
    
    await WalletService.get_or_create_user(u_id)
    success = await WalletService.deposit(u_id, amt, ref, "تغذية إدارية مباشرة")
    await state.clear()
    if success:
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
    await cb.message.edit_text("📢 أرسل نص الرسالة التي تريد إذاعتها لجميع المستخدمين:")

@dp.message(AdminActions.broadcast_msg)
async def adm_broadcast_rec(message: types.Message, state: FSMContext):
    broadcast_text = message.text
    await state.clear()
    
    async with get_db() as db:
        cursor = await db.execute("SELECT user_id FROM users")
        users = await cursor.fetchall()

    sent = 0
    await message.reply(f"⏳ جارٍ الإرسال إلى {len(users)} مستخدم بأمان...")
    for idx, u in enumerate(users):
        try:
            await bot.send_message(u[0], f"📢 <b>إشعار عام من الإدارة:</b>\n\n{html.escape(broadcast_text)}")
            sent += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_message(u[0], f"📢 <b>إشعار عام من الإدارة:</b>\n\n{html.escape(broadcast_text)}")
                sent += 1
            except Exception:
                pass
        except Exception:
            pass

        if idx % 20 == 0:
            await asyncio.sleep(1)

    await message.answer(f"✅ اكتملت الإذاعة بنجاح! تم التسليم لـ {sent} مستخدم.")

@dp.callback_query(F.data == "adm:home")
async def adm_home_return(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 إحصائيات النظام", callback_data="adm:stats")],
        [InlineKeyboardButton(text="💵 تغذية رصيد مستخدم", callback_data="adm:add_bal"), InlineKeyboardButton(text="💱 سعر صرف الدولار", callback_data="adm:set_rate")],
        [InlineKeyboardButton(text="📢 إذاعة جماعية", callback_data="adm:broadcast")],
        [InlineKeyboardButton(text="❌ إغلاق اللوحة", callback_data="adm:close")]
    ])
    await cb.message.edit_text("⚙️ <b>لوحة التحكم الرئيسية للمدير (V2 Wallet-Core):</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm:close")
async def adm_close(cb: types.CallbackQuery):
    await cb.message.delete()

# =====================================================================
# 18. نقطة الإقلاع والتشغيل
# =====================================================================
async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("🚀 Syria Store Wallet-First System is running successfully...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
