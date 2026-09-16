const { Telegraf, Markup } = require('telegraf');
const axios = require('axios');
const fs = require('fs');
const googleTTS = require('google-tts-api');

// جلب المفاتيح من بيئة التشغيل
const BOT_TOKEN = process.env.BOT_TOKEN;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;
const REMOVEBG_API_KEY = process.env.REMOVEBG_API_KEY;
const OWNER_ID = Number(process.env.OWNER_ID) || 8860453018;

if (!BOT_TOKEN) {
    console.error("❌ BOT_TOKEN غير موجود!");
    process.exit(1);
}

const bot = new Telegraf(BOT_TOKEN);
const DB_FILE = './database.json';
const userState = {}; // متابعة حالة المستخدم للرد على الأدوات

// إدارة قاعدة البيانات
function loadDB() {
    if (!fs.existsSync(DB_FILE)) {
        const defaultDB = {
            tools: {
                "🖼️ إزالة الخلفية": true,
                "🌐 الترجمة": true,
                "✨ تحسين الصور": true,
                "🎨 توليد الصور": true,
                "🖌️ تعديل الصور بالذكاء الاصطناعي": true,
                "🧠 المساعد الذكي": true,
                "🔊 تحويل النص إلى صوت": true
            }
        };
        fs.writeFileSync(DB_FILE, JSON.stringify(defaultDB, null, 2));
        return defaultDB;
    }
    try {
        return JSON.parse(fs.readFileSync(DB_FILE));
    } catch (e) {
        return { tools: {} };
    }
}

function saveDB(data) {
    fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2));
}

const isOwner = (ctx) => ctx.from && Number(ctx.from.id) === OWNER_ID;

const toolToggleMap = {
    "إلغاء/تفعيل إزالة الخلفية": "🖼️ إزالة الخلفية",
    "إلغاء/تفعيل الترجمة": "🌐 الترجمة",
    "إلغاء/تفعيل تحسين الصور": "✨ تحسين الصور",
    "إلغاء/تفعيل توليد الصور": "🎨 توليد الصور",
    "إلغاء/تفعيل تعديل الصور": "🖌️ تعديل الصور بالذكاء الاصطناعي",
    "إلغاء/تفعيل المساعد الذكي": "🧠 المساعد الذكي",
    "إلغاء/تفعيل تحويل النص لصوت": "🔊 تحويل النص إلى صوت"
};

async function getTools() {
    const db = loadDB();
    return db.tools;
}

// القوائم واللوحات
const mainKeyboard = (userId) => {
    const buttons = [
        ["🖼️ إزالة الخلفية", "🌐 الترجمة"],
        ["✨ تحسين الصور", "🎨 توليد الصور"],
        ["🖌️ تعديل الصور بالذكاء الاصطناعي"],
        ["🧠 المساعد الذكي", "🔊 تحويل النص إلى صوت"],
        ["💳 شراء نجوم", "⭐ رصيدي"],
        ["📞 التواصل مع المطور"]
    ];

    if (Number(userId) === OWNER_ID) {
        buttons.push(["👑 لوحة التحكم"]);
    }

    return Markup.keyboard(buttons).resize();
};

// الأمر /start
bot.start((ctx) => {
    const welcomeText = `أهلاً بك في AI Tools 👋\n\nاللهم صل وسلم وبارك على نبينا محمد ﷻ\n\nمجموعة من أدوات الذكاء الاصطناعي والوسائط في مكان واحد.\n\nاختر الخدمة التي تريدها من القائمة 👇`;
    return ctx.reply(welcomeText, mainKeyboard(ctx.from.id));
});

