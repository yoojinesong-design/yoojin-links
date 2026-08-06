'use client'
import { useState } from 'react'
import Link from 'next/link'

const PAIN_POINTS = [
  { pain: '배달앱 주문 놓쳐서 별점 떨어짐', fix: '모든 배달앱 주문 한 화면에' },
  { pain: '구글에 가게 검색해도 안 나옴', fix: '구글 프로필 자동 관리' },
  { pain: '예약 전화 받다가 요리 태움', fix: '링크 하나로 예약 자동 접수' },
  { pain: '단골 손님한테 연락할 방법이 없음', fix: '문자/카카오 한번에 발송' },
  { pain: '나쁜 리뷰 달렸는데 뭐라고 써야 할지 모름', fix: 'AI가 정중한 답변 제안' },
]

const FEATURES = [
  { icon: '📱', title: '주문 통합관리', desc: '배민, 쿠팡이츠, 요기요 주문을 한 화면에서 확인하고 관리하세요.' },
  { icon: '📅', title: '쉬운 예약관리', desc: '링크 하나 공유하면 손님이 직접 예약. 전화 안 받아도 돼요.' },
  { icon: '⭐', title: '리뷰 답변 도우미', desc: '리뷰 알림 + AI 답변 제안. 한 번 터치로 바로 게시할 수 있어요.' },
  { icon: '🔍', title: '구글 가게 관리', desc: '영업시간, 메뉴, 사진 — 가게 정보를 쉽게 업데이트하세요.' },
  { icon: '💬', title: '고객 소통', desc: '휴무일 공지, 이벤트, 신메뉴 알림을 한 번에 발송하세요.' },
  { icon: '📊', title: '매출 한눈에', desc: '오늘, 이번 주, 이번 달 매출을 간단하게 확인하세요.' },
]

const TESTIMONIALS = [
  { name: 'A 사장님', shop: '감자탕 전문점', years: '예상 후기', quote: '배달앱 주문 놓치는 거 없어졌어요. 이제 마음 편하게 요리에만 집중해요.' },
  { name: 'B 사장님', shop: '칼국수 전문점', years: '예상 후기', quote: '아들이 해주던 구글 관리를 이제 제가 직접 해요. 생각보다 쉽더라고요.' },
  { name: 'C 사장님', shop: '분식점', years: '예상 후기', quote: '글씨가 커서 좋아요. 복잡한 거 하나도 없고, 딱 필요한 것만 있어요.' },
]

const STEPS = [
  { num: '1', title: '가입하고 가게 정보 입력', desc: '상호명, 주소, 메뉴만 넣으면 돼요.' },
  { num: '2', title: '배달앱, 구글 연동', desc: '저희가 처음부터 끝까지 도와드려요.' },
  { num: '3', title: '끝! 이제 다 관리하세요', desc: '핸드폰 하나로 가게를 관리할 수 있어요.' },
]

