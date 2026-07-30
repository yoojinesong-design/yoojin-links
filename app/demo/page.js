'use client'
import { useState } from 'react'
import Link from 'next/link'

const TODAY = new Date()
const fmt = (d) => d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })

const BOOKINGS = [
  { id: 1, customer: 'Sarah Chen', phone: '(512) 555-0142', vehicle: '2023 Tesla Model Y', type: 'suv', service: 'Full Detail', price: 170, deposit: 50, time: '8:00 AM', duration: '2.5 hrs', status: 'confirmed', notes: 'White exterior, pet hair in backseat' },
  { id: 2, customer: 'Marcus Johnson', phone: '(512) 555-0198', vehicle: '2022 BMW 3 Series', type: 'sedan', service: 'Ceramic Coating', price: 350, deposit: 50, time: '11:00 AM', duration: '4 hrs', status: 'confirmed', notes: 'Midnight blue. Wants showroom finish.' },
  { id: 3, customer: 'Emily Rodriguez', phone: '(512) 555-0267', vehicle: '2024 Ford F-150', type: 'truck', service: 'Exterior Wash', price: 90, deposit: 50, time: '4:00 PM', duration: '1 hr', status: 'pending', notes: '' },
]

const TOMORROW_BOOKINGS = [
  { id: 4, customer: 'David Kim', phone: '(512) 555-0311', vehicle: '2023 Honda Civic', type: 'sedan', service: 'Interior Deep Clean', price: 80, deposit: 50, time: '9:00 AM', duration: '1.5 hrs', status: 'confirmed', notes: 'Spilled coffee on passenger seat' },
  { id: 5, customer: 'Amanda Torres', phone: '(512) 555-0389', vehicle: '2022 Chevy Tahoe', type: 'suv', service: 'Full Detail', price: 170, deposit: 50, time: '11:30 AM', duration: '2.5 hrs', status: 'confirmed', notes: '' },
]

const RECENT_CUSTOMERS = [
  { name: 'Jake Williams', lastService: '12 days ago', service: 'Full Detail', total: 130, visits: 4 },
  { name: 'Lisa Park', lastService: '28 days ago', service: 'Ceramic Coating', total: 350, visits: 2 },
  { name: 'Robert Chen', lastService: '45 days ago', service: 'Exterior Wash', total: 60, visits: 7 },
  { name: 'Maria Santos', lastService: '62 days ago', service: 'Full Detail', total: 170, visits: 3, rebook: true },
  { name: 'Tom Bradley', lastService: '91 days ago', service: 'Interior Clean', total: 100, visits: 1, rebook: true },
]

