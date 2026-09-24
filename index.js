const { Telegraf, Markup } = require("telegraf");
const BOT_TOKEN = String(process.env.BOT_TOKEN || "").trim();
if (!BOT_TOKEN) throw new Error("BOT_TOKEN is missing");
const bot = new Telegraf(BOT_TOKEN);
const sessions = new Map();

const MAIN = Markup.keyboard([
  ["🎮 الألعاب"],
  ["🎯 X و O", "✊ حجر ورق مقص"],
  ["🔢 خمن الرقم", "🧠 اختبار سريع"],
  ["🔤 ترتيب الكلمة", "➕ تحدي الحساب"],
  ["🎲 النرد", "🪙 عملة"],
  ["🟢 أربعة في صف", "⭕ الذاكرة"],
  ["🎯 الأقرب يفوز", "❓ صح أو خطأ"]
]).resize();

const BACK = Markup.inlineKeyboard([[Markup.button.callback("⬅️ القائمة","menu")]]);
const uid = ctx => String(ctx.from.id);
const setS = (ctx,v) => sessions.set(uid(ctx),v);
const getS = ctx => sessions.get(uid(ctx));
const clearS = ctx => sessions.delete(uid(ctx));
const shuffle = a => { const x=[...a]; for(let i=x.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[x[i],x[j]]=[x[j],x[i]];} return x; };
async function editOrReply(ctx,text,extra){ try{return await ctx.editMessageText(text,extra)}catch{return await ctx.reply(text,extra)} }
async function menu(ctx){ clearS(ctx); if(ctx.callbackQuery) await ctx.answerCbQuery().catch(()=>{}); await ctx.reply("🎮 اختر لعبة:",MAIN); }

bot.start(async ctx=>{clearS(ctx);await ctx.reply("🎮 أهلاً بك!\n\nهذا بوت ألعاب فقط.\nاختر لعبة من القائمة 👇",MAIN)});
bot.hears("🎮 الألعاب",menu);

