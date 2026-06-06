# Query Analyzer — Live Examples on `postgres.accdb`

**Generated:** 2026-06-05
**Connection:** COM (WinComAdapter) — full schema index analysis
**Mode:** `dry_run=false`, `sample_size=3`

---

## Summary

| # | Query | Complexity | Score | Duration | Rows | Anti-patterns |
|---|-------|------------|-------|----------|------|---------------|
| 1 | Simple SELECT — Baseline | simple | 0 | 163.7ms | ⚠️ error | — |
| 2 | Leading Wildcard LIKE — Anti-pattern | simple | 10 | 237.0ms | ⚠️ error | Wildcard |
| 3 | Aggregate with Unindexed WHERE — Missing Index | simple | 3 | 28.6ms | ⚠️ error | Agg |
| 4 | Single JOIN with Unindexed WHERE — Missing Index | simple | 10 | 164.0ms | ⚠️ error | JOIN(1) |
| 5 | Multi-JOIN with Unindexed Email — Complex | moderate | 30 | 2.1ms | ⚠️ error | JOIN(3) |
| 6 | Function in WHERE — Index Prevention | simple | 8 | 33.4ms | ⚠️ error | FuncWHERE |
| 7 | Subquery in WHERE — Moderate Complexity | moderate | 28 | 32.4ms | ⚠️ error | SubQ, FuncWHERE |
| 8 | NOT IN Subquery — Classic Anti-pattern | moderate | 31 | 32.7ms | ⚠️ error | SubQ, FuncWHERE, NOT IN |
| 9 | GROUP BY + HAVING + ORDER BY — Moderate | moderate | 21 | 3.0ms | ⚠️ error | JOIN(1), Agg, GROUP BY, ORDER BY |
| 10 | Cartesian Join — Heavy Anti-pattern | simple | 15 | 31.9ms | ⚠️ error | Cartesian |

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

⚠️ **Execution error:** COUNT execution failed: string indices must be integers, not 'str'

### Schema Analysis

**Tables analyzed:** 1
**Index info available:** ✗

### Recommendations

- Missing index on customers.customer_id — column used in WHERE/JOIN but not indexed

### Full Result

<details>
<summary>Click to expand JSON</summary>

