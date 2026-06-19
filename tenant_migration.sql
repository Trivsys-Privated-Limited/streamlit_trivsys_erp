-- Idempotent tenant migration to fix schema mismatches
-- 1) Ensure purchases.order_id exists
ALTER TABLE purchases
  ADD COLUMN IF NOT EXISTS `order_id` INT DEFAULT NULL;

-- 2) Ensure purchases.order_id FK to purchase_orders(id)
-- If the constraint doesn't exist, this block will add it. It checks information_schema.
SET @cnt = (
  SELECT COUNT(*)
  FROM information_schema.TABLE_CONSTRAINTS tc
  JOIN information_schema.KEY_COLUMN_USAGE ku ON ku.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
  WHERE tc.TABLE_SCHEMA = DATABASE()
    AND tc.TABLE_NAME = 'purchases'
    AND ku.COLUMN_NAME = 'order_id'
    AND tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
);

SELECT @cnt as existing_fk_for_order_id;

-- If no FK exists, add it
SET @s = NULL;
SET @s = IF(@cnt = 0, 'ALTER TABLE purchases ADD CONSTRAINT fk_purchases_order_id FOREIGN KEY (order_id) REFERENCES purchase_orders(id);', 'SELECT "fk_exists"');
PREPARE stmt FROM @s;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 3) Fix order_items foreign key to reference products(id)
-- Drop the existing FK on order_items that references products(product_id) if present
-- We detect the FK name and drop it safely
SET @fkname = (
  SELECT rc.CONSTRAINT_NAME
  FROM information_schema.REFERENTIAL_CONSTRAINTS rc
  JOIN information_schema.KEY_COLUMN_USAGE ku ON ku.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
  WHERE rc.CONSTRAINT_SCHEMA = DATABASE()
    AND ku.TABLE_NAME = 'order_items'
    AND ku.COLUMN_NAME = 'product_id'
    AND rc.REFERENCED_TABLE_NAME = 'products'
  LIMIT 1
);

SELECT @fkname as fk_to_drop;

SET @s = NULL;
SET @s = IF(@fkname IS NOT NULL, CONCAT('ALTER TABLE order_items DROP FOREIGN KEY `', @fkname, '`;'), 'SELECT "no_fk_to_drop"');
PREPARE stmt FROM @s;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Recreate the correct FK (if not present)
SET @cnt2 = (
  SELECT COUNT(*)
  FROM information_schema.TABLE_CONSTRAINTS tc
  JOIN information_schema.KEY_COLUMN_USAGE ku ON ku.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
  WHERE tc.TABLE_SCHEMA = DATABASE()
    AND tc.TABLE_NAME = 'order_items'
    AND ku.COLUMN_NAME = 'product_id'
    AND tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
);

SET @s = IF(@cnt2 = 0, 'ALTER TABLE order_items ADD CONSTRAINT fk_order_items_product_id FOREIGN KEY (product_id) REFERENCES products(id);', 'SELECT "fk_exists"');
PREPARE stmt FROM @s;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Optional: create tenant_sessions table if missing
CREATE TABLE IF NOT EXISTS tenant_sessions (
    token VARCHAR(128) PRIMARY KEY,
    session_data TEXT NOT NULL,
    browser_id VARCHAR(128) NOT NULL,
    expires DOUBLE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- End of migration
