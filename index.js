const { Telegraf, Markup } = require('telegraf');
const fs = require('fs');
const axios = require('axios');

// قراءة المفاتيح آمنة من متغيرات البيئة
const BOT_TOKEN = process.env.BOT_TOKEN;
const OWNER_ID = 8860453018;

const OPENROUTER_KEY = process.env.OPENROUTER_API_KEY;
const OPENAI_KEY = process.env.OPENAI_API_KEY;
const REMOVEBG_KEY = process.env.REMOVEBG_API_KEY;

const bot = new Telegraf(BOT_TOKEN);
const DB_FILE = './database.json';
const userState = new Map();

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

async function getTools() {
    return loadDB().tools;
}

const isOwner = (ctx) => ctx.from && Number(ctx.from.id) === OWNER_ID;

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
    userState.delete(ctx.from.id);
    return ctx.reply("أهلاً بك في AI Tools 👋\nاختر الخدمة من القائمة:", mainKeyboard(ctx.from.id));
});

bot.launch().then(() => {
    console.log("🚀 Bot Started");
});

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
    return ctx.reply(welcomeText, mainKeyboard(ctx.from.id));
});

// --- معالجة الضغط على الأدوات ---
bot.hears("🖼️ إزالة الخلفية", (ctx) => checkToolActive(ctx, "🖼️ إزالة الخلفية", (ctx) => {
    userState.set(ctx.from.id, 'removebg');
    ctx.reply("🖼️ أرسل الصورة الآن لإزالة خلفيتها.");
}));

bot.hears("🌐 الترجمة", (ctx) => checkToolActive(ctx, "🌐 الترجمة", (ctx) => {
    userState.set(ctx.from.id, 'translate');
    ctx.reply("🌐 أرسل النص الذي تريد ترجمته إلى العربية/الإنجليزية.");
}));

bot.hears("🎨 توليد الصور", (ctx) => checkToolActive(ctx, "🎨 توليد الصور", (ctx) => {
    userState.set(ctx.from.id, 'generate');
    ctx.reply("🎨 اكتب وصف الصورة التي تريد إنشاءها بالإنجليزية أو العربية.");
}));

bot.hears("🧠 المساعد الذكي", (ctx) => checkToolActive(ctx, "🧠 المساعد الذكي", (ctx) => {
    userState.set(ctx.from.id, 'ai_chat');
    ctx.reply("🧠 أهلاً بك! اكتب أي سؤال وسأجيبك فوراً باستخدام الذكاء الاصطناعي.");
}));

bot.hears("🔊 تحويل النص إلى صوت", (ctx) => checkToolActive(ctx, "🔊 تحويل النص إلى صوت", (ctx) => {
    userState.set(ctx.from.id, 'tts');
    ctx.reply("🔊 أرسل النص الذي تريد تحويله إلى مقطع صوتي.");
}));

bot.hears("✨ تحسين الصور", (ctx) => checkToolActive(ctx, "✨ تحسين الصور", (ctx) => {
    ctx.reply("✨ أداة تحسين الصور قيد الصيانة حالياً.");
}));

bot.hears("🖌️ تعديل الصور بالذكاء الاصطناعي", (ctx) => checkToolActive(ctx, "🖌️ تعديل الصور بالذكاء الاصطناعي", (ctx) => {
    ctx.reply("🖌️ أداة تعديل الصور قيد التحديث.");
}));

bot.hears("⭐ رصيدي", (ctx) => {
    ctx.reply("⭐ رصيدك الحالي: غير محدود (جميع الأدوات مجانية 🎁).");
});

bot.hears("💳 شراء نجوم", (ctx) => {
    ctx.reply("ℹ️ جميع أدوات البوت مجانية 100% ولا تتطلب أي شحن!");
});

bot.hears("📞 التواصل مع المطور", (ctx) => {
    ctx.reply("📞 للتواصل مع المطور:\n @N3_UNK");
});

// --- لوحة تحكم المالك ---
bot.hears("👑 لوحة التحكم", async (ctx) => {
    if (!isOwner(ctx)) return ctx.reply("❌ هذا الأمر مخصص للمالك فقط.");

    const ownerMenu = Markup.keyboard([
        ["⚙️ إدارة تفعيل/تعطيل الأدوات"],
        ["📊 الإحصائيات"],
        ["🔙 القائمة الرئيسية"]
    ]).resize();

    return ctx.reply("👑 أهلاً بك في لوحة تحكم المالك:", ownerMenu);
});

