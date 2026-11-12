import { getSupabaseAdmin } from '@/lib/supabase-server'
import { refreshSquareToken } from '@/lib/square'

const TABLE = 'store_square_credentials'
const REFRESH_WINDOW_MS = 7 * 24 * 60 * 60 * 1000 // 만료 7일 전부터 갱신

// Square 토큰은 공개 RLS 테이블(stores)에 두지 않고,
// 서비스 롤로만 읽을 수 있는 별도 테이블에 저장한다.
export async function saveSquareCredentials(storeId, token, location) {
  const admin = getSupabaseAdmin()
  if (!admin) throw new Error('SUPABASE_SERVICE_ROLE_KEY is not set')

  const connectedAt = new Date().toISOString()

  const { error } = await admin.from(TABLE).upsert({
    store_id: storeId,
    access_token: token.access_token,
    refresh_token: token.refresh_token ?? null,
    merchant_id: token.merchant_id ?? null,
    expires_at: token.expires_at ?? null,
    location_id: location.id,
    currency: location.currency || 'USD',
    connected_at: connectedAt,
  })
  if (error) throw error

  // 공개 테이블에는 "연결됨" 표시만 남긴다
  const { error: flagErr } = await admin
    .from('stores')
    .update({ square_connected_at: connectedAt })
    .eq('id', storeId)
  if (flagErr) throw flagErr
}

// 주문 전송용 인증 정보 조회. 연결 안 됐거나 서버 키가 없으면 null.
export async function getSquareCredentials(storeId) {
  const admin = getSupabaseAdmin()
  if (!admin) return null

  const { data: creds } = await admin.from(TABLE).select('*').eq('store_id', storeId).maybeSingle()
  if (!creds) return null

  let accessToken = creds.access_token
  const expiresSoon = creds.expires_at
    && new Date(creds.expires_at).getTime() - Date.now() < REFRESH_WINDOW_MS

  if (expiresSoon && creds.refresh_token) {
    try {
      const token = await refreshSquareToken(creds.refresh_token)
      accessToken = token.access_token
      await admin.from(TABLE).update({
        access_token: token.access_token,
        refresh_token: token.refresh_token ?? creds.refresh_token,
        expires_at: token.expires_at ?? null,
      }).eq('store_id', storeId)
    } catch (e) {
      console.error('Square token refresh error:', e)
    }
  }

  return { accessToken, locationId: creds.location_id, currency: creds.currency }
}
