'use client'
import { useState, useCallback, useEffect, useRef, useMemo } from 'react'

/* ── Confetti (scales with tier) ── */
function fireConfetti(tier = 1) {
  const canvas = document.createElement('canvas')
  canvas.style.cssText = 'position:fixed;inset:0;z-index:9999;pointer-events:none;width:100%;height:100%'
  document.body.appendChild(canvas)
  canvas.width = window.innerWidth * 2
  canvas.height = window.innerHeight * 2
  const ctx = canvas.getContext('2d')
  ctx.scale(2, 2)
  const count = tier === 3 ? 120 : tier === 2 ? 80 : 45
  const colors = tier === 3
    ? ['#f43f5e','#ec4899','#a855f7','#8b5cf6','#f59e0b','#22d3ee','#34d399','#fbbf24']
    : ['#a855f7','#ec4899','#f59e0b','#8b5cf6','#f43f5e','#22d3ee','#34d399']
  const pieces = Array.from({ length: count }, () => ({
    x: window.innerWidth / 2 + (Math.random() - 0.5) * 200,
    y: window.innerHeight / 2,
    vx: (Math.random() - 0.5) * (tier === 3 ? 24 : 16),
    vy: -Math.random() * (tier === 3 ? 24 : 18) - 4,
    w: Math.random() * 8 + 4, h: Math.random() * 6 + 2,
    color: colors[Math.floor(Math.random() * colors.length)],
    rot: Math.random() * Math.PI * 2, rv: (Math.random() - 0.5) * 0.3,
    gravity: 0.4 + Math.random() * 0.2,
  }))
  let frame = 0
  const maxFrames = tier === 3 ? 120 : 90
  const animate = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    let alive = false
    for (const p of pieces) {
      p.x += p.vx; p.vy += p.gravity; p.y += p.vy; p.rot += p.rv; p.vx *= 0.98
      if (p.y < window.innerHeight + 50) {
        alive = true; ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot)
        ctx.fillStyle = p.color; ctx.globalAlpha = Math.max(0, 1 - frame / maxFrames)
        ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h); ctx.restore()
      }
    }
    frame++
    if (alive && frame < maxFrames) requestAnimationFrame(animate)
    else canvas.remove()
  }
  requestAnimationFrame(animate)
}

/* ── Sound (Web Audio API) ── */
let audioCtx = null
function getAudioCtx() {
  if (!audioCtx) { try { audioCtx = new (window.AudioContext || window.webkitAudioContext)() } catch { return null } }
  return audioCtx
}
function playTick(pitch = 800) {
  const ctx = getAudioCtx(); if (!ctx) return
  const osc = ctx.createOscillator(), gain = ctx.createGain()
  osc.connect(gain); gain.connect(ctx.destination)
  osc.frequency.value = pitch; osc.type = 'sine'; gain.gain.value = 0.04
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.06)
  osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.06)
}
function playReveal(tier = 1) {
  const ctx = getAudioCtx(); if (!ctx) return
  const notes = tier === 3 ? [523,659,784,1047] : tier === 2 ? [523,659,784] : [523,659]
  notes.forEach((freq, i) => {
    const osc = ctx.createOscillator(), gain = ctx.createGain()
    osc.connect(gain); gain.connect(ctx.destination)
    osc.frequency.value = freq; osc.type = 'sine'; gain.gain.value = 0.06
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15 * (i + 1) + 0.2)
    osc.start(ctx.currentTime + 0.12 * i); osc.stop(ctx.currentTime + 0.12 * i + 0.25)
  })
}
function haptic(pattern) { try { if (navigator.vibrate) navigator.vibrate(pattern) } catch { /* */ } }

/* ─────────────────────────────────────────────
   CHALLENGES
   ───────────────────────────────────────────── */
