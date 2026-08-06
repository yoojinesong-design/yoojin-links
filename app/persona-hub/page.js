'use client'
import { useState } from 'react'
import Link from 'next/link'

const FEATURES = [
  {
    icon: '🎭',
    title: 'Persona Manager',
    desc: 'One dashboard for all your artist identities. Genre, bio, socials, cover art specs — each persona gets its own space.',
  },
  {
    icon: '📅',
    title: 'Release Calendar',
    desc: 'See every drop across every persona. Prevent self-cannibalization. Never accidentally release two singles on the same Friday.',
  },
  {
    icon: '💰',
    title: 'Revenue by Persona',
    desc: 'Upload your DistroKid/TuneCore CSV — see earnings broken down by artist name. Know which persona actually pays.',
  },
  {
    icon: '🤖',
    title: 'AI Disclosure Assistant',
    desc: 'EU AI Act Article 50 is live. DDEX 5.0 requires AI fields. Get a per-release checklist so you never miss a disclosure.',
  },
  {
    icon: '🔗',
    title: 'Smart Link Hub',
    desc: 'One pre-save/streaming link per persona, all managed from one place. No more juggling 20 Linkfire accounts.',
  },
  {
    icon: '📊',
    title: 'Cross-Persona Analytics',
    desc: 'Total streams, top platforms, growth trends — rolled up or per persona. Export for tax season.',
  },
]

const PAIN_POINTS = [
  { pain: 'DistroKid gives you 2 artist slots on the basic plan', fix: 'Manage unlimited personas from one dashboard' },
  { pain: 'Spreadsheet hell tracking releases across 5+ names', fix: 'Visual calendar — all personas, color-coded' },
  { pain: 'No idea which persona is actually making money', fix: 'CSV upload → instant per-persona revenue breakdown' },
  { pain: 'EU AI Act just started — what boxes do I check?', fix: 'Per-release AI disclosure checklist with audit log' },
  { pain: 'Forgot you dropped a track the same day as another alias', fix: 'Collision alerts before you schedule' },
]

