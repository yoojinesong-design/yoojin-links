-- Square POS 연동 필드 추가
-- Supabase SQL Editor에서 실행하세요

-- stores 테이블에 Square 인증 정보 컬럼 추가
ALTER TABLE stores ADD COLUMN IF NOT EXISTS square_access_token TEXT;
ALTER TABLE stores ADD COLUMN IF NOT EXISTS square_refresh_token TEXT;
ALTER TABLE stores ADD COLUMN IF NOT EXISTS square_merchant_id TEXT;
ALTER TABLE stores ADD COLUMN IF NOT EXISTS square_location_id TEXT;
ALTER TABLE stores ADD COLUMN IF NOT EXISTS square_connected_at TIMESTAMPTZ;

-- orders 테이블에 Square 주문 ID 컬럼 추가
ALTER TABLE orders ADD COLUMN IF NOT EXISTS square_order_id TEXT;
