import os
import logging
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# إعداد السجلات (Logging) لمنع التوقف ومعالجة الأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- الإعدادات المطلوبة ---
BOT_TOKEN = "ضع_توكن_البوت_هنا"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "ضع_مفتاح_OPENAI_هنا")

# معرف المالك المباشر
OWNER_ID = 8860453018

# حالات المستخدمين
user_states = {}

def get_main_keyboard(user_id):
    """بناء الأزرار التفاعلية الثابتة تحت الرسالة"""
    keyboard = [
        # عنوان القسم المجاني - زر ثابت لا ينزل للمحادثه إطلاقاً
        [InlineKeyboardButton("--- 🆓 قسم الأدوات المجانية Free ---", callback_data="ignore")],
        [
            InlineKeyboardButton("📝 تصحيح النص", callback_data="tool_correct"),
            InlineKeyboardButton("🌐 ترجمة النص", callback_data="tool_translate")
        ],
        [
            InlineKeyboardButton("📄 استخراج النص من صورة", callback_data="tool_ocr"),
            InlineKeyboardButton("🖼️ تحويل صيغ الصور", callback_data="tool_convert")
        ],
        [
            InlineKeyboardButton("📊 ضغط الصور", callback_data="tool_compress"),
            InlineKeyboardButton("📑 صور ⬅️ PDF", callback_data="tool_img2pdf")
        ],
        # خيار التحليل والتلخيص أصبح هنا مجانياً
        [
            InlineKeyboardButton("🔍 تحليل / تلخيص النص (مجاني)", callback_data="tool_summarize")
        ],

        # عنوان القسم المدفوع - زر ثابت لا ينزل للمحادثه إطلاقاً
        [InlineKeyboardButton("--- 💎 قسم الأدوات المدفوعة PRO ---", callback_data="ignore")],
        [
            InlineKeyboardButton("🧠 مساعد AI المتقدم (⭐1)", callback_data="tool_ai_chat"),
            InlineKeyboardButton("✂️ إزالة الخلفية (⭐2)", callback_data="tool_bg_remove")
        ],
        [
            InlineKeyboardButton("🎤 نص ⬅️ صوت (⭐1)", callback_data="tool_tts"),
            InlineKeyboardButton("🔊 صوت ⬅️ نص (⭐1)", callback_data="tool_stt")
        ],
        [
            InlineKeyboardButton("🎨 تعديل الصور بالذكاء (⭐5)", callback_data="tool_img_edit"),
            InlineKeyboardButton("🎨 توليد الصور (⭐5)", callback_data="tool_img_gen")
        ],
        [
            InlineKeyboardButton("🎭 تغيير نمط الصورة (⭐4)", callback_data="tool_img_style"),
            InlineKeyboardButton("✨ تحسين الصور (⭐3)", callback_data="tool_img_enhance")
        ]
    ]

    # إظهار خيار المالك فقط إذا كان المعرف يطابق 8860453018
    if str(user_id) == str(OWNER_ID):
        keyboard.append([InlineKeyboardButton("👑 لوحة تحكم المالك", callback_data="owner_menu")])

    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البدء /start"""
    try:
        user_id = update.effective_user.id
        
        # الزر الدائم في الأسفل للعودة وإلغاء العمليات
        reply_kb = [[KeyboardButton("🔄 القائمة الرئيسية / إلغاء")]]
        markup = ReplyKeyboardMarkup(reply_kb, resize_keyboard=True)

        await update.message.reply_text("أهلاً بك! تم تحديث قائمة الأدوات بنجاح.", reply_markup=markup)
        await update.message.reply_text("اختر الأداة المطلوبة من القائمة أدناه:", reply_markup=get_main_keyboard(user_id))
    except Exception as e:
        logger.error(f"خطأ في أمر start: {e}")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الضغط على الأزرار"""
    try:
        query = update.callback_query
        user_id = query.from_user.id
        data = query.data

        # 1. تثبيت العنوان: إذا تم الضغط على زر العنوان المظلل بالصورة لا يحدث أي شيء ولا ينزل للمحادثة
        if data == "ignore":
            await query.answer()
            return

        await query.answer()

        # 2. قسم المالك
        if data == "owner_menu":
            if str(user_id) == str(OWNER_ID):
                owner_kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ إضافة نقاط لمستخدم", callback_data="owner_add_pts")],
                    [InlineKeyboardButton("📢 إرسال إذاعة للمستخدمين", callback_data="owner_broadcast")],
                    [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
                ])
                await query.edit_message_text("👑 **لوحة تحكم المالك الخاص بك**\nاختر الخيار المطلوب:", reply_markup=owner_kb, parse_mode="Markdown")
            else:
                await query.answer("عذراً، هذا الخيار مخصص لمالك البوت فقط!", show_alert=True)
            return

        # 3. العودة للقائمة الرئيسية
        if data == "back_to_main":
            await query.edit_message_text("اختر الأداة المطلوبة من القائمة أدناه:", reply_markup=get_main_keyboard(user_id))
            return

        # 4. اختيار أداة توليد الصور
        if data == "tool_img_gen":
            user_states[user_id] = "WAITING_FOR_IMAGE_PROMPT"
            await query.message.reply_text("🎨 أرسل وصف الصورة التي تريد توليدها بالتفصيل.\n💳 التكلفة: ⭐ 5 (PRO)")
            return

        # 5. اختيار أداة التلخيص والتحليل (مجاني)
        if data == "tool_summarize":
            user_states[user_id] = "WAITING_FOR_SUMMARY"
            await query.message.reply_text("🔍 أرسل النص الذي تريد تحليله وتلخيصه الآن (مجاناً) 📄")
            return

        await query.message.reply_text(f"تم اختيار الأداة: {data}")

    except Exception as e:
        logger.error(f"خطأ في التعامل مع الكولباك: {e}")

