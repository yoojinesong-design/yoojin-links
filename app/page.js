'use client'
import { useState } from 'react'
import Link from 'next/link'

const FEATURES = [
  {
    icon: '🔗',
    title: 'Self-Booking Link',
    desc: 'Share one link on Instagram, Google, texts. Customers book themselves — no phone tag while you\'re detailing.',
  },
  {
    icon: '💳',
    title: 'Auto Deposits',
    desc: 'Collect $25–50 deposits at booking. The system asks, not you — no awkward conversations. No-shows drop to under 5%.',
  },
  {
    icon: '💬',
    title: 'SMS Reminders',
    desc: '24hr and 2hr reminders included in your plan. No per-message fees. Customers actually show up.',
  },
  {
    icon: '✅',
    title: 'Tap-to-Pay',
    desc: 'Job done? Tap "Complete" — customer gets a payment link. Balance minus deposit, auto-calculated.',
  },
  {
    icon: '🔄',
    title: 'Rebook Automation',
    desc: '60 or 90 days later: "Time for your next detail!" Auto-text with your booking link. 60–70% of revenue is repeat.',
  },
]

const PAIN_POINTS = [
  { before: 'Texting back and forth for every booking', after: 'One link. They book themselves.' },
  { before: 'Driving 30 min and they\'re not home', after: '$50 deposit collected upfront, auto.' },
  { before: 'Wet hands, can\'t answer the phone', after: 'Bookings come in while you work.' },
  { before: 'End of month — who paid? who didn\'t?', after: 'Every payment tracked. One dashboard.' },
  { before: 'Forgetting to follow up with regulars', after: 'Auto rebook text at 60/90 days.' },
]

