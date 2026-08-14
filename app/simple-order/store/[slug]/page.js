'use client'
import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'

const DEMO_STORE = {
  name: '한울 농산',
  slug: 'demo',
  description: '국내산 프리미엄 식자재를 산지에서 직접 배송합니다',
  type: '식자재',
  products: [
    { id: 1, name: '유기농 들기름', price: 18000, unit: '병 (300ml)', category: '식용유', emoji: '🫒' },
    { id: 2, name: '참기름 (대)', price: 22000, unit: '병 (500ml)', category: '식용유', emoji: '🍶' },
    { id: 3, name: '고춧가루 1kg', price: 35000, unit: '봉', category: '양념', emoji: '🌶️' },
    { id: 4, name: '된장 2kg', price: 15000, unit: '통', category: '양념', emoji: '🥣' },
    { id: 5, name: '간장 1.8L', price: 12000, unit: '병', category: '양념', emoji: '🫙' },
    { id: 6, name: '쌀 10kg', price: 45000, unit: '포', category: '곡류', emoji: '🌾' },
    { id: 7, name: '찹쌀 5kg', price: 28000, unit: '포', category: '곡류', emoji: '🍚' },
    { id: 8, name: '들깨가루 500g', price: 16000, unit: '봉', category: '양념', emoji: '🌿' },
    { id: 9, name: '콩기름 1.8L', price: 8500, unit: '병', category: '식용유', emoji: '🧴' },
    { id: 10, name: '천일염 3kg', price: 9000, unit: '봉', category: '기타', emoji: '🧂' },
    { id: 11, name: '식초 1.8L', price: 5500, unit: '병', category: '기타', emoji: '🍾' },
    { id: 12, name: '미숫가루 1kg', price: 12000, unit: '봉', category: '곡류', emoji: '🥤' },
  ],
}

function formatWon(n) { return '₩' + n.toLocaleString('ko-KR') }

