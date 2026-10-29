<!-- fde-scope mirror · repo: goday-org/FDE-Handbook · license: MIT · commit: 229db7b57e3362f3a66c3b757b1cb0c264e69535
     upstream path: book_en/chapter10.md · retrieved: 2026-10-06 · verbatim; report issues upstream. -->

# Chapter 10: Case Study: Deploying a Secure AI Platform

This chapter synthesizes the engineering patterns, security practices, and architectural decisions discussed throughout this book into a single end-to-end case study. We follow the deployment of a secure, production-grade enterprise AI and data platform for a global financial institution: **Apex Global Wealth**.

We detail the landing zone design, database migrations, dbt transformations, RAG indexing pipelines, multi-agent loops, and evaluation metrics, providing a comprehensive blueprint for enterprise deployments.

---

## 1. Case Study Overview & System Architecture

Apex Global Wealth required an AI platform to analyze multi-million-row client portfolios, cross-reference them with market research PDFs containing complex tables, and generate audit-ready financial advice reports.

### Operational Requirements
* **Regulatory Compliance**: All customer data must remain within a private cloud network. No data can be sent to external APIs over the public internet, and cloud APIs must be protected by a service perimeter.
* **Accuracy Guarantee**: Generative models must not hallucinate portfolio balances or transaction records. Every statement in a generated report must be grounded in verified system data.
* **Performance SLA**: End-to-end report generation must complete in under 5 minutes, replacing a manual process that takes up to 48 hours.


<svg viewBox="0 0 750 280" width="100%" height="auto" style="background-color: #fafafa; border: 1px solid #e1e1e8; border-radius: 4px; margin: 20px 0; display: block;">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#333" />
    </marker>
  </defs>

  <!-- VPC Service Controls Boundary -->
  <rect x="15" y="15" width="720" height="250" fill="#e8f5e9" stroke="#2e7d32" stroke-width="2.5" stroke-dasharray="8" rx="8" />
  <text x="375" y="35" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="12" fill="#2e7d32">VPC SERVICE CONTROLS SECURITY PERIMETER</text>

  <!-- Host Network Project Subnets -->
  <rect x="30" y="55" width="220" height="190" fill="#f4f4f6" stroke="#333" stroke-width="1.5" rx="6" />
  <text x="140" y="75" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="11" fill="#111">Shared VPC (Host Project)</text>
  
  <rect x="45" y="95" width="190" height="60" fill="#fff" stroke="#666" rx="4" />
  <text x="140" y="115" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="10">Subnet GKE</text>
  <text x="140" y="130" text-anchor="middle" font-family="monospace" font-size="8" fill="#555">10.100.0.0/20 (Private)</text>

  <rect x="45" y="170" width="190" height="60" fill="#fff" stroke="#666" rx="4" />
  <text x="140" y="190" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="10">Subnet Data / SQL</text>
  <text x="140" y="205" text-anchor="middle" font-family="monospace" font-size="8" fill="#555">10.200.0.0/20 (PSC)</text>

  <!-- Service Project (GKE Platform) -->
  <rect x="280" y="55" width="220" height="190" fill="#e3f2fd" stroke="#1a73e8" stroke-width="1.5" rx="6" />
  <text x="390" y="75" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="11" fill="#1a73e8">Service Project (Platform)</text>
  
  <rect x="295" y="95" width="190" height="135" fill="#fff" stroke="#1a73e8" rx="4" />
  <text x="390" y="115" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="10">LangGraph Agents</text>
  <text x="390" y="135" text-anchor="middle" font-family="monospace" font-size="8" fill="#666">DBA Worker (PostgreSQL)</text>
  <text x="390" y="155" text-anchor="middle" font-family="monospace" font-size="8" fill="#666">RAG Ingestion (LlamaParse)</text>
  <text x="390" y="175" text-anchor="middle" font-family="monospace" font-size="8" fill="#666">Supervisor (State Machine)</text>
  <text x="390" y="195" text-anchor="middle" font-family="monospace" font-size="8" fill="#1a73e8">KSA maps via GSA (WI)</text>

  <!-- Protected Services (BigQuery & Vertex) -->
  <rect x="530" y="55" width="180" height="190" fill="#fff9c4" stroke="#fbc02d" stroke-width="1.5" rx="6" />
  <text x="620" y="75" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="11" fill="#b79008">Protected GCP APIs</text>

  <rect x="545" y="95" width="150" height="60" fill="#fff" stroke="#fbc02d" rx="4" />
  <text x="620" y="115" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="10">BigQuery DWH</text>
  <text x="620" y="130" text-anchor="middle" font-family="monospace" font-size="8" fill="#666">Medallion Gold Data</text>

  <rect x="545" y="170" width="150" height="60" fill="#fff" stroke="#fbc02d" rx="4" />
  <text x="620" y="190" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="10">Vertex AI / LLM</text>
  <text x="620" y="205" text-anchor="middle" font-family="monospace" font-size="8" fill="#666">Gemini 1.5 &amp; Vector</text>

  <!-- Flow Connections -->
  <path d="M 250 120 L 280 120" fill="none" stroke="#333" stroke-width="1.5" marker-end="url(#arrow)" />
  <path d="M 500 120 L 530 120" fill="none" stroke="#333" stroke-width="1.5" marker-end="url(#arrow)" />
