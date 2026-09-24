
const { Telegraf, Markup } = require("telegraf");

const BOT_TOKEN = process.env.BOT_TOKEN || process.env.TELEGRAM_BOT_TOKEN;
if (!BOT_TOKEN) throw new Error("BOT_TOKEN is missing");

const bot = new Telegraf(BOT_TOKEN);

const xoGames = new Map();
const connectGames = new Map();
const guessGames = new Map();
const rpsGames = new Map();

function id() {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
}

function gameMenu() {
  return Markup.keyboard([
    ["🎮 X و O", "✊ حجر ورق مقص"],
    ["🔴 أربعة في صف", "🔢 تخمين الرقم"],
  ]).resize();
}

bot.start(async (ctx) => {
  await ctx.reply(
    "🎮 ألعاب Experiences\n\nاختر لعبة:",
    gameMenu()
  );
});

bot.hears("🎮 الألعاب", async (ctx) => {
  await ctx.reply("🎮 اختر لعبة:", gameMenu());
});

/* =========================================================
   X و O
   ========================================================= */

function xoWinner(board) {
  const lines = [
    [0,1,2],[3,4,5],[6,7,8],
    [0,3,6],[1,4,7],[2,5,8],
    [0,4,8],[2,4,6]
  ];
  for (const [a,b,c] of lines) {
    if (board[a] && board[a] === board[b] && board[a] === board[c]) {
      return board[a];
    }
  }
  return board.every(Boolean) ? "draw" : null;
}

function xoText(g) {
  let s = "🎮 لعبة X و O\n\n";
  for (let r = 0; r < 3; r++) {
    s += `${g.board[r*3] || "⬜"} ${g.board[r*3+1] || "⬜"} ${g.board[r*3+2] || "⬜"}\n`;
  }
  s += "\n";
  if (g.status === "finished") {
    s += g.winner === "draw" ? "🤝 تعادل!" : `🏆 الفائز: ${g.winner}`;
  } else if (g.mode === "bot") {
    s += g.turn === "X" ? "🎯 دورك — ❌ X" : "🤖 دور البوت — ⭕ O";
  } else {
    s += g.turn === "X" ? "🎯 دور اللاعب الأول — ❌ X" : "🎯 دور اللاعب الثاني — ⭕ O";
  }
  return s;
}

function xoKeyboard(g) {
  const rows = [];
  for (let r = 0; r < 3; r++) {
    const row = [];
    for (let c = 0; c < 3; c++) {
      const n = r * 3 + c;
      row.push(Markup.button.callback(
        g.board[n] || "⬜",
        g.board[n] ? "noop" : `xo:${g.id}:${n}`
      ));
    }
    rows.push(row);
  }
  rows.push([
    Markup.button.callback("🔄 إعادة اللعب", `xore:${g.id}`),
    Markup.button.callback("❌ إنهاء", `xoend:${g.id}`)
  ]);
  return Markup.inlineKeyboard(rows);
}

function minimax(board, maximizing) {
  const result = xoWinner(board);
  if (result === "O") return 10;
  if (result === "X") return -10;
  if (result === "draw") return 0;

  if (maximizing) {
    let best = -Infinity;
    for (let i = 0; i < 9; i++) {
      if (!board[i]) {
        board[i] = "O";
        best = Math.max(best, minimax(board, false));
        board[i] = "";
      }
    }
    return best;
  }

  let best = Infinity;
  for (let i = 0; i < 9; i++) {
    if (!board[i]) {
      board[i] = "X";
      best = Math.min(best, minimax(board, true));
      board[i] = "";
    }
  }
  return best;
}

function botMove(board) {
  let bestScore = -Infinity;
  let best = null;

  for (let i = 0; i < 9; i++) {
    if (!board[i]) {
      board[i] = "O";
      const score = minimax(board, false);
      board[i] = "";
      if (score > bestScore) {
        bestScore = score;
        best = i;
      }
    }
  }
  return best;
}

