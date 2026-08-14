import { NextResponse } from 'next/server'
import { getSupabaseServer } from '../../../../lib/supabase-server'

// POST /api/simple-order/stores — 가게 생성 + 상품 등록
export async function POST(request) {
  const body = await request.json()
  const { name, slug, description, type, notification_email, products } = body

  if (!name || !slug) {
    return NextResponse.json({ error: '가게 이름과 주소가 필요합니다.' }, { status: 400 })
  }

  const supabase = await getSupabaseServer()

  if (!supabase) {
    // Supabase 미연결 → 데모 모드
    return NextResponse.json({ ok: true, demo: true, slug })
  }

  // 1. 가게 생성
  const { data: store, error: storeErr } = await supabase
    .from('stores')
    .insert({ name, slug, description, type: type || '식자재', notification_email })
    .select()
    .single()

  if (storeErr) {
    if (storeErr.code === '23505') {
      return NextResponse.json({ error: '이미 사용 중인 주소예요. 다른 주소를 입력해주세요.' }, { status: 409 })
    }
    return NextResponse.json({ error: '가게 생성에 실패했어요.' }, { status: 500 })
  }

  // 2. 상품 등록
  if (products && products.length > 0) {
    const productRows = products.map((p, i) => ({
      store_id: store.id,
      name: p.name,
      price: p.price,
      unit: p.unit || '',
      category: p.category || '기타',
      emoji: p.emoji || '📦',
      sort_order: i,
    }))

    const { error: prodErr } = await supabase.from('products').insert(productRows)
    if (prodErr) {
      console.error('Products insert error:', prodErr)
    }
  }

  return NextResponse.json({ ok: true, store })
}
