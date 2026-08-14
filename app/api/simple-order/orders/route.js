import { NextResponse } from 'next/server'
import { getSupabaseServer } from '../../../../lib/supabase-server'

// POST /api/simple-order/orders — 주문 생성 + 알림
export async function POST(request) {
  const body = await request.json()
  const { store_slug, customer_name, customer_contact, customer_note, items, total } = body

  if (!store_slug || !customer_name || !customer_contact || !items?.length) {
    return NextResponse.json({ error: '필수 정보가 빠졌어요.' }, { status: 400 })
  }

  const supabase = await getSupabaseServer()

  if (!supabase) {
    return NextResponse.json({
      ok: true,
      demo: true,
      order: { order_number: 'DEMO-' + Date.now().toString(36).toUpperCase() },
    })
  }

  // 가게 조회
  const { data: store } = await supabase
    .from('stores')
    .select('id, name, notification_email')
    .eq('slug', store_slug)
    .single()

  if (!store) {
    return NextResponse.json({ error: '가게를 찾을 수 없어요.' }, { status: 404 })
  }

  // 주문번호 생성
  const orderNumber = 'ORD-' + Date.now().toString(36).toUpperCase()

  // 주문 저장
  const { data: order, error: orderErr } = await supabase
    .from('orders')
    .insert({
      store_id: store.id,
      order_number: orderNumber,
      customer_name,
      customer_contact,
      customer_note: customer_note || '',
      items,
      total,
      status: 'pending',
    })
    .select()
    .single()

  if (orderErr) {
    console.error('Order insert error:', orderErr)
    return NextResponse.json({ error: '주문 저장에 실패했어요.' }, { status: 500 })
  }

  // 이메일 알림 (notification_email이 있으면)
  if (store.notification_email) {
    try {
      await sendOrderNotification(store, order, items)
    } catch (e) {
      console.error('Notification error:', e)
      // 알림 실패해도 주문은 성공
    }
  }

  return NextResponse.json({ ok: true, order: { id: order.id, order_number: orderNumber } })
}

// GET /api/simple-order/orders?store_slug=xxx — 가게 주문 목록
export async function GET(request) {
  const { searchParams } = new URL(request.url)
  const storeSlug = searchParams.get('store_slug')

  if (!storeSlug) {
    return NextResponse.json({ error: 'store_slug가 필요합니다.' }, { status: 400 })
  }

  const supabase = await getSupabaseServer()

  if (!supabase) {
    return NextResponse.json({ orders: [], demo: true })
  }

  // 가게 ID 조회
  const { data: store } = await supabase
    .from('stores')
    .select('id')
    .eq('slug', storeSlug)
    .single()

  if (!store) {
    return NextResponse.json({ error: '가게를 찾을 수 없어요.' }, { status: 404 })
  }

  // 주문 목록
  const { data: orders } = await supabase
    .from('orders')
    .select('*')
    .eq('store_id', store.id)
    .order('created_at', { ascending: false })
    .limit(100)

  return NextResponse.json({
    orders: (orders || []).map(o => ({
      id: o.id,
      order_number: o.order_number,
      customer: {
        name: o.customer_name,
        contact: o.customer_contact,
        note: o.customer_note,
      },
      items: o.items,
      total: o.total,
      status: o.status,
      date: o.created_at,
    })),
  })
}

// 이메일 알림 함수 (향후 Resend/SendGrid 등 연동)
async function sendOrderNotification(store, order, items) {
  // Resend API 키가 있으면 이메일 발송
  const resendKey = process.env.RESEND_API_KEY
  if (!resendKey) {
    console.log(`[알림] ${store.name}에 새 주문: ${order.order_number} (₩${order.total.toLocaleString()}) — 이메일 서비스 미연결`)
    return
  }

  const itemList = items.map(i => `• ${i.name} × ${i.qty} = ₩${(i.price * i.qty).toLocaleString()}`).join('\n')

  await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${resendKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from: 'SimpleOrder <noreply@simpleorder.kr>',
      to: store.notification_email,
      subject: `[주문알림] ${order.customer_name}님이 ₩${order.total.toLocaleString()} 주문했어요`,
      text: `새 주문이 들어왔어요!\n\n주문번호: ${order.order_number}\n업체: ${order.customer_name}\n연락처: ${order.customer_contact}\n\n${itemList}\n\n합계: ₩${order.total.toLocaleString()}\n\n대시보드에서 확인하세요.`,
    }),
  })
}
