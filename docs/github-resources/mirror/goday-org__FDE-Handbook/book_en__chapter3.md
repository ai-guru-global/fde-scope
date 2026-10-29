<!-- fde-scope mirror · repo: goday-org/FDE-Handbook · license: MIT · commit: 229db7b57e3362f3a66c3b757b1cb0c264e69535
     upstream path: book_en/chapter3.md · retrieved: 2026-10-06 · verbatim; report issues upstream. -->

# Chapter 3: Enterprise Data Audits and Schema Recovery

Data in the real world is messy, but data inside legacy enterprise databases is outright chaotic. When an FDE integrates a modern platform with a client's core operations, they are rarely greeted with a clean, documented, relational schema. Instead, they find undocumented tables, columns with names like `VAR_FLD_19`, mixed data encodings, orphaned rows, and inconsistent date-time structures.

Before building automated workflows or training AI models, the FDE must perform a comprehensive data audit. They must reverse engineer the undocumented schemas and write robust, optimized SQL query blocks to extract, clean, and rebuild relational structures.

This chapter outlines the methodology of enterprise data audits and details the SQL forensics toolset—specifically recursive queries, window functions, and execution plan tuning.

---

## 1. Schema Forensics & Undocumented Tables

In enterprise systems, documentation is often years out of date. To recover the schema, the FDE must inspect system catalogs and query distribution statistics.

### Database System Catalog Auditing
Most relational engines store metadata in system catalogs. An FDE begins by querying these views to identify table sizes, index layouts, and key relationships.

```sql
-- Find undocumented tables with high row counts and no indexes (PostgreSQL example)
SELECT 
    schemaname, 
    relname AS table_name, 
    n_live_tup AS row_count,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
    seq_scan AS sequential_scans,
    idx_scan AS index_scans
FROM 
    pg_stat_user_tables
WHERE 
    n_live_tup > 100000 
    AND idx_scan = 0
ORDER BY 
    n_live_tup DESC;
```

This query identifies tables with heavy read traffic that lack proper index coverage, a common cause of application performance degradation.

---

## 2. Advanced SQL Forensics Toolset

To trace data lineages, rebuild broken hierarchies, and identify duplicate entities across millions of rows, the FDE relies on advanced SQL constructs.

### 1. Hierarchical Extraction with Recursive CTEs
In enterprise architectures, hierarchies (like corporate divisions, ledger hierarchies, or reporting structures) are often stored in flat tables using parent-ID models with missing constraints. An FDE uses recursive Common Table Expressions (CTEs) to rebuild these trees and detect loops.

```sql
-- Rebuild hierarchical reporting structures and identify circular loops
WITH RECURSIVE org_tree AS (
    -- Anchor member: Select root managers
    SELECT 
        employee_id,
        manager_id,
        first_name,
        last_name,
        1 AS depth,
        ARRAY[employee_id] AS path,
        FALSE AS is_cycle
    FROM 
        employees
    WHERE 
        manager_id IS NULL
        
    UNION ALL
    
    -- Recursive member: Join child rows to parent tree
    SELECT 
        e.employee_id,
        e.manager_id,
        e.first_name,
        e.last_name,
        t.depth + 1 AS depth,
        t.path || e.employee_id AS path,
        e.employee_id = ANY(t.path) AS is_cycle
    FROM 
        employees e
    INNER JOIN 
        org_tree t ON e.manager_id = t.employee_id
    WHERE 
        NOT t.is_cycle
)
SELECT 
    employee_id,
    manager_id,
    first_name,
    last_name,
    depth,
    path,
    is_cycle
FROM 
    org_tree
ORDER BY 
    path;
```

This script extracts the entire hierarchy, traces the reporting path of each node, and flags circular relationships (`is_cycle`) that would break standard reporting logic.

### 2. Window Functions for Data Deduplication
Enterprise data often contains duplicate rows caused by failed ingestion attempts. Standard `DISTINCT` calls are too blunt for this issue. FDEs use analytic window functions to partition records and isolate the newest, most complete entry.