export default function Home() {
  const [openFaq, setOpenFaq] = useState(null)
  const faqs = [
    { q: 'Do I need any special hardware?', a: 'Nope. Just your phone and a Stripe account. Setup takes 10 minutes.' },
    { q: 'What if a customer doesn\'t show?', a: 'You keep the deposit. The cancellation policy is shown at booking — they agreed to it.' },
    { q: 'Are SMS costs really included?', a: 'Yes. Up to 100 texts/month included. Most solo detailers use 60–80. No surprise fees.' },
    { q: 'Can I customize my services and prices?', a: 'Fully. Set different prices for Sedan, SUV, Truck. Add-ons like ceramic coating, interior deep clean, etc.' },
    { q: 'Is there a contract?', a: 'No. Month-to-month, cancel anytime. 14-day free trial to start.' },
  ]

  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [waitlistError, setWaitlistError] = useState('')

  const handleWaitlist = async (e) => {
    e.preventDefault()
    if (!email || submitting) return
    setSubmitting(true)
    setWaitlistError('')
    try {
      const res = await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, product: 'detailbook' }),
      })
      const data = await res.json()
      if (!res.ok && res.status !== 200) throw new Error(data.error || 'Something went wrong')
      setSubmitted(true)
    } catch (err) {
      setWaitlistError(err.message || 'Network error — please try again')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen">
      {/* Nav */}
      <nav className="fixed top-0 w-full z-50 border-b border-neutral-800/60 bg-neutral-950/80 backdrop-blur-lg">
        <div className="max-w-5xl mx-auto px-5 h-14 flex items-center justify-between">
          <span className="text-lg font-bold tracking-tight">Detail<span className="text-sky-400">Book</span></span>
          <div className="flex items-center gap-4">
            <Link href="/demo" className="text-sm text-neutral-400 hover:text-neutral-200 transition">Live Demo</Link>
            <a href="#waitlist" className="text-sm bg-sky-500 hover:bg-sky-400 text-white px-4 py-1.5 rounded-md font-medium transition">Join Waitlist</a>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-28 pb-20 px-5">
        <div className="max-w-3xl mx-auto text-center">
          <div className="inline-block text-xs font-semibold tracking-widest uppercase text-sky-400 border border-sky-400/30 rounded px-3 py-1 mb-6">
            Built for Solo Mobile Detailers
          </div>
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight leading-[1.1] mb-5">
            Stop texting.<br />
            <span className="text-sky-400">Start booking.</span>
          </h1>
          <p className="text-lg text-neutral-400 max-w-xl mx-auto mb-8 leading-relaxed">
            One link for bookings. Auto deposits. SMS reminders. Tap-to-pay.
            Everything a solo detailer needs — nothing you don't. <strong className="text-neutral-300">$39/mo.</strong>
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link href="/setup" className="bg-sky-500 hover:bg-sky-400 text-white px-6 py-3 rounded-lg font-semibold text-base transition shadow-lg shadow-sky-500/20">
              Start 14-Day Free Trial
            </Link>
            <Link href="/demo" className="border border-neutral-700 hover:border-neutral-500 text-neutral-300 px-6 py-3 rounded-lg font-medium text-base transition">
              See Live Demo
            </Link>
          </div>
          <p className="text-xs text-neutral-600 mt-4">No credit card required. Setup in 10 minutes.</p>
        </div>
      </section>

      {/* Stats bar */}
      <section className="border-y border-neutral-800/60 bg-neutral-900/40">
        <div className="max-w-4xl mx-auto px-5 py-8 grid grid-cols-2 sm:grid-cols-4 gap-6 text-center">
          {[
            ['15–25%', 'No-show rate without deposits'],
            ['3+ hrs/day', 'Spent on texts, calls, admin'],
            ['63%', 'Of detailers use no software'],
            ['$39/mo', 'Everything included'],
          ].map(([num, label]) => (
            <div key={label}>
              <div className="text-2xl font-bold text-sky-400">{num}</div>
              <div className="text-xs text-neutral-500 mt-1">{label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Before/After */}
      <section className="py-20 px-5">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-12">
            <div className="text-xs font-semibold tracking-widest uppercase text-sky-400 mb-2">Before → After</div>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">Your day, minus the chaos</h2>
          </div>
          <div className="space-y-3">
            {PAIN_POINTS.map((p, i) => (
              <div key={i} className="grid grid-cols-1 sm:grid-cols-[1fr_auto_1fr] gap-2 sm:gap-4 items-center bg-neutral-900/50 border border-neutral-800/60 rounded-lg p-4">
                <div className="text-sm text-neutral-500 line-through">{p.before}</div>
                <div className="hidden sm:block text-sky-400 text-lg">→</div>
                <div className="text-sm font-medium text-neutral-200">{p.after}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 px-5 bg-neutral-900/30">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-14">
            <div className="text-xs font-semibold tracking-widest uppercase text-sky-400 mb-2">5 Things, Done Right</div>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">Not 50 features. Just the 5 you need.</h2>
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

      {/* How it works */}
      <section className="py-20 px-5">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-14">
            <div className="text-xs font-semibold tracking-widest uppercase text-sky-400 mb-2">How It Works</div>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">10 minutes to your booking page</h2>
          </div>
          <div className="space-y-6">
            {[
              { step: '1', title: 'Sign up & add your services', desc: 'Exterior wash, full detail, ceramic coating — set your prices by vehicle size.' },
              { step: '2', title: 'Share your link', desc: 'Put it in your Instagram bio, Google listing, and text signature. One link does it all.' },
              { step: '3', title: 'Customers book + pay deposit', desc: 'They pick a service, choose a time, pay $50 deposit. You get notified.' },
              { step: '4', title: 'Show up, detail, get paid', desc: 'Reminders sent automatically. Finish the job, tap Complete, they pay the balance.' },
            ].map((s) => (
              <div key={s.step} className="flex gap-5 items-start">
                <div className="w-9 h-9 rounded-full bg-sky-500/15 border border-sky-500/30 text-sky-400 font-bold text-sm flex items-center justify-center flex-shrink-0 mt-0.5">{s.step}</div>
                <div>
                  <h3 className="font-bold text-base mb-1">{s.title}</h3>
                  <p className="text-sm text-neutral-400 leading-relaxed">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-20 px-5 bg-neutral-900/30">
        <div className="max-w-md mx-auto text-center">
          <div className="text-xs font-semibold tracking-widest uppercase text-sky-400 mb-2">Simple Pricing</div>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight mb-10">One plan. Everything included.</h2>
          <div className="bg-neutral-900/80 border border-neutral-700/60 rounded-2xl p-8">
            <div className="text-5xl font-extrabold mb-1">$39<span className="text-lg font-normal text-neutral-500">/mo</span></div>
            <p className="text-sm text-neutral-500 mb-6">14-day free trial. No credit card required.</p>
            <ul className="text-left space-y-3 mb-8">
              {[
                'Unlimited bookings',
                'Custom booking page (yourname.detailbook.app)',
                'Deposit collection via Stripe',
                '100 SMS reminders/mo included',
                'Tap-to-pay at job completion',
                'Customer history & rebook automation',
                'Mobile-first dashboard',
                'Revenue reports for tax time',
              ].map((item) => (
                <li key={item} className="flex gap-2 text-sm text-neutral-300">
                  <span className="text-sky-400 flex-shrink-0">✓</span>
                  {item}
                </li>
              ))}
            </ul>
            <Link href="/setup" className="block w-full bg-sky-500 hover:bg-sky-400 text-white py-3 rounded-lg font-semibold transition shadow-lg shadow-sky-500/20">
              Start Free Trial
            </Link>
          </div>
          <p className="text-xs text-neutral-600 mt-6">Stripe processing fees (2.9% + 30¢) apply to customer payments. That's it.</p>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-20 px-5">
        <div className="max-w-2xl mx-auto">
          <h2 className="text-2xl font-bold tracking-tight text-center mb-10">Questions</h2>
          <div className="space-y-2">
            {faqs.map((faq, i) => (
              <div key={i} className="border border-neutral-800/60 rounded-lg overflow-hidden">
                <button
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="w-full flex justify-between items-center px-5 py-4 text-left hover:bg-neutral-900/40 transition"
                >
                  <span className="font-medium text-sm">{faq.q}</span>
                  <span className="text-neutral-500 text-lg ml-4">{openFaq === i ? '−' : '+'}</span>
                </button>
                {openFaq === i && (
                  <div className="px-5 pb-4 text-sm text-neutral-400 leading-relaxed">{faq.a}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA / Waitlist */}
      <section id="waitlist" className="py-20 px-5 border-t border-neutral-800/60">
        <div className="max-w-xl mx-auto text-center">
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight mb-4">
            Your next detail is booked<br />
            <span className="text-sky-400">before you finish this one.</span>
          </h2>
          <p className="text-neutral-400 mb-8 text-base">
            Early access launching soon. Join the waitlist — first 100 detailers get 3 months free.
          </p>
          {submitted ? (
            <div className="bg-sky-500/10 border border-sky-500/30 rounded-lg p-6">
              <div className="text-sky-400 text-2xl mb-2">✓</div>
              <p className="text-neutral-200 font-medium">You're on the list. We'll email you when it's ready.</p>
            </div>
          ) : (
            <form onSubmit={handleWaitlist} className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                className="flex-1 bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-3 text-sm text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:border-sky-500 transition"
              />
              <button
                type="submit"
                disabled={submitting}
                className="bg-sky-500 hover:bg-sky-400 disabled:opacity-60 text-white px-6 py-3 rounded-lg font-semibold text-sm transition shadow-lg shadow-sky-500/20 whitespace-nowrap"
              >
                {submitting ? 'Joining...' : 'Join Waitlist'}
              </button>
            </form>
          )}
          {waitlistError && <p className="text-red-400 text-sm mt-3">{waitlistError}</p>}
          <div className="mt-6">
            <Link href="/setup" className="text-sm text-neutral-500 hover:text-neutral-300 transition">
              or start your 14-day free trial now →
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-neutral-800/60 py-8 px-5">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row justify-between items-center gap-4 text-xs text-neutral-600">
          <span>DetailBook — Built for solo detailers, by someone who gets it.</span>
          <div className="flex gap-4">
            <Link href="/demo" className="hover:text-neutral-400 transition">Demo</Link>
            <Link href="/persona-hub" className="hover:text-neutral-400 transition">PersonaHub</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
