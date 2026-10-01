File "/home/runner/work/mybot/mybot/bot.py", line 471
    ][span_23](start_span)[span_23](end_span)
NameError: name 'span_23' is not defined
```[span_2](start_span)[span_2](end_span)

أنت ما زلت تشغّل النسخة القديمة من ملف `bot.py` التي تحتوي على وسوم نصية تالفة مثل `[span_23]` و `[span_20]` و `[span_21]` دخلت أثناء النسخ القديم وتسببت في توقف الكود[span_3](start_span)[span_3](end_span).

---

### طريقة الحل خطوة بخطوة:

1. ادخل إلى تبويب **Code** في أعلى المستودع.
2. اضغط على ملف **`bot.py`**.
3. اضغط على أيقونة **القلم (Edit this file)**.
4. امسح كل السطور الموجودة في الملف حتى يصبح فارغاً تماماً.
5. انسخ الكود التالي النظيف والمعدل بالكامل والصقه:

```python
import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    FSInputFile
)

BOT_TOKEN = "8774564171:AAFxpEXjd6BVSCMwYhE5Eg_7ZxiIN1yhHmI"
ADMIN_ID = 123456789

GROUPS = {
    "balance": -1003745247353,
    "games": -1004426615122,
    "accounts": -1003985654158,
    "social": -1004411774893,
    "support": -1004420804667
}

SHAM_NAME = "سكينه حمود طه"
SHAM_ADDR = "be03739e320f3dfd318a1a7faebae16a"
QR_IMAGE_PATH = "qr_sham.jpg"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

conn = sqlite3.connect("bot_system.db", check_same_thread=False)
cursor = conn.cursor()
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

def get_setting(key: str) -> float:
    cursor.execute("SELECT val FROM settings WHERE key=?", (key,))
    row = cursor.fetchone()
    return row[0] if row else 0.0

def update_setting(key: str, val: float):
    cursor.execute("UPDATE settings SET val=? WHERE key=?", (val, key))
    conn.commit()

class OrderState(StatesGroup):
    entering_phone_syr = State()
    entering_phone_mtn = State()
    entering_station_syr = State()
    entering_station_mtn = State()
    entering_invoice = State()
    entering_cash_amount = State()
    entering_cash_target = State()
    entering_game_data = State()
    entering_quote_details = State()
    entering_social_target = State()
    entering_ad_phone = State()
    entering_custom_ad_days = State()
    waiting_receipt = State()
    admin_sending_link = State()
    support_ticket = State()

