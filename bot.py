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
# 1. الإعدادات والمتغيرات الأساسية
# =====================================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    # ضع التوكن هنا أو مرره كمتغير بيئة
    BOT_TOKEN = "8774564171:AAE_kxJM-yZ97f52_dTGwnKTLyfvsARM5Ik"

ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))  # ضع آيدي حسابك الحقيقي هنا
CHANNEL_ID = -1004492385043
CHANNEL_LINK = "https://t.me/SyriaStore_ch"

# معرفات المجموعات لكل قسم
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

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# قفل لمنع التزامن والسباق على مستوى الذاكرة
wallet_locks = {}

def get_user_lock(user_id: int) -> asyncio.Lock:
    if user_id not in wallet_locks:
        wallet_locks[user_id] = asyncio.Lock()
    return wallet_locks[user_id]

# دالة توليد معرفات فريدة
def generate_uid(prefix: str = "ORD") -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{int(time.time()) % 1000000:06d}-{suffix}"

# =====================================================================
# 2. طبقة قاعدة البيانات والدفتر المحاسبي (Database & Ledger)
# =====================================================================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute("PRAGMA foreign_keys = ON;")

        # 1. جدول المستخدمين
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            balance INTEGER DEFAULT 0 CHECK(balance >= 0),
            is_vip INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            role TEXT DEFAULT 'USER' CHECK(role IN ('USER', 'STAFF', 'ADMIN')),
            staff_department TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 2. جدول الطلبات الموحد
        await db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            department TEXT NOT NULL,
            service_name TEXT NOT NULL,
            target_data TEXT NOT NULL,
            price INTEGER NOT NULL CHECK(price >= 0),
            status TEXT DEFAULT 'PENDING_PAYMENT' CHECK(status IN ('PENDING_PAYMENT', 'PROCESSING', 'COMPLETED', 'REJECTED', 'REFUNDED')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
        """)

        # 3. جدول المدفوعات والشام كاش
        await db.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id TEXT PRIMARY KEY,
            order_id TEXT,
            user_id INTEGER NOT NULL,
            method TEXT NOT NULL,
            amount INTEGER NOT NULL CHECK(amount > 0),
            sham_tx_id TEXT UNIQUE,
            receipt_file_id TEXT,
            status TEXT DEFAULT 'UNDER_REVIEW' CHECK(status IN ('UNDER_REVIEW', 'ACCEPTED', 'DECLINED')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(order_id) REFERENCES orders(order_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
        """)

        # 4. الدفتر المحاسبي للمحفظة (Ledger)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS wallet_ledger (
            ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            reference_id TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('DEPOSIT', 'PURCHASE', 'REFUND', 'ADJUSTMENT')),
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
        """)

        # 5. الإعدادات
        await db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            val REAL
        );
        """)
        await db.execute("INSERT OR IGNORE INTO settings (key, val) VALUES ('dollar_rate', 150.0);")
        await db.commit()

