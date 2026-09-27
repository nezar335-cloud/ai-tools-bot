const { Telegraf, Markup } = require('telegraf');
const { execFile } = require('child_process');
const { promisify } = require('util');
const ffmpegPath = require('ffmpeg-static');
const execFileAsync = promisify(execFile);
const fs = require('fs');
const path = require('path');
const axios = require('axios');
const FormData = require('form-data');

// ========== التهيئة ==========
const BOT_TOKEN = (process.env.BOT_TOKEN || '').trim();
const OWNER_ID = String(process.env.OWNER_ID || '').trim();
const DEVELOPER_URL = process.env.DEVELOPER_URL || 'https://t.me/N3_UNK';
const REMOVEBG_API_KEY = (process.env.REMOVEBG_API_KEY || '').trim();
const GROQ_API_KEY = (process.env.GROQ_API_KEY || '').trim();
if (!BOT_TOKEN) throw new Error('❌ BOT_TOKEN غير موجود');
if (!OWNER_ID) throw new Error('❌ OWNER_ID غير موجود');

const bot = new Telegraf(BOT_TOKEN);

async function transcodePreviewIfNeeded(inputPath, outputPath) {
  await execFileAsync(
    ffmpegPath,
    [
      '-y', '-i', inputPath,
      '-vf', "scale='if(gt(iw,ih),854,-2)':'if(gt(iw,ih),-2,480)',fps=30",
      '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '30',
      '-c:a', 'aac', '-b:a', '96k',
      '-movflags', '+faststart',
      outputPath
    ],
    { timeout: 180000 }
  );
}

// ========== قاعدة البيانات ==========
const DB_FILE = path.join(__dirname, 'bot_data.json');
const TMP_DIR = path.join(__dirname, 'tmp');

if (!fs.existsSync(TMP_DIR)) {
  fs.mkdirSync(TMP_DIR, { recursive: true });
}

const DEFAULT_DB = {
  users: {},
  stats: {
    messages: 0,
    starts: 0
  },

  tools: {
    removebg: true,
    qr: true,
    stt: true,
    xo: true
  },

  prices: {
    removebg: 0,
    qr: 0,
    stt: 0,
    xo: 0
  },

  discounts: {
    removebg: 0,
    qr: 0,
    stt: 0,
    xo: 0
  }
};

function loadDB() {
  try {
    if (!fs.existsSync(DB_FILE)) {
      saveDB(DEFAULT_DB);
      return JSON.parse(JSON.stringify(DEFAULT_DB));
    }

    const data = JSON.parse(
      fs.readFileSync(DB_FILE, 'utf8')
    );

    if (!data.users) data.users = {};
    if (!data.stats) data.stats = {};

    if (typeof data.stats.messages !== 'number') {
      data.stats.messages = 0;
    }

    if (typeof data.stats.starts !== 'number') {
      data.stats.starts = 0;
    }

    // ========== الأدوات ==========
    if (!data.tools) data.tools = {};

    for (const key of Object.keys(DEFAULT_DB.tools)) {
      if (typeof data.tools[key] !== 'boolean') {
        data.tools[key] = DEFAULT_DB.tools[key];
      }
    }

    delete data.tools.tts;
    delete data.tools.download;

    // ========== الأسعار ==========
    if (!data.prices) data.prices = {};

    for (const key of Object.keys(DEFAULT_DB.prices)) {
      if (
        typeof data.prices[key] !== 'number' ||
        data.prices[key] < 0
      ) {
        data.prices[key] = DEFAULT_DB.prices[key];
      }
    }

    delete data.prices.tts;
    delete data.prices.download;

    // ========== الخصومات ==========
    if (!data.discounts) data.discounts = {};

    for (const key of Object.keys(DEFAULT_DB.discounts)) {
      if (
        typeof data.discounts[key] !== 'number' ||
        data.discounts[key] < 0 ||
        data.discounts[key] > 100
      ) {
        data.discounts[key] =
          DEFAULT_DB.discounts[key];
      }
    }

    delete data.discounts.tts;
    delete data.discounts.download;

    saveDB(data);

    return data;
  } catch (err) {
    console.error(
      '❌ DB read error:',
      err && err.message ? err.message : err
    );

    try {
      saveDB(DEFAULT_DB);
    } catch (_) {}

    return JSON.parse(
      JSON.stringify(DEFAULT_DB)
    );
  }
}

function saveDB(data) {
  try {
    fs.writeFileSync(
      DB_FILE,
      JSON.stringify(data, null, 2),
      'utf8'
    );
  } catch (err) {
    console.error(
      '❌ DB write error:',
      err && err.message ? err.message : err
    );
  }
}

loadDB();

// ========== تعريف الأدوات ==========
const TOOL_INFO = {
  removebg: {
    name: '🖼️ إزالة خلفية',
    priceName: 'إزالة الخلفية'
  },

  qr: {
    name: '🔲 إنشاء QR',
    priceName: 'إنشاء QR'
  },

  stt: {
    name: '🎤 تحويل صوت إلى نص',
    priceName: 'تحويل صوت إلى نص'
  },

  xo: {
    name: '🎮 لعبة X و O',
    priceName: 'لعبة X و O'
  }
};

function isToolEnabled(toolKey) {
  const db = loadDB();

  return (
    db.tools &&
    db.tools[toolKey] === true
  );
}

function getToolPrice(toolKey) {
  const db = loadDB();

  return Number(
    db.prices &&
    db.prices[toolKey] !== undefined
      ? db.prices[toolKey]
      : 0
  );
}

function getToolDiscount(toolKey) {
  const db = loadDB();

  const value = Number(
    db.discounts &&
    db.discounts[toolKey] !== undefined
      ? db.discounts[toolKey]
      : 0
  );

  if (!Number.isFinite(value)) {
    return 0;
  }

  return Math.min(
    100,
    Math.max(0, value)
  );
}

function getFinalToolPrice(toolKey) {
  const basePrice =
    getToolPrice(toolKey);

  const discount =
    getToolDiscount(toolKey);

  if (basePrice <= 0) {
    return 0;
  }

  if (discount >= 100) {
    return 0;
  }

  const finalPrice =
    Math.floor(
      basePrice *
      (100 - discount) /
      100
    );

  return Math.max(
    0,
    finalPrice
  );
}

function formatPrice(price) {
  return Number(price) === 0
    ? 'مجاني'
    : `${price} رصيد`;
}

function formatToolPrice(toolKey) {
  const basePrice =
    getToolPrice(toolKey);

  const discount =
    getToolDiscount(toolKey);

  const finalPrice =
    getFinalToolPrice(toolKey);

  if (basePrice === 0) {
    return 'مجاني';
  }

  if (discount <= 0) {
    return `${basePrice} رصيد`;
  }

  return `${basePrice} رصيد → ${finalPrice} رصيد (${discount}% خصم)`;
}

// ========== إدارة خصم الأداة ==========
function getUserBalance(userId) {
  const db = loadDB();
  const id = String(userId);

  if (!db.users[id]) {
    return null;
  }

  return Number(
    db.users[id].balance || 0
  );
}

function addUserBalance(userId, amount) {
  const db = loadDB();
  const id = String(userId);

  if (!db.users[id]) {
    return {
      success: false,
      message: '❌ المستخدم غير موجود.'
    };
  }

  const value = Number(amount);

  if (
    !Number.isSafeInteger(value) ||
    value <= 0
  ) {
    return {
      success: false,
      message: '❌ المبلغ غير صالح.'
    };
  }

  const oldBalance =
    Number(db.users[id].balance || 0);

  const newBalance =
    oldBalance + value;

  if (!Number.isSafeInteger(newBalance)) {
    return {
      success: false,
      message: '❌ الرصيد أصبح أكبر من الحد المسموح.'
    };
  }

  db.users[id].balance =
    newBalance;

  saveDB(db);

  return {
    success: true,
    oldBalance,
    newBalance
  };
}

function removeUserBalance(userId, amount) {
  const db = loadDB();
  const id = String(userId);

  if (!db.users[id]) {
    return {
      success: false,
      message: '❌ المستخدم غير موجود.'
    };
  }

  const value = Number(amount);

  if (
    !Number.isSafeInteger(value) ||
    value <= 0
  ) {
    return {
      success: false,
      message: '❌ المبلغ غير صالح.'
    };
  }

  const oldBalance =
    Number(db.users[id].balance || 0);

  const newBalance =
    Math.max(
      0,
      oldBalance - value
    );

  db.users[id].balance =
    newBalance;

  saveDB(db);

  return {
    success: true,
    oldBalance,
    newBalance
  };
}

function setUserBalance(userId, amount) {
  const db = loadDB();
  const id = String(userId);

  if (!db.users[id]) {
    return {
      success: false,
      message: '❌ المستخدم غير موجود.'
    };
  }

  const value = Number(amount);

  if (
    !Number.isSafeInteger(value) ||
    value < 0
  ) {
    return {
      success: false,
      message: '❌ الرصيد غير صالح.'
    };
  }

  db.users[id].balance =
    value;

  saveDB(db);

  return {
    success: true,
    newBalance: value
  };
}

function chargeTool(userId, toolKey) {
  const db = loadDB();
  const id = String(userId);

  if (!db.users[id]) {
    return {
      success: false,
      charged: 0,
      message: '❌ المستخدم غير موجود.'
    };
  }

  const finalPrice =
    getFinalToolPrice(toolKey);

  const balance =
    Number(
      db.users[id].balance || 0
    );

  if (finalPrice <= 0) {
    return {
      success: true,
      charged: 0,
      balance,
      finalPrice: 0
    };
  }

  if (balance < finalPrice) {
    return {
      success: false,
      charged: 0,
      balance,
      finalPrice,
      message:
        `❌ رصيدك غير كافٍ.\n\n💰 رصيدك: ${balance}\n💳 المطلوب: ${finalPrice} رصيد`
    };
  }

  db.users[id].balance =
    balance - finalPrice;

  db.users[id].usage_count =
    Number(
      db.users[id].usage_count || 0
    ) + 1;

  saveDB(db);

  return {
    success: true,
    charged: finalPrice,
    balance:
      balance - finalPrice,
    finalPrice
  };
}

function refundToolCharge(userId, amount) {
  if (
    !Number.isSafeInteger(
      Number(amount)
    ) ||
    Number(amount) <= 0
  ) {
    return false;
  }

  const result =
    addUserBalance(
      userId,
      Number(amount)
    );

  return result.success;
}

// ========== الحالات ==========
const ownerState = new Map();
const userState = new Map();

// ==================================================
// ========== لعبة X و O ==========
// ==================================================

const xoGames = new Map();
let xoGameCounter = 0;

function createGameId() {
  xoGameCounter++;

  return (
    Date.now().toString(36) +
    xoGameCounter.toString(36)
  ).slice(-12);
}

function createXoGame(mode, creatorId) {
  const game = {
    id: createGameId(),
    mode,
    board: Array(9).fill(''),
    turn: 'X',
    status: 'waiting',
    creatorId: String(creatorId),
    playerX: String(creatorId),
    playerO: null,
    winner: null,
    createdAt: Date.now(),

    messageX: null,
    messageO: null
  };

  xoGames.set(game.id, game);

  return game;
}

