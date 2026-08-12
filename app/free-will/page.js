'use client'
import { useState, useCallback, useEffect, useRef } from 'react'

/* ─── Activity database ─── */
const ACTIVITIES = [
  // Individual + Free + Outdoor
  { text: 'Go for a walk and count how many dogs you see 🐕', tags: ['individual', 'free', 'outdoor'], emoji: '🚶', vibe: 'chill' },
  { text: 'Find a park bench and people-watch for 20 minutes', tags: ['individual', 'free', 'outdoor'], emoji: '🪑', vibe: 'chill' },
  { text: 'Take photos of interesting shadows', tags: ['individual', 'free', 'outdoor'], emoji: '📸', vibe: 'creative' },
  { text: 'Go cloud-watching and name the shapes', tags: ['individual', 'free', 'outdoor'], emoji: '☁️', vibe: 'chill' },
  { text: 'Do a handstand (or try to) in a park', tags: ['individual', 'free', 'outdoor'], emoji: '🤸', vibe: 'active' },
  { text: 'Walk barefoot in grass for 10 minutes', tags: ['individual', 'free', 'outdoor'], emoji: '🌿', vibe: 'chill' },
  { text: 'Sprint as fast as you can for 30 seconds', tags: ['individual', 'free', 'outdoor'], emoji: '🏃', vibe: 'active' },
  { text: 'Find the tallest tree nearby and sit under it', tags: ['individual', 'free', 'outdoor'], emoji: '🌳', vibe: 'chill' },

  // Individual + Free + Indoor
  { text: 'Rearrange your room — feng shui style', tags: ['individual', 'free', 'indoor'], emoji: '🛋️', vibe: 'creative' },
  { text: 'Write a letter to your future self', tags: ['individual', 'free', 'indoor'], emoji: '✉️', vibe: 'creative' },
  { text: 'Learn to fold an origami crane', tags: ['individual', 'free', 'indoor'], emoji: '🦢', vibe: 'creative' },
  { text: 'Dance like nobody is watching for one full song', tags: ['individual', 'free', 'indoor'], emoji: '💃', vibe: 'active' },
  { text: 'Try meditating for just 5 minutes', tags: ['individual', 'free', 'indoor'], emoji: '🧘', vibe: 'chill' },
  { text: 'Draw a self-portrait without looking at the paper', tags: ['individual', 'free', 'indoor'], emoji: '🎨', vibe: 'creative' },
  { text: 'Organize one drawer — just one', tags: ['individual', 'free', 'indoor'], emoji: '🗄️', vibe: 'productive' },
  { text: 'Cook something with only ingredients you already have', tags: ['individual', 'free', 'indoor'], emoji: '👨‍🍳', vibe: 'creative' },
  { text: 'Take a cold shower — if you dare', tags: ['individual', 'free', 'indoor'], emoji: '🚿', vibe: 'active' },
  { text: 'Start a journal — write literally anything', tags: ['individual', 'free', 'indoor'], emoji: '📓', vibe: 'creative' },

  // Individual + Paid
  { text: 'Treat yourself to a fancy coffee ☕', tags: ['individual', 'paid', 'outdoor'], emoji: '☕', vibe: 'chill' },
  { text: 'Buy a book you\'d never normally pick', tags: ['individual', 'paid', 'indoor'], emoji: '📚', vibe: 'creative' },
  { text: 'Get a houseplant and name it', tags: ['individual', 'paid', 'indoor'], emoji: '🪴', vibe: 'chill' },
  { text: 'Try a new restaurant — chef\'s choice', tags: ['individual', 'paid', 'outdoor'], emoji: '🍽️', vibe: 'adventurous' },
  { text: 'Take a pottery or art class', tags: ['individual', 'paid', 'indoor'], emoji: '🏺', vibe: 'creative' },
  { text: 'Go see a movie solo — pick the weirdest one', tags: ['individual', 'paid', 'indoor'], emoji: '🎬', vibe: 'adventurous' },

  // Group + Free + Outdoor
  { text: 'Have a picnic with whatever\'s in the fridge', tags: ['group', 'free', 'outdoor'], emoji: '🧺', vibe: 'chill' },
  { text: 'Play frisbee or catch in a park', tags: ['group', 'free', 'outdoor'], emoji: '🥏', vibe: 'active' },
  { text: 'Go on a photo walk — everyone shoots the same thing differently', tags: ['group', 'free', 'outdoor'], emoji: '📷', vibe: 'creative' },
  { text: 'Organize a sunset-watching session', tags: ['group', 'free', 'outdoor'], emoji: '🌅', vibe: 'chill' },
  { text: 'Play hide and seek — yes, as adults', tags: ['group', 'free', 'outdoor'], emoji: '🙈', vibe: 'active' },
  { text: 'Have a walking debate about a silly topic', tags: ['group', 'free', 'outdoor'], emoji: '🗣️', vibe: 'social' },
  { text: 'Stargaze and make up new constellations', tags: ['group', 'free', 'outdoor'], emoji: '⭐', vibe: 'chill' },

  // Group + Free + Indoor
  { text: 'Host a potluck with whatever everyone already has', tags: ['group', 'free', 'indoor'], emoji: '🍲', vibe: 'social' },
  { text: 'Have a movie marathon — let a random number pick the films', tags: ['group', 'free', 'indoor'], emoji: '🎥', vibe: 'chill' },
  { text: 'Play charades but only with movie villains', tags: ['group', 'free', 'indoor'], emoji: '🎭', vibe: 'social' },
  { text: 'Cook a meal together where each person makes one course', tags: ['group', 'free', 'indoor'], emoji: '🧑‍🍳', vibe: 'creative' },
  { text: 'Have a lip-sync battle', tags: ['group', 'free', 'indoor'], emoji: '🎤', vibe: 'active' },
  { text: 'Build a blanket fort. No age limit.', tags: ['group', 'free', 'indoor'], emoji: '🏰', vibe: 'creative' },
  { text: 'Play "two truths and a lie" and actually try to fool people', tags: ['group', 'free', 'indoor'], emoji: '🤥', vibe: 'social' },

  // Group + Paid
  { text: 'Go bowling and loser buys snacks', tags: ['group', 'paid', 'indoor'], emoji: '🎳', vibe: 'active' },
  { text: 'Book an escape room', tags: ['group', 'paid', 'indoor'], emoji: '🔐', vibe: 'adventurous' },
  { text: 'Go thrift shopping and find the most ridiculous outfit', tags: ['group', 'paid', 'outdoor'], emoji: '🛍️', vibe: 'creative' },
  { text: 'Rent kayaks or paddleboards', tags: ['group', 'paid', 'outdoor'], emoji: '🛶', vibe: 'active' },
  { text: 'Take a cooking class together', tags: ['group', 'paid', 'indoor'], emoji: '👩‍🍳', vibe: 'creative' },

  // Charity / Volunteering
  { text: 'Donate clothes you haven\'t worn in a year', tags: ['individual', 'charity', 'indoor', 'free'], emoji: '👕', vibe: 'productive' },
  { text: 'Volunteer at a local food bank', tags: ['group', 'charity', 'outdoor', 'free'], emoji: '🥫', vibe: 'productive' },
  { text: 'Write encouraging notes and leave them in library books', tags: ['individual', 'charity', 'indoor', 'free'], emoji: '💌', vibe: 'creative' },
  { text: 'Help an elderly neighbor with groceries or chores', tags: ['individual', 'charity', 'outdoor', 'free'], emoji: '🤝', vibe: 'productive' },
  { text: 'Organize a bake sale for a local cause', tags: ['group', 'charity', 'outdoor', 'paid'], emoji: '🧁', vibe: 'social' },
  { text: 'Donate blood — it literally saves lives', tags: ['individual', 'charity', 'indoor', 'free'], emoji: '🩸', vibe: 'productive' },
  { text: 'Teach someone a skill you have', tags: ['group', 'charity', 'indoor', 'free'], emoji: '📖', vibe: 'social' },
  { text: 'Buy a stranger\'s coffee', tags: ['individual', 'charity', 'outdoor', 'paid'], emoji: '☕', vibe: 'social' },
  { text: 'Organize a community meal for unhoused neighbors', tags: ['group', 'charity', 'outdoor', 'paid'], emoji: '🍛', vibe: 'social' },

  // Environment / Eco
  { text: 'Do a 15-minute trash pickup in your neighborhood', tags: ['individual', 'environment', 'outdoor', 'free'], emoji: '🗑️', vibe: 'productive' },
  { text: 'Plant a tree or start a small garden', tags: ['individual', 'environment', 'outdoor', 'paid'], emoji: '🌱', vibe: 'creative' },
  { text: 'Organize a beach / park cleanup with friends', tags: ['group', 'environment', 'outdoor', 'free'], emoji: '🏖️', vibe: 'active' },
  { text: 'Build a bird feeder from recycled materials', tags: ['individual', 'environment', 'outdoor', 'free'], emoji: '🐦', vibe: 'creative' },
  { text: 'Start composting — even a small bin counts', tags: ['individual', 'environment', 'indoor', 'free'], emoji: '♻️', vibe: 'productive' },
  { text: 'Swap single-use items for reusable ones today', tags: ['individual', 'environment', 'indoor', 'paid'], emoji: '🌍', vibe: 'productive' },
  { text: 'Organize a clothing swap party', tags: ['group', 'environment', 'indoor', 'free'], emoji: '👗', vibe: 'social' },
  { text: 'Take public transit or bike instead of driving today', tags: ['individual', 'environment', 'outdoor', 'free'], emoji: '🚲', vibe: 'active' },
  { text: 'Set up a little free library box', tags: ['group', 'environment', 'outdoor', 'paid'], emoji: '📚', vibe: 'creative' },

  // Adventurous / Wild
  { text: 'Go somewhere you\'ve never been within 5 miles of home', tags: ['individual', 'free', 'outdoor'], emoji: '🗺️', vibe: 'adventurous' },
  { text: 'Talk to a stranger (nicely) and learn one thing about them', tags: ['individual', 'free', 'outdoor'], emoji: '👋', vibe: 'adventurous' },
  { text: 'Say yes to the next thing someone suggests', tags: ['individual', 'free', 'outdoor'], emoji: '✅', vibe: 'adventurous' },
  { text: 'Learn 5 words in a language you don\'t speak', tags: ['individual', 'free', 'indoor'], emoji: '🌐', vibe: 'creative' },
  { text: 'Call someone you haven\'t talked to in 6+ months', tags: ['individual', 'free', 'indoor'], emoji: '📞', vibe: 'social' },
  { text: 'Go to a random bus stop and ride to the last stop', tags: ['individual', 'paid', 'outdoor'], emoji: '🚌', vibe: 'adventurous' },
  { text: 'Explore a neighborhood you\'ve never walked through', tags: ['individual', 'free', 'outdoor'], emoji: '🏘️', vibe: 'adventurous' },
  { text: 'Visit a museum — actually read the plaques this time', tags: ['individual', 'paid', 'indoor'], emoji: '🏛️', vibe: 'creative' },
]