bot.hears("⚙️ إدارة تفعيل/تعطيل الأدوات", async (ctx) => {
    if (!isOwner(ctx)) return;
    const tools = await getTools();

    let text = "⚙️ **حالة الأدوات الحالية:**\n\n";
    for (const [toolName, status] of Object.entries(tools)) {
        text += `${toolName}: ${status ? "✅ مفعلة" : "❌ معطلة"}\n`;
    }

    const toggleButtons = Object.keys(toolToggleMap).map(btnText => [btnText]);
    toggleButtons.push(["🔙 القائمة الرئيسية"]);

    return ctx.reply(text, Markup.keyboard(toggleButtons).resize());
});

bot.hears("📊 الإحصائيات", async (ctx) => {
    if (!isOwner(ctx)) return;
    return ctx.reply("📊 **إحصائيات البوت:**\n\n• الحالة: شغال 100% ✅\n• المفاتيح: مدمجة بنجاح 🔑");
});

// --- التبديل في الإعدادات ---
bot.use(async (ctx, next) => {
    const text = ctx.message?.text;
    if (text && toolToggleMap[text]) {
        if (!isOwner(ctx)) return ctx.reply("❌ هذا الإجراء مخصص للمالك فقط.");

        const targetTool = toolToggleMap[text];
        const db = loadDB();

        db.tools[targetTool] = !db.tools[targetTool];
        saveDB(db);

        const newStatus = db.tools[targetTool] ? "✅ تم التفعيل" : "❌ تم التعطيل";
        return ctx.reply(`تم تغيير حالة أداة (${targetTool}) إلى: ${newStatus}`);
    }
    return next();
});

// --- معالجة الصور والنصوص (الخدمات الفعليه) ---
bot.on('photo', async (ctx) => {
    const state = userState.get(ctx.from.id);
    if (state === 'removebg') {
        ctx.reply('⏳ جاري إزالة الخلفية، انتظر لحظة...');
        try {
            const photo = ctx.message.photo[ctx.message.photo.length - 1];
            const fileLink = await ctx.telegram.getFileLink(photo.file_id);
            
            const response = await axios.post('https://api.remove.bg/v1.0/removebg', {
                image_url: fileLink.href,
                size: 'auto'
            }, {
                headers: { 'X-Api-Key': REMOVEBG_KEY },
                responseType: 'arraybuffer'
            });

            await ctx.replyWithDocument({ source: Buffer.from(response.data), filename: 'no-bg.png' }, { caption: '✅ تمت إزالة الخلفية بنجاح!' });
        } catch (err) {
            ctx.reply('❌ فشلت إزالة الخلفية، تأكد من رصيد المفتاح أو الصورة.');
        }
        userState.delete(ctx.from.id);
    }
});

bot.on('text', async (ctx) => {
    const text = ctx.message.text;
    const userId = ctx.from.id;
    const state = userState.get(userId);

    if (text === "🔙 القائمة الرئيسية") {
        userState.delete(userId);
        return ctx.reply("العودة للقائمة الرئيسية:", mainKeyboard(userId));
    }

    if (state === 'ai_chat' || state === 'translate') {
        ctx.reply('⏳ جاري المعالجة...');
        try {
            const prompt = state === 'translate' ? `Translate this text accurately: ${text}` : text;
            const res = await axios.post('https://openrouter.ai/api/v1/chat/completions', {
                model: 'openai/gpt-4o-mini',
                messages: [{ role: 'user', content: prompt }]
            }, {
                headers: { 'Authorization': `Bearer ${OPENROUTER_KEY}`, 'Content-Type': 'application/json' }
            });

            const reply = res.data.choices[0].message.content;
            ctx.reply(reply);
        } catch (e) {
            ctx.reply('❌ حدث خطأ أثناء الاتصال بالذكاء الاصطناعي.');
        }
        userState.delete(userId);
    } else if (state === 'generate') {
        ctx.reply('🎨 جاري توليد الصورة، يرجى الانتظار...');
        try {
            const res = await axios.post('https://api.openai.com/v1/images/generations', {
                model: 'dall-e-3',
                prompt: text,
                n: 1,
                size: '1024x1024'
            }, {
                headers: { 'Authorization': `Bearer ${OPENAI_KEY}`, 'Content-Type': 'application/json' }
            });

            const imageUrl = res.data.data[0].url;
            ctx.replyWithPhoto(imageUrl, { caption: '✨ تم إنشاء الصورة بنجاح!' });
        } catch (e) {
            ctx.reply('❌ فشل إنشاء الصورة.');
        }
        userState.delete(userId);
    } else if (state === 'tts') {
        const ttsUrl = `https://translate.google.com/translate_tts?ie=UTF-8&q=${encodeURIComponent(text)}&tl=ar&client=tw-ob`;
        ctx.replyWithAudio({ url: ttsUrl, title: 'AI Voice' });
        userState.delete(userId);
    }
});

