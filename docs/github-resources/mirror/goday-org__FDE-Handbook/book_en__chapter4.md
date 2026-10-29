<!-- fde-scope mirror · repo: goday-org/FDE-Handbook · license: MIT · commit: 229db7b57e3362f3a66c3b757b1cb0c264e69535
     upstream path: book_en/chapter4.md · retrieved: 2026-10-06 · verbatim; report issues upstream. -->

# Chapter 4: Modern Data Architectures in Practice

Once legacy schemas are audited and structured, the FDE must design a scalable data architecture to process and serve this data. In the enterprise world, scaling is not just about choosing a larger server. It requires selecting the right storage patterns—such as Star Schemas versus One Big Table (OBT)—designing ingestion pipelines using the Medallion Architecture, handling computational bottlenecks like data skew, and implementing data quality testing.

This chapter dissects these modern data architectures, provides a complete PySpark script to resolve data skew using salting, and details dbt configurations for validating data quality.

---

## 1. Storage Layouts: Star Schema vs. One Big Table (OBT)

Choosing the correct storage layout determines the performance and cost of downstream analytics and AI applications.

### 1. The Star Schema (Dimensional Modeling)
Developed by Ralph Kimball, the Star Schema separates business data into:
* **Fact Tables**: Large tables containing quantitative metrics (e.g., transactions, logs).
* **Dimension Tables**: Smaller tables containing descriptive attributes (e.g., customer details, store locations).
* **Pros**: Maximizes storage efficiency by reducing redundancy; easy for business analysts to understand.
* **Cons**: Requires complex SQL joins (`JOIN`) at query time, which can slow down modern column-oriented cloud warehouses.

### 2. One Big Table (OBT)
In modern cloud data warehouses (like BigQuery or Snowflake), storage is inexpensive, but join computations are expensive. OBT denormalizes facts and dimensions into a single wide table.
* **Pros**: Eliminates join overhead entirely, resulting in sub-second query latency for large datasets.
* **Cons**: High storage duplication; updating a single dimension attribute requires modifying millions of rows.

---

## 2. The Medallion Architecture

To process raw enterprise files into clean data tables, FDEs implement the three-tier Medallion Architecture.


<svg viewBox="0 0 750 200" width="100%" height="auto" style="background-color: #fafafa; border: 1px solid #e1e1e8; border-radius: 4px; margin: 20px 0; display: block;">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#333" />
    </marker>
  </defs>

  <!-- Ingestion -->
  <rect x="20" y="70" width="100" height="60" fill="#fff" stroke="#666" rx="4" />
  <text x="70" y="95" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="11">Raw Sources</text>
  <text x="70" y="112" text-anchor="middle" font-family="monospace" font-size="9" fill="#555">CSV / DB Logs</text>

  <line x1="120" y1="100" x2="160" y2="100" stroke="#333" stroke-width="1.5" marker-end="url(#arrow)" />

  <!-- Bronze -->
  <rect x="170" y="50" width="140" height="100" fill="#f5f5f5" stroke="#795548" stroke-width="2" rx="6" />
  <text x="240" y="80" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="12" fill="#795548">BRONZE LAYER</text>
  <text x="240" y="105" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#333">Raw Ingestion</text>
  <text x="240" y="125" text-anchor="middle" font-family="monospace" font-size="9" fill="#666">Append-Only / History</text>

  <line x1="310" y1="100" x2="350" y2="100" stroke="#333" stroke-width="1.5" marker-end="url(#arrow)" />

  <!-- Silver -->
  <rect x="360" y="50" width="140" height="100" fill="#eceff1" stroke="#607d8b" stroke-width="2" rx="6" />
  <text x="430" y="80" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="12" fill="#607d8b">SILVER LAYER</text>
  <text x="430" y="105" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#333">Cleaned &amp; Enriched</text>
  <text x="430" y="125" text-anchor="middle" font-family="monospace" font-size="9" fill="#666">Deduplicated / Conformed</text>

  <line x1="500" y1="100" x2="540" y2="100" stroke="#333" stroke-width="1.5" marker-end="url(#arrow)" />

  <!-- Gold -->
  <rect x="550" y="50" width="140" height="100" fill="#fff9c4" stroke="#fbc02d" stroke-width="2" rx="6" />
  <text x="620" y="80" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="12" fill="#fbc02d">GOLD LAYER</text>
  <text x="620" y="105" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#333">Business Views</text>
  <text x="620" y="125" text-anchor="middle" font-family="monospace" font-size="9" fill="#666">Aggregated / BI Ready</text>