function getXoGame(gameId) {
  return xoGames.get(gameId);
}

function checkXoWinner(board) {
  const lines = [
    [0, 1, 2],
    [3, 4, 5],
    [6, 7, 8],
    [0, 3, 6],
    [1, 4, 7],
    [2, 5, 8],
    [0, 4, 8],
    [2, 4, 6]
  ];

  for (const [a, b, c] of lines) {
    if (
      board[a] &&
      board[a] === board[b] &&
      board[a] === board[c]
    ) {
      return board[a];
    }
  }

  if (board.every(Boolean)) {
    return 'draw';
  }

  return null;
}

function getPlayerSymbol(game, userId) {
  const id = String(userId);

  if (String(game.playerX) === id) {
    return 'X';
  }

  if (
    game.playerO &&
    String(game.playerO) === id
  ) {
    return 'O';
  }

  return null;
}

function getXoKeyboard(game) {
  const buttons = [];

  for (let row = 0; row < 3; row++) {
    const line = [];

    for (let col = 0; col < 3; col++) {
      const index = row * 3 + col;
      const value = game.board[index];

      line.push(
        Markup.button.callback(
          value || '⬜',
          value
            ? 'xo_noop'
            : `xo_move:${game.id}:${index}`
        )
      );
    }

    buttons.push(line);
  }

  buttons.push([
    Markup.button.callback(
      '🔄 إعادة اللعب',
      `xo_rematch:${game.id}`
    )
  ]);

  buttons.push([
    Markup.button.callback(
      '❌ إنهاء اللعبة',
      `xo_end:${game.id}`
    )
  ]);

  return Markup.inlineKeyboard(buttons);
}

function getXoBoardText(game) {
  let text = '🎮 لعبة X و O\n\n';

  if (game.mode === 'local') {
    text += '📱 لعب على نفس الجوال\n\n';
  } else if (game.mode === 'bot') {
    text += '🤖 ضد البوت\n\n';
  } else {
    text += '👥 ضد مستخدم آخر\n\n';
  }

  text += '❌ = X\n⭕ = O\n\n';

  if (game.status === 'waiting') {
    text += '⏳ في انتظار اللاعب الثاني...';
    return text;
  }

  if (game.status === 'finished') {
    if (game.winner === 'draw') {
      text += '🤝 تعادل!';
    } else {
      text += `🏆 الفائز: ${
        game.winner === 'X'
          ? '❌ X'
          : '⭕ O'
      }`;
    }

    return text;
  }

  if (game.mode === 'bot') {
    text +=
      game.turn === 'X'
        ? '🎯 دورك — ❌ X'
        : '🤖 دور البوت — ⭕ O';
  } else if (game.mode === 'local') {
    text +=
      game.turn === 'X'
        ? '👤 دور اللاعب الأول — ❌ X'
        : '👤 دور اللاعب الثاني — ⭕ O';
  } else {
    text +=
      game.turn === 'X'
        ? '🎯 دور ❌ X'
        : '🎯 دور ⭕ O';
  }

  return text;
}

function renderXoBoard(game) {
  return {
    text: getXoBoardText(game),
    extra: getXoKeyboard(game)
  };
}

// ==================================================
// ========== تحديث لوحات اللعب عن بعد ==========
// ==================================================

async function updateFriendBoards(game) {
  if (
    !game ||
    game.mode !== 'friend'
  ) {
    return;
  }

  const board = renderXoBoard(game);

  if (
    game.playerX &&
    game.messageX
  ) {
    try {
      await bot.telegram.editMessageText(
        String(game.playerX),
        game.messageX,
        undefined,
        board.text,
        board.extra
      );
    } catch (_) {}
  }

  if (
    game.playerO &&
    game.messageO
  ) {
    try {
      await bot.telegram.editMessageText(
        String(game.playerO),
        game.messageO,
        undefined,
        board.text,
        board.extra
      );
    } catch (_) {}
  }
}

// ========== ذكاء البوت ==========
function minimax(board, isMaximizing) {
  const result = checkXoWinner(board);

  if (result === 'O') return 10;
  if (result === 'X') return -10;
  if (result === 'draw') return 0;

  if (isMaximizing) {
    let bestScore = -Infinity;

    for (let i = 0; i < 9; i++) {
      if (!board[i]) {
        board[i] = 'O';

        const score = minimax(
          board,
          false
        );

        board[i] = '';

        bestScore = Math.max(
          bestScore,
          score
        );
      }
    }

    return bestScore;
  }

  let bestScore = Infinity;

  for (let i = 0; i < 9; i++) {
    if (!board[i]) {
      board[i] = 'X';

      const score = minimax(
        board,
        true
      );

      board[i] = '';

      bestScore = Math.min(
        bestScore,
        score
      );
    }
  }

  return bestScore;
}

function getBestBotMove(board) {
  let bestScore = -Infinity;
  let bestMove = null;

  for (let i = 0; i < 9; i++) {
    if (!board[i]) {
      board[i] = 'O';

      const score = minimax(
        board,
        false
      );

      board[i] = '';

      if (score > bestScore) {
        bestScore = score;
        bestMove = i;
      }
    }
  }

  return bestMove;
}

function finishXoGame(game, result) {
  game.status = 'finished';
  game.winner = result;
}

function cleanupOldXoGames() {
  const now = Date.now();

  for (const [id, game] of xoGames.entries()) {
    if (
      now - game.createdAt >
      2 * 60 * 60 * 1000
    ) {
      xoGames.delete(id);
    }
  }
}

setInterval(
  cleanupOldXoGames,
  10 * 60 * 1000
);

// ========== رسالة الترحيب ==========
const welcomeMessage = `﷽

اللهم صلِّ وسلم وبارك على سيدنا محمد ﷺ

أهلاً بك في بوت AI Tools 👋

بوتك لأدوات الذكاء الاصطناعي والخدمات الرقمية ⚡
حمّل، حوّل، عدّل وأنشئ بسهولة.

اختر الأداة التي تريد استخدامها:)`;

// ========== الكيبوردات ==========
const mainKeyboard = Markup.keyboard([
  ['🖼️ إزالة خلفية', '🔲 إنشاء QR'],
  ['🎮 لعبة X و O', '🎤 تحويل صوت إلى نص'],
  ['💰 رصيدي'],
  ['👨‍💻 التواصل مع المطور']
]).resize();

const ownerMainKeyboard = Markup.keyboard([
  ['🖼️ إزالة خلفية', '🔲 إنشاء QR'],
  ['🎮 لعبة X و O', '🎤 تحويل صوت إلى نص'],
  ['💰 رصيدي'],
  ['👨‍💻 التواصل مع المطور'],
  ['👑 لوحة المالك']
]).resize();

const ownerKeyboard = Markup.keyboard([
  ['👥 المستخدمون', '📊 الإحصائيات'],
  ['🟢 الأدوات', '💰 الأسعار'],
  ['🎁 الرصيد', '🚫 الحظر'],
  ['📢 إذاعة', '🏷️ الخصم'],
  ['🔑 اختبار الخدمات'],
  ['⬅️ القائمة الرئيسية']
]).resize();

const btnTexts = [
  '🖼️ إزالة خلفية',
  '🔲 إنشاء QR',
  '🎮 لعبة X و O',
  '🎤 تحويل صوت إلى نص',
  '💰 رصيدي',
  '👨‍💻 التواصل مع المطور',
  '👑 لوحة المالك',
  '👥 المستخدمون',
  '📊 الإحصائيات',
  '🟢 الأدوات',
  '💰 الأسعار',
  '🎁 الرصيد',
  '🚫 الحظر',
  '📢 إذاعة',
  '🏷️ الخصم',
  '🔑 اختبار الخدمات',
  '⬅️ القائمة الرئيسية'
];

// ========== أدوات مساعدة ==========
function safeUnlink(filePath) {
  try {
    if (
      filePath &&
      fs.existsSync(filePath)
    ) {
      fs.unlinkSync(filePath);
    }
  } catch (err) {
    console.error(
      '❌ File delete error:',
      err && err.message
        ? err.message
        : err
    );
  }
}


async function editStatusMessage(ctx, statusMessage, text) {
  if (!statusMessage) return;
  try {
    await ctx.telegram.editMessageText(
      String(ctx.chat.id),
      statusMessage.message_id,
      undefined,
      text
    );
  } catch (_) {}
}

function splitText(
  text,
  maxLength = 200
) {
  const result = [];
  let remaining = String(
    text || ''
  ).trim();

  while (
    remaining.length > maxLength
  ) {
    let cut =
      remaining.lastIndexOf(
        ' ',
        maxLength
      );

    if (cut < 1) {
      cut = maxLength;
    }

    result.push(
      remaining
        .slice(0, cut)
        .trim()
    );

    remaining =
      remaining
        .slice(cut)
        .trim();
  }

  if (remaining) {
    result.push(remaining);
  }

  return result;
}

// ==================================================
// ========== حماية المحظورين ==========
// ==================================================

bot.use(async (ctx, next) => {
  if (!ctx.from) {
    await next();
    return;
  }

  const db = loadDB();
  const userId = String(ctx.from.id);
  const user = db.users[userId];

  if (
    user &&
    user.is_banned &&
    userId !== OWNER_ID
  ) {
    await ctx.reply(
      '🚫 أنت محظور من استخدام البوت.'
    );
    return;
  }

  await next();
});

// ==================================================
// ========== تسجيل المستخدم والإحصائيات ==========
// ==================================================

bot.use(async (ctx, next) => {
  if (!ctx.from) {
    await next();
    return;
  }

  const db = loadDB();
  const userId = String(ctx.from.id);

  if (!db.users[userId]) {
    db.users[userId] = {
      id: ctx.from.id,
      username: ctx.from.username || '',
      first_name: ctx.from.first_name || '',
      joined_at: new Date().toISOString(),
      is_banned: false,
      balance: 0,
      usage_count: 0,
      last_start: 0
    };

    saveDB(db);
  }

  const txt =
    ctx.message &&
    ctx.message.text
      ? ctx.message.text
      : null;

  if (
    txt &&
    !txt.startsWith('/') &&
    !btnTexts.includes(txt)
  ) {
    db.stats.messages =
      Number(db.stats.messages || 0) + 1;

    saveDB(db);
  }

  await next();
});

// ==================================================
// ========== /start ==========
// ==================================================

const SESSION_GAP =
  30 * 60 * 1000;

