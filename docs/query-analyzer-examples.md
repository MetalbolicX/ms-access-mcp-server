# Query Analyzer — Live Examples on `postgres.accdb`

**Generated:** 2026-06-05
**Connection:** COM (WinComAdapter) — full schema index analysis
**Mode:** `dry_run=false`, `sample_size=3`

---

## Summary

| # | Query | Complexity | Score | Duration | Rows | Anti-patterns |
|---|-------|------------|-------|----------|------|---------------|
| 1 | Simple SELECT — Baseline | simple | 0 | 32.5ms | 1 | — |
| 2 | Leading Wildcard LIKE — Anti-pattern | simple | 10 | 40.1ms | 0 | Wildcard |
| 3 | Aggregate with Unindexed WHERE — Missing Index | simple | 3 | 34.1ms | 1 | Agg |
| 4 | Single JOIN with Unindexed WHERE — Missing Index | simple | 10 | 33.2ms | 3 | JOIN(1) |
| 5 | Multi-JOIN with Unindexed Email — Complex | moderate | 30 | 1.9ms | 0 | JOIN(3) |
| 6 | Function in WHERE — Index Prevention | simple | 8 | 35.1ms | 4 | FuncWHERE |
| 7 | Subquery in WHERE — Moderate Complexity | moderate | 28 | 34.1ms | 1 | SubQ, FuncWHERE |
| 8 | NOT IN Subquery — Classic Anti-pattern | moderate | 31 | 32.3ms | 0 | SubQ, FuncWHERE, NOT IN |
| 9 | GROUP BY + HAVING + ORDER BY — Moderate | moderate | 21 | 4.6ms | 0 | JOIN(1), Agg, GROUP BY, ORDER BY |
| 10 | Cartesian Join — Heavy Anti-pattern | simple | 15 | 33.8ms | 21 | Cartesian |

---

## 1. Simple SELECT — Baseline

*PK lookup, no anti-patterns — should be clean.*

```sql
SELECT * FROM customers WHERE customer_id = 1
```

### Complexity

**Label:** simple  |  **Score:** 0/100

| Pattern | Detected |
|---------|----------|
| Joins | ✗ (0) |
| Subquery | ✗ |
| Correlated subquery | ✗ |
| DISTINCT | ✗ |
| ORDER BY | ✗ |
| GROUP BY | ✗ |
| Aggregate functions | ✗ |
| Function in WHERE | ✗ |
| Leading wildcard LIKE | ✗ |
| Cartesian join | ✗ |
| NOT IN | ✗ |
| OR condition | ✗ |
| UNION | ✗ |

### Execution

**Duration:** 32.54ms

**Rows (COUNT):** 1

**Sample rows:**

```json
[
  {
    "customer_id": 1,
    "customer_name": "Alice Johnson",
    "customer_email": "alice@email.com",
    "customer_phone": "555-0101",
    "customer_created_at": "2026-06-04T18:50:44+00:00"
  }
]
```

### Schema Analysis

**Tables analyzed:** 1
**Index info available:** ✓

| Table | Indexed columns |
|-------|-----------------|
| `customers` | customer_id |

### Recommendations

- No significant performance issues detected
- Query returns 1 rows from table(s) — consider pagination if too large

### Full Result

<details>
<summary>Click to expand JSON</summary>

```json
{
  "success": true,
  "query": "SELECT * FROM customers WHERE customer_id = 1",
  "execution": {
    "duration_ms": 32.54030000061903,
    "rows_total": 1,
    "sample_size": 3,
    "sampled_data": [
      {
        "customer_id": 1,
        "customer_name": "Alice Johnson",
        "customer_email": "alice@email.com",
        "customer_phone": "555-0101",
        "customer_created_at": "2026-06-04T18:50:44+00:00"
      }
    ],
    "error": null
  },
  "complexity": {
    "tables_involved": [
      "customers"
    ],
    "join_count": 0,
    "has_subquery": false,
    "has_correlated_subquery": false,
    "has_distinct": false,
    "has_order_by": false,
    "has_group_by": false,
    "has_aggregates": false,
    "has_where_function": false,
    "has_leading_wildcard_like": false,
    "has_cartesian_join": false,
    "has_not_in": false,
    "has_or_condition": false,
    "has_union": false,
    "score": 0,
    "complexity_label": "simple"
  },
  "schema_analysis": {
    "success": true,
    "table_count": 1,
    "indexed_columns": {
      "customers": [
        "customer_id"
      ]
    },
    "index_info_available": true
  },
  "recommendations": [
    "No significant performance issues detected",
    "Query returns 1 rows from table(s) \u2014 consider pagination if too large"
  ]
}
```