# =====================================================================
# 3. خدمات المحفظة والعمليات المالية الذرية (Wallet Service)
# =====================================================================
class WalletService:
    @staticmethod
    async def get_or_create_user(user_id: int, username: str = "", full_name: str = ""):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT user_id, username, balance, is_vip, is_banned, role, staff_department FROM users WHERE user_id=?", (user_id,))
            row = await cursor.fetchone()
            if not row:
                role = "ADMIN" if user_id == ADMIN_ID else "USER"
                await db.execute(
                    "INSERT INTO users (user_id, username, full_name, role) VALUES (?, ?, ?, ?)",
                    (user_id, username, full_name, role)
                )
                await db.commit()
                return (user_id, username, 0, 0, 0, role, None)
            return row

    @staticmethod
    async def deposit(user_id: int, amount: int, ref_id: str, note: str = "") -> bool:
        """إيداع رصيد بالمحفظة وتسجيل قيد في الـ Ledger"""
        if amount <= 0:
            return False
        async with get_user_lock(user_id):
            async with aiosqlite.connect(DB_PATH) as db:
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
    async def deduct_for_order(user_id: int, order_id: str, amount: int) -> bool:
        """خصم آمن وذري لشراء خدمة مع تسجيل القيد"""
        if amount <= 0:
            return False
        async with get_user_lock(user_id):
            async with aiosqlite.connect(DB_PATH) as db:
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
                        "INSERT INTO wallet_ledger (user_id, reference_id, type, amount, balance_after, note) VALUES (?, ?, 'PURCHASE', ?, ?, 'شراء خدمة')",
                        (user_id, order_id, -amount, new_bal)
                    )
                    await db.execute("UPDATE orders SET status = 'PROCESSING' WHERE order_id = ?", (order_id,))
                    await db.commit()
                    return True
                except Exception as e:
                    await db.rollback()
                    logging.error(f"Deduct error: {e}")
                    return False

    @staticmethod
    async def refund(order_id: str) -> Tuple[bool, int, int]:
        """استرجاع مبلغ طلب ملغي للمحفظة فوراً"""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT user_id, price, status FROM orders WHERE order_id = ?", (order_id,))
            order = await cursor.fetchone()
            if not order or order[2] in ['REFUNDED', 'REJECTED']:
                return False, 0, 0

            user_id, price = order[0], order[1]
            async with get_user_lock(user_id):
                await db.execute("BEGIN IMMEDIATE TRANSACTION;")
                try:
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
# 4. الحالات FSM
# =====================================================================
class ClientOrder(StatesGroup):
    inputting_data = State()
    manual_receipt = State()

class WalletFlow(StatesGroup):
    amount = State()
    receipt = State()
    tx_code = State()

class AdminFlow(StatesGroup):
    broadcast = State()
    edit_rate = State()
    add_balance_user = State()
    add_balance_amt = State()

# =====================================================================
# 5. واجهة العميل (Client Interface)
# =====================================================================
def client_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 قسم الرصيد والكاش", callback_data="sec:balance")],
        [InlineKeyboardButton(text="🎮 قسم شحن الألعاب", callback_data="sec:games")],
        [InlineKeyboardButton(text="💬 قسم تطبيقات الشات", callback_data="sec:chat")],
        [InlineKeyboardButton(text="📦 قسم الحسابات الجاهزة", callback_data="sec:accounts")],
        [InlineKeyboardButton(text="🚀 قسم السوشيال ميديا", callback_data="sec:social")],
        [InlineKeyboardButton(text="💳 المحفظة والشحن", callback_data="client:wallet")],
        [InlineKeyboardButton(text="🛠 الدعم الفني", callback_data="sec:support")]
    ])

@dp.message(CommandStart())
@dp.message(F.text == "📋 القائمة الرئيسية")
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    u = await WalletService.get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    if u[4] == 1:
        await message.answer("⛔ حسابك محظور من استخدام البوت.")
        return

    rank = "🌟 زبون دائم (VIP)" if u[3] == 1 else "👤 زبون عادي"
    text = (
        f"👋 <b>مرحباً بك في سوريا ستور (Syria Store)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏷 <b>الرتبة:</b> {rank}\n"
        f"💰 <b>رصيد المحفظة:</b> <code>{u[2]:,} ل.س</code>\n"
        f"🆔 <b>معرّفك:</b> <code>{u[0]}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"اختر القسم المطلوب للبدء فوراً:"
    )
    kb = client_main_kb()
    await message.answer(text, reply_markup=kb)

