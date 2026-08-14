'use client'
import { useState } from 'react'
import Link from 'next/link'

export default function SimpleOrderLanding() {
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
        body: JSON.stringify({ email, product: 'simple-order' }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || '오류가 발생했어요')
      setSubmitted(true)
    } catch (err) {
      setError(err.message || '다시 시도해 주세요')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-white text-neutral-900">
      {/* Nav */}
      <nav className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-xl border-b border-neutral-100">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <span className="text-xl font-bold tracking-tight">simple<span className="text-blue-600">order</span></span>
          <div className="flex items-center gap-4">
            <Link href="/simple-order/store/demo" className="text-sm text-neutral-500 hover:text-neutral-900 transition font-medium">데모</Link>
            <Link href="/simple-order/dashboard" className="text-sm text-neutral-500 hover:text-neutral-900 transition font-medium">대시보드</Link>
            <Link href="/simple-order/create" className="text-sm bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-full font-semibold transition">시작하기</Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-32 pb-24 px-6">
        <div className="max-w-3xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 text-sm font-medium text-blue-600 bg-blue-50 rounded-full px-4 py-2 mb-8">
            <span className="w-2 h-2 bg-blue-600 rounded-full animate-pulse" />
            B2B 주문을 가장 심플하게
          </div>
          <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight leading-[1.1] mb-6 text-neutral-900">
            링크 하나로<br />
            <span className="text-blue-600">주문 받으세요.</span>
          </h1>
          <p className="text-lg sm:text-xl text-neutral-500 max-w-lg mx-auto mb-10 leading-relaxed">
            카탈로그 없이, 엑셀 없이, 전화 없이.<br />
            거래처가 직접 골라서 주문합니다.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link href="/simple-order/create" className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-4 rounded-2xl font-bold text-lg transition shadow-lg shadow-blue-600/20">
              무료로 시작 →
            </Link>
            <Link href="/simple-order/store/demo" className="border-2 border-neutral-200 hover:border-neutral-300 text-neutral-700 px-8 py-4 rounded-2xl font-bold text-lg transition">
              데모 보기
            </Link>
          </div>
        </div>
      </section>

      {/* Visual mockup */}
      <section className="px-6 pb-24">
        <div className="max-w-4xl mx-auto">
          <div className="bg-neutral-50 rounded-3xl border border-neutral-200 p-8 sm:p-12">
            <div className="flex items-center gap-2 mb-8">
              <div className="w-3 h-3 rounded-full bg-red-400" />
              <div className="w-3 h-3 rounded-full bg-yellow-400" />
              <div className="w-3 h-3 rounded-full bg-green-400" />
              <span className="text-xs text-neutral-400 ml-3 font-mono">yourshop.simpleorder.kr</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              {[
                { name: '유기농 들기름', price: '₩18,000', unit: '병', color: 'bg-amber-50 border-amber-100' },
                { name: '참기름 (대)', price: '₩22,000', unit: '병', color: 'bg-orange-50 border-orange-100' },
                { name: '고춧가루 1kg', price: '₩35,000', unit: '봉', color: 'bg-red-50 border-red-100' },
                { name: '된장 2kg', price: '₩15,000', unit: '통', color: 'bg-yellow-50 border-yellow-100' },
                { name: '간장 1.8L', price: '₩12,000', unit: '병', color: 'bg-stone-50 border-stone-100' },
                { name: '쌀 10kg', price: '₩45,000', unit: '포', color: 'bg-green-50 border-green-100' },
              ].map((item) => (
                <div key={item.name} className={`${item.color} border rounded-2xl p-5 transition hover:scale-[1.02]`}>
                  <div className="text-base font-bold text-neutral-800 mb-1">{item.name}</div>
                  <div className="text-lg font-extrabold text-neutral-900">{item.price}<span className="text-sm font-normal text-neutral-400">/{item.unit}</span></div>
                  <div className="mt-3 flex items-center gap-2">
                    <div className="flex items-center bg-white rounded-lg border border-neutral-200">
                      <button className="px-3 py-1.5 text-neutral-400 font-bold text-lg">−</button>
                      <span className="px-3 py-1.5 text-sm font-bold text-neutral-700 min-w-[32px] text-center">0</span>
                      <button className="px-3 py-1.5 text-blue-600 font-bold text-lg">+</button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-6 flex justify-end">
              <div className="bg-blue-600 text-white px-6 py-3 rounded-xl font-bold text-base">주문하기 →</div>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-24 px-6 bg-neutral-50">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-neutral-900">이렇게 쉬워요</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
            {[
              { step: '01', title: '상품 등록', desc: '이름, 가격, 단위만 입력하세요.\n사진도 선택사항이에요.', icon: '📦' },
              { step: '02', title: '링크 공유', desc: '생성된 주문 페이지 링크를\n거래처에 보내세요.', icon: '🔗' },
              { step: '03', title: '주문 확인', desc: '거래처가 수량 선택 후 주문.\n알림으로 바로 확인.', icon: '✅' },
            ].map((s) => (
              <div key={s.step} className="text-center">
                <div className="text-4xl mb-4">{s.icon}</div>
                <div className="text-xs font-bold text-blue-600 tracking-widest mb-2">{s.step}</div>
                <h3 className="text-xl font-bold mb-3 text-neutral-900">{s.title}</h3>
                <p className="text-base text-neutral-500 leading-relaxed whitespace-pre-line">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pain → Solution */}
      <section className="py-24 px-6">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-neutral-900">이런 경험, 있으시죠?</h2>
          </div>
          <div className="space-y-4">
            {[
              { pain: '카톡으로 주문받다가 누락', fix: '주문 페이지에서 자동 접수' },
              { pain: '엑셀로 주문서 관리하다 실수', fix: '대시보드에서 한눈에 관리' },
              { pain: '거래처마다 가격 따로 알려줘야 함', fix: '거래처별 맞춤 가격표' },
              { pain: '주문 전화 받느라 일 못 함', fix: '24시간 자동 주문 접수' },
            ].map((p, i) => (
              <div key={i} className="grid grid-cols-1 sm:grid-cols-[1fr_48px_1fr] gap-3 items-center bg-neutral-50 rounded-2xl p-6 border border-neutral-100">
                <div className="text-base text-neutral-500 line-through decoration-neutral-300">{p.pain}</div>
                <div className="hidden sm:flex justify-center"><span className="text-blue-600 text-xl font-bold">→</span></div>
                <div className="text-base font-semibold text-blue-600">{p.fix}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-24 px-6 bg-neutral-50">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-neutral-900">필요한 것만, 깔끔하게</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { icon: '🔗', title: '원클릭 주문 링크', desc: '거래처에 링크만 보내면 끝. 회원가입 필요 없어요.' },
              { icon: '📱', title: '모바일 최적화', desc: '핸드폰에서도 바로 주문. 거래처 사장님도 편해요.' },
              { icon: '🔔', title: '실시간 알림', desc: '주문 들어오면 카톡/문자로 바로 알려드려요.' },
              { icon: '📊', title: '주문 대시보드', desc: '오늘/주간/월간 주문 현황을 한눈에.' },
              { icon: '💰', title: '거래처별 가격', desc: 'A거래처, B거래처 다른 가격? 자동 적용.' },
              { icon: '📋', title: '주문서 자동생성', desc: '주문 확인 후 PDF 주문서 자동 발행.' },
            ].map((f) => (
              <div key={f.title} className="bg-white border border-neutral-100 rounded-2xl p-6 hover:shadow-md transition-shadow">
                <div className="text-2xl mb-3">{f.icon}</div>
                <h3 className="font-bold text-lg mb-2 text-neutral-900">{f.title}</h3>
                <p className="text-base text-neutral-500 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-24 px-6">
        <div className="max-w-lg mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-12 text-neutral-900">심플한 가격</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-white border border-neutral-200 rounded-3xl p-8 text-left">
              <div className="text-sm font-semibold text-neutral-400 mb-3 tracking-wide">FREE</div>
              <div className="text-4xl font-extrabold mb-1 text-neutral-900">$0</div>
              <p className="text-sm text-neutral-400 mb-6">거래처 3곳까지</p>
              <ul className="space-y-3">
                {['상품 20개', '주문 알림', '기본 대시보드'].map(f => (
                  <li key={f} className="flex gap-3 text-base text-neutral-600">
                    <span className="text-blue-600 flex-shrink-0">✓</span>{f}
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-blue-600 text-white rounded-3xl p-8 text-left relative">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-blue-900 text-white text-xs font-bold px-4 py-1 rounded-full tracking-wide">POPULAR</div>
              <div className="text-sm font-semibold text-blue-200 mb-3 tracking-wide">PRO</div>
              <div className="text-4xl font-extrabold mb-1">$19<span className="text-lg font-normal text-blue-200">/mo</span></div>
              <p className="text-sm text-blue-200 mb-6">거래처 무제한</p>
              <ul className="space-y-3">
                {['상품 무제한', '거래처별 가격', 'PDF 주문서', '매출 리포트', '카톡 알림', '우선 지원'].map(f => (
                  <li key={f} className="flex gap-3 text-base text-blue-50">
                    <span className="text-blue-200 flex-shrink-0">✓</span>{f}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* CTA / Waitlist */}
      <section id="waitlist" className="py-24 px-6 bg-neutral-50">
        <div className="max-w-xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight mb-4 text-neutral-900">
            주문, 이제<br /><span className="text-blue-600">심플하게.</span>
          </h2>
          <p className="text-neutral-500 mb-10 text-lg">
            이메일 남겨주시면 가장 먼저 초대해드릴게요.
          </p>
          {submitted ? (
            <div className="bg-blue-50 border border-blue-100 rounded-2xl p-8">
              <div className="text-blue-600 text-3xl mb-2">✓</div>
              <p className="text-neutral-900 font-bold text-lg">신청 완료! 곧 연락드릴게요.</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="이메일 주소"
                className="flex-1 bg-white border border-neutral-200 rounded-2xl px-5 py-4 text-base text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-600/10 transition"
              />
              <button
                type="submit"
                disabled={submitting}
                className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-6 py-4 rounded-2xl font-bold text-base transition shadow-lg shadow-blue-600/20 whitespace-nowrap"
              >
                {submitting ? '신청 중...' : '무료 신청 →'}
              </button>
            </form>
          )}
          {error && <p className="text-red-500 text-base mt-3">{error}</p>}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-neutral-100 py-10 px-6">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row justify-between items-center gap-4 text-sm text-neutral-400">
          <span>simpleorder — B2B 주문을 링크 하나로</span>
          <div className="flex gap-6">
            <Link href="/simple-order/store/demo" className="hover:text-neutral-600 transition">데모</Link>
            <Link href="/simple-order/dashboard" className="hover:text-neutral-600 transition">대시보드</Link>
            <Link href="/" className="hover:text-neutral-600 transition">홈</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
