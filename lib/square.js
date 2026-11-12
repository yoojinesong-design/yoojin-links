import { SquareClient, SquareEnvironment } from 'square'

const isProduction = () => process.env.SQUARE_ENVIRONMENT === 'production'
const oauthBaseUrl = () => (isProduction() ? SquareEnvironment.Production : SquareEnvironment.Sandbox)
const siteUrl = () => process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000'

// Square가 지원하는 통화 중 소수점 단위가 없는 통화 (금액을 그대로 전달)
const ZERO_DECIMAL_CURRENCIES = new Set(['JPY'])

export function isSquareConfigured() {
  return Boolean(process.env.SQUARE_APP_ID && process.env.SQUARE_APP_SECRET)
}

// Square 클라이언트 생성 (가게별 access token 사용)
export function getSquareClient(accessToken) {
  return new SquareClient({ token: accessToken, environment: oauthBaseUrl() })
}

// Square OAuth URL 생성
export function getSquareAuthUrl(storeSlug) {
  const params = new URLSearchParams({
    client_id: process.env.SQUARE_APP_ID,
    scope: 'ORDERS_WRITE ORDERS_READ MERCHANT_PROFILE_READ',
    state: storeSlug,
    redirect_uri: `${siteUrl()}/api/simple-order/square/callback`,
  })
  return `${oauthBaseUrl()}/oauth2/authorize?${params}`
}

async function requestToken(body) {
  const res = await fetch(`${oauthBaseUrl()}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      client_id: process.env.SQUARE_APP_ID,
      client_secret: process.env.SQUARE_APP_SECRET,
      ...body,
    }),
  })
  const data = await res.json()
  if (!res.ok || !data.access_token) {
    throw new Error(`Square token request failed (${res.status})`)
  }
  return data
}

// Square OAuth 코드 → 토큰 교환
export function exchangeSquareToken(code) {
  return requestToken({ code, grant_type: 'authorization_code' })
}

// 만료 전 토큰 갱신 (Square access token은 30일 후 만료)
export function refreshSquareToken(refreshToken) {
  return requestToken({ refresh_token: refreshToken, grant_type: 'refresh_token' })
}

// 가맹점의 첫 번째 매장(location) 조회
export async function getPrimaryLocation(accessToken) {
  const { locations = [] } = await getSquareClient(accessToken).locations.list()
  return locations.find(l => l.status === 'ACTIVE') || locations[0] || null
}

// SimpleOrder 주문 → Square 주문 생성
// item.price는 매장 통화의 기본 단위(예: 달러, 엔)로 저장된 정수
export async function createSquareOrder({ accessToken, locationId, currency }, order) {
  const minorUnits = ZERO_DECIMAL_CURRENCIES.has(currency) ? 1 : 100

  const note = [`연락처: ${order.customer_contact}`, order.customer_note]
    .filter(Boolean)
    .join(' / ')
    .slice(0, 500)

  const { order: created } = await getSquareClient(accessToken).orders.create({
    idempotencyKey: `simpleorder-${order.id}`,
    order: {
      locationId,
      referenceId: order.order_number,
      lineItems: order.items.map(item => ({
        name: item.name,
        quantity: String(item.qty),
        basePriceMoney: { amount: BigInt(item.price * minorUnits), currency },
      })),
      fulfillments: [{
        type: 'PICKUP',
        state: 'PROPOSED',
        pickupDetails: {
          recipient: { displayName: order.customer_name },
          note,
          scheduleType: 'ASAP',
        },
      }],
      metadata: { simpleorder_id: String(order.id) },
    },
  })

  return created
}
