import { NextResponse } from 'next/server'
import { getSupabaseServer } from '@/lib/supabase-server'
import { createSquareOrder } from '@/lib/square'
import { getSquareCredentials } from '@/lib/square-credentials'

const MAX_QTY = 9999

// POST /api/simple-order/orders — 주문 생성 + 알림 + Square POS 연동
export async function POST(request) {
  const body = await request.json().catch(() => null)
  const { store_slug, customer_name, customer_contact, customer_note, items } = body || {}

  if (!store_slug || !customer_name || !customer_contact || !Array.isArray(items) || items.length === 0) {
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

  const { data: store } = await supabase
    .from('stores')
    .select('id, name, notification_email')
    .eq('slug', store_slug)
    .single()

  if (!store) {
    return NextResponse.json({ error: '가게를 찾을 수 없어요.' }, { status: 404 })
  }

  // 가격은 브라우저가 보낸 값을 믿지 않고 DB의 상품 가격으로 다시 계산한다
  const { data: products } = await supabase
    .from('products')
    .select('id, name, price')
    .eq('store_id', store.id)
    .eq('active', true)

  const productById = new Map((products || []).map(p => [String(p.id), p]))
  const orderItems = []

  for (const item of items) {
    const product = productById.get(String(item?.id))
    const qty = Number(item?.qty)
    if (!product || !Number.isInteger(qty) || qty < 1 || qty > MAX_QTY) {
      return NextResponse.json({ error: '주문 상품 정보가 올바르지 않아요. 페이지를 새로고침 후 다시 시도해주세요.' }, { status: 400 })
    }
    orderItems.push({ id: product.id, name: product.name, price: product.price, qty })
  }

  const total = orderItems.reduce((sum, i) => sum + i.price * i.qty, 0)
  const orderNumber = 'ORD-' + Date.now().toString(36).toUpperCase()

  const { data: order, error: orderErr } = await supabase
    .from('orders')
    .insert({
      store_id: store.id,
      order_number: orderNumber,
      customer_name,
      customer_contact,
      customer_note: customer_note || '',
      items: orderItems,
      total,
      status: 'pending',
    })
    .select()
    .single()

  if (orderErr) {
    console.error('Order insert error:', orderErr)
    return NextResponse.json({ error: '주문 저장에 실패했어요.' }, { status: 500 })
  }

  // Square POS 연동 — 연결된 가게면 Square에도 주문 전송.
  // 실패해도 주문 자체는 성공으로 처리한다.
  let squareOrderId = null
  try {
    const credentials = await getSquareCredentials(store.id)
    if (credentials) {
      const squareOrder = await createSquareOrder(credentials, order)
      squareOrderId = squareOrder?.id || null
      if (squareOrderId) {
        await supabase.from('orders').update({ square_order_id: squareOrderId }).eq('id', order.id)
      }
    }
  } catch (e) {
    console.error('Square order sync error:', e)
  }

  if (store.notification_email) {
    try {
      await sendOrderNotification(store, order)
    } catch (e) {
      console.error('Notification error:', e)
    }
  }

  return NextResponse.json({
    ok: true,
    order: { id: order.id, order_number: orderNumber, total },
    square_synced: Boolean(squareOrderId),
  })
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

  const { data: store } = await supabase
    .from('stores')
    .select('id')
    .eq('slug', storeSlug)
    .single()

  if (!store) {
    return NextResponse.json({ error: '가게를 찾을 수 없어요.' }, { status: 404 })
  }

  const { data: orders, error } = await supabase
    .from('orders')
    .select('*')
    .eq('store_id', store.id)
    .order('created_at', { ascending: false })
    .limit(100)

  if (error) {
    console.error('Orders fetch error:', error)
    return NextResponse.json({ error: '주문을 불러오지 못했어요.' }, { status: 500 })
  }

  return NextResponse.json({
    orders: orders.map(o => ({
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

// 새 주문 이메일 알림 (RESEND_API_KEY가 있을 때만 발송)
async function sendOrderNotification(store, order) {
  const resendKey = process.env.RESEND_API_KEY
  const won = (n) => `₩${n.toLocaleString('ko-KR')}`

  if (!resendKey) {
    console.log(`[알림] ${store.name}에 새 주문: ${order.order_number} (${won(order.total)}) — 이메일 서비스 미연결`)
    return
  }

  const itemList = order.items.map(i => `• ${i.name} × ${i.qty} = ${won(i.price * i.qty)}`).join('\n')

  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${resendKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from: 'SimpleOrder <noreply@simpleorder.kr>',
      to: store.notification_email,
      subject: `[주문알림] ${order.customer_name}님이 ${won(order.total)} 주문했어요`,
      text: `새 주문이 들어왔어요!\n\n주문번호: ${order.order_number}\n업체: ${order.customer_name}\n연락처: ${order.customer_contact}\n\n${itemList}\n\n합계: ${won(order.total)}\n\n대시보드에서 확인하세요.`,
    }),
  })

  if (!res.ok) throw new Error(`Resend responded ${res.status}`)
}
