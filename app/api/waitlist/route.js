import { NextResponse } from 'next/server'
import { getSupabaseServer } from '../../../lib/supabase-server'

export async function POST(request) {
  const { email, product } = await request.json()

  if (!email || !email.includes('@')) {
    return NextResponse.json({ error: 'Valid email required' }, { status: 400 })
  }

  const supabase = await getSupabaseServer()

  if (!supabase) {
    return NextResponse.json({ ok: true, demo: true })
  }

  const { error } = await supabase
    .from('waitlist')
    .upsert({ email, product: product || 'persona-hub' }, { onConflict: 'email,product' })

  if (error) {
    return NextResponse.json({ error: 'Could not save. Try again.' }, { status: 500 })
  }

  return NextResponse.json({ ok: true })
}
