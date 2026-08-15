'use client'
import { useState, useCallback, useEffect, useRef, useMemo } from 'react'

/* ── Confetti ── */
function fireConfetti(tier = 1, vibe = 'genius') {
  const canvas = document.createElement('canvas')
  canvas.style.cssText = 'position:fixed;inset:0;z-index:9999;pointer-events:none;width:100%;height:100%'
  document.body.appendChild(canvas)
  canvas.width = window.innerWidth * 2; canvas.height = window.innerHeight * 2
  const ctx = canvas.getContext('2d'); ctx.scale(2, 2)
  const count = tier === 3 ? 130 : tier === 2 ? 80 : 50
  const colors = ({ unhinged: ['#f43f5e','#ec4899','#fb7185','#fda4af','#be185d','#f5f5f5'], genius: ['#818cf8','#6366f1','#a78bfa','#c4b5fd','#4f46e5','#f5f5f5'], wholesome: ['#fbbf24','#f59e0b','#fcd34d','#fde68a','#d97706','#f5f5f5'] })[vibe] || ['#818cf8','#6366f1','#a78bfa','#c4b5fd','#4f46e5','#f5f5f5']
  const pieces = Array.from({ length: count }, () => ({ x: window.innerWidth/2+(Math.random()-0.5)*200, y: window.innerHeight/2, vx: (Math.random()-0.5)*(tier===3?26:16), vy: -Math.random()*(tier===3?26:18)-5, w: Math.random()*8+3, h: Math.random()*6+2, color: colors[Math.floor(Math.random()*colors.length)], rot: Math.random()*Math.PI*2, rv: (Math.random()-0.5)*0.3, gravity: 0.38+Math.random()*0.2 }))
  let frame = 0; const maxFrames = tier === 3 ? 130 : 95
  const animate = () => { ctx.clearRect(0,0,canvas.width,canvas.height); let alive = false; for (const p of pieces) { p.x+=p.vx;p.vy+=p.gravity;p.y+=p.vy;p.rot+=p.rv;p.vx*=0.98; if(p.y<window.innerHeight+50){alive=true;ctx.save();ctx.translate(p.x,p.y);ctx.rotate(p.rot);ctx.fillStyle=p.color;ctx.globalAlpha=Math.max(0,1-frame/maxFrames);ctx.fillRect(-p.w/2,-p.h/2,p.w,p.h);ctx.restore()}}; frame++; if(alive&&frame<maxFrames) requestAnimationFrame(animate); else canvas.remove() }
  requestAnimationFrame(animate)
}

/* ── Sound ── */
let audioCtx = null
function getAudioCtx() { if(!audioCtx){try{audioCtx=new(window.AudioContext||window.webkitAudioContext)()}catch{return null}}; return audioCtx }
function playTick(pitch=800) { const ctx=getAudioCtx();if(!ctx)return;const o=ctx.createOscillator(),g=ctx.createGain();o.connect(g);g.connect(ctx.destination);o.frequency.value=pitch;o.type='sine';g.gain.value=0.04;g.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+0.06);o.start(ctx.currentTime);o.stop(ctx.currentTime+0.06) }
function playReveal(tier=1) { const ctx=getAudioCtx();if(!ctx)return;const notes=tier===3?[523,659,784,1047]:tier===2?[523,659,784]:[523,659];notes.forEach((f,i)=>{const o=ctx.createOscillator(),g=ctx.createGain();o.connect(g);g.connect(ctx.destination);o.frequency.value=f;o.type='sine';g.gain.value=0.06;g.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+0.15*(i+1)+0.2);o.start(ctx.currentTime+0.12*i);o.stop(ctx.currentTime+0.12*i+0.25)}) }
function haptic(p) { try{if(navigator.vibrate)navigator.vibrate(p)}catch{} }

