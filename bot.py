import os
import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    FSInputFile
)

BOT_TOKEN = "8774564171:AAFxpEXjd6BVSCMwYhE5Eg_7ZxiIN1yhHmI"
ADMIN_ID = 5346581925

# بيانات شام كاش المعتمدة
SHAM_NAME = "سكينه حمود طه"
SHAM_CODE = "be03739e320f3dfd318a1a7faebae16a"
QR_IMAGE_NAME = "IMG-20260923-WA0003.jpg"

GROUPS = {
    "ichancy": -1004416182163,
    "balance": -1004423851571,
    "games": -1004426615112,
    "social": -1004411774893,
    "support": -1004420804667
}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class OrderFlow(StatesGroup):
    ichancy_action = State()
    ichancy_phone = State()
    ichancy_amount = State()
    ichancy_account_id = State()
    ichancy_receipt = State()
    ichancy_txid = State()
    
    balance_type = State()
    service_type = State()
    target_phone = State()
    city = State()
    station_code = State()
    package_amount = State()
    balance_receipt = State()
    balance_txid = State()
    
    game_item = State()
    game_uid = State()
    game_receipt = State()
    game_txid = State()
    
    social_action = State()
    social_link = State()
    ad_days = State()
    social_receipt = State()
    social_txid = State()
    
    support_section = State()
    support_txid = State()
    support_text = State()

class AdminReply(StatesGroup):
    waiting_for_price = State()
    waiting_for_support_text = State()