bot.start(async (ctx) => {
  const userId = String(
    ctx.from.id
  );

  const isOwner =
    userId === OWNER_ID;

  const db = loadDB();
  const now = Date.now();

  const kb = isOwner
    ? ownerMainKeyboard
    : mainKeyboard;

  const payload =
    ctx.startPayload || '';

  if (
    typeof payload === 'string' &&
    payload.startsWith('xo_')
  ) {
    const gameId =
      payload.slice(3);

    const game =
      getXoGame(gameId);

    if (!game) {
      await ctx.reply(
        '❌ رابط اللعبة غير صالح أو انتهت اللعبة.'
      );
      return;
    }

    if (
      game.mode !== 'friend'
    ) {
      await ctx.reply(
        '❌ هذه الدعوة غير صالحة.'
      );
      return;
    }

    if (
      String(game.creatorId) === userId
    ) {
      await ctx.reply(
        '❌ أنت صاحب هذه اللعبة بالفعل.'
      );
      return;
    }

    if (game.playerO) {
      await ctx.reply(
        '❌ اللعبة ممتلئة بالفعل.'
      );
      return;
    }

    game.playerO = userId;
    game.status = 'playing';
    game.createdAt = Date.now();

    const board =
      renderXoBoard(game);

    try {
      const sentBoard =
        await ctx.reply(
          board.text,
          board.extra
        );

      game.messageO =
        sentBoard.message_id;
    } catch (_) {}

    await updateFriendBoards(game);

    return;
  }

  if (!db.users[userId]) {
    db.users[userId] = {
      id: ctx.from.id,
      username:
        ctx.from.username || '',
      first_name:
        ctx.from.first_name || '',
      joined_at:
        new Date().toISOString(),
      is_banned: false,
      balance: 0,
      usage_count: 0,
      last_start: now
    };

    db.stats.starts =
      Number(
        db.stats.starts || 0
      ) + 1;

    saveDB(db);

    await ctx.reply(
      welcomeMessage,
      kb
    );

    return;
  }

  const user =
    db.users[userId];

  const lastStart =
    Number(
      user.last_start || 0
    );

  const newSession =
    !lastStart ||
    now - lastStart >
      SESSION_GAP;

  user.username =
    ctx.from.username || '';

  user.first_name =
    ctx.from.first_name || '';

  user.last_start = now;

  db.stats.starts =
    Number(
      db.stats.starts || 0
    ) + 1;

  saveDB(db);

  if (newSession) {
    await ctx.reply(
      welcomeMessage,
      kb
    );
    return;
  }

  await ctx.reply(
    'اختر أداة من القائمة 👇',
    kb
  );
});

// ==================================================
// ========== لعبة X و O - القائمة الرئيسية ==========
// ==================================================

bot.hears(
  '🎮 لعبة X و O',
  async (ctx) => {
    if (!isToolEnabled('xo')) {
      await ctx.reply(
        '⛔ لعبة X و O متوقفة حاليًا.'
      );
      return;
    }

    await ctx.reply(
      `🎮 لعبة X و O

💰 السعر: ${formatToolPrice('xo')}

اختر طريقة اللعب:`,
      Markup.inlineKeyboard([
        [
          Markup.button.callback(
            '🤖 لعب ضد البوت',
            'xo_start_bot'
          )
        ],
        [
          Markup.button.callback(
            '👥 لعب ضد مستخدم آخر',
            'xo_start_friend'
          )
        ],
        [
          Markup.button.callback(
            '📱 لاعبين على نفس الجوال',
            'xo_start_local'
          )
        ]
      ])
    );
  }
);

// ========== ضد البوت ==========
bot.action(
  'xo_start_bot',
  async (ctx) => {
    if (!isToolEnabled('xo')) {
      await ctx.answerCbQuery(
        '⛔ اللعبة متوقفة.',
        { show_alert: true }
      );
      return;
    }

    const charge =
      chargeTool(
        ctx.from.id,
        'xo'
      );

    if (!charge.success) {
      await ctx.answerCbQuery(
        charge.message,
        { show_alert: true }
      );
      return;
    }

    const game =
      createXoGame(
        'bot',
        ctx.from.id
      );

    game.playerX =
      String(ctx.from.id);

    game.playerO = 'BOT';
    game.status = 'playing';

    await ctx.answerCbQuery(
      charge.charged > 0
        ? `🎮 تم خصم ${charge.charged} رصيد`
        : '🎮 بدأت اللعبة!'
    );

    const board =
      renderXoBoard(game);

    await ctx.reply(
      board.text,
      board.extra
    );
  }
);

// ========== ضد مستخدم ==========
bot.action(
  'xo_start_friend',
  async (ctx) => {
    if (!isToolEnabled('xo')) {
      await ctx.answerCbQuery(
        '⛔ اللعبة متوقفة.',
        { show_alert: true }
      );
      return;
    }

    const charge =
      chargeTool(
        ctx.from.id,
        'xo'
      );

    if (!charge.success) {
      await ctx.answerCbQuery(
        charge.message,
        { show_alert: true }
      );
      return;
    }

    const game =
      createXoGame(
        'friend',
        ctx.from.id
      );

    let botUsername = '';

    try {
      const me =
        await ctx.telegram.getMe();

      botUsername =
        me.username || '';
    } catch (_) {}

    if (!botUsername) {
      xoGames.delete(game.id);

      if (charge.charged > 0) {
        refundToolCharge(
          ctx.from.id,
          charge.charged
        );
      }

      await ctx.answerCbQuery(
        '❌ تعذر إنشاء رابط الدعوة وتم إرجاع الرصيد.',
        { show_alert: true }
      );

      return;
    }

    const inviteLink =
      `https://t.me/${botUsername}?start=xo_${game.id}`;

    await ctx.answerCbQuery(
      charge.charged > 0
        ? `✅ تم خصم ${charge.charged} رصيد وإنشاء الدعوة!`
        : '✅ تم إنشاء الدعوة!'
    );

    await ctx.reply(
      `👥 تم إنشاء لعبة جديدة!

❌ أنت اللاعب X.

أرسل هذا الرابط لصديقك لينضم إلى اللعبة:

${inviteLink}

⏳ في انتظار اللاعب الثاني...`
    );

    const board =
      renderXoBoard(game);

    try {
      const sentBoard =
        await ctx.reply(
          board.text,
          board.extra
        );

      game.messageX =
        sentBoard.message_id;
    } catch (_) {}
  }
);

// ========== نفس الجوال ==========
bot.action(
  'xo_start_local',
  async (ctx) => {
    if (!isToolEnabled('xo')) {
      await ctx.answerCbQuery(
        '⛔ اللعبة متوقفة.',
        { show_alert: true }
      );
      return;
    }

    const charge =
      chargeTool(
        ctx.from.id,
        'xo'
      );

    if (!charge.success) {
      await ctx.answerCbQuery(
        charge.message,
        { show_alert: true }
      );
      return;
    }

    const game =
      createXoGame(
        'local',
        ctx.from.id
      );

    game.playerX =
      String(ctx.from.id);

    game.playerO = null;
    game.status = 'playing';

    await ctx.answerCbQuery(
      charge.charged > 0
        ? `📱 تم خصم ${charge.charged} رصيد`
        : '📱 بدأت اللعبة!'
    );

    const board =
      renderXoBoard(game);

    await ctx.reply(
      board.text,
      board.extra
    );
  }
);

// ========== ضغطة غير مستخدمة ==========
bot.action(
  'xo_noop',
  async (ctx) => {
    await ctx.answerCbQuery(
      'هذه الخانة مستخدمة بالفعل.'
    );
  }
);

// ==================================================
// ========== حركة X و O ==========
// ==================================================

bot.action(
  /^xo_move:([^:]+):(\d)$/,
  async (ctx) => {
    const gameId =
      ctx.match[1];

    const index =
      Number(ctx.match[2]);

    const game =
      getXoGame(gameId);

    if (!game) {
      await ctx.answerCbQuery(
        '❌ انتهت اللعبة.',
        { show_alert: true }
      );
      return;
    }

    if (!isToolEnabled('xo')) {
      await ctx.answerCbQuery(
        '⛔ اللعبة متوقفة.',
        { show_alert: true }
      );
      return;
    }

    if (
      game.status === 'waiting'
    ) {
      await ctx.answerCbQuery(
        '⏳ في انتظار اللاعب الثاني.',
        { show_alert: true }
      );
      return;
    }

    if (
      game.status === 'finished'
    ) {
      await ctx.answerCbQuery(
        '🏁 انتهت اللعبة.',
        { show_alert: true }
      );
      return;
    }

    if (
      !Number.isInteger(index) ||
      index < 0 ||
      index > 8
    ) {
      await ctx.answerCbQuery(
        '❌ حركة غير صالحة.'
      );
      return;
    }

    let symbol = null;

    if (game.mode === 'local') {
      symbol = game.turn;
    } else {
      const userId =
        String(ctx.from.id);

      symbol =
        getPlayerSymbol(
          game,
          userId
        );

      if (!symbol) {
        await ctx.answerCbQuery(
          '❌ أنت لست لاعبًا في هذه اللعبة.',
          { show_alert: true }
        );
        return;
      }
    }

    if (
      game.mode === 'bot' &&
      symbol !== 'X'
    ) {
      await ctx.answerCbQuery(
        '❌ هذه اللعبة لك أنت فقط.',
        { show_alert: true }
      );
      return;
    }

    if (
      game.turn !== symbol
    ) {
      await ctx.answerCbQuery(
        '⏳ ليس دورك.',
        { show_alert: true }
      );
      return;
    }

    if (game.board[index]) {
      await ctx.answerCbQuery(
        '❌ هذه الخانة مستخدمة.'
      );
      return;
    }

    game.board[index] =
      symbol;

    game.createdAt =
      Date.now();

    const result =
      checkXoWinner(
        game.board
      );

    if (result) {
      finishXoGame(
        game,
        result
      );

      await ctx.answerCbQuery(
        result === 'draw'
          ? '🤝 تعادل!'
          : '🏆 انتهت اللعبة!'
      );

      const board =
        renderXoBoard(game);

      if (
        game.mode === 'bot' ||
        game.mode === 'local'
      ) {
        try {
          await ctx.editMessageText(
            board.text,
            board.extra
          );
        } catch (_) {}
      }

      if (
        game.mode === 'friend'
      ) {
        await updateFriendBoards(
          game
        );
      }

      return;
    }

    game.turn =
      symbol === 'X'
        ? 'O'
        : 'X';

    await ctx.answerCbQuery(
      '✅ تم تسجيل الحركة.'
    );

    if (
      game.mode === 'bot' &&
      game.turn === 'O'
    ) {
      try {
        await ctx.editMessageText(
          getXoBoardText(game),
          getXoKeyboard(game)
        );
      } catch (_) {}

      await new Promise(
        (resolve) =>
          setTimeout(
            resolve,
            500
          )
      );

      const botMove =
        getBestBotMove(
          game.board
        );

      if (
        botMove !== null &&
        game.status === 'playing'
      ) {
        game.board[botMove] =
          'O';

        const botResult =
          checkXoWinner(
            game.board
          );

        if (botResult) {
          finishXoGame(
            game,
            botResult
          );
        } else {
          game.turn = 'X';
        }
      }

      game.createdAt =
        Date.now();

      const finalBoard =
        renderXoBoard(game);

      try {
        await ctx.editMessageText(
          finalBoard.text,
          finalBoard.extra
        );
      } catch (_) {}

      return;
    }

    if (
      game.mode === 'local'
    ) {
      const board =
        renderXoBoard(game);

      try {
        await ctx.editMessageText(
          board.text,
          board.extra
        );
      } catch (_) {}

      return;
    }

    if (
      game.mode === 'friend'
    ) {
      await updateFriendBoards(
        game
      );

      return;
    }

    const board =
      renderXoBoard(game);

    try {
      await ctx.editMessageText(
        board.text,
        board.extra
      );
    } catch (_) {}
  }
);

