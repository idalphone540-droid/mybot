"""
Syria Store Bot - Wallet-First (Production)
aiogram 3.x + aiosqlite

التشغيل:
    pip install -U aiogram aiosqlite
    export BOT_TOKEN="xxxx"        # إلزامي (لا تضعه داخل الكود أبداً)
    export ADMIN_ID="5346581925"   # اختياري
    python syria_store_bot.py
"""
import asyncio
import base64
import difflib
import gzip
import hashlib
import html
import json
import logging
import math
import os
import random
import re
import shutil
import sqlite3
import string
import tempfile
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
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
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
    # الحسابات تذهب لمجموعة الأرقام والسوشيال. لفصلها لاحقاً ضع آيدي مجموعة جديدة في ACCOUNTS_ADMIN_GROUP
    "accounts": int(os.getenv("ACCOUNTS_ADMIN_GROUP", "0") or 0) or -1004411774893,
    "social": -1004411774893,
    "support": -1004420804667,
    # مجموعة مراجعة مكافآت الإحالة: ضع آيديها في REFERRAL_ADMIN_GROUP (وإلا تُرسل لمجموعة الإيداعات)
    "referral": int(os.getenv("REFERRAL_ADMIN_GROUP", "0") or 0) or -1003985654158,
}
ALL_ADMIN_GROUPS = list(GROUPS.values())
DEPOSIT_ADMIN_GROUP = GROUPS["wallet"]
REFERRAL_ADMIN_GROUP = GROUPS["referral"]
REFERRAL_TARGET = 5  # القيمة الافتراضية لعدد الإحالات المطلوبة لكل مكافأة (يعدّلها المدير من اللوحة)
ORDER_ID_START = 10000  # أرقام الطلبات تسلسلية: 10001، 10002، ...
# نسخة القاعدة الاحتياطية تُرسل إلى هذه المحادثة (اجعلها خاصة، والبوت مشرف فيها)
BACKUP_CHAT_ID = int(os.getenv("BACKUP_CHAT_ID", "-1004478472616") or 0)
BACKUP_INTERVAL_MIN = int(os.getenv("BACKUP_INTERVAL_MIN", "60"))
BACKUP_ONLY_IF_CHANGED = os.getenv("BACKUP_ONLY_IF_CHANGED", "0") == "1"
# كلمة سر تشفير النسخ الاحتياطية (اختيارية لكنها موصى بها). تتطلب مكتبة cryptography في requirements.txt
BACKUP_PASSWORD = os.getenv("BACKUP_PASSWORD", "")
TZ_OFFSET_HOURS = int(os.getenv("TZ_OFFSET_HOURS", "3"))        # توقيت سوريا UTC+3
REPORT_HOUR_LOCAL = int(os.getenv("REPORT_HOUR_LOCAL", "23"))  # ساعة إرسال التقرير اليومي بالتوقيت المحلي
STALE_ORDER_MIN = int(os.getenv("STALE_ORDER_MIN", "30"))      # تذكير بالطلبات المعلقة بعد X دقيقة
STALE_PAYMENT_MIN = int(os.getenv("STALE_PAYMENT_MIN", "15"))  # تذكير بالإيداعات غير المراجَعة
MAX_PENDING_DEPOSITS = int(os.getenv("MAX_PENDING_DEPOSITS", "3"))
MAX_DEPOSITS_PER_DAY = int(os.getenv("MAX_DEPOSITS_PER_DAY", "10"))
MAX_DECLINED_24H = int(os.getenv("MAX_DECLINED_24H", "3"))
THROTTLE_EVENTS = int(os.getenv("THROTTLE_EVENTS", "15"))      # أقصى عدد ضغطات/رسائل لكل مستخدم
THROTTLE_WINDOW = int(os.getenv("THROTTLE_WINDOW", "10"))      # خلال X ثانية
HEALTHCHECK_URL = os.getenv("HEALTHCHECK_URL", "").strip()     # رابط نبض خارجي (healthchecks.io) اختياري

SHAM_NAME = "سكينه حمود طه"
SHAM_ADDR = "be03739e320f3dfd318a1a7faebae16a"
QR_IMAGE_PATH = "qr_sham.jpg"
DB_PATH = os.getenv("DB_PATH", "syria_store_v2.db")
DEFAULT_MARGIN = float(os.getenv("DEFAULT_MARGIN", "5"))
BALANCE_DEFAULT_MARGIN = float(os.getenv("DEFAULT_MARGIN_BALANCE", "5"))
DEFAULT_DOLLAR_RATE = float(os.getenv("DOLLAR_RATE", "150"))

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

# أسعار التكلفة عليك (بالليرة). سعر البيع = التكلفة × (1 + نسبة ربح الرصيد) من /admin
SYR_UNITS = [
    (9.61, 10.27), (20.19, 21.58), (23.07, 24.65), (24.03, 25.68), (25.96, 27.74),
    (30.76, 32.88), (40.38, 43.16), (45.19, 48.30), (48.07, 51.38), (52.88, 56.52),
    (62.50, 66.80), (68.26, 72.96), (72.11, 77.07), (77.88, 83.24), (81.73, 87.35),
    (86.53, 92.49), (96.15, 102.77), (100.96, 107.92), (105.76, 113.04), (115.38, 123.33),
    (125.00, 133.61), (130.76, 139.76), (144.23, 154.17), (160.57, 171.63), (163.46, 174.72),
    (173.07, 184.99), (183.65, 196.30), (192.30, 205.55), (211.53, 226.10), (240.38, 256.93),
    (288.46, 308.32), (317.30, 339.16), (370.19, 395.69), (432.69, 462.49), (480.76, 513.87),
    (576.92, 616.66), (625.00, 668.04), (721.15, 770.82), (769.23, 822.19), (951.92, 1017.48),
]

MTN_UNITS = [
    (10, 10.69), (20, 21.38), (25, 26.72), (30, 32.07), (35, 37.41), (40, 42.75),
    (50, 53.44), (60, 64.14), (70, 74.82), (85, 90.85), (100, 106.04), (170, 181.71), (200, 213.78),
    (280, 299.28), (360, 384.79), (400, 427.55), (500, 534.44), (600, 641.32),
    (750, 801.66), (1000, 1068.87), (1500, 1603.31),
]

STATION_VALS = [
    (500, 535), (1000, 1070), (1500, 1605), (2000, 2140), (2500, 2675),
    (3000, 3210), (4000, 4280), (5000, 5350), (10000, 10700),
]

# ---------------------------------------------------------------------
# كتالوج الألعاب — أسعار الجملة بالدولار (التكلفة عليك).
# سعر البيع = الجملة × سعر الدولار × (1 + نسبة ربح الألعاب) — تُضبط من /admin
# لتعديل سعر أو إضافة فئة: عدّل السطر فقط. صيغة الفئة: ("الاسم", السعر_بالدولار)
# ---------------------------------------------------------------------
GAMES_CATALOG = {
    "pubg": {
        "emoji": "🔫", "name": "ببجي موبايل (PUBG)",
        "ask": "أرسل آيدي اللاعب:",
        "packs": [
            ("60 شدة", 1.0), ("120 شدة", 2.0), ("180 شدة", 3.0), ("300+25 شدة", 5.0),
            ("385 شدة", 6.0), ("600+60 شدة", 10.0), ("720 شدة", 11.0), ("985 شدة", 15.0),
            ("1320 شدة", 20.0), ("1500+300 شدة", 25.0), ("2125 شدة", 30.0),
            ("3000+850 شدة", 50.0), ("4510 شدة", 60.0), ("6000+2100 شدة", 100.0),
            ("10020 شدة", 125.0),
        ],
    },
    "ff": {
        "emoji": "🔥", "name": "فري فاير (جواهر)",
        "ask": "أرسل آيدي اللاعب:",
        "packs": [
            ("100+10 جوهرة", 1.0), ("210+20 جوهرة", 2.0), ("340 جوهرة", 3.3),
            ("460 جوهرة", 4.4), ("530+51 جوهرة", 5.5), ("811 جوهرة", 7.7),
            ("1080+120 جوهرة", 11.0), ("1162 جوهرة", 12.0), ("2200+240 جوهرة", 22.0),
            ("3641 جوهرة", 33.0), ("4880 جوهرة", 44.0),
        ],
    },
    "ffm": {
        "emoji": "🎖", "name": "فري فاير (عضويات)",
        "ask": "أرسل آيدي اللاعب:",
        "packs": [
            ("ترقية المستوى 6", 0.46), ("ترقية المستوى 10", 0.69), ("ترقية المستوى 15", 0.69),
            ("ترقية المستوى 20", 0.69), ("ترقية المستوى 25", 0.69), ("ترقية المستوى 30", 1.03),
            ("عضوية أسبوعية", 2.71), ("تصريح بوياه", 3.37), ("عضوية شهرية", 10.94),
            ("لفة 50 أسلحة (جينتوكي)", 16.68), ("لفات أسلحة إيفو (EVO VAULT)", 16.68),
        ],
    },
    "coc": {
        "emoji": "⚔️", "name": "كلاش أوف كلانس (CoC)",
        "ask": "أرسل الإيميل الذي تريد التفعيل عليه + رقم للتواصل:",
        "packs": [
            ("80 مجوهرة", 1.03), ("منتج بقيمة 0.99", 1.55), ("منتج بقيمة 2.99", 4.13),
            ("500 مجوهرة", 5.16), ("منتج بقيمة 3.99", 5.16), ("منتج بقيمة 4.99", 6.19),
            ("التذكرة الذهبية", 7.22), ("منتج بقيمة 6.99", 8.26), ("المناظر (سكنات القرية)", 8.26),
            ("المظاهر (سكنات الملوك)", 8.26), ("1200 مجوهرة", 10.32), ("منتج بقيمة 9.99", 11.35),
            ("تذكرة الحدث", 12.39), ("منتج بقيمة 12.99", 14.45), ("منتج بقيمة 14.99", 16.51),
            ("2500 مجوهرة", 20.64), ("منتج بقيمة 19.99", 21.67),
        ],
    },
    "cr": {
        "emoji": "👑", "name": "كلاش رويال",
        "ask": "أرسل الإيميل الذي تريد التفعيل عليه + رقم للتواصل:",
        "packs": [
            ("80 جوهرة", 1.03), ("500 جوهرة", 5.16), ("التذكرة المصغرة", 6.19),
            ("1200 جوهرة", 10.32), ("التذكرة الماسية", 12.39), ("2500 جوهرة", 20.64),
        ],
    },
    "brawl": {
        "emoji": "💥", "name": "براول ستارز",
        "ask": "أرسل الإيميل الذي تريد التفعيل عليه + رقم للتواصل:",
        "packs": [
            ("30 جوهرة", 2.06), ("80 جوهرة", 5.16), ("منتج بقيمة 3.99", 5.16),
            ("منتج بقيمة 4.99", 6.19), ("منتج بقيمة 5.99", 7.22), ("منتج بقيمة 6.99", 8.26),
            ("Brawl Pass", 9.29), ("المظاهر (السكنات)", 9.29), ("منتج بقيمة 7.99", 9.29),
            ("170 جوهرة", 10.32), ("منتج بقيمة 8.99", 10.32), ("منتج بقيمة 9.99", 11.35),
            ("Brawl Pass Plus", 13.42), ("المظاهر (السكنات) - فئة 2", 16.51),
            ("360 جوهرة", 20.64), ("Brawl Pass Pro", 25.80), ("950 جوهرة", 51.61),
            ("2000 جوهرة", 103.21),
        ],
    },
    "hayday": {
        "emoji": "🌾", "name": "هاي داي (Hay Day)",
        "ask": "أرسل الإيميل الذي تريد التفعيل عليه + رقم للتواصل:",
        "packs": [
            ("50+5 جوهرة", 2.06), ("130+13 جوهرة", 5.16), ("275+28 جوهرة", 10.32),
            ("فارم باس", 12.39), ("فارم باس بلاس", 18.58), ("570+57 جوهرة", 20.64),
        ],
    },
    "jawaker": {
        "emoji": "🃏", "name": "جواكر (Jawaker)",
        "ask": "أرسل آيدي اللاعب:",
        "tokens": {"min": 10000, "unit_syp": 0.150},  # شحن توكنز بالكمية (سعر الجملة بالليرة للتوكن)
        "packs": [
            ("مسرّع الأحمر 100%", 1.65), ("Premium (Black)", 6.19), ("مسرّع الأزرق 150%", 7.74),
            ("مسرّع الأسود 300%", 14.24), ("Premium Plus+ (Red)", 27.35),
            ("توكنز 400,000 VIP", 46.45), ("توكنز 525,000 VIP", 60.38), ("توكنز 805,000 VIP", 90.83),
        ],
    },
    "cod": {
        "emoji": "🎯", "name": "كول أوف ديوتي (CoD)",
        "ask": "أرسل رقم الزبون (واتساب):",
        "packs": [
            ("80 Points", 1.50), ("400+20 Points", 5.90), ("800+80 Points", 11.27),
            ("2000+400 Points", 27.90), ("3750+1250 Points", 55.79),
        ],
    },
    "fc": {
        "emoji": "⚽", "name": "FC (Silver / Point)",
        "ask": ("أرسل آيدي اللاعب + اسم السيرفر.\n"
                "السيرفرات: الكويت، قطر، البحرين، مصر، المغرب، العراق، تركيا، سنغافورة، تايلاند، "
                "إندونيسيا، كولومبيا، بيرو، تشيلي، الإكوادور، بوليفيا، باراغواي، نيجيريا، أستراليا، "
                "نيوزيلندا، الهند، بنغلادش، باكستان، نيبال، الجزائر، غانا، كينيا، تونس، السعودية، "
                "هونغ كونغ، جنوب أفريقيا، سريلانكا، الإمارات:"),
        "packs": [
            ("Silver 99", 1.23), ("Point 100", 1.23), ("Silver 499", 6.10), ("Point 520", 6.10),
            ("Silver 999", 12.08), ("Point 1070", 12.08), ("Silver 1999", 24.17),
            ("Point 2200", 24.17), ("Silver 4999", 60.42), ("Point 5750", 60.42),
            ("Silver 9999", 120.84), ("Point 12000", 120.84),
        ],
    },
    "efoot": {
        "emoji": "🥅", "name": "إي فوتبول (eFootball)",
        "ask": "أرسل رقم هاتف الزبون (واتساب):",
        "packs": [
            ("حزمة سواريز", 2.15), ("حزمة كاسياس", 4.29), ("300 كوينز", 5.90), ("550 كوينز", 6.97),
            ("750 كوينز", 8.58), ("1040 كوينز", 10.73), ("2130 كوينز", 21.46),
            ("3250 كوينز", 32.19), ("5700 كوينز", 53.11), ("12800 كوينز", 104.08),
        ],
    },
    "pubgp": {
        "emoji": "🎫", "name": "حزم الازدهار ببجي",
        "ask": "أرسل آيدي اللاعب:",
        "packs": [
            ("برايم شهر", 0.92), ("حزمة الشراء الأول", 0.94), ("عروض أسبوعية (1)", 0.94),
            ("حزمة ترقية الأسلحة", 2.77), ("برايم 3 أشهر", 2.77), ("عروض أسبوعية (2)", 2.78),
            ("الشعار الأسطوري الأسبوعي", 2.78), ("حزمة الشعار الخرافي", 4.63),
            ("برايم 6 أشهر", 5.55), ("Elite Pass (1-50)", 5.56), ("برايم بلاس شهر", 9.25),
            ("برايم 12 شهر", 11.10), ("Elite Pass (1-100)", 11.30),
            ("Elite Pass Plus (1-100)", 27.61), ("برايم بلاس 3 أشهر", 27.75),
            ("برايم بلاس 6 أشهر", 55.49), ("برايم بلاس 12 شهر", 110.97),
        ],
    },
    "sniper": {
        "emoji": "🎯", "name": "Pure Sniper",
        "ask": "أرسل آيدي اللاعب:",
        "packs": [
            ("900 Gold", 5.58), ("1900 Gold", 11.38), ("4300 Gold", 22.98),
            ("11000 Gold", 58.01), ("24000 Gold", 113.82),
        ],
    },
    "hok": {
        "emoji": "🗡", "name": "Honor Of Kings",
        "ask": "أرسل آيدي اللاعب فقط:",
        "packs": [
            ("400 Token", 5.47), ("800 Token", 10.94), ("2400 Token", 32.83),
            ("4000 Token", 54.72), ("8000 Token", 109.45),
        ],
    },
    "merge": {
        "emoji": "🏰", "name": "Merge Kingdoms",
        "ask": "أرسل آيدي اللاعب فقط:",
        "packs": [
            ("ألماس 1$", 1.17), ("ألماس 5$", 5.32), ("ألماس 30$", 29.77),
            ("ألماس 50$", 48.91), ("ألماس 100$", 96.75),
        ],
    },
    "lastwar": {
        "emoji": "🪖", "name": "Last War",
        "ask": "أرسل آيدي اللاعب + رقم للتواصل:",
        "packs": [
            ("منتج بقيمة 0.99", 1.56),
            ("منتج بقيمة 3.99", 5.21),
            ("منتج بقيمة 4.99", 6.25),
            ("منتج بقيمة 9.99", 11.47),
            ("WeeklyPass", 19.8),
            ("Season Battle Pass", 19.8),
            ("Dawn Fund", 19.8),
            ("منتج بقيمة 19.99", 22.93),
            ("Super Monthly Pass", 23.97),
            ("Overlord Growth Handbook", 23.97),
        ],
    },
    "pool8": {
        "emoji": "🎱", "name": "8 Ball Pool",
        "ask": "أرسل آيدي اللاعب:",
        "packs": [
            ("112000 Coins", 2.21),
            ("110 Cash", 2.21),
            ("256000 Coins", 4.42),
            ("250 Cash", 4.42),
            ("800000 Coins", 11.05),
            ("800 Cash", 11.05),
            ("2000 Cash", 22.11),
            ("2000000 Coins", 22.11),
        ],
    },
    "lords": {
        "emoji": "🏯", "name": "Lords Mobile",
        "ask": "أرسل آيدي اللاعب:",
        "packs": [
            ("195 ألماسة", 2.3),
            ("بطاقة أسبوعية", 2.3),
            ("395 ألماسة", 4.61),
            ("785 ألماسة", 8.59),
            ("1179 ألماسة", 14.67),
            ("1964 ألماسة", 24.09),
            ("3928 ألماسة", 48.19),
            ("7857 ألماسة", 95.33),
            ("11785 ألماسة", 142.47),
            ("19642 ألماسة", 237.79),
        ],
    },
    "whiteout": {
        "emoji": "❄️", "name": "Whiteout Survival",
        "ask": "أرسل آيدي اللاعب:",
        "packs": [
            ("99 ألماسة", 1.39),
            ("299 ألماسة", 4.17),
            ("499 ألماسة", 5.66),
            ("999 ألماسة", 11.22),
            ("1999 ألماسة", 22.76),
            ("4999 ألماسة", 56.09),
            ("9999 ألماسة", 112.18),
        ],
    },
    "genshin": {
        "emoji": "🌸", "name": "Genshin Impact",
        "ask": "أرسل آيدي اللاعب + السيرفر (أمريكا / أوروبا / آسيا / تايوان-هونغ كونغ-ماكاو) + اسم الشخصية في اللعبة:",
        "packs": [
            ("60 صلة زمنية", 1.03),
            ("بركة قمر الويلكين", 5.2),
            ("300+30 كريستالة", 5.2),
            ("980+110 كريستالة", 15.62),
            ("980+110 كرونال نيكسوس", 15.62),
            ("1980+260 كريستالة", 31.26),
            ("1980+260 كرونال نيكسوس", 31.26),
            ("3280+300 كريستالة", 52.11),
            ("6480+1600 كريستالة", 104.22),
            ("6480+1600 كرونال نيكسوس", 104.22),
        ],
    },
    "mlbb": {
        "emoji": "🛡", "name": "Mobile Legends",
        "ask": "أرسل آيدي اللاعب + السيرفر:",
        "packs": [
            ("ألماس 253+25", 4.57),
            ("ألماس 505+66", 9.14),
            ("ألماس 1010+182", 18.29),
            ("ألماس 1515+273", 27.43),
            ("ألماس 2525+480", 45.72),
            ("ألماس 3030+576", 54.86),
            ("ألماس 4008+802", 73.15),
            ("ألماس 5010+1002", 91.43),
        ],
    },
    "delta": {
        "emoji": "🔺", "name": "Delta Force Mobile",
        "ask": "أرسل آيدي اللاعب:",
        "packs": [
            ("60+Bonus", 1.09),
            ("300+Bonus", 4.93),
            ("420+Bonus", 6.57),
            ("680+Bonus", 8.65),
            ("1280+Bonus", 18.61),
            ("3280+Bonus", 47.06),
            ("6480+Bonus", 91.93),
            ("12960+Bonus", 207.95),
            ("19440+Bonus", 300.97),
        ],
    },
    "bloodstrike": {
        "emoji": "🩸", "name": "Blood Strike",
        "ask": "أرسل آيدي اللاعب:",
        "packs": [
            ("100+5 Gold", 0.93),
            ("300+20 Gold", 2.87),
            ("Strike Pass Elite", 3.52),
            ("500+40 Gold", 4.39),
            ("Strike Pass Premium", 7.95),
            ("1000+100 Gold", 8.79),
            ("2000+260 Gold", 17.6),
            ("5000+800 Gold", 44.09),
        ],
    },
    "arena": {
        "emoji": "🎒", "name": "Arena Breakout",
        "ask": "أرسل آيدي اللاعب:",
        "packs": [
            ("60+6 Bonds", 0.87),
            ("310+25 Bonds", 4.4),
            ("630+45 Bonds", 8.8),
            ("1580+110 Bonds", 22.0),
            ("3200+200 Bonds", 44.08),
            ("6500+320 Bonds", 88.01),
        ],
    },
    "pubgvn": {
        "emoji": "🇻🇳", "name": "ببجي فيتنام (PUBG VN)",
        "ask": "أرسل آيدي اللاعب:",
        "packs": [
            ("56 UC+Bonus", 1.38),
            ("140 UC+Bonus", 2.64),
            ("280 UC+Bonus", 5.16),
            ("560 UC+Bonus", 10.43),
            ("1400 UC+Bonus", 25.22),
            ("2800 UC+Bonus", 50.45),
        ],
    },
    "ludo": {
        "emoji": "🎲", "name": "يلا لودو (Yalla Ludo)",
        "ask": "أرسل آيدي اللاعب:",
        "packs": [
            ("2230 ألماس", 4.99),
            ("5150 ألماس", 9.97),
            ("27640 ألماس", 49.15),
            ("55800 ألماس", 99.16),
        ],
    },
    "tarbee3a": {
        "emoji": "🀄", "name": "تربيعة",
        "ask": "أرسل آيدي اللاعب:",
        "packs": [
            ("32,800 TopUp", 1.41),
            ("94,300 TopUp", 3.96),
            ("215,800 TopUp", 7.92),
            ("406,800 TopUp", 13.76),
            ("1,080,000 TopUp", 31.48),
            ("2,376,000 TopUp", 63.06),
            ("5,427,000 TopUp", 131.33),
        ],
    },
}
GAMES_PER_PAGE = 8
PACKS_PER_PAGE = 8

