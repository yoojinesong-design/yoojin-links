'use client'
import { useState } from 'react'
import Link from 'next/link'
import {
  SHOP_INFO, TABS, PLATFORMS, RECENT_ORDERS, TODAY_RESERVATIONS,
  ALL_ORDERS, RESERVATIONS_TODAY, RESERVATIONS_TOMORROW,
  MENU_ITEMS, REVIEWS, MESSAGES_SENT, MESSAGE_TEMPLATES,
} from '@/data/kai-sushi-demo'

function fmt$(n) { return '$' + n.toFixed(2) }

function StatusBadge({ status }) {
  const styles = {
    Pending: 'bg-yellow-600/30 text-yellow-300 border-yellow-600/50',
    Preparing: 'bg-orange-600/30 text-orange-300 border-orange-600/50',
    Ready: 'bg-blue-600/30 text-blue-300 border-blue-600/50',
    Done: 'bg-green-600/30 text-green-300 border-green-600/50',
    Confirmed: 'bg-green-600/30 text-green-300 border-green-600/50',
    Cancelled: 'bg-red-600/30 text-red-300 border-red-600/50',
  }
  return (
    <span className={`inline-block px-3 py-1 rounded-full text-sm font-bold border ${styles[status] || 'bg-neutral-700 text-neutral-300'}`}>
      {status}
    </span>
  )
}

function PlatformBadge({ platform }) {
  const p = PLATFORMS[platform]
  if (!p) return null
  return (
    <span className="inline-block px-3 py-1 rounded-full text-sm font-bold text-white" style={{ backgroundColor: p.color }}>
      {platform}
    </span>
  )
}

function StatCard({ icon, label, value, sub, subColor }) {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 flex flex-col gap-2">
      <div className="text-base text-neutral-400 flex items-center gap-2">
        <span className="text-xl">{icon}</span>
        <span className="font-medium">{label}</span>
      </div>
      <div className="text-2xl font-bold text-white">{value}</div>
      {sub && <div className="text-sm font-semibold" style={{ color: subColor || '#9CA3AF' }}>{sub}</div>}
    </div>
  )
}

/* ── Tab: Today ── */
function TabToday() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon="💰" label="Today's Revenue" value={fmt$(1842.50)} sub="+18% vs last Sat ↑" subColor="#22C55E" />
        <StatCard icon="🛵" label="Delivery Orders" value="31" sub="DD 14 / UE 10 / Phone 7" />
        <StatCard icon="📅" label="Reservations" value="6 tables" sub="23 guests total" />
        <StatCard icon="⭐" label="New Reviews" value="2" sub="Avg ⭐ 4.4" />
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
        <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">🔔 Recent Orders</h2>
        <div className="space-y-3">
          {RECENT_ORDERS.map((o, i) => (
            <div key={i} className="flex flex-wrap items-center gap-3 bg-neutral-800/60 rounded-xl p-4 border border-neutral-700/50">
              <span className="text-lg font-bold text-neutral-300 min-w-[80px]">{o.time}</span>
              <PlatformBadge platform={o.platform} />
              <span className="text-base text-neutral-200 flex-1 min-w-[140px]">{o.items}</span>
              <span className="text-lg font-bold text-amber-400 min-w-[80px] text-right">{fmt$(o.amount)}</span>
              <StatusBadge status={o.status} />
            </div>
          ))}
        </div>
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
        <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">📅 Today's Reservations</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {TODAY_RESERVATIONS.map((r, i) => (
            <div key={i} className="bg-neutral-800/60 rounded-xl p-4 border border-neutral-700/50">
              <div className="flex items-center justify-between mb-2">
                <span className="text-lg font-bold text-amber-400">🕐 {r.time}</span>
                <span className="text-base text-neutral-300">{r.name} · {r.size} guests</span>
              </div>
              {r.request && <div className="text-sm text-neutral-400 bg-neutral-700/40 rounded-lg px-3 py-2">💬 {r.request}</div>}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

