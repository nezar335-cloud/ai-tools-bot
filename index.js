const { Telegraf, Markup } = require('telegraf');
const axios = require('axios');
const fs = require('fs');
const googleTTS = require('google-tts-api');

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
const userState = {};

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

bot.start((ctx) => {
    const welcomeText = `أهلاً بك في AI Tools 👋\n\nاللهم صل وسلم وبارك على نبينا محمد ﷻ\n\nمجموعة من أدوات الذكاء الاصطناعي والوسائط في مكان واحد.\n\nاختر الخدمة التي تريدها من القائمة 👇`;
    return ctx.reply(welcomeText, mainKeyboard(ctx.from.id));
});

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

const checkTool = async (ctx, toolName, action) => {
    const tools = await getTools();
    if (tools[toolName] === false) {
        return ctx.reply(`⚠️ أداة (${toolName}) معطلة حالياً من قبل الإدارة.`);
    }
    action();
};

bot.hears("🌐 الترجمة", (ctx) => checkTool(ctx, "🌐 الترجمة", () => {
    userState[ctx.from.id] = 'translate';
    ctx.reply("🌐 أرسل النص الذي تريد ترجمته.");
}));

bot.hears("🧠 المساعد الذكي", (ctx) => checkTool(ctx, "🧠 المساعد الذكي", () => {
    userState[ctx.from.id] = 'ai';
    ctx.reply("🧠 اكتب سؤالك أو طلبك.");
}));

bot.hears("🔊 تحويل النص إلى صوت", (ctx) => checkTool(ctx, "🔊 تحويل النص إلى صوت", () => {
    userState[ctx.from.id] = 'tts';
    ctx.reply("🔊 أرسل النص الذي تريد تحويله إلى صوت.");
}));

bot.hears("🎨 توليد الصور", (ctx) => checkTool(ctx, "🎨 توليد الصور", () => {
    ctx.reply("🎨 أرسل وصف الصورة.");
}));

bot.hears("🖼️ إزالة الخلفية", (ctx) => checkTool(ctx, "🖼️ إزالة الخلفية", () => {
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

bot.on('text', async (ctx) => {
    const state = userState[ctx.from.id];
    const text = ctx.message.text;

    if (!state) return;

    if (state === 'translate') {
        try {
            const res = await axios.get(`https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=ar&dt=t&q=${encodeURIComponent(text)}`);
            delete userState[ctx.from.id];
            return ctx.reply(`<b>الترجمة:</b>\n\n${res.data[0][0][0]}`, { parse_mode: 'HTML' });
        } catch (e) {
            return ctx.reply("❌ حدث خطأ أثناء الترجمة.");
        }
    }

    if (state === 'ai') {
        try {
            const response = await axios.post('https://openrouter.ai/api/v1/chat/completions', {
                model: 'google/gemini-2.5-flash',
                messages: [{ role: 'user', content: text }]
            }, {
                headers: {
                    'Authorization': `Bearer ${OPENROUTER_API_KEY || OPENAI_API_KEY}`,
                    'Content-Type': 'application/json'
                }
            });
            delete userState[ctx.from.id];
            return ctx.reply(response.data.choices[0].message.content);
        } catch (e) {
            return ctx.reply("❌ حدث خطأ في معالجة طلب الذكاء الاصطناعي.");
        }
    }

    if (state === 'tts') {
        try {
            const url = googleTTS.getAudioUrl(text, { lang: 'ar', slow: false, host: 'https://translate.google.com' });
            delete userState[ctx.from.id];
            return ctx.replyWithAudio({ url: url, filename: 'voice.mp3' });
        } catch (e) {
            return ctx.reply("❌ حدث خطأ في تحويل الصوت.");
        }
    }
});

bot.launch().then(() => console.log("🤖 AI Tools Bot is Running Successfully!")).catch(err => console.error("Error launching bot:", err));

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