# ----------------- دورة شحن المحفظة -----------------
@dp.callback_query(F.data == "client:wallet")
async def wallet_home(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    u = await WalletService.get_or_create_user(cb.from_user.id)
    txt = (
        f"💳 <b>محفظتك الإلكترونية</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 الرصيد الحالي: <code>{u[2]:,} ل.س</code>\n\n"
        f"• يمكنك الشحن مسبقاً والشراء الفوري بضغطة زر دون انتظار تدقيق الإشعار في كل طلب."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ شحن رصيد المحفظة", callback_data="wallet:topup")],
        [InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_home")]
    ])
    await cb.message.edit_text(txt, reply_markup=kb)

@dp.callback_query(F.data == "wallet:topup")
async def wallet_topup_start(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(WalletFlow.amount)
    await cb.message.edit_text("💵 أدخل المبلغ الذي تريد إيداعه بالليرة السورية (أقل مبلغ 1,000 ل.س):")

@dp.message(WalletFlow.amount)
async def wallet_amt_rec(message: types.Message, state: FSMContext):
    try:
        amt = int(message.text.strip().replace(",", ""))
        if amt < 1000:
            await message.reply("⚠️️ الحد الأدنى للإيداع هو 1,000 ل.س:")
            return
        await state.update_data(dep_amt=amt)
        await state.set_state(WalletFlow.tx_code)
        await message.answer(
            f"🧾 <b>طلب شحن محفظة بقيمة: {amt:,} ل.س</b>\n\n"
            f"👤 الاسم: <code>{html.escape(SHAM_NAME)}</code>\n"
            f"🔗 العنوان: <code>{html.escape(SHAM_ADDR)}</code>\n\n"
            f"⚠️ قم بالتحويل، ثم <b>أرسل رقم العملية (Transaction ID) الخاص بشام كاش هنا</b> لمنع التكرار:"
        )
    except Exception:
        await message.reply("⚠️ يرجى إدخال مبلغ صحيح بالأرقام:")

@dp.message(WalletFlow.tx_code)
async def wallet_tx_rec(message: types.Message, state: FSMContext):
    tx_code = message.text.strip()
    # التحقق من أن رقم العملية غير مكرر
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT payment_id FROM payments WHERE sham_tx_id = ?", (tx_code,))
        if await cursor.fetchone():
            await message.reply("⛔ رقم العملية هذا مستخدم مسبقاً! يرجى إدخال رقم صحيح:")
            return

    await state.update_data(sham_tx=tx_code)
    await state.set_state(WalletFlow.receipt)
    await message.answer("📸 الآن أرسل صورة إشعار التحويل لتأكيد الإيداع:")

@dp.message(WalletFlow.receipt, F.photo)
async def wallet_receipt_rec(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amt = data["dep_amt"]
    tx_code = data["sham_tx"]
    pay_id = generate_uid("PAY")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO payments (payment_id, user_id, method, amount, sham_tx_id, receipt_file_id) VALUES (?, ?, 'SHAM_CASH', ?, ?, ?)",
            (pay_id, message.from_user.id, amt, tx_code, message.photo[-1].file_id)
        )
        await db.commit()

    u_info = f"@{html.escape(message.from_user.username)}" if message.from_user.username else "بدون"
    text_to_group = (
        f"💳 <b>إيداع جديد بالمحفظة قيد التدقيق:</b>\n"
        f"🆔 رقم الدفعة: <code>{pay_id}</code>\n"
        f"👤 الزبون: {u_info} (<code>{message.from_user.id}</code>)\n"
        f"💰 المبلغ المطلوب: <b>{amt:,} ل.س</b>\n"
        f"🧾 رقم العملية: <code>{html.escape(tx_code)}</code>\n"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ قبول وتغذية الرصيد", callback_data=f"adm_pay:ok:{pay_id}"),
            InlineKeyboardButton(text="❌ رفض", callback_data=f"adm_pay:no:{pay_id}")
        ]
    ])
    await bot.send_photo(GROUPS["wallet"], photo=message.photo[-1].file_id, caption=text_to_group, reply_markup=kb)
    await state.clear()
    await message.answer("✅ تم إرسال إشعار الإيداع للتدقيق، سيصلك إشعار فور تأكيده وشحن رصيدك!")

