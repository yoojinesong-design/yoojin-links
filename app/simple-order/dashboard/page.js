'use client'
import { useState, useEffect } from 'react'
import Link from 'next/link'

function formatWon(n) {
  return '₩' + n.toLocaleString('ko-KR')
}

function formatDate(iso) {
  const d = new Date(iso)
  const month = d.getMonth() + 1
  const day = d.getDate()
  const hour = d.getHours()
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${month}/${day} ${hour}:${min}`
}

const DEMO_ORDERS = [
  {
    id: 'ORD-A1B2C',
    customer: { name: '순이네 감자탕', contact: '010-1234-5678', note: '들기름 2병은 다음주 화요일에 배송 부탁드려요' },
    items: [
      { name: '유기농 들기름', price: 18000, qty: 5 },
      { name: '고춧가루 1kg', price: 35000, qty: 2 },
      { name: '된장 2kg', price: 15000, qty: 3 },
    ],
    total: 205000,
    date: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    status: 'pending',
  },
  {
    id: 'ORD-D3E4F',
    customer: { name: '맛나분식', contact: '010-9876-5432', note: '' },
    items: [
      { name: '참기름 (대)', price: 22000, qty: 3 },
      { name: '간장 1.8L', price: 12000, qty: 5 },
      { name: '쌀 10kg', price: 45000, qty: 2 },
    ],
    total: 216000,
    date: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(),
    status: 'confirmed',
  },
  {
    id: 'ORD-G5H6I',
    customer: { name: '행복한 밥상', contact: '010-5555-1234', note: '정문 앞에 놓아주세요' },
    items: [
      { name: '콩기름 1.8L', price: 8500, qty: 10 },
      { name: '천일염 3kg', price: 9000, qty: 5 },
    ],
    total: 130000,
    date: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
    status: 'delivered',
  },
  {
    id: 'ORD-J7K8L',
    customer: { name: '김사장 식당', contact: '010-3333-7777', note: '' },
    items: [
      { name: '들깨가루 500g', price: 16000, qty: 4 },
      { name: '식초 1.8L', price: 5500, qty: 6 },
      { name: '미숫가루 1kg', price: 12000, qty: 2 },
    ],
    total: 121000,
    date: new Date(Date.now() - 1000 * 60 * 60 * 48).toISOString(),
    status: 'delivered',
  },
]

const STATUS_MAP = {
  pending: { label: '대기', color: 'bg-amber-100 text-amber-700' },
  confirmed: { label: '확인', color: 'bg-blue-100 text-blue-700' },
  delivered: { label: '배송완료', color: 'bg-green-100 text-green-700' },
  cancelled: { label: '취소', color: 'bg-red-100 text-red-700' },
}

export default function Dashboard() {
  const [tab, setTab] = useState('orders')
  const [orders, setOrders] = useState([])
  const [stores, setStores] = useState({})
  const [selectedOrder, setSelectedOrder] = useState(null)

  useEffect(() => {
    // Load from localStorage, fallback to demo
    try {
      const savedOrders = JSON.parse(localStorage.getItem('simpleorder_orders') || '[]')
      const savedStores = JSON.parse(localStorage.getItem('simpleorder_stores') || '{}')
      setOrders(savedOrders.length > 0 ? savedOrders : DEMO_ORDERS)
      setStores(savedStores)
    } catch {
      setOrders(DEMO_ORDERS)
    }
  }, [])

  const updateOrderStatus = (orderId, newStatus) => {
    setOrders(prev => {
      const next = prev.map(o => o.id === orderId ? { ...o, status: newStatus } : o)
      try { localStorage.setItem('simpleorder_orders', JSON.stringify(next)) } catch {}
      return next
    })
  }

  const todayOrders = orders.filter(o => {
    const d = new Date(o.date)
    const now = new Date()
    return d.toDateString() === now.toDateString()
  })

  const todayRevenue = todayOrders.reduce((sum, o) => sum + o.total, 0)
  const pendingCount = orders.filter(o => o.status === 'pending').length
  const totalRevenue = orders.reduce((sum, o) => sum + o.total, 0)
  const storeList = Object.values(stores)

  return (
    <div className="min-h-screen bg-neutral-50 text-neutral-900">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white border-b border-neutral-200">
        <div className="max-w-4xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/simple-order" className="text-xl font-bold tracking-tight">
            simple<span className="text-blue-600">order</span>
            <span className="text-xs text-neutral-400 ml-2 font-normal">대시보드</span>
          </Link>
          <div className="flex items-center gap-3">
            <Link href="/simple-order/create"
              className="text-sm bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-full font-semibold transition">
              + 새 가게
            </Link>
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
          {[
            { label: '오늘 주문', value: `${todayOrders.length}건`, icon: '📦', accent: 'bg-blue-50 border-blue-100' },
            { label: '오늘 매출', value: formatWon(todayRevenue), icon: '💰', accent: 'bg-green-50 border-green-100' },
            { label: '대기 주문', value: `${pendingCount}건`, icon: '⏳', accent: 'bg-amber-50 border-amber-100' },
            { label: '총 매출', value: formatWon(totalRevenue), icon: '📊', accent: 'bg-purple-50 border-purple-100' },
          ].map(s => (
            <div key={s.label} className={`${s.accent} border rounded-2xl p-5`}>
              <div className="text-xl mb-2">{s.icon}</div>
              <div className="text-xs text-neutral-400 font-medium mb-1">{s.label}</div>
              <div className="text-lg font-extrabold text-neutral-900">{s.value}</div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-neutral-100 rounded-xl p-1 mb-6">
          {[
            { key: 'orders', label: '주문 관리', icon: '📋' },
            { key: 'stores', label: '내 가게', icon: '🏪' },
          ].map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex-1 py-3 rounded-lg text-sm font-bold transition ${
                tab === t.key ? 'bg-white text-neutral-900 shadow-sm' : 'text-neutral-500 hover:text-neutral-700'
              }`}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>

        {/* Orders Tab */}
        {tab === 'orders' && (
          <div className="space-y-3">
            {orders.length === 0 ? (
              <div className="text-center py-16 text-neutral-400">
                <div className="text-4xl mb-3">📭</div>
                <p className="font-medium">아직 주문이 없어요</p>
                <p className="text-sm mt-1">거래처에 주문 링크를 공유해보세요!</p>
              </div>
            ) : (
              orders.map(order => {
                const status = STATUS_MAP[order.status] || STATUS_MAP.pending
                return (
                  <div key={order.id}
                    className="bg-white border border-neutral-200 rounded-2xl p-5 hover:shadow-md transition-shadow cursor-pointer"
                    onClick={() => setSelectedOrder(selectedOrder?.id === order.id ? null : order)}>
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <div className="font-bold text-neutral-900">{order.customer.name}</div>
                        <div className="text-xs text-neutral-400 mt-0.5">{formatDate(order.date)} · {order.customer.contact}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-extrabold text-neutral-900">{formatWon(order.total)}</span>
                        <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${status.color}`}>{status.label}</span>
                      </div>
                    </div>

                    <div className="text-sm text-neutral-500">
                      {order.items.map(i => `${i.name} ×${i.qty}`).join(', ')}
                    </div>

                    {order.customer.note && (
                      <div className="mt-2 text-xs text-neutral-400 bg-neutral-50 rounded-lg px-3 py-2">
                        💬 {order.customer.note}
                      </div>
                    )}

                    {/* Expanded detail */}
                    {selectedOrder?.id === order.id && (
                      <div className="mt-4 pt-4 border-t border-neutral-100">
                        <div className="space-y-2 mb-4">
                          {order.items.map((item, i) => (
                            <div key={i} className="flex justify-between text-sm">
                              <span className="text-neutral-600">{item.name} × {item.qty}</span>
                              <span className="font-bold text-neutral-900">{formatWon(item.price * item.qty)}</span>
                            </div>
                          ))}
                        </div>

                        {order.status === 'pending' && (
                          <div className="flex gap-2">
                            <button
                              onClick={(e) => { e.stopPropagation(); updateOrderStatus(order.id, 'confirmed') }}
                              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2.5 rounded-xl font-bold text-sm transition">
                              ✓ 주문 확인
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); updateOrderStatus(order.id, 'cancelled') }}
                              className="px-4 py-2.5 border border-neutral-200 hover:border-red-300 text-neutral-400 hover:text-red-500 rounded-xl font-bold text-sm transition">
                              취소
                            </button>
                          </div>
                        )}
                        {order.status === 'confirmed' && (
                          <button
                            onClick={(e) => { e.stopPropagation(); updateOrderStatus(order.id, 'delivered') }}
                            className="w-full bg-green-600 hover:bg-green-700 text-white py-2.5 rounded-xl font-bold text-sm transition">
                            📦 배송 완료
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>
        )}

        {/* Stores Tab */}
        {tab === 'stores' && (
          <div>
            {storeList.length === 0 ? (
              <div className="text-center py-16">
                <div className="text-4xl mb-3">🏪</div>
                <p className="text-neutral-400 font-medium mb-1">등록된 가게가 없어요</p>
                <p className="text-sm text-neutral-300 mb-6">5분 만에 주문 페이지를 만들어보세요</p>
                <Link href="/simple-order/create"
                  className="inline-block bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-2xl font-bold transition">
                  + 가게 만들기
                </Link>
              </div>
            ) : (
              <div className="space-y-3">
                {storeList.map(s => (
                  <div key={s.slug} className="bg-white border border-neutral-200 rounded-2xl p-6">
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <h3 className="text-lg font-extrabold text-neutral-900">{s.name}</h3>
                        <p className="text-sm text-neutral-400 mt-0.5">{s.description || s.type}</p>
                      </div>
                      <span className="text-xs bg-green-100 text-green-700 font-bold px-3 py-1 rounded-full">활성</span>
                    </div>

                    <div className="flex items-center gap-3 text-sm mb-4">
                      <span className="text-neutral-400">📦 상품 {s.products?.length || 0}개</span>
                      <span className="text-neutral-400">·</span>
                      <span className="text-neutral-400">🏷️ {s.type}</span>
                    </div>

                    <div className="bg-neutral-50 rounded-xl px-4 py-3 mb-4">
                      <div className="text-xs text-neutral-400 mb-1">주문 링크</div>
                      <div className="text-blue-600 font-bold text-sm">{s.slug}.simpleorder.kr</div>
                    </div>

                    <div className="flex gap-2">
                      <Link href={`/simple-order/store/${s.slug}`}
                        className="flex-1 text-center border border-neutral-200 hover:border-neutral-300 text-neutral-700 py-2.5 rounded-xl font-bold text-sm transition">
                        페이지 보기
                      </Link>
                      <button
                        onClick={() => {
                          const url = `${window.location.origin}/simple-order/store/${s.slug}`
                          navigator.clipboard.writeText(url)
                        }}
                        className="flex-1 text-center bg-blue-600 hover:bg-blue-700 text-white py-2.5 rounded-xl font-bold text-sm transition">
                        📋 링크 복사
                      </button>
                    </div>
                  </div>
                ))}

                <Link href="/simple-order/create"
                  className="block text-center border-2 border-dashed border-neutral-200 hover:border-blue-300 text-neutral-400 hover:text-blue-600 py-6 rounded-2xl font-bold transition">
                  + 가게 추가
                </Link>
              </div>
            )}

            {/* Demo store link */}
            <div className="mt-8 text-center">
              <Link href="/simple-order/store/demo" className="text-sm text-neutral-400 hover:text-blue-600 transition">
                데모 가게 보기 →
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