</details>

---

## 2. Leading Wildcard LIKE — Anti-pattern

*LIKE '%term' on an unindexed column — prevents index usage.*

```sql
SELECT * FROM products WHERE product_name LIKE '%Mouse%'
```

### Complexity

**Label:** simple  |  **Score:** 10/100

| Pattern | Detected |
|---------|----------|
| Joins | ✗ (0) |
| Subquery | ✗ |
| Correlated subquery | ✗ |
| DISTINCT | ✗ |
| ORDER BY | ✗ |
| GROUP BY | ✗ |
| Aggregate functions | ✗ |
| Function in WHERE | ✗ |
| Leading wildcard LIKE | ✓ |
| Cartesian join | ✗ |
| NOT IN | ✗ |
| OR condition | ✗ |
| UNION | ✗ |

### Execution

**Duration:** 40.12ms

**Rows (COUNT):** N/A

### Schema Analysis

**Tables analyzed:** 1
**Index info available:** ✓

| Table | Indexed columns |
|-------|-----------------|
| `products` | product_category_id, product_id |

### Recommendations

- Missing index on products.product_name — column used in WHERE/JOIN but not indexed
- LIKE with leading wildcard in WHERE clause prevents index usage on column(s)

### Full Result

<details>
<summary>Click to expand JSON</summary>

```json
{
  "success": true,
  "query": "SELECT * FROM products WHERE product_name LIKE '%Mouse%'",
  "execution": {
    "duration_ms": 40.12239999974554,
    "rows_total": 0,
    "sample_size": 3,
    "sampled_data": [],
    "error": null
  },
  "complexity": {
    "tables_involved": [
      "products"
    ],
    "join_count": 0,
    "has_subquery": false,
    "has_correlated_subquery": false,
    "has_distinct": false,
    "has_order_by": false,
    "has_group_by": false,
    "has_aggregates": false,
    "has_where_function": false,
    "has_leading_wildcard_like": true,
    "has_cartesian_join": false,
    "has_not_in": false,
    "has_or_condition": false,
    "has_union": false,
    "score": 10,
    "complexity_label": "simple"
  },
  "schema_analysis": {
    "success": true,
    "table_count": 1,
    "indexed_columns": {
      "products": [
        "product_id",
        "product_category_id"
      ]
    },
    "index_info_available": true
  },
  "recommendations": [
    "Missing index on products.product_name \u2014 column used in WHERE/JOIN but not indexed",
    "LIKE with leading wildcard in WHERE clause prevents index usage on column(s)"
  ]
}
```

</details>

---

## 3. Aggregate with Unindexed WHERE — Missing Index

*COUNT(*) on a filtered column that has no index.*

```sql
SELECT COUNT(*) AS n FROM orders WHERE order_status = 'shipped'
```

### Complexity

**Label:** simple  |  **Score:** 3/100

| Pattern | Detected |
|---------|----------|
| Joins | ✗ (0) |
| Subquery | ✗ |
| Correlated subquery | ✗ |
| DISTINCT | ✗ |
| ORDER BY | ✗ |
| GROUP BY | ✗ |
| Aggregate functions | ✓ |
| Function in WHERE | ✗ |
| Leading wildcard LIKE | ✗ |
| Cartesian join | ✗ |
| NOT IN | ✗ |
| OR condition | ✗ |
| UNION | ✗ |

### Execution

**Duration:** 34.14ms

**Rows (COUNT):** 1

**Sample rows:**

```json
[
  {
    "n": 1
  }
]
```

### Schema Analysis

**Tables analyzed:** 1
**Index info available:** ✓

| Table | Indexed columns |
|-------|-----------------|
| `orders` | order_customer_id, order_id |

### Recommendations

- Missing index on orders.order_status — column used in WHERE/JOIN but not indexed
- Query returns 1 rows from table(s) — consider pagination if too large

### Full Result

<details>
<summary>Click to expand JSON</summary>