</svg>

1. **Bronze (Raw Ingestion)**: An append-only repository containing the exact structure of source files. It retains historical records and preserves audit capability.
2. **Silver (Enriched & Validated)**: Data is cleaned, typed, deduplicated, and conformed to core schemas. It serves as the primary query target for analytical engines.
3. **Gold (Business Ready)**: Highly aggregated, analytical tables partitioned by business keys. It feeds dashboards and AI agent memory blocks.

---

## 3. Computational Scaling: Resolving Data Skew in PySpark

When processing data at scale in Spark or Ray, an FDE will frequently encounter **data skew**. Skew occurs when a single partition key (e.g., a generic customer ID like `NULL` or a default tenant key `0`) contains significantly more rows than other keys. 

During a join or aggregation, Spark shuffles all rows sharing a key to a single executor. The executor handling the skewed key runs out of memory (OOM) or takes hours to complete, leaving other executors idle.

An FDE resolves data skew using **salting**—prepending a random integer to the join keys to distribute the skewed values across multiple partitions, joining them against an exploded dimension table.

```python
# Spark Salting implementation to resolve executor OOM bottlenecks
import random
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder \
    .appName("FDE-Salting-Demo") \
    .config("spark.sql.shuffle.partitions", "200") \
    .getOrCreate()

# Mock skewed fact dataset (e.g., millions of transaction records)
fact_df = spark.createDataFrame([
    ("UNKNOWN", 10.5), ("UNKNOWN", 25.0), ("UNKNOWN", 100.2), # Skewed keys
    ("CUST_01", 50.0), ("CUST_02", 75.5)
], ["customer_id", "amount"])

# Mock dimension dataset (customer descriptive labels)
dim_df = spark.createDataFrame([
    ("UNKNOWN", "Guest Customer"),
    ("CUST_01", "Enterprise Tier A"),
    ("CUST_02", "Enterprise Tier B")
], ["customer_id", "customer_name"])

# Number of salt bins to split the skewed partition
SALT_BINS = 4

# Step 1: Prepend random salt to the fact table
salted_fact_df = fact_df.withColumn(
    "salt", 
    F.floor(F.rand() * SALT_BINS)
).withColumn(
    "join_key",
    F.concat(F.col("customer_id"), F.lit("_"), F.col("salt"))
)

# Step 2: Explode the dimension table to match salted keys
salted_dim_df = dim_df.withColumn(
    "salts",
    F.array([F.lit(i) for i in range(SALT_BINS)])
).withColumn(
    "salt",
    F.explode("salts")
).withColumn(
    "join_key",
    F.concat(F.col("customer_id"), F.lit("_"), F.col("salt"))
)

# Step 3: Perform join using the salted keys
joined_df = salted_fact_df.join(
    salted_dim_df,
    on="join_key",
    how="inner"
).select(
    salted_fact_df["customer_id"],
    salted_dim_df["customer_name"],
    F.col("amount")
)

joined_df.show(truncate=False)
```

Adding the salt value distributes the `UNKNOWN` rows across multiple executors, preventing OOM issues and balancing cluster usage.

---

## 4. Data Quality Testing: Operational Safeguards with dbt

An FDE cannot assume that incoming data will remain clean. They must implement testing pipelines to act as circuit breakers, stopping processing if data quality fails.

### Schema Validation & Assertion Tests (dbt schema.yml)
Using `dbt`, FDEs configure assertion tests directly within their project manifests to validate data models during processing.

```yaml
version: 2

models:
  - name: silver_customers
    description: "Deduplicated and validated customer directory"
    columns:
      - name: customer_id
        description: "Primary key"
        tests:
          - unique
          - not_null
      - name: email_address
        description: "Customer email contact"
        tests:
          - not_null
          - relationships:
              to: ref('bronze_raw_customers')
              field: raw_email
      - name: lifecycle_status
        description: "Customer lifecycle tier"
        tests:
          - accepted_values:
              values: ['lead', 'active', 'inactive', 'churned']
```

Running `dbt test` validates these rules. If a column contains unacceptable values or null values in primary keys, the pipeline halts immediately, preventing bad data from corrupting downstream gold datasets or AI memory blocks.

---

## Summary

Designing data architectures requires balancing scale, computing efficiency, and data quality. By utilizing denormalized OBT layouts for high-performance querying, structuring pipelines using the Medallion pattern, salting to prevent Spark data skew, and configuring dbt assertions, FDEs establish robust data architectures that scale reliably in production.
