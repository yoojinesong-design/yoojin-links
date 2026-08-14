import { NextResponse } from 'next/server'
import { getSupabaseServer } from '../../../../../lib/supabase-server'

// GET /api/simple-order/stores/[slug] — 가게 + 상품 조회
export async function GET(request, { params }) {
  const { slug } = await params

  const supabase = await getSupabaseServer()

  if (!supabase) {
    return NextResponse.json({ error: 'DB 미연결', demo: true }, { status: 503 })
  }

  // 가게 조회
  const { data: store, error: storeErr } = await supabase
    .from('stores')
    .select('*')
    .eq('slug', slug)
    .single()

  if (storeErr || !store) {
    return NextResponse.json({ error: '가게를 찾을 수 없어요.' }, { status: 404 })
  }

  // 상품 조회
  const { data: products } = await supabase
    .from('products')
    .select('*')
    .eq('store_id', store.id)
    .eq('active', true)
    .order('sort_order', { ascending: true })

  return NextResponse.json({
    store: {
      id: store.id,
      name: store.name,
      slug: store.slug,
      description: store.description,
      type: store.type,
    },
    products: (products || []).map(p => ({
      id: p.id,
      name: p.name,
      price: p.price,
      unit: p.unit,
      category: p.category,
      emoji: p.emoji,
    })),
  })
}
