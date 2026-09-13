import os
import io
import re
import base64
import sqlite3
import logging
import tempfile
from datetime import datetime
from threading import Thread
from flask import Flask

import httpx
from PIL import Image, ImageEnhance, ImageFilter
import fitz
import edge_tts

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, PreCheckoutQueryHandler, filters,
)

# =========================
# KEEP-ALIVE SERVER FOR RENDER
# =========================
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot is running perfectly!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

keep_alive()

# =========================
# SETTINGS
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("ADMIN_TELEGRAM_ID", "8860453018")))
DATABASE = os.getenv("DATABASE", "ai_tools.db")
STARTER_STARS = 10

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_FREE_MODEL = os.getenv("OPENROUTER_FREE_MODEL", "openrouter/free")
OPENROUTER_VISION_MODEL = os.getenv("OPENROUTER_VISION_MODEL", "openrouter/free")
OPENROUTER_IMAGE_MODEL = os.getenv("OPENROUTER_IMAGE_MODEL", "")

REMOVEBG_API_KEY = os.getenv("REMOVEBG_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# =========================
# TOOLS / DEFAULT PRICES
# =========================
TOOLS = {
    "translation": "🌐 ترجمة النص",
    "text_tools": "📝 تصحيح النص",
    "ocr": "🔤 استخراج النص من صورة",
    "image_convert": "🖼️ تحويل صيغ الصور",
    "image_compress": "📦 ضغط الصور",
    "image_to_pdf": "📄 صور → PDF",
    "pdf_to_images": "🖼️ PDF → صور",
    "background_removal": "✂️ إزالة الخلفية",
    "tts": "🗣️ نص → صوت",
    "stt": "🎤 صوت → نص",
    "image_generation": "🎨 توليد الصور",
    "image_edit": "🪄 تعديل الصور بالذكاء الاصطناعي",
    "image_enhancement": "✨ تحسين الصور",
    "style_transfer": "🎭 تغيير نمط الصورة",
    "pdf_summary": "📄 تحليل/تلخيص PDF",
    "ai_assistant": "🧠 مساعد AI المتقدم",
}

DEFAULT_PRICES = {
    "translation": 0,
    "text_tools": 0,
    "ocr": 0,
    "image_convert": 0,
    "image_compress": 0,
    "image_to_pdf": 0,
    "pdf_to_images": 0,
    "background_removal": 2,
    "tts": 1,
    "stt": 1,
    "image_generation": 5,
    "image_edit": 5,
    "image_enhancement": 3,
    "style_transfer": 4,
    "pdf_summary": 3,
    "ai_assistant": 1,
}

# =========================
# DATABASE
# =========================
def db():
    c = sqlite3.connect(DATABASE, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        stars INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS usage_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        tool TEXT NOT NULL,
        stars INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS prices(tool TEXT PRIMARY KEY, price INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS tool_status(tool TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS discount(
        id INTEGER PRIMARY KEY CHECK(id=1),
        enabled INTEGER NOT NULL DEFAULT 0,
        percentage INTEGER NOT NULL DEFAULT 0
    );
    """)

    for tool, price in DEFAULT_PRICES.items():
        c.execute("INSERT OR IGNORE INTO prices(tool,price) VALUES(?,?)", (tool, price))
    c.execute("INSERT OR IGNORE INTO discount(id,enabled,percentage) VALUES(1,0,0)")
    for tool in TOOLS:
        c.execute("INSERT OR IGNORE INTO tool_status(tool,enabled) VALUES(?,1)", (tool,))
    c.commit()
    c.close()


def register_user(user):
    c = db()
    c.execute("""INSERT INTO users(user_id,username,first_name,stars,created_at)
                 VALUES(?,?,?,?,?)
                 ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    first_name=excluded.first_name""",
              (user.id, user.username, user.first_name, STARTER_STARS,
               datetime.now().isoformat(timespec="seconds")))
    c.commit()
    c.close()


def get_balance(uid):
    c = db()
    r = c.execute("SELECT stars FROM users WHERE user_id=?", (uid,)).fetchone()
    c.close()
    return int(r["stars"]) if r else 0


def change_balance(uid, amount):
    c = db()
    c.execute("UPDATE users SET stars=stars+? WHERE user_id=?", (amount, uid))
    c.commit()
    c.close()


def get_discount():
    c = db()
    r = c.execute("SELECT enabled,percentage FROM discount WHERE id=1").fetchone()
    c.close()
    return bool(r["enabled"]), int(r["percentage"])


def get_price(tool):
    c = db()
    r = c.execute("SELECT price FROM prices WHERE tool=?", (tool,)).fetchone()
    c.close()
    base = int(r["price"]) if r else 0
    enabled, percentage = get_discount()
    if base <= 0:
        return 0
    return max(0, round(base * (100 - percentage) / 100)) if enabled else base


def set_price(tool, price):
    c = db()
    c.execute("""INSERT INTO prices(tool,price) VALUES(?,?)
                 ON CONFLICT(tool) DO UPDATE SET price=excluded.price""",
              (tool, max(0, int(price))))
    c.commit()
    c.close()


def is_enabled(tool):
    c = db()
    r = c.execute("SELECT enabled FROM tool_status WHERE tool=?", (tool,)).fetchone()
    c.close()
    return bool(r["enabled"]) if r else False


def set_enabled(tool, enabled):
    c = db()
    c.execute("UPDATE tool_status SET enabled=? WHERE tool=?", (int(enabled), tool))
    c.commit()
    c.close()


def log_usage(uid, tool, stars, status):
    c = db()
    c.execute("INSERT INTO usage_logs(user_id,tool,stars,status,created_at) VALUES(?,?,?,?,?)",
              (uid, tool, stars, status, datetime.now().isoformat(timespec="seconds")))
    c.commit()
    c.close()

# =========================
# KEYBOARDS
# =========================
def grid_buttons(items, prefix, columns=2):
    rows = []
    row = []
    for key, label in items:
        row.append(InlineKeyboardButton(label, callback_data=f"{prefix}:{key}"))
        if len(row) == columns:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def home_kb():
    rows = [
        [InlineKeyboardButton("🆓 الأدوات المجانية", callback_data="free")],
        [InlineKeyboardButton("⭐ الأدوات بالنقاط", callback_data="stars")],
        [InlineKeyboardButton("🤖 أدوات الذكاء الاصطناعي", callback_data="ai")],
        [InlineKeyboardButton("⭐ رصيدي", callback_data="balance"),
         InlineKeyboardButton("💳 الباقات", callback_data="plans")],
    ]
    return InlineKeyboardMarkup(rows)


def back_home():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الرئيسية", callback_data="home")]])


def free_kb():
    items = [(k, v) for k, v in TOOLS.items() if get_price(k) == 0 and is_enabled(k)]
    rows = grid_buttons(items, "free")
    rows.append([InlineKeyboardButton("🔙 الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(rows)


def stars_kb():
    items = [(k, f"{v} — ⭐{get_price(k)}") for k, v in TOOLS.items()
             if get_price(k) > 0 and is_enabled(k)]
    rows = grid_buttons(items, "pro")
    rows.append([InlineKeyboardButton("🔙 الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(rows)


def ai_kb():
    ai_keys = ["image_generation", "image_edit", "image_enhancement", "style_transfer", "pdf_summary", "ai_assistant"]
    items = []
    for k in ai_keys:
        if is_enabled(k):
            price = get_price(k)
            label = TOOLS[k] if price == 0 else f"{TOOLS[k]} — ⭐{price}"
            items.append((k, label))
    rows = grid_buttons(items, "pro")
    rows.append([InlineKeyboardButton("🔙 الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(rows)


def plans_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ شراء 100 Stars", callback_data="buy:100"),
         InlineKeyboardButton("⭐ شراء 500 Stars", callback_data="buy:500")],
        [InlineKeyboardButton("⭐ شراء 1000 Stars", callback_data="buy:1000")],
        [InlineKeyboardButton("🔙 الرئيسية", callback_data="home")],
    ])

# =========================
# OPENROUTER HELPERS
# =========================
def or_headers():
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://telegram.org",
        "X-Title": "AI Tools Telegram Bot",
    }


async def openrouter_chat(prompt, system="أنت مساعد مفيد داخل بوت Telegram.", vision_image_bytes=None, model=None):
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY غير موجود في المتغيرات البيئية")

    content = [{"type": "text", "text": prompt}]
    if vision_image_bytes is not None:
        mime = "image/jpeg"
        try:
            im = Image.open(io.BytesIO(vision_image_bytes))
            mime = Image.MIME.get(im.format, "image/jpeg")
        except Exception:
            pass
        b64 = base64.b64encode(vision_image_bytes).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})

    payload = {
        "model": model or (OPENROUTER_VISION_MODEL if vision_image_bytes else OPENROUTER_FREE_MODEL),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        "temperature": 0.2,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{OPENROUTER_BASE_URL}/chat/completions", headers=or_headers(), json=payload)
        if r.status_code >= 400:
            raise RuntimeError(f"OpenRouter {r.status_code}: {r.text[:500]}")
        data = r.json()
    text = data["choices"][0]["message"].get("content", "")
    if isinstance(text, list):
        text = "".join(x.get("text", "") for x in text if isinstance(x, dict))
    if not str(text).strip():
        raise RuntimeError("OpenRouter returned empty response")
    return str(text).strip()


async def ocr_image(image_bytes):
    return await openrouter_chat(
        "استخرج كل النص الظاهر في الصورة حرفيًا قدر الإمكان. لا تشرح ولا تلخص. حافظ على ترتيب الأسطر واللغة العربية.",
        system="أنت OCR دقيق. أعد النص فقط.",
        vision_image_bytes=image_bytes,
    )


async def translate_text(text, target):
    language = {"en": "English", "ar": "Arabic", "fr": "French", "tr": "Turkish", "de": "German"}.get(target, target)
    return await openrouter_chat(
        f"Translate the following text to {language}. Return only the translation and preserve formatting.\n\n{text}",
        system="You are a professional translator."
    )

# =========================
# IMAGE / FILE HELPERS
# =========================
async def remove_background(image_bytes):
    if not REMOVEBG_API_KEY:
        raise RuntimeError("إزالة الخلفية تحتاج REMOVEBG_API_KEY")
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            "https://api.remove.bg/v1.0/removebg",
            headers={"X-Api-Key": REMOVEBG_API_KEY},
            files={"image_file": ("image.png", image_bytes, "image/png")},
            data={"size": "auto"},
        )
        if r.status_code != 200:
            raise RuntimeError(f"remove.bg {r.status_code}: {r.text[:300]}")
        return r.content


def local_image(image_bytes, operation):
    image = Image.open(io.BytesIO(image_bytes))
    if operation == "compress":
        image.thumbnail((2000, 2000))
        out = io.BytesIO()
        image.convert("RGB").save(out, "JPEG", quality=65, optimize=True)
        return out.getvalue(), "compressed.jpg"
    if operation == "convert":
        out = io.BytesIO()
        image.convert("RGBA").save(out, "PNG", optimize=True)
        return out.getvalue(), "converted.png"
    if operation == "enhance":
        image = ImageEnhance.Sharpness(image).enhance(1.8)
        image = ImageEnhance.Contrast(image).enhance(1.15)
        image = ImageEnhance.Color(image).enhance(1.1)
        image = image.filter(ImageFilter.UnsharpMask(radius=1, percent=120))
        out = io.BytesIO()
        image.convert("RGB").save(out, "JPEG", quality=95)
        return out.getvalue(), "enhanced.jpg"
    raise ValueError("unknown operation")


def images_to_pdf(image_bytes_list):
    images = []
    for b in image_bytes_list:
        images.append(Image.open(io.BytesIO(b)).convert("RGB"))
    out = io.BytesIO()
    if images:
        images[0].save(out, "PDF", save_all=True, append_images=images[1:])
    return out.getvalue()

# =========================
# OPENAI PREMIUM HELPERS
# =========================
async def openai_image_generate(prompt):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY غير موجود. توليد الصور يحتاج مفتاح OpenAI.")
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    result = await client.images.generate(
        model=os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3"),
        prompt=prompt,
        size="1024x1024",
        response_format="b64_json"
    )
    return base64.b64decode(result.data[0].b64_json)


async def openai_edit_image(image_bytes, prompt):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY غير موجود. تعديل الصور يحتاج مفتاح OpenAI.")
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    f.write(image_bytes)
    f.close()
    try:
        with open(f.name, "rb") as img:
            result = await client.images.edit(
                model=os.getenv("OPENAI_IMAGE_MODEL", "dall-e-2"),
                image=img,
                prompt=prompt,
                size="1024x1024",
                response_format="b64_json"
            )
        return base64.b64decode(result.data[0].b64_json)
    finally:
        try:
            os.unlink(f.name)
        except OSError:
            pass


async def openai_transcribe(audio_bytes, filename="voice.ogg"):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY غير موجود. تحويل الصوت إلى نص يحتاج مفتاح OpenAI.")
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    f = tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1] or ".ogg", delete=False)
    f.write(audio_bytes)
    f.close()
    try:
        with open(f.name, "rb") as audio:
            r = await client.audio.transcriptions.create(
                model=os.getenv("OPENAI_STT_MODEL", "whisper-1"),
                file=audio,
            )
        return r.text.strip()
    finally:
        try:
            os.unlink(f.name)
        except OSError:
            pass


async def text_to_speech(text):
    f = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    f.close()
    try:
        await edge_tts.Communicate(text, "ar-SA-HamedNeural").save(f.name)
        with open(f.name, "rb") as x:
            return x.read()
    finally:
        try:
            os.unlink(f.name)
        except OSError:
            pass

# =========================
# CREDITS
# =========================
async def require_credits(update, tool):
    if update.effective_user.id == OWNER_ID:
        return True
    price = get_price(tool)
    if price <= 0:
        return True
    balance = get_balance(update.effective_user.id)
    if balance < price:
        await update.effective_message.reply_text(
            f"❌ رصيدك غير كافٍ.\n\nالسعر: ⭐{price}\nرصيدك: ⭐{balance}\n\nيمكنك شراء Stars من الباقات.",
            reply_markup=plans_kb(),
        )
        return False
    return True


def charge_after_success(uid, tool):
    if uid == OWNER_ID:
        return 0
    p = get_price(tool)
    if p > 0:
        change_balance(uid, -p)
        log_usage(uid, tool, p, "success")
    return p

# =========================
# COMMANDS / MENUS
# =========================
async def start(update, context):
    register_user(update.effective_user)
    await update.message.reply_text(
        "👋 أهلاً بك في AI TOOLS!\n\nاختر ما تريد:",
        reply_markup=home_kb(),
    )


async def admin(update, context):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ غير مصرح.")
        return
    await update.message.reply_text(
        "👑 لوحة المالك\n\nتقدر من هنا تتحكم بالأسعار والحالة والخصومات والرصيد.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 الأسعار", callback_data="admin:prices")],
            [InlineKeyboardButton("🛠️ تشغيل / إيقاف الأدوات", callback_data="admin:tools")],
            [InlineKeyboardButton("🎁 الخصومات", callback_data="admin:discount")],
            [InlineKeyboardButton("⭐ تعديل رصيد", callback_data="admin:balance")],
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin:stats")],
            [InlineKeyboardButton("🔙 الرئيسية", callback_data="home")],
        ]),
    )

# =========================
# CALLBACKS
# =========================
async def callbacks(update, context):
    q = update.callback_query
    await q.answer()
    register_user(q.from_user)
    data = q.data

    if data == "home":
        context.user_data.clear()
        await q.edit_message_text("🤖 AI TOOLS\n\nاختر ما تريد:", reply_markup=home_kb())
        return

    if data == "free":
        await q.edit_message_text("🆓 الأدوات المجانية\n\nيمكن للمالك نقل أي أداة إلى هنا بجعل سعرها ⭐0.", reply_markup=free_kb())
        return

    if data == "stars":
        await q.edit_message_text("⭐ الأدوات بالنقاط\n\nتُخصم النقاط بعد نجاح العملية فقط.", reply_markup=stars_kb())
        return

    if data == "ai":
        await q.edit_message_text("🤖 أدوات الذكاء الاصطناعي", reply_markup=ai_kb())
        return

    if data == "balance":
        await q.edit_message_text(
            f"⭐ رصيدك الحالي: {get_balance(q.from_user.id)} Stars",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 شراء Stars", callback_data="plans")],
                [InlineKeyboardButton("🔙 الرئيسية", callback_data="home")],
            ]),
        )
        return

    if data == "plans":
        await q.edit_message_text("💳 اختر باقة Stars التي تريد شراءها:", reply_markup=plans_kb())
        return

    if data.startswith("buy:"):
        amount = int(data.split(":")[1])
        await context.bot.send_invoice(
            chat_id=q.message.chat_id,
            title=f"{amount} Stars",
            description=f"إضافة {amount} Stars إلى رصيدك داخل البوت",
            payload=f"stars:{amount}:{q.from_user.id}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(f"{amount} Telegram Stars", amount)],
        )
        return

    if data.startswith("free:") or data.startswith("pro:"):
        tool = data.split(":", 1)[1]
        if tool not in TOOLS:
            await q.edit_message_text("❌ أداة غير معروفة.", reply_markup=home_kb())
            return
        if not is_enabled(tool):
            await q.edit_message_text("⏸️ الأداة متوقفة مؤقتًا.", reply_markup=back_home())
            return
        if not await require_credits(q, tool):
            return

        context.user_data["pending_tool"] = tool
        prompts = {
            "background_removal": "✂️ أرسل صورة لإزالة الخلفية.",
            "ocr": "🔤 أرسل صورة لاستخراج النص.",
            "image_convert": "🖼️ أرسل صورة لتحويلها إلى PNG.",
            "image_compress": "📦 أرسل صورة لضغطها.",
            "image_to_pdf": "📄 أرسل صورة أو أكثر، وسأجمعها في PDF.",
            "pdf_to_images": "🖼️ أرسل ملف PDF.",
            "translation": "🌐 أرسل مثل: ترجم إلى الإنجليزية: مرحبًا بالعالم",
            "text_tools": "📝 أرسل النص لتصحيحه وترتيبه.",
            "tts": "🗣️ أرسل النص لتحويله إلى صوت. هذه الأداة بالنقاط.",
            "stt": "🎤 أرسل رسالة صوتية أو ملف صوت. هذه الأداة بالنقاط.",
            "image_generation": "🎨 أرسل وصف الصورة.",
            "image_edit": "🪄 أرسل الصورة، ثم وصف التعديل.",
            "image_enhancement": "✨ أرسل الصورة لتحسينها.",
            "style_transfer": "🎭 أرسل الصورة، ثم وصف النمط.",
            "pdf_summary": "📄 أرسل ملف PDF لتحليله وتلخيصه.",
            "ai_assistant": "🧠 أرسل سؤالك.",
        }
        price = get_price(tool)
        label = "مجاني" if price == 0 else f"⭐{price}"
        await q.edit_message_text(f"{prompts[tool]}\n\n💳 التكلفة: {label}", reply_markup=back_home())
        return

    if data.startswith("admin:") and q.from_user.id == OWNER_ID:
        action = data.split(":", 1)[1]
        if action == "prices":
            rows = []
            items = list(TOOLS.items())
            for i in range(0, len(items), 2):
                row = []
                for t, name in items[i:i + 2]:
                    row.append(InlineKeyboardButton(f"{name} · ⭐{get_price(t)}", callback_data=f"setprice:{t}"))
                rows.append(row)
            rows.append([InlineKeyboardButton("🔙 لوحة المالك", callback_data="admin")])
            await q.edit_message_text("💰 الأسعار\n\nاجعل السعر 0 لإرجاع الأداة مجانية.", reply_markup=InlineKeyboardMarkup(rows))
            return

        if action == "tools":
            rows = []
            items = list(TOOLS.items())
            for i in range(0, len(items), 2):
                row = []
                for t, name in items[i:i + 2]:
                    state = "🟢" if is_enabled(t) else "🔴"
                    row.append(InlineKeyboardButton(f"{state} {name}", callback_data=f"toggle:{t}"))
                rows.append(row)
            rows.append([InlineKeyboardButton("🔙 لوحة المالك", callback_data="admin")])
            await q.edit_message_text("🛠️ تشغيل / إيقاف الأدوات\n\nاضغط الأداة لتبديل حالتها.", reply_markup=InlineKeyboardMarkup(rows))
            return

        if action == "stats":
            c = db()
            users = c.execute("SELECT COUNT(*) x FROM users").fetchone()["x"]
            ops = c.execute("SELECT COUNT(*) x FROM usage_logs").fetchone()["x"]
            spent = c.execute("SELECT COALESCE(SUM(stars),0) x FROM usage_logs WHERE status='success'").fetchone()["x"]
            c.close()
            await q.edit_message_text(
                f"📊 الإحصائيات\n\n👤 المستخدمون: {users}\n📌 العمليات الناجحة: {ops}\n⭐ Stars المستخدمة: {spent}",
                reply_markup=back_home(),
            )
            return

        if action == "balance":
            context.user_data["admin_action"] = "balance"
            await q.edit_message_text("⭐ أرسل بهذا الشكل:\nUserID amount\n\nمثال: 123456789 20")
            return

        if action == "discount":
            enabled, percentage = get_discount()
            state = f"🟢 خصم {percentage}% فعال" if enabled else "🔴 لا يوجد خصم فعال"
            await q.edit_message_text(
                f"🎁 الخصومات\n\nالحالة: {state}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ إضافة / تغيير الخصم", callback_data="discount:set")],
                    [InlineKeyboardButton("❌ إزالة الخصم", callback_data="discount:off")],
                    [InlineKeyboardButton("🔙 لوحة المالك", callback_data="admin")],
                ]),
            )
            return

    if data == "admin" and q.from_user.id == OWNER_ID:
        await admin(update, context)
        return

    if data == "discount:set" and q.from_user.id == OWNER_ID:
        context.user_data["admin_action"] = "discount"
        await q.edit_message_text("🎁 أرسل نسبة الخصم من 0 إلى 100.\n\nمثال: 20")
        return

    if data == "discount:off" and q.from_user.id == OWNER_ID:
        c = db()
        c.execute("UPDATE discount SET enabled=0,percentage=0 WHERE id=1")
        c.commit()
        c.close()
        await q.edit_message_text("✅ تم إزالة الخصم.", reply_markup=back_home())
        return

    if data.startswith("toggle:") and q.from_user.id == OWNER_ID:
        t = data.split(":", 1)[1]
        if t in TOOLS:
            set_enabled(t, not is_enabled(t))
        await q.edit_message_text("✅ تم تحديث حالة الأداة.", reply_markup=back_home())
        return

    if data.startswith("setprice:") and q.from_user.id == OWNER_ID:
        t = data.split(":", 1)[1]
        if t not in TOOLS:
            return
        context.user_data["admin_action"] = "price"
        context.user_data["price_tool"] = t
        await q.edit_message_text(
            f"💰 السعر الحالي لـ {TOOLS[t]}: ⭐{get_price(t)}\n\nأرسل السعر الجديد.\nاكتب 0 لجعلها مجانية."
        )
        return

# =========================
# PAYMENTS
# =========================
async def precheckout(update, context):
    await update.pre_checkout_query.answer(ok=True)


async def successful_payment(update, context):
    p = update.message.successful_payment
    if not p.invoice_payload.startswith("stars:"):
        return
    _, amount, target = p.invoice_payload.split(":")
    amount = int(amount)
    target = int(target)
    if target != update.effective_user.id:
        return
    change_balance(target, amount)
    log_usage(target, "telegram_stars_purchase", -amount, "purchase")
    await update.message.reply_text(
        f"✅ تم الدفع!\n➕ ⭐{amount}\n⭐ رصيدك الآن: {get_balance(target)}",
        reply_markup=home_kb(),
    )

# =========================
# TEXT
# =========================
async def text_handler(update, context):
    user = update.effective_user
    register_user(user)
    text = (update.message.text or "").strip()

    if user.id == OWNER_ID and context.user_data.get("admin_action"):
        action = context.user_data["admin_action"]
        if action == "price":
            try:
                value = int(text)
                if value < 0:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("❌ أرسل رقمًا صحيحًا، أو 0 لجعل الأداة مجانية.")
                return
            tool = context.user_data.get("price_tool")
            if tool in TOOLS:
                set_price(tool, value)
            context.user_data.clear()
            await update.message.reply_text("✅ تم تحديث السعر.", reply_markup=home_kb())
            return

        if action == "balance":
            try:
                target, amount = map(int, text.split())
            except Exception:
                await update.message.reply_text("❌ استخدم: UserID amount")
                return
            change_balance(target, amount)
            context.user_data.clear()
            await update.message.reply_text(f"✅ الرصيد الآن: ⭐{get_balance(target)}", reply_markup=home_kb())
            return

        if action == "discount":
            try:
                percentage = int(text)
                if not 0 <= percentage <= 100:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("❌ أرسل نسبة من 0 إلى 100.")
                return
            c = db()
            if percentage == 0:
                c.execute("UPDATE discount SET enabled=0,percentage=0 WHERE id=1")
            else:
                c.execute("UPDATE discount SET enabled=1,percentage=? WHERE id=1", (percentage,))
            c.commit()
            c.close()
            context.user_data.clear()
            await update.message.reply_text("✅ تم تحديث الخصم.", reply_markup=home_kb())
            return

    tool = context.user_data.get("pending_tool")
    if not tool:
        return

    try:
        if tool == "translation":
            m = re.match(r"ترجم(?:\s+إلى)?\s+([\w\u0600-\u06FF]+)\s*:\s*(.+)", text, re.S | re.I)
            if not m:
                await update.message.reply_text("مثال: ترجم إلى الإنجليزية: مرحبًا")
                return
            target_name = m.group(1).lower()
            target = {
                "الإنجليزية": "en", "انجليزية": "en", "english": "en",
                "العربية": "ar", "عربي": "ar", "العربيه": "ar",
                "الفرنسية": "fr", "التركية": "tr", "الألمانية": "de",
            }.get(target_name, target_name)
            result = await translate_text(m.group(2), target)
            context.user_data.clear()
            await update.message.reply_text("🌐 الترجمة:\n\n" + result, reply_markup=home_kb())
            return

        if tool == "text_tools":
            result = await openrouter_chat(
                "صحح النص التالي لغويًا ورتبه مع الحفاظ على المعنى. أعد النص المصحح فقط:\n\n" + text,
                system="أنت مدقق لغوي عربي محترف.",
            )
            context.user_data.clear()
            await update.message.reply_text("📝 النص المصحح:\n\n" + result, reply_markup=home_kb())
            return

        if tool == "tts":
            if not await require_credits(update, tool):
                return
            audio = await text_to_speech(text)
            p = charge_after_success(user.id, tool)
            context.user_data.clear()
            await update.message.reply_audio(
                audio=io.BytesIO(audio),
                caption=f"🗣️ تم تحويل النص إلى صوت.\n⭐ تم الخصم: {p}",
                reply_markup=home_kb(),
            )
            return

        if tool == "ai_assistant":
            if not await require_credits(update, tool):
                return
            result = await openrouter_chat(text, system="أنت مساعد AI متقدم. أجب بالعربية ما لم يطلب المستخدم غير ذلك.")
            p = charge_after_success(user.id, tool)
            context.user_data.clear()
            await update.message.reply_text(f"🧠 {result}\n\n⭐ تم الخصم: {p}", reply_markup=home_kb())
            return

        if tool == "image_generation":
            if not await require_credits(update, tool):
                return
            if not OPENROUTER_IMAGE_MODEL and not OPENAI_API_KEY:
                raise RuntimeError("توليد الصور يحتاج مزود صور، مثل OPENAI_API_KEY")
            if OPENAI_API_KEY:
                image = await openai_image_generate(text)
            else:
                raise RuntimeError("OPENROUTER_IMAGE_MODEL غير مدعوم في هذا الإصدار")
            p = charge_after_success(user.id, tool)
            context.user_data.clear()
            await update.message.reply_photo(photo=io.BytesIO(image), caption=f"🎨 تم التوليد. ⭐{p}", reply_markup=home_kb())
            return

        if tool in {"style_transfer", "image_edit"}:
            context.user_data["edit_prompt"] = text
            context.user_data["waiting_edit_image"] = True
            await update.message.reply_text("📷 أرسل الصورة الآن.", reply_markup=back_home())
            return

    except Exception as e:
        logger.exception("text tool failed")
        log_usage(user.id, tool, 0, "failed")
        context.user_data.clear()
        await update.message.reply_text(f"❌ فشلت العملية ولم يتم الخصم.\n\n{str(e)[:300]}", reply_markup=home_kb())

# =========================
# PHOTO
# =========================
async def photo_handler(update, context):
    user = update.effective_user
    register_user(user)
    tool = context.user_data.get("pending_tool")
    if not tool:
        await update.message.reply_text("اختر أداة أولًا.", reply_markup=home_kb())
        return

    f = await update.message.photo[-1].get_file()
    data = bytes(await f.download_as_bytearray())

    try:
        if tool == "background_removal":
            if not await require_credits(update, tool):
                return
            result = await remove_background(data)
            p = charge_after_success(user.id, tool)
            context.user_data.clear()
            await update.message.reply_document(io.BytesIO(result), filename="no-background.png", caption=f"✂️ تم حذف الخلفية.\n⭐ تم الخصم: {p}", reply_markup=home_kb())
            return

        if tool == "ocr":
            result = await ocr_image(data)
            context.user_data.clear()
            await update.message.reply_text("🔤 النص المستخرج:\n\n" + result, reply_markup=home_kb())
            return

        if tool == "image_convert":
            result, name = local_image(data, "convert")
            context.user_data.clear()
            await update.message.reply_document(io.BytesIO(result), filename=name, caption="🖼️ تم التحويل.", reply_markup=home_kb())
            return

        if tool == "image_compress":
            result, name = local_image(data, "compress")
            context.user_data.clear()
            await update.message.reply_document(io.BytesIO(result), filename=name, caption="📦 تم الضغط.", reply_markup=home_kb())
            return

        if tool == "image_to_pdf":
            result = images_to_pdf([data])
            context.user_data.clear()
            await update.message.reply_document(io.BytesIO(result), filename="images.pdf", caption="📄 تم إنشاء PDF.", reply_markup=home_kb())
            return

        if tool == "image_enhancement":
            if not await require_credits(update, tool):
                return
            result, name = local_image(data, "enhance")
            p = charge_after_success(user.id, tool)
            context.user_data.clear()
            await update.message.reply_document(io.BytesIO(result), filename=name, caption=f"✨ تم تحسين الصورة.\n⭐ تم الخصم: {p}", reply_markup=home_kb())
            return

        if tool in {"image_edit", "style_transfer"}:
            if not await require_credits(update, tool):
                return
            prompt = context.user_data.get("edit_prompt")
            if not prompt:
                context.user_data["edit_image_bytes"] = data
                context.user_data["waiting_edit_prompt"] = True
                await update.message.reply_text("🪄 أرسل وصف التعديل الآن.", reply_markup=back_home())
                return
            result = await openai_edit_image(data, prompt)
            p = charge_after_success(user.id, tool)
            context.user_data.clear()
            await update.message.reply_photo(photo=io.BytesIO(result), caption=f"🪄 تم التعديل.\n⭐ تم الخصم: {p}", reply_markup=home_kb())
            return

    except Exception as e:
        logger.exception("photo failed")
        log_usage(user.id, tool, 0, "failed")
        context.user_data.clear()
        await update.message.reply_text(f"❌ فشلت العملية ولم يتم الخصم.\n\n{str(e)[:300]}", reply_markup=home_kb())

# =========================
# DOCUMENT / VOICE
# =========================
async def document_handler(update, context):
    user = update.effective_user
    register_user(user)
    tool = context.user_data.get("pending_tool")
    if not tool:
        await update.message.reply_text("اختر أداة أولًا.", reply_markup=home_kb())
        return

    f = await update.message.document.get_file()
    data = bytes(await f.download_as_bytearray())

    try:
        if tool == "pdf_to_images":
            pdf = fitz.open(stream=data, filetype="pdf")
            for i, page in enumerate(pdf):
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                await update.message.reply_document(io.BytesIO(pix.tobytes("png")), filename=f"page-{i+1}.png")
            pdf.close()
            context.user_data.clear()
            await update.message.reply_text("🖼️ تم استخراج الصفحات.", reply_markup=home_kb())
            return

        if tool == "pdf_summary":
            if not await require_credits(update, tool):
                return
            pdf = fitz.open(stream=data, filetype="pdf")
            text = "\n".join(p.get_text() for p in pdf)[:60000]
            pdf.close()
            result = await openrouter_chat("لخص هذا PDF بالعربية واستخرج أهم النقاط والعناوين:\n\n" + text, system="أنت محلل مستندات محترف.")
            p = charge_after_success(user.id, tool)
            context.user_data.clear()
            await update.message.reply_text(f"📄 الملخص:\n\n{result}\n\n⭐ تم الخصم: {p}", reply_markup=home_kb())
            return

        if tool == "stt":
            if not await require_credits(update, tool):
                return
            result = await openai_transcribe(data, update.message.document.file_name or "audio.ogg")
            p = charge_after_success(user.id, tool)
            context.user_data.clear()
            await update.message.reply_text(f"🎤 النص:\n\n{result}\n\n⭐ تم الخصم: {p}", reply_markup=home_kb())
            return

    except Exception as e:
        logger.exception("document failed")
        log_usage(user.id, tool, 0, "failed")
        context.user_data.clear()
        await update.message.reply_text(f"❌ فشلت العملية ولم يتم الخصم.\n\n{str(e)[:300]}", reply_markup=home_kb())


async def voice_handler(update, context):
    user = update.effective_user
    register_user(user)
    tool = context.user_data.get("pending_tool")
    if tool != "stt":
        await update.message.reply_text("اختر 🎤 صوت → نص أولًا.", reply_markup=home_kb())
        return
    if not await require_credits(update, tool):
        return
    try:
        f = await update.message.voice.get_file()
        data = bytes(await f.download_as_bytearray())
        result = await openai_transcribe(data, "voice.ogg")
        p = charge_after_success(user.id, tool)
        context.user_data.clear()
        await update.message.reply_text(f"🎤 النص:\n\n{result}\n\n⭐ تم الخصم: {p}", reply_markup=home_kb())
    except Exception as e:
        logger.exception("voice failed")
        log_usage(user.id, tool, 0, "failed")
        context.user_data.clear()
        await update.message.reply_text(f"❌ فشل التحويل ولم يتم الخصم.\n\n{str(e)[:300]}", reply_markup=home_kb())

# =========================
# ERROR / MAIN
# =========================
async def error_handler(update, context):
    logger.exception("Unhandled error", exc_info=context.error)


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)
    logger.info("AI TOOLS BOT running")
    app.run_polling()


if __name__ == "__main__":
    main()
import fitz
import edge_tts

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, PreCheckoutQueryHandler, filters,
)

# =========================
# SETTINGS
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("ADMIN_TELEGRAM_ID", "8860453018")))
DATABASE = os.getenv("DATABASE", "ai_tools.db")

# OpenRouter: ONE key for free text/vision models.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_FREE_MODEL = os.getenv("OPENROUTER_FREE_MODEL", "openrouter/free")
# Vision-capable free model can be changed from Render without editing code.
OPENROUTER_VISION_MODEL = os.getenv("OPENROUTER_VISION_MODEL", "openrouter/free")
# Image generation is NOT currently free on OpenRouter; keep disabled unless credits exist.
OPENROUTER_IMAGE_MODEL = os.getenv("OPENROUTER_IMAGE_MODEL", "")

# Optional separate services.
REMOVEBG_API_KEY = os.getenv("REMOVEBG_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # optional: paid OpenAI image/STT

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# =========================
# TOOLS / PRICES
# =========================
FREE_TOOLS = {
    "background_removal": "✂️ إزالة الخلفية",
    "ocr": "🔤 استخراج النص من صورة",
    "image_convert": "🖼️ تحويل صيغ الصور",
    "image_compress": "📦 ضغط الصور",
    "image_to_pdf": "📄 صور → PDF",
    "pdf_to_images": "🖼️ PDF → صور",
    "translation": "🌐 ترجمة النص",
    "text_tools": "📝 تصحيح النص",
    "tts": "🗣️ نص → صوت",
}

PRO_TOOLS = {
    "image_generation": "🎨 توليد الصور",
    "image_edit": "🪄 تعديل الصور بالذكاء الاصطناعي",
    "image_enhancement": "✨ تحسين الصور",
    "style_transfer": "🎭 تغيير نمط الصورة",
    "stt": "🎤 صوت → نص",
    "pdf_summary": "📄 تحليل/تلخيص PDF",
    "ai_assistant": "🧠 مساعد AI المتقدم",
}

ALL_TOOLS = {**FREE_TOOLS, **PRO_TOOLS}
DEFAULT_PRICES = {
    "image_generation": 5,
    "image_edit": 5,
    "image_enhancement": 3,
    "style_transfer": 4,
    "stt": 1,
    "pdf_summary": 3,
    "ai_assistant": 1,
}

# =========================
# DATABASE
# =========================
def db():
    c = sqlite3.connect(DATABASE, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        stars INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS usage_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        tool TEXT NOT NULL,
        stars INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS prices(tool TEXT PRIMARY KEY, price INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS tool_status(tool TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS discount(id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL DEFAULT 0, percentage INTEGER NOT NULL DEFAULT 0);
    """)
    for tool, price in DEFAULT_PRICES.items():
        c.execute("INSERT OR IGNORE INTO prices(tool,price) VALUES(?,?)", (tool, price))
    c.execute("INSERT OR IGNORE INTO discount(id,enabled,percentage) VALUES(1,0,0)")
    for tool in ALL_TOOLS:
        c.execute("INSERT OR IGNORE INTO tool_status(tool,enabled) VALUES(?,1)", (tool,))
    c.commit(); c.close()


def register_user(user):
    c = db()
    c.execute("""INSERT INTO users(user_id,username,first_name,stars,created_at)
                 VALUES(?,?,?,?,?)
                 ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name""",
              (user.id, user.username, user.first_name, 0, datetime.now().isoformat(timespec="seconds")))
    c.commit(); c.close()


def get_balance(uid):
    c = db(); r = c.execute("SELECT stars FROM users WHERE user_id=?", (uid,)).fetchone(); c.close()
    return int(r["stars"]) if r else 0


def change_balance(uid, amount):
    c = db(); c.execute("UPDATE users SET stars=stars+? WHERE user_id=?", (amount, uid)); c.commit(); c.close()


def get_price(tool):
    c = db()
    r = c.execute("SELECT price FROM prices WHERE tool=?", (tool,)).fetchone()
    d = c.execute("SELECT enabled,percentage FROM discount WHERE id=1").fetchone()
    c.close()
    base = int(r["price"]) if r else 0
    return max(0, round(base * (100 - d["percentage"]) / 100)) if d and d["enabled"] else base


def set_price(tool, price):
    c = db(); c.execute("INSERT INTO prices(tool,price) VALUES(?,?) ON CONFLICT(tool) DO UPDATE SET price=excluded.price", (tool,price)); c.commit(); c.close()


def is_enabled(tool):
    c = db(); r = c.execute("SELECT enabled FROM tool_status WHERE tool=?", (tool,)).fetchone(); c.close()
    return bool(r["enabled"]) if r else False


def set_enabled(tool, enabled):
    c = db(); c.execute("UPDATE tool_status SET enabled=? WHERE tool=?", (int(enabled),tool)); c.commit(); c.close()


def log_usage(uid, tool, stars, status):
    c = db(); c.execute("INSERT INTO usage_logs(user_id,tool,stars,status,created_at) VALUES(?,?,?,?,?)", (uid,tool,stars,status,datetime.now().isoformat(timespec="seconds"))); c.commit(); c.close()

# =========================
# KEYBOARDS
# =========================
def home_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆓 الأدوات المجانية", callback_data="free")],
        [InlineKeyboardButton("💎 الأدوات المدفوعة", callback_data="pro")],
        [InlineKeyboardButton("🤖 الذكاء الاصطناعي", callback_data="ai")],
        [InlineKeyboardButton("⭐ رصيدي", callback_data="balance")],
        [InlineKeyboardButton("💳 الاشتراك والباقات", callback_data="plans")],
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
    ])


def back_home():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الرئيسية", callback_data="home")]])


def free_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(v, callback_data=f"free:{k}")] for k,v in FREE_TOOLS.items()
    ] + [[InlineKeyboardButton("🔙 الرئيسية", callback_data="home")]])