# ---------------------------------------------------------------------
# كتالوج الحسابات الجاهزة — أسعار الجملة بالدولار.
# سعر البيع = الجملة × سعر الدولار × (1 + نسبة ربح الحسابات) — تُضبط من /admin
# صيغة الفئة: ("الاسم", السعر_بالدولار) — و"notes" تظهر للزبون قبل الشراء.
# ---------------------------------------------------------------------
ACCOUNTS_CATALOG = {
    "chatgpt": {
        "emoji": "🤖", "name": "ChatGPT",
        "ask": "أرسل الإيميل (البريد الإلكتروني الذي تريد التفعيل عليه):",
        "packs": [("ChatGPT شهر مع ضمان", 6.13), ("ChatGPT Go شهر مع ضمان", 9.20), ("ChatGPT Plus شهر مع ضمان", 21.46)],
    },
    "netflix": {
        "emoji": "🎬", "name": "Netflix",
        "ask": "أرسل رقم للتواصل:",
        "packs": [("شهر - جهاز واحد", 4.09), ("سنة - جهاز واحد", 22.48)],
        "notes": ("• يتطلب التفعيل الاتصال بـ ExpressVPN على سيرفر مصر (Egypt) حصراً لإتمام الدخول.\n"
                  "• لشاشات LG وSamsung لا يدعم التطبيق الـ VPN مباشرة، ويلزم تشغيله عبر TV Box أو توصيل لابتوب "
                  "عبر HDMI أو بث المحتوى (Cast) من الهاتف."),
    },
    "iptv": {
        "emoji": "📺", "name": "IPTV",
        "ask": "أرسل رقم للتواصل:",
        "packs": [("اشتراك شهر", 2.04), ("اشتراك 3 شهور", 4.09), ("اشتراك سنة", 10.22)],
        "notes": ("• العملية يدوية وتستغرق بعض الوقت لتنفيذها.\n"
                  "• تحميل التطبيق عبر الرابط: aftv.news/5258786\n"
                  "• إدخال بيانات الاشتراك الخاصة بك والاستمتاع بالمشاهدة مباشرة."),
    },
    "shahid": {
        "emoji": "🎞", "name": "Shahid VIP",
        "ask": "أرسل رقم الموبايل:",
        "packs": [("شهر - شخصي غير مشترك (شاشة + موبايل)", 4.09), ("3 شهور - شخصي غير مشترك (شاشة + موبايل)", 8.18)],
    },
    "appleid": {
        "emoji": "🍎", "name": "Apple ID",
        "ask": "أرسل رقم الموبايل:",
        "packs": [("حساب متجر App Store", 1.12)],
        "notes": ("• العملية آلية وتعمل على مدار اليوم.\n"
                  "• يُستعمل الحساب فقط كـ Apple ID لتنزيل التطبيقات من App Store.\n"
                  "• لا يُستعمل نهائياً كحساب iCloud، والجهة غير مسؤولة عن استعماله كـ iCloud."),
    },
    "capcut": {
        "emoji": "✂️", "name": "CapCut Pro",
        "ask": "أرسل رقم التواصل:",
        "packs": [("شهر", 3.07), ("6 شهور", 11.24), ("سنة", 33.72)],
    },
    "anghami": {
        "emoji": "🎵", "name": "Anghami Plus",
        "ask": "أرسل رقم التواصل:",
        "packs": [("شهر", 3.58), ("6 أشهر", 12.26), ("سنة", 19.42)],
    },
    "canva": {
        "emoji": "🎨", "name": "Canva Pro",
        "ask": "أرسل الإيميل الذي تريد التفعيل عليه:",
        "packs": [("سنة", 2.0)],
    },
    "picsart": {
        "emoji": "🖼", "name": "Picsart",
        "ask": "أرسل رقم للتواصل:",
        "packs": [("حساب شخصي لمدة سنة", 15.33)],
    },
    "adobe": {
        "emoji": "🅰️", "name": "Adobe",
        "ask": "أرسل رقم للتواصل:",
        "packs": [("اشتراك سنة", 124.67)],
    },
    "gemini": {
        "emoji": "✨", "name": "Gemini Pro",
        "ask": "أرسل الإيميل الذي تريد التفعيل عليه:",
        "packs": [("سنة", 1.53)],
    },
    "perplexity": {
        "emoji": "🔎", "name": "Perplexity Pro",
        "ask": "أرسل رقم للتواصل:",
        "packs": [("اشتراك سنة", 42.92)],
    },
    "supergrok": {
        "emoji": "🧠", "name": "SuperGrok",
        "ask": "أرسل رقم للتواصل:",
        "packs": [("تفعيل 3 شهور", 36.79)],
    },
    "antigravity": {
        "emoji": "🚀", "name": "Google Antigravity",
        "ask": "أرسل رقم للتواصل:",
        "packs": [("تفعيل سنة", 35.77)],
    },
    "gmail": {
        "emoji": "📧", "name": "حساب Gmail",
        "ask": "أرسل رقم للتواصل:",
        "packs": [("حساب Gmail جديد", 1.02)],
    },
    "duolingo": {
        "emoji": "🦉", "name": "Duolingo",
        "ask": "أرسل رقم للتواصل:",
        "packs": [("سنة Super Duolingo", 1.02)],
    },
    "cursor": {
        "emoji": "⌨️", "name": "Cursor",
        "ask": "أرسل رقم للتواصل:",
        "packs": [("Cursor Pro - شهر", 19.42), ("Cursor Pro Plus - شهر", 61.31)],
    },
    "prime": {
        "emoji": "📦", "name": "Amazon Prime",
        "ask": "أرسل رقم للتواصل:",
        "packs": [("6 أشهر", 4.09)],
    },
    "eleven": {
        "emoji": "🎙", "name": "ElevenLabs Creator",
        "ask": "أرسل رقم للتواصل:",
        "packs": [("شهر", 9.20)],
    },
    "runway": {
        "emoji": "🎥", "name": "Runway Pro",
        "ask": "أرسل رقم للتواصل:",
        "packs": [("12 شهر", 34.74)],
    },
    "heygen": {
        "emoji": "🧑‍💼", "name": "Heygen Pro",
        "ask": "أرسل البريد الإلكتروني المسجل على Heygen + كلمة المرور (في رسالة واحدة):",
        "packs": [("خدمة Heygen Pro على الإيميل الشخصي", 17.37)],
    },
    "expressvpn": {
        "emoji": "🔐", "name": "ExpressVPN",
        "ask": "أرسل رقم تواصل:",
        "packs": [("شهر - كمبيوتر", 1.02), ("شهر - موبايل", 1.02), ("3 أشهر", 4.09), ("6 أشهر", 6.13), ("سنة", 12.26)],
    },
}
ACCOUNTS_PER_PAGE = 8

# ---------------------------------------------------------------------
# كتالوج السوشيال ميديا — أسعار الجملة بالدولار.
# سعر البيع = الجملة × سعر الدولار × (1 + نسبة ربح السوشيال) — تُضبط من /admin
# ---------------------------------------------------------------------
SOCIAL_PLATFORMS = {
    "fb": ("📘", "فيسبوك"),
    "ig": ("📸", "إنستغرام"),
    "tg": ("✈️", "تلغرام"),
}
SOCIAL_SERVICES = {
    "fb_ads": {"plat": "fb", "name": "إعلانات ممولة", "ask": "أرسل رقم هاتفك للتواصل وتجهيز الإعلان:",
        "packs": [
            ("لمدة يوم", 3.07),
            ("لمدة يومين", 6.13),
            ("لمدة 3 أيام", 9.2),
            ("لمدة 4 أيام", 12.26),
            ("لمدة 5 أيام", 15.33),
            ("لمدة 6 أيام", 18.39),
            ("لمدة 7 أيام", 21.46),
            ("لمدة 10 أيام", 30.66),
        ]},
    "fb_views": {"plat": "fb", "name": "مشاهدات فيديو / ريلز", "ask": "أرسل رابط الفيديو:",
        "packs": [
            ("5,000 مشاهدة", 1.53),
            ("10,000 مشاهدة", 2.04),
            ("50,000 مشاهدة", 10.22),
            ("100,000 مشاهدة", 20.44),
        ]},
    "fb_story": {"plat": "fb", "name": "تفاعل (ريأكشن) ستوري", "ask": "أرسل رابط الستوري:",
        "packs": [
            ("1,000 تفاعل", 0.61),
            ("5,000 تفاعل", 3.07),
            ("10,000 تفاعل", 6.13),
            ("50,000 تفاعل", 30.66),
        ]},
    "fb_likes": {"plat": "fb", "name": "لايكات منشور", "ask": "أرسل رابط المنشور:",
        "packs": [
            ("5,000 لايك", 4.09),
            ("10,000 لايك", 7.66),
            ("50,000 لايك", 36.79),
        ]},
    "fb_followers": {"plat": "fb", "name": "متابعين صفحات / حسابات", "ask": "أرسل رابط الصفحة:",
        "packs": [
            ("1,000 متابع", 0.72),
            ("5,000 متابع", 3.58),
            ("10,000 متابع", 7.15),
            ("50,000 متابع", 35.77),
        ]},
    "fb_comments": {"plat": "fb", "name": "تعليقات عربية عشوائية", "ask": "أرسل رابط المنشور:",
        "packs": [
            ("200 تعليق", 1.23),
            ("500 تعليق", 3.07),
            ("1,000 تعليق", 6.13),
            ("5,000 تعليق", 30.66),
        ]},
    "ig_views": {"plat": "ig", "name": "مشاهدات فيديو", "ask": "أرسل رابط الفيديو:",
        "packs": [
            ("500 ألف مشاهدة", 1.53),
            ("مليون مشاهدة", 3.07),
            ("5 ملايين مشاهدة", 10.22),
            ("10 ملايين مشاهدة", 20.44),
        ]},
    "ig_likes": {"plat": "ig", "name": "لايكات منشور", "ask": "أرسل رابط المنشور:",
        "packs": [
            ("5,000 لايك", 3.83),
            ("10,000 لايك", 7.66),
            ("50,000 لايك", 38.32),
        ]},
    "ig_comments": {"plat": "ig", "name": "تعليقات عربية عشوائية", "ask": "أرسل رابط المنشور:",
        "packs": [
            ("1,000 تعليق عربي عشوائي", 10.22),
        ]},
    "ig_followers": {"plat": "ig", "name": "متابعين", "ask": "أرسل رابط الصفحة:",
        "packs": [
            ("1,000 متابع (حسابات أجنبية)", 4.09),
            ("1,000 متابع (حسابات عربية)", 11.24),
            ("5,000 متابع", 15.33),
            ("10,000 متابع", 30.66),
        ]},
    "tg_members_f": {"plat": "tg", "name": "أعضاء قنوات وكروبات (حسابات أجنبية)", "ask": "أرسل رابط القناة:",
        "packs": [
            ("5,000 عضو", 2.55),
            ("10,000 عضو", 5.11),
            ("20,000 عضو", 10.22),
        ]},
    "tg_members_a": {"plat": "tg", "name": "أعضاء قنوات وكروبات (حسابات عربية)", "ask": "أرسل رابط القناة:",
        "packs": [
            ("1,000 عضو", 2.04),
            ("5,000 عضو", 10.22),
        ]},
    "tg_react": {"plat": "tg", "name": "تفاعل منشور", "ask": "أرسل رابط المنشور:",
        "packs": [
            ("1,000 تفاعل", 0.51),
            ("5,000 تفاعل", 2.55),
            ("10,000 تفاعل", 5.11),
        ]},
    "tg_views": {"plat": "tg", "name": "مشاهدات منشور", "ask": "أرسل رابط المنشور:",
        "packs": [
            ("5,000 مشاهدة", 1.02),
            ("50,000 مشاهدة", 10.22),
        ]},
    "tg_story": {"plat": "tg", "name": "رياكشن ستوري", "ask": "أرسل رابط الستوري:",
        "packs": [
            ("5,000 رياكشن", 1.02),
            ("10,000 رياكشن", 2.04),
        ]},
}
# ---------------------------------------------------------------------
# كتالوج أرقام التفعيل — أسعار الجملة بالدولار.
# سعر البيع = الجملة × سعر الدولار × (1 + نسبة ربح الأرقام) — تُضبط من /admin
# ---------------------------------------------------------------------
NUMBERS_CATALOG = {
    "wa": {"emoji": "🟢", "name": "رقم تفعيل واتساب", "ask": "أرسل رقم التواصل:", "usd": 3.00},
    "tg": {"emoji": "🔵", "name": "رقم تيلغرام أمريكي", "ask": "أرسل رقم التواصل:", "usd": 3.00},
    "apple": {"emoji": "🍎", "name": "رقم لإنشاء حساب آبل أمريكي", "ask": "أرسل رقم التواصل:", "usd": 3.00},
    "tiktok": {"emoji": "🎵", "name": "رقم تفعيل TikTok", "ask": "أرسل رقم التواصل:", "usd": 3.00},
}

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


async def seed_catalog(db):
    """ينقل الكتالوج المكتوب في الملف إلى القاعدة مرة واحدة فقط (إن كانت الجداول فارغة)."""
    cur = await db.execute("SELECT COUNT(*) FROM catalog_services")
    if (await cur.fetchone())[0] > 0:
        return
    await db.execute("BEGIN IMMEDIATE;")
    try:
        async def add_service(section, name, emoji, ask, notes="", kind="packs", platform="", mn=0, mp=0.0, up=0.0, tm=0, tu=0.0):
            c = await db.execute(
                "INSERT INTO catalog_services (section, platform, name, emoji, ask, notes, kind, min_qty, min_price, unit_price, tok_min, tok_unit) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (section, platform, name, emoji, ask, notes, kind, mn, mp, up, tm, tu),
            )
            return c.lastrowid

        async def add_packs(sid, packs):
            await db.executemany(
                "INSERT INTO catalog_packs (service_id, label, price, cur) VALUES (?, ?, ?, 'USD')",
                [(sid, label, price) for label, price in packs],
            )

        for g in GAMES_CATALOG.values():
            tk = g.get("tokens") or {}
            sid = await add_service("games", g["name"], g["emoji"], g["ask"], tm=tk.get("min", 0), tu=tk.get("unit_syp", 0.0))
            await add_packs(sid, g["packs"])
        for it in CHAT_ITEMS:
            if it["kind"] == "qty":
                await add_service("chat", it["name"], "💬", "أرسل آيدي اللاعب:", kind="qty",
                                  mn=it["min"], mp=it["min_price"], up=it["unit"])
            else:
                sid = await add_service("chat", it["name"], "💬", "أرسل آيدي اللاعب:")
                await add_packs(sid, it["packs"])
        for a in ACCOUNTS_CATALOG.values():
            sid = await add_service("accounts", a["name"], a["emoji"], a["ask"], notes=a.get("notes", ""))
            await add_packs(sid, a["packs"])
        for sv in SOCIAL_SERVICES.values():
            sid = await add_service("social", sv["name"], SOCIAL_PLATFORMS[sv["plat"]][0], sv["ask"], platform=sv["plat"])
            await add_packs(sid, sv["packs"])
        for n in NUMBERS_CATALOG.values():
            sid = await add_service("numbers", n["name"], n["emoji"], n["ask"])
            await add_packs(sid, [("رقم", n["usd"])])
        await db.execute("COMMIT;")
        log.info("catalog seeded from file constants")
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
            cost REAL,
            cancel_reason TEXT DEFAULT '',
            reminded INTEGER DEFAULT 0,
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
        await db.execute("CREATE TABLE IF NOT EXISTS bot_config (key TEXT PRIMARY KEY, value TEXT);")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS catalog_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section TEXT NOT NULL,
            platform TEXT DEFAULT '',
            name TEXT NOT NULL,
            emoji TEXT DEFAULT '',
            ask TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            kind TEXT NOT NULL DEFAULT 'packs' CHECK(kind IN ('packs', 'qty')),
            min_qty INTEGER DEFAULT 0,
            min_price REAL DEFAULT 0,
            unit_price REAL DEFAULT 0,
            tok_min INTEGER DEFAULT 0,
            tok_unit REAL DEFAULT 0,
            is_hidden INTEGER DEFAULT 0
        );""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS catalog_packs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER NOT NULL REFERENCES catalog_services(id) ON DELETE CASCADE,
            label TEXT NOT NULL,
            price REAL NOT NULL CHECK(price > 0),
            cur TEXT NOT NULL DEFAULT 'USD' CHECK(cur IN ('USD', 'SYP')),
            is_hidden INTEGER DEFAULT 0
        );""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_cat_services_section ON catalog_services(section, is_hidden);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_cat_packs_service ON catalog_packs(service_id, is_hidden);")
        await db.execute("CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY, val INTEGER NOT NULL);")
        await db.execute("INSERT OR IGNORE INTO counters (name, val) VALUES ('order', ?)", (ORDER_ID_START,))
        # ترحيل: أعمدة الإحالة في جدول المستخدمين
        cur = await db.execute("PRAGMA table_info(users)")
        ucols = {r[1] for r in await cur.fetchall()}
        if "referred_by" not in ucols:
            await db.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
        if "ref_enrolled" not in ucols:
            await db.execute("ALTER TABLE users ADD COLUMN ref_enrolled INTEGER DEFAULT 0")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            referred_id INTEGER PRIMARY KEY,
            referrer_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'COMPLETED')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            reward_id INTEGER
        );""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS referral_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            batch_no INTEGER NOT NULL,
            amount INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'PAID', 'REJECTED')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            decided_at TIMESTAMP,
            rtype TEXT NOT NULL DEFAULT 'balance',
            rtext TEXT NOT NULL DEFAULT '',
            UNIQUE(referrer_id, batch_no)
        );""")
        for tbl, col, ddl in (("referrals", "reward_id", "INTEGER"), ("referral_rewards", "rtype", "TEXT NOT NULL DEFAULT 'balance'"),
                              ("referral_rewards", "rtext", "TEXT NOT NULL DEFAULT ''")):
            cur = await db.execute(f"PRAGMA table_info({tbl})")
            if col not in {r[1] for r in await cur.fetchall()}:
                await db.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {ddl}")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id, status);")
        for tbl, col, ddl in (("orders", "cost", "REAL"), ("orders", "cancel_reason", "TEXT DEFAULT ''"),
                              ("orders", "reminded", "INTEGER DEFAULT 0"), ("payments", "reminded", "INTEGER DEFAULT 0"),
                              ("catalog_services", "sensitive", "INTEGER DEFAULT 0")):
            cur = await db.execute(f"PRAGMA table_info({tbl})")
            if col not in {r[1] for r in await cur.fetchall()}:
                await db.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {ddl}")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS staff_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            staff_id INTEGER NOT NULL,
            staff_name TEXT,
            action TEXT NOT NULL,
            ref TEXT,
            detail TEXT
        );""")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_status_created ON orders(status, created_at);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_payments_status_created ON payments(status, created_at);")
        await seed_catalog(db)
        await db.execute("UPDATE catalog_services SET sensitive=1 WHERE section='accounts' AND name LIKE 'Heygen%' AND sensitive=0")

        for k, v in (("dollar_rate", DEFAULT_DOLLAR_RATE), ("num_whatsapp", 400.0), ("num_telegram", 300.0), ("margin_games", DEFAULT_MARGIN), ("margin_chat", DEFAULT_MARGIN), ("margin_accounts", DEFAULT_MARGIN), ("margin_social", DEFAULT_MARGIN), ("margin_numbers", DEFAULT_MARGIN), ("margin_balance", BALANCE_DEFAULT_MARGIN), ("margin_station", 7.0), ("margin_invoice", 5.0), ("margin_cash", 5.0), ("referral_reward", 0.0), ("referral_percent", 0.0), ("referral_target", float(REFERRAL_TARGET))):
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


# قناة الاشتراك الإجباري الافتراضية: https://t.me/Syriansto (يمكن تغييرها من /admin أو من متغيرات البيئة)
ENV_CONFIG = {
    "force_channel": os.getenv("FORCE_CHANNEL", "-1003772883011").strip(),
    "force_link": os.getenv("FORCE_LINK", "https://t.me/Syriansto").strip(),
}


async def get_config(key: str, default: str = "") -> str:
    """إعدادات نصية. القيمة المحفوظة من لوحة المدير أولى، ثم متغير البيئة."""
    async with get_db() as db:
        cur = await db.execute("SELECT value FROM bot_config WHERE key=?", (key,))
        row = await cur.fetchone()
    if row and row[0] not in (None, ""):
        return row[0]
    return ENV_CONFIG.get(key) or default