def main_menu():
    kb = [
        [KeyboardButton(text="🎰 خدمات iChancy")],
        [KeyboardButton(text="📱 رصيد وكاش وكازية (Syriatel / MTN)")],
        [KeyboardButton(text="🎮 شحن الألعاب"), KeyboardButton(text="💬 شحن تطبيقات الشات")],
        [KeyboardButton(text="📲 أرقام تفعيل"), KeyboardButton(text="🚀 خدمات السوشيال ميديا")],
        [KeyboardButton(text="📢 إعلانات ممولة فيسبوك")],
        [KeyboardButton(text="📩 الدعم الفني والشكاوى")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

async def send_payment_instructions(message: types.Message, amount: int):
    caption = (
        f"💳 **بيانات الدفع عبر شام كاش:**\n\n"
        f"👤 **اسم الحساب:** `{SHAM_NAME}`\n"
        f"🔢 **كود التحويل (اضغط للنسخ):**\n`{SHAM_CODE}`\n\n"
        f"💰 **المبلغ المطلوب تحويله:** **{amount:,} ل.س**\n\n"
        f"📸 يرجى إتمام التحويل ثم إرسال **صورة إشعار الدفع** هنا:"
    )
    if os.path.exists(QR_IMAGE_NAME):
        photo = FSInputFile(QR_IMAGE_NAME)
        await message.answer_photo(photo=photo, caption=caption, parse_mode=ParseMode.MARKDOWN)
    else:
        await message.answer(caption, parse_mode=ParseMode.MARKDOWN)

@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    text = (
        f"أهلاً بك **{message.from_user.full_name}** في بوت الخدمات الموحد 🌟\n\n"
        "يرجى اختيار الخدمة المطلوبة من القائمة أدناه:"
    )
    await message.answer(text, reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN)

# 1. قسم iChancy
@dp.message(F.text == "🎰 خدمات iChancy")
async def ichancy_menu(message: types.Message, state: FSMContext):
    await state.clear()
    buttons = [
        [InlineKeyboardButton(text="➕ إنشاء حساب جديد", callback_data="ichancy_create")],
        [InlineKeyboardButton(text="📥 إيداع رصيد", callback_data="ichancy_deposit")],
        [InlineKeyboardButton(text="📤 سحب رصيد", callback_data="ichancy_withdraw")]
    ]
    await message.answer("اختر العملية المطلوبة لـ **iChancy**:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=ParseMode.MARKDOWN)

@dp.callback_query(F.data.startswith("ichancy_"))
async def ichancy_choice(call: types.CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]
    await state.update_data(action=action)
    if action == "create":
        await call.message.answer("يرجى إرسال رقم هاتفك لإنشاء الحساب (مثال: 0912345678):")
        await state.set_state(OrderFlow.ichancy_phone)
    elif action in ["deposit", "withdraw"]:
        await call.message.answer("أدخل آيدي الحساب في iChancy:")
        await state.set_state(OrderFlow.ichancy_account_id)
    await call.answer()

@dp.message(OrderFlow.ichancy_phone)
async def ichancy_phone_step(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not (re.match(r"^09\d{8}$", phone)):
        return await message.answer("⚠️ رقم الهاتف غير صحيح. يجب أن يبدأ بـ 09 ويتألف من 10 خانات:")
    msg = (
        f"🎰 **طلب جديد: إنشاء حساب iChancy**\n"
        f"👤 الزبون: {message.from_user.mention_html()} (ID: <code>{message.from_user.id}</code>)\n"
        f"📞 رقم الهاتف: <code>{phone}</code>"
    )
    btns = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ تم الإنشاء", callback_data=f"done_{message.from_user.id}"),
        InlineKeyboardButton(text="❌ رفض", callback_data=f"reject_{message.from_user.id}")
    ]])
    await bot.send_message(GROUPS["ichancy"], msg, reply_markup=btns, parse_mode=ParseMode.HTML)
    await message.answer("✅ تم إرسال طلبك للإدارة، ستصلك رسالة تحتوي بيانات الحساب فور تجهيزه.", reply_markup=main_menu())
    await state.clear()

@dp.message(OrderFlow.ichancy_account_id)
async def ichancy_acc_step(message: types.Message, state: FSMContext):
    await state.update_data(account_id=message.text.strip())
    await message.answer("أدخل المبلغ بالليرة السورية:")
    await state.set_state(OrderFlow.ichancy_amount)

@dp.message(OrderFlow.ichancy_amount)
async def ichancy_amount_step(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("يرجى إدخال مبلغ صحيح أرقاماً فقط:")
    amount = int(message.text)
    data = await state.get_data()
    action = data.get("action")
    await state.update_data(amount=amount)
    
    if action == "deposit":
        await send_payment_instructions(message, amount)
        await state.set_state(OrderFlow.ichancy_receipt)
    else:
        msg = (
            f"📤 **طلب سحب رصيد iChancy**\n"
            f"👤 الزبون: {message.from_user.mention_html()} (ID: <code>{message.from_user.id}</code>)\n"
            f"🆔 آيدي الحساب: <code>{data.get('account_id')}</code>\n"
            f"💰 المبلغ المطلوب: <code>{amount:,} ل.س</code>"
        )
        btns = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ تم التحويل", callback_data=f"done_{message.from_user.id}"),
            InlineKeyboardButton(text="❌ رفض", callback_data=f"reject_{message.from_user.id}")
        ]])
        await bot.send_message(GROUPS["ichancy"], msg, reply_markup=btns, parse_mode=ParseMode.HTML)
        await message.answer("✅ تم إرسال طلب السحب للإدارة وسيتم التحويل لحسابك بأسرع وقت.", reply_markup=main_menu())
        await state.clear()

@dp.message(OrderFlow.ichancy_receipt, F.photo)
async def ichancy_receipt_step(message: types.Message, state: FSMContext):
    await state.update_data(receipt_photo=message.photo[-1].file_id)
    await message.answer("أرسل الآن **رقم عملية التحويل** (رقم العملية / TXID):", parse_mode=ParseMode.MARKDOWN)
    await state.set_state(OrderFlow.ichancy_txid)

@dp.message(OrderFlow.ichancy_txid)
async def ichancy_txid_step(message: types.Message, state: FSMContext):
    txid = message.text.strip()
    data = await state.get_data()
    msg = (
        f"📥 **طلب إيداع رصيد iChancy**\n"
        f"👤 الزبون: {message.from_user.mention_html()} (ID: <code>{message.from_user.id}</code>)\n"
        f"🆔 آيدي الحساب: <code>{data.get('account_id')}</code>\n"
        f"💰 المبلغ: <code>{data.get('amount'):,} ل.س</code>\n"
        f"🔢 رقم العملية: <code>{txid}</code>"
    )
    btns = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ تأكيد الإيداع", callback_data=f"done_{message.from_user.id}"),
        InlineKeyboardButton(text="❌ رفض", callback_data=f"reject_{message.from_user.id}")
    ]])
    await bot.send_photo(GROUPS["ichancy"], photo=data.get('receipt_photo'), caption=msg, reply_markup=btns, parse_mode=ParseMode.HTML)
    await message.answer("✅ تم استلام طلب الإيداع بنجاح، جاري التحقق والشحن.", reply_markup=main_menu())
    await state.clear()

