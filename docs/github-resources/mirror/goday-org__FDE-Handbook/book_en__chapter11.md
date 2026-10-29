<!-- fde-scope mirror · repo: goday-org/FDE-Handbook · license: MIT · commit: 229db7b57e3362f3a66c3b757b1cb0c264e69535
     upstream path: book_en/chapter11.md · retrieved: 2026-10-06 · verbatim; report issues upstream. -->

# Chapter 11: Glossary & Bibliography

As a multidisciplinary field, Forward Deployed Engineering uses terminology spanning software engineering, cloud network security, distributed systems, and consulting frameworks. 

This final chapter serves as a reference manual, providing an FDE glossary and an annotated bibliography of books, whitepapers, and documentation for further study.

---

## 1. The FDE Glossary

### A2A (Agent-to-Agent Protocol)
An open, HTTP-based communication protocol designed by Google. It defines standard schemas for agents to discover one another, transfer runtime context, route messages, and delegate sub-tasks dynamically across distributed microservices.

### Access Context Manager (ACM)
A Google Cloud service that defines attribute-based access control policies for protected resources. ACM operates at the organization level, defining conditions based on IP range, device security state, user identities, and geographic locations to permit or deny access to APIs.

### Active Directory (AD) Integration
The process of linking enterprise software to a client's central user database (typically Microsoft Active Directory or LDAP) for authentication and authorization. In FDE engagements, this involves configuring SAML or OIDC plugins to handle secure Single Sign-On (SSO).

### ADK (Agent Development Kit)
Google’s open-source, code-first framework for building multi-agent systems. It provides software engineering structures (classes, interfaces, dependency injection patterns) for managing agent prompts, tools, and states.

### Air-Gapped Environment
A high-security network design where servers have no physical or logical connection to the public internet. Deployments in these environments require all dependencies (libraries, container images, base models) to be pre-packaged and run locally.

### AutoSxS (Automated Side-by-Side)
A pairwise evaluation methodology where a high-performance model (e.g., Gemini 1.5 Pro) acts as a judge, comparing the outputs of two distinct models/prompts against a defined rubric to calculate a statistical win rate.

### BM25 (Okapi BM25)
A ranking function used by search engines to estimate the relevance of documents to a given search query. It is based on a probabilistic retrieval framework that scores matches based on term frequency (TF) and inverse document frequency (IDF).

### Bronze Zone
The initial ingestion layer in the Medallion Architecture. It stores raw, unmodified data streams (JSON, CSV, or database change logs) in an immutable format to ensure complete data lineage.

### Cloud Interconnect
A Google Cloud service providing high-bandwidth, low-latency physical connections between an enterprise’s on-premises network and the GCP virtual network. It bypasses the public internet, routing traffic over private fiber.

### Cross-Encoder Reranker
A deep learning model that takes a query and a retrieved document together as a single input and computes a relevancy score. Unlike Bi-Encoders, which evaluate query and document embeddings independently, Cross-Encoders capture complex token interactions, yielding higher ranking precision at the cost of higher latency.

### dbt (Data Build Tool)
A development framework that enables data analysts and engineers to build, test, and document data transformations inside SQL-based data warehouses. It treats SQL queries as models, managing dependencies and executing transformations using standard software engineering principles.

### dbt Incremental Model
A performance optimization pattern in dbt where only new or updated database rows are transformed and inserted during a run, rather than rebuilding the entire table. It reduces runtime and cloud resource consumption on large datasets.

### dbt Test Assertion
An automated data validation rule defined in YAML that runs assertions against database columns (e.g., checking for unique values, non-null values, or foreign key relationships) to verify data quality during the build pipeline.

### Dev vs. Delta
The architectural framework that splits software into the core, client-agnostic platform code developed at headquarters (Dev) and the custom integration code written to deploy the platform at a specific client site (Delta).

### Egress Policy (VPC SC)
A firewall-style rule in Google Cloud VPC Service Controls that specifies which identities (service accounts, users) can move data from protected services inside the security perimeter to external projects or public storage.

