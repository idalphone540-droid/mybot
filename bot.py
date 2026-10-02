import asyncio
import logging
import os
import re
import sqlite3
from aiogram import Bot, Dispatcher, F, types
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
# يفضل وضع التوكن في متغيرات البيئة os.getenv("BOT_TOKEN")
BOT_TOKEN = "8774564171:AAE_kxJM-yZ97f52_dTGwnKTLyfvsARM5Ik"
ADMIN_ID = 123456789  # استبدله بآيدي الأدمن الأساسي

CHANNEL_ID = -1004492385043
CHANNEL_LINK = "https://t.me/SyriaStore_ch"

GROUPS = {
    "wallet": -1003984372814,   # إدارة المحفظة والمالية
    "balance": -1003745247353,  # إدارة الرصيد والكاش
    "games": -1004426615112,    # إدارة الألعاب والشات
    "accounts": -1003985654158, # إدارة الحسابات والاشتراكات
    "social": -1004411774893,   # إدارة السوشيال والأرقام
    "support": -1004420804667   # إدارة الدعم الفني
}

ALL_ADMIN_GROUPS = list(GROUPS.values())

SHAM_NAME = "سكينه حمود طه"
SHAM_ADDR = "be03739e320f3dfd318a1a7faebae16a"
QR_IMAGE_PATH = "qr_sham.jpg"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ----------------- قاعدة البيانات (المستخدمين والمحفظة) -----------------
conn = sqlite3.connect("bot_store.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance REAL DEFAULT 0.0,
    is_vip INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    val REAL
)
""")

cursor.execute("INSERT OR IGNORE INTO settings (key, val) VALUES ('dollar_rate', 150.0)")
cursor.execute("INSERT OR IGNORE INTO settings (key, val) VALUES ('num_whatsapp', 400.0)")
cursor.execute("INSERT OR IGNORE INTO settings (key, val) VALUES ('num_telegram', 300.0)")
conn.commit()

def get_user(user_id: int, username: str = ""):
    cursor.execute("SELECT user_id, username, balance, is_vip FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, username, balance, is_vip) VALUES (?, ?, 0.0, 0)", (user_id, username))
        conn.commit()
        return (user_id, username, 0.0, 0)
    return row

def update_user_balance(user_id: int, delta: float):
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (delta, user_id))
    cursor.execute("UPDATE users SET is_vip = 1 WHERE user_id=? AND balance > 0", (user_id,))
    conn.commit()

def get_setting(key: str) -> float:
    cursor.execute("SELECT val FROM settings WHERE key=?", (key,))
    row = cursor.fetchone()
    return row[0] if row else 0.0

def update_setting(key: str, val: float):
    cursor.execute("UPDATE settings SET val=? WHERE key=?", (val, key))
    conn.commit()

def persistent_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📋 القائمة الرئيسية")]],
        resize_keyboard=True,
        persistent=True
    )

# ----------------- فحص الاشتراك الإجباري -----------------
async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status not in ["left", "kicked"]
    except Exception as e:
        logging.error(f"خطأ في فحص الاشتراك: {e}")
        return True

def sub_check_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 اشترك في القناة أولاً", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="🔄 تم الاشتراك (تأكيد)", callback_data="check_subscription")]
    ])

def is_admin_or_group(user_id: int, chat_id: int) -> bool:
    return user_id == ADMIN_ID or chat_id in ALL_ADMIN_GROUPS

# ----------------- الكتالوج والبيانات -----------------
GOVERNORATES = [
    "دمشق", "ريف دمشق", "حمص", "ريف حمص", "حماة", "ريف حماة",
    "طرطوس", "درعا", "اللاذقية", "ريف اللاذقية", "حلب", "القامشلي",
    "الرقة", "دير الزور", "البوكمال", "الحسكة", "السويداء", "القنيطرة",
    "إدلب", "جبلة", "القلمون"
]

ACCOUNTS_LIST = [
    "Shahid VIP", "Watch It", "OSN+", "TOD TV", "Disney+", "Amazon Prime Video",
    "Apple TV+", "IPTV سنة", "IPTV 6 أشهر", "Spotify Premium", "YouTube Premium",
    "Anghami Plus", "SoundCloud Pro", "Deezer Premium", "Canva Pro سنة",
    "Canva Pro شهر", "Adobe Cloud", "TradingView Pro", "Duolingo Plus",
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
    "ff": [("100 جوهرة", 1.0), ("210 جوهرة", 2.0), ("530 جوهرة", 5.0), ("1080 جوهرة", 10.0), ("2200 جوهرة", 20.0), ("5600 جوهرة", 50.0)],
    "jawaker": [("15,000 توكنز", 1.5), ("50,000 توكنز", 4.0), ("150,000 توكنز", 10.0), ("باشا (شهر)", 6.0)],
    "coc": [("500 جوهرة", 5.0), ("1200 جوهرة", 10.0), ("2500 جوهرة", 20.0), ("6500 جوهرة", 50.0), ("14000 جوهرة", 100.0)]
}

# ----------------- الحالات FSM -----------------
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

# ----------------- بناء القوائم الرئيسية والفرعية -----------------
def main_menu_text_and_kb(user_id: int, username: str):
    u = get_user(user_id, username)
    rank = "🌟 زبون دائم (VIP)" if u[3] == 1 else "👤 زبون عادي"
    text = (
        f"👋 **أهلاً بك في متجر Syria Store المتكامل**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏷 **الرتبة:** {rank}\n"
        f"💳 **رصيد محفظتك:** `{u[2]:,.2f} ل.س`\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"اختر القسم المطلوب لتصفح الخدمات:"
    )
    kb = [
        [InlineKeyboardButton(text="📞 قسم الرصيد والكاش", callback_data="sec_balance")],
        [InlineKeyboardButton(text="🎮 قسم شحن الألعاب", callback_data="sec_games")],
        [InlineKeyboardButton(text="💬 قسم تطبيقات الشات", callback_data="sec_chat")],
        [InlineKeyboardButton(text="📦 قسم الحسابات والاشتراكات", callback_data="sec_accounts")],
        [InlineKeyboardButton(text="🚀 قسم السوشيال ميديا والإعلانات", callback_data="sec_social")],
        [InlineKeyboardButton(text="📱 قسم أرقام التفعيل", callback_data="sec_numbers")],
        [InlineKeyboardButton(text="💳 محفظتي وشحن الرصيد", callback_data="sec_wallet")],
        [InlineKeyboardButton(text="🛠 الدعم الفني والشكاوى", callback_data="sec_support")]
    ]
    return text, InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(F.text == "📋 القائمة الرئيسية")
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    if not await is_subscribed(message.from_user.id):
        await message.answer(
            "⚠️ عذراً عزيزي، يجب عليك الاشتراك في قناة البوت الرسمية أولاً لتتمكن من استخدام الخدمات:\n\n"
            "اضغط على الزر بالأسفل للاشتراك، ثم اضغط على زر (تم الاشتراك).",
            reply_markup=sub_check_keyboard()
        )
        return
    text, kb = main_menu_text_and_kb(message.from_user.id, message.from_user.username or "")
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")
    await message.answer("💡 استخدم الزر الثابت بالأسفل للعودة للقائمة دائماً.", reply_markup=persistent_keyboard())

@dp.callback_query(F.data == "check_subscription")
async def check_sub_cb(cb: types.CallbackQuery):
    if await is_subscribed(cb.from_user.id):
        try:
            await cb.message.delete()
        except Exception:
            pass
        text, kb = main_menu_text_and_kb(cb.from_user.id, cb.from_user.username or "")
        await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await cb.answer("❌ لم تقم بالاشتراك في القناة بعد! اشترك ثم اضغط تأكيد.", show_alert=True)

@dp.callback_query(F.data == "back_main")
async def back_to_main(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = main_menu_text_and_kb(cb.from_user.id, cb.from_user.username or "")
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await cb.message.answer(text, reply_markup=kb, parse_mode="Markdown")

# ----------------- قسم المحفظة والمالية -----------------
@dp.callback_query(F.data == "sec_wallet")
async def wallet_home(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    u = get_user(cb.from_user.id, cb.from_user.username or "")
    rank = "🌟 زبون دائم (VIP)" if u[3] == 1 else "👤 زبون عادي"
    txt = (
        f"💳 **محفظة سوريا ستور الإلكترونية:**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏷 **رتبة حسابك:** {rank}\n"
        f"💰 **رصيدك الحالي:** `{u[2]:,.2f} ليرة سورية`\n\n"
        f"💡 **مزايا شحن المحفظة (الزبون الدائم):**\n"
        f"• شراء فوري لأي خدمة بضغطة زر دون إرسال إشعارات في كل مرة.\n"
        f"• أولوية وسرعة فائقة في التنفيذ.\n"
        f"• الترقية التلقائية لحساب VIP.\n"
    )
    kb = [
        [InlineKeyboardButton(text="➕ شحن رصيد المحفظة", callback_data="wallet_deposit")],
        [InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_main")]
    ]
    await cb.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

@dp.callback_query(F.data == "wallet_deposit")
async def wallet_dep_start(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.wallet_deposit_amt)
    await cb.message.edit_text(
        "💵 أدخل المبلغ الذي ترغب في إيداعه بمحفظتك بالليرة السورية:\n"
        "(مثال: `50000` أو `100000`):",
        parse_mode="Markdown"
    )

@dp.message(OrderState.wallet_deposit_amt)
async def wallet_dep_amt_receive(message: types.Message, state: FSMContext):
    try:
        amt = float(message.text.strip().replace(",", ""))
        if amt < 500:
            await message.reply("⚠️ أقل مبلغ للشحن هو 500 ليرة سورية:")
            return
        await state.update_data(dep_amt=amt)
        await state.set_state(OrderState.wallet_deposit_receipt)
        txt = (
            f"🧾 **طلب شحن محفظة:**\n"
            f"• المبلغ المراد إيداعه: **{amt:,.2f} ل.س**\n\n"
            f"💳 **بيانات التحويل عبر شام كاش:**\n"
            f"👤 الاسم: `{SHAM_NAME}`\n"
            f"🔗 العنوان: `{SHAM_ADDR}`\n\n"
            f"⚠️ يرجى تحويل المبلغ ثم **رفع صورة إشعار التحويل هنا فوراً**."
        )
        if os.path.exists(QR_IMAGE_PATH):
            photo = FSInputFile(QR_IMAGE_PATH)
            await message.answer_photo(photo, caption=txt, parse_mode="Markdown")
        else:
            await message.answer(txt, parse_mode="Markdown")
    except Exception:
        await message.reply("⚠️ يرجى إدخال مبلغ صحيح بالأرقام:")

@dp.message(OrderState.wallet_deposit_receipt, F.photo)
async def wallet_dep_receipt_proc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amt = data.get("dep_amt", 0)
    user_info = f"@{message.from_user.username}" if message.from_user.username else "بدون يوزر"

    group_text = (
        f"💳 **إيداع جديد للمحفظة قيد المراجعة:**\n"
        f"👤 الزبون: {user_info} (`{message.from_user.id}`)\n"
        f"💰 المبلغ المطلوب شحنه: **{amt:,.2f} ل.س**\n"
    )
    kb = [
        [
            InlineKeyboardButton(text=f"✅ تأكيد الإيداع ({amt:,.0f} ل.س)", callback_data=f"wconf:{message.from_user.id}:{amt}"),
            InlineKeyboardButton(text="❌ رفض الإيداع", callback_data=f"wrej:{message.from_user.id}")
        ]
    ]
    await bot.send_photo(
        chat_id=GROUPS["wallet"],
        photo=message.photo[-1].file_id,
        caption=group_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="Markdown"
    )
    await state.clear()
    text, menu_kb = main_menu_text_and_kb(message.from_user.id, message.from_user.username or "")
    await message.answer(
        "✅ تم استلام إشعار الإيداع بنجاح وإرساله للمالية!\n"
        "سيتم شحن المحفظة فور تدقيق التحويل وستصلك رسالة تأكيد.",
        reply_markup=menu_kb
    )

@dp.callback_query(F.data.startswith("wconf:"))
async def wallet_admin_confirm(cb: types.CallbackQuery):
    if not is_admin_or_group(cb.from_user.id, cb.message.chat.id):
        await cb.answer("⛔ لا تملك صلاحية تنفيذ هذا الإجراء!", show_alert=True)
        return

    _, u_id, amt = cb.data.split(":")
    u_id = int(u_id)
    amt = float(amt)
    update_user_balance(u_id, amt)
    new_u = get_user(u_id)
    try:
        await bot.send_message(
            u_id,
            f"🎉 **مبروك! تم تأكيد إيداعك بنجاح!**\n\n"
            f"➕ المبلغ المضاف: **{amt:,.2f} ل.س**\n"
            f"💳 رصيد محفظتك الحالي: **{new_u[2]:,.2f} ل.س**\n"
            f"🌟 تم تفعيل ميزة الشراء الفوري كزبون دائم.",
            parse_mode="Markdown"
        )
        if cb.message.caption:
            await cb.message.edit_caption(caption=cb.message.caption + f"\n\n🟢 **تم تأكيد الشحن بنجاح ({amt:,.0f} ل.س)**", reply_markup=None)
    except Exception as e:
        await cb.answer(f"خطأ: {e}", show_alert=True)

@dp.callback_query(F.data.startswith("wrej:"))
async def wallet_admin_reject(cb: types.CallbackQuery):
    if not is_admin_or_group(cb.from_user.id, cb.message.chat.id):
        await cb.answer("⛔ لا تملك صلاحية تنفيذ هذا الإجراء!", show_alert=True)
        return

    u_id = int(cb.data.split(":")[1])
    try:
        await bot.send_message(u_id, "❌ نعتذر منك، تم رفض إشعار الإيداع لعدم تطابق التحويل.")
        if cb.message.caption:
            await cb.message.edit_caption(caption=cb.message.caption + "\n\n🔴 **تم رفض الإيداع**", reply_markup=None)
    except Exception as e:
        await cb.answer(f"خطأ: {e}", show_alert=True)

# ----------------- آلية الدفع الذكية -----------------
async def prompt_payment(message: types.Message, state: FSMContext, user_id: int):
    data = await state.get_data()
    price = data.get("price", 0)
    service = data.get("service", "")
    target = data.get("target", "")

    user = get_user(user_id)
    balance = user[2]

    kb = []
    if balance >= price:
        kb.append([InlineKeyboardButton(text=f"⚡ خصم فوري من المحفظة ({price:,.0f} ل.س)", callback_data="pay_wallet")])
    kb.append([InlineKeyboardButton(text="💳 دفع يدوي عبر شام كاش", callback_data="pay_manual")])
    kb.append([InlineKeyboardButton(text="🔙 إلغاء والرجوع", callback_data="back_main")])

    summary_text = (
        f"🧾 **ملخص تفاصيل طلبك:**\n"
        f"• الخدمة: **{service}**\n"
        f"• البيانات: `{target}`\n"
        f"• المبلغ المطلوب: **{price:,.2f} ل.س**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💳 رصيد محفظتك الحالي: **{balance:,.2f} ل.س**\n\n"
        f"اختر وسيلة الدفع التي تناسبك أدناه:"
    )
    await message.answer(summary_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

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

    user = get_user(cb.from_user.id)
    if user[2] < price:
        await cb.answer("⚠️ رصيد محفظتك غير كافٍ! اختر الدفع اليدوي أو اشحن محفظتك.", show_alert=True)
        return

    update_user_balance(cb.from_user.id, -price)
    new_user = get_user(cb.from_user.id)

    user_info = f"@{cb.from_user.username}" if cb.from_user.username else "بدون يوزر"
    order_info = (
        f"⚡ **طلب مدفوع ومقتطع من المحفظة (فوري):**\n"
        f"👤 الزبون: {user_info} (`{cb.from_user.id}`)\n"
        f"🏷 الخدمة: **{service}**\n"
        f"🎯 البيانات: `{target}`\n"
        f"💰 المبلغ المخصوم: **{price:,.2f} ل.س**\n"
        f"💳 رصيد المحفظة المتبقي: **{new_user[2]:,.2f} ل.س**\n\n"
        f"💡 للرد على الزبون، قم بالرد المباشر (Reply) على هذه الرسالة."
    )
    kb = [
        [
            InlineKeyboardButton(text="✅ تم التنفيذ", callback_data=f"done:{cb.from_user.id}"),
            InlineKeyboardButton(text="❌ إلغاء وإرجاع الرصيد", callback_data=f"refund:{cb.from_user.id}:{price}")
        ]
    ]

    await bot.send_message(group_id, order_info, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    await state.clear()

    text, menu_kb = main_menu_text_and_kb(cb.from_user.id, cb.from_user.username or "")
    await cb.message.edit_text(
        f"✅ **تم خصم {price:,.2f} ل.س من محفظتك بنجاح!**\n"
        f"تم تحويل طلبك للإدارة وجارٍ التنفيذ بأولوية قصوى.\n"
        f"💳 رصيدك المتبقي: `{new_user[2]:,.2f} ل.س`",
        reply_markup=menu_kb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "pay_manual")
async def manual_pay_prompt(cb: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    price = data.get("price", 0)
    pay_text = (
        f"💳 **بيانات التحويل عبر شام كاش:**\n"
        f"👤 الاسم: `{SHAM_NAME}`\n"
        f"🔗 العنوان: `{SHAM_ADDR}`\n"
        f"💰 المطلوب: **{price:,.2f} ليرة سورية**\n\n"
        f"⚠️ يرجى تحويل المبلغ ثم **رفع صورة إشعار التحويل هنا فوراً**."
    )
    await state.set_state(OrderState.waiting_receipt)
    if os.path.exists(QR_IMAGE_PATH):
        photo = FSInputFile(QR_IMAGE_PATH)
        await cb.message.answer_photo(photo, caption=pay_text, parse_mode="Markdown")
    else:
        await cb.message.answer(pay_text, parse_mode="Markdown")
    await cb.answer()

@dp.message(OrderState.waiting_receipt, F.photo)
async def receive_manual_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    sec = data.get("sec", "balance")
    group_id = GROUPS.get(sec, GROUPS["balance"])

    order_info = (
        f"🔔 **طلب يدوي جديد قيد المراجعة:**\n"
        f"👤 الزبون: @{message.from_user.username or 'بدون'} (`{message.from_user.id}`)\n"
        f"🏷 الخدمة: {data.get('service')}\n"
        f"🎯 البيانات: `{data.get('target')}`\n"
        f"💰 المبلغ المطلوب: **{data.get('price')} ل.س**\n\n"
        f"💡 للرد على الزبون، قم بالرد المباشر (Reply) على هذه الرسالة."
    )
    kb = [
        [
            InlineKeyboardButton(text="✅ تم التنفيذ", callback_data=f"done:{message.from_user.id}"),
            InlineKeyboardButton(text="❌ رفض الطلب", callback_data=f"rej:{message.from_user.id}")
        ]
    ]

    await bot.send_photo(
        chat_id=group_id,
        photo=message.photo[-1].file_id,
        caption=order_info,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="Markdown"
    )
    await state.clear()
    text, menu_kb = main_menu_text_and_kb(message.from_user.id, message.from_user.username or "")
    await message.answer(
        "✅ تم استلام إشعار الدفع وإرساله للإدارة. سيتم إشعارك فور اكتمال التنفيذ.",
        reply_markup=menu_kb
    )

@dp.callback_query(F.data.startswith("refund:"))
async def refund_wallet(cb: types.CallbackQuery):
    if not is_admin_or_group(cb.from_user.id, cb.message.chat.id):
        await cb.answer("⛔ لا تملك صلاحية!", show_alert=True)
        return

    _, u_id, amt = cb.data.split(":")
    u_id = int(u_id)
    amt = float(amt)
    update_user_balance(u_id, amt)
    try:
        await bot.send_message(u_id, f"↩️ تم إلغاء الطلب وإرجاع **{amt:,.2f} ل.س** إلى رصيد محفظتك.")
        if cb.message.caption:
            await cb.message.edit_caption(caption=cb.message.caption + "\n\n🟡 **تم الإلغاء واسترجاع المبلغ للمحفظة**", reply_markup=None)
        elif cb.message.text:
            await cb.message.edit_text(text=cb.message.text + "\n\n🟡 **تم الإلغاء واسترجاع المبلغ للمحفظة**", reply_markup=None)
    except Exception as e:
        await cb.answer(f"خطأ: {e}", show_alert=True)

# ----------------- قسم الرصيد والكاش -----------------
@dp.callback_query(F.data == "sec_balance")
async def balance_menu(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="🔴 سيريتل (Syriatel)", callback_data="net:syr")],
        [InlineKeyboardButton(text="🟡 إم تي إن (MTN)", callback_data="net:mtn")],
        [InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_main")]
    ]
    await cb.message.edit_text("اختر الشبكة المطلوبة:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("net:"))
async def net_menu(cb: types.CallbackQuery):
    net = cb.data.split(":")[1]
    name = "Syriatel" if net == "syr" else "MTN"
    kb = [
        [InlineKeyboardButton(text=f"📲 وحدات {name}", callback_data=f"bopt:{net}:units")],
        [InlineKeyboardButton(text=f"⛽ جملة {name} كازية", callback_data=f"bopt:{net}:station")],
        [InlineKeyboardButton(text=f"🧾 فواتير {name}", callback_data=f"bopt:{net}:invoice")],
        [InlineKeyboardButton(text=f"💵 كاش {name}", callback_data=f"bopt:{net}:cash")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="sec_balance")]
    ]
    await cb.message.edit_text(f"خدمات شبكة {name}:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("bopt:"))
async def handle_bopt(cb: types.CallbackQuery, state: FSMContext):
    _, net, opt = cb.data.split(":")
    net_name = "Syriatel" if net == "syr" else "MTN"

    if opt == "units":
        items = SYR_UNITS if net == "syr" else MTN_UNITS
        buttons = []
        for idx, (u, p) in enumerate(items):
            buttons.append(InlineKeyboardButton(text=f"{u} ⬅ {p}ل.س", callback_data=f"u_{net}_{idx}"))
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"net:{net}")])
        await cb.message.edit_text(f"اختر فئة وحدات {net_name}:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

    elif opt == "station":
        buttons = []
        for idx, (a, p) in enumerate(STATION_VALS):
            buttons.append(InlineKeyboardButton(text=f"فئة {a} ⬅ {p}ل.س", callback_data=f"s_{net}_{idx}"))
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"net:{net}")])
        await cb.message.edit_text(f"اختر فئة كازية {net_name}:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

    elif opt == "invoice":
        await state.update_data(sec="balance", service=f"فواتير {net_name}", net=net)
        if net == "syr":
            await state.set_state(OrderState.syr_invoice_num)
            await cb.message.edit_text("أدخل رقم فاتورة Syriatel:")
        else:
            await state.set_state(OrderState.mtn_invoice_num)
            await cb.message.edit_text("أدخل رقم فاتورة MTN:")

    elif opt == "cash":
        await state.update_data(sec="balance", service=f"كاش {net_name}", net=net)
        if net == "syr":
            await state.set_state(OrderState.syr_cash_amt)
            await cb.message.edit_text("أدخل كمية كاش Syriatel المطلوبة (أقل كمية 1,000 ل.س):")
        else:
            await state.set_state(OrderState.mtn_cash_amt)
            await cb.message.edit_text("أدخل كمية كاش MTN المطلوبة (أقل كمية 1,000 ل.س):")

@dp.callback_query(F.data.startswith("u_"))
async def select_unit(cb: types.CallbackQuery, state: FSMContext):
    _, net, idx = cb.data.split("_")
    items = SYR_UNITS if net == "syr" else MTN_UNITS
    u, p = items[int(idx)]
    await state.update_data(sec="balance", service=f"وحدات {net.upper()}", unit=u, price=p, net=net)
    if net == "syr":
        await state.set_state(OrderState.syr_units_phone)
        await cb.message.edit_text("أدخل رقم سيريتل المطلوب التحويل إليه (مؤلف من 10 خانات يبدأ بـ 09):")
    else:
        await state.set_state(OrderState.mtn_units_phone)
        await cb.message.edit_text("أدخل رقم MTN المطلوب التحويل إليه (مؤلف من 10 خانات يبدأ بـ 09):")

@dp.message(OrderState.syr_units_phone)
async def proc_syr_u_phone(message: types.Message, state: FSMContext):
    p = message.text.strip()
    if not (p.isdigit() and len(p) == 10 and p.startswith("09")):
        await message.reply("⚠️ رقم سيريتل يجب أن يكون مؤلفاً من 10 خانات ويبدأ بـ 09:")
        return
    await state.update_data(target=f"رقم سيريتل: {p}")
    await prompt_payment(message, state, message.from_user.id)

@dp.message(OrderState.mtn_units_phone)
async def proc_mtn_u_phone(message: types.Message, state: FSMContext):
    p = message.text.strip()
    if not (p.isdigit() and len(p) == 10 and p.startswith("09")):
        await message.reply("⚠️ رقم MTN يجب أن يكون مؤلفاً من 10 خانات ويبدأ بـ 09:")
        return
    await state.update_data(target=f"رقم MTN: {p}")
    await prompt_payment(message, state, message.from_user.id)

@dp.callback_query(F.data.startswith("s_"))
async def select_station(cb: types.CallbackQuery, state: FSMContext):
    _, net, idx = cb.data.split("_")
    a, p = STATION_VALS[int(idx)]
    await state.update_data(sec="balance", service=f"جملة كازية {net.upper()}", amount=a, price=p, net=net)
    if net == "syr":
        await state.set_state(OrderState.syr_station_code)
        await cb.message.edit_text("أدخل كود كازية Syriatel (مؤلف من 6 أرقام):")
    else:
        await state.set_state(OrderState.mtn_station_code)
        await cb.message.edit_text("أدخل كود كازية MTN:")

@dp.message(OrderState.syr_station_code)
async def proc_syr_st_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if not (code.isdigit() and len(code) == 6):
        await message.reply("⚠️ كود كازية سيريتل يجب أن يتكون من 6 أرقام حصراً:")
        return
    await state.update_data(st_code=code)
    await state.set_state(OrderState.syr_station_gov)
    buttons = [InlineKeyboardButton(text=g, callback_data=f"gov_syr:{g}") for g in GOVERNORATES]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    await message.answer("اختر المحافظة:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("gov_syr:"), OrderState.syr_station_gov)
async def proc_syr_st_gov(cb: types.CallbackQuery, state: FSMContext):
    gov = cb.data.split(":")[1]
    data = await state.get_data()
    target_info = f"كود كازية: {data.get('st_code')} | المحافظة: {gov}"
    await state.update_data(target=target_info)
    await prompt_payment_cb(cb, state)

@dp.message(OrderState.mtn_station_code)
async def proc_mtn_st_code(message: types.Message, state: FSMContext):
    await state.update_data(st_code=message.text.strip())
    await state.set_state(OrderState.mtn_station_num)
    await message.answer("أدخل رقم كازية MTN:")

@dp.message(OrderState.mtn_station_num)
async def proc_mtn_st_num(message: types.Message, state: FSMContext):
    await state.update_data(st_num=message.text.strip())
    await state.set_state(OrderState.mtn_station_gov)
    buttons = [InlineKeyboardButton(text=g, callback_data=f"gov_mtn:{g}") for g in GOVERNORATES]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    await message.answer("اختر المحافظة:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("gov_mtn:"), OrderState.mtn_station_gov)
async def proc_mtn_st_gov(cb: types.CallbackQuery, state: FSMContext):
    gov = cb.data.split(":")[1]
    data = await state.get_data()
    target_info = f"كود: {data.get('st_code')} | رقم: {data.get('st_num')} | المحافظة: {gov}"
    await state.update_data(target=target_info)
    await prompt_payment_cb(cb, state)

@dp.message(OrderState.syr_invoice_num)
async def proc_syr_inv_num(message: types.Message, state: FSMContext):
    await state.update_data(inv_num=message.text.strip())
    await state.set_state(OrderState.syr_invoice_amt)
    await message.answer("أدخل قيمة الفاتورة بالليرة السورية:")

@dp.message(OrderState.syr_invoice_amt)
async def proc_syr_inv_amt(message: types.Message, state: FSMContext):
    try:
        amt = float(message.text.strip())
        final_price = round(amt * 1.05, 2)
        data = await state.get_data()
        await state.update_data(target=f"فاتورة سيريتل: {data.get('inv_num')} | القيمة: {amt}", price=final_price)
        await prompt_payment(message, state, message.from_user.id)
    except Exception:
        await message.reply("⚠️ أدخل قيمة صحيحة بالأرقام:")

@dp.message(OrderState.mtn_invoice_num)
async def proc_mtn_inv_num(message: types.Message, state: FSMContext):
    await state.update_data(inv_num=message.text.strip())
    await state.set_state(OrderState.mtn_invoice_amt)
    await message.answer("أدخل قيمة الفاتورة بالليرة السورية:")

@dp.message(OrderState.mtn_invoice_amt)
async def proc_mtn_inv_amt(message: types.Message, state: FSMContext):
    try:
        amt = float(message.text.strip())
        final_price = round(amt * 1.05, 2)
        data = await state.get_data()
        await state.update_data(target=f"فاتورة MTN: {data.get('inv_num')} | القيمة: {amt}", price=final_price)
        await prompt_payment(message, state, message.from_user.id)
    except Exception:
        await message.reply("⚠️ أدخل قيمة صحيحة بالأرقام:")

@dp.message(OrderState.syr_cash_amt)
async def proc_syr_cash_amt(message: types.Message, state: FSMContext):
    try:
        amt = float(message.text.strip())
        if amt < 1000:
            await message.reply("⚠️ أقل كمية هي 1,000 ل.س:")
            return
        final_price = round(amt * 1.05, 2)
        await state.update_data(price=final_price, amount=amt)
        await state.set_state(OrderState.syr_cash_id)
        await message.answer("أدخل معرّف Player-ID لاستلام كاش Syriatel:")
    except Exception:
        await message.reply("⚠️ أدخل قيمة صحيحة بالأرقام:")

@dp.message(OrderState.syr_cash_id)
async def proc_syr_cash_id(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(target=f"Player-ID: {message.text.strip()} | الكمية: {data.get('amount')}")
    await prompt_payment(message, state, message.from_user.id)

@dp.message(OrderState.mtn_cash_amt)
async def proc_mtn_cash_amt(message: types.Message, state: FSMContext):
    try:
        amt = float(message.text.strip())
        if amt < 1000:
            await message.reply("⚠️ أقل كمية هي 1,000 ل.س:")
            return
        final_price = round(amt * 1.05, 2)
        await state.update_data(price=final_price, amount=amt)
        await state.set_state(OrderState.mtn_cash_num)
        await message.answer("أدخل رقم كاش MTN المطلوب التحويل إليه:")
    except Exception:
        await message.reply("⚠️ أدخل قيمة صحيحة بالأرقام:")

@dp.message(OrderState.mtn_cash_num)
async def proc_mtn_cash_num(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(target=f"رقم كاش MTN: {message.text.strip()} | الكمية: {data.get('amount')}")
    await prompt_payment(message, state, message.from_user.id)

# ----------------- قسم شحن الألعاب -----------------
@dp.callback_query(F.data == "sec_games")
async def games_menu(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="🔫 ببجي (PUBG)", callback_data="game:pubg")],
        [InlineKeyboardButton(text="🔥 فري فاير (Free Fire)", callback_data="game:ff")],
        [InlineKeyboardButton(text="🃏 جواكر (Jawaker)", callback_data="game:jawaker")],
        [InlineKeyboardButton(text="⚔️ كلاش أوف كلانس (CoC)", callback_data="game:coc")],
        [InlineKeyboardButton(text="🎮 باقي الألعاب (31 لعبة) [طلب تسعير]", callback_data="quote:game")],
        [InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_main")]
    ]
    await cb.message.edit_text("اختر اللعبة المطلوبة:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("game:"))
async def game_packs_view(cb: types.CallbackQuery):
    g_key = cb.data.split(":")[1]
    rate = get_setting("dollar_rate")
    buttons = []
    for idx, (p_name, p_usd) in enumerate(GAME_PACKS[g_key]):
        price_syr = round(p_usd * rate, 2)
        buttons.append([InlineKeyboardButton(text=f"{p_name} ⬅ {price_syr} ل.س", callback_data=f"buyg:{g_key}:{idx}")])
    buttons.append([InlineKeyboardButton(text="🔙 رجوع للألعاب", callback_data="sec_games")])
    await cb.message.edit_text("اختر الباقة المطلوبة:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("buyg:"))
async def buy_game_pack(cb: types.CallbackQuery, state: FSMContext):
    _, g_key, idx = cb.data.split(":")
    p_name, p_usd = GAME_PACKS[g_key][int(idx)]
    rate = get_setting("dollar_rate")
    price_syr = round(p_usd * rate, 2)
    await state.update_data(sec="games", service=f"شحن {g_key.upper()} ({p_name})", price=price_syr)
    await state.set_state(OrderState.entering_game_data)
    await cb.message.edit_text("أدخل الآيدي (Player ID) واسم حسابك في اللعبة:")

@dp.message(OrderState.entering_game_data)
async def proc_game_data(message: types.Message, state: FSMContext):
    await state.update_data(target=f"آيدي اللعبة: {message.text.strip()}")
    await prompt_payment(message, state, message.from_user.id)

# ----------------- قسم تطبيقات الشات -----------------
@dp.callback_query(F.data == "sec_chat")
async def chat_menu(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="🌟 Soul Star (كوينز × 0.025)", callback_data="chat:soulstar")],
        [InlineKeyboardButton(text="❄️ Soulchill (كريستال × 0.30)", callback_data="chat:soulchill")],
        [InlineKeyboardButton(text="💬 IMO (ألماس)", callback_data="chat:imo")],
        [InlineKeyboardButton(text="🗣 Talsa chat (كوينز × 0.02)", callback_data="chat:talsa")],
        [InlineKeyboardButton(text="🔍 باقي التطبيقات (186 تطبيق) [تسعير]", callback_data="quote:chat")],
        [InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_main")]
    ]
    await cb.message.edit_text("اختر تطبيق الشات المطلوب:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("chat:"))
async def chat_calc_prompt(cb: types.CallbackQuery, state: FSMContext):
    c_key = cb.data.split(":")[1]
    await state.update_data(sec="games", chat_app=c_key)
    await state.set_state(OrderState.entering_chat_qty)
    await cb.message.edit_text("أدخل (الآيدي) متبوعاً بـ (الكمية المطلوبة):\nمثال: `123456 5000`", parse_mode="Markdown")

@dp.message(OrderState.entering_chat_qty)
async def proc_chat_calc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    c_key = data.get("chat_app")
    try:
        parts = message.text.strip().split()
        u_id = parts[0]
        qty = float(parts[1])
        if c_key == "soulstar":
            price = round(qty * 0.025, 2)
            s_name = "Soul Star"
        elif c_key == "soulchill":
            price = round(qty * 0.30, 2)
            s_name = "Soulchill"
        elif c_key == "talsa":
            price = round(qty * 0.02, 2)
            s_name = "Talsa chat"
        else:
            price = round(qty * 1.0, 2)
            s_name = "IMO"

        await state.update_data(service=f"شحن {s_name}", target=f"الآيدي: {u_id} | الكمية: {qty}", price=price)
        await prompt_payment(message, state, message.from_user.id)
    except Exception:
        await message.reply("⚠️ أرسل الآيدي ثم الكمية وبينهما مسافة بشكل صحيح.")

# ----------------- قسم الحسابات والاشتراكات -----------------
@dp.callback_query(F.data == "sec_accounts")
async def accounts_menu(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="🤖 ChatGPT عادي (1,700 ل.س - شهر)", callback_data="acc:ChatGPT عادي:1700")],
        [InlineKeyboardButton(text="⚡ ChatGPT Go (2,000 ل.س - ضمان)", callback_data="acc:ChatGPT Go:2000")],
        [InlineKeyboardButton(text="💎 ChatGPT Plus شهر (3,500 ل.س)", callback_data="acc:ChatGPT Plus شهر:3500")],
        [InlineKeyboardButton(text="🎬 Netflix شهر جهاز واحد (800 ل.س)", callback_data="acc:Netflix شهر:800")],
        [InlineKeyboardButton(text="🍿 Netflix سنة جهاز واحد (5,000 ل.س)", callback_data="acc:Netflix سنة:5000")],
        [InlineKeyboardButton(text="📋 باقي الحسابات (27 خدمة) [اختر من القائمة]", callback_data="acc_page:0")],
        [InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_main")]
    ]
    await cb.message.edit_text("اختر الحساب الجاهز المطلوب:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

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

    buttons.append([InlineKeyboardButton(text="🔙 رجوع للحسابات", callback_data="sec_accounts")])
    await cb.message.edit_text(f"اختر الحساب المطلوب (صفحة {page+1} من 5):", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

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
    await cb.message.edit_text(
        f"لقد اخترت: **{acc_name}**\n\nاختر المدة المطلوبة بالضغط على الزر أدناه:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("acc_dur:"))
async def account_duration_finish(cb: types.CallbackQuery, state: FSMContext):
    dur = cb.data.split(":")[1]
    data = await state.get_data()
    acc_name = data.get("selected_acc_name", "حساب مميز")

    group_id = GROUPS["accounts"]
    user_info = f"@{cb.from_user.username}" if cb.from_user.username else "بدون يوزر"
    text_to_group = (
        f"📩 **طلب حساب جاهز:**\n"
        f"👤 الزبون: {user_info} (`{cb.from_user.id}`)\n"
        f"🏷 الحساب: **{acc_name}**\n"
        f"⏳ المدة: **{dur}**\n\n"
        f"💡 لتسعير الطلب والرد على الزبون، قم بعمل رد (Reply) مباشر على هذه الرسالة."
    )
    await bot.send_message(group_id, text_to_group, parse_mode="Markdown")
    text, menu_kb = main_menu_text_and_kb(cb.from_user.id, cb.from_user.username or "")
    await cb.message.edit_text(
        f"✅ تم إرسال طلبك لحساب **{acc_name}** ({dur}) للإدارة بنجاح.\n"
        f"سيتم الرد عليك هنا بالتفاصيل والسعر قريباً.",
        reply_markup=menu_kb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("acc:"))
async def acc_confirm(cb: types.CallbackQuery, state: FSMContext):
    _, name, price = cb.data.split(":")
    await state.update_data(sec="accounts", service=f"حساب {name}", price=float(price), target="حساب رسمي مع الضمان")
    await prompt_payment_cb(cb, state)

# ----------------- قسم السوشيال ميديا والإعلانات والأرقام -----------------
@dp.callback_query(F.data == "sec_social")
async def social_menu(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="📘 خدمات فيسبوك", callback_data="soc:fb")],
        [InlineKeyboardButton(text="📸 خدمات إنستغرام", callback_data="soc:ig")],
        [InlineKeyboardButton(text="✈ خدمات تلغرام", callback_data="soc:tg")],
        [InlineKeyboardButton(text="📢 إعلانات ممولة فيسبوك", callback_data="soc:ads")],
        [InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_main")]
    ]
    await cb.message.edit_text("اختر منصة السوشيال ميديا:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("soc:"))
async def soc_platforms(cb: types.CallbackQuery):
    plat = cb.data.split(":")[1]
    if plat == "fb":
        kb = [
            [InlineKeyboardButton(text="👁 مشاهدات 10k (500 ل.س)", callback_data="sbuy:fb:مشاهدات 10k:500")],
            [InlineKeyboardButton(text="👍 لايكات منشور 5k (700 ل.س)", callback_data="sbuy:fb:لايكات منشور 5k:700")],
            [InlineKeyboardButton(text="👥 متابعين 1k (150 ل.س)", callback_data="sbuy:fb:متابعين 1k:150")],
            [InlineKeyboardButton(text="💬 تعليقات عربية 200 (250 ل.س)", callback_data="sbuy:fb:تعليقات عربية 200:250")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="sec_social")]
        ]
        await cb.message.edit_text("باقات فيسبوك:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    elif plat == "ig":
        kb = [
            [InlineKeyboardButton(text="👁 مشاهدات 500k (300 ل.س)", callback_data="sbuy:ig:مشاهدات 500k:300")],
            [InlineKeyboardButton(text="❤️ لايكات 5k (700 ل.س)", callback_data="sbuy:ig:لايكات 5k:700")],
            [InlineKeyboardButton(text="👥 متابعين أجنبي 1k (700 ل.س)", callback_data="sbuy:ig:متابعين أجنبي 1k:700")],
            [InlineKeyboardButton(text="👥 متابعين عربي 1k (1,350 ل.س)", callback_data="sbuy:ig:متابعين عربي 1k:1350")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="sec_social")]
        ]
        await cb.message.edit_text("باقات إنستغرام:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    elif plat == "tg":
        kb = [
            [InlineKeyboardButton(text="👥 أعضاء قنوات 1k (400 ل.س)", callback_data="sbuy:tg:أعضاء 1k:400")],
            [InlineKeyboardButton(text="🔥 تفاعلات 1k (150 ل.س)", callback_data="sbuy:tg:تفاعلات 1k:150")],
            [InlineKeyboardButton(text="👁 مشاهدات 5k (200 ل.س)", callback_data="sbuy:tg:مشاهدات 5k:200")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="sec_social")]
        ]
        await cb.message.edit_text("باقات تلغرام:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    elif plat == "ads":
        buttons = []
        for d, p in [
            (1, 600), (2, 1100), (3, 1500), (4, 2000), (5, 2500),
            (6, 3000), (7, 3600), (10, 5000)
        ]:
            buttons.append(InlineKeyboardButton(text=f"إعلان {d} أيام ⬅ {p}ل.س", callback_data=f"ad_f:{d}:{p}"))
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        rows.append([InlineKeyboardButton(text="⚙ مدة مخصصة (200 ل.س/يوم)", callback_data="ad_c")])
        rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="sec_social")])
        await cb.message.edit_text("اختر مدة الإعلان الممول:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("sbuy:"))
async def soc_buy(cb: types.CallbackQuery, state: FSMContext):
    _, plat, name, price = cb.data.split(":")
    await state.update_data(sec="social", service=f"{plat.upper()} - {name}", price=float(price))
    await state.set_state(OrderState.entering_social_link)
    await cb.message.edit_text("أرسل الآن رابط الحساب أو المنشور المطلوب:")

@dp.message(OrderState.entering_social_link)
async def proc_soc_link(message: types.Message, state: FSMContext):
    await state.update_data(target=message.text.strip())
    await prompt_payment(message, state, message.from_user.id)

@dp.callback_query(F.data.startswith("ad_f:"))
async def ad_f_click(cb: types.CallbackQuery, state: FSMContext):
    _, d, p = cb.data.split(":")
    await state.update_data(sec="social", service=f"إعلان ممول ({d} أيام)", price=float(p))
    await state.set_state(OrderState.entering_ad_phone)
    await cb.message.edit_text("أدخل رقم هاتفك للتواصل وتجهيز تفاصيل الإعلان:")

@dp.callback_query(F.data == "ad_c")
async def ad_c_click(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.entering_custom_ad_days)
    await cb.message.edit_text("أدخل عدد الأيام المطلوبة (اليوم = 200 ل.س):")

@dp.message(OrderState.entering_custom_ad_days)
async def proc_c_ad(message: types.Message, state: FSMContext):
    try:
        days = int(message.text.strip())
        price = days * 200
        await state.update_data(sec="social", service=f"إعلان مخصص ({days} أيام)", price=price)
        await state.set_state(OrderState.entering_ad_phone)
        await message.answer("أدخل رقم هاتفك للتواصل:")
    except Exception:
        await message.reply("⚠️ أدخل عدداً صحيحاً بالأرقام:")

@dp.message(OrderState.entering_ad_phone)
async def proc_ad_phone(message: types.Message, state: FSMContext):
    await state.update_data(target=f"رقم تواصل الإعلان: {message.text.strip()}")
    await prompt_payment(message, state, message.from_user.id)

@dp.callback_query(F.data == "sec_numbers")
async def numbers_menu(cb: types.CallbackQuery):
    p_wa = get_setting("num_whatsapp")
    p_tg = get_setting("num_telegram")
    kb = [
        [InlineKeyboardButton(text=f"🟢 رقم واتساب أجنبي ({p_wa} ل.س)", callback_data="buyn:whatsapp")],
        [InlineKeyboardButton(text=f"🔵 رقم تلغرام أمريكي ({p_tg} ل.س)", callback_data="buyn:telegram")],
        [InlineKeyboardButton(text="📱 رقم تيك توك [طلب تسعير]", callback_data="quote:num_tiktok")],
        [InlineKeyboardButton(text="🌐 تفعيل غوغل [طلب تسعير]", callback_data="quote:num_google")],
        [InlineKeyboardButton(text="🍎 تفعيل آبل [طلب تسعير]", callback_data="quote:num_apple")],
        [InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_main")]
    ]
    await cb.message.edit_text("قسم أرقام التفعيل:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("buyn:"))
async def buy_num_fast(cb: types.CallbackQuery, state: FSMContext):
    target = cb.data.split(":")[1]
    price = get_setting(f"num_{target}")
    name = "واتساب أجنبي" if target == "whatsapp" else "تلغرام أمريكي"
    await state.update_data(sec="social", service=f"رقم {name}", price=price, target="رابط تفعيل")
    await prompt_payment_cb(cb, state)

# ----------------- طلبات التسعير التفاعلية -----------------
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
    await state.set_state(QuoteState.entering_quote_text)
    await cb.message.answer(
        f"✍️ يرجى كتابة تفاصيل طلبك الآن بالتفصيل:\n"
        f"(اسم الخدمة أو اللعبة + الآيدي + الكمية المطلوبة):"
    )
    await cb.answer()

@dp.message(QuoteState.entering_quote_text)
async def generic_quote_receive(message: types.Message, state: FSMContext):
    data = await state.get_data()
    sec = data.get("q_sec", "games")
    label = data.get("q_label", "طلب تسعير")
    group_id = GROUPS.get(sec, GROUPS["games"])

    user_info = f"@{message.from_user.username}" if message.from_user.username else "بدون يوزر"
    text_to_group = (
        f"📩 **{label}:**\n"
        f"👤 الزبون: {user_info} (`{message.from_user.id}`)\n"
        f"📝 **التفاصيل:**\n{message.text}\n\n"
        f"💡 لتسعير الطلب والرد على الزبون، قم بعمل رد (Reply) مباشر على هذه الرسالة واكتب السعر والتفاصيل."
    )
    await bot.send_message(group_id, text_to_group, parse_mode="Markdown")
    await state.clear()
    text, menu_kb = main_menu_text_and_kb(message.from_user.id, message.from_user.username or "")
    await message.answer(
        "✅ تم استلام طلبك وإرساله للإدارة بنجاح. سيتم مراجعته والرد عليك هنا قريباً بالسعر.",
        reply_markup=menu_kb
    )

# ----------------- معالجة الردود من الإدارة في جميع المجموعات -----------------
@dp.message(F.chat.id.in_(ALL_ADMIN_GROUPS), F.reply_to_message)
async def admin_group_reply_handler(message: types.Message):
    orig = message.reply_to_message.text or message.reply_to_message.caption or ""
    # استخراج الآيدي بين علامات (` و `)
    match = re.search(r"\(`(\d+)`\)", orig)
    if match:
        try:
            cust_id = int(match.group(1))
            text, menu_kb = main_menu_text_and_kb(cust_id, "")
            await bot.send_message(
                cust_id,
                f"💬 **إشعار من الإدارة بخصوص طلبك:**\n\n{message.text}",
                reply_markup=menu_kb
            )
            await message.reply("✅ تم إيصال رسالتك إلى الزبون بنجاح.")
        except Exception as e:
            await message.reply(f"⚠️ فشل إرسال الرد للزبون: {e}")

# ----------------- إدارة الطلبات والدعم -----------------
@dp.callback_query(F.data.startswith("done:"))
async def order_done(cb: types.CallbackQuery):
    if not is_admin_or_group(cb.from_user.id, cb.message.chat.id):
        await cb.answer("⛔ لا تملك صلاحية!", show_alert=True)
        return

    u_id = int(cb.data.split(":")[1])
    try:
        text, menu_kb = main_menu_text_and_kb(u_id, "")
        await bot.send_message(u_id, "✅ تم تنفيذ طلبك بنجاح! شكراً لتعاملك معنا.", reply_markup=menu_kb)
        if cb.message.caption:
            await cb.message.edit_caption(caption=cb.message.caption + "\n\n🟢 **تم التنفيذ**", reply_markup=None)
        elif cb.message.text:
            await cb.message.edit_text(text=cb.message.text + "\n\n🟢 **تم التنفيذ**", reply_markup=None)
    except Exception as e:
        await cb.answer(f"خطأ: {e}", show_alert=True)

@dp.callback_query(F.data.startswith("rej:"))
async def order_reject(cb: types.CallbackQuery):
    if not is_admin_or_group(cb.from_user.id, cb.message.chat.id):
        await cb.answer("⛔ لا تملك صلاحية!", show_alert=True)
        return

    u_id = int(cb.data.split(":")[1])
    try:
        text, menu_kb = main_menu_text_and_kb(u_id, "")
        await bot.send_message(u_id, "❌ نعتذر منك، تم رفض الطلب لوجود خطأ في الإشعار أو البيانات.", reply_markup=menu_kb)
        if cb.message.caption:
            await cb.message.edit_caption(caption=cb.message.caption + "\n\n🔴 **تم الرفض**", reply_markup=None)
        elif cb.message.text:
            await cb.message.edit_text(text=cb.message.text + "\n\n🔴 **تم الرفض**", reply_markup=None)
    except Exception as e:
        await cb.answer(f"خطأ: {e}", show_alert=True)

@dp.callback_query(F.data == "sec_support")
async def support_start(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.support_ticket)
    await cb.message.edit_text("اكتب استفسارك أو مشكلتك بالتفصيل وسيقوم فريق الدعم بالرد عليك هنا:")

@dp.message(OrderState.support_ticket)
async def support_forward(message: types.Message, state: FSMContext):
    txt = (
        f"📩 **تذكرة دعم فني جديدة:**\n"
        f"👤 الزبون: @{message.from_user.username or 'بدون'} (`{message.from_user.id}`)\n\n"
        f"📝 الرسالة:\n{message.text}\n\n"
        f"💡 للرد على الزبون، قم بعمل رد (Reply) مباشر على هذه الرسالة."
    )
    await bot.send_message(GROUPS["support"], txt, parse_mode="Markdown")
    await state.clear()
    text, menu_kb = main_menu_text_and_kb(message.from_user.id, message.from_user.username or "")
    await message.answer(
        "✅ تم إرسال رسالتك للدعم الفني، سنرد عليك هنا بأقرب وقت.",
        reply_markup=menu_kb
    )

# ----------------- أوامر الأدمن الأساسية -----------------
@dp.message(Command("add_balance"))
async def admin_add_bal(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, u_id, amt = message.text.split()
        update_user_balance(int(u_id), float(amt))
        await message.reply(f"✅ تم إضافة {amt} ل.س إلى حساب المستخدم {u_id}")
    except Exception:
        await message.reply("⚠️ الاستخدام: `/add_balance [user_id] [amount]`")

@dp.message(Command("rate"))
async def set_dollar(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        val = float(message.text.split()[1])
        update_setting("dollar_rate", val)
        await message.reply(f"✅ تم تحديث سعر صرف الدولار: {val} ل.س")
    except Exception:
        await message.reply("⚠️ الاستخدام: `/rate 150`")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