# 2. قسم الرصيد والكاش والكازية
@dp.message(F.text == "📱 رصيد وكاش وكازية (Syriatel / MTN)")
async def balance_menu(message: types.Message, state: FSMContext):
    await state.clear()
    btns = [
        [InlineKeyboardButton(text="🔴 سيريتل (Syriatel)", callback_data="network_syriatel")],
        [InlineKeyboardButton(text="🟡 إم تي إن (MTN)", callback_data="network_mtn")]
    ]
    await message.answer("اختر الشبكة:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("network_"))
async def network_choice(call: types.CallbackQuery, state: FSMContext):
    net = call.data.split("_")[1]
    await state.update_data(network=net)
    btns = [
        [InlineKeyboardButton(text="💳 رصيد عادي", callback_data="serv_normal")],
        [InlineKeyboardButton(text="💵 كاش (+5%)", callback_data="serv_cash")],
        [InlineKeyboardButton(text="🧾 دفع فواتير (+5%)", callback_data="serv_bill")],
        [InlineKeyboardButton(text="⛽ كازية جملة (+7%)", callback_data="serv_gas")]
    ]
    await call.message.answer(f"اختر نوع الخدمة لشبكة **{net.upper()}**:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), parse_mode=ParseMode.MARKDOWN)
    await call.answer()

@dp.callback_query(F.data.startswith("serv_"))
async def service_choice(call: types.CallbackQuery, state: FSMContext):
    serv = call.data.split("_")[1]
    await state.update_data(service=serv)
    data = await state.get_data()
    net = data.get("network")

    if serv == "gas":
        cities = ["دمشق", "ريف دمشق", "حلب", "حمص", "حماة", "اللاذقية", "طرطوس", "السويداء", "درعا", "القنيطرة", "دير الزور", "الحسكة", "الرقة"]
        kb = [[InlineKeyboardButton(text=c, callback_data=f"gas_city_{c}")] for c in cities]
        await call.message.answer("اختر محافظة الكازية:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await call.message.answer(f"أدخل رقم هاتف {net.upper()} المستلم (10 خانات):")
        await state.set_state(OrderFlow.target_phone)
    await call.answer()

@dp.callback_query(F.data.startswith("gas_city_"))
async def gas_city_choice(call: types.CallbackQuery, state: FSMContext):
    city = call.data.split("_")[2]
    await state.update_data(city=city)
    data = await state.get_data()
    net = data.get("network")
    await call.message.answer(f"أدخل رقم خط الكازية لشبكة {net.upper()} (10 خانات):")
    await state.set_state(OrderFlow.target_phone)
    await call.answer()

@dp.message(OrderFlow.target_phone)
async def target_phone_step(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    data = await state.get_data()
    net = data.get("network")
    
    if net == "syriatel" and not (re.match(r"^09(3|8|9)\d{7}$", phone)):
        return await message.answer("⚠️ رقم سيريتل غير صحيح، يجب أن يتألف من 10 خانات ويبدأ بـ 093 أو 098 أو 099:")
    elif net == "mtn" and not (re.match(r"^09(4|5|6|7)\d{7}$", phone)):
        return await message.answer("⚠️ رقم MTN غير صحيح، يجب أن يتألف من 10 خانات ويبدأ بـ 094 أو 095 أو 096 أو 097:")
        
    await state.update_data(target_phone=phone)
    
    if data.get("service") == "gas":
        code_len = 8 if net == "syriatel" else 9
        await message.answer(f"أدخل كود الكازية الخاص بـ {net.upper()} والمؤلف من **{code_len} خانات** حصراً:", parse_mode=ParseMode.MARKDOWN)
        await state.set_state(OrderFlow.station_code)
    else:
        if data.get("service") in ["cash", "bill"]:
            await message.answer("أدخل المبلغ المطلوب بالليرة السورية:")
            await state.set_state(OrderFlow.package_amount)
        else:
            amounts = [5000, 10000, 20000, 25000, 50000, 100000]
            kb = [[InlineKeyboardButton(text=f"{a:,} ل.س", callback_data=f"amt_{a}")] for a in amounts]
            await message.answer("اختر فئة الرصيد:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.message(OrderFlow.station_code)
async def station_code_step(message: types.Message, state: FSMContext):
    code = message.text.strip()
    data = await state.get_data()
    net = data.get("network")
    expected = 8 if net == "syriatel" else 9
    
    if not (code.isdigit() and len(code) == expected):
        return await message.answer(f"⚠️ كود الكازية غير صالح. يجب أن يتكون من {expected} أرقام بالضبط:")
    
    await state.update_data(station_code=code)
    amounts = [500, 1000, 2000, 5000, 10000]
    kb = [[InlineKeyboardButton(text=f"{a:,}", callback_data=f"amt_{a}")] for a in amounts]
    await message.answer("اختر فئة شحن الكازية:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("amt_"))
async def amount_choice(call: types.CallbackQuery, state: FSMContext):
    amt = int(call.data.split("_")[1])
    await proceed_with_balance_amount(call.message, state, amt)
    await call.answer()

@dp.message(OrderFlow.package_amount)
async def manual_amount_step(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("يرجى إدخال مبلغ صحيح أرقاماً فقط:")
    await proceed_with_balance_amount(message, state, int(message.text))

async def proceed_with_balance_amount(msg_obj, state: FSMContext, amt: int):
    data = await state.get_data()
    serv = data.get("service")
    
    if serv in ["cash", "bill"]:
        final_price = round(amt * 1.05)
    elif serv == "gas":
        final_price = round(amt * 1.07)
    else:
        final_price = amt
        
    await state.update_data(package_amount=amt, final_price=final_price)
    await send_payment_instructions(msg_obj, final_price)
    await state.set_state(OrderFlow.balance_receipt)

@dp.message(OrderFlow.balance_receipt, F.photo)
async def balance_receipt_step(message: types.Message, state: FSMContext):
    await state.update_data(receipt_photo=message.photo[-1].file_id)
    await message.answer("أدخل **رقم عملية التحويل** الموضح بالإشعار:")
    await state.set_state(OrderFlow.balance_txid)

@dp.message(OrderFlow.balance_txid)
async def balance_txid_step(message: types.Message, state: FSMContext):
    txid = message.text.strip()
    data = await state.get_data()
    
    details = (
        f"📱 **طلب شحن رصيد / كاش**\n"
        f"👤 الزبون: {message.from_user.mention_html()} (ID: <code>{message.from_user.id}</code>)\n"
        f"📶 الشبكة: <b>{data.get('network').upper()}</b> | ⚙️ الخدمة: <b>{data.get('service')}</b>\n"
        f"📞 الرقم: <code>{data.get('target_phone')}</code>\n"
    )
    if data.get('city'):
        details += f"📍 المحافظة: <b>{data.get('city')}</b>\n"
    if data.get('station_code'):
        details += f"⛽ كود الكازية: <code>{data.get('station_code')}</code>\n"
    details += (
        f"💵 المبلغ/الفئة: <b>{data.get('package_amount'):,}</b>\n"
        f"💰 الإجمالي المطلوب: <b>{data.get('final_price'):,} ل.س</b>\n"
        f"🔢 رقم العملية: <code>{txid}</code>"
    )
    btns = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ تم التنفيذ", callback_data=f"done_{message.from_user.id}"),
        InlineKeyboardButton(text="❌ رفض", callback_data=f"reject_{message.from_user.id}")
    ]])
    await bot.send_photo(GROUPS["balance"], photo=data.get('receipt_photo'), caption=details, reply_markup=btns, parse_mode=ParseMode.HTML)
    await message.answer("✅ تم إرسال طلبك وجاري التنفيذ.", reply_markup=main_menu())
    await state.clear()

# 3. قسم الألعاب وتطبيقات الشات
@dp.message(F.text == "🎮 شحن الألعاب")
async def games_menu(message: types.Message, state: FSMContext):
    await state.clear()
    btns = [
        [InlineKeyboardButton(text="🟡 شدات ببجي (PUBG)", callback_data="game_pubg")],
        [InlineKeyboardButton(text="💎 فري فاير (Free Fire)", callback_data="game_freefire")],
        [InlineKeyboardButton(text="➕ لعبة أخرى مخصصة", callback_data="game_custom")]
    ]
    await message.answer("اختر اللعبة المطلوبة:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.message(F.text == "💬 شحن تطبيقات الشات")
async def chat_apps_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(game_type="تطبيق شات/بث")
    await message.answer("أرسل اسم التطبيق والكمية المطلوبة والمعرف (مثال: 500 كوينز تيك توك - المعرف: Ahmad_sy):")
    await state.set_state(OrderFlow.game_item)

@dp.callback_query(F.data.startswith("game_"))
async def game_choice(call: types.CallbackQuery, state: FSMContext):
    choice = call.data.split("_")[1]
    if choice == "pubg":
        packs = ["60 شدة UC", "325 شدة UC", "660 شدة UC", "1800 شدة UC", "3850 شدة UC", "8100 شدة UC"]
        kb = [[InlineKeyboardButton(text=p, callback_data=f"pack_pubg_{p}")] for p in packs]
        await call.message.answer("اختر باقة شدات ببجي:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    elif choice == "freefire":
        packs = ["💎 100+10 جوهرة", "💎 210+21 جوهرة", "💎 530+53 جوهرة", "💎 1080+108 جوهرة", "💎 2200+220 جوهرة", "👑 عضوية أسبوعية", "👑 عضوية شهرية"]
        kb = [[InlineKeyboardButton(text=p, callback_data=f"pack_ff_{p}")] for p in packs]
        await call.message.answer("اختر باقة فري فاير:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await call.message.answer("أرسل اسم اللعبة والكمية المطلوبة:")
        await state.set_state(OrderFlow.game_item)
    await call.answer()

@dp.callback_query(F.data.startswith("pack_"))
async def pack_choice(call: types.CallbackQuery, state: FSMContext):
    pack = call.data.split("_", 2)[2]
    await state.update_data(game_item=pack)
    await call.message.answer("أرسل آيدي الحساب (Player ID) أرقاماً فقط:")
    await state.set_state(OrderFlow.game_uid)
    await call.answer()

@dp.message(OrderFlow.game_item)
async def custom_game_item(message: types.Message, state: FSMContext):
    await state.update_data(game_item=message.text.strip())
    await message.answer("أرسل آيدي الحساب أو المعرف:")
    await state.set_state(OrderFlow.game_uid)

@dp.message(OrderFlow.game_uid)
async def game_uid_step(message: types.Message, state: FSMContext):
    uid = message.text.strip()
    data = await state.get_data()
    item = data.get("game_item")
    
    text = (
        f"🎮 **طلب تسعير جديد**\n"
        f"👤 الزبون: {message.from_user.mention_html()} (ID: <code>{message.from_user.id}</code>)\n"
        f"📦 الطلب: <b>{item}</b>\n"
        f"🆔 الآيدي/المعرف: <code>{uid}</code>"
    )
    btns = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💰 تسعير الطلب", callback_data=f"price_{message.from_user.id}"),
        InlineKeyboardButton(text="❌ غير متوفر", callback_data=f"reject_{message.from_user.id}")
    ]])
    await bot.send_message(GROUPS["games"], text, reply_markup=btns, parse_mode=ParseMode.HTML)
    await message.answer("⏳ تم استلام طلبك وإرساله للإدارة لتحديد السعر، ستصلك رسالة بالسعر فوراً.", reply_markup=main_menu())
    await state.clear()

# 4. قسم الأرقام والسوشيال والإعلانات
@dp.message(F.text == "📲 أرقام تفعيل")
async def numbers_menu(message: types.Message):
    btns = [
        [InlineKeyboardButton(text="🟢 واتساب (WhatsApp)", callback_data="num_whatsapp")],
        [InlineKeyboardButton(text="🔵 تليجرام (Telegram)", callback_data="num_telegram")],
        [InlineKeyboardButton(text="🔴 حساب Google", callback_data="num_google")],
        [InlineKeyboardButton(text="⚪ حساب Apple", callback_data="num_apple")]
    ]
    await message.answer("اختر التطبيق المطلوب لتفعيل رقم:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("num_"))
async def num_choice(call: types.CallbackQuery):
    app = call.data.split("_")[1]
    text = (
        f"📲 **طلب تفعيل رقم لـ {app.upper()}**\n"
        f"👤 الزبون: {call.from_user.mention_html()} (ID: <code>{call.from_user.id}</code>)"
    )
    btns = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💰 تسعير الرقم", callback_data=f"price_{call.from_user.id}"),
        InlineKeyboardButton(text="❌ غير متوفر", callback_data=f"reject_{call.from_user.id}")
    ]])
    await bot.send_message(GROUPS["social"], text, reply_markup=btns, parse_mode=ParseMode.HTML)
    await call.message.answer("⏳ تم إرسال طلب الرقم للإدارة، ستصلك رسالة بالسعر فوراً.", reply_markup=main_menu())
    await call.answer()

@dp.message(F.text == "🚀 خدمات السوشيال ميديا")
async def social_menu(message: types.Message):
    btns = [
        [InlineKeyboardButton(text="🔵 مشاهدات ريلز فيسبوك", callback_data="soc_fb_views")],
        [InlineKeyboardButton(text="🔵 تفاعل ريأكشن ستوري فيسبوك", callback_data="soc_fb_story")],
        [InlineKeyboardButton(text="🔵 لايكات منشور فيسبوك", callback_data="soc_fb_likes")],
        [InlineKeyboardButton(text="🔵 متابعين فيسبوك", callback_data="soc_fb_followers")],
        [InlineKeyboardButton(text="🔵 تعليقات عربية فيسبوك", callback_data="soc_fb_comments")],
        [InlineKeyboardButton(text="🟣 مشاهدات ريلز إنستغرام", callback_data="soc_ig_views")],
        [InlineKeyboardButton(text="🟣 لايكات منشور إنستغرام", callback_data="soc_ig_likes")],
        [InlineKeyboardButton(text="🟣 متابعين إنستغرام", callback_data="soc_ig_followers")]
    ]
    await message.answer("اختر الخدمة المطلوبة:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

SOCIAL_PACKS = {
    "fb_views": [("5,000", 231), ("10,000", 308), ("50,000", 1540), ("100,000", 3080)],
    "fb_story": [("1,000", 94), ("5,000", 462), ("10,000", 935), ("50,000", 4620)],
    "fb_likes": [("5,000", 616), ("10,000", 1210), ("50,000", 5610)],
    "fb_followers": [("1,000", 110), ("5,000", 550), ("10,000", 1100), ("50,000", 5500)],
    "fb_comments": [("200", 220), ("500", 528), ("1,000", 1045), ("5,000", 4840)],
    "ig_views": [("500,000", 275), ("1,000,000", 550), ("5,000,000", 2090), ("10,000,000", 3410)],
    "ig_likes": [("5,000", 605), ("10,000", 1210), ("50,000", 6050)],
    "ig_followers": [("1,000", 660), ("5,000", 2420), ("10,000", 4840)],
}

@dp.callback_query(F.data.startswith("soc_"))
async def soc_pack_choice(call: types.CallbackQuery, state: FSMContext):
    key = call.data.replace("soc_", "")
    await state.update_data(soc_key=key)
    items = SOCIAL_PACKS.get(key, [])
    kb = [[InlineKeyboardButton(text=f"{qty} بسعر {price} ل.س", callback_data=f"buy_soc_{qty}_{price}")] for qty, price in items]
    await call.message.answer("اختر الباقة المطلوبة:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()

@dp.callback_query(F.data.startswith("buy_soc_"))
async def buy_soc_step(call: types.CallbackQuery, state: FSMContext):
    _, _, qty, price = call.data.split("_")
    await state.update_data(qty=qty, price=int(price))
    await call.message.answer("أرسل رابط الحساب أو المنشور المطلوب تزويده:")
    await state.set_state(OrderFlow.social_link)
    await call.answer()

@dp.message(OrderFlow.social_link)
async def soc_link_step(message: types.Message, state: FSMContext):
    link = message.text.strip()
    if not (link.startswith("http://") or link.startswith("https://")):
        return await message.answer("⚠️ يرجى إرسال رابط صحيح يبدأ بـ https:// :")
    await state.update_data(link=link)
    data = await state.get_data()
    await send_payment_instructions(message, data.get('price'))
    await state.set_state(OrderFlow.social_receipt)

@dp.message(F.text == "📢 إعلانات ممولة فيسبوك")
async def fb_ads_menu(message: types.Message, state: FSMContext):
    await state.clear()
    kb = [[InlineKeyboardButton(text=f"{d} يوم ({d*504:,} ل.س)", callback_data=f"fb_ad_{d}")] for d in range(1, 11)]
    await message.answer("اختر مدة الإعلان الممول على فيسبوك (من 1 إلى 10 أيام):", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("fb_ad_"))
async def fb_ad_choice(call: types.CallbackQuery, state: FSMContext):
    days = int(call.data.split("_")[2])
    total = days * 504
    await state.update_data(ad_days=days, price=total, soc_key="إعلان ممول فيسبوك")
    await call.message.answer("أرسل رابط الصفحة أو المنشور المراد تمويله:")
    await state.set_state(OrderFlow.social_link)
    await call.answer()

@dp.message(OrderFlow.social_receipt, F.photo)
async def social_receipt_step(message: types.Message, state: FSMContext):
    await state.update_data(receipt_photo=message.photo[-1].file_id)
    await message.answer("أدخل **رقم عملية التحويل**:")
    await state.set_state(OrderFlow.social_txid)

@dp.message(OrderFlow.social_txid)
async def social_txid_step(message: types.Message, state: FSMContext):
    txid = message.text.strip()
    data = await state.get_data()
    details = (
        f"🌐 **طلب خدمات سوشيال / إعلانات**\n"
        f"👤 الزبون: {message.from_user.mention_html()} (ID: <code>{message.from_user.id}</code>)\n"
        f"📦 الخدمة: <b>{data.get('soc_key')}</b>\n"
        f"🔗 الرابط: {data.get('link')}\n"
        f"💰 القيمة: <b>{data.get('price'):,} ل.س</b>\n"
        f"🔢 رقم العملية: <code>{txid}</code>"
    )
    btns = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ بدء التنفيذ", callback_data=f"done_{message.from_user.id}"),
        InlineKeyboardButton(text="❌ رفض", callback_data=f"reject_{message.from_user.id}")
    ]])
    await bot.send_photo(GROUPS["social"], photo=data.get('receipt_photo'), caption=details, reply_markup=btns, parse_mode=ParseMode.HTML)
    await message.answer("✅ تم استلام طلبك بنجاح وجاري المتابعة والتنفيذ.", reply_markup=main_menu())
    await state.clear()

# 5. قسم الدعم الفني والشكاوى
@dp.message(F.text == "📩 الدعم الفني والشكاوى")
async def support_start(message: types.Message, state: FSMContext):
    await state.clear()
    btns = [
        [InlineKeyboardButton(text="🎰 مشكلة iChancy", callback_data="sup_ichancy")],
        [InlineKeyboardButton(text="📱 مشكلة رصيد/كاش", callback_data="sup_balance")],
        [InlineKeyboardButton(text="🎮 مشكلة ألعاب/شات", callback_data="sup_games")],
        [InlineKeyboardButton(text="🌐 مشكلة سوشيال/أرقام", callback_data="sup_social")],
        [InlineKeyboardButton(text="❓ استفسار عام", callback_data="sup_general")]
    ]
    await message.answer("يرجى اختيار قسم المشكلة:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("sup_"))
async def sup_choice(call: types.CallbackQuery, state: FSMContext):
    section = call.data.replace("sup_", "")
    await state.update_data(sup_section=section)
    await call.message.answer("أدخل رقم العملية المتعلقة بالمشكلة (أو أرسل 'لا يوجد'):")
    await state.set_state(OrderFlow.support_txid)
    await call.answer()

@dp.message(OrderFlow.support_txid)
async def sup_txid_step(message: types.Message, state: FSMContext):
    await state.update_data(sup_txid=message.text.strip())
    await message.answer("اكتب تفاصيل الشكوى أو المشكلة بوضوح:")
    await state.set_state(OrderFlow.support_text)

@dp.message(OrderFlow.support_text)
async def sup_text_step(message: types.Message, state: FSMContext):
    txt = message.text.strip()
    data = await state.get_data()
    msg = (
        f"📩 **شكوى / تذكرة دعم فني جديدة**\n"
        f"👤 الزبون: {message.from_user.mention_html()} (ID: <code>{message.from_user.id}</code>)\n"
        f"🏷 القسم: <b>{data.get('sup_section')}</b>\n"
        f"🔢 رقم العملية: <code>{data.get('sup_txid')}</code>\n\n"
        f"📝 نص الرسالة:\n{txt}"
    )
    btns = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✍️ الرد على الزبون", callback_data=f"reply_sup_{message.from_user.id}")
    ]])
    await bot.send_message(GROUPS["support"], msg, reply_markup=btns, parse_mode=ParseMode.HTML)
    await message.answer("✅ تم إرسال شكواك لفريق الدعم الفني، وسيتم الرد عليك هنا قريباً.", reply_markup=main_menu())
    await state.clear()

