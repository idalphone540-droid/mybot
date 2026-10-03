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
BOT_TOKEN = os.getenv("BOT_TOKEN", "8774564171:AAGpWz69WLB76vYsLkPXIXiLOO-3rWt2RiQ").strip()
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
