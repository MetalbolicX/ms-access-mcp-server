-- ============================================================
-- Small Store Data Model (Access ANSI-92 SQL)
--
-- Target: db/postgres.accdb
-- Naming: snake_case, plural tables, singular-prefixed fields
--
-- All constraints are inline at the end of each CREATE TABLE
-- following the standard Access pattern:
--   PRIMARY KEY (...)
--   FOREIGN KEY (...) REFERENCES ... ON UPDATE CASCADE
--   CONSTRAINT ... CHECK (...)
--
-- Execute via MCP server:
--   connect_access(database_path="db/postgres.accdb", use_com=True)
--   execute_sql_script(script_path="db/create-store-tables.sql")
-- ============================================================

-- ============================================================
-- TABLES
-- ============================================================

CREATE TABLE categories (
    category_id          AUTOINCREMENT,
    category_name       VARCHAR(100)    NOT NULL,
    category_description VARCHAR(255),
    PRIMARY KEY (category_id)
);

CREATE TABLE products (
    product_id          AUTOINCREMENT,
    product_category_id INTEGER         NOT NULL,
    product_name        VARCHAR(150)    NOT NULL,
    product_sku         VARCHAR(30)     NOT NULL,
    product_price       CURRENCY        NOT NULL,
    product_stock       INTEGER         NOT NULL DEFAULT 0,
    product_created_at  DATETIME        NOT NULL DEFAULT NOW(),
    PRIMARY KEY (product_id),
    FOREIGN KEY (product_category_id) REFERENCES categories (category_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE customers (
    customer_id         AUTOINCREMENT,
    customer_name       VARCHAR(100)    NOT NULL,
    customer_email      VARCHAR(150),
    customer_phone      VARCHAR(30),
    customer_created_at DATETIME        NOT NULL DEFAULT NOW(),
    PRIMARY KEY (customer_id)
);

CREATE TABLE orders (
    order_id            AUTOINCREMENT,
    order_customer_id   INTEGER         NOT NULL,
    order_date          DATETIME        NOT NULL DEFAULT NOW(),
    order_status        VARCHAR(20)     NOT NULL DEFAULT 'pending',
    order_total         CURRENCY,
    PRIMARY KEY (order_id),
    FOREIGN KEY (order_customer_id) REFERENCES customers (customer_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE order_items (
    order_item_id           AUTOINCREMENT,
    order_item_order_id     INTEGER         NOT NULL,
    order_item_product_id   INTEGER         NOT NULL,
    order_item_quantity     INTEGER         NOT NULL,
    order_item_unit_price   CURRENCY        NOT NULL,
    PRIMARY KEY (order_item_id),
    FOREIGN KEY (order_item_order_id) REFERENCES orders (order_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (order_item_product_id) REFERENCES products (product_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- ============================================================
-- SAMPLE DATA
-- ============================================================

INSERT INTO categories (category_name, category_description)
VALUES ('Electronics', 'Gadgets, devices, and accessories');
INSERT INTO categories (category_name, category_description)
VALUES ('Clothing', 'Apparel and fashion items');
INSERT INTO categories (category_name, category_description)
VALUES ('Books', 'Physical and digital books');

INSERT INTO products
    (product_category_id, product_name, product_sku,
     product_price, product_stock, product_created_at)
VALUES (1, 'Wireless Mouse',       'ELE-MOU-001', 25.99, 150, NOW());
INSERT INTO products
    (product_category_id, product_name, product_sku,
     product_price, product_stock, product_created_at)
VALUES (1, 'USB-C Hub',            'ELE-HUB-002', 45.50, 80, NOW());
INSERT INTO products
    (product_category_id, product_name, product_sku,
     product_price, product_stock, product_created_at)
VALUES (1, 'Bluetooth Speaker',    'ELE-SPK-003', 79.99, 40, NOW());
INSERT INTO products
    (product_category_id, product_name, product_sku,
     product_price, product_stock, product_created_at)
VALUES (2, 'Cotton T-Shirt',       'CLO-TSH-001', 19.99, 200, NOW());
INSERT INTO products
    (product_category_id, product_name, product_sku,
     product_price, product_stock, product_created_at)
VALUES (2, 'Denim Jacket',         'CLO-JCK-002', 89.99, 35, NOW());
INSERT INTO products
    (product_category_id, product_name, product_sku,
     product_price, product_stock, product_created_at)
VALUES (3, 'Clean Code',           'BOK-CLN-001', 42.00, 60, NOW());
INSERT INTO products
    (product_category_id, product_name, product_sku,
     product_price, product_stock, product_created_at)
VALUES (3, 'Pragmatic Programmer', 'BOK-PRG-002', 38.50, 45, NOW());

INSERT INTO customers (customer_name, customer_email, customer_phone, customer_created_at)
VALUES ('Alice Johnson', 'alice@email.com', '555-0101', NOW());
INSERT INTO customers (customer_name, customer_email, customer_phone, customer_created_at)
VALUES ('Bob Martinez', 'bob@email.com', '555-0102', NOW());
INSERT INTO customers (customer_name, customer_email, customer_phone, customer_created_at)
VALUES ('Carol Chen', 'carol@email.com', '555-0103', NOW());
INSERT INTO customers (customer_name, customer_email, customer_phone, customer_created_at)
VALUES ('David Silva', 'david@email.com', '555-0104', NOW());

INSERT INTO orders (order_customer_id, order_date, order_status, order_total)
VALUES (1, NOW(), 'shipped', 71.49);
INSERT INTO orders (order_customer_id, order_date, order_status, order_total)
VALUES (2, NOW(), 'pending', 89.99);
INSERT INTO orders (order_customer_id, order_date, order_status, order_total)
VALUES (3, NOW(), 'delivered', 42.00);
INSERT INTO orders (order_customer_id, order_date, order_status, order_total)
VALUES (4, NOW(), 'pending', 110.48);

INSERT INTO order_items
    (order_item_order_id, order_item_product_id,
     order_item_quantity, order_item_unit_price)
VALUES (1, 1, 1, 25.99);
INSERT INTO order_items
    (order_item_order_id, order_item_product_id,
     order_item_quantity, order_item_unit_price)
VALUES (1, 3, 1, 45.50);
INSERT INTO order_items
    (order_item_order_id, order_item_product_id,
     order_item_quantity, order_item_unit_price)
VALUES (2, 5, 1, 89.99);
INSERT INTO order_items
    (order_item_order_id, order_item_product_id,
     order_item_quantity, order_item_unit_price)
VALUES (3, 6, 1, 42.00);
INSERT INTO order_items
    (order_item_order_id, order_item_product_id,
     order_item_quantity, order_item_unit_price)
VALUES (4, 2, 2, 45.50);
INSERT INTO order_items
    (order_item_order_id, order_item_product_id,
     order_item_quantity, order_item_unit_price)
VALUES (4, 4, 1, 19.99);