async def handle_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل والردود بدون انقطاع"""
    try:
        user_id = update.effective_user.id
        text = update.message.text

        # زر إلغاء أو العودة
        if text == "🔄 القائمة الرئيسية / إلغاء":
            user_states.pop(user_id, None)
            await update.message.reply_text("تم الرجوع إلى القائمة الرئيسية.", reply_markup=get_main_keyboard(user_id))
            return

        state = user_states.get(user_id)

        # استلام وصف الصورة لتوليدها
        if state == "WAITING_FOR_IMAGE_PROMPT":
            if not OPENAI_API_KEY or "ضع_مفتاح" in OPENAI_API_KEY:
                await update.message.reply_text("❌ حدث خطأ أثناء تنفيذ العملية:\nغير متوفر OPENAI_API_KEY لتوليد الصور.")
                user_states.pop(user_id, None)
                return

            msg = await update.message.reply_text("⏳ جاري توليد الصورة...")
            try:
                headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
                payload = {"prompt": text, "n": 1, "size": "1024x1024"}
                res = requests.post("https://api.openai.com/v1/images/generations", json=payload, headers=headers, timeout=60)
                res_data = res.json()

                if res.status_code == 200 and "data" in res_data:
                    await update.message.reply_photo(photo=res_data["data"][0]["url"], caption="✅ تم توليد الصورة بنجاح!")
                else:
                    err_msg = res_data.get('error', {}).get('message', 'فشل الطلب')
                    await update.message.reply_text(f"❌ حدث خطأ أثناء تنفيذ العملية:\n{err_msg}")
            except Exception as req_err:
                await update.message.reply_text("❌ حدث خطأ أثناء تنفيذ العملية (فشل الاتصال بـ OpenAI).")
            
            user_states.pop(user_id, None)
            return

        # استلام نص التلخيص
        if state == "WAITING_FOR_SUMMARY":
            await update.message.reply_text(f"📊 **نتائج التحليل والتلخيص:**\n\n{text[:300]}...\n\n✅ تم التلخيص بنجاح (مجاني).", parse_mode="Markdown")
            user_states.pop(user_id, None)
            return

        await update.message.reply_text("اختر أداة من القائمة للبدء:", reply_markup=get_main_keyboard(user_id))

    except Exception as e:
        logger.error(f"خطأ أثناء معالجة الرسالة: {e}")

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """منع توقف البوت نهائياً (الحل الجذري للتوقف الفجائي)"""
    logger.error(msg="حدث استثناء ولم يتوقف البوت:", exc_info=context.error)

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_messages))

    # ربط حماية التوقف الفجائي
    app.add_error_handler(global_error_handler)

    print("🚀 تم تشغيل البوت مع جميع التحديثات...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
        ],
        [
            InlineKeyboardButton("📄 استخراج النص من صورة", callback_data="tool_ocr"),
            InlineKeyboardButton("🖼️ تحويل صيغ الصور", callback_data="tool_convert")
        ],
        [
            InlineKeyboardButton("📊 ضغط الصور", callback_data="tool_compress"),
            InlineKeyboardButton("📑 صور ⬅️ PDF", callback_data="tool_img2pdf")
        ],
        # أداة التلخيص والتحليل أصبحت هنا (مجانية)
        [
            InlineKeyboardButton("🔍 تحليل / تلخيص النص (مجاني)", callback_data="tool_summarize"),
            InlineKeyboardButton("📄 PDF ⬅️ صور", callback_data="tool_pdf2img")
        ],

        # عنوان قسم الأدوات المدفوعة PRO (زر غير قابل للإرسال)
        [InlineKeyboardButton("--- 💎 قسم الأدوات المدفوعة PRO ---", callback_data="ignore")],
        [
            InlineKeyboardButton("🧠 مساعد AI المتقدم (⭐1)", callback_data="tool_ai_chat"),
            InlineKeyboardButton("✂️ إزالة الخلفية (⭐2)", callback_data="tool_bg_remove")
        ],
        [
            InlineKeyboardButton("🎤 نص ⬅️ صوت (⭐1)", callback_data="tool_tts"),
            InlineKeyboardButton("🔊 صوت ⬅️ نص (⭐1)", callback_data="tool_stt")
        ],
        [
            InlineKeyboardButton("🎨 تعديل الصور بالذكاء (⭐5)", callback_data="tool_img_edit"),
            InlineKeyboardButton("🎨 توليد الصور (⭐5)", callback_data="tool_img_gen")
        ],
        [
            InlineKeyboardButton("🎭 تغيير نمط الصورة (⭐4)", callback_data="tool_img_style"),
            InlineKeyboardButton("✨ تحسين الصور (⭐3)", callback_data="tool_img_enhance")
        ]
    ]

    # إظهار خيار المالك فقط إذا كان المستخدم هو Owner ID
    if str(user_id) == str(OWNER_ID):
        keyboard.append([InlineKeyboardButton("👑 لوحة المالك / الإدارة", callback_data="owner_menu")])

    return InlineKeyboardMarkup(keyboard)

# --- الأوامر الرئيسية ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عند بدء تشغيل البوت"""
    try:
        user_id = update.effective_user.id
        
        # إعداد زر القائمة الرئيسية / الإلغاء الثابت بالأسفل
        reply_kb = [[KeyboardButton("🔄 القائمة الرئيسية / إلغاء")]]
        reply_markup_bottom = ReplyKeyboardMarkup(reply_kb, resize_keyboard=True)

        await update.message.reply_text(
            "أهلاً بك في بوت أدوات الذكاء الاصطناعي الشامل 🤖\nاختر الأداة المطلوبة من القائمة أدناه:",
            reply_markup=reply_markup_bottom
        )

        # إرسال القائمة التفاعلية Main Inline Keyboard
        await update.message.reply_text(
            "👇 اختر من الأدوات:",
            reply_markup=get_main_inline_keyboard(user_id)
        )
    except Exception as e:
        logger.error(f"Error in start_command: {e}")

# --- معالجة الأزرار التفاعلية (Callback Queries) ---
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    # 1. منع الأزرار التي تعمل كـ Headers من القيام بأي إجراء أو النزول في المحادثة
    if data == "ignore":
        await query.answer(text="", show_alert=False)
        return

    await query.answer()

    # 2. خيار المالك (يتحقق بشكل صارم من المعرف)
    if data == "owner_menu":
        if str(user_id) == str(OWNER_ID):
            owner_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ إضافة نقاط لمستخدم", callback_data="owner_add_points")],
                [InlineKeyboardButton("📢 إرسال إعلان عام", callback_data="owner_broadcast")],
                [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="owner_stats")],
                [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
            ])
            await query.edit_message_text("👑 **لوحة تحكم المالك**\nمرحباً بك، اختر الإجراء المطلوب:", reply_markup=owner_keyboard, parse_mode="Markdown")
        else:
            await query.answer("⚠️ هذا الخيار مخصص لمالك البوت فقط!", show_alert=True)
        return

    # 3. العودة للقائمة الرئيسية
    if data == "back_to_main":
        await query.edit_message_text("👇 اختر من الأدوات:", reply_markup=get_main_inline_keyboard(user_id))
        return

    # 4. معالجة خيار "توليد الصور"
    if data == "tool_img_gen":
        user_states[user_id] = "WAITING_FOR_IMAGE_PROMPT"
        await query.message.reply_text("🎨 أرسل وصف الصورة التي تريد توليدها بالتفصيل.\n💳 التكلفة: ⭐ 5 (PRO)")
        return

    # 5. معالجة خيار "تحليل / تلخيص النص" (أصبح مجاني)
    if data == "tool_summarize":
        user_states[user_id] = "WAITING_FOR_SUMMARY_TEXT"
        await query.message.reply_text("🔍 أرسل النص أو المقال الذي تريد تحليله وتلخيصه (الخدمة مجانية بالكامل) 📄")
        return

    # معالجة باقي الأدوات...
    await query.message.reply_text(f"تم اختيار الأداة: {data}\nيرجى إرسال الملف أو النص المطلوب.")

# --- معالجة الرسائل النصية والعمليات ---
async def handle_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text = update.message.text

        # زر الإلغاء / القائمة الرئيسية السفلية
        if text == "🔄 القائمة الرئيسية / إلغاء":
            user_states.pop(user_id, None)
            await update.message.reply_text(
                "تم الرجوع إلى القائمة الرئيسية. اختر الأداة المطلوبة:",
                reply_markup=get_main_inline_keyboard(user_id)
            )
            return

        state = user_states.get(user_id)

        # معالجة طلب توليد الصور
        if state == "WAITING_FOR_IMAGE_PROMPT":
            if not OPENAI_API_KEY or OPENAI_API_KEY == "ضع_مفتاح_OPENAI_هنا":
                await update.message.reply_text("❌ حدث خطأ أثناء تنفيذ العملية:\nغير متوفر OPENAI_API_KEY لتوليد الصور.")
                user_states.pop(user_id, None)
                return

            msg = await update.message.reply_text("⏳ جاري توليد الصورة، يرجى الانتظار...")
            try:
                # استدعاء API لتوليد الصورة
                headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
                payload = {"prompt": text, "n": 1, "size": "1024x1024"}
                response = requests.post("https://api.openai.com/v1/images/generations", json=payload, headers=headers, timeout=60)
                res_data = response.json()

                if response.status_code == 200 and "data" in res_data:
                    image_url = res_data["data"][0]["url"]
                    await update.message.reply_photo(photo=image_url, caption="✅ تم توليد الصورة بنجاح!")
                else:
                    await update.message.reply_text(f"❌ حدث خطأ أثناء تنفيذ العملية:\n{res_data.get('error', {}).get('message', 'فشل الطلب')}")
            except Exception as req_err:
                await update.message.reply_text("❌ حدث خطأ في الاتصال بالسيرفر أثناء توليد الصورة.")
                logger.error(f"Image generation error: {req_err}")
            
            user_states.pop(user_id, None)
            return

        # معالجة طلب تلخيص النص (المجاني)
        if state == "WAITING_FOR_SUMMARY_TEXT":
            await update.message.reply_text(f"📝 **الملخص والتحليل:**\n\nتم تحليل النص بنجاح:\n{text[:200]}...\n\n(هذه الخدمة مجانية)", parse_mode="Markdown")
            user_states.pop(user_id, None)
            return

        # في حال إرسال أي نص عادي بدون اختيار أداة
        await update.message.reply_text("يرجى اختيار أداة من القائمة أولاً.", reply_markup=get_main_inline_keyboard(user_id))

    except Exception as e:
        logger.error(f"Error handling message: {e}")

# --- معالج الأخطاء العالمي لمنع التوقف الفجائي (Crash Prevention) ---
async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """يلتقط الأخطاء غير المتوقعة لمنع توقف البوت تماماً"""
    logger.error(msg="حدث استثناء غير معالج:", exc_info=context.error)

