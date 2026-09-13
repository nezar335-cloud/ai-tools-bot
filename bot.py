import os
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder


# =========================
# إعدادات البوت
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")


# =========================
# تشغيل البوت
# =========================

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================
# القوائم
# =========================

def main_menu():
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="🖼️ أدوات الصور",
        callback_data="images"
    )

    keyboard.button(
        text="🔊 الصوت والنص",
        callback_data="audio"
    )

    keyboard.button(
        text="🌐 الترجمة",
        callback_data="translation"
    )

    keyboard.button(
        text="🧠 أدوات الذكاء الاصطناعي",
        callback_data="ai"
    )

    keyboard.button(
        text="⭐ رصيدي",
        callback_data="balance"
    )

    keyboard.adjust(2, 2, 1)

    return keyboard.as_markup()


def back_button():
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="🔙 رجوع",
        callback_data="back"
    )

    return keyboard.as_markup()


# =========================
# /start
# =========================

@dp.message(CommandStart())
async def start_command(message: Message):

    user = message.from_user

    text = (
        f"👋 أهلاً بك {user.first_name}!\n\n"
        "🤖 مرحباً بك في بوت AI Tools\n\n"
        "✨ مجموعة من أدوات الذكاء الاصطناعي "
        "للصور والصوت والنص.\n\n"
        "اختر ما تريد من القائمة أدناه 👇"
    )

    await message.answer(
        text,
        reply_markup=main_menu()
    )


# =========================
# أدوات الصور
# =========================

@dp.callback_query(F.data == "images")
async def images_menu(callback: CallbackQuery):

    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="🖼️ توليد صورة بالذكاء الاصطناعي",
        callback_data="image_generate"
    )

    keyboard.button(
        text="✂️ إزالة الخلفية",
        callback_data="remove_background"
    )

    keyboard.button(
        text="✨ تحسين الصورة",
        callback_data="enhance_image"
    )

    keyboard.button(
        text="🎨 تغيير نمط الصورة",
        callback_data="image_style"
    )

    keyboard.button(
        text="📝 تحويل الصورة إلى نص",
        callback_data="ocr"
    )

    keyboard.button(
        text="🔙 رجوع",
        callback_data="back"
    )

    keyboard.adjust(1)

    await callback.message.edit_text(
        "🖼️ **أدوات الصور**\n\n"
        "اختر الأداة التي تريد استخدامها:",
        reply_markup=keyboard.as_markup(),
        parse_mode="Markdown"
    )

    await callback.answer()


# =========================
# الصوت والنص
# =========================

@dp.callback_query(F.data == "audio")
async def audio_menu(callback: CallbackQuery):

    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="🔊 تحويل النص إلى صوت",
        callback_data="text_to_speech"
    )

    keyboard.button(
        text="🎤 تحويل الصوت إلى نص",
        callback_data="speech_to_text"
    )

    keyboard.button(
        text="🔙 رجوع",
        callback_data="back"
    )

    keyboard.adjust(1)

    await callback.message.edit_text(
        "🔊 **الصوت والنص**\n\n"
        "اختر الأداة:",
        reply_markup=keyboard.as_markup(),
        parse_mode="Markdown"
    )

    await callback.answer()


# =========================
# الترجمة
# =========================

@dp.callback_query(F.data == "translation")
async def translation_menu(callback: CallbackQuery):

    await callback.message.edit_text(
        "🌐 **الترجمة**\n\n"
        "أرسل النص الذي تريد ترجمته.\n\n"
        "هذه الأداة سيتم تفعيلها في المرحلة القادمة.",
        reply_markup=back_button(),
        parse_mode="Markdown"
    )

    await callback.answer()


# =========================
# أدوات الذكاء الاصطناعي
# =========================

@dp.callback_query(F.data == "ai")
async def ai_menu(callback: CallbackQuery):

    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="🧠 المساعد الذكي",
        callback_data="ai_assistant"
    )

    keyboard.button(
        text="✍️ كتابة وتحسين النصوص",
        callback_data="text_tools"
    )

    keyboard.button(
        text="🪄 تعديل الصور بالأوامر",
        callback_data="ai_edit"
    )

    keyboard.button(
        text="🔙 رجوع",
        callback_data="back"
    )

    keyboard.adjust(1)

    await callback.message.edit_text(
        "🧠 **أدوات الذكاء الاصطناعي**\n\n"
        "اختر الأداة:",
        reply_markup=keyboard.as_markup(),
        parse_mode="Markdown"
    )

    await callback.answer()


# =========================
# الرصيد
# =========================

@dp.callback_query(F.data == "balance")
async def balance(callback: CallbackQuery):

    # الرصيد الحقيقي سنربطه بقاعدة PostgreSQL لاحقاً
    balance_value = 0

    await callback.message.edit_text(
        f"⭐ **رصيدك الحالي:** {balance_value} ⭐\n\n"
        "يمكن استخدام ⭐ للأدوات PRO.",
        reply_markup=back_button(),
        parse_mode="Markdown"
    )

    await callback.answer()


# =========================
# زر الرجوع
# =========================

@dp.callback_query(F.data == "back")
async def go_back(callback: CallbackQuery):

    await callback.message.edit_text(
        "🏠 **القائمة الرئيسية**\n\n"
        "اختر ما تريد:",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

    await callback.answer()


# =========================
# الأدوات التي سنبرمجها لاحقاً
# =========================

@dp.callback_query(
    F.data.in_({
        "image_generate",
        "remove_background",
        "enhance_image",
        "image_style",
        "ocr",
        "text_to_speech",
        "speech_to_text",
        "ai_assistant",
        "text_tools",
        "ai_edit"
    })
)
async def coming_soon(callback: CallbackQuery):

    await callback.message.edit_text(
        "⏳ **هذه الأداة قيد التجهيز**\n\n"
        "سنقوم بتفعيلها وربطها بالمحرك المناسب في الخطوات القادمة. 🚀",
        reply_markup=back_button(),
        parse_mode="Markdown"
    )

    await callback.answer()


# =========================
# تشغيل البوت
# =========================

async def main():

    print("🤖 AI Tools Bot is starting...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