```json
{
  "success": true,
  "query": "SELECT COUNT(*) AS n FROM orders WHERE order_status = 'shipped'",
  "execution": {
    "duration_ms": 34.14009999960399,
    "rows_total": 1,
    "sample_size": 3,
    "sampled_data": [
      {
        "n": 1
      }
    ],
    "error": null
  },
  "complexity": {
    "tables_involved": [
      "orders"
    ],
    "join_count": 0,
    "has_subquery": false,
    "has_correlated_subquery": false,
    "has_distinct": false,
    "has_order_by": false,
    "has_group_by": false,
    "has_aggregates": true,
    "has_where_function": false,
    "has_leading_wildcard_like": false,
    "has_cartesian_join": false,
    "has_not_in": false,
    "has_or_condition": false,
    "has_union": false,
    "score": 3,
    "complexity_label": "simple"
  },
  "schema_analysis": {
    "success": true,
    "table_count": 1,
    "indexed_columns": {
      "orders": [
        "order_id",
        "order_customer_id"
      ]
    },
    "index_info_available": true
  },
  "recommendations": [
    "Missing index on orders.order_status \u2014 column used in WHERE/JOIN but not indexed",
    "Query returns 1 rows from table(s) \u2014 consider pagination if too large"
  ]
}
```

</details>

---

## 4. Single JOIN with Unindexed WHERE — Missing Index

*One JOIN plus a filter on an unindexed column.*

```sql
SELECT c.customer_name, o.order_total FROM customers c INNER JOIN orders o ON c.customer_id = o.order_customer_id WHERE o.order_total > 50
```

### Complexity

**Label:** simple  |  **Score:** 10/100

| Pattern | Detected |
|---------|----------|
| Joins | ✓ (1) |
| Subquery | ✗ |
| Correlated subquery | ✗ |
| DISTINCT | ✗ |
| ORDER BY | ✗ |
| GROUP BY | ✗ |
| Aggregate functions | ✗ |
| Function in WHERE | ✗ |
| Leading wildcard LIKE | ✗ |
| Cartesian join | ✗ |
| NOT IN | ✗ |
| OR condition | ✗ |
| UNION | ✗ |

### Execution

**Duration:** 33.21ms

**Rows (COUNT):** 3

**Sample rows:**

```json
[
  {
    "customer_name": "Alice Johnson",
    "order_total": "71.49"
  },
  {
    "customer_name": "Bob Martinez",
    "order_total": "89.99"
  },
  {
    "customer_name": "David Silva",
    "order_total": "110.48"
  }
]
```

### Schema Analysis

**Tables analyzed:** 2
**Index info available:** ✓

| Table | Indexed columns |
|-------|-----------------|
| `customers` | customer_id |
| `orders` | order_customer_id, order_id |

### Recommendations

- Missing index on customers.order_total — column used in WHERE/JOIN but not indexed
- Missing index on orders.order_total — column used in WHERE/JOIN but not indexed
- Query returns 3 rows from table(s) — consider pagination if too large

### Full Result

<details>
<summary>Click to expand JSON</summary>

```json
{
  "success": true,
  "query": "SELECT c.customer_name, o.order_total FROM customers c INNER JOIN orders o ON c.customer_id = o.order_customer_id WHERE o.order_total > 50",
  "execution": {
    "duration_ms": 33.20510000048671,
    "rows_total": 3,
    "sample_size": 3,
    "sampled_data": [
      {
        "customer_name": "Alice Johnson",
        "order_total": "71.49"
      },
      {
        "customer_name": "Bob Martinez",
        "order_total": "89.99"
      },
      {
        "customer_name": "David Silva",
        "order_total": "110.48"
      }
    ],
    "error": null
  },
  "complexity": {
    "tables_involved": [
      "customers",
      "orders"
    ],
    "join_count": 1,
    "has_subquery": false,
    "has_correlated_subquery": false,
    "has_distinct": false,
    "has_order_by": false,
    "has_group_by": false,
    "has_aggregates": false,
    "has_where_function": false,
    "has_leading_wildcard_like": false,
    "has_cartesian_join": false,
    "has_not_in": false,
    "has_or_condition": false,
    "has_union": false,
    "score": 10,
    "complexity_label": "simple"
  },
  "schema_analysis": {
    "success": true,
    "table_count": 2,
    "indexed_columns": {
      "customers": [
        "customer_id"
      ],
      "orders": [
        "order_id",
        "order_customer_id"
      ]
    },
    "index_info_available": true
  },
  "recommendations": [
    "Missing index on customers.order_total \u2014 column used in WHERE/JOIN but not indexed",
    "Missing index on orders.order_total \u2014 column used in WHERE/JOIN but not indexed",
    "Query returns 3 rows from table(s) \u2014 consider pagination if too large"
  ]
}
```

