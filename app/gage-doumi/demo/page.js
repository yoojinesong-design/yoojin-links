'use client'
import { useState } from 'react'
import Link from 'next/link'

const TABS = [
  { key: '오늘현황', icon: '📊' },
  { key: '주문관리', icon: '🛵' },
  { key: '예약관리', icon: '📅' },
  { key: '우리가게', icon: '🏪' },
  { key: '리뷰', icon: '⭐' },
  { key: '고객소통', icon: '💬' },
]

const PLATFORMS = {
  배민: { color: '#2AC1BC', label: '배달의민족' },
  쿠팡이츠: { color: '#E3004F', label: '쿠팡이츠' },
  요기요: { color: '#FA0050', label: '요기요' },
  전화: { color: '#F59E0B', label: '전화주문' },
}

const RECENT_ORDERS = [
  { time: '14:32', platform: '배민', items: '감자탕(중) 1, 공기밥 2', amount: 32000, status: '배달중' },
  { time: '14:15', platform: '쿠팡이츠', items: '뼈해장국 2, 수육(소) 1', amount: 43000, status: '조리중' },
  { time: '13:58', platform: '요기요', items: '감자탕(대) 1, 공기밥 4', amount: 43000, status: '완료' },
  { time: '13:40', platform: '배민', items: '감자탕(소) 2, 뼈해장국 1', amount: 59000, status: '완료' },
  { time: '13:22', platform: '전화', items: '수육(대) 1, 공기밥 2', amount: 37000, status: '완료' },
]

const TODAY_RESERVATIONS = [
  { time: '17:00', name: '박**', size: 4, request: '창가 자리 부탁드려요' },
  { time: '18:00', name: '이**', size: 6, request: '아기 의자 필요' },
  { time: '18:30', name: '김**', size: 2, request: '' },
  { time: '19:00', name: '최**', size: 8, request: '생일 파티, 케이크 반입 가능한가요?' },
]

const ALL_ORDERS = [
  { id: 1, time: '14:32', platform: '배민', customer: '김**', items: '감자탕(중) 1, 공기밥 2', amount: 32000, status: '배달중' },
  { id: 2, time: '14:15', platform: '쿠팡이츠', customer: '이**', items: '뼈해장국 2, 수육(소) 1', amount: 43000, status: '조리중' },
  { id: 3, time: '13:58', platform: '요기요', customer: '박**', items: '감자탕(대) 1, 공기밥 4', amount: 43000, status: '완료' },
  { id: 4, time: '13:40', platform: '배민', customer: '정**', items: '감자탕(소) 2, 뼈해장국 1', amount: 59000, status: '완료' },
  { id: 5, time: '13:22', platform: '전화', customer: '한**', items: '수육(대) 1, 공기밥 2', amount: 37000, status: '완료' },
  { id: 6, time: '12:50', platform: '배민', customer: '조**', items: '감자탕(중) 1, 수육(소) 1', amount: 55000, status: '완료' },
  { id: 7, time: '12:30', platform: '쿠팡이츠', customer: '윤**', items: '뼈해장국 3, 공기밥 3', amount: 30000, status: '완료' },
  { id: 8, time: '12:05', platform: '요기요', customer: '강**', items: '감자탕(대) 1, 뼈해장국 1', amount: 48000, status: '완료' },
  { id: 9, time: '11:45', platform: '배민', customer: '송**', items: '수육(대) 1, 감자탕(소) 1', amount: 60000, status: '완료' },
  { id: 10, time: '11:20', platform: '전화', customer: '임**', items: '감자탕(중) 2, 공기밥 4', amount: 64000, status: '완료' },
]