// ==================================================
// ========== إعادة اللعب ==========
// ==================================================

bot.action(
  /^xo_rematch:(.+)$/,
  async (ctx) => {
    const oldGame =
      getXoGame(ctx.match[1]);

    if (!oldGame) {
      await ctx.answerCbQuery(
        '❌ انتهت بيانات اللعبة.',
        { show_alert: true }
      );
      return;
    }

    if (!isToolEnabled('xo')) {
      await ctx.answerCbQuery(
        '⛔ اللعبة متوقفة.',
        { show_alert: true }
      );
      return;
    }

    const userId =
      String(ctx.from.id);

    if (
      oldGame.mode !== 'local' &&
      oldGame.mode === 'friend' &&
      userId !== String(oldGame.playerX) &&
      userId !== String(oldGame.playerO)
    ) {
      await ctx.answerCbQuery(
        '❌ أنت لست لاعبًا.',
        { show_alert: true }
      );
      return;
    }

    if (
      oldGame.mode === 'bot' &&
      userId !== String(oldGame.playerX)
    ) {
      await ctx.answerCbQuery(
        '❌ أنت لست صاحب اللعبة.',
        { show_alert: true }
      );
      return;
    }

    const charge =
      chargeTool(
        ctx.from.id,
        'xo'
      );

    if (!charge.success) {
      await ctx.answerCbQuery(
        charge.message,
        { show_alert: true }
      );
      return;
    }

    const newGame =
      createXoGame(
        oldGame.mode,
        oldGame.creatorId
      );

    newGame.playerX =
      oldGame.playerX;

    newGame.playerO =
      oldGame.playerO;

    newGame.status =
      oldGame.mode === 'friend'
        ? (
            newGame.playerO
              ? 'playing'
              : 'waiting'
          )
        : 'playing';

    if (
      oldGame.mode === 'friend'
    ) {
      newGame.messageX =
        oldGame.messageX;

      newGame.messageO =
        oldGame.messageO;
    }

    xoGames.delete(
      oldGame.id
    );

    await ctx.answerCbQuery(
      charge.charged > 0
        ? `🔄 تم خصم ${charge.charged} رصيد`
        : '🔄 بدأت لعبة جديدة!'
    );

    const board =
      renderXoBoard(newGame);

    if (
      newGame.mode === 'friend'
    ) {
      await updateFriendBoards(
        newGame
      );

      if (
        !newGame.messageX &&
        newGame.playerX
      ) {
        try {
          const sent =
            await bot.telegram.sendMessage(
              String(newGame.playerX),
              board.text,
              board.extra
            );

          newGame.messageX =
            sent.message_id;
        } catch (_) {}
      }

      return;
    }

    try {
      await ctx.editMessageText(
        board.text,
        board.extra
      );
    } catch (_) {
      try {
        await ctx.reply(
          board.text,
          board.extra
        );
      } catch (_) {}
    }
  }
);

// ==================================================
// ========== إنهاء اللعبة ==========
// ==================================================

bot.action(
  /^xo_end:(.+)$/,
  async (ctx) => {
    const game =
      getXoGame(ctx.match[1]);

    if (!game) {
      await ctx.answerCbQuery(
        '❌ اللعبة غير موجودة.'
      );
      return;
    }

    const userId =
      String(ctx.from.id);

    let allowed = false;

    if (
      game.mode === 'local'
    ) {
      allowed = true;
    } else if (
      game.mode === 'bot'
    ) {
      allowed =
        userId ===
        String(game.playerX);
    } else {
      allowed =
        userId ===
          String(game.playerX) ||
        userId ===
          String(game.playerO);
    }

    if (!allowed) {
      await ctx.answerCbQuery(
        '❌ أنت لست لاعبًا.',
        { show_alert: true }
      );
      return;
    }

    game.status = 'finished';
    game.winner = null;

    const endText =
      '❌ تم إنهاء لعبة X و O.';

    if (
      game.mode === 'friend'
    ) {
      if (
        game.playerX &&
        game.messageX
      ) {
        try {
          await bot.telegram.editMessageText(
            String(game.playerX),
            game.messageX,
            undefined,
            endText
          );
        } catch (_) {}
      }

      if (
        game.playerO &&
        game.messageO
      ) {
        try {
          await bot.telegram.editMessageText(
            String(game.playerO),
            game.messageO,
            undefined,
            endText
          );
        } catch (_) {}
      }
    } else {
      try {
        await ctx.editMessageText(
          endText
        );
      } catch (_) {
        try {
          await ctx.reply(
            endText
          );
        } catch (_) {}
      }
    }

    xoGames.delete(
      game.id
    );

    await ctx.answerCbQuery(
      '❌ تم إنهاء اللعبة.'
    );
  }
);

// ==================================================
// ========== QR ==========
// ==================================================

bot.hears(
  '🔲 إنشاء QR',
  async (ctx) => {
    if (!isToolEnabled('qr')) {
      await ctx.reply(
        '⛔ هذه الأداة متوقفة حاليًا.'
      );
      return;
    }

    userState.set(
      String(ctx.from.id),
      { action: 'qr' }
    );

    await ctx.reply(
      `🔲 أرسل النص أو الرابط لتحويله إلى QR:

💰 السعر: ${formatToolPrice('qr')}`
    );
  }
);

// ==================================================
// ========== إزالة الخلفية ==========
// ==================================================

bot.hears(
  '🖼️ إزالة خلفية',
  async (ctx) => {
    if (!isToolEnabled('removebg')) {
      await ctx.reply(
        '⛔ هذه الأداة متوقفة حاليًا.'
      );
      return;
    }

    userState.set(
      String(ctx.from.id),
      { action: 'removebg' }
    );

    await ctx.reply(
      `🖼️ أرسل الصورة لإزالة خلفيتها:

💰 السعر: ${formatToolPrice('removebg')}`
    );
  }
);

// ==================================================
// ========== تحويل صوت إلى نص ==========
// ==================================================

bot.hears(
  '🎤 تحويل صوت إلى نص',
  async (ctx) => {
    if (!isToolEnabled('stt')) {
      await ctx.reply(
        '⛔ هذه الأداة متوقفة حاليًا.'
      );
      return;
    }

    userState.set(
      String(ctx.from.id),
      { action: 'stt' }
    );

    await ctx.reply(
      `🎤 أرسل المقطع الصوتي:

💰 السعر: ${formatToolPrice('stt')}

⚠️ تنبيه: قد لا يتم التعرف على الصوت كاملًا، خصوصًا في الأغاني أو التسجيلات التي فيها موسيقى أو صوت غير واضح.`
    );
  }
);

// ==================================================
// ========== رصيدي ==========
// ==================================================

bot.hears(
  '💰 رصيدي',
  async (ctx) => {
    const userId =
      String(ctx.from.id);

    const balance =
      getUserBalance(userId);

    if (balance === null) {
      await ctx.reply(
        '❌ لم يتم العثور على حسابك.'
      );
      return;
    }

    await ctx.reply(
      `💰 رصيدك الحالي

💳 ${balance} رصيد`
    );
  }
);

// ==================================================
// ========== التواصل مع المطور ==========
// ==================================================

bot.hears(
  '👨‍💻 التواصل مع المطور',
  async (ctx) => {
    await ctx.reply(
      'للتواصل مع المطور:',
      Markup.inlineKeyboard([
        [
          Markup.button.url(
            '👨‍💻 اضغط هنا',
            DEVELOPER_URL
          )
        ]
      ])
    );
  }
);

// ==================================================
// ========== لوحة المالك ==========
// ==================================================

bot.hears(
  '👑 لوحة المالك',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.reply(
        '❌ هذا الخيار للمالك فقط.'
      );
      return;
    }

    ownerState.set(
      OWNER_ID,
      null
    );

    await ctx.reply(
      '👑 لوحة المالك',
      ownerKeyboard
    );
  }
);

bot.hears(
  '⬅️ القائمة الرئيسية',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      return;
    }

    ownerState.set(
      OWNER_ID,
      null
    );

    await ctx.reply(
      '🏠 القائمة الرئيسية',
      ownerMainKeyboard
    );
  }
);

// ==================================================
// ========== الإحصائيات ==========
// ==================================================

bot.hears(
  '📊 الإحصائيات',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      return;
    }

    const db = loadDB();

    const count =
      Object.keys(db.users).length;

    await ctx.reply(
      `📊 إحصائيات البوت

👥 المستخدمون: ${count}
💬 الرسائل: ${db.stats.messages || 0}
▶️ مرات /start: ${db.stats.starts || 0}`
    );
  }
);

// ==================================================
// ========== المستخدمون ==========
// ==================================================

bot.hears(
  '👥 المستخدمون',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      return;
    }

    const db = loadDB();

    const list =
      Object.values(db.users).slice(
        0,
        30
      );

    let text =
      `👥 إجمالي المستخدمين: ${Object.keys(db.users).length}\n\n`;

    list.forEach((u, i) => {
      text +=
        `${i + 1}. ${u.first_name || 'بدون اسم'} | ID: ${u.id}${u.is_banned ? ' 🚫' : ''}\n`;
    });

    if (
      Object.keys(db.users).length > 30
    ) {
      text +=
        '\n... (يتم عرض 30 فقط)';
    }

    await ctx.reply(text);
  }
);

// ==================================================
// ========== إدارة الأدوات ==========
// ==================================================

function toolsKeyboard() {
  const db = loadDB();

  return Markup.inlineKeyboard([
    [
      Markup.button.callback(
        `${db.tools.removebg ? '🟢' : '🔴'} ${TOOL_INFO.removebg.name.replace('🖼️ ', '')}`,
        'tool_toggle_removebg'
      )
    ],
    [
      Markup.button.callback(
        `${db.tools.qr ? '🟢' : '🔴'} ${TOOL_INFO.qr.name.replace('🔲 ', '')}`,
        'tool_toggle_qr'
      )
    ],
    [
      Markup.button.callback(
        `${db.tools.stt ? '🟢' : '🔴'} ${TOOL_INFO.stt.name.replace('🎤 ', '')}`,
        'tool_toggle_stt'
      )
    ],
    [
      Markup.button.callback(
        `${db.tools.xo ? '🟢' : '🔴'} ${TOOL_INFO.xo.name.replace('🎮 ', '')}`,
        'tool_toggle_xo'
      )
    ],
    [
      Markup.button.callback(
        '🔄 تحديث',
        'tools_refresh'
      )
    ]
  ]);
}