</svg>

---

## 2. Step-by-Step Implementation Guide

An FDE deploys the Apex Global Wealth platform using a structured, step-by-step lifecycle workflow:

### Step 1: Landing Zone Setup
Configure the Shared VPC, private GKE cluster, Access Context Manager policies, and Workload Identity bindings using the Terraform configurations detailed in Chapters 5 and 6. This establishes the secure foundation for the platform.

### Step 2: Database Ingest and dbt Transformations
* The FDE uses dbt to extract raw, transaction-level records from the legacy database, load them into the Bronze layer, and transform them into a clean Star Schema in the Silver layer.
* High-volume tables are structured and scaled using the PySpark data salting techniques detailed in Chapter 4 to resolve executor processing bottlenecks.
* Before processing continues, `dbt test` assertions validate the schema and ensure no invalid data is loaded.

### Step 3: RAG Ingestion Pipeline
* Financial market research PDFs are parsed using LlamaParse, transforming tables and charts into structured Markdown format.
* The parsed markdown chunks are vectorized using Vertex AI embeddings and indexed in Vertex AI Vector Search to enable semantic retrieval.

### Step 4: Multi-Agent Deployment
* The LangGraph multi-agent orchestrator is deployed on GKE nodes.
* The **Supervisor Agent** coordinates execution steps:
  1. The **Database Agent** uses custom SQL tools to extract the relevant client's portfolio state.
  2. The **RAG Agent** queries the vector index using the hybrid search architecture (dense vector + sparse BM25 merged via RRF) to retrieve the latest market insights.
  3. The **Report Generator Agent** synthesizes these inputs into the final advisory document.

### Step 5: Continuous Evaluation Setup
The evaluation suite runs Faithfulness audits on generated reports. Reports that fail to meet defined threshold scores are flagged and routed to a compliance queue for manual review before delivery.

---

## 3. Production Deployment Playbook & Configuration Blueprints

Below are the complete deployment configurations used to verify the platform's production readiness.

### 1. dbt Transformation Configuration
This dbt model transforms raw transactions into the conformed Silver-level fact table.

```sql
-- models/silver/silver_portfolio_balances.sql
{{ config(
    materialized='incremental',
    unique_key='balance_id',
    partition_by={
      "field": "as_of_date",
      "data_type": "date",
      "granularity": "day"
    }
) }}

WITH raw_transactions AS (
    SELECT * FROM {{ ref('bronze_raw_transactions') }}
    {% if is_incremental() %}
    WHERE transaction_timestamp >= (SELECT MAX(transaction_timestamp) FROM {{ this }})
    {% endif %}
),

cleaned_balances AS (
    SELECT
        MD5(CONCAT(customer_id, '|', transaction_date)) AS balance_id,
        customer_id,
        CAST(transaction_date AS DATE) AS as_of_date,
        SUM(amount) OVER (
            PARTITION BY customer_id 
            ORDER BY transaction_timestamp 
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS current_balance,
        transaction_timestamp AS last_updated_at
    FROM
        raw_transactions
)

SELECT * FROM cleaned_balances
```

### 2. GKE Deployment Manifest
This deployment manifest runs the LangGraph supervisor agent inside the private GKE subnet, mapping access permissions via Workload Identity.

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fde-supervisor-deployment
  namespace: fde-secure-platform
  labels:
    app: fde-supervisor
spec:
  replicas: 3
  selector:
    matchLabels:
      app: fde-supervisor
  template:
    metadata:
      labels:
        app: fde-supervisor
    spec:
      # Reference the KSA mapped to Workload Identity
      serviceAccountName: data-processor-ksa
      containers:
      - name: platform-orchestrator
        image: gcr.io/apex-global-wealth/fde-orchestrator:v1.2.0
        ports:
        - containerPort: 8080
        env:
        - name: PROJECT_ID
          value: "apex-service-project"
        - name: LOCATION
          value: "us-central1"
        resources:
          limits:
            memory: "4Gi"
            cpu: "2000m"
          requests:
            memory: "2Gi"
            cpu: "1000m"
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          runAsNonRoot: true
          runAsUser: 10001
```

This configuration ensures the application has sufficient memory to run the LangGraph orchestrator, is secured using least-privilege run contexts, and has read-only root filesystem permissions to prevent container manipulation.

---

## Summary

Deploying enterprise AI platforms requires integrating secure networking, structured data pipelines, precise retrieval mechanisms, and continuous output validation. By synthesizing Shared VPC networks, dbt transformations, hybrid search RAG architectures, and LangGraph multi-agent loops into a unified, secure system, FDEs deliver robust, compliant AI solutions that meet enterprise operational requirements.
