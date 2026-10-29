<!-- fde-scope mirror · repo: goday-org/FDE-Handbook · license: MIT · commit: 229db7b57e3362f3a66c3b757b1cb0c264e69535
     upstream path: book_en/chapter9.md · retrieved: 2026-10-06 · verbatim; report issues upstream. -->

# Chapter 9: Evaluation and Verification of LLM Systems

Unlike traditional software systems where outputs are deterministic, generative AI applications are probabilistic. An agent prompt that works perfectly today may produce incorrect outputs tomorrow due to model updates, changes in retrieval context, or variations in user input. In enterprise settings, deploying AI without continuous validation represents a significant risk.

To manage this, FDEs implement a dual-loop evaluation framework: an **Inner Loop** for developer validation during prototyping, and an **Outer Loop** for automated validation of production logs.

This chapter details the two-loop evaluation methodology, outlines key RAG metrics, provides a complete Python implementation of an LLM-as-a-judge evaluation suite, and explains the AutoSxS (Side-by-Side) pattern.

---

## 1. The Two-Loop Evaluation Lifecycle

To ensure AI applications perform reliably from prototype to production, FDEs deploy evaluation pipelines across two cycles:


<svg viewBox="0 0 750 250" width="100%" height="auto" style="background-color: #fafafa; border: 1px solid #e1e1e8; border-radius: 4px; margin: 20px 0; display: block;">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#333" />
    </marker>
  </defs>

  <!-- Inner Loop (Dev-time) -->
  <rect x="30" y="40" width="310" height="170" fill="#f4f4f6" stroke="#333" stroke-width="2" rx="6" />
  <text x="185" y="60" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="12" fill="#111">INNER LOOP (Developer Evaluation)</text>
  
  <rect x="50" y="80" width="270" height="40" fill="#fff" stroke="#666" rx="4" />
  <text x="185" y="105" text-anchor="middle" font-family="sans-serif" font-size="10">Test-driven development (Golden Dataset)</text>
  
  <rect x="50" y="140" width="270" height="40" fill="#fff" stroke="#666" rx="4" />
  <text x="185" y="165" text-anchor="middle" font-family="sans-serif" font-size="10">Ad-hoc evaluations on 50+ queries</text>

  <!-- Transition -->
  <line x1="340" y1="125" x2="400" y2="125" stroke="#333" stroke-width="2" marker-end="url(#arrow)" />
  <text x="370" y="115" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#666" font-weight="bold">Release</text>

  <!-- Outer Loop (Production-time) -->
  <rect x="410" y="40" width="310" height="170" fill="#e8f5e9" stroke="#2e7d32" stroke-width="2" rx="6" />
  <text x="565" y="60" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="12" fill="#2e7d32">OUTER LOOP (Production Guardrails)</text>
  
  <rect x="430" y="80" width="270" height="40" fill="#fff" stroke="#2e7d32" rx="4" />
  <text x="565" y="105" text-anchor="middle" font-family="sans-serif" font-size="10">Automated runbook audits (1000+ logs)</text>
  
  <rect x="430" y="140" width="270" height="40" fill="#fff" stroke="#2e7d32" rx="4" />
  <text x="565" y="165" text-anchor="middle" font-family="sans-serif" font-size="10">Continuous metric validation &amp; alert thresholds</text>
</svg>

1. **The Inner Loop (Development Time)**: Focuses on quick iteration. The developer tests changes against a curated **Golden Dataset** (typically 50-100 high-priority query-context-response pairs) using an evaluation script to verify that performance does not regress.
2. **The Outer Loop (Production Time)**: Runs asynchronously in production. It samples live conversation logs, passing them to an evaluation pipeline to monitor performance metrics at scale. If metrics fall below defined thresholds, alert notifications are triggered.

---

## 2. Core Metrics for RAG Systems

FDEs validate RAG applications using three key metrics:
1. **Faithfulness (Groundedness)**: Measures whether the generated answer is derived *only* from the retrieved context. It prevents the model from introducing outside information (hallucinations).
$$\text{Faithfulness} = \frac{\text{Number of statements in answer supported by context}}{\text{Total number of statements in answer}}$$
2. **Answer Relevance**: Measures whether the generated response directly addresses the user's query.
$$\text{Answer Relevance} = \text{Cosine Similarity}(\text{Embedding(Answer)}, \text{Embedding(Query)}) $$
3. **Context Recall**: Measures whether the retrieval pipeline successfully extracted all relevant information needed to answer the query.
$$\text{Context Recall} = \frac{\text{Number of ground-truth statements found in retrieved context}}{\text{Total number of ground-truth statements}}$$