export default function Dashboard() {
  const [tab, setTab] = useState('today')
  const [bookings, setBookings] = useState(BOOKINGS)
  const [completedId, setCompletedId] = useState(null)

  const handleComplete = (id) => {
    setCompletedId(id)
    setBookings(bookings.map(b => b.id === id ? { ...b, status: 'completed' } : b))
  }

  const todayRevenue = bookings.filter(b => b.status === 'completed').reduce((sum, b) => sum + b.price, 0)
  const todayPending = bookings.filter(b => b.status !== 'completed').reduce((sum, b) => sum + b.price, 0)
  const weekRevenue = 1240
  const monthRevenue = 4860

  return (
    <div className="min-h-screen bg-neutral-950">
      {/* Top bar */}
      <div className="border-b border-neutral-800/60 bg-neutral-900/40 sticky top-0 z-50 backdrop-blur-lg">
        <div className="max-w-3xl mx-auto px-5 h-14 flex items-center justify-between">
          <Link href="/" className="text-lg font-bold tracking-tight">
            Detail<span className="text-sky-400">Book</span>
          </Link>
          <div className="flex items-center gap-3">
            <span className="text-xs text-neutral-500">Demo Dashboard</span>
            <div className="w-8 h-8 bg-sky-500/15 border border-sky-500/30 rounded-full flex items-center justify-center text-xs font-bold text-sky-400">M</div>
          </div>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-5 py-6">
        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <div className="bg-neutral-900/60 border border-neutral-800/60 rounded-xl p-4">
            <div className="text-xs text-neutral-500 mb-1">Today</div>
            <div className="text-xl font-bold">${todayRevenue + todayPending}</div>
            <div className="text-xs text-neutral-600">{bookings.length} jobs</div>
          </div>
          <div className="bg-neutral-900/60 border border-neutral-800/60 rounded-xl p-4">
            <div className="text-xs text-neutral-500 mb-1">This Week</div>
            <div className="text-xl font-bold">${weekRevenue}</div>
            <div className="text-xs text-neutral-600">8 jobs</div>
          </div>
          <div className="bg-neutral-900/60 border border-neutral-800/60 rounded-xl p-4">
            <div className="text-xs text-neutral-500 mb-1">This Month</div>
            <div className="text-xl font-bold">${monthRevenue}</div>
            <div className="text-xs text-neutral-600">31 jobs</div>
          </div>
          <div className="bg-neutral-900/60 border border-neutral-800/60 rounded-xl p-4">
            <div className="text-xs text-neutral-500 mb-1">Rebook Due</div>
            <div className="text-xl font-bold text-amber-400">2</div>
            <div className="text-xs text-neutral-600">60+ days ago</div>
          </div>
        </div>

        {/* Booking link */}
        <div className="bg-sky-500/8 border border-sky-500/20 rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-6">
          <div>
            <div className="text-xs font-semibold text-sky-400 mb-1">Your Booking Link</div>
            <div className="text-sm text-neutral-300 font-mono">detailbook.app/mikes-mobile-detailing</div>
          </div>
          <Link href="/book/demo-detailer" className="text-xs bg-sky-500 hover:bg-sky-400 text-white px-4 py-2 rounded-md font-medium transition whitespace-nowrap">
            View Booking Page
          </Link>
        </div>

        {/* Tab navigation */}
        <div className="flex gap-1 mb-4 bg-neutral-900/40 rounded-lg p-1">
          {[
            { id: 'today', label: `Today (${bookings.length})` },
            { id: 'tomorrow', label: `Tomorrow (${TOMORROW_BOOKINGS.length})` },
            { id: 'customers', label: 'Customers' },
          ].map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex-1 py-2 rounded-md text-sm font-medium transition ${
                tab === t.id ? 'bg-neutral-800 text-neutral-100' : 'text-neutral-500 hover:text-neutral-300'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Today */}
        {tab === 'today' && (
          <div className="space-y-3">
            {bookings.map(b => (
              <div key={b.id} className={`border rounded-xl p-4 transition ${
                b.status === 'completed'
                  ? 'border-emerald-500/30 bg-emerald-500/5'
                  : b.status === 'pending'
                  ? 'border-amber-500/30 bg-amber-500/5'
                  : 'border-neutral-800/60 bg-neutral-900/40'
              }`}>
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="font-bold text-sm flex items-center gap-2">
                      {b.customer}
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        b.status === 'completed' ? 'bg-emerald-500/15 text-emerald-400'
                        : b.status === 'pending' ? 'bg-amber-500/15 text-amber-400'
                        : 'bg-sky-500/15 text-sky-400'
                      }`}>
                        {b.status === 'completed' ? 'Done' : b.status === 'pending' ? 'Unconfirmed' : 'Confirmed'}
                      </span>
                    </div>
                    <div className="text-xs text-neutral-500 mt-0.5">{b.phone}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-sky-400">${b.price}</div>
                    <div className="text-xs text-neutral-600">dep. ${b.deposit}</div>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs mb-3">
                  <div><span className="text-neutral-600">Time</span> <span className="text-neutral-300 ml-1">{b.time}</span></div>
                  <div><span className="text-neutral-600">Duration</span> <span className="text-neutral-300 ml-1">{b.duration}</span></div>
                  <div><span className="text-neutral-600">Service</span> <span className="text-neutral-300 ml-1">{b.service}</span></div>
                  <div><span className="text-neutral-600">Vehicle</span> <span className="text-neutral-300 ml-1 truncate">{b.vehicle}</span></div>
                </div>

                {b.notes && (
                  <div className="text-xs text-neutral-500 bg-neutral-800/40 rounded-lg px-3 py-2 mb-3">
                    {b.notes}
                  </div>
                )}

                {b.status !== 'completed' && (
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleComplete(b.id)}
                      className="flex-1 bg-emerald-500 hover:bg-emerald-400 text-white py-2 rounded-lg text-xs font-semibold transition"
                    >
                      Mark Complete → Send Payment Link
                    </button>
                  </div>
                )}

                {b.status === 'completed' && completedId === b.id && (
                  <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3 text-xs text-emerald-400">
                    Payment link sent to {b.customer} for ${b.price - b.deposit} (total ${b.price} minus ${b.deposit} deposit).
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Tomorrow */}
        {tab === 'tomorrow' && (
          <div className="space-y-3">
            <div className="bg-sky-500/8 border border-sky-500/20 rounded-lg p-3 text-xs text-sky-400 mb-2">
              SMS reminders will be sent automatically at 4:00 PM today (24hr before) and tomorrow morning (2hr before).
            </div>
            {TOMORROW_BOOKINGS.map(b => (
              <div key={b.id} className="border border-neutral-800/60 bg-neutral-900/40 rounded-xl p-4">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="font-bold text-sm">{b.customer}</div>
                    <div className="text-xs text-neutral-500">{b.phone}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-sky-400">${b.price}</div>
                    <div className="text-xs text-neutral-600">dep. ${b.deposit}</div>
                  </div>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  <div><span className="text-neutral-600">Time</span> <span className="text-neutral-300 ml-1">{b.time}</span></div>
                  <div><span className="text-neutral-600">Duration</span> <span className="text-neutral-300 ml-1">{b.duration}</span></div>
                  <div><span className="text-neutral-600">Service</span> <span className="text-neutral-300 ml-1">{b.service}</span></div>
                  <div><span className="text-neutral-600">Vehicle</span> <span className="text-neutral-300 ml-1 truncate">{b.vehicle}</span></div>
                </div>
                {b.notes && (
                  <div className="text-xs text-neutral-500 bg-neutral-800/40 rounded-lg px-3 py-2 mt-3">{b.notes}</div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Customers */}
        {tab === 'customers' && (
          <div className="space-y-2">
            {RECENT_CUSTOMERS.map((c, i) => (
              <div key={i} className={`border rounded-xl p-4 flex items-center justify-between ${
                c.rebook ? 'border-amber-500/30 bg-amber-500/5' : 'border-neutral-800/60 bg-neutral-900/40'
              }`}>
                <div>
                  <div className="font-bold text-sm flex items-center gap-2">
                    {c.name}
                    {c.rebook && (
                      <span className="text-xs bg-amber-500/15 text-amber-400 px-2 py-0.5 rounded-full font-medium">
                        Rebook due
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-neutral-500 mt-0.5">
                    Last: {c.service} · {c.lastService} · {c.visits} visits
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {c.rebook && (
                    <button className="text-xs bg-amber-500 hover:bg-amber-400 text-white px-3 py-1.5 rounded-md font-medium transition">
                      Send Rebook Text
                    </button>
                  )}
                  <div className="text-sm font-bold text-neutral-400">${c.total}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
