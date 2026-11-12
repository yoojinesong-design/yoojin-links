import { NextResponse } from 'next/server'
import { getSupabaseServer } from '@/lib/supabase-server'

const SLUG_RE = /^[a-z0-9가-힣]+(-[a-z0-9가-힣]+)*$/

// POST /api/simple-order/stores — 가게 생성 + 상품 등록
export async function POST(request) {
  const body = await request.json().catch(() => null)
  const { name, slug, description, type, notification_email, products } = body || {}

  if (!name || !slug) {
    return NextResponse.json({ error: '가게 이름과 주소가 필요합니다.' }, { status: 400 })
  }
  if (!SLUG_RE.test(slug) || slug.length > 60) {
    return NextResponse.json({ error: '주소는 영문 소문자, 숫자, 한글, 하이픈(-)만 쓸 수 있어요.' }, { status: 400 })
  }

  const productRows = (Array.isArray(products) ? products : []).map((p, i) => ({
    name: String(p?.name || '').trim(),
    price: Number(p?.price),
    unit: p?.unit || '',
    category: p?.category || '기타',
    emoji: p?.emoji || '📦',
    sort_order: i,
  }))

  if (productRows.some(p => !p.name || !Number.isInteger(p.price) || p.price < 0)) {
    return NextResponse.json({ error: '상품 이름과 가격(0 이상의 정수)을 확인해주세요.' }, { status: 400 })
  }

  const supabase = await getSupabaseServer()

  if (!supabase) {
    // Supabase 미연결 → 데모 모드
    return NextResponse.json({ ok: true, demo: true, slug })
  }

  const { data: store, error: storeErr } = await supabase
    .from('stores')
    .insert({ name, slug, description, type: type || '식자재', notification_email })
    .select('id, name, slug, description, type')
    .single()

  if (storeErr) {
    if (storeErr.code === '23505') {
      return NextResponse.json({ error: '이미 사용 중인 주소예요. 다른 주소를 입력해주세요.' }, { status: 409 })
    }
    console.error('Store insert error:', storeErr)
    return NextResponse.json({ error: '가게 생성에 실패했어요.' }, { status: 500 })
  }

  if (productRows.length > 0) {
    const { error: prodErr } = await supabase
      .from('products')
      .insert(productRows.map(p => ({ ...p, store_id: store.id })))
    if (prodErr) {
      console.error('Products insert error:', prodErr)
      return NextResponse.json({ ok: true, store, warning: '가게는 만들어졌지만 상품 저장에 실패했어요.' })
    }
  }

  return NextResponse.json({ ok: true, store })
}