# لوحة المشرفين
@dp.callback_query(F.data.startswith("price_"))
async def admin_set_price(call: types.CallbackQuery, state: FSMContext):
    user_id = int(call.data.split("_")[1])
    await state.set_state(AdminReply.waiting_for_price)
    await state.update_data(reply_to_user=user_id)
    await call.message.reply("✏️ أرسل الآن السعر بالأرقام ليتم إرساله للزبون:")
    await call.answer()

@dp.message(AdminReply.waiting_for_price)
async def admin_send_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.reply("يرجى إرسال السعر أرقاماً فقط.")
    price = int(message.text)
    data = await state.get_data()
    user_id = data.get("reply_to_user")
    
    caption = (
        f"💰 **تم تحديد السعر لطلبك:** **{price:,} ل.س**\n\n"
        f"👤 **اسم الحساب:** `{SHAM_NAME}`\n"
        f"🔢 **كود التحويل (اضغط للنسخ):**\n`{SHAM_CODE}`\n\n"
        "لإتمام الطلب، يرجى التحويل إلى حساب شام كاش الموضح أعلاه ثم إرسال الإشعار."
    )
    try:
        if os.path.exists(QR_IMAGE_NAME):
            photo = FSInputFile(QR_IMAGE_NAME)
            await bot.send_photo(user_id, photo=photo, caption=caption, parse_mode=ParseMode.MARKDOWN)
        else:
            await bot.send_message(user_id, caption, parse_mode=ParseMode.MARKDOWN)
        await message.reply("✅ تم إرسال السعر للزبون بنجاح.")
    except Exception as e:
        await message.reply(f"⚠️ فشل إرسال السعر: {e}")
    await state.clear()

