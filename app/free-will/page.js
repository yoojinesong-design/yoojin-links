'use client'
import { useState, useCallback, useEffect, useRef } from 'react'

/* ─────────────────────────────────────────────────────────────
   ACTIVITIES — wildly creative yet genuinely useful.
   The kind of thing where people comment
   "amazing use of free will" on the post.
   ───────────────────────────────────────────────────────────── */
const ACTIVITIES = [
  // Solo + Free + Indoor — Creative chaos
  { text: 'Write a formal resignation letter to a bad habit. Seal it. Burn it.', tags: ['solo', 'free', 'indoor'], emoji: '🔥', vibe: 'unhinged' },
  { text: 'Build a tiny museum exhibit for the most interesting object in your junk drawer', tags: ['solo', 'free', 'indoor'], emoji: '🏛️', vibe: 'genius' },
  { text: 'Write a Yelp review for your own kitchen. Be brutally honest.', tags: ['solo', 'free', 'indoor'], emoji: '⭐', vibe: 'unhinged' },
  { text: 'Design a national flag for your apartment. Explain the symbolism.', tags: ['solo', 'free', 'indoor'], emoji: '🏳️', vibe: 'genius' },
  { text: 'Compose a breakup letter to an app you\'re deleting', tags: ['solo', 'free', 'indoor'], emoji: '💔', vibe: 'unhinged' },
  { text: 'Make an IKEA-style instruction manual for making your bed', tags: ['solo', 'free', 'indoor'], emoji: '📐', vibe: 'genius' },
  { text: 'Create a nature documentary narration of yourself making coffee', tags: ['solo', 'free', 'indoor'], emoji: '🎬', vibe: 'unhinged' },
  { text: 'Draw a map of your home from memory. Include all the danger zones.', tags: ['solo', 'free', 'indoor'], emoji: '🗺️', vibe: 'genius' },
  { text: 'Write a 5-star review of water. It deserves the recognition.', tags: ['solo', 'free', 'indoor'], emoji: '💧', vibe: 'unhinged' },
  { text: 'Make a resume for your pet. List their skills honestly.', tags: ['solo', 'free', 'indoor'], emoji: '📄', vibe: 'genius' },
  { text: 'Rearrange a bookshelf by color and feel emotionally healed', tags: ['solo', 'free', 'indoor'], emoji: '📚', vibe: 'wholesome' },
  { text: 'Draw a self-portrait using only your non-dominant hand. Frame it.', tags: ['solo', 'free', 'indoor'], emoji: '🎨', vibe: 'genius' },
  { text: 'Write a recipe for your current emotional state', tags: ['solo', 'free', 'indoor'], emoji: '🧑‍🍳', vibe: 'unhinged' },
  { text: 'Create a playlist that tells the story of your entire week', tags: ['solo', 'free', 'indoor'], emoji: '🎵', vibe: 'wholesome' },
  { text: 'Write a formal apology to a plant you forgot to water', tags: ['solo', 'free', 'indoor'], emoji: '🌿', vibe: 'unhinged' },
  { text: 'Make a PowerPoint presentation about why your favorite snack is superior', tags: ['solo', 'free', 'indoor'], emoji: '📊', vibe: 'genius' },
  { text: 'Build a time capsule in a shoebox. Open in 5 years.', tags: ['solo', 'free', 'indoor'], emoji: '📦', vibe: 'wholesome' },
  { text: 'Write your morning routine as if it were a heist movie script', tags: ['solo', 'free', 'indoor'], emoji: '🎭', vibe: 'genius' },
  { text: 'Take a photo of every door in your home. Make a gallery.', tags: ['solo', 'free', 'indoor'], emoji: '🚪', vibe: 'genius' },
  { text: 'Invent a cocktail (or mocktail) with only what you have. Name it something dramatic.', tags: ['solo', 'free', 'indoor'], emoji: '🍹', vibe: 'unhinged' },

  // Solo + Free + Outdoor — Beautiful weird
  { text: 'Find a stranger\'s lost glove on the street. Imagine the life it lived.', tags: ['solo', 'free', 'outdoor'], emoji: '🧤', vibe: 'wholesome' },
  { text: 'Sit on a park bench and write a one-page biography for every person who walks by', tags: ['solo', 'free', 'outdoor'], emoji: '📝', vibe: 'genius' },
  { text: 'Find the most architecturally ugly building near you. Write it a love letter.', tags: ['solo', 'free', 'outdoor'], emoji: '🏢', vibe: 'unhinged' },
  { text: 'Take a photo walk but only shoot reflections', tags: ['solo', 'free', 'outdoor'], emoji: '📸', vibe: 'genius' },
  { text: 'Find a tree. Sit under it. Write the tree a thank you note.', tags: ['solo', 'free', 'outdoor'], emoji: '🌳', vibe: 'wholesome' },
  { text: 'Walk until you find something beautiful. Take a photo. Walk home.', tags: ['solo', 'free', 'outdoor'], emoji: '🚶', vibe: 'wholesome' },
  { text: 'Pick a cloud. Name it. Watch your cloud until it changes shape. Mourn it.', tags: ['solo', 'free', 'outdoor'], emoji: '☁️', vibe: 'unhinged' },
  { text: 'Go to a bookstore and read only the first sentence of 20 books. Pick the winner.', tags: ['solo', 'free', 'outdoor'], emoji: '📖', vibe: 'genius' },
  { text: 'Take the scenic route to somewhere boring. See if the journey fixes it.', tags: ['solo', 'free', 'outdoor'], emoji: '🛤️', vibe: 'wholesome' },
  { text: 'Collect 5 interesting leaves. Press them. Start a tiny herbarium.', tags: ['solo', 'free', 'outdoor'], emoji: '🍂', vibe: 'genius' },

  // Solo + Paid
  { text: 'Buy a stranger\'s coffee. Leave before they can thank you.', tags: ['solo', 'paid', 'outdoor'], emoji: '☕', vibe: 'wholesome' },
  { text: 'Go to a thrift store. Buy the weirdest mug you can find. It\'s your personality now.', tags: ['solo', 'paid', 'outdoor'], emoji: '🍵', vibe: 'unhinged' },
  { text: 'Buy flowers for yourself. You\'ve been through a lot.', tags: ['solo', 'paid', 'outdoor'], emoji: '💐', vibe: 'wholesome' },
  { text: 'Go to a restaurant alone. Order the chef\'s favorite, not yours.', tags: ['solo', 'paid', 'outdoor'], emoji: '🍽️', vibe: 'genius' },
  { text: 'Buy a disposable camera. Use all 27 shots today. Develop them next month.', tags: ['solo', 'paid', 'outdoor'], emoji: '📷', vibe: 'genius' },
  { text: 'Take a pottery class. Make something hideous. Love it unconditionally.', tags: ['solo', 'paid', 'indoor'], emoji: '🏺', vibe: 'wholesome' },
  { text: 'Buy a notebook that costs more than you\'d normally spend. Write only important things in it.', tags: ['solo', 'paid', 'indoor'], emoji: '📓', vibe: 'genius' },

  // Group + Free + Indoor — Collaborative chaos
  { text: 'Host an awards ceremony for everyday objects in your house. Acceptance speeches mandatory.', tags: ['group', 'free', 'indoor'], emoji: '🏆', vibe: 'unhinged' },
  { text: 'Everyone draws a portrait of the person to their left. Exhibition opening follows.', tags: ['group', 'free', 'indoor'], emoji: '🖼️', vibe: 'genius' },
  { text: 'Build a blanket fort. No phones allowed inside. Talk like it\'s 2005.', tags: ['group', 'free', 'indoor'], emoji: '🏰', vibe: 'wholesome' },
  { text: 'Each person pitches a business that should absolutely not exist. Vote on the worst.', tags: ['group', 'free', 'indoor'], emoji: '💼', vibe: 'unhinged' },
  { text: 'Cook a meal where each person only controls one ingredient. No communication.', tags: ['group', 'free', 'indoor'], emoji: '🍳', vibe: 'genius' },
  { text: 'Everyone writes a letter to their 10-year-ago self. Read them aloud or not.', tags: ['group', 'free', 'indoor'], emoji: '✉️', vibe: 'wholesome' },
  { text: 'Create a Wikipedia page for your friend group. Include controversies.', tags: ['group', 'free', 'indoor'], emoji: '📰', vibe: 'unhinged' },
  { text: 'Play "museum" — everyone brings one object and writes a plaque for it', tags: ['group', 'free', 'indoor'], emoji: '🏛️', vibe: 'genius' },
  { text: 'Write and perform a 3-minute play about something that happened to the group', tags: ['group', 'free', 'indoor'], emoji: '🎭', vibe: 'genius' },
  { text: 'Everyone teaches the group one skill in exactly 5 minutes. Timer is strict.', tags: ['group', 'free', 'indoor'], emoji: '⏱️', vibe: 'genius' },

  // Group + Free + Outdoor
  { text: 'Do a photo walk where everyone shoots the same subject. Compare at the end. Art show.', tags: ['group', 'free', 'outdoor'], emoji: '📸', vibe: 'genius' },
  { text: 'Each person navigates to a random spot on the map. Race to get there. Meet for food after.', tags: ['group', 'free', 'outdoor'], emoji: '🗺️', vibe: 'unhinged' },
  { text: 'Have a walking debate on the most unserious topic possible. Judge declares winner.', tags: ['group', 'free', 'outdoor'], emoji: '⚖️', vibe: 'unhinged' },
  { text: 'Stargaze and invent new constellations. Name them after inside jokes.', tags: ['group', 'free', 'outdoor'], emoji: '⭐', vibe: 'wholesome' },
  { text: 'Film a 60-second mockumentary about a completely normal park. Narrate dramatically.', tags: ['group', 'free', 'outdoor'], emoji: '🎥', vibe: 'genius' },

  // Group + Paid
  { text: 'Go thrift shopping. Everyone has $5 to find the most thoughtful gift for the person next to them.', tags: ['group', 'paid', 'outdoor'], emoji: '🎁', vibe: 'wholesome' },
  { text: 'Book an escape room. Take it extremely seriously. Debrief afterward like it was a real mission.', tags: ['group', 'paid', 'indoor'], emoji: '🔐', vibe: 'unhinged' },
  { text: 'Everyone buys one weird ingredient. You have 1 hour to make it into dinner.', tags: ['group', 'paid', 'indoor'], emoji: '🛒', vibe: 'genius' },
  { text: 'Hit a flea market. Everyone finds one thing with a story. Best story wins.', tags: ['group', 'paid', 'outdoor'], emoji: '🏪', vibe: 'genius' },

  // Charity — creative kindness
  { text: 'Write 10 encouraging sticky notes. Hide them in library books for strangers to find.', tags: ['solo', 'charity', 'indoor', 'free'], emoji: '💌', vibe: 'wholesome' },
  { text: 'Bake cookies. Knock on your neighbor\'s door. Just say "these are for you."', tags: ['solo', 'charity', 'outdoor', 'paid'], emoji: '🍪', vibe: 'wholesome' },
  { text: 'Organize a skill swap — teach someone to cook, learn guitar in return', tags: ['group', 'charity', 'indoor', 'free'], emoji: '🔄', vibe: 'genius' },
  { text: 'Fill a backpack with essentials (socks, snacks, water). Give it to someone who needs it.', tags: ['solo', 'charity', 'outdoor', 'paid'], emoji: '🎒', vibe: 'wholesome' },
  { text: 'Organize a "pay what you can" neighborhood dinner. Everyone brings something.', tags: ['group', 'charity', 'outdoor', 'free'], emoji: '🍛', vibe: 'genius' },
  { text: 'Write a glowing recommendation on LinkedIn for someone who helped you and never knew it', tags: ['solo', 'charity', 'indoor', 'free'], emoji: '✍️', vibe: 'wholesome' },
  { text: 'Create care packages for a local shelter. Include a handwritten note in each.', tags: ['group', 'charity', 'indoor', 'paid'], emoji: '📦', vibe: 'wholesome' },
  { text: 'Leave a $5 bill in a children\'s book at a bookstore. Tuck it in chapter one.', tags: ['solo', 'charity', 'outdoor', 'paid'], emoji: '💵', vibe: 'genius' },
  { text: 'Compliment 5 strangers today. Specific compliments only. No "nice shirt" energy.', tags: ['solo', 'charity', 'outdoor', 'free'], emoji: '💬', vibe: 'wholesome' },

  // Environment — eco with style
  { text: 'Do a 15-minute trash pickup. Post the haul. Make people feel something.', tags: ['solo', 'eco', 'outdoor', 'free'], emoji: '🗑️', vibe: 'genius' },
  { text: 'Build a bird feeder from a milk carton. Paint it. Give it an address number.', tags: ['solo', 'eco', 'outdoor', 'free'], emoji: '🐦', vibe: 'genius' },
  { text: 'Start a windowsill herb garden with seeds from the grocery store. Name each plant.', tags: ['solo', 'eco', 'indoor', 'paid'], emoji: '🌱', vibe: 'wholesome' },
  { text: 'Organize a clothing swap party. Dress code: wear your swap.', tags: ['group', 'eco', 'indoor', 'free'], emoji: '👗', vibe: 'genius' },
  { text: 'Plant a tree. Take a photo with it every year. Watch you both grow.', tags: ['solo', 'eco', 'outdoor', 'paid'], emoji: '🌳', vibe: 'wholesome' },
  { text: 'Organize a beach cleanup and turn the best trash finds into an art installation', tags: ['group', 'eco', 'outdoor', 'free'], emoji: '🏖️', vibe: 'genius' },
  { text: 'Start composting. Give your compost bin a name. It\'s family now.', tags: ['solo', 'eco', 'indoor', 'free'], emoji: '♻️', vibe: 'unhinged' },
  { text: 'Set up a Little Free Library. Stock it with your favorites. Add handwritten reviews.', tags: ['group', 'eco', 'outdoor', 'paid'], emoji: '📚', vibe: 'genius' },
  { text: 'Repair something you were about to throw away. Film the process. Oddly satisfying content.', tags: ['solo', 'eco', 'indoor', 'free'], emoji: '🔧', vibe: 'genius' },

  // Adventurous — slightly unhinged but brilliant
  { text: 'Go to a random floor of a library. Read the first book your hand touches for 30 min.', tags: ['solo', 'free', 'indoor'], emoji: '📕', vibe: 'genius' },
  { text: 'Learn to say "this is a wonderful day" in 7 languages. Use all 7 today.', tags: ['solo', 'free', 'indoor'], emoji: '🌐', vibe: 'unhinged' },
  { text: 'Call someone you haven\'t talked to in a year. Don\'t explain. Just ask how they are.', tags: ['solo', 'free', 'indoor'], emoji: '📞', vibe: 'wholesome' },
  { text: 'Go to a random bus stop. Ride to the end. Document everything like a travel vlogger.', tags: ['solo', 'paid', 'outdoor'], emoji: '🚌', vibe: 'genius' },
  { text: 'Explore a neighborhood you\'ve never been to. Rate it on vibes. Write a fake travel review.', tags: ['solo', 'free', 'outdoor'], emoji: '🏘️', vibe: 'unhinged' },
  { text: 'Go to a museum. Pick one painting. Sit with it for 15 min. Write what it told you.', tags: ['solo', 'paid', 'indoor'], emoji: '🖼️', vibe: 'genius' },
  { text: 'Write a letter to yourself at 80. Tell them what mattered today.', tags: ['solo', 'free', 'indoor'], emoji: '👴', vibe: 'wholesome' },
  { text: 'Walk into a grocery store. Buy only things you\'ve never tried. Cook mystery dinner.', tags: ['solo', 'paid', 'indoor'], emoji: '🛒', vibe: 'genius' },
  { text: 'Spend an hour learning a skill on YouTube that has zero practical use. Master it.', tags: ['solo', 'free', 'indoor'], emoji: '🎓', vibe: 'unhinged' },
  { text: 'Take a photo of something ordinary every day for a week. See if it changes.', tags: ['solo', 'free', 'outdoor'], emoji: '📱', vibe: 'genius' },
]

