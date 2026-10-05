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
import html
import json
import logging
import math
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
DEFAULT_MARGIN = float(os.getenv("DEFAULT_MARGIN", "25"))
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
        await db.execute("CREATE TABLE IF NOT EXISTS bot_config (key TEXT PRIMARY KEY, value TEXT);")

        for k, v in (("dollar_rate", DEFAULT_DOLLAR_RATE), ("num_whatsapp", 400.0), ("num_telegram", 300.0), ("margin_games", DEFAULT_MARGIN), ("margin_chat", DEFAULT_MARGIN), ("margin_accounts", DEFAULT_MARGIN), ("margin_social", DEFAULT_MARGIN), ("margin_numbers", DEFAULT_MARGIN)):
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


ENV_CONFIG = {"force_channel": "-1003772883011", "force_link": "https://t.me/Syriansto"}



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
    set_margin = State()
    find_user = State()
    msg_user = State()
    set_channel = State()
    broadcast_msg = State()


class ChatInput(StatesGroup):
    entering_data = State()


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
    rows.append([B("✅ تحققت من الاشتراك", "chk_sub")])
    text = ("📣 <b>للاستفادة من البوت يجب الاشتراك في قناتنا أولاً.</b>\n\n"
            "اشترك في القناة ثم اضغط «✅ تحققت من الاشتراك».")
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
dp.message.outer_middleware(AccessGateMiddleware())
dp.callback_query.outer_middleware(AccessGateMiddleware())
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
        [B("👤 إدارة مستخدم", "adm:user")],
        [B("➕ تغذية رصيد", "adm:add_bal"), B("➖ سحب رصيد", "adm:sub_bal")],
        [B("💱 سعر الدولار", "adm:set_rate"), B("📈 نسب الربح", "adm:margin")],
        [B("📣 الاشتراك الإجباري", "adm:fsub"), B("🛠 وضع الصيانة", "adm:maint")],
        [B("📢 إذاعة جماعية", "adm:broadcast")],
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
MARGIN_SECTIONS = {"games": "الألعاب", "chat": "تطبيقات الشات", "accounts": "الحسابات الجاهزة", "social": "السوشيال ميديا", "numbers": "أرقام التفعيل"}  # أقسام أخرى تُضاف هنا لاحقاً


async def sell_price(cost_usd: Optional[float] = None, cost_syp: Optional[float] = None, section: str = "games") -> int:
    """سعر البيع = الجملة × (1 + نسبة الربح)، مع تقريب لأعلى. الدولار يُحوَّل بسعر الصرف الحالي."""
    margin = await get_setting(f"margin_{section}")
    cost = cost_usd * await get_setting("dollar_rate") if cost_usd is not None else float(cost_syp or 0)
    return max(1, math.ceil(round(cost * (1 + margin / 100), 6)))


