'use client'
import { useState } from 'react'
import Link from 'next/link'

const CATEGORIES = ['전체', '식용유', '양념', '곡류', '기타']

const PRODUCTS = [
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
]

function formatWon(n) {
  return '₩' + n.toLocaleString('ko-KR')
}

export default function SimpleOrderDemo() {
  const [cart, setCart] = useState({})
  const [category, setCategory] = useState('전체')
  const [orderPlaced, setOrderPlaced] = useState(false)
  const [showCart, setShowCart] = useState(false)

  const filtered = category === '전체' ? PRODUCTS : PRODUCTS.filter(p => p.category === category)

  const updateQty = (id, delta) => {
    setCart(prev => {
      const next = { ...prev }
      const val = (next[id] || 0) + delta
      if (val <= 0) delete next[id]
      else next[id] = val
      return next
    })
  }

  const totalItems = Object.values(cart).reduce((a, b) => a + b, 0)
  const totalPrice = Object.entries(cart).reduce((sum, [id, qty]) => {
    const product = PRODUCTS.find(p => p.id === Number(id))
    return sum + (product ? product.price * qty : 0)
  }, 0)

  const cartProducts = Object.entries(cart)
    .map(([id, qty]) => ({ ...PRODUCTS.find(p => p.id === Number(id)), qty }))
    .filter(p => p.name)

  if (orderPlaced) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center px-6">
        <div className="text-center max-w-md">
          <div className="text-6xl mb-6">✅</div>
          <h1 className="text-2xl font-extrabold text-neutral-900 mb-3">주문이 접수되었습니다!</h1>
          <p className="text-neutral-500 mb-2">주문 번호: <span className="font-bold text-neutral-700">#ORD-2024-0847</span></p>
          <p className="text-neutral-400 text-sm mb-8">확인 문자가 발송되었습니다. 영업일 1일 내 담당자가 연락드립니다.</p>
          <div className="bg-neutral-50 rounded-2xl p-6 border border-neutral-100 text-left mb-8">
            <div className="text-sm font-bold text-neutral-400 mb-3 tracking-wide">주문 요약</div>
            {cartProducts.map(p => (
              <div key={p.id} className="flex justify-between text-base py-1.5">
                <span className="text-neutral-700">{p.name} × {p.qty}</span>
                <span className="font-bold text-neutral-900">{formatWon(p.price * p.qty)}</span>
              </div>
            ))}
            <div className="border-t border-neutral-200 mt-3 pt-3 flex justify-between text-lg font-extrabold">
              <span>합계</span>
              <span className="text-blue-600">{formatWon(totalPrice)}</span>
            </div>
          </div>
          <button onClick={() => { setOrderPlaced(false); setCart({}); setShowCart(false) }}
            className="text-blue-600 font-semibold hover:underline">
            ← 다시 주문하기
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-white text-neutral-900">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-neutral-100">
        <div className="max-w-3xl mx-auto px-6 h-16 flex items-center justify-between">
          <div>
            <div className="text-lg font-extrabold text-neutral-900">한울 농산</div>
            <div className="text-xs text-neutral-400">B2B 주문 페이지</div>
          </div>
          <button
            onClick={() => setShowCart(!showCart)}
            className="relative bg-blue-600 text-white px-5 py-2.5 rounded-full font-semibold text-sm transition hover:bg-blue-700"
          >
            🛒 {totalItems > 0 && <span className="ml-1">{totalItems}개</span>}
            {totalItems > 0 && (
              <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center">
                {totalItems}
              </span>
            )}
          </button>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-6 py-8">
        {/* Welcome */}
        <div className="mb-8">
          <h1 className="text-2xl font-extrabold text-neutral-900 mb-2">안녕하세요, <span className="text-blue-600">순이네 감자탕</span>님</h1>
          <p className="text-neutral-400">필요한 상품의 수량을 선택하고 주문해주세요.</p>
        </div>

        {/* Category filter */}
        <div className="flex gap-2 mb-8 overflow-x-auto pb-2">
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              onClick={() => setCategory(cat)}
              className={`px-5 py-2.5 rounded-full text-sm font-semibold whitespace-nowrap transition ${
                category === cat
                  ? 'bg-blue-600 text-white'
                  : 'bg-neutral-100 text-neutral-500 hover:bg-neutral-200'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Products */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {filtered.map(product => {
            const qty = cart[product.id] || 0
            return (
              <div
                key={product.id}
                className={`border rounded-2xl p-5 transition-all ${
                  qty > 0 ? 'border-blue-200 bg-blue-50/50 shadow-sm' : 'border-neutral-100 bg-white hover:border-neutral-200'
                }`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="text-2xl mb-1">{product.emoji}</div>
                    <div className="font-bold text-neutral-900">{product.name}</div>
                    <div className="text-xs text-neutral-400 mt-0.5">{product.unit}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-extrabold text-neutral-900">{formatWon(product.price)}</div>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  {qty > 0 ? (
                    <>
                      <div className="flex items-center bg-white rounded-xl border border-neutral-200">
                        <button onClick={() => updateQty(product.id, -1)} className="px-4 py-2 text-neutral-400 font-bold text-lg hover:text-red-500 transition">−</button>
                        <span className="px-4 py-2 font-bold text-neutral-900 min-w-[40px] text-center">{qty}</span>
                        <button onClick={() => updateQty(product.id, 1)} className="px-4 py-2 text-blue-600 font-bold text-lg hover:text-blue-700 transition">+</button>
                      </div>
                      <div className="text-sm font-bold text-blue-600">{formatWon(product.price * qty)}</div>
                    </>
                  ) : (
                    <button
                      onClick={() => updateQty(product.id, 1)}
                      className="w-full py-2.5 rounded-xl border-2 border-dashed border-neutral-200 text-neutral-400 font-semibold text-sm hover:border-blue-300 hover:text-blue-600 transition"
                    >
                      + 담기
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {/* Cart Panel */}
        {showCart && totalItems > 0 && (
          <div className="fixed inset-0 bg-black/20 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center" onClick={() => setShowCart(false)}>
            <div className="bg-white w-full sm:max-w-md rounded-t-3xl sm:rounded-3xl p-8 max-h-[80vh] overflow-y-auto shadow-2xl" onClick={e => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-extrabold text-neutral-900">주문 확인</h2>
                <button onClick={() => setShowCart(false)} className="text-neutral-400 hover:text-neutral-600 text-2xl">×</button>
              </div>

              <div className="space-y-3 mb-6">
                {cartProducts.map(p => (
                  <div key={p.id} className="flex items-center justify-between bg-neutral-50 rounded-xl p-4">
                    <div>
                      <div className="font-bold text-neutral-900">{p.emoji} {p.name}</div>
                      <div className="text-sm text-neutral-400">{formatWon(p.price)} × {p.qty}</div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="font-bold text-neutral-900">{formatWon(p.price * p.qty)}</span>
                      <button onClick={() => updateQty(p.id, -p.qty)} className="text-neutral-300 hover:text-red-500 transition text-lg">✕</button>
                    </div>
                  </div>
                ))}
              </div>

              <div className="border-t border-neutral-100 pt-4 mb-6">
                <div className="flex justify-between text-lg font-extrabold">
                  <span>총 합계</span>
                  <span className="text-blue-600">{formatWon(totalPrice)}</span>
                </div>
                <div className="text-xs text-neutral-400 mt-1">{totalItems}개 상품</div>
              </div>

              <div className="space-y-3 mb-6">
                <input placeholder="업체명" defaultValue="순이네 감자탕" className="w-full bg-neutral-50 border border-neutral-200 rounded-xl px-4 py-3 text-base focus:outline-none focus:border-blue-600 transition" />
                <input placeholder="담당자 연락처" defaultValue="010-1234-5678" className="w-full bg-neutral-50 border border-neutral-200 rounded-xl px-4 py-3 text-base focus:outline-none focus:border-blue-600 transition" />
                <textarea placeholder="요청사항 (선택)" rows={2} className="w-full bg-neutral-50 border border-neutral-200 rounded-xl px-4 py-3 text-base focus:outline-none focus:border-blue-600 transition resize-none" />
              </div>

              <button
                onClick={() => setOrderPlaced(true)}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white py-4 rounded-2xl font-bold text-lg transition shadow-lg shadow-blue-600/20"
              >
                주문하기 — {formatWon(totalPrice)}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Floating cart bar */}
      {totalItems > 0 && !showCart && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-neutral-100 p-4 z-40 shadow-[0_-4px_20px_rgba(0,0,0,0.05)]">
          <div className="max-w-3xl mx-auto flex items-center justify-between">
            <div>
              <div className="text-sm text-neutral-400">{totalItems}개 상품</div>
              <div className="text-xl font-extrabold text-neutral-900">{formatWon(totalPrice)}</div>
            </div>
            <button
              onClick={() => setShowCart(true)}
              className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3.5 rounded-2xl font-bold text-base transition shadow-lg shadow-blue-600/20"
            >
              주문하기 →
            </button>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="max-w-3xl mx-auto px-6 py-8 text-center border-t border-neutral-100 mt-8">
        <p className="text-xs text-neutral-300 mb-2">이 페이지는 데모용 가상 데이터입니다.</p>
        <p className="text-xs text-neutral-300">
          Powered by <Link href="/simple-order" className="text-blue-400 hover:text-blue-600 transition font-medium">simpleorder</Link>
        </p>
      </div>
    </div>
  )
}
