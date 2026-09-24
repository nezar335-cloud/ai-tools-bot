const { Telegraf, Markup } = require('telegraf');
const http = require('http');

const BOT_TOKEN = process.env.BOT_TOKEN;

if (!BOT_TOKEN) {
  throw new Error('BOT_TOKEN is missing');
}

const bot = new Telegraf(BOT_TOKEN);

/* =========================================================
   STORAGE
   ========================================================= */

const users = new Map();
const waiting = {
  ttt: null,
  rps: null,
  connect4: null,
  dice: null
};

const games = new Map();

function getUser(id) {
  if (!users.has(id)) {
    users.set(id, {
      state: null,
      data: {}
    });
  }

  return users.get(id);
}

function gameKey(a, b) {
  return [a, b].sort((x, y) => x - y).join(':');
}

function clearUserState(id) {
  const user = getUser(id);
  user.state = null;
  user.data = {};
}

/* =========================================================
   MAIN MENU
   ========================================================= */

function gamesMenu() {
  return Markup.inlineKeyboard([
    [
      Markup.button.callback('❌⭕ X و O', 'game_ttt'),
      Markup.button.callback('✊ حجر ورق مقص', 'game_rps')
    ],
    [
      Markup.button.callback('🔴 أربعة في صف', 'game_connect4'),
      Markup.button.callback('🎲 النرد', 'game_dice')
    ],
    [
      Markup.button.callback('🧠 الذاكرة', 'game_memory'),
      Markup.button.callback('🔢 تخمين الرقم', 'game_guess')
    ],
    [
      Markup.button.callback('⚡ أسرع إجابة', 'game_fast')
    ]
  ]);
}

function backButton() {
  return Markup.inlineKeyboard([
    [Markup.button.callback('🎮 الألعاب', 'games_menu')]
  ]);
}

bot.start(async (ctx) => {
  clearUserState(ctx.from.id);

  await ctx.reply(
    `🎮 أهلاً بك في بوت الألعاب

اختر لعبة من القائمة:`,
    gamesMenu()
  );
});

bot.command('games', async (ctx) => {
  clearUserState(ctx.from.id);

  await ctx.reply(
    '🎮 اختر اللعبة:',
    gamesMenu()
  );
});

bot.action('games_menu', async (ctx) => {
  await ctx.answerCbQuery();
  clearUserState(ctx.from.id);

  await ctx.editMessageText(
    '🎮 اختر اللعبة:',
    gamesMenu()
  );
});

/* =========================================================
   X O
   ========================================================= */

function tttBoard(board, gameId) {
  const buttons = [];

  for (let r = 0; r < 3; r++) {
    const row = [];

    for (let c = 0; c < 3; c++) {
      const i = r * 3 + c;

      row.push(
        Markup.button.callback(
          board[i] || '⬜',
          `ttt_move:${gameId}:${i}`
        )
      );
    }

    buttons.push(row);
  }

  buttons.push([
    Markup.button.callback('❌ خروج', `game_cancel:${gameId}`)
  ]);

  return Markup.inlineKeyboard(buttons);
}

