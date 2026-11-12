import { NextResponse } from 'next/server'
import { getSquareAuthUrl, isSquareConfigured } from '@/lib/square'
import { getSupabaseAdmin } from '@/lib/supabase-server'

// GET /api/simple-order/square/connect?store=slug
// → Square OAuth 페이지로 리다이렉트
export async function GET(request) {
  const { searchParams } = new URL(request.url)
  const storeSlug = searchParams.get('store')

  if (!storeSlug) {
    return NextResponse.json({ error: 'store 파라미터가 필요합니다.' }, { status: 400 })
  }

  if (!isSquareConfigured() || !getSupabaseAdmin()) {
    return NextResponse.json({
      error: 'Square 연동이 아직 설정되지 않았어요. SQUARE_APP_ID, SQUARE_APP_SECRET, SUPABASE_SERVICE_ROLE_KEY 환경변수가 필요합니다.',
      setup_guide: 'https://developer.squareup.com/apps',
    }, { status: 503 })
  }

  return NextResponse.redirect(getSquareAuthUrl(storeSlug))
}
