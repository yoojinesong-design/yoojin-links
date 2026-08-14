'use client'
import { useState } from 'react'
import Link from 'next/link'

const EMOJI_OPTIONS = ['🫒','🍶','🌶️','🥣','🫙','🌾','🍚','🌿','🧴','🧂','🍾','🥤','🍖','🥩','🐟','🦐','🥬','🥕','🍅','🧈','🥚','🍞','☕','🍰','🧁','🍕','🍔','🥗','🍜','🍣']

const CATEGORY_PRESETS = {
  '식자재': ['식용유','양념','곡류','수산','축산','채소','기타'],
  '식당': ['메인메뉴','사이드','음료','세트메뉴','기타'],
  '카페': ['커피','음료','디저트','빵','기타'],
  '베이커리': ['빵','케이크','쿠키','음료','기타'],
  '기타': ['카테고리1','카테고리2','기타'],
}

export default function CreateStore() {
  const [step, setStep] = useState(1)
  const [store, setStore] = useState({ name: '', slug: '', description: '', type: '식자재', email: '' })
  const [products, setProducts] = useState([])
  const [newProduct, setNewProduct] = useState({ name: '', price: '', unit: '', emoji: '📦', category: '' })
  const [showEmojiPicker, setShowEmojiPicker] = useState(false)
  const [created, setCreated] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const generateSlug = (name) => {
    return name.toLowerCase().replace(/[^a-z0-9가-힣]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') || 'my-store'
  }

  const updateStore = (key, value) => {
    setStore(prev => {
      const next = { ...prev, [key]: value }
      if (key === 'name') next.slug = generateSlug(value)
      return next
    })
  }

  const addProduct = () => {
    if (!newProduct.name || !newProduct.price) return
    const categories = CATEGORY_PRESETS[store.type] || CATEGORY_PRESETS['기타']
    setProducts(prev => [
      ...prev,
      { id: Date.now(), ...newProduct, price: Number(newProduct.price), category: newProduct.category || categories[0] },
    ])
    setNewProduct({ name: '', price: '', unit: '', emoji: '📦', category: '' })
  }

  const removeProduct = (id) => setProducts(prev => prev.filter(p => p.id !== id))

  const handleCreate = async () => {
    setSaving(true)
    setError('')
    try {
      // 1. API로 가게 + 상품 저장
      const res = await fetch('/api/simple-order/stores', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: store.name,
          slug: store.slug,
          description: store.description,
          type: store.type,
          notification_email: store.email,
          products: products.map(p => ({
            name: p.name,
            price: p.price,
            unit: p.unit,
            category: p.category,
            emoji: p.emoji,
          })),
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || '저장에 실패했어요')

      // 2. localStorage에도 저장 (오프라인 폴백)
      try {
        const stores = JSON.parse(localStorage.getItem('simpleorder_stores') || '{}')
        stores[store.slug] = { ...store, products, createdAt: new Date().toISOString() }
        localStorage.setItem('simpleorder_stores', JSON.stringify(stores))
      } catch {}

      setCreated(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const categories = CATEGORY_PRESETS[store.type] || CATEGORY_PRESETS['기타']
  const storeUrl = typeof window !== 'undefined'
    ? `${window.location.origin}/simple-order/store/${store.slug}`
    : `/simple-order/store/${store.slug}`

  if (created) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center px-6">
        <div className="text-center max-w-md">
          <div className="text-6xl mb-6">🎉</div>
          <h1 className="text-3xl font-extrabold text-neutral-900 mb-3">주문 페이지 완성!</h1>
          <p className="text-neutral-500 mb-8">거래처에 아래 링크를 공유하세요.</p>
          <div className="bg-neutral-50 rounded-2xl border border-neutral-200 p-5 mb-6">
            <div className="text-xs text-neutral-400 mb-2 font-medium">내 주문 페이지 링크</div>
            <div className="text-blue-600 font-bold text-sm break-all">{storeUrl}</div>
          </div>
          <button
            onClick={() => { navigator.clipboard.writeText(storeUrl) }}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white py-4 rounded-2xl font-bold text-lg transition shadow-lg shadow-blue-600/20 mb-3"
          >📋 링크 복사</button>
          <div className="flex gap-3">
            <Link href={`/simple-order/store/${store.slug}`}
              className="flex-1 border-2 border-neutral-200 hover:border-neutral-300 text-neutral-700 py-3 rounded-2xl font-bold transition text-center">
              페이지 보기 →
            </Link>
            <Link href={`/simple-order/dashboard?store=${store.slug}`}
              className="flex-1 border-2 border-blue-100 hover:border-blue-200 text-blue-600 py-3 rounded-2xl font-bold transition text-center">
              대시보드 →
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-white text-neutral-900">
      <nav className="sticky top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-neutral-100">
        <div className="max-w-2xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/simple-order" className="text-xl font-bold tracking-tight">
            simple<span className="text-blue-600">order</span>
          </Link>
          <div className="flex items-center gap-1.5">
            {[1, 2, 3].map(s => (
              <div key={s} className={`h-2 rounded-full transition-all ${
                s === step ? 'w-8 bg-blue-600' : s < step ? 'w-8 bg-blue-200' : 'w-8 bg-neutral-200'
              }`} />
            ))}
          </div>
        </div>
      </nav>

      <div className="max-w-2xl mx-auto px-6 py-12">
        {/* Step 1: Store Info */}
        {step === 1 && (
          <div>
            <div className="mb-10">
              <div className="text-sm font-bold text-blue-600 tracking-widest mb-2">STEP 1</div>
              <h1 className="text-3xl font-extrabold tracking-tight mb-2">가게 정보</h1>
              <p className="text-neutral-400">기본 정보만 입력하면 바로 시작할 수 있어요.</p>
            </div>
            <div className="space-y-5">
              <div>
                <label className="block text-sm font-semibold text-neutral-700 mb-2">가게 이름 *</label>
                <input value={store.name} onChange={(e) => updateStore('name', e.target.value)}
                  placeholder="예: 한울 농산"
                  className="w-full bg-neutral-50 border border-neutral-200 rounded-2xl px-5 py-4 text-base focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/10 transition" />
              </div>
              <div>
                <label className="block text-sm font-semibold text-neutral-700 mb-2">주문 페이지 주소</label>
                <div className="flex items-center bg-neutral-50 border border-neutral-200 rounded-2xl px-5 py-4">
                  <span className="text-neutral-400 text-sm">simpleorder.kr/</span>
                  <input value={store.slug} onChange={(e) => updateStore('slug', e.target.value)}
                    className="bg-transparent text-blue-600 font-bold text-sm focus:outline-none flex-1" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-semibold text-neutral-700 mb-2">한줄 소개</label>
                <input value={store.description} onChange={(e) => updateStore('description', e.target.value)}
                  placeholder="예: 신선한 국내산 식자재를 직접 배송합니다"
                  className="w-full bg-neutral-50 border border-neutral-200 rounded-2xl px-5 py-4 text-base focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/10 transition" />
              </div>
              <div>
                <label className="block text-sm font-semibold text-neutral-700 mb-2">주문 알림 이메일</label>
                <input type="email" value={store.email} onChange={(e) => updateStore('email', e.target.value)}
                  placeholder="주문이 들어오면 이 이메일로 알려드려요"
                  className="w-full bg-neutral-50 border border-neutral-200 rounded-2xl px-5 py-4 text-base focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/10 transition" />
              </div>
              <div>
                <label className="block text-sm font-semibold text-neutral-700 mb-2">업종</label>
                <div className="flex flex-wrap gap-2">
                  {Object.keys(CATEGORY_PRESETS).map(type => (
                    <button key={type} onClick={() => updateStore('type', type)}
                      className={`px-5 py-2.5 rounded-full text-sm font-semibold transition ${
                        store.type === type ? 'bg-blue-600 text-white' : 'bg-neutral-100 text-neutral-500 hover:bg-neutral-200'
                      }`}>{type}</button>
                  ))}
                </div>
              </div>
            </div>
            <button onClick={() => store.name && setStep(2)} disabled={!store.name}
              className="w-full mt-10 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white py-4 rounded-2xl font-bold text-lg transition shadow-lg shadow-blue-600/20">
              다음: 상품 등록 →
            </button>
          </div>
        )}

        {/* Step 2: Products */}
        {step === 2 && (
          <div>
            <div className="mb-10">
              <div className="text-sm font-bold text-blue-600 tracking-widest mb-2">STEP 2</div>
              <h1 className="text-3xl font-extrabold tracking-tight mb-2">상품 등록</h1>
              <p className="text-neutral-400">거래처에서 주문할 수 있는 상품을 추가하세요.</p>
            </div>
            <div className="bg-neutral-50 rounded-2xl border border-neutral-200 p-6 mb-6">
              <div className="grid grid-cols-[auto_1fr] gap-4 mb-4">
                <div className="relative">
                  <button onClick={() => setShowEmojiPicker(!showEmojiPicker)}
                    className="w-14 h-14 bg-white border border-neutral-200 rounded-xl text-2xl flex items-center justify-center hover:border-blue-300 transition">
                    {newProduct.emoji}
                  </button>
                  {showEmojiPicker && (
                    <div className="absolute top-16 left-0 bg-white border border-neutral-200 rounded-2xl p-3 shadow-xl z-10 grid grid-cols-6 gap-1 w-64">
                      {EMOJI_OPTIONS.map(e => (
                        <button key={e} onClick={() => { setNewProduct(p => ({ ...p, emoji: e })); setShowEmojiPicker(false) }}
                          className="w-9 h-9 text-xl hover:bg-neutral-100 rounded-lg transition flex items-center justify-center">{e}</button>
                      ))}
                    </div>
                  )}
                </div>
                <input value={newProduct.name} onChange={(e) => setNewProduct(p => ({ ...p, name: e.target.value }))}
                  placeholder="상품 이름 *"
                  className="bg-white border border-neutral-200 rounded-xl px-4 py-3 text-base focus:outline-none focus:border-blue-600 transition" />
              </div>
              <div className="grid grid-cols-3 gap-3 mb-4">
                <input type="number" value={newProduct.price} onChange={(e) => setNewProduct(p => ({ ...p, price: e.target.value }))}
                  placeholder="가격 *" className="bg-white border border-neutral-200 rounded-xl px-4 py-3 text-base focus:outline-none focus:border-blue-600 transition" />
                <input value={newProduct.unit} onChange={(e) => setNewProduct(p => ({ ...p, unit: e.target.value }))}
                  placeholder="단위 (병, kg...)" className="bg-white border border-neutral-200 rounded-xl px-4 py-3 text-base focus:outline-none focus:border-blue-600 transition" />
                <select value={newProduct.category} onChange={(e) => setNewProduct(p => ({ ...p, category: e.target.value }))}
                  className="bg-white border border-neutral-200 rounded-xl px-4 py-3 text-base focus:outline-none focus:border-blue-600 transition text-neutral-700">
                  <option value="">카테고리</option>
                  {categories.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <button onClick={addProduct} disabled={!newProduct.name || !newProduct.price}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white py-3 rounded-xl font-bold transition">
                + 상품 추가
              </button>
            </div>
            {products.length > 0 ? (
              <div className="space-y-2 mb-8">
                <div className="text-sm font-semibold text-neutral-400 mb-3">등록된 상품 ({products.length})</div>
                {products.map(p => (
                  <div key={p.id} className="flex items-center justify-between bg-white border border-neutral-100 rounded-xl p-4">
                    <div className="flex items-center gap-3">
                      <span className="text-xl">{p.emoji}</span>
                      <div>
                        <div className="font-bold text-neutral-900 text-sm">{p.name}</div>
                        <div className="text-xs text-neutral-400">₩{p.price.toLocaleString()}{p.unit && ` / ${p.unit}`} · {p.category}</div>
                      </div>
                    </div>
                    <button onClick={() => removeProduct(p.id)} className="text-neutral-300 hover:text-red-500 transition text-lg">✕</button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-neutral-300">
                <div className="text-4xl mb-3">📦</div>
                <p>상품을 추가해주세요</p>
              </div>
            )}
            <div className="flex gap-3">
              <button onClick={() => setStep(1)} className="px-6 py-4 rounded-2xl font-bold text-neutral-500 hover:bg-neutral-100 transition">← 이전</button>
              <button onClick={() => products.length > 0 && setStep(3)} disabled={products.length === 0}
                className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white py-4 rounded-2xl font-bold text-lg transition shadow-lg shadow-blue-600/20">
                다음: 미리보기 →
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Preview */}
        {step === 3 && (
          <div>
            <div className="mb-10">
              <div className="text-sm font-bold text-blue-600 tracking-widest mb-2">STEP 3</div>
              <h1 className="text-3xl font-extrabold tracking-tight mb-2">미리보기</h1>
              <p className="text-neutral-400">거래처가 보게 될 주문 페이지예요.</p>
            </div>
            <div className="bg-neutral-50 rounded-3xl border border-neutral-200 p-6 sm:p-8 mb-8">
              <div className="flex items-center gap-2 mb-6">
                <div className="w-2.5 h-2.5 rounded-full bg-red-400" />
                <div className="w-2.5 h-2.5 rounded-full bg-yellow-400" />
                <div className="w-2.5 h-2.5 rounded-full bg-green-400" />
                <span className="text-xs text-neutral-400 ml-2 font-mono">{store.slug}.simpleorder.kr</span>
              </div>
              <div className="bg-white rounded-2xl border border-neutral-100 p-6">
                <h3 className="text-xl font-extrabold text-neutral-900 mb-1">{store.name}</h3>
                {store.description && <p className="text-sm text-neutral-400 mb-4">{store.description}</p>}
                <div className="grid grid-cols-2 gap-3">
                  {products.slice(0, 4).map(p => (
                    <div key={p.id} className="border border-neutral-100 rounded-xl p-4">
                      <div className="text-xl mb-1">{p.emoji}</div>
                      <div className="font-bold text-sm text-neutral-900">{p.name}</div>
                      <div className="text-sm font-extrabold text-neutral-900 mt-1">
                        ₩{p.price.toLocaleString()}
                        {p.unit && <span className="text-xs font-normal text-neutral-400">/{p.unit}</span>}
                      </div>
                    </div>
                  ))}
                </div>
                {products.length > 4 && <p className="text-xs text-neutral-400 mt-3 text-center">+{products.length - 4}개 더</p>}
              </div>
            </div>
            <div className="bg-white border border-neutral-100 rounded-2xl p-6 mb-8">
              <div className="text-sm font-bold text-neutral-400 mb-4 tracking-wide">요약</div>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between"><span className="text-neutral-500">가게 이름</span><span className="font-bold text-neutral-900">{store.name}</span></div>
                <div className="flex justify-between"><span className="text-neutral-500">업종</span><span className="font-bold text-neutral-900">{store.type}</span></div>
                <div className="flex justify-between"><span className="text-neutral-500">등록 상품</span><span className="font-bold text-neutral-900">{products.length}개</span></div>
                <div className="flex justify-between"><span className="text-neutral-500">알림 이메일</span><span className="font-bold text-neutral-900">{store.email || '미설정'}</span></div>
                <div className="flex justify-between"><span className="text-neutral-500">주문 페이지</span><span className="font-bold text-blue-600">{store.slug}.simpleorder.kr</span></div>
              </div>
            </div>
            {error && <p className="text-red-500 text-sm mb-4 text-center">{error}</p>}
            <div className="flex gap-3">
              <button onClick={() => setStep(2)} className="px-6 py-4 rounded-2xl font-bold text-neutral-500 hover:bg-neutral-100 transition">← 이전</button>
              <button onClick={handleCreate} disabled={saving}
                className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-4 rounded-2xl font-bold text-lg transition shadow-lg shadow-blue-600/20">
                {saving ? '저장 중...' : '🚀 주문 페이지 만들기'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