const FILTER_GROUPS = [
  {
    label: 'Who',
    icon: '👤',
    options: [
      { key: 'individual', label: 'Solo', emoji: '🧑' },
      { key: 'group', label: 'Group', emoji: '👥' },
    ],
  },
  {
    label: 'Where',
    icon: '📍',
    options: [
      { key: 'indoor', label: 'Indoor', emoji: '🏠' },
      { key: 'outdoor', label: 'Outdoor', emoji: '🌳' },
    ],
  },
  {
    label: 'Cost',
    icon: '💰',
    options: [
      { key: 'free', label: 'Free', emoji: '🆓' },
      { key: 'paid', label: 'Paid', emoji: '💳' },
    ],
  },
  {
    label: 'Purpose',
    icon: '💡',
    options: [
      { key: 'charity', label: 'Charity', emoji: '❤️' },
      { key: 'environment', label: 'Eco', emoji: '🌍' },
    ],
  },
]

const VIBE_COLORS = {
  chill: { bg: 'from-blue-500/20 to-indigo-500/20', border: 'border-blue-500/30', text: 'text-blue-400', label: '😌 Chill' },
  active: { bg: 'from-orange-500/20 to-red-500/20', border: 'border-orange-500/30', text: 'text-orange-400', label: '⚡ Active' },
  creative: { bg: 'from-purple-500/20 to-pink-500/20', border: 'border-purple-500/30', text: 'text-purple-400', label: '🎨 Creative' },
  social: { bg: 'from-green-500/20 to-emerald-500/20', border: 'border-green-500/30', text: 'text-green-400', label: '💬 Social' },
  adventurous: { bg: 'from-amber-500/20 to-yellow-500/20', border: 'border-amber-500/30', text: 'text-amber-400', label: '🧭 Adventurous' },
  productive: { bg: 'from-teal-500/20 to-cyan-500/20', border: 'border-teal-500/30', text: 'text-teal-400', label: '✅ Productive' },
}