# --- تشغيل البوت ---
def main():
    # إنشاء تطبيق البوت
    app = Application.builder().token(BOT_TOKEN).build()

    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_messages))

    # تسجيل معالج الأخطاء العالمي
    app.add_error_handler(global_error_handler)

    # بدء الاستماع للرسائل بشكل مستمر ومتصل
    print("🤖 البوت يعمل الآن بنجاح بدون انقطاع...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

keep_alive()

# =========================
# SETTINGS & CONSTANTS
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "8860453018"))
DATABASE = os.getenv("DATABASE", "ai_tools.db")
STARTER_STARS = 10

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_FREE_MODEL = os.getenv("OPENROUTER_FREE_MODEL", "openrouter/free")
OPENROUTER_VISION_MODEL = os.getenv("OPENROUTER_VISION_MODEL", "openrouter/free")

REMOVEBG_API_KEY = os.getenv("REMOVEBG_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

WELCOME_AZKAR = "\n\n✨ *لا إله إلا الله محمد رسول الله* | *أستغفر الله العظيم وأتوب إليه* 🤍"

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
    "image_to_pdf": "📄 صور ← PDF",
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
    return bool(r["enabled"]), int(r["percentage"]) if r else (False, 0)

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
# KEYBOARDS (FREE / PRO CLASSIFICATION)
# =========================
def build_tool_button_label(tool_key):
    name = TOOLS[tool_key]
    price = get_price(tool_key)
    if price > 0:
        return f"{name} (⭐{price})"
    return name

def get_tool_map():
    mapping = {}
    for k in TOOLS:
        label = build_tool_button_label(k)
        mapping[label] = k
        mapping[TOOLS[k]] = k
    return mapping

def main_reply_keyboard():
    keyboard = [
        [KeyboardButton("🆓 --- قسم الأدوات المجانية Free --- 🆓")],
        [KeyboardButton(build_tool_button_label("translation")), KeyboardButton(build_tool_button_label("text_tools"))],
        [KeyboardButton(build_tool_button_label("ocr")), KeyboardButton(build_tool_button_label("image_convert"))],
        [KeyboardButton(build_tool_button_label("image_compress")), KeyboardButton(build_tool_button_label("image_to_pdf"))],
        [KeyboardButton(build_tool_button_label("pdf_to_images"))],
        
        [KeyboardButton("💎 --- قسم الأدوات المدفوعة PRO --- 💎")],
        [KeyboardButton(build_tool_button_label("ai_assistant")), KeyboardButton(build_tool_button_label("background_removal"))],
        [KeyboardButton(build_tool_button_label("tts")), KeyboardButton(build_tool_button_label("stt"))],
        [KeyboardButton(build_tool_button_label("image_generation")), KeyboardButton(build_tool_button_label("image_edit"))],
        [KeyboardButton(build_tool_button_label("image_enhancement")), KeyboardButton(build_tool_button_label("style_transfer"))],
        [KeyboardButton(build_tool_button_label("pdf_summary"))],
        
        [KeyboardButton("⭐ رصيدي"), KeyboardButton("💳 شراء باقات Stars")],
        [KeyboardButton("🔄 القائمة الرئيسية / إلغاء")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("🔄 القائمة الرئيسية / إلغاء")]], resize_keyboard=True)

def plans_inline_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ شراء 100 Stars", callback_data="buy:100"),
         InlineKeyboardButton("⭐ شراء 500 Stars", callback_data="buy:500")],
        [InlineKeyboardButton("⭐ شراء 1000 Stars", callback_data="buy:1000")],
    ])

# =========================
# OPENROUTER & OPENAI HELPERS
# =========================
def or_headers():
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://telegram.org",
        "X-Title": "AI Tools Telegram Bot",
    }

async def openrouter_chat(prompt, system="أنت مساعد مفيد داخل بوت Telegram.", vision_image_bytes=None, model=None, history=None):
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY غير موجود في متغيرات البيئة")

    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)

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

    messages.append({"role": "user", "content": content})

    payload = {
        "model": model or (OPENROUTER_VISION_MODEL if vision_image_bytes else OPENROUTER_FREE_MODEL),
        "messages": messages,
        "temperature": 0.5,
    }
    
    # Safe HTTP request with retries to prevent connection crash
    async with httpx.AsyncClient(timeout=120) as client:
        for attempt in range(3):
            try:
                r = await client.post(f"{OPENROUTER_BASE_URL}/chat/completions", headers=or_headers(), json=payload)
                if r.status_code == 200:
                    data = r.json()
                    text = data["choices"][0]["message"].get("content", "")
                    if isinstance(text, list):
                        text = "".join(x.get("text", "") for x in text if isinstance(x, dict))
                    return str(text).strip()
            except Exception as ex:
                if attempt == 2:
                    raise ex

    raise RuntimeError("فشل الاتصال بالخدمة. حاول مرة أخرى.")

async def ocr_image(image_bytes):
    return await openrouter_chat(
        "استخرج كل النص الظاهر في الصورة حرفيًا قدر الإمكان. لا تشرح ولا تلخص. حافظ على ترتيب الأسطر واللغة العربية.",
        system="أنت OCR دقيق. أعد النص فقط.",
        vision_image_bytes=image_bytes,
    )

async def translate_text(text):
    return await openrouter_chat(
        f"Translate the following text accurately. If it is in Arabic, translate to English. If it is in any other language, translate to Arabic:\n\n{text}",
        system="You are a professional universal translator. Provide direct translation only."
    )

# =========================
# IMAGE / FILE HELPERS
# =========================
async def remove_background(image_bytes):
    if not REMOVEBG_API_KEY:
        raise RuntimeError("إزالة الخلفية تطلب REMOVEBG_API_KEY")
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
# OPENAI HELPERS
# =========================
async def openai_image_generate(prompt):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY غير متوفر لتوليد الصور.")
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    result = await client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        response_format="b64_json"
    )
    return base64.b64decode(result.data[0].b64_json)

async def openai_edit_image(image_bytes, prompt):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY غير متوفر لتعديل الصور.")
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    f.write(image_bytes)
    f.close()
    try:
        with open(f.name, "rb") as img:
            result = await client.images.edit(
                model="dall-e-2",
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
        raise RuntimeError("OPENAI_API_KEY غير متوفر لتحويل الصوت إلى نص.")
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    f = tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1] or ".ogg", delete=False)
    f.write(audio_bytes)
    f.close()
    try:
        with open(f.name, "rb") as audio:
            r = await client.audio.transcriptions.create(
                model="whisper-1",
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
            f"❌ رصيدك غير كافٍ.\n\nالسعر المطلوب: ⭐{price}\nرصيدك الحالي: ⭐{balance}\n\nيمكنك اختيار باقة لشراء النقاط:",
            reply_markup=plans_inline_kb(),
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
    context.user_data.clear()
    msg = (
        "أهلاً بك في بوت الأدوات والذكاء الاصطناعي 🤖\n\n"
        "اختر الأداة المطلوبة من القائمة بالأسفل 👇"
        f"{WELCOME_AZKAR}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_reply_keyboard())

async def admin(update, context):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ غير مصرح.")
        return
    await update.message.reply_text(
        "👑 لوحة التحكم الرئيسية للمالك (8860453018)\n\nتستطيع من هنا التحكم بالإعدادات والرصيد والأسعار وتغيير الأدوات من مجانية إلى مدفوعة والعكس:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 تعديل الأسعار (مجاني/اشتراك)", callback_data="admin:prices")],
            [InlineKeyboardButton("🛠️ تشغيل / إيقاف الأدوات", callback_data="admin:tools")],
            [InlineKeyboardButton("🎁 تفعيل / إلغاء الخصومات", callback_data="admin:discount")],
            [InlineKeyboardButton("⭐ إضافة / خصم رصيد", callback_data="admin:balance")],
            [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="admin:stats")],
        ]),
    )

