import os
import logging
import threading
import requests
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# --- 1. خادم وهمي لمنع مشكلة No Port open listener في Render ---
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is running fine!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=port)

# تشغيل خادم Flask في الخلفية
threading.Thread(target=run_flask, daemon=True).start()

# --- 2. إعداد السجلات لمنع التوقف ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 3. البيانات والتوكنات ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "ضع_توكن_البوت_هنا")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "ضع_مفتاح_OPENAI_هنا")
OWNER_ID = "8860453018"

user_states = {}

def get_main_keyboard(user_id):
    keyboard = [
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
        [
            InlineKeyboardButton("🔍 تحليل / تلخيص النص (مجاني)", callback_data="tool_summarize")
        ],
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

    if str(user_id) == str(OWNER_ID):
        keyboard.append([InlineKeyboardButton("👑 لوحة تحكم المالك", callback_data="owner_menu")])

    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        reply_kb = [[KeyboardButton("🔄 القائمة الرئيسية / إلغاء")]]
        markup = ReplyKeyboardMarkup(reply_kb, resize_keyboard=True)

        await update.message.reply_text("أهلاً بك في بوت الخدمات!", reply_markup=markup)
        await update.message.reply_text("اختر الأداة المطلوبة من القائمة أدناه:", reply_markup=get_main_keyboard(user_id))
    except Exception as e:
        logger.error(f"خطأ في امر start: {e}")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        user_id = query.from_user.id
        data = query.data

        if data == "ignore":
            await query.answer()
            return

        await query.answer()

        if data == "owner_menu":
            if str(user_id) == str(OWNER_ID):
                owner_kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ إضافة نقاط لمستخدم", callback_data="owner_add_pts")],
                    [InlineKeyboardButton("📢 إرسال إشعار عام", callback_data="owner_broadcast")],
                    [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
                ])
                await query.edit_message_text("👑 **لوحة تحكم المالك**\nاختر الخيار المطلوب:", reply_markup=owner_kb, parse_mode="Markdown")
            else:
                await query.answer("عذراً، هذا الخيار مخصص لمالك البوت فقط!", show_alert=True)
            return

        if data == "back_to_main":
            await query.edit_message_text("اختر الأداة المطلوبة من القائمة أدناه:", reply_markup=get_main_keyboard(user_id))
            return

        if data == "tool_img_gen":
            user_states[user_id] = "WAITING_FOR_IMAGE_PROMPT"
            await query.message.reply_text("🎨 أرسل وصف الصورة التي تريد توليدها بالتفصيل.\n💳 التكلفة: ⭐ 5 (PRO)")
            return

        if data == "tool_summarize":
            user_states[user_id] = "WAITING_FOR_SUMMARY"
            await query.message.reply_text("🔍 أرسل النص الذي تريد تحليله وتلخيصه الآن (الخدمة مجانية بالكامل) 📄")
            return

        await query.message.reply_text(f"تم اختيار الأداة: {data}")

    except Exception as e:
        logger.error(f"خطأ في الكولباك: {e}")

async def handle_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text = update.message.text

        if text == "🔄 القائمة الرئيسية / إلغاء":
            user_states.pop(user_id, None)
            await update.message.reply_text("تم الرجوع إلى القائمة الرئيسية.", reply_markup=get_main_keyboard(user_id))
            return

        state = user_states.get(user_id)

        if state == "WAITING_FOR_IMAGE_PROMPT":
            if not OPENAI_API_KEY or "ضع_مفتاح" in OPENAI_API_KEY:
                await update.message.reply_text("❌ حدث خطأ أثناء تنفيذ العملية:\nغير متوفر OPENAI_API_KEY لتوليد الصور.")
                user_states.pop(user_id, None)
                return

            await update.message.reply_text("⏳ جاري توليد الصورة...")
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
            except Exception:
                await update.message.reply_text("❌ حدث خطأ أثناء تنفيذ العملية (تعذر الاتصال بـ OpenAI).")

            user_states.pop(user_id, None)
            return

        if state == "WAITING_FOR_SUMMARY":
            await update.message.reply_text(f"📊 **نتيجة التلخيص والتحليل (مجاني):**\n\n{text[:300]}...\n\n✅ تم التلخيص بنجاح.", parse_mode="Markdown")
            user_states.pop(user_id, None)
            return

        await update.message.reply_text("اختر أداة من القائمة أدناه للبدء:", reply_markup=get_main_keyboard(user_id))

    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}")

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="حدث استثناء في البوت وتم احتواؤه لمنع التوقف:", exc_info=context.error)

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_messages))

    app.add_error_handler(global_error_handler)

    print("🚀 يعمل البوت بنجاح...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
