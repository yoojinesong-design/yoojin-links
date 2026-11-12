import { redirect } from 'next/navigation'

// 예전 데모 주소 — 실제 주문 페이지와 같은 화면을 쓰는 데모 가게로 보낸다
export default function SimpleOrderDemoRedirect() {
  redirect('/simple-order/store/demo')
}