async def show_games_list(cb: types.CallbackQuery, page: int):
    keys = list(GAMES_CATALOG.keys())
    total = max(1, (len(keys) + GAMES_PER_PAGE - 1) // GAMES_PER_PAGE)
    page = min(max(page, 0), total - 1)
    chunk = keys[page * GAMES_PER_PAGE:(page + 1) * GAMES_PER_PAGE]
    rows = [[B(f"{GAMES_CATALOG[k]['emoji']} {GAMES_CATALOG[k]['name']}", f"gm:{k}:0")] for k in chunk]
    nav = []
    if page > 0:
        nav.append(B("⬅️ السابق", f"gl:{page - 1}"))
    if page < total - 1:
        nav.append(B("التالي ➡️", f"gl:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([B("🎮 باقي الألعاب [طلب تسعير]", "quote:game")])
    rows.append([B("🔙 العودة للرئيسية", "back_home")])
    await safe_edit(cb, f"🎮 <b>اختر اللعبة المطلوبة</b> (صفحة {page + 1} من {total}):", KB(rows))


@dp.callback_query(F.data == "sec:games")
async def games_home(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_games_list(cb, 0)


@dp.callback_query(F.data.startswith("gl:"))
async def games_page(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_games_list(cb, int(cb.data.split(":")[1]))


@dp.callback_query(F.data.startswith("gm:"))
async def game_packs_view(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    _, g_key, page_s = cb.data.split(":")
    game = GAMES_CATALOG[g_key]
    packs = game["packs"]
    total = max(1, (len(packs) + PACKS_PER_PAGE - 1) // PACKS_PER_PAGE)
    page = min(max(int(page_s), 0), total - 1)
    start = page * PACKS_PER_PAGE
    rows = []
    if page == 0 and game.get("tokens"):
        rows.append([B("🪙 شحن توكنز بالكمية", f"gtok:{g_key}")])
    for i in range(start, min(start + PACKS_PER_PAGE, len(packs))):
        label, usd = packs[i]
        price = await sell_price(cost_usd=usd)
        rows.append([B(f"{label} ⬅ {price:,} ل.س", f"gb:{g_key}:{i}")])
    nav = []
    if page > 0:
        nav.append(B("⬅️ السابق", f"gm:{g_key}:{page - 1}"))
    if page < total - 1:
        nav.append(B("التالي ➡️", f"gm:{g_key}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([B("🔙 رجوع للألعاب", "sec:games")])
    await safe_edit(cb, f"{game['emoji']} <b>{esc(game['name'])}</b>\nاختر الباقة (صفحة {page + 1} من {total}):", KB(rows))


@dp.callback_query(F.data.startswith("gb:"))
async def buy_game_pack(cb: types.CallbackQuery, state: FSMContext):
    _, g_key, idx = cb.data.split(":")
    game = GAMES_CATALOG[g_key]
    label, usd = game["packs"][int(idx)]
    price = await sell_price(cost_usd=usd)  # السعر دائماً من الخادم
    await state.clear()
    await state.update_data(g_dept="games", g_service=f"{game['name']} - {label}", g_price=price)
    await state.set_state(GlobalOrderState.input_data)
    await safe_edit(
        cb,
        f"{game['emoji']} لقد اخترت: <b>{esc(game['name'])} - {esc(label)}</b> ({price:,} ل.س)\n\n{esc(game['ask'])}",
        cancel_kb(f"gm:{g_key}:0"),
    )


@dp.callback_query(F.data.startswith("gtok:"))
async def game_tokens_start(cb: types.CallbackQuery, state: FSMContext):
    g_key = cb.data.split(":")[1]
    game = GAMES_CATALOG[g_key]
    tk = game["tokens"]
    await state.clear()
    await state.update_data(tok_game=g_key)
    await state.set_state(GameTokens.entering)
    unit = await sell_price(cost_syp=tk["unit_syp"] * 1000) / 1000
    await safe_edit(
        cb,
        f"🪙 <b>شحن توكنز {esc(game['name'])}</b>\n"
        f"الحد الأدنى: <b>{tk['min']:,}</b> توكن\n"
        f"السعر التقريبي: <b>{unit:.3f} ل.س</b> للتوكن\n\n"
        f"أرسل الآيدي ثم الكمية وبينهما مسافة:\nمثال: <code>123456 10000</code>",
        cancel_kb(f"gm:{g_key}:0"),
    )


@dp.message(GameTokens.entering)
async def game_tokens_receive(message: types.Message, state: FSMContext):
    data = await state.get_data()
    game = GAMES_CATALOG.get(data.get("tok_game", ""))
    if not game or not game.get("tokens"):
        await state.clear()
        await message.answer("⚠️ انتهت الجلسة، يرجى الاختيار من جديد.", reply_markup=HOME_KB)
        return
    tk = game["tokens"]
    parts = txt(message).split()
    qty = to_int(parts[1]) if len(parts) >= 2 else None
    if qty is None:
        await message.reply("⚠️ أرسل الآيدي ثم الكمية (رقم صحيح) وبينهما مسافة:")
        return
    if qty < tk["min"]:
        await message.reply(f"⚠️ الحد الأدنى للكمية {tk['min']:,} توكن:")
        return
    if qty > 100_000_000:
        await message.reply("⚠️ الكمية غير صالحة:")
        return
    price = await sell_price(cost_syp=qty * tk["unit_syp"])
    await process_wallet_purchase(
        message, message.from_user.id, "games", f"{game['name']} - توكنز ({qty:,})",
        f"الآيدي: {parts[0][:100]}", price, state,
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


async def chat_qty_cost(item: dict, qty: int) -> float:
    """تكلفة الجملة: الحد الأدنى بالضبط = السعر الثابت، وما فوقه = الكمية × سعر الوحدة (بحد أدنى سعر الحد الأدنى)."""
    if qty == item["min"]:
        return item["min_price"]
    return max(item["min_price"], qty * item["unit"])


async def chat_qty_price(item: dict, qty: int) -> int:
    # أسعار الشات بالكمية ثابتة بالليرة ولا تتبع سعر الدولار
    return await sell_price(cost_syp=await chat_qty_cost(item, qty), section="chat")


async def show_chat_list(cb: types.CallbackQuery, page: int):
    total = max(1, (len(CHAT_ITEMS) + CHAT_PER_PAGE - 1) // CHAT_PER_PAGE)
    page = min(max(page, 0), total - 1)
    start = page * CHAT_PER_PAGE
    buttons = [B(f"💬 {it['name']}", f"ca:{start + i}") for i, it in enumerate(CHAT_ITEMS[start:start + CHAT_PER_PAGE])]
    rows = [[B("🔍 بحث عن تطبيق بالاسم", "chat_search")]] + rows_of(buttons, 2)
    nav = []
    if page > 0:
        nav.append(B("⬅️ السابق", f"cl:{page - 1}"))
    if page < total - 1:
        nav.append(B("التالي ➡️", f"cl:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([B("🔍 تطبيق غير موجود [طلب تسعير]", "quote:chat")])
    rows.append([B("🔙 العودة للرئيسية", "back_home")])
    await safe_edit(cb, f"💬 <b>اختر تطبيق الشات المطلوب</b> (صفحة {page + 1} من {total}):", KB(rows))


@dp.callback_query(F.data == "sec:chat")
async def chat_menu(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_chat_list(cb, 0)


@dp.callback_query(F.data.startswith("cl:"))
async def chat_list_page(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_chat_list(cb, int(cb.data.split(":")[1]))


@dp.callback_query(F.data == "chat_search")
async def chat_search_start(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(ChatSearch.query)
    await safe_edit(cb, "🔍 اكتب اسم التطبيق أو جزءاً منه (مثال: <code>soul</code>):", cancel_kb("sec:chat"))


@dp.message(ChatSearch.query)
async def chat_search_receive(message: types.Message, state: FSMContext):
    q = txt(message).lower().replace(" ", "")
    if len(q) < 2:
        await message.reply("⚠️ اكتب حرفين على الأقل:")
        return
    found = [(i, it) for i, it in enumerate(CHAT_ITEMS) if q in it["name"].lower().replace(" ", "")][:12]
    if not found:
        await message.reply("لا توجد نتائج. جرّب اسماً آخر، أو اطلب تسعيراً للتطبيق:", reply_markup=KB([
            [B("🔍 طلب تسعير تطبيق", "quote:chat")], [B("🔙 قائمة التطبيقات", "sec:chat")]]))
        return
    await state.clear()
    rows = rows_of([B(f"💬 {it['name']}", f"ca:{i}") for i, it in found], 2)
    rows.append([B("🔍 بحث جديد", "chat_search"), B("🔙 القائمة", "sec:chat")])
    await message.answer(f"🔍 نتائج البحث ({len(found)}):", reply_markup=KB(rows))


@dp.callback_query(F.data.startswith("ca:"))
async def chat_app_view(cb: types.CallbackQuery, state: FSMContext):
    idx = int(cb.data.split(":")[1])
    it = CHAT_ITEMS[idx]
    back = f"cl:{idx // CHAT_PER_PAGE}"
    await state.clear()
    if it["kind"] == "qty":
        margin = await get_setting("margin_chat")
        unit_sell = it["unit"] * (1 + margin / 100)
        price_min = await chat_qty_price(it, it["min"])
        await state.update_data(c_idx=idx)
        await state.set_state(ChatInput.entering_data)
        await safe_edit(
            cb,
            f"💬 <b>{esc(it['name'])}</b>\n"
            f"────────────────────────────\n"
            f"📉 الحد الأدنى: <b>{it['min']:,}</b> = <b>{price_min:,} ل.س</b>\n"
            f"📈 ما فوق الحد الأدنى: <b>{unit_sell:.5f}</b> ل.س للوحدة\n"
            f"────────────────────────────\n"
            f"أرسل الآيدي ثم الكمية وبينهما مسافة:\nمثال: <code>123456 {it['min']}</code>",
            cancel_kb(back),
        )
    else:
        rows = []
        for pi, (label, usd) in enumerate(it["packs"]):
            price = await sell_price(cost_usd=usd, section="chat")
            rows.append([B(f"{label} ⬅ {price:,} ل.س", f"cp:{idx}:{pi}")])
        rows.append([B("🔙 رجوع", back)])
        await safe_edit(cb, f"💬 <b>{esc(it['name'])}</b>\nاختر الباقة:", KB(rows))


@dp.callback_query(F.data.startswith("cp:"))
async def chat_pack_buy(cb: types.CallbackQuery, state: FSMContext):
    _, idx_s, pi_s = cb.data.split(":")
    it = CHAT_ITEMS[int(idx_s)]
    label, usd = it["packs"][int(pi_s)]
    price = await sell_price(cost_usd=usd, section="chat")  # السعر من الخادم دائماً
    await state.clear()
    await state.update_data(g_dept="games", g_service=f"{it['name']} - {label}", g_price=price)
    await state.set_state(GlobalOrderState.input_data)
    await safe_edit(cb, f"💬 لقد اخترت: <b>{esc(it['name'])} - {esc(label)}</b> ({price:,} ل.س)\n\nأرسل آيدي اللاعب:", cancel_kb(f"ca:{idx_s}"))


@dp.message(ChatInput.entering_data)
async def proc_chat_calc_receive(message: types.Message, state: FSMContext):
    data = await state.get_data()
    idx = data.get("c_idx")
    if idx is None or not (0 <= int(idx) < len(CHAT_ITEMS)) or CHAT_ITEMS[int(idx)]["kind"] != "qty":
        await state.clear()
        await message.answer("⚠️ انتهت الجلسة، يرجى الاختيار من جديد.", reply_markup=KB([[B("💬 قائمة التطبيقات", "sec:chat")]]))
        return
    it = CHAT_ITEMS[int(idx)]
    parts = txt(message).split()
    qty = to_int(parts[1]) if len(parts) >= 2 else None
    if qty is None:
        await message.reply("⚠️ أرسل الآيدي ثم الكمية (رقم صحيح) وبينهما مسافة:")
        return
    if qty < it["min"]:
        await message.reply(f"⚠️ الحد الأدنى للكمية في {esc(it['name'])} هو {it['min']:,}:")
        return
    if qty > 10_000_000_000:
        await message.reply("⚠️ الكمية غير صالحة:")
        return
    price = await chat_qty_price(it, qty)
    await process_wallet_purchase(
        message, message.from_user.id, "games", f"{it['name']} ({qty:,})", f"الآيدي: {parts[0][:100]}", price, state
    )


# =====================================================================
# 15. الحسابات الجاهزة
# =====================================================================
async def show_accounts_list(cb: types.CallbackQuery, page: int):
    keys = list(ACCOUNTS_CATALOG.keys())
    total = max(1, (len(keys) + ACCOUNTS_PER_PAGE - 1) // ACCOUNTS_PER_PAGE)
    page = min(max(page, 0), total - 1)
    chunk = keys[page * ACCOUNTS_PER_PAGE:(page + 1) * ACCOUNTS_PER_PAGE]
    rows = rows_of([B(f"{ACCOUNTS_CATALOG[k]['emoji']} {ACCOUNTS_CATALOG[k]['name']}", f"ac:{k}") for k in chunk], 2)
    nav = []
    if page > 0:
        nav.append(B("⬅️ السابق", f"al:{page - 1}"))
    if page < total - 1:
        nav.append(B("التالي ➡️", f"al:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([B("📋 حساب غير موجود [طلب تسعير]", "quote:acc")])
    rows.append([B("🔙 العودة للرئيسية", "back_home")])
    await safe_edit(cb, f"📦 <b>اختر الحساب المطلوب</b> (صفحة {page + 1} من {total}):", KB(rows))


@dp.callback_query(F.data == "sec:accounts")
async def accounts_home(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_accounts_list(cb, 0)


@dp.callback_query(F.data.startswith("al:"))
async def accounts_page(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_accounts_list(cb, int(cb.data.split(":")[1]))


@dp.callback_query(F.data.startswith("ac:"))
async def account_view(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    key = cb.data.split(":")[1]
    acc = ACCOUNTS_CATALOG[key]
    rows = []
    for i, (label, usd) in enumerate(acc["packs"]):
        price = await sell_price(cost_usd=usd, section="accounts")
        rows.append([B(f"{label} ⬅ {price:,} ل.س", f"ab:{key}:{i}")])
    rows.append([B("🔙 رجوع للحسابات", "sec:accounts")])
    notes = f"\n\n📌 <b>ملاحظات هامة:</b>\n{esc(acc['notes'])}" if acc.get("notes") else ""
    await safe_edit(cb, f"{acc['emoji']} <b>{esc(acc['name'])}</b>\nاختر الباقة:{notes}", KB(rows))


@dp.callback_query(F.data.startswith("ab:"))
async def account_buy(cb: types.CallbackQuery, state: FSMContext):
    _, key, idx = cb.data.split(":")
    acc = ACCOUNTS_CATALOG[key]
    label, usd = acc["packs"][int(idx)]
    price = await sell_price(cost_usd=usd, section="accounts")  # السعر من الخادم دائماً
    await state.clear()
    await state.update_data(g_dept="accounts", g_service=f"{acc['name']} - {label}", g_price=price)
    await state.set_state(GlobalOrderState.input_data)
    notes = f"\n\n📌 {esc(acc['notes'])}" if acc.get("notes") else ""
    await safe_edit(
        cb,
        f"{acc['emoji']} لقد اخترت: <b>{esc(acc['name'])} - {esc(label)}</b> ({price:,} ل.س){notes}\n\n{esc(acc['ask'])}",
        cancel_kb(f"ac:{key}"),
    )


# =====================================================================
# 16. السوشيال ميديا والإعلانات
# =====================================================================
@dp.callback_query(F.data == "sec:social")
async def social_menu(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    rows = [[B(f"{emo} خدمات {name}", f"sp:{k}")] for k, (emo, name) in SOCIAL_PLATFORMS.items()]
    rows.append([B("🔙 العودة للرئيسية", "back_home")])
    await safe_edit(cb, "🚀 <b>اختر منصة السوشيال ميديا:</b>", KB(rows))


@dp.callback_query(F.data.startswith("sp:"))
async def social_platform(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    plat = cb.data.split(":")[1]
    emo, name = SOCIAL_PLATFORMS[plat]
    rows = [[B(sv["name"], f"ss:{k}")] for k, sv in SOCIAL_SERVICES.items() if sv["plat"] == plat]
    rows.append([B("🔙 رجوع", "sec:social")])
    await safe_edit(cb, f"{emo} <b>خدمات {name}:</b>\nاختر الخدمة:", KB(rows))


@dp.callback_query(F.data.startswith("ss:"))
async def social_service(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    key = cb.data.split(":")[1]
    sv = SOCIAL_SERVICES[key]
    rows = []
    for i, (label, usd) in enumerate(sv["packs"]):
        price = await sell_price(cost_usd=usd, section="social")
        rows.append([B(f"{label} ⬅ {price:,} ل.س", f"sb:{key}:{i}")])
    rows.append([B("🔙 رجوع", f"sp:{sv['plat']}")])
    await safe_edit(cb, f"🚀 <b>{esc(sv['name'])}</b>\nاختر الباقة:", KB(rows))


@dp.callback_query(F.data.startswith("sb:"))
async def social_buy(cb: types.CallbackQuery, state: FSMContext):
    _, key, idx = cb.data.split(":")
    sv = SOCIAL_SERVICES[key]
    label, usd = sv["packs"][int(idx)]
    price = await sell_price(cost_usd=usd, section="social")  # السعر من الخادم دائماً
    emo, pname = SOCIAL_PLATFORMS[sv["plat"]]
    await state.clear()
    await state.update_data(g_dept="social", g_service=f"{pname} - {sv['name']} ({label})", g_price=price)
    await state.set_state(GlobalOrderState.input_data)
    await safe_edit(
        cb,
        f"{emo} لقد اخترت: <b>{esc(sv['name'])} - {esc(label)}</b> ({price:,} ل.س)\n\n{esc(sv['ask'])}",
        cancel_kb(f"ss:{key}"),
    )


# =====================================================================
# 17. أرقام التفعيل
# =====================================================================
@dp.callback_query(F.data == "sec:numbers")
async def numbers_home(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    rows = []
    for k, n in NUMBERS_CATALOG.items():
        price = await sell_price(cost_usd=n["usd"], section="numbers")
        rows.append([B(f"{n['emoji']} {n['name']} ({price:,} ل.س)", f"nb:{k}")])
    rows.append([B("🌐 تفعيل غوغل / خدمة أخرى [طلب تسعير]", "quote:num_google")])
    rows.append([B("🔙 العودة للرئيسية", "back_home")])
    await safe_edit(cb, "📱 <b>قسم أرقام التفعيل:</b>", KB(rows))


@dp.callback_query(F.data.startswith("nb:"))
async def number_buy(cb: types.CallbackQuery, state: FSMContext):
    key = cb.data.split(":")[1]
    n = NUMBERS_CATALOG[key]
    price = await sell_price(cost_usd=n["usd"], section="numbers")  # السعر من الخادم دائماً
    await state.clear()
    await state.update_data(g_dept="social", g_service=n["name"], g_price=price)
    await state.set_state(GlobalOrderState.input_data)
    await safe_edit(cb, f"{n['emoji']} لقد اخترت: <b>{esc(n['name'])}</b> ({price:,} ل.س)\n\n{esc(n['ask'])}", cancel_kb("sec:numbers"))


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
def in_staff_group(cb: types.CallbackQuery) -> bool:
    if cb.from_user.id == ADMIN_ID:  # المدير يعمل من لوحته الخاصة أيضاً
        return True
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


@dp.callback_query(F.data.startswith("adm:o:"))
async def adm_order_card(cb: types.CallbackQuery):
    if not is_admin_cb(cb):
        return
    oid = cb.data.split(":", 2)[2]
    async with get_db() as db:
        cur = await db.execute(
            "SELECT user_id, department, service_name, target_data, price, status, created_at FROM orders WHERE order_id=?", (oid,)
        )
        o = await cur.fetchone()
    if not o:
        await cb.answer("⚠️ الطلب غير موجود.", show_alert=True)
        return
    uid, dept, service, target, price, status, created = o
    text = (
        f"📦 <b>بطاقة طلب</b>\n"
        f"🆔 <code>{oid}</code>\n"
        f"👤 الزبون: <code>{uid}</code>\n"
        f"🔑 UID: <code>{uid}</code>\n"
        f"🗂 القسم: {esc(dept)}\n"
        f"📦 الخدمة: <b>{esc(service)}</b>\n"
        f"🎯 البيانات: <code>{esc(target)}</code>\n"
        f"💰 السعر: <b>{price:,} ل.س</b>\n"
        f"📌 الحالة: <b>{status}</b>\n"
        f"🕒 {created}"
    )
    kb = KB([[B("✅ تم التنفيذ", f"ord_act:done:{oid}"), B("❌ إلغاء واسترجاع", f"ord_act:ref:{oid}")]]) if status == "PROCESSING" else None
    await cb.message.answer(text, reply_markup=kb)


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


@dp.callback_query(F.data == "adm:margin")
async def adm_margin_menu(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin_cb(cb):
        return
    await state.clear()
    rows = []
    for key, label in MARGIN_SECTIONS.items():
        m = await get_setting(f"margin_{key}")
        rows.append([B(f"{label}: {m:g}%", f"adm:mg:{key}")])
    rows.append([B("🔙 رجوع", "adm:home")])
    await safe_edit(cb, "📈 <b>نسبة الربح لكل قسم</b>\nاختر القسم لتعديل نسبته:", KB(rows))


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