bot.hears("🎮 X و O", async (ctx) => {
  await ctx.reply(
    "🎮 لعبة X و O\n\nاختر طريقة اللعب:",
    Markup.inlineKeyboard([
      [Markup.button.callback("🤖 ضد الذكاء الاصطناعي", "xostart:bot")],
      [Markup.button.callback("📱 لاعبين على نفس الجوال", "xostart:local")]
    ])
  );
});

bot.action(/^xostart:(bot|local)$/, async (ctx) => {
  await ctx.answerCbQuery();

  const mode = ctx.match[1];
  const g = {
    id: id(),
    mode,
    board: Array(9).fill(""),
    turn: "X",
    status: "playing",
    winner: null,
    userId: String(ctx.from.id),
    createdAt: Date.now()
  };

  xoGames.set(g.id, g);
  await ctx.reply(xoText(g), xoKeyboard(g));
});

bot.action(/^xo:([^:]+):([0-8])$/, async (ctx) => {
  const g = xoGames.get(ctx.match[1]);
  const n = Number(ctx.match[2]);

  if (!g) return ctx.answerCbQuery("❌ انتهت اللعبة.", { show_alert: true });
  if (g.status === "finished") return ctx.answerCbQuery("🏁 انتهت اللعبة.");
  if (String(ctx.from.id) !== g.userId) return ctx.answerCbQuery("❌ هذه اللعبة ليست لك.");
  if (g.board[n]) return ctx.answerCbQuery("❌ الخانة مستخدمة.");
  if (g.turn !== "X") return ctx.answerCbQuery("⏳ انتظر دور البوت.");

  g.board[n] = "X";
  let result = xoWinner(g.board);

  if (!result) {
    g.turn = "O";
    if (g.mode === "bot") {
      const move = botMove(g.board);
      if (move !== null) g.board[move] = "O";
      result = xoWinner(g.board);
      if (!result) g.turn = "X";
    } else {
      g.turn = "O";
    }
  }

  if (result) {
    g.status = "finished";
    g.winner = result;
  }

  await ctx.answerCbQuery();
  await ctx.editMessageText(xoText(g), xoKeyboard(g));
});

bot.action(/^xore:(.+)$/, async (ctx) => {
  const old = xoGames.get(ctx.match[1]);
  if (!old) return ctx.answerCbQuery("❌ انتهت اللعبة.");

  const g = {
    ...old,
    board: Array(9).fill(""),
    turn: "X",
    status: "playing",
    winner: null,
    createdAt: Date.now()
  };
  xoGames.set(g.id, g);
  await ctx.answerCbQuery("🔄 بدأت لعبة جديدة");
  await ctx.editMessageText(xoText(g), xoKeyboard(g));
});

bot.action(/^xoend:(.+)$/, async (ctx) => {
  xoGames.delete(ctx.match[1]);
  await ctx.answerCbQuery("تم إنهاء اللعبة.");
  try { await ctx.editMessageText("❌ تم إنهاء لعبة X و O."); } catch (_) {}
});

/* =========================================================
   حجر ورق مقص
   ========================================================= */

const RPS = {
  rock: "✊",
  paper: "✋",
  scissors: "✌️"
};

function rpsResult(a, b) {
  if (a === b) return "draw";
  if (
    (a === "rock" && b === "scissors") ||
    (a === "paper" && b === "rock") ||
    (a === "scissors" && b === "paper")
  ) return "win";
  return "lose";
}

bot.hears("✊ حجر ورق مقص", async (ctx) => {
  const g = { id: id(), userId: String(ctx.from.id) };
  rpsGames.set(g.id, g);

  await ctx.reply(
    "✊ حجر ورق مقص\n\nاختر حركتك:",
    Markup.inlineKeyboard([
      [
        Markup.button.callback("✊ حجر", `rps:${g.id}:rock`),
        Markup.button.callback("✋ ورق", `rps:${g.id}:paper`)
      ],
      [Markup.button.callback("✌️ مقص", `rps:${g.id}:scissors`)]
    ])
  );
});