/* ─── Shuffle text animation characters ─── */
const SLOT_EMOJIS = ['🎲', '🎰', '✨', '🌟', '💫', '🎯', '🔮', '🎪', '🎨', '🚀', '⚡', '🌈', '🎭', '🎪', '🦋', '🌸']

export default function FreeWillUtilizer() {
  const [activeFilters, setActiveFilters] = useState(new Set())
  const [currentActivity, setCurrentActivity] = useState(null)
  const [isSpinning, setIsSpinning] = useState(false)
  const [slotEmoji, setSlotEmoji] = useState('🎲')
  const [history, setHistory] = useState([])
  const [copied, setCopied] = useState(false)
  const [shakeCard, setShakeCard] = useState(false)
  const spinInterval = useRef(null)
  const cardRef = useRef(null)

  const toggleFilter = (key) => {
    setActiveFilters((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const getFilteredActivities = useCallback(() => {
    if (activeFilters.size === 0) return ACTIVITIES
    return ACTIVITIES.filter((a) =>
      [...activeFilters].every((f) => a.tags.includes(f))
    )
  }, [activeFilters])

  const filteredCount = getFilteredActivities().length

  const spin = useCallback(() => {
    const pool = getFilteredActivities()
    if (pool.length === 0) {
      setShakeCard(true)
      setTimeout(() => setShakeCard(false), 500)
      return
    }

    setIsSpinning(true)

    // Emoji slot animation
    let count = 0
    spinInterval.current = setInterval(() => {
      setSlotEmoji(SLOT_EMOJIS[Math.floor(Math.random() * SLOT_EMOJIS.length)])
      count++
      if (count > 12) {
        clearInterval(spinInterval.current)
      }
    }, 80)

    setTimeout(() => {
      const pick = pool[Math.floor(Math.random() * pool.length)]
      setCurrentActivity(pick)
      setSlotEmoji(pick.emoji)
      setIsSpinning(false)
      setHistory((prev) => [pick, ...prev.filter((h) => h.text !== pick.text)].slice(0, 10))
    }, 1100)
  }, [getFilteredActivities])

  useEffect(() => {
    return () => { if (spinInterval.current) clearInterval(spinInterval.current) }
  }, [])

  const shareText = currentActivity
    ? `🎲 My free will says: "${currentActivity.text}"\n\nTry the Free Will Utilizer!`
    : ''

  const shareToTwitter = () => {
    const url = `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}`
    window.open(url, '_blank', 'width=550,height=420')
  }

  const shareToFacebook = () => {
    const url = `https://www.facebook.com/sharer/sharer.php?quote=${encodeURIComponent(shareText)}`
    window.open(url, '_blank', 'width=550,height=420')
  }

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(shareText)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard may not be available */
    }
  }

  const vibeStyle = currentActivity ? VIBE_COLORS[currentActivity.vibe] : null

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 overflow-x-hidden">
      {/* Ambient background blobs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-purple-600/8 rounded-full blur-3xl" />
        <div className="absolute top-1/3 -right-20 w-80 h-80 bg-blue-600/8 rounded-full blur-3xl" />
        <div className="absolute -bottom-20 left-1/3 w-72 h-72 bg-pink-600/6 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10">
        {/* Header */}
        <header className="pt-10 pb-6 px-5 text-center">
          <div className="inline-flex items-center gap-2 text-xs font-semibold tracking-widest uppercase text-purple-400 border border-purple-400/30 rounded-full px-4 py-1.5 mb-5">
            <span className="animate-pulse">✦</span> Use Your Free Will <span className="animate-pulse">✦</span>
          </div>
          <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight leading-[1.1] mb-4">
            <span className="bg-gradient-to-r from-purple-400 via-pink-400 to-amber-400 bg-clip-text text-transparent">
              Free Will
            </span>
            <br />
            <span className="text-neutral-200">Utilizer</span>
          </h1>
          <p className="text-base sm:text-lg text-neutral-500 max-w-md mx-auto leading-relaxed">
            You have free will — might as well use it.<br />
            <span className="text-neutral-400">Spin for something to do right now.</span>
          </p>
        </header>

        {/* Filter controls */}
        <section className="max-w-2xl mx-auto px-5 mb-8">
          <div className="bg-neutral-900/60 border border-neutral-800/60 rounded-2xl p-4 sm:p-5 backdrop-blur-sm">
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-semibold tracking-widest uppercase text-neutral-500">Dial it in</span>
              {activeFilters.size > 0 && (
                <button
                  onClick={() => setActiveFilters(new Set())}
                  className="text-xs text-neutral-600 hover:text-neutral-400 transition"
                >
                  Clear all
                </button>
              )}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {FILTER_GROUPS.map((group) => (
                <div key={group.label}>
                  <div className="text-[11px] font-medium text-neutral-600 mb-1.5 pl-0.5">{group.icon} {group.label}</div>
                  <div className="flex flex-col gap-1.5">
                    {group.options.map((opt) => {
                      const active = activeFilters.has(opt.key)
                      return (
                        <button
                          key={opt.key}
                          onClick={() => toggleFilter(opt.key)}
                          className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200 ${
                            active
                              ? 'bg-purple-500/20 border border-purple-500/40 text-purple-300 shadow-sm shadow-purple-500/10'
                              : 'bg-neutral-800/60 border border-neutral-700/40 text-neutral-400 hover:bg-neutral-800 hover:text-neutral-300'
                          }`}
                        >
                          <span>{opt.emoji}</span>
                          <span>{opt.label}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 text-center">
              <span className="text-[11px] text-neutral-600">
                {filteredCount} {filteredCount === 1 ? 'activity' : 'activities'} available
              </span>
            </div>
          </div>
        </section>

        {/* Main card / result */}
        <section className="max-w-lg mx-auto px-5 mb-8">
          <div
            ref={cardRef}
            className={`relative rounded-3xl border p-8 sm:p-10 text-center min-h-[260px] flex flex-col items-center justify-center transition-all duration-500 ${
              shakeCard ? 'animate-[shake_0.5s_ease-in-out]' : ''
            } ${
              currentActivity && !isSpinning
                ? `bg-gradient-to-br ${vibeStyle.bg} ${vibeStyle.border}`
                : 'bg-neutral-900/60 border-neutral-800/60'
            }`}
            style={{
              animation: shakeCard
                ? 'shake 0.5s ease-in-out'
                : isSpinning
                ? 'pulse-glow 0.3s ease-in-out infinite alternate'
                : 'none',
            }}
          >
            {/* Spinning / idle / result */}
            {isSpinning ? (
              <div className="flex flex-col items-center gap-4">
                <div className="text-6xl sm:text-7xl animate-bounce">{slotEmoji}</div>
                <div className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <div
                      key={i}
                      className="w-2 h-2 rounded-full bg-purple-400"
                      style={{
                        animation: `bounce 0.6s ease-in-out ${i * 0.15}s infinite alternate`,
                      }}
                    />
                  ))}
                </div>
                <p className="text-sm text-neutral-500 animate-pulse">Consulting the universe...</p>
              </div>
            ) : currentActivity ? (
              <div className="flex flex-col items-center gap-4 animate-[fadeUp_0.5s_ease-out]">
                <div className="text-5xl sm:text-6xl mb-1">{currentActivity.emoji}</div>
                <p className="text-lg sm:text-xl font-semibold leading-snug text-neutral-100 max-w-sm">
                  {currentActivity.text}
                </p>
                <div className="flex flex-wrap gap-2 justify-center mt-1">
                  <span className={`text-[11px] font-medium px-2.5 py-1 rounded-full ${vibeStyle.border} ${vibeStyle.text} bg-black/20`}>
                    {vibeStyle.label}
                  </span>
                  {currentActivity.tags.map((t) => (
                    <span
                      key={t}
                      className="text-[11px] font-medium px-2.5 py-1 rounded-full border border-neutral-700/50 text-neutral-500 bg-black/20"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3 text-neutral-600">
                <div className="text-5xl sm:text-6xl opacity-40">🎲</div>
                <p className="text-base">Your destiny awaits</p>
                <p className="text-xs text-neutral-700">Hit the button below ↓</p>
              </div>
            )}
          </div>

          {/* Spin button */}
          <div className="flex justify-center mt-6">
            <button
              onClick={spin}
              disabled={isSpinning}
              className={`group relative px-8 sm:px-10 py-4 rounded-2xl font-bold text-base sm:text-lg transition-all duration-300 ${
                isSpinning
                  ? 'bg-neutral-800 text-neutral-600 cursor-wait'
                  : filteredCount === 0
                  ? 'bg-neutral-800 text-neutral-600 cursor-not-allowed'
                  : 'bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white shadow-lg shadow-purple-500/25 hover:shadow-purple-500/40 hover:scale-[1.03] active:scale-[0.98]'
              }`}
            >
              {isSpinning ? (
                '✨ Spinning...'
              ) : currentActivity ? (
                <>🎲 Spin Again</>
              ) : filteredCount === 0 ? (
                'No activities match'
              ) : (
                <>🎲 Use Your Free Will</>
              )}
            </button>
          </div>
        </section>

        {/* Share section — visible when there's a result */}
        {currentActivity && !isSpinning && (
          <section className="max-w-lg mx-auto px-5 mb-10 animate-[fadeUp_0.4s_ease-out]">
            <div className="bg-neutral-900/40 border border-neutral-800/40 rounded-2xl p-5">
              <p className="text-xs font-semibold tracking-widest uppercase text-neutral-600 mb-3 text-center">
                Share your decision with the world
              </p>
              <div className="flex flex-wrap gap-2 justify-center">
                <button
                  onClick={shareToTwitter}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-neutral-800/80 border border-neutral-700/50 text-sm font-medium text-neutral-300 hover:bg-neutral-700/80 hover:text-white transition-all"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                  Post
                </button>
                <button
                  onClick={shareToFacebook}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-neutral-800/80 border border-neutral-700/50 text-sm font-medium text-neutral-300 hover:bg-neutral-700/80 hover:text-white transition-all"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>
                  Share
                </button>
                <button
                  onClick={copyToClipboard}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-neutral-800/80 border border-neutral-700/50 text-sm font-medium text-neutral-300 hover:bg-neutral-700/80 hover:text-white transition-all"
                >
                  {copied ? '✅' : '📋'}
                  {copied ? 'Copied!' : 'Copy'}
                </button>
                {typeof navigator !== 'undefined' && navigator.share && (
                  <button
                    onClick={() => navigator.share({ text: shareText }).catch(() => {})}
                    className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-neutral-800/80 border border-neutral-700/50 text-sm font-medium text-neutral-300 hover:bg-neutral-700/80 hover:text-white transition-all"
                  >
                    📤 Share
                  </button>
                )}
              </div>
              {/* Preview card for social */}
              <div className="mt-4 bg-neutral-950/60 border border-neutral-800/40 rounded-xl p-4 text-center">
                <p className="text-xs text-neutral-600 mb-2">Preview</p>
                <p className="text-sm text-neutral-400">
                  🎲 My free will says: &quot;{currentActivity.text}&quot;
                </p>
                <p className="text-xs text-neutral-600 mt-1">Try the Free Will Utilizer!</p>
              </div>
            </div>
          </section>
        )}

        {/* History */}
        {history.length > 1 && (
          <section className="max-w-lg mx-auto px-5 mb-10">
            <div className="bg-neutral-900/30 border border-neutral-800/30 rounded-2xl p-5">
              <p className="text-xs font-semibold tracking-widest uppercase text-neutral-600 mb-3">
                🕐 Your free will history
              </p>
              <div className="space-y-2">
                {history.slice(1).map((item, i) => (
                  <div
                    key={item.text}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg bg-neutral-900/40 border border-neutral-800/30 text-sm text-neutral-500"
                    style={{ opacity: 1 - i * 0.08 }}
                  >
                    <span>{item.emoji}</span>
                    <span className="truncate">{item.text}</span>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* Fun bottom section */}
        <section className="max-w-lg mx-auto px-5 pb-12 text-center">
          <div className="border-t border-neutral-800/40 pt-8">
            <p className="text-xs text-neutral-700 leading-relaxed max-w-sm mx-auto">
              You have approximately 2.5 billion seconds in your life. Each spin is one second well spent deciding how to spend the next few thousand. No pressure.
            </p>
            <p className="text-xs text-neutral-800 mt-3">
              Built with ✦ free will ✦
            </p>
          </div>
        </section>
      </div>

      {/* Animations */}
      <style jsx>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          20% { transform: translateX(-8px) rotate(-1deg); }
          40% { transform: translateX(8px) rotate(1deg); }
          60% { transform: translateX(-5px) rotate(-0.5deg); }
          80% { transform: translateX(5px) rotate(0.5deg); }
        }
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulse-glow {
          from { box-shadow: 0 0 20px rgba(168, 85, 247, 0.1); }
          to { box-shadow: 0 0 40px rgba(168, 85, 247, 0.25); }
        }
        @keyframes bounce {
          from { transform: translateY(0); }
          to { transform: translateY(-6px); }
        }
      `}</style>
    </div>
  )
}
