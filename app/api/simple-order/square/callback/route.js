import { NextResponse } from 'next/server'
import { getSupabaseServer } from '@/lib/supabase-server'
import { exchangeSquareToken, getPrimaryLocation } from '@/lib/square'
import { saveSquareCredentials } from '@/lib/square-credentials'

// GET /api/simple-order/square/callback?code=xxx&state=store-slug
// Square OAuth 콜백 — 토큰 저장 + 대시보드로 리다이렉트
export async function GET(request) {
  const { searchParams } = new URL(request.url)
  const code = searchParams.get('code')
  const storeSlug = searchParams.get('state')

  const backToDashboard = (result) => {
    const url = new URL('/simple-order/dashboard', request.url)
    if (storeSlug) url.searchParams.set('store', storeSlug)
    url.searchParams.set('square', result)
    return NextResponse.redirect(url)
  }

  // 사용자가 거부한 경우
  if (searchParams.get('error')) return backToDashboard('denied')
  if (!code || !storeSlug) return backToDashboard('error')

  try {
    const supabase = await getSupabaseServer()
    const { data: store } = supabase
      ? await supabase.from('stores').select('id').eq('slug', storeSlug).single()
      : { data: null }
    if (!store) throw new Error(`Store not found: ${storeSlug}`)

    const token = await exchangeSquareToken(code)

    const location = await getPrimaryLocation(token.access_token)
    if (!location) throw new Error('No Square location on this account')

    await saveSquareCredentials(store.id, token, location)

    return backToDashboard('connected')
  } catch (err) {
    console.error('Square OAuth error:', err)
    return backToDashboard('error')
  }
}
