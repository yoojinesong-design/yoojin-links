'use client'
import { useState, useEffect, useCallback, Suspense } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'

function formatWon(n) { return '₩' + n.toLocaleString('ko-KR') }
function formatDate(iso) {
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
}

const DEMO_ORDERS = [
  { id:'demo-1', order_number:'ORD-A1B2C', customer:{name:'순이네 감자탕',contact:'010-1234-5678',note:'들기름 2병은 다음주 화요일에 배송 부탁드려요'},
    items:[{name:'유기농 들기름',price:18000,qty:5},{name:'고춧가루 1kg',price:35000,qty:2},{name:'된장 2kg',price:15000,qty:3}],
    total:205000, date:new Date(Date.now()-1800000).toISOString(), status:'pending' },
  { id:'demo-2', order_number:'ORD-D3E4F', customer:{name:'맛나분식',contact:'010-9876-5432',note:''},
    items:[{name:'참기름 (대)',price:22000,qty:3},{name:'간장 1.8L',price:12000,qty:5},{name:'쌀 10kg',price:45000,qty:2}],
    total:216000, date:new Date(Date.now()-10800000).toISOString(), status:'confirmed' },
  { id:'demo-3', order_number:'ORD-G5H6I', customer:{name:'행복한 밥상',contact:'010-5555-1234',note:'정문 앞에 놓아주세요'},
    items:[{name:'콩기름 1.8L',price:8500,qty:10},{name:'천일염 3kg',price:9000,qty:5}],
    total:130000, date:new Date(Date.now()-86400000).toISOString(), status:'delivered' },
  { id:'demo-4', order_number:'ORD-J7K8L', customer:{name:'김사장 식당',contact:'010-3333-7777',note:''},
    items:[{name:'들깨가루 500g',price:16000,qty:4},{name:'식초 1.8L',price:5500,qty:6},{name:'미숫가루 1kg',price:12000,qty:2}],
    total:121000, date:new Date(Date.now()-172800000).toISOString(), status:'delivered' },
]

const STATUS_MAP = {
  pending: { label: '대기', color: 'bg-amber-100 text-amber-700' },
  confirmed: { label: '확인', color: 'bg-blue-100 text-blue-700' },
  delivered: { label: '배송완료', color: 'bg-green-100 text-green-700' },
  cancelled: { label: '취소', color: 'bg-red-100 text-red-700' },
}

export default function Dashboard() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-neutral-50 flex items-center justify-center"><div className="animate-pulse text-neutral-400">로딩 중...</div></div>}>
      <DashboardContent />
    </Suspense>
  )
}

