import { NextResponse } from 'next/server'
import { getSupabaseServer } from '../../../../../lib/supabase-server'

// PATCH /api/simple-order/orders/[id] — 주문 상태 변경
export async function PATCH(request, { params }) {
  const { id } = await params
  const { status } = await request.json()

  const validStatuses = ['pending', 'confirmed', 'delivered', 'cancelled']
  if (!validStatuses.includes(status)) {
    return NextResponse.json({ error: '올바른 상태가 아닙니다.' }, { status: 400 })
  }

  const supabase = await getSupabaseServer()

  if (!supabase) {
    return NextResponse.json({ ok: true, demo: true })
  }

  const { data, error } = await supabase
    .from('orders')
    .update({ status })
    .eq('id', id)
    .select()
    .single()

  if (error) {
    return NextResponse.json({ error: '상태 변경에 실패했어요.' }, { status: 500 })
  }

  return NextResponse.json({ ok: true, order: data })
}