</details>

---

## 5. Multi-JOIN with Unindexed Email — Complex

*3 JOINs across 4 tables with WHERE on unindexed customer_email.*

```sql
SELECT c.customer_name, p.product_name, oi.order_item_quantity FROM customers c INNER JOIN orders o ON c.customer_id = o.order_customer_id INNER JOIN order_items oi ON o.order_id = oi.order_item_order_id INNER JOIN products p ON oi.order_item_product_id = p.product_id WHERE c.customer_email = 'alice@email.com'
```

### Complexity

**Label:** moderate  |  **Score:** 30/100

| Pattern | Detected |
|---------|----------|
| Joins | ✓ (3) |
| Subquery | ✗ |
| Correlated subquery | ✗ |
| DISTINCT | ✗ |
| ORDER BY | ✗ |
| GROUP BY | ✗ |
| Aggregate functions | ✗ |
| Function in WHERE | ✗ |
| Leading wildcard LIKE | ✗ |
| Cartesian join | ✗ |
| NOT IN | ✗ |
| OR condition | ✗ |
| UNION | ✗ |

### Execution

**Duration:** 1.90ms

**Rows (COUNT):** N/A

### Schema Analysis

**Tables analyzed:** 4
**Index info available:** ✓

| Table | Indexed columns |
|-------|-----------------|
| `customers` | customer_id |
| `order_items` | order_item_id, order_item_order_id, order_item_product_id |
| `orders` | order_customer_id, order_id |
| `products` | product_category_id, product_id |

### Recommendations

- Missing index on customers.customer_email — column used in WHERE/JOIN but not indexed
- Missing index on orders.customer_email — column used in WHERE/JOIN but not indexed
- Missing index on order_items.customer_email — column used in WHERE/JOIN but not indexed
- Missing index on products.customer_email — column used in WHERE/JOIN but not indexed

### Full Result

<details>
<summary>Click to expand JSON</summary>

```json
{
  "success": true,
  "query": "SELECT c.customer_name, p.product_name, oi.order_item_quantity FROM customers c INNER JOIN orders o ON c.customer_id = o.order_customer_id INNER JOIN order_items oi ON o.order_id = oi.order_item_order_id INNER JOIN products p ON oi.order_item_product_id = p.product_id WHERE c.customer_email = 'alice@email.com'",
  "execution": {
    "duration_ms": 1.8982000001415145,
    "rows_total": 0,
    "sample_size": 3,
    "sampled_data": [],
    "error": null
  },
  "complexity": {
    "tables_involved": [
      "customers",
      "orders",
      "order_items",
      "products"
    ],
    "join_count": 3,
    "has_subquery": false,
    "has_correlated_subquery": false,
    "has_distinct": false,
    "has_order_by": false,
    "has_group_by": false,
    "has_aggregates": false,
    "has_where_function": false,
    "has_leading_wildcard_like": false,
    "has_cartesian_join": false,
    "has_not_in": false,
    "has_or_condition": false,
    "has_union": false,
    "score": 30,
    "complexity_label": "moderate"
  },
  "schema_analysis": {
    "success": true,
    "table_count": 4,
    "indexed_columns": {
      "customers": [
        "customer_id"
      ],
      "order_items": [
        "order_item_id",
        "order_item_order_id",
        "order_item_product_id"
      ],
      "orders": [
        "order_id",
        "order_customer_id"
      ],
      "products": [
        "product_id",
        "product_category_id"
      ]
    },
    "index_info_available": true
  },
  "recommendations": [
    "Missing index on customers.customer_email \u2014 column used in WHERE/JOIN but not indexed",
    "Missing index on orders.customer_email \u2014 column used in WHERE/JOIN but not indexed",
    "Missing index on order_items.customer_email \u2014 column used in WHERE/JOIN but not indexed",
    "Missing index on products.customer_email \u2014 column used in WHERE/JOIN but not indexed"
  ]
}
```

</details>

---

## 6. Function in WHERE — Index Prevention

*VBA YEAR() function in WHERE — function call prevents index usage.*

```sql
SELECT * FROM orders WHERE YEAR(order_date) = 2026
```

### Complexity

**Label:** simple  |  **Score:** 8/100