async def set_config(key: str, value: str):
    async with get_db() as db:
        await db.execute(
            "INSERT INTO bot_config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


async def force_channel_ref():
    ch = await get_config("force_channel")
    if ch in ("", "off"):
        return None
    return int(ch) if ch.lstrip("-").isdigit() else ch


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
    async def create_order(user_id: int, dept: str, service: str, target: str, price: int,
                           cost: Optional[float] = None) -> Tuple[str, int, Optional[str]]:
        """خصم + رقم تسلسلي + إنشاء الطلب + قيد المحفظة في معاملة واحدة.
        يرجع (OK|NO_FUNDS|ERROR، الرصيد، رقم الطلب)."""
        if price <= 0:
            return "ERROR", 0, None
        try:
            async with write_tx() as db:
                cur = await db.execute(
                    "UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ? AND is_banned = 0",
                    (price, user_id, price),
                )
                if cur.rowcount == 0:
                    cur = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
                    r = await cur.fetchone()
                    return "NO_FUNDS", (r[0] if r else 0), None
                cur = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
                new_bal = (await cur.fetchone())[0]
                await db.execute("INSERT OR IGNORE INTO counters (name, val) VALUES ('order', ?)", (ORDER_ID_START,))
                await db.execute("UPDATE counters SET val = val + 1 WHERE name = 'order'")
                cur = await db.execute("SELECT val FROM counters WHERE name = 'order'")
                order_id = str((await cur.fetchone())[0])
                await db.execute(
                    "INSERT INTO orders (order_id, user_id, department, service_name, target_data, price, status, cost) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'PROCESSING', ?)",
                    (order_id, user_id, dept, service, target, price, cost),
                )
                await db.execute(
                    "INSERT INTO wallet_ledger (user_id, reference_id, type, amount, balance_after, note) "
                    "VALUES (?, ?, 'PURCHASE', ?, ?, ?)",
                    (user_id, order_id, -price, new_bal, f"شراء: {service}"),
                )
                return "OK", new_bal, order_id
        except Exception as e:
            log.error("create_order error: %s", e)
            return "ERROR", 0, None

    @staticmethod
    async def refund(order_id: str, reason: str = "") -> Tuple[bool, int, int]:
        try:
            async with write_tx() as db:
                cur = await db.execute("SELECT user_id, price FROM orders WHERE order_id = ? AND status = 'PROCESSING'", (order_id,))
                order = await cur.fetchone()
                if not order:
                    return False, 0, 0
                cur = await db.execute(
                    "UPDATE orders SET status = 'REFUNDED', cancel_reason = ? WHERE order_id = ? AND status = 'PROCESSING'",
                    (reason, order_id),
                )
                if cur.rowcount == 0:
                    return False, 0, 0
                user_id, price = order
                nb = await WalletService._credit(db, user_id, price, order_id, "REFUND", "استرجاع قيمة طلب")
                if nb is None:
                    raise RuntimeError("user missing")
                await WalletService._scrub_if_sensitive(db, order_id)
                return True, user_id, price
        except Exception as e:
            log.error("Refund error: %s", e)
            return False, 0, 0

    @staticmethod
    async def _scrub_if_sensitive(db, order_id: str):
        """يمسح بيانات الطلب الحساسة (مثل كلمات المرور) بعد انتهائه إن كانت الخدمة معلَّمة حساسة."""
        cur = await db.execute("SELECT service_name FROM orders WHERE order_id = ?", (order_id,))
        row = await cur.fetchone()
        if not row:
            return
        cur = await db.execute(
            "SELECT 1 FROM catalog_services WHERE sensitive = 1 AND ? LIKE name || '%' LIMIT 1", (row[0],)
        )
        if await cur.fetchone():
            await db.execute("UPDATE orders SET target_data = '[🔒 حُذفت بعد التنفيذ لأسباب أمنية]' WHERE order_id = ?", (order_id,))

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
            if not cur.rowcount:
                return None
            await WalletService._scrub_if_sensitive(db, order_id)
            return (row[0], row[1])

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
    async def admin_debit(user_id: int, amount: int, ref_id: str, note: str = "") -> Optional[int]:
        """سحب رصيد إداري ذري. يرجع الرصيد الجديد أو None إن لم يكفِ الرصيد/المستخدم غير موجود."""
        if amount <= 0:
            return None
        try:
            async with write_tx() as db:
                cur = await db.execute(
                    "UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?", (amount, user_id, amount)
                )
                if cur.rowcount == 0:
                    return None
                cur = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
                nb = (await cur.fetchone())[0]
                await db.execute(
                    "INSERT INTO wallet_ledger (user_id, reference_id, type, amount, balance_after, note) "
                    "VALUES (?, ?, 'ADMIN_DEBIT', ?, ?, ?)",
                    (user_id, ref_id, -amount, nb, note),
                )
                return nb
        except Exception as e:
            log.error("admin_debit error: %s", e)
            return None

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
        table = "orders" if (ref.startswith("ORD-") or ref.isdigit()) else "payments" if ref.startswith("PAY-") else None
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
    set_margin = State()
    find_user = State()
    msg_user = State()
    set_channel = State()
    cat_edit = State()
    cat_pack_add = State()
    cat_new_name = State()
    cat_new_ask = State()
    cat_new_qty = State()
    set_reward = State()
    set_reward_pct = State()
    set_ref_target = State()
    set_ref_text = State()
    set_margin_all = State()
    find_order = State()
    add_staff = State()
    broadcast_msg = State()


class ChatInput(StatesGroup):
    entering_id = State()
    entering_data = State()
    confirm = State()


class GameTokens(StatesGroup):
    entering = State()


class ChatSearch(StatesGroup):
    query = State()




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


_INVISIBLE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff\u00ad\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(s: str) -> str:
    """يزيل الرموز الخفية (اتجاه النص، المسافات الصفرية، رموز التحكم) التي تفسد نسخ الآيديات."""
    return _INVISIBLE.sub("", s or "").strip()


def txt(m: types.Message) -> str:
    return clean_text(m.text or "")


AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalize_digits(s: str) -> str:
    return (s or "").translate(AR_DIGITS)


def to_int(s: str) -> Optional[int]:
    s = normalize_digits(s).replace(",", "").replace("٬", "").strip()
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
    for attempt in range(3):
        try:
            if photo:
                await bot.send_photo(group_id, photo=photo, caption=text, reply_markup=kb)
            else:
                await bot.send_message(group_id, text, reply_markup=kb)
            return True
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except Exception as e:
            log.error("send_to_staff group=%s attempt=%s failed: %s", group_id, attempt + 1, e)
            await asyncio.sleep(1.5 * (attempt + 1))
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
        [B("🔍 بحث عن خدمة", "cse:all")],
        [B("📞 الرصيد والكاش", "sec:balance"), B("🎮 شحن الألعاب", "sec:games")],
        [B("💬 برامج الشات", "sec:chat"), B("📦 الحسابات الرقمية", "sec:accounts")],
        [B("🚀 سوشيال ميديا", "sec:social"), B("📱 أرقام التفعيل", "sec:numbers")],
        [B("📦 طلباتي", "client:orders"), B("💳 كشف المحفظة", "client:wallet_info")],
        [B("🎁 شارك واربح", "ref:home"), B("🛠 الدعم والشكاوى", "sec:support")],
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


_sub_cache: Dict[int, float] = {}
_sub_warn_at = 0.0


async def check_subscription(user_id: int) -> bool:
    global _sub_warn_at
    ref = await force_channel_ref()
    if not ref:
        return True
    now = time.monotonic()
    if _sub_cache.get(user_id, 0) > now:
        return True
    try:
        m = await bot.get_chat_member(ref, user_id)
        ok = m.status in ("member", "administrator", "creator") or (m.status == "restricted" and getattr(m, "is_member", False))
    except Exception as e:
        # لا نقفل البوت على الجميع إذا تعذر الفحص (مثلاً البوت ليس مشرفاً في القناة)
        log.error("subscription check failed: %s", e)
        if now - _sub_warn_at > 600:
            _sub_warn_at = now
            try:
                await bot.send_message(ADMIN_ID, "⚠️ تعذر فحص الاشتراك الإجباري. تأكد أن البوت <b>مشرف</b> في القناة وأن المعرف صحيح. "
                                                 "تم السماح للمستخدمين مؤقتاً.")
            except Exception:
                pass
        return True
    if ok:
        _sub_cache[user_id] = now + 120
    return ok


async def send_sub_prompt(event):
    link = await get_config("force_link")
    if not link:
        ref = await force_channel_ref()
        if isinstance(ref, str) and ref.startswith("@"):
            link = f"https://t.me/{ref[1:]}"
        elif isinstance(ref, int):
            # قناة خاصة بلا رابط محدد: ننشئ رابط دعوة تلقائياً (يتطلب أن يكون البوت مشرفاً بصلاحية الدعوة)
            try:
                link = await bot.export_chat_invite_link(ref)
                await set_config("force_link", link)
            except Exception as e:
                log.warning("could not create invite link: %s", e)
    rows = []
    if link:
        rows.append([InlineKeyboardButton(text="📣 الاشتراك في القناة", url=link)])
    rows.append([B("تحقق من الاشتراك ✅", "chk_sub")])
    text = ("📣 <b>للاستفادة من البوت يجب الاشتراك في قناتنا أولاً.</b>\n\n"
            "اشترك في القناة ثم اضغط «تحقق من الاشتراك ✅».")
    try:
        if isinstance(event, types.CallbackQuery):
            await event.answer("⚠️ اشترك في القناة أولاً.", show_alert=True)
            await bot.send_message(event.from_user.id, text, reply_markup=KB(rows))
        else:
            await event.answer(text, reply_markup=KB(rows))
    except Exception as e:
        log.warning("send_sub_prompt failed: %s", e)


class AccessGateMiddleware(BaseMiddleware):
    """وضع الصيانة + الاشتراك الإجباري في المحادثات الخاصة (المدير مستثنى)."""

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        chat = data.get("event_chat")
        if not user or user.is_bot or not chat or chat.type != "private" or user.id == ADMIN_ID:
            return await handler(event, data)
        if await get_config("maintenance") == "1":
            try:
                if isinstance(event, types.CallbackQuery):
                    await event.answer("🛠 البوت في وضع الصيانة حالياً، سنعود قريباً.", show_alert=True)
                else:
                    await event.answer("🛠 البوت في وضع الصيانة حالياً، سنعود قريباً.")
            except Exception:
                pass
            return None
        if isinstance(event, types.CallbackQuery) and event.data == "chk_sub":
            return await handler(event, data)
        if not await check_subscription(user.id):
            await send_sub_prompt(event)
            return None
        return await handler(event, data)


_throttle: Dict[int, list] = {}
_throttle_warned: Dict[int, float] = {}


class ThrottleMiddleware(BaseMiddleware):
    """حد لسرعة التفاعل لكل مستخدم (ضد الإغراق). المدير مستثنى."""

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        chat = data.get("event_chat")
        if not user or user.is_bot or user.id == ADMIN_ID or not chat or chat.type != "private":
            return await handler(event, data)
        now = time.monotonic()
        if len(_throttle) > 5000:
            for k in [k for k, v in _throttle.items() if not v or now - v[-1] > THROTTLE_WINDOW]:
                _throttle.pop(k, None)
        q = _throttle.setdefault(user.id, [])
        while q and now - q[0] > THROTTLE_WINDOW:
            q.pop(0)
        q.append(now)
        if len(q) > THROTTLE_EVENTS:
            try:
                if isinstance(event, types.CallbackQuery):
                    await event.answer("⏳ مهلاً، تفاعلات كثيرة بسرعة.")
                elif now - _throttle_warned.get(user.id, 0) > THROTTLE_WINDOW:
                    _throttle_warned[user.id] = now
                    await event.answer("⏳ الرجاء التمهل قليلاً ثم أعد المحاولة.")
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


dp.message.outer_middleware(ThrottleMiddleware())
dp.callback_query.outer_middleware(ThrottleMiddleware())
dp.message.outer_middleware(UserGuardMiddleware())
dp.callback_query.outer_middleware(UserGuardMiddleware())
dp.message.outer_middleware(AccessGateMiddleware())
dp.callback_query.outer_middleware(AccessGateMiddleware())
dp.callback_query.middleware(AutoAnswerMiddleware())


_last_err_alert: Dict[str, float] = {}


async def alert_admin_error(exc: BaseException):
    """ينبّه المدير بخطأ غير متوقع (مرة كل 5 دقائق لكل نوع خطأ)."""
    key = f"{type(exc).__name__}:{str(exc)[:80]}"
    now = time.monotonic()
    if now - _last_err_alert.get(key, 0) < 300:
        return
    _last_err_alert[key] = now
    try:
        await bot.send_message(ADMIN_ID, f"🚨 <b>خطأ غير متوقع في البوت</b>\n<code>{esc(key)}</code>")
    except Exception:
        pass


@dp.error()
async def global_error_handler(event: ErrorEvent):
    log.exception("Unhandled error: %s", event.exception)
    await alert_admin_error(event.exception)
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
@dp.message(CommandStart(deep_link=True), F.chat.type == "private")
async def start_deeplink(message: types.Message, command: CommandObject, state: FSMContext):
    arg = command.args or ""
    if arg.startswith("ref_"):
        rid = to_int(arg[4:])
        if rid:
            try:
                await register_referral(message.from_user.id, rid)
            except Exception as e:
                log.warning("register_referral failed: %s", e)
    await start_handler(message, state)


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


@dp.callback_query(F.data == "chk_sub")
async def chk_sub_cb(cb: types.CallbackQuery, state: FSMContext):
    _sub_cache.pop(cb.from_user.id, None)
    if await check_subscription(cb.from_user.id):
        await state.clear()
        u = await WalletService.get_or_create_user(cb.from_user.id)
        await safe_edit(cb, format_home_text(u), main_dashboard_kb())
    else:
        await cb.answer("⚠️ لم نجد اشتراكك بعد. اشترك في القناة ثم اضغط تحقق.", show_alert=True)


async def admin_counts() -> Tuple[int, int]:
    async with get_db() as db:
        o = (await (await db.execute("SELECT COUNT(*) FROM orders WHERE status='PROCESSING'")).fetchone())[0]
        p = (await (await db.execute("SELECT COUNT(*) FROM payments WHERE status='UNDER_REVIEW'")).fetchone())[0]
    return o, p


async def admin_kb():
    o, p = await admin_counts()
    return KB([
        [B("📊 الإحصائيات", "adm:stats")],
        [B(f"📋 الطلبات المعلقة ({o})", "adm:pend"), B(f"💳 الإيداعات المعلقة ({p})", "adm:payp")],
        [B("🗂 إدارة الخدمات", "adm:cat"), B("🎁 الإحالة", "adm:ref")],
        [B("👤 إدارة مستخدم", "adm:user"), B("🔎 بحث عن طلب", "adm:findo")],
        [B("📈 تقرير اليوم", "adm:report:0"), B("📉 تقرير الأمس", "adm:report:1")],
        [B("🧮 مطابقة الأرصدة", "adm:recon"), B("🧾 سجل الإجراءات", "adm:audit")],
        [B("👮 الموظفون", "adm:staff")],
        [B("➕ تغذية رصيد", "adm:add_bal"), B("➖ سحب رصيد", "adm:sub_bal")],
        [B("💱 سعر الدولار", "adm:set_rate"), B("📈 نسب الربح", "adm:margin")],
        [B("📣 الاشتراك الإجباري", "adm:fsub"), B("🛠 وضع الصيانة", "adm:maint")],
        [B("📢 إذاعة جماعية", "adm:broadcast"), B("💾 نسخة احتياطية", "adm:backup")],
        [B("❌ إغلاق اللوحة", "adm:close")],
    ])


async def admin_title() -> str:
    maint = await get_config("maintenance") == "1"
    ref = await force_channel_ref()
    title = await get_config("force_title")
    rate = await get_setting("dollar_rate")
    return (
        "⚙️ <b>لوحة تحكم المدير</b>\n"
        "────────────────────────────\n"
        f"💱 سعر الدولار: <b>{rate:,.2f} ل.س</b>\n"
        f"🛠 وضع الصيانة: {'🔴 مفعّل' if maint else '🟢 متوقف'}\n"
        f"📣 الاشتراك الإجباري: {('🟢 ' + esc(str(title or ref))) if ref else '⚪ متوقف'}"
    )


@dp.message(Command("admin"), F.chat.type == "private")
async def admin_panel_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.reply("⛔ هذا الأمر مخصص للمدير العام فقط!")
        return
    await state.clear()
    await message.answer(await admin_title(), reply_markup=await admin_kb())


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
LEDGER_LABEL = {"DEPOSIT": "➕ إيداع", "PURCHASE": "🛒 شراء", "REFUND": "↩️ استرجاع",
                "ADMIN_DEBIT": "➖ سحب إداري", "REFERRAL": "🎁 مكافأة إحالة"}


async def ledger_lines(uid: int, limit: int = 10) -> str:
    rows = await fetch_all(
        "SELECT type, amount, balance_after, created_at FROM wallet_ledger WHERE user_id=? ORDER BY ledger_id DESC LIMIT ?",
        (uid, limit),
    )
    if not rows:
        return "—"
    return "\n".join(f"{LEDGER_LABEL.get(r['type'], r['type'])} {r['amount']:+,} → {r['balance_after']:,} · {str(r['created_at'])[5:16]}"
                     for r in rows)


@dp.callback_query(F.data == "client:wallet_info")
async def wallet_info_view(cb: types.CallbackQuery):
    u = await WalletService.get_or_create_user(cb.from_user.id)
    text = (
        f"💳 <b>بيانات محفظتك الإلكترونية</b>\n"
        f"────────────────────────────\n"
        f"💰 الرصيد المتاح: <b>{u[2]:,} ل.س</b>\n"
        f"🆔 معرّف الحساب: <code>{u[0]}</code>\n\n"
        f"🧾 <b>آخر الحركات:</b>\n{await ledger_lines(u[0])}\n\n"
        f"• يمكنك استخدام هذا الرصيد لشراء أي خدمة فورياً بضغطة زر دون الحاجة للتحويل في كل مرة."
    )
    await safe_edit(cb, text, KB([[B("➕ شحن رصيد إضافي", "wallet:topup")], [B("🔙 العودة للرئيسية", "back_home")]]))


@dp.callback_query(F.data == "wallet:topup")
async def wallet_topup_start(cb: types.CallbackQuery, state: FSMContext):
    reason = await deposit_block_reason(cb.from_user.id)
    if reason:
        await safe_edit(cb, reason, HOME_KB)
        return
    await state.clear()
    await state.set_state(WalletFlow.tx_code)
    pay_text = (
        f"💵 <b>شحن المحفظة عبر شام كاش</b>\n"
        f"────────────────────────────\n"
        f"👤 الاسم: <code>{esc(SHAM_NAME)}</code>\n"
        f"🔗 العنوان: <code>{esc(SHAM_ADDR)}</code>\n"
        f"────────────────────────────\n"
        f"1️⃣ حوّل المبلغ عبر شام كاش إلى الحساب أعلاه.\n"
        f"2️⃣ أرسل هنا <b>رقم العملية (Transaction ID)</b> — أرقام فقط:"
    )
    if os.path.exists(QR_IMAGE_PATH):
        try:
            if isinstance(cb.message, types.Message):
                await cb.message.delete()
        except Exception:
            pass
        await bot.send_photo(cb.from_user.id, FSInputFile(QR_IMAGE_PATH), caption=pay_text, reply_markup=cancel_kb())
    else:
        await safe_edit(cb, pay_text, cancel_kb())


_decl_alert_at: Dict[int, float] = {}


async def deposit_block_reason(uid: int) -> Optional[str]:
    """حدود الإساءة: إيداعات معلقة كثيرة، أو عدد يومي كبير، أو رفض متكرر."""
    r = await fetch_one(
        "SELECT COALESCE(SUM(status='UNDER_REVIEW'), 0) AS pend, "
        "COALESCE(SUM(created_at >= datetime('now', '-1 day')), 0) AS day_n, "
        "COALESCE(SUM(status='DECLINED' AND created_at >= datetime('now', '-1 day')), 0) AS dec_n "
        "FROM payments WHERE user_id=?", (uid,)
    )
    if r["dec_n"] >= MAX_DECLINED_24H:
        now = time.monotonic()
        if now - _decl_alert_at.get(uid, 0) > 6 * 3600:
            _decl_alert_at[uid] = now
            try:
                await bot.send_message(ADMIN_ID, f"🚨 المستخدم <code>{uid}</code> لديه {r['dec_n']} إيداعات مرفوضة خلال 24 ساعة، وتم إيقاف طلباته الجديدة مؤقتاً.")
            except Exception:
                pass
        return "⛔ تم إيقاف طلبات الإيداع مؤقتاً بسبب تكرار الطلبات المرفوضة. يرجى التواصل مع الدعم الفني."
    if r["pend"] >= MAX_PENDING_DEPOSITS:
        return f"⏳ لديك {r['pend']} طلبات إيداع قيد المراجعة. انتظر تأكيدها قبل إرسال طلب جديد."
    if r["day_n"] >= MAX_DEPOSITS_PER_DAY:
        return "⛔ بلغت الحد الأقصى لطلبات الإيداع اليوم. حاول غداً أو تواصل مع الدعم."
    return None


async def tx_exists(tx_code: str) -> bool:
    async with get_db() as db:
        cur = await db.execute("SELECT 1 FROM payments WHERE sham_tx_id = ?", (tx_code,))
        return await cur.fetchone() is not None


@dp.message(WalletFlow.tx_code)
async def wallet_tx_rec(message: types.Message, state: FSMContext):
    tx_code = re.sub(r"[\s\-_.,]", "", normalize_digits(txt(message)))
    if not tx_code.isdigit() or not (4 <= len(tx_code) <= 30):
        await message.reply("⚠️ رقم العملية يجب أن يتكون من أرقام فقط (من 4 إلى 30 رقماً). أعد إرساله:")
        return
    if await tx_exists(tx_code):
        await message.reply("⛔ رقم العملية هذا مستخدم مسبقاً! يرجى إدخال رقم صحيح:")
        return
    await state.update_data(sham_tx=tx_code)
    await state.set_state(WalletFlow.amount)
    await message.answer(
        f"💰 الآن أرسل <b>المبلغ المحوَّل</b> بالليرة السورية (أقل مبلغ {MIN_TOPUP:,} ل.س):",
        reply_markup=cancel_kb(),
    )


@dp.message(WalletFlow.amount)
async def wallet_amt_rec(message: types.Message, state: FSMContext):
    amt = to_int(txt(message))
    if amt is None or amt < MIN_TOPUP or amt > 1_000_000_000:
        await message.reply(f"⚠️ يرجى إدخال مبلغ صحيح بالأرقام (الحد الأدنى {MIN_TOPUP:,} ل.س):")
        return
    data = await state.get_data()
    tx_code = data.get("sham_tx", "")
    if not tx_code:
        await state.clear()
        await message.answer("⚠️ انتهت جلسة الشحن، يرجى البدء من جديد.", reply_markup=KB([[B("➕ شحن المحفظة", "wallet:topup")]]))
        return

    reason = await deposit_block_reason(message.from_user.id)
    if reason:
        await state.clear()
        await message.answer(reason, reply_markup=HOME_KB)
        return
    pay_id = generate_uid("PAY")
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO payments (payment_id, user_id, method, amount, sham_tx_id) VALUES (?, ?, 'SHAM_CASH', ?, ?)",
                (pay_id, message.from_user.id, amt, tx_code),
            )
    except aiosqlite.IntegrityError:
        await state.set_state(WalletFlow.tx_code)
        await message.reply("⛔ رقم العملية هذا مستخدم مسبقاً! أرسل رقم عملية صحيحاً:")
        return

    text_to_group = (
        f"💳 <b>طلب إيداع جديد قيد التدقيق المالي:</b>\n"
        f"🆔 رقم الدفعة: <code>{pay_id}</code>\n"
        f"👤 الزبون: {user_tag(message.from_user)} (<code>{message.from_user.id}</code>)\n"
        f"🔑 UID: <code>{message.from_user.id}</code>\n"
        f"💰 المبلغ المحوَّل: <b>{amt:,} ل.س</b>\n"
        f"🧾 رقم العملية: <code>{esc(tx_code)}</code>\n"
    )
    kb = KB([[B("✅ تأكيد وإيداع", f"adm_pay:ok:{pay_id}"), B("❌ رفض", f"adm_pay:no:{pay_id}")]])
    await send_to_staff(DEPOSIT_ADMIN_GROUP, text_to_group, kb)
    await state.clear()
    await message.answer(
        "✅ تم إرسال طلب الإيداع للإدارة، وسيُضاف الرصيد لمحفظتك فور التأكيد وسيصلك إشعار.",
        reply_markup=HOME_KB,
    )


@dp.message(WalletFlow.receipt)
async def wallet_old_receipt_state(message: types.Message, state: FSMContext):
    """حالة قديمة (كانت تنتظر صورة): نُنهيها ونوجّه الزبون للطريقة الجديدة."""
    await state.clear()
    await message.answer("ℹ️ صار الشحن بالنص فقط (رقم العملية ثم المبلغ). ابدأ من جديد:",
                         reply_markup=KB([[B("➕ شحن المحفظة", "wallet:topup")]]))


ORDER_STATUS_LABEL = {
    "PROCESSING": "⏳ قيد المعالجة", "COMPLETED": "✅ تم التنفيذ",
    "REFUNDED": "❌ ملغي", "REJECTED": "❌ ملغي",
}


@dp.callback_query(F.data == "client:orders")
async def my_orders(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    async with get_db() as db:
        cur = await db.execute(
            "SELECT order_id, service_name, price, status, created_at FROM orders WHERE user_id = ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT 20", (cb.from_user.id,)
        )
        rows = await cur.fetchall()
    if not rows:
        await safe_edit(cb, "📦 لا توجد طلبات بعد.", HOME_KB)
        return
    lines = ["📦 <b>آخر طلباتك</b> (حتى 20):", "────────────────────────────"]
    for oid, name, price, status, created in rows:
        lines.append(f"{ORDER_STATUS_LABEL.get(status, status)} — {esc(name)} — <b>{price:,}</b> ل.س\n"
                     f"<code>{oid}</code> · {str(created)[:16]}")
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3990] + "…"
    detail_rows = [[B(f"🔎 {oid} — {name[:22]}", f"co:{oid}")] for oid, name, *_ in rows[:8]]
    await safe_edit(cb, text, KB(detail_rows + [[B("🔄 تحديث", "client:orders")], [B("🏠 الرئيسية", "back_home")]]))


@dp.callback_query(F.data.startswith("co:"))
async def order_detail(cb: types.CallbackQuery):
    oid = cb.data.split(":", 1)[1]
    row = await fetch_one(
        "SELECT order_id, service_name, target_data, price, status, created_at, cancel_reason FROM orders "
        "WHERE order_id=? AND user_id=?", (oid, cb.from_user.id)
    )
    if not row:
        await cb.answer("⚠️ الطلب غير موجود.", show_alert=True)
        return
    text = (
        f"📦 <b>تفاصيل الطلب</b>\n────────────────────────────\n"
        f"🆔 الرقم: <code>{row['order_id']}</code>\n"
        f"📦 الخدمة: <b>{esc(row['service_name'])}</b>\n"
        f"🎯 البيانات: <code>{esc(row['target_data'])}</code>\n"
        f"💵 السعر: <b>{row['price']:,} ل.س</b>\n"
        f"📌 الحالة: <b>{ORDER_STATUS_LABEL.get(row['status'], row['status'])}</b>\n"
        f"🕒 {str(row['created_at'])[:16]}"
        + (f"\n📝 سبب الإلغاء: {esc(row['cancel_reason'])}" if row["cancel_reason"] else "")
    )
    await safe_edit(cb, text, KB([[B("🔙 طلباتي", "client:orders")], [B("🛠 الدعم", "sec:support")]]))


# =====================================================================
# 11. محرك الشراء الموحد (خصم فوري ذري)
# =====================================================================
_recent_purchases: Dict[Tuple[int, str, str], float] = {}


async def process_wallet_purchase(event, user_id: int, dept: str, service: str, target: str, price: int, state: FSMContext,
                                  copy_value: Optional[str] = None, cost_syp: Optional[float] = None):
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
    status, balance, ord_id = await WalletService.create_order(user_id, dept, service, target, price, cost_syp)

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
        f"💰 المبلغ المخصوم: <b>{price:,} ل.س</b>\n"
        + (f"📋 للنسخ: <code>{esc(copy_value)}</code>\n" if copy_value else "")
        + f"\n💡 للرد على الزبون، قم بعمل رد (Reply) مباشر على هذه الرسالة."
    )
    kb_group = KB([[B("✅ تم التنفيذ", f"ord_act:done:{ord_id}"), B("❌ إلغاء واسترجاع", f"ord_act:ref:{ord_id}")]])
    await send_to_staff(group_id, group_card, kb_group)

    success_card = (
        f"⏳ <b>طلبك قيد المعالجة</b>\n"
        f"────────────────────────────\n"
        f"🆔 رقم الطلب: <code>{ord_id}</code>\n"
        f"📦 الخدمة: <b>{esc(service)}</b>\n"
        f"🎯 البيانات: <code>{esc(target)}</code>\n"
        f"💵 المبلغ المخصوم: <b>{price:,} ل.س</b>\n"
        f"💰 رصيدك المتبقي: <b>{balance:,} ل.س</b>\n"
        f"────────────────────────────\n"
        f"✅ تم الخصم من محفظتك وتحويل الطلب لفريق التنفيذ، وسيصلك إشعار فور الانتهاء.\n"
        f"📦 تابع حالته من «طلباتي» في القائمة الرئيسية."
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
        buttons = []
        for i, (u, cost) in enumerate(items):
            price = await sell_price(cost_syp=cost, section="balance")
            buttons.append(B(f"{u:g} ⬅ {price:,} ل.س", f"bu_{net}_{i}"))
        rows = rows_of(buttons, 2) + [[B("🔙 رجوع", f"net:{net}")]]
        await safe_edit(cb, f"📲 <b>اختر فئة وحدات {name}:</b>", KB(rows))
    elif opt == "station":
        buttons = []
        for i, (a, _old) in enumerate(STATION_VALS):
            price = await sell_price(cost_syp=a, section="station")
            buttons.append(B(f"فئة {a:,} ⬅ {price:,} ل.س", f"bs_{net}_{i}"))
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
    u, cost = items[int(idx)]
    p = await sell_price(cost_syp=cost, section="balance")  # السعر من الخادم دائماً
    name = net_name_of(net)
    await state.update_data(s_title=f"وحدات {name} ({u:g} وحدة)", s_price=int(p),
                            s_px={"t": "cost", "cost": float(cost), "sec": "balance"})
    await state.set_state(BalanceState.syr_units_phone if net == "syr" else BalanceState.mtn_units_phone)
    await safe_edit(
        cb,
        f"📲 اخترت فئة <b>{u:g} وحدة</b> ({p:,} ل.س)\n\n{LINE_PROMPT}",
        cancel_kb(f"bopt:{net}:units"),
    )


LINE_PROMPT = "📞 أرسل رقم الهاتف أو كود الخط المراد التحويل إليه:"
NET_PREFIXES = {"syr": ("093", "098", "099"), "mtn": ("094", "095", "096")}


def parse_line_input(raw: str, net: str) -> Tuple[Optional[str], str]:
    """فحص ذكي: يرجع (النوع، القيمة) حيث النوع phone أو code، أو (None، رسالة الخطأ)."""
    s = normalize_digits(raw or "")
    s = re.sub(r"[\s\-\.\(\)]", "", s)
    for pre in ("+963", "00963"):
        if s.startswith(pre):
            rest = s[len(pre):]
            if rest.startswith("0") and len(rest) == 10:
                rest = rest[1:]
            s = "0" + rest
            break
    if not s.isdigit():
        return None, "⚠️ أرسل أرقاماً فقط (رقم هاتف أو كود خط):"
    name = net_name_of(net)
    if s.startswith("09"):
        if len(s) != 10:
            return None, "⚠️ رقم الهاتف يجب أن يتكون من 10 خانات ويبدأ بـ 09:"
        if s[:3] not in NET_PREFIXES[net]:
            return None, f"⚠️ هذا الرقم لا يتبع شبكة {name}. أرسل رقماً صحيحاً:"
        return "phone", s
    if not (3 <= len(s) <= 20):
        return None, "⚠️ كود الخط غير صالح. أرسل رقم الهاتف (09...) أو كود الخط:"
    return "code", s


def line_target(kind: str, value: str, net: str) -> str:
    return f"{'رقم' if kind == 'phone' else 'كود الخط'} {net_name_of(net)}: {value}"


async def _units_phone(message: types.Message, state: FSMContext, net: str):
    kind, val = parse_line_input(txt(message), net)
    if kind is None:
        await message.reply(val)
        return
    data = await state.get_data()
    if "s_title" not in data:
        await state.clear()
        await message.answer("⚠️ انتهت الجلسة، يرجى الاختيار من جديد.", reply_markup=HOME_KB)
        return
    await guarded_purchase(message, state, "balance", data["s_title"], line_target(kind, val, net),
                           data["s_price"], data.get("s_px"), copy_value=val)


@dp.message(BalanceState.syr_units_phone)
async def proc_syr_phone(message: types.Message, state: FSMContext):
    await _units_phone(message, state, "syr")


@dp.message(BalanceState.mtn_units_phone)
async def proc_mtn_phone(message: types.Message, state: FSMContext):
    await _units_phone(message, state, "mtn")


@dp.callback_query(F.data.startswith("bs_"))
async def sel_station_pack(cb: types.CallbackQuery, state: FSMContext):
    _, net, idx = cb.data.split("_")
    a, _old = STATION_VALS[int(idx)]
    p = await sell_price(cost_syp=a, section="station")  # السعر من الخادم دائماً
    name = net_name_of(net)
    await state.update_data(s_title=f"جملة كازية {name} (فئة {a:,})", s_price=int(p),
                            s_px={"t": "cost", "cost": float(a), "sec": "station"})
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
    await guarded_purchase(cb, state, "balance", data["s_title"], target, data["s_price"], data.get("s_px"))


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
    await guarded_purchase(cb, state, "balance", data["s_title"], target, data["s_price"], data.get("s_px"))


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
    await process_wallet_purchase(message, message.from_user.id, "balance", f"فاتورة {name} ({amt:,} ل.س)", target, await sell_price(cost_syp=amt, section="invoice"), state, cost_syp=float(amt))


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
    await state.update_data(c_amt=amt, c_price=await sell_price(cost_syp=amt, section="cash"))
    await state.set_state(nxt)
    await message.answer(prompt)


@dp.message(BalanceState.syr_cash_amt)
async def proc_syr_cash_amt(message: types.Message, state: FSMContext):
    await _cash_amt(message, state, BalanceState.syr_cash_id, LINE_PROMPT)


@dp.message(BalanceState.mtn_cash_amt)
async def proc_mtn_cash_amt(message: types.Message, state: FSMContext):
    await _cash_amt(message, state, BalanceState.mtn_cash_num, LINE_PROMPT)


async def _cash_target(message: types.Message, state: FSMContext, net: str):
    kind, val = parse_line_input(txt(message), net)
    data = await state.get_data()
    if kind is None:
        await message.reply(val)
        return
    if "c_amt" not in data:
        await state.clear()
        await message.answer("⚠️ انتهت الجلسة، يرجى الاختيار من جديد.", reply_markup=HOME_KB)
        return
    name = net_name_of(net)
    target = f"{line_target(kind, val, net)} | الكمية: {data['c_amt']:,}"
    await guarded_purchase(message, state, "balance", f"كاش {name} ({data['c_amt']:,})", target, data["c_price"],
                           {"t": "cost", "cost": float(data["c_amt"]), "sec": "cash"}, copy_value=val)


@dp.message(BalanceState.syr_cash_id)
async def proc_syr_cash_id(message: types.Message, state: FSMContext):
    await _cash_target(message, state, "syr")


@dp.message(BalanceState.mtn_cash_num)
async def proc_mtn_cash_num(message: types.Message, state: FSMContext):
    await _cash_target(message, state, "mtn")


# =====================================================================
# 13. شحن الألعاب
# =====================================================================
MARGIN_SECTIONS = {"balance": "الرصيد (وحدات سيريتل/MTN)", "station": "الكازيات (جملة)", "invoice": "الفواتير", "cash": "الكاش", "games": "الألعاب", "chat": "تطبيقات الشات", "accounts": "الحسابات الجاهزة", "social": "السوشيال ميديا", "numbers": "أرقام التفعيل"}  # أقسام أخرى تُضاف هنا لاحقاً


async def sell_price(cost_usd: Optional[float] = None, cost_syp: Optional[float] = None, section: str = "games") -> int:
    """سعر البيع = الجملة × (1 + نسبة الربح)، مع تقريب لأعلى. الدولار يُحوَّل بسعر الصرف الحالي."""
    margin = await get_setting(f"margin_{section}")
    cost = cost_usd * await get_setting("dollar_rate") if cost_usd is not None else float(cost_syp or 0)
    return max(1, math.ceil(round(cost * (1 + margin / 100), 6)))


# =====================================================================
# 13. محرك الكتالوج (قاعدة البيانات) — واجهة الزبون
#   الألعاب، تطبيقات الشات، الحسابات، السوشيال، أرقام التفعيل:
#   كلها تُقرأ من جداول catalog_services / catalog_packs وتُدار من /admin
# =====================================================================
SECTIONS = {
    "games": {"emoji": "🎮", "label": "الألعاب", "title": "اختر اللعبة المطلوبة", "per_page": 8, "cols": 1,
              "dept": "games", "quote": ("quote:game", "🎮 باقي الألعاب [طلب تسعير]")},
    "chat": {"emoji": "💬", "label": "تطبيقات الشات", "title": "اختر تطبيق الشات المطلوب", "per_page": 10, "cols": 2,
             "dept": "games", "search": True, "quote": ("quote:chat", "🔍 تطبيق غير موجود [طلب تسعير]")},
    "accounts": {"emoji": "📦", "label": "الحسابات الجاهزة", "title": "اختر الحساب المطلوب", "per_page": 8, "cols": 2,
                 "dept": "accounts", "quote": ("quote:acc", "📋 حساب غير موجود [طلب تسعير]")},
    "social": {"emoji": "🚀", "label": "السوشيال ميديا", "title": "اختر منصة السوشيال ميديا", "per_page": 8, "cols": 1,
               "dept": "social"},
    "numbers": {"emoji": "📱", "label": "أرقام التفعيل", "title": "قسم أرقام التفعيل", "per_page": 8, "cols": 1,
                "dept": "social", "quote": ("quote:num_google", "🌐 تفعيل غوغل / خدمة أخرى [طلب تسعير]")},
}

VISIBLE_COND = ("s.is_hidden=0 AND (s.kind='qty' OR EXISTS "
                "(SELECT 1 FROM catalog_packs p WHERE p.service_id=s.id AND p.is_hidden=0))")


async def fetch_all(sql: str, params: tuple = ()) -> list:
    async with get_db() as db:
        cur = await db.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in await cur.fetchall()]


