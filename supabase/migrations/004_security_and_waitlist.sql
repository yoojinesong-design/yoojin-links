-- 004: Square 토큰 비공개화 + waitlist에 simple-order 추가
-- Supabase SQL Editor에서 실행하세요 (002, 003 실행 후)

-- 1. waitlist: simple-order 랜딩의 신청도 저장되도록 허용
ALTER TABLE public.waitlist DROP CONSTRAINT IF EXISTS waitlist_product_check;
ALTER TABLE public.waitlist ADD CONSTRAINT waitlist_product_check
  CHECK (product IN ('detailbook', 'persona-hub', 'gage-doumi', 'simple-order'));

-- 2. Square 인증 정보를 서버 전용 테이블로 분리
--    stores 테이블은 누구나 읽을 수 있어서(stores_public_read) 토큰을 두면 안 됨.
--    이 테이블은 RLS만 켜고 정책을 만들지 않으므로 서비스 롤 키로만 접근 가능.
CREATE TABLE IF NOT EXISTS store_square_credentials (
  store_id UUID PRIMARY KEY REFERENCES stores(id) ON DELETE CASCADE,
  access_token TEXT NOT NULL,
  refresh_token TEXT,
  merchant_id TEXT,
  location_id TEXT NOT NULL,
  currency TEXT NOT NULL DEFAULT 'USD',
  expires_at TIMESTAMPTZ,
  connected_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE store_square_credentials ENABLE ROW LEVEL SECURITY;

-- 3. 기존에 stores에 저장된 토큰이 있으면 옮기기
INSERT INTO store_square_credentials (store_id, access_token, refresh_token, merchant_id, location_id, connected_at)
SELECT id, square_access_token, square_refresh_token, square_merchant_id, square_location_id,
       COALESCE(square_connected_at, now())
FROM stores
WHERE square_access_token IS NOT NULL AND square_location_id IS NOT NULL
ON CONFLICT (store_id) DO NOTHING;

-- 4. 공개 테이블에서 비밀 값 제거 (square_connected_at은 "연결됨" 표시용으로 유지)
ALTER TABLE stores DROP COLUMN IF EXISTS square_access_token;
ALTER TABLE stores DROP COLUMN IF EXISTS square_refresh_token;
ALTER TABLE stores DROP COLUMN IF EXISTS square_merchant_id;
ALTER TABLE stores DROP COLUMN IF EXISTS square_location_id;
