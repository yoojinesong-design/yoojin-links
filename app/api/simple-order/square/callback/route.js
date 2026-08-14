import { NextResponse } from 'next/server'
import { getSupabaseServer } from '../../../../../lib/supabase-server'
import { exchangeSquareToken, getSquareClient } from '../../../../../lib/square'

// GET /api/simple-order/square/callback?code=xxx&state=store-slug
// Square OAuth 콜백 — 토큰 저장 + 대시보드로 리다이렉트
export async function GET(request) {
  const { searchParams } = new URL(request.url)
  const code = searchParams.get('code')
  const storeSlug = searchParams.get('state')
  const error = searchParams.get('error')

  // 사용자가 거부한 경우
  if (error) {
    return NextResponse.redirect(new URL(`/simple-order/dashboard?store=${storeSlug}&square=denied`, request.url))
  }

  if (!code || !storeSlug) {
    return NextResponse.redirect(new URL('/simple-order/dashboard?square=error', request.url))
  }

  try {
    // 1. 코드 → 토큰 교환
    const tokenData = await exchangeSquareToken(code)

    if (!tokenData.access_token) {
      throw new Error('토큰 교환 실패')
    }

    // 2. 가맹점 정보 + 위치(매장) 조회
    const client = getSquareClient(tokenData.access_token)

    // 첫 번째 location 가져오기
    const locationsRes = await client.locationsApi.listLocations()
    const locations = locationsRes.result.locations || []
    const location = locations[0]

    if (!location) {
      throw new Error('Square 매장 정보를 찾을 수 없어요')
    }

    // 3. Supabase에 토큰 저장
    const supabase = await getSupabaseServer()

    if (supabase) {
      await supabase
        .from('stores')
        .update({
          square_access_token: tokenData.access_token,
          square_refresh_token: tokenData.refresh_token,
          square_merchant_id: tokenData.merchant_id,
          square_location_id: location.id,
          square_connected_at: new Date().toISOString(),
        })
        .eq('slug', storeSlug)
    }

    // 4. 대시보드로 리다이렉트 (성공)
    return NextResponse.redirect(
      new URL(`/simple-order/dashboard?store=${storeSlug}&square=connected`, request.url)
    )
  } catch (err) {
    console.error('Square OAuth error:', err)
    return NextResponse.redirect(
      new URL(`/simple-order/dashboard?store=${storeSlug}&square=error`, request.url)
    )
  }
}