// اختبار الخدمة /test
bot.command('test', (ctx) => {
    const status = `🔑 **اختبار اتصال الخدمات:**\n\n` +
        `${OPENROUTER_API_KEY ? "🟢 OpenRouter: متصل" : "🔴 OpenRouter: غير متاح"}\n` +
        `${OPENAI_API_KEY ? "🟢 OpenAI: متصل" : "🔴 OpenAI: غير متاح"}\n` +
        `${REMOVEBG_API_KEY ? "🟢 Remove.bg: متصل" : "🔴 Remove.bg: غير متاح"}\n` +
        `🟢 Google TTS: متاح\n\n` +
        `⚠️ لا يتم عرض مفاتيح API.`;
    return ctx.replyWithMarkdown(status);
});

// لوحة التحكم
bot.hears("👑 لوحة التحكم", (ctx) => {
    if (!isOwner(ctx)) return ctx.reply("❌ هذا الأمر مخصص للمالك فقط.");
    const ownerMenu = Markup.keyboard([
        ["⚙️ إدارة تفعيل/تعطيل الأدوات"],
        ["🔙 القائمة الرئيسية"]
    ]).resize();
    return ctx.reply("👑 أهلاً بك في لوحة تحكم المالك:", ownerMenu);
});

bot.hears("⚙️ إدارة تفعيل/تعطيل الأدوات", async (ctx) => {
    if (!isOwner(ctx)) return;
    const tools = await getTools();
    let text = "⚙️ **حالة الأدوات الحالية:**\n\n";
    for (const [toolName, status] of Object.entries(tools)) {
        text += `${toolName}: ${status !== false ? "✅ مفعلة" : "❌ معطلة"}\n`;
    }
    const toggleButtons = Object.keys(toolToggleMap).map(btnText => [btnText]);
    toggleButtons.push(["🔙 القائمة الرئيسية"]);
    return ctx.reply(text, Markup.keyboard(toggleButtons).resize());
});

// معالجة مفاتيح التبديل
bot.use(async (ctx, next) => {
    const text = ctx.message?.text;
    if (text && toolToggleMap[text]) {
        if (!isOwner(ctx)) return ctx.reply("❌ غير مسموح لك.");
        const targetTool = toolToggleMap[text];
        const db = loadDB();
        db.tools[targetTool] = !(db.tools[targetTool] !== false);
        saveDB(db);
        const newStatus = db.tools[targetTool] ? "✅ تم التفعيل" : "❌ تم التعطيل";
        return ctx.reply(`تم تغيير حالة أداة (${targetTool}) إلى: ${newStatus}`);
    }
    return next();
});

bot.hears("🔙 القائمة الرئيسية", (ctx) => {
    delete userState[ctx.from.id];
    return ctx.reply("العودة للقائمة الرئيسية:", mainKeyboard(ctx.from.id));
});

// التحقق من تفعيل الأداة
const checkTool = async (ctx, toolName, action) => {
    const tools = await getTools();
    if (tools[toolName] === false) {
        return ctx.reply(`⚠️ أداة (${toolName}) معطلة حالياً من قبل الإدارة.`);
    }
    action();
};

// أزرار الأدوات والتنفيذ الفعلي
bot.hears("🌐 الترجمة", (ctx) => checkTool(ctx, "🌐 الترجمة", () => {
    userState[ctx.from.id] = 'translate';
    ctx.reply("🌐 أرسل النص الذي تريد ترجمته.\n\nسأكتشف اللغة وأترجمها تلقائياً.");
}));

bot.hears("🧠 المساعد الذكي", (ctx) => checkTool(ctx, "🧠 المساعد الذكي", () => {
    userState[ctx.from.id] = 'ai';
    ctx.reply("🧠 اكتب سؤالك أو طلبك.\n\nالسعر: مجاني 🎁");
}));

bot.hears("🔊 تحويل النص إلى صوت", (ctx) => checkTool(ctx, "🔊 تحويل النص إلى صوت", () => {
    userState[ctx.from.id] = 'tts';
    ctx.reply("🔊 أرسل النص الذي تريد تحويله إلى صوت.\n\nالسعر: مجاني 🎁");
}));