def pro_kb():
    rows = [[InlineKeyboardButton(f"{v} — ⭐{get_price(k)}", callback_data=f"pro:{k}")] for k,v in PRO_TOOLS.items()]
    rows += [[InlineKeyboardButton("💳 شراء Stars", callback_data="plans")], [InlineKeyboardButton("🔙 الرئيسية", callback_data="home")]]
    return InlineKeyboardMarkup(rows)


def plans_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ شراء 100 Stars", callback_data="buy:100")],
        [InlineKeyboardButton("⭐ شراء 500 Stars", callback_data="buy:500")],
        [InlineKeyboardButton("⭐ شراء 1000 Stars", callback_data="buy:1000")],
        [InlineKeyboardButton("🔙 الرئيسية", callback_data="home")],
    ])

# =========================
# OPENROUTER HELPERS
# =========================
def or_headers():
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://telegram.org",
        "X-Title": "AI Tools Telegram Bot",
    }


async def openrouter_chat(prompt, system="أنت مساعد مفيد داخل بوت Telegram.", vision_image_bytes=None, model=None):
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY غير موجود في Render")

    content = [{"type":"text", "text":prompt}]
    if vision_image_bytes is not None:
        mime = "image/jpeg"
        try:
            im = Image.open(io.BytesIO(vision_image_bytes))
            mime = Image.MIME.get(im.format, "image/jpeg")
        except Exception:
            pass
        b64 = base64.b64encode(vision_image_bytes).decode()
        content.append({"type":"image_url", "image_url":{"url":f"data:{mime};base64,{b64}"}})

    payload = {
        "model": model or (OPENROUTER_VISION_MODEL if vision_image_bytes else OPENROUTER_FREE_MODEL),
        "messages":[
            {"role":"system","content":system},
            {"role":"user","content":content},
        ],
        "temperature":0.2,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{OPENROUTER_BASE_URL}/chat/completions", headers=or_headers(), json=payload)
        if r.status_code >= 400:
            raise RuntimeError(f"OpenRouter {r.status_code}: {r.text[:500]}")
        data = r.json()
    text = data["choices"][0]["message"].get("content", "")
    if isinstance(text, list):
        text = "".join(x.get("text","") for x in text if isinstance(x,dict))
    if not str(text).strip():
        raise RuntimeError("OpenRouter returned empty response")
    return str(text).strip()


async def ocr_image(image_bytes):
    return await openrouter_chat(
        "استخرج كل النص الظاهر في الصورة حرفيًا قدر الإمكان. لا تشرح ولا تلخص. حافظ على ترتيب الأسطر واللغة العربية.",
        system="أنت OCR دقيق. أعد النص فقط.",
        vision_image_bytes=image_bytes,
    )


async def translate_text(text, target):
    language = {"en":"English","ar":"Arabic","fr":"French","tr":"Turkish","de":"German"}.get(target,target)
    return await openrouter_chat(
        f"Translate the following text to {language}. Return only the translation and preserve formatting.\n\n{text}",
        system="You are a professional translator."
    )

# =========================
# IMAGE / FILE HELPERS
# =========================
async def remove_background(image_bytes):
    if not REMOVEBG_API_KEY:
        raise RuntimeError("إزالة الخلفية تحتاج REMOVEBG_API_KEY. هذه خدمة منفصلة عن OpenRouter.")
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post("https://api.remove.bg/v1.0/removebg",
                              headers={"X-Api-Key":REMOVEBG_API_KEY},
                              files={"image_file":("image.png",image_bytes,"image/png")},
                              data={"size":"auto"})
        if r.status_code != 200:
            raise RuntimeError(f"remove.bg {r.status_code}: {r.text[:300]}")
        return r.content


def local_image(image_bytes, operation):
    image = Image.open(io.BytesIO(image_bytes))
    if operation == "compress":
        image.thumbnail((2000,2000)); out=io.BytesIO(); image.convert("RGB").save(out,"JPEG",quality=65,optimize=True); return out.getvalue(),"compressed.jpg"
    if operation == "convert":
        out=io.BytesIO(); image.convert("RGBA").save(out,"PNG",optimize=True); return out.getvalue(),"converted.png"
    if operation == "enhance":
        image=ImageEnhance.Sharpness(image).enhance(1.8); image=ImageEnhance.Contrast(image).enhance(1.15); image=ImageEnhance.Color(image).enhance(1.1); image=image.filter(ImageFilter.UnsharpMask(radius=1,percent=120)); out=io.BytesIO(); image.save(out,"JPEG",quality=95); return out.getvalue(),"enhanced.jpg"
    raise ValueError("unknown operation")


def images_to_pdf(image_bytes_list):
    images=[]
    for b in image_bytes_list:
        im=Image.open(io.BytesIO(b)).convert("RGB")
        images.append(im)
    out=io.BytesIO()
    if images: images[0].save(out,"PDF",save_all=True,append_images=images[1:])
    return out.getvalue()

# =========================
# OPTIONAL OPENAI PREMIUM HELPERS
# =========================
async def openai_image_generate(prompt):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY غير موجود. توليد الصور بالذكاء الاصطناعي يحتاج مزود صور مدفوع/تجريبي.")
    from openai import AsyncOpenAI
    client=AsyncOpenAI(api_key=OPENAI_API_KEY)
    result=await client.images.generate(model=os.getenv("OPENAI_IMAGE_MODEL","gpt-image-1"), prompt=prompt, size="1024x1024")
    return base64.b64decode(result.data[0].b64_json)


async def openai_edit_image(image_bytes,prompt):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY غير موجود. تعديل الصور بالذكاء الاصطناعي يحتاج مزود صور مدفوع/تجريبي.")
    from openai import AsyncOpenAI
    client=AsyncOpenAI(api_key=OPENAI_API_KEY)
    f=tempfile.NamedTemporaryFile(suffix=".png",delete=False); f.write(image_bytes); f.close()
    try:
        with open(f.name,"rb") as img:
            result=await client.images.edit(model=os.getenv("OPENAI_IMAGE_MODEL","gpt-image-1"), image=img, prompt=prompt, size="1024x1024")
        return base64.b64decode(result.data[0].b64_json)
    finally:
        try: os.unlink(f.name)
        except OSError: pass


async def openai_transcribe(audio_bytes, filename="voice.ogg"):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY غير موجود. STT يحتاج مزود تحويل صوت إلى نص.")
    from openai import AsyncOpenAI
    client=AsyncOpenAI(api_key=OPENAI_API_KEY)
    f=tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1] or ".ogg",delete=False); f.write(audio_bytes); f.close()
    try:
        with open(f.name,"rb") as audio:
            r=await client.audio.transcriptions.create(model=os.getenv("OPENAI_STT_MODEL","gpt-4o-mini-transcribe"),file=audio)
        return r.text.strip()
    finally:
        try: os.unlink(f.name)
        except OSError: pass


