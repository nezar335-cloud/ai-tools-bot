
const { Telegraf, Markup } = require("telegraf");

const TOKEN = process.env.BOT_TOKEN;
if (!TOKEN) throw new Error("BOT_TOKEN is missing");

const bot = new Telegraf(TOKEN);
const sessions = new Map();

const menu = () => Markup.keyboard([
  ["❌⭕ X و O", "✊ حجر ورق مقص"],
  ["🔴 أربعة في صف", "🎲 النرد"],
  ["🔢 تخمين الرقم", "🧠 الذاكرة"],
  ["🧠 أسئلة عامة", "⚡ أسرع إجابة"],
  ["🔤 ترتيب الحروف", "🧩 لغز الكلمة"],
  ["🚢 معركة السفن", "🪙 العملة"],
  ["🧮 تحدي الحساب", "🃏 الأزواج"],
  ["🎯 خمن الأقرب", "🎰 الصناديق"],
  ["🔥 صح أو خطأ", "🏹 ضربة الحظ"],
  ["🐍 الثعبان", "🏆 مسابقة 5 أسئلة"]
]).resize();

const key = id => String(id);
const set = (uid, game, data = {}) => sessions.set(key(uid), { game, ...data });
const get = uid => sessions.get(key(uid));
const clear = uid => sessions.delete(key(uid));

bot.start(ctx => ctx.reply("🎮 Experiences\n\nاختر لعبة:", menu()));

bot.hears("🎮 الألعاب", ctx => ctx.reply("🎮 اختر لعبة:", menu()));

/* ---------- generic helpers ---------- */

function inlineBack() {
  return Markup.inlineKeyboard([
    [Markup.button.callback("🔄 مرة أخرى", "again_menu")]
  ]);
}

bot.action("again_menu", async ctx => {
  await ctx.answerCbQuery();
  await ctx.reply("🎮 اختر لعبة:", menu());
});

/* ---------- X O ---------- */