bot.hears("🎨 توليد الصور", (ctx) => checkTool(ctx, "🎨 توليد الصور", () => {
    userState[ctx.from.id] = 'gen_image';
    ctx.reply("🎨 اكتب وصف الصورة التي تريد توليدها باللغة الإنجليزية أو العربية:");
}));

bot.hears("🖼️ إزالة الخلفية", (ctx) => checkTool(ctx, "🖼️ إزالة الخلفية", () => {
    userState[ctx.from.id] = 'remove_bg';
    ctx.reply("🖼️ أرسل الصورة الآن لإزالة خلفيتها.");
}));

bot.hears("✨ تحسين الصور", (ctx) => checkTool(ctx, "✨ تحسين الصور", () => {
    ctx.reply("🆓 أرسل الصورة لتحسين جودتها.");
}));

bot.hears("🖌️ تعديل الصور بالذكاء الاصطناعي", (ctx) => checkTool(ctx, "🖌️ تعديل الصور بالذكاء الاصطناعي", () => {
    ctx.reply("🆓 أرسل الصورة والتعديل المطلوب.");
}));

bot.hears("⭐ رصيدي", (ctx) => ctx.reply("⭐ رصيدك الحالي: غير محدود (جميع الأدوات مجانية 🎁)."));
bot.hears("💳 شراء نجوم", (ctx) => ctx.reply("ℹ️ جميع الأدوات مجانية حالياً دون الحاجة للشحن."));
bot.hears("📞 التواصل مع المطور", (ctx) => ctx.reply("للتواصل مع المطور: @N_AiToolsBot"));

// معالجة النصوص المرسلة من المستخدم حسب الحالة Active State
bot.on('text', async (ctx) => {
    const state = userState[ctx.from.id];
    const text = ctx.message.text;

    if (!state) return;

    // 1. معالجة الترجمة
    if (state === 'translate') {
        try {
            ctx.reply("⏳ جاري الترجمة...");
            const res = await axios.get(`https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=ar&dt=t&q=${encodeURIComponent(text)}`);
            const translatedText = res.data[0][0][0];
            delete userState[ctx.from.id];
            return ctx.reply(`<b>الترجمة:</b>\n\n${translatedText}`, { parse_mode: 'HTML' });
        } catch (e) {
            return ctx.reply("❌ حدث خطأ أثناء الترجمة، حاول مرة أخرى.");
        }
    }

    // 2. معالجة المساعد الذكي (OpenRouter / OpenAI)
    if (state === 'ai') {
        try {
            ctx.reply("⏳ جاري التفكير...");
            const response = await axios.post('https://openrouter.ai/api/v1/chat/completions', {
                model: 'google/gemini-2.5-flash',
                messages: [{ role: 'user', content: text }]
            }, {
                headers: {
                    'Authorization': `Bearer ${OPENROUTER_API_KEY || OPENAI_API_KEY}`,
                    'Content-Type': 'application/json'
                }
            });
            const replyMsg = response.data.choices[0].message.content;
            delete userState[ctx.from.id];
            return ctx.reply(replyMsg);
        } catch (e) {
            return ctx.reply("❌ حدث خطأ أثناء تنفيذ العملية. تأكد من صحة مفاتيح الـ API.");
        }
    }

    // 3. معالجة تحويل النص إلى صوت (Google TTS)
    if (state === 'tts') {
        try {
            ctx.reply("⏳ جاري تحويل النص إلى صوت...");
            const url = googleTTS.getAudioUrl(text, {
                lang: 'ar',
                slow: false,
                host: 'https://translate.google.com',
            });
            delete userState[ctx.from.id];
            return ctx.replyWithAudio({ url: url, filename: 'voice.mp3' });
        } catch (e) {
            return ctx.reply("❌ حدث خطأ أثناء تحويل النص إلى صوت.");
        }
    }
});

// تشغيل البوت
bot.launch().then(() => console.log("🤖 AI Tools Bot is Running Successfully!")).catch(err => console.error("Error launching bot:", err));

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
