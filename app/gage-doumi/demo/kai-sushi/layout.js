export const metadata = {
  title: 'KAI Sushi & Roll — 가게도우미 sample dashboard',
  description: 'Sample restaurant dashboard built around KAI Sushi & Roll’s public listing info. Orders, reservations and reviews are made up for the demo.',
  // 실제 가게 이름이 들어간 샘플 페이지라 검색엔진에는 노출하지 않는다
  robots: { index: false, follow: false },
}

export default function KaiSushiDemoLayout({ children }) {
  return children
}