/* ── Data ── */
const C = [
  {t:"Send 'I finally did it' to five people. Do not elaborate.",g:['solo','free','indoor'],e:'📱',v:'unhinged',r:1},
  {t:"Open your camera roll. The 7th photo is now your lock screen for a week. No appeals.",g:['solo','free','indoor'],e:'🔒',v:'unhinged',r:1},
  {t:"Text someone you haven't talked to in over a year. Just 'I was thinking about you.' Nothing else.",g:['solo','free','indoor'],e:'💬',v:'wholesome',r:1},
  {t:"Order delivery to a park bench. Set up a tablecloth and a candle. Eat a full three-course meal there.",g:['solo','paid','outdoor'],e:'🕯️',v:'unhinged',r:1},
  {t:"Take a photo of exactly what's in front of you right now. Post it captioned 'It's done.'",g:['solo','free','indoor'],e:'📸',v:'unhinged',r:1},
  {t:"Google 'events near me tonight.' Go to the weirdest one.",g:['solo','free','outdoor'],e:'🎯',v:'genius',r:1},
  {t:"Walk into a bakery. Ask what their personal favorite is. Buy two. Give them one.",g:['solo','paid','outdoor'],e:'🥐',v:'wholesome',r:1},
  {t:"Walk into the nicest hotel lobby in your city. Sit at the bar. Order one drink. Talk to whoever's next to you.",g:['solo','paid','outdoor'],e:'🥃',v:'genius',r:1},
  {t:"Go to a restaurant alone. Order the chef's favorite, not yours.",g:['solo','paid','outdoor'],e:'🍽️',v:'genius',r:1},
  {t:"Wear something you've been saving 'for a special occasion.' Today is the occasion.",g:['solo','free','indoor'],e:'👔',v:'genius',r:1},
  {t:"Walk into a store you've never entered. Buy the third thing you touch.",g:['solo','paid','outdoor'],e:'🚪',v:'genius',r:1},
  {t:"Go to a live show tonight for a genre you've never listened to. Stay for the whole thing. Talk to the band after.",g:['solo','paid','outdoor'],e:'🎵',v:'genius',r:1},
  {t:"Go to a bookstore. Buy the book with the best cover. No reading the summary.",g:['solo','paid','outdoor'],e:'📖',v:'genius',r:1},
  {t:"Pick a direction. Walk for exactly 20 minutes. Whatever you find, eat there.",g:['solo','paid','outdoor'],e:'🧭',v:'genius',r:1},
  {t:"Ask a barista to make you 'whatever they wish people would order.' Tip well.",g:['solo','paid','outdoor'],e:'☕',v:'wholesome',r:1},
  {t:"Buy a lottery ticket. Before you scratch it, write down exactly what you'd do with the money. Keep the note regardless.",g:['solo','paid','indoor'],e:'🎰',v:'genius',r:1},
  {t:"Go to a flea market. $10 budget. Buy the one thing that tells the best story.",g:['solo','paid','outdoor'],e:'🪆',v:'genius',r:1},
  {t:"Put your phone face-down. First notification you get — fully act on it. No matter what.",g:['solo','free','indoor'],e:'🔔',v:'unhinged',r:1},
  {t:"Hand your phone to a friend. They pick your wallpaper, ringtone, and profile photo. 48 hours.",g:['group','free','indoor'],e:'🤝',v:'unhinged',r:1},
  {t:"Go to an art supply store. Buy something you have no idea how to use. Make something with it tonight. Frame it.",g:['solo','paid','outdoor'],e:'🎨',v:'genius',r:1},
  {t:"Go to a thrift store. Buy the weirdest painting there. Hang it prominently. Tell guests it's an original.",g:['solo','paid','outdoor'],e:'🎨',v:'unhinged',r:1},
  {t:"Learn three phrases in a language you'll never need. Use all three in conversation today.",g:['solo','free','indoor'],e:'🗣️',v:'genius',r:1},
  {t:"Sit at a coffee shop window. Write down the imagined life story of every person who walks by for 30 minutes.",g:['solo','paid','outdoor'],e:'✍️',v:'genius',r:1},
  {t:"Find a flight under $100. Book it. You leave this week. Figure out the rest on the plane.",g:['solo','paid','outdoor'],e:'✈️',v:'unhinged',r:1},
  {t:"Leave a $5 bill tucked into chapter one of a kids' book at a bookstore.",g:['solo','paid','outdoor'],e:'💵',v:'wholesome',r:1},
  {t:"Write a Yelp review of your own apartment. 3 stars. Be fair but harsh.",g:['solo','free','indoor'],e:'⭐',v:'unhinged',r:2},
  {t:"Film a full house tour of your place like it's a $4 million listing. Use the voice.",g:['solo','free','indoor'],e:'🏠',v:'unhinged',r:2},
  {t:"Write a fake Wikipedia article about yourself. Include an 'Early Life,' 'Controversies,' and 'Legacy' section.",g:['solo','free','indoor'],e:'📖',v:'unhinged',r:2},
  {t:"Make a fake documentary trailer about your roommate's most mundane habit. Film festival submission quality.",g:['solo','free','indoor'],e:'🎬',v:'unhinged',r:2},
  {t:"Create a restaurant menu for meals you can make right now. Name the restaurant. Design a logo.",g:['solo','free','indoor'],e:'📋',v:'genius',r:2},
  {t:"Design a movie poster for the most boring day of your life. Tagline and everything.",g:['solo','free','indoor'],e:'🎞️',v:'genius',r:2},
  {t:"Recreate a famous painting with what's in your kitchen. Photograph both side by side.",g:['solo','free','indoor'],e:'🖼️',v:'genius',r:2},
  {t:"Cook a dish from a cuisine you've never tried. The recipe must be in that language.",g:['solo','paid','indoor'],e:'🧑‍🍳',v:'genius',r:2},
  {t:"Ride public transit to the last stop. Get off. Walk around for 30 minutes. Get back on.",g:['solo','paid','outdoor'],e:'🚌',v:'genius',r:2},
  {t:"Find a viewpoint you've never been to within 30 minutes. Go at golden hour.",g:['solo','free','outdoor'],e:'🌇',v:'wholesome',r:2},
  {t:"Go to a farmers market. Buy the strangest thing. Build tonight's dinner around it.",g:['solo','paid','outdoor'],e:'🥬',v:'genius',r:2},
  {t:"Sit in a hotel lobby you have no business being in. Order a coffee. Act like you own the place.",g:['solo','paid','outdoor'],e:'🏨',v:'unhinged',r:2},
  {t:"Go to a café. Write one page about whatever's on your mind. Leave it folded on the table.",g:['solo','paid','outdoor'],e:'✍️',v:'genius',r:2},
  {t:"Go to an open house for a home you can't afford. Take it very seriously.",g:['solo','free','outdoor'],e:'🏡',v:'unhinged',r:2},
  {t:"Go to a restaurant you've walked past 100 times but never entered. Get the server's pick.",g:['solo','paid','outdoor'],e:'🚶',v:'genius',r:2},
  {t:"Walk into a random building's lobby. Take the elevator to the highest floor. See what's up there.",g:['solo','free','outdoor'],e:'🛗',v:'unhinged',r:2},
  {t:"Go to a museum. Pick one piece. Sit with it for 15 minutes. Write what it said to you.",g:['solo','paid','indoor'],e:'🏛️',v:'genius',r:2},
  {t:"Cook a meal where each person controls one ingredient. No communication allowed.",g:['group','free','indoor'],e:'🍳',v:'genius',r:2},
  {t:"Everyone records a 60-second voice memo to their future self. Seal them. Open in 1 year.",g:['group','free','indoor'],e:'🔮',v:'wholesome',r:1},
  {t:"Go bowling. Loser gives a 3-minute acceptance speech thanking everyone for the loss.",g:['group','paid','outdoor'],e:'🎳',v:'unhinged',r:1},
  {t:"Host a dinner where every dish must be someone's cultural comfort food. No repeats.",g:['group','paid','indoor'],e:'🍛',v:'wholesome',r:2},
  {t:"Each person teaches the group one skill in exactly 5 minutes. Timer is law.",g:['group','free','indoor'],e:'⏱️',v:'genius',r:1},
  {t:"Go thrift shopping. $5 budget. Buy the most thoughtful gift for the person next to you.",g:['group','paid','outdoor'],e:'🎁',v:'wholesome',r:1},
  {t:"Everyone writes one secret on a piece of paper. Shuffle. Read them out loud. Nobody claims theirs. Ever.",g:['group','free','indoor'],e:'🤫',v:'unhinged',r:2},
  {t:"Watch a movie none of you have seen. Pause it halfway. Everyone writes how it ends.",g:['group','free','indoor'],e:'📺',v:'genius',r:1},
  {t:"Take the same photo of the same subject. Compare. Crown a winner. Winner picks dinner.",g:['group','free','outdoor'],e:'📷',v:'genius',r:1},
  {t:"Apply for a job you're wildly unqualified for. Put real effort into the cover letter.",g:['solo','free','indoor'],e:'📝',v:'unhinged',r:2},
  {t:"Go to a car dealership. Test drive something absurd. Take notes like you're serious.",g:['solo','free','outdoor'],e:'🚗',v:'unhinged',r:2},
  {t:"Spend a full day without your phone. Write down everything you noticed by the end.",g:['solo','free','outdoor'],e:'📵',v:'genius',r:2},
  {t:"Set an alarm for 4am. Watch the entire sunrise. Don't bring your phone.",g:['solo','free','outdoor'],e:'🌅',v:'genius',r:2},
  {t:"Learn to solve a Rubik's cube this week. Post your final time.",g:['solo','paid','indoor'],e:'🧊',v:'genius',r:2},
  {t:"Text everyone in your recent contacts one specific memory you have with them. No context.",g:['solo','free','indoor'],e:'💭',v:'wholesome',r:2},
  {t:"Bring a chess set to a park. Challenge strangers. Play at least five games. Lose gracefully.",g:['solo','free','outdoor'],e:'♟️',v:'genius',r:2},
  {t:"Learn to moonwalk this week. Film daily progress. Post only the final video.",g:['solo','free','indoor'],e:'🕺',v:'genius',r:2},
  {t:"Learn to cook one dish from your grandparents' culture. Call them for the recipe.",g:['solo','paid','indoor'],e:'🍲',v:'wholesome',r:2},
  {t:"Show up to a pickup basketball game. Play your hardest even if you're terrible. Buy everyone drinks after.",g:['solo','paid','outdoor'],e:'🏀',v:'wholesome',r:2},
  {t:"Go to a karaoke bar alone. Sing one song. Leave immediately after.",g:['solo','paid','outdoor'],e:'🎤',v:'unhinged',r:2},
  {t:"Pick a random Wikipedia article. Become an expert on it. Bring it up in every conversation for 24 hours.",g:['solo','free','indoor'],e:'🧠',v:'genius',r:1},
  {t:"Make a time capsule with someone you care about. Seal it. GPS mark it. Calendar reminder: 5 years.",g:['group','free','outdoor'],e:'⏳',v:'wholesome',r:1},
  {t:"Buy a disposable camera. Use all 27 shots in one day. Develop them next month.",g:['solo','paid','outdoor'],e:'📷',v:'genius',r:3},
  {t:"Learn one song on an instrument you don't play. Perform it at dinner.",g:['solo','paid','indoor'],e:'🎸',v:'genius',r:3},
  {t:"Sign up for an open mic. Dramatic reading of your last text conversation.",g:['solo','free','outdoor'],e:'🎪',v:'unhinged',r:3},
  {t:"Rent formal wear. Wear it to do something completely mundane. Don't explain.",g:['solo','paid','outdoor'],e:'🤵',v:'unhinged',r:3},
  {t:"Make a zine about something hyper-specific you care about. Print 10 copies. Leave them places.",g:['solo','paid','indoor'],e:'📰',v:'genius',r:3},
  {t:"Enter a competition none of you have any business being in. Document the journey.",g:['group','paid','outdoor'],e:'🏅',v:'genius',r:3},
  {t:"Write and perform a 3-minute play about something that actually happened to your friend group.",g:['group','free','indoor'],e:'🎭',v:'genius',r:3},
  {t:"Pick a random spot on a map. Everyone takes a different route. Meet for food.",g:['group','free','outdoor'],e:'🗺️',v:'genius',r:3},
  {t:"Cook the most complex recipe you can find. Film every failure. Post only the final plate.",g:['solo','paid','indoor'],e:'👨‍🍳',v:'genius',r:3},
  {t:"Flip a coin at a train station. Take whichever train it lands on. Spend the day wherever.",g:['solo','paid','outdoor'],e:'🚂',v:'genius',r:3},
  {t:"Interview your oldest living relative about their life. Record it. Keep it forever.",g:['solo','free','indoor'],e:'🎙️',v:'wholesome',r:3},
  {t:"Organize a dinner where everyone pays what they can. Each person brings one dish.",g:['group','free','outdoor'],e:'🥘',v:'wholesome',r:3},
]
// Expand short keys to full shape
const CHALLENGES = C.map(c => ({ text: c.t, tags: c.g, emoji: c.e, vibe: c.v, tier: c.r }))