async def fetch_one(sql: str, params: tuple = ()):
    rows = await fetch_all(sql, params)
    return rows[0] if rows else None


async def exec_sql(sql: str, params: tuple = ()) -> Tuple[Optional[int], int]:
    async with get_db() as db:
        cur = await db.execute(sql, params)
        return cur.lastrowid, cur.rowcount


async def get_service(sid: int):
    return await fetch_one("SELECT * FROM catalog_services WHERE id=?", (sid,))


def fmt_num(v: float) -> str:
    return f"{float(v):.8f}".rstrip("0").rstrip(".") or "0"


async def visible_services(section: str, platform: Optional[str] = None) -> list:
    sql = f"SELECT s.* FROM catalog_services s WHERE s.section=? AND {VISIBLE_COND}"
    params = [section]
    if platform:
        sql += " AND s.platform=?"
        params.append(platform)
    sql += " ORDER BY " + ("lower(s.name)" if section == "chat" else "s.id")
    return await fetch_all(sql, tuple(params))


async def pack_sell_price(pack: dict, section: str) -> int:
    if pack["cur"] == "USD":
        return await sell_price(cost_usd=pack["price"], section=section)
    return await sell_price(cost_syp=pack["price"], section=section)


def qty_cost(svc: dict, qty: int) -> float:
    """الحد الأدنى بالضبط = السعر الثابت، وما فوقه = الكمية × سعر الوحدة (ولا يقل عن سعر الحد الأدنى)."""
    if qty == svc["min_qty"]:
        return svc["min_price"]
    return max(svc["min_price"], qty * svc["unit_price"])


def order_service_name(svc: dict, label: str) -> str:
    if svc["section"] == "social":
        plat = SOCIAL_PLATFORMS.get(svc["platform"], ("", ""))[1]
        return f"{plat} - {svc['name']} ({label})" if plat else f"{svc['name']} ({label})"
    if svc["section"] == "numbers":
        return svc["name"]
    return f"{svc['name']} - {label}"


def svc_emoji(svc: dict) -> str:
    return svc.get("emoji") or SECTIONS.get(svc["section"], {}).get("emoji", "")