# ----------------- معالج الشراء والدفع الموحد -----------------
async def create_and_route_order(cb_or_msg, user_id: int, dept: str, service: str, target: str, price: int, state: FSMContext):
    """إنشاء الطلب في قاعدة البيانات وعرض خيارات الدفع الذكية"""
    ord_id = generate_uid("ORD")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO orders (order_id, user_id, department, service_name, target_data, price) VALUES (?, ?, ?, ?, ?, ?)",
            (ord_id, user_id, dept, service, target, price)
        )
        await db.commit()

    u = await WalletService.get_or_create_user(user_id)
    kb = []
    if u[2] >= price:
        kb.append([InlineKeyboardButton(text=f"⚡ خصم فوري من المحفظة ({price:,} ل.س)", callback_data=f"pay:w:{ord_id}")])
    kb.append([InlineKeyboardButton(text="💳 دفع يدوي شام كاش", callback_data=f"pay:m:{ord_id}")])
    kb.append([InlineKeyboardButton(text="❌ إلغاء الطلب", callback_data=f"pay:c:{ord_id}")])

    text = (
        f"🧾 <b>تفاصيل الطلب:</b> <code>{ord_id}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 الخدمة: <b>{html.escape(service)}</b>\n"
        f"🎯 البيانات: <code>{html.escape(target)}</code>\n"
        f"💰 المبلغ المطلوب: <b>{price:,} ل.س</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💳 رصيد محفظتك: <code>{u[2]:,} ل.س</code>\n\n"
        f"اختر وسيلة الدفع لإتمام طلبك:"
    )
    if isinstance(cb_or_msg, types.CallbackQuery):
        await cb_or_msg.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await cb_or_msg.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("pay:w:"))
async def pay_wallet_exec(cb: types.CallbackQuery):
    ord_id = cb.data.split(":")[2]
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id, department, service_name, target_data, price, status FROM orders WHERE order_id = ?", (ord_id,))
        order = await cursor.fetchone()

    if not order or order[5] != "PENDING_PAYMENT":
        await cb.answer("⚠️ الطلب غير صالح أو تمت معالجته مسبقاً!", show_alert=True)
        return

    user_id, dept, s_name, target, price = order[0], order[1], order[2], order[3], order[4]
    success = await WalletService.deduct_for_order(user_id, ord_id, price)
    if not success:
        await cb.answer("⚠️ رصيد محفظتك غير كافٍ!", show_alert=True)
        return

    # إرسال الطلب فوراً لمجموعة القسم المختص
    group_id = GROUPS.get(dept, GROUPS["balance"])
    u_info = f"@{html.escape(cb.from_user.username)}" if cb.from_user.username else "بدون"
    text_to_group = (
        f"⚡ <b>طلب جديد مدفوع بالمحفظة (جاهز للتنفيذ):</b>\n"
        f"🆔 رقم الطلب: <code>{ord_id}</code>\n"
        f"👤 الزبون: {u_info} (<code>{user_id}</code>)\n"
        f"📦 الخدمة: <b>{html.escape(s_name)}</b>\n"
        f"🎯 البيانات: <code>{html.escape(target)}</code>\n"
        f"💰 المبلغ المقتطع: <b>{price:,} ل.س</b>\n\n"
        f"💡 للرد على الزبون، قم بالرد المباشر (Reply) على هذه الرسالة."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ تم التنفيذ", callback_data=f"ord_act:done:{ord_id}"),
            InlineKeyboardButton(text="❌ إلغاء واسترجاع", callback_data=f"ord_act:ref:{ord_id}")
        ]
    ])
    await bot.send_message(group_id, text_to_group, reply_markup=kb)
    await cb.message.edit_text(
        f"✅ <b>تم خصم {price:,} ل.س من محفظتك بنجاح!</b>\n"
        f"تم تحويل طلبك <code>{ord_id}</code> إلى فريق التنفيذ بأولوية قصوى.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_home")]])
    )

@dp.callback_query(F.data.startswith("pay:m:"))
async def pay_manual_start(cb: types.CallbackQuery, state: FSMContext):
    ord_id = cb.data.split(":")[2]
    await state.update_data(current_order_id=ord_id)
    await state.set_state(ClientOrder.manual_receipt)
    pay_text = (
        f"💳 <b>بيانات الدفع عبر شام كاش:</b>\n"
        f"👤 الاسم: <code>{html.escape(SHAM_NAME)}</code>\n"
        f"🔗 العنوان: <code>{html.escape(SHAM_ADDR)}</code>\n\n"
        f"⚠️ قم بالتحويل ثم <b>أرسل صورة إشعار التحويل هنا فوراً</b>:"
    )
    if os.path.exists(QR_IMAGE_PATH):
        await cb.message.answer_photo(FSInputFile(QR_IMAGE_PATH), caption=pay_text)
    else:
        await cb.message.answer(pay_text)
    await cb.answer()