| Pattern | Detected |
|---------|----------|
| Joins | ✗ (0) |
| Subquery | ✗ |
| Correlated subquery | ✗ |
| DISTINCT | ✗ |
| ORDER BY | ✗ |
| GROUP BY | ✗ |
| Aggregate functions | ✗ |
| Function in WHERE | ✓ |
| Leading wildcard LIKE | ✗ |
| Cartesian join | ✗ |
| NOT IN | ✗ |
| OR condition | ✗ |
| UNION | ✗ |

### Execution

**Duration:** 35.06ms

**Rows (COUNT):** 4

**Sample rows:**

```json
[
  {
    "order_id": 1,
    "order_customer_id": 1,
    "order_date": "2026-06-04T18:50:44+00:00",
    "order_status": "shipped",
    "order_total": "71.49"
  },
  {
    "order_id": 2,
    "order_customer_id": 2,
    "order_date": "2026-06-04T18:50:44+00:00",
    "order_status": "pending",
    "order_total": "89.99"
  },
  {
    "order_id": 3,
    "order_customer_id": 3,
    "order_date": "2026-06-04T18:50:44+00:00",
    "order_status": "delivered",
    "order_total": "42"
  }
]
```

### Schema Analysis

**Tables analyzed:** 1
**Index info available:** ✓

| Table | Indexed columns |
|-------|-----------------|
| `orders` | order_customer_id, order_id |

### Recommendations

- Function YEAR() in WHERE clause prevents index usage on order_date
- Query returns 4 rows from table(s) — consider pagination if too large

### Full Result

<details>
<summary>Click to expand JSON</summary>

```json
{
  "success": true,
  "query": "SELECT * FROM orders WHERE YEAR(order_date) = 2026",
  "execution": {
    "duration_ms": 35.05609999956505,
    "rows_total": 4,
    "sample_size": 3,
    "sampled_data": [
      {
        "order_id": 1,
        "order_customer_id": 1,
        "order_date": "2026-06-04T18:50:44+00:00",
        "order_status": "shipped",
        "order_total": "71.49"
      },
      {
        "order_id": 2,
        "order_customer_id": 2,
        "order_date": "2026-06-04T18:50:44+00:00",
        "order_status": "pending",
        "order_total": "89.99"
      },
      {
        "order_id": 3,
        "order_customer_id": 3,
        "order_date": "2026-06-04T18:50:44+00:00",
        "order_status": "delivered",
        "order_total": "42"
      }
    ],
    "error": null
  },
  "complexity": {
    "tables_involved": [
      "orders"
    ],
    "join_count": 0,
    "has_subquery": false,
    "has_correlated_subquery": false,
    "has_distinct": false,
    "has_order_by": false,
    "has_group_by": false,
    "has_aggregates": false,
    "has_where_function": true,
    "has_leading_wildcard_like": false,
    "has_cartesian_join": false,
    "has_not_in": false,
    "has_or_condition": false,
    "has_union": false,
    "score": 8,
    "complexity_label": "simple"
  },
  "schema_analysis": {
    "success": true,
    "table_count": 1,
    "indexed_columns": {
      "orders": [
        "order_id",
        "order_customer_id"
      ]
    },
    "index_info_available": true
  },
  "recommendations": [
    "Function YEAR() in WHERE clause prevents index usage on order_date",
    "Query returns 4 rows from table(s) \u2014 consider pagination if too large"
  ]
}
```

</details>

---

## 7. Subquery in WHERE — Moderate Complexity

*IN (SELECT ...) nested subquery adds to score.*

```sql
SELECT product_name FROM products WHERE product_id IN (SELECT order_item_product_id FROM order_items WHERE order_item_quantity > 1)
```

### Complexity

**Label:** moderate  |  **Score:** 28/100

| Pattern | Detected |
|---------|----------|
| Joins | ✗ (0) |
| Subquery | ✓ |
| Correlated subquery | ✓ |
| DISTINCT | ✗ |
| ORDER BY | ✗ |
| GROUP BY | ✗ |
| Aggregate functions | ✗ |
| Function in WHERE | ✓ |
| Leading wildcard LIKE | ✗ |
| Cartesian join | ✗ |
| NOT IN | ✗ |
| OR condition | ✗ |
| UNION | ✗ |

### Execution

**Duration:** 34.07ms

**Rows (COUNT):** 1

**Sample rows:**