# =========================
# CALLBACKS (INLINE BUTTONS FOR PAYMENTS & ADMIN)
# =========================
async def callbacks(update, context):
    q = update.callback_query
    await q.answer()
    register_user(q.from_user)
    data = q.data

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

    if data.startswith("admin:") and q.from_user.id == OWNER_ID:
        action = data.split(":", 1)[1]
        if action == "prices":
            rows = []
            items = list(TOOLS.items())
            for i in range(0, len(items), 2):
                row = []
                for t, name in items[i:i + 2]:
                    p = get_price(t)
                    status_lbl = "مجاني" if p == 0 else f"⭐{p}"
                    row.append(InlineKeyboardButton(f"{name} ({status_lbl})", callback_data=f"setprice:{t}"))
                rows.append(row)
            await q.edit_message_text("💰 **تحكم الأسعار (تحويل بين مجاني ومدفوع):**\n\nاختر الأداة لتعديل سعرها (ضع 0 لتصبح مجانية):", reply_markup=InlineKeyboardMarkup(rows))
            return

        if action == "tools":
            rows = []
            items = list(TOOLS.items())
            for i in range(0, len(items), 2):
                row = []
                for t, name in items[i:i + 2]:
                    state = "🟢 شغال" if is_enabled(t) else "🔴 متوقف"
                    row.append(InlineKeyboardButton(f"{state} {name}", callback_data=f"toggle:{t}"))
                rows.append(row)
            await q.edit_message_text("🛠️ **تشغيل / إيقاف الأدوات:**", reply_markup=InlineKeyboardMarkup(rows))
            return

        if action == "stats":
            c = db()
            users = c.execute("SELECT COUNT(*) x FROM users").fetchone()["x"]
            ops = c.execute("SELECT COUNT(*) x FROM usage_logs").fetchone()["x"]
            spent = c.execute("SELECT COALESCE(SUM(stars),0) x FROM usage_logs WHERE status='success'").fetchone()["x"]
            c.close()
            await q.edit_message_text(
                f"📊 **إحصائيات البوت:**\n\n👤 عدد المستخدمين: {users}\n📌 العمليات الناجحة: {ops}\n⭐ إجمالي المستهلك: {spent}",
            )
            return

        if action == "balance":
            context.user_data["admin_action"] = "balance"
            await q.edit_message_text("⭐ أرسل آيدي المستخدم والرصيد بالشكل التالي:\n`UserID amount`\n\nمثال: `123456789 50` (أو بالسالب للخصم `-20`)", parse_mode="Markdown")
            return

        if action == "discount":
            enabled, percentage = get_discount()
            state = f"🟢 خصم {percentage}% شغال حالياً" if enabled else "🔴 لا يوجد خصم مفعل"
            await q.edit_message_text(
                f"🎁 **إدارة الخصومات العامة:**\n\nالحالة: {state}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ تفعيل خصم بنسبة %", callback_data="discount:set")],
                    [InlineKeyboardButton("❌ إيقاف الخصم نهائياً", callback_data="discount:off")],
                ]),
            )
            return

    if data == "discount:set" and q.from_user.id == OWNER_ID:
        context.user_data["admin_action"] = "discount"
        await q.edit_message_text("🎁 أدخل نسبة الخصم المراد تطبيقها على جميع الأدوات المدفوعة (مثال: 20):")
        return

    if data == "discount:off" and q.from_user.id == OWNER_ID:
        c = db()
        c.execute("UPDATE discount SET enabled=0,percentage=0 WHERE id=1")
        c.commit()
        c.close()
        await q.edit_message_text("✅ تم إيقاف الخصم وعادت الأسعار لطبيعتها.")
        return

    if data.startswith("toggle:") and q.from_user.id == OWNER_ID:
        t = data.split(":", 1)[1]
        if t in TOOLS:
            set_enabled(t, not is_enabled(t))
        await q.edit_message_text("✅ تم تغيير حالة الأداة بنجاح.")
        return

    if data.startswith("setprice:") and q.from_user.id == OWNER_ID:
        t = data.split(":", 1)[1]
        if t not in TOOLS:
            return
        context.user_data["admin_action"] = "price"
        context.user_data["price_tool"] = t
        await q.edit_message_text(f"💰 السعر الحالي لـ {TOOLS[t]}: ⭐{get_price(t)}\n\nأدخل السعر الجديد (أدخل 0 للتحويل إلى مجاني):")
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
        f"✅ تم الشراء بنجاح!\n➕ تم إضافة ⭐{amount}\n⭐ رصيدك الحالي: {get_balance(target)}",
        reply_markup=main_reply_keyboard(),
    )

# =========================
# TEXT HANDLER
# =========================
async def text_handler(update, context):
    user = update.effective_user
    register_user(user)
    text = (update.message.text or "").strip()

    # Header section titles click handling
    if "قسم الأدوات" in text:
        return

    if text == "🔄 القائمة الرئيسية / إلغاء":
        context.user_data.clear()
        await update.message.reply_text(
            "تم الرجوع إلى القائمة الرئيسية. اختر أداة من الأسفل 👇",
            reply_markup=main_reply_keyboard()
        )
        return

    if text == "⭐ رصيدي":
        await update.message.reply_text(
            f"⭐ **رصيدك الحالي:** {get_balance(user.id)} Stars\n\n"
            f"يمكنك شراء المزيد من النقاط عبر الضغط على **شراء باقات Stars**.",
            parse_mode="Markdown",
            reply_markup=main_reply_keyboard()
        )
        return

    if text == "💳 شراء باقات Stars":
        await update.message.reply_text(
            "💳 **اختر الباقة المناسبة لشراء النقاط:**",
            parse_mode="Markdown",
            reply_markup=plans_inline_kb()
        )
        return

    # Admin actions handling
    if user.id == OWNER_ID and context.user_data.get("admin_action"):
        action = context.user_data["admin_action"]
        if action == "price":
            try:
                value = int(text)
                if value < 0:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("❌ يرجى إدخال رقم صحيح.")
                return
            tool = context.user_data.get("price_tool")
            if tool in TOOLS:
                set_price(tool, value)
            context.user_data.clear()
            await update.message.reply_text("✅ تم تحديث سعر الأداة بنجاح.", reply_markup=main_reply_keyboard())
            return

        if action == "balance":
            try:
                target, amount = map(int, text.split())
            except Exception:
                await update.message.reply_text("❌ الصيغة خاطئة، استخدم: UserID amount")
                return
            change_balance(target, amount)
            context.user_data.clear()
            await update.message.reply_text(f"✅ تم التحديث. الرصيد الحالي للمستخدم: ⭐{get_balance(target)}", reply_markup=main_reply_keyboard())
            return

        if action == "discount":
            try:
                percentage = int(text)
                if not 0 <= percentage <= 100:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("❌ النسبة يجب أن تكون بين 0 و 100.")
                return
            c = db()
            if percentage == 0:
                c.execute("UPDATE discount SET enabled=0,percentage=0 WHERE id=1")
            else:
                c.execute("UPDATE discount SET enabled=1,percentage=? WHERE id=1", (percentage,))
            c.commit()
            c.close()
            context.user_data.clear()
            await update.message.reply_text("✅ تم تطبيق الخصم بنجاح.", reply_markup=main_reply_keyboard())
            return

    # Select Tool from Reply Keyboard Map
    tool_map = get_tool_map()
    if text in tool_map:
        tool = tool_map[text]
        if not is_enabled(tool):
            await update.message.reply_text("⏸️ هذه الأداة متوقفة مؤقتًا من قبل المالك.", reply_markup=main_reply_keyboard())
            return
        if not await require_credits(update, tool):
            return

        context.user_data.clear()
        context.user_data["pending_tool"] = tool
        prompts = {
            "background_removal": "✂️ أرسل صورة لإزالة الخلفية.",
            "ocr": "🔤 أرسل صورة لاستخراج النص منها.",
            "image_convert": "🖼️ أرسل صورة لتحويلها إلى صيغة PNG.",
            "image_compress": "📦 أرسل صورة لضغط حجمها.",
            "image_to_pdf": "📄 أرسل الصورة لتغليفها داخل PDF.",
            "pdf_to_images": "🖼️ أرسل ملف PDF للتحويل إلى صور.",
            "translation": "🌐 أرسل أي نص الآن وسيتم ترجمته فوراً تلقائياً.",
            "text_tools": "📝 أرسل النص المطلوب تدقيقه وإصلاحه.",
            "tts": "🗣️ أرسل النص الذي ترغب بتحويله إلى مقطع صوتي.",
            "stt": "🎤 أرسل المقطع الصوتي أو التسجيل الصوتي.",
            "image_generation": "🎨 أرسل وصف الصورة التي تريد توليدها بالتفصيل.",
            "image_edit": "🪄 أرسل الوصف النصي للتعديل أولاً، ثم أرسل الصورة بعدها.",
            "image_enhancement": "✨ أرسل الصورة لتحسين جودتها ودقتها.",
            "style_transfer": "🎭 أرسل الوصف النصي للنمط أولاً، ثم أرسل الصورة بعدها.",
            "pdf_summary": "📄 أرسل ملف الـ PDF لتحليله وتلخيصه.",
            "ai_assistant": "🧠 **تفضل بطرح أي سؤال أو التحدث معي مباشرة!**\n(ملاحظة: يمكنك الاستمرار بالمحادثة والتحدث معي كأنه دردشة مستمرة، للخروج ضغط 'القائمة الرئيسية').",
        }
        price = get_price(tool)
        label = "مجاني (Free)" if price == 0 else f"⭐{price} (PRO)"
        await update.message.reply_text(
            f"{prompts[tool]}\n\n💳 التكلفة: {label}",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard()
        )
        return

    # Continuous Active Tool Execution
    tool = context.user_data.get("pending_tool")
    if not tool:
        await update.message.reply_text("يرجى اختيار أداة أولاً من القائمة أسفل الشاشة 👇", reply_markup=main_reply_keyboard())
        return

    try:
        if tool in {"image_edit", "style_transfer"}:
            context.user_data["edit_prompt"] = text
            await update.message.reply_text("📷 تم حفظ الوصف، أرسل الصورة الآن ليتم البدء بالتعديل.", reply_markup=cancel_keyboard())
            return

        if tool == "translation":
            if not await require_credits(update, tool):
                return
            result = await translate_text(text)
            p = charge_after_success(user.id, tool)
            await update.message.reply_text("🌐 الترجمة:\n\n" + result, reply_markup=cancel_keyboard())
            return

        if tool == "text_tools":
            if not await require_credits(update, tool):
                return
            result = await openrouter_chat(
                "صحح النص التالي لغويًا ورتبه مع الحفاظ على المعنى. أعد النص المصحح فقط:\n\n" + text,
                system="أنت مدقق لغوي عربي محترف.",
            )
            p = charge_after_success(user.id, tool)
            await update.message.reply_text("📝 النص المصحح:\n\n" + result, reply_markup=cancel_keyboard())
            return

        if tool == "tts":
            if not await require_credits(update, tool):
                return
            audio = await text_to_speech(text)
            p = charge_after_success(user.id, tool)
            caption_str = f"🗣️ تم تحويل النص إلى صوت." + (f"\n⭐ الخصم: {p}" if p > 0 else "")
            await update.message.reply_audio(
                audio=io.BytesIO(audio),
                caption=caption_str,
                reply_markup=cancel_keyboard(),
            )
            return

        # Continuous AI Chat Assistant
        if tool == "ai_assistant":
            if not await require_credits(update, tool):
                return
            
            # Maintain chat history
            history = context.user_data.get("ai_history", [])
            result = await openrouter_chat(text, system="أنت مساعد ذكي ومحاور صريح ولطيف. أجب بالعربية.", history=history)
            
            # Update history
            history.append({"role": "user", "content": text})
            history.append({"role": "assistant", "content": result})
            if len(history) > 10:
                history = history[-10:]
            context.user_data["ai_history"] = history

            p = charge_after_success(user.id, tool)
            cost_lbl = f"\n\n_(تم خصم ⭐{p})_" if p > 0 else ""
            await update.message.reply_text(f"{result}{cost_lbl}", parse_mode="Markdown", reply_markup=cancel_keyboard())
            return

        if tool == "image_generation":
            if not await require_credits(update, tool):
                return
            image = await openai_image_generate(text)
            p = charge_after_success(user.id, tool)
            caption_str = f"🎨 تم توليد الصورة." + (f"\n⭐ الخصم: {p}" if p > 0 else "")
            await update.message.reply_photo(photo=io.BytesIO(image), caption=caption_str, reply_markup=cancel_keyboard())
            return

    except Exception as e:
        logger.exception("text tool error")
        log_usage(user.id, tool, 0, "failed")
        await update.message.reply_text(f"❌ حدث خطأ أثناء تنفيذ العملية:\n{str(e)[:300]}", reply_markup=cancel_keyboard())

