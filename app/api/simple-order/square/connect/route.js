import { NextResponse } from 'next/server'
import { getSquareAuthUrl } from '../../../../../lib/square'

// GET /api/simple-order/square/connect?store=slug
// → Square OAuth 페이지로 리다이렉트
export async function GET(request) {
  const { searchParams } = new URL(request.url)
  const storeSlug = searchParams.get('store')

  if (!storeSlug) {
    return NextResponse.json({ error: 'store 파라미터가 필요합니다.' }, { status: 400 })
  }

  if (!process.env.SQUARE_APP_ID) {
    return NextResponse.json({
      error: 'Square 앱이 설정되지 않았어요. SQUARE_APP_ID 환경변수를 설정해주세요.',
      setup_guide: 'https://developer.squareup.com/apps',
    }, { status: 503 })
  }

  const authUrl = getSquareAuthUrl(storeSlug)
  return NextResponse.redirect(authUrl)
}