<svg viewBox="0 0 700 230" width="100%" height="auto" style="background-color: #fafafa; border: 1px solid #e1e1e8; border-radius: 4px; margin: 20px 0; display: block;">
  <!-- Partition 1 -->
  <rect x="50" y="40" width="280" height="150" fill="#f4f4f6" stroke="#333" stroke-width="1.5" rx="5" />
  <text x="190" y="30" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="12" fill="#111">PARTITION: Customer_A</text>
  
  <rect x="70" y="55" width="240" height="35" fill="#e8f5e9" stroke="#2e7d32" rx="3" />
  <text x="80" y="76" font-family="monospace" font-size="10" fill="#2e7d32">Row 1: 2026-05-20 | Active  | row_number=1</text>
  
  <rect x="70" y="100" width="240" height="35" fill="#fff" stroke="#999" rx="3" />
  <text x="80" y="121" font-family="monospace" font-size="10" fill="#555">Row 2: 2026-05-19 | Pending | row_number=2</text>
  
  <rect x="70" y="145" width="240" height="35" fill="#fff" stroke="#999" rx="3" />
  <text x="80" y="166" font-family="monospace" font-size="10" fill="#555">Row 3: 2026-05-18 | Draft   | row_number=3</text>

  <!-- Partition 2 -->
  <rect x="370" y="40" width="280" height="150" fill="#f4f4f6" stroke="#333" stroke-width="1.5" rx="5" />
  <text x="510" y="30" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="12" fill="#111">PARTITION: Customer_B</text>
  
  <rect x="390" y="55" width="240" height="35" fill="#e8f5e9" stroke="#2e7d32" rx="3" />
  <text x="400" y="76" font-family="monospace" font-size="10" fill="#2e7d32">Row 1: 2026-05-20 | Active  | row_number=1</text>
  
  <rect x="390" y="100" width="240" height="35" fill="#fff" stroke="#999" rx="3" />
  <text x="400" y="121" font-family="monospace" font-size="10" fill="#555">Row 2: 2026-05-15 | Inactive| row_number=2</text>
  
  <rect x="390" y="145" width="240" height="35" fill="#fff" stroke="#999" rx="3" />
  <text x="400" y="166" font-family="monospace" font-size="10" fill="#555">Row 3: 2026-05-10 | Created | row_number=3</text>
</svg>

```sql
-- Isolate the most recent record per customer partition
WITH ranked_records AS (
    SELECT 
        record_id,
        customer_id,
        status,
        updated_timestamp,
        row_number() OVER (
            PARTITION BY customer_id 
            ORDER BY updated_timestamp DESC, record_id DESC
        ) as row_num
    FROM 
        customer_history
)
SELECT 
    record_id,
    customer_id,
    status,
    updated_timestamp
FROM 
    ranked_records
WHERE 
    row_num = 1;
```

By partitioning by the unique identifier (`customer_id`) and sorting by time (`updated_timestamp`), we isolate the latest state of each entity, discarding previous revisions.

---

## 3. Query Optimization & Execution Plan Analysis

When querying tables with hundreds of millions of rows, an unoptimized join will crash the database engine or time out. FDEs analyze execution plans to diagnose query bottlenecks.

### Interpreting execution plans (EXPLAIN ANALYZE)
FDEs prepend `EXPLAIN ANALYZE` to queries to review the planner's decisions.

```sql
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT 
    c.customer_name, 
    SUM(o.order_amount)
FROM 
    orders o
JOIN 
    customers c ON o.customer_id = c.customer_id
WHERE 
    o.order_date >= '2026-01-01'
GROUP BY 
    c.customer_name;
```

#### Diagnostic Indicators:
* **Sequential Scan (Seq Scan)**: Indicates the database engine is reading every page of a table from disk. If a table has millions of rows and the scanner hits a `Seq Scan` on a filter field, an index is missing.
* **Hash Join vs. Nested Loop**: For large datasets, a `Hash Join` is preferred. A `Nested Loop` with high loop counts indicates a missing index on the join key.
* **Buffers (Shared Hit/Read)**: Shows how many data pages were read from memory cache (`Hit`) vs. disk (`Read`). High disk read counts suggest configuration adjustments or index enhancements are required.

---

## Summary

Data audits are the foundation of any enterprise software deployment. By querying database catalogs, using recursive queries to rebuild hierarchies, and applying window partitioning to clean duplicates, FDEs establish a reliable data foundation for the platform.