def main_menu():
    kb = [
        [InlineKeyboardButton(text="📞 قسم الرصيد والكاش", callback_data="sec_balance")],
        [InlineKeyboardButton(text="🎮 قسم شحن الألعاب", callback_data="sec_games")],
        [InlineKeyboardButton(text="💬 قسم تطبيقات الشات", callback_data="sec_chat")],
        [InlineKeyboardButton(text="📦 قسم الحسابات الجاهزة", callback_data="sec_accounts")],
        [InlineKeyboardButton(text="🚀 قسم السوشيال ميديا والإعلانات", callback_data="sec_social")],
        [InlineKeyboardButton(text="📱 قسم أرقام التفعيل", callback_data="sec_numbers")],
        [InlineKeyboardButton(text="🛠 الدعم الفني والشكاوى", callback_data="sec_support")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer("👋 أهلاً بك في بوت الخدمات المتكامل.\nاختر القسم المطلوب من القائمة أدناه:", reply_markup=main_menu())

@dp.message(Command("rate"))
async def set_dollar(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        val = float(message.text.split()[1])
        update_setting("dollar_rate", val)
        await message.reply(f"✅ تم تحديث سعر صرف الدولار: {val} ل.س")
    except Exception:
        await message.reply("⚠️ الاستخدام: `/rate 150`")

@dp.message(Command("set_num"))
async def set_num(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        _, target, price = message.text.split()
        update_setting(f"num_{target}", float(price))
        await message.reply(f"✅ تم تحديث سعر رقم {target} إلى: {price} ل.س")
    except Exception:
        await message.reply("⚠️ الاستخدام: `/set_num whatsapp 400`")

@dp.callback_query(F.data == "back_main")
async def back_to_main(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("اختر القسم المطلوب أدناه:", reply_markup=main_menu())

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
        await state.update_data(sec="balance", service=f"فواتير {net_name}")
        await state.set_state(OrderState.entering_invoice)
        await cb.message.edit_text(f"أدخل رقم فاتورة {net_name} وقيمتها مفصولين بمسافة:\nمثال: `09XXXXXXXX 15000`", parse_mode="Markdown")

    elif opt == "cash":
        await state.update_data(sec="balance", service=f"كاش {net_name}", net=net)
        await state.set_state(OrderState.entering_cash_amount)
        await cb.message.edit_text(f"أدخل كمية كاش {net_name} المطلوبة (الحد الأدنى 1,000 ل.س):")

@dp.callback_query(F.data.startswith("u_"))
async def select_unit(cb: types.CallbackQuery, state: FSMContext):
    _, net, idx = cb.data.split("_")
    items = SYR_UNITS if net == "syr" else MTN_UNITS
    u, p = items[int(idx)]
    await state.update_data(sec="balance", service=f"وحدات {net.upper()}", unit=u, price=p, net=net)
    if net == "syr":
        await state.set_state(OrderState.entering_phone_syr)
        await cb.message.edit_text("أدخل رقم سيريتل مؤلف من 10 خانات (مثال: 0912345678):")
    else:
        await state.set_state(OrderState.entering_phone_mtn)
        await cb.message.edit_text("أدخل رقم MTN مؤلف من 10 خانات (مثال: 0944123456):")

@dp.message(OrderState.entering_phone_syr)
async def proc_phone_syr(message: types.Message, state: FSMContext):
    p = message.text.strip()
    if not (p.isdigit() and len(p) == 10 and p.startswith("09")):
        await message.reply("⚠️ الرقم غير صحيح! يجب أن يتكون من 10 خانات ويبدأ بـ 09:")
        return
    await state.update_data(target=p)
    await prompt_payment(message, state)

@dp.message(OrderState.entering_phone_mtn)
async def proc_phone_mtn(message: types.Message, state: FSMContext):
    p = message.text.strip()
    if not (p.isdigit() and len(p) == 10 and p.startswith("09")):
        await message.reply("⚠️ الرقم غير صحيح! يجب أن يتكون من 10 خانات ويبدأ بـ 09:")
        return
    await state.update_data(target=p)
    await prompt_payment(message, state)

@dp.callback_query(F.data.startswith("s_"))
async def select_station(cb: types.CallbackQuery, state: FSMContext):
    _, net, idx = cb.data.split("_")
    a, p = STATION_VALS[int(idx)]
    await state.update_data(sec="balance", service=f"كازية {net.upper()}", amount=a, price=p)
    if net == "syr":
        await state.set_state(OrderState.entering_station_syr)
        await cb.message.edit_text("أدخل كود الكازية (6 خانات) متبوعاً بالمحافظة:\nمثال: `123456 دمشق`", parse_mode="Markdown")
    else:
        await state.set_state(OrderState.entering_station_mtn)
        await cb.message.edit_text("أدخل كود الكازية ورقم البطاقة والمحافظة:\nمثال: `123456 0944000000 حمص`", parse_mode="Markdown")

@dp.message(OrderState.entering_station_syr)
async def proc_syr_st(message: types.Message, state: FSMContext):
    await state.update_data(target=f"كازية سيريتل: {message.text.strip()}")
    await prompt_payment(message, state)

@dp.message(OrderState.entering_station_mtn)
async def proc_mtn_st(message: types.Message, state: FSMContext):
    await state.update_data(target=f"كازية MTN: {message.text.strip()}")
    await prompt_payment(message, state)

@dp.message(OrderState.entering_invoice)
async def proc_invoice(message: types.Message, state: FSMContext):
    try:
        inv, amt = message.text.strip().split()
        final_price = round(float(amt) * 1.05, 2)
        await state.update_data(target=f"رقم الفاتورة: {inv} | المبلغ: {amt}", price=final_price)
        await prompt_payment(message, state)
    except Exception:
        await message.reply("⚠️ تنسيق خاطئ! أرسل رقم الفاتورة ثم المبلغ وبينهما مسافة.")

@dp.message(OrderState.entering_cash_amount)
async def proc_cash_amt(message: types.Message, state: FSMContext):
    try:
        amt = float(message.text.strip())
        if amt < 1000:
            await message.reply("⚠️ الحد الأدنى لكاش هو 1,000 ل.س:")
            return
        final_price = round(amt * 1.05, 2)
        await state.update_data(price=final_price, amount=amt)
        data = await state.get_data()
        await state.set_state(OrderState.entering_cash_target)
        if data.get("net") == "syr":
            await message.answer("أدخل معرّف Player-ID الخاص بك لاستلام كاش سيريتل:")
        else:
            await message.answer("أدخل رقم MTN كاش المطلوب التحويل إليه:")
    except Exception:
        await message.reply("⚠️ أدخل رقماً صحيحاً بالأرقام:")

@dp.message(OrderState.entering_cash_target)
async def proc_cash_tgt(message: types.Message, state: FSMContext):
    await state.update_data(target=f"الكاش: {message.text.strip()}")
    await prompt_payment(message, state)

GAME_PACKS = {
    "pubg": [("60 UC", 1.0), ("325 UC", 5.0), ("660 UC", 10.0), ("1800 UC", 25.0), ("3850 UC", 50.0), ("8100 UC", 100.0)],
    "ff": [("100 جوهرة", 1.0), ("210 جوهرة", 2.0), ("530 جوهرة", 5.0), ("1080 جوهرة", 10.0), ("2200 جوهرة", 20.0), ("5600 جوهرة", 50.0)],
    "jawaker": [("15,000 توكنز", 1.5), ("50,000 توكنز", 4.0), ("150,000 توكنز", 10.0), ("باشا (شهر)", 6.0)],
    "coc": [("500 جوهرة", 5.0), ("1200 جوهرة", 10.0), ("2500 جوهرة", 20.0), ("6500 جوهرة", 50.0), ("14000 جوهرة", 100.0)]
}

@dp.callback_query(F.data == "sec_games")
async def games_menu(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="🔫 ببجي (PUBG)", callback_data="game:pubg")],
        [InlineKeyboardButton(text="🔥 فري فاير (Free Fire)", callback_data="game:ff")],
        [InlineKeyboardButton(text="🃏 جواكر (Jawaker)", callback_data="game:jawaker")],
        [InlineKeyboardButton(text="⚔️ كلاش أوف كلانس (CoC)", callback_data="game:coc")],
        [InlineKeyboardButton(text="🎮 باقي الألعاب [طلب تسعير]", callback_data="quote:game")],
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
    await prompt_payment(message, state)

@dp.callback_query(F.data == "sec_chat")
async def chat_menu(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="🌟 Soul Star (كوينز)", callback_data="chat:soulstar")],
        [InlineKeyboardButton(text="❄️ Soulchill (كريستال)", callback_data="chat:soulchill")],
        [InlineKeyboardButton(text="💬 IMO (ألماس)", callback_data="chat:imo")],
        [InlineKeyboardButton(text="🗣 Talsa chat (كوينز)", callback_data="chat:talsa")],
        [InlineKeyboardButton(text="🔍 باقي التطبيقات [طلب تسعير]", callback_data="quote:chat")],
        [InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_main")]
    ]
    await cb.message.edit_text("اختر تطبيق الشات المطلوب:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("chat:"))
async def chat_calc_prompt(cb: types.CallbackQuery, state: FSMContext):
    c_key = cb.data.split(":")[1]
    await state.update_data(sec="games", chat_app=c_key)
    await state.set_state(OrderState.entering_quote_details)
    await cb.message.edit_text("أدخل (الآيدي) متبوعاً بـ (الكمية المطلوبة):\nمثال: `123456 5000`", parse_mode="Markdown")

@dp.message(OrderState.entering_quote_details)
async def proc_chat_calc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    c_key = data.get("chat_app")
    try:
        u_id, qty = message.text.strip().split()
        qty = float(qty)
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
        await prompt_payment(message, state)
    except Exception:
        await message.reply("⚠️ تنسيق غير صحيح! أرسل الآيدي ثم الكمية وبينهما مسافة.")

@dp.callback_query(F.data == "sec_accounts")
async def accounts_menu(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="🤖 ChatGPT عادي (1,700 ل.س)", callback_data="acc_buy:ChatGPT عادي:1700")],
        [InlineKeyboardButton(text="⚡ ChatGPT Go (2,000 ل.س)", callback_data="acc_buy:ChatGPT Go:2000")],
        [InlineKeyboardButton(text="💎 ChatGPT Plus شهر (3,500 ل.س)", callback_data="acc_buy:ChatGPT Plus شهر:3500")],
        [InlineKeyboardButton(text="🎬 Netflix شهر (800 ل.س)", callback_data="acc_buy:Netflix شهر:800")],
        [InlineKeyboardButton(text="🍿 Netflix سنة (5,000 ل.س)", callback_data="acc_buy:Netflix سنة:5000")],
        [InlineKeyboardButton(text="📋 باقي الحسابات (27 خدمة) [تسعير]", callback_data="quote:account")],
        [InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_main")]
    ]
    await cb.message.edit_text("اختر الحساب المطلوب:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("acc_buy:"))
async def acc_buy_fixed(cb: types.CallbackQuery, state: FSMContext):
    _, name, price = cb.data.split(":")
    await state.update_data(sec="accounts", service=f"حساب {name}", price=float(price), target="حساب جاهز مع الضمان")
    await prompt_payment_cb(cb, state)

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

@dp.callback_query(F.data == "soc:fb")
async def fb_menu(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="👁 مشاهدات 10k (500 ل.س)", callback_data="sbuy:fb:مشاهدات 10k:500")],
        [InlineKeyboardButton(text="👍 لايكات منشور 5k (700 ل.س)", callback_data="sbuy:fb:لايكات منشور 5k:700")],
        [InlineKeyboardButton(text="👥 متابعين 1k (150 ل.س)", callback_data="sbuy:fb:متابعين 1k:150")],
        [InlineKeyboardButton(text="💬 تعليقات عربية 200 (250 ل.س)", callback_data="sbuy:fb:تعليقات عربية 200:250")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="sec_social")]
    ]
    await cb.message.edit_text("باقات فيسبوك:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "soc:ig")
async def ig_menu(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="👁 مشاهدات 500k (300 ل.س)", callback_data="sbuy:ig:مشاهدات 500k:300")],
        [InlineKeyboardButton(text="❤️ لايكات 5k (700 ل.س)", callback_data="sbuy:ig:لايكات 5k:700")],
        [InlineKeyboardButton(text="👥 متابعين أجنبي 1k (700 ل.س)", callback_data="sbuy:ig:متابعين أجنبي 1k:700")],
        [InlineKeyboardButton(text="👥 متابعين عربي 1k (1,350 ل.س)", callback_data="sbuy:ig:متابعين عربي 1k:1350")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="sec_social")]
    ]
    await cb.message.edit_text("باقات إنستغرام:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "soc:tg")
async def tg_menu(cb: types.CallbackQuery):
    kb = [
        [InlineKeyboardButton(text="👥 أعضاء قنوات 1k (400 ل.س)", callback_data="sbuy:tg:أعضاء 1k:400")],
        [InlineKeyboardButton(text="🔥 تفاعلات 1k (150 ل.س)", callback_data="sbuy:tg:تفاعلات 1k:150")],
        [InlineKeyboardButton(text="👁 مشاهدات 5k (200 ل.س)", callback_data="sbuy:tg:مشاهدات 5k:200")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="sec_social")]
    ]
    await cb.message.edit_text("باقات تلغرام:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("sbuy:"))
async def soc_buy(cb: types.CallbackQuery, state: FSMContext):
    _, plat, name, price = cb.data.split(":")
    await state.update_data(sec="social", service=f"{plat.upper()} - {name}", price=float(price))
    await state.set_state(OrderState.entering_social_target)
    await cb.message.edit_text("أرسل الآن رابط الحساب أو المنشور المطلوب:")

@dp.message(OrderState.entering_social_target)
async def proc_soc_link(message: types.Message, state: FSMContext):
    await state.update_data(target=message.text.strip())
    await prompt_payment(message, state)

AD_DAYS = [
    (1, 600), (2, 1100), (3, 1500), (4, 2000), (5, 2500),
    (6, 3000), (7, 3600), (10, 5000)
]

@dp.callback_query(F.data == "soc:ads")
async def ads_menu(cb: types.CallbackQuery):
    buttons = []
    for d, p in AD_DAYS:
        buttons.append(InlineKeyboardButton(text=f"إعلان {d} أيام ⬅ {p}ل.س", callback_data=f"ad_fixed:{d}:{p}"))
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="⚙️ تحديد أيام حسب الطلب (200 ل.س/يوم)", callback_data="ad_custom")])
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="sec_social")])
    await cb.message.edit_text("اختر مدة الإعلان الممول على فيسبوك:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.callback_query(F.data.startswith("ad_fixed:"))
async def ad_fixed_click(cb: types.CallbackQuery, state: FSMContext):
    _, d, p = cb.data.split(":")
    await state.update_data(sec="social", service=f"إعلان ممول ({d} أيام)", price=float(p))
    await state.set_state(OrderState.entering_ad_phone)
    await cb.message.edit_text("يرجى كتابة رقم الهاتف للتواصل معك:")

@dp.callback_query(F.data == "ad_custom")
async def ad_custom_click(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.entering_custom_ad_days)
    await cb.message.edit_text("أدخل عدد الأيام المطلوبة للإعلان (كل يوم = 200 ل.س):")

@dp.message(OrderState.entering_custom_ad_days)
async def proc_custom_ad(message: types.Message, state: FSMContext):
    try:
        days = int(message.text.strip())
        price = days * 200
        await state.update_data(sec="social", service=f"إعلان ممول مخصص ({days} أيام)", price=price)
        await state.set_state(OrderState.entering_ad_phone)
        await message.answer("أدخل رقم هاتفك للتواصل:")
    except Exception:
        await message.reply("⚠️ يرجى إدخال عدد صحيح بالأرقام:")

@dp.message(OrderState.entering_ad_phone)
async def proc_ad_phone(message: types.Message, state: FSMContext):
    await state.update_data(target=f"رقم تواصل الإعلان: {message.text.strip()}")
    await prompt_payment(message, state)

@dp.callback_query(F.data == "sec_numbers")
async def numbers_menu(cb: types.CallbackQuery, state: FSMContext):
    p_wa = get_setting("num_whatsapp")
    p_tg = get_setting("num_telegram")
    kb = [
        [InlineKeyboardButton(text=f"🟢 رقم واتساب أجنبي ({p_wa} ل.س)", callback_data="buy_n:whatsapp")],
        [InlineKeyboardButton(text=f"🔵 رقم تلغرام أمريكي ({p_tg} ل.س)", callback_data="buy_n:telegram")],
        [InlineKeyboardButton(text="📱 رقم تيك توك [طلب تسعير]", callback_data="quote:num_tiktok")],
        [InlineKeyboardButton(text="🌐 تفعيل غوغل [طلب تسعير]", callback_data="quote:num_google")],
        [InlineKeyboardButton(text="🍎 تفعيل آبل [طلب تسعير]", callback_data="quote:num_apple")],
        [InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_main")]
    ]
    await cb.message.edit_text("قسم أرقام التفعيل:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("buy_n:"))
async def buy_num_fast(cb: types.CallbackQuery, state: FSMContext):
    target = cb.data.split(":")[1]
    price = get_setting(f"num_{target}")
    name = "واتساب أجنبي" if target == "whatsapp" else "تلغرام أمريكي"
    await state.update_data(sec="social", service=f"رقم {name}", price=price, target="رابط تفعيل")
    await prompt_payment_cb(cb, state)

@dp.callback_query(F.data.startswith("quote:"))
async def generic_quote(cb: types.CallbackQuery):
    q_type = cb.data.split(":")[1]
    g_map = {
        "game": ("games", "لعبة إضافية"),
        "chat": ("games", "تطبيق شات"),
        "account": ("accounts", "حساب جاهز"),
        "num_tiktok": ("social", "رقم تيك توك"),
        "num_google": ("social", "تفعيل غوغل"),
        "num_apple": ("social", "تفعيل آبل")
    }
    sec, label = g_map.get(q_type, ("games", "طلب عام"))
    group_id = GROUPS[sec]
    text = (
        f"📩 **طلب تسعير جديد:**\n"
        f"👤 الزبون: @{cb.from_user.username or 'بدون'} (`{cb.from_user.id}`)\n"
        f"🏷 التصنيف: **{label}**\n\n"
        f"✏️ اضغط الزر بالأسفل لتحديد السعر وإرساله للزبون:"
    )
    kb = [[InlineKeyboardButton(text="💰 تسعير الطلب", callback_data=f"setquote:{cb.from_user.id}:{label}")]]
    await bot.send_message(group_id, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    await cb.answer("✅ تم إرسال طلبك للإدارة، سيصلك السعر هنا قريباً.", show_alert=True)

async def prompt_payment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    price = data.get("price", 0)
    service = data.get("service", "")
    target = data.get("target", "")

    pay_text = (
        f"🧾 **ملخص تفاصيل طلبك:**\n"
        f"• الخدمة: **{service}**\n"
        f"• البيانات: `{target}`\n"
        f"• المبلغ المطلوب: **{price} ليرة سورية**\n\n"
        f"💳 **بيانات التحويل عبر شام كاش:**\n"
        f"👤 الاسم: `{SHAM_NAME}`\n"
        f"🔗 العنوان: `{SHAM_ADDR}`\n\n"
        f"⚠️ يرجى تحويل المبلغ ثم **رفع صورة إشعار التحويل هنا فوراً**."
    )
    await state.set_state(OrderState.waiting_receipt)
    try:
        photo = FSInputFile(QR_IMAGE_PATH)
        await message.answer_photo(photo, caption=pay_text, parse_mode="Markdown")
    except Exception:
        await message.answer(pay_text, parse_mode="Markdown")

async def prompt_payment_cb(cb: types.CallbackQuery, state: FSMContext):
    await prompt_payment(cb.message, state)

@dp.message(OrderState.waiting_receipt, F.photo)
async def receive_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    sec = data.get("sec", "balance")
    group_id = GROUPS.get(sec, GROUPS["balance"])

    order_info = (
        f"🔔 **طلب مسدد وجديد:**\n"
        f"👤 الزبون: @{message.from_user.username or 'بدون'} (`{message.from_user.id}`)\n"
        f"🏷 الخدمة: {data.get('service')}\n"
        f"🎯 البيانات: `{data.get('target')}`\n"
        f"💰 المبلغ المسدد: **{data.get('price')} ل.س**\n"
    )

    kb = [
        [
            InlineKeyboardButton(text="✅ تم التنفيذ", callback_data=f"done:{message.from_user.id}"),
            InlineKeyboardButton(text="❌ رفض الطلب", callback_data=f"rej:{message.from_user.id}")
        ]
    ]
    if sec == "social" and "رقم" in data.get("service", ""):
        kb.append([InlineKeyboardButton(text="🔗 إرسال رابط التفعيل", callback_data=f"sendlink:{message.from_user.id}")])

    await bot.send_photo(
        chat_id=group_id,
        photo=message.photo[-1].file_id,
        caption=order_info,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="Markdown"
    )
    await state.clear()
    await message.answer("✅ تم استلام إشعار الدفع وإرساله لفريق الإدارة. سيتم إشعارك فور اكتمال التنفيذ.")

@dp.callback_query(F.data.startswith("done:"))
async def order_done(cb: types.CallbackQuery):
    u_id = int(cb.data.split(":")[1])
    try:
        await bot.send_message(u_id, "✅ تم تنفيذ طلبك بنجاح! شكراً لتعاملك معنا.")
        if cb.message.caption:
            await cb.message.edit_caption(caption=cb.message.caption + "\n\n🟢 **تم التنفيذ**", reply_markup=None)
        else:
            await cb.message.edit_text(text=cb.message.text + "\n\n🟢 **تم التنفيذ**", reply_markup=None)
    except Exception as e:
        await cb.answer(f"خطأ: {e}", show_alert=True)

@dp.callback_query(F.data.startswith("rej:"))
async def order_reject(cb: types.CallbackQuery):
    u_id = int(cb.data.split(":")[1])
    try:
        await bot.send_message(u_id, "❌ نعتذر منك، تم رفض الطلب لوجود خطأ في الإشعار أو البيانات.")
        if cb.message.caption:
            await cb.message.edit_caption(caption=cb.message.caption + "\n\n🔴 **تم الرفض**", reply_markup=None)
        else:
            await cb.message.edit_text(text=cb.message.text + "\n\n🔴 **تم الرفض**", reply_markup=None)
    except Exception as e:
        await cb.answer(f"خطأ: {e}", show_alert=True)

@dp.callback_query(F.data.startswith("sendlink:"))
async def ask_admin_link(cb: types.CallbackQuery, state: FSMContext):
    u_id = cb.data.split(":")[1]
    await state.update_data(target_cust=u_id)
    await state.set_state(OrderState.admin_sending_link)
    await cb.message.reply("✏️ أرسل الآن رابط التفعيل فقط ليتم تحويله للزبون:")

@dp.message(OrderState.admin_sending_link)
async def deliver_link(message: types.Message, state: FSMContext):
    data = await state.get_data()
    c_id = int(data.get("target_cust"))
    link = message.text.strip()
    msg = (
        f"🔗 **رابط تفعيل رقمك جاهز:**\n\n"
        f"{link}\n\n"
        f"⚠️ يرجى الدخول إلى الرابط واتباع قواعد التفعيل بدقة لتفعيل الرقم واستلام الكود."
    )
    try:
        await bot.send_message(c_id, msg)
        await message.reply("✅ تم إرسال الرابط للزبون بنجاح.")
        await state.clear()
    except Exception as e:
        await message.reply(f"⚠️ فشل الإرسال: {e}")

@dp.callback_query(F.data == "sec_support")
async def support_start(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.support_ticket)
    await cb.message.edit_text("اكتب استفسارك أو مشكلتك بالتفصيل وسيقوم فريق الدعم بالرد عليك هنا:")

@dp.message(OrderState.support_ticket)
async def support_forward(message: types.Message, state: FSMContext):
    txt = (
        f"📩 **تذكرة دعم فني جديدة:**\n"
        f"👤 الزبون: @{message.from_user.username or 'بدون'} (`{message.from_user.id}`)\n\n"
        f"📝 الرسالة:\n{message.text}"
    )
    await bot.send_message(GROUPS["support"], txt, parse_mode="Markdown")
    await state.clear()
    await message.answer("✅ تم إرسال رسالتك للدعم الفني، سنرد عليك هنا بأقرب وقت.")

@dp.message(F.chat.id == GROUPS["support"], F.reply_to_message)
async def support_group_reply(message: types.Message):
    orig = message.reply_to_message.text or message.reply_to_message.caption or ""
    if "(`" in orig and "`)" in orig:
        try:
            cust_id = int(orig.split("(`")[1].split("`)")[0])
            await bot.send_message(cust_id, f"💬 **رد الدعم الفني:**\n\n{message.text}")
            await message.reply("✅ تم توصيل الرد للزبون.")
        except Exception as e:
            await message.reply(f"⚠️️ فشل الإرسال: {e}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
