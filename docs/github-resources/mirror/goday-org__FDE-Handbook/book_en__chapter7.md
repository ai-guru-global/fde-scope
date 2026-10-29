<!-- fde-scope mirror · repo: goday-org/FDE-Handbook · license: MIT · commit: 229db7b57e3362f3a66c3b757b1cb0c264e69535
     upstream path: book_en/chapter7.md · retrieved: 2026-10-06 · verbatim; report issues upstream. -->

# Chapter 7: Enterprise RAG (Retrieval-Augmented Generation) Blueprint

Applying generative AI to enterprise datasets requires a robust retrieval architecture. Simply feeding thousands of PDF files into an LLM context window results in poor response accuracy, high token costs, and context window exhaustion. To scale LLM systems, FDEs deploy **Retrieval-Augmented Generation (RAG)** systems.

A production-grade enterprise RAG system must handle complex, multi-modal documents (such as PDFs containing tables, diagrams, and scanned text), execute fast searches across millions of records using hybrid retrieval methodologies, and run securely within private networking boundaries.

This chapter outlines the enterprise RAG architecture, provides a complete Python script for document ingestion using LlamaParse, details hybrid retrieval using dense vector search and sparse BM25 retrieval, and implements the Reciprocal Rank Fusion (RRF) algorithm.

---

## 1. Hybrid Search Architecture

To ensure high retrieval recall and precision, enterprise RAG platforms combine two distinct search methodologies:
1. **Dense Vector Search (Semantic Retrieval)**: Uses deep learning embeddings (e.g., from Vertex AI text-embeddings API) to capture semantic meaning. It excels at finding conceptually similar matches even if the query uses different words.
2. **Sparse Retrieval (Keyword Matching)**: Uses statistical keyword matching (e.g., BM25). It excels at matching exact product codes, acronyms, and unique serial numbers that vector embeddings might miss.


<svg viewBox="0 0 750 250" width="100%" height="auto" style="background-color: #fafafa; border: 1px solid #e1e1e8; border-radius: 4px; margin: 20px 0; display: block;">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#333" />
    </marker>
  </defs>

  <!-- Query Input -->
  <rect x="20" y="90" width="120" height="60" fill="#f4f4f6" stroke="#333" stroke-width="2" rx="6" />
  <text x="80" y="115" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="12" fill="#111">User Query</text>
  <text x="80" y="132" text-anchor="middle" font-family="monospace" font-size="9" fill="#555">"GKE PSC setup"</text>

  <!-- Query Split -->
  <path d="M 140 120 L 220 60" fill="none" stroke="#333" stroke-width="1.5" marker-end="url(#arrow)" />
  <path d="M 140 120 L 220 180" fill="none" stroke="#333" stroke-width="1.5" marker-end="url(#arrow)" />

  <!-- Dense Pipeline -->
  <rect x="230" y="30" width="180" height="60" fill="#fff" stroke="#1a73e8" rx="4" />
  <text x="320" y="55" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="11" fill="#1a73e8">Dense Embeddings Search</text>
  <text x="320" y="72" text-anchor="middle" font-family="monospace" font-size="9" fill="#666">Vector Index (Semantic)</text>

  <!-- Sparse Pipeline -->
  <rect x="230" y="150" width="180" height="60" fill="#fff" stroke="#1a73e8" rx="4" />
  <text x="320" y="175" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="11" fill="#1a73e8">Sparse BM25 Search</text>
  <text x="320" y="192" text-anchor="middle" font-family="monospace" font-size="9" fill="#666">Lucene / Elasticsearch (Keyword)</text>

  <!-- Connect to Fusion -->
  <path d="M 410 60 L 490 120" fill="none" stroke="#333" stroke-width="1.5" marker-end="url(#arrow)" />
  <path d="M 410 180 L 490 120" fill="none" stroke="#333" stroke-width="1.5" marker-end="url(#arrow)" />

  <!-- Fusion & Rerank -->
  <rect x="500" y="90" width="220" height="70" fill="#e8f5e9" stroke="#2e7d32" stroke-width="2" rx="6" />
  <text x="610" y="115" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="12" fill="#2e7d32">Reciprocal Rank Fusion (RRF)</text>
  <text x="610" y="132" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#333">&amp; Cross-Encoder Reranking</text>
  <text x="610" y="147" text-anchor="middle" font-family="monospace" font-size="9" fill="#666">Outputs Top-K Context chunks</text>
</svg>

The results of these two pipelines are merged using Reciprocal Rank Fusion (RRF), which recalculates relevance ranks, and sorted using a Cross-Encoder Reranker model before being sent to the LLM.

---

## 2. Ingestion & Document Parsing with LlamaParse

