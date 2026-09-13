import os
import io
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

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    PreCheckoutQueryHandler,
    filters,
)


# =========================================================
# KEEP ALIVE - RENDER
# =========================================================

web_app = Flask(__name__)


@web_app.route("/")
def home():
    return "Bot is running perfectly!"


def run_web():
    port = int(os.environ.get("PORT", "8080"))
    web_app.run(host="0.0.0.0", port=port)


def keep_alive():
    t = Thread(target=run_web, daemon=True)
    t.start()


keep_alive()


# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = int(os.getenv("OWNER_ID", "8860453018"))

DATABASE = os.getenv("DATABASE", "ai_tools.db")

STARTER_STARS = 10

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv(
    "OPENROUTER_BASE_URL",
    "https://openrouter.ai/api/v1"
)

OPENROUTER_FREE_MODEL = os.getenv(
    "OPENROUTER_FREE_MODEL",
    "openrouter/free"
)

# ضع هنا نموذج Vision يدعم الصور إذا أردت OCR.
# يمكن تغييره من Environment Variables في Render.
OPENROUTER_VISION_MODEL = os.getenv(
    "OPENROUTER_VISION_MODEL",
    "openrouter/free"
)

REMOVEBG_API_KEY = os.getenv("REMOVEBG_API_KEY", "")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

OPENAI_IMAGE_MODEL = os.getenv(
    "OPENAI_IMAGE_MODEL",
    "gpt-4o"
)

OPENAI_STT_MODEL = os.getenv(
    "OPENAI_STT_MODEL",
    "gpt-4o-mini-transcribe"
)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger(__name__)


# =========================================================
# TOOLS
# =========================================================

TOOLS = {
    "translation": "🌐 ترجمة النص",
    "text_tools": "📝 تصحيح النص",
    "ocr": "🔤 استخراج النص من صورة",
    "image_convert": "🖼️ تحويل صيغ الصور",
    "image_compress": "📦 ضغط الصور",
    "image_to_pdf": "📄 صور ← PDF",
    "pdf_to_images": "🖼️ PDF ← صور",
    "pdf_summary": "📄 تحليل/تلخيص PDF",
    "background_removal": "✂️ إزالة الخلفية",
    "tts": "🗣️ نص ← صوت",
    "stt": "🎤 صوت ← نص",
    "image_generation": "🎨 توليد الصور",
    "image_edit": "🪄 تعديل الصور بالذكاء الاصطناعي",
    "image_enhancement": "✨ تحسين الصور",
    "style_transfer": "🎭 تغيير نمط الصورة",
    "ai_assistant": "🧠 مساعد AI المتقدم",
}


# =========================================================
# DEFAULT PRICES
# =========================================================

DEFAULT_PRICES = {
    "translation": 0,
    "text_tools": 0,
    "ocr": 0,
    "image_convert": 0,
    "image_compress": 0,
    "image_to_pdf": 0,
    "pdf_to_images": 0,
    "pdf_summary": 0,

    "background_removal": 2,
    "tts": 1,
    "stt": 1,
    "image_generation": 5,
    "image_edit": 5,
    "image_enhancement": 3,
    "style_transfer": 4,
    "ai_assistant": 1,
}


# =========================================================
# DATABASE
# =========================================================