@dp.message(ClientOrder.manual_receipt, F.photo)
async def pay_manual_receipt_rec(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ord_id = data.get("current_order_id")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT department, service_name, target_data, price FROM orders WHERE order_id = ?", (ord_id,))
        order = await cursor.fetchone()

    dept, s_name, target, price = order[0], order[1], order[2], order[3]
    pay_id = generate_uid("PAY")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO payments (payment_id, order_id, user_id, method, amount, receipt_file_id) VALUES (?, ?, ?, 'SHAM_CASH', ?, ?)",
            (pay_id, ord_id, message.from_user.id, price, message.photo[-1].file_id)
        )
        await db.commit()

    group_id = GROUPS.get(dept, GROUPS["balance"])
    u_info = f"@{html.escape(message.from_user.username)}" if message.from_user.username else "بدون"
    text_to_group = (
        f"🔔 <b>طلب يدوي جديد قيد مراجعة الدفع:</b>\n"
        f"🆔 رقم الطلب: <code>{ord_id}</code>\n"
        f"🆔 دفعة: <code>{pay_id}</code>\n"
        f"👤 الزبون: {u_info} (<code>{message.from_user.id}</code>)\n"
        f"📦 الخدمة: <b>{html.escape(s_name)}</b>\n"
        f"🎯 البيانات: <code>{html.escape(target)}</code>\n"
        f"💰 المبلغ المطلوب: <b>{price:,} ل.س</b>\n"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ قبول وتأكيد التنفيذ", callback_data=f"ord_act:done:{ord_id}"),
            InlineKeyboardButton(text="❌ رفض الطلب", callback_data=f"ord_act:rej:{ord_id}")
        ]
    ])
    await bot.send_photo(group_id, photo=message.photo[-1].file_id, caption=text_to_group, reply_markup=kb)
    await state.clear()
    await message.answer("✅ تم إرسال إشعار الدفع للإدارة! سيتم إشعارك فور تدقيقه وتنفيذه.")

# =====================================================================
# 6. إجراءات الموظفين والمجموعات (Staff Order Actions)
# =====================================================================
@dp.callback_query(F.data.startswith("ord_act:"))
async def handle_staff_order_action(cb: types.CallbackQuery):
    _, action, ord_id = cb.data.split(":")
    async with aiosqlite.connect(DB_PATH) as db:
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
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE orders SET status = 'COMPLETED' WHERE order_id = ?", (ord_id,))
            await db.commit()
        await bot.send_message(cust_id, f"🎉 <b>تم تنفيذ طلبك بنجاح!</b>\n📦 الخدمة: <b>{html.escape(s_name)}</b>\n🆔 رقم الطلب: <code>{ord_id}</code>")
        if cb.message.caption:
            await cb.message.edit_caption(caption=cb.message.caption + "\n\n🟢 <b>تم التنفيذ بنجاح</b>", reply_markup=None)
        else:
            await cb.message.edit_text(text=cb.message.text + "\n\n🟢 <b>تم التنفيذ بنجاح</b>", reply_markup=None)

    elif action == "ref":
        success, uid, refunded_amt = await WalletService.refund(ord_id)
        if success:
            await bot.send_message(uid, f"↩️ <b>تم إلغاء الطلب {ord_id}</b> وإعادة مبلغ <b>{refunded_amt:,} ل.س</b> إلى محفظتك.")
            await cb.message.edit_text(text=cb.message.text + "\n\n🟡 <b>تم الإلغاء واسترجاع الرصيد للمحفظة</b>", reply_markup=None)
        else:
            await cb.answer("تعذر استرجاع المبلغ، قد يكون مسترجعاً مسبقاً!", show_alert=True)

    elif action == "rej":
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE orders SET status = 'REJECTED' WHERE order_id = ?", (ord_id,))
            await db.commit()
        await bot.send_message(cust_id, f"❌ نعتذر منك، تم رفض طلبك رقم <code>{ord_id}</code> لوجود خطأ في الإشعار أو البيانات.")
        if cb.message.caption:
            await cb.message.edit_caption(caption=cb.message.caption + "\n\n🔴 <b>تم رفض الطلب</b>", reply_markup=None)