const CHALLENGES = [
  // ── MAKE SOMETHING ──
  { text: 'Design a national flag for your apartment. Present the symbolism to someone with a straight face.', tags: ['solo','free','indoor'], emoji: '🏴', vibe: 'unhinged', tier: 2 },
  { text: 'Build a tiny museum exhibit for the most interesting object in your junk drawer. Write a plaque.', tags: ['solo','free','indoor'], emoji: '🏛️', vibe: 'genius', tier: 2 },
  { text: 'Create an IKEA-style instruction manual for something you do every day. Illustrate it.', tags: ['solo','free','indoor'], emoji: '📐', vibe: 'genius', tier: 2 },
  { text: 'Draw a self-portrait using only your non-dominant hand. Frame it. Hang it up. Don\'t explain.', tags: ['solo','free','indoor'], emoji: '🎨', vibe: 'genius', tier: 1 },
  { text: 'Write your morning routine as a heist movie script. Cast your friends in the roles.', tags: ['solo','free','indoor'], emoji: '🎬', vibe: 'genius', tier: 2 },
  { text: 'Film yourself eating a meal in complete silence, then dub over it with Gordon Ramsay-level commentary.', tags: ['solo','free','indoor'], emoji: '🍽️', vibe: 'unhinged', tier: 1 },
  { text: 'Build a time capsule in a shoebox. Include something from today that will confuse future you.', tags: ['solo','free','indoor'], emoji: '📦', vibe: 'wholesome', tier: 2 },
  { text: 'Cook a meal from a cuisine you\'ve never tried using only YouTube tutorials in that language. No subtitles.', tags: ['solo','paid','indoor'], emoji: '🧑‍🍳', vibe: 'genius', tier: 2 },
  { text: 'Create a Wikipedia article for your friend group. Include the "controversies" section.', tags: ['group','free','indoor'], emoji: '📰', vibe: 'unhinged', tier: 2 },
  { text: 'Map your home from memory. Label the danger zones, the vibes, the contested territories.', tags: ['solo','free','indoor'], emoji: '🗺️', vibe: 'genius', tier: 1 },
  { text: 'Invent a cocktail with only what you have right now. Name it something absurdly dramatic.', tags: ['solo','free','indoor'], emoji: '🍹', vibe: 'unhinged', tier: 1 },
  { text: 'Recreate a famous painting with stuff from your kitchen. Side by side photo. Frame both.', tags: ['solo','free','indoor'], emoji: '🖼️', vibe: 'genius', tier: 2 },
  { text: 'Build a website for something that doesn\'t need one. Your cat. A specific chair. That one drawer.', tags: ['solo','free','indoor'], emoji: '💻', vibe: 'unhinged', tier: 2 },
  { text: 'Build something useless out of cardboard. Give it a product name, a tagline, and a fake Amazon listing.', tags: ['solo','free','indoor'], emoji: '📦', vibe: 'unhinged', tier: 2 },
  { text: 'Photograph your entire fridge. Write Michelin-star descriptions for every item. Post the gallery.', tags: ['solo','free','indoor'], emoji: '🧊', vibe: 'unhinged', tier: 1 },
  { text: 'Learn a card trick. Perform it badly at a dinner party. Refuse to acknowledge it failed.', tags: ['solo','free','indoor'], emoji: '🃏', vibe: 'unhinged', tier: 1 },
  { text: 'Cook the most complex recipe you can find. Film every failure. Post only the final plate.', tags: ['solo','paid','indoor'], emoji: '👨‍🍳', vibe: 'genius', tier: 3 },

  // ── GO SOMEWHERE ──
  { text: 'Sit on a park bench and write a one-paragraph biography for every person who walks by.', tags: ['solo','free','outdoor'], emoji: '📝', vibe: 'genius', tier: 1 },
  { text: 'Find the most architecturally ugly building near you. Write it a love letter. Photograph both.', tags: ['solo','free','outdoor'], emoji: '🏢', vibe: 'unhinged', tier: 2 },
  { text: 'Take a photo walk but only shoot reflections. Post the series.', tags: ['solo','free','outdoor'], emoji: '📸', vibe: 'genius', tier: 1 },
  { text: 'Go to a café you\'ve never been to. Sit at the bar. Sketch everyone from memory after you leave.', tags: ['solo','paid','outdoor'], emoji: '✏️', vibe: 'genius', tier: 1 },
  { text: 'Go to a bookstore. Read only the first sentence of 20 books. Crown a winner.', tags: ['solo','free','outdoor'], emoji: '📖', vibe: 'genius', tier: 1 },
  { text: 'Ride a random bus to the last stop. Document everything like you\'re a travel vlogger in a foreign country.', tags: ['solo','paid','outdoor'], emoji: '🚌', vibe: 'genius', tier: 3 },
  { text: 'Go to a museum. Pick one painting. Sit with it for 15 minutes. Write down what it told you.', tags: ['solo','paid','indoor'], emoji: '🖼️', vibe: 'genius', tier: 2 },
  { text: 'Buy a disposable camera. Use all 27 shots in one day. Develop them next month. No previews.', tags: ['solo','paid','outdoor'], emoji: '📷', vibe: 'genius', tier: 3 },
  { text: 'Find a viewpoint you can walk to. Go at golden hour. Take one photo. Make it your wallpaper for a month.', tags: ['solo','free','outdoor'], emoji: '🌇', vibe: 'wholesome', tier: 1 },
  { text: 'Take a photo of something completely ordinary every day for a week. See if your eye changes.', tags: ['solo','free','outdoor'], emoji: '📱', vibe: 'genius', tier: 2 },
  { text: 'Pick a direction. Walk for exactly 30 minutes. Whatever you find, eat lunch there. No GPS.', tags: ['solo','paid','outdoor'], emoji: '🧭', vibe: 'genius', tier: 1 },
  { text: 'Go to a train station. Let a coin flip decide which train you take. Spend the day wherever it goes.', tags: ['solo','paid','outdoor'], emoji: '🚂', vibe: 'genius', tier: 3 },
  { text: 'Pick a random address on Google Maps in another country. Learn everything about that exact spot.', tags: ['solo','free','indoor'], emoji: '🌍', vibe: 'genius', tier: 2 },

  // ── WITH PEOPLE ──
  { text: 'Build a blanket fort. No phones inside. Talk like it\'s 2005.', tags: ['group','free','indoor'], emoji: '🏰', vibe: 'wholesome', tier: 1 },
  { text: 'Each person pitches a business that should absolutely not exist. The worst idea wins.', tags: ['group','free','indoor'], emoji: '💼', vibe: 'unhinged', tier: 1 },
  { text: 'Cook a meal where each person controls one ingredient. No communication allowed.', tags: ['group','free','indoor'], emoji: '🍳', vibe: 'genius', tier: 2 },
  { text: 'Write and perform a 3-minute play about something that actually happened to the group.', tags: ['group','free','indoor'], emoji: '🎭', vibe: 'genius', tier: 3 },
  { text: 'Everyone teaches the group one skill in exactly 5 minutes. Timer is strict. No mercy.', tags: ['group','free','indoor'], emoji: '⏱️', vibe: 'genius', tier: 1 },
  { text: 'Do a photo walk. Same subject, everyone shoots it differently. Compare. Crown a winner.', tags: ['group','free','outdoor'], emoji: '📸', vibe: 'genius', tier: 1 },
  { text: 'Pick a random spot on a map. Everyone races to get there by different routes. Meet for food after.', tags: ['group','free','outdoor'], emoji: '🗺️', vibe: 'unhinged', tier: 3 },
  { text: 'Film a 60-second mockumentary about a completely normal park. Narrate like it\'s the Amazon.', tags: ['group','free','outdoor'], emoji: '🎥', vibe: 'genius', tier: 2 },
  { text: 'Go thrift shopping. $5 budget. Find the most thoughtful gift for the person next to you.', tags: ['group','paid','outdoor'], emoji: '🎁', vibe: 'wholesome', tier: 1 },
  { text: 'Everyone buys one weird ingredient. You have 1 hour to make it into an actual meal. Document it.', tags: ['group','paid','indoor'], emoji: '🛒', vibe: 'genius', tier: 2 },
  { text: 'Host a movie night for films nobody has heard of. Serve snacks that match each film\'s vibe.', tags: ['group','paid','indoor'], emoji: '🎬', vibe: 'genius', tier: 2 },
  { text: 'Watch a movie in a language nobody speaks. No subtitles. Everyone writes their version of the plot.', tags: ['group','free','indoor'], emoji: '📺', vibe: 'unhinged', tier: 1 },
  { text: 'Enter a competition none of you have any business being in. Document the journey.', tags: ['group','paid','outdoor'], emoji: '🏅', vibe: 'genius', tier: 3 },

  // ── DO GOOD ──
  { text: 'Bake cookies. Knock on a neighbor\'s door. Just say "these are for you." Leave.', tags: ['solo','charity','outdoor','paid'], emoji: '🍪', vibe: 'wholesome', tier: 1 },
  { text: 'Organize a skill swap — teach someone to cook, learn guitar in return. Film the contrast.', tags: ['group','charity','indoor','free'], emoji: '🔄', vibe: 'genius', tier: 2 },
  { text: 'Fill a backpack with essentials. Give it to someone who needs it. Include a handwritten note.', tags: ['solo','charity','outdoor','paid'], emoji: '🎒', vibe: 'wholesome', tier: 2 },
  { text: 'Organize a "pay what you can" neighborhood dinner. Everyone brings one dish.', tags: ['group','charity','outdoor','free'], emoji: '🍛', vibe: 'genius', tier: 3 },
  { text: 'Leave a $5 bill tucked into chapter one of a children\'s book at a bookstore.', tags: ['solo','charity','outdoor','paid'], emoji: '💵', vibe: 'genius', tier: 1 },
  { text: 'Interview your oldest living relative about their life. Record it. Keep it forever.', tags: ['solo','charity','indoor','free'], emoji: '🎙️', vibe: 'wholesome', tier: 2 },

  // ── SAVE THE PLANET ──
  { text: 'Do a 15-minute trash pickup in your neighborhood. Photograph the haul. Make people feel things.', tags: ['solo','eco','outdoor','free'], emoji: '🗑️', vibe: 'genius', tier: 1 },
  { text: 'Build a bird feeder from a milk carton. Paint it. Give it an address number. Welcome tenants.', tags: ['solo','eco','outdoor','free'], emoji: '🐦', vibe: 'genius', tier: 2 },
  { text: 'Plant a tree. Take a photo with it. Take the same photo every year. Watch you both change.', tags: ['solo','eco','outdoor','paid'], emoji: '🌳', vibe: 'wholesome', tier: 2 },
  { text: 'Organize a beach cleanup. Turn the best trash finds into an art installation. Title each piece.', tags: ['group','eco','outdoor','free'], emoji: '🏖️', vibe: 'genius', tier: 3 },
  { text: 'Repair something you were about to throw away. Film the process. Post it as oddly satisfying content.', tags: ['solo','eco','indoor','free'], emoji: '🔧', vibe: 'genius', tier: 1 },
  { text: 'Set up a Little Free Library. Stock it with your favorites. Add handwritten reviews inside each.', tags: ['group','eco','outdoor','paid'], emoji: '📚', vibe: 'genius', tier: 3 },
  { text: 'Pick one single-use item you buy weekly. Find a reusable version. Use it for a month. Report back.', tags: ['solo','eco','indoor','paid'], emoji: '♻️', vibe: 'genius', tier: 2 },

  // ── GO DEEP ──
  { text: 'Call someone you haven\'t talked to in a year. Don\'t explain why. Just ask how they are.', tags: ['solo','free','indoor'], emoji: '📞', vibe: 'wholesome', tier: 1 },
  { text: 'Pick a skill you were obsessed with as a kid. Spend an afternoon getting back into it. See what stuck.', tags: ['solo','free','indoor'], emoji: '🧩', vibe: 'wholesome', tier: 2 },
  { text: 'Take a pottery class. Make something hideous. Love it unconditionally. Display it prominently.', tags: ['solo','paid','indoor'], emoji: '🏺', vibe: 'wholesome', tier: 2 },
  { text: 'Learn to cook one dish from your grandparents\' culture. Call them for the recipe. Record the call.', tags: ['solo','paid','indoor'], emoji: '🍲', vibe: 'wholesome', tier: 2 },
  { text: 'Go to a restaurant alone. Order the chef\'s favorite, not yours. Trust the universe.', tags: ['solo','paid','outdoor'], emoji: '🍽️', vibe: 'genius', tier: 1 },
  { text: 'Walk into a grocery store. Buy only things you\'ve never tried. Cook a mystery dinner. Rate it.', tags: ['solo','paid','indoor'], emoji: '🛒', vibe: 'genius', tier: 2 },
  { text: 'Learn to solve a Rubik\'s cube this week. Time yourself. Beat your own record. Post the final time.', tags: ['solo','paid','indoor'], emoji: '🧊', vibe: 'genius', tier: 2 },
  { text: 'Spend a full day without your phone. Write about what you noticed by the end.', tags: ['solo','free','outdoor'], emoji: '🌿', vibe: 'genius', tier: 2 },
  { text: 'Take an ice-cold shower every morning for a week. Journal one sentence each time. Post the arc.', tags: ['solo','free','indoor'], emoji: '🥶', vibe: 'genius', tier: 2 },

  // ── PURE AUDACITY ──
  { text: 'Learn one song on an instrument you don\'t play. Perform it at a dinner. Accept all applause.', tags: ['solo','paid','indoor'], emoji: '🎸', vibe: 'genius', tier: 3 },
  { text: 'Go to a coffee shop. Write a short story in one sitting. Leave it folded on the table when you go.', tags: ['solo','paid','outdoor'], emoji: '✍️', vibe: 'genius', tier: 2 },
  { text: 'Set an alarm for 3am. Watch the sunrise. Make it the most intentional thing you do this month.', tags: ['solo','free','outdoor'], emoji: '🌅', vibe: 'genius', tier: 2 },
  { text: 'Make a zine about something hyper-specific you care about. Staple 10 copies. Distribute them.', tags: ['solo','paid','indoor'], emoji: '📰', vibe: 'genius', tier: 3 },
  { text: 'Go to a flea market with $10. Buy the one thing that tells the best story. Frame it. Write the story.', tags: ['solo','paid','outdoor'], emoji: '🪆', vibe: 'genius', tier: 1 },
  { text: 'Text everyone in your recent contacts a memory you have with them. No context. Just the memory.', tags: ['solo','free','indoor'], emoji: '💭', vibe: 'wholesome', tier: 2 },
  { text: 'Go to a farmer\'s market. Buy exactly one of the strangest thing there. Cook dinner around it.', tags: ['solo','paid','outdoor'], emoji: '🥬', vibe: 'genius', tier: 1 },
  { text: 'Wear something you\'ve been saving "for a special occasion." Today is the occasion. You decided.', tags: ['solo','free','indoor'], emoji: '👔', vibe: 'genius', tier: 1 },
  { text: 'Commission a caricature of yourself. Use it as your LinkedIn photo for a week. Commit fully.', tags: ['solo','paid','outdoor'], emoji: '🎪', vibe: 'unhinged', tier: 3 },
  { text: 'Film a 10-second timelapse of something you do every day. Post it with zero context.', tags: ['solo','free','indoor'], emoji: '⏩', vibe: 'genius', tier: 1 },
  { text: 'Hand-letter a lyric that\'s been stuck in your head all week. Give it to someone who\'d get it.', tags: ['solo','free','indoor'], emoji: '✒️', vibe: 'wholesome', tier: 1 },
]

