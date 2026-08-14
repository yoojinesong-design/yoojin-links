-- SimpleOrder 테이블
-- Supabase SQL Editor에서 실행하세요

-- 1. 가게
CREATE TABLE IF NOT EXISTS stores (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  type TEXT DEFAULT '식자재',
  notification_email TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 2. 상품
CREATE TABLE IF NOT EXISTS products (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  store_id UUID REFERENCES stores(id) ON DELETE CASCADE NOT NULL,
  name TEXT NOT NULL,
  price INTEGER NOT NULL,
  unit TEXT,
  category TEXT DEFAULT '기타',
  emoji TEXT DEFAULT '📦',
  sort_order INTEGER DEFAULT 0,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 3. 주문
CREATE TABLE IF NOT EXISTS orders (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  store_id UUID REFERENCES stores(id) NOT NULL,
  order_number TEXT NOT NULL,
  customer_name TEXT NOT NULL,
  customer_contact TEXT NOT NULL,
  customer_note TEXT,
  items JSONB NOT NULL DEFAULT '[]',
  total INTEGER NOT NULL DEFAULT 0,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending','confirmed','delivered','cancelled')),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_stores_slug ON stores(slug);
CREATE INDEX IF NOT EXISTS idx_products_store ON products(store_id);
CREATE INDEX IF NOT EXISTS idx_orders_store ON orders(store_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at DESC);

-- RLS (Row Level Security) - 공개 접근 허용 (인증 없이 사용)
ALTER TABLE stores ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

-- 누구나 읽기/쓰기 가능 (MVP 단계)
CREATE POLICY "stores_public_read" ON stores FOR SELECT USING (true);
CREATE POLICY "stores_public_insert" ON stores FOR INSERT WITH CHECK (true);
CREATE POLICY "stores_public_update" ON stores FOR UPDATE USING (true);

CREATE POLICY "products_public_read" ON products FOR SELECT USING (true);
CREATE POLICY "products_public_insert" ON products FOR INSERT WITH CHECK (true);
CREATE POLICY "products_public_update" ON products FOR UPDATE USING (true);

CREATE POLICY "orders_public_read" ON orders FOR SELECT USING (true);
CREATE POLICY "orders_public_insert" ON orders FOR INSERT WITH CHECK (true);
CREATE POLICY "orders_public_update" ON orders FOR UPDATE USING (true);