bot.action(/^rps:([^:]+):(rock|paper|scissors)$/, async (ctx) => {
  const g = rpsGames.get(ctx.match[1]);
  if (!g) return ctx.answerCbQuery("❌ انتهت اللعبة.");
  if (String(ctx.from.id) !== g.userId) return ctx.answerCbQuery("❌ هذه اللعبة ليست لك.");

  const keys = Object.keys(RPS);
  const botChoice = keys[Math.floor(Math.random() * keys.length)];
  const result = rpsResult(ctx.match[2], botChoice);

  const title =
    result === "win" ? "🏆 فزت!" :
    result === "lose" ? "🤖 فاز الذكاء الاصطناعي!" :
    "🤝 تعادل!";

  rpsGames.delete(g.id);
  await ctx.answerCbQuery();
  await ctx.editMessageText(
    `✊ حجر ورق مقص\n\nأنت: ${RPS[ctx.match[2]]}\nالذكاء الاصطناعي: ${RPS[botChoice]}\n\n${title}`,
    Markup.inlineKeyboard([
      [Markup.button.callback("🔄 لعب مرة أخرى", "rpsagain")]
    ])
  );
});

bot.action("rpsagain", async (ctx) => {
  await ctx.answerCbQuery();
  const g = { id: id(), userId: String(ctx.from.id) };
  rpsGames.set(g.id, g);
  await ctx.editMessageText(
    "✊ حجر ورق مقص\n\nاختر حركتك:",
    Markup.inlineKeyboard([
      [
        Markup.button.callback("✊ حجر", `rps:${g.id}:rock`),
        Markup.button.callback("✋ ورق", `rps:${g.id}:paper`)
      ],
      [Markup.button.callback("✌️ مقص", `rps:${g.id}:scissors`)]
    ])
  );
});

/* =========================================================
   تخمين الرقم
   ========================================================= */

bot.hears("🔢 تخمين الرقم", async (ctx) => {
  const g = {
    id: id(),
    userId: String(ctx.from.id),
    secret: Math.floor(Math.random() * 100) + 1,
    attempts: 0
  };
  guessGames.set(g.id, g);

  await ctx.reply(
    "🔢 لعبة تخمين الرقم\n\nخمّن رقمًا من 1 إلى 100 وأرسل الرقم هنا."
  );
});

bot.on("text", async (ctx, next) => {
  const userId = String(ctx.from.id);
  const text = ctx.message.text.trim();

  if (["/start", "🎮 X و O", "✊ حجر ورق مقص", "🔴 أربعة في صف", "🔢 تخمين الرقم", "🎮 الألعاب"].includes(text)) {
    return next();
  }

  const g = [...guessGames.values()].reverse().find(x => x.userId === userId);
  if (!g) return next();

  if (!/^\d+$/.test(text)) {
    return ctx.reply("❌ أرسل رقمًا من 1 إلى 100.");
  }

  const n = Number(text);
  if (n < 1 || n > 100) {
    return ctx.reply("❌ الرقم يجب أن يكون من 1 إلى 100.");
  }

  g.attempts++;

  if (n === g.secret) {
    guessGames.delete(g.id);
    return ctx.reply(`🏆 صحيح!\n\nالرقم هو ${g.secret}\nعدد المحاولات: ${g.attempts}`);
  }

  await ctx.reply(n < g.secret ? "⬆️ الرقم أكبر." : "⬇️ الرقم أصغر.");
});

/* =========================================================
   أربعة في صف - لاعبان على نفس الجوال
   ========================================================= */

const C_ROWS = 6;
const C_COLS = 7;

function emptyConnectBoard() {
  return Array.from({ length: C_ROWS }, () => Array(C_COLS).fill(""));
}

function connectWinner(b, p) {
  const dirs = [[0,1],[1,0],[1,1],[1,-1]];
  for (let r = 0; r < C_ROWS; r++) {
    for (let c = 0; c < C_COLS; c++) {
      if (b[r][c] !== p) continue;
      for (const [dr, dc] of dirs) {
        let count = 1;
        for (let k = 1; k < 4; k++) {
          const rr = r + dr*k, cc = c + dc*k;
          if (rr < 0 || rr >= C_ROWS || cc < 0 || cc >= C_COLS || b[rr][cc] !== p) break;
          count++;
        }
        if (count >= 4) return true;
      }
    }
  }
  return false;
}