```json
[
  {
    "product_name": "USB-C Hub"
  }
]
```

### Schema Analysis

**Tables analyzed:** 2
**Index info available:** ✓

| Table | Indexed columns |
|-------|-----------------|
| `order_items` | order_item_id, order_item_order_id, order_item_product_id |
| `products` | product_category_id, product_id |

### Recommendations

- Missing index on products.SELECT — column used in WHERE/JOIN but not indexed
- Missing index on order_items.product_id — column used in WHERE/JOIN but not indexed
- Correlated subquery detected — consider rewriting as JOIN for better performance
- Function in WHERE clause prevents index usage on column(s)
- Query returns 1 rows from table(s) — consider pagination if too large

### Full Result

<details>
<summary>Click to expand JSON</summary>

```json
{
  "success": true,
  "query": "SELECT product_name FROM products WHERE product_id IN (SELECT order_item_product_id FROM order_items WHERE order_item_quantity > 1)",
  "execution": {
    "duration_ms": 34.06930000073771,
    "rows_total": 1,
    "sample_size": 3,
    "sampled_data": [
      {
        "product_name": "USB-C Hub"
      }
    ],
    "error": null
  },
  "complexity": {
    "tables_involved": [
      "products",
      "order_items"
    ],
    "join_count": 0,
    "has_subquery": true,
    "has_correlated_subquery": true,
    "has_distinct": false,
    "has_order_by": false,
    "has_group_by": false,
    "has_aggregates": false,
    "has_where_function": true,
    "has_leading_wildcard_like": false,
    "has_cartesian_join": false,
    "has_not_in": false,
    "has_or_condition": false,
    "has_union": false,
    "score": 28,
    "complexity_label": "moderate"
  },
  "schema_analysis": {
    "success": true,
    "table_count": 2,
    "indexed_columns": {
      "order_items": [
        "order_item_id",
        "order_item_order_id",
        "order_item_product_id"
      ],
      "products": [
        "product_id",
        "product_category_id"
      ]
    },
    "index_info_available": true
  },
  "recommendations": [
    "Missing index on products.SELECT \u2014 column used in WHERE/JOIN but not indexed",
    "Missing index on order_items.product_id \u2014 column used in WHERE/JOIN but not indexed",
    "Correlated subquery detected \u2014 consider rewriting as JOIN for better performance",
    "Function in WHERE clause prevents index usage on column(s)",
    "Query returns 1 rows from table(s) \u2014 consider pagination if too large"
  ]
}
```

</details>

---

## 8. NOT IN Subquery — Classic Anti-pattern

*NOT IN limits query plan options — prefer NOT EXISTS or LEFT JOIN.*

```sql
SELECT c.customer_name FROM customers c WHERE c.customer_id NOT IN (SELECT order_customer_id FROM orders)
```

### Complexity

**Label:** moderate  |  **Score:** 31/100

| Pattern | Detected |
|---------|----------|
| Joins | ✗ (0) |
| Subquery | ✓ |
| Correlated subquery | ✗ |
| DISTINCT | ✗ |
| ORDER BY | ✗ |
| GROUP BY | ✗ |
| Aggregate functions | ✗ |
| Function in WHERE | ✓ |
| Leading wildcard LIKE | ✗ |
| Cartesian join | ✗ |
| NOT IN | ✓ |
| OR condition | ✗ |
| UNION | ✗ |

### Execution

**Duration:** 32.29ms

**Rows (COUNT):** N/A

### Schema Analysis

**Tables analyzed:** 2
**Index info available:** ✓

| Table | Indexed columns |
|-------|-----------------|
| `customers` | customer_id |
| `orders` | order_customer_id, order_id |

### Recommendations

- Missing index on customers.FROM — column used in WHERE/JOIN but not indexed
- Missing index on orders.FROM — column used in WHERE/JOIN but not indexed
- NOT IN detected — consider NOT EXISTS or LEFT JOIN as alternative
- Function in WHERE clause prevents index usage on column(s)

### Full Result

<details>
<summary>Click to expand JSON</summary>