export default function PersonaHubLanding() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!email || submitting) return
    setSubmitting(true)
    setError('')
    try {
      const res = await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, product: 'persona-hub' }),
      })
      const data = await res.json()
      if (!res.ok && res.status !== 200) throw new Error(data.error || 'Something went wrong')
      setSubmitted(true)
    } catch (err) {
      setError(err.message || 'Network error — please try again')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      {/* Nav */}
      <nav className="fixed top-0 w-full z-50 border-b border-neutral-800/60 bg-neutral-950/80 backdrop-blur-lg">
        <div className="max-w-5xl mx-auto px-5 h-14 flex items-center justify-between">
          <span className="text-lg font-bold tracking-tight">Persona<span className="text-violet-400">Hub</span></span>
          <div className="flex items-center gap-4">
            <Link href="/persona-hub/dashboard" className="text-sm text-neutral-400 hover:text-neutral-200 transition">Dashboard</Link>
            <a href="#waitlist" className="text-sm bg-violet-500 hover:bg-violet-400 text-white px-4 py-1.5 rounded-md font-medium transition">Get Early Access</a>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-28 pb-20 px-5">
        <div className="max-w-3xl mx-auto text-center">
          <div className="inline-block text-xs font-semibold tracking-widest uppercase text-violet-400 border border-violet-400/30 rounded px-3 py-1 mb-6">
            For Multi-Persona Music Creators
          </div>
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight leading-[1.1] mb-5">
            20 artist names.<br />
            <span className="text-violet-400">One command center.</span>
          </h1>
          <p className="text-lg text-neutral-400 max-w-xl mx-auto mb-8 leading-relaxed">
            Release calendar, revenue tracking, AI compliance — all your personas in one dashboard.
            Built by someone who actually runs 20 aliases.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link href="/persona-hub/dashboard" className="bg-violet-500 hover:bg-violet-400 text-white px-6 py-3 rounded-lg font-semibold text-base transition shadow-lg shadow-violet-500/20">
              Try the Dashboard
            </Link>
            <a href="#waitlist" className="border border-neutral-700 hover:border-neutral-500 text-neutral-300 px-6 py-3 rounded-lg font-medium text-base transition">
              Join Waitlist
            </a>
          </div>
        </div>
      </section>

      {/* Who is this for */}
      <section className="border-y border-neutral-800/60 bg-neutral-900/40">
        <div className="max-w-4xl mx-auto px-5 py-8 grid grid-cols-2 sm:grid-cols-4 gap-6 text-center">
          {[
            ['🎵', 'AI Music Producers', 'Suno, Udio, custom models'],
            ['🎤', 'Multi-Alias Artists', '2+ names on DistroKid/TuneCore'],
            ['🎹', 'Beat Makers', 'Different brands for different genres'],
            ['🎧', 'Label Owners', 'Solo labels with multiple acts'],
          ].map(([icon, title, desc]) => (
            <div key={title}>
              <div className="text-2xl mb-2">{icon}</div>
              <div className="text-sm font-semibold">{title}</div>
              <div className="text-xs text-neutral-500 mt-1">{desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Pain → Fix */}
      <section className="py-20 px-5">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-12">
            <div className="text-xs font-semibold tracking-widest uppercase text-violet-400 mb-2">The Problem → The Fix</div>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">Managing multiple aliases shouldn't be this painful</h2>
          </div>
          <div className="space-y-3">
            {PAIN_POINTS.map((p, i) => (
              <div key={i} className="grid grid-cols-1 sm:grid-cols-[1fr_auto_1fr] gap-2 sm:gap-4 items-center bg-neutral-900/50 border border-neutral-800/60 rounded-lg p-4">
                <div className="text-sm text-neutral-500">{p.pain}</div>
                <div className="hidden sm:block text-violet-400 text-lg">→</div>
                <div className="text-sm font-medium text-neutral-200">{p.fix}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 px-5 bg-neutral-900/30">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-14">
            <div className="text-xs font-semibold tracking-widest uppercase text-violet-400 mb-2">Core Features</div>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">Everything you need. Nothing you don't.</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {FEATURES.map((f) => (
              <div key={f.title} className="bg-neutral-900/60 border border-neutral-800/60 rounded-xl p-6">
                <div className="text-2xl mb-3">{f.icon}</div>
                <h3 className="font-bold text-base mb-2">{f.title}</h3>
                <p className="text-sm text-neutral-400 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* AI Compliance Callout */}
      <section className="py-20 px-5">
        <div className="max-w-3xl mx-auto">
          <div className="bg-gradient-to-br from-violet-500/10 to-fuchsia-500/10 border border-violet-500/20 rounded-2xl p-8 sm:p-10">
            <div className="text-xs font-semibold tracking-widest uppercase text-violet-400 mb-3">EU AI Act Article 50 — Live Since Aug 2, 2026</div>
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight mb-4">AI disclosure is no longer optional.</h2>
            <p className="text-neutral-400 text-sm leading-relaxed mb-4">
              DDEX 5.0 now requires <code className="text-violet-300 bg-violet-500/10 px-1.5 py-0.5 rounded text-xs">IsAIGenerated</code>,
              <code className="text-violet-300 bg-violet-500/10 px-1.5 py-0.5 rounded text-xs">AIComponentType</code>, and
              <code className="text-violet-300 bg-violet-500/10 px-1.5 py-0.5 rounded text-xs">AITrainingDisclosure</code> fields
              on every release. Spotify adopted them September 2025. Fines up to €15M or 3% of revenue.
            </p>
            <p className="text-neutral-400 text-sm leading-relaxed">
              PersonaHub gives you a <strong className="text-neutral-200">per-release checklist</strong> that walks you through exactly which boxes to check,
              keeps an audit log, and tracks platform-specific requirements (Spotify AI Credits, Apple Music, YouTube).
            </p>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-20 px-5 bg-neutral-900/30">
        <div className="max-w-lg mx-auto text-center">
          <div className="text-xs font-semibold tracking-widest uppercase text-violet-400 mb-2">Pricing</div>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight mb-10">Start free. Upgrade when you're ready.</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-neutral-900/80 border border-neutral-700/60 rounded-2xl p-6 text-left">
              <div className="text-sm font-semibold text-neutral-400 mb-2">Free</div>
              <div className="text-3xl font-extrabold mb-1">$0</div>
              <p className="text-xs text-neutral-500 mb-4">Up to 3 personas</p>
              <ul className="space-y-2">
                {['3 personas', 'Release calendar', 'AI disclosure checklist', 'Basic revenue view'].map(f => (
                  <li key={f} className="flex gap-2 text-sm text-neutral-400">
                    <span className="text-violet-400 flex-shrink-0">✓</span>{f}
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-neutral-900/80 border-2 border-violet-500/50 rounded-2xl p-6 text-left relative">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-violet-500 text-white text-xs font-bold px-3 py-1 rounded-full">Popular</div>
              <div className="text-sm font-semibold text-violet-400 mb-2">Pro</div>
              <div className="text-3xl font-extrabold mb-1">$9<span className="text-lg font-normal text-neutral-500">/mo</span></div>
              <p className="text-xs text-neutral-500 mb-4">Unlimited personas</p>
              <ul className="space-y-2">
                {['Unlimited personas', 'CSV revenue import', 'Cross-persona analytics', 'Collision alerts', 'Export & audit log', 'Priority support'].map(f => (
                  <li key={f} className="flex gap-2 text-sm text-neutral-300">
                    <span className="text-violet-400 flex-shrink-0">✓</span>{f}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Waitlist */}
      <section id="waitlist" className="py-20 px-5">
        <div className="max-w-xl mx-auto text-center">
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight mb-4">
            Built by a 20-persona creator.<br />
            <span className="text-violet-400">For creators like you.</span>
          </h2>
          <p className="text-neutral-400 mb-8 text-base">
            Early access launching soon. Join the waitlist — first 50 users get Pro free for 6 months.
          </p>
          {submitted ? (
            <div className="bg-violet-500/10 border border-violet-500/30 rounded-lg p-6">
              <div className="text-violet-400 text-2xl mb-2">✓</div>
              <p className="text-neutral-200 font-medium">You're on the list. We'll email you when it's ready.</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                className="flex-1 bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-3 text-sm text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:border-violet-500 transition"
              />
              <button
                type="submit"
                disabled={submitting}
                className="bg-violet-500 hover:bg-violet-400 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-3 rounded-lg font-semibold text-sm transition shadow-lg shadow-violet-500/20 whitespace-nowrap"
              >
                {submitting ? 'Joining...' : 'Join Waitlist'}
              </button>
            </form>
          )}
          {error && <p className="text-red-400 text-sm mt-3">{error}</p>}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-neutral-800/60 py-8 px-5">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row justify-between items-center gap-4 text-xs text-neutral-600">
          <span>PersonaHub — Built for multi-persona music creators.</span>
          <div className="flex gap-4">
            <Link href="/persona-hub/dashboard" className="hover:text-neutral-400 transition">Dashboard</Link>
            <Link href="/" className="hover:text-neutral-400 transition">DetailBook</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