// --- تشغيل البوت ---
bot.launch().then(() => {
    console.log("🚀 AI Tools Bot is running successfully with embedded keys!");
}).catch((err) => {
    console.error("❌ Error launching bot:", err);
});

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
    fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2));
}

async function getTools() {
    const db = loadDB();
    return db.tools;
}

// --- دالة الحماية والتحقق من المالك ---
const isOwner = (ctx) => ctx.from && Number(ctx.from.id) === OWNER_ID;

// --- خريطة أزرار لوحة التحكم بالتفعيل/التعطيل ---
const toolToggleMap = {
    "إلغاء/تفعيل إزالة الخلفية": "🖼️ إزالة الخلفية",
    "إلغاء/تفعيل الترجمة": "🌐 الترجمة",
    "إلغاء/تفعيل تحسين الصور": "✨ تحسين الصور",
    "إلغاء/تفعيل توليد الصور": "🎨 توليد الصور",
    "إلغاء/تفعيل تعديل الصور": "🖌️ تعديل الصور بالذكاء الاصطناعي",
    "إلغاء/تفعيل المساعد الذكي": "🧠 المساعد الذكي",
    "إلغاء/تفعيل تحويل النص لصوت": "🔊 تحويل النص إلى صوت"
};

// --- لوحة الأزرار الرئيسية (تطابق الصورة تماماً) ---
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

// --- فحص هل الأداة مفعلة قبل التشغيل ---
const checkToolActive = async (ctx, toolName, handler) => {
    const tools = await getTools();
    if (tools[toolName] === false) {
        return ctx.reply(`⚠️ أداة (${toolName}) معطلة حالياً من قبل الإدارة.`);
    }
    return handler(ctx);
};

// --- الواجهة الترحيبية /start ---
bot.start((ctx) => {
    const welcomeText = `أهلاً بك في AI Tools 👋\n\nاللهم صل وسلم وبارك على نبينا محمد ﷻ\n\nمجموعة من أدوات الذكاء الاصطناعي والوسائط في مكان واحد.\n\nاختر الخدمة التي تريدها من القائمة 👇`;
    return ctx.reply(welcomeText, mainKeyboard(ctx.from.id));
});

// --- معالجة أزرار الأدوات الأساسية (جميعها مجانية) ---
bot.hears("🖼️ إزالة الخلفية", (ctx) => checkToolActive(ctx, "🖼️ إزالة الخلفية", (ctx) => {
    ctx.reply("🆓 أداة إزالة الخلفية (مجانية):\nيرجى إرسال الصورة الآن لإزالة خلفيتها.");
}));

bot.hears("🌐 الترجمة", (ctx) => checkToolActive(ctx, "🌐 الترجمة", (ctx) => {
    ctx.reply("🆓 أداة الترجمة (مجانية):\nأرسل النص الذي تريد ترجمته الآن.");
}));

bot.hears("✨ تحسين الصور", (ctx) => checkToolActive(ctx, "✨ تحسين الصور", (ctx) => {
    ctx.reply("🆓 أداة تحسين الصور (مجانية):\nأرسل الصورة المراد تحسين جودتها.");
}));

bot.hears("🎨 توليد الصور", (ctx) => checkToolActive(ctx, "🎨 توليد الصور", (ctx) => {
    ctx.reply("🆓 أداة توليد الصور (مجانية):\nاكتب وصف الصورة التي تريد إنشاءها.");
}));