```json
{
  "success": true,
  "query": "SELECT c.customer_name FROM customers c WHERE c.customer_id NOT IN (SELECT order_customer_id FROM orders)",
  "execution": {
    "duration_ms": 32.290199999806646,
    "rows_total": 0,
    "sample_size": 3,
    "sampled_data": [],
    "error": null
  },
  "complexity": {
    "tables_involved": [
      "customers",
      "orders"
    ],
    "join_count": 0,
    "has_subquery": true,
    "has_correlated_subquery": false,
    "has_distinct": false,
    "has_order_by": false,
    "has_group_by": false,
    "has_aggregates": false,
    "has_where_function": true,
    "has_leading_wildcard_like": false,
    "has_cartesian_join": false,
    "has_not_in": true,
    "has_or_condition": false,
    "has_union": false,
    "score": 31,
    "complexity_label": "moderate"
  },
  "schema_analysis": {
    "success": true,
    "table_count": 2,
    "indexed_columns": {
      "customers": [
        "customer_id"
      ],
      "orders": [
        "order_id",
        "order_customer_id"
      ]
    },
    "index_info_available": true
  },
  "recommendations": [
    "Missing index on customers.FROM \u2014 column used in WHERE/JOIN but not indexed",
    "Missing index on orders.FROM \u2014 column used in WHERE/JOIN but not indexed",
    "NOT IN detected \u2014 consider NOT EXISTS or LEFT JOIN as alternative",
    "Function in WHERE clause prevents index usage on column(s)"
  ]
}
```

</details>

---

## 9. GROUP BY + HAVING + ORDER BY — Moderate

*Join, aggregates, GROUP BY, HAVING, ORDER BY — multiple patterns.*

```sql
SELECT c.category_name, COUNT(p.product_id) AS cnt, AVG(p.product_price) AS avg_price FROM products p INNER JOIN categories c ON p.product_category_id = c.category_id GROUP BY c.category_name HAVING COUNT(p.product_id) > 1 ORDER BY cnt DESC
```

### Complexity

**Label:** moderate  |  **Score:** 21/100

| Pattern | Detected |
|---------|----------|
| Joins | ✓ (1) |
| Subquery | ✗ |
| Correlated subquery | ✗ |
| DISTINCT | ✗ |
| ORDER BY | ✓ |
| GROUP BY | ✓ |
| Aggregate functions | ✓ |
| Function in WHERE | ✗ |
| Leading wildcard LIKE | ✗ |
| Cartesian join | ✗ |
| NOT IN | ✗ |
| OR condition | ✗ |
| UNION | ✗ |

### Execution

**Duration:** 4.64ms

**Rows (COUNT):** N/A

### Schema Analysis

**Tables analyzed:** 2
**Index info available:** ✓

| Table | Indexed columns |
|-------|-----------------|
| `categories` | category_id |
| `products` | product_category_id, product_id |

### Recommendations

- No significant performance issues detected

### Full Result

<details>
<summary>Click to expand JSON</summary>

```json
{
  "success": true,
  "query": "SELECT c.category_name, COUNT(p.product_id) AS cnt, AVG(p.product_price) AS avg_price FROM products p INNER JOIN categories c ON p.product_category_id = c.category_id GROUP BY c.category_name HAVING COUNT(p.product_id) > 1 ORDER BY cnt DESC",
  "execution": {
    "duration_ms": 4.636700000446581,
    "rows_total": 0,
    "sample_size": 3,
    "sampled_data": [],
    "error": null
  },
  "complexity": {
    "tables_involved": [
      "products",
      "categories"
    ],
    "join_count": 1,
    "has_subquery": false,
    "has_correlated_subquery": false,
    "has_distinct": false,
    "has_order_by": true,
    "has_group_by": true,
    "has_aggregates": true,
    "has_where_function": false,
    "has_leading_wildcard_like": false,
    "has_cartesian_join": false,
    "has_not_in": false,
    "has_or_condition": false,
    "has_union": false,
    "score": 21,
    "complexity_label": "moderate"
  },
  "schema_analysis": {
    "success": true,
    "table_count": 2,
    "indexed_columns": {
      "categories": [
        "category_id"
      ],
      "products": [
        "product_id",
        "product_category_id"
      ]
    },
    "index_info_available": true
  },
  "recommendations": [
    "No significant performance issues detected"
  ]
}
```

</details>

---

## 10. Cartesian Join — Heavy Anti-pattern

*Unqualified FROM with no WHERE/JOIN → cartesian product explosion.*

```sql
SELECT * FROM categories, products
```

### Complexity

**Label:** simple  |  **Score:** 15/100