async def text_to_speech(text):
    f=tempfile.NamedTemporaryFile(suffix=".mp3",delete=False); f.close()
    try:
        await edge_tts.Communicate(text,"ar-SA-HamedNeural").save(f.name)
        with open(f.name,"rb") as x: return x.read()
    finally:
        try: os.unlink(f.name)
        except OSError: pass

# =========================
# COMMON
# =========================
async def require_credits(update, tool):
    price=get_price(tool); balance=get_balance(update.effective_user.id)
    if balance < price:
        await update.effective_message.reply_text(f"❌ رصيدك غير كافٍ.\n\nالسعر: ⭐{price}\nرصيدك: ⭐{balance}",reply_markup=plans_kb())
        return False
    return True


def charge_after_success(uid,tool):
    p=get_price(tool); change_balance(uid,-p); log_usage(uid,tool,p,"success"); return p

# =========================
# COMMANDS / MENUS
# =========================
async def start(update,context):
    register_user(update.effective_user)
    await update.message.reply_text("👋 أهلاً بك في AI TOOLS!\n\nاختر القسم:",reply_markup=home_kb())

async def admin(update,context):
    if update.effective_user.id != OWNER_ID: await update.message.reply_text("❌ غير مصرح."); return
    await update.message.reply_text("👑 لوحة المالك",reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 الأسعار",callback_data="admin:prices")],
        [InlineKeyboardButton("🛠️ تشغيل/إيقاف الأدوات",callback_data="admin:tools")],
        [InlineKeyboardButton("📊 الإحصائيات",callback_data="admin:stats")],
        [InlineKeyboardButton("⭐ تعديل رصيد",callback_data="admin:balance")],
        [InlineKeyboardButton("🎁 الخصم",callback_data="admin:discount")],
        [InlineKeyboardButton("🔙 الرئيسية",callback_data="home")],
    ]))