@dp.callback_query(F.data.startswith("adm_pay:"))
async def handle_admin_payment_action(cb: types.CallbackQuery):
    _, act, pay_id = cb.data.split(":")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id, amount, status FROM payments WHERE payment_id = ?", (pay_id,))
        payment = await cursor.fetchone()

    if not payment or payment[2] != "UNDER_REVIEW":
        await cb.answer("⚠️ تمت معالجة هذه الدفعة مسبقاً!", show_alert=True)
        return

    u_id, amt = payment[0], payment[1]
    if act == "ok":
        await WalletService.deposit(u_id, amt, pay_id, "شحن محفظة عبر شام كاش")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE payments SET status = 'ACCEPTED' WHERE payment_id = ?", (pay_id,))
            await db.commit()
        u = await WalletService.get_or_create_user(u_id)
        await bot.send_message(u_id, f"🎉 <b>تم تأكيد إيداعك بنجاح!</b>\n➕ تمت إضافة: <b>{amt:,} ل.س</b>\n💳 رصيدك الحالي: <code>{u[2]:,} ل.س</code>")
        await cb.message.edit_caption(caption=cb.message.caption + f"\n\n🟢 <b>تم قبول الإيداع ({amt:,} ل.س)</b>", reply_markup=None)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE payments SET status = 'DECLINED' WHERE payment_id = ?", (pay_id,))
            await db.commit()
        await bot.send_message(u_id, f"❌ نعتذر منك، تم رفض إشعار الإيداع للدفعة <code>{pay_id}</code> لعدم تطابق التحويل.")
        await cb.message.edit_caption(caption=cb.message.caption + "\n\n🔴 <b>تم رفض الإيداع</b>", reply_markup=None)

# ----------------- ردود المشرفين في المجموعات -----------------
@dp.message(F.chat.id.in_(ALL_ADMIN_GROUPS), F.reply_to_message)
async def admin_group_direct_reply(message: types.Message):
    if not message.reply_to_message.from_user.is_bot:
        return
    orig = message.reply_to_message.text or message.reply_to_message.caption or ""
    match = re.search(r"\(<code>(\d+)</code>\)", orig)
    if match and message.text:
        cust_id = int(match.group(1))
        try:
            await bot.send_message(cust_id, f"💬 <b>رسالة من الإدارة بخصوص طلبك:</b>\n\n{html.escape(message.text)}")
            await message.reply("✅ تم تسليم الرد للعميل.")
        except Exception as e:
            await message.reply(f"⚠️ تعذر الإرسال: {e}")

# =====================================================================
# 7. لوحة الإدارة الشاملة (/admin)
# =====================================================================
@dp.message(Command("admin"))
async def admin_panel_start(message: types.Message):
    u = await WalletService.get_or_create_user(message.from_user.id)
    if u[5] != "ADMIN":
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 إحصائيات النظام", callback_data="adm:stats"), InlineKeyboardButton(text="👥 بحث عن مستخدم", callback_data="adm:find_user")],
        [InlineKeyboardButton(text="💵 تعديل رصيد مستخدم", callback_data="adm:edit_bal"), InlineKeyboardButton(text="💱 سعر صرف الدولار", callback_data="adm:set_rate")],
        [InlineKeyboardButton(text="📢 إذاعة جماعية", callback_data="adm:broadcast")],
        [InlineKeyboardButton(text="❌ إغلاق اللوحة", callback_data="adm:close")]
    ])
    await message.answer("⚙️ <b>لوحة التحكم الرئيسية للمدير (V2 Core):</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm:stats")