/* ── Config ── */
const FILTER_GROUPS = [
  { label: 'Who', options: [{ key: 'solo', label: 'Solo', icon: '🧑' }, { key: 'group', label: 'Crew', icon: '👥' }] },
  { label: 'Where', options: [{ key: 'indoor', label: 'Indoor', icon: '🏠' }, { key: 'outdoor', label: 'Outside', icon: '☀️' }] },
  { label: 'Cost', options: [{ key: 'free', label: 'Free', icon: '✌️' }, { key: 'paid', label: 'Worth it', icon: '💸' }] },
  { label: 'Vibe', options: [{ key: 'charity', label: 'Kind', icon: '❤️' }, { key: 'eco', label: 'Eco', icon: '🌍' }] },
]
const TIER_FILTERS = [{ key: 1, label: '5 min', icon: '⚡' }, { key: 2, label: '1 hour', icon: '⏰' }, { key: 3, label: 'Epic', icon: '🌟' }]

const VIBE_META = {
  unhinged: { gradient: 'from-rose-500 via-pink-500 to-fuchsia-600', glow: 'rgba(244,63,94,0.35)', badge: '🫠 unhinged', bg: 'from-rose-500/15 to-fuchsia-500/15', border: 'border-rose-500/25', canvasBg: ['#1a0a1e','#2d0a1e'], canvasAccent: '#f43f5e' },
  genius: { gradient: 'from-violet-500 via-purple-500 to-indigo-600', glow: 'rgba(139,92,246,0.35)', badge: '🧠 genius', bg: 'from-violet-500/15 to-indigo-500/15', border: 'border-violet-500/25', canvasBg: ['#0f0a2e','#1a0a2e'], canvasAccent: '#8b5cf6' },
  wholesome: { gradient: 'from-amber-400 via-orange-400 to-yellow-500', glow: 'rgba(251,191,36,0.35)', badge: '🥹 wholesome', bg: 'from-amber-500/15 to-yellow-500/15', border: 'border-amber-500/25', canvasBg: ['#1e1405','#1e1a05'], canvasAccent: '#fbbf24' },
}
const TIER_META = {
  1: { label: 'right now', color: 'text-emerald-400', border: 'border-emerald-500/20', desc: '5 min or less' },
  2: { label: 'commit to it', color: 'text-amber-400', border: 'border-amber-500/20', desc: 'set aside an hour' },
  3: { label: 'life event', color: 'text-rose-400', border: 'border-rose-500/20', desc: 'this becomes a story' },
}
const SPIN_WORDS = ['Consulting the multiverse…','Channeling chaotic good…','Loading free will.exe…','Rolling the existential dice…','Calibrating spontaneity…','Summoning audacity…','Contacting your future self…']
const SLOT_EMOJIS = ['🎲','✨','🌟','💫','🎯','🔮','🎪','🚀','⚡','🌈','🦋','🌀','💥','🫧','🪄']