async function sendToolsPanel(ctx) {
  const db = loadDB();

  let text =
    '🟢 إدارة الأدوات\n\n';

  for (
    const key of Object.keys(TOOL_INFO)
  ) {
    text +=
      `${db.tools[key] ? '🟢' : '🔴'} ${TOOL_INFO[key].name}\n`;
  }

  text +=
    '\n🟢 = تعمل\n🔴 = متوقفة\n\nاضغط على الأداة لتغيير حالتها.';

  await ctx.reply(
    text,
    toolsKeyboard()
  );
}

bot.hears(
  '🟢 الأدوات',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      return;
    }

    ownerState.set(
      OWNER_ID,
      null
    );

    await sendToolsPanel(ctx);
  }
);

async function toggleTool(
  ctx,
  toolKey
) {
  if (
    String(ctx.from.id) !== OWNER_ID
  ) {
    await ctx.answerCbQuery('❌');
    return;
  }

  const db = loadDB();

  db.tools[toolKey] =
    !db.tools[toolKey];

  saveDB(db);

  await ctx.answerCbQuery(
    db.tools[toolKey]
      ? '🟢 تم تشغيل الأداة'
      : '🔴 تم إيقاف الأداة'
  );

  await ctx.editMessageReplyMarkup(
    toolsKeyboard().reply_markup
  );
}

bot.action(
  'tool_toggle_removebg',
  (ctx) =>
    toggleTool(
      ctx,
      'removebg'
    )
);

bot.action(
  'tool_toggle_qr',
  (ctx) =>
    toggleTool(
      ctx,
      'qr'
    )
);

bot.action(
  'tool_toggle_stt',
  (ctx) =>
    toggleTool(
      ctx,
      'stt'
    )
);

bot.action(
  'tool_toggle_xo',
  (ctx) =>
    toggleTool(
      ctx,
      'xo'
    )
);

bot.action(
  'tools_refresh',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    await ctx.answerCbQuery(
      '🔄 تم التحديث'
    );

    await ctx.editMessageReplyMarkup(
      toolsKeyboard().reply_markup
    );
  }
);

// ==================================================
// ========== إدارة الأسعار ==========
// ==================================================

function pricesKeyboard() {
  const db = loadDB();

  return Markup.inlineKeyboard([
    [
      Markup.button.callback(
        `🖼️ إزالة الخلفية: ${formatToolPrice('removebg')}`,
        'price_edit_removebg'
      )
    ],
    [
      Markup.button.callback(
        `🔲 إنشاء QR: ${formatToolPrice('qr')}`,
        'price_edit_qr'
      )
    ],
    [
      Markup.button.callback(
        `🎤 صوت إلى نص: ${formatToolPrice('stt')}`,
        'price_edit_stt'
      )
    ],
    [
      Markup.button.callback(
        `🎮 لعبة X و O: ${formatToolPrice('xo')}`,
        'price_edit_xo'
      )
    ],
    [
      Markup.button.callback(
        '🔄 تحديث',
        'prices_refresh'
      )
    ]
  ]);
}

async function sendPricesPanel(ctx) {
  const db = loadDB();

  let text =
    '💰 إدارة الأسعار\n\n';

  for (
    const key of Object.keys(TOOL_INFO)
  ) {
    text +=
      `${TOOL_INFO[key].name}: ${formatToolPrice(key)}\n`;
  }

  text +=
    '\nاضغط على الأداة لتعديل سعرها.\n\n💡 السعر الأساسي والخصم يتم تطبيقهما فعليًا على رصيد المستخدم.';

  await ctx.reply(
    text,
    pricesKeyboard()
  );
}

bot.hears(
  '💰 الأسعار',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      return;
    }

    ownerState.set(
      OWNER_ID,
      null
    );

    await sendPricesPanel(ctx);
  }
);

function startPriceEdit(
  ctx,
  toolKey
) {
  ownerState.set(
    OWNER_ID,
    {
      action: 'price_edit',
      tool: toolKey
    }
  );

  return ctx.reply(
    `💰 تعديل سعر: ${TOOL_INFO[toolKey].name}\n\nالسعر الحالي: ${formatToolPrice(toolKey)}\n\nأرسل السعر بالأرقام فقط.\nأرسل 0 لجعل الأداة مجانية.`
  );
}

bot.action(
  'price_edit_removebg',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    await ctx.answerCbQuery();

    await startPriceEdit(
      ctx,
      'removebg'
    );
  }
);

bot.action(
  'price_edit_qr',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    await ctx.answerCbQuery();

    await startPriceEdit(
      ctx,
      'qr'
    );
  }
);

bot.action(
  'price_edit_stt',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    await ctx.answerCbQuery();

    await startPriceEdit(
      ctx,
      'stt'
    );
  }
);

bot.action(
  'price_edit_xo',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    await ctx.answerCbQuery();

    await startPriceEdit(
      ctx,
      'xo'
    );
  }
);

bot.action(
  'prices_refresh',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    await ctx.answerCbQuery(
      '🔄 تم التحديث'
    );

    await ctx.editMessageReplyMarkup(
      pricesKeyboard().reply_markup
    );
  }
);

// ==================================================
// ========== الخصم ==========
// ==================================================

function discountsKeyboard() {
  const db = loadDB();

  return Markup.inlineKeyboard([
    [
      Markup.button.callback(
        `🖼️ إزالة الخلفية: ${db.discounts.removebg}%`,
        'discount_edit_removebg'
      )
    ],
    [
      Markup.button.callback(
        `🔲 إنشاء QR: ${db.discounts.qr}%`,
        'discount_edit_qr'
      )
    ],
    [
      Markup.button.callback(
        `🎤 صوت إلى نص: ${db.discounts.stt}%`,
        'discount_edit_stt'
      )
    ],
    [
      Markup.button.callback(
        `🎮 لعبة X و O: ${db.discounts.xo}%`,
        'discount_edit_xo'
      )
    ],
    [
      Markup.button.callback(
        '🏷️ خصم على الكل',
        'discount_edit_all'
      )
    ],
    [
      Markup.button.callback(
        '🔄 تحديث',
        'discounts_refresh'
      )
    ]
  ]);
}

async function sendDiscountPanel(ctx) {
  const db = loadDB();

  let text =
    '🏷️ إدارة الخصومات\n\n';

  for (
    const key of Object.keys(TOOL_INFO)
  ) {
    const base =
      getToolPrice(key);

    const discount =
      getToolDiscount(key);

    const finalPrice =
      getFinalToolPrice(key);

    text +=
      `${TOOL_INFO[key].name}\n` +
      `💰 السعر الأساسي: ${formatPrice(base)}\n` +
      `🏷️ الخصم: ${discount}%\n` +
      `💳 السعر بعد الخصم: ${formatPrice(finalPrice)}\n\n`;
  }

  text +=
    'اضغط على الأداة لتحديد نسبة الخصم.\n\n' +
    '📌 أرسل أي نسبة من 0% إلى 100%.\n' +
    '0% = بدون خصم\n' +
    '100% = مجانية';

  await ctx.reply(
    text,
    discountsKeyboard()
  );
}

bot.hears(
  '🏷️ الخصم',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      return;
    }

    ownerState.set(
      OWNER_ID,
      null
    );

    await sendDiscountPanel(ctx);
  }
);

function startDiscountEdit(
  ctx,
  toolKey
) {
  ownerState.set(
    OWNER_ID,
    {
      action: 'discount_edit',
      tool: toolKey
    }
  );

  return ctx.reply(
    `🏷️ تعديل خصم: ${TOOL_INFO[toolKey].name}

الخصم الحالي: ${getToolDiscount(toolKey)}%

السعر الأساسي: ${formatPrice(getToolPrice(toolKey))}
السعر بعد الخصم الحالي: ${formatPrice(getFinalToolPrice(toolKey))}

أرسل نسبة الخصم بالأرقام فقط.
مثال: 25

يمكنك استخدام أي نسبة من 0 إلى 100.
0 = بدون خصم
100 = مجاني`
  );
}

bot.action(
  'discount_edit_removebg',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    await ctx.answerCbQuery();

    await startDiscountEdit(
      ctx,
      'removebg'
    );
  }
);

bot.action(
  'discount_edit_qr',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    await ctx.answerCbQuery();

    await startDiscountEdit(
      ctx,
      'qr'
    );
  }
);

bot.action(
  'discount_edit_stt',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    await ctx.answerCbQuery();

    await startDiscountEdit(
      ctx,
      'stt'
    );
  }
);

bot.action(
  'discount_edit_xo',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    await ctx.answerCbQuery();

    await startDiscountEdit(
      ctx,
      'xo'
    );
  }
);

// ========== خصم على جميع الأدوات ==========
bot.action(
  'discount_edit_all',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    ownerState.set(
      OWNER_ID,
      {
        action: 'discount_edit_all'
      }
    );

    await ctx.answerCbQuery();

    await ctx.reply(
      `🏷️ تعديل الخصم على جميع الأدوات

أرسل نسبة الخصم بالأرقام فقط.
مثال: 25

يمكنك استخدام أي نسبة من 0 إلى 100.
0 = بدون خصم
100 = مجاني`
    );
  }
);

bot.action(
  'discounts_refresh',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    await ctx.answerCbQuery(
      '🔄 تم التحديث'
    );

    try {
      await ctx.editMessageText(
        '🏷️ إدارة الخصومات',
        discountsKeyboard()
      );
    } catch (_) {
      try {
        await ctx.editMessageReplyMarkup(
          discountsKeyboard().reply_markup
        );
      } catch (_) {}
    }
  }
);

// ==================================================
// ========== إدارة الرصيد ==========
// ==================================================

function balanceKeyboard() {
  return Markup.inlineKeyboard([
    [
      Markup.button.callback(
        '➕ إضافة رصيد',
        'balance_add'
      )
    ],
    [
      Markup.button.callback(
        '➖ خصم رصيد',
        'balance_remove'
      )
    ],
    [
      Markup.button.callback(
        '✏️ تعيين رصيد',
        'balance_set'
      )
    ],
    [
      Markup.button.callback(
        '🔎 عرض رصيد مستخدم',
        'balance_view'
      )
    ],
    [
      Markup.button.callback(
        '🔄 تحديث',
        'balance_refresh'
      )
    ]
  ]);
}

async function sendBalancePanel(ctx) {
  const db = loadDB();

  const users =
    Object.keys(db.users).length;

  let totalBalance = 0;

  for (
    const id of Object.keys(db.users)
  ) {
    totalBalance +=
      Number(
        db.users[id].balance || 0
      );
  }

  await ctx.reply(
    `🎁 إدارة الرصيد

👥 المستخدمون: ${users}
💰 إجمالي الأرصدة: ${totalBalance} رصيد

اختر العملية التي تريد تنفيذها:`,
    balanceKeyboard()
  );
}

bot.hears(
  '🎁 الرصيد',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      return;
    }

    ownerState.set(
      OWNER_ID,
      null
    );

    await sendBalancePanel(ctx);
  }
);