async def adm_stats_view(cb: types.CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        c1 = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await c1.fetchone())[0]
        c2 = await db.execute("SELECT COUNT(*) FROM orders")
        total_orders = (await c2.fetchone())[0]
        c3 = await db.execute("SELECT SUM(amount) FROM payments WHERE status = 'ACCEPTED'")
        total_income = (await c3.fetchone())[0] or 0

    txt = (
        f"📊 <b>إحصائيات المنصة:</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 إجمالي المستخدمين: <b>{total_users:,}</b>\n"
        f"📦 إجمالي الطلبات: <b>{total_orders:,}</b>\n"
        f"💰 إجمالي الإيداعات المقبولة: <b>{total_income:,} ل.س</b>\n"
    )
    await cb.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 رجوع", callback_data="adm:home")]]))

@dp.callback_query(F.data == "adm:home")
async def adm_home_return(cb: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 إحصائيات النظام", callback_data="adm:stats"), InlineKeyboardButton(text="👥 بحث عن مستخدم", callback_data="adm:find_user")],
        [InlineKeyboardButton(text="💵 تعديل رصيد مستخدم", callback_data="adm:edit_bal"), InlineKeyboardButton(text="💱 سعر صرف الدولار", callback_data="adm:set_rate")],
        [InlineKeyboardButton(text="📢 إذاعة جماعية", callback_data="adm:broadcast")],
        [InlineKeyboardButton(text="❌ إغلاق اللوحة", callback_data="adm:close")]
    ])
    await cb.message.edit_text("⚙️ <b>لوحة التحكم الرئيسية للمدير:</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm:close")
async def adm_close(cb: types.CallbackQuery):
    await cb.message.delete()

@dp.callback_query(F.data == "back_home")
async def back_to_home_cb(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    u = await WalletService.get_or_create_user(cb.from_user.id)
    rank = "🌟 زبون دائم (VIP)" if u[3] == 1 else "👤 زبون عادي"
    text = (
        f"👋 <b>مرحباً بك في سوريا ستور (Syria Store)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏷 <b>الرتبة:</b> {rank}\n"
        f"💰 <b>رصيد المحفظة:</b> <code>{u[2]:,} ل.س</code>\n"
        f"🆔 <b>معرّفك:</b> <code>{u[0]}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"اختر القسم المطلوب للبدء فوراً:"
    )
    await cb.message.edit_text(text, reply_markup=client_main_kb())

# =====================================================================
# 8. نموذج تجريبي لقسم الشحن (للتأكد من عمل دورة الطلب كاملة)
# =====================================================================
@dp.callback_query(F.data == "sec:games")
async def test_game_menu(cb: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔫 ببجي: 60 UC (15,000 ل.س)", callback_data="demo_buy:pubg_60:15000:ببجي 60 UC")],
        [InlineKeyboardButton(text="🔫 ببجي: 325 UC (75,000 ل.س)", callback_data="demo_buy:pubg_325:75000:ببجي 325 UC")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_home")]
    ])
    await cb.message.edit_text("اختر الباقة التجريبية لاختبار دورة الطلب:", reply_markup=kb)

@dp.callback_query(F.data.startswith("demo_buy:"))
async def test_game_buy(cb: types.CallbackQuery, state: FSMContext):
    _, code, price, title = cb.data.split(":")
    await state.update_data(demo_item=title, demo_price=int(price))
    await state.set_state(ClientOrder.inputting_data)
    await cb.message.edit_text(f"أدخل الآيدي (Player ID) واسمك داخل اللعبة لشحن <b>{title}</b>:")

@dp.message(ClientOrder.inputting_data)
async def test_game_input_done(message: types.Message, state: FSMContext):
    data = await state.get_data()
    item = data["demo_item"]
    price = data["demo_price"]
    target = message.text.strip()
    await state.clear()
    await create_and_route_order(message, message.from_user.id, "games", item, target, price, state)

# =====================================================================
# 9. نقطة الإقلاع والتشغيل
# =====================================================================
async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("🚀 Syria Store Core V2 Engine is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