# =========================
# CALLBACKS
# =========================
async def callbacks(update,context):
    q=update.callback_query; await q.answer(); register_user(q.from_user); data=q.data
    if data=="home": await q.edit_message_text("🤖 AI TOOLS\n\nاختر القسم:",reply_markup=home_kb()); return
    if data=="free": await q.edit_message_text("🆓 الأدوات المجانية",reply_markup=free_kb()); return
    if data=="pro": await q.edit_message_text("💎 الأدوات المدفوعة\n\nتخصم Stars بعد نجاح العملية فقط.",reply_markup=pro_kb()); return
    if data=="ai": await q.edit_message_text("🤖 الذكاء الاصطناعي",reply_markup=pro_kb()); return
    if data=="balance": await q.edit_message_text(f"⭐ رصيدك: {get_balance(q.from_user.id)}",reply_markup=plans_kb()); return
    if data=="plans": await q.edit_message_text("💳 شراء Stars داخل Telegram:",reply_markup=plans_kb()); return
    if data=="settings": await q.edit_message_text("⚙️ الإعدادات\n\nالإعدادات الأساسية جاهزة.",reply_markup=back_home()); return

    if data.startswith("buy:"):
        amount=int(data.split(":")[1])
        await context.bot.send_invoice(chat_id=q.message.chat_id,title=f"{amount} Stars",description=f"إضافة {amount} Stars",payload=f"stars:{amount}:{q.from_user.id}",provider_token="",currency="XTR",prices=[LabeledPrice(f"{amount} Telegram Stars",amount)])
        return

    if data.startswith("free:"):
        tool=data.split(":",1)[1]; context.user_data["pending_tool"]=tool
        prompts={
            "background_removal":"✂️ أرسل صورة لإزالة الخلفية.",
            "ocr":"🔤 أرسل صورة لاستخراج النص.",
            "image_convert":"🖼️ أرسل صورة لتحويلها إلى PNG.",
            "image_compress":"📦 أرسل صورة لضغطها.",
            "image_to_pdf":"📄 أرسل صورة/صور. سأجمع الصور في PDF.",
            "pdf_to_images":"🖼️ أرسل ملف PDF.",
            "translation":"🌐 أرسل مثل: ترجم إلى الإنجليزية: مرحبًا بالعالم",
            "text_tools":"📝 أرسل النص لتصحيحه وترتيبه.",
            "tts":"🗣️ أرسل النص لتحويله إلى صوت.",
        }
        await q.edit_message_text(prompts[tool],reply_markup=back_home()); return

    if data.startswith("pro:"):
        tool=data.split(":",1)[1]
        if not is_enabled(tool): await q.edit_message_text("⏸️ الأداة متوقفة مؤقتًا.",reply_markup=back_home()); return
        if get_balance(q.from_user.id)<get_price(tool): await q.edit_message_text(f"❌ تحتاج ⭐{get_price(tool)}\nرصيدك ⭐{get_balance(q.from_user.id)}",reply_markup=plans_kb()); return
        context.user_data["pending_tool"]=tool
        prompts={"image_generation":"🎨 أرسل وصف الصورة.","image_edit":"🪄 أرسل الصورة ثم وصف التعديل.","image_enhancement":"✨ أرسل الصورة لتحسينها.","style_transfer":"🎭 أرسل الصورة ثم وصف النمط.","stt":"🎤 أرسل رسالة صوتية/ملف صوت.","pdf_summary":"📄 أرسل PDF.","ai_assistant":"🧠 أرسل سؤالك."}
        await q.edit_message_text(f"{prompts[tool]}\n\n⭐ السعر: {get_price(tool)}",reply_markup=back_home()); return

    if data.startswith("admin:") and q.from_user.id==OWNER_ID:
        action=data.split(":",1)[1]
        if action=="prices":
            await q.edit_message_text("💰 اختر السعر:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"{n} ⭐{get_price(t)}",callback_data=f"setprice:{t}")] for t,n in PRO_TOOLS.items()]+[[InlineKeyboardButton("🔙",callback_data="home")]])); return
        if action=="tools":
            await q.edit_message_text("🛠️ حالة الأدوات:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"{'🟢' if is_enabled(t) else '🔴'} {n}",callback_data=f"toggle:{t}")] for t,n in ALL_TOOLS.items()]+[[InlineKeyboardButton("🔙",callback_data="home")]])); return
        if action=="stats":
            c=db(); users=c.execute("SELECT COUNT(*) x FROM users").fetchone()["x"]; ops=c.execute("SELECT COUNT(*) x FROM usage_logs").fetchone()["x"]; spent=c.execute("SELECT COALESCE(SUM(stars),0) x FROM usage_logs WHERE status='success'").fetchone()["x"]; c.close()
            await q.edit_message_text(f"📊 المستخدمون: {users}\n📌 العمليات: {ops}\n⭐ Stars المستخدمة: {spent}",reply_markup=back_home()); return
        if action=="balance": context.user_data["admin_action"]="balance"; await q.edit_message_text("أرسل: UserID amount"); return
        if action=="discount": context.user_data["admin_action"]="discount"; await q.edit_message_text("أرسل نسبة الخصم 0-100:"); return

    if data.startswith("toggle:") and q.from_user.id==OWNER_ID:
        t=data.split(":",1)[1]; set_enabled(t,not is_enabled(t)); await q.edit_message_text("✅ تم تحديث الحالة.",reply_markup=back_home()); return
    if data.startswith("setprice:") and q.from_user.id==OWNER_ID:
        t=data.split(":",1)[1]; context.user_data["admin_action"]="price"; context.user_data["price_tool"]=t; await q.edit_message_text(f"أرسل السعر الجديد لـ {PRO_TOOLS[t]}:"); return

# =========================
# PAYMENTS
# =========================
async def precheckout(update,context): await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update,context):
    p=update.message.successful_payment
    if not p.invoice_payload.startswith("stars:"): return
    _,amount,target=p.invoice_payload.split(":"); amount=int(amount); target=int(target)
    if target!=update.effective_user.id: return
    change_balance(target,amount); log_usage(target,"telegram_stars_purchase",-amount,"purchase")
    await update.message.reply_text(f"✅ تم الدفع!\n➕ ⭐{amount}\n⭐ رصيدك: {get_balance(target)}",reply_markup=home_kb())

# =========================
# TEXT
# =========================
async def text_handler(update,context):
    user=update.effective_user; register_user(user); text=(update.message.text or "").strip()

    if user.id==OWNER_ID and context.user_data.get("admin_action"):
        a=context.user_data["admin_action"]
        if a=="price":
            try: v=int(text); assert v>=0
            except: await update.message.reply_text("❌ رقم غير صحيح."); return
            set_price(context.user_data["price_tool"],v); context.user_data.clear(); await update.message.reply_text("✅ تم.",reply_markup=home_kb()); return
        if a=="balance":
            try: target,amount=map(int,text.split())
            except: await update.message.reply_text("❌ استخدم UserID amount"); return
            change_balance(target,amount); context.user_data.clear(); await update.message.reply_text(f"✅ الرصيد: ⭐{get_balance(target)}"); return
        if a=="discount":
            try: p=int(text); assert 0<=p<=100
            except: await update.message.reply_text("❌ من 0 إلى 100."); return
            c=db(); c.execute("UPDATE discount SET enabled=1,percentage=? WHERE id=1",(p,)); c.commit(); c.close(); context.user_data.clear(); await update.message.reply_text("✅ تم تفعيل الخصم."); return

    tool=context.user_data.get("pending_tool")
    if not tool: return

    try:
        if tool=="translation":
            m=re.match(r"ترجم(?:\s+إلى)?\s+([\w\u0600-\u06FF]+)\s*:\s*(.+)",text,re.S|re.I)
            if not m: await update.message.reply_text("مثال: ترجم إلى الإنجليزية: مرحبًا"); return
            target_name=m.group(1).lower(); target={"الإنجليزية":"en","انجليزية":"en","english":"en","العربية":"ar","عربي":"ar","الفرنسية":"fr","التركية":"tr","الألمانية":"de"}.get(target_name,target_name)
            result=await translate_text(m.group(2),target); context.user_data.pop("pending_tool",None); await update.message.reply_text("🌐 الترجمة:\n\n"+result,reply_markup=home_kb()); return

        if tool=="text_tools":
            result=await openrouter_chat("صحح النص التالي لغويًا ورتبه مع الحفاظ على المعنى. أعد النص المصحح فقط:\n\n"+text,system="أنت مدقق لغوي عربي محترف.")
            context.user_data.pop("pending_tool",None); await update.message.reply_text("📝 النص المصحح:\n\n"+result,reply_markup=home_kb()); return

        if tool=="tts":
            audio=await text_to_speech(text); context.user_data.pop("pending_tool",None); await update.message.reply_audio(audio=io.BytesIO(audio),caption="🗣️ تم تحويل النص إلى صوت.",reply_markup=home_kb()); return

        if tool=="ai_assistant":
            if not await require_credits(update,tool): return
            result=await openrouter_chat(text,system="أنت مساعد AI متقدم. أجب بالعربية ما لم يطلب المستخدم غير ذلك.")
            p=charge_after_success(user.id,tool); context.user_data.pop("pending_tool",None); await update.message.reply_text(f"🧠 {result}\n\n⭐ تم الخصم: {p}",reply_markup=home_kb()); return

        if tool=="image_generation":
            if not await require_credits(update,tool): return
            if not OPENROUTER_IMAGE_MODEL and not OPENAI_API_KEY:
                await update.message.reply_text("⚠️ توليد الصور يحتاج مزود صور. مفتاح OpenRouter الحالي لا يجعل توليد الصور مجانيًا؛ أضف OPENAI_API_KEY أو OPENROUTER_IMAGE_MODEL مع رصيد.",reply_markup=plans_kb()); return
            image=await openai_image_generate(text) if OPENAI_API_KEY else None
            if image is None: raise RuntimeError("OPENROUTER image generation adapter not enabled")
            p=charge_after_success(user.id,tool); context.user_data.pop("pending_tool",None); await update.message.reply_photo(photo=io.BytesIO(image),caption=f"🎨 تم التوليد. ⭐{p}",reply_markup=home_kb()); return

        if tool=="style_transfer":
            context.user_data["style_prompt"]=text; context.user_data["waiting_style_image"]=True; await update.message.reply_text("📷 أرسل الصورة الآن."); return

    except Exception as e:
        logger.exception("text tool failed")
        log_usage(user.id,tool,0,"failed")
        await update.message.reply_text(f"❌ فشلت العملية ولم يتم خصم Stars.\n\n{str(e)[:300]}",reply_markup=home_kb())

# =========================
# PHOTO
# =========================
async def photo_handler(update,context):
    user=update.effective_user; register_user(user); tool=context.user_data.get("pending_tool")
    if not tool: await update.message.reply_text("اختر أداة أولًا.",reply_markup=home_kb()); return
    f=await update.message.photo[-1].get_file(); data=bytes(await f.download_as_bytearray())
    try:
        if tool=="background_removal":
            result=await remove_background(data); context.user_data.pop("pending_tool",None); await update.message.reply_document(io.BytesIO(result),filename="no-background.png",caption="✂️ تم حذف الخلفية.",reply_markup=home_kb()); return
        if tool=="ocr":
            result=await ocr_image(data); context.user_data.pop("pending_tool",None); await update.message.reply_text("🔤 النص المستخرج:\n\n"+result,reply_markup=home_kb()); return
        if tool=="image_convert":
            result,name=local_image(data,"convert"); context.user_data.pop("pending_tool",None); await update.message.reply_document(io.BytesIO(result),filename=name,caption="🖼️ تم التحويل.",reply_markup=home_kb()); return
        if tool=="image_compress":
            result,name=local_image(data,"compress"); context.user_data.pop("pending_tool",None); await update.message.reply_document(io.BytesIO(result),filename=name,caption="📦 تم الضغط.",reply_markup=home_kb()); return
        if tool=="image_enhancement":
            if not await require_credits(update,tool): return
            result,name=local_image(data,"enhance"); p=charge_after_success(user.id,tool); context.user_data.pop("pending_tool",None); await update.message.reply_document(io.BytesIO(result),filename=name,caption=f"✨ تم التحسين محليًا. ⭐{p}",reply_markup=home_kb()); return
        if tool in {"image_edit","style_transfer"}:
            if not await require_credits(update,tool): return
            prompt=context.user_data.get("style_prompt") or context.user_data.get("edit_prompt")
            if not prompt:
                context.user_data["edit_image_bytes"]=data; context.user_data["waiting_edit_prompt"]=True; await update.message.reply_text("🪄 أرسل وصف التعديل الآن."); return
            result=await openai_edit_image(data,prompt); p=charge_after_success(user.id,tool); context.user_data.clear(); await update.message.reply_photo(io.BytesIO(result),caption=f"🪄 تم التعديل. ⭐{p}",reply_markup=home_kb()); return
    except Exception as e:
        logger.exception("photo failed"); log_usage(user.id,tool,0,"failed"); await update.message.reply_text(f"❌ فشلت العملية ولم يتم الخصم.\n\n{str(e)[:300]}",reply_markup=home_kb())

# =========================
# DOCUMENT / VOICE
# =========================
async def document_handler(update,context):
    user=update.effective_user; register_user(user); tool=context.user_data.get("pending_tool")
    if not tool: await update.message.reply_text("اختر أداة أولًا.",reply_markup=home_kb()); return
    f=await update.message.document.get_file(); data=bytes(await f.download_as_bytearray())
    try:
        if tool=="pdf_to_images":
            pdf=fitz.open(stream=data,filetype="pdf")
            for i,page in enumerate(pdf):
                pix=page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False)
                await update.message.reply_document(io.BytesIO(pix.tobytes("png")),filename=f"page-{i+1}.png")
            context.user_data.pop("pending_tool",None); await update.message.reply_text("🖼️ تم استخراج الصفحات.",reply_markup=home_kb()); return
        if tool=="pdf_summary":
            if not await require_credits(update,tool): return
            pdf=fitz.open(stream=data,filetype="pdf"); text="\n".join(p.get_text() for p in pdf)[:60000]
            result=await openrouter_chat("لخص هذا PDF بالعربية واستخرج أهم النقاط والعناوين:\n\n"+text,system="أنت محلل مستندات محترف.")
            p=charge_after_success(user.id,tool); context.user_data.pop("pending_tool",None); await update.message.reply_text(f"📄 الملخص:\n\n{result}\n\n⭐{p}",reply_markup=home_kb()); return
        if tool=="stt":
            if not await require_credits(update,tool): return
            result=await openai_transcribe(data,update.message.document.file_name or "audio.ogg"); p=charge_after_success(user.id,tool); context.user_data.pop("pending_tool",None); await update.message.reply_text(f"🎤 النص:\n\n{result}\n\n⭐{p}",reply_markup=home_kb()); return
    except Exception as e:
        logger.exception("document failed"); log_usage(user.id,tool,0,"failed"); await update.message.reply_text(f"❌ فشلت العملية ولم يتم الخصم.\n\n{str(e)[:300]}",reply_markup=home_kb())