bot.hears("🖌️ تعديل الصور بالذكاء الاصطناعي", (ctx) => checkToolActive(ctx, "🖌️ تعديل الصور بالذكاء الاصطناعي", (ctx) => {
    ctx.reply("🆓 أداة تعديل الصور (مجانية):\nأرسل الصورة مع كتابة التعديل المطلوب.");
}));

bot.hears("🧠 المساعد الذكي", (ctx) => checkToolActive(ctx, "🧠 المساعد الذكي", (ctx) => {
    ctx.reply("🆓 المساعد الذكي (مجاني):\nأهلاً بك! اكتب سؤالك وسأجيبك فوراً.");
}));

bot.hears("🔊 تحويل النص إلى صوت", (ctx) => checkToolActive(ctx, "🔊 تحويل النص إلى صوت", (ctx) => {
    ctx.reply("🆓 تحويل النص إلى صوت (مجاني):\nأرسل النص الذي تريد تحويله إلى مقطع صوتي.");
}));

// --- الأزرار الشخصية والشحن ---
bot.hears("⭐ رصيدي", (ctx) => {
    ctx.reply("⭐ رصيدك الحالي: غير محدود (جميع الأدوات متاحة بشكل مجاني بالكامل 🎁).");
});

bot.hears("💳 شراء نجوم", (ctx) => {
    ctx.reply("ℹ️ جميع أدوات البوت حالياً مجانية 100% ولا تتطلب أي عملية شراء أو شحن!");
});

bot.hears("📞 التواصل مع المطور", (ctx) => {
    ctx.reply("📞 للتواصل المباشر مع المطور الدعم الفني:\n اضغط هنا: @YourUsername");
});

// --- لوحة تحكم المالك ---
bot.hears("👑 لوحة التحكم", async (ctx) => {
    if (!isOwner(ctx)) return ctx.reply("❌ هذا الأمر مخصص للمالك فقط.");

    const ownerMenu = Markup.keyboard([
        ["⚙️ إدارة تفعيل/تعطيل الأدوات"],
        ["📊 الإحصائيات"],
        ["🔙 القائمة الرئيسية"]
    ]).resize();

    return ctx.reply("👑 أهلاً بك في لوحة تحكم المالك:", ownerMenu);
});

// --- قائمة التفعيل والتعطيل للمالك ---
bot.hears("⚙️ إدارة تفعيل/تعطيل الأدوات", async (ctx) => {
    if (!isOwner(ctx)) return;
    const tools = await getTools();

    let text = "⚙️ **حالة الأدوات الحالية:**\n\n";
    for (const [toolName, status] of Object.entries(tools)) {
        text += `${toolName}: ${status ? "✅ مفعلة" : "❌ معطلة"}\n`;
    }

    const toggleButtons = Object.keys(toolToggleMap).map(btnText => [btnText]);
    toggleButtons.push(["🔙 القائمة الرئيسية"]);

    return ctx.reply(text, Markup.keyboard(toggleButtons).resize());
});

bot.hears("📊 الإحصائيات", async (ctx) => {
    if (!isOwner(ctx)) return;
    return ctx.reply("📊 **إحصائيات البوت:**\n\n• حالة البوت: يعمل بنجاح ✅\n• نظام الأدوات: مجاني بالكامل 🆓");
});

// --- معالج التبديل (Tool Toggle Handler) ---
bot.use(async (ctx, next) => {
    const text = ctx.message?.text;
    if (text && toolToggleMap[text]) {
        if (!isOwner(ctx)) return ctx.reply("❌ هذا الإجراء مخصص للمالك فقط.");

        const targetTool = toolToggleMap[text];
        const db = loadDB();

        db.tools[targetTool] = !db.tools[targetTool];
        saveDB(db);

        const newStatus = db.tools[targetTool] ? "✅ تم التفعيل" : "❌ تم التعطيل";
        return ctx.reply(`تم تغيير حالة أداة (${targetTool}) إلى: ${newStatus}`);
    }
    return next();
});

// --- زر العودة ---
bot.hears("🔙 القائمة الرئيسية", (ctx) => {
    return ctx.reply("العودة للقائمة الرئيسية:", mainKeyboard(ctx.from.id));
});

// --- تشغيل البوت مع الدعم الدائم على Railway ---
bot.launch().then(() => {
    console.log("🚀 AI Tools Bot is successfully running!");
});

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
