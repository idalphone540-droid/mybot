import os
import asyncio
import logging
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

# بيانات شام كاش المعتمدة من الصورة
SHAM_NAME = "سكينه حمود طه"
SHAM_CODE = "be03739e320f3dfd318a1a7faebae16a"
QR_IMAGE_NAME = "1000027198.jpg" # اسم صورة الباركود المرفقة

# أيديات المجموعات والقناة من دفترك
GROUPS = {
    "balance": -1003745247353,         # مجموعة إدارة الرصيد (Syriatel / MTN)[span_26](start_span)[span_26](end_span)[span_27](start_span)[span_27](end_span)
    "games_chat": -1004426615122,      # مجموعة إدارة الألعاب وتطبيقات الشات[span_28](start_span)[span_28](end_span)[span_29](start_span)[span_29](end_span)
    "accounts": -1003985654158,        # مجموعة إدارة الحسابات الجاهزة[span_30](start_span)[span_30](end_span)[span_31](start_span)[span_31](end_span)
    "social": -1004411774893,          # مجموعة إدارة الأرقام وخدمات سوشيال ميديا[span_32](start_span)[span_32](end_span)[span_33](start_span)[span_33](end_span)
    "support": -1004420804667,         # مجموعة إدارة الدعم الفني والشكاوى[span_34](start_span)[span_34](end_span)[span_35](start_span)[span_35](end_span)
    "channel": -1004492385043          # القناة العامة للبوت (الاشتراك الإجباري)[span_36](start_span)[span_36](end_span)[span_37](start_span)[span_37](end_span)
}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class OrderFlow(StatesGroup):
    # حالات عامة للطلب والدفع
    selecting_service = State()
    target_phone = State()
    city = State()
    station_code = State()
    item_details = State()
    item_uid = State()
    social_link = State()
    waiting_receipt = State()
    waiting_txid = State()
    
    # دعم فني
    support_section = State()
    support_txid = State()
    support_text = State()

def main_menu():
    kb = [
        [KeyboardButton(text="📱 رصيد وكاش وكازية (Syriatel / MTN)")],
        [KeyboardButton(text="🎮 شحن الألعاب"), KeyboardButton(text="💬 شحن تطبيقات الشات")],
        [KeyboardButton(text="🛒 الحسابات الجاهزة"), KeyboardButton(text="📲 أرقام تفعيل")],
        [KeyboardButton(text="🚀 خدمات السوشيال ميديا"), KeyboardButton(text="📢 إعلانات ممولة فيسبوك")],
        [KeyboardButton(text="📩 الدعم الفني والشكاوى")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=GROUPS["channel"], user_id=user_id)
        if member.status not in ["left", "kicked"]:
            return True
    except Exception as e:
        logging.error(f"Error checking subscription: {e}")
    return False

async def send_payment_instructions(message: types.Message, amount: int, details_text: str):
    caption = (
        f"💳 **بيانات الدفع عبر شام كاش:**\n\n"
        f"👤 **اسم الحساب:** `{SHAM_NAME}`\n"
        f"🔢 **كود التحويل (اضغط للنسخ):**\n`{SHAM_CODE}`\n\n"
        f"📋 **الخدمة:** {details_text}\n"
        f"💰 **المبلغ المطلوب تحويله:** **{amount:,} ل.س**\n\n"
        f"📸 يرجى إتمام التحويل عبر باركود شام كاش أعلاه، ثم إرسال **صورة إشعار الدفع** أو **رقم العملية (TXID)** هنا:"
    )
    if os.path.exists(QR_IMAGE_NAME):
        photo = FSInputFile(QR_IMAGE_NAME)
        await message.answer_photo(photo=photo, caption=caption, parse_mode=ParseMode.MARKDOWN)
    else:
        await message.answer(caption, parse_mode=ParseMode.MARKDOWN)

@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if not await check_subscription(user_id):
        join_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 اشترك في قناة البوت الان", url=f"https://t.me/c/{str(GROUPS['channel'])[4:]}/1")], 
            [InlineKeyboardButton(text="✅ تحقق من الاشتراك", callback_data="check_sub")]
        ])
        return await message.answer(
            "⚠️ **عذراً، يجب عليك الاشتراك في قناة البوت أولاً لتتمكن من استخدامه.**\n\n"
            "يرجى الاشتراك ثم اضغط على زر (تحقق من الاشتراك):",
            reply_markup=join_kb,
            parse_mode=ParseMode.MARKDOWN
        )
    
    await message.answer(
        f"أهلاً بك **{message.from_user.full_name}** في بوت الخدمات الموحد 🌟\n\nيرجى اختيار الخدمة المطلوبة:",
        reply_markup=main_menu(),
        parse_mode=ParseMode.MARKDOWN
    )