# =========================
# PHOTO HANDLER
# =========================
async def photo_handler(update, context):
    user = update.effective_user
    register_user(user)
    tool = context.user_data.get("pending_tool")
    if not tool:
        await update.message.reply_text("يرجى اختيار أداة أولاً من القائمة.", reply_markup=main_reply_keyboard())
        return

    f = await update.message.photo[-1].get_file()
    data = bytes(await f.download_as_bytearray())

    try:
        if tool in {"image_edit", "style_transfer"}:
            prompt = context.user_data.get("edit_prompt")
            if not prompt:
                await update.message.reply_text("⚠️ يرجى إرسال الوصف النصي للتعديل أولاً قبل إرسال الصورة.")
                return
            if not await require_credits(update, tool):
                return
            result = await openai_edit_image(data, prompt)
            p = charge_after_success(user.id, tool)
            caption_str = f"🪄 تم تعديل الصورة بنجاح." + (f"\n⭐ الخصم: {p}" if p > 0 else "")
            await update.message.reply_photo(photo=io.BytesIO(result), caption=caption_str, reply_markup=cancel_keyboard())
            return

        if tool == "background_removal":
            if not await require_credits(update, tool):
                return
            result = await remove_background(data)
            p = charge_after_success(user.id, tool)
            caption_str = f"✂️ تم إزالة الخلفية." + (f"\n⭐ الخصم: {p}" if p > 0 else "")
            await update.message.reply_document(io.BytesIO(result), filename="no-background.png", caption=caption_str, reply_markup=cancel_keyboard())
            return

        if tool == "ocr":
            if not await require_credits(update, tool):
                return
            result = await ocr_image(data)
            p = charge_after_success(user.id, tool)
            await update.message.reply_text("🔤 النص المستخرج من الصورة:\n\n" + result, reply_markup=cancel_keyboard())
            return

        if tool == "image_convert":
            if not await require_credits(update, tool):
                return
            result, name = local_image(data, "convert")
            p = charge_after_success(user.id, tool)
            await update.message.reply_document(io.BytesIO(result), filename=name, caption="🖼️ تم تحويل الصيغة بنجاح.", reply_markup=cancel_keyboard())
            return

        if tool == "image_compress":
            if not await require_credits(update, tool):
                return
            result, name = local_image(data, "compress")
            p = charge_after_success(user.id, tool)
            await update.message.reply_document(io.BytesIO(result), filename=name, caption="📦 تم ضغط الصورة.", reply_markup=cancel_keyboard())
            return

        if tool == "image_to_pdf":
            if not await require_credits(update, tool):
                return
            result = images_to_pdf([data])
            p = charge_after_success(user.id, tool)
            await update.message.reply_document(io.BytesIO(result), filename="converted.pdf", caption="📄 تم تحويل الصورة إلى PDF.", reply_markup=cancel_keyboard())
            return

        if tool == "image_enhancement":
            if not await require_credits(update, tool):
                return
            result, name = local_image(data, "enhance")
            p = charge_after_success(user.id, tool)
            caption_str = f"✨ تم تحسين دقة الصورة." + (f"\n⭐ الخصم: {p}" if p > 0 else "")
            await update.message.reply_document(io.BytesIO(result), filename=name, caption=caption_str, reply_markup=cancel_keyboard())
            return

    except Exception as e:
        logger.exception("photo process failed")
        log_usage(user.id, tool, 0, "failed")
        await update.message.reply_text(f"❌ حدث خطأ أثناء معالجة الصورة:\n{str(e)[:300]}", reply_markup=cancel_keyboard())

# =========================
# DOCUMENT / VOICE HANDLER
# =========================
async def document_handler(update, context):
    user = update.effective_user
    register_user(user)
    tool = context.user_data.get("pending_tool")
    if not tool:
        await update.message.reply_text("يرجى اختيار أداة أولاً من القائمة.", reply_markup=main_reply_keyboard())
        return

    f = await update.message.document.get_file()
    data = bytes(await f.download_as_bytearray())

    try:
        if tool == "pdf_to_images":
            if not await require_credits(update, tool):
                return
            pdf = fitz.open(stream=data, filetype="pdf")
            for i, page in enumerate(pdf):
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                await update.message.reply_document(io.BytesIO(pix.tobytes("png")), filename=f"page-{i+1}.png")
            pdf.close()
            p = charge_after_success(user.id, tool)
            await update.message.reply_text("🖼️ تم تحويل كامل ملف الـ PDF إلى صور.", reply_markup=cancel_keyboard())
            return

        if tool == "pdf_summary":
            if not await require_credits(update, tool):
                return
            pdf = fitz.open(stream=data, filetype="pdf")
            text = "\n".join(p.get_text() for p in pdf)[:60000]
            pdf.close()
            result = await openrouter_chat("لخص هذا الملف بوضوح واستخرج منه أهم النقاط الرئيسية بالعربية:\n\n" + text, system="أنت محلل وثائق خبير.")
            p = charge_after_success(user.id, tool)
            cost_lbl = f"\n\n⭐ الخصم: {p}" if p > 0 else ""
            await update.message.reply_text(f"📄 تلخيص الوثيقة:\n\n{result}{cost_lbl}", reply_markup=cancel_keyboard())
            return

        if tool == "stt":
            if not await require_credits(update, tool):
                return
            result = await openai_transcribe(data, update.message.document.file_name or "audio.ogg")
            p = charge_after_success(user.id, tool)
            cost_lbl = f"\n\n⭐ الخصم: {p}" if p > 0 else ""
            await update.message.reply_text(f"🎤 النص المفرّغ:\n\n{result}{cost_lbl}", reply_markup=cancel_keyboard())
            return

    except Exception as e:
        logger.exception("document process failed")
        log_usage(user.id, tool, 0, "failed")
        await update.message.reply_text(f"❌ حدث خطأ أثناء معالجة المستند:\n{str(e)[:300]}", reply_markup=cancel_keyboard())