const RESERVATIONS_TODAY = [
  { id: 1, time: '17:00', name: '박준혁', phone: '010-****-3842', size: 4, request: '창가 자리 부탁드려요', status: '확정' },
  { id: 2, time: '18:00', name: '이수진', phone: '010-****-7291', size: 6, request: '아기 의자 필요', status: '확정' },
  { id: 3, time: '18:30', name: '김태영', phone: '010-****-1058', size: 2, request: '', status: '확정' },
  { id: 4, time: '19:00', name: '최민서', phone: '010-****-5523', size: 8, request: '생일 파티, 케이크 반입 가능한가요?', status: '대기' },
  { id: 5, time: '19:30', name: '정하늘', phone: '010-****-8834', size: 3, request: '', status: '확정' },
  { id: 6, time: '20:00', name: '한소영', phone: '010-****-4412', size: 5, request: '조용한 자리 부탁드립니다', status: '확정' },
  { id: 7, time: '20:30', name: '오현우', phone: '010-****-9917', size: 4, request: '', status: '확정' },
  { id: 8, time: '21:00', name: '문지원', phone: '010-****-6603', size: 2, request: '늦을 수 있어요 (10분 정도)', status: '확정' },
]

const RESERVATIONS_TOMORROW = [
  { id: 9, time: '12:00', name: '강민재', phone: '010-****-2281', size: 10, request: '단체 회식, 코스 메뉴 문의', status: '확정' },
  { id: 10, time: '17:30', name: '유지은', phone: '010-****-3349', size: 4, request: '', status: '대기' },
  { id: 11, time: '18:00', name: '배성호', phone: '010-****-7756', size: 3, request: '알레르기 있음 (갑각류)', status: '확정' },
  { id: 12, time: '19:00', name: '신예린', phone: '010-****-1192', size: 6, request: '', status: '확정' },
  { id: 13, time: '20:00', name: '권도윤', phone: '010-****-8845', size: 2, request: '', status: '대기' },
]

const MENU_ITEMS = [
  { name: '감자탕', prices: [{ size: '소', price: 25000 }, { size: '중', price: 30000 }, { size: '대', price: 39000 }] },
  { name: '뼈해장국', prices: [{ size: '', price: 9000 }] },
  { name: '수육', prices: [{ size: '소', price: 25000 }, { size: '대', price: 35000 }] },
  { name: '모듬순대', prices: [{ size: '', price: 15000 }] },
  { name: '김치전', prices: [{ size: '', price: 12000 }] },
  { name: '공기밥', prices: [{ size: '', price: 1000 }] },
  { name: '소주', prices: [{ size: '', price: 5000 }] },
  { name: '맥주', prices: [{ size: '', price: 5000 }] },
]

const REVIEWS = [
  {
    id: 1, stars: 5, platform: '배달의민족', date: '2024-01-15',
    text: '감자탕이 정말 진하고 맛있어요! 뼈에 살도 많고 국물이 끝내줍니다. 밥 두 그릇 뚝딱했어요 ㅎㅎ',
    reply: '감사합니다 고객님! 항상 정성껏 끓이고 있습니다. 또 방문해주세요 😊',
  },
  {
    id: 2, stars: 4, platform: '구글', date: '2024-01-14',
    text: '오랜만에 방문했는데 여전히 맛있네요. 다만 주차가 좀 불편해요. 맛은 변함없이 좋습니다!',
    reply: null,
    aiSuggestion: '감사합니다 고객님! 주차 불편을 드려 죄송합니다. 현재 인근 공영주차장(도보 2분)과 제휴를 준비하고 있습니다. 다음 방문 시에는 더 편하게 오실 수 있도록 하겠습니다. 맛있게 드셨다니 기쁩니다! 😊',
  },
  {
    id: 3, stars: 5, platform: '네이버', date: '2024-01-13',
    text: '수육이 부드럽고 양이 많아서 좋았어요. 가족 모임으로 갔는데 모두 만족했습니다. 특히 어머니가 국물이 시원하다고 좋아하셨어요.',
    reply: null,
  },
  {
    id: 4, stars: 3, platform: '배달의민족', date: '2024-01-12',
    text: '맛은 괜찮은데 배달이 좀 늦었어요. 40분 걸렸습니다. 음식은 따뜻하게 왔어요.',
    reply: '고객님, 배달 지연으로 불편을 드려 정말 죄송합니다. 피크 시간대 배달 개선을 위해 노력하겠습니다. 다음에는 더 빠르게 배달해드리겠습니다!',
  },
  {
    id: 5, stars: 2, platform: '요기요', date: '2024-01-11',
    text: '감자탕 주문했는데 감자가 너무 적었어요. 예전에는 이렇지 않았는데... 좀 아쉬워요.',
    reply: null,
  },
]