@dp.callback_query(F.data == "check_sub")
async def verify_sub(call: types.CallbackQuery, state: FSMContext):
    if await check_subscription(call.from_user.id):
        await call.message.delete()
        await call.message.answer("✅ تم التحقق من اشتراكك بنجاح. اختر الخدمة المطلوبة:", reply_markup=main_menu())
    else:
        await call.answer("⚠️ لم تقم بالاشتراك في القناة بعد!", show_alert=True)

# 1. قسم الرصيد (Syriatel / MTN)
@dp.message(F.text == "📱 رصيد وكاش وكازية (Syriatel / MTN)")
async def balance_menu(message: types.Message, state: FSMContext):
    if not await check_subscription(message.from_user.id): return
    await state.clear()
    btns = [
        [InlineKeyboardButton(text="🔴 سيريتل (Syriatel)", callback_data="net_syriatel")],
        [InlineKeyboardButton(text="🟡 إم تي إن (MTN)", callback_data="net_mtn")]
    ]
    await message.answer("اختر الشبكة:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("net_"))
async def net_choice(call: types.CallbackQuery, state: FSMContext):
    net = call.data.split("_")[1]
    await state.update_data(network=net)
    btns = [
        [InlineKeyboardButton(text="📶 وحدات", callback_data="serv_units")],
        [InlineKeyboardButton(text="⛽ كازية جملة", callback_data="serv_gas")],
        [InlineKeyboardButton(text="🧾 فواتير", callback_data="serv_bills")],
        [InlineKeyboardButton(text="💵 كاش", callback_data="serv_cash")]
    ]
    await call.message.answer(f"اختر الخدمة لشبكة **{net.upper()}**:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), parse_mode=ParseMode.MARKDOWN)
    await call.answer()

@dp.callback_query(F.data.startswith("serv_"))
async def service_type_choice(call: types.CallbackQuery, state: FSMContext):
    serv = call.data.split("_")[1]
    await state.update_data(service=serv)
    data = await state.get_data()
    net = data.get("network")

    if serv == "gas":
        cities = ["دمشق", "ريف دمشق", "حلب", "حمص", "حماة", "اللاذقية", "طرطوس", "السويداء", "درعا", "القنيطرة", "دير الزور", "الحسكة", "الرقة"]
        kb = [[InlineKeyboardButton(text=c, callback_data=f"city_{c}")] for c in cities]
        await call.message.answer("اختر المحافظة:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await call.message.answer(f"أدخل رقم هاتف {net.upper()} (10 خانات):")
        await state.set_state(OrderFlow.target_phone)
    await call.answer()

@dp.callback_query(F.data.startswith("city_"))
async def city_choice(call: types.CallbackQuery, state: FSMContext):
    city = call.data.split("_")[1]
    await state.update_data(city=city)
    net = (await state.get_data()).get("network")
    code_len = 6 if net == "syriatel" else "متعدد"
    await call.message.answer(f"أدخل كود الكازية ({code_len}):")
    await state.set_state(OrderFlow.station_code)
    await call.answer()

@dp.message(OrderFlow.station_code)
async def station_code_step(message: types.Message, state: FSMContext):
    await state.update_data(station_code=message.text.strip())
    await message.answer("أدخل رقم خط الكازية (10 خانات):")
    await state.set_state(OrderFlow.target_phone)

@dp.message(OrderFlow.target_phone)
async def phone_step(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    await state.update_data(target_phone=phone)
    data = await state.get_data()
    
    await message.answer("أدخل الفئة أو المبلغ المطلوبة:")
    await state.set_state(OrderFlow.item_details)

@dp.message(OrderFlow.item_details)
async def balance_amount_step(message: types.Message, state: FSMContext):
    amount_text = message.text.strip()
    await state.update_data(item_details=amount_text)
    
    # حساب السعر تقريبياً أو حسب جداول الدفتر
    try:
        val = int(''.filter(str.isdigit, amount_text) or "1000")
    except:
        val = 1000
    
    data = await state.get_data()
    serv = data.get("service")
    if serv in ["cash", "bills"]:
        price = round(val * 1.05)
    elif serv == "gas":
        price = round(val * 1.07)
    else:
        price = val  # يتم ضبطها بناءً على الفئات المدونة بالدفتر

    await state.update_data(final_price=price)
    await send_payment_instructions(message, price, f"رصيد {data.get('network')} - {serv} - فئة: {amount_text}")
    await state.set_state(OrderFlow.waiting_receipt)

# 2. قسم الألعاب
@dp.message(F.text == "🎮 شحن الألعاب")
async def games_menu(message: types.Message, state: FSMContext):
    if not await check_subscription(message.from_user.id): return
    await state.clear()
    btns = [
        [InlineKeyboardButton(text="🟡 ببجي موبايل (PUBG)", callback_data="game_pubg")],
        [InlineKeyboardButton(text="💎 فري فاير (Free Fire)", callback_data="game_ff")],
        [InlineKeyboardButton(text="🃏 جواكر (Jawaker)", callback_data="game_jawaker")],
        [InlineKeyboardButton(text="🛡️ كلاش أوف كلانس (Clash of Clans)", callback_data="game_clash")],
        [InlineKeyboardButton(text="🔍 بحث عن لعبة أخرى", callback_data="game_other")]
    ]
    await message.answer("اختر اللعبة المطلوبة:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("game_"))
async def game_selection(call: types.CallbackQuery, state: FSMContext):
    g = call.data.split("_")[1]
    await state.update_data(game_type=g)
    if g == "other":
        await call.message.answer("أرسل اسم اللعبة والطلب المطلوب:")
    else:
        await call.message.answer("أرسل الفئة أو الباقة المطلوبة:")
    await state.set_state(OrderFlow.item_details)
    await call.answer()

# 3. قسم تطبيقات الشات
@dp.message(F.text == "💬 شحن تطبيقات الشات")
async def chat_menu(message: types.Message, state: FSMContext):
    if not await check_subscription(message.from_user.id): return
    await state.clear()
    await state.update_data(game_type="chat_app")
    await message.answer("أرسل اسم تطبيق الشات (مثل: SoulStar, SoulChill, Imo...) والكمية المطلوبة:")
    await state.set_state(OrderFlow.item_details)

# 4. استقبال الآيدي للألعاب والشات ثم طلب الدفع
@dp.message(OrderFlow.item_details)
async def item_details_step(message: types.Message, state: FSMContext):
    await state.update_data(item_details=message.text.strip())
    await message.answer("أرسل الآن **آيدي الحساب (Player ID)** أو المعرف الخاص بك:")
    await state.set_state(OrderFlow.item_uid)

@dp.message(OrderFlow.item_uid)
async def item_uid_step(message: types.Message, state: FSMContext):
    await state.update_data(item_uid=message.text.strip())
    await message.answer("أدخل السعر المطلوب (أو أرسل 0 إذا كنت تنتظر تسعير الإدارة، أو أدخل السعر المتفق عليه):")
    # كمثال نأخذ السعر أو نطلب إرساله للإدارة
    await state.set_state(OrderFlow.waiting_receipt)
    # للتبسيط نطلب الإشعار مباشرة أو السعر
    await message.answer("يرجى إتمام الدفع عبر شام كاش وإرسال الإشعار أو رقم العملية:")

# استقبال إيصال الدفع لجميع الأقسام وتحويله لمجموعة الإدارة
@dp.message(OrderFlow.waiting_receipt, F.photo | F.text)
async def receive_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_id = message.photo[-1].file_id if message.photo else None
    tx_text = message.text or (message.caption or "صورة إشعار دفع")
    
    order_details = (
        f"📥 **طلب جديد قيد التدقيق**\n"
        f"👤 الزبون: {message.from_user.mention_html()} (ID: <code>{message.from_user.id}</code>)\n"
        f"📱 البيانات: {data}\n"
        f"🔢 إشعار الدفع / TXID: <code>{tx_text}</code>"
    )
    
    btns = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ قبول وتنفيد", callback_data=f"accept_{message.from_user.id}"),
        InlineKeyboardButton(text="❌ رفض الطلب", callback_data=f"reject_{message.from_user.id}")
    ]])
    
    # التوجيه للمجموعة المناسبة حسب القسم
    target_group = GROUPS["games_chat"]
    if data.get("network"):
        target_group = GROUPS["balance"]
    elif data.get("game_type") in ["chat_app"]:
        target_group = GROUPS["games_chat"]
        
    if photo_id:
        await bot.send_photo(target_group, photo=photo_id, caption=order_details, reply_markup=btns, parse_mode=ParseMode.HTML)
    else:
        await bot.send_message(target_group, order_details, reply_markup=btns, parse_mode=ParseMode.HTML)
        
    await message.answer("✅ تم إرسال إشعار الدفع والطلب للإدارة بنجاح. جاري التدقيق والتنفيذ.", reply_markup=main_menu())
    await state.clear()

# أزرار تحكم الموظفين (قبول / رفض)
@dp.callback_query(F.data.startswith("accept_"))
async def accept_order(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    try:
        await bot.send_message(user_id, "✅ **تم قبول طلبك!** جاري تنفيذ الطلب الآن.")
    except:
        pass
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.reply("✅ تمت الموافقة وإبلاغ الزبون ببدء التنفيذ.")
    await call.answer()

@dp.callback_query(F.data.startswith("reject_"))
async def reject_order(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    try:
        await bot.send_message(user_id, "❌ **عذراً، تم رفض طلبك** أو أن إشعار الدفع غير صحيح. يراجع الدعم الفني.")
    except:
        pass
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.reply("❌ تم رفض الطلب وإبلاغ الزبون.")
    await call.answer()

async def main():
    print("🚀 البوت يعمل الآن بكامل الصلاحيات والهيكلية المطلوبة...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