```json
{
  "success": true,
  "query": "SELECT * FROM customers WHERE customer_id = 1",
  "execution": {
    "duration_ms": 163.70119999965027,
    "rows_total": null,
    "sample_size": 3,
    "sampled_data": null,
    "error": "COUNT execution failed: string indices must be integers, not 'str'"
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
    "indexed_columns": {},
    "index_info_available": false
  },
  "recommendations": [
    "Missing index on customers.customer_id \u2014 column used in WHERE/JOIN but not indexed"
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

⚠️ **Execution error:** COUNT execution failed: string indices must be integers, not 'str'

### Schema Analysis

**Tables analyzed:** 1
**Index info available:** ✓

| Table | Indexed columns |
|-------|-----------------|
| `products` | product_category_id |

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
    "duration_ms": 236.96990000007645,
    "rows_total": null,
    "sample_size": 3,
    "sampled_data": null,
    "error": "COUNT execution failed: string indices must be integers, not 'str'"
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

⚠️ **Execution error:** COUNT execution failed: string indices must be integers, not 'str'

### Schema Analysis

**Tables analyzed:** 1
**Index info available:** ✓

| Table | Indexed columns |
|-------|-----------------|
| `orders` | order_customer_id |

### Recommendations

- Missing index on orders.order_status — column used in WHERE/JOIN but not indexed

### Full Result

<details>
<summary>Click to expand JSON</summary>

```json
{
  "success": true,
  "query": "SELECT COUNT(*) AS n FROM orders WHERE order_status = 'shipped'",
  "execution": {
    "duration_ms": 28.61140000004525,
    "rows_total": null,
    "sample_size": 3,
    "sampled_data": null,
    "error": "COUNT execution failed: string indices must be integers, not 'str'"
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
        "order_customer_id"
      ]
    },
    "index_info_available": true
  },
  "recommendations": [
    "Missing index on orders.order_status \u2014 column used in WHERE/JOIN but not indexed"
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

⚠️ **Execution error:** COUNT execution failed: string indices must be integers, not 'str'

### Schema Analysis

**Tables analyzed:** 2
**Index info available:** ✓

| Table | Indexed columns |
|-------|-----------------|
| `orders` | order_customer_id |

### Recommendations

- Missing index on customers.order_total — column used in WHERE/JOIN but not indexed
- Missing index on orders.order_total — column used in WHERE/JOIN but not indexed

### Full Result

<details>
<summary>Click to expand JSON</summary>

```json
{
  "success": true,
  "query": "SELECT c.customer_name, o.order_total FROM customers c INNER JOIN orders o ON c.customer_id = o.order_customer_id WHERE o.order_total > 50",
  "execution": {
    "duration_ms": 164.04330000023037,
    "rows_total": null,
    "sample_size": 3,
    "sampled_data": null,
    "error": "COUNT execution failed: string indices must be integers, not 'str'"
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
      "orders": [
        "order_customer_id"
      ]
    },
    "index_info_available": true
  },
  "recommendations": [
    "Missing index on customers.order_total \u2014 column used in WHERE/JOIN but not indexed",
    "Missing index on orders.order_total \u2014 column used in WHERE/JOIN but not indexed"
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

⚠️ **Execution error:** COUNT execution failed: string indices must be integers, not 'str'

### Schema Analysis

**Tables analyzed:** 4
**Index info available:** ✓

| Table | Indexed columns |
|-------|-----------------|
| `order_items` | order_item_order_id, order_item_product_id |
| `orders` | order_customer_id |
| `products` | product_category_id |

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
    "duration_ms": 2.0985999999538762,
    "rows_total": null,
    "sample_size": 3,
    "sampled_data": null,
    "error": "COUNT execution failed: string indices must be integers, not 'str'"
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
      "order_items": [
        "order_item_order_id",
        "order_item_product_id"
      ],
      "orders": [
        "order_customer_id"
      ],
      "products": [
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

⚠️ **Execution error:** COUNT execution failed: string indices must be integers, not 'str'

### Schema Analysis

**Tables analyzed:** 1
**Index info available:** ✓

| Table | Indexed columns |
|-------|-----------------|
| `orders` | order_customer_id |

### Recommendations

- Function YEAR() in WHERE clause prevents index usage on order_date

### Full Result

<details>
<summary>Click to expand JSON</summary>

```json
{
  "success": true,
  "query": "SELECT * FROM orders WHERE YEAR(order_date) = 2026",
  "execution": {
    "duration_ms": 33.41880000016317,
    "rows_total": null,
    "sample_size": 3,
    "sampled_data": null,
    "error": "COUNT execution failed: string indices must be integers, not 'str'"
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
        "order_customer_id"
      ]
    },
    "index_info_available": true
  },
  "recommendations": [
    "Function YEAR() in WHERE clause prevents index usage on order_date"
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

⚠️ **Execution error:** COUNT execution failed: string indices must be integers, not 'str'

### Schema Analysis

**Tables analyzed:** 2
**Index info available:** ✓

| Table | Indexed columns |
|-------|-----------------|
| `order_items` | order_item_order_id, order_item_product_id |
| `products` | product_category_id |

### Recommendations

- Missing index on products.order_item_quantity — column used in WHERE/JOIN but not indexed
- Missing index on order_items.order_item_quantity — column used in WHERE/JOIN but not indexed
- Correlated subquery detected — consider rewriting as JOIN for better performance
- Function in WHERE clause prevents index usage on column(s)

### Full Result

<details>
<summary>Click to expand JSON</summary>

```json
{
  "success": true,
  "query": "SELECT product_name FROM products WHERE product_id IN (SELECT order_item_product_id FROM order_items WHERE order_item_quantity > 1)",
  "execution": {
    "duration_ms": 32.407599999714876,
    "rows_total": null,
    "sample_size": 3,
    "sampled_data": null,
    "error": "COUNT execution failed: string indices must be integers, not 'str'"
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
        "order_item_order_id",
        "order_item_product_id"
      ],
      "products": [
        "product_category_id"
      ]
    },
    "index_info_available": true
  },
  "recommendations": [
    "Missing index on products.order_item_quantity \u2014 column used in WHERE/JOIN but not indexed",
    "Missing index on order_items.order_item_quantity \u2014 column used in WHERE/JOIN but not indexed",
    "Correlated subquery detected \u2014 consider rewriting as JOIN for better performance",
    "Function in WHERE clause prevents index usage on column(s)"
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

⚠️ **Execution error:** COUNT execution failed: string indices must be integers, not 'str'

### Schema Analysis

**Tables analyzed:** 2
**Index info available:** ✓

| Table | Indexed columns |
|-------|-----------------|
| `orders` | order_customer_id |

### Recommendations

- Missing index on customers.SELECT — column used in WHERE/JOIN but not indexed
- Missing index on orders.SELECT — column used in WHERE/JOIN but not indexed
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
    "duration_ms": 32.74199999987104,
    "rows_total": null,
    "sample_size": 3,
    "sampled_data": null,
    "error": "COUNT execution failed: string indices must be integers, not 'str'"
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
      "orders": [
        "order_customer_id"
      ]
    },
    "index_info_available": true
  },
  "recommendations": [
    "Missing index on customers.SELECT \u2014 column used in WHERE/JOIN but not indexed",
    "Missing index on orders.SELECT \u2014 column used in WHERE/JOIN but not indexed",
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

⚠️ **Execution error:** COUNT execution failed: string indices must be integers, not 'str'

### Schema Analysis

**Tables analyzed:** 2
**Index info available:** ✓

| Table | Indexed columns |
|-------|-----------------|
| `products` | product_category_id |

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
    "duration_ms": 3.0264999995779363,
    "rows_total": null,
    "sample_size": 3,
    "sampled_data": null,
    "error": "COUNT execution failed: string indices must be integers, not 'str'"
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
      "products": [
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

⚠️ **Execution error:** COUNT execution failed: string indices must be integers, not 'str'

### Schema Analysis

**Tables analyzed:** 1
**Index info available:** ✗

### Recommendations

- Cartesian join detected between ['categories'] — missing JOIN condition?

### Full Result

<details>
<summary>Click to expand JSON</summary>

```json
{
  "success": true,
  "query": "SELECT * FROM categories, products",
  "execution": {
    "duration_ms": 31.934999999975844,
    "rows_total": null,
    "sample_size": 3,
    "sampled_data": null,
    "error": "COUNT execution failed: string indices must be integers, not 'str'"
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
    "indexed_columns": {},
    "index_info_available": false
  },
  "recommendations": [
    "Cartesian join detected between ['categories'] \u2014 missing JOIN condition?"
  ]
}
```

</details>

---