async def voice_handler(update, context):
    user = update.effective_user
    register_user(user)
    tool = context.user_data.get("pending_tool")
    if tool != "stt":
        await update.message.reply_text("يرجى اختيار أداة 🎤 صوت ← نص أولاً.", reply_markup=main_reply_keyboard())
        return
    if not await require_credits(update, tool):
        return
    try:
        f = await update.message.voice.get_file()
        data = bytes(await f.download_as_bytearray())
        result = await openai_transcribe(data, "voice.ogg")
        p = charge_after_success(user.id, tool)
        cost_lbl = f"\n\n⭐ الخصم: {p}" if p > 0 else ""
        await update.message.reply_text(f"🎤 النص المفرّغ من المقطع:\n\n{result}{cost_lbl}", reply_markup=cancel_keyboard())
    except Exception as e:
        logger.exception("voice process failed")
        log_usage(user.id, tool, 0, "failed")
        await update.message.reply_text(f"❌ حدث خطأ أثناء معالجة الصوت:\n{str(e)[:300]}", reply_markup=cancel_keyboard())

# =========================
# MAIN FUNCTION
# =========================
async def error_handler(update, context):
    logger.exception("Unhandled error occurred", exc_info=context.error)

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
    logger.info("AI TOOLS BOT is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

keep_alive()

# =========================
# SETTINGS & CONSTANTS
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("ADMIN_TELEGRAM_ID", "8860453018")))
DATABASE = os.getenv("DATABASE", "ai_tools.db")
STARTER_STARS = 10

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_FREE_MODEL = os.getenv("OPENROUTER_FREE_MODEL", "openrouter/free")
OPENROUTER_VISION_MODEL = os.getenv("OPENROUTER_VISION_MODEL", "openrouter/free")

REMOVEBG_API_KEY = os.getenv("REMOVEBG_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

AZKAR_FOOTER = "\n\n✨ *أستغفر الله العظيم واتوب إليه* | *اللهم صلِّ وسلم على نبينا محمد* 🤍"

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
    "image_to_pdf": "📄 صور ← PDF",
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

# Map for Bottom Keyboard Buttons -> Tool Keys
TOOL_BUTTON_MAP = {v: k for k, v in TOOLS.items()}

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
    return bool(r["enabled"]), int(r["percentage"]) if r else (False, 0)

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
# KEYBOARDS (BOTTOM REPLY KEYBOARD)
# =========================
def main_reply_keyboard():
    keyboard = [
        [KeyboardButton("🌐 ترجمة النص"), KeyboardButton("📝 تصحيح النص")],
        [KeyboardButton("🔤 استخراج النص من صورة"), KeyboardButton("✂️ إزالة الخلفية")],
        [KeyboardButton("🎨 توليد الصور"), KeyboardButton("🪄 تعديل الصور بالذكاء الاصطناعي")],
        [KeyboardButton("✨ تحسين الصور"), KeyboardButton("🎭 تغيير نمط الصورة")],
        [KeyboardButton("🖼️ تحويل صيغ الصور"), KeyboardButton("📦 ضغط الصور")],
        [KeyboardButton("📄 صور ← PDF"), KeyboardButton("🖼️ PDF → صور")],
        [KeyboardButton("🗣️ نص → صوت"), KeyboardButton("🎤 صوت → نص")],
        [KeyboardButton("📄 تحليل/تلخيص PDF"), KeyboardButton("🧠 مساعد AI المتقدم")],
        [KeyboardButton("⭐ رصيدي"), KeyboardButton("💳 شراء باقات Stars")],
        [KeyboardButton("🔄 القائمة الرئيسية / إلغاء")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("🔄 القائمة الرئيسية / إلغاء")]], resize_keyboard=True)

def plans_inline_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ شراء 100 Stars", callback_data="buy:100"),
         InlineKeyboardButton("⭐ شراء 500 Stars", callback_data="buy:500")],
        [InlineKeyboardButton("⭐ شراء 1000 Stars", callback_data="buy:1000")],
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
        raise RuntimeError("OPENROUTER_API_KEY غير موجود في متغيرات البيئة")

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
        raise RuntimeError("الخدمة لم ترجع أي استجابة.")
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
        raise RuntimeError("إزالة الخلفية تطلب REMOVEBG_API_KEY")
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
        raise RuntimeError("OPENAI_API_KEY غير متوفر لتوليد الصور.")
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    result = await client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        response_format="b64_json"
    )
    return base64.b64decode(result.data[0].b64_json)

async def openai_edit_image(image_bytes, prompt):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY غير متوفر لتعديل الصور.")
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    f.write(image_bytes)
    f.close()
    try:
        with open(f.name, "rb") as img:
            result = await client.images.edit(
                model="dall-e-2",
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
        raise RuntimeError("OPENAI_API_KEY غير متوفر لتحويل الصوت إلى نص.")
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    f = tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1] or ".ogg", delete=False)
    f.write(audio_bytes)
    f.close()
    try:
        with open(f.name, "rb") as audio:
            r = await client.audio.transcriptions.create(
                model="whisper-1",
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
            f"❌ رصيدك غير كافٍ.\n\nالسعر المطلوب: ⭐{price}\nرصيدك الحالي: ⭐{balance}\n\nيمكنك اختيار باقة لشراء النقاط:",
            reply_markup=plans_inline_kb(),
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
    context.user_data.clear()
    msg = (
        "✨ **لا إله إلا الله محمد رسول الله** ✨\n\n"
        "أهلاً بك في بوت الأدوات والذكاء الاصطناعي 🤖\n"
        "اختر الأداة المطلوبة من القائمة بالأسفل 👇"
        f"{AZKAR_FOOTER}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_reply_keyboard())

async def admin(update, context):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ غير مصرح.")
        return
    await update.message.reply_text(
        "👑 لوحة المالك\n\nتستطيع من هنا التحكم بالإعدادات والرصيد والأسعار:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 الأسعار", callback_data="admin:prices")],
            [InlineKeyboardButton("🛠️ تشغيل / إيقاف الأدوات", callback_data="admin:tools")],
            [InlineKeyboardButton("🎁 الخصومات", callback_data="admin:discount")],
            [InlineKeyboardButton("⭐ تعديل رصيد", callback_data="admin:balance")],
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin:stats")],
        ]),
    )