const FILTER_GROUPS = [
  { label: 'Who', options: [{ key: 'solo', label: 'Solo', icon: '🧍' }, { key: 'group', label: 'Crew', icon: '👥' }] },
  { label: 'Where', options: [{ key: 'indoor', label: 'Inside', icon: '🏠' }, { key: 'outdoor', label: 'Outside', icon: '☀️' }] },
  { label: 'Cost', options: [{ key: 'free', label: 'Free', icon: '✌️' }, { key: 'paid', label: '$', icon: '💰' }] },
]
const TIER_FILTERS = [{ key: 1, label: '5 min', icon: '⚡' }, { key: 2, label: '1 hour', icon: '⏰' }, { key: 3, label: 'All day', icon: '🌟' }]
const VM = {
  unhinged: { glow: 'rgba(244,63,94,0.10)', badge: '🫠 unhinged', border: 'border-rose-500/20', accent: '#f43f5e', canvasBg: ['#1a0612','#12061a'], canvasAccent: '#f43f5e' },
  genius: { glow: 'rgba(129,140,248,0.10)', badge: '🧠 big brain', border: 'border-indigo-400/20', accent: '#818cf8', canvasBg: ['#08082e','#0e082e'], canvasAccent: '#818cf8' },
  wholesome: { glow: 'rgba(251,191,36,0.10)', badge: '🥹 wholesome', border: 'border-amber-500/20', accent: '#fbbf24', canvasBg: ['#1a1405','#1a1005'], canvasAccent: '#fbbf24' },
}
const TM = {
  1: { label: 'right now', color: 'text-emerald-400', border: 'border-emerald-500/15' },
  2: { label: 'commit to it', color: 'text-sky-400', border: 'border-sky-500/15' },
  3: { label: 'life event', color: 'text-rose-400', border: 'border-rose-500/15' },
}
const SPIN_WORDS = ['hold on let me ask the void…','manifesting rn…','the algorithm is thinking…','loading your roman empire…','consulting your future self…','ok wait this one hits…','the universe is typing…']
const SLOT_EMOJIS = ['🎲','✨','🌟','💫','🎯','🔮','🎪','🚀','⚡','🌀','💥','🫧','🪄','🌈','🦋']
const MILESTONES = { 3:{msg:'3 days in. no one can stop you.',emoji:'🔥'}, 7:{msg:'a whole week of main character energy',emoji:'⚡'}, 14:{msg:'two weeks. this is a lifestyle now.',emoji:'💅'}, 30:{msg:'30 days. you are genuinely unhinged.',emoji:'👑'}, 100:{msg:'100 days. you ARE free will.',emoji:'🏆'} }

