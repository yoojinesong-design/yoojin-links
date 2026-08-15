export const TABS = [
  { key: '오늘현황', icon: '📊' },
  { key: '주문관리', icon: '🛵' },
  { key: '예약관리', icon: '📅' },
  { key: '우리가게', icon: '🏪' },
  { key: '리뷰', icon: '⭐' },
  { key: '고객소통', icon: '💬' },
]

export const PLATFORMS = {
  배민: { color: '#2AC1BC', label: '배달의민족' },
  쿠팡이츠: { color: '#E3004F', label: '쿠팡이츠' },
  요기요: { color: '#FA0050', label: '요기요' },
  전화: { color: '#F59E0B', label: '전화주문' },
}

export const RECENT_ORDERS = [
  { time: '14:32', platform: '배민', items: '감자탕(중) 1, 공기밥 2', amount: 32000, status: '배달중' },
  { time: '14:15', platform: '쿠팡이츠', items: '뼈해장국 2, 수육(소) 1', amount: 43000, status: '조리중' },
  { time: '13:58', platform: '요기요', items: '감자탕(대) 1, 공기밥 4', amount: 43000, status: '완료' },
  { time: '13:40', platform: '배민', items: '감자탕(소) 2, 뼈해장국 1', amount: 59000, status: '완료' },
  { time: '13:22', platform: '전화', items: '수육(대) 1, 공기밥 2', amount: 37000, status: '완료' },
]

export const TODAY_RESERVATIONS = [
  { time: '17:00', name: '박**', size: 4, request: '창가 자리 부탁드려요' },
  { time: '18:00', name: '이**', size: 6, request: '아기 의자 필요' },
  { time: '18:30', name: '김**', size: 2, request: '' },
  { time: '19:00', name: '최**', size: 8, request: '생일 파티, 케이크 반입 가능한가요?' },
]

export const ALL_ORDERS = [
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

export const RESERVATIONS_TODAY = [
  { id: 1, time: '17:00', name: '박준혁', phone: '010-****-3842', size: 4, request: '창가 자리 부탁드려요', status: '확정' },
  { id: 2, time: '18:00', name: '이수진', phone: '010-****-7291', size: 6, request: '아기 의자 필요', status: '확정' },
  { id: 3, time: '18:30', name: '김태영', phone: '010-****-1058', size: 2, request: '', status: '확정' },
  { id: 4, time: '19:00', name: '최민서', phone: '010-****-5523', size: 8, request: '생일 파티, 케이크 반입 가능한가요?', status: '대기' },
  { id: 5, time: '19:30', name: '정하늘', phone: '010-****-8834', size: 3, request: '', status: '확정' },
  { id: 6, time: '20:00', name: '한소영', phone: '010-****-4412', size: 5, request: '조용한 자리 부탁드립니다', status: '확정' },
  { id: 7, time: '20:30', name: '오현우', phone: '010-****-9917', size: 4, request: '', status: '확정' },
  { id: 8, time: '21:00', name: '문지원', phone: '010-****-6603', size: 2, request: '늦을 수 있어요 (10분 정도)', status: '확정' },
]

export const RESERVATIONS_TOMORROW = [
  { id: 9, time: '12:00', name: '강민재', phone: '010-****-2281', size: 10, request: '단체 회식, 코스 메뉴 문의', status: '확정' },
  { id: 10, time: '17:30', name: '유지은', phone: '010-****-3349', size: 4, request: '', status: '대기' },
  { id: 11, time: '18:00', name: '배성호', phone: '010-****-7756', size: 3, request: '알레르기 있음 (갑각류)', status: '확정' },
  { id: 12, time: '19:00', name: '신예린', phone: '010-****-1192', size: 6, request: '', status: '확정' },
  { id: 13, time: '20:00', name: '권도윤', phone: '010-****-8845', size: 2, request: '', status: '대기' },
]

export const MENU_ITEMS = [
  { name: '감자탕', prices: [{ size: '소', price: 25000 }, { size: '중', price: 30000 }, { size: '대', price: 39000 }] },
  { name: '뼈해장국', prices: [{ size: '', price: 9000 }] },
  { name: '수육', prices: [{ size: '소', price: 25000 }, { size: '대', price: 35000 }] },
  { name: '모듬순대', prices: [{ size: '', price: 15000 }] },
  { name: '김치전', prices: [{ size: '', price: 12000 }] },
  { name: '공기밥', prices: [{ size: '', price: 1000 }] },
  { name: '소주', prices: [{ size: '', price: 5000 }] },
  { name: '맥주', prices: [{ size: '', price: 5000 }] },
]

export const REVIEWS = [
  { id: 1, stars: 5, platform: '배달의민족', date: '2024-01-15', text: '감자탕이 정말 진하고 맛있어요! 뼈에 살도 많고 국물이 끝내줍니다. 밥 두 그릇 뚝딱했어요 ㅎㅎ', reply: '감사합니다 고객님! 항상 정성껏 끓이고 있습니다. 또 방문해주세요 😊' },
  { id: 2, stars: 4, platform: '구글', date: '2024-01-14', text: '오랜만에 방문했는데 여전히 맛있네요. 다만 주차가 좀 불편해요. 맛은 변함없이 좋습니다!', reply: null, aiSuggestion: '감사합니다 고객님! 주차 불편을 드려 죄송합니다. 현재 인근 공영주차장(도보 2분)과 제휴를 준비하고 있습니다. 다음 방문 시에는 더 편하게 오실 수 있도록 하겠습니다. 맛있게 드셨다니 기쁩니다! 😊' },
  { id: 3, stars: 5, platform: '네이버', date: '2024-01-13', text: '수육이 부드럽고 양이 많아서 좋았어요. 가족 모임으로 갔는데 모두 만족했습니다. 특히 어머니가 국물이 시원하다고 좋아하셨어요.', reply: null },
  { id: 4, stars: 3, platform: '배달의민족', date: '2024-01-12', text: '맛은 괜찮은데 배달이 좀 늦었어요. 40분 걸렸습니다. 음식은 따뜻하게 왔어요.', reply: '고객님, 배달 지연으로 불편을 드려 정말 죄송합니다. 피크 시간대 배달 개선을 위해 노력하겠습니다. 다음에는 더 빠르게 배달해드리겠습니다!' },
  { id: 5, stars: 2, platform: '요기요', date: '2024-01-11', text: '감자탕 주문했는데 감자가 너무 적었어요. 예전에는 이렇지 않았는데... 좀 아쉬워요.', reply: null },
]

export const MESSAGES_SENT = [
  { date: '2024-01-14', type: '🎉 이벤트', title: '설 연휴 특별 할인 안내', recipients: 234 },
  { date: '2024-01-10', type: '🚫 휴무', title: '1월 15일 (월) 정기휴무 안내', recipients: 234 },
  { date: '2024-01-05', type: '🆕 신메뉴', title: '겨울 신메뉴 - 우거지 감자탕 출시!', recipients: 198 },
]

export const MESSAGE_TEMPLATES = [
  { icon: '🎉', label: '이벤트/할인 공지', desc: '특별 할인, 이벤트 소식을 알려보세요' },
  { icon: '🚫', label: '휴무일 안내', desc: '임시 휴무, 연휴 안내를 보내세요' },
  { icon: '🆕', label: '신메뉴 소개', desc: '새로운 메뉴를 고객에게 알려보세요' },
  { icon: '📅', label: '예약 리마인더', desc: '예약 손님에게 리마인더를 보내세요' },
]