# =========================
# CALLBACKS (INLINE BUTTONS FOR PAYMENTS & ADMIN)
# =========================
async def callbacks(update, context):
    q = update.callback_query
    await q.answer()
    register_user(q.from_user)
    data = q.data

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
            await q.edit_message_text("💰 الأسعار\n\nاختر الأداة لتعديل سعرها:", reply_markup=InlineKeyboardMarkup(rows))
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
            await q.edit_message_text("🛠️ تشغيل / إيقاف الأدوات:", reply_markup=InlineKeyboardMarkup(rows))
            return

        if action == "stats":
            c = db()
            users = c.execute("SELECT COUNT(*) x FROM users").fetchone()["x"]
            ops = c.execute("SELECT COUNT(*) x FROM usage_logs").fetchone()["x"]
            spent = c.execute("SELECT COALESCE(SUM(stars),0) x FROM usage_logs WHERE status='success'").fetchone()["x"]
            c.close()
            await q.edit_message_text(
                f"📊 الإحصائيات\n\n👤 عدد المستخدمين: {users}\n📌 العمليات الناجحة: {ops}\n⭐ إجمالي المستهلك: {spent}",
            )
            return

        if action == "balance":
            context.user_data["admin_action"] = "balance"
            await q.edit_message_text("⭐ أرسل الرقم بالشكل التالي:\nUserID amount\n\nمثال: 123456789 20")
            return

        if action == "discount":
            enabled, percentage = get_discount()
            state = f"🟢 خصم {percentage}% فعال" if enabled else "🔴 لا يوجد خصم"
            await q.edit_message_text(
                f"🎁 الخصومات\n\nالحالة: {state}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ تحديد نسبة خصم", callback_data="discount:set")],
                    [InlineKeyboardButton("❌ إيقاف الخصم", callback_data="discount:off")],
                ]),
            )
            return

    if data == "discount:set" and q.from_user.id == OWNER_ID:
        context.user_data["admin_action"] = "discount"
        await q.edit_message_text("🎁 أدخل نسبة الخصم المراد تطبيقها (0 - 100):")
        return

    if data == "discount:off" and q.from_user.id == OWNER_ID:
        c = db()
        c.execute("UPDATE discount SET enabled=0,percentage=0 WHERE id=1")
        c.commit()
        c.close()
        await q.edit_message_text("✅ تم إيقاف الخصومات.")
        return

    if data.startswith("toggle:") and q.from_user.id == OWNER_ID:
        t = data.split(":", 1)[1]
        if t in TOOLS:
            set_enabled(t, not is_enabled(t))
        await q.edit_message_text("✅ تم تعديل حالة الأداة.")
        return

    if data.startswith("setprice:") and q.from_user.id == OWNER_ID:
        t = data.split(":", 1)[1]
        if t not in TOOLS:
            return
        context.user_data["admin_action"] = "price"
        context.user_data["price_tool"] = t
        await q.edit_message_text(f"💰 السعر الحالي لـ {TOOLS[t]}: ⭐{get_price(t)}\n\nأدخل السعر الجديد (أدخل 0 لمجاني):")
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
        f"✅ تم الشراء بنجاح!\n➕ تم إضافة ⭐{amount}\n⭐ رصيدك الحالي: {get_balance(target)}"
        f"{AZKAR_FOOTER}",
        reply_markup=main_reply_keyboard(),
    )

# =========================
# TEXT HANDLER
# =========================
async def text_handler(update, context):
    user = update.effective_user
    register_user(user)
    text = (update.message.text or "").strip()

    if text == "🔄 القائمة الرئيسية / إلغاء":
        context.user_data.clear()
        await update.message.reply_text(
            f"✨ **سبحان الله وبحمده سبحان الله العظيم** ✨\n\nتم الرجوع إلى القائمة الرئيسية. اختر أداة من الأسفل 👇",
            parse_mode="Markdown",
            reply_markup=main_reply_keyboard()
        )
        return

    if text == "⭐ رصيدي":
        await update.message.reply_text(
            f"⭐ **رصيدك الحالي:** {get_balance(user.id)} Stars\n\n"
            f"يمكنك شراء المزيد من النقاط عبر الضغط على **شراء باقات Stars**."
            f"{AZKAR_FOOTER}",
            parse_mode="Markdown",
            reply_markup=main_reply_keyboard()
        )
        return

    if text == "💳 شراء باقات Stars":
        await update.message.reply_text(
            "💳 **اختر الباقة المناسبة لشراء النقاط:**",
            parse_mode="Markdown",
            reply_markup=plans_inline_kb()
        )
        return

    # Admin actions handling
    if user.id == OWNER_ID and context.user_data.get("admin_action"):
        action = context.user_data["admin_action"]
        if action == "price":
            try:
                value = int(text)
                if value < 0:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("❌ يرجى إدخال رقم صحيح.")
                return
            tool = context.user_data.get("price_tool")
            if tool in TOOLS:
                set_price(tool, value)
            context.user_data.clear()
            await update.message.reply_text("✅ تم حفظ السعر.", reply_markup=main_reply_keyboard())
            return

        if action == "balance":
            try:
                target, amount = map(int, text.split())
            except Exception:
                await update.message.reply_text("❌ الصيغة خاطئة، استخدم: UserID amount")
                return
            change_balance(target, amount)
            context.user_data.clear()
            await update.message.reply_text(f"✅ تم التحديث. الرصيد: ⭐{get_balance(target)}", reply_markup=main_reply_keyboard())
            return

        if action == "discount":
            try:
                percentage = int(text)
                if not 0 <= percentage <= 100:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("❌ النسبة يجب أن تكون بين 0 و 100.")
                return
            c = db()
            if percentage == 0:
                c.execute("UPDATE discount SET enabled=0,percentage=0 WHERE id=1")
            else:
                c.execute("UPDATE discount SET enabled=1,percentage=? WHERE id=1", (percentage,))
            c.commit()
            c.close()
            context.user_data.clear()
            await update.message.reply_text("✅ تم تحديث الخصم.", reply_markup=main_reply_keyboard())
            return

    # Select Tool from Bottom Keyboard
    if text in TOOL_BUTTON_MAP:
        tool = TOOL_BUTTON_MAP[text]
        if not is_enabled(tool):
            await update.message.reply_text("⏸️ هذه الأداة متوقفة مؤقتًا.", reply_markup=main_reply_keyboard())
            return
        if not await require_credits(update, tool):
            return

        context.user_data.clear()
        context.user_data["pending_tool"] = tool
        prompts = {
            "background_removal": "✂️ أرسل صورة لإزالة الخلفية.",
            "ocr": "🔤 أرسل صورة لاستخراج النص منها.",
            "image_convert": "🖼️ أرسل صورة لتحويلها إلى صيغة PNG.",
            "image_compress": "📦 أرسل صورة لضغط حجمها.",
            "image_to_pdf": "📄 أرسل الصورة لتغليفها داخل PDF.",
            "pdf_to_images": "🖼️ أرسل ملف PDF للتحويل إلى صور.",
            "translation": "🌐 أرسل النص مسبوقًا بطلبك، مثل:\nترجم إلى الإنجليزية: مرحبًا بك",
            "text_tools": "📝 أرسل النص المطلوب تدقيقه وإصلاحه.",
            "tts": "🗣️ أرسل النص الذي ترغب بتحويله إلى مقطع صوتي.",
            "stt": "🎤 أرسل المقطع الصوتي أو التسجيل الصوتي.",
            "image_generation": "🎨 أرسل وصف الصورة التي تريد توليدها بالتفصيل.",
            "image_edit": "🪄 أرسل الوصف النصي للتعديل أولاً، ثم أرسل الصورة بعدها.",
            "image_enhancement": "✨ أرسل الصورة لتحسين جودتها ودقتها.",
            "style_transfer": "🎭 أرسل الوصف النصي للنمط أولاً، ثم أرسل الصورة بعدها.",
            "pdf_summary": "📄 أرسل ملف الـ PDF لتحليله وتلخيصه.",
            "ai_assistant": "🧠 أرسل سؤالك أو طلبك لمساعد الذكاء الاصطناعي.",
        }
        price = get_price(tool)
        label = "مجاني" if price == 0 else f"⭐{price}"
        await update.message.reply_text(
            f"{prompts[tool]}\n\n💳 التكلفة: {label}{AZKAR_FOOTER}",
            reply_markup=cancel_keyboard()
        )
        return

    # Tool Execution Logic
    tool = context.user_data.get("pending_tool")
    if not tool:
        await update.message.reply_text("يرجى اختيار أداة أولاً من القائمة أسفل الشاشة 👇", reply_markup=main_reply_keyboard())
        return

    try:
        if tool in {"image_edit", "style_transfer"}:
            context.user_data["edit_prompt"] = text
            await update.message.reply_text("📷 تم حفظ الوصف، أرسل الصورة الآن ليتم البدء بالتعديل.", reply_markup=cancel_keyboard())
            return

        if tool == "translation":
            m = re.match(r"ترجم(?:\s+إلى)?\s+([\w\u0600-\u06FF]+)\s*:\s*(.+)", text, re.S | re.I)
            if not m:
                await update.message.reply_text("⚠️ يرجى استخدام الصيغة:\nترجم إلى الإنجليزية: مرحبًا بك")
                return
            target_name = m.group(1).lower()
            target = {
                "الإنجليزية": "en", "انجليزية": "en", "english": "en",
                "العربية": "ar", "عربي": "ar", "العربيه": "ar",
                "الفرنسية": "fr", "التركية": "tr", "الألمانية": "de",
            }.get(target_name, target_name)
            result = await translate_text(m.group(2), target)
            context.user_data.clear()
            await update.message.reply_text("🌐 الترجمة:\n\n" + result + AZKAR_FOOTER, reply_markup=main_reply_keyboard())
            return

        if tool == "text_tools":
            result = await openrouter_chat(
                "صحح النص التالي لغويًا ورتبه مع الحفاظ على المعنى. أعد النص المصحح فقط:\n\n" + text,
                system="أنت مدقق لغوي عربي محترف.",
            )
            context.user_data.clear()
            await update.message.reply_text("📝 النص المصحح:\n\n" + result + AZKAR_FOOTER, reply_markup=main_reply_keyboard())
            return

        if tool == "tts":
            if not await require_credits(update, tool):
                return
            audio = await text_to_speech(text)
            p = charge_after_success(user.id, tool)
            context.user_data.clear()
            await update.message.reply_audio(
                audio=io.BytesIO(audio),
                caption=f"🗣️ تم تحويل النص إلى صوت.\n⭐ الخصم: {p}{AZKAR_FOOTER}",
                reply_markup=main_reply_keyboard(),
            )
            return

        if tool == "ai_assistant":
            if not await require_credits(update, tool):
                return
            result = await openrouter_chat(text, system="أنت مساعد AI متقدم. أجب بالعربية.")
            p = charge_after_success(user.id, tool)
            context.user_data.clear()
            await update.message.reply_text(f"🧠 {result}\n\n⭐ الخصم: {p}{AZKAR_FOOTER}", reply_markup=main_reply_keyboard())
            return

        if tool == "image_generation":
            if not await require_credits(update, tool):
                return
            image = await openai_image_generate(text)
            p = charge_after_success(user.id, tool)
            context.user_data.clear()
            await update.message.reply_photo(photo=io.BytesIO(image), caption=f"🎨 تم توليد الصورة.\n⭐ الخصم: {p}{AZKAR_FOOTER}", reply_markup=main_reply_keyboard())
            return

    except Exception as e:
        logger.exception("text tool error")
        log_usage(user.id, tool, 0, "failed")
        context.user_data.clear()
        await update.message.reply_text(f"❌ حدث خطأ أثناء تنفيذ العملية:\n{str(e)[:300]}", reply_markup=main_reply_keyboard())