function connectText(g) {
  let s = "🔴 أربعة في صف\n\n";
  for (let r = 0; r < C_ROWS; r++) {
    s += g.board[r].map(x => x || "⚪").join("");
    s += "\n";
  }
  s += "\n";
  if (g.finished) {
    s += g.winner === "draw" ? "🤝 تعادل!" : `🏆 الفائز: ${g.winner === "R" ? "🔴" : "🟡"}`;
  } else {
    s += g.turn === "R" ? "🔴 دور اللاعب الأول" : "🟡 دور اللاعب الثاني";
  }
  return s;
}

function connectKeyboard(g) {
  const rows = [];
  rows.push(Array.from({ length: C_COLS }, (_, c) =>
    Markup.button.callback(String(c + 1), `c4:${g.id}:${c}`)
  ));
  rows.push([
    Markup.button.callback("🔄 إعادة اللعب", `c4re:${g.id}`),
    Markup.button.callback("❌ إنهاء", `c4end:${g.id}`)
  ]);
  return Markup.inlineKeyboard(rows);
}

bot.hears("🔴 أربعة في صف", async (ctx) => {
  const g = {
    id: id(),
    userId: String(ctx.from.id),
    board: emptyConnectBoard(),
    turn: "R",
    finished: false,
    winner: null
  };
  connectGames.set(g.id, g);
  await ctx.reply(connectText(g), connectKeyboard(g));
});

bot.action(/^c4:([^:]+):([0-6])$/, async (ctx) => {
  const g = connectGames.get(ctx.match[1]);
  const col = Number(ctx.match[2]);

  if (!g) return ctx.answerCbQuery("❌ انتهت اللعبة.");
  if (String(ctx.from.id) !== g.userId) return ctx.answerCbQuery("❌ هذه اللعبة ليست لك.");
  if (g.finished) return ctx.answerCbQuery("🏁 انتهت اللعبة.");

  let row = -1;
  for (let r = C_ROWS - 1; r >= 0; r--) {
    if (!g.board[r][col]) { row = r; break; }
  }
  if (row === -1) return ctx.answerCbQuery("❌ العمود ممتلئ.");

  const p = g.turn;
  g.board[row][col] = p;

  if (connectWinner(g.board, p)) {
    g.finished = true;
    g.winner = p;
  } else if (g.board[0].every(Boolean)) {
    g.finished = true;
    g.winner = "draw";
  } else {
    g.turn = p === "R" ? "Y" : "R";
  }

  await ctx.answerCbQuery();
  await ctx.editMessageText(connectText(g), connectKeyboard(g));
});

bot.action(/^c4re:(.+)$/, async (ctx) => {
  const g = connectGames.get(ctx.match[1]);
  if (!g) return ctx.answerCbQuery("❌ انتهت اللعبة.");
  g.board = emptyConnectBoard();
  g.turn = "R";
  g.finished = false;
  g.winner = null;
  await ctx.answerCbQuery("🔄 بدأت لعبة جديدة");
  await ctx.editMessageText(connectText(g), connectKeyboard(g));
});

bot.action(/^c4end:(.+)$/, async (ctx) => {
  connectGames.delete(ctx.match[1]);
  await ctx.answerCbQuery("تم إنهاء اللعبة.");
  try { await ctx.editMessageText("❌ تم إنهاء لعبة أربعة في صف."); } catch (_) {}
});

bot.action("noop", async (ctx) => {
  await ctx.answerCbQuery("❌ هذه الخانة مستخدمة.");
});

/* تنظيف الألعاب القديمة */
setInterval(() => {
  const limit = Date.now() - 2 * 60 * 60 * 1000;
  for (const [k, g] of xoGames) if ((g.createdAt || 0) < limit) xoGames.delete(k);
}, 10 * 60 * 1000);

bot.catch((err) => {
  console.error("BOT ERROR:", err && err.stack ? err.stack : err);
});

bot.launch()
  .then(() => console.log("Experiences games bot is running"))
  .catch((err) => {
    console.error("Failed to launch bot:", err && err.stack ? err.stack : err);
    process.exit(1);
  });

process.once("SIGINT", () => bot.stop("SIGINT"));
process.once("SIGTERM", () => bot.stop("SIGTERM"));
