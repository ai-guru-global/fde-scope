<!-- fde-scope mirror · repo: goday-org/FDE-Handbook · license: MIT · commit: 229db7b57e3362f3a66c3b757b1cb0c264e69535
     upstream path: README.md · retrieved: 2026-10-06 · verbatim; report issues upstream. -->

# Forward Deployed Engineering Handbook (FDE-Handbook)

> **Bridging Core Products and Client Realities in the Enterprise & AI Era**

---

Welcome to the **Forward Deployed Engineering Handbook (FDE-Handbook)**, an open-source publication and guide detailing the specialized skills, software architectures, security perimeters, and communication frameworks required to deploy high-value enterprise and AI platforms inside complex, highly secured client networks.

This handbook is designed for software engineers, solutions architects, technical consultants, and engineering leaders who want to master the art of client-embedded systems engineering.

---

## 📖 Downloads

The handbook is compiled and published in both English and Chinese. You can download the pre-compiled, publication-ready PDF volumes directly:

*   📘 **[English Version (PDF)](./fde_handbook_en.pdf)** (61 pages)
*   📕 **[Chinese Version (PDF)](./fde_handbook_zh.pdf)** (63 pages)

---

## 🗺️ Handbook Outline

The handbook is structured into 11 chapters, spanning soft consulting frameworks to hard cloud systems, networking, and LLM evaluation suites:

1.  **Chapter 1: The FDE Persona** — Defining the FDE hybrid identity, the "Dev vs. Delta" architectural boundary, and the five phases of the engagement lifecycle.
2.  **Chapter 2: Advisory Mindset & Stakeholder Diplomacy** — Structure problem-solving using MECE, communicate using Barbara Minto’s Pyramid Principle, establish the Minimum Viable Value (MVV), and align hostile DBA and SecOps teams.
3.  **Chapter 3: Enterprise Data Auditing & Schema Recovery** — Reverse-engineering undocumented legacy databases, tracing circular tree loops using Recursive CTEs, deduplicating history using window functions, and enforcing data quality using dbt assertions.
4.  **Chapter 4: Modern Data Architecture & Pipelines** — The Medallion Architecture, Lambda vs. Kappa designs, Columnar Data Warehouses, and resolving executor OOMs via Spark data salting.
5.  **Chapter 5: Secure Cloud Landing Zones** — Building enterprise infrastructure with Google Cloud Shared VPC, private GKE clusters, and Kubernetes Workload Identity.
6.  **Chapter 6: Hardening with VPC Service Controls** — Designing secure logical perimeters (VPC-SC), configuring inbound/outbound rules, and auditing exfiltration logs.
7.  **Chapter 7: Enterprise RAG (Retrieval-Augmented Generation)** — Processing complex document structures, implementing hybrid search (BM25 + Dense Vector), and rank fusion via Reciprocal Rank Fusion (RRF).
8.  **Chapter 8: Multi-Agent Orchestration & Core Workflows** — Designing stateful agent graphs using LangGraph, handling sub-agent task delegation via the Agent-to-Agent (A2A) protocol, and implementing human-in-the-loop gates.
9.  **Chapter 9: LLM System Evaluation & Guardrails** — Structuring development (inner loop) and production (outer loop) evaluation pipelines, implementing LLM-as-a-Judge scoring, and measuring system updates using AutoSxS win-rate analytics.
10. **Chapter 10: Case Studies & Production Readiness** — Real-world migrations (porting legacy stored procedures to dbt/BigQuery, deploying Private RAG on GKE), and executing operations handovers with runbooks.
11. **Chapter 11: Glossary & Bibliography** — Deep dive definition manual for core FDE/cloud networking terms and annotated reading guides.

---

## 🛠️ Local Compilation

The handbook features beautiful inline vector diagrams (SVGs) and code blocks. If you wish to edit the markdown files and rebuild the PDFs locally, you can use the provided compiler script.

### Prerequisites

1.  **Python 3.8+**
2.  **pip dependencies**:
    ```bash
    pip install markdown playwright
    ```
3.  **Playwright Chromium compiler**:
    ```bash
    playwright install chromium
    ```

### Compilation Command

Run the compilation script in the root directory:

```bash
python3 compile_pdf.py
```

This script will:
1.  Read the chapters from `book_en/` and `book_zh/`.
2.  Dynamically map chapter titles and section subheadings to generate unique anchor IDs.
3.  Generate the interactive, multi-level **Table of Contents** with active page links.
4.  Isolate inline SVG code blocks from markdown translation to preserve raw vector output.
5.  Compile the custom layout, serif cover sheets, page headers/footers, and margins using Playwright Chromium to output `fde_handbook_en.pdf` and `fde_handbook_zh.pdf`.

---

## 📁 Repository Structure

```text
├── book_en/               # English chapter Markdown files
├── book_zh/               # Chinese chapter Markdown files
├── compile_pdf.py         # Playwright compilation script
├── cover_giraffe.png      # Cover illustration asset
├── fde_handbook_en.pdf    # Compiled English PDF
└── fde_handbook_zh.pdf    # Compiled Chinese PDF
```

---

## ⚖️ License

*   **Compiler Code (`compile_pdf.py`)**: Distributed under the [MIT License](./LICENSE).
*   **Handbook Content (`book_en/`, `book_zh/` chapters)**: Distributed under the [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)](https://creativecommons.org/licenses/by-nc-sa/4.0/) License.