const MESSAGES_SENT = [
  { date: '2024-01-14', type: '🎉 이벤트', title: '설 연휴 특별 할인 안내', recipients: 234 },
  { date: '2024-01-10', type: '🚫 휴무', title: '1월 15일 (월) 정기휴무 안내', recipients: 234 },
  { date: '2024-01-05', type: '🆕 신메뉴', title: '겨울 신메뉴 - 우거지 감자탕 출시!', recipients: 198 },
]

const MESSAGE_TEMPLATES = [
  { icon: '🎉', label: '이벤트/할인 공지', desc: '특별 할인, 이벤트 소식을 알려보세요' },
  { icon: '🚫', label: '휴무일 안내', desc: '임시 휴무, 연휴 안내를 보내세요' },
  { icon: '🆕', label: '신메뉴 소개', desc: '새로운 메뉴를 고객에게 알려보세요' },
  { icon: '📅', label: '예약 리마인더', desc: '예약 손님에게 리마인더를 보내세요' },
]

function formatWon(n) {
  return '₩' + n.toLocaleString('ko-KR')
}

function StatusBadge({ status }) {
  const styles = {
    '접수대기': 'bg-yellow-600/30 text-yellow-300 border-yellow-600/50',
    '조리중': 'bg-orange-600/30 text-orange-300 border-orange-600/50',
    '배달중': 'bg-blue-600/30 text-blue-300 border-blue-600/50',
    '완료': 'bg-green-600/30 text-green-300 border-green-600/50',
    '확정': 'bg-green-600/30 text-green-300 border-green-600/50',
    '대기': 'bg-yellow-600/30 text-yellow-300 border-yellow-600/50',
    '취소': 'bg-red-600/30 text-red-300 border-red-600/50',
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
        <span className="font-medium" style={{ fontSize: '16px' }}>{label}</span>
      </div>
      <div className="text-2xl font-bold text-white" style={{ fontSize: '28px' }}>{value}</div>
      {sub && <div className="text-sm font-semibold" style={{ color: subColor || '#9CA3AF', fontSize: '14px' }}>{sub}</div>}
    </div>
  )
}

