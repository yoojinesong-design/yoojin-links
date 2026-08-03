'use client'
import { useState } from 'react'
import Link from 'next/link'

const VEHICLE_SIZES = ['Sedan / Coupe', 'SUV / Crossover', 'Truck / Van']

const DEFAULT_SERVICES = [
  { id: 1, name: 'Exterior Wash', prices: [60, 80, 90], duration: 60, enabled: true },
  { id: 2, name: 'Interior Deep Clean', prices: [80, 100, 120], duration: 90, enabled: true },
  { id: 3, name: 'Full Detail (Ext + Int)', prices: [130, 170, 200], duration: 150, enabled: true },
  { id: 4, name: 'Ceramic Coating', prices: [350, 450, 500], duration: 240, enabled: false },
  { id: 5, name: 'Paint Correction + Ceramic', prices: [600, 750, 850], duration: 480, enabled: false },
]

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

export default function SetupPage() {
  const [step, setStep] = useState(1)
  const [business, setBusiness] = useState({ name: '', location: '', phone: '' })
  const [services, setServices] = useState(DEFAULT_SERVICES)
  const [deposit, setDeposit] = useState(50)
  const [hours, setHours] = useState({ start: '08:00', end: '18:00' })
  const [workDays, setWorkDays] = useState(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'])
  const [completed, setCompleted] = useState(false)

  const slug = business.name
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, '')
    .replace(/\s+/g, '-')
    .slice(0, 40) || 'your-business'

  const toggleService = (id) => {
    setServices(prev => prev.map(s => s.id === id ? { ...s, enabled: !s.enabled } : s))
  }

  const updatePrice = (id, idx, val) => {
    setServices(prev => prev.map(s => {
      if (s.id !== id) return s
      const newPrices = [...s.prices]
      newPrices[idx] = parseInt(val) || 0
      return { ...s, prices: newPrices }
    }))
  }

  const toggleDay = (day) => {
    setWorkDays(prev =>
      prev.includes(day) ? prev.filter(d => d !== day) : [...prev, day]
    )
  }

  const totalSteps = 4
  const canAdvance = step === 1 ? business.name.length > 0
    : step === 2 ? services.some(s => s.enabled)
    : step === 3 ? workDays.length > 0
    : true

  if (completed) {
    return (
      <div className="min-h-screen bg-neutral-950 text-neutral-100 flex items-center justify-center px-5">
        <div className="max-w-md text-center">
          <div className="w-16 h-16 bg-emerald-500/15 border border-emerald-500/30 rounded-2xl flex items-center justify-center text-3xl mx-auto mb-6">
            ✓
          </div>
          <h1 className="text-2xl font-bold tracking-tight mb-3">You're all set!</h1>
          <p className="text-neutral-400 text-sm mb-6">
            Your booking page is live. Share this link on Instagram, Google, texts — anywhere.
          </p>

          <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4 mb-6">
            <div className="text-xs font-semibold text-sky-400 mb-1">Your Booking Link</div>
            <div className="text-base text-neutral-200 font-mono">detailbook.app/{slug}</div>
          </div>

          <div className="space-y-3">
            <Link href="/book/demo-detailer" className="block w-full bg-sky-500 hover:bg-sky-400 text-white py-3 rounded-lg font-semibold transition">
              Preview Your Booking Page
            </Link>
            <Link href="/demo" className="block w-full border border-neutral-700 hover:border-neutral-500 text-neutral-300 py-3 rounded-lg font-medium transition">
              Go to Dashboard
            </Link>
          </div>

          <div className="mt-8 bg-sky-500/8 border border-sky-500/20 rounded-xl p-4">
            <p className="text-xs text-sky-400 font-semibold mb-1">Next steps</p>
            <ul className="text-xs text-neutral-400 space-y-1 text-left">
              <li>• Connect your Stripe account for payments</li>
              <li>• Add your booking link to Instagram bio</li>
              <li>• Update your Google Business listing</li>
              <li>• Set up your text signature with the link</li>
            </ul>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      {/* Header */}
      <div className="border-b border-neutral-800/60 bg-neutral-900/40">
        <div className="max-w-lg mx-auto px-5 h-14 flex items-center justify-between">
          <Link href="/" className="text-lg font-bold tracking-tight">
            Detail<span className="text-sky-400">Book</span>
          </Link>
          <span className="text-xs text-neutral-500">Setup · Step {step} of {totalSteps}</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="max-w-lg mx-auto px-5 pt-4">
        <div className="flex gap-1.5">
          {Array.from({ length: totalSteps }, (_, i) => (
            <div
              key={i}
              className={`h-1 flex-1 rounded-full transition-all ${
                i < step ? 'bg-sky-500' : 'bg-neutral-800'
              }`}
            />
          ))}
        </div>
      </div>

      <div className="max-w-lg mx-auto px-5 py-8">
        {/* Step 1: Business Info */}
        {step === 1 && (
          <div>
            <h2 className="text-xl font-bold tracking-tight mb-1">Your business</h2>
            <p className="text-sm text-neutral-500 mb-6">This shows on your booking page.</p>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Business Name</label>
                <input
                  type="text"
                  value={business.name}
                  onChange={e => setBusiness(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="e.g. Mike's Mobile Detailing"
                  className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-3 text-sm text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:border-sky-500 transition"
                />
                {business.name && (
                  <p className="text-xs text-neutral-600 mt-1.5 font-mono">detailbook.app/{slug}</p>
                )}
              </div>
              <div>
                <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Location</label>
                <input
                  type="text"
                  value={business.location}
                  onChange={e => setBusiness(prev => ({ ...prev, location: e.target.value }))}
                  placeholder="e.g. Austin, TX"
                  className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-3 text-sm text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:border-sky-500 transition"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Phone</label>
                <input
                  type="tel"
                  value={business.phone}
                  onChange={e => setBusiness(prev => ({ ...prev, phone: e.target.value }))}
                  placeholder="(512) 555-0100"
                  className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-3 text-sm text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:border-sky-500 transition"
                />
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Services & Pricing */}
        {step === 2 && (
          <div>
            <h2 className="text-xl font-bold tracking-tight mb-1">Services & pricing</h2>
            <p className="text-sm text-neutral-500 mb-6">Toggle on the services you offer. Set prices by vehicle size.</p>

            <div className="space-y-3">
              {services.map(s => (
                <div key={s.id} className={`border rounded-xl overflow-hidden transition ${
                  s.enabled ? 'border-neutral-700/60 bg-neutral-900/40' : 'border-neutral-800/40 bg-neutral-900/20 opacity-60'
                }`}>
                  <div className="flex items-center gap-3 px-4 py-3">
                    <button
                      onClick={() => toggleService(s.id)}
                      className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 transition ${
                        s.enabled ? 'bg-sky-500 border-sky-500' : 'border-neutral-600'
                      }`}
                    >
                      {s.enabled && <span className="text-white text-xs">✓</span>}
                    </button>
                    <span className="text-sm font-medium flex-1">{s.name}</span>
                    <span className="text-xs text-neutral-500">{Math.floor(s.duration / 60)}h{s.duration % 60 > 0 ? ` ${s.duration % 60}m` : ''}</span>
                  </div>

                  {s.enabled && (
                    <div className="px-4 pb-3 grid grid-cols-3 gap-2">
                      {VEHICLE_SIZES.map((v, idx) => (
                        <div key={v}>
                          <label className="block text-[10px] text-neutral-500 mb-1">{v}</label>
                          <div className="relative">
                            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500 text-xs">$</span>
                            <input
                              type="number"
                              value={s.prices[idx]}
                              onChange={e => updatePrice(s.id, idx, e.target.value)}
                              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg pl-7 pr-2 py-2 text-xs text-neutral-100 focus:outline-none focus:border-sky-500 transition tabular-nums"
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="mt-6">
              <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Deposit Amount</label>
              <div className="flex items-center gap-3">
                <div className="relative flex-1 max-w-[120px]">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500 text-sm">$</span>
                  <input
                    type="number"
                    value={deposit}
                    onChange={e => setDeposit(parseInt(e.target.value) || 0)}
                    className="w-full bg-neutral-900 border border-neutral-700 rounded-lg pl-7 pr-3 py-3 text-sm text-neutral-100 focus:outline-none focus:border-sky-500 transition tabular-nums"
                  />
                </div>
                <span className="text-xs text-neutral-500">collected at booking to reduce no-shows</span>
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Availability */}
        {step === 3 && (
          <div>
            <h2 className="text-xl font-bold tracking-tight mb-1">Availability</h2>
            <p className="text-sm text-neutral-500 mb-6">When can customers book you?</p>

            <div className="mb-6">
              <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">Work Days</label>
              <div className="grid grid-cols-2 gap-2">
                {DAYS.map(day => (
                  <button
                    key={day}
                    onClick={() => toggleDay(day)}
                    className={`py-2.5 rounded-lg text-sm font-medium transition border ${
                      workDays.includes(day)
                        ? 'bg-sky-500/15 border-sky-500/30 text-sky-400'
                        : 'bg-neutral-900 border-neutral-800 text-neutral-600 hover:text-neutral-400'
                    }`}
                  >
                    {day}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Start Time</label>
                <select
                  value={hours.start}
                  onChange={e => setHours(prev => ({ ...prev, start: e.target.value }))}
                  className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-3 text-sm text-neutral-100 focus:outline-none focus:border-sky-500 transition"
                >
                  {Array.from({ length: 12 }, (_, i) => i + 5).map(h => (
                    <option key={h} value={`${String(h).padStart(2, '0')}:00`}>
                      {h > 12 ? `${h - 12}:00 PM` : h === 12 ? '12:00 PM' : `${h}:00 AM`}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">End Time</label>
                <select
                  value={hours.end}
                  onChange={e => setHours(prev => ({ ...prev, end: e.target.value }))}
                  className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-3 text-sm text-neutral-100 focus:outline-none focus:border-sky-500 transition"
                >
                  {Array.from({ length: 12 }, (_, i) => i + 12).map(h => (
                    <option key={h} value={`${String(h).padStart(2, '0')}:00`}>
                      {h > 12 ? `${h - 12}:00 PM` : '12:00 PM'}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Review */}
        {step === 4 && (
          <div>
            <h2 className="text-xl font-bold tracking-tight mb-1">Review & launch</h2>
            <p className="text-sm text-neutral-500 mb-6">Everything look good?</p>

            <div className="space-y-4">
              <div className="bg-neutral-900/40 border border-neutral-800/60 rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Business</h3>
                  <button onClick={() => setStep(1)} className="text-xs text-sky-400 hover:text-sky-300 transition">Edit</button>
                </div>
                <div className="text-sm font-medium">{business.name || 'Unnamed'}</div>
                {business.location && <div className="text-xs text-neutral-500">{business.location}</div>}
                {business.phone && <div className="text-xs text-neutral-500">{business.phone}</div>}
              </div>

              <div className="bg-neutral-900/40 border border-neutral-800/60 rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Services</h3>
                  <button onClick={() => setStep(2)} className="text-xs text-sky-400 hover:text-sky-300 transition">Edit</button>
                </div>
                <div className="space-y-1.5">
                  {services.filter(s => s.enabled).map(s => (
                    <div key={s.id} className="flex items-center justify-between text-sm">
                      <span>{s.name}</span>
                      <span className="text-xs text-neutral-500 tabular-nums">${s.prices[0]}–${s.prices[2]}</span>
                    </div>
                  ))}
                </div>
                <div className="text-xs text-neutral-600 mt-2">Deposit: ${deposit} per booking</div>
              </div>

              <div className="bg-neutral-900/40 border border-neutral-800/60 rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Availability</h3>
                  <button onClick={() => setStep(3)} className="text-xs text-sky-400 hover:text-sky-300 transition">Edit</button>
                </div>
                <div className="text-sm">{workDays.join(', ')}</div>
                <div className="text-xs text-neutral-500 mt-1">
                  {parseInt(hours.start) > 12 ? `${parseInt(hours.start) - 12} PM` : `${parseInt(hours.start)} AM`}
                  {' – '}
                  {parseInt(hours.end) > 12 ? `${parseInt(hours.end) - 12} PM` : `${parseInt(hours.end)} AM`}
                </div>
              </div>

              <div className="bg-sky-500/8 border border-sky-500/20 rounded-xl p-4">
                <div className="text-xs font-semibold text-sky-400 mb-1">Your Booking Link</div>
                <div className="text-base text-neutral-200 font-mono">detailbook.app/{slug}</div>
              </div>
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="flex gap-3 mt-8">
          {step > 1 && (
            <button
              onClick={() => setStep(s => s - 1)}
              className="border border-neutral-700 hover:border-neutral-500 text-neutral-300 px-6 py-3 rounded-lg font-medium text-sm transition"
            >
              Back
            </button>
          )}
          <button
            onClick={() => {
              if (step < totalSteps) setStep(s => s + 1)
              else setCompleted(true)
            }}
            disabled={!canAdvance}
            className="flex-1 bg-sky-500 hover:bg-sky-400 disabled:opacity-40 disabled:hover:bg-sky-500 text-white py-3 rounded-lg font-semibold text-sm transition"
          >
            {step === totalSteps ? 'Launch Booking Page' : 'Continue'}
          </button>
        </div>
      </div>
    </div>
  )
}