function checkWinner(board) {
  const wins = [
    [0, 1, 2],
    [3, 4, 5],
    [6, 7, 8],
    [0, 3, 6],
    [1, 4, 7],
    [2, 5, 8],
    [0, 4, 8],
    [2, 4, 6]
  ];

  for (const [a, b, c] of wins) {
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

function minimax(board, maximizing) {
  const result = checkWinner(board);

  if (result === 'O') return 10;
  if (result === 'X') return -10;
  if (result === 'draw') return 0;

  const moves = [];

  for (let i = 0; i < 9; i++) {
    if (!board[i]) {
      board[i] = maximizing ? 'O' : 'X';

      const score = minimax(board, !maximizing);

      board[i] = null;

      moves.push({
        index: i,
        score
      });
    }
  }

  if (maximizing) {
    return Math.max(...moves.map(x => x.score));
  }

  return Math.min(...moves.map(x => x.score));
}

function bestAIMove(board) {
  let bestScore = -Infinity;
  let bestMove = null;

  for (let i = 0; i < 9; i++) {
    if (!board[i]) {
      board[i] = 'O';

      const score = minimax(board, false);

      board[i] = null;

      if (score > bestScore) {
        bestScore = score;
        bestMove = i;
      }
    }
  }

  return bestMove;
}

bot.action('game_ttt', async (ctx) => {
  await ctx.answerCbQuery();

  await ctx.editMessageText(
    `❌⭕ X و O

اختر طريقة اللعب:`,
    Markup.inlineKeyboard([
      [
        Markup.button.callback('🤖 ضد الذكاء الاصطناعي', 'ttt_ai')
      ],
      [
        Markup.button.callback('👥 ضد لاعب', 'ttt_pvp')
      ],
      [
        Markup.button.callback('🔙 رجوع', 'games_menu')
      ]
    ])
  );
});

bot.action('ttt_ai', async (ctx) => {
  await ctx.answerCbQuery();

  const id = `ttt_ai_${ctx.from.id}_${Date.now()}`;

  games.set(id, {
    type: 'ttt_ai',
    board: Array(9).fill(null),
    player: ctx.from.id
  });

  await ctx.editMessageText(
    `❌⭕ X و O

أنت X وتبدأ أولاً.`,
    tttBoard(games.get(id).board, id)
  );
});

bot.action('ttt_pvp', async (ctx) => {
  await ctx.answerCbQuery();

  const id = ctx.from.id;

  if (waiting.ttt === id) {
    await ctx.answerCbQuery('أنت بالفعل في قائمة الانتظار');
    return;
  }

  if (waiting.ttt && waiting.ttt !== id) {
    const opponent = waiting.ttt;
    waiting.ttt = null;

    const gameId = `ttt_${gameKey(id, opponent)}_${Date.now()}`;

    games.set(gameId, {
      type: 'ttt_pvp',
      players: [opponent, id],
      turn: opponent,
      board: Array(9).fill(null)
    });

    await ctx.editMessageText(
      `❌⭕ بدأت المباراة!

دورك إذا كان رمزك X.`,
      tttBoard(games.get(gameId).board, gameId)
    );

    try {
      await bot.telegram.sendMessage(
        opponent,
        `❌⭕ تم العثور على لاعب!

أنت X وتبدأ.`,
        tttBoard(games.get(gameId).board, gameId)
      );
    } catch (_) {}

    return;
  }

  waiting.ttt = id;

  await ctx.editMessageText(
    `❌⭕ X و O

⏳ أنت في انتظار لاعب آخر...

عندما يدخل لاعب آخر تبدأ المباراة.`,
    backButton()
  );
});

bot.action(/^ttt_move:(.+):(\d+)$/, async (ctx) => {
  await ctx.answerCbQuery();

  const gameId = ctx.match[1];
  const index = Number(ctx.match[2]);

  const game = games.get(gameId);

  if (!game) return;

  if (game.board[index]) {
    await ctx.answerCbQuery('هذه الخانة مستخدمة');
    return;
  }

  if (game.type === 'ttt_ai') {
    game.board[index] = 'X';

    let result = checkWinner(game.board);

    if (result) {
      await finishTTT(ctx, game, result);
      return;
    }

    const aiMove = bestAIMove(game.board);

    if (aiMove !== null) {
      game.board[aiMove] = 'O';
    }

    result = checkWinner(game.board);

    if (result) {
      await finishTTT(ctx, game, result);
      return;
    }

    await ctx.editMessageText(
      `❌⭕ X و O

أنت X`,
      tttBoard(game.board, gameId)
    );

    return;
  }

  if (!game.players.includes(ctx.from.id)) return;

  if (game.turn !== ctx.from.id) {
    await ctx.answerCbQuery('ليس دورك');
    return;
  }

  const symbol =
    game.players[0] === ctx.from.id ? 'X' : 'O';

  game.board[index] = symbol;

  const result = checkWinner(game.board);

  if (result) {
    await finishTTTPvp(gameId, result);
    return;
  }

  game.turn =
    game.players.find(id => id !== ctx.from.id);

  await updateTTTPvp(gameId);
});

async function finishTTT(ctx, game, result) {
  games.delete(
    [...games.entries()].find(([, g]) => g === game)?.[0]
  );

  let text;

  if (result === 'X') {
    text = '🏆 فزت! X انتصر.';
  } else if (result === 'O') {
    text = '🤖 الذكاء الاصطناعي فاز.';
  } else {
    text = '🤝 تعادل!';
  }

  await ctx.editMessageText(
    `❌⭕ X و O\n\n${text}`,
    backButton()
  );
}

async function finishTTTPvp(gameId, result) {
  const game = games.get(gameId);

  if (!game) return;

  games.delete(gameId);

  let text;

  if (result === 'draw') {
    text = '🤝 انتهت المباراة بالتعادل.';
  } else {
    const winner =
      result === 'X'
        ? game.players[0]
        : game.players[1];

    const loser =
      game.players.find(id => id !== winner);

    text = `🏆 الفائز: لاعب ${winner}`;
  }

  for (const player of game.players) {
    try {
      await bot.telegram.sendMessage(
        player,
        `❌⭕ X و O\n\n${text}`,
        backButton()
      );
    } catch (_) {}
  }
}

async function updateTTTPvp(gameId) {
  const game = games.get(gameId);

  if (!game) return;

  for (const player of game.players) {
    const symbol =
      game.players[0] === player ? 'X' : 'O';

    const turnText =
      game.turn === player
        ? '🔥 دورك الآن'
        : '⏳ انتظر دور اللاعب الآخر';

    try {
      await bot.telegram.sendMessage(
        player,
        `❌⭕ X و O

رمزك: ${symbol}
${turnText}`,
        tttBoard(game.board, gameId)
      );
    } catch (_) {}
  }
}

/* =========================================================
   ROCK PAPER SCISSORS
   ========================================================= */

const rpsChoices = {
  rock: '🪨',
  paper: '📄',
  scissors: '✂️'
};

function rpsKeyboard(prefix) {
  return Markup.inlineKeyboard([
    [
      Markup.button.callback('🪨', `${prefix}:rock`),
      Markup.button.callback('📄', `${prefix}:paper`),
      Markup.button.callback('✂️', `${prefix}:scissors`)
    ],
    [
      Markup.button.callback('🔙 رجوع', 'games_menu')
    ]
  ]);
}

function rpsWinner(a, b) {
  if (a === b) return 'draw';

  if (
    (a === 'rock' && b === 'scissors') ||
    (a === 'paper' && b === 'rock') ||
    (a === 'scissors' && b === 'paper')
  ) {
    return 'a';
  }

  return 'b';
}

bot.action('game_rps', async (ctx) => {
  await ctx.answerCbQuery();

  await ctx.editMessageText(
    '✊ حجر ورق مقص\n\nاختر طريقة اللعب:',
    Markup.inlineKeyboard([
      [
        Markup.button.callback('🤖 ضد AI', 'rps_ai')
      ],
      [
        Markup.button.callback('👥 ضد لاعب', 'rps_pvp')
      ],
      [
        Markup.button.callback('🔙 رجوع', 'games_menu')
      ]
    ])
  );
});

bot.action('rps_ai', async (ctx) => {
  await ctx.answerCbQuery();

  getUser(ctx.from.id).state = 'rps_ai';

  await ctx.editMessageText(
    '✊ حجر ورق مقص\n\nاختر:',
    rpsKeyboard('rps_ai_move')
  );
});

bot.action(/^rps_ai_move:(rock|paper|scissors)$/, async (ctx) => {
  await ctx.answerCbQuery();

  const player = ctx.match[1];

  const choices = Object.keys(rpsChoices);
  const ai = choices[Math.floor(Math.random() * choices.length)];

  const result = rpsWinner(player, ai);

  let text;

  if (result === 'draw') {
    text = '🤝 تعادل!';
  } else if (result === 'a') {
    text = '🏆 أنت فزت!';
  } else {
    text = '🤖 الذكاء الاصطناعي فاز.';
  }

  await ctx.editMessageText(
    `✊ حجر ورق مقص

أنت: ${rpsChoices[player]}
AI: ${rpsChoices[ai]}

${text}`,
    backButton()
  );
});

bot.action('rps_pvp', async (ctx) => {
  await ctx.answerCbQuery();

  const id = ctx.from.id;

  if (waiting.rps === id) {
    await ctx.answerCbQuery('أنت في الانتظار بالفعل');
    return;
  }

  if (waiting.rps && waiting.rps !== id) {
    const opponent = waiting.rps;
    waiting.rps = null;

    const gameId = `rps_${gameKey(id, opponent)}_${Date.now()}`;

    games.set(gameId, {
      type: 'rps_pvp',
      players: [opponent, id],
      choices: {}
    });

    for (const player of [opponent, id]) {
      try {
        await bot.telegram.sendMessage(
          player,
          `✊ حجر ورق مقص

تم العثور على لاعب.
اختر حركتك:`,
          rpsKeyboard(`rps_pvp_move:${gameId}`)
        );
      } catch (_) {}
    }

    return;
  }

  waiting.rps = id;

  await ctx.editMessageText(
    `✊ حجر ورق مقص

⏳ في انتظار لاعب...`,
    backButton()
  );
});

bot.action(/^rps_pvp_move:(.+):(rock|paper|scissors)$/, async (ctx) => {
  await ctx.answerCbQuery();

  const gameId = ctx.match[1];
  const choice = ctx.match[2];

  const game = games.get(gameId);

  if (!game) return;

  if (!game.players.includes(ctx.from.id)) return;

  if (game.choices[ctx.from.id]) {
    await ctx.answerCbQuery('اخترت بالفعل');
    return;
  }

  game.choices[ctx.from.id] = choice;

  await ctx.editMessageText(
    '✊ تم تسجيل اختيارك.\n\n⏳ في انتظار اللاعب الآخر...'
  );

  if (Object.keys(game.choices).length < 2) return;

  const a = game.players[0];
  const b = game.players[1];

  const result = rpsWinner(
    game.choices[a],
    game.choices[b]
  );

  let text;

  if (result === 'draw') {
    text = '🤝 تعادل!';
  } else {
    const winner = result === 'a' ? a : b;
    text = `🏆 الفائز: لاعب ${winner}`;
  }

  games.delete(gameId);

  for (const player of game.players) {
    try {
      await bot.telegram.sendMessage(
        player,
        `✊ حجر ورق مقص\n\n${text}`,
        backButton()
      );
    } catch (_) {}
  }
});

/* =========================================================
   CONNECT 4
   ========================================================= */

function connect4Board(board, gameId) {
  const rows = [];

  for (let r = 0; r < 6; r++) {
    const row = [];

    for (let c = 0; c < 7; c++) {
      const value = board[r][c] || '⚪';

      row.push(
        Markup.button.callback(
          value,
          `c4_move:${gameId}:${c}`
        )
      );
    }

    rows.push(row);
  }

  rows.push([
    Markup.button.callback('❌ خروج', `game_cancel:${gameId}`)
  ]);

  return Markup.inlineKeyboard(rows);
}

function createC4Board() {
  return Array.from(
    { length: 6 },
    () => Array(7).fill(null)
  );
}

function c4Drop(board, col, symbol) {
  for (let r = 5; r >= 0; r--) {
    if (!board[r][col]) {
      board[r][col] = symbol;
      return r;
    }
  }

  return -1;
}

function c4Winner(board) {
  const directions = [
    [0, 1],
    [1, 0],
    [1, 1],
    [1, -1]
  ];

  for (let r = 0; r < 6; r++) {
    for (let c = 0; c < 7; c++) {
      if (!board[r][c]) continue;

      for (const [dr, dc] of directions) {
        let count = 1;

        for (let n = 1; n < 4; n++) {
          const rr = r + dr * n;
          const cc = c + dc * n;

          if (
            rr >= 0 &&
            rr < 6 &&
            cc >= 0 &&
            cc < 7 &&
            board[rr][cc] === board[r][c]
          ) {
            count++;
          } else {
            break;
          }
        }

        if (count >= 4) {
          return board[r][c];
        }
      }
    }
  }

  if (board.every(row => row.every(Boolean))) {
    return 'draw';
  }

  return null;
}

bot.action('game_connect4', async (ctx) => {
  await ctx.answerCbQuery();

  const id = ctx.from.id;

  if (waiting.connect4 && waiting.connect4 !== id) {
    const opponent = waiting.connect4;
    waiting.connect4 = null;

    const gameId = `c4_${gameKey(id, opponent)}_${Date.now()}`;

    games.set(gameId, {
      type: 'connect4',
      players: [opponent, id],
      turn: opponent,
      board: createC4Board()
    });

    await sendC4State(gameId);
    return;
  }

  waiting.connect4 = id;

  await ctx.editMessageText(
    `🔴 أربعة في صف

⏳ في انتظار لاعب آخر...`,
    backButton()
  );
});

async function sendC4State(gameId) {
  const game = games.get(gameId);

  if (!game) return;

  for (const player of game.players) {
    const symbol =
      player === game.players[0] ? '🔴' : '🟡';

    const text =
      game.turn === player
        ? `🔴 أربعة في صف\n\nرمزك: ${symbol}\n🔥 دورك`
        : `🔴 أربعة في صف\n\nرمزك: ${symbol}\n⏳ انتظر دور الخصم`;

    try {
      await bot.telegram.sendMessage(
        player,
        text,
        connect4Board(game.board, gameId)
      );
    } catch (_) {}
  }
}

bot.action(/^c4_move:(.+):(\d+)$/, async (ctx) => {
  await ctx.answerCbQuery();

  const gameId = ctx.match[1];
  const col = Number(ctx.match[2]);

  const game = games.get(gameId);

  if (!game) return;

  if (game.turn !== ctx.from.id) {
    await ctx.answerCbQuery('ليس دورك');
    return;
  }

  const symbol =
    game.players[0] === ctx.from.id ? '🔴' : '🟡';

  if (c4Drop(game.board, col, symbol) === -1) {
    await ctx.answerCbQuery('هذا العمود ممتلئ');
    return;
  }

  const result = c4Winner(game.board);

  if (result) {
    games.delete(gameId);

    const text =
      result === 'draw'
        ? '🤝 تعادل!'
        : `🏆 الفائز: ${result}`;

    for (const player of game.players) {
      try {
        await bot.telegram.sendMessage(
          player,
          `🔴 أربعة في صف\n\n${text}`,
          backButton()
        );
      } catch (_) {}
    }

    return;
  }

  game.turn =
    game.players.find(id => id !== ctx.from.id);

  await sendC4State(gameId);
});

/* =========================================================
   DICE
   ========================================================= */

bot.action('game_dice', async (ctx) => {
  await ctx.answerCbQuery();

  const id = ctx.from.id;

  if (waiting.dice && waiting.dice !== id) {
    const opponent = waiting.dice;
    waiting.dice = null;

    const gameId = `dice_${gameKey(id, opponent)}_${Date.now()}`;

    games.set(gameId, {
      type: 'dice',
      players: [opponent, id],
      rolls: {}
    });

    for (const player of [opponent, id]) {
      try {
        await bot.telegram.sendMessage(
          player,
          `🎲 مباراة نرد\n\nاضغط لرمي النرد:`,
          Markup.inlineKeyboard([
            [
              Markup.button.callback(
                '🎲 ارمي النرد',
                `dice_roll:${gameId}`
              )
            ]
          ])
        );
      } catch (_) {}
    }

    return;
  }

  waiting.dice = id;

  await ctx.editMessageText(
    `🎲 النرد

⏳ في انتظار لاعب آخر...`,
    backButton()
  );
});

bot.action(/^dice_roll:(.+)$/, async (ctx) => {
  await ctx.answerCbQuery();

  const gameId = ctx.match[1];
  const game = games.get(gameId);

  if (!game) return;

  if (game.rolls[ctx.from.id]) {
    await ctx.answerCbQuery('رميت بالفعل');
    return;
  }

  const value =
    Math.floor(Math.random() * 6) + 1;

  game.rolls[ctx.from.id] = value;

  await ctx.editMessageText(
    `🎲 رميتك: ${value}\n\n⏳ في انتظار اللاعب الآخر...`
  );

  if (Object.keys(game.rolls).length < 2) return;

  const a = game.players[0];
  const b = game.players[1];

  const va = game.rolls[a];
  const vb = game.rolls[b];

  let result;

  if (va > vb) {
    result = `🏆 الفائز لاعب ${a}`;
  } else if (vb > va) {
    result = `🏆 الفائز لاعب ${b}`;
  } else {
    result = '🤝 تعادل!';
  }

  games.delete(gameId);

  for (const player of game.players) {
    try {
      await bot.telegram.sendMessage(
        player,
        `🎲 النرد

🎲 لاعب 1: ${va}
🎲 لاعب 2: ${vb}

${result}`,
        backButton()
      );
    } catch (_) {}
  }
});

/* =========================================================
   MEMORY
   ========================================================= */

function createMemorySequence(length) {
  const symbols = [
    '🍎',
    '🍌',
    '🍇',
    '🍉',
    '🍒',
    '🥝',
    '🍋',
    '🥭',
    '🍓',
    '🍑'
  ];

  const result = [];

  for (let i = 0; i < length; i++) {
    result.push(
      symbols[Math.floor(Math.random() * symbols.length)]
    );
  }

  return result;
}

bot.action('game_memory', async (ctx) => {
  await ctx.answerCbQuery();

  const sequence = createMemorySequence(5);

  const user = getUser(ctx.from.id);

  user.state = 'memory';
  user.data = {
    sequence,
    answer: [],
    startedAt: Date.now()
  };

  await ctx.editMessageText(
    `🧠 تحدي الذاكرة

احفظ الترتيب:

${sequence.join('  ')}

⏳ سأخفيه بعد 3 ثواني...`
  );

  setTimeout(async () => {
    try {
      const current = getUser(ctx.from.id);

      if (current.state !== 'memory') return;

      await ctx.editMessageText(
        `🧠 تحدي الذاكرة

اختَر الرموز بالترتيب الذي ظهر:`,
        memoryKeyboard()
      );
    } catch (_) {}
  }, 3000);
});

function memoryKeyboard() {
  return Markup.inlineKeyboard([
    [
      Markup.button.callback('🍎', 'memory_pick:🍎'),
      Markup.button.callback('🍌', 'memory_pick:🍌'),
      Markup.button.callback('🍇', 'memory_pick:🍇')
    ],
    [
      Markup.button.callback('🍉', 'memory_pick:🍉'),
      Markup.button.callback('🍒', 'memory_pick:🍒'),
      Markup.button.callback('🥝', 'memory_pick:🥝')
    ],
    [
      Markup.button.callback('🍋', 'memory_pick:🍋'),
      Markup.button.callback('🥭', 'memory_pick:🥭'),
      Markup.button.callback('🍓', 'memory_pick:🍓')
    ],
    [
      Markup.button.callback('🍑', 'memory_pick:🍑')
    ]
  ]);
}

bot.action(/^memory_pick:(.+)$/, async (ctx) => {
  await ctx.answerCbQuery();

  const user = getUser(ctx.from.id);

  if (user.state !== 'memory') return;

  user.data.answer.push(ctx.match[1]);

  const answer = user.data.answer;
  const sequence = user.data.sequence;

  const index = answer.length - 1;

  if (answer[index] !== sequence[index]) {
    clearUserState(ctx.from.id);

    await ctx.editMessageText(
      `🧠 انتهت اللعبة

❌ خطأ!

الترتيب الصحيح:
${sequence.join('  ')}`,
      backButton()
    );

    return;
  }

  if (answer.length === sequence.length) {
    clearUserState(ctx.from.id);

    await ctx.editMessageText(
      `🧠 ممتاز! 🎉

✅ تذكرت الترتيب كاملًا.`,
      backButton()
    );

    return;
  }

  await ctx.editMessageText(
    `🧠 الذاكرة

التقدم:
${answer.join('  ')}

اختر الرمز التالي:`,
    memoryKeyboard()
  );
});

/* =========================================================
   GUESS NUMBER
   ========================================================= */

bot.action('game_guess', async (ctx) => {
  await ctx.answerCbQuery();

  const user = getUser(ctx.from.id);

  user.state = 'guess';
  user.data = {
    number: Math.floor(Math.random() * 100) + 1,
    attempts: 0
  };

  await ctx.editMessageText(
    `🔢 تخمين الرقم

أنا اخترت رقمًا من 1 إلى 100.

أرسل تخمينك في رسالة.`
  );
});

bot.on('text', async (ctx, next) => {
  const user = getUser(ctx.from.id);

  if (user.state !== 'guess') {
    return next();
  }

  const value = Number(ctx.message.text);

  if (!Number.isInteger(value) || value < 1 || value > 100) {
    await ctx.reply('❌ أرسل رقمًا صحيحًا من 1 إلى 100.');
    return;
  }

  user.data.attempts++;

  if (value === user.data.number) {
    const attempts = user.data.attempts;

    clearUserState(ctx.from.id);

    await ctx.reply(
      `🎉 صحيح!

الرقم هو: ${value}
عدد المحاولات: ${attempts}`,
      backButton()
    );

    return;
  }

  if (value < user.data.number) {
    await ctx.reply('⬆️ الرقم أكبر.');
  } else {
    await ctx.reply('⬇️ الرقم أصغر.');
  }
});

/* =========================================================
   FASTEST ANSWER
   ========================================================= */

const fastQuestions = [
  {
    q: 'كم يساوي 5 + 7؟',
    answers: ['12']
  },
  {
    q: 'ما عاصمة فرنسا؟',
    answers: ['باريس']
  },
  {
    q: 'كم عدد أيام الأسبوع؟',
    answers: ['7', 'سبعة']
  },
  {
    q: 'كم يساوي 10 × 2؟',
    answers: ['20', 'عشرين']
  },
  {
    q: 'ما لون السماء غالبًا في النهار؟',
    answers: ['أزرق']
  }
];

const activeFast = new Map();

bot.action('game_fast', async (ctx) => {
  await ctx.answerCbQuery();

  const chatId = ctx.chat.id;

  const question =
    fastQuestions[
      Math.floor(Math.random() * fastQuestions.length)
    ];

  activeFast.set(chatId, {
    question,
    winner: null
  });

  await ctx.editMessageText(
    `⚡ أسرع إجابة

السؤال:

${question.q}

🏃 أول شخص يرسل الإجابة الصحيحة يفوز!`
  );
});

bot.on('text', async (ctx, next) => {
  const chatId = ctx.chat.id;

  const game = activeFast.get(chatId);

  if (!game || game.winner) {
    return next();
  }

  const answer =
    ctx.message.text.trim().toLowerCase();

  const correct = game.question.answers.some(
    x => x.toLowerCase() === answer
  );

  if (!correct) return;

  game.winner = ctx.from.id;

  activeFast.delete(chatId);

  await ctx.reply(
    `⚡🏆 فاز ${ctx.from.first_name}!

الإجابة الصحيحة:
${game.question.answers[0]}`,
    backButton()
  );
});

/* =========================================================
   CANCEL
   ========================================================= */

bot.action(/^game_cancel:(.+)$/, async (ctx) => {
  await ctx.answerCbQuery();

  const gameId = ctx.match[1];
  const game = games.get(gameId);

  if (game) {
    games.delete(gameId);
  }

  await ctx.editMessageText(
    '❌ تم إلغاء اللعبة.',
    backButton()
  );
});

/* =========================================================
   ERROR HANDLING
   ========================================================= */

bot.catch((err) => {
  console.error('BOT ERROR:', err);
});

/* =========================================================
   RENDER HTTP SERVER
   ========================================================= */

const PORT = process.env.PORT || 3000;

http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, {
      'Content-Type': 'text/plain'
    });

    res.end('OK');
    return;
  }

  res.writeHead(200, {
    'Content-Type': 'text/plain'
  });

  res.end('Experiences Games Bot');
}).listen(PORT, () => {
  console.log(`HTTP server running on port ${PORT}`);
});

/* =========================================================
   START BOT
   ========================================================= */

bot.launch({
  dropPendingUpdates: true
});

console.log('🎮 Experiences Games Bot started');

/* Graceful shutdown */

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