---

## 3. Implementation: LLM-As-A-Judge Evaluation Suite

To automate evaluation at scale, FDEs use an **LLM-as-a-Judge** pattern. A highly capable model (like Gemini 1.5 Pro) is configured with specific criteria prompts to analyze and score responses generated by other models.

Below is a complete Python script implementing an LLM-as-a-judge pipeline to evaluate Faithfulness.

```python
# evaluation_suite.py
import json
import os
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel

def get_judge_response(prompt: str) -> str:
    # Initialize the judge model (Gemini 1.5 Pro)
    model = GenerativeModel("gemini-1.5-pro-002")
    response = model.generate_content(prompt)
    return response.text

# Define the judge evaluation prompt template
JUDGE_TEMPLATE = """
You are an expert system auditor. Analyze the provided Context and Answer, and evaluate the Faithfulness of the answer.

[Context]
{context}

[Answer]
{answer}

Your task is to:
1. Extract all discrete statements made in the Answer.
2. For each statement, verify if it is directly supported by the Context.
3. Calculate the Faithfulness Score (supported statements divided by total statements).

Return your analysis ONLY as a valid JSON object matching this structure:
{{
  "statements": [
    {{
      "statement": "The GKE subnet range is 10.100.0.0/20",
      "supported": true,
      "explanation": "Supported by the first sentence of the context."
    }}
  ],
  "faithfulness_score": 1.0
}}
"""

def evaluate_faithfulness(context: str, answer: str) -> float:
    formatted_prompt = JUDGE_TEMPLATE.format(context=context, answer=answer)
    raw_response = get_judge_response(formatted_prompt)
    
    try:
        # Parse JSON output from the judge
        clean_json = raw_response.strip().replace("```json", "").replace("```", "")
        data = json.loads(clean_json)
        return data.get("faithfulness_score", 0.0)
    except Exception as e:
        print(f"Error parsing judge response: {e}")
        return 0.0

# Execution Demonstration
if __name__ == "__main__":
    mock_context = (
        "Shared VPC subnet is allocated at 10.100.0.0/20. "
        "Workload Identity maps KSAs to GSAs without static json key files."
    )
    
    # Example 1: Grounded response (Faithful)
    faithful_answer = "We use GKE Workload Identity to map KSAs to GSAs, which avoids json key files."
    score_1 = evaluate_faithfulness(mock_context, faithful_answer)
    print(f"Faithfulness Score 1: {score_1:.2f}")

    # Example 2: Hallucinated response (Unfaithful)
    hallucinated_answer = "Shared VPC subnet is allocated at 10.100.0.0/20 and connects to AWS VPC via VPN."
    score_2 = evaluate_faithfulness(mock_context, hallucinated_answer)
    print(f"Faithfulness Score 2: {score_2:.2f}")
```

---

## 4. The AutoSxS (Side-by-Side) Pattern

When upgrading a platform's underlying model (e.g., transitioning from Gemini 1.0 to Gemini 1.5), FDEs use the **AutoSxS (Auto Side-by-Side)** pattern to validate the upgrade.

Instead of scoring responses in isolation, AutoSxS feeds the same query and context to both models (Model A and Model B), and asks the judge model to compare their outputs directly, declaring a winner and providing a detailed explanation.

### AutoSxS Comparison Criteria
* **Correctness**: Which model's response matches the reference answer more accurately?
* **Completeness**: Did one model address parts of the query that the other missed?
* **Conciseness**: Did a model introduce unnecessary verbosity or filler text?
* **Safety**: Are both responses free of security and bias issues?

Running AutoSxS across a golden dataset provides a clear win-rate percentage, allowing the FDE to verify model upgrades before deploying them to production.

---

## Summary

Generative AI applications require continuous validation to run reliably at scale. By implementing a dual-loop evaluation framework, tracking key metrics like Faithfulness and Context Recall, using LLM-as-a-judge pipelines to automate evaluations, and applying the AutoSxS pattern to validate model upgrades, FDEs ensure their platforms deliver consistent, accurate results in production.