export default function GageDoumiLanding() {
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
        body: JSON.stringify({ email, product: 'gage-doumi' }),
      })
      const data = await res.json()
      if (!res.ok && res.status !== 200) throw new Error(data.error || '오류가 발생했어요')
      setSubmitted(true)
    } catch (err) {
      setError(err.message || '네트워크 오류 — 다시 시도해 주세요')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      {/* Nav */}
      <nav className="fixed top-0 w-full z-50 border-b border-neutral-800/60 bg-neutral-950/80 backdrop-blur-lg">
        <div className="max-w-5xl mx-auto px-5 h-14 flex items-center justify-between">
          <span className="text-lg font-bold tracking-tight">가게<span className="text-amber-400">도우미</span></span>
          <a href="#waitlist" className="text-base bg-amber-500 hover:bg-amber-400 text-neutral-950 px-5 py-2 rounded-lg font-bold transition">무료 체험</a>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-28 pb-20 px-5">
        <div className="max-w-3xl mx-auto text-center">
          <div className="inline-block text-sm font-semibold tracking-wide text-amber-400 border border-amber-400/30 rounded-full px-4 py-1.5 mb-6">
            식당 사장님을 위한 디지털 매니저
          </div>
          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight leading-[1.2] mb-6">
            기술 몰라도 괜찮아요.<br />
            <span className="text-amber-400">사장님 가게, 저희가 도와드립니다.</span>
          </h1>
          <p className="text-lg sm:text-xl text-neutral-400 max-w-xl mx-auto mb-8 leading-relaxed">
            구글 관리, 배달앱, 예약, 고객 메시지까지 —<br className="hidden sm:block" />
            복잡한 건 저희가 다 해드릴게요. 쉬운 화면 하나로.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <a href="#waitlist" className="bg-amber-500 hover:bg-amber-400 text-neutral-950 px-8 py-4 rounded-xl font-bold text-lg transition shadow-lg shadow-amber-500/20">
              무료로 시작하기
            </a>
            <Link href="/gage-doumi/demo" className="border border-neutral-700 hover:border-neutral-500 text-neutral-300 px-8 py-4 rounded-xl font-bold text-lg transition">
              데모 보기
            </Link>
          </div>
          <p className="text-sm text-neutral-500 mt-4">설치 없음. 핸드폰으로 바로 시작.</p>
        </div>
      </section>

      {/* Stats */}
      <section className="border-y border-neutral-800/60 bg-neutral-900/40">
        <div className="max-w-4xl mx-auto px-5 py-10 grid grid-cols-2 sm:grid-cols-4 gap-6 text-center">
          {[
            ['~70%', '소상공인 중 디지털 전환\n어려움 호소*'],
            ['하루 2시간+', '배달앱, 전화, 예약에\n쓰는 시간(추정)'],
            ['평균 3+개', '사장님이 동시에\n관리하는 앱 수(추정)'],
            ['$14.99/mo', 'Everything included'],
          ].map(([stat, desc]) => (
            <div key={stat}>
              <div className="text-2xl sm:text-3xl font-extrabold text-amber-400 mb-2">{stat}</div>
              <div className="text-sm text-neutral-400 whitespace-pre-line leading-snug">{desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Pain points */}
      <section className="py-20 px-5">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-12">
            <div className="text-sm font-semibold tracking-wide text-amber-400 mb-2">고민 → 해결</div>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">이런 고민, 사장님도 하고 계시죠?</h2>
          </div>
          <div className="space-y-3">
            {PAIN_POINTS.map((p, i) => (
              <div key={i} className="grid grid-cols-1 sm:grid-cols-[1fr_auto_1fr] gap-2 sm:gap-4 items-center bg-neutral-900/50 border border-neutral-800/60 rounded-xl p-5">
                <div className="text-base text-neutral-400">{p.pain}</div>
                <div className="hidden sm:block text-amber-400 text-xl font-bold">→</div>
                <div className="text-base font-semibold text-amber-300">{p.fix}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 px-5 bg-neutral-900/30">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-14">
            <div className="text-sm font-semibold tracking-wide text-amber-400 mb-2">주요 기능</div>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">딱 필요한 것만. 복잡한 건 없습니다.</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {FEATURES.map((f) => (
              <div key={f.title} className="bg-neutral-900/60 border border-neutral-800/60 rounded-xl p-6">
                <div className="text-3xl mb-3">{f.icon}</div>
                <h3 className="font-bold text-lg mb-2">{f.title}</h3>
                <p className="text-base text-neutral-400 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-20 px-5">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-14">
            <div className="text-sm font-semibold tracking-wide text-amber-400 mb-2">시작하기</div>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">10분이면 시작할 수 있어요</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            {STEPS.map((s) => (
              <div key={s.num} className="text-center">
                <div className="w-14 h-14 rounded-full bg-amber-500/20 border-2 border-amber-500/40 flex items-center justify-center mx-auto mb-4">
                  <span className="text-2xl font-extrabold text-amber-400">{s.num}</span>
                </div>
                <h3 className="font-bold text-lg mb-2">{s.title}</h3>
                <p className="text-base text-neutral-400">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-20 px-5 bg-neutral-900/30">
        <div className="max-w-lg mx-auto text-center">
          <div className="text-sm font-semibold tracking-wide text-amber-400 mb-2">가격 안내</div>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight mb-10">쉽고 투명한 가격</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-neutral-900/80 border border-neutral-700/60 rounded-2xl p-6 text-left">
              <div className="text-base font-semibold text-neutral-400 mb-2">무료</div>
              <div className="text-3xl font-extrabold mb-1">$0</div>
              <p className="text-sm text-neutral-500 mb-4">부담 없이 시작하세요</p>
              <ul className="space-y-2">
                {['기본 주문관리', '예약 5건/월', '리뷰 알림'].map(f => (
                  <li key={f} className="flex gap-2 text-base text-neutral-400">
                    <span className="text-amber-400 flex-shrink-0">✓</span>{f}
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-neutral-900/80 border-2 border-amber-500/50 rounded-2xl p-6 text-left relative">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-amber-500 text-neutral-950 text-sm font-bold px-4 py-1 rounded-full">추천</div>
              <div className="text-base font-semibold text-amber-400 mb-2">프로</div>
              <div className="text-3xl font-extrabold mb-1">$14.99<span className="text-lg font-normal text-neutral-500">/mo</span></div>
              <p className="text-sm text-neutral-500 mb-4">첫 달 무료 체험</p>
              <ul className="space-y-2">
                {['무제한 예약', 'AI 리뷰 답변', '고객 메시지 발송', '매출 리포트', '구글 프로필 관리', '우선 고객 지원'].map(f => (
                  <li key={f} className="flex gap-2 text-base text-neutral-300">
                    <span className="text-amber-400 flex-shrink-0">✓</span>{f}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="py-20 px-5">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-14">
            <div className="text-sm font-semibold tracking-wide text-amber-400 mb-2">이런 변화를 기대해요</div>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">사장님들이 기대하는 후기</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {TESTIMONIALS.map((t) => (
              <div key={t.name} className="bg-neutral-900/60 border border-neutral-800/60 rounded-xl p-6">
                <p className="text-base text-neutral-300 leading-relaxed mb-4">"{t.quote}"</p>
                <div>
                  <div className="font-bold text-base">{t.name}</div>
                  <div className="text-sm text-neutral-500">{t.shop} · {t.years}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA / Waitlist */}
      <section id="waitlist" className="py-20 px-5 bg-neutral-900/30">
        <div className="max-w-xl mx-auto text-center">
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight mb-4">
            사장님 가게도<br />
            <span className="text-amber-400">쉬워질 수 있어요</span>
          </h2>
          <p className="text-neutral-400 mb-8 text-lg">
            이메일 남겨주시면 빠르게 안내드리겠습니다.
          </p>
          {submitted ? (
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-6">
              <div className="text-amber-400 text-3xl mb-2">✓</div>
              <p className="text-neutral-200 font-bold text-lg">신청 완료! 빠르게 연락드리겠습니다.</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="이메일 주소"
                className="flex-1 bg-neutral-900 border border-neutral-700 rounded-xl px-5 py-4 text-base text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:border-amber-500 transition"
              />
              <button
                type="submit"
                disabled={submitting}
                className="bg-amber-500 hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed text-neutral-950 px-6 py-4 rounded-xl font-bold text-base transition shadow-lg shadow-amber-500/20 whitespace-nowrap"
              >
                {submitting ? '신청 중...' : '무료 신청하기'}
              </button>
            </form>
          )}
          {error && <p className="text-red-400 text-base mt-3">{error}</p>}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-neutral-800/60 py-8 px-5">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row justify-between items-center gap-4 text-sm text-neutral-600">
          <span>가게도우미 — 식당 사장님을 위한 디지털 매니저</span>
          <div className="flex gap-4">
            <Link href="/gage-doumi/demo" className="hover:text-neutral-400 transition">데모</Link>
            <Link href="/" className="hover:text-neutral-400 transition">홈</Link>
          </div>
        </div>
        <div className="max-w-5xl mx-auto mt-4 text-xs text-neutral-700 leading-relaxed text-center">
          <p>* 통계 수치는 내부 추정치이며 정확하지 않을 수 있습니다. 예상 후기는 실제 사용자의 후기가 아닙니다.</p>
          <p className="mt-1">배달의민족, 쿠팡이츠, 요기요, 구글은 각 회사의 등록 상표입니다. 가게도우미는 해당 회사와 제휴하거나 보증을 받지 않았습니다.</p>
        </div>
      </footer>
    </div>
  )
}