const FILTER_GROUPS = [
  {
    label: 'Who',
    options: [
      { key: 'solo', label: 'Solo', icon: '🧑' },
      { key: 'group', label: 'Crew', icon: '👥' },
    ],
  },
  {
    label: 'Where',
    options: [
      { key: 'indoor', label: 'Indoor', icon: '🏠' },
      { key: 'outdoor', label: 'Outside', icon: '☀️' },
    ],
  },
  {
    label: 'Cost',
    options: [
      { key: 'free', label: 'Free', icon: '✌️' },
      { key: 'paid', label: 'Worth it', icon: '💸' },
    ],
  },
  {
    label: 'Energy',
    options: [
      { key: 'charity', label: 'Kind', icon: '❤️' },
      { key: 'eco', label: 'Eco', icon: '🌍' },
    ],
  },
]

const VIBE_META = {
  unhinged: {
    gradient: 'from-rose-500 via-pink-500 to-fuchsia-600',
    glow: 'rgba(244,63,94,0.35)',
    badge: '🫠 beautifully unhinged',
    bg: 'from-rose-500/15 to-fuchsia-500/15',
    border: 'border-rose-500/25',
  },
  genius: {
    gradient: 'from-violet-500 via-purple-500 to-indigo-600',
    glow: 'rgba(139,92,246,0.35)',
    badge: '🧠 lowkey genius',
    bg: 'from-violet-500/15 to-indigo-500/15',
    border: 'border-violet-500/25',
  },
  wholesome: {
    gradient: 'from-amber-400 via-orange-400 to-yellow-500',
    glow: 'rgba(251,191,36,0.35)',
    badge: '🥹 aggressively wholesome',
    bg: 'from-amber-500/15 to-yellow-500/15',
    border: 'border-amber-500/25',
  },
}