/* ── Tab: Orders ── */
function TabOrders() {
  const [filter, setFilter] = useState('All')
  const filters = ['All', 'DoorDash', 'Uber Eats', 'Walk-in', 'Phone']
  const filterMap = { 'Uber Eats': 'UberEats' }
  const filtered = filter === 'All' ? ALL_ORDERS : ALL_ORDERS.filter(o => o.platform === (filterMap[filter] || filter))

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2">
        {filters.map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`px-5 py-3 rounded-xl font-bold transition-colors border ${filter === f ? 'bg-rose-500 text-white border-rose-400' : 'bg-neutral-800 text-neutral-300 border-neutral-700 hover:bg-neutral-700'}`}
            style={{ minHeight: '48px' }}>
            {f}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {filtered.map(o => (
          <div key={o.id} className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
            <div className="flex flex-wrap items-center gap-3 mb-3">
              <span className="text-lg font-bold text-neutral-300">🕐 {o.time}</span>
              <PlatformBadge platform={o.platform} />
              <span className="text-base text-neutral-400">{o.customer}</span>
              <div className="flex-1" />
              <StatusBadge status={o.status} />
            </div>
            <div className="text-base text-neutral-200 mb-2">🍣 {o.items}</div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="text-xl font-bold text-amber-400">{fmt$(o.amount)}</span>
              <div className="flex gap-2">
                {o.status === 'Preparing' && (
                  <button className="px-6 py-3 rounded-xl font-bold text-white bg-blue-600 hover:bg-blue-500 transition-colors" style={{ minHeight: '48px' }}>
                    ✅ Ready
                  </button>
                )}
                {o.status !== 'Done' && (
                  <button className="px-6 py-3 rounded-xl font-bold text-white bg-green-600 hover:bg-green-500 transition-colors" style={{ minHeight: '48px' }}>
                    ✔️ Done
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── Tab: Reservations ── */
function TabReservations() {
  const today = new Date()
  const tomorrow = new Date(today)
  tomorrow.setDate(tomorrow.getDate() + 1)
  const fmtDate = (d) => d.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })

  const renderRow = (r) => (
    <div key={r.id} className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
      <div className="flex flex-wrap items-center gap-3 mb-2">
        <span className="text-lg font-bold text-amber-400">🕐 {r.time}</span>
        <span className="text-lg text-white font-bold">{r.name}</span>
        <span className="text-base text-neutral-400">📞 {r.phone}</span>
        <span className="text-lg text-neutral-200 font-semibold">👥 {r.size}</span>
        <div className="flex-1" />
        <StatusBadge status={r.status} />
      </div>
      {r.request && <div className="text-base text-neutral-300 bg-neutral-800/60 rounded-lg px-4 py-2 mb-3">💬 {r.request}</div>}
      <div className="flex flex-wrap gap-2">
        {r.status === 'Pending' && (
          <button className="px-5 py-3 rounded-xl font-bold text-white bg-green-600 hover:bg-green-500 transition-colors" style={{ minHeight: '48px' }}>
            ✅ Confirm
          </button>
        )}
        <button className="px-5 py-3 rounded-xl font-bold text-white bg-neutral-700 hover:bg-neutral-600 transition-colors" style={{ minHeight: '48px' }}>
          📞 Call
        </button>
      </div>
    </div>
  )

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold text-white">📅 {fmtDate(today)} (Today)</h2>
        <button className="px-6 py-3 rounded-xl font-bold text-white bg-rose-500 hover:bg-rose-400 transition-colors" style={{ minHeight: '48px' }}>
          ➕ New Reservation
        </button>
      </div>
      <div className="space-y-3">{RESERVATIONS_TODAY.map(renderRow)}</div>

      <h2 className="text-xl font-bold text-white pt-2">📅 {fmtDate(tomorrow)} (Tomorrow)</h2>
      <div className="space-y-3">{RESERVATIONS_TOMORROW.map(renderRow)}</div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 text-center">
          <div className="text-base text-neutral-400 mb-1">📅 Today</div>
          <div className="text-2xl font-bold text-amber-400">{RESERVATIONS_TODAY.length} tables</div>
        </div>
        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 text-center">
          <div className="text-base text-neutral-400 mb-1">📅 Tomorrow</div>
          <div className="text-2xl font-bold text-amber-400">{RESERVATIONS_TOMORROW.length} tables</div>
        </div>
      </div>
    </div>
  )
}

/* ── Tab: My Shop ── */
function TabMyShop() {
  const info = [
    { icon: '🍣', label: 'Restaurant', value: SHOP_INFO.name },
    { icon: '📍', label: 'Address', value: SHOP_INFO.address },
    { icon: '📞', label: 'Phone', value: SHOP_INFO.phone },
    { icon: '⏰', label: 'Hours', value: SHOP_INFO.hours },
    { icon: '🚫', label: 'Closed', value: SHOP_INFO.closedDay },
  ]

  return (
    <div className="space-y-6">
      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
        <h2 className="text-xl font-bold text-white mb-4">🏪 Shop Info</h2>
        <div className="space-y-4">
          {info.map((item, i) => (
            <div key={i} className="flex flex-wrap items-center justify-between gap-3 bg-neutral-800/60 rounded-xl p-4 border border-neutral-700/50">
              <div className="flex items-center gap-3 flex-1 min-w-[200px]">
                <span className="text-xl">{item.icon}</span>
                <div>
                  <div className="text-sm text-neutral-400">{item.label}</div>
                  <div className="text-lg text-white font-semibold">{item.value}</div>
                </div>
              </div>
              <button className="px-5 py-3 rounded-xl font-bold text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 transition-colors" style={{ minHeight: '48px' }}>
                ✏️ Edit
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
        <h2 className="text-xl font-bold text-white mb-4">🍣 Menu</h2>
        {MENU_ITEMS.map((cat, ci) => (
          <div key={ci} className="mb-6 last:mb-0">
            <h3 className="text-base font-bold text-rose-400 uppercase tracking-wider mb-3">{cat.category}</h3>
            <div className="space-y-2">
              {cat.items.map((item, j) => (
                <div key={j} className="flex flex-wrap items-center justify-between gap-2 bg-neutral-800/60 rounded-xl p-4 border border-neutral-700/50">
                  <div>
                    <span className="text-lg text-white font-bold">{item.name}</span>
                    {item.desc && <div className="text-sm text-neutral-400 mt-0.5">{item.desc}</div>}
                  </div>
                  <span className="text-lg text-amber-400 font-semibold">{fmt$(item.price)}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
        <h2 className="text-xl font-bold text-white mb-4">🌐 Online Platforms</h2>
        <div className="space-y-3">
          {[
            { name: 'Yelp', rating: '4.4★ · 468 reviews', color: '#D32323', connected: true },
            { name: 'Google Business', rating: '4.3★ · 380+ reviews', color: '#4285F4', connected: true },
            { name: 'DoorDash', rating: 'Active', color: '#FF3008', connected: true },
            { name: 'Uber Eats', rating: 'Active', color: '#06C167', connected: true },
          ].map((p, i) => (
            <div key={i} className="flex flex-wrap items-center gap-3 bg-neutral-800/60 rounded-xl p-4 border border-neutral-700/50">
              <span className="text-lg font-bold text-white" style={{ color: p.color }}>{p.name}</span>
              <span className="text-base text-neutral-300">{p.rating}</span>
              <div className="flex-1" />
              <span className="text-green-400 font-bold text-sm">✅ Connected</span>
            </div>
          ))}
        </div>
        <div className="text-sm text-neutral-500 mt-3">🏆 Neighborhood Favorite: 2020, 2022, 2023</div>
      </div>
    </div>
  )
}

/* ── Tab: Reviews ── */
function TabReviews() {
  const [reviewFilter, setReviewFilter] = useState('All')
  const filters = ['All', 'Needs Reply', 'Lowest First']

  let filtered = [...REVIEWS]
  if (reviewFilter === 'Needs Reply') filtered = filtered.filter(r => !r.reply)
  if (reviewFilter === 'Lowest First') filtered = filtered.sort((a, b) => a.stars - b.stars)

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 text-center">
          <div className="text-base text-neutral-400 mb-1">⭐ Avg Rating</div>
          <div className="text-2xl font-bold text-amber-400">{SHOP_INFO.rating}</div>
        </div>
        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 text-center">
          <div className="text-base text-neutral-400 mb-1">📝 Total Reviews</div>
          <div className="text-2xl font-bold text-white">{SHOP_INFO.reviewCount}</div>
        </div>
        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 text-center">
          <div className="text-base text-neutral-400 mb-1">📈 This Month</div>
          <div className="text-2xl font-bold text-green-400">+12</div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {filters.map(f => (
          <button key={f} onClick={() => setReviewFilter(f)}
            className={`px-5 py-3 rounded-xl font-bold transition-colors border ${reviewFilter === f ? 'bg-rose-500 text-white border-rose-400' : 'bg-neutral-800 text-neutral-300 border-neutral-700 hover:bg-neutral-700'}`}
            style={{ minHeight: '48px' }}>
            {f}
          </button>
        ))}
      </div>

      <div className="space-y-4">
        {filtered.map(r => (
          <div key={r.id} className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
            <div className="flex flex-wrap items-center gap-3 mb-3">
              <span className="text-lg">{'⭐'.repeat(r.stars)}{'☆'.repeat(5 - r.stars)}</span>
              <span className="text-sm text-neutral-400 px-3 py-1 rounded-full bg-neutral-800 border border-neutral-700">{r.platform}</span>
              <span className="text-sm text-neutral-500">{r.date}</span>
            </div>
            <p className="text-base text-neutral-200 mb-4 leading-relaxed">{r.text}</p>

            {r.reply && (
              <div className="bg-neutral-800/60 rounded-xl p-4 border border-neutral-700/50 mb-3">
                <div className="text-sm text-neutral-400 mb-2">💬 Owner Reply</div>
                <p className="text-base text-neutral-300">{r.reply}</p>
              </div>
            )}

            {r.aiSuggestion && (
              <div className="bg-rose-500/10 rounded-xl p-4 border border-rose-500/30 mb-3">
                <div className="text-base text-rose-400 font-bold mb-2">🤖 AI Suggested Reply</div>
                <p className="text-base text-neutral-200 mb-3">{r.aiSuggestion}</p>
                <div className="flex flex-wrap gap-2">
                  <button className="px-5 py-3 rounded-xl font-bold text-white bg-rose-500 hover:bg-rose-400 transition-colors" style={{ minHeight: '48px' }}>
                    ✅ Use This Reply
                  </button>
                  <button className="px-5 py-3 rounded-xl font-bold text-neutral-300 bg-neutral-700 hover:bg-neutral-600 transition-colors" style={{ minHeight: '48px' }}>
                    ✏️ Write My Own
                  </button>
                </div>
              </div>
            )}

            {!r.reply && !r.aiSuggestion && (
              <button className="px-5 py-3 rounded-xl font-bold text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 transition-colors" style={{ minHeight: '48px' }}>
                ✏️ Reply
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── Tab: Messages ── */
function TabMessages() {
  const [composing, setComposing] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState(null)

  return (
    <div className="space-y-6">
      <button onClick={() => { setComposing(true); setSelectedTemplate(null) }}
        className="w-full px-6 py-4 rounded-2xl font-bold text-white bg-rose-500 hover:bg-rose-400 transition-colors text-center text-xl" style={{ minHeight: '56px' }}>
        ✉️ New Message
      </button>

      {composing && (
        <div className="bg-neutral-900 border border-rose-500/30 rounded-2xl p-5 space-y-4">
          <h3 className="text-lg font-bold text-white">✉️ Compose Message</h3>
          {!selectedTemplate && (
            <div className="grid grid-cols-2 gap-3">
              {MESSAGE_TEMPLATES.map((t, i) => (
                <button key={i} onClick={() => setSelectedTemplate(t)}
                  className="bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 rounded-xl p-4 text-left transition-colors">
                  <div className="text-lg mb-1">{t.icon} {t.label}</div>
                  <div className="text-sm text-neutral-400">{t.desc}</div>
                </button>
              ))}
            </div>
          )}
          {selectedTemplate && (
            <>
              <div className="text-base text-rose-400 font-semibold">{selectedTemplate.icon} {selectedTemplate.label}</div>
              <textarea rows={5} placeholder="Type your message…"
                className="w-full bg-neutral-800 border border-neutral-700 rounded-xl p-4 text-white placeholder-neutral-500 resize-none focus:outline-none focus:border-rose-500 text-base" />
              <div className="flex flex-wrap gap-3">
                <button className="px-6 py-3 rounded-xl font-bold text-white bg-rose-500 hover:bg-rose-400 transition-colors" style={{ minHeight: '48px' }}>
                  📤 Send
                </button>
                <button onClick={() => { setComposing(false); setSelectedTemplate(null) }}
                  className="px-6 py-3 rounded-xl font-bold text-neutral-300 bg-neutral-700 hover:bg-neutral-600 transition-colors" style={{ minHeight: '48px' }}>
                  Cancel
                </button>
              </div>
            </>
          )}
        </div>
      )}

      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
        <h2 className="text-xl font-bold text-white mb-4">📨 Sent Messages</h2>
        <div className="space-y-3">
          {MESSAGES_SENT.map((m, i) => (
            <div key={i} className="flex flex-wrap items-center gap-3 bg-neutral-800/60 rounded-xl p-4 border border-neutral-700/50">
              <span className="text-sm text-neutral-400">{m.date}</span>
              <span className="text-sm px-3 py-1 rounded-full bg-neutral-700 text-neutral-300 font-bold">{m.type}</span>
              <span className="text-base text-white flex-1 min-w-[140px] font-semibold">{m.title}</span>
              <span className="text-base text-neutral-400">👥 {m.recipients}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

/* ── Main page ── */
export default function KaiSushiDemo() {
  const [activeTab, setActiveTab] = useState('Today')

  const renderTab = () => {
    switch (activeTab) {
      case 'Today': return <TabToday />
      case 'Orders': return <TabOrders />
      case 'Reservations': return <TabReservations />
      case 'My Shop': return <TabMyShop />
      case 'Reviews': return <TabReviews />
      case 'Messages': return <TabMessages />
      default: return <TabToday />
    }
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-white">
      <div className="max-w-4xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <Link href="/gage-doumi" className="text-rose-400 font-bold text-lg flex items-center gap-2">
              🍣 가게도우미
            </Link>
            <h1 className="text-2xl font-bold text-white mt-1">KAI Sushi & Roll</h1>
            <div className="text-sm text-neutral-500">1448 E Lincoln Ave, Orange, CA</div>
          </div>
          <div className="text-right">
            <div className="flex items-center gap-1 text-amber-400 font-bold">⭐ {SHOP_INFO.rating} <span className="text-neutral-500 font-normal text-sm">({SHOP_INFO.reviewCount})</span></div>
            <div className="text-sm text-neutral-500">Mon–Sat 11 AM – 9:30 PM</div>
          </div>
        </div>

        {/* Tab Nav */}
        <div className="overflow-x-auto -mx-4 px-4 mb-6">
          <div className="flex gap-2 min-w-max">
            {TABS.map(tab => (
              <button key={tab.key} onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2 px-5 py-3 rounded-xl font-bold whitespace-nowrap transition-colors border ${activeTab === tab.key ? 'bg-rose-500 text-white border-rose-400' : 'bg-neutral-900 text-neutral-300 border-neutral-800 hover:bg-neutral-800'}`}
                style={{ minHeight: '48px' }}>
                <span className="text-xl">{tab.icon}</span>
                {tab.key}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        {renderTab()}

        {/* Footer */}
        <div className="mt-8 pt-6 border-t border-neutral-800 text-center space-y-2">
          <p className="text-sm text-neutral-500">🍣 가게도우미 — Restaurant management made simple</p>
          <p className="text-xs text-neutral-600">
            Demo built with real data from KAI Sushi & Roll (kaisushiorange.com, Yelp, Google).
            Simulated orders & reservations for illustration. Not affiliated with KAI Sushi.
          </p>
        </div>
      </div>
    </div>
  )
}