bot.action(
  'balance_add',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    ownerState.set(
      OWNER_ID,
      {
        action: 'balance_add_user'
      }
    );

    await ctx.answerCbQuery();

    await ctx.reply(
      '➕ إضافة رصيد\n\nأرسل آيدي المستخدم:'
    );
  }
);

bot.action(
  'balance_remove',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    ownerState.set(
      OWNER_ID,
      {
        action: 'balance_remove_user'
      }
    );

    await ctx.answerCbQuery();

    await ctx.reply(
      '➖ خصم رصيد\n\nأرسل آيدي المستخدم:'
    );
  }
);

bot.action(
  'balance_set',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    ownerState.set(
      OWNER_ID,
      {
        action: 'balance_set_user'
      }
    );

    await ctx.answerCbQuery();

    await ctx.reply(
      '✏️ تعيين رصيد\n\nأرسل آيدي المستخدم:'
    );
  }
);

bot.action(
  'balance_view',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    ownerState.set(
      OWNER_ID,
      {
        action: 'balance_view_user'
      }
    );

    await ctx.answerCbQuery();

    await ctx.reply(
      '🔎 عرض رصيد مستخدم\n\nأرسل آيدي المستخدم:'
    );
  }
);

bot.action(
  'balance_refresh',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    await ctx.answerCbQuery(
      '🔄 تم التحديث'
    );

    try {
      await ctx.editMessageReplyMarkup(
        balanceKeyboard().reply_markup
      );
    } catch (_) {}
  }
);

// ==================================================
// ========== اختبار الخدمات ==========
// ==================================================

async function testRemoveBGService() {
  if (!REMOVEBG_API_KEY) {
    return {
      name: '🖼️ remove.bg',
      ok: false,
      message: 'مفتاح API غير مهيأ'
    };
  }

  try {
    const response =
      await axios.get(
        'https://api.remove.bg/v1.0/account',
        {
          headers: {
            'X-Api-Key':
              REMOVEBG_API_KEY
          },
          timeout: 20000
        }
      );

    if (
      response.status >= 200 &&
      response.status < 300
    ) {
      return {
        name: '🖼️ remove.bg',
        ok: true,
        message: 'المفتاح يعمل'
      };
    }

    return {
      name: '🖼️ remove.bg',
      ok: false,
      message:
        `استجابة غير متوقعة: ${response.status}`
    };
  } catch (err) {
    const status =
      err &&
      err.response &&
      err.response.status
        ? err.response.status
        : null;

    if (
      status === 401 ||
      status === 403
    ) {
      return {
        name: '🖼️ remove.bg',
        ok: false,
        message: 'المفتاح غير صحيح أو غير مصرح'
      };
    }

    return {
      name: '🖼️ remove.bg',
      ok: false,
      message:
        status
          ? `HTTP ${status}`
          : 'تعذر الاتصال بالخدمة'
    };
  }
}

async function testGroqService() {
  if (!GROQ_API_KEY) {
    return {
      name: '🎤 Groq',
      ok: false,
      message: 'مفتاح API غير مهيأ'
    };
  }

  try {
    const response =
      await axios.get(
        'https://api.groq.com/openai/v1/models',
        {
          headers: {
            Authorization:
              `Bearer ${GROQ_API_KEY}`
          },
          timeout: 20000
        }
      );

    if (
      response.status >= 200 &&
      response.status < 300
    ) {
      return {
        name: '🎤 Groq',
        ok: true,
        message: 'المفتاح يعمل'
      };
    }

    return {
      name: '🎤 Groq',
      ok: false,
      message:
        `استجابة غير متوقعة: ${response.status}`
    };
  } catch (err) {
    const status =
      err &&
      err.response &&
      err.response.status
        ? err.response.status
        : null;

    if (
      status === 401 ||
      status === 403
    ) {
      return {
        name: '🎤 Groq',
        ok: false,
        message: 'المفتاح غير صحيح أو غير مصرح'
      };
    }

    return {
      name: '🎤 Groq',
      ok: false,
      message:
        status
          ? `HTTP ${status}`
          : 'تعذر الاتصال بالخدمة'
    };
  }
}



async function testQRService() {
  try {
    const response =
      await axios.get(
        'https://api.qrserver.com/v1/create-qr-code/',
        {
          params: {
            size: '100x100',
            data: 'AI Tools Test'
          },
          responseType: 'arraybuffer',
          timeout: 20000,
          validateStatus: () => true
        }
      );

    if (
      response.status >= 200 &&
      response.status < 300 &&
      response.data &&
      response.data.length > 50
    ) {
      return {
        name: '🔲 QR Server',
        ok: true,
        message: 'الخدمة تعمل'
      };
    }

    return {
      name: '🔲 QR Server',
      ok: false,
      message:
        `HTTP ${response.status}`
    };
  } catch (_) {
    return {
      name: '🔲 QR Server',
      ok: false,
      message: 'تعذر الاتصال بالخدمة'
    };
  }
}

async function runServiceTests() {
  const results =
    await Promise.all([
      testRemoveBGService(),
      testGroqService(),
      testQRService()
    ]);

  let text =
    '🔑 اختبار الخدمات\n\n';

  for (const result of results) {
    text +=
      `${result.ok ? '🟢' : '🔴'} ${result.name}\n` +
      `↳ ${result.message}\n\n`;
  }

  text +=
    '⚙️ تم اختبار الخدمات الحالية.';
  return text;
}

bot.hears(
  '🔑 اختبار الخدمات',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      return;
    }

    let statusMessage = null;
    try {
      statusMessage = await ctx.reply('⏳ جارٍ اختبار الخدمات...');
      const result = await runServiceTests();
      await editStatusMessage(ctx, statusMessage, '✅ تم اختبار الخدمات.');
      await ctx.reply(result);
    } catch (err) {
      console.error(
        'Service test error:',
        err && err.message
          ? err.message
          : err
      );

      await editStatusMessage(ctx, statusMessage, '❌ حدث خطأ أثناء اختبار الخدمات.');
    }
  }
);

// ==================================================
// ========== الإذاعة ==========
// ==================================================

bot.hears(
  '📢 إذاعة',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      return;
    }

    ownerState.set(
      OWNER_ID,
      'broadcast'
    );

    await ctx.reply(
      '📢 اكتب الرسالة التي تريد إرسالها لجميع المستخدمين:'
    );
  }
);

// ==================================================
// ========== الحظر ==========
// ==================================================

bot.hears(
  '🚫 الحظر',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      return;
    }

    await ctx.reply(
      '🚫 اختر العملية:',
      Markup.inlineKeyboard([
        [
          Markup.button.callback(
            '🚫 حظر مستخدم',
            'ban_start'
          )
        ],
        [
          Markup.button.callback(
            '✅ فك الحظر',
            'unban_start'
          )
        ]
      ])
    );
  }
);

bot.action(
  'ban_start',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    ownerState.set(
      OWNER_ID,
      'ban'
    );

    await ctx.answerCbQuery();

    await ctx.reply(
      '🚫 اكتب آيدي المستخدم الذي تريد حظره:'
    );
  }
);

bot.action(
  'unban_start',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.answerCbQuery('❌');
      return;
    }

    ownerState.set(
      OWNER_ID,
      'unban'
    );

    await ctx.answerCbQuery();

    await ctx.reply(
      '✅ اكتب آيدي المستخدم الذي تريد فك الحظر عنه:'
    );
  }
);

// ==================================================
// ========== معالج النص ==========
// ==================================================

