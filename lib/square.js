import { Client, Environment } from 'square'

// Square 클라이언트 생성 (가게별 access token 사용)
export function getSquareClient(accessToken) {
  return new Client({
    accessToken,
    environment: process.env.SQUARE_ENVIRONMENT === 'production'
      ? Environment.Production
      : Environment.Sandbox,
  })
}

// Square OAuth URL 생성
export function getSquareAuthUrl(storeSlug) {
  const appId = process.env.SQUARE_APP_ID
  const baseUrl = process.env.SQUARE_ENVIRONMENT === 'production'
    ? 'https://connect.squareup.com'
    : 'https://connect.squareupsandbox.com'

  const redirectUri = `${process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000'}/api/simple-order/square/callback`

  const scopes = [
    'ORDERS_WRITE',
    'ORDERS_READ',
    'MERCHANT_PROFILE_READ',
    'ITEMS_READ',
  ].join('+')

  return `${baseUrl}/oauth2/authorize?client_id=${appId}&scope=${scopes}&state=${storeSlug}&redirect_uri=${encodeURIComponent(redirectUri)}`
}

// SimpleOrder 주문 → Square 주문 생성
export async function createSquareOrder(accessToken, locationId, order) {
  const client = getSquareClient(accessToken)

  const lineItems = order.items.map(item => ({
    name: item.name,
    quantity: String(item.qty),
    basePriceMoney: {
      amount: BigInt(item.price),
      currency: 'KRW',
    },
  }))

  const result = await client.ordersApi.createOrder({
    order: {
      locationId,
      lineItems,
      fulfillments: [{
        type: 'PICKUP',
        state: 'PROPOSED',
        pickupDetails: {
          recipient: {
            displayName: order.customer_name,
            phoneNumber: order.customer_contact,
          },
          note: order.customer_note || '',
          scheduleType: 'ASAP',
        },
      }],
      metadata: {
        simpleorder_id: order.id || '',
        simpleorder_number: order.order_number || '',
      },
    },
    idempotencyKey: `so-${order.order_number}-${Date.now()}`,
  })

  return result.result.order
}

// Square OAuth 토큰 교환
export async function exchangeSquareToken(code) {
  const baseUrl = process.env.SQUARE_ENVIRONMENT === 'production'
    ? 'https://connect.squareup.com'
    : 'https://connect.squareupsandbox.com'

  const res = await fetch(`${baseUrl}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      client_id: process.env.SQUARE_APP_ID,
      client_secret: process.env.SQUARE_APP_SECRET,
      code,
      grant_type: 'authorization_code',
    }),
  })

  return res.json()
}