@dp.callback_query(F.data.startswith("reply_sup_"))
async def admin_support_reply(call: types.CallbackQuery, state: FSMContext):
    user_id = int(call.data.split("_")[2])
    await state.set_state(AdminReply.waiting_for_support_text)
    await state.update_data(reply_to_user=user_id)
    await call.message.reply("✏️ اكتب نص الرد على الزبون:")
    await call.answer()

@dp.message(AdminReply.waiting_for_support_text)
async def admin_send_support(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("reply_to_user")
    reply_msg = f"📩 **رد من فريق الدعم الفني:**\n\n{message.text}"
    try:
        await bot.send_message(user_id, reply_msg, parse_mode=ParseMode.MARKDOWN)
        await message.reply("✅ تم إرسال الرد إلى الزبون.")
    except Exception as e:
        await message.reply(f"⚠️ فشل إرسال الرسالة: {e}")
    await state.clear()

@dp.callback_query(F.data.startswith("done_"))
async def admin_action_done(call: types.CallbackQuery):
    user_id = call.data.split("_")[-1]
    try:
        await bot.send_message(user_id, "✅ **تم تنفيذ طلبك بنجاح!** شكراً لاستخدامك خدماتنا.")
    except:
        pass
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.reply("✅ تم تأكيد إتمام الطلب.")
    await call.answer()

@dp.callback_query(F.data.startswith("reject_"))
async def admin_action_reject(call: types.CallbackQuery):
    user_id = call.data.split("_")[1]
    try:
        await bot.send_message(user_id, "❌ **نعتذر منك، تم رفض الطلب أو تعذر تنفيذه حالياً.**")
    except:
        pass
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.reply("❌ تم تسجيل الرفض.")
    await call.answer()

async def main():
    print("🚀 جاري تشغيل البوت...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