bot.on(
  'text',
  async (ctx, next) => {
    const userId =
      String(ctx.from.id);

    const text =
      ctx.message.text;

    if (userId === OWNER_ID) {
      const state =
        ownerState.get(
          OWNER_ID
        );

      // ===== إضافة رصيد - طلب الآيدي =====
      if (
        state &&
        state.action === 'balance_add_user' &&
        !btnTexts.includes(text)
      ) {
        const targetId =
          text.trim();

        if (!/^\d+$/.test(targetId)) {
          await ctx.reply(
            '❌ أرسل آيدي رقمي صحيح.'
          );
          return;
        }

        const db = loadDB();

        if (!db.users[targetId]) {
          ownerState.set(
            OWNER_ID,
            null
          );

          await ctx.reply(
            '❌ المستخدم غير موجود.'
          );
          return;
        }

        ownerState.set(
          OWNER_ID,
          {
            action: 'balance_add_amount',
            userId: targetId
          }
        );

        await ctx.reply(
          `➕ المستخدم: ${targetId}

💰 الرصيد الحالي: ${Number(db.users[targetId].balance || 0)}

أرسل كمية الرصيد التي تريد إضافتها:`
        );

        return;
      }

      // ===== إضافة رصيد - إدخال المبلغ =====
      if (
        state &&
        state.action === 'balance_add_amount' &&
        !btnTexts.includes(text)
      ) {
        const amountText =
          text.trim();

        if (!/^\d+$/.test(amountText)) {
          await ctx.reply(
            '❌ أرسل رقمًا صحيحًا فقط.'
          );
          return;
        }

        const amount =
          Number(amountText);

        const result =
          addUserBalance(
            state.userId,
            amount
          );

        ownerState.set(
          OWNER_ID,
          null
        );

        if (!result.success) {
          await ctx.reply(
            result.message
          );
          return;
        }

        await ctx.reply(
          `✅ تم إضافة الرصيد بنجاح.

👤 المستخدم: ${state.userId}
➕ المضاف: ${amount} رصيد
💰 الرصيد السابق: ${result.oldBalance}
💰 الرصيد الحالي: ${result.newBalance}`,
          balanceKeyboard()
        );

        return;
      }

      // ===== خصم رصيد - طلب الآيدي =====
      if (
        state &&
        state.action === 'balance_remove_user' &&
        !btnTexts.includes(text)
      ) {
        const targetId =
          text.trim();

        if (!/^\d+$/.test(targetId)) {
          await ctx.reply(
            '❌ أرسل آيدي رقمي صحيح.'
          );
          return;
        }

        const db = loadDB();

        if (!db.users[targetId]) {
          ownerState.set(
            OWNER_ID,
            null
          );

          await ctx.reply(
            '❌ المستخدم غير موجود.'
          );
          return;
        }

        ownerState.set(
          OWNER_ID,
          {
            action: 'balance_remove_amount',
            userId: targetId
          }
        );

        await ctx.reply(
          `➖ المستخدم: ${targetId}

💰 الرصيد الحالي: ${Number(db.users[targetId].balance || 0)}

أرسل كمية الرصيد التي تريد خصمها:`
        );

        return;
      }

      // ===== خصم رصيد - إدخال المبلغ =====
      if (
        state &&
        state.action === 'balance_remove_amount' &&
        !btnTexts.includes(text)
      ) {
        const amountText =
          text.trim();

        if (!/^\d+$/.test(amountText)) {
          await ctx.reply(
            '❌ أرسل رقمًا صحيحًا فقط.'
          );
          return;
        }

        const amount =
          Number(amountText);

        const result =
          removeUserBalance(
            state.userId,
            amount
          );

        ownerState.set(
          OWNER_ID,
          null
        );

        if (!result.success) {
          await ctx.reply(
            result.message
          );
          return;
        }

        await ctx.reply(
          `✅ تم خصم الرصيد بنجاح.

👤 المستخدم: ${state.userId}
➖ المخصوم: ${amount} رصيد
💰 الرصيد السابق: ${result.oldBalance}
💰 الرصيد الحالي: ${result.newBalance}`,
          balanceKeyboard()
        );

        return;
      }

      // ===== تعيين رصيد - طلب الآيدي =====
      if (
        state &&
        state.action === 'balance_set_user' &&
        !btnTexts.includes(text)
      ) {
        const targetId =
          text.trim();

        if (!/^\d+$/.test(targetId)) {
          await ctx.reply(
            '❌ أرسل آيدي رقمي صحيح.'
          );
          return;
        }

        const db = loadDB();

        if (!db.users[targetId]) {
          ownerState.set(
            OWNER_ID,
            null
          );

          await ctx.reply(
            '❌ المستخدم غير موجود.'
          );
          return;
        }

        ownerState.set(
          OWNER_ID,
          {
            action: 'balance_set_amount',
            userId: targetId
          }
        );

        await ctx.reply(
          `✏️ المستخدم: ${targetId}

💰 الرصيد الحالي: ${Number(db.users[targetId].balance || 0)}

أرسل الرصيد الجديد:`
        );

        return;
      }

      // ===== تعيين رصيد - إدخال المبلغ =====
      if (
        state &&
        state.action === 'balance_set_amount' &&
        !btnTexts.includes(text)
      ) {
        const amountText =
          text.trim();

        if (!/^\d+$/.test(amountText)) {
          await ctx.reply(
            '❌ أرسل رقمًا صحيحًا فقط.'
          );
          return;
        }

        const amount =
          Number(amountText);

        const result =
          setUserBalance(
            state.userId,
            amount
          );

        ownerState.set(
          OWNER_ID,
          null
        );

        if (!result.success) {
          await ctx.reply(
            result.message
          );
          return;
        }

        await ctx.reply(
          `✅ تم تعيين الرصيد.

👤 المستخدم: ${state.userId}
💰 الرصيد الجديد: ${result.newBalance} رصيد`,
          balanceKeyboard()
        );

        return;
      }

      // ===== عرض رصيد مستخدم =====
      if (
        state &&
        state.action === 'balance_view_user' &&
        !btnTexts.includes(text)
      ) {
        const targetId =
          text.trim();

        ownerState.set(
          OWNER_ID,
          null
        );

        if (!/^\d+$/.test(targetId)) {
          await ctx.reply(
            '❌ أرسل آيدي رقمي صحيح.'
          );
          return;
        }

        const db = loadDB();

        if (!db.users[targetId]) {
          await ctx.reply(
            '❌ المستخدم غير موجود.'
          );
          return;
        }

        const user =
          db.users[targetId];

        await ctx.reply(
          `🔎 معلومات الرصيد

👤 المستخدم: ${targetId}
📝 الاسم: ${user.first_name || 'بدون اسم'}
🔗 اليوزر: ${user.username ? '@' + user.username : 'بدون يوزر'}

💰 الرصيد: ${Number(user.balance || 0)} رصيد
📊 الاستخدامات: ${Number(user.usage_count || 0)}`,
          balanceKeyboard()
        );

        return;
      }

      // ===== تعديل السعر =====
      if (
        state &&
        state.action === 'price_edit' &&
        !btnTexts.includes(text)
      ) {
        const toolKey =
          state.tool;

        const value =
          text.trim();

        if (
          !/^\d+$/.test(value)
        ) {
          await ctx.reply(
            '❌ أرسل السعر بالأرقام فقط.\nمثال: 5'
          );
          return;
        }

        const price =
          Number(value);

        if (
          !Number.isSafeInteger(price) ||
          price < 0
        ) {
          await ctx.reply(
            '❌ السعر غير صالح.'
          );
          return;
        }

        const db = loadDB();

        db.prices[toolKey] =
          price;

        saveDB(db);

        ownerState.set(
          OWNER_ID,
          null
        );

        await ctx.reply(
          `✅ تم حفظ سعر ${TOOL_INFO[toolKey].name}\n💰 السعر الأساسي: ${formatPrice(price)}\n🏷️ الخصم الحالي: ${getToolDiscount(toolKey)}%\n💳 السعر النهائي: ${formatPrice(getFinalToolPrice(toolKey))}`,
          pricesKeyboard()
        );

        return;
      }

      // ===== تعديل الخصم =====
      if (
        state &&
        state.action === 'discount_edit' &&
        !btnTexts.includes(text)
      ) {
        const toolKey =
          state.tool;

        const value =
          text.trim();

        if (
          !/^\d+$/.test(value)
        ) {
          await ctx.reply(
            '❌ أرسل نسبة الخصم بالأرقام فقط.'
          );
          return;
        }

        const discount =
          Number(value);

        if (
          !Number.isSafeInteger(discount) ||
          discount < 0 ||
          discount > 100
        ) {
          await ctx.reply(
            '❌ نسبة الخصم يجب أن تكون من 0 إلى 100.'
          );
          return;
        }

        const db = loadDB();

        db.discounts[toolKey] =
          discount;

        saveDB(db);

        ownerState.set(
          OWNER_ID,
          null
        );

        await ctx.reply(
          `✅ تم حفظ الخصم.

🛠️ الأداة: ${TOOL_INFO[toolKey].name}
💰 السعر الأساسي: ${formatPrice(getToolPrice(toolKey))}
🏷️ الخصم: ${discount}%
💳 السعر بعد الخصم: ${formatPrice(getFinalToolPrice(toolKey))}`,
          discountsKeyboard()
        );

        return;
      }

      // ===== تعديل الخصم على جميع الأدوات =====
      if (
        state &&
        state.action === 'discount_edit_all' &&
        !btnTexts.includes(text)
      ) {
        const value =
          text.trim();

        if (
          !/^\d+$/.test(value)
        ) {
          await ctx.reply(
            '❌ أرسل نسبة الخصم بالأرقام فقط.'
          );
          return;
        }

        const discount =
          Number(value);

        if (
          !Number.isSafeInteger(discount) ||
          discount < 0 ||
          discount > 100
        ) {
          await ctx.reply(
            '❌ نسبة الخصم يجب أن تكون من 0 إلى 100.'
          );
          return;
        }

        const db = loadDB();

        for (
          const key of Object.keys(TOOL_INFO)
        ) {
          db.discounts[key] =
            discount;
        }

        saveDB(db);

        ownerState.set(
          OWNER_ID,
          null
        );

        await ctx.reply(
          `✅ تم تطبيق الخصم على جميع الأدوات.

🏷️ الخصم: ${discount}%

تم تطبيقه على:
🖼️ إزالة الخلفية
🔲 إنشاء QR
🎤 صوت إلى نص
🎮 لعبة X و O`,
          discountsKeyboard()
        );

        return;
      }

      // ===== إذاعة =====
      if (
        state === 'broadcast' &&
        !btnTexts.includes(text)
      ) {
        ownerState.set(
          OWNER_ID,
          null
        );

        const db = loadDB();

        let sent = 0;
        let failed = 0;

        for (
          const id of Object.keys(
            db.users
          )
        ) {
          if (
            db.users[id].is_banned
          ) {
            continue;
          }

          try {
            await bot.telegram.sendMessage(
              id,
              text
            );

            sent++;
          } catch (_) {
            failed++;
          }
        }

        await ctx.reply(
          `✅ تم الإرسال: ${sent}\n❌ فشل: ${failed}`
        );

        return;
      }

      // ===== حظر =====
      if (
        state === 'ban' &&
        !btnTexts.includes(text)
      ) {
        ownerState.set(
          OWNER_ID,
          null
        );

        const targetId =
          text.trim();

        if (
          targetId === OWNER_ID
        ) {
          await ctx.reply(
            '❌ لا يمكن حظر المالك.'
          );
          return;
        }

        if (
          !/^\d+$/.test(targetId)
        ) {
          await ctx.reply(
            '❌ أرسل آيدي رقمي صحيح.'
          );
          return;
        }

        const db = loadDB();

        if (
          db.users[targetId]
        ) {
          db.users[targetId].is_banned =
            true;

          saveDB(db);

          await ctx.reply(
            `✅ تم حظر: ${targetId}`
          );

          return;
        }

        await ctx.reply(
          '❌ المستخدم غير موجود.'
        );

        return;
      }

      // ===== فك الحظر =====
      if (
        state === 'unban' &&
        !btnTexts.includes(text)
      ) {
        ownerState.set(
          OWNER_ID,
          null
        );

        const targetId =
          text.trim();

        if (
          !/^\d+$/.test(targetId)
        ) {
          await ctx.reply(
            '❌ أرسل آيدي رقمي صحيح.'
          );
          return;
        }

        const db = loadDB();

        if (
          db.users[targetId]
        ) {
          db.users[targetId].is_banned =
            false;

          saveDB(db);

          await ctx.reply(
            `✅ تم فك الحظر عن: ${targetId}`
          );

          return;
        }

        await ctx.reply(
          '❌ المستخدم غير موجود.'
        );

        return;
      }
    }

    if (
      btnTexts.includes(text)
    ) {
      await next();
      return;
    }

    const state =
      userState.get(userId);

    // ===== QR =====
    if (
      state &&
      state.action === 'qr'
    ) {
      userState.delete(userId);

      if (!isToolEnabled('qr')) {
        await ctx.reply(
          '⛔ هذه الأداة متوقفة حاليًا.'
        );
        return;
      }

      const charge =
        chargeTool(
          userId,
          'qr'
        );

      if (!charge.success) {
        await ctx.reply(
          charge.message
        );
        return;
      }

      let filePath = null;

      try {
        const qrUrl =
          `https://api.qrserver.com/v1/create-qr-code/?size=600x600&data=${encodeURIComponent(text)}`;

        const response =
          await axios.get(
            qrUrl,
            {
              responseType:
                'arraybuffer',
              timeout: 30000
            }
          );

        filePath =
          path.join(
            TMP_DIR,
            `qr_${userId}_${Date.now()}.png`
          );

        fs.writeFileSync(
          filePath,
          Buffer.from(
            response.data
          )
        );

        await ctx.replyWithPhoto(
          { source: filePath },
          {
            caption:
              charge.charged > 0
                ? `✅ تم إنشاء QR بنجاح.\n💳 تم خصم ${charge.charged} رصيد.`
                : '✅ تم إنشاء QR بنجاح.'
          }
        );
      } catch (err) {
        if (charge.charged > 0) {
          refundToolCharge(
            userId,
            charge.charged
          );
        }

        console.error(
          'QR error:',
          err && err.message
            ? err.message
            : err
        );

        await ctx.reply(
          charge.charged > 0
            ? '❌ حدث خطأ أثناء إنشاء QR وتم إرجاع الرصيد.'
            : '❌ حدث خطأ أثناء إنشاء QR.'
        );
      } finally {
        safeUnlink(filePath);
      }

      return;
    }

    await next();
  }
);