function TabToday() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon="💰" label="오늘 매출" value={formatWon(847000)} sub="어제보다 +12% ↑" subColor="#22C55E" />
        <StatCard icon="🛵" label="배달 주문" value="23건" sub="배민 12 / 쿠팡 6 / 요기요 5" />
        <StatCard icon="📅" label="예약" value="8팀" sub="총 35명" />
        <StatCard icon="⭐" label="새 리뷰" value="3건" sub="평균 ⭐ 4.3" />
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
        <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2" style={{ fontSize: '22px' }}>
          🔔 실시간 주문
        </h2>
        <div className="space-y-3">
          {RECENT_ORDERS.map((o, i) => (
            <div key={i} className="flex flex-wrap items-center gap-3 bg-neutral-800/60 rounded-xl p-4 border border-neutral-700/50">
              <span className="text-lg font-bold text-neutral-300 min-w-[60px]" style={{ fontSize: '18px' }}>{o.time}</span>
              <PlatformBadge platform={o.platform} />
              <span className="text-base text-neutral-200 flex-1 min-w-[140px]" style={{ fontSize: '16px' }}>{o.items}</span>
              <span className="text-lg font-bold text-amber-400 min-w-[90px] text-right" style={{ fontSize: '20px' }}>{formatWon(o.amount)}</span>
              <StatusBadge status={o.status} />
            </div>
          ))}
        </div>
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
        <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2" style={{ fontSize: '22px' }}>
          📅 오늘 예약
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {TODAY_RESERVATIONS.map((r, i) => (
            <div key={i} className="bg-neutral-800/60 rounded-xl p-4 border border-neutral-700/50">
              <div className="flex items-center justify-between mb-2">
                <span className="text-lg font-bold text-amber-400" style={{ fontSize: '20px' }}>🕐 {r.time}</span>
                <span className="text-base text-neutral-300" style={{ fontSize: '16px' }}>{r.name} · {r.size}인</span>
              </div>
              {r.request && <div className="text-sm text-neutral-400 bg-neutral-700/40 rounded-lg px-3 py-2" style={{ fontSize: '14px' }}>💬 {r.request}</div>}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function TabOrders() {
  const [filter, setFilter] = useState('전체')
  const filters = ['전체', '배달의민족', '쿠팡이츠', '요기요', '전화주문']
  const filterMap = { '배달의민족': '배민', '쿠팡이츠': '쿠팡이츠', '요기요': '요기요', '전화주문': '전화' }
  const filtered = filter === '전체' ? ALL_ORDERS : ALL_ORDERS.filter(o => o.platform === (filterMap[filter] || filter))

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2">
        {filters.map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`px-5 py-3 rounded-xl font-bold transition-colors border ${filter === f ? 'bg-amber-500 text-neutral-950 border-amber-400' : 'bg-neutral-800 text-neutral-300 border-neutral-700 hover:bg-neutral-700'}`}
            style={{ fontSize: '16px', minHeight: '48px' }}>
            {f}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {filtered.map(o => (
          <div key={o.id} className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
            <div className="flex flex-wrap items-center gap-3 mb-3">
              <span className="text-lg font-bold text-neutral-300" style={{ fontSize: '18px' }}>🕐 {o.time}</span>
              <PlatformBadge platform={o.platform} />
              <span className="text-base text-neutral-400" style={{ fontSize: '16px' }}>{o.customer}</span>
              <div className="flex-1" />
              <StatusBadge status={o.status} />
            </div>
            <div className="text-base text-neutral-200 mb-2" style={{ fontSize: '18px' }}>🍲 {o.items}</div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="text-xl font-bold text-amber-400" style={{ fontSize: '22px' }}>{formatWon(o.amount)}</span>
              <div className="flex gap-2">
                {(o.status === '접수대기' || o.status === '조리중') && (
                  <button className="px-6 py-3 rounded-xl font-bold text-neutral-950 bg-amber-500 hover:bg-amber-400 transition-colors" style={{ fontSize: '16px', minHeight: '48px' }}>
                    ✅ 접수
                  </button>
                )}
                {o.status !== '완료' && (
                  <button className="px-6 py-3 rounded-xl font-bold text-white bg-green-600 hover:bg-green-500 transition-colors" style={{ fontSize: '16px', minHeight: '48px' }}>
                    ✔️ 완료
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

function TabReservations() {
  const today = new Date()
  const tomorrow = new Date(today)
  tomorrow.setDate(tomorrow.getDate() + 1)
  const fmtDate = (d) => `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold text-white" style={{ fontSize: '22px' }}>📅 {fmtDate(today)} (오늘)</h2>
        <button className="px-6 py-3 rounded-xl font-bold text-neutral-950 bg-amber-500 hover:bg-amber-400 transition-colors" style={{ fontSize: '18px', minHeight: '48px' }}>
          ➕ 새 예약
        </button>
      </div>

      <div className="space-y-3">
        {RESERVATIONS_TODAY.map(r => (
          <div key={r.id} className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
            <div className="flex flex-wrap items-center gap-3 mb-2">
              <span className="text-lg font-bold text-amber-400" style={{ fontSize: '20px' }}>🕐 {r.time}</span>
              <span className="text-lg text-white font-bold" style={{ fontSize: '18px' }}>{r.name}</span>
              <span className="text-base text-neutral-400" style={{ fontSize: '16px' }}>📞 {r.phone}</span>
              <span className="text-lg text-neutral-200 font-semibold" style={{ fontSize: '18px' }}>👥 {r.size}인</span>
              <div className="flex-1" />
              <StatusBadge status={r.status} />
            </div>
            {r.request && <div className="text-base text-neutral-300 bg-neutral-800/60 rounded-lg px-4 py-2 mb-3" style={{ fontSize: '16px' }}>💬 {r.request}</div>}
            <div className="flex flex-wrap gap-2">
              {r.status === '대기' && (
                <button className="px-5 py-3 rounded-xl font-bold text-neutral-950 bg-amber-500 hover:bg-amber-400 transition-colors" style={{ fontSize: '16px', minHeight: '48px' }}>
                  ✅ 확정
                </button>
              )}
              <button className="px-5 py-3 rounded-xl font-bold text-white bg-neutral-700 hover:bg-neutral-600 transition-colors" style={{ fontSize: '16px', minHeight: '48px' }}>
                📞 전화하기
              </button>
              {r.status !== '취소' && (
                <button className="px-5 py-3 rounded-xl font-bold text-red-300 bg-red-900/30 hover:bg-red-900/50 border border-red-800/50 transition-colors" style={{ fontSize: '16px', minHeight: '48px' }}>
                  ❌ 취소
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      <h2 className="text-xl font-bold text-white pt-2" style={{ fontSize: '22px' }}>📅 {fmtDate(tomorrow)} (내일)</h2>
      <div className="space-y-3">
        {RESERVATIONS_TOMORROW.map(r => (
          <div key={r.id} className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
            <div className="flex flex-wrap items-center gap-3 mb-2">
              <span className="text-lg font-bold text-amber-400" style={{ fontSize: '20px' }}>🕐 {r.time}</span>
              <span className="text-lg text-white font-bold" style={{ fontSize: '18px' }}>{r.name}</span>
              <span className="text-base text-neutral-400" style={{ fontSize: '16px' }}>📞 {r.phone}</span>
              <span className="text-lg text-neutral-200 font-semibold" style={{ fontSize: '18px' }}>👥 {r.size}인</span>
              <div className="flex-1" />
              <StatusBadge status={r.status} />
            </div>
            {r.request && <div className="text-base text-neutral-300 bg-neutral-800/60 rounded-lg px-4 py-2 mb-3" style={{ fontSize: '16px' }}>💬 {r.request}</div>}
            <div className="flex flex-wrap gap-2">
              {r.status === '대기' && (
                <button className="px-5 py-3 rounded-xl font-bold text-neutral-950 bg-amber-500 hover:bg-amber-400 transition-colors" style={{ fontSize: '16px', minHeight: '48px' }}>
                  ✅ 확정
                </button>
              )}
              <button className="px-5 py-3 rounded-xl font-bold text-white bg-neutral-700 hover:bg-neutral-600 transition-colors" style={{ fontSize: '16px', minHeight: '48px' }}>
                📞 전화하기
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 text-center">
          <div className="text-base text-neutral-400 mb-1" style={{ fontSize: '16px' }}>📅 오늘 총 예약</div>
          <div className="text-2xl font-bold text-amber-400" style={{ fontSize: '28px' }}>8팀</div>
        </div>
        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 text-center">
          <div className="text-base text-neutral-400 mb-1" style={{ fontSize: '16px' }}>📅 내일 총 예약</div>
          <div className="text-2xl font-bold text-amber-400" style={{ fontSize: '28px' }}>5팀</div>
        </div>
      </div>
    </div>
  )
}

function TabMyShop() {
  const shopInfo = [
    { icon: '🏪', label: '가게이름', value: '순이네 감자탕' },
    { icon: '📍', label: '주소', value: '서울시 마포구 합정동 123-4' },
    { icon: '📞', label: '전화', value: '02-1234-5678' },
    { icon: '⏰', label: '영업시간', value: '10:00 - 22:00' },
    { icon: '🚫', label: '정기 휴무', value: '매주 월요일' },
  ]

  return (
    <div className="space-y-6">
      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
        <h2 className="text-xl font-bold text-white mb-4" style={{ fontSize: '22px' }}>🏪 가게 정보</h2>
        <div className="space-y-4">
          {shopInfo.map((info, i) => (
            <div key={i} className="flex flex-wrap items-center justify-between gap-3 bg-neutral-800/60 rounded-xl p-4 border border-neutral-700/50">
              <div className="flex items-center gap-3 flex-1 min-w-[200px]">
                <span className="text-xl">{info.icon}</span>
                <div>
                  <div className="text-sm text-neutral-400" style={{ fontSize: '14px' }}>{info.label}</div>
                  <div className="text-lg text-white font-semibold" style={{ fontSize: '20px' }}>{info.value}</div>
                </div>
              </div>
              <button className="px-5 py-3 rounded-xl font-bold text-amber-400 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 transition-colors" style={{ fontSize: '16px', minHeight: '48px' }}>
                ✏️ 수정
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
        <h2 className="text-xl font-bold text-white mb-4" style={{ fontSize: '22px' }}>🍽️ 메뉴</h2>
        <div className="space-y-3">
          {MENU_ITEMS.map((item, i) => (
            <div key={i} className="flex flex-wrap items-center justify-between gap-2 bg-neutral-800/60 rounded-xl p-4 border border-neutral-700/50">
              <span className="text-lg text-white font-bold" style={{ fontSize: '20px' }}>{item.name}</span>
              <div className="flex flex-wrap gap-3">
                {item.prices.map((p, j) => (
                  <span key={j} className="text-base text-amber-400 font-semibold" style={{ fontSize: '18px' }}>
                    {p.size ? `(${p.size}) ` : ''}{formatWon(p.price)}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
        <h2 className="text-xl font-bold text-white mb-4" style={{ fontSize: '22px' }}>🌐 구글 비즈니스</h2>
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <span className="text-lg font-bold text-green-400" style={{ fontSize: '20px' }}>✅ 구글 비즈니스 연동됨</span>
        </div>
        <div className="text-base text-neutral-400 mb-4" style={{ fontSize: '16px' }}>📅 마지막 동기화: 2024년 1월 15일 오후 3:42</div>
        <button className="px-6 py-3 rounded-xl font-bold text-neutral-950 bg-amber-500 hover:bg-amber-400 transition-colors" style={{ fontSize: '16px', minHeight: '48px' }}>
          🔄 정보 업데이트
        </button>
      </div>
    </div>
  )
}

function TabReviews() {
  const [reviewFilter, setReviewFilter] = useState('전체')
  const reviewFilters = ['전체', '답변 안 한 리뷰', '별점 낮은 순']

  let filtered = [...REVIEWS]
  if (reviewFilter === '답변 안 한 리뷰') filtered = filtered.filter(r => !r.reply)
  if (reviewFilter === '별점 낮은 순') filtered = filtered.sort((a, b) => a.stars - b.stars)

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 text-center">
          <div className="text-base text-neutral-400 mb-1" style={{ fontSize: '16px' }}>⭐ 평균 별점</div>
          <div className="text-2xl font-bold text-amber-400" style={{ fontSize: '28px' }}>4.3</div>
        </div>
        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 text-center">
          <div className="text-base text-neutral-400 mb-1" style={{ fontSize: '16px' }}>📝 총 리뷰</div>
          <div className="text-2xl font-bold text-white" style={{ fontSize: '28px' }}>127건</div>
        </div>
        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 text-center">
          <div className="text-base text-neutral-400 mb-1" style={{ fontSize: '16px' }}>📈 이번 달</div>
          <div className="text-2xl font-bold text-green-400" style={{ fontSize: '28px' }}>+8건</div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {reviewFilters.map(f => (
          <button key={f} onClick={() => setReviewFilter(f)}
            className={`px-5 py-3 rounded-xl font-bold transition-colors border ${reviewFilter === f ? 'bg-amber-500 text-neutral-950 border-amber-400' : 'bg-neutral-800 text-neutral-300 border-neutral-700 hover:bg-neutral-700'}`}
            style={{ fontSize: '16px', minHeight: '48px' }}>
            {f}
          </button>
        ))}
      </div>

      <div className="space-y-4">
        {filtered.map(r => (
          <div key={r.id} className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
            <div className="flex flex-wrap items-center gap-3 mb-3">
              <span className="text-lg" style={{ fontSize: '20px' }}>{'⭐'.repeat(r.stars)}{'☆'.repeat(5 - r.stars)}</span>
              <span className="text-sm text-neutral-400 px-3 py-1 rounded-full bg-neutral-800 border border-neutral-700" style={{ fontSize: '14px' }}>{r.platform}</span>
              <span className="text-sm text-neutral-500" style={{ fontSize: '14px' }}>{r.date}</span>
            </div>
            <p className="text-base text-neutral-200 mb-4 leading-relaxed" style={{ fontSize: '18px' }}>{r.text}</p>

            {r.reply && (
              <div className="bg-neutral-800/60 rounded-xl p-4 border border-neutral-700/50 mb-3">
                <div className="text-sm text-neutral-400 mb-2" style={{ fontSize: '14px' }}>💬 사장님 답변</div>
                <p className="text-base text-neutral-300" style={{ fontSize: '16px' }}>{r.reply}</p>
              </div>
            )}

            {r.aiSuggestion && (
              <div className="bg-amber-500/10 rounded-xl p-4 border border-amber-500/30 mb-3">
                <div className="text-base text-amber-400 font-bold mb-2" style={{ fontSize: '16px' }}>🤖 AI 추천 답변</div>
                <p className="text-base text-neutral-200 mb-3" style={{ fontSize: '16px' }}>{r.aiSuggestion}</p>
                <div className="flex flex-wrap gap-2">
                  <button className="px-5 py-3 rounded-xl font-bold text-neutral-950 bg-amber-500 hover:bg-amber-400 transition-colors" style={{ fontSize: '16px', minHeight: '48px' }}>
                    ✅ 이 답변 사용하기
                  </button>
                  <button className="px-5 py-3 rounded-xl font-bold text-neutral-300 bg-neutral-700 hover:bg-neutral-600 transition-colors" style={{ fontSize: '16px', minHeight: '48px' }}>
                    ✏️ 직접 작성
                  </button>
                </div>
              </div>
            )}

            {!r.reply && !r.aiSuggestion && (
              <button className="px-5 py-3 rounded-xl font-bold text-amber-400 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 transition-colors" style={{ fontSize: '16px', minHeight: '48px' }}>
                ✏️ 답변하기
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function TabCommunication() {
  const [composing, setComposing] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState(null)

  return (
    <div className="space-y-6">
      <button onClick={() => { setComposing(true); setSelectedTemplate(null) }}
        className="w-full px-6 py-4 rounded-2xl font-bold text-neutral-950 bg-amber-500 hover:bg-amber-400 transition-colors text-center" style={{ fontSize: '20px', minHeight: '56px' }}>
        ✉️ 새 메시지 보내기
      </button>

      {composing && (
        <div className="bg-neutral-900 border border-amber-500/30 rounded-2xl p-5 space-y-4">
          <h3 className="text-lg font-bold text-white" style={{ fontSize: '20px' }}>✉️ 메시지 작성</h3>
          {!selectedTemplate && (
            <div className="grid grid-cols-2 gap-3">
              {MESSAGE_TEMPLATES.map((t, i) => (
                <button key={i} onClick={() => setSelectedTemplate(t)}
                  className="bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 rounded-xl p-4 text-left transition-colors"
                  style={{ minHeight: '48px' }}>
                  <div className="text-lg mb-1" style={{ fontSize: '18px' }}>{t.icon} {t.label}</div>
                  <div className="text-sm text-neutral-400" style={{ fontSize: '14px' }}>{t.desc}</div>
                </button>
              ))}
            </div>
          )}
          {selectedTemplate && (
            <>
              <div className="text-base text-amber-400 font-semibold" style={{ fontSize: '16px' }}>{selectedTemplate.icon} {selectedTemplate.label}</div>
              <textarea
                rows={5}
                placeholder="메시지 내용을 입력하세요..."
                className="w-full bg-neutral-800 border border-neutral-700 rounded-xl p-4 text-white placeholder-neutral-500 resize-none focus:outline-none focus:border-amber-500"
                style={{ fontSize: '18px' }}
              />
              <div className="flex flex-wrap gap-3">
                <button className="px-6 py-3 rounded-xl font-bold text-neutral-950 bg-amber-500 hover:bg-amber-400 transition-colors" style={{ fontSize: '16px', minHeight: '48px' }}>
                  📤 보내기
                </button>
                <button onClick={() => { setComposing(false); setSelectedTemplate(null) }}
                  className="px-6 py-3 rounded-xl font-bold text-neutral-300 bg-neutral-700 hover:bg-neutral-600 transition-colors" style={{ fontSize: '16px', minHeight: '48px' }}>
                  취소
                </button>
              </div>
            </>
          )}
        </div>
      )}

      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
        <h2 className="text-xl font-bold text-white mb-4" style={{ fontSize: '22px' }}>📋 메시지 템플릿</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {MESSAGE_TEMPLATES.map((t, i) => (
            <button key={i} onClick={() => { setComposing(true); setSelectedTemplate(t) }}
              className="bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 rounded-xl p-4 text-left transition-colors"
              style={{ minHeight: '48px' }}>
              <div className="text-lg font-bold text-white mb-1" style={{ fontSize: '18px' }}>{t.icon} {t.label}</div>
              <div className="text-sm text-neutral-400" style={{ fontSize: '14px' }}>{t.desc}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
        <h2 className="text-xl font-bold text-white mb-4" style={{ fontSize: '22px' }}>📨 최근 보낸 메시지</h2>
        <div className="space-y-3">
          {MESSAGES_SENT.map((m, i) => (
            <div key={i} className="flex flex-wrap items-center gap-3 bg-neutral-800/60 rounded-xl p-4 border border-neutral-700/50">
              <span className="text-base text-neutral-400" style={{ fontSize: '14px' }}>{m.date}</span>
              <span className="text-sm px-3 py-1 rounded-full bg-neutral-700 text-neutral-300 font-bold" style={{ fontSize: '14px' }}>{m.type}</span>
              <span className="text-base text-white flex-1 min-w-[140px] font-semibold" style={{ fontSize: '18px' }}>{m.title}</span>
              <span className="text-base text-neutral-400" style={{ fontSize: '16px' }}>👥 {m.recipients}명</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function GageDoumiDemo() {
  const [activeTab, setActiveTab] = useState('오늘현황')

  const renderTab = () => {
    switch (activeTab) {
      case '오늘현황': return <TabToday />
      case '주문관리': return <TabOrders />
      case '예약관리': return <TabReservations />
      case '우리가게': return <TabMyShop />
      case '리뷰': return <TabReviews />
      case '고객소통': return <TabCommunication />
      default: return <TabToday />
    }
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-white">
      <div className="max-w-4xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <Link href="/gage-doumi" className="text-amber-400 font-bold text-lg flex items-center gap-2" style={{ fontSize: '18px' }}>
              🏪 가게도우미
            </Link>
            <h1 className="text-2xl font-bold text-white mt-1" style={{ fontSize: '26px' }}>순이네 감자탕</h1>
          </div>
          <div className="text-right">
            <div className="text-base text-neutral-400" style={{ fontSize: '16px' }}>👤 사장님</div>
            <div className="text-sm text-neutral-500" style={{ fontSize: '14px' }}>2024.01.15 (월)</div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="overflow-x-auto -mx-4 px-4 mb-6">
          <div className="flex gap-2 min-w-max">
            {TABS.map(tab => (
              <button key={tab.key} onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2 px-5 py-3 rounded-xl font-bold whitespace-nowrap transition-colors border ${activeTab === tab.key ? 'bg-amber-500 text-neutral-950 border-amber-400' : 'bg-neutral-900 text-neutral-300 border-neutral-800 hover:bg-neutral-800'}`}
                style={{ fontSize: '16px', minHeight: '48px' }}>
                <span className="text-xl">{tab.icon}</span>
                {tab.key}
              </button>
            ))}
          </div>
        </div>

        {/* Tab Content */}
        {renderTab()}

        {/* Footer */}
        <div className="mt-8 pt-6 border-t border-neutral-800 text-center space-y-2">
          <p className="text-sm text-neutral-500" style={{ fontSize: '14px' }}>🏪 가게도우미 — 우리 가게 관리를 쉽고 편하게</p>
          <p className="text-xs text-neutral-600">이 페이지의 모든 데이터는 데모용 가상 데이터입니다. 실제 가게/고객 정보가 아닙니다.</p>
        </div>
      </div>
    </div>
  )
}