async def show_section(cb: types.CallbackQuery, section: str, page: int = 0):
    meta = SECTIONS[section]
    if section == "social":
        rows = [[B(f"{emo} خدمات {name}", f"sp:{k}")] for k, (emo, name) in SOCIAL_PLATFORMS.items()]
        rows.append([B("🔙 العودة للرئيسية", "back_home")])
        await safe_edit(cb, f"{meta['emoji']} <b>{meta['title']}:</b>", KB(rows))
        return

    if section == "numbers":
        items = await fetch_all(
            "SELECT p.id AS pid, p.label, p.price, p.cur, s.name, s.emoji, "
            "(SELECT COUNT(*) FROM catalog_packs q WHERE q.service_id=s.id AND q.is_hidden=0) AS n "
            "FROM catalog_packs p JOIN catalog_services s ON s.id=p.service_id "
            "WHERE s.section='numbers' AND s.is_hidden=0 AND p.is_hidden=0 ORDER BY s.id, p.id"
        )
        rows = []
        for it in items:
            price = await pack_sell_price(it, "numbers")
            title = it["name"] + (f" - {it['label']}" if it["n"] > 1 else "")
            rows.append([B(f"{it['emoji'] or meta['emoji']} {title} ({price:,} ل.س)", f"pb:{it['pid']}")])
        if meta.get("quote"):
            rows.append([B(meta["quote"][1], meta["quote"][0])])
        rows.append([B("🔙 العودة للرئيسية", "back_home")])
        await safe_edit(cb, f"{meta['emoji']} <b>{meta['title']}:</b>", KB(rows))
        return

    services = await visible_services(section)
    per = meta["per_page"]
    total = max(1, (len(services) + per - 1) // per)
    page = min(max(page, 0), total - 1)
    chunk = services[page * per:(page + 1) * per]
    buttons = [B(f"{svc_emoji(s)} {s['name']}", f"cv:{s['id']}:{page}:0") for s in chunk]
    rows = []
    if meta.get("search"):
        rows.append([B("🔍 بحث عن تطبيق بالاسم", f"cse:{section}")])
    rows += rows_of(buttons, meta["cols"])
    nav = []
    if page > 0:
        nav.append(B("⬅️ السابق", f"cs:{section}:{page - 1}"))
    if page < total - 1:
        nav.append(B("التالي ➡️", f"cs:{section}:{page + 1}"))
    if nav:
        rows.append(nav)
    if meta.get("quote"):
        rows.append([B(meta["quote"][1], meta["quote"][0])])
    rows.append([B("🔙 العودة للرئيسية", "back_home")])
    head = f"{meta['emoji']} <b>{meta['title']}</b> (صفحة {page + 1} من {total}):"
    if not services:
        head = f"{meta['emoji']} لا توجد خدمات متاحة حالياً في هذا القسم."
    await safe_edit(cb, head, KB(rows))


@dp.callback_query(F.data.in_({"sec:games", "sec:chat", "sec:accounts", "sec:social", "sec:numbers"}))
async def section_entry(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_section(cb, cb.data.split(":")[1], 0)


@dp.callback_query(F.data.startswith("cs:"))
async def section_page(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    _, section, page = cb.data.split(":")
    if section in SECTIONS:
        await show_section(cb, section, int(page))


@dp.callback_query(F.data.startswith("sp:"))
async def social_platform(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    plat = cb.data.split(":")[1]
    if plat not in SOCIAL_PLATFORMS:
        return
    emo, name = SOCIAL_PLATFORMS[plat]
    services = await visible_services("social", plat)
    rows = [[B(s["name"], f"cv:{s['id']}:0:0")] for s in services]
    rows.append([B("🔙 رجوع", "sec:social")])
    await safe_edit(cb, f"{emo} <b>خدمات {name}:</b>\nاختر الخدمة:", KB(rows))


@dp.callback_query(F.data.startswith("cv:"))
async def service_view(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    _, sid_s, lp_s, pp_s = cb.data.split(":")
    svc = await get_service(int(sid_s))
    if not svc or svc["is_hidden"]:
        await cb.answer("⚠️ هذه الخدمة غير متاحة حالياً.", show_alert=True)
        return
    lp, pp = int(lp_s), int(pp_s)
    section = svc["section"]
    back = f"sp:{svc['platform']}" if section == "social" and svc["platform"] in SOCIAL_PLATFORMS else f"cs:{section}:{lp}"
    notes = f"\n\n📌 <b>ملاحظات هامة:</b>\n{esc(svc['notes'])}" if svc.get("notes") else ""

    if svc["kind"] == "qty":
        margin = await get_setting(f"margin_{section}")
        unit_sell = svc["unit_price"] * (1 + margin / 100)
        price_min = await sell_price(cost_syp=svc["min_price"], section=section)
        await state.update_data(c_sid=svc["id"])
        await state.set_state(ChatInput.entering_id)
        await safe_edit(
            cb,
            f"{svc_emoji(svc)} <b>{esc(svc['name'])}</b>\n"
            f"────────────────────────────\n"
            f"📉 الحد الأدنى: <b>{svc['min_qty']:,}</b> = <b>{price_min:,} ل.س</b>\n"
            f"📈 ما فوق الحد الأدنى: <b>{unit_sell:.5f}</b> ل.س للوحدة\n"
            f"────────────────────────────\n"
            f"1️⃣ أرسل <b>الآيدي (ID)</b> الخاص بحسابك:{notes}",
            cancel_kb(back),
        )
        return

    packs = await fetch_all("SELECT * FROM catalog_packs WHERE service_id=? AND is_hidden=0 ORDER BY id", (svc["id"],))
    per = 8
    total = max(1, (len(packs) + per - 1) // per)
    pp = min(max(pp, 0), total - 1)
    rows = []
    if pp == 0 and svc["tok_min"] > 0:
        rows.append([B("🪙 شحن توكنز بالكمية", f"tok:{svc['id']}")])
    for p in packs[pp * per:(pp + 1) * per]:
        price = await pack_sell_price(p, section)
        rows.append([B(f"{p['label']} ⬅ {price:,} ل.س", f"pb:{p['id']}")])
    nav = []
    if pp > 0:
        nav.append(B("⬅️ السابق", f"cv:{svc['id']}:{lp}:{pp - 1}"))
    if pp < total - 1:
        nav.append(B("التالي ➡️", f"cv:{svc['id']}:{lp}:{pp + 1}"))
    if nav:
        rows.append(nav)
    rows.append([B("🔙 رجوع", back)])
    await safe_edit(cb, f"{svc_emoji(svc)} <b>{esc(svc['name'])}</b>\nاختر الباقة (صفحة {pp + 1} من {total}):{notes}", KB(rows))


@dp.callback_query(F.data.startswith("pb:"))
async def pack_buy(cb: types.CallbackQuery, state: FSMContext):
    pid = int(cb.data.split(":")[1])
    row = await fetch_one(
        "SELECT p.id AS pid, p.label, p.price, p.cur, p.is_hidden AS phid, s.id AS sid, s.section, s.platform, "
        "s.name, s.emoji, s.ask, s.notes, s.is_hidden AS shid "
        "FROM catalog_packs p JOIN catalog_services s ON s.id=p.service_id WHERE p.id=?", (pid,)
    )
    if not row or row["phid"] or row["shid"]:
        await cb.answer("⚠️ هذه الباقة لم تعد متاحة.", show_alert=True)
        return
    section = row["section"]
    price = await pack_sell_price(row, section)  # السعر من الخادم دائماً
    service_name = order_service_name(row, row["label"])
    await state.clear()
    await state.update_data(g_dept=SECTIONS[section]["dept"], g_service=service_name, g_price=price, g_confirm=(section == "chat"),
                            g_px={"t": "pack", "id": pid})
    await state.set_state(GlobalOrderState.input_data)
    notes = f"\n\n📌 {esc(row['notes'])}" if row.get("notes") else ""
    back = "cs:numbers:0" if section == "numbers" else f"cv:{row['sid']}:0:0"
    await safe_edit(
        cb,
        f"{svc_emoji(row)} لقد اخترت: <b>{esc(service_name)}</b> ({price:,} ل.س){notes}\n\n{esc(row['ask'] or 'أرسل البيانات المطلوبة:')}",
        cancel_kb(back),
    )


@dp.callback_query(F.data.startswith("tok:"))
async def tokens_start(cb: types.CallbackQuery, state: FSMContext):
    svc = await get_service(int(cb.data.split(":")[1]))
    if not svc or svc["is_hidden"] or svc["tok_min"] <= 0:
        await cb.answer("⚠️ غير متاح.", show_alert=True)
        return
    await state.clear()
    await state.update_data(tok_sid=svc["id"])
    await state.set_state(GameTokens.entering)
    unit = (await sell_price(cost_syp=svc["tok_unit"] * 1000, section=svc["section"])) / 1000
    await safe_edit(
        cb,
        f"🪙 <b>شحن توكنز {esc(svc['name'])}</b>\n"
        f"الحد الأدنى: <b>{svc['tok_min']:,}</b> توكن\n"
        f"السعر التقريبي: <b>{unit:.3f} ل.س</b> للتوكن\n\n"
        f"أرسل الآيدي ثم الكمية وبينهما مسافة:\nمثال: <code>123456 {svc['tok_min']}</code>",
        cancel_kb(f"cv:{svc['id']}:0:0"),
    )


@dp.message(GameTokens.entering)
async def tokens_receive(message: types.Message, state: FSMContext):
    data = await state.get_data()
    svc = await get_service(int(data["tok_sid"])) if data.get("tok_sid") else None
    if not svc or svc["is_hidden"] or svc["tok_min"] <= 0:
        await state.clear()
        await message.answer("⚠️ انتهت الجلسة، يرجى الاختيار من جديد.", reply_markup=HOME_KB)
        return
    parts = txt(message).split()
    qty = to_int(parts[1]) if len(parts) >= 2 else None
    if qty is None:
        await message.reply("⚠️ أرسل الآيدي ثم الكمية (رقم صحيح) وبينهما مسافة:")
        return
    if qty < svc["tok_min"]:
        await message.reply(f"⚠️ الحد الأدنى للكمية {svc['tok_min']:,} توكن:")
        return
    if qty > 100_000_000:
        await message.reply("⚠️ الكمية غير صالحة:")
        return
    price = await sell_price(cost_syp=qty * svc["tok_unit"], section=svc["section"])
    await process_wallet_purchase(
        message, message.from_user.id, SECTIONS[svc["section"]]["dept"], f"{svc['name']} - توكنز ({qty:,})",
        f"الآيدي: {parts[0][:100]}", price, state, cost_syp=qty * svc["tok_unit"],
    )


async def current_price(px: Optional[dict]):
    """يعيد (السعر الحالي، التكلفة بالليرة) من مصدر التسعير، أو (None, None) إن لم تعد الخدمة متاحة."""
    if not px:
        return None, None
    t = px.get("t")
    if t == "pack":
        row = await fetch_one(
            "SELECT p.price, p.cur, p.is_hidden AS phid, s.section, s.is_hidden AS shid "
            "FROM catalog_packs p JOIN catalog_services s ON s.id=p.service_id WHERE p.id=?", (px["id"],)
        )
        if not row or row["phid"] or row["shid"]:
            return None, None
        cost = row["price"] * (await get_setting("dollar_rate") if row["cur"] == "USD" else 1)
        return await sell_price(cost_syp=cost, section=row["section"]), cost
    if t == "qty":
        svc = await get_service(int(px["sid"]))
        if not svc or svc["is_hidden"]:
            return None, None
        cost = qty_cost(svc, int(px["qty"]))
        return await sell_price(cost_syp=cost, section=svc["section"]), cost
    if t == "cost":
        return await sell_price(cost_syp=float(px["cost"]), section=px["sec"]), float(px["cost"])
    return None, None


async def guarded_purchase(event, state: FSMContext, dept: str, service: str, target: str, shown_price: int,
                           px: Optional[dict], copy_value: Optional[str] = None, confirm: bool = False):
    """يعيد حساب السعر لحظة الشراء. إن تغيّر منذ اختيار الزبون لا نخصم دون موافقته."""
    cur, cost = await current_price(px) if px else (None, None)
    if px and cur is None:
        await state.clear()
        await respond(event, "⚠️ هذه الخدمة لم تعد متاحة حالياً. اختر خدمة أخرى.", HOME_KB)
        return
    price = cur if cur is not None else int(shown_price)
    if cur is not None and cur != int(shown_price):
        await show_confirm(event, state, dept, service, target, price, copy_value=copy_value, px=px,
                           notice=f"⚠️ <b>تغيّر السعر</b> منذ اختيارك: كان {int(shown_price):,} ل.س وصار <b>{price:,} ل.س</b>.")
        return
    if confirm:
        await show_confirm(event, state, dept, service, target, price, copy_value=copy_value, px=px)
        return
    await process_wallet_purchase(event, event.from_user.id, dept, service, target, price, state,
                                  copy_value=copy_value, cost_syp=cost)


async def show_confirm(event, state: FSMContext, dept: str, service: str, target: str, price: int,
                       copy_value: Optional[str] = None, px: Optional[dict] = None, notice: str = ""):
    """شاشة تأكيد قبل الخصم. إن كان الرصيد لا يكفي تظهر بطاقة الشحن مباشرة."""
    u = await WalletService.get_or_create_user(event.from_user.id)
    if u[2] < price:
        _, cost = await current_price(px) if px else (None, None)
        await process_wallet_purchase(event, event.from_user.id, dept, service, target, price, state, cost_syp=cost)
        return
    await state.clear()
    await state.update_data(cf_dept=dept, cf_service=service, cf_target=target, cf_price=int(price), cf_copy=copy_value, cf_px=px)
    await state.set_state(ChatInput.confirm)
    text = (
        (notice + "\n\n" if notice else "") +
        f"🧾 <b>تأكيد العملية</b>\n"
        f"────────────────────────────\n"
        f"📦 الخدمة: <b>{esc(service)}</b>\n"
        f"🎯 البيانات: <code>{esc(target)}</code>\n"
        f"💵 السعر: <b>{int(price):,} ل.س</b>\n"
        f"💰 رصيدك الحالي: <b>{u[2]:,} ل.س</b>\n"
        f"💳 الرصيد بعد الخصم: <b>{u[2] - int(price):,} ل.س</b>\n"
        f"────────────────────────────\n"
        f"اضغط «تأكيد الشراء» ليُخصم المبلغ من محفظتك ويُرسل الطلب للتنفيذ."
    )
    await respond(event, text, KB([[B("✅ تأكيد الشراء", "cfm:ok")], [B("❌ إلغاء", "back_home")]]))


@dp.callback_query(F.data == "cfm:ok", ChatInput.confirm)
async def confirm_purchase(cb: types.CallbackQuery, state: FSMContext):
    d = await state.get_data()
    if not d.get("cf_price") or not d.get("cf_service"):
        await state.clear()
        await safe_edit(cb, "⚠️ انتهت صلاحية هذه الخطوة. يرجى البدء من جديد:", HOME_KB)
        return
    px = d.get("cf_px")
    cur, cost = await current_price(px) if px else (None, None)
    if px and cur is None:
        await state.clear()
        await safe_edit(cb, "⚠️ هذه الخدمة لم تعد متاحة حالياً.", HOME_KB)
        return
    if cur is not None and cur != int(d["cf_price"]):
        await show_confirm(cb, state, d["cf_dept"], d["cf_service"], d["cf_target"], cur, copy_value=d.get("cf_copy"), px=px,
                           notice=f"⚠️ <b>تغيّر السعر</b> قبل التأكيد: كان {int(d['cf_price']):,} ل.س وصار <b>{cur:,} ل.س</b>.")
        return
    await process_wallet_purchase(
        cb, cb.from_user.id, d["cf_dept"], d["cf_service"], d["cf_target"], d["cf_price"], state,
        copy_value=d.get("cf_copy"), cost_syp=cost,
    )


@dp.message(ChatInput.entering_id)
async def qty_receive_id(message: types.Message, state: FSMContext):
    data = await state.get_data()
    svc = await get_service(int(data["c_sid"])) if data.get("c_sid") else None
    if not svc or svc["kind"] != "qty" or svc["is_hidden"]:
        await state.clear()
        await message.answer("⚠️ انتهت الجلسة، يرجى الاختيار من جديد.", reply_markup=KB([[B("💬 قائمة التطبيقات", "sec:chat")]]))
        return
    uid_text = txt(message)
    if not uid_text or len(uid_text) > 100 or " " in uid_text.strip():
        await message.reply("⚠️ أرسل الآيدي فقط (بدون مسافات، حتى 100 حرف):")
        return
    await state.update_data(c_id=uid_text)
    await state.set_state(ChatInput.entering_data)
    min_q = max(1, svc["min_qty"])
    price_min = await sell_price(cost_syp=svc["min_price"], section=svc["section"])
    await message.answer(
        f"✅ الآيدي: <code>{esc(uid_text)}</code>\n\n"
        f"2️⃣ أرسل <b>الكمية المطلوبة</b> (الحد الأدنى {min_q:,} = {price_min:,} ل.س):",
        reply_markup=cancel_kb(f"cs:{svc['section']}:0"),
    )


@dp.message(ChatInput.entering_data)
async def qty_receive(message: types.Message, state: FSMContext):
    data = await state.get_data()
    svc = await get_service(int(data["c_sid"])) if data.get("c_sid") else None
    if not svc or svc["kind"] != "qty" or svc["is_hidden"] or not data.get("c_id"):
        await state.clear()
        await message.answer("⚠️ انتهت الجلسة، يرجى الاختيار من جديد.", reply_markup=KB([[B("💬 قائمة التطبيقات", "sec:chat")]]))
        return
    qty = to_int(txt(message))
    if qty is None:
        await message.reply("⚠️ أرسل الكمية كرقم صحيح:")
        return
    min_q = max(1, svc["min_qty"])
    if qty < min_q:
        await message.reply(f"⚠️ الحد الأدنى للكمية في {esc(svc['name'])} هو {min_q:,}:")
        return
    if qty > 10_000_000_000:
        await message.reply("⚠️ الكمية غير صالحة:")
        return
    price = await sell_price(cost_syp=qty_cost(svc, qty), section=svc["section"])
    await show_confirm(
        message, state, SECTIONS[svc["section"]]["dept"], f"{svc['name']} ({qty:,})",
        f"الآيدي: {data['c_id'][:100]}", price, copy_value=data["c_id"][:100],
        px={"t": "qty", "sid": svc["id"], "qty": qty},
    )


def norm_name(s: str) -> str:
    return re.sub(r"[\s\-_.]+", "", normalize_digits(s or "").lower())


@dp.callback_query(F.data.startswith("cse:"))
async def search_start(cb: types.CallbackQuery, state: FSMContext):
    section = cb.data.split(":")[1]
    if section != "all" and section not in SECTIONS:
        return
    await state.clear()
    await state.update_data(search_section=section)
    await state.set_state(ChatSearch.query)
    back = "back_home" if section == "all" else f"cs:{section}:0"
    await safe_edit(
        cb,
        "🔍 اكتب اسم اللعبة أو التطبيق أو الخدمة، أو <b>جزءاً من الاسم</b> (عربي أو إنجليزي):\n"
        "مثال: <code>soul</code> أو <code>ببجي</code> أو <code>netflix</code>",
        cancel_kb(back),
    )


@dp.message(ChatSearch.query)
async def search_receive(message: types.Message, state: FSMContext):
    data = await state.get_data()
    section = data.get("search_section", "all")
    q = norm_name(txt(message))
    if len(q) < 2:
        await message.reply("⚠️ اكتب حرفين على الأقل:")
        return
    services = []
    for sec in (list(SECTIONS) if section == "all" else [section]):
        services += await visible_services(sec)
    found = [sv for sv in services if q in norm_name(sv["name"])]
    if not found:  # تسامح مع الأخطاء الإملائية
        by_name = {norm_name(sv["name"]): sv for sv in services}
        found = [by_name[c] for c in difflib.get_close_matches(q, list(by_name), n=8, cutoff=0.6)]
    found = found[:15]
    back = "back_home" if section == "all" else f"cs:{section}:0"
    if not found:
        no_rows = []
        if section != "all" and SECTIONS[section].get("quote"):
            no_rows.append([B(SECTIONS[section]["quote"][1], SECTIONS[section]["quote"][0])])
        no_rows.append([B("🔙 رجوع", back)])
        await message.reply("لا توجد نتائج. جرّب جزءاً آخر من الاسم:", reply_markup=KB(no_rows))
        return
    await state.clear()
    rows = [[B(f"{svc_emoji(sv)} {sv['name']}", f"cv:{sv['id']}:0:0")] for sv in found]
    rows.append([B("🔍 بحث جديد", f"cse:{section}"), B("🔙 رجوع", back)])
    await message.answer(f"🔍 نتائج البحث ({len(found)}):", reply_markup=KB(rows))


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
    confirm = bool(data.get("g_confirm"))
    await guarded_purchase(
        message, state, data.get("g_dept", "games"), data.get("g_service", "خدمة عامة"),
        f"الآيدي: {target[:100]}" if confirm else target[:500], data["g_price"], data.get("g_px"),
        copy_value=target[:100] if confirm else None, confirm=confirm,
    )


# =====================================================================
# 14. برامج الشات
# =====================================================================
# ---------------------------------------------------------------------
# كتالوج تطبيقات الشات — أسعار الجملة بالليرة السورية.
# صيغة السطر:  الاسم|الحد الأدنى|سعر الجملة عند الحد الأدنى|سعر الوحدة بعده
#   - الكمية = الحد الأدنى بالضبط  → سعر الجملة الثابت
#   - الكمية أكبر                   → الكمية × سعر الوحدة (ولا يقل عن سعر الحد الأدنى)
# لإضافة تطبيق أو تعديل سعر: عدّل السطر فقط.
# ---------------------------------------------------------------------
CHAT_QTY_DATA = """
Soul Star|10000|155.81|0.022
Soulchill|1000|246.42|0.27
SHABAB CHAT|50000|158.36|0.0035
Siba Chat|10000|164.25|0.022
Taka Chat|10000|144.58|0.012
Yaahlan Chat|1000|252.69|0.27
Migo Live|10000|167.10|0.022
Beela Chat|1000|12.61|0.012
Yoho|15000|217.84|0.012
Up Live|1|2.03|2.07
YoYo|1000|111.41|0.13
SoulFa chat|1000|189.96|0.21
Party Star|2000|298.55|0.17
Super Live|200|186.52|0.95
Habby Chat|1000|15.32|0.022
Talk Talk|1500|176.37|0.14
Ayome Chat|1500|206.84|0.16
4Fun Chat|25000|222.48|0.012
Poppo Live|15000|218.76|0.016
Cocco Live|10000|151.85|0.017
Oohla Chat|2000|207.44|0.12
Hiya Chat|1500|224.92|0.17
Majlis|1000|149.32|0.17
Waho Live|10000|142.82|0.016
Xena Live|10000|152.54|0.017
HamiParty|15000|209.15|0.016
HAWA CHAT|5000|400.57|0.10
OPA LIVE|20000|237.70|0.014
SO MATCH|10000|178.34|0.020
HiParty|10000|154.09|0.017
DANA CHAT|30000|175.56|0.008
FUN UP|10000|153.63|0.017
Binmo Chat|10000|557.46|0.058
Amo Chat|10000|88.99|0.011
Hiyoo|2500|35.31|0.016
Amar Chat|3000|368.54|0.14
Sama Chat|10000|120.46|0.014
WAKI STAR|2000000|70.52|0.00004
Salam Chat|200000|273.35|0.0016
Habi|10000|149.62|0.017
Pota live|100000|359.21|0.004
RoStar|10000|281.38|0.031
Halo Star|5000000|173.92|0.00004
Top Top|100000|623.89|0.007
LitChat|10000|255.15|0.028
saya chat|10000|250.77|0.028
Soodfa|50000|122.40|0.0027
Saada|1500|234.51|0.18
Fansy Live|10000|73.92|0.010
sahra chat|10000|1030.18|0.11
willchill|20000|234.46|0.013
yoki|20000|167.29|0.010
BoBo Chat|20000|131.76|0.008
wadi chat|17500|131.24|0.009
dika live|100000|173.06|0.002
GIMME LIVE|10000|179.07|0.020
yoparti|10000|299.69|0.033
Junko|60000|168.99|0.003
Likee|200|515.34|2.60
Bigo Live|50|124.97|2.52
Ahlan Chat|3000|164.26|0.06
MicoChat|8000|375.91|0.05
Azal Live|1500|99.21|0.07
Tami Live|100000|208.40|0.0023
Tada|1000|175.46|0.20
LightChat|5000|180.26|0.04
Sugo Chat|10000|201.15|0.022
Lami Chat|2000|78.07|0.043
Aswat chat|1500|151.35|0.11
Soyo|15000|171.18|0.013
Higo Chat|1000|149.84|0.17
Layla chat|10000|325.30|0.036
Yooy Chat|50000|130.45|0.0029
mango live|10000|342.12|0.038
Dimo Chat|1000|130.46|0.14
Olamet Chat|12000|241.78|0.022
honey jar chat|200|220.15|1.12
Lama Chat|5000|123.26|0.027
SoulChat|10000|212.03|0.023
LigoLive|1000|173.28|0.19
Kwai|200|305.18|1.55
Allo|1000|12.59|0.014
Star Maker chat|200|305.10|1.55
Hoby chat|10000|113.17|0.013
ASHA Chat|10000|165.15|0.018
WASLA Chat|10000|436.56|0.048
Wyak Chat|500000|148.57|0.00033
Maza Chat|20000|177.98|0.010
Dido Chat|2000|147.26|0.081
Boli Chat|10000|133.64|0.015
Halla Chat|10000|175.94|0.019
LaYam Chat|10000|75.46|0.008
OurTalk Chat|100000|345.81|0.0038
Hayuki Chat|25000|180.63|0.008
Fofo Chat|200000|242.99|0.0013
Yayya Chat|10000|128.55|0.014
Hopi Star|4000000|139.60|0.00004
Hapi live|1000000|146.50|0.00016
Yolo Chat|10000|1114.08|0.12
Pocket chat|10000|338.19|0.037
CARNI LIVE|1500|166.68|0.13
Hart live|12000|141.81|0.013
Laki chat|22000|153.29|0.008
Rooh chat|15000|176.96|0.013
Vostar Chat|200000|130.64|0.0007
PAWA LIVE|20000|234.80|0.013
Baat LIVE|10000|141.32|0.016
Tayyb CHAT|1000000|103.68|0.00012
HATI Chat|10000|24.81|0.0028
Niu Chat|100000|126.82|0.0014
BEST LIVE|500000|131.80|0.00029
KESSMET CHAT|10000|724.84|0.080
HOOB CHAT|50000|109.00|0.0024
KARAK CHAT|70000|150.24|0.0024
NIVI Chat|5000|162.68|0.036
WIKOO|80000|115.95|0.0016
YULA CHAT|50000|150.35|0.0033
TI LIVE|120|130.12|1.19
NAFASS|45000|118.60|0.0029
RIXO CHAT|50000|109.26|0.0024
WAHDA CHAT|15000|229.49|0.017
MOMA LIVE|47500|147.12|0.0034
TAYA CHAT|10000|155.75|0.017
LOTFUN CHAT|50000|664.76|0.015
SAHI LIVE|9200|146.39|0.018
WAAW CHAT|40000|172.71|0.0048
DAWA CHAT|70000|149.85|0.0024
CHAMET|15000|360.90|0.026
Lions Chat|10000|169.87|0.019
Mr7ba chat|300000|15.02|0.00006
Zaffa chat|55000|114.02|0.0023
Hago chat|12500|169.04|0.015
Mikoo chat|30000|162.24|0.006
1STAR CHAT|10000|150.96|0.017
NABD CHAT|100000|218.00|0.0024
SOHHA LIVE|60000|158.10|0.0029
Hoki chat|10000|161.85|0.018
ZAAR CHAT|1000|5.80|0.0065
up fun|25000|148.54|0.0066
PEP LIVE|1500|229.83|0.17
alulu chat|3250|136.71|0.046
PIKA STAR|1250|139.95|0.12
HIGH CHAT|1000|147.10|0.16
SKY CHAT|1000|156.17|0.17
haya|70|157.54|2.45
ARIA CHAT|10000|149.99|0.017
DITTO LIVE|3000|115.06|0.042
SOUL U|1000|11.56|0.013
LiveMe+|1000|1678.70|1.85
iFun Chat|10000|122.09|0.013
WEGO LIVE|15000|170.59|0.013
Veco|10000|120.41|0.014
SAWALFNA|10000|143.58|0.016
KARAWAN|1000|135.80|0.15
HALA ME|20000|125.30|0.007
YOBI CHAT|5000|763.78|0.17
PARTY HERO|100|14.85|0.16
YUDO FUN|20000|117.68|0.007
"""

# تطبيقات بفئات ثابتة: الاسم → [(الفئة, السعر بالدولار)]
CHAT_PACKS_DATA = {
    "IMO": [("100 ألماسة", 1.89), ("200 ألماسة", 3.78), ("500 ألماسة", 9.46),
            ("1000 ألماسة", 18.91), ("2000 ألماسة", 37.82), ("5000 ألماسة", 94.56)],
    "Yalla Live": [("2900 ذهبة", 25.21), ("5900 ذهبة", 50.41), ("12500 ذهبة", 100.82)],
    "Meyo": [("490 ألماس", 5.26), ("980 ألماس", 10.50), ("1960 ألماس", 20.97),
             ("4900 ألماس", 52.14), ("9800 ألماس", 104.28)],
    "TUMILE CHAT": [("650 ألماس", 3.80), ("1250 ألماس", 7.15), ("1800 ألماس", 9.91),
                    ("3500 ألماس", 17.74), ("7000 ألماس", 34.95), ("15000 ألماس", 75.72),
                    ("35000 ألماس", 177.91)],
    "LIVU CHAT": [("360 ألماس", 2.89), ("650 ألماس", 3.72), ("1800 ألماس", 9.80),
                  ("7000 ألماس", 34.95), ("15000 ألماس", 75.72), ("35000 ألماس", 177.91)],
}


def _build_chat_items():
    items = []
    for line in CHAT_QTY_DATA.strip().splitlines():
        if not line.strip():
            continue
        name, mn, mp, un = [x.strip() for x in line.split("|")]
        items.append({"name": name, "kind": "qty", "min": int(mn), "min_price": float(mp), "unit": float(un)})
    for name, packs in CHAT_PACKS_DATA.items():
        items.append({"name": name, "kind": "packs", "packs": packs})
    items.sort(key=lambda x: x["name"].lower())
    return items


CHAT_ITEMS = _build_chat_items()
CHAT_PER_PAGE = 10


# =====================================================================
# 15. الحسابات الجاهزة
# =====================================================================
# =====================================================================
# 16. السوشيال ميديا والإعلانات
# =====================================================================
# =====================================================================
# 17. أرقام التفعيل
# =====================================================================
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
        "acc": ("accounts", "📦 طلب تسعير حساب"),
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
_admin_cache: Dict[Tuple[int, int], float] = {}


async def is_authorized(user_id: int, chat_id: int) -> bool:
    """المدير، أو موظف مضاف من اللوحة، أو مشرف تلغرام في مجموعة الإدارة نفسها."""
    if user_id == ADMIN_ID:
        return True
    if chat_id not in ALL_ADMIN_GROUPS:
        return False
    if await fetch_one("SELECT 1 AS x FROM staff WHERE user_id=?", (user_id,)):
        return True
    key = (chat_id, user_id)
    now = time.monotonic()
    if _admin_cache.get(key, 0) > now:
        return True
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        if m.status in ("administrator", "creator"):
            _admin_cache[key] = now + 300
            return True
    except Exception as e:
        log.warning("get_chat_member failed: %s", e)
    return False


async def staff_guard(cb: types.CallbackQuery) -> bool:
    chat_id = cb.message.chat.id if isinstance(cb.message, types.Message) else 0
    if await is_authorized(cb.from_user.id, chat_id):
        return True
    await cb.answer("⛔ ليست لديك صلاحية. يجب أن تكون مشرفاً في المجموعة أو مضافاً لقائمة الموظفين.", show_alert=True)
    return False


async def log_staff(cb: types.CallbackQuery, action: str, ref, detail: str = ""):
    try:
        await exec_sql(
            "INSERT INTO staff_actions (staff_id, staff_name, action, ref, detail) VALUES (?, ?, ?, ?, ?)",
            (cb.from_user.id, cb.from_user.full_name or cb.from_user.username or "", action, str(ref), (detail or "")[:300]),
        )
    except Exception as e:
        log.warning("log_staff failed: %s", e)


def by_line(cb: types.CallbackQuery) -> str:
    return f"\n👤 بواسطة: {esc(cb.from_user.full_name or cb.from_user.username or str(cb.from_user.id))}"


REFUND_REASONS = {
    "1": "بيانات الطلب غير صحيحة",
    "2": "الخدمة غير متوفرة حالياً",
    "3": "بناءً على طلبك",
    "4": "تعذّر التنفيذ لدى المورّد",
}


@dp.callback_query(F.data.startswith("ord_act:"))
async def handle_staff_order_action(cb: types.CallbackQuery):
    if not await staff_guard(cb):
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
        await log_staff(cb, "ORDER_DONE", ord_id, s_name)
        await append_status(cb.message, "🟢 <b>تم التنفيذ بنجاح</b>" + by_line(cb))

    elif action == "ref":
        # اختيار سبب الإلغاء قبل الاسترجاع (يصل الزبون مع الإشعار)
        rows = [[B(txt_, f"ord_rs:{ord_id}:{code}")] for code, txt_ in REFUND_REASONS.items()]
        rows.append([B("🔙 تراجع", f"ord_rs:{ord_id}:0")])
        try:
            await cb.message.edit_reply_markup(reply_markup=KB(rows))
        except Exception as e:
            log.warning("edit_reply_markup failed: %s", e)


@dp.callback_query(F.data.startswith("ord_rs:"))
async def handle_refund_reason(cb: types.CallbackQuery):
    if not await staff_guard(cb):
        return
    _, ord_id, code = cb.data.split(":")
    if code == "0":
        try:
            await cb.message.edit_reply_markup(reply_markup=KB([[B("✅ تم التنفيذ", f"ord_act:done:{ord_id}"),
                                                                 B("❌ إلغاء واسترجاع", f"ord_act:ref:{ord_id}")]]))
        except Exception:
            pass
        return
    reason = REFUND_REASONS.get(code, "")
    ok, uid, amt = await WalletService.refund(ord_id, reason)
    if not ok:
        await cb.answer("⚠️ تعذر الاسترجاع: الطلب معالج مسبقاً أو غير موجود.", show_alert=True)
        return
    try:
        await bot.send_message(uid, f"↩️ <b>تم إلغاء الطلب {ord_id}</b> وإعادة مبلغ <b>{amt:,} ل.س</b> إلى محفظتك.\n📝 السبب: {esc(reason)}")
    except Exception as e:
        log.warning("notify customer failed: %s", e)
    await log_staff(cb, "ORDER_REFUND", ord_id, reason)
    await append_status(cb.message, f"🟡 <b>تم الإلغاء واسترجاع الرصيد</b> — السبب: {esc(reason)}" + by_line(cb))


@dp.callback_query(F.data.startswith("adm_pay:"))
async def handle_admin_payment_action(cb: types.CallbackQuery):
    if not await staff_guard(cb):
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
        try:
            await referral_after_completion(u_id)
        except Exception as e:
            log.error("referral hook failed: %s", e)
        await log_staff(cb, "PAYMENT_OK", pay_id, f"{amt} ل.س للمستخدم {u_id}")
        await append_status(cb.message, f"🟢 <b>تم قبول الإيداع ({amt:,} ل.س)</b>" + by_line(cb))
    else:
        u_id = await WalletService.decline_payment(pay_id)
        if u_id is None:
            await cb.answer("⚠️ تمت معالجة هذه الدفعة مسبقاً!", show_alert=True)
            return
        try:
            await bot.send_message(u_id, f"❌ نعتذر منك، تم رفض إشعار الإيداع للدفعة <code>{pay_id}</code> لعدم تطابق التحويل.")
        except Exception as e:
            log.warning("notify customer failed: %s", e)
        await log_staff(cb, "PAYMENT_NO", pay_id, f"المستخدم {u_id}")
        await append_status(cb.message, "🔴 <b>تم رفض الإيداع</b>" + by_line(cb))


async def extract_customer_id(orig_text: str) -> Optional[int]:
    """استخراج آيدي الزبون: UID أولاً، ثم سطر الزبون، ثم رقم الطلب/الدفعة من قاعدة البيانات، ثم أي رقم بين قوسين."""
    m = re.search(r"UID:\s*(\d{5,15})", orig_text)
    if m:
        return int(m.group(1))
    m = re.search(r"الزبون:.*?\((\d{5,15})\)", orig_text)
    if m:
        return int(m.group(1))
    m = re.search(r"رقم الطلب:\s*(\d{4,})", orig_text)
    if m:
        uid = await WalletService.user_by_reference(m.group(1))
        if uid:
            return uid
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
# 19ب. نظام الإحالة (مشروط بأول عملية شراء منفذة + مراجعة المشرف)
# =====================================================================
_bot_username: Optional[str] = None


async def get_bot_username() -> str:
    global _bot_username
    if not _bot_username:
        _bot_username = (await bot.me()).username
    return _bot_username


async def register_referral(new_user_id: int, referrer_id: int) -> bool:
    """يربط المدعو بصاحب الدعوة. شروط: صاحب الدعوة مشترك في البرنامج، لا إحالة للنفس،
    والمدعو لم يشحن ولم يشترِ من قبل ولا إحالة سابقة له."""
    if new_user_id == referrer_id:
        return False
    try:
        async with write_tx() as db:
            cur = await db.execute("SELECT ref_enrolled FROM users WHERE user_id=?", (referrer_id,))
            r = await cur.fetchone()
            if not r or not r[0]:
                return False
            cur = await db.execute("SELECT 1 FROM referrals WHERE referred_id=?", (new_user_id,))
            if await cur.fetchone():
                return False
            cur = await db.execute("SELECT 1 FROM orders WHERE user_id=? LIMIT 1", (new_user_id,))
            if await cur.fetchone():
                return False
            cur = await db.execute("SELECT 1 FROM payments WHERE user_id=? AND status='ACCEPTED' LIMIT 1", (new_user_id,))
            if await cur.fetchone():
                return False
            await db.execute("INSERT INTO referrals (referred_id, referrer_id) VALUES (?, ?)", (new_user_id, referrer_id))
            await db.execute("UPDATE users SET referred_by=? WHERE user_id=?", (referrer_id, new_user_id))
            return True
    except Exception as e:
        log.error("register_referral error: %s", e)
        return False


async def get_referral_target() -> int:
    try:
        v = int(await get_setting("referral_target"))
    except Exception:
        v = 0
    return v if v >= 1 else REFERRAL_TARGET


async def compute_reward(db, referred_ids: list) -> int:
    """مكافأة الرصيد: إن حُدّدت نسبة % فهي من مجموع أول شحن مؤكد لكل صديق في الدفعة، وإلا القيمة الثابتة."""
    cur = await db.execute("SELECT key, val FROM settings WHERE key IN ('referral_reward', 'referral_percent')")
    st = {k: v for k, v in await cur.fetchall()}
    pct = float(st.get("referral_percent") or 0)
    fixed = int(st.get("referral_reward") or 0)
    if pct <= 0:
        return fixed
    total = 0
    for rid in referred_ids:
        c = await db.execute(
            "SELECT amount FROM payments WHERE user_id=? AND status='ACCEPTED' ORDER BY created_at, rowid LIMIT 1", (rid,)
        )
        row = await c.fetchone()
        total += row[0] if row else 0
    return int(total * pct / 100)


async def referral_mark_completed(user_id: int):
    """تُستدعى فور تأكيد أول إيداع للمدعو. ترجع None أو قاموساً:
    referrer, done (المكتملة)، pending_in_batch، target، rtype، rtext، created (قائمة (reward_id، amount))."""
    async with write_tx() as db:
        cur = await db.execute("SELECT referrer_id FROM referrals WHERE referred_id=? AND status='PENDING'", (user_id,))
        r = await cur.fetchone()
        if not r:
            return None
        referrer = r[0]
        await db.execute(
            "UPDATE referrals SET status='COMPLETED', completed_at=CURRENT_TIMESTAMP WHERE referred_id=? AND status='PENDING'",
            (user_id,),
        )
        cur = await db.execute("SELECT val FROM settings WHERE key='referral_target'")
        row = await cur.fetchone()
        target = int(row[0]) if row and row[0] and int(row[0]) >= 1 else REFERRAL_TARGET
        cur = await db.execute("SELECT value FROM bot_config WHERE key='referral_type'")
        row = await cur.fetchone()
        rtype = row[0] if row and row[0] in ("balance", "feature") else "balance"
        cur = await db.execute("SELECT value FROM bot_config WHERE key='referral_feature_text'")
        row = await cur.fetchone()
        rtext = (row[0] if row and row[0] else "") if rtype == "feature" else ""

        created = []
        for _ in range(20):
            cur = await db.execute(
                "SELECT referred_id FROM referrals WHERE referrer_id=? AND status='COMPLETED' AND reward_id IS NULL "
                "ORDER BY completed_at, referred_id LIMIT ?", (referrer, target),
            )
            ids = [x[0] for x in await cur.fetchall()]
            if len(ids) < target:
                break
            cur = await db.execute("SELECT COALESCE(MAX(batch_no), 0) + 1 FROM referral_rewards WHERE referrer_id=?", (referrer,))
            batch = (await cur.fetchone())[0]
            amount = await compute_reward(db, ids) if rtype == "balance" else 0
            cur = await db.execute(
                "INSERT INTO referral_rewards (referrer_id, batch_no, amount, rtype, rtext) VALUES (?, ?, ?, ?, ?)",
                (referrer, batch, amount, rtype, rtext),
            )
            rid = cur.lastrowid
            await db.execute(
                f"UPDATE referrals SET reward_id=? WHERE referred_id IN ({','.join('?' * len(ids))})", (rid, *ids)
            )
            created.append((rid, amount))
        cur = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=? AND status='COMPLETED'", (referrer,))
        done = (await cur.fetchone())[0]
        cur = await db.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id=? AND status='COMPLETED' AND reward_id IS NULL", (referrer,)
        )
        in_batch = (await cur.fetchone())[0]
        return {"referrer": referrer, "done": done, "in_batch": in_batch, "target": target,
                "rtype": rtype, "rtext": rtext, "created": created}


async def referral_decide_reward(rid: int, approve: bool):
    """يرجع (الحالة، user_id، المبلغ، النوع، النص): OK | DONE | NO_AMOUNT | ERROR."""
    try:
        async with write_tx() as db:
            cur = await db.execute(
                "SELECT referrer_id, amount, status, rtype, rtext FROM referral_rewards WHERE id=?", (rid,)
            )
            row = await cur.fetchone()
            if not row or row[2] != "PENDING":
                return "DONE", 0, 0, "", ""
            uid, amount, _, rtype, rtext = row
            if not approve:
                await db.execute("UPDATE referral_rewards SET status='REJECTED', decided_at=CURRENT_TIMESTAMP WHERE id=?", (rid,))
                return "OK", uid, 0, rtype, rtext
            if rtype == "feature":
                await db.execute("UPDATE referral_rewards SET status='PAID', decided_at=CURRENT_TIMESTAMP WHERE id=?", (rid,))
                return "OK", uid, 0, rtype, rtext
            if amount <= 0:  # لم تكن القيمة محددة عند الإنشاء: نحسبها بالإعدادات الحالية
                cur = await db.execute("SELECT referred_id FROM referrals WHERE reward_id=?", (rid,))
                amount = await compute_reward(db, [x[0] for x in await cur.fetchall()])
            if amount <= 0:
                return "NO_AMOUNT", 0, 0, rtype, rtext
            await db.execute(
                "UPDATE referral_rewards SET status='PAID', amount=?, decided_at=CURRENT_TIMESTAMP WHERE id=?", (amount, rid)
            )
            nb = await WalletService._credit(db, uid, amount, f"REFRW-{rid}", "REFERRAL", "مكافأة إحالة")
            if nb is None:
                raise RuntimeError("referrer missing")
            return "OK", uid, amount, rtype, rtext
    except Exception as e:
        log.error("referral_decide_reward error: %s", e)
        return "ERROR", 0, 0, "", ""


async def referral_after_completion(user_id: int):
    """إشعارات بعد أول شحن مؤكد للمدعو: تقدّم صاحب الدعوة، وطلب صرف المكافأة لمجموعة المراجعة."""
    res = await referral_mark_completed(user_id)
    if not res:
        return
    referrer, target = res["referrer"], res["target"]
    try:
        if res["created"]:
            msg = (f"🎁 <b>أكملت {target} إحالات ناجحة!</b>\nتم إرسال طلب مكافأتك للإدارة للمراجعة، "
                   f"وسيصلك إشعار فور الموافقة.")
        else:
            msg = (f"🎁 <b>إحالة جديدة مكتملة!</b>\nقام أحد أصدقائك بشحن محفظته.\n"
                   f"تقدّمك: <b>{res['in_batch']} / {target}</b>")
        await bot.send_message(referrer, msg)
    except Exception:
        pass
    for reward_id, amount in res["created"]:
        u = await WalletService.get_or_create_user(referrer)
        if res["rtype"] == "feature":
            value_line = f"🎁 نوع المكافأة: <b>ميزة</b> — {esc(res['rtext'] or 'غير محدد')}"
            warn = "" if res["rtext"] else "\n⚠️ لم يُحدَّد وصف الميزة — حدّده من لوحة المدير (🎁 الإحالة)."
        else:
            value_line = f"💰 قيمة المكافأة: <b>{amount:,} ل.س</b> (رصيد)"
            warn = "" if amount > 0 else "\n⚠️ لم تُحدَّد قيمة المكافأة بعد — حدّدها من لوحة المدير (🎁 الإحالة) ثم اضغط صرف."
        text = (
            f"🎁 <b>طلب صرف مكافأة إحالة</b>\n"
            f"👤 الزبون: {('@' + esc(u[1])) if u[1] else 'بدون'} (<code>{referrer}</code>)\n"
            f"🔑 UID: <code>{referrer}</code>\n"
            f"📛 الاسم: {esc(u[6] or '—')}\n"
            f"✅ إحالات مكتملة: <b>{res['done']}</b> (الهدف: {target} لكل مكافأة)\n"
            f"{value_line}{warn}"
        )
        kb = KB([[B("✅ صرف المكافأة", f"ref_rw:ok:{reward_id}"), B("❌ رفض", f"ref_rw:no:{reward_id}")]])
        await send_to_staff(REFERRAL_ADMIN_GROUP, text, kb)


async def referral_screen(uid: int):
    target = await get_referral_target()
    rtype = await get_config("referral_type", "balance")
    rtext = await get_config("referral_feature_text", "")
    async with get_db() as db:
        cur = await db.execute("SELECT ref_enrolled FROM users WHERE user_id=?", (uid,))
        r = await cur.fetchone()
        enrolled = bool(r and r[0])
        cur = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=? AND status='COMPLETED'", (uid,))
        done = (await cur.fetchone())[0]
        cur = await db.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id=? AND status='COMPLETED' AND reward_id IS NULL", (uid,))
        in_batch = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=? AND status='PENDING'", (uid,))
        pending = (await cur.fetchone())[0]
    reward = int(await get_setting("referral_reward"))
    pct = await get_setting("referral_percent")
    if rtype == "feature":
        prize = f"🎁 المكافأة: <b>{esc(rtext)}</b>\n" if rtext else ""
    elif pct > 0:
        prize = f"🎁 المكافأة: <b>{pct:g}%</b> من أول شحن لأصدقائك\n"
    elif reward > 0:
        prize = f"🎁 المكافأة: <b>{reward:,} ل.س</b> رصيد في محفظتك\n"
    else:
        prize = ""
    if not enrolled:
        text = (
            "🎁 <b>شارك واربح</b>\n────────────────────────────\n"
            f"ادعُ أصدقاءك عبر رابطك الخاص. وعندما يقوم <b>{target} أشخاص</b> منهم بشحن محفظتهم "
            "داخل البوت (بعد تأكيد الإيداع) تحصل على مكافأة.\n"
            + (f"\n{prize}" if prize else "") +
            "\n• لا تُحتسب الإحالة بمجرد الدخول أو الاشتراك بالقناة أو التصفح، بل فور أول شحن مؤكد للمحفظة.\n"
            "• الاشتراك في البرنامج اختياري."
        )
        kb = KB([[B("✅ اشترك في برنامج الإحالة", "ref:join")], [B("🔙 الرئيسية", "back_home")]])
    else:
        link = f"https://t.me/{await get_bot_username()}?start=ref_{uid}"
        text = (
            "🎁 <b>شارك واربح</b>\n────────────────────────────\n"
            f"🔗 رابط دعوتك:\n<code>{link}</code>\n\n"
            f"✅ إحالات مكتملة: <b>{done}</b>\n"
            f"⏳ بانتظار أول شحن: <b>{pending}</b>\n"
            f"📈 تقدّمك نحو المكافأة القادمة: <b>{in_batch} / {target}</b>\n"
            + prize +
            "\nانسخ الرابط وأرسله لأصدقائك."
        )
        kb = KB([[B("🔄 تحديث", "ref:home")], [B("🔙 الرئيسية", "back_home")]])
    return text, kb


@dp.callback_query(F.data == "ref:home")
async def ref_home(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = await referral_screen(cb.from_user.id)
    await safe_edit(cb, text, kb)


@dp.callback_query(F.data == "ref:join")
async def ref_join(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await WalletService.get_or_create_user(cb.from_user.id, cb.from_user.username or "", cb.from_user.full_name or "")
    await exec_sql("UPDATE users SET ref_enrolled=1 WHERE user_id=?", (cb.from_user.id,))
    text, kb = await referral_screen(cb.from_user.id)
    await safe_edit(cb, text, kb)


@dp.callback_query(F.data.startswith("ref_rw:"))
async def ref_reward_action(cb: types.CallbackQuery):
    if not await staff_guard(cb):
        return
    _, act, rid_s = cb.data.split(":")
    status, uid, amount, rtype, rtext = await referral_decide_reward(int(rid_s), act == "ok")
    if status == "NO_AMOUNT":
        await cb.answer("⚠️ حدّد قيمة المكافأة أولاً من لوحة المدير (🎁 الإحالة).", show_alert=True)
        return
    if status == "DONE":
        await cb.answer("⚠️ تمت معالجة هذا الطلب مسبقاً!", show_alert=True)
        return
    if status != "OK":
        await cb.answer("⚠️ حدث خطأ، حاول مجدداً.", show_alert=True)
        return
    try:
        if act == "ok" and rtype == "feature":
            await bot.send_message(uid, f"🎉 <b>تهانينا!</b> أكملت إحالاتك بنجاح.\n🎁 مكافأتك: <b>{esc(rtext or 'ميزة خاصة')}</b>\nتواصل مع الدعم لاستلامها.")
        elif act == "ok":
            await bot.send_message(uid, f"🎉 <b>تهانينا!</b> أكملت إحالاتك بنجاح، وتمت إضافة <b>{amount:,} ل.س</b> إلى محفظتك كمكافأة.")
        else:
            await bot.send_message(uid, "ℹ️ تمت مراجعة طلب مكافأة الإحالة ولم تتم الموافقة عليه. للاستفسار تواصل مع الدعم.")
    except Exception as e:
        log.warning("notify referrer failed: %s", e)
    if act != "ok":
        note = "🔴 <b>تم رفض المكافأة</b>"
    elif rtype == "feature":
        note = f"🟢 <b>تمت الموافقة على المكافأة (ميزة): {esc(rtext)}</b>"
    else:
        note = f"🟢 <b>تم صرف المكافأة ({amount:,} ل.س)</b>"
    await log_staff(cb, "REWARD_OK" if act == "ok" else "REWARD_NO", rid_s, note[:200])
    await append_status(cb.message, note + by_line(cb))


# =====================================================================
# 20. لوحة المدير (كاملة)
# =====================================================================
def is_admin_cb(cb: types.CallbackQuery) -> bool:
    return cb.from_user.id == ADMIN_ID


async def show_admin_home(cb: types.CallbackQuery):
    await safe_edit(cb, await admin_title(), await admin_kb())


@dp.callback_query(F.data == "adm:home")
async def adm_home_return(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.clear()
    await show_admin_home(cb)


@dp.callback_query(F.data == "adm:close")
async def adm_close(cb: types.CallbackQuery):
    if not is_admin_cb(cb):
        return
    try:
        await cb.message.delete()
    except Exception:
        pass


# ---------------- الإحصائيات ----------------
@dp.callback_query(F.data == "adm:stats")
async def adm_stats_view(cb: types.CallbackQuery):
    if not is_admin_cb(cb):
        return
    async def one(db, sql):
        return (await (await db.execute(sql)).fetchone())[0] or 0

    async with get_db() as db:
        users = await one(db, "SELECT COUNT(*) FROM users")
        vip = await one(db, "SELECT COUNT(*) FROM users WHERE is_vip=1")
        banned = await one(db, "SELECT COUNT(*) FROM users WHERE is_banned=1")
        orders = await one(db, "SELECT COUNT(*) FROM orders")
        pending = await one(db, "SELECT COUNT(*) FROM orders WHERE status='PROCESSING'")
        done = await one(db, "SELECT COUNT(*) FROM orders WHERE status='COMPLETED'")
        refunded = await one(db, "SELECT COUNT(*) FROM orders WHERE status='REFUNDED'")
        income = await one(db, "SELECT SUM(amount) FROM payments WHERE status='ACCEPTED'")
        liab = await one(db, "SELECT SUM(balance) FROM users")
        sales = await one(db, "SELECT SUM(price) FROM orders WHERE status IN ('PROCESSING','COMPLETED')")
        t_orders = await one(db, "SELECT COUNT(*) FROM orders WHERE date(created_at)=date('now')")
        t_sales = await one(db, "SELECT SUM(price) FROM orders WHERE date(created_at)=date('now') AND status IN ('PROCESSING','COMPLETED')")
        t_dep = await one(db, "SELECT SUM(amount) FROM payments WHERE status='ACCEPTED' AND date(created_at)=date('now')")
    rate = await get_setting("dollar_rate")
    text = (
        f"📊 <b>إحصائيات المنصة:</b>\n"
        f"────────────────────────────\n"
        f"👥 المستخدمون: <b>{users:,}</b> (VIP: {vip:,} | محظور: {banned:,})\n"
        f"📦 الطلبات: <b>{orders:,}</b> (منفذ: {done:,} | معلق: {pending:,} | مسترجع: {refunded:,})\n"
        f"💰 إجمالي الإيداعات المقبولة: <b>{income:,} ل.س</b>\n"
        f"🛒 إجمالي المبيعات: <b>{sales:,} ل.س</b>\n"
        f"🏦 أرصدة الزبائن (التزامات): <b>{liab:,} ل.س</b>\n"
        f"────────────────────────────\n"
        f"📅 <b>اليوم (UTC):</b> طلبات {t_orders:,} | مبيعات {t_sales:,} | إيداعات {t_dep:,} ل.س\n"
        f"💱 سعر الدولار: <b>{rate:,.2f} ل.س</b>"
    )
    await safe_edit(cb, text, KB([[B("🔄 تحديث", "adm:stats")], [B("🔙 رجوع", "adm:home")]]))


# ---------------- الطلبات والإيداعات المعلقة ----------------
@dp.callback_query(F.data == "adm:pend")
async def adm_pending_orders(cb: types.CallbackQuery):
    if not is_admin_cb(cb):
        return
    async with get_db() as db:
        cur = await db.execute(
            "SELECT order_id, service_name, price FROM orders WHERE status='PROCESSING' ORDER BY created_at DESC LIMIT 20"
        )
        rows = await cur.fetchall()
    if not rows:
        await safe_edit(cb, "✅ لا توجد طلبات معلقة.", KB([[B("🔙 رجوع", "adm:home")]]))
        return
    kb = [[B(f"{price:,} | {name[:30]}", f"adm:o:{oid}")] for oid, name, price in rows]
    kb.append([B("🔙 رجوع", "adm:home")])
    await safe_edit(cb, f"📋 <b>الطلبات المعلقة</b> (آخر {len(rows)}):\nاضغط على طلب لعرض بطاقته وتنفيذه:", KB(kb))


async def order_admin_card(oid: str):
    row = await fetch_one(
        "SELECT user_id, department, service_name, target_data, price, status, created_at, cost, cancel_reason "
        "FROM orders WHERE order_id=?", (oid,)
    )
    if not row:
        return None, None
    profit = f"\n📈 الربح: <b>{row['price'] - row['cost']:,.0f} ل.س</b> (التكلفة {row['cost']:,.0f})" if row["cost"] is not None else ""
    text = (
        f"📦 <b>بطاقة طلب</b>\n"
        f"🆔 رقم الطلب: <code>{oid}</code>\n"
        f"👤 الزبون: <code>{row['user_id']}</code>\n"
        f"🔑 UID: <code>{row['user_id']}</code>\n"
        f"🗂 القسم: {esc(row['department'])}\n"
        f"📦 الخدمة: <b>{esc(row['service_name'])}</b>\n"
        f"🎯 البيانات: <code>{esc(row['target_data'])}</code>\n"
        f"💰 السعر: <b>{row['price']:,} ل.س</b>{profit}\n"
        f"📌 الحالة: <b>{row['status']}</b>\n"
        f"🕒 {row['created_at']}"
        + (f"\n📝 سبب الإلغاء: {esc(row['cancel_reason'])}" if row["cancel_reason"] else "")
    )
    kb = KB([[B("✅ تم التنفيذ", f"ord_act:done:{oid}"), B("❌ إلغاء واسترجاع", f"ord_act:ref:{oid}")]]) if row["status"] == "PROCESSING" else None
    return text, kb


@dp.callback_query(F.data.startswith("adm:o:"))
async def adm_order_card(cb: types.CallbackQuery):
    if not is_admin_cb(cb):
        return
    text, kb = await order_admin_card(cb.data.split(":", 2)[2])
    if not text:
        await cb.answer("⚠️ الطلب غير موجود.", show_alert=True)
        return
    await cb.message.answer(text, reply_markup=kb)


@dp.callback_query(F.data == "adm:findo")
async def adm_find_order_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.set_state(AdminActions.find_order)
    await safe_edit(cb, "🔎 أرسل <b>رقم الطلب</b> (مثال: <code>10023</code>):", cancel_kb("adm:home"))


@dp.message(AdminActions.find_order)
async def adm_find_order_rec(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    oid = normalize_digits(txt(message)).replace(",", "")
    text, kb = await order_admin_card(oid)
    if not text:
        await message.reply("⚠️ لا يوجد طلب بهذا الرقم. أعد المحاولة:")
        return
    await state.clear()
    await message.answer(text, reply_markup=kb)


@dp.callback_query(F.data == "adm:payp")
async def adm_pending_payments(cb: types.CallbackQuery):
    if not is_admin_cb(cb):
        return
    async with get_db() as db:
        cur = await db.execute(
            "SELECT payment_id, user_id, amount FROM payments WHERE status='UNDER_REVIEW' ORDER BY created_at DESC LIMIT 20"
        )
        rows = await cur.fetchall()
    if not rows:
        await safe_edit(cb, "✅ لا توجد إيداعات قيد المراجعة.", KB([[B("🔙 رجوع", "adm:home")]]))
        return
    kb = [[B(f"{amt:,} ل.س | {uid}", f"adm:p:{pid}")] for pid, uid, amt in rows]
    kb.append([B("🔙 رجوع", "adm:home")])
    await safe_edit(cb, f"💳 <b>الإيداعات قيد المراجعة</b> (آخر {len(rows)}):\nاضغط لعرض الإشعار وقبوله أو رفضه:", KB(kb))


@dp.callback_query(F.data.startswith("adm:p:"))
async def adm_payment_card(cb: types.CallbackQuery):
    if not is_admin_cb(cb):
        return
    pid = cb.data.split(":", 2)[2]
    async with get_db() as db:
        cur = await db.execute(
            "SELECT user_id, amount, sham_tx_id, receipt_file_id, status FROM payments WHERE payment_id=?", (pid,)
        )
        r = await cur.fetchone()
    if not r:
        await cb.answer("⚠️ الدفعة غير موجودة.", show_alert=True)
        return
    uid, amt, tx, file_id, status = r
    text = (
        f"💳 <b>بطاقة إيداع</b>\n"
        f"🆔 رقم الدفعة: <code>{pid}</code>\n"
        f"👤 الزبون: <code>{uid}</code>\n"
        f"🔑 UID: <code>{uid}</code>\n"
        f"💰 المبلغ: <b>{amt:,} ل.س</b>\n"
        f"🧾 رقم العملية: <code>{esc(tx or '')}</code>\n"
        f"📌 الحالة: <b>{status}</b>"
    )
    kb = KB([[B("✅ قبول وتغذية الرصيد", f"adm_pay:ok:{pid}"), B("❌ رفض الإيداع", f"adm_pay:no:{pid}")]]) if status == "UNDER_REVIEW" else None
    try:
        if file_id:
            await bot.send_photo(cb.from_user.id, photo=file_id, caption=text, reply_markup=kb)
        else:
            await cb.message.answer(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)


# ---------------- إدارة المستخدمين ----------------
async def user_card(uid: int):
    async with get_db() as db:
        cur = await db.execute(f"SELECT {USER_COLS}, created_at FROM users WHERE user_id=?", (uid,))
        u = await cur.fetchone()
        if not u:
            return None, None
        c = await (await db.execute("SELECT COUNT(*), COALESCE(SUM(status='PROCESSING'),0) FROM orders WHERE user_id=?", (uid,))).fetchone()
        dep = (await (await db.execute("SELECT SUM(amount) FROM payments WHERE user_id=? AND status='ACCEPTED'", (uid,))).fetchone())[0] or 0
        led = await (await db.execute(
            "SELECT type, amount, balance_after, created_at FROM wallet_ledger WHERE user_id=? ORDER BY ledger_id DESC LIMIT 5", (uid,)
        )).fetchall()
    uname = f"@{esc(u[1])}" if u[1] else "—"
    lines = "\n".join(f"• {t} | {a:+,} → {b:,} | {d}" for t, a, b, d in led) or "—"
    text = (
        f"👤 <b>بطاقة مستخدم</b>\n"
        f"────────────────────────────\n"
        f"🆔 <code>{u[0]}</code> | {uname}\n"
        f"📛 الاسم: {esc(u[6] or '—')}\n"
        f"💰 الرصيد: <b>{u[2]:,} ل.س</b>\n"
        f"⭐ VIP: {'نعم' if u[3] else 'لا'} | 🚫 محظور: {'نعم' if u[4] else 'لا'} | الرتبة: {u[5]}\n"
        f"📦 الطلبات: {c[0]} (معلق: {c[1]}) | 💳 إجمالي الإيداعات: {dep:,}\n"
        f"🕒 انضم: {u[7]}\n"
        f"────────────────────────────\n"
        f"🧾 <b>آخر الحركات:</b>\n{lines}"
    )
    kb = KB([
        [B("➕ إضافة رصيد", f"adm:ub:add:{uid}"), B("➖ سحب رصيد", f"adm:ub:sub:{uid}")],
        [B("✅ فك الحظر" if u[4] else "🚫 حظر", f"adm:ban:{uid}"), B("✉️ مراسلة", f"adm:msg:{uid}")],
        [B("🔙 لوحة التحكم", "adm:home")],
    ])
    return text, kb


@dp.callback_query(F.data == "adm:user")
async def adm_user_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.set_state(AdminActions.find_user)
    await safe_edit(cb, "👤 أرسل <b>آيدي المستخدم</b> أو <b>@اسم_المستخدم</b>:", cancel_kb("adm:home"))


@dp.message(AdminActions.find_user)
async def adm_user_find(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    q = txt(message)
    uid = to_int(q)
    if uid is None and q:
        async with get_db() as db:
            cur = await db.execute("SELECT user_id FROM users WHERE lower(username)=lower(?)", (q.lstrip("@"),))
            row = await cur.fetchone()
        uid = row[0] if row else None
    if uid is None:
        await message.reply("⚠️ لم أجد مستخدماً بهذا المعرف. أعد المحاولة:")
        return
    text, kb = await user_card(uid)
    if not text:
        await message.reply("⚠️ المستخدم غير موجود في قاعدة البيانات. أعد المحاولة:")
        return
    await state.clear()
    await message.answer(text, reply_markup=kb)


@dp.callback_query(F.data.startswith("adm:ban:"))
async def adm_toggle_ban(cb: types.CallbackQuery):
    if not is_admin_cb(cb):
        return
    uid = int(cb.data.split(":")[2])
    if uid == ADMIN_ID:
        await cb.answer("⛔ لا يمكن حظر المدير.", show_alert=True)
        return
    async with get_db() as db:
        await db.execute("UPDATE users SET is_banned = 1 - is_banned WHERE user_id=?", (uid,))
    text, kb = await user_card(uid)
    if text:
        await safe_edit(cb, text, kb)


@dp.callback_query(F.data.startswith("adm:ub:"))
async def adm_user_balance(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    _, _, mode, uid = cb.data.split(":")
    await state.update_data(target_uid=int(uid), bal_mode=mode)
    await state.set_state(AdminActions.add_bal_amount)
    verb = "إضافته إلى" if mode == "add" else "سحبه من"
    await cb.message.answer(f"💵 أدخل المبلغ المراد {verb} حساب <code>{uid}</code>:", reply_markup=cancel_kb("adm:home"))


@dp.callback_query(F.data.startswith("adm:msg:"))
async def adm_user_msg_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    uid = int(cb.data.split(":")[2])
    await state.update_data(target_uid=uid)
    await state.set_state(AdminActions.msg_user)
    await cb.message.answer(f"✉️ اكتب الرسالة التي تريد إرسالها للمستخدم <code>{uid}</code>:", reply_markup=cancel_kb("adm:home"))


@dp.message(AdminActions.msg_user)
async def adm_user_msg_send(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if not txt(message):
        await message.reply("⚠️ أرسل نصاً:")
        return
    uid = (await state.get_data()).get("target_uid")
    await state.clear()
    try:
        await bot.send_message(uid, f"💬 <b>رسالة من الإدارة:</b>\n\n{esc(txt(message))}")
        await message.reply("✅ تم إرسال الرسالة.")
    except TelegramForbiddenError:
        await message.reply("⚠️ المستخدم حظر البوت.")
    except Exception as e:
        await message.reply(f"⚠️ فشل الإرسال: {esc(str(e))}")


# ---------------- تغذية/سحب الرصيد ----------------
@dp.callback_query(F.data.in_({"adm:add_bal", "adm:sub_bal"}))
async def adm_bal_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    mode = "add" if cb.data == "adm:add_bal" else "sub"
    await state.clear()
    await state.update_data(bal_mode=mode)
    await state.set_state(AdminActions.add_bal_user)
    verb = "تغذية رصيده" if mode == "add" else "سحب الرصيد منه"
    await safe_edit(cb, f"👤 أدخل آيدي المستخدم (User ID) المراد {verb}:", cancel_kb("adm:home"))


@dp.message(AdminActions.add_bal_user)
async def adm_bal_user_rec(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    u_id = to_int(txt(message))
    if not u_id:
        await message.reply("⚠️ يرجى إدخال آيدي صحيح بالأرقام:")
        return
    await state.update_data(target_uid=u_id)
    await state.set_state(AdminActions.add_bal_amount)
    await message.answer(f"💵 أدخل المبلغ لحساب <code>{u_id}</code>:")


@dp.message(AdminActions.add_bal_amount)
async def adm_bal_amt_rec(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    amt = to_int(txt(message))
    if not amt or amt <= 0:
        await message.reply("⚠️ المبلغ يجب أن يكون رقماً صحيحاً وأكبر من صفر:")
        return
    data = await state.get_data()
    u_id, mode = data.get("target_uid"), data.get("bal_mode", "add")
    await state.clear()
    if not u_id:
        await message.reply("⚠️ انتهت الجلسة، أعد المحاولة من /admin")
        return
    await WalletService.get_or_create_user(u_id)
    ref = generate_uid("ADM")
    if mode == "add":
        ok = await WalletService.deposit(u_id, amt, ref, "تغذية إدارية مباشرة")
        if ok:
            u = await WalletService.get_or_create_user(u_id)
            await message.reply(f"✅ تمت إضافة <b>{amt:,} ل.س</b> للمستخدم <code>{u_id}</code>.\n💰 رصيده الآن: <b>{u[2]:,}</b>")
            try:
                await bot.send_message(u_id, f"🎉 <b>تمت إضافة {amt:,} ل.س إلى رصيد محفظتك من الإدارة!</b>")
            except Exception:
                pass
        else:
            await message.reply("❌ تعذر إضافة الرصيد.")
    else:
        nb = await WalletService.admin_debit(u_id, amt, ref, "سحب إداري")
        if nb is None:
            await message.reply("❌ تعذر السحب: رصيد المستخدم لا يكفي أو المستخدم غير موجود.")
        else:
            await message.reply(f"✅ تم سحب <b>{amt:,} ل.س</b> من <code>{u_id}</code>.\n💰 رصيده الآن: <b>{nb:,}</b>")
            try:
                await bot.send_message(u_id, f"ℹ️ تم سحب <b>{amt:,} ل.س</b> من رصيد محفظتك من قبل الإدارة.")
            except Exception:
                pass


# ---------------- سعر الدولار ونسب الربح ----------------
@dp.callback_query(F.data == "adm:set_rate")
async def adm_set_rate_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
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
    await message.reply(f"✅ تم تحديث سعر صرف الدولار إلى: <b>{val:,.2f} ل.س</b>\nالأسعار المبنية على الدولار تتبعه فوراً، أما ما سعره بالليرة (الشات بالكمية، الرصيد والكاش) فيبقى ثابتاً.")


# ---------------- إدارة الخدمات (الكتالوج) ----------------
def cur_sym(cur: str) -> str:
    return "$" if cur == "USD" else "ل.س"


def parse_price(s: str):
    """رقم مع $ = دولار، وبدونها = ليرة سورية. يرجع (السعر, العملة) أو None."""
    s = s.strip().replace("٫", ".").replace("،", ",")
    usd = "$" in s
    s = s.replace("$", "").replace(",", "").strip()
    try:
        v = float(s)
    except ValueError:
        return None
    if v != v or v <= 0 or v > 1e9:
        return None
    return v, ("USD" if usd else "SYP")


def parse_pack_lines(text: str):
    """كل سطر: الاسم = السعر. يرجع (القائمة, الأسطر الخاطئة)."""
    good, bad = [], []
    for line in text.splitlines():
        line = line.strip().lstrip("*•-– ").strip()
        if not line:
            continue
        label, sep, price = line.rpartition("=")
        pr = parse_price(price) if sep else None
        label = label.strip()
        if not label or len(label) > 80 or pr is None:
            bad.append(line)
        else:
            good.append((label, pr[0], pr[1]))
    return good, bad


async def service_card(sid: int):
    s = await get_service(sid)
    if not s:
        return None, None
    packs = await fetch_all("SELECT * FROM catalog_packs WHERE service_id=? ORDER BY id", (sid,))
    sec = SECTIONS[s["section"]]
    plat = f" | المنصة: {SOCIAL_PLATFORMS[s['platform']][1]}" if s["platform"] in SOCIAL_PLATFORMS else ""
    lines = [
        f"🗂 <b>{esc(s['name'])}</b>",
        f"القسم: {sec['label']}{plat}",
        f"الحالة: {'🙈 مخفية عن الزبائن' if s['is_hidden'] else '👁 ظاهرة'}",
        f"النوع: {'بالكمية' if s['kind'] == 'qty' else 'فئات ثابتة'}",
        f"نص الطلب: {esc(s['ask'] or '—')}",
    ]
    if s["notes"]:
        lines.append(f"الملاحظات: {esc(s['notes'])}")
    if s["kind"] == "qty":
        lines.append(f"📉 الحد الأدنى: {s['min_qty']:,} = {fmt_num(s['min_price'])} ل.س | 📈 الوحدة بعده: {fmt_num(s['unit_price'])} ل.س")
    else:
        lines.append(f"عدد الفئات: {len(packs)}" + ("  ⚠️ لا فئات: الخدمة لا تظهر للزبائن" if not packs else ""))
    if s["tok_min"]:
        lines.append(f"🪙 توكنز: الحد الأدنى {s['tok_min']:,} | سعر التوكن {fmt_num(s['tok_unit'])} ل.س")
    rows = []
    for p in packs:
        mark = "🙈 " if p["is_hidden"] else ""
        rows.append([B(f"{mark}{p['label']} — {fmt_num(p['price'])}{cur_sym(p['cur'])}", f"adm:pk:{p['id']}")])
    if s["kind"] == "packs":
        rows.append([B("➕ إضافة فئات", f"adm:pa:{sid}")])
    else:
        rows.append([B("✏️ الحد الأدنى والأسعار", f"adm:ed:s:{sid}:qty")])
    if s["tok_min"]:
        rows.append([B("🪙 تعديل التوكنز", f"adm:ed:s:{sid}:tok")])
    rows.append([B("✏️ الاسم", f"adm:ed:s:{sid}:name"), B("✏️ نص الطلب", f"adm:ed:s:{sid}:ask")])
    rows.append([B("✏️ الملاحظات", f"adm:ed:s:{sid}:notes")])
    rows.append([B("🔒 بيانات حساسة: مفعّل" if s.get("sensitive") else "🔓 بيانات حساسة: معطّل", f"adm:sens:{sid}")])
    rows.append([B("👁 إظهار" if s["is_hidden"] else "🙈 إخفاء", f"adm:hd:s:{sid}"), B("🗑 حذف الخدمة", f"adm:dl:s:{sid}")])
    rows.append([B("🔙 القسم", f"adm:cs:{s['section']}:0")])
    return "\n".join(lines), KB(rows)


async def pack_card(pid: int):
    p = await fetch_one("SELECT * FROM catalog_packs WHERE id=?", (pid,))
    if not p:
        return None, None
    s = await get_service(p["service_id"])
    text = (
        f"💠 <b>{esc(p['label'])}</b>\n"
        f"الخدمة: {esc(s['name'] if s else '—')}\n"
        f"💰 سعر الجملة: <b>{fmt_num(p['price'])} {cur_sym(p['cur'])}</b> ({'دولار' if p['cur'] == 'USD' else 'ليرة سورية'})\n"
        f"الحالة: {'🙈 مخفية' if p['is_hidden'] else '👁 ظاهرة'}"
    )
    kb = KB([
        [B("✏️ السعر", f"adm:ed:p:{pid}:price"), B("✏️ الاسم", f"adm:ed:p:{pid}:label")],
        [B("👁 إظهار" if p["is_hidden"] else "🙈 إخفاء", f"adm:hd:p:{pid}"), B("🗑 حذف", f"adm:dl:p:{pid}")],
        [B("🔙 الخدمة", f"adm:sv:{p['service_id']}")],
    ])
    return text, kb


@dp.callback_query(F.data == "adm:cat")
async def adm_cat_menu(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.clear()
    rows = []
    for k, meta in SECTIONS.items():
        r = await fetch_one("SELECT COUNT(*) AS n, COALESCE(SUM(is_hidden),0) AS h FROM catalog_services WHERE section=?", (k,))
        rows.append([B(f"{meta['emoji']} {meta['label']} ({r['n']})", f"adm:cs:{k}:0")])
    rows.append([B("🔙 رجوع", "adm:home")])
    await safe_edit(cb, "🗂 <b>إدارة الخدمات</b>\nاختر القسم:", KB(rows))


@dp.callback_query(F.data.startswith("adm:cs:"))
async def adm_cat_section(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.clear()
    _, _, section, page_s = cb.data.split(":")
    if section not in SECTIONS:
        return
    items = await fetch_all(
        "SELECT * FROM catalog_services WHERE section=? ORDER BY " + ("lower(name)" if section == "chat" else "id"), (section,)
    )
    per = 8
    total = max(1, (len(items) + per - 1) // per)
    page = min(max(int(page_s), 0), total - 1)
    chunk = items[page * per:(page + 1) * per]
    rows = [[B("➕ إضافة خدمة جديدة", f"adm:csa:{section}")]]
    rows += rows_of([B(("🙈 " if s["is_hidden"] else "") + s["name"], f"adm:sv:{s['id']}") for s in chunk], 1)
    nav = []
    if page > 0:
        nav.append(B("⬅️ السابق", f"adm:cs:{section}:{page - 1}"))
    if page < total - 1:
        nav.append(B("التالي ➡️", f"adm:cs:{section}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([B("🔙 الأقسام", "adm:cat")])
    meta = SECTIONS[section]
    await safe_edit(cb, f"{meta['emoji']} <b>{meta['label']}</b> — {len(items)} خدمة (صفحة {page + 1} من {total})", KB(rows))


@dp.callback_query(F.data.startswith("adm:sv:"))
async def adm_service_card(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.clear()
    text, kb = await service_card(int(cb.data.split(":")[2]))
    if not text:
        await cb.answer("⚠️ الخدمة غير موجودة.", show_alert=True)
        return
    await safe_edit(cb, text, kb)


@dp.callback_query(F.data.startswith("adm:pk:"))
async def adm_pack_card(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.clear()
    text, kb = await pack_card(int(cb.data.split(":")[2]))
    if not text:
        await cb.answer("⚠️ الفئة غير موجودة.", show_alert=True)
        return
    await safe_edit(cb, text, kb)


@dp.callback_query(F.data.startswith("adm:hd:"))
async def adm_toggle_hidden(cb: types.CallbackQuery):
    if not is_admin_cb(cb):
        return
    _, _, kind, id_s = cb.data.split(":")
    table = "catalog_services" if kind == "s" else "catalog_packs"
    await exec_sql(f"UPDATE {table} SET is_hidden = 1 - is_hidden WHERE id=?", (int(id_s),))
    text, kb = await (service_card(int(id_s)) if kind == "s" else pack_card(int(id_s)))
    if text:
        await safe_edit(cb, text, kb)


@dp.callback_query(F.data.startswith("adm:sens:"))
async def adm_toggle_sensitive(cb: types.CallbackQuery):
    if not is_admin_cb(cb):
        return
    sid = int(cb.data.split(":")[2])
    await exec_sql("UPDATE catalog_services SET sensitive = 1 - COALESCE(sensitive, 0) WHERE id=?", (sid,))
    text, kb = await service_card(sid)
    if text:
        await safe_edit(cb, text, kb)
    await cb.answer("🔒 تُمسح بيانات الطلب (مثل كلمات المرور) تلقائياً بعد التنفيذ أو الإلغاء." )


@dp.callback_query(F.data.startswith("adm:dl:"))
async def adm_delete_confirm(cb: types.CallbackQuery):
    if not is_admin_cb(cb):
        return
    _, _, kind, id_s = cb.data.split(":")
    if kind == "s":
        s = await get_service(int(id_s))
        name, back = (s["name"] if s else "—"), f"adm:sv:{id_s}"
        extra = "\nسيُحذف معها كل فئاتها."
    else:
        p = await fetch_one("SELECT * FROM catalog_packs WHERE id=?", (int(id_s),))
        name, back = (p["label"] if p else "—"), f"adm:pk:{id_s}"
        extra = ""
    await safe_edit(
        cb, f"🗑 هل أنت متأكد من حذف <b>{esc(name)}</b>؟{extra}\n\nالطلبات السابقة والأرصدة لا تتأثر.",
        KB([[B("✅ نعم، احذف", f"adm:dly:{kind}:{id_s}"), B("❌ تراجع", back)]]),
    )


@dp.callback_query(F.data.startswith("adm:dly:"))
async def adm_delete_do(cb: types.CallbackQuery):
    if not is_admin_cb(cb):
        return
    _, _, kind, id_s = cb.data.split(":")
    sid = int(id_s)
    if kind == "s":
        s = await get_service(sid)
        await exec_sql("DELETE FROM catalog_packs WHERE service_id=?", (sid,))
        await exec_sql("DELETE FROM catalog_services WHERE id=?", (sid,))
        await cb.answer("🗑 تم حذف الخدمة.", show_alert=True)
        sec = s["section"] if s else None
        if sec:
            items = await fetch_all("SELECT id FROM catalog_services WHERE section=?", (sec,))
            await safe_edit(cb, f"{SECTIONS[sec]['emoji']} تم الحذف. المتبقي في القسم: {len(items)} خدمة.",
                            KB([[B("🔙 القسم", f"adm:cs:{sec}:0")]]))
    else:
        p = await fetch_one("SELECT * FROM catalog_packs WHERE id=?", (sid,))
        await exec_sql("DELETE FROM catalog_packs WHERE id=?", (sid,))
        await cb.answer("🗑 تم حذف الفئة.", show_alert=True)
        if p:
            text, kb = await service_card(p["service_id"])
            if text:
                await safe_edit(cb, text, kb)


# ----- تعديل الحقول -----
EDIT_PROMPTS = {
    "name": "✏️ أرسل الاسم الجديد:",
    "ask": "✏️ أرسل نص الطلب الجديد (ما يظهر للزبون عند طلب بياناته):",
    "notes": "✏️ أرسل الملاحظات الجديدة (أو أرسل <code>-</code> لحذفها):",
    "qty": ("✏️ أرسل ثلاثة أرقام مفصولة بمسافة:\nالحد الأدنى، سعر الحد الأدنى (ل.س)، سعر الوحدة بعده (ل.س)\n"
            "مثال: <code>10000 155.81 0.022</code>"),
    "tok": "✏️ أرسل رقمين: الحد الأدنى للتوكنز، سعر التوكن بالليرة.\nمثال: <code>10000 0.15</code>",
    "price": "✏️ أرسل السعر الجديد. رقم مع <code>$</code> للدولار، وبدونها بالليرة.\nمثال: <code>1.5$</code> أو <code>2500</code>",
    "label": "✏️ أرسل الاسم الجديد للفئة:",
}


@dp.callback_query(F.data.startswith("adm:ed:"))
async def adm_edit_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    _, _, kind, id_s, field = cb.data.split(":")
    if field not in EDIT_PROMPTS:
        return
    await state.clear()
    await state.update_data(ek=kind, eid=int(id_s), field=field)
    await state.set_state(AdminActions.cat_edit)
    back = f"adm:sv:{id_s}" if kind == "s" else f"adm:pk:{id_s}"
    await safe_edit(cb, EDIT_PROMPTS[field], cancel_kb(back))


@dp.message(AdminActions.cat_edit)
async def adm_edit_receive(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    kind, eid, field = data.get("ek"), data.get("eid"), data.get("field")
    t = txt(message)
    if not t or kind not in ("s", "p") or field not in EDIT_PROMPTS:
        await message.reply("⚠️ أرسل قيمة صحيحة:")
        return
    if kind == "s":
        if field in ("name", "ask", "notes"):
            if field == "notes" and t == "-":
                t = ""
            limit = {"name": 80, "ask": 600, "notes": 1500}[field]
            if len(t) > limit or (field == "name" and not t):
                await message.reply(f"⚠️ الطول الأقصى {limit} حرفاً:")
                return
            await exec_sql(f"UPDATE catalog_services SET {field}=? WHERE id=?", (t, eid))
        elif field == "qty":
            parts = t.replace(",", "").split()
            try:
                mn, mp, up = int(parts[0]), float(parts[1]), float(parts[2])
                assert mn >= 1 and mp > 0 and up > 0 and mp == mp and up == up
            except Exception:
                await message.reply("⚠️ الصيغة: الحد الأدنى (عدد صحيح) ثم سعر الحد الأدنى ثم سعر الوحدة، كلها أكبر من صفر:")
                return
            await exec_sql("UPDATE catalog_services SET min_qty=?, min_price=?, unit_price=? WHERE id=?", (mn, mp, up, eid))
        elif field == "tok":
            parts = t.replace(",", "").split()
            try:
                mn, up = int(parts[0]), float(parts[1])
                assert mn >= 1 and up > 0 and up == up
            except Exception:
                await message.reply("⚠️ الصيغة: الحد الأدنى (عدد صحيح) ثم سعر التوكن، أكبر من صفر:")
                return
            await exec_sql("UPDATE catalog_services SET tok_min=?, tok_unit=? WHERE id=?", (mn, up, eid))
        else:
            await message.reply("⚠️ حقل غير صالح.")
            return
        await state.clear()
        text, kb = await service_card(eid)
    else:
        if field == "label":
            if len(t) > 80:
                await message.reply("⚠️ الطول الأقصى 80 حرفاً:")
                return
            await exec_sql("UPDATE catalog_packs SET label=? WHERE id=?", (t, eid))
        elif field == "price":
            pr = parse_price(t)
            if not pr:
                await message.reply("⚠️ سعر غير صالح. مثال: <code>1.5$</code> أو <code>2500</code>")
                return
            await exec_sql("UPDATE catalog_packs SET price=?, cur=? WHERE id=?", (pr[0], pr[1], eid))
        else:
            await message.reply("⚠️ حقل غير صالح.")
            return
        await state.clear()
        text, kb = await pack_card(eid)
    if text:
        await message.answer("✅ تم الحفظ.\n\n" + text, reply_markup=kb)
    else:
        await message.answer("✅ تم الحفظ.", reply_markup=KB([[B("🗂 إدارة الخدمات", "adm:cat")]]))


# ----- إضافة فئات -----
@dp.callback_query(F.data.startswith("adm:pa:"))
async def adm_pack_add_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    sid = int(cb.data.split(":")[2])
    await state.clear()
    await state.update_data(sid=sid)
    await state.set_state(AdminActions.cat_pack_add)
    await safe_edit(
        cb,
        "➕ <b>إضافة فئات</b>\nأرسل كل فئة في سطر بصيغة: <code>الاسم = السعر</code>\n"
        "رقم مع <code>$</code> للدولار، وبدونها بالليرة. ويمكنك إرسال عدة أسطر دفعة واحدة:\n\n"
        "<code>100 جوهرة = 1.5$\n500 جوهرة = 7000</code>",
        cancel_kb(f"adm:sv:{sid}"),
    )


@dp.message(AdminActions.cat_pack_add)
async def adm_pack_add_receive(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    sid = (await state.get_data()).get("sid")
    good, bad = parse_pack_lines(message.text or "")
    if bad or not good:
        await message.reply("⚠️ لم يُضف شيء. أسطر غير صالحة:\n" + "\n".join(esc(b) for b in bad[:10])
                            if bad else "⚠️ أرسل سطراً واحداً على الأقل بصيغة: الاسم = السعر")
        return
    async with get_db() as db:
        await db.executemany("INSERT INTO catalog_packs (service_id, label, price, cur) VALUES (?, ?, ?, ?)",
                             [(sid, l, p, c) for l, p, c in good])
    await state.clear()
    text, kb = await service_card(sid)
    await message.answer(f"✅ أُضيفت {len(good)} فئة.\n\n{text}", reply_markup=kb)


# ----- إضافة خدمة جديدة -----
DEFAULT_ASK = "أرسل آيدي اللاعب:"


@dp.callback_query(F.data.startswith("adm:csa:"))
async def adm_service_add_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    section = cb.data.split(":")[2]
    if section not in SECTIONS:
        return
    await state.clear()
    await state.update_data(new_section=section)
    await state.set_state(AdminActions.cat_new_name)
    await safe_edit(cb, f"➕ <b>خدمة جديدة في {SECTIONS[section]['label']}</b>\nأرسل اسم الخدمة:", cancel_kb(f"adm:cs:{section}:0"))


@dp.message(AdminActions.cat_new_name)
async def adm_service_add_name(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    name = txt(message)
    if not name or len(name) > 80:
        await message.reply("⚠️ أرسل اسماً (حتى 80 حرفاً):")
        return
    data = await state.get_data()
    section = data.get("new_section")
    await state.update_data(new_name=name)
    if section == "chat":
        await message.answer("ما نوع هذه الخدمة؟", reply_markup=KB([
            [B("📊 بالكمية (حد أدنى + سعر وحدة)", "adm:nk:qty")],
            [B("📦 فئات ثابتة", "adm:nk:packs")]]))
    elif section == "social":
        await message.answer("اختر المنصة:", reply_markup=KB(
            [[B(f"{e} {n}", f"adm:np:{k}")] for k, (e, n) in SOCIAL_PLATFORMS.items()]))
    else:
        await state.set_state(AdminActions.cat_new_ask)
        await message.answer(f"أرسل نص الطلب (ما يُطلب من الزبون)، أو <code>-</code> للنص الافتراضي:\n<i>{DEFAULT_ASK}</i>")


@dp.callback_query(F.data.startswith("adm:nk:"))
async def adm_service_add_kind(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.update_data(new_kind=cb.data.split(":")[2])
    await state.set_state(AdminActions.cat_new_ask)
    await safe_edit(cb, f"أرسل نص الطلب (ما يُطلب من الزبون)، أو <code>-</code> للنص الافتراضي:\n<i>{DEFAULT_ASK}</i>")


@dp.callback_query(F.data.startswith("adm:np:"))
async def adm_service_add_platform(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    plat = cb.data.split(":")[2]
    if plat not in SOCIAL_PLATFORMS:
        return
    await state.update_data(new_platform=plat)
    await state.set_state(AdminActions.cat_new_ask)
    await safe_edit(cb, "أرسل نص الطلب (مثلاً: أرسل رابط المنشور:)، أو <code>-</code> للنص الافتراضي:")


async def _create_service(state: FSMContext, qty=None) -> int:
    d = await state.get_data()
    section = d["new_section"]
    kind = d.get("new_kind", "packs")
    ask = d.get("new_ask") or DEFAULT_ASK
    if kind == "qty":
        sid, _ = await exec_sql(
            "INSERT INTO catalog_services (section, platform, name, emoji, ask, kind, min_qty, min_price, unit_price) "
            "VALUES (?, ?, ?, ?, ?, 'qty', ?, ?, ?)",
            (section, d.get("new_platform", ""), d["new_name"], SECTIONS[section]["emoji"], ask, qty[0], qty[1], qty[2]),
        )
    else:
        sid, _ = await exec_sql(
            "INSERT INTO catalog_services (section, platform, name, emoji, ask, kind) VALUES (?, ?, ?, ?, ?, 'packs')",
            (section, d.get("new_platform", ""), d["new_name"], SECTIONS[section]["emoji"], ask),
        )
    return sid


@dp.message(AdminActions.cat_new_ask)
async def adm_service_add_ask(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    t = txt(message)
    if not t or len(t) > 600:
        await message.reply("⚠️ أرسل نصاً (حتى 600 حرف) أو - للافتراضي:")
        return
    await state.update_data(new_ask="" if t == "-" else t)
    d = await state.get_data()
    if d.get("new_kind") == "qty":
        await state.set_state(AdminActions.cat_new_qty)
        await message.answer(EDIT_PROMPTS["qty"])
        return
    sid = await _create_service(state)
    await state.clear()
    text, kb = await service_card(sid)
    await message.answer("✅ أُنشئت الخدمة. أضف لها الآن فئاتها بزر «➕ إضافة فئات» (لا تظهر للزبائن قبل ذلك).\n\n" + text, reply_markup=kb)


@dp.message(AdminActions.cat_new_qty)
async def adm_service_add_qty(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    parts = txt(message).replace(",", "").split()
    try:
        mn, mp, up = int(parts[0]), float(parts[1]), float(parts[2])
        assert mn >= 1 and mp > 0 and up > 0 and mp == mp and up == up
    except Exception:
        await message.reply("⚠️ الصيغة: الحد الأدنى (عدد صحيح) ثم سعر الحد الأدنى ثم سعر الوحدة، كلها أكبر من صفر:")
        return
    sid = await _create_service(state, qty=(mn, mp, up))
    await state.clear()
    text, kb = await service_card(sid)
    await message.answer("✅ أُنشئت الخدمة وهي ظاهرة للزبائن.\n\n" + text, reply_markup=kb)


@dp.callback_query(F.data == "adm:ref")
async def adm_ref_panel(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.clear()
    async with get_db() as db:
        async def one(sql):
            return (await (await db.execute(sql)).fetchone())[0] or 0
        enrolled = await one("SELECT COUNT(*) FROM users WHERE ref_enrolled=1")
        pend = await one("SELECT COUNT(*) FROM referrals WHERE status='PENDING'")
        done = await one("SELECT COUNT(*) FROM referrals WHERE status='COMPLETED'")
        rw_pend = await one("SELECT COUNT(*) FROM referral_rewards WHERE status='PENDING'")
        rw_paid = await one("SELECT COUNT(*) FROM referral_rewards WHERE status='PAID'")
        paid_sum = await one("SELECT SUM(amount) FROM referral_rewards WHERE status='PAID'")
    target = await get_referral_target()
    rtype = await get_config("referral_type", "balance")
    rtext = await get_config("referral_feature_text", "")
    reward = int(await get_setting("referral_reward"))
    pct = await get_setting("referral_percent")
    if rtype == "feature":
        mode = f"🎁 <b>ميزة</b>: {esc(rtext) if rtext else '⚠️ لم يُحدَّد الوصف بعد'}"
    elif pct > 0:
        mode = f"💰 <b>رصيد</b>: نسبة <b>{pct:g}%</b> من مجموع أول شحن لكل صديق في الدفعة"
    else:
        mode = f"💰 <b>رصيد</b>: قيمة ثابتة <b>{reward:,} ل.س</b>"
    text = (
        "🎁 <b>نظام الإحالة</b>\n────────────────────────────\n"
        f"👥 المشتركون في البرنامج: <b>{enrolled:,}</b>\n"
        f"⏳ إحالات بانتظار أول شحن: <b>{pend:,}</b>\n"
        f"✅ إحالات مكتملة: <b>{done:,}</b>\n"
        f"🏆 مكافآت معلقة: <b>{rw_pend:,}</b> | مصروفة: <b>{rw_paid:,}</b> ({paid_sum:,} ل.س)\n"
        f"────────────────────────────\n"
        f"🎯 عدد الإحالات المطلوب لكل مكافأة: <b>{target}</b>\n"
        f"نوع المكافأة: {mode}\n"
        f"<i>تغيير هذه الإعدادات يسري على المكافآت القادمة فقط.</i>"
    )
    rows = [[B(f"🎯 عدد الإحالات المطلوب ({target})", "adm:ref_target")],
            [B("🔁 تبديل النوع: " + ("ميزة ← رصيد" if rtype == "feature" else "رصيد ← ميزة"), "adm:ref_type")]]
    if rtype == "feature":
        rows.append([B("✏️ وصف الميزة", "adm:ref_text")])
    else:
        rows.append([B("✏️ القيمة الثابتة (ل.س)", "adm:ref_set"), B("✏️ النسبة %", "adm:ref_pct")])
    rows.append([B("🔙 رجوع", "adm:home")])
    await safe_edit(cb, text, KB(rows))


@dp.callback_query(F.data == "adm:ref_target")
async def adm_ref_target_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.set_state(AdminActions.set_ref_target)
    await safe_edit(cb, "🎯 أرسل عدد الأشخاص المطلوب دعوتهم (ممن شحنوا محفظتهم) لاحتساب مكافأة واحدة:\nمثال: <code>5</code>", cancel_kb("adm:ref"))


@dp.message(AdminActions.set_ref_target)
async def adm_ref_target_rec(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    val = to_int(txt(message))
    if val is None or not (1 <= val <= 1000):
        await message.reply("⚠️ أدخل رقماً صحيحاً بين 1 و 1000:")
        return
    await update_setting("referral_target", float(val))
    await state.clear()
    await message.reply(f"✅ عدد الإحالات المطلوب لكل مكافأة الآن: <b>{val}</b>")


@dp.callback_query(F.data == "adm:ref_type")
async def adm_ref_type_toggle(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    cur = await get_config("referral_type", "balance")
    await set_config("referral_type", "balance" if cur == "feature" else "feature")
    await adm_ref_panel(cb, state)


@dp.callback_query(F.data == "adm:ref_text")
async def adm_ref_text_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.set_state(AdminActions.set_ref_text)
    await safe_edit(cb, "✏️ أرسل وصف الميزة التي يحصل عليها الزبون (مثال: اشتراك Netflix شهر مجاناً):", cancel_kb("adm:ref"))


@dp.message(AdminActions.set_ref_text)
async def adm_ref_text_rec(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    t = txt(message)
    if not t or len(t) > 300:
        await message.reply("⚠️ أرسل وصفاً (حتى 300 حرف):")
        return
    await set_config("referral_feature_text", t)
    await state.clear()
    await message.reply(f"✅ وصف الميزة الآن: <b>{esc(t)}</b>")


@dp.callback_query(F.data == "adm:ref_set")
async def adm_ref_set_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.set_state(AdminActions.set_reward)
    await safe_edit(cb, "💰 أرسل قيمة المكافأة الثابتة بالليرة السورية (تُودَع في رصيد الزبون عن كل مكافأة):", cancel_kb("adm:ref"))


@dp.message(AdminActions.set_reward)
async def adm_ref_set_rec(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    val = to_int(txt(message))
    if val is None or val < 0 or val > 1_000_000_000:
        await message.reply("⚠️ أدخل رقماً صحيحاً (0 أو أكبر):")
        return
    await update_setting("referral_reward", float(val))
    await state.clear()
    await message.reply(f"✅ قيمة مكافأة الإحالة الثابتة الآن: <b>{val:,} ل.س</b>")


@dp.callback_query(F.data == "adm:ref_pct")
async def adm_ref_pct_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.set_state(AdminActions.set_reward_pct)
    await safe_edit(
        cb,
        "📈 أرسل نسبة المكافأة %.\nتُحسب من <b>مجموع أول شحن مؤكد</b> لأصدقاء الدفعة.\n"
        "مثال: <code>10</code>. وأرسل <code>0</code> لإلغاء النسبة والعودة للقيمة الثابتة.",
        cancel_kb("adm:ref"),
    )


@dp.message(AdminActions.set_reward_pct)
async def adm_ref_pct_rec(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        val = float(normalize_digits(txt(message)).replace("%", "").replace(",", "."))
        if not (0 <= val <= 1000) or val != val:
            raise ValueError
    except ValueError:
        await message.reply("⚠️ أدخل رقماً بين 0 و 1000:")
        return
    await update_setting("referral_percent", val)
    await state.clear()
    await message.reply(f"✅ نسبة مكافأة الإحالة الآن: <b>{val:g}%</b>" + ("" if val > 0 else " (معطّلة: تُستخدم القيمة الثابتة)"))


def _local_day(days_ago: int = 0) -> str:
    return f"date('now', '+{TZ_OFFSET_HOURS} hours', '-{int(days_ago)} days')"


async def build_report(days_ago: int = 0) -> str:
    day = _local_day(days_ago)
    ld = f"date(created_at, '+{TZ_OFFSET_HOURS} hours')"
    async with get_db() as db:
        async def one(sql):
            return await (await db.execute(sql)).fetchone()
        label = (await one(f"SELECT {day}"))[0]
        o = await one(
            "SELECT COUNT(*), COALESCE(SUM(price), 0), COALESCE(SUM(CASE WHEN cost IS NOT NULL THEN price END), 0), "
            "COALESCE(SUM(cost), 0), COALESCE(SUM(CASE WHEN cost IS NULL THEN 1 ELSE 0 END), 0) "
            f"FROM orders WHERE status IN ('PROCESSING', 'COMPLETED') AND {ld} = {day}")
        r = await one(f"SELECT COUNT(*), COALESCE(SUM(price), 0) FROM orders WHERE status IN ('REFUNDED', 'REJECTED') AND {ld} = {day}")
        d = await one(f"SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payments WHERE status='ACCEPTED' AND {ld} = {day}")
        dd = await one(f"SELECT COUNT(*) FROM payments WHERE status='DECLINED' AND {ld} = {day}")
        nu = await one(f"SELECT COUNT(*) FROM users WHERE {ld} = {day}")
        po = await one("SELECT COUNT(*) FROM orders WHERE status='PROCESSING'")
        pp = await one("SELECT COUNT(*) FROM payments WHERE status='UNDER_REVIEW'")
        cur = await db.execute(
            f"SELECT service_name, COUNT(*) AS c FROM orders WHERE status IN ('PROCESSING', 'COMPLETED') AND {ld} = {day} "
            "GROUP BY service_name ORDER BY c DESC LIMIT 5")
        top = await cur.fetchall()
    profit = o[2] - o[3]
    top_lines = "\n".join(f"• {esc(n)} × {c}" for n, c in top) or "—"
    note = f"\n⚠️ {o[4]} طلب بلا تكلفة مسجلة (لا تدخل في الربح)." if o[4] else ""
    return (
        f"📊 <b>تقرير يوم {label}</b>\n"
        f"────────────────────────────\n"
        f"🛒 الطلبات: <b>{o[0]:,}</b> | المبيعات: <b>{o[1]:,} ل.س</b>\n"
        f"💹 الربح (المبيعات − التكلفة): <b>{profit:,.0f} ل.س</b>{note}\n"
        f"↩️ المسترجع: <b>{r[0]:,}</b> طلب ({r[1]:,} ل.س)\n"
        f"💳 الإيداعات المقبولة: <b>{d[0]:,}</b> ({d[1]:,} ل.س) | المرفوضة: {dd[0]:,}\n"
        f"👥 مستخدمون جدد: <b>{nu[0]:,}</b>\n"
        f"────────────────────────────\n"
        f"⏳ معلّق الآن: {po[0]:,} طلب، {pp[0]:,} إيداع\n"
        f"🏆 الأكثر طلباً:\n{top_lines}"
    )


@dp.callback_query(F.data.startswith("adm:report:"))
async def adm_report(cb: types.CallbackQuery):
    if not is_admin_cb(cb):
        return
    days = int(cb.data.split(":")[2])
    text = await build_report(days)
    await safe_edit(cb, text, KB([[B("📈 اليوم", "adm:report:0"), B("📉 الأمس", "adm:report:1")], [B("🔙 رجوع", "adm:home")]]))


async def reconcile_balances() -> list:
    """أي مستخدم رصيده لا يساوي مجموع حركاته في كشف المحفظة."""
    return await fetch_all(
        "SELECT u.user_id, u.balance, COALESCE(SUM(l.amount), 0) AS led FROM users u "
        "LEFT JOIN wallet_ledger l ON l.user_id = u.user_id GROUP BY u.user_id "
        "HAVING u.balance != COALESCE(SUM(l.amount), 0)"
    )


@dp.callback_query(F.data == "adm:recon")
async def adm_reconcile(cb: types.CallbackQuery):
    if not is_admin_cb(cb):
        return
    bad = await reconcile_balances()
    if not bad:
        text = "✅ <b>المطابقة سليمة:</b> رصيد كل زبون يساوي مجموع حركاته."
    else:
        text = "🚨 <b>اختلافات في الأرصدة:</b>\n" + "\n".join(
            f"• <code>{b['user_id']}</code>: الرصيد {b['balance']:,} | مجموع الحركات {b['led']:,}" for b in bad[:20])
    await safe_edit(cb, text, KB([[B("🔄 إعادة الفحص", "adm:recon")], [B("🔙 رجوع", "adm:home")]]))


@dp.callback_query(F.data == "adm:audit")
async def adm_audit(cb: types.CallbackQuery):
    if not is_admin_cb(cb):
        return
    rows = await fetch_all("SELECT ts, staff_name, staff_id, action, ref, detail FROM staff_actions ORDER BY id DESC LIMIT 20")
    if not rows:
        text = "🧾 لا توجد إجراءات مسجلة بعد."
    else:
        text = "🧾 <b>آخر إجراءات الموظفين:</b>\n" + "\n".join(
            f"• {str(r['ts'])[5:16]} | {esc(r['staff_name'] or r['staff_id'])} | {r['action']} | <code>{esc(r['ref'])}</code>"
            + (f" | {esc(r['detail'])}" if r["detail"] else "") for r in rows)
    await safe_edit(cb, text[:4000], KB([[B("🔄 تحديث", "adm:audit")], [B("🔙 رجوع", "adm:home")]]))


@dp.callback_query(F.data == "adm:staff")
async def adm_staff(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.clear()
    rows = await fetch_all("SELECT user_id, name FROM staff ORDER BY added_at")
    kb = [[B(f"🗑 {r['name'] or r['user_id']} ({r['user_id']})", f"adm:staff_del:{r['user_id']}")] for r in rows]
    kb.append([B("➕ إضافة موظف", "adm:staff_add")])
    kb.append([B("🔙 رجوع", "adm:home")])
    await safe_edit(
        cb,
        "👮 <b>الموظفون المصرّح لهم</b>\nيستطيع تنفيذ الطلبات وقبول الإيداعات: <b>المدير</b>، وهؤلاء الموظفون، "
        "و<b>مشرفو تلغرام</b> في مجموعات الإدارة. أي عضو آخر في المجموعة لا يستطيع الضغط على الأزرار.\n"
        + ("\nلا يوجد موظفون مضافون." if not rows else ""),
        KB(kb),
    )


@dp.callback_query(F.data == "adm:staff_add")
async def adm_staff_add_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.set_state(AdminActions.add_staff)
    await safe_edit(cb, "➕ أرسل <b>آيدي الموظف</b> (رقم)، ويمكنك إضافة اسمه بعده:\nمثال: <code>123456789 أحمد</code>", cancel_kb("adm:staff"))


@dp.message(AdminActions.add_staff)
async def adm_staff_add_rec(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    parts = txt(message).split(maxsplit=1)
    uid = to_int(parts[0]) if parts else None
    if not uid:
        await message.reply("⚠️ أرسل آيدي صحيحاً بالأرقام:")
        return
    await exec_sql("INSERT OR REPLACE INTO staff (user_id, name) VALUES (?, ?)", (uid, parts[1][:60] if len(parts) > 1 else ""))
    await state.clear()
    await message.reply(f"✅ أُضيف الموظف <code>{uid}</code>.", reply_markup=KB([[B("👮 الموظفون", "adm:staff")]]))


@dp.callback_query(F.data.startswith("adm:staff_del:"))
async def adm_staff_del(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await exec_sql("DELETE FROM staff WHERE user_id=?", (int(cb.data.split(":")[2]),))
    await adm_staff(cb, state)


@dp.callback_query(F.data == "adm:margin")
async def adm_margin_menu(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.clear()
    rows = []
    for key, label in MARGIN_SECTIONS.items():
        m = await get_setting(f"margin_{key}")
        rows.append([B(f"{label}: {m:g}%", f"adm:mg:{key}")])
    rows.append([B("📊 نسبة موحدة لكل الأقسام", "adm:mgall")])
    rows.append([B("🔙 رجوع", "adm:home")])
    await safe_edit(cb, "📈 <b>نسبة الربح لكل قسم</b>\nاختر القسم لتعديل نسبته، أو عيّن نسبة موحدة للجميع:", KB(rows))


@dp.callback_query(F.data == "adm:mgall")
async def adm_margin_all_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.set_state(AdminActions.set_margin_all)
    await safe_edit(cb, "📊 أرسل نسبة الربح الموحدة % لتُطبَّق على <b>كل الأقسام</b> (مثال: 5):", cancel_kb("adm:margin"))


@dp.message(AdminActions.set_margin_all)
async def adm_margin_all_rec(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        val = float(normalize_digits(txt(message)).replace("%", "").replace(",", "."))
        if not (0 <= val <= 1000) or val != val:
            raise ValueError
    except ValueError:
        await message.reply("⚠️ أدخل رقماً بين 0 و 1000:")
        return
    for key in MARGIN_SECTIONS:
        await update_setting(f"margin_{key}", val)
    await state.clear()
    await message.reply(f"✅ تم ضبط نسبة الربح <b>{val:g}%</b> لكل الأقسام ({len(MARGIN_SECTIONS)} قسماً).")


@dp.callback_query(F.data.startswith("adm:mg:"))
async def adm_margin_pick(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    key = cb.data.split(":")[2]
    if key not in MARGIN_SECTIONS:
        return
    await state.update_data(margin_key=key)
    await state.set_state(AdminActions.set_margin)
    m = await get_setting(f"margin_{key}")
    await safe_edit(cb, f"📈 نسبة ربح <b>{MARGIN_SECTIONS[key]}</b> الحالية: <b>{m:g}%</b>\n\nأدخل النسبة الجديدة (مثال: 25):", cancel_kb("adm:margin"))


@dp.message(AdminActions.set_margin)
async def adm_margin_rec(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        val = float(txt(message).replace("%", "").replace(",", "."))
        if not (0 <= val <= 1000) or val != val:
            raise ValueError
    except ValueError:
        await message.reply("⚠️ أدخل رقماً بين 0 و 1000:")
        return
    key = (await state.get_data()).get("margin_key")
    await state.clear()
    if key not in MARGIN_SECTIONS:
        await message.reply("⚠️ انتهت الجلسة، أعد المحاولة من /admin")
        return
    await update_setting(f"margin_{key}", val)
    await message.reply(f"✅ تم ضبط نسبة ربح {MARGIN_SECTIONS[key]} على <b>{val:g}%</b>")


# ---------------- الاشتراك الإجباري ----------------
@dp.callback_query(F.data == "adm:fsub")
async def adm_fsub_menu(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.clear()
    ref = await force_channel_ref()
    title = await get_config("force_title")
    link = await get_config("force_link")
    if ref:
        text = (f"📣 <b>الاشتراك الإجباري: مفعّل</b>\n"
                f"📢 القناة: <b>{esc(str(title or ref))}</b> (<code>{esc(str(ref))}</code>)\n"
                f"🔗 الرابط: {esc(link) if link else 'غير محدد'}")
    else:
        text = "📣 <b>الاشتراك الإجباري: متوقف</b>\nلتفعيله عيّن قناة (يجب أن يكون البوت مشرفاً فيها)."
    rows = [[B("✏️ تعيين / تغيير القناة", "adm:fsub_set")]]
    if ref:
        rows.append([B("🗑 إلغاء الاشتراك الإجباري", "adm:fsub_off")])
    rows.append([B("🔙 رجوع", "adm:home")])
    await safe_edit(cb, text, KB(rows))


@dp.callback_query(F.data == "adm:fsub_set")
async def adm_fsub_set_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.set_state(AdminActions.set_channel)
    await safe_edit(
        cb,
        "✏️ أرسل معرّف القناة:\n"
        "• قناة عامة: <code>@channel_name</code>\n"
        "• قناة خاصة: الآيدي الرقمي <code>-100123456789</code> (يمكن إضافة رابط الدعوة بعده بمسافة)\n\n"
        "⚠️ <b>أضف البوت كمشرف في القناة أولاً</b> وإلا لن يستطيع فحص الاشتراك.",
        cancel_kb("adm:fsub"),
    )


@dp.message(AdminActions.set_channel)
async def adm_fsub_set_rec(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    parts = txt(message).split()
    if not parts:
        await message.reply("⚠️ أرسل معرّف القناة:")
        return
    raw = parts[0]
    link = parts[1] if len(parts) > 1 else ""
    m = re.match(r"^(?:https?://)?t\.me/([A-Za-z0-9_]{4,})/?$", raw)
    if m:
        raw = "@" + m.group(1)
    elif re.match(r"^[A-Za-z0-9_]{4,}$", raw):
        raw = "@" + raw
    ref = int(raw) if raw.lstrip("-").isdigit() else raw
    try:
        chat = await bot.get_chat(ref)
    except Exception as e:
        await message.reply(f"❌ تعذر الوصول للقناة: {esc(str(e))}\nتأكد من المعرف وأن البوت مضاف فيها، ثم أعد المحاولة:")
        return
    try:
        me = await bot.get_chat_member(chat.id, bot.id)
        bot_is_admin = me.status in ("administrator", "creator")
    except Exception:
        bot_is_admin = False
    if not link:
        if chat.username:
            link = f"https://t.me/{chat.username}"
        else:
            try:
                link = await bot.export_chat_invite_link(chat.id)
            except Exception:
                link = ""
    await set_config("force_channel", str(chat.id))
    await set_config("force_title", chat.title or "")
    await set_config("force_link", link)
    _sub_cache.clear()
    await state.clear()
    warn = "" if bot_is_admin else "\n\n⚠️ <b>البوت ليس مشرفاً في القناة</b>، لن يعمل الفحص قبل رفعه كمشرف."
    if not link:
        warn += "\n⚠️ لا يوجد رابط دعوة، أرسل الإعداد مجدداً مع الرابط بعد الآيدي."
    await message.reply(f"✅ تم تفعيل الاشتراك الإجباري على <b>{esc(chat.title or str(chat.id))}</b>.{warn}")


@dp.callback_query(F.data == "adm:fsub_off")
async def adm_fsub_off(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await set_config("force_channel", "off")
    _sub_cache.clear()
    await cb.answer("تم إلغاء الاشتراك الإجباري.", show_alert=True)
    await adm_fsub_menu(cb, state)


# ---------------- وضع الصيانة ----------------
@dp.callback_query(F.data == "adm:maint")
async def adm_maint_toggle(cb: types.CallbackQuery):
    if not is_admin_cb(cb):
        return
    on = await get_config("maintenance") == "1"
    await set_config("maintenance", "0" if on else "1")
    await cb.answer("تم إيقاف وضع الصيانة." if on else "تم تفعيل وضع الصيانة: المستخدمون محجوبون مؤقتاً.", show_alert=True)
    await show_admin_home(cb)


# ---------------- الإذاعة ----------------
@dp.callback_query(F.data == "adm:broadcast")
async def adm_broadcast_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
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
# مهام التشغيل الدورية: تذكيرات، نبض خارجي، مطابقة الأرصدة، التقرير اليومي
# =====================================================================
async def remind_stale():
    """تذكير واحد لكل طلب/إيداع تأخر دون إجراء (لا تكرار)."""
    orders = await fetch_all(
        "SELECT order_id, department, service_name FROM orders WHERE status='PROCESSING' AND reminded=0 "
        f"AND created_at < datetime('now', '-{int(STALE_ORDER_MIN)} minutes') ORDER BY created_at LIMIT 60"
    )
    by_dept: Dict[str, list] = {}
    for o in orders:
        by_dept.setdefault(o["department"], []).append(o)
    for dept, items in by_dept.items():
        lines = "\n".join(f"• <code>{i['order_id']}</code> — {esc(i['service_name'])}" for i in items[:15])
        more = f"\n… و{len(items) - 15} أخرى" if len(items) > 15 else ""
        await send_to_staff(
            GROUPS.get(dept, GROUPS["balance"]),
            f"⏰ <b>تذكير: {len(items)} طلب معلّق منذ أكثر من {STALE_ORDER_MIN} دقيقة</b>\n{lines}{more}",
        )
        for i in items:
            await exec_sql("UPDATE orders SET reminded=1 WHERE order_id=?", (i["order_id"],))
    pays = await fetch_all(
        "SELECT payment_id, user_id, amount FROM payments WHERE status='UNDER_REVIEW' AND reminded=0 "
        f"AND created_at < datetime('now', '-{int(STALE_PAYMENT_MIN)} minutes') ORDER BY created_at LIMIT 30"
    )
    if pays:
        lines = "\n".join(f"• <code>{x['payment_id']}</code> — {x['amount']:,} ل.س — <code>{x['user_id']}</code>" for x in pays[:15])
        await send_to_staff(DEPOSIT_ADMIN_GROUP, f"⏰ <b>تذكير: {len(pays)} إيداع بانتظار المراجعة منذ أكثر من {STALE_PAYMENT_MIN} دقيقة</b>\n{lines}")
        for x in pays:
            await exec_sql("UPDATE payments SET reminded=1 WHERE payment_id=?", (x["payment_id"],))


async def heartbeat():
    """نبض لمراقب خارجي مجاني (مثل healthchecks.io): إن توقف النبض ينبّهك الموقع."""
    if not HEALTHCHECK_URL:
        return
    try:
        import aiohttp
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as sess:
            async with sess.get(HEALTHCHECK_URL):
                pass
    except Exception as e:
        log.warning("heartbeat failed: %s", e)


async def scheduled_reconcile():
    bad = await reconcile_balances()
    if bad:
        lines = "\n".join(f"• <code>{b['user_id']}</code>: الرصيد {b['balance']:,} | الحركات {b['led']:,}" for b in bad[:15])
        try:
            await bot.send_message(ADMIN_ID, f"🚨 <b>اختلاف في أرصدة {len(bad)} زبون</b>\n{lines}")
        except Exception:
            pass


async def maybe_send_daily_report():
    local = time.gmtime(time.time() + TZ_OFFSET_HOURS * 3600)
    if local.tm_hour < REPORT_HOUR_LOCAL:
        return
    day = time.strftime("%Y-%m-%d", local)
    if await get_config("last_report_day") == day:
        return
    await set_config("last_report_day", day)
    try:
        await bot.send_message(ADMIN_ID, await build_report(0))
    except Exception as e:
        log.warning("daily report failed: %s", e)


async def ops_loop():
    tick = 0
    await asyncio.sleep(30)
    while True:
        try:
            await heartbeat()
            if tick % 5 == 0:
                await remind_stale()
            if tick and tick % 360 == 0:
                await scheduled_reconcile()
            await maybe_send_daily_report()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error("ops loop error: %s", e)
        tick += 1
        await asyncio.sleep(60)


_ops_task: Optional[asyncio.Task] = None


def start_ops_task():
    global _ops_task
    _ops_task = asyncio.create_task(ops_loop())

    def _done(t: asyncio.Task):
        if t.cancelled():
            return
        log.error("ops loop stopped unexpectedly: %s — restarting in 30s", t.exception())
        asyncio.get_running_loop().call_later(30, start_ops_task)

    _ops_task.add_done_callback(_done)


# =====================================================================
# النسخ الاحتياطي التلقائي إلى تلغرام (BACKUP_CHAT_ID)
# =====================================================================
_last_backup_mtime = 0.0


def _db_mtime() -> float:
    m = 0.0
    for suffix in ("", "-wal"):
        try:
            m = max(m, os.path.getmtime(DB_PATH + suffix))
        except OSError:
            pass
    return m


def _make_backup_file(dest_gz: str):
    """نسخة متسقة عبر واجهة backup في SQLite (آمنة أثناء الكتابة) + فحص سلامة + ضغط."""
    tmp = dest_gz + ".tmp.db"
    src = sqlite3.connect(DB_PATH, timeout=30)
    try:
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
            res = dst.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            dst.close()
    finally:
        src.close()
    if res != "ok":
        raise RuntimeError(f"integrity_check: {res}")
    with open(tmp, "rb") as fi, gzip.open(dest_gz, "wb", compresslevel=6) as fo:
        shutil.copyfileobj(fi, fo)
    os.remove(tmp)


def _encrypt_backup(path_gz: str) -> str:
    """تشفير النسخة بكلمة سر (Fernet + PBKDF2). يرفع ImportError إن لم تكن مكتبة cryptography مثبتة."""
    from cryptography.fernet import Fernet
    salt = os.urandom(16)
    key = base64.urlsafe_b64encode(hashlib.pbkdf2_hmac("sha256", BACKUP_PASSWORD.encode(), salt, 200_000, dklen=32))
    with open(path_gz, "rb") as f:
        token = Fernet(key).encrypt(f.read())
    out = path_gz + ".enc"
    with open(out, "wb") as f:
        f.write(b"SSB1" + salt + token)
    return out


_enc_warned = False


async def do_backup(reason: str) -> Tuple[bool, str]:
    global _last_backup_mtime
    if not BACKUP_CHAT_ID:
        return False, "BACKUP_CHAT_ID غير مضبوط"
    stamp = time.strftime("%Y-%m-%d_%H%M", time.gmtime())
    path = os.path.join(tempfile.gettempdir(), f"syria_store_{stamp}.db.gz")
    mtime = _db_mtime()
    try:
        global _enc_warned
        await asyncio.to_thread(_make_backup_file, path)
        send_path, enc_note = path, "⚠️ غير مشفّرة"
        if BACKUP_PASSWORD:
            try:
                send_path = await asyncio.to_thread(_encrypt_backup, path)
                enc_note = "🔒 مشفّرة"
            except ImportError:
                if not _enc_warned:
                    _enc_warned = True
                    try:
                        await bot.send_message(ADMIN_ID, "⚠️ BACKUP_PASSWORD مضبوط لكن مكتبة <code>cryptography</code> غير مثبتة، فالنسخ تُرسل غير مشفّرة. أضفها إلى requirements.txt.")
                    except Exception:
                        pass
        size = os.path.getsize(send_path)
        for attempt in range(3):
            try:
                await bot.send_document(
                    BACKUP_CHAT_ID, FSInputFile(send_path),
                    caption=f"💾 نسخة احتياطية {stamp} UTC ({reason}) — {size / 1024:.0f} KB — {enc_note}",
                )
                break
            except TelegramRetryAfter as e:
                if attempt == 2:
                    raise
                await asyncio.sleep(e.retry_after + 1)
        _last_backup_mtime = mtime
        return True, f"{size / 1024:.0f} KB"
    except Exception as e:
        log.error("backup failed: %s", e)
        return False, str(e)
    finally:
        for fp in (path, path + ".enc", path + ".tmp.db"):
            try:
                os.remove(fp)
            except OSError:
                pass


async def backup_loop():
    await asyncio.sleep(60)
    while True:
        try:
            if (not BACKUP_ONLY_IF_CHANGED) or _db_mtime() > _last_backup_mtime:
                ok, info = await do_backup("تلقائي")
                if not ok:
                    try:
                        await bot.send_message(ADMIN_ID, f"⚠️ فشلت النسخة الاحتياطية التلقائية: {esc(info)}")
                    except Exception:
                        pass
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error("backup loop error: %s", e)
        await asyncio.sleep(max(5, BACKUP_INTERVAL_MIN) * 60)


@dp.callback_query(F.data == "adm:backup")
async def adm_backup_now(cb: types.CallbackQuery):
    if not is_admin_cb(cb):
        return
    await cb.answer("⏳ جارٍ إنشاء النسخة...")
    ok, info = await do_backup("يدوي")
    await cb.message.answer(f"✅ أُرسلت النسخة الاحتياطية ({info})." if ok else f"❌ فشلت النسخة: {esc(info)}")


# =====================================================================
# 22. الإقلاع
# =====================================================================
_backup_task: Optional[asyncio.Task] = None


def start_backup_task():
    """يشغّل حلقة النسخ الاحتياطي ويعيد تشغيلها تلقائياً إن توقفت لأي سبب."""
    global _backup_task
    _backup_task = asyncio.create_task(backup_loop())

    def _done(t: asyncio.Task):
        if t.cancelled():
            return
        log.error("backup loop stopped unexpectedly: %s — restarting in 30s", t.exception())
        asyncio.get_running_loop().call_later(30, start_backup_task)

    _backup_task.add_done_callback(_done)


async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=False)
    log.info("🚀 Syria Store Wallet-First System is running...")
    start_backup_task()
    start_ops_task()
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if _backup_task:
            _backup_task.cancel()
        if _ops_task:
            _ops_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped.")