### Fenced Code Block
A markdown syntax pattern using triple backticks (```) to define preformatted blocks of text, typically source code. Markdown parsers render these blocks within `<pre><code>` tags, preserving whitespace and escaping special HTML characters.

### Gold Zone
The final consumption layer in the Medallion Architecture. It stores highly structured, pre-aggregated, denormalized tables optimized for fast query speeds in user dashboards and LLM context retrieval.

### Groundedness (Faithfulness)
A quality metric for LLMs. It measures the degree to which a model's output is based *only* on the provided context, penalizing any information introduced from the model's pre-trained weights (hallucinations).

### Hybrid Search
A search pipeline that combines dense vector search (capturing semantic intent) and sparse BM25 keyword matching (capturing exact terms and product codes) into a single query to optimize retrieval recall and precision.

### Ingress Policy (VPC SC)
A security rule in VPC Service Controls specifying under what conditions (e.g., source IP, caller identity, geographic origin) an external resource or network is allowed to call APIs inside the protected security perimeter.

### LangGraph
An orchestration library designed for building stateful, multi-agent systems as cyclic graphs. It allows developers to define complex loops, memory managers, and tool execution routes while enforcing strict state schemas.

### LlamaParse
A document parsing service optimized for converting unstructured PDFs, manuals, and scanned documents into structured Markdown format. It specializes in extracting tabular data, preserving column alignment and cellular relationships.

### MECE
Mutually Exclusive, Collectively Exhaustive. A structured problem-solving framework that divides a complex problem into distinct, non-overlapping categories (Mutually Exclusive) that cover the entire problem space (Collectively Exhaustive).

### One Big Table (OBT)
A data modeling pattern where all dimension columns are flattened into a single, massive table, eliminating the need for `JOIN` queries. It is highly optimized for read-heavy operations in columnar data warehouses.

### Private Service Connect (PSC)
A Google Cloud networking service that allows private consumption of services across VPC networks or managed APIs (like BigQuery or Cloud SQL) using internal IP addresses. It eliminates the need for public IP routes or internet gateways.

### Pyramid Principle
A communication framework pioneered by Barbara Minto. It dictates that communication should present the final recommendation or answer first, followed by supporting arguments, and finally the supporting evidence.

### Reciprocal Rank Fusion (RRF)
An algorithm used in hybrid search pipelines. It combines the ranked results of multiple search algorithms (e.g., dense vector search and BM25 keyword search) into a single, optimized rank list by summing the reciprocals of their individual ranks.

### Salting
A distributed computing optimization technique to resolve data skew. It appends a random integer (the "salt") to the join keys of a skewed dataset, spreading the work evenly across multiple CPU executors.

### Shared VPC
A networking feature in Google Cloud that allows an organization to associate multiple projects with a single virtual network. A host project manages the subnets and route tables, while service projects deploy resources (like GKE clusters) directly into those shared subnets.

### Shuffle Partitioning
The process in distributed computing (such as Spark or MapReduce) where data is redistributed across network nodes to execute operations like Joins or Aggregations. Misconfigured shuffle boundaries on skewed data cause execution bottlenecks and OOM errors.

### Silver Zone
The processing layer in the Medallion Architecture. It cleans, types, schema-enforces, and deduplicates raw data from the Bronze zone, creating the single source of truth for the organization.

### VPC Service Controls (VPC SC)
A Google Cloud security service that defines a logical perimeter around managed APIs (like BigQuery and Cloud Storage), preventing data exfiltration and blocking access from unauthorized projects or networks.

### Workload Identity Federation
A secure authentication protocol in Kubernetes and Google Cloud. It maps a Kubernetes Service Account (KSA) inside a cluster directly to a Google Cloud IAM Service Account (GSA) at runtime, eliminating the need to store long-lived JSON credentials.

---

## 2. Recommended Reading & Bibliography

### Systems & Data Engineering

#### Kleppmann, Martin. *Designing Data-Intensive Applications*. O'Reilly Media, 2017.
*   **Why read:** The absolute "Bible" for understanding database storage engines, index mechanics, replication, distributed system consensus, and data processing models. Critical for the data engineering portion of the FDE stack.

#### Google SRE Team. *Site Reliability Engineering: How Google Runs Production Systems*. O'Reilly Media, 2016.
*   **Why read:** Establishes the operational mindset for monitoring, alerting, error budgets, and incident management. Essential for ensuring client deployments remain stable after hand-off.

#### Brooks, Frederick P. *The Mythical Man-Month: Essays on Software Engineering*. Addison-Wesley, 1995.
*   **Why read:** Focuses on the human element of software engineering, scheduling traps, and the architectural distinction between conceptual integrity and implementation detail. Essential for FDEs managing complex timelines at client sites.

#### Codd, Edgar F. *"A Relational Model of Data for Large Shared Data Banks."* Communications of the ACM, 1970.
*   **Why read:** The seminal whitepaper that introduced relational database algebra. Understanding these foundations is critical for FDEs tasked with auditing legacy relational systems and optimizing join operations.

---

### Communication & Business Strategy

#### Minto, Barbara. *The Minto Pyramid Principle: Logic in Writing, Thinking and Problem Solving*. Minto International, 1996.
*   **Why read:** The foundational text for executive communication. Teaches how to structure written and oral reports to communicate technical recommendations to C-suite buyers effectively.

#### Maister, David H., Charles H. Green, and Robert M. Galford. *The Trusted Advisor*. Free Press, 2000.
*   **Why read:** Explores how to transition from a technical vendor to a strategic partner. Provides frameworks for defusing stakeholder resistance and building trust.

---

### Whitepapers & Technical Documentation

#### Palantir Technologies. *"Dev versus Delta: Demystifying Engineering Roles at Palantir."* Palantir Blog, 2019.
*   **Why read:** The origin story of the Forward Deployed Engineering role. Details the architectural separation of platform and integration layers.

#### Anthropic Engineering. *"Demystifying Evals for AI Agents."* Anthropic Research, 2024.
*   **Why read:** A deep dive into why manual vibes-testing fails for AI agents and how to build automated evaluation suites for non-deterministic LLM chains.

#### Google Cloud. *"Google Cloud Architecture Framework."* Google Cloud Documentation, 2025.
*   **Why read:** The definitive reference guide for GCP system design, outlining security best practices, cost optimization, and GKE design patterns.

#### Vaswani, Ashish, et al. *"Attention Is All You Need."* Advances in Neural Information Processing Systems, 2017.
*   **Why read:** The original research paper that introduced the Transformer architecture, which forms the basis for modern Large Language Models and embedding generators used in RAG systems.