Enterprise documents (like PDF manuals and system specifications) frequently contain tables and two-column layouts. Standard text splitters read tables row-by-row, which destroys table cell relationships. FDEs resolve this by using **LlamaParse** to extract documents as structured Markdown, preserving tables in clean Markdown formatting.

Below is a complete Python script for parsing PDFs, splitting markdown content, and generating embeddings using Vertex AI.

```python
# ingestion_pipeline.py
import os
from llama_parse import LlamaParse
from langchain.text_splitter import MarkdownTextSplitter
from google.cloud import aiplatform
from google.cloud.aiplatform.models import Prediction

def initialize_vertex_ai(project_id, location):
    aiplatform.init(project = project_id, location = location)

def parse_pdf_to_markdown(file_path, api_key):
    # Configure LlamaParse to extract structured Markdown tables
    parser = LlamaParse(
        api_key=api_key,
        result_type="markdown",
        verbose=True,
        language="en"
    )
    documents = parser.load_data(file_path)
    return documents[0].text

def split_markdown_content(markdown_text):
    # Split text using markdown boundary rules (headers, lists)
    text_splitter = MarkdownTextSplitter(
        chunk_size=1000,
        chunk_overlap=150
    )
    chunks = text_splitter.split_text(markdown_text)
    return chunks

def generate_vertex_embeddings(texts, project_id):
    # Generate dense vector embeddings using Vertex AI text-embeddings API
    from vertexai.language_models import TextEmbeddingModel
    
    model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    embeddings = model.get_embeddings(texts)
    return [e.values for e in embeddings]

# Execution Demonstration
if __name__ == "__main__":
    API_KEY = os.environ.get("LLAMA_CLOUD_API_KEY", "mock_key")
    PROJECT_ID = "service-project-id"
    
    # 1. Parse document
    print("Parsing enterprise PDF specs...")
    raw_md = parse_pdf_to_markdown("specs.pdf", API_KEY)
    
    # 2. Split text
    print("Splitting Markdown content into chunks...")
    chunks = split_markdown_content(raw_md)
    
    # 3. Generate embeddings
    print("Generating dense embeddings using Vertex AI...")
    embeddings = generate_vertex_embeddings(chunks[:3], PROJECT_ID)
    print(f"Generated {len(embeddings)} vectors. Vector dimensions: {len(embeddings[0])}")
```

---

## 3. Merging Search Results: Reciprocal Rank Fusion (RRF)

Reciprocal Rank Fusion (RRF) combines search results from multiple pipelines (dense vector search and sparse BM25 keyword matching) without requiring normalized search scores.

The RRF score for a document $d \in D$ is calculated as:
$$RRF\_Score(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
Where $r_m(d)$ is the rank of document $d$ in search pipeline $m$ (1-indexed), and $k$ is a constant (typically set to 60) that reduces the impact of low-ranked outliers.

Below is the Python implementation of the RRF algorithm.

```python
# reciprocal_rank_fusion.py

def reciprocal_rank_fusion(dense_results, sparse_results, k=60):
    """
    Combines search results from dense and sparse pipelines.
    
    dense_results: Ordered list of document IDs from vector search.
    sparse_results: Ordered list of document IDs from BM25 keyword search.
    """
    rrf_scores = {}
    
    # Process dense vector search results
    for rank, doc_id in enumerate(dense_results, start=1):
        if doc_id not in rrf_scores:
            rrf_scores[doc_id] = 0.0
        rrf_scores[doc_id] += 1.0 / (k + rank)
        
    # Process sparse keyword search results
    for rank, doc_id in enumerate(sparse_results, start=1):
        if doc_id not in rrf_scores:
            rrf_scores[doc_id] = 0.0
        rrf_scores[doc_id] += 1.0 / (k + rank)
        
    # Sort documents by their calculated RRF score in descending order
    sorted_docs = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)
    return sorted_docs

# Verification Execution
if __name__ == "__main__":
    # Mock doc IDs returned by the search pipelines
    dense_hits = ["doc_A", "doc_B", "doc_C", "doc_D"]
    sparse_hits = ["doc_C", "doc_A", "doc_E", "doc_F"]
    
    fused_results = reciprocal_rank_fusion(dense_hits, sparse_hits, k=60)
    print("Fused Results (Doc ID, RRF Score):")
    for doc, score in fused_results:
        print(f" - {doc}: {score:.5f}")
```

In this scenario, `doc_C` and `doc_A` rank highly because they were retrieved by both search pipelines, ensuring the most relevant context is prioritized.

---

## Summary

Production-grade RAG systems require robust document ingestion pipelines and precise search mechanics. By using LlamaParse to extract structured tables, combining vector search with keyword matching using Reciprocal Rank Fusion, and securing connections within VPC SC boundaries, FDEs build scalable RAG architectures that deliver accurate, secure context retrieval for enterprise applications.
