const { Telegraf, Markup } = require('telegraf');
const fs = require('fs');

// يمكنك وضع التوكين هنا مباشرة أو ضبطه في متغيرات بيئة Railway باسم BOT_TOKEN
const BOT_TOKEN = process.env.BOT_TOKEN || 'ضع_توكين_البوت_هنا';
const OWNER_ID = 8860453018;

const bot = new Telegraf(BOT_TOKEN);
const DB_FILE = './database.json';

// --- إدارة قاعدة البيانات المحلية ---
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
            },
            users: {}
        };
        fs.writeFileSync(DB_FILE, JSON.stringify(defaultDB, null, 2));
        return defaultDB;
    }
    try {
        return JSON.parse(fs.readFileSync(DB_FILE));
    } catch (e) {
        return { tools: {}, users: {} };
    }
}

function saveDB(data) {
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