export default function StorePage() {
  const params = useParams()
  const slug = params.slug
  const [store, setStore] = useState(null)
  const [loading, setLoading] = useState(true)
  const [cart, setCart] = useState({})
  const [category, setCategory] = useState('전체')
  const [showCart, setShowCart] = useState(false)
  const [orderPlaced, setOrderPlaced] = useState(false)
  const [ordering, setOrdering] = useState(false)
  const [orderNumber, setOrderNumber] = useState('')
  const [orderForm, setOrderForm] = useState({ name: '', contact: '', note: '' })

  useEffect(() => {
    async function loadStore() {
      // 데모 슬러그
      if (slug === 'demo') {
        setStore(DEMO_STORE)
        setLoading(false)
        return
      }

      // API에서 가져오기
      try {
        const res = await fetch(`/api/simple-order/stores/${slug}`)
        if (res.ok) {
          const data = await res.json()
          setStore({ ...data.store, products: data.products })
          setLoading(false)
          return
        }
      } catch {}

      // localStorage 폴백
      try {
        const stores = JSON.parse(localStorage.getItem('simpleorder_stores') || '{}')
        if (stores[slug]) {
          setStore(stores[slug])
          setLoading(false)
          return
        }
      } catch {}

      setLoading(false)
    }
    loadStore()
  }, [slug])

  if (loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="animate-pulse text-neutral-400">로딩 중...</div>
      </div>
    )
  }

  if (!store) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center px-6">
        <div className="text-center max-w-sm">
          <div className="text-5xl mb-4">🔍</div>
          <h1 className="text-2xl font-extrabold text-neutral-900 mb-2">페이지를 찾을 수 없어요</h1>
          <p className="text-neutral-400 mb-6">이 주소의 가게가 아직 등록되지 않았어요.</p>
          <Link href="/simple-order" className="text-blue-600 font-bold hover:underline">SimpleOrder 알아보기 →</Link>
        </div>
      </div>
    )
  }

  const categories = ['전체', ...new Set(store.products.map(p => p.category))]
  const filtered = category === '전체' ? store.products : store.products.filter(p => p.category === category)

  const updateQty = (id, delta) => {
    setCart(prev => {
      const next = { ...prev }
      const val = (next[id] || 0) + delta
      if (val <= 0) { delete next[id] } else { next[id] = val }
      return next
    })
  }

  const totalItems = Object.values(cart).reduce((a, b) => a + b, 0)
  const totalPrice = Object.entries(cart).reduce((sum, [id, qty]) => {
    const product = store.products.find(p => String(p.id) === String(id))
    return sum + (product ? product.price * qty : 0)
  }, 0)

  const cartProducts = Object.entries(cart)
    .map(([id, qty]) => ({ ...store.products.find(p => String(p.id) === String(id)), qty }))
    .filter(p => p.name)

  const handleOrder = async () => {
    if (!orderForm.name || !orderForm.contact) return
    setOrdering(true)
    try {
      const res = await fetch('/api/simple-order/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          store_slug: slug,
          customer_name: orderForm.name,
          customer_contact: orderForm.contact,
          customer_note: orderForm.note,
          items: cartProducts.map(p => ({ id: p.id, name: p.name, price: p.price, qty: p.qty })),
          total: totalPrice,
        }),
      })
      const data = await res.json()
      setOrderNumber(data.order?.order_number || 'ORD-' + Date.now().toString(36).toUpperCase())
    } catch {
      setOrderNumber('ORD-' + Date.now().toString(36).toUpperCase())
    }

    // localStorage에도 저장 (대시보드 폴백)
    try {
      const orders = JSON.parse(localStorage.getItem('simpleorder_orders') || '[]')
      orders.unshift({
        id: Date.now().toString(),
        storeSlug: slug,
        customer: orderForm,
        items: cartProducts.map(p => ({ name: p.name, price: p.price, qty: p.qty })),
        total: totalPrice,
        date: new Date().toISOString(),
        status: 'pending',
      })
      localStorage.setItem('simpleorder_orders', JSON.stringify(orders))
    } catch {}

    setOrdering(false)
    setOrderPlaced(true)
  }

  if (orderPlaced) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center px-6">
        <div className="text-center max-w-md w-full">
          <div className="w-20 h-20 bg-green-50 rounded-full flex items-center justify-center mx-auto mb-6">
            <span className="text-4xl">✅</span>
          </div>
          <h1 className="text-2xl font-extrabold text-neutral-900 mb-2">주문이 접수되었습니다!</h1>
          <p className="text-neutral-500 text-sm mb-2">주문번호: <span className="font-bold text-neutral-700">{orderNumber}</span></p>
          <p className="text-neutral-400 text-sm mb-8">확인 후 담당자가 연락드릴 예정이에요.</p>
          <div className="bg-neutral-50 rounded-2xl border border-neutral-100 p-6 text-left mb-8">
            <div className="text-xs font-bold text-neutral-400 mb-4 tracking-wide">주문 요약</div>
            {cartProducts.map(p => (
              <div key={p.id} className="flex justify-between text-sm py-2 border-b border-neutral-100 last:border-0">
                <span className="text-neutral-600">{p.emoji} {p.name} × {p.qty}</span>
                <span className="font-bold text-neutral-900">{formatWon(p.price * p.qty)}</span>
              </div>
            ))}
            <div className="flex justify-between text-lg font-extrabold mt-4 pt-3 border-t border-neutral-200">
              <span>합계</span>
              <span className="text-blue-600">{formatWon(totalPrice)}</span>
            </div>
          </div>
          <button onClick={() => { setOrderPlaced(false); setCart({}); setShowCart(false); setOrderForm({ name: '', contact: '', note: '' }) }}
            className="text-blue-600 font-semibold hover:underline">← 다시 주문하기</button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-neutral-50 text-neutral-900">
      <header className="sticky top-0 z-50 bg-white/90 backdrop-blur-xl border-b border-neutral-100">
        <div className="max-w-2xl mx-auto px-6 h-16 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-extrabold text-neutral-900 leading-tight">{store.name}</h1>
            {store.description && <p className="text-xs text-neutral-400 leading-tight">{store.description}</p>}
          </div>
          <button onClick={() => totalItems > 0 && setShowCart(true)}
            className={`relative px-5 py-2.5 rounded-full font-semibold text-sm transition ${
              totalItems > 0 ? 'bg-blue-600 text-white hover:bg-blue-700' : 'bg-neutral-100 text-neutral-400'
            }`}>
            🛒 {totalItems > 0 ? `${totalItems}개` : '비어있음'}
          </button>
        </div>
      </header>

      <div className="max-w-2xl mx-auto px-6 py-6">
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2 -mx-6 px-6">
          {categories.map(cat => (
            <button key={cat} onClick={() => setCategory(cat)}
              className={`px-5 py-2.5 rounded-full text-sm font-semibold whitespace-nowrap transition ${
                category === cat ? 'bg-neutral-900 text-white' : 'bg-white text-neutral-500 hover:bg-neutral-100 border border-neutral-200'
              }`}>{cat}</button>
          ))}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {filtered.map(product => {
            const qty = cart[product.id] || 0
            return (
              <div key={product.id}
                className={`bg-white border rounded-2xl p-5 transition-all ${
                  qty > 0 ? 'border-blue-200 ring-1 ring-blue-100 shadow-sm' : 'border-neutral-200 hover:border-neutral-300'
                }`}>
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-neutral-50 rounded-xl flex items-center justify-center text-2xl">{product.emoji}</div>
                    <div>
                      <div className="font-bold text-neutral-900 leading-tight">{product.name}</div>
                      <div className="text-xs text-neutral-400 mt-0.5">{product.unit}</div>
                    </div>
                  </div>
                  <div className="text-lg font-extrabold text-neutral-900">{formatWon(product.price)}</div>
                </div>
                {qty > 0 ? (
                  <div className="flex items-center justify-between">
                    <div className="flex items-center bg-neutral-50 rounded-xl border border-neutral-200">
                      <button onClick={() => updateQty(product.id, -1)} className="w-10 h-10 flex items-center justify-center text-neutral-400 font-bold text-lg hover:text-red-500 transition">−</button>
                      <span className="w-10 h-10 flex items-center justify-center font-bold text-neutral-900">{qty}</span>
                      <button onClick={() => updateQty(product.id, 1)} className="w-10 h-10 flex items-center justify-center text-blue-600 font-bold text-lg hover:text-blue-700 transition">+</button>
                    </div>
                    <div className="text-sm font-bold text-blue-600">{formatWon(product.price * qty)}</div>
                  </div>
                ) : (
                  <button onClick={() => updateQty(product.id, 1)}
                    className="w-full py-2.5 rounded-xl border-2 border-dashed border-neutral-200 text-neutral-400 font-semibold text-sm hover:border-blue-300 hover:text-blue-600 transition">
                    + 담기
                  </button>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Cart Modal */}
      {showCart && totalItems > 0 && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center" onClick={() => setShowCart(false)}>
          <div className="bg-white w-full sm:max-w-md rounded-t-3xl sm:rounded-3xl max-h-[85vh] overflow-y-auto shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="sticky top-0 bg-white border-b border-neutral-100 px-6 py-5 flex items-center justify-between rounded-t-3xl">
              <h2 className="text-xl font-extrabold text-neutral-900">주문서</h2>
              <button onClick={() => setShowCart(false)} className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-neutral-100 text-neutral-400 text-xl transition">×</button>
            </div>
            <div className="p-6">
              <div className="space-y-2 mb-6">
                {cartProducts.map(p => (
                  <div key={p.id} className="flex items-center justify-between bg-neutral-50 rounded-xl p-4">
                    <div className="flex items-center gap-3">
                      <span className="text-lg">{p.emoji}</span>
                      <div>
                        <div className="font-bold text-sm text-neutral-900">{p.name}</div>
                        <div className="text-xs text-neutral-400">{formatWon(p.price)} × {p.qty}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="font-bold text-sm text-neutral-900">{formatWon(p.price * p.qty)}</span>
                      <button onClick={() => updateQty(p.id, -p.qty)} className="text-neutral-300 hover:text-red-500 transition">✕</button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="border-t border-neutral-100 pt-4 mb-6">
                <div className="flex justify-between items-center">
                  <div>
                    <div className="text-lg font-extrabold text-neutral-900">합계</div>
                    <div className="text-xs text-neutral-400">{totalItems}개 상품</div>
                  </div>
                  <div className="text-2xl font-extrabold text-blue-600">{formatWon(totalPrice)}</div>
                </div>
              </div>
              <div className="space-y-3 mb-6">
                <input value={orderForm.name} onChange={(e) => setOrderForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="업체명 *"
                  className="w-full bg-neutral-50 border border-neutral-200 rounded-xl px-4 py-3.5 text-base focus:outline-none focus:border-blue-600 transition" />
                <input value={orderForm.contact} onChange={(e) => setOrderForm(f => ({ ...f, contact: e.target.value }))}
                  placeholder="연락처 (전화번호) *"
                  className="w-full bg-neutral-50 border border-neutral-200 rounded-xl px-4 py-3.5 text-base focus:outline-none focus:border-blue-600 transition" />
                <textarea value={orderForm.note} onChange={(e) => setOrderForm(f => ({ ...f, note: e.target.value }))}
                  placeholder="요청사항 (선택)" rows={2}
                  className="w-full bg-neutral-50 border border-neutral-200 rounded-xl px-4 py-3.5 text-base focus:outline-none focus:border-blue-600 transition resize-none" />
              </div>
              <button onClick={handleOrder} disabled={!orderForm.name || !orderForm.contact || ordering}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white py-4 rounded-2xl font-bold text-lg transition shadow-lg shadow-blue-600/20">
                {ordering ? '주문 중...' : `주문 확인 — ${formatWon(totalPrice)}`}
              </button>
            </div>
          </div>
        </div>
      )}

      {totalItems > 0 && !showCart && (
        <div className="fixed bottom-0 left-0 right-0 bg-white/90 backdrop-blur-xl border-t border-neutral-200 p-4 z-40">
          <div className="max-w-2xl mx-auto flex items-center justify-between">
            <div>
              <div className="text-xs text-neutral-400 font-medium">{totalItems}개 상품</div>
              <div className="text-xl font-extrabold text-neutral-900">{formatWon(totalPrice)}</div>
            </div>
            <button onClick={() => setShowCart(true)}
              className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3.5 rounded-2xl font-bold transition shadow-lg shadow-blue-600/20">주문하기 →</button>
          </div>
        </div>
      )}

      <div className="max-w-2xl mx-auto px-6 py-8 text-center mt-8">
        <p className="text-xs text-neutral-300">
          Powered by <Link href="/simple-order" className="text-blue-400 hover:text-blue-600 transition font-medium">SimpleOrder</Link>
        </p>
      </div>
    </div>
  )
}