function getDailyChallenge() {
  const d = new Date()
  const seed = d.getFullYear() * 10000 + (d.getMonth() + 1) * 100 + d.getDate()
  return CHALLENGES[seed % CHALLENGES.length]
}

const STREAK_MILESTONES = {
  3: { msg: '3 days strong 🔥', emoji: '🔥' },
  7: { msg: 'One whole week ⚡', emoji: '⚡' },
  14: { msg: 'Two weeks 💪', emoji: '💪' },
  30: { msg: '30 days. Legend. 👑', emoji: '👑' },
  100: { msg: '100 days. You are free will. 🏆', emoji: '🏆' },
}

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
      const saved = JSON.parse(localStorage.getItem('fwu-stats') || '{}')
      if (saved.spins) setTotalSpins(saved.spins)
      if (saved.accepted) setAccepted(saved.accepted)
      if (saved.streak) setDayStreak(saved.streak)
      if (saved.lastDay) setLastDay(saved.lastDay)
      if (saved.soundOn === false) setSoundOn(false)
      const today = new Date().toDateString()
      if (saved.lastDay) { const diff = Math.floor((new Date(today) - new Date(saved.lastDay)) / 86400000); if (diff > 1) setDayStreak(0) }
    } catch { /* */ }
  }, [])

  const saveStats = (spins, acc, streak, day) => {
    try { localStorage.setItem('fwu-stats', JSON.stringify({ spins, accepted: acc, streak, lastDay: day, soundOn })) } catch { /* */ }
  }
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
    const totalTicks = 18
    const scheduleTick = () => {
      if (tick >= totalTicks) return
      const delay = 50 + tick * 12 + (tick > 12 ? (tick - 12) * 30 : 0)
      spinRef.current = setTimeout(() => {
        setSlotEmoji(SLOT_EMOJIS[Math.floor(Math.random() * SLOT_EMOJIS.length)])
        if (soundOn) playTick(600 + tick * 30); haptic(20); tick++; scheduleTick()
      }, delay)
    }
    scheduleTick()
    setTimeout(() => {
      const pick = pool[Math.floor(Math.random() * pool.length)]
      setCurrent(pick); setSlotEmoji(pick.emoji); setIsSpinning(false)
      setHistory(prev => [pick, ...prev.filter(h => h.text !== pick.text)].slice(0, 12))
      fireConfetti(pick.tier); if (soundOn) playReveal(pick.tier)
      haptic(pick.tier === 3 ? [100,50,100,50,200] : pick.tier === 2 ? [60,40,100] : 80)
      const newSpins = totalSpins + 1; setTotalSpins(newSpins)
      const today = new Date().toDateString()
      let newStreak = dayStreak
      if (lastDay !== today) {
        const diff = lastDay ? Math.floor((new Date(today) - new Date(lastDay)) / 86400000) : 999
        newStreak = diff <= 1 ? dayStreak + 1 : 1; setDayStreak(newStreak); setLastDay(today)
        if (STREAK_MILESTONES[newStreak]) { setStreakMilestone(STREAK_MILESTONES[newStreak]); setTimeout(() => setStreakMilestone(null), 3500) }
      }
      saveStats(newSpins, accepted, newStreak, today)
    }, 1600)
  }, [getPool, totalSpins, accepted, dayStreak, lastDay, soundOn])

  useEffect(() => () => { if (spinRef.current) clearTimeout(spinRef.current) }, [])

  const acceptChallenge = () => {
    if (challengeAccepted) return
    setChallengeAccepted(true); const newAcc = accepted + 1; setAccepted(newAcc)
    saveStats(totalSpins, newAcc, dayStreak, lastDay); if (soundOn) playReveal(1); haptic(60)
  }

  const vibe = current ? VIBE_META[current.vibe] : null
  const tier = current ? TIER_META[current.tier] : null
  const dayLabel = dayStreak > 0 ? `Day ${dayStreak} of using my free will:` : 'Today I chose to:'
  const shareText = current ? `${dayLabel}\n\n${current.text}\n\namazing use of free will ✦\n#amazinguseoffreewill` : ''
  const tweetUrl = () => `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}`
  const whatsappUrl = () => `https://wa.me/?text=${encodeURIComponent(shareText)}`
  const copyText = async () => { try { await navigator.clipboard.writeText(shareText); setCopied(true); setTimeout(() => setCopied(false), 2200) } catch { /* */ } }

  const downloadShareCard = useCallback(() => {
    if (!current) return
    const v = VIBE_META[current.vibe], t = TIER_META[current.tier]
    const W = 1080, H = 1350, c = document.createElement('canvas')
    c.width = W; c.height = H; const ctx = c.getContext('2d')
    const bg = ctx.createLinearGradient(0, 0, W, H)
    bg.addColorStop(0, v.canvasBg[0]); bg.addColorStop(1, v.canvasBg[1])
    ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H)
    // grid
    ctx.strokeStyle = 'rgba(255,255,255,0.015)'; ctx.lineWidth = 1
    for (let x = 0; x < W; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke() }
    for (let y = 0; y < H; y += 40) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke() }
    // glow
    const grd = ctx.createRadialGradient(W / 2, H * 0.36, 0, W / 2, H * 0.36, 420)
    grd.addColorStop(0, v.glow); grd.addColorStop(0.6, v.glow.replace('0.35', '0.08')); grd.addColorStop(1, 'transparent')
    ctx.fillStyle = grd; ctx.fillRect(0, 0, W, H)
    // text
    ctx.textAlign = 'center'
    ctx.fillStyle = 'rgba(255,255,255,0.25)'; ctx.font = '500 18px system-ui, sans-serif'
    ctx.fillText('✦  FREE WILL UTILIZER  ✦', W / 2, 70)
    ctx.fillStyle = 'rgba(255,255,255,0.45)'; ctx.font = '400 26px system-ui, sans-serif'
    ctx.fillText(dayStreak > 0 ? `Day ${dayStreak}` : 'Today I chose to:', W / 2, 120)
    ctx.font = '140px serif'; ctx.fillText(current.emoji, W / 2, H * 0.3 + 20)
    ctx.fillStyle = '#f5f5f5'; ctx.font = 'bold 44px system-ui, sans-serif'
    const words = current.text.split(' '); let lines = [], line = ''
    for (const w of words) { const test = line ? line + ' ' + w : w; if (ctx.measureText(test).width > W - 180) { lines.push(line); line = w } else line = test }
    if (line) lines.push(line)
    lines.forEach((l, i) => ctx.fillText(l, W / 2, H * 0.43 + i * 60))
    const badgeY = H * 0.43 + lines.length * 60 + 45
    ctx.fillStyle = 'rgba(255,255,255,0.35)'; ctx.font = '500 24px system-ui, sans-serif'
    ctx.fillText(`${v.badge}  ·  ${t.label}`, W / 2, badgeY)
    ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(W * 0.15, H * 0.74); ctx.lineTo(W * 0.85, H * 0.74); ctx.stroke()
    ctx.fillStyle = '#d4d4d4'; ctx.font = 'italic 36px Georgia, serif'
    ctx.fillText('"amazing use of free will"', W / 2, H * 0.74 + 65)
    ctx.fillStyle = 'rgba(255,255,255,0.2)'; ctx.font = '400 20px system-ui, sans-serif'
    ctx.fillText('#amazinguseoffreewill', W / 2, H - 65)
    const link = document.createElement('a'); link.download = 'amazing-use-of-free-will.png'
    link.href = c.toDataURL('image/png'); link.click()
  }, [current, dayStreak])

  const dailyVibe = VIBE_META[daily.vibe], dailyTier = TIER_META[daily.tier]

  /* ── noise texture data URI ── */
  const noiseUrl = "data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E"

  return (
    <div className="min-h-screen bg-[#060609] text-neutral-100 overflow-x-hidden selection:bg-purple-500/30">
      {/* Ambient bg + noise */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-48 -left-48 w-[600px] h-[600px] bg-purple-600/[0.04] rounded-full blur-[150px]" />
        <div className="absolute top-1/2 -right-32 w-[400px] h-[400px] bg-rose-600/[0.03] rounded-full blur-[150px]" />
        <div className="absolute -bottom-32 left-1/4 w-80 h-80 bg-amber-600/[0.025] rounded-full blur-[120px]" />
        <div className="absolute inset-0" style={{ backgroundImage: `url("${noiseUrl}")`, backgroundRepeat: 'repeat', opacity: 0.5, mixBlendMode: 'overlay' }} />
      </div>

      {/* Streak milestone toast */}
      {streakMilestone && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50 bg-white/[0.08] backdrop-blur-xl px-6 py-3 rounded-2xl shadow-2xl border border-white/[0.1]" style={{ animation: 'card-reveal 0.4s ease' }}>
          <p className="text-sm font-semibold text-white text-center">{streakMilestone.emoji} {streakMilestone.msg}</p>
        </div>
      )}

      <div className="relative z-10 max-w-lg mx-auto px-5">
        {/* ── Header ── */}
        <header className="pt-14 pb-8 text-center">
          <p className="text-[10px] font-medium tracking-[0.35em] uppercase text-neutral-600 mb-5">
            you have free will · might as well use it
          </p>
          <h1 className="text-[2.75rem] sm:text-6xl font-black tracking-[-0.03em] leading-[1] mb-4">
            <span className="bg-gradient-to-r from-neutral-100 via-purple-200 to-neutral-100 bg-clip-text text-transparent">Free Will</span>
            <br />
            <span className="text-neutral-500 text-3xl sm:text-4xl font-bold tracking-[-0.02em]">Utilizer</span>
          </h1>
          <p className="text-[13px] text-neutral-500 max-w-[280px] mx-auto leading-relaxed">
            The kind where people comment<br /><span className="text-neutral-300 italic">&quot;amazing use of free will&quot;</span>
          </p>
        </header>

        {/* Stats */}
        {totalSpins > 0 && (
          <div className="flex items-center justify-center gap-4 mb-6 text-[11px] text-neutral-600 flex-wrap">
            {dayStreak > 0 && <><span className="text-purple-400/80 font-medium">day {dayStreak}</span><span className="w-px h-2.5 bg-neutral-800" /></>}
            <span>{totalSpins} spins</span>
            <span className="w-px h-2.5 bg-neutral-800" />
            <span>{accepted} accepted</span>
            <span className="w-px h-2.5 bg-neutral-800" />
            <span>{Math.round((accepted / Math.max(totalSpins, 1)) * 100)}%</span>
          </div>
        )}

        {/* Daily challenge */}
        {!current && !isSpinning && (
          <section className="mb-6" style={{ animation: 'card-reveal 0.5s ease' }}>
            <button
              onClick={() => { setCurrent(daily); fireConfetti(daily.tier); if (soundOn) playReveal(daily.tier) }}
              className="w-full bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 text-left hover:bg-white/[0.05] transition-all active:scale-[0.99] group"
            >
              <div className="flex items-center gap-3.5">
                <span className="text-2xl">{daily.emoji}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] font-semibold tracking-[0.2em] uppercase text-purple-400/70">Today</span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${dailyTier.border} ${dailyTier.color} bg-white/[0.03]`}>{dailyTier.label}</span>
                  </div>
                  <p className="text-sm text-neutral-400 leading-snug truncate group-hover:text-neutral-300 transition-colors">{daily.text}</p>
                </div>
                <span className="text-neutral-700 text-sm group-hover:text-neutral-500 transition-colors">→</span>
              </div>
            </button>
          </section>
        )}

        {/* Filters */}
        <section className="mb-6">
          <button onClick={() => setShowFilters(!showFilters)}
            className="w-full flex items-center justify-between px-4 py-2.5 bg-white/[0.02] border border-white/[0.04] rounded-xl text-xs text-neutral-600 hover:bg-white/[0.04] transition-all">
            <span className="flex items-center gap-2">
              <span className="text-[10px] font-medium tracking-[0.15em] uppercase">
                {anyFilterActive ? `${poolSize} matches` : 'Filter'}
              </span>
              {anyFilterActive && <button onClick={(e) => { e.stopPropagation(); setActiveFilters(new Set()); setTierFilter(null) }} className="text-[10px] text-neutral-700 hover:text-neutral-400 underline ml-1">clear</button>}
            </span>
            <span className={`text-neutral-700 transition-transform text-[10px] ${showFilters ? 'rotate-180' : ''}`}>▾</span>
          </button>
          {showFilters && (
            <div className="mt-2 bg-white/[0.02] border border-white/[0.04] rounded-2xl p-4 backdrop-blur-sm" style={{ animation: 'card-reveal 0.2s ease' }}>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
                {FILTER_GROUPS.map(g => (
                  <div key={g.label} className="space-y-1.5">
                    <div className="text-[10px] font-medium text-neutral-600 pl-0.5">{g.label}</div>
                    {g.options.map(o => {
                      const on = activeFilters.has(o.key)
                      return <button key={o.key} onClick={() => toggleFilter(o.key)} className={`w-full flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium transition-all ${on ? 'bg-purple-500/10 border border-purple-400/20 text-purple-300' : 'bg-white/[0.02] border border-white/[0.04] text-neutral-600 hover:bg-white/[0.04] hover:text-neutral-400'}`}>
                        <span className="text-sm">{o.icon}</span><span>{o.label}</span>
                      </button>
                    })}
                  </div>
                ))}
              </div>
              <div className="border-t border-white/[0.03] pt-3">
                <div className="text-[10px] font-medium text-neutral-600 pl-0.5 mb-1.5">Time</div>
                <div className="flex gap-2">
                  {TIER_FILTERS.map(t => (
                    <button key={t.key} onClick={() => setTierFilter(tierFilter === t.key ? null : t.key)}
                      className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium transition-all ${tierFilter === t.key ? 'bg-purple-500/10 border border-purple-400/20 text-purple-300' : 'bg-white/[0.02] border border-white/[0.04] text-neutral-600 hover:bg-white/[0.04]'}`}>
                      <span>{t.icon}</span><span>{t.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </section>

        {/* ── Main card ── */}
        <section className="mb-6">
          {/* Gradient border wrapper */}
          <div className="rounded-[1.75rem] p-[1px]" style={{
            background: current && !isSpinning
              ? `linear-gradient(135deg, ${vibe.canvasAccent}33, transparent 40%, transparent 60%, ${vibe.canvasAccent}22)`
              : isSpinning
              ? 'linear-gradient(135deg, rgba(168,85,247,0.15), transparent 40%, transparent 60%, rgba(168,85,247,0.1))'
              : 'linear-gradient(135deg, rgba(255,255,255,0.04), transparent 40%, transparent 60%, rgba(255,255,255,0.02))',
          }}>
            <div
              onClick={!current && !isSpinning ? spin : undefined}
              className={`relative rounded-[calc(1.75rem-1px)] min-h-[300px] sm:min-h-[360px] flex flex-col items-center justify-center p-8 sm:p-10 text-center transition-all duration-700 ${
                !current && !isSpinning ? 'cursor-pointer hover:bg-white/[0.02]' : ''
              }`}
              style={{
                background: current && !isSpinning
                  ? `radial-gradient(ellipse at 50% 30%, ${vibe.glow.replace('0.35','0.08')}, transparent 70%), #0a0a10`
                  : '#0a0a10',
                animation: shakeCard ? 'shake 0.6s ease' : isSpinning ? 'pulse-glow 0.35s ease infinite alternate' : 'none',
              }}
            >
              {isSpinning ? (
                <div className="flex flex-col items-center gap-5">
                  <div className="text-7xl sm:text-8xl" style={{ animation: 'spin-wobble 0.4s ease infinite', filter: 'blur(0.5px)' }}>{slotEmoji}</div>
                  <div className="flex gap-1.5">
                    {[0,1,2,3].map(i => <div key={i} className="w-1 h-1 rounded-full bg-purple-400/50" style={{ animation: `dot-bounce 0.5s ease ${i * 0.1}s infinite alternate` }} />)}
                  </div>
                  <p className="text-xs text-neutral-600 italic">{spinWord}</p>
                </div>
              ) : current ? (
                <div className="flex flex-col items-center gap-5" style={{ animation: 'card-reveal 0.6s cubic-bezier(0.16,1,0.3,1)' }}>
                  <div className="text-6xl sm:text-7xl">{current.emoji}</div>
                  <p className="text-lg sm:text-xl font-semibold leading-snug text-neutral-100 max-w-sm tracking-[-0.01em]">
                    {current.text}
                  </p>
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-medium tracking-wide px-2.5 py-1 rounded-full bg-white/[0.04] border ${vibe.border} text-neutral-500`}>{vibe.badge}</span>
                    <span className={`text-[10px] font-medium tracking-wide px-2.5 py-1 rounded-full bg-white/[0.04] border ${tier.border} ${tier.color}`}>{tier.label}</span>
                  </div>
                  {/* Share */}
                  <div className="flex items-center gap-1.5 mt-1">
                    <a href={tweetUrl()} target="_blank" rel="noopener noreferrer" className="p-2 rounded-full bg-white/[0.04] hover:bg-white/[0.1] transition-all" title="X">
                      <svg className="w-3.5 h-3.5 text-neutral-500" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                    </a>
                    <a href={whatsappUrl()} target="_blank" rel="noopener noreferrer" className="p-2 rounded-full bg-white/[0.04] hover:bg-white/[0.1] transition-all" title="WhatsApp">
                      <svg className="w-3.5 h-3.5 text-neutral-500" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
                    </a>
                    <button onClick={copyText} className="p-2 rounded-full bg-white/[0.04] hover:bg-white/[0.1] transition-all" title="Copy">
                      <span className="text-xs">{copied ? '✓' : '⎘'}</span>
                    </button>
                    <button onClick={downloadShareCard} className="p-2 rounded-full bg-white/[0.04] hover:bg-white/[0.1] transition-all" title="Story card">
                      <span className="text-xs">↓</span>
                    </button>
                    <button onClick={() => { if (typeof navigator !== 'undefined' && navigator.share) navigator.share({ text: shareText }).catch(() => {}) }}
                      className="p-2 rounded-full bg-white/[0.04] hover:bg-white/[0.1] transition-all sm:hidden" title="Share">
                      <span className="text-xs">↗</span>
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-4">
                  <div className="text-6xl" style={{ animation: 'float 3s ease-in-out infinite' }}>🎲</div>
                  <p className="text-[15px] text-neutral-500 font-medium">Tap to use your free will</p>
                  <p className="text-[11px] text-neutral-700">{poolSize} challenges</p>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* Buttons */}
        <div className="flex flex-col items-center gap-3 mb-8">
          <button onClick={spin} disabled={isSpinning}
            className={`w-full py-4 rounded-2xl font-semibold text-[15px] tracking-[-0.01em] transition-all duration-300 ${
              isSpinning ? 'bg-white/[0.03] text-neutral-700 cursor-wait'
              : poolSize === 0 ? 'bg-white/[0.03] text-neutral-700 cursor-not-allowed'
              : 'bg-white/[0.06] border border-white/[0.08] text-neutral-200 hover:bg-white/[0.1] hover:border-white/[0.12] active:scale-[0.98] shadow-[0_0_30px_rgba(168,85,247,0.06)]'
            }`}>
            {isSpinning ? 'Spinning…' : current ? 'Spin again' : poolSize === 0 ? 'No matches' : 'Use your free will'}
          </button>
          {current && !isSpinning && (
            <button onClick={acceptChallenge}
              className={`px-6 py-2.5 rounded-xl text-sm font-medium transition-all active:scale-[0.97] ${
                challengeAccepted ? 'bg-emerald-500/10 border border-emerald-400/20 text-emerald-400'
                : 'bg-white/[0.03] border border-white/[0.06] text-neutral-500 hover:bg-white/[0.06] hover:text-neutral-300'
              }`} style={{ animation: 'card-reveal 0.3s ease' }}>
              {challengeAccepted ? '✓ Accepted' : 'Accept challenge'}
            </button>
          )}
          <button onClick={() => { setSoundOn(!soundOn); try { localStorage.setItem('fwu-stats', JSON.stringify({ spins: totalSpins, accepted, streak: dayStreak, lastDay, soundOn: !soundOn })) } catch { /* */ } }}
            className="text-[10px] text-neutral-800 hover:text-neutral-500 transition">
            {soundOn ? '♪ on' : '♪ off'}
          </button>
        </div>

        {/* History */}
        {history.length > 1 && (
          <section className="mb-10">
            <p className="text-[10px] font-medium tracking-[0.2em] uppercase text-neutral-700 mb-3">Previous</p>
            <div className="space-y-1">
              {history.slice(1).map((item, i) => (
                <button key={item.text} onClick={() => { setCurrent(item); setChallengeAccepted(false) }}
                  className="w-full flex items-center gap-3 px-3 py-2 rounded-xl bg-white/[0.01] border border-white/[0.02] text-sm text-neutral-600 text-left hover:bg-white/[0.03] transition-colors"
                  style={{ opacity: 1 - i * 0.08 }}>
                  <span className="text-sm flex-shrink-0">{item.emoji}</span>
                  <span className="truncate flex-1">{item.text}</span>
                </button>
              ))}
            </div>
          </section>
        )}

        {/* Footer */}
        <footer className="pb-14 text-center border-t border-white/[0.02] pt-8">
          <p className="text-[11px] text-neutral-700 leading-relaxed max-w-[260px] mx-auto">
            ~2.5 billion seconds in a life. You just used one to decide how to spend the next few thousand.
          </p>
        </footer>
      </div>

      <style jsx>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0) rotate(0); }
          15% { transform: translateX(-8px) rotate(-1.5deg); }
          30% { transform: translateX(8px) rotate(1.5deg); }
          45% { transform: translateX(-4px) rotate(-0.5deg); }
          60% { transform: translateX(4px) rotate(0.5deg); }
        }
        @keyframes card-reveal {
          from { opacity: 0; transform: translateY(12px) scale(0.98); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes pulse-glow {
          from { box-shadow: 0 0 20px rgba(168, 85, 247, 0.04); }
          to { box-shadow: 0 0 50px rgba(168, 85, 247, 0.12); }
        }
        @keyframes dot-bounce {
          from { transform: translateY(0); opacity: 0.3; }
          to { transform: translateY(-6px); opacity: 1; }
        }
        @keyframes spin-wobble {
          0% { transform: rotate(0) scale(1); }
          25% { transform: rotate(8deg) scale(1.06); }
          50% { transform: rotate(-8deg) scale(0.94); }
          75% { transform: rotate(4deg) scale(1.02); }
          100% { transform: rotate(0) scale(1); }
        }
        @keyframes float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-8px); }
        }
      `}</style>
    </div>
  )
}