// ==================================================
// ========== معالجة الصور ==========
// ==================================================

bot.on(
  'photo',
  async (ctx) => {
    const userId =
      String(ctx.from.id);

    const state =
      userState.get(userId);

    if (
      !state ||
      state.action !== 'removebg'
    ) {
      return;
    }

    userState.delete(userId);

    if (
      !isToolEnabled('removebg')
    ) {
      await ctx.reply(
        '⛔ هذه الأداة متوقفة حاليًا.'
      );
      return;
    }

    if (!REMOVEBG_API_KEY) {
      await ctx.reply(
        '❌ مفتاح remove.bg غير مهيأ.'
      );
      return;
    }

    const charge =
      chargeTool(
        userId,
        'removebg'
      );

    if (!charge.success) {
      await ctx.reply(
        charge.message
      );
      return;
    }

    let filePath = null;
    let statusMessage = null;

    try {
      statusMessage = await ctx.reply(
        '⏳ جارٍ إزالة الخلفية...'
      );

      const photos =
        ctx.message.photo;

      const largest =
        photos[
          photos.length - 1
        ];

      const fileLink =
        await ctx.telegram.getFileLink(
          largest.file_id
        );

      const imgRes =
        await axios.get(
          fileLink.href,
          {
            responseType:
              'arraybuffer',
            timeout: 60000
          }
        );

      const imageBuffer =
        Buffer.from(imgRes.data);

      const form =
        new FormData();

      form.append(
        'image_file',
        imageBuffer,
        {
          filename: 'image.jpg'
        }
      );

      form.append(
        'size',
        'auto'
      );

      // لا يوجد bg_color هنا
      // النتيجة ستكون PNG بخلفية شفافة

      const response =
        await axios.post(
          'https://api.remove.bg/v1.0/removebg',
          form,
          {
            headers: {
              ...form.getHeaders(),
              'X-Api-Key':
                REMOVEBG_API_KEY
            },
            responseType:
              'arraybuffer',
            timeout: 60000
          }
        );

      if (
        !response.data ||
        response.data.length < 100
      ) {
        throw new Error(
          'الصورة الناتجة غير صالحة'
        );
      }

      filePath =
        path.join(
          TMP_DIR,
          `nobg_${userId}_${Date.now()}.png`
        );

      fs.writeFileSync(
        filePath,
        Buffer.from(
          response.data
        )
      );

      await editStatusMessage(ctx, statusMessage, '✅ جاهز — تمت إزالة الخلفية.');

      await ctx.replyWithDocument(
        {
          source: filePath,
          filename:
            `nobg_${Date.now()}.png`
        },
        {
          caption:
            charge.charged > 0
              ? `🖼️ PNG بخلفية شفافة.\n💳 تم خصم ${charge.charged} رصيد.`
              : '🖼️ PNG بخلفية شفافة.'
        }
      );
    } catch (err) {
      if (charge.charged > 0) {
        refundToolCharge(
          userId,
          charge.charged
        );
      }

      let msg =
        '❌ فشل إزالة الخلفية.';

      if (
        err.response &&
        err.response.status === 402
      ) {
        msg =
          '❌ انتهى رصيد remove.bg.';
      } else if (
        err.response &&
        err.response.status === 403
      ) {
        msg =
          '❌ مفتاح remove.bg غير صحيح.';
      }

      console.error(
        'RemoveBG error:',
        err && err.message
          ? err.message
          : err
      );

      await editStatusMessage(
        ctx,
        statusMessage,
        charge.charged > 0
          ? `${msg}\n\n💰 تم إرجاع ${charge.charged} رصيد لك.`
          : msg
      );
    } finally {
      safeUnlink(filePath);
    }
  }
);

// ==================================================
// ========== معالجة الصوت ==========
// ==================================================

async function processAudioToText(
  ctx,
  fileId,
  userId
) {
  if (!isToolEnabled('stt')) {
    await ctx.reply(
      '⛔ هذه الأداة متوقفة حاليًا.'
    );
    return;
  }

  if (!GROQ_API_KEY) {
    await ctx.reply(
      '❌ مفتاح GROQ_API_KEY غير مهيأ.'
    );
    return;
  }

  const charge =
    chargeTool(
      userId,
      'stt'
    );

  if (!charge.success) {
    await ctx.reply(
      charge.message
    );
    return;
  }

  let filePath = null;
  let statusMessage = null;

  try {
    statusMessage = await ctx.reply(
      '⏳ جارٍ تحويل الصوت إلى نص...'
    );

    const fileLink =
      await ctx.telegram.getFileLink(
        fileId
      );

    const audioResponse =
      await axios.get(
        fileLink.href,
        {
          responseType:
            'arraybuffer',
          timeout: 120000,
          maxContentLength:
            25 * 1024 * 1024,
          maxBodyLength:
            25 * 1024 * 1024
        }
      );

    const contentType =
      String(
        audioResponse.headers[
          'content-type'
        ] || ''
      ).toLowerCase();

    let extension = 'ogg';

    if (
      contentType.includes('mp3')
    ) {
      extension = 'mp3';
    } else if (
      contentType.includes('mp4')
    ) {
      extension = 'mp4';
    } else if (
      contentType.includes('mpeg')
    ) {
      extension = 'mpeg';
    } else if (
      contentType.includes('wav')
    ) {
      extension = 'wav';
    } else if (
      contentType.includes('webm')
    ) {
      extension = 'webm';
    } else if (
      contentType.includes('m4a')
    ) {
      extension = 'm4a';
    }

    filePath =
      path.join(
        TMP_DIR,
        `stt_${userId}_${Date.now()}.${extension}`
      );

    fs.writeFileSync(
      filePath,
      Buffer.from(
        audioResponse.data
      )
    );

    const form =
      new FormData();

    form.append(
      'file',
      fs.createReadStream(
        filePath
      ),
      {
        filename:
          path.basename(filePath)
      }
    );

    form.append(
      'model',
      'whisper-large-v3'
    );

    form.append(
      'response_format',
      'json'
    );

    form.append(
      'temperature',
      '0'
    );

    const response =
      await axios.post(
        'https://api.groq.com/openai/v1/audio/transcriptions',
        form,
        {
          headers: {
            ...form.getHeaders(),
            Authorization:
              `Bearer ${GROQ_API_KEY}`
          },
          timeout: 180000,
          maxContentLength:
            10 * 1024 * 1024
        }
      );

    const result =
      response.data;

    const transcript =
      result &&
      typeof result.text ===
        'string'
        ? result.text.trim()
        : '';

    if (!transcript) {
      throw new Error(
        'لم يتم استخراج نص من الصوت'
      );
    }

    await editStatusMessage(ctx, statusMessage, '✅ تم تحويل الصوت إلى نص بنجاح.');

    await ctx.reply(
      charge.charged > 0
        ? `📝 النص المستخرج:\n\n${transcript}\n\n💳 تم خصم ${charge.charged} رصيد.`
        : `📝 النص المستخرج:\n\n${transcript}`
    );
  } catch (err) {
    if (charge.charged > 0) {
      refundToolCharge(
        userId,
        charge.charged
      );
    }

    let details =
      err && err.message
        ? err.message
        : 'unknown';

    try {
      if (
        err.response &&
        err.response.data
      ) {
        const raw =
          Buffer.isBuffer(
            err.response.data
          )
            ? err.response.data.toString()
            : JSON.stringify(
                err.response.data
              );

        if (raw) {
          details =
            raw.slice(0, 500);
        }
      }
    } catch (_) {}

    console.error(
      'STT error:',
      details
    );

    await editStatusMessage(
      ctx,
      statusMessage,
      charge.charged > 0
        ? '❌ فشل تحويل الصوت إلى نص.\n\n💰 تم إرجاع الرصيد لك.'
        : '❌ فشل تحويل الصوت إلى نص.'
    );
  } finally {
    safeUnlink(filePath);
  }
}

bot.on(
  'voice',
  async (ctx) => {
    const userId =
      String(ctx.from.id);

    const state =
      userState.get(userId);

    if (
      !state ||
      state.action !== 'stt'
    ) {
      return;
    }

    userState.delete(userId);

    await processAudioToText(
      ctx,
      ctx.message.voice.file_id,
      userId
    );
  }
);

bot.on(
  'audio',
  async (ctx) => {
    const userId =
      String(ctx.from.id);

    const state =
      userState.get(userId);

    if (
      !state ||
      state.action !== 'stt'
    ) {
      return;
    }

    userState.delete(userId);

    await processAudioToText(
      ctx,
      ctx.message.audio.file_id,
      userId
    );
  }
);


bot.on(
  'video',
  async (ctx) => {
    const userId = String(ctx.from.id);
    const state = userState.get(userId);

    if (!state || state.action !== 'stt') return;

    userState.delete(userId);
    await processAudioToText(
      ctx,
      ctx.message.video.file_id,
      userId
    );
  }
);

bot.on(
  'document',
  async (ctx) => {
    const userId = String(ctx.from.id);
    const state = userState.get(userId);

    if (!state || state.action !== 'stt') return;

    const mime = String(ctx.message.document.mime_type || '').toLowerCase();
    const name = String(ctx.message.document.file_name || '').toLowerCase();
    const allowed = /^(audio\/|video\/)|\.(mp3|mp4|m4a|ogg|wav|webm|mpeg|mpga|flac)$/.test(mime) || /\.(mp3|mp4|m4a|ogg|wav|webm|mpeg|mpga|flac)$/.test(name);

    if (!allowed) return;

    userState.delete(userId);
    await processAudioToText(
      ctx,
      ctx.message.document.file_id,
      userId
    );
  }
);

// ==================================================
// ========== أمر /admin ==========
// ==================================================

bot.command(
  'admin',
  async (ctx) => {
    if (
      String(ctx.from.id) !== OWNER_ID
    ) {
      await ctx.reply(
        '❌ هذا الأمر للمالك فقط.'
      );
      return;
    }

    ownerState.set(
      OWNER_ID,
      null
    );

    await ctx.reply(
      '👑 لوحة المالك',
      ownerKeyboard
    );
  }
);

// ==================================================
// ========== معالجة الأخطاء ==========
// ==================================================

bot.catch(
  (err, ctx) => {
    console.error(
      `❌ Error for ${ctx.updateType}:`,
      err && err.message
        ? err.message
        : err
    );
  }
);

// ==================================================
// ========== تشغيل ==========
// ==================================================

bot.launch({
  dropPendingUpdates: true
})
.then(() => {
  console.log(
    '✅ AI Tools Bot is running...'
  );

  console.log(
    `👑 Owner ID: ${OWNER_ID}`
  );
})
.catch((err) => {
  console.error(
    '❌ Failed to launch bot:',
    err && err.message
      ? err.message
      : err
  );

  process.exit(1);
});

process.once(
  'SIGINT',
  () => bot.stop('SIGINT')
);

process.once(
  'SIGTERM',
  () => bot.stop('SIGTERM')
);