def db():
    connection = sqlite3.connect(
        DATABASE,
        timeout=30
    )
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    c = db()

    c.executescript(
        """
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

        CREATE TABLE IF NOT EXISTS prices(
            tool TEXT PRIMARY KEY,
            price INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tool_status(
            tool TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS discount(
            id INTEGER PRIMARY KEY CHECK(id=1),
            enabled INTEGER NOT NULL DEFAULT 0,
            percentage INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS payments(
            charge_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )

    for tool, price in DEFAULT_PRICES.items():
        c.execute(
            """
            INSERT OR IGNORE INTO prices(tool, price)
            VALUES(?, ?)
            """,
            (tool, price)
        )

    c.execute(
        """
        INSERT OR IGNORE INTO discount(id, enabled, percentage)
        VALUES(1, 0, 0)
        """
    )

    for tool in TOOLS:
        c.execute(
            """
            INSERT OR IGNORE INTO tool_status(tool, enabled)
            VALUES(?, 1)
            """,
            (tool,)
        )

    c.commit()
    c.close()


def register_user(user):
    c = db()

    # مهم:
    # عند أول تسجيل فقط يحصل المستخدم على STARTER_STARS.
    c.execute(
        """
        INSERT INTO users(
            user_id,
            username,
            first_name,
            stars,
            created_at
        )
        VALUES(?, ?, ?, ?, ?)

        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name
        """,
        (
            user.id,
            user.username,
            user.first_name,
            STARTER_STARS,
            datetime.now().isoformat(timespec="seconds"),
        )
    )

    c.commit()
    c.close()


def get_balance(uid):
    c = db()

    row = c.execute(
        "SELECT stars FROM users WHERE user_id=?",
        (uid,)
    ).fetchone()

    c.close()

    return int(row["stars"]) if row else 0


def change_balance(uid, amount):
    c = db()

    c.execute(
        "UPDATE users SET stars=stars+? WHERE user_id=?",
        (amount, uid)
    )

    c.commit()
    c.close()


def get_discount():
    c = db()

    row = c.execute(
        """
        SELECT enabled, percentage
        FROM discount
        WHERE id=1
        """
    ).fetchone()

    c.close()

    if not row:
        return False, 0

    return bool(row["enabled"]), int(row["percentage"])


def get_price(tool):
    c = db()

    row = c.execute(
        "SELECT price FROM prices WHERE tool=?",
        (tool,)
    ).fetchone()

    c.close()

    base = int(row["price"]) if row else 0

    if base <= 0:
        return 0

    enabled, percentage = get_discount()

    if not enabled:
        return base

    return max(
        0,
        round(base * (100 - percentage) / 100)
    )


def set_price(tool, price):
    c = db()

    c.execute(
        """
        INSERT INTO prices(tool, price)
        VALUES(?, ?)

        ON CONFLICT(tool)
        DO UPDATE SET price=excluded.price
        """,
        (tool, max(0, int(price)))
    )

    c.commit()
    c.close()


def is_enabled(tool):
    c = db()

    row = c.execute(
        "SELECT enabled FROM tool_status WHERE tool=?",
        (tool,)
    ).fetchone()

    c.close()

    return bool(row["enabled"]) if row else False


def set_enabled(tool, enabled):
    c = db()

    c.execute(
        """
        UPDATE tool_status
        SET enabled=?
        WHERE tool=?
        """,
        (int(enabled), tool)
    )

    c.commit()
    c.close()


def log_usage(uid, tool, stars, status):
    c = db()

    c.execute(
        """
        INSERT INTO usage_logs(
            user_id,
            tool,
            stars,
            status,
            created_at
        )
        VALUES(?, ?, ?, ?, ?)
        """,
        (
            uid,
            tool,
            stars,
            status,
            datetime.now().isoformat(timespec="seconds"),
        )
    )

    c.commit()
    c.close()


# =========================================================
# CREDITS
# =========================================================

def reserve_credits(uid, tool):
    """
    يحجز الرصيد قبل العملية لمنع استخدام أكثر من الرصيد
    عند إرسال عدة طلبات بسرعة.
    """

    if uid == OWNER_ID:
        return True, 0

    price = get_price(tool)

    if price <= 0:
        return True, 0

    c = db()

    cursor = c.execute(
        """
        UPDATE users
        SET stars=stars-?
        WHERE user_id=?
        AND stars>=?
        """,
        (price, uid, price)
    )

    success = cursor.rowcount == 1

    c.commit()
    c.close()

    if not success:
        return False, price

    return True, price


def refund_credits(uid, tool, amount):
    if uid == OWNER_ID or amount <= 0:
        return

    change_balance(uid, amount)

    log_usage(
        uid,
        tool,
        amount,
        "refunded"
    )


def complete_charge(uid, tool, amount):
    if uid == OWNER_ID:
        return

    if amount > 0:
        log_usage(
            uid,
            tool,
            amount,
            "success"
        )


async def require_credits(update, tool):
    uid = update.effective_user.id

    success, price = reserve_credits(uid, tool)

    if success:
        return True, price

    balance = get_balance(uid)

    await update.effective_message.reply_text(
        "❌ رصيدك غير كافٍ.\n\n"
        f"السعر: ⭐{price}\n"
        f"رصيدك الحالي: ⭐{balance}\n\n"
        "يمكنك شراء Stars من قسم الباقات.",
        reply_markup=plans_kb(),
    )

    return False, 0


# =========================================================
# KEYBOARDS
# =========================================================

def main_menu_kb(user_id):
    rows = []

    free_items = [
        (k, v)
        for k, v in TOOLS.items()
        if get_price(k) == 0 and is_enabled(k)
    ]

    if free_items:
        rows.append([
            InlineKeyboardButton(
                "--- 🆓 الأدوات المجانية ---",
                callback_data="nop"
            )
        ])

        for i in range(0, len(free_items), 2):
            pair = free_items[i:i + 2]

            rows.append([
                InlineKeyboardButton(
                    name,
                    callback_data=f"select:{tool}"
                )
                for tool, name in pair
            ])

    pro_items = [
        (k, f"{v} (⭐{get_price(k)})")
        for k, v in TOOLS.items()
        if get_price(k) > 0 and is_enabled(k)
    ]

    if pro_items:
        rows.append([
            InlineKeyboardButton(
                "--- 💎 الأدوات المدفوعة PRO ---",
                callback_data="nop"
            )
        ])

        for i in range(0, len(pro_items), 2):
            pair = pro_items[i:i + 2]

            rows.append([
                InlineKeyboardButton(
                    name,
                    callback_data=f"select:{tool}"
                )
                for tool, name in pair
            ])

    rows.append([
        InlineKeyboardButton(
            "⭐ رصيدي",
            callback_data="balance"
        ),
        InlineKeyboardButton(
            "💳 شراء Stars",
            callback_data="plans"
        )
    ])

    if user_id == OWNER_ID:
        rows.append([
            InlineKeyboardButton(
                "👑 لوحة تحكم المالك",
                callback_data="admin"
            )
        ])

    return InlineKeyboardMarkup(rows)


def back_home():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔙 القائمة الرئيسية / إلغاء",
                callback_data="home"
            )
        ]
    ])


def plans_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⭐ شراء 100 Stars",
                callback_data="buy:100"
            ),
            InlineKeyboardButton(
                "⭐ شراء 500 Stars",
                callback_data="buy:500"
            ),
        ],
        [
            InlineKeyboardButton(
                "⭐ شراء 1000 Stars",
                callback_data="buy:1000"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 الرئيسية",
                callback_data="home"
            )
        ],
    ])


# =========================================================
# OPENROUTER
# =========================================================

def or_headers():
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://telegram.org",
        "X-Title": "AI Tools Telegram Bot",
    }


async def openrouter_chat(
    prompt,
    system="أنت مساعد مفيد داخل بوت Telegram.",
    vision_image_bytes=None,
    model=None,
):
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY غير موجود."
        )

    if vision_image_bytes is None:
        content = prompt
    else:
        mime = "image/jpeg"

        try:
            im = Image.open(
                io.BytesIO(vision_image_bytes)
            )

            mime = Image.MIME.get(
                im.format,
                "image/jpeg"
            )

        except Exception:
            pass

        b64 = base64.b64encode(
            vision_image_bytes
        ).decode()

        content = [
            {
                "type": "text",
                "text": prompt,
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime};base64,{b64}"
                },
            },
        ]

    payload = {
        "model": model or (
            OPENROUTER_VISION_MODEL
            if vision_image_bytes
            else OPENROUTER_FREE_MODEL
        ),
        "messages": [
            {
                "role": "system",
                "content": system,
            },
            {
                "role": "user",
                "content": content,
            },
        ],
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(
        timeout=120
    ) as client:

        response = await client.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=or_headers(),
            json=payload,
        )

    if response.status_code >= 400:
        raise RuntimeError(
            f"OpenRouter {response.status_code}: "
            f"{response.text[:500]}"
        )

    data = response.json()

    try:
        text = data["choices"][0]["message"].get(
            "content",
            ""
        )
    except Exception:
        raise RuntimeError(
            "OpenRouter returned invalid response."
        )

    if isinstance(text, list):
        text = "".join(
            x.get("text", "")
            for x in text
            if isinstance(x, dict)
        )

    if not str(text).strip():
        raise RuntimeError(
            "OpenRouter returned empty response."
        )

    return str(text).strip()


async def ocr_image(image_bytes):
    return await openrouter_chat(
        "استخرج كل النص الظاهر في الصورة حرفيًا "
        "قدر الإمكان. لا تشرح ولا تلخص. "
        "حافظ على ترتيب الأسطر واللغة.",
        system="أنت OCR دقيق. أعد النص فقط.",
        vision_image_bytes=image_bytes,
    )


async def translate_text(text):
    return await openrouter_chat(
        "Translate the following text accurately. "
        "If it is Arabic, translate it to English. "
        "If it is English or another language, "
        "translate it to Arabic:\n\n"
        + text,
        system="You are a professional translator.",
    )


# =========================================================
# IMAGE / FILE HELPERS
# =========================================================

async def remove_background(image_bytes):
    if not REMOVEBG_API_KEY:
        raise RuntimeError(
            "REMOVEBG_API_KEY غير موجود."
        )

    async with httpx.AsyncClient(
        timeout=120
    ) as client:

        response = await client.post(
            "https://api.remove.bg/v1.0/removebg",
            headers={
                "X-Api-Key": REMOVEBG_API_KEY
            },
            files={
                "image_file": (
                    "image.png",
                    image_bytes,
                    "image/png"
                )
            },
            data={
                "size": "auto"
            },
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"remove.bg {response.status_code}: "
            f"{response.text[:300]}"
        )

    return response.content


def local_image(image_bytes, operation):
    image = Image.open(
        io.BytesIO(image_bytes)
    )

    if operation == "compress":

        image.thumbnail(
            (2000, 2000)
        )

        out = io.BytesIO()

        image.convert("RGB").save(
            out,
            "JPEG",
            quality=65,
            optimize=True,
        )

        return out.getvalue(), "compressed.jpg"

    if operation == "convert":

        out = io.BytesIO()

        image.convert("RGBA").save(
            out,
            "PNG",
            optimize=True,
        )

        return out.getvalue(), "converted.png"

    if operation == "enhance":

        image = ImageEnhance.Sharpness(
            image
        ).enhance(1.8)

        image = ImageEnhance.Contrast(
            image
        ).enhance(1.15)

        image = ImageEnhance.Color(
            image
        ).enhance(1.1)

        image = image.filter(
            ImageFilter.UnsharpMask(
                radius=1,
                percent=120
            )
        )

        out = io.BytesIO()

        image.convert("RGB").save(
            out,
            "JPEG",
            quality=95,
        )

        return out.getvalue(), "enhanced.jpg"

    raise ValueError(
        "Unknown image operation."
    )


def images_to_pdf(image_bytes_list):
    images = [
        Image.open(
            io.BytesIO(data)
        ).convert("RGB")
        for data in image_bytes_list
    ]

    out = io.BytesIO()

    if images:
        images[0].save(
            out,
            "PDF",
            save_all=True,
            append_images=images[1:],
        )

    return out.getvalue()


# =========================================================
# OPENAI
# =========================================================

async def openai_image_generate(prompt):
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY غير موجود."
        )

    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=OPENAI_API_KEY
    )

    result = await client.images.generate(
        model=OPENAI_IMAGE_MODEL,
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )

    if not result.data:
        raise RuntimeError(
            "OpenAI لم يرجع صورة."
        )

    image_url = result.data[0].url
    if not image_url:
        raise RuntimeError("OpenAI لم يرجع رابط الصورة.")

    async with httpx.AsyncClient(timeout=60) as client_http:
        resp = await client_http.get(image_url)
        if resp.status_code != 200:
            raise RuntimeError("تعذر تحميل الصورة المولدة من رابط OpenAI.")
        return resp.content


async def openai_edit_image(
    image_bytes,
    prompt
):
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY غير موجود."
        )

    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=OPENAI_API_KEY
    )

    f = tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False
    )

    f.write(image_bytes)
    f.close()

    try:

        with open(f.name, "rb") as image_file:

            result = await client.images.edit(
                model=OPENAI_IMAGE_MODEL,
                image=image_file,
                prompt=prompt,
                size="1024x1024",
            )

        if not result.data:
            raise RuntimeError(
                "OpenAI لم يرجع صورة معدلة."
            )

        image_url = result.data[0].url
        if not image_url:
            raise RuntimeError("OpenAI لم يرجع رابط الصورة المعدلة.")

        async with httpx.AsyncClient(timeout=60) as client_http:
            resp = await client_http.get(image_url)
            if resp.status_code != 200:
                raise RuntimeError("تعذر تحميل الصورة المعدلة من رابط OpenAI.")
            return resp.content

    finally:

        try:
            os.unlink(f.name)
        except OSError:
            pass


async def openai_transcribe(
    audio_bytes,
    filename="voice.ogg"
):
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY غير موجود."
        )

    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=OPENAI_API_KEY
    )

    suffix = os.path.splitext(
        filename
    )[1] or ".ogg"

    f = tempfile.NamedTemporaryFile(
        suffix=suffix,
        delete=False
    )

    f.write(audio_bytes)
    f.close()

    try:

        with open(f.name, "rb") as audio_file:

            result = await client.audio.transcriptions.create(
                model=OPENAI_STT_MODEL,
                file=audio_file,
            )

        return result.text.strip()

    finally:

        try:
            os.unlink(f.name)
        except OSError:
            pass


async def text_to_speech(text):
    f = tempfile.NamedTemporaryFile(
        suffix=".mp3",
        delete=False
    )

    f.close()

    try:

        await edge_tts.Communicate(
            text,
            "ar-SA-HamedNeural"
        ).save(f.name)

        with open(f.name, "rb") as audio:
            return audio.read()

    finally:

        try:
            os.unlink(f.name)
        except OSError:
            pass


# =========================================================
# START
# =========================================================

async def start(update, context):
    register_user(
        update.effective_user
    )

    context.user_data.clear()

    await update.message.reply_text(
        "👋 أهلاً بك في بوت أدوات الذكاء الاصطناعي!\n\n"
        "اختر الأداة المطلوبة:",
        reply_markup=main_menu_kb(
            update.effective_user.id
        ),
    )


# =========================================================
# ADMIN
# =========================================================

def admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "💰 الأسعار",
                callback_data="admin:prices"
            )
        ],
        [
            InlineKeyboardButton(
                "🛠️ تشغيل / إيقاف الأدوات",
                callback_data="admin:tools"
            )
        ],
        [
            InlineKeyboardButton(
                "🎁 الخصومات",
                callback_data="admin:discount"
            )
        ],
        [
            InlineKeyboardButton(
                "⭐ تعديل رصيد مستخدم",
                callback_data="admin:balance"
            )
        ],
        [
            InlineKeyboardButton(
                "📊 الإحصائيات",
                callback_data="admin:stats"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 الرئيسية",
                callback_data="home"
            )
        ],
    ])


async def admin(update, context):
    if update.effective_user.id != OWNER_ID:
        await update.effective_message.reply_text(
            "❌ هذه اللوحة خاصة بالمالك."
        )
        return

    text = (
        "👑 لوحة تحكم المالك\n\n"
        "إدارة الأسعار والأدوات والخصومات."
    )

    # مهم:
    # يعمل سواء جاء الطلب من /admin أو من زر Callback.
    if update.callback_query:

        await update.callback_query.edit_message_text(
            text,
            reply_markup=admin_keyboard()
        )

    else:

        await update.message.reply_text(
            text,
            reply_markup=admin_keyboard()
        )


# =========================================================
# CALLBACKS
# =========================================================

async def callbacks(update, context):

    q = update.callback_query

    await q.answer()

    register_user(q.from_user)

    data = q.data

    # -----------------------------------------------------
    # NO OP
    # -----------------------------------------------------

    if data == "nop":
        return

    # -----------------------------------------------------
    # HOME
    # -----------------------------------------------------

    if data == "home":

        context.user_data.clear()

        await q.edit_message_text(
            "👇 القائمة الرئيسية:",
            reply_markup=main_menu_kb(
                q.from_user.id
            )
        )

        return

    # -----------------------------------------------------
    # BALANCE
    # -----------------------------------------------------

    if data == "balance":

        await q.edit_message_text(
            f"⭐ رصيدك الحالي: "
            f"{get_balance(q.from_user.id)} Stars",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "💳 شراء Stars",
                        callback_data="plans"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 الرئيسية",
                        callback_data="home"
                    )
                ],
            ])
        )

        return

    # -----------------------------------------------------
    # PLANS
    # -----------------------------------------------------

    if data == "plans":

        await q.edit_message_text(
            "💳 اختر باقة Stars:",
            reply_markup=plans_kb()
        )

        return

    # -----------------------------------------------------
    # BUY STARS
    # -----------------------------------------------------

    if data.startswith("buy:"):

        amount = int(
            data.split(":")[1]
        )

        await context.bot.send_invoice(
            chat_id=q.message.chat_id,
            title=f"{amount} Stars",
            description=(
                f"إضافة {amount} Stars "
                "إلى رصيدك داخل البوت"
            ),
            payload=(
                f"stars:{amount}:"
                f"{q.from_user.id}"
            ),
            currency="XTR",
            prices=[
                LabeledPrice(
                    f"{amount} Telegram Stars",
                    amount
                )
            ],
        )

        return

    # -----------------------------------------------------
    # SELECT TOOL
    # -----------------------------------------------------

    if data.startswith("select:"):

        tool = data.split(
            ":",
            1
        )[1]

        if tool not in TOOLS:

            await q.edit_message_text(
                "❌ أداة غير معروفة.",
                reply_markup=back_home()
            )

            return

        if not is_enabled(tool):

            await q.edit_message_text(
                "⏸️ هذه الأداة متوقفة مؤقتًا.",
                reply_markup=back_home()
            )

            return

        context.user_data["pending_tool"] = tool

        # عند اختيار أداة جديدة نحذف بيانات التعديل القديمة.
        context.user_data.pop(
            "edit_prompt",
            None
        )

        price = get_price(tool)

        label = (
            "مجاني 🆓"
            if price == 0
            else f"⭐{price}"
        )

        prompts = {

            "translation":
                "🌐 أرسل النص الذي تريد ترجمته.",

            "text_tools":
                "📝 أرسل النص لتصحيحه وترتيبه.",

            "ocr":
                "🔤 أرسل صورة لاستخراج النص منها.",

            "image_convert":
                "🖼️ أرسل صورة لتحويلها إلى PNG.",

            "image_compress":
                "📦 أرسل صورة لضغط حجمها.",

            "image_to_pdf":
                "📄 أرسل صورة لتحويلها إلى PDF.",

            "pdf_to_images":
                "🖼️ أرسل ملف PDF.",

            "pdf_summary":
                "📄 أرسل ملف PDF لتحليله وتلخيصه.",

            "background_removal":
                "✂️ أرسل صورة لإزالة الخلفية.",

            "tts":
                "🗣️ أرسل النص لتحويله إلى صوت.",

            "stt":
                "🎤 أرسل تسجيلًا صوتيًا أو ملفًا صوتيًا.",

            "image_generation":
                "🎨 أرسل وصف الصورة التي تريد توليدها.",

            "image_edit":
                "🪄 أرسل وصف التعديل أولًا، ثم أرسل الصورة.",

            "image_enhancement":
                "✨ أرسل الصورة لتحسينها.",

            "style_transfer":
                "🎭 أرسل وصف النمط أولًا، ثم أرسل الصورة.",

            "ai_assistant":
                "🧠 اكتب رسالتك وسأجيبك.\n"
                "المحادثة تستمر حتى تضغط الرئيسية.",
        }

        await q.edit_message_text(
            f"{prompts[tool]}\n\n"
            f"💳 التكلفة: {label}",
            reply_markup=back_home()
        )

        return

    # -----------------------------------------------------
    # ADMIN MAIN
    # -----------------------------------------------------

    if data == "admin":

        if q.from_user.id != OWNER_ID:
            return

        await admin(
            update,
            context
        )

        return

    # -----------------------------------------------------
    # ADMIN SECTIONS
    # -----------------------------------------------------

    if data.startswith("admin:"):

        if q.from_user.id != OWNER_ID:
            return

        action = data.split(
            ":",
            1
        )[1]

        # PRICES
        if action == "prices":

            rows = []

            items = list(
                TOOLS.items()
            )

            for i in range(
                0,
                len(items),
                2
            ):

                row = []

                for tool, name in items[
                    i:i + 2
                ]:

                    row.append(
                        InlineKeyboardButton(
                            f"{name} · ⭐{get_price(tool)}",
                            callback_data=(
                                f"setprice:{tool}"
                            )
                        )
                    )

                rows.append(row)

            rows.append([
                InlineKeyboardButton(
                    "🔙 لوحة المالك",
                    callback_data="admin"
                )
            ])

            await q.edit_message_text(
                "💰 الأسعار\n\n"
                "اضغط على الأداة لتغيير سعرها.\n"
                "اكتب 0 لجعلها مجانية.",
                reply_markup=InlineKeyboardMarkup(rows)
            )

            return

        # TOOLS
        if action == "tools":

            rows = []

            items = list(
                TOOLS.items()
            )

            for i in range(
                0,
                len(items),
                2
            ):

                row = []

                for tool, name in items[
                    i:i + 2
                ]:

                    state = (
                        "🟢"
                        if is_enabled(tool)
                        else "🔴"
                    )

                    row.append(
                        InlineKeyboardButton(
                            f"{state} {name}",
                            callback_data=(
                                f"toggle:{tool}"
                            )
                        )
                    )

                rows.append(row)

            rows.append([
                InlineKeyboardButton(
                    "🔙 لوحة المالك",
                    callback_data="admin"
                )
            ])

            await q.edit_message_text(
                "🛠️ تشغيل / إيقاف الأدوات:",
                reply_markup=InlineKeyboardMarkup(rows)
            )

            return

        # DISCOUNT
        if action == "discount":

            enabled, percentage = get_discount()

            state = (
                f"🟢 خصم {percentage}%"
                if enabled
                else "🔴 لا يوجد خصم"
            )

            await q.edit_message_text(
                f"🎁 الخصومات\n\n"
                f"الحالة: {state}",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "➕ تحديد الخصم",
                            callback_data="discount:set"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "❌ إيقاف الخصم",
                            callback_data="discount:off"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔙 لوحة المالك",
                            callback_data="admin"
                        )
                    ],
                ])
            )

            return

        # BALANCE
        if action == "balance":

            context.user_data[
                "admin_action"
            ] = "balance"

            await q.edit_message_text(
                "⭐ أرسل:\n\n"
                "UserID amount\n\n"
                "مثال:\n"
                "123456789 50\n\n"
                "استخدم -50 للخصم."
            )

            return

        # STATS
        if action == "stats":

            c = db()

            users = c.execute(
                "SELECT COUNT(*) x FROM users"
            ).fetchone()["x"]

            operations = c.execute(
                "SELECT COUNT(*) x FROM usage_logs"
            ).fetchone()["x"]

            spent = c.execute(
                """
                SELECT COALESCE(
                    SUM(stars),
                    0
                ) x
                FROM usage_logs
                WHERE status='success'
                """
            ).fetchone()["x"]

            c.close()

            await q.edit_message_text(
                "📊 إحصائيات البوت\n\n"
                f"👤 المستخدمون: {users}\n"
                f"📌 العمليات: {operations}\n"
                f"⭐ Stars المستهلكة: {spent}",
                reply_markup=back_home()
            )

            return

    # -----------------------------------------------------
    # SET DISCOUNT
    # -----------------------------------------------------

    if data == "discount:set":

        if q.from_user.id != OWNER_ID:
            return

        context.user_data[
            "admin_action"
        ] = "discount"

        await q.edit_message_text(
            "🎁 أرسل نسبة الخصم من 1 إلى 100:"
        )

        return

    # -----------------------------------------------------
    # DISCOUNT OFF
    # -----------------------------------------------------

    if data == "discount:off":

        if q.from_user.id != OWNER_ID:
            return

        c = db()

        c.execute(
            """
            UPDATE discount
            SET enabled=0,
                percentage=0
            WHERE id=1
            """
        )

        c.commit()
        c.close()

        await q.edit_message_text(
            "✅ تم إيقاف الخصم.",
            reply_markup=back_home()
        )

        return

    # -----------------------------------------------------
    # TOGGLE TOOL
    # -----------------------------------------------------

    if data.startswith("toggle:"):

        if q.from_user.id != OWNER_ID:
            return

        tool = data.split(
            ":",
            1
        )[1]

        if tool in TOOLS:

            set_enabled(
                tool,
                not is_enabled(tool)
            )

        await q.edit_message_text(
            "✅ تم تغيير حالة الأداة.",
            reply_markup=back_home()
        )

        return

    # -----------------------------------------------------
    # SET PRICE
    # -----------------------------------------------------

    if data.startswith("setprice:"):

        if q.from_user.id != OWNER_ID:
            return

        tool = data.split(
            ":",
            1
        )[1]

        if tool not in TOOLS:
            return

        context.user_data[
            "admin_action"
        ] = "price"

        context.user_data[
            "price_tool"
        ] = tool

        await q.edit_message_text(
            f"💰 السعر الحالي:\n"
            f"{TOOLS[tool]} = ⭐{get_price(tool)}\n\n"
            "أرسل السعر الجديد.\n"
            "0 = مجاني"
        )

        return


# =========================================================
# PAYMENTS
# =========================================================

async def precheckout(update, context):

    query = update.pre_checkout_query

    payload = query.invoice_payload

    if not payload.startswith("stars:"):

        await query.answer(
            ok=False,
            error_message="فاتورة غير صالحة."
        )

        return

    try:

        _, amount, target = payload.split(":")

        amount = int(amount)
        target = int(target)

        if (
            target != query.from_user.id
            or amount <= 0
        ):

            await query.answer(
                ok=False,
                error_message="بيانات الفاتورة غير صحيحة."
            )

            return

        await query.answer(
            ok=True
        )

    except Exception:

        await query.answer(
            ok=False,
            error_message="فاتورة غير صالحة."
        )


async def successful_payment(update, context):

    payment = update.message.successful_payment

    payload = payment.invoice_payload

    if not payload.startswith("stars:"):
        return

    try:

        _, amount, target = payload.split(":")

        amount = int(amount)
        target = int(target)

    except Exception:

        await update.message.reply_text(
            "❌ تعذر قراءة بيانات الدفع."
        )

        return

    if target != update.effective_user.id:
        return

    charge_id = (
        payment.telegram_payment_charge_id
    )

    c = db()

    # يمنع إضافة الرصيد مرتين لنفس عملية الدفع.
    existing = c.execute(
        """
        SELECT charge_id
        FROM payments
        WHERE charge_id=?
        """,
        (charge_id,)
    ).fetchone()

    if existing:

        c.close()

        await update.message.reply_text(
            "ℹ️ هذه العملية تمت إضافتها سابقًا."
        )

        return

    c.execute(
        """
        INSERT INTO payments(
            charge_id,
            user_id,
            amount,
            created_at
        )
        VALUES(?, ?, ?, ?)
        """,
        (
            charge_id,
            target,
            amount,
            datetime.now().isoformat(
                timespec="seconds"
            ),
        )
    )

    c.commit()
    c.close()

    change_balance(
        target,
        amount
    )

    log_usage(
        target,
        "telegram_stars_purchase",
        -amount,
        "purchase"
    )

    await update.message.reply_text(
        "✅ تم الشراء بنجاح!\n\n"
        f"➕ تمت إضافة ⭐{amount}\n"
        f"⭐ رصيدك الحالي: "
        f"{get_balance(target)}",
        reply_markup=main_menu_kb(target)
    )


# =========================================================
# TEXT HANDLER
# =========================================================

async def text_handler(update, context):

    user = update.effective_user

    register_user(user)

    text = (
        update.message.text or ""
    ).strip()

    if not text:
        return

    # -----------------------------------------------------
    # ADMIN ACTIONS
    # -----------------------------------------------------

    if (
        user.id == OWNER_ID
        and context.user_data.get("admin_action")
    ):

        action = context.user_data[
            "admin_action"
        ]

        # PRICE
        if action == "price":

            try:

                value = int(text)

                if value < 0:
                    raise ValueError

            except ValueError:

                await update.message.reply_text(
                    "❌ أرسل رقمًا صحيحًا."
                )

                return

            tool = context.user_data.get(
                "price_tool"
            )

            if tool in TOOLS:
                set_price(
                    tool,
                    value
                )

            context.user_data.clear()

            await update.message.reply_text(
                "✅ تم تعديل السعر.",
                reply_markup=main_menu_kb(
                    user.id
                )
            )

            return

        # BALANCE
        if action == "balance":

            try:

                target, amount = map(
                    int,
                    text.split()
                )

            except Exception:

                await update.message.reply_text(
                    "❌ الصيغة:\n"
                    "UserID amount"
                )

                return

            # نتأكد أن المستخدم موجود.
            if get_balance(target) == 0:

                c = db()

                exists = c.execute(
                    """
                    SELECT user_id
                    FROM users
                    WHERE user_id=?
                    """,
                    (target,)
                ).fetchone()

                c.close()

                if not exists:

                    await update.message.reply_text(
                        "❌ المستخدم غير موجود في قاعدة البيانات."
                    )

                    return

            change_balance(
                target,
                amount
            )

            context.user_data.clear()

            await update.message.reply_text(
                "✅ تم تعديل الرصيد.\n"
                f"⭐ الرصيد الحالي: "
                f"{get_balance(target)}",
                reply_markup=main_menu_kb(
                    user.id
                )
            )

            return

        # DISCOUNT
        if action == "discount":

            try:

                percentage = int(text)

                if not 0 <= percentage <= 100:
                    raise ValueError

            except ValueError:

                await update.message.reply_text(
                    "❌ أرسل نسبة من 0 إلى 100."
                )

                return

            c = db()

            if percentage == 0:

                c.execute(
                    """
                    UPDATE discount
                    SET enabled=0,
                        percentage=0
                    WHERE id=1
                    """
                )

            else:

                c.execute(
                    """
                    UPDATE discount
                    SET enabled=1,
                        percentage=?
                    WHERE id=1
                    """,
                    (percentage,)
                )

            c.commit()
            c.close()

            context.user_data.clear()

            await update.message.reply_text(
                "✅ تم تحديث الخصم.",
                reply_markup=main_menu_kb(
                    user.id
                )
            )

            return

    # -----------------------------------------------------
    # GET CURRENT TOOL
    # -----------------------------------------------------

    tool = context.user_data.get(
        "pending_tool"
    )

    if not tool:

        await update.message.reply_text(
            "يرجى اختيار أداة أولًا:",
            reply_markup=main_menu_kb(
                user.id
            )
        )

        return

    # -----------------------------------------------------
    # TRANSLATION
    # -----------------------------------------------------

    if tool == "translation":

        reserved, price = await require_credits(
            update,
            tool
        )

        if not reserved:
            return

        try:

            result = await translate_text(
                text
            )

            complete_charge(
                user.id,
                tool,
                price
            )

            await update.message.reply_text(
                "🌐 الترجمة:\n\n"
                + result,
                reply_markup=back_home()
            )

        except Exception as e:

            refund_credits(
                user.id,
                tool,
                price
            )

            raise e

        return

    # -----------------------------------------------------
    # TEXT TOOLS
    # -----------------------------------------------------

    if tool == "text_tools":

        reserved, price = await require_credits(
            update,
            tool
        )

        if not reserved:
            return

        try:

            result = await openrouter_chat(
                "صحح النص التالي لغويًا ورتبه "
                "مع الحفاظ على المعنى. "
                "أعد النص المصحح فقط:\n\n"
                + text,
                system=(
                    "أنت مدقق لغوي عربي محترف."
                ),
            )

            complete_charge(
                user.id,
                tool,
                price
            )

            await update.message.reply_text(
                "📝 النص المصحح:\n\n"
                + result,
                reply_markup=back_home()
            )

        except Exception as e:

            refund_credits(
                user.id,
                tool,
                price
            )

            raise e

        return

    # -----------------------------------------------------
    # TTS
    # -----------------------------------------------------

    if tool == "tts":

        reserved, price = await require_credits(
            update,
            tool
        )

        if not reserved:
            return

        try:

            audio = await text_to_speech(
                text
            )

            complete_charge(
                user.id,
                tool,
                price
            )

            await update.message.reply_audio(
                audio=io.BytesIO(audio),
                caption=(
                    "🗣️ تم تحويل النص إلى صوت.\n"
                    f"⭐ التكلفة: {price}"
                ),
                reply_markup=back_home()
            )

        except Exception as e:

            refund_credits(
                user.id,
                tool,
                price
            )

            raise e

        return

    # -----------------------------------------------------
    # AI ASSISTANT
    # -----------------------------------------------------

    if tool == "ai_assistant":

        reserved, price = await require_credits(
            update,
            tool
        )

        if not reserved:
            return

        try:

            history = context.user_data.setdefault(
                "ai_history",
                []
            )

            history.append({
                "role": "user",
                "content": text
            })

            # نحتفظ بآخر 12 رسالة فقط.
            history = history[-12:]

            context.user_data[
                "ai_history"
            ] = history

            messages_text = []

            for item in history:

                role = (
                    "المستخدم"
                    if item["role"] == "user"
                    else "المساعد"
                )

                messages_text.append(
                    f"{role}: {item['content']}"
                )

            prompt = (
                "هذه محادثة مستمرة.\n\n"
                + "\n\n".join(messages_text)
                + "\n\nأجب على آخر رسالة."
            )

            result = await openrouter_chat(
                prompt,
                system=(
                    "أنت مساعد AI متقدم. "
                    "حافظ على سياق المحادثة "
                    "وأجب بالعربية بوضوح."
                ),
            )

            history.append({
                "role": "assistant",
                "content": result
            })

            context.user_data[
                "ai_history"
            ] = history[-12:]

            complete_charge(
                user.id,
                tool,
                price
            )

            await update.message.reply_text(
                "🧠 " + result,
                reply_markup=back_home()
            )

        except Exception as e:

            # نحذف آخر رسالة مستخدم إذا فشلت العملية.
            if context.user_data.get(
                "ai_history"
            ):
                context.user_data[
                    "ai_history"
                ].pop()

            refund_credits(
                user.id,
                tool,
                price
            )

            raise e

        return

    # -----------------------------------------------------
    # IMAGE GENERATION
    # -----------------------------------------------