const SPIN_WORDS = [
  'Consulting the multiverse...',
  'Channeling chaotic energy...',
  'Asking the universe politely...',
  'Loading free will.exe...',
  'Rolling the existential dice...',
  'Deploying whimsy...',
  'Calibrating spontaneity...',
  'Summoning audacity...',
]

const SLOT_EMOJIS = ['🎲', '✨', '🌟', '💫', '🎯', '🔮', '🎪', '🚀', '⚡', '🌈', '🦋', '🌀', '💥', '🫧']

export default function FreeWillUtilizer() {
  const [activeFilters, setActiveFilters] = useState(new Set())
  const [current, setCurrent] = useState(null)
  const [isSpinning, setIsSpinning] = useState(false)
  const [slotEmoji, setSlotEmoji] = useState('🎲')
  const [spinWord, setSpinWord] = useState(SPIN_WORDS[0])
  const [history, setHistory] = useState([])
  const [copied, setCopied] = useState(false)
  const [shakeCard, setShakeCard] = useState(false)
  const [showShareCard, setShowShareCard] = useState(false)
  const spinRef = useRef(null)
  const shareCardRef = useRef(null)

  const toggleFilter = (key) => {
    setActiveFilters((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  const getPool = useCallback(() => {
    if (activeFilters.size === 0) return ACTIVITIES
    return ACTIVITIES.filter((a) =>
      [...activeFilters].every((f) => a.tags.includes(f))
    )
  }, [activeFilters])

  const poolSize = getPool().length

  const spin = useCallback(() => {
    const pool = getPool()
    if (!pool.length) {
      setShakeCard(true)
      setTimeout(() => setShakeCard(false), 600)
      return
    }

    setIsSpinning(true)
    setShowShareCard(false)
    setSpinWord(SPIN_WORDS[Math.floor(Math.random() * SPIN_WORDS.length)])

    let tick = 0
    spinRef.current = setInterval(() => {
      setSlotEmoji(SLOT_EMOJIS[Math.floor(Math.random() * SLOT_EMOJIS.length)])
      tick++
      if (tick > 14) clearInterval(spinRef.current)
    }, 70)

    setTimeout(() => {
      const pick = pool[Math.floor(Math.random() * pool.length)]
      setCurrent(pick)
      setSlotEmoji(pick.emoji)
      setIsSpinning(false)
      setHistory((prev) => [pick, ...prev.filter((h) => h.text !== pick.text)].slice(0, 12))
    }, 1200)
  }, [getPool])

  useEffect(() => () => { if (spinRef.current) clearInterval(spinRef.current) }, [])

  const vibe = current ? VIBE_META[current.vibe] : null

  /* ── share text ── */
  const shareText = current
    ? `"${current.text}"\n\namazing use of free will ✦\n\nTry it: `
    : ''

  const tweetUrl = () => `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}`

  const copyText = async () => {
    try {
      await navigator.clipboard.writeText(shareText)
      setCopied(true)
      setTimeout(() => setCopied(false), 2200)
    } catch { /* */ }
  }

  /* ── screenshot-ready share card via canvas ── */
  const downloadShareCard = useCallback(() => {
    if (!current) return
    const v = VIBE_META[current.vibe]
    const W = 1080, H = 1350 // IG story size
    const c = document.createElement('canvas')
    c.width = W; c.height = H
    const ctx = c.getContext('2d')

    // background
    const bg = ctx.createLinearGradient(0, 0, W, H)
    if (current.vibe === 'unhinged') { bg.addColorStop(0, '#1a0a1e'); bg.addColorStop(1, '#2d0a1e') }
    else if (current.vibe === 'genius') { bg.addColorStop(0, '#0f0a2e'); bg.addColorStop(1, '#1a0a2e') }
    else { bg.addColorStop(0, '#1e1405'); bg.addColorStop(1, '#1e1a05') }
    ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H)

    // glow circle
    const grd = ctx.createRadialGradient(W / 2, H * 0.38, 0, W / 2, H * 0.38, 380)
    grd.addColorStop(0, v.glow); grd.addColorStop(1, 'transparent')
    ctx.fillStyle = grd; ctx.fillRect(0, 0, W, H)

    // emoji
    ctx.font = '120px serif'
    ctx.textAlign = 'center'
    ctx.fillText(current.emoji, W / 2, H * 0.3)

    // activity text — word wrap
    ctx.fillStyle = '#f5f5f5'
    ctx.font = 'bold 42px -apple-system, system-ui, sans-serif'
    const words = current.text.split(' ')
    let lines = [], line = ''
    for (const w of words) {
      const test = line ? line + ' ' + w : w
      if (ctx.measureText(test).width > W - 160) { lines.push(line); line = w }
      else line = test
    }
    if (line) lines.push(line)
    const lineH = 56
    const textY = H * 0.42
    lines.forEach((l, i) => ctx.fillText(l, W / 2, textY + i * lineH))

    // vibe badge
    ctx.fillStyle = '#888'
    ctx.font = '28px -apple-system, system-ui, sans-serif'
    ctx.fillText(v.badge, W / 2, textY + lines.length * lineH + 50)

    // divider
    const divY = H * 0.72
    ctx.strokeStyle = 'rgba(255,255,255,0.1)'
    ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(W * 0.2, divY); ctx.lineTo(W * 0.8, divY); ctx.stroke()

    // "amazing use of free will"
    ctx.fillStyle = '#d4d4d4'
    ctx.font = 'italic 32px Georgia, serif'
    ctx.fillText('amazing use of free will', W / 2, divY + 60)

    // branding
    ctx.fillStyle = '#525252'
    ctx.font = '22px -apple-system, system-ui, sans-serif'
    ctx.fillText('✦ Free Will Utilizer ✦', W / 2, H - 80)

    // download
    const link = document.createElement('a')
    link.download = 'free-will.png'
    link.href = c.toDataURL('image/png')
    link.click()
  }, [current])

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-neutral-100 overflow-x-hidden selection:bg-purple-500/30">
      {/* Ambient */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-48 -left-48 w-[500px] h-[500px] bg-purple-600/[0.06] rounded-full blur-[100px]" />
        <div className="absolute top-1/2 -right-32 w-96 h-96 bg-rose-600/[0.05] rounded-full blur-[100px]" />
        <div className="absolute -bottom-32 left-1/4 w-80 h-80 bg-amber-600/[0.04] rounded-full blur-[100px]" />
      </div>

      <div className="relative z-10 max-w-xl mx-auto px-5">

        {/* ── Header ── */}
        <header className="pt-12 pb-8 text-center">
          <p className="text-[11px] font-semibold tracking-[0.25em] uppercase text-neutral-600 mb-5">
            ✦ you have free will ✦ might as well use it ✦
          </p>
          <h1 className="text-5xl sm:text-6xl font-black tracking-tight leading-[1.05] mb-4">
            <span className="bg-gradient-to-r from-purple-400 via-pink-400 to-amber-300 bg-clip-text text-transparent">
              Free Will
            </span>
            <br />
            <span className="text-neutral-300 text-4xl sm:text-5xl font-extrabold">Utilizer</span>
          </h1>
          <p className="text-sm text-neutral-600 max-w-xs mx-auto leading-relaxed">
            Wildly creative ideas you can actually do.<br />
            The kind where people comment<br />
            <span className="italic text-neutral-400">&quot;amazing use of free will&quot;</span>
          </p>
        </header>

        {/* ── Filters ── */}
        <section className="mb-8">
          <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 backdrop-blur-sm">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[11px] font-semibold tracking-[0.2em] uppercase text-neutral-600">Dial it in</span>
              {activeFilters.size > 0 && (
                <button onClick={() => setActiveFilters(new Set())} className="text-[11px] text-neutral-700 hover:text-neutral-400 transition">
                  Clear
                </button>
              )}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              {FILTER_GROUPS.map((g) => (
                <div key={g.label} className="space-y-1.5">
                  <div className="text-[10px] font-medium text-neutral-700 pl-0.5">{g.label}</div>
                  {g.options.map((o) => {
                    const on = activeFilters.has(o.key)
                    return (
                      <button
                        key={o.key}
                        onClick={() => toggleFilter(o.key)}
                        className={`w-full flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium transition-all duration-200 ${
                          on
                            ? 'bg-purple-500/15 border border-purple-400/30 text-purple-300 shadow-[0_0_12px_rgba(168,85,247,0.08)]'
                            : 'bg-white/[0.03] border border-white/[0.06] text-neutral-500 hover:bg-white/[0.06] hover:text-neutral-300'
                        }`}
                      >
                        <span className="text-sm">{o.icon}</span>
                        <span>{o.label}</span>
                      </button>
                    )
                  })}
                </div>
              ))}
            </div>
            <div className="mt-3 text-center">
              <span className="text-[10px] text-neutral-700">
                {poolSize} idea{poolSize !== 1 ? 's' : ''} in the pool
              </span>
            </div>
          </div>
        </section>

        {/* ── Main card ── */}
        <section className="mb-6">
          <div
            className={`relative rounded-3xl border min-h-[280px] sm:min-h-[320px] flex flex-col items-center justify-center p-8 sm:p-10 text-center transition-all duration-700 ${
              current && !isSpinning
                ? `bg-gradient-to-br ${vibe.bg} ${vibe.border}`
                : 'bg-white/[0.02] border-white/[0.06]'
            }`}
            style={{
              animation: shakeCard ? 'shake 0.6s ease' : isSpinning ? 'pulse-glow 0.35s ease infinite alternate' : 'none',
              boxShadow: current && !isSpinning ? `0 0 60px ${vibe.glow.replace('0.35', '0.12')}` : 'none',
            }}
          >
            {isSpinning ? (
              <div className="flex flex-col items-center gap-5">
                <div className="text-7xl" style={{ animation: 'spin-wobble 0.4s ease infinite' }}>{slotEmoji}</div>
                <div className="flex gap-1.5">
                  {[0, 1, 2, 3].map((i) => (
                    <div key={i} className="w-1.5 h-1.5 rounded-full bg-purple-400/60" style={{ animation: `dot-bounce 0.5s ease ${i * 0.1}s infinite alternate` }} />
                  ))}
                </div>
                <p className="text-xs text-neutral-600 italic">{spinWord}</p>
              </div>
            ) : current ? (
              <div className="flex flex-col items-center gap-5" style={{ animation: 'card-reveal 0.6s cubic-bezier(0.16,1,0.3,1)' }}>
                <div className="text-6xl sm:text-7xl">{current.emoji}</div>
                <p className="text-lg sm:text-xl font-bold leading-snug text-neutral-100 max-w-sm">
                  {current.text}
                </p>
                <span className={`text-[11px] font-semibold tracking-wide px-3 py-1.5 rounded-full ${vibe.border} bg-black/30 text-neutral-300`}>
                  {vibe.badge}
                </span>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <div className="text-6xl opacity-20" style={{ animation: 'float 3s ease-in-out infinite' }}>🎲</div>
                <p className="text-sm text-neutral-600">Your next amazing use of free will</p>
                <p className="text-[11px] text-neutral-800">is one tap away ↓</p>
              </div>
            )}
          </div>

          {/* Spin button */}
          <div className="flex justify-center mt-6">
            <button
              onClick={spin}
              disabled={isSpinning}
              className={`relative px-10 py-4 rounded-2xl font-bold text-base transition-all duration-300 ${
                isSpinning
                  ? 'bg-neutral-900 text-neutral-700 cursor-wait'
                  : poolSize === 0
                  ? 'bg-neutral-900 text-neutral-700 cursor-not-allowed'
                  : 'bg-gradient-to-r from-purple-600 via-pink-600 to-purple-600 bg-[length:200%_100%] text-white shadow-[0_4px_30px_rgba(168,85,247,0.25)] hover:shadow-[0_4px_40px_rgba(168,85,247,0.4)] hover:scale-[1.03] active:scale-[0.97]'
              }`}
              style={!isSpinning && poolSize > 0 ? { animation: 'shimmer 3s ease infinite' } : {}}
            >
              {isSpinning
                ? '✨ Spinning...'
                : current
                ? '🎲 Use It Again'
                : poolSize === 0
                ? 'No ideas match'
                : '🎲 Use Your Free Will'}
            </button>
          </div>
        </section>

        {/* ── Share section ── */}
        {current && !isSpinning && (
          <section className="mb-8" style={{ animation: 'card-reveal 0.4s ease' }}>
            <div className="bg-white/[0.02] border border-white/[0.05] rounded-2xl p-5">
              <p className="text-[10px] font-semibold tracking-[0.2em] uppercase text-neutral-700 mb-4 text-center">
                Post it. Own it. Let them comment.
              </p>

              <div className="flex flex-wrap gap-2 justify-center mb-4">
                {/* Twitter / X */}
                <a
                  href={tweetUrl()}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm font-medium text-neutral-400 hover:bg-white/[0.08] hover:text-white transition-all"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                  Post
                </a>

                {/* Download for IG story */}
                <button
                  onClick={downloadShareCard}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm font-medium text-neutral-400 hover:bg-white/[0.08] hover:text-white transition-all"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="2" width="20" height="20" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="18" cy="6" r="1.5"/></svg>
                  Story Card
                </button>

                {/* Copy */}
                <button
                  onClick={copyText}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm font-medium text-neutral-400 hover:bg-white/[0.08] hover:text-white transition-all"
                >
                  {copied ? '✅ Copied!' : '📋 Copy'}
                </button>

                {/* Native share (mobile) */}
                <button
                  onClick={() => {
                    if (typeof navigator !== 'undefined' && navigator.share) {
                      navigator.share({ text: shareText }).catch(() => {})
                    }
                  }}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm font-medium text-neutral-400 hover:bg-white/[0.08] hover:text-white transition-all sm:hidden"
                >
                  📤 Share
                </button>
              </div>

              {/* Preview */}
              <div className="bg-black/30 border border-white/[0.05] rounded-xl p-5 text-center space-y-2">
                <p className="text-sm text-neutral-300 font-medium leading-relaxed">
                  &quot;{current.text}&quot;
                </p>
                <p className="text-xs text-neutral-500 italic">amazing use of free will ✦</p>
              </div>
            </div>
          </section>
        )}

        {/* ── History ── */}
        {history.length > 1 && (
          <section className="mb-10">
            <p className="text-[10px] font-semibold tracking-[0.2em] uppercase text-neutral-700 mb-3">
              Free will log
            </p>
            <div className="space-y-1.5">
              {history.slice(1).map((item, i) => (
                <div
                  key={item.text}
                  className="flex items-center gap-3 px-3.5 py-2.5 rounded-xl bg-white/[0.02] border border-white/[0.04] text-sm text-neutral-600"
                  style={{ opacity: 1 - i * 0.07 }}
                >
                  <span className="text-base flex-shrink-0">{item.emoji}</span>
                  <span className="truncate">{item.text}</span>
                  <span className="text-[10px] ml-auto flex-shrink-0 text-neutral-800">{VIBE_META[item.vibe].badge.split(' ')[0]}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ── Footer ── */}
        <footer className="pb-14 text-center border-t border-white/[0.04] pt-8">
          <p className="text-[11px] text-neutral-800 leading-relaxed max-w-xs mx-auto mb-3">
            ~2.5 billion seconds in a life. You just spent 1 deciding how to use the next few thousand. Pretty efficient, honestly.
          </p>
          <p className="text-[10px] text-neutral-900">
            ✦ built with free will ✦
          </p>
        </footer>
      </div>

      {/* ── Keyframes ── */}
      <style jsx>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0) rotate(0); }
          15% { transform: translateX(-10px) rotate(-2deg); }
          30% { transform: translateX(10px) rotate(2deg); }
          45% { transform: translateX(-6px) rotate(-1deg); }
          60% { transform: translateX(6px) rotate(1deg); }
          75% { transform: translateX(-2px) rotate(-0.5deg); }
        }
        @keyframes card-reveal {
          from { opacity: 0; transform: translateY(16px) scale(0.97); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes pulse-glow {
          from { box-shadow: 0 0 30px rgba(168, 85, 247, 0.08); }
          to { box-shadow: 0 0 50px rgba(168, 85, 247, 0.2); }
        }
        @keyframes dot-bounce {
          from { transform: translateY(0); opacity: 0.4; }
          to { transform: translateY(-8px); opacity: 1; }
        }
        @keyframes spin-wobble {
          0% { transform: rotate(0) scale(1); }
          25% { transform: rotate(8deg) scale(1.05); }
          50% { transform: rotate(-8deg) scale(0.95); }
          75% { transform: rotate(4deg) scale(1.02); }
          100% { transform: rotate(0) scale(1); }
        }
        @keyframes float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-8px); }
        }
        @keyframes shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
    </div>
  )
}