function DashboardContent() {
  const searchParams = useSearchParams()
  const storeSlug = searchParams.get('store') || ''
  const squareStatus = searchParams.get('square') // 'connected', 'denied', 'error'

  const [tab, setTab] = useState('orders')
  const [orders, setOrders] = useState([])
  const [stores, setStores] = useState({})
  const [selectedOrder, setSelectedOrder] = useState(null)
  const [isDemo, setIsDemo] = useState(false)
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState(null)
  const [squareBanner, setSquareBanner] = useState(squareStatus)

  const loadOrders = useCallback(async () => {
    const slug = storeSlug || Object.keys(stores)[0]

    // API에서 주문 가져오기
    if (slug) {
      try {
        const res = await fetch(`/api/simple-order/orders?store_slug=${slug}`)
        if (res.ok) {
          const data = await res.json()
          if (!data.demo && data.orders.length > 0) {
            setOrders(data.orders)
            setIsDemo(false)
            setLoading(false)
            setLastRefresh(new Date())
            return
          }
        }
      } catch {}
    }

    // localStorage 폴백
    try {
      const savedOrders = JSON.parse(localStorage.getItem('simpleorder_orders') || '[]')
      if (savedOrders.length > 0) {
        setOrders(savedOrders.map(o => ({
          ...o,
          customer: o.customer || { name: o.customer_name, contact: o.customer_contact, note: o.customer_note },
          date: o.date || o.created_at,
        })))
        setIsDemo(false)
        setLoading(false)
        setLastRefresh(new Date())
        return
      }
    } catch {}

    // 데모 데이터
    setOrders(DEMO_ORDERS)
    setIsDemo(true)
    setLoading(false)
    setLastRefresh(new Date())
  }, [storeSlug, stores])

  useEffect(() => {
    // 가게 목록 로드
    try {
      const savedStores = JSON.parse(localStorage.getItem('simpleorder_stores') || '{}')
      setStores(savedStores)
    } catch {}
    loadOrders()
  }, [loadOrders])

  // 30초마다 자동 새로고침
  useEffect(() => {
    const interval = setInterval(loadOrders, 30000)
    return () => clearInterval(interval)
  }, [loadOrders])

  const updateOrderStatus = async (orderId, newStatus) => {
    // API로 상태 변경
    try {
      await fetch(`/api/simple-order/orders/${orderId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      })
    } catch {}

    // 로컬 상태 업데이트
    setOrders(prev => {
      const next = prev.map(o => (o.id === orderId ? { ...o, status: newStatus } : o))
      try { localStorage.setItem('simpleorder_orders', JSON.stringify(next)) } catch {}
      return next
    })
  }

  const todayOrders = orders.filter(o => new Date(o.date).toDateString() === new Date().toDateString())
  const todayRevenue = todayOrders.reduce((sum, o) => sum + o.total, 0)
  const pendingCount = orders.filter(o => o.status === 'pending').length
  const totalRevenue = orders.reduce((sum, o) => sum + o.total, 0)
  const storeList = Object.values(stores)

  if (loading) {
    return (
      <div className="min-h-screen bg-neutral-50 flex items-center justify-center">
        <div className="animate-pulse text-neutral-400">로딩 중...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-neutral-50 text-neutral-900">
      <header className="sticky top-0 z-50 bg-white border-b border-neutral-200">
        <div className="max-w-4xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/simple-order" className="text-xl font-bold tracking-tight">
            simple<span className="text-blue-600">order</span>
            <span className="text-xs text-neutral-400 ml-2 font-normal">대시보드</span>
          </Link>
          <div className="flex items-center gap-3">
            {isDemo && (
              <span className="text-xs bg-amber-100 text-amber-700 px-3 py-1 rounded-full font-bold">데모 모드</span>
            )}
            <button onClick={loadOrders} className="text-sm text-neutral-400 hover:text-neutral-600 transition" title="새로고침">
              🔄
            </button>
            <Link href="/simple-order/create"
              className="text-sm bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-full font-semibold transition">
              + 새 가게
            </Link>
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Square 연결 결과 배너 */}
        {squareBanner === 'connected' && (
          <div className="bg-green-50 border border-green-200 text-green-800 rounded-2xl px-5 py-4 mb-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xl">✅</span>
              <div>
                <div className="font-bold text-sm">Square POS 연결 완료!</div>
                <div className="text-xs text-green-600">이제 새 주문이 자동으로 Square POS에 들어와요.</div>
              </div>
            </div>
            <button onClick={() => setSquareBanner(null)} className="text-green-400 hover:text-green-600 text-lg">✕</button>
          </div>
        )}
        {squareBanner === 'denied' && (
          <div className="bg-amber-50 border border-amber-200 text-amber-800 rounded-2xl px-5 py-4 mb-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xl">⚠️</span>
              <div>
                <div className="font-bold text-sm">Square 연결을 취소했어요</div>
                <div className="text-xs text-amber-600">설정 탭에서 다시 연결할 수 있어요.</div>
              </div>
            </div>
            <button onClick={() => setSquareBanner(null)} className="text-amber-400 hover:text-amber-600 text-lg">✕</button>
          </div>
        )}
        {squareBanner === 'error' && (
          <div className="bg-red-50 border border-red-200 text-red-800 rounded-2xl px-5 py-4 mb-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xl">❌</span>
              <div>
                <div className="font-bold text-sm">Square 연결에 실패했어요</div>
                <div className="text-xs text-red-600">잠시 후 다시 시도해주세요.</div>
              </div>
            </div>
            <button onClick={() => setSquareBanner(null)} className="text-red-400 hover:text-red-600 text-lg">✕</button>
          </div>
        )}

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

        {/* Auto refresh indicator */}
        {lastRefresh && (
          <div className="text-xs text-neutral-300 text-right mb-4">
            마지막 갱신: {formatDate(lastRefresh.toISOString())} · 30초마다 자동 갱신
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 bg-neutral-100 rounded-xl p-1 mb-6">
          {[
            { key: 'orders', label: '주문 관리', icon: '📋' },
            { key: 'stores', label: '내 가게', icon: '🏪' },
            { key: 'settings', label: '설정', icon: '⚙️' },
          ].map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`flex-1 py-3 rounded-lg text-sm font-bold transition ${
                tab === t.key ? 'bg-white text-neutral-900 shadow-sm' : 'text-neutral-500 hover:text-neutral-700'
              }`}>
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
                const isNew = order.status === 'pending' && (Date.now() - new Date(order.date).getTime()) < 3600000
                return (
                  <div key={order.id}
                    className={`bg-white border rounded-2xl p-5 hover:shadow-md transition-shadow cursor-pointer ${
                      isNew ? 'border-amber-200 ring-1 ring-amber-100' : 'border-neutral-200'
                    }`}
                    onClick={() => setSelectedOrder(selectedOrder === order.id ? null : order.id)}>
                    {isNew && (
                      <div className="text-xs font-bold text-amber-600 mb-2 flex items-center gap-1">
                        <span className="w-1.5 h-1.5 bg-amber-500 rounded-full animate-pulse" />
                        새 주문
                      </div>
                    )}
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <div className="font-bold text-neutral-900">{order.customer?.name || order.customer_name}</div>
                        <div className="text-xs text-neutral-400 mt-0.5">{formatDate(order.date)} · {order.customer?.contact || order.customer_contact}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-extrabold text-neutral-900">{formatWon(order.total)}</span>
                        <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${status.color}`}>{status.label}</span>
                      </div>
                    </div>
                    <div className="text-sm text-neutral-500">
                      {order.items.map(i => `${i.name} ×${i.qty}`).join(', ')}
                    </div>
                    {(order.customer?.note || order.customer_note) && (
                      <div className="mt-2 text-xs text-neutral-400 bg-neutral-50 rounded-lg px-3 py-2">
                        💬 {order.customer?.note || order.customer_note}
                      </div>
                    )}

                    {selectedOrder === order.id && (
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
                            <button onClick={(e) => { e.stopPropagation(); updateOrderStatus(order.id, 'confirmed') }}
                              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2.5 rounded-xl font-bold text-sm transition">
                              ✓ 주문 확인
                            </button>
                            <button onClick={(e) => { e.stopPropagation(); updateOrderStatus(order.id, 'cancelled') }}
                              className="px-4 py-2.5 border border-neutral-200 hover:border-red-300 text-neutral-400 hover:text-red-500 rounded-xl font-bold text-sm transition">
                              취소
                            </button>
                          </div>
                        )}
                        {order.status === 'confirmed' && (
                          <button onClick={(e) => { e.stopPropagation(); updateOrderStatus(order.id, 'delivered') }}
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
                      <button onClick={() => { navigator.clipboard.writeText(`${window.location.origin}/simple-order/store/${s.slug}`) }}
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
            <div className="mt-8 text-center">
              <Link href="/simple-order/store/demo" className="text-sm text-neutral-400 hover:text-blue-600 transition">데모 가게 보기 →</Link>
            </div>
          </div>
        )}

        {/* Settings Tab */}
        {tab === 'settings' && (
          <div className="space-y-6">
            {/* Square POS 연동 */}
            <div className="bg-white border border-neutral-200 rounded-2xl p-6">
              <div className="flex items-start gap-4 mb-5">
                <div className="w-12 h-12 bg-neutral-900 rounded-xl flex items-center justify-center flex-shrink-0">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                    <rect x="3" y="3" width="18" height="18" rx="3" fill="white" />
                    <rect x="7" y="7" width="10" height="10" rx="1.5" fill="#121212" />
                  </svg>
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-extrabold text-neutral-900">Square POS 연동</h3>
                  <p className="text-sm text-neutral-400 mt-1">
                    Square를 연결하면 온라인 주문이 자동으로 POS에 들어와요.
                    별도로 주문을 옮기지 않아도 돼요.
                  </p>
                </div>
              </div>

              {squareBanner === 'connected' ? (
                <div className="bg-green-50 border border-green-200 rounded-xl px-5 py-4">
                  <div className="flex items-center gap-3">
                    <span className="w-2.5 h-2.5 bg-green-500 rounded-full" />
                    <div>
                      <div className="text-sm font-bold text-green-800">연결됨</div>
                      <div className="text-xs text-green-600 mt-0.5">새 주문이 자동으로 Square POS에 전송돼요</div>
                    </div>
                  </div>
                </div>
              ) : (
                <div>
                  <div className="bg-neutral-50 rounded-xl px-5 py-4 mb-4">
                    <div className="text-sm font-bold text-neutral-700 mb-2">이렇게 작동해요</div>
                    <ul className="text-xs text-neutral-500 space-y-2">
                      <li className="flex items-start gap-2">
                        <span className="text-blue-500 mt-0.5">①</span>
                        아래 버튼으로 Square 계정 인증
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-blue-500 mt-0.5">②</span>
                        거래처가 주문을 넣으면
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-blue-500 mt-0.5">③</span>
                        Square POS에 자동으로 주문이 생성돼요
                      </li>
                    </ul>
                  </div>

                  {storeSlug ? (
                    <a
                      href={`/api/simple-order/square/connect?store=${storeSlug}`}
                      className="inline-flex items-center gap-2 bg-neutral-900 hover:bg-neutral-800 text-white px-6 py-3 rounded-xl font-bold text-sm transition w-full justify-center"
                    >
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                        <rect x="3" y="3" width="18" height="18" rx="3" fill="white" />
                        <rect x="7" y="7" width="10" height="10" rx="1.5" fill="#121212" />
                      </svg>
                      Square 연결하기
                    </a>
                  ) : (
                    <div className="text-sm text-neutral-400 bg-neutral-50 rounded-xl px-4 py-3 text-center">
                      먼저 가게를 선택해주세요. URL에 <code className="bg-neutral-100 px-1.5 py-0.5 rounded text-xs">?store=slug</code>를 추가하세요.
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 알림 설정 */}
            <div className="bg-white border border-neutral-200 rounded-2xl p-6">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center flex-shrink-0">
                  <span className="text-2xl">📧</span>
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-extrabold text-neutral-900">이메일 알림</h3>
                  <p className="text-sm text-neutral-400 mt-1">
                    새 주문이 들어오면 이메일로 알림을 보내요.
                    가게 생성 시 입력한 이메일로 발송됩니다.
                  </p>
                  <div className="mt-3 bg-neutral-50 rounded-xl px-4 py-3">
                    <div className="flex items-center gap-2 text-sm text-neutral-500">
                      <span className="w-2 h-2 bg-green-400 rounded-full" />
                      Resend API 연동으로 자동 발송
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* 요금제 */}
            <div className="bg-white border border-neutral-200 rounded-2xl p-6">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 bg-purple-50 rounded-xl flex items-center justify-center flex-shrink-0">
                  <span className="text-2xl">💎</span>
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-extrabold text-neutral-900">요금제</h3>
                  <p className="text-sm text-neutral-400 mt-1">
                    현재 무료 체험 중이에요.
                  </p>
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <div className="bg-neutral-50 rounded-xl px-4 py-3 text-center">
                      <div className="text-xs text-neutral-400 mb-1">무료</div>
                      <div className="text-lg font-extrabold text-neutral-900">₩0</div>
                      <div className="text-xs text-neutral-400">주문 50건/월</div>
                    </div>
                    <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 text-center">
                      <div className="text-xs text-blue-600 font-bold mb-1">프로</div>
                      <div className="text-lg font-extrabold text-blue-700">$19</div>
                      <div className="text-xs text-blue-500">무제한 + POS 연동</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