function xoWinner(b) {
  const lines=[[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
  for (const [a,c,d] of lines) if (b[a] && b[a]===b[c] && b[a]===b[d]) return b[a];
  return b.every(Boolean) ? "draw" : null;
}
function minimax(b,max) {
  const r=xoWinner(b);
  if(r==="O")return 10;if(r==="X")return -10;if(r==="draw")return 0;
  let best=max?-Infinity:Infinity;
  for(let i=0;i<9;i++)if(!b[i]){
    b[i]=max?"O":"X";const s=minimax(b,!max);b[i]="";
    best=max?Math.max(best,s):Math.min(best,s);
  }
  return best;
}
function aiXO(b){
  let best=-Infinity,move=0;
  for(let i=0;i<9;i++)if(!b[i]){
    b[i]="O";const s=minimax(b,false);b[i]="";
    if(s>best){best=s;move=i;}
  }
  return move;
}
function xoKb(id,b){
  const rows=[];
  for(let r=0;r<3;r++)rows.push([0,1,2].map(c=>{
    const i=r*3+c;
    return Markup.button.callback(b[i]||"⬜",`xo:${id}:${i}`);
  }));
  rows.push([Markup.button.callback("🔄",`xonew:${id}`),Markup.button.callback("❌","xostop")]);
  return Markup.inlineKeyboard(rows);
}
function xoMsg(g){
  let s="❌⭕ X و O\n\n";
  for(let r=0;r<3;r++)s+=g.b.slice(r*3,r*3+3).map(x=>x||"⬜").join(" ")+"\n";
  if(g.done)s+="\n"+(g.w==="draw"?"🤝 تعادل!":`🏆 الفائز: ${g.w}`);
  else s+=g.turn==="X"?"\n🎯 دورك":"\n🤖 دور الذكاء الاصطناعي";
  return s;
}
bot.hears("❌⭕ X و O",async ctx=>{
  const id=Date.now().toString(36);set(ctx.from.id,"xo",{id,b:Array(9).fill(""),turn:"X",done:false,w:null});
  const g=get(ctx.from.id);
  await ctx.reply(xoMsg(g),xoKb(id,g.b));
});
bot.action(/^xo:([^:]+):([0-8])$/,async ctx=>{
  const g=get(ctx.from.id);const n=+ctx.match[2];
  if(!g||g.game!=="xo"||g.id!==ctx.match[1])return ctx.answerCbQuery("❌ اللعبة انتهت.");
  if(g.done||g.b[n]||g.turn!=="X")return ctx.answerCbQuery("⏳ انتظر دورك.");
  g.b[n]="X";let r=xoWinner(g.b);
  if(!r){g.turn="O";g.b[aiXO(g.b)]="O";r=xoWinner(g.b);if(!r)g.turn="X";}
  if(r){g.done=true;g.w=r;}
  await ctx.answerCbQuery();await ctx.editMessageText(xoMsg(g),xoKb(g.id,g.b));
});
bot.action(/^xonew:(.+)$/,async ctx=>{
  const g=get(ctx.from.id);if(!g)return ctx.answerCbQuery();
  g.b=Array(9).fill("");g.turn="X";g.done=false;g.w=null;
  await ctx.answerCbQuery("🔄");await ctx.editMessageText(xoMsg(g),xoKb(g.id,g.b));
});
bot.action("xostop",async ctx=>{clear(ctx.from.id);await ctx.answerCbQuery("تم الإنهاء.");});

/* ---------- Rock Paper Scissors ---------- */

const R={rock:"✊",paper:"✋",scissors:"✌️"};
function rps(a,b){if(a===b)return"draw";return(a==="rock"&&b==="scissors")||(a==="paper"&&b==="rock")||(a==="scissors"&&b==="paper")?"win":"lose";}
bot.hears("✊ حجر ورق مقص",async ctx=>{
  const id=Date.now().toString(36);set(ctx.from.id,"rps",{id});
  await ctx.reply("✊ اختر:",Markup.inlineKeyboard([
    [Markup.button.callback("✊ حجر",`rps:${id}:rock`),Markup.button.callback("✋ ورق",`rps:${id}:paper`),Markup.button.callback("✌️ مقص",`rps:${id}:scissors`)]
  ]));
});
bot.action(/^rps:([^:]+):(rock|paper|scissors)$/,async ctx=>{
  const g=get(ctx.from.id);if(!g||g.id!==ctx.match[1])return ctx.answerCbQuery("انتهت اللعبة.");
  const p=ctx.match[2], a=["rock","paper","scissors"][Math.floor(Math.random()*3)], z=rps(p,a);
  clear(ctx.from.id);await ctx.answerCbQuery();
  await ctx.editMessageText(`✊ حجر ورق مقص\n\nأنت: ${R[p]}\nAI: ${R[a]}\n\n${z==="win"?"🏆 فزت!":z==="lose"?"🤖 خسرت!":"🤝 تعادل!"}`,inlineBack());
});

/* ---------- Four in a Row ---------- */

function cboard(){return Array.from({length:6},()=>Array(7).fill(""))}
function cwin(b,p){const ds=[[0,1],[1,0],[1,1],[1,-1]];for(let r=0;r<6;r++)for(let c=0;c<7;c++)if(b[r][c]===p)for(const[d,e]of ds){let n=1;for(let k=1;k<4;k++){let x=r+d*k,y=c+e*k;if(x<0||x>=6||y<0||y>=7||b[x][y]!==p)break;n++}if(n>=4)return true}return false}
function ctext(g){let s="🔴 أربعة في صف\n\n";g.b.forEach(r=>s+=r.map(x=>x||"⚪").join("")+"\n");return s+`\n${g.done?(g.w==="draw"?"🤝 تعادل!":`🏆 الفائز ${g.w==="R"?"🔴":"🟡"}`):g.turn==="R"?"🔴 دورك":"🟡 دورك"}`}
function ckb(g){return Markup.inlineKeyboard([
  Array.from({length:7},(_,i)=>Markup.button.callback(String(i+1),`c4:${g.id}:${i}`)),
  [Markup.button.callback("🔄",`c4new:${g.id}`)]
])}
bot.hears("🔴 أربعة في صف",async ctx=>{
  const id=Date.now().toString(36),g={id,b:cboard(),turn:"R",done:false,w:null};set(ctx.from.id,"c4",g);
  await ctx.reply(ctext(g),ckb(g));
});
bot.action(/^c4:([^:]+):([0-6])$/,async ctx=>{
  const g=get(ctx.from.id),col=+ctx.match[2];if(!g||g.id!==ctx.match[1])return ctx.answerCbQuery("انتهت.");
  if(g.done)return ctx.answerCbQuery("انتهت.");
  let row=-1;for(let r=5;r>=0;r--)if(!g.b[r][col]){row=r;break}
  if(row<0)return ctx.answerCbQuery("العمود ممتلئ.");
  const p=g.turn;g.b[row][col]=p;
  if(cwin(g.b,p)){g.done=true;g.w=p}else if(g.b[0].every(Boolean)){g.done=true;g.w="draw"}else g.turn=p==="R"?"Y":"R";
  await ctx.answerCbQuery();await ctx.editMessageText(ctext(g),ckb(g));
});
bot.action(/^c4new:(.+)$/,async ctx=>{const g=get(ctx.from.id);if(!g)return ctx.answerCbQuery();g.b=cboard();g.turn="R";g.done=false;g.w=null;await ctx.answerCbQuery("🔄");await ctx.editMessageText(ctext(g),ckb(g));});

/* ---------- Dice ---------- */

bot.hears("🎲 النرد",async ctx=>{
  const a=Math.floor(Math.random()*6)+1,b=Math.floor(Math.random()*6)+1;
  await ctx.reply(`🎲 النرد\n\nأنت: ${a}\nالذكاء الاصطناعي: ${b}\n\n${a>b?"🏆 فزت!":a<b?"🤖 فاز AI":"🤝 تعادل!"}`,inlineBack());
});

/* ---------- Guess Number ---------- */

bot.hears("🔢 تخمين الرقم",async ctx=>{
  set(ctx.from.id,"guess",{secret:Math.floor(Math.random()*100)+1,n:0});
  await ctx.reply("🔢 اخترت رقمًا من 1 إلى 100.\nأرسل تخمينك.");
});

/* ---------- Memory ---------- */

bot.hears("🧠 الذاكرة",async ctx=>{
  const all=["🍎","🍌","🍇","🍉","🍒","🥝","🍋","🥭","🍓","🍑"];
  const seq=Array.from({length:5},()=>all[Math.floor(Math.random()*all.length)]);
  set(ctx.from.id,"memory",{seq,pos:0});
  await ctx.reply(`🧠 احفظ الترتيب:\n\n${seq.join("  ")}\n\nسأخفيه بعد 3 ثوانٍ...`);
  setTimeout(async()=>{
    const g=get(ctx.from.id);if(!g||g.game!=="memory")return;
    await ctx.reply("الآن اختر الرموز بالترتيب:",Markup.inlineKeyboard(all.map(x=>[Markup.button.callback(x,`mem:${x}`)])));
  },3000);
});
bot.action(/^mem:(.+)$/,async ctx=>{
  const g=get(ctx.from.id);if(!g||g.game!=="memory")return ctx.answerCbQuery();
  const x=ctx.match[1];
  if(x!==g.seq[g.pos]){clear(ctx.from.id);return ctx.answerCbQuery("❌ خطأ!",{show_alert:true});}
  g.pos++;
  if(g.pos===g.seq.length){clear(ctx.from.id);await ctx.answerCbQuery("🏆 ممتاز!");await ctx.reply("🧠 تذكرت الترتيب كاملًا!");return}
  await ctx.answerCbQuery("✅ صحيح");
});

/* ---------- General Quiz ---------- */

const quiz=[
 ["ما عاصمة اليمن؟",["صنعاء","عدن","تعز"],0],
 ["كم عدد أيام الأسبوع؟",["5","7","10"],1],
 ["ما الكوكب المعروف بالكوكب الأحمر؟",["المريخ","الزهرة","المشتري"],0],
 ["كم يساوي 5 + 7؟",["10","12","14"],1],
 ["ما أكبر محيط؟",["الأطلسي","الهندي","الهادئ"],2]
];
bot.hears("🧠 أسئلة عامة",async ctx=>{
  const q=quiz[Math.floor(Math.random()*quiz.length)],id=Date.now().toString(36);
  set(ctx.from.id,"quiz",{id,q});
  await ctx.reply(`🧠 ${q[0]}`,Markup.inlineKeyboard(q[1].map((x,i)=>[Markup.button.callback(x,`quiz:${id}:${i}`)])));
});
bot.action(/^quiz:([^:]+):(\d)$/,async ctx=>{
  const g=get(ctx.from.id),i=+ctx.match[2];if(!g||g.id!==ctx.match[1])return ctx.answerCbQuery("انتهى.");
  clear(ctx.from.id);await ctx.answerCbQuery(i===g.q[2]?"✅ صحيح!":"❌ خطأ!",{show_alert:true});
});

/* ---------- Fast Answer ---------- */

const fast=[
 ["كم يساوي 10 + 5؟","15"],["ما عاصمة فرنسا؟","باريس"],["كم عدد أيام الأسبوع؟","7"],["كم يساوي 3 × 4؟","12"]
];
bot.hears("⚡ أسرع إجابة",async ctx=>{
  const q=fast[Math.floor(Math.random()*fast.length)];
  set(ctx.from.id,"fast",{q});
  await ctx.reply(`⚡ أسرع إجابة\n\n${q[0]}\n\nأرسل الإجابة.`);
});

/* ---------- Scramble ---------- */

const words=["مدرسة","سيارة","كمبيوتر","تفاحة","كتاب","هاتف","شمس","قمر"];
function shuffle(s){return s.split("").sort(()=>Math.random()-.5).join("")}
bot.hears("🔤 ترتيب الحروف",async ctx=>{
  const w=words[Math.floor(Math.random()*words.length)],scr=shuffle(w);
  set(ctx.from.id,"scramble",{w});
  await ctx.reply(`🔤 رتب الحروف:\n\n${scr}\n\nأرسل الكلمة الصحيحة.`);
});

/* ---------- Word Riddle ---------- */

const riddles=[
 ["له أسنان ولا يعض؟","مشط"],
 ["شيء يمشي بلا رجلين ويبكي بلا عينين؟","سحاب"],
 ["له أوراق وليس نباتًا؟","كتاب"]
];
bot.hears("🧩 لغز الكلمة",async ctx=>{
  const r=riddles[Math.floor(Math.random()*riddles.length)];
  set(ctx.from.id,"riddle",{answer:r[1]});
  await ctx.reply(`🧩 ${r[0]}\n\nأرسل الإجابة.`);
});

/* ---------- Coin ---------- */

bot.hears("🪙 العملة",async ctx=>{
  const x=Math.random()<.5?"وجه 🟡":"كتابة ⚪";
  await ctx.reply(`🪙 النتيجة: ${x}`,inlineBack());
});

/* ---------- Math ---------- */

bot.hears("🧮 تحدي الحساب",async ctx=>{
  const a=Math.floor(Math.random()*20)+1,b=Math.floor(Math.random()*20)+1;
  set(ctx.from.id,"math",{answer:a+b});
  await ctx.reply(`🧮 احسب بسرعة:\n\n${a} + ${b} = ؟`);
});

/* ---------- Closest Guess ---------- */

bot.hears("🎯 خمن الأقرب",async ctx=>{
  const n=Math.floor(Math.random()*100)+1;
  set(ctx.from.id,"closest",{n});
  await ctx.reply("🎯 اخترت رقمًا من 1 إلى 100.\nأرسل تخمينك.");
});

/* ---------- Boxes ---------- */

bot.hears("🎰 الصناديق",async ctx=>{
  const prize=Math.floor(Math.random()*3);
  await ctx.reply("🎰 اختر صندوقًا:",Markup.inlineKeyboard([
    [0,1,2].map(i=>Markup.button.callback(`📦 ${i+1}`,`box:${i}:${prize}`))
  ]));
});
bot.action(/^box:(\d):(\d)$/,async ctx=>{
  const a=+ctx.match[1],p=+ctx.match[2];
  await ctx.answerCbQuery(a===p?"🎉 وجدت الصندوق!":"❌ الصندوق فارغ.",{show_alert:true});
});

/* ---------- True / False ---------- */

const tf=[
 ["الشمس نجم.","صح",true],
 ["الأرض أكبر من الشمس.","خطأ",false],
 ["الماء يتجمد عند 0 مئوية.","صح",true],
 ["عدد شهور السنة 10.","خطأ",false]
];
bot.hears("🔥 صح أو خطأ",async ctx=>{
  const q=tf[Math.floor(Math.random()*tf.length)],id=Date.now().toString(36);
  set(ctx.from.id,"tf",{id,q});
  await ctx.reply(`🔥 ${q[0]}`,Markup.inlineKeyboard([
    [Markup.button.callback("✅ صح",`tf:${id}:1`),Markup.button.callback("❌ خطأ",`tf:${id}:0`)]
  ]));
});
bot.action(/^tf:([^:]+):([01])$/,async ctx=>{
  const g=get(ctx.from.id),a=+ctx.match[2];if(!g||g.id!==ctx.match[1])return ctx.answerCbQuery();
  clear(ctx.from.id);await ctx.answerCbQuery(a===+g.q[2]?"✅ صحيح!":"❌ خطأ!",{show_alert:true});
});

/* ---------- Lucky Shot ---------- */

bot.hears("🏹 ضربة الحظ",async ctx=>{
  const target=Math.floor(Math.random()*5);
  await ctx.reply("🏹 اختر هدفًا:",Markup.inlineKeyboard([
    [0,1,2,3,4].map(i=>Markup.button.callback(`🎯 ${i+1}`,`shot:${i}:${target}`))
  ]));
});
bot.action(/^shot:(\d):(\d)$/,async ctx=>{
  const a=+ctx.match[1],t=+ctx.match[2];
  await ctx.answerCbQuery(a===t?"🎯 إصابة!":"🏹 أخطأت!",{show_alert:true});
});

/* ---------- Snake (turn-based mini version) ---------- */

bot.hears("🐍 الثعبان",async ctx=>{
  set(ctx.from.id,"snake",{score:0});
  await ctx.reply("🐍 الثعبان\n\nاضغط الاتجاهات لتحريك الثعبان وجمع الطعام.",Markup.inlineKeyboard([
    [Markup.button.callback("⬆️","sn:U")],
    [Markup.button.callback("⬅️","sn:L"),Markup.button.callback("🟢 طعام","sn:F"),Markup.button.callback("➡️","sn:R")],
    [Markup.button.callback("⬇️","sn:D")]
  ]));
});
bot.action(/^sn:(U|D|L|R|F)$/,async ctx=>{
  const g=get(ctx.from.id);if(!g)return ctx.answerCbQuery();
  if(ctx.match[1]==="F")g.score++;
  await ctx.answerCbQuery(ctx.match[1]==="F"?`🍎 +1\nالنقاط: ${g.score}`:`🐍 حركة\nالنقاط: ${g.score}`);
});

/* ---------- Battleships mini ---------- */

bot.hears("🚢 معركة السفن",async ctx=>{
  const ship=Math.floor(Math.random()*9);
  set(ctx.from.id,"ships",{ship});
  await ctx.reply("🚢 اختر خانة لإطلاق النار:",Markup.inlineKeyboard(
    Array.from({length:9},(_,i)=>Markup.button.callback(`🌊 ${i+1}`,`ship:${i}`))
  ));
});
bot.action(/^ship:(\d)$/,async ctx=>{
  const g=get(ctx.from.id);if(!g)return ctx.answerCbQuery();
  const n=+ctx.match[1];clear(ctx.from.id);
  await ctx.answerCbQuery(n===g.ship?"💥 أصبت السفينة!":"🌊 لم تصب.",{show_alert:true});
});

/* ---------- Pairs ---------- */

bot.hears("🃏 الأزواج",async ctx=>{
  const icons=["🍎","🍌","🍇","🍒"];
  const cards=[...icons,...icons].sort(()=>Math.random()-.5);
  const id=Date.now().toString(36);
  set(ctx.from.id,"pairs",{id,cards,open:[],matched:[]});
  await pairsRender(ctx);
});
async function pairsRender(ctx){
  const g=get(ctx.from.id);
  const rows=[];
  for(let r=0;r<2;r++){
    const row=[];
    for(let c=0;c<4;c++){
      const i=r*4+c;
      const visible=g.matched.includes(i)||g.open.includes(i);
      row.push(Markup.button.callback(visible?g.cards[i]:"❓",`pair:${g.id}:${i}`));
    }
    rows.push(row);
  }
  await ctx.reply("🃏 اكشف البطاقات وابحث عن الأزواج:",Markup.inlineKeyboard(rows));
}
bot.action(/^pair:([^:]+):([0-7])$/,async ctx=>{
  const g=get(ctx.from.id),i=+ctx.match[2];if(!g||g.id!==ctx.match[1])return ctx.answerCbQuery();
  if(g.matched.includes(i)||g.open.includes(i))return ctx.answerCbQuery();
  g.open.push(i);
  if(g.open.length===2){
    if(g.cards[g.open[0]]===g.cards[g.open[1]]){
      g.matched.push(...g.open);g.open=[];
      await ctx.answerCbQuery("✅ زوج!");
    }else{
      await ctx.answerCbQuery("❌ ليسا متطابقين");
      setTimeout(()=>{const x=get(ctx.from.id);if(x&&x.game==="pairs"){x.open=[]}},800);
    }
  }
  await pairsRender(ctx);
});

/* ---------- 5 Question Championship ---------- */

bot.hears("🏆 مسابقة 5 أسئلة",async ctx=>{
  set(ctx.from.id,"champ",{i:0,score:0});
  await champNext(ctx);
});
async function champNext(ctx){
  const g=get(ctx.from.id);
  if(g.i>=5){clear(ctx.from.id);return ctx.reply(`🏆 انتهت المسابقة!\n\nنتيجتك: ${g.score}/5`,inlineBack())}
  const q=quiz[g.i%quiz.length],id=Date.now().toString(36);
  g.q=q;g.id=id;
  await ctx.reply(`🏆 السؤال ${g.i+1}/5\n\n${q[0]}`,Markup.inlineKeyboard(q[1].map((x,i)=>[Markup.button.callback(x,`ch:${id}:${i}`)])));
}
bot.action(/^ch:([^:]+):(\d)$/,async ctx=>{
  const g=get(ctx.from.id),i=+ctx.match[2];if(!g||g.id!==ctx.match[1])return ctx.answerCbQuery();
  if(i===g.q[2])g.score++;g.i++;
  await ctx.answerCbQuery(i===g.q[2]?"✅":"❌");
  await champNext(ctx);
});

/* ---------- Text game router ---------- */

bot.on("text",async ctx=>{
  const uid=ctx.from.id, text=ctx.message.text.trim(),g=get(uid);
  if(!g)return;

  if(g.game==="guess"){
    const n=Number(text);
    if(!Number.isInteger(n)||n<1||n>100)return ctx.reply("أرسل رقمًا من 1 إلى 100.");
    g.n++;
    if(n===g.secret){clear(uid);return ctx.reply(`🏆 صحيح! الرقم ${n} بعد ${g.n} محاولة.`);}
    return ctx.reply(n<g.secret?"⬆️ أكبر":"⬇️ أصغر");
  }
  if(g.game==="fast"){
    if(text.toLowerCase()===g.q[1].toLowerCase()){clear(uid);return ctx.reply("⚡🏆 إجابة صحيحة!");}
    return ctx.reply("❌ ليست الإجابة الصحيحة.");
  }
  if(g.game==="scramble"){
    if(text===g.w){clear(uid);return ctx.reply("🔤🏆 صحيح!");}
    return ctx.reply("❌ حاول مرة أخرى.");
  }
  if(g.game==="riddle"){
    if(text===g.answer){clear(uid);return ctx.reply("🧩🏆 صحيح!");}
    return ctx.reply("❌ حاول مرة أخرى.");
  }
  if(g.game==="math"){
    if(Number(text)===g.answer){clear(uid);return ctx.reply("🧮🏆 صحيح!");}
    return ctx.reply("❌ خطأ، حاول مرة أخرى.");
  }
  if(g.game==="closest"){
    const n=Number(text);
    if(Number.isInteger(n)){clear(uid);return ctx.reply(`🎯 رقم الهدف كان ${g.n}.\nتخمينك: ${n}\nالفارق: ${Math.abs(n-g.n)}`);}
  }
});

/* ---------- Word / riddle / math menu handlers ---------- */

bot.hears("🔤 ترتيب الحروف",async ctx=>{
  const w=["مدرسة","سيارة","كتاب","هاتف","تفاحة"][Math.floor(Math.random()*5)];
  set(ctx.from.id,"scramble",{w});
  await ctx.reply(`🔤 رتب الحروف:\n\n${shuffle(w)}\n\nأرسل الكلمة.`);
});
bot.hears("🧩 لغز الكلمة",async ctx=>{
  const a=[["له أسنان ولا يعض؟","مشط"],["له أوراق وليس نباتًا؟","كتاب"],["شيء نراه ولا نمسكه؟","الظل"]][Math.floor(Math.random()*3)];
  set(ctx.from.id,"riddle",{answer:a[1]});await ctx.reply(`🧩 ${a[0]}\n\nأرسل الإجابة.`);
});
bot.hears("🧮 تحدي الحساب",async ctx=>{
  const a=Math.floor(Math.random()*20)+1,b=Math.floor(Math.random()*20)+1;
  set(ctx.from.id,"math",{answer:a+b});await ctx.reply(`🧮 ${a} + ${b} = ؟`);
});
bot.hears("🎯 خمن الأقرب",async ctx=>{
  const n=Math.floor(Math.random()*100)+1;set(ctx.from.id,"closest",{n});
  await ctx.reply("🎯 خمن رقمًا من 1 إلى 100.");
});
bot.hears("⚡ أسرع إجابة",async ctx=>{
  const q=fast[Math.floor(Math.random()*fast.length)];set(ctx.from.id,"fast",{q});
  await ctx.reply(`⚡ ${q[0]}`);
});

/* ---------- safety ---------- */

bot.catch(err=>console.error("BOT ERROR:",err?.stack||err));
bot.launch().then(()=>console.log("Experiences games bot running")).catch(err=>{console.error(err);process.exit(1)});
process.once("SIGINT",()=>bot.stop("SIGINT"));
process.once("SIGTERM",()=>bot.stop("SIGTERM"));

function shuffle(s){return s.split("").sort(()=>Math.random()-.5).join("")}