async def voice_handler(update,context):
    user=update.effective_user; register_user(user); tool=context.user_data.get("pending_tool")
    if tool!="stt": await update.message.reply_text("اختر 🎤 صوت → نص أولًا.",reply_markup=home_kb()); return
    if not await require_credits(update,tool): return
    try:
        f=await update.message.voice.get_file(); data=bytes(await f.download_as_bytearray()); result=await openai_transcribe(data,"voice.ogg"); p=charge_after_success(user.id,tool); context.user_data.pop("pending_tool",None); await update.message.reply_text(f"🎤 النص:\n\n{result}\n\n⭐{p}",reply_markup=home_kb())
    except Exception as e:
        logger.exception("voice failed"); log_usage(user.id,tool,0,"failed"); await update.message.reply_text(f"❌ فشل التحويل ولم يتم الخصم.\n\n{str(e)[:300]}",reply_markup=home_kb())

# =========================
# ERROR / MAIN
# =========================
async def error_handler(update,context): logger.exception("Unhandled error",exc_info=context.error)

def main():
    init_db()
    app=Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("admin",admin))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT,successful_payment))
    app.add_handler(MessageHandler(filters.PHOTO,photo_handler))
    app.add_handler(MessageHandler(filters.VOICE,voice_handler))
    app.add_handler(MessageHandler(filters.Document.ALL,document_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler))
    app.add_error_handler(error_handler)
    logger.info("AI TOOLS BOT running")
    app.run_polling()

if __name__=="__main__": main()