/* X/O */
const wins=[[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
function xoWin(b){for(const [a,c,d] of wins)if(b[a]&&b[a]===b[c]&&b[a]===b[d])return b[a];return b.every(Boolean)?"draw":null}
function xoKb(g){const rows=[];for(let r=0;r<3;r++){const row=[];for(let c=0;c<3;c++){const i=r*3+c;row.push(Markup.button.callback(g.b[i]||"⬜",g.b[i]?"noop":`xo:${i}`))}rows.push(row)}rows.push([Markup.button.callback("🔄 جديد","xo:new"),Markup.button.callback("⬅️ القائمة","menu")]);return Markup.inlineKeyboard(rows)}
function minimax(b,max){const w=xoWin(b);if(w==="O")return 10;if(w==="X")return -10;if(w==="draw")return 0;const v=[];for(let i=0;i<9;i++)if(!b[i]){b[i]=max?"O":"X";v.push(minimax(b,!max));b[i]=""}return max?Math.max(...v):Math.min(...v)}
function aiMove(b){let best=-Infinity,m=-1;for(let i=0;i<9;i++)if(!b[i]){b[i]="O";const s=minimax(b,false);b[i]="";if(s>best){best=s;m=i}}return m}
async function startXO(ctx){setS(ctx,{type:"xo",b:Array(9).fill(""),over:false});await ctx.reply("🎯 X و O\n\nأنت ❌ وأنا ⭕\nابدأ:",xoKb(getS(ctx)))}
bot.hears("🎯 X و O",startXO);
bot.action(/^xo:(\d)$/,async ctx=>{await ctx.answerCbQuery().catch(()=>{});const g=getS(ctx);if(!g||g.type!=="xo"||g.over)return;const i=+ctx.match[1];if(g.b[i])return;g.b[i]="X";let w=xoWin(g.b);if(w){g.over=true;return editOrReply(ctx,w==="draw"?"🤝 تعادل!":"🏆 فزت أنت! 🎉",xoKb(g))}const m=aiMove(g.b);if(m>=0)g.b[m]="O";w=xoWin(g.b);if(w){g.over=true;return editOrReply(ctx,w==="draw"?"🤝 تعادل!":"🤖 فاز الكمبيوتر.",xoKb(g))}return editOrReply(ctx,"🎯 دورك — ❌",xoKb(g))});
bot.action("xo:new",async ctx=>{await ctx.answerCbQuery().catch(()=>{});await startXO(ctx)});

/* RPS */
const RPS=["✊ حجر","📄 ورق","✂️ مقص"];
function rpsKb(){return Markup.inlineKeyboard([RPS.map((x,i)=>Markup.button.callback(x,`rps:${i}`)),[Markup.button.callback("⬅️ القائمة","menu")]])}
bot.hears("✊ حجر ورق مقص",async ctx=>{setS(ctx,{type:"rps"});await ctx.reply("✊ حجر ورق مقص\nاختر:",rpsKb())});
bot.action(/^rps:(\d)$/,async ctx=>{await ctx.answerCbQuery().catch(()=>{});const g=getS(ctx);if(!g||g.type!=="rps")return;const me=RPS[+ctx.match[1]],ai=RPS[Math.floor(Math.random()*3)];const win=(me===ai)?"🤝 تعادل":((me.startsWith("✊")&&ai.startsWith("✂️"))||(me.startsWith("📄")&&ai.startsWith("✊"))||(me.startsWith("✂️")&&ai.startsWith("📄"))?"🏆 فزت!":"🤖 الكمبيوتر فاز");await ctx.reply(`${me}\n🤖 الكمبيوتر: ${ai}\n\n${win}`,rpsKb())});

/* Guess */
bot.hears("🔢 خمن الرقم",async ctx=>{setS(ctx,{type:"guess",n:Math.floor(Math.random()*100)+1,tries:0});await ctx.reply("🔢 خمن رقمًا من 1 إلى 100.\nاكتب الرقم:")});

/* Quiz */
const quiz=[["ما عاصمة اليمن؟",["صنعاء","عدن","تعز"],0],["كم عدد أيام الأسبوع؟",["5","7","10"],1],["ما الكوكب المعروف بالكوكب الأحمر؟",["المريخ","الزهرة","عطارد"],0],["2 + 8 = ؟",["9","10","12"],1],["كم شهرًا في السنة؟",["10","12","14"],1]];
function quizKb(q){return Markup.inlineKeyboard(q[1].map((x,i)=>[Markup.button.callback(x,`quiz:${i}`)]).concat([[Markup.button.callback("⬅️ القائمة","menu")]]))}
async function sendQuiz(ctx){const g=getS(ctx);if(!g||g.i>=g.q.length)return;const q=g.q[g.i];await ctx.reply(`🧠 السؤال ${g.i+1}/${g.q.length}\n\n${q[0]}`,quizKb(q))}
bot.hears("🧠 اختبار سريع",async ctx=>{setS(ctx,{type:"quiz",q:shuffle(quiz),i:0,score:0});await sendQuiz(ctx)});
bot.action(/^quiz:(\d)$/,async ctx=>{await ctx.answerCbQuery().catch(()=>{});const g=getS(ctx);if(!g||g.type!=="quiz")return;const q=g.q[g.i];if(+ctx.match[1]===q[2])g.score++;g.i++;if(g.i>=g.q.length){clearS(ctx);return ctx.reply(`🏁 انتهى الاختبار!\n\nنتيجتك: ${g.score}/${g.q.length}`,BACK)}await sendQuiz(ctx)});

/* Scramble + Math */
const words=["مدرسة","حاسوب","مكتبة","سيارة","برتقال","هاتف","مطر"];
bot.hears("🔤 ترتيب الكلمة",async ctx=>{const word=words[Math.floor(Math.random()*words.length)];setS(ctx,{type:"scramble",word});await ctx.reply(`🔤 رتب الحروف:\n\n${shuffle([...word]).join(" ")}\n\nاكتب الكلمة:`)});
bot.hears("➕ تحدي الحساب",async ctx=>{const a=Math.floor(Math.random()*20)+1,b=Math.floor(Math.random()*20)+1;setS(ctx,{type:"math",ans:a+b});await ctx.reply(`➕ احسب:\n\n${a} + ${b} = ؟\n\nاكتب الإجابة:`)});

/* Dice/Coin */
bot.hears("🎲 النرد",ctx=>ctx.reply(`🎲 النتيجة: ${Math.floor(Math.random()*6)+1}`,BACK));
bot.hears("🪙 عملة",ctx=>ctx.reply(`🪙 النتيجة: ${Math.random()<.5?"وجه":"كتابة"}`,BACK));

/* Connect Four */
const R=6,C=7;
function c4win(b){for(let r=0;r<R;r++)for(let c=0;c<C;c++){const p=b[r][c];if(!p)continue;for(const [dr,dc] of [[0,1],[1,0],[1,1],[1,-1]]){let n=1;for(let k=1;k<4;k++){const rr=r+dr*k,cc=c+dc*k;if(rr>=0&&rr<R&&cc>=0&&cc<C&&b[rr][cc]===p)n++;else break}if(n>=4)return p}}return b.every(x=>x.every(Boolean))?"draw":null}
function c4Text(g){return "🟢 أربعة في صف\n\n"+g.b.map(x=>x.map(v=>v||"⚪").join(" ")).join("\n")+`\n\nالدور: ${g.t}`}
function c4Kb(){return Markup.inlineKeyboard([Array.from({length:C},(_,c)=>Markup.button.callback(String(c+1),`c4:${c}`)),[Markup.button.callback("🔄 جديد","c4:new"),Markup.button.callback("⬅️ القائمة","menu")]])}
async function startC4(ctx){setS(ctx,{type:"c4",b:Array.from({length:R},()=>Array(C).fill("")),t:"🔴",over:false});await ctx.reply(c4Text(getS(ctx)),c4Kb())}
bot.hears("🟢 أربعة في صف",startC4);
bot.action(/^c4:(\d)$/,async ctx=>{await ctx.answerCbQuery().catch(()=>{});const g=getS(ctx);if(!g||g.type!=="c4"||g.over)return;const c=+ctx.match[1];let r=-1;for(let i=R-1;i>=0;i--)if(!g.b[i][c]){r=i;break}if(r<0)return;g.b[r][c]=g.t;const w=c4win(g.b);if(w){g.over=true;return editOrReply(ctx,w==="draw"?"🤝 تعادل!":`🏆 الفائز ${w}`,c4Kb())}g.t=g.t==="🔴"?"🟡":"🔴";await editOrReply(ctx,c4Text(g),c4Kb())});
bot.action("c4:new",async ctx=>{await ctx.answerCbQuery().catch(()=>{});await startC4(ctx)});

/* Memory */
function memKb(g){const rows=[];for(let r=0;r<4;r++){const row=[];for(let c=0;c<4;c++){const i=r*4+c,show=g.open.includes(i)||g.hit.includes(i);row.push(Markup.button.callback(show?g.cards[i]:"❓",show?"noop":`mem:${i}`))}rows.push(row)}rows.push([Markup.button.callback("🔄 جديد","mem:new"),Markup.button.callback("⬅️ القائمة","menu")]);return Markup.inlineKeyboard(rows)}
function memText(g){return `⭕ الذاكرة\n\nالأزواج: ${g.hit.length/2}/8`}
async function startMem(ctx){const cards=shuffle(["🍎","🍎","🍌","🍌","🍇","🍇","🍉","🍉","🥝","🥝","🍒","🍒","🥕","🥕","🌽","🌽"]);setS(ctx,{type:"mem",cards,open:[],hit:[],busy:false});await ctx.reply(memText(getS(ctx)),memKb(getS(ctx)))}
bot.hears("⭕ الذاكرة",startMem);
bot.action(/^mem:(\d+)$/,async ctx=>{await ctx.answerCbQuery().catch(()=>{});const g=getS(ctx);if(!g||g.type!=="mem"||g.busy)return;const i=+ctx.match[1];if(g.open.includes(i)||g.hit.includes(i))return;g.open.push(i);if(g.open.length===1)return editOrReply(ctx,memText(g),memKb(g));g.busy=true;await editOrReply(ctx,memText(g),memKb(g));const[a,b]=g.open;if(g.cards[a]===g.cards[b]){g.hit.push(a,b);g.open=[];g.busy=false;if(g.hit.length===16){clearS(ctx);return ctx.reply("🏆 ممتاز! وجدت كل الأزواج.",BACK)}return ctx.reply(memText(g),memKb(g))}setTimeout(async()=>{const cur=getS(ctx);if(cur!==g)return;cur.open=[];cur.busy=false;try{await ctx.reply(memText(cur),memKb(cur))}catch(e){console.error("MEMORY_ERROR",e.stack||e)}},800)});
bot.action("mem:new",async ctx=>{await ctx.answerCbQuery().catch(()=>{});await startMem(ctx)});

/* Closest + True/False */
bot.hears("🎯 الأقرب يفوز",async ctx=>{setS(ctx,{type:"closest",n:Math.floor(Math.random()*100)+1});await ctx.reply("🎯 اكتب رقمًا من 1 إلى 100:")});
const tf=[["الشمس نجم.",true],["عدد أيام الأسبوع 8.",false],["الماء يتجمد عند 0° مئوية في الظروف المعتادة.",true],["القمر أكبر من الأرض.",false],["اليمن تقع في قارة آسيا.",true]];
async function sendTF(ctx){const g=getS(ctx),q=g.q[g.i];await ctx.reply(`❓ ${q[0]}`,Markup.inlineKeyboard([[Markup.button.callback("صح","tf:1"),Markup.button.callback("خطأ","tf:0")],[Markup.button.callback("⬅️ القائمة","menu")]]))}
bot.hears("❓ صح أو خطأ",async ctx=>{setS(ctx,{type:"tf",q:shuffle(tf),i:0,s:0});await sendTF(ctx)});
bot.action(/^tf:(0|1)$/,async ctx=>{await ctx.answerCbQuery().catch(()=>{});const g=getS(ctx);if(!g||g.type!=="tf")return;if(Boolean(+ctx.match[1])===g.q[g.i][1])g.s++;g.i++;if(g.i>=g.q.length){clearS(ctx);return ctx.reply(`🏁 النتيجة: ${g.s}/${g.q.length}`,BACK)}await sendTF(ctx)});

/* Text games */
bot.on("text",async ctx=>{
  const g=getS(ctx); if(!g)return;
  const t=String(ctx.message.text||"").trim();
  if(g.type==="guess"){if(!/^\d+$/.test(t)){return ctx.reply("❌ اكتب رقمًا من 1 إلى 100.")}const n=+t;if(n<1||n>100)return ctx.reply("❌ اكتب رقمًا من 1 إلى 100.");g.tries++;if(n===g.n){clearS(ctx);return ctx.reply(`🏆 صحيح! الرقم هو ${g.n}\nالمحاولات: ${g.tries}`,BACK)}return ctx.reply(n<g.n?"⬆️ الرقم أكبر.":"⬇️ الرقم أصغر.")}
  if(g.type==="scramble"){if(t===g.word){clearS(ctx);return ctx.reply("🏆 صحيح!",BACK)}return ctx.reply("❌ حاول مرة أخرى.")}
  if(g.type==="math"){if(!/^-?\d+$/.test(t))return ctx.reply("❌ اكتب رقمًا.");if(+t===g.ans){clearS(ctx);return ctx.reply("🏆 إجابة صحيحة!",BACK)}return ctx.reply("❌ خطأ، حاول مرة أخرى.")}
  if(g.type==="closest"){if(!/^\d+$/.test(t))return ctx.reply("❌ اكتب رقمًا من 1 إلى 100.");const n=+t;if(n<1||n>100)return ctx.reply("❌ اكتب رقمًا من 1 إلى 100.");const d=Math.abs(n-g.n);clearS(ctx);return ctx.reply(`🎯 الرقم السري: ${g.n}\nاختيارك: ${n}\nالفارق: ${d}\n\n${d===0?"🏆 إصابة مباشرة!":d<=5?"🔥 قريب جدًا!":"👍"} `,BACK)}
});

/* Global safety */
bot.action("menu",async ctx=>{await ctx.answerCbQuery().catch(()=>{});await menu(ctx)});
bot.action("noop",ctx=>ctx.answerCbQuery().catch(()=>{}));
bot.catch((err,ctx)=>console.error("BOT_HANDLER_ERROR", {message:err?.message,stack:err?.stack,update_id:ctx?.update?.update_id}));
process.on("unhandledRejection",e=>console.error("UNHANDLED_REJECTION",e?.stack||e));
process.on("uncaughtException",e=>console.error("UNCAUGHT_EXCEPTION",e?.stack||e));

bot.launch().then(()=>console.log("🎮 Games bot started successfully")).catch(e=>{console.error("BOT_LAUNCH_ERROR",e?.stack||e);process.exit(1)});
process.once("SIGINT",()=>bot.stop("SIGINT"));
process.once("SIGTERM",()=>bot.stop("SIGTERM"));
