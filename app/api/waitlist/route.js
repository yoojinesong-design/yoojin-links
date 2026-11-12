import { NextResponse } from 'next/server'
import { getSupabaseServer } from '@/lib/supabase-server'

const PRODUCTS = ['detailbook', 'persona-hub', 'gage-doumi', 'simple-order']
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export async function POST(request) {
  const body = await request.json().catch(() => null)
  const email = String(body?.email || '').trim().toLowerCase()
  const product = body?.product

  if (!EMAIL_RE.test(email) || email.length > 254) {
    return NextResponse.json({ error: 'Valid email required' }, { status: 400 })
  }
  if (!PRODUCTS.includes(product)) {
    return NextResponse.json({ error: 'Unknown product' }, { status: 400 })
  }

  const supabase = await getSupabaseServer()

  if (!supabase) {
    return NextResponse.json({ ok: true, demo: true })
  }

  // waitlist는 insert만 허용(RLS)하므로 upsert 대신 insert를 쓰고,
  // 이미 등록된 이메일(unique 위반)은 성공으로 처리한다.
  const { error } = await supabase.from('waitlist').insert({ email, product })

  if (error && error.code !== '23505') {
    console.error('Waitlist insert error:', error)
    return NextResponse.json({ error: 'Could not save. Try again.' }, { status: 500 })
  }

  return NextResponse.json({ ok: true })
}