| Pattern | Detected |
|---------|----------|
| Joins | ✗ (0) |
| Subquery | ✗ |
| Correlated subquery | ✗ |
| DISTINCT | ✗ |
| ORDER BY | ✗ |
| GROUP BY | ✗ |
| Aggregate functions | ✗ |
| Function in WHERE | ✗ |
| Leading wildcard LIKE | ✗ |
| Cartesian join | ✓ |
| NOT IN | ✗ |
| OR condition | ✗ |
| UNION | ✗ |

### Execution

**Duration:** 33.78ms

**Rows (COUNT):** 21

**Sample rows:**

```json
[
  {
    "category_id": 1,
    "category_name": "Electronics",
    "category_description": "Gadgets, devices, and accessories",
    "product_id": 1,
    "product_category_id": 1,
    "product_name": "Wireless Mouse",
    "product_sku": "ELE-MOU-001",
    "product_price": "25.99",
    "product_stock": 150,
    "product_created_at": "2026-06-04T18:50:44+00:00"
  },
  {
    "category_id": 2,
    "category_name": "Clothing",
    "category_description": "Apparel and fashion items",
    "product_id": 1,
    "product_category_id": 1,
    "product_name": "Wireless Mouse",
    "product_sku": "ELE-MOU-001",
    "product_price": "25.99",
    "product_stock": 150,
    "product_created_at": "2026-06-04T18:50:44+00:00"
  },
  {
    "category_id": 3,
    "category_name": "Books",
    "category_description": "Physical and digital books",
    "product_id": 1,
    "product_category_id": 1,
    "product_name": "Wireless Mouse",
    "product_sku": "ELE-MOU-001",
    "product_price": "25.99",
    "product_stock": 150,
    "product_created_at": "2026-06-04T18:50:44+00:00"
  }
]
```

### Schema Analysis

**Tables analyzed:** 1
**Index info available:** ✓

| Table | Indexed columns |
|-------|-----------------|
| `categories` | category_id |

### Recommendations

- Cartesian join detected between ['categories'] — missing JOIN condition?
- Query returns 21 rows from table(s) — consider pagination if too large

### Full Result

<details>
<summary>Click to expand JSON</summary>

```json
{
  "success": true,
  "query": "SELECT * FROM categories, products",
  "execution": {
    "duration_ms": 33.77530000034312,
    "rows_total": 21,
    "sample_size": 3,
    "sampled_data": [
      {
        "category_id": 1,
        "category_name": "Electronics",
        "category_description": "Gadgets, devices, and accessories",
        "product_id": 1,
        "product_category_id": 1,
        "product_name": "Wireless Mouse",
        "product_sku": "ELE-MOU-001",
        "product_price": "25.99",
        "product_stock": 150,
        "product_created_at": "2026-06-04T18:50:44+00:00"
      },
      {
        "category_id": 2,
        "category_name": "Clothing",
        "category_description": "Apparel and fashion items",
        "product_id": 1,
        "product_category_id": 1,
        "product_name": "Wireless Mouse",
        "product_sku": "ELE-MOU-001",
        "product_price": "25.99",
        "product_stock": 150,
        "product_created_at": "2026-06-04T18:50:44+00:00"
      },
      {
        "category_id": 3,
        "category_name": "Books",
        "category_description": "Physical and digital books",
        "product_id": 1,
        "product_category_id": 1,
        "product_name": "Wireless Mouse",
        "product_sku": "ELE-MOU-001",
        "product_price": "25.99",
        "product_stock": 150,
        "product_created_at": "2026-06-04T18:50:44+00:00"
      }
    ],
    "error": null
  },
  "complexity": {
    "tables_involved": [
      "categories"
    ],
    "join_count": 0,
    "has_subquery": false,
    "has_correlated_subquery": false,
    "has_distinct": false,
    "has_order_by": false,
    "has_group_by": false,
    "has_aggregates": false,
    "has_where_function": false,
    "has_leading_wildcard_like": false,
    "has_cartesian_join": true,
    "has_not_in": false,
    "has_or_condition": false,
    "has_union": false,
    "score": 15,
    "complexity_label": "simple"
  },
  "schema_analysis": {
    "success": true,
    "table_count": 1,
    "indexed_columns": {
      "categories": [
        "category_id"
      ]
    },
    "index_info_available": true
  },
  "recommendations": [
    "Cartesian join detected between ['categories'] \u2014 missing JOIN condition?",
    "Query returns 21 rows from table(s) \u2014 consider pagination if too large"
  ]
}
```

</details>

---