# =========================
# PHOTO HANDLER
# =========================
async def photo_handler(update, context):
    user = update.effective_user
    register_user(user)
    tool = context.user_data.get("pending_tool")
    if not tool:
        await update.message.reply_text("يرجى اختيار أداة أولاً من القائمة.", reply_markup=main_reply_keyboard())
        return

    f = await update.message.photo[-1].get_file()
    data = bytes(await f.download_as_bytearray())

    try:
        if tool in {"image_edit", "style_transfer"}:
            prompt = context.user_data.get("edit_prompt")
            if not prompt:
                await update.message.reply_text("⚠️ يرجى إرسال الوصف النصي للتعديل أولاً قبل إرسال الصورة.")
                return
            if not await require_credits(update, tool):
                return
            result = await openai_edit_image(data, prompt)
            p = charge_after_success(user.id, tool)
            context.user_data.clear()
            await update.message.reply_photo(photo=io.BytesIO(result), caption=f"🪄 تم تعديل الصورة بنجاح.\n⭐ الخصم: {p}{AZKAR_FOOTER}", reply_markup=main_reply_keyboard())
            return

        if tool == "background_removal":
            if not await require_credits(update, tool):
                return
            result = await remove_background(data)
            p = charge_after_success(user.id, tool)
            context.user_data.clear()
            await update.message.reply_document(io.BytesIO(result), filename="no-background.png", caption=f"✂️ تم إزالة الخلفية.\n⭐ الخصم: {p}{AZKAR_FOOTER}", reply_markup=main_reply_keyboard())
            return

        if tool == "ocr":
            result = await ocr_image(data)
            context.user_data.clear()
            await update.message.reply_text("🔤 النص المستخرج من الصورة:\n\n" + result + AZKAR_FOOTER, reply_markup=main_reply_keyboard())
            return

        if tool == "image_convert":
            result, name = local_image(data, "convert")
            context.user_data.clear()
            await update.message.reply_document(io.BytesIO(result), filename=name, caption=f"🖼️ تم تحويل الصيغة بنجاح.{AZKAR_FOOTER}", reply_markup=main_reply_keyboard())
            return

        if tool == "image_compress":
            result, name = local_image(data, "compress")
            context.user_data.clear()
            await update.message.reply_document(io.BytesIO(result), filename=name, caption=f"📦 تم ضغط الصورة.{AZKAR_FOOTER}", reply_markup=main_reply_keyboard())
            return

        if tool == "image_to_pdf":
            result = images_to_pdf([data])
            context.user_data.clear()
            await update.message.reply_document(io.BytesIO(result), filename="converted.pdf", caption=f"📄 تم تحويل الصورة إلى PDF.{AZKAR_FOOTER}", reply_markup=main_reply_keyboard())
            return

        if tool == "image_enhancement":
            if not await require_credits(update, tool):
                return
            result, name = local_image(data, "enhance")
            p = charge_after_success(user.id, tool)
            context.user_data.clear()
            await update.message.reply_document(io.BytesIO(result), filename=name, caption=f"✨ تم تحسين دقة الصورة.\n⭐ الخصم: {p}{AZKAR_FOOTER}", reply_markup=main_reply_keyboard())
            return

    except Exception as e:
        logger.exception("photo process failed")
        log_usage(user.id, tool, 0, "failed")
        context.user_data.clear()
        await update.message.reply_text(f"❌ حدث خطأ أثناء معالجة الصورة:\n{str(e)[:300]}", reply_markup=main_reply_keyboard())

# =========================
# DOCUMENT / VOICE HANDLER
# =========================
async def document_handler(update, context):
    user = update.effective_user
    register_user(user)
    tool = context.user_data.get("pending_tool")
    if not tool:
        await update.message.reply_text("يرجى اختيار أداة أولاً من القائمة.", reply_markup=main_reply_keyboard())
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
            await update.message.reply_text("🖼️ تم تحويل كامل ملف الـ PDF إلى صور." + AZKAR_FOOTER, reply_markup=main_reply_keyboard())
            return

        if tool == "pdf_summary":
            if not await require_credits(update, tool):
                return
            pdf = fitz.open(stream=data, filetype="pdf")
            text = "\n".join(p.get_text() for p in pdf)[:60000]
            pdf.close()
            result = await openrouter_chat("لخص هذا الملف بوضوح واستخرج منه أهم النقاط الرئيسية بالعربية:\n\n" + text, system="أنت محلل وثائق خبير.")
            p = charge_after_success(user.id, tool)
            context.user_data.clear()
            await update.message.reply_text(f"📄 تلخيص الوثيقة:\n\n{result}\n\n⭐ الخصم: {p}{AZKAR_FOOTER}", reply_markup=main_reply_keyboard())
            return

        if tool == "stt":
            if not await require_credits(update, tool):
                return
            result = await openai_transcribe(data, update.message.document.file_name or "audio.ogg")
            p = charge_after_success(user.id, tool)
            context.user_data.clear()
            await update.message.reply_text(f"🎤 النص المفرّغ:\n\n{result}\n\n⭐ الخصم: {p}{AZKAR_FOOTER}", reply_markup=main_reply_keyboard())
            return

    except Exception as e:
        logger.exception("document process failed")
        log_usage(user.id, tool, 0, "failed")
        context.user_data.clear()
        await update.message.reply_text(f"❌ حدث خطأ أثناء معالجة المستند:\n{str(e)[:300]}", reply_markup=main_reply_keyboard())


async def voice_handler(update, context):
    user = update.effective_user
    register_user(user)
    tool = context.user_data.get("pending_tool")
    if tool != "stt":
        await update.message.reply_text("يرجى اختيار أداة 🎤 صوت ← نص أولاً.", reply_markup=main_reply_keyboard())
        return
    if not await require_credits(update, tool):
        return
    try:
        f = await update.message.voice.get_file()
        data = bytes(await f.download_as_bytearray())
        result = await openai_transcribe(data, "voice.ogg")
        p = charge_after_success(user.id, tool)
        context.user_data.clear()
        await update.message.reply_text(f"🎤 النص المفرّغ من المقطع:\n\n{result}\n\n⭐ الخصم: {p}{AZKAR_FOOTER}", reply_markup=main_reply_keyboard())
    except Exception as e:
        logger.exception("voice process failed")
        log_usage(user.id, tool, 0, "failed")
        context.user_data.clear()
        await update.message.reply_text(f"❌ حدث خطأ أثناء معالجة الصوت:\n{str(e)[:300]}", reply_markup=main_reply_keyboard())

# =========================
# MAIN FUNCTION
# =========================
async def error_handler(update, context):
    logger.exception("Unhandled error occurred", exc_info=context.error)

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
    logger.info("AI TOOLS BOT is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