function getDailyChallenge() { const d=new Date(); return CHALLENGES[(d.getFullYear()*10000+(d.getMonth()+1)*100+d.getDate())%CHALLENGES.length] }

export default function FreeWillUtilizer() {
  const [activeFilters, setActiveFilters] = useState(new Set())
  const [tierFilter, setTierFilter] = useState(null)
  const [current, setCurrent] = useState(null)
  const [isSpinning, setIsSpinning] = useState(false)
  const [slotEmoji, setSlotEmoji] = useState('🎲')
  const [spinWord, setSpinWord] = useState(SPIN_WORDS[0])
  const [history, setHistory] = useState([])
  const [copied, setCopied] = useState(false)
  const [shakeCard, setShakeCard] = useState(false)
  const [totalSpins, setTotalSpins] = useState(0)
  const [accepted, setAccepted] = useState(0)
  const [challengeAccepted, setChallengeAccepted] = useState(false)
  const [showFilters, setShowFilters] = useState(false)
  const [streakMilestone, setStreakMilestone] = useState(null)
  const [soundOn, setSoundOn] = useState(true)
  const spinRef = useRef(null)
  const [dayStreak, setDayStreak] = useState(0)
  const [lastDay, setLastDay] = useState(null)
  const daily = useMemo(() => getDailyChallenge(), [])

  useEffect(() => {
    try {
      const s = JSON.parse(localStorage.getItem('fwu-stats') || '{}')
      if (s.spins) setTotalSpins(s.spins); if (s.accepted) setAccepted(s.accepted)
      if (s.streak) setDayStreak(s.streak); if (s.lastDay) setLastDay(s.lastDay)
      if (s.soundOn === false) setSoundOn(false)
      const today = new Date().toDateString()
      if (s.lastDay) { const diff = Math.floor((new Date(today) - new Date(s.lastDay)) / 86400000); if (diff > 1) setDayStreak(0) }
    } catch {}
  }, [])

  const saveStats = (spins, acc, streak, day) => { try { localStorage.setItem('fwu-stats', JSON.stringify({ spins, accepted: acc, streak, lastDay: day, soundOn })) } catch {} }
  const toggleFilter = (key) => setActiveFilters(prev => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n })
  const getPool = useCallback(() => {
    let pool = CHALLENGES
    if (activeFilters.size > 0) pool = pool.filter(a => [...activeFilters].every(f => a.tags.includes(f)))
    if (tierFilter) pool = pool.filter(a => a.tier === tierFilter)
    return pool
  }, [activeFilters, tierFilter])

  const poolSize = getPool().length
  const anyFilterActive = activeFilters.size > 0 || tierFilter !== null

  const spin = useCallback(() => {
    const pool = getPool()
    if (!pool.length) { setShakeCard(true); setTimeout(() => setShakeCard(false), 600); return }
    setIsSpinning(true); setChallengeAccepted(false)
    setSpinWord(SPIN_WORDS[Math.floor(Math.random() * SPIN_WORDS.length)])
    let tick = 0
    const scheduleTick = () => {
      if (tick >= 16) return
      spinRef.current = setTimeout(() => {
        setSlotEmoji(SLOT_EMOJIS[Math.floor(Math.random() * SLOT_EMOJIS.length)])
        if (soundOn) playTick(600 + tick * 35); haptic(15); tick++; scheduleTick()
      }, 40 + tick * 14 + (tick > 10 ? (tick - 10) * 35 : 0))
    }
    scheduleTick()
    setTimeout(() => {
      const pick = pool[Math.floor(Math.random() * pool.length)]
      setCurrent(pick); setSlotEmoji(pick.emoji); setIsSpinning(false)
      setHistory(prev => [pick, ...prev.filter(h => h.text !== pick.text)].slice(0, 10))
      fireConfetti(pick.tier, pick.vibe); if (soundOn) playReveal(pick.tier)
      haptic(pick.tier === 3 ? [100,50,100,50,200] : pick.tier === 2 ? [60,40,100] : 80)
      const newSpins = totalSpins + 1; setTotalSpins(newSpins)
      const today = new Date().toDateString()
      let newStreak = dayStreak
      if (lastDay !== today) {
        const diff = lastDay ? Math.floor((new Date(today) - new Date(lastDay)) / 86400000) : 999
        newStreak = diff <= 1 ? dayStreak + 1 : 1; setDayStreak(newStreak); setLastDay(today)
        if (MILESTONES[newStreak]) { setStreakMilestone(MILESTONES[newStreak]); setTimeout(() => setStreakMilestone(null), 3500) }
      }
      saveStats(newSpins, accepted, newStreak, today)
    }, 1400)
  }, [getPool, totalSpins, accepted, dayStreak, lastDay, soundOn])

  useEffect(() => () => { if (spinRef.current) clearTimeout(spinRef.current) }, [])

  const acceptChallenge = () => {
    if (challengeAccepted) return
    setChallengeAccepted(true); const newAcc = accepted + 1; setAccepted(newAcc)
    saveStats(totalSpins, newAcc, dayStreak, lastDay); if (soundOn) playReveal(1); haptic(60)
  }

  const vibe = current ? VM[current.vibe] : null
  const tier = current ? TM[current.tier] : null
  const dayLabel = dayStreak > 0 ? `day ${dayStreak} of using my free will:` : 'today i chose to:'
  const shareText = current ? `${dayLabel}\n\n${current.text}\n\namazing use of free will ✦` : ''
  const tweetUrl = () => `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}`
  const whatsappUrl = () => `https://wa.me/?text=${encodeURIComponent(shareText)}`
  const copyText = async () => { try { await navigator.clipboard.writeText(shareText); setCopied(true); setTimeout(() => setCopied(false), 2200) } catch {} }

  const downloadShareCard = useCallback(() => {
    if (!current) return
    const v = VM[current.vibe], tm = TM[current.tier], W = 1080, H = 1350, c = document.createElement('canvas')
    c.width = W; c.height = H; const ctx = c.getContext('2d')
    const bg = ctx.createLinearGradient(0,0,W,H); bg.addColorStop(0,v.canvasBg[0]); bg.addColorStop(1,v.canvasBg[1]); ctx.fillStyle=bg; ctx.fillRect(0,0,W,H)
    ctx.strokeStyle='rgba(255,255,255,0.012)'; ctx.lineWidth=1
    for(let x=0;x<W;x+=40){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke()}
    for(let y=0;y<H;y+=40){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke()}
    const grd=ctx.createRadialGradient(W/2,H*0.35,0,W/2,H*0.35,420); grd.addColorStop(0,v.glow.replace('0.10','0.25')); grd.addColorStop(0.6,v.glow.replace('0.10','0.06')); grd.addColorStop(1,'transparent'); ctx.fillStyle=grd; ctx.fillRect(0,0,W,H)
    ctx.textAlign='center'
    ctx.fillStyle='rgba(255,255,255,0.2)'; ctx.font='500 18px system-ui,sans-serif'; ctx.fillText('✦  free will utilizer  ✦',W/2,70)
    ctx.fillStyle='rgba(255,255,255,0.4)'; ctx.font='400 26px system-ui,sans-serif'; ctx.fillText(dayStreak>0?`day ${dayStreak}`:'today i chose to:',W/2,120)
    ctx.font='140px serif'; ctx.fillText(current.emoji,W/2,H*0.3+20)
    ctx.fillStyle='#f0f0f0'; ctx.font='bold 44px system-ui,sans-serif'
    const words=current.text.split(' '); let lines=[],line=''
    for(const w of words){const test=line?line+' '+w:w;if(ctx.measureText(test).width>W-180){lines.push(line);line=w}else line=test}
    if(line)lines.push(line); lines.forEach((l,i)=>ctx.fillText(l,W/2,H*0.43+i*60))
    ctx.fillStyle='rgba(255,255,255,0.3)'; ctx.font='500 24px system-ui,sans-serif'; ctx.fillText(`${v.badge}  ·  ${tm.label}`,W/2,H*0.43+lines.length*60+50)
    ctx.strokeStyle='rgba(255,255,255,0.05)'; ctx.lineWidth=1; ctx.beginPath(); ctx.moveTo(W*0.15,H*0.74); ctx.lineTo(W*0.85,H*0.74); ctx.stroke()
    ctx.fillStyle='#d4d4d4'; ctx.font='italic 36px Georgia,serif'; ctx.fillText('"amazing use of free will"',W/2,H*0.74+65)
    ctx.fillStyle='rgba(255,255,255,0.15)'; ctx.font='400 20px system-ui,sans-serif'; ctx.fillText('#amazinguseoffreewill',W/2,H-65)
    const link=document.createElement('a'); link.download='amazing-use-of-free-will.png'; link.href=c.toDataURL('image/png'); link.click()
  }, [current, dayStreak])

  const dailyVibe = VM[daily.vibe], dailyTier = TM[daily.tier]
  const noiseUrl = "data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E"

  return (
    <div className="min-h-screen bg-[#050507] text-neutral-100 overflow-x-hidden selection:bg-indigo-500/30">
      {/* Ambient */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-[-200px] left-1/2 -translate-x-1/2 w-[700px] h-[500px] rounded-full blur-[120px]" style={{ background: 'radial-gradient(ellipse, rgba(129,140,248,0.06), transparent 70%)', animation: 'ambient-drift 12s ease-in-out infinite alternate' }} />
        <div className="absolute bottom-[-100px] left-1/4 w-[400px] h-[300px] rounded-full blur-[100px]" style={{ background: 'radial-gradient(ellipse, rgba(244,63,94,0.03), transparent 70%)', animation: 'ambient-drift 15s ease-in-out infinite alternate-reverse' }} />
        <div className="absolute top-1/3 right-[-100px] w-[300px] h-[400px] rounded-full blur-[100px]" style={{ background: 'radial-gradient(ellipse, rgba(251,191,36,0.02), transparent 70%)', animation: 'ambient-drift 18s ease-in-out infinite alternate' }} />
        <div className="absolute inset-0" style={{ backgroundImage: `url("${noiseUrl}")`, backgroundRepeat: 'repeat', opacity: 0.6, mixBlendMode: 'overlay' }} />
        {[...Array(20)].map((_, i) => (
          <div key={i} className="absolute w-px h-px rounded-full bg-white/20" style={{ left: `${5+(i*47)%90}%`, top: `${3+(i*31)%94}%`, animation: `particle-float ${6+(i%5)*2}s ease-in-out ${(i%7)*-1.5}s infinite alternate`, width: i%3===0?'2px':'1px', height: i%3===0?'2px':'1px', opacity: 0.15+(i%4)*0.05 }} />
        ))}
      </div>

      {/* Streak toast */}
      {streakMilestone && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50 bg-white/[0.06] backdrop-blur-2xl px-6 py-3 rounded-2xl shadow-2xl border border-white/[0.08]" style={{ animation: 'card-reveal 0.4s ease' }}>
          <p className="text-sm font-medium text-white text-center">{streakMilestone.emoji} {streakMilestone.msg}</p>
        </div>
      )}

      <div className="relative z-10 max-w-lg mx-auto px-5">
        {/* Header */}
        <header className="pt-16 pb-10 text-center">
          <p className="text-[10px] font-medium tracking-[0.35em] uppercase text-neutral-600 mb-6" style={{ animation: 'card-reveal 0.8s ease' }}>you have free will · use it or lose it</p>
          <h1 className="text-5xl sm:text-[3.75rem] font-black tracking-[-0.04em] leading-[0.85] mb-3" style={{ animation: 'card-reveal 0.6s ease' }}>
            <span style={{ background: 'linear-gradient(135deg, #e0e7ff 0%, #818cf8 40%, #c4b5fd 60%, #f0f0f0 100%)', backgroundSize: '200% 200%', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', animation: 'gradient-shift 8s ease infinite' }}>free will</span>
          </h1>
          <div className="text-xl sm:text-2xl font-extralight tracking-[0.2em] uppercase text-neutral-600 mb-7" style={{ animation: 'card-reveal 0.7s ease' }}>
            utilizer <span className="text-indigo-400/60" style={{ animation: 'star-pulse 3s ease-in-out infinite' }}>✦</span>
          </div>
          <p className="text-[13px] text-neutral-600 max-w-[260px] mx-auto leading-relaxed" style={{ animation: 'card-reveal 0.9s ease' }}>
            for when someone comments<br /><span className="text-neutral-400 italic">&quot;amazing use of free will&quot;</span>
          </p>
        </header>

        {/* Stats */}
        {totalSpins > 0 && (
          <div className="flex items-center justify-center gap-4 mb-8 text-[11px] text-neutral-700 flex-wrap">
            {dayStreak > 0 && <><span className="text-indigo-400/70 font-medium">day {dayStreak}</span><span className="w-px h-2.5 bg-neutral-800/60" /></>}
            <span>{totalSpins} spins</span><span className="w-px h-2.5 bg-neutral-800/60" /><span>{accepted} accepted</span><span className="w-px h-2.5 bg-neutral-800/60" /><span>{Math.round((accepted/Math.max(totalSpins,1))*100)}%</span>
          </div>
        )}

        {/* Daily */}
        {!current && !isSpinning && (
          <section className="mb-8" style={{ animation: 'card-reveal 0.5s ease' }}>
            <button onClick={() => { setCurrent(daily); fireConfetti(daily.tier, daily.vibe); if (soundOn) playReveal(daily.tier) }}
              className="w-full bg-white/[0.02] border border-white/[0.05] rounded-2xl p-4 text-left hover:bg-white/[0.04] transition-all active:scale-[0.99] group">
              <div className="flex items-center gap-3.5">
                <span className="text-2xl">{daily.emoji}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] font-semibold tracking-[0.2em] uppercase text-indigo-400/60">today&apos;s move</span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${dailyTier.border} ${dailyTier.color} bg-white/[0.02]`}>{dailyTier.label}</span>
                  </div>
                  <p className="text-[13px] text-neutral-500 leading-snug truncate group-hover:text-neutral-400 transition-colors">{daily.text}</p>
                </div>
                <span className="text-neutral-800 text-sm group-hover:text-neutral-600 transition-colors">→</span>
              </div>
            </button>
          </section>
        )}

        {/* Filters */}
        <section className="mb-8">
          <button onClick={() => setShowFilters(!showFilters)} className="w-full flex items-center justify-between px-4 py-2.5 bg-white/[0.015] border border-white/[0.04] rounded-xl text-xs text-neutral-700 hover:bg-white/[0.03] transition-all">
            <span className="flex items-center gap-2">
              <span className="text-[10px] font-medium tracking-[0.15em] uppercase">{anyFilterActive ? `${poolSize} match${poolSize !== 1 ? 'es' : ''}` : 'filter'}</span>
              {anyFilterActive && <button onClick={(e) => { e.stopPropagation(); setActiveFilters(new Set()); setTierFilter(null) }} className="text-[10px] text-neutral-800 hover:text-neutral-500 underline ml-1">clear</button>}
            </span>
            <span className={`text-neutral-800 transition-transform text-[10px] ${showFilters ? 'rotate-180' : ''}`}>▾</span>
          </button>
          {showFilters && (
            <div className="mt-2 bg-white/[0.015] border border-white/[0.04] rounded-2xl p-4" style={{ animation: 'card-reveal 0.2s ease' }}>
              <div className="grid grid-cols-3 gap-2 mb-3">
                {FILTER_GROUPS.map(g => (
                  <div key={g.label} className="space-y-1.5">
                    <div className="text-[10px] font-medium text-neutral-700 pl-0.5">{g.label}</div>
                    {g.options.map(o => {
                      const on = activeFilters.has(o.key)
                      return <button key={o.key} onClick={() => toggleFilter(o.key)} className={`w-full flex items-center gap-1.5 px-2.5 py-2 rounded-xl text-xs font-medium transition-all ${on ? 'bg-indigo-500/10 border border-indigo-400/20 text-indigo-300' : 'bg-white/[0.02] border border-white/[0.04] text-neutral-600 hover:bg-white/[0.04] hover:text-neutral-500'}`}>
                        <span className="text-sm">{o.icon}</span><span>{o.label}</span>
                      </button>
                    })}
                  </div>
                ))}
              </div>
              <div className="border-t border-white/[0.03] pt-3">
                <div className="text-[10px] font-medium text-neutral-700 pl-0.5 mb-1.5">Time</div>
                <div className="flex gap-2">
                  {TIER_FILTERS.map(t => (
                    <button key={t.key} onClick={() => setTierFilter(tierFilter === t.key ? null : t.key)}
                      className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium transition-all ${tierFilter === t.key ? 'bg-indigo-500/10 border border-indigo-400/20 text-indigo-300' : 'bg-white/[0.02] border border-white/[0.04] text-neutral-600 hover:bg-white/[0.04]'}`}>
                      <span>{t.icon}</span><span>{t.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </section>

        {/* Main Card */}
        <section className="mb-8">
          <div className="rounded-[1.75rem] p-px" style={{
            background: current && !isSpinning ? `conic-gradient(from var(--border-angle, 0deg), ${vibe.accent}30, transparent 30%, transparent 70%, ${vibe.accent}18)` : isSpinning ? 'conic-gradient(from var(--border-angle, 0deg), rgba(129,140,248,0.15), transparent 30%, transparent 70%, rgba(129,140,248,0.10))' : 'linear-gradient(135deg, rgba(255,255,255,0.04), transparent 40%, transparent 60%, rgba(255,255,255,0.02))',
            animation: current || isSpinning ? 'border-rotate 4s linear infinite' : 'none',
          }}>
            <div onClick={!current && !isSpinning ? spin : undefined}
              className={`relative rounded-[calc(1.75rem-1px)] min-h-[320px] sm:min-h-[380px] flex flex-col items-center justify-center p-8 sm:p-12 text-center transition-all duration-700 ${!current && !isSpinning ? 'cursor-pointer hover:bg-white/[0.015]' : ''}`}
              style={{
                background: current && !isSpinning ? `radial-gradient(ellipse at 50% 30%, ${vibe.glow.replace('0.10','0.06')}, transparent 70%), #08080f` : '#08080f',
                boxShadow: current && !isSpinning ? `0 0 80px ${vibe.glow}, 0 8px 32px rgba(0,0,0,0.4)` : '0 8px 32px rgba(0,0,0,0.3)',
                animation: shakeCard ? 'shake 0.6s ease' : isSpinning ? 'pulse-glow 0.35s ease infinite alternate' : 'none',
              }}>
              {isSpinning ? (
                <div className="flex flex-col items-center gap-5">
                  <div className="text-7xl sm:text-8xl" style={{ animation: 'spin-wobble 0.35s ease infinite', filter: 'blur(0.5px)' }}>{slotEmoji}</div>
                  <div className="flex gap-1.5">{[0,1,2,3].map(i => <div key={i} className="w-1 h-1 rounded-full bg-indigo-400/40" style={{ animation: `dot-bounce 0.5s ease ${i*0.1}s infinite alternate` }} />)}</div>
                  <p className="text-xs text-neutral-700 italic">{spinWord}</p>
                </div>
              ) : current ? (
                <div className="flex flex-col items-center gap-5" style={{ animation: 'card-reveal 0.6s cubic-bezier(0.16,1,0.3,1)' }}>
                  <div className="text-7xl sm:text-8xl">{current.emoji}</div>
                  <p className="text-xl sm:text-2xl font-semibold leading-snug text-neutral-100 max-w-md tracking-[-0.01em]">{current.text}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-[10px] font-medium tracking-wide px-2.5 py-1 rounded-full bg-white/[0.03] border ${vibe.border} text-neutral-500`}>{vibe.badge}</span>
                    <span className={`text-[10px] font-medium tracking-wide px-2.5 py-1 rounded-full bg-white/[0.03] border ${tier.border} ${tier.color}`}>{tier.label}</span>
                  </div>
                  <div className="flex items-center gap-1.5 mt-2">
                    <a href={tweetUrl()} target="_blank" rel="noopener noreferrer" className="p-2.5 rounded-full bg-white/[0.03] hover:bg-white/[0.08] transition-all" title="Post on X">
                      <svg className="w-3.5 h-3.5 text-neutral-600" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                    </a>
                    <a href={whatsappUrl()} target="_blank" rel="noopener noreferrer" className="p-2.5 rounded-full bg-white/[0.03] hover:bg-white/[0.08] transition-all" title="WhatsApp">
                      <svg className="w-3.5 h-3.5 text-neutral-600" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
                    </a>
                    <button onClick={copyText} className="p-2.5 rounded-full bg-white/[0.03] hover:bg-white/[0.08] transition-all" title="Copy"><span className="text-xs text-neutral-600">{copied ? '✓' : '⎘'}</span></button>
                    <button onClick={downloadShareCard} className="p-2.5 rounded-full bg-white/[0.03] hover:bg-white/[0.08] transition-all" title="Download story card"><span className="text-xs text-neutral-600">↓</span></button>
                    <button onClick={() => { if (typeof navigator !== 'undefined' && navigator.share) navigator.share({ text: shareText }).catch(() => {}) }} className="p-2.5 rounded-full bg-white/[0.03] hover:bg-white/[0.08] transition-all sm:hidden" title="Share"><span className="text-xs text-neutral-600">↗</span></button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-5">
                  <div className="text-7xl" style={{ animation: 'float 3s ease-in-out infinite' }}>🎲</div>
                  <p className="text-[15px] text-neutral-600 font-medium">tap to spin</p>
                  <p className="text-[11px] text-neutral-800">{poolSize} ways to use it</p>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* Buttons */}
        <div className="flex flex-col items-center gap-3 mb-10">
          <button onClick={spin} disabled={isSpinning}
            className={`w-full py-4 rounded-2xl font-semibold text-[15px] tracking-[-0.01em] transition-all duration-300 ${isSpinning ? 'bg-white/[0.02] text-neutral-800 cursor-wait' : poolSize === 0 ? 'bg-white/[0.02] text-neutral-800 cursor-not-allowed' : 'bg-white/[0.05] border border-white/[0.07] text-neutral-300 hover:bg-white/[0.08] hover:border-white/[0.12] hover:text-neutral-100 active:scale-[0.97] shadow-[0_0_60px_rgba(129,140,248,0.06),0_0_120px_rgba(129,140,248,0.02)]'}`}>
            {isSpinning ? 'one sec…' : current ? 'spin again' : poolSize === 0 ? 'no matches' : 'use your free will'}
          </button>
          {current && !isSpinning && (
            <button onClick={acceptChallenge}
              className={`px-6 py-2.5 rounded-xl text-sm font-medium transition-all active:scale-[0.97] ${challengeAccepted ? 'bg-emerald-500/10 border border-emerald-400/20 text-emerald-400' : 'bg-white/[0.02] border border-white/[0.05] text-neutral-600 hover:bg-white/[0.05] hover:text-neutral-400'}`} style={{ animation: 'card-reveal 0.3s ease' }}>
              {challengeAccepted ? '✓ locked in' : "i'm doing this"}
            </button>
          )}
          <button onClick={() => { setSoundOn(!soundOn); try { localStorage.setItem('fwu-stats', JSON.stringify({ spins: totalSpins, accepted, streak: dayStreak, lastDay, soundOn: !soundOn })) } catch {} }}
            className="text-[10px] text-neutral-800 hover:text-neutral-600 transition mt-1">{soundOn ? '♪ on' : '♪ off'}</button>
        </div>

        {/* History */}
        {history.length > 1 && (
          <section className="mb-12">
            <p className="text-[10px] font-medium tracking-[0.2em] uppercase text-neutral-800 mb-3">Previous</p>
            <div className="space-y-1">
              {history.slice(1).map((item, i) => (
                <button key={item.text} onClick={() => { setCurrent(item); setChallengeAccepted(false) }}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl bg-white/[0.01] border border-white/[0.02] text-sm text-neutral-700 text-left hover:bg-white/[0.03] hover:text-neutral-500 transition-colors"
                  style={{ opacity: 1 - i * 0.08 }}>
                  <span className="text-sm flex-shrink-0">{item.emoji}</span>
                  <span className="truncate flex-1">{item.text}</span>
                </button>
              ))}
            </div>
          </section>
        )}

        {/* Footer */}
        <footer className="pb-16 text-center border-t border-white/[0.03] pt-10">
          <p className="text-[11px] text-neutral-700 leading-relaxed max-w-[260px] mx-auto mb-3">you get ~2.5 billion seconds.<br />you just spent one deciding<br />how to use the next few thousand.</p>
          <p className="text-[10px] text-neutral-800"><span style={{ background: 'linear-gradient(90deg, rgba(129,140,248,0.4), rgba(244,63,94,0.4), rgba(251,191,36,0.4))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>✦</span></p>
        </footer>
      </div>

      <style jsx>{`
        @keyframes shake { 0%,100%{transform:translateX(0) rotate(0)} 15%{transform:translateX(-8px) rotate(-1.5deg)} 30%{transform:translateX(8px) rotate(1.5deg)} 45%{transform:translateX(-4px) rotate(-0.5deg)} 60%{transform:translateX(4px) rotate(0.5deg)} }
        @keyframes card-reveal { from{opacity:0;transform:translateY(14px) scale(0.97)} to{opacity:1;transform:translateY(0) scale(1)} }
        @keyframes pulse-glow { from{box-shadow:0 0 20px rgba(129,140,248,0.03),0 8px 32px rgba(0,0,0,0.3)} to{box-shadow:0 0 60px rgba(129,140,248,0.1),0 8px 32px rgba(0,0,0,0.3)} }
        @keyframes dot-bounce { from{transform:translateY(0);opacity:0.3} to{transform:translateY(-6px);opacity:1} }
        @keyframes spin-wobble { 0%{transform:rotate(0) scale(1)} 25%{transform:rotate(8deg) scale(1.06)} 50%{transform:rotate(-8deg) scale(0.94)} 75%{transform:rotate(4deg) scale(1.02)} 100%{transform:rotate(0) scale(1)} }
        @keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-10px)} }
        @property --border-angle { syntax:'<angle>'; initial-value:0deg; inherits:false }
        @keyframes border-rotate { to{--border-angle:360deg} }
        @keyframes gradient-shift { 0%,100%{background-position:0% 50%} 50%{background-position:100% 50%} }
        @keyframes star-pulse { 0%,100%{opacity:0.6;transform:scale(1)} 50%{opacity:1;transform:scale(1.15)} }
        @keyframes ambient-drift { 0%{transform:translate(0,0) scale(1)} 100%{transform:translate(30px,-20px) scale(1.1)} }
        @keyframes particle-float { 0%{transform:translateY(0) translateX(0);opacity:0.1} 50%{opacity:0.25} 100%{transform:translateY(-30px) translateX(15px);opacity:0.05} }
      `}</style>
    </div>
  )
}
