-- Run this in your Supabase SQL editor to set up the ShopSmart schema.

-- price_snapshots: one row every time a user views a product — builds real price history over time
CREATE TABLE IF NOT EXISTS price_snapshots (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  product_key TEXT        NOT NULL,   -- normalized lowercase title, max 200 chars
  seller_name TEXT        NOT NULL,
  source      TEXT        NOT NULL,
  price       NUMERIC(10,2) NOT NULL,
  recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- fast lookup by product + time — this is the main query pattern for price history
CREATE INDEX IF NOT EXISTS idx_snapshots_product_time
  ON price_snapshots (product_key, recorded_at DESC);

-- price_alerts: stored when a user sets a drop alert via the product page
CREATE TABLE IF NOT EXISTS price_alerts (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  email         TEXT        NOT NULL,
  product_title TEXT        NOT NULL,
  seller        TEXT        NOT NULL,
  current_price NUMERIC(10,2),
  target_price  NUMERIC(10,2) NOT NULL,
  is_triggered  BOOLEAN     DEFAULT FALSE,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- for scheduled jobs that check which alerts to fire
CREATE INDEX IF NOT EXISTS idx_alerts_pending
  ON price_alerts (is_triggered, target_price)
  WHERE is_triggered = FALSE;
