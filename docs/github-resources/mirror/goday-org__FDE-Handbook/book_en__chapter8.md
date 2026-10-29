<!-- fde-scope mirror · repo: goday-org/FDE-Handbook · license: MIT · commit: 229db7b57e3362f3a66c3b757b1cb0c264e69535
     upstream path: book_en/chapter8.md · retrieved: 2026-10-06 · verbatim; report issues upstream. -->

# Chapter 8: Multi-Agent Orchestration & Custom Tools

Single-prompt LLM interactions are insufficient for executing complex, multi-step enterprise workflows. If an application must audit a database table, generate a reconciliation report, and email the results to a department manager, a single LLM call will struggle to plan and execute these actions reliably. FDEs resolve this by deploying **Multi-Agent Systems**.

In a multi-agent architecture, complex operations are broken down into specialized agents (e.g., a Database Query Agent, a Data Validation Agent, and a Reporting Agent) that collaborate. These agents use custom tools to interact with external APIs, maintain shared state, and handle execution errors dynamically.

This chapter details the multi-agent architectural patterns, provides a complete LangGraph Python implementation of a cooperative agent loop, and outlines error-handling strategies.

---

## 1. Multi-Agent Collaboration Topology

In production systems, agents coordinate using a **Supervisor-Worker** or **Peer-to-Peer Network** topology. Under the Supervisor model, a central supervisor agent receives user input, delegates sub-tasks to specialized worker agents, collects their findings, and returns the final output.


<svg viewBox="0 0 750 250" width="100%" height="auto" style="background-color: #fafafa; border: 1px solid #e1e1e8; border-radius: 4px; margin: 20px 0; display: block;">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#333" />
    </marker>
  </defs>

  <!-- User Input -->
  <rect x="20" y="90" width="110" height="60" fill="#f4f4f6" stroke="#333" stroke-width="2" rx="6" />
  <text x="75" y="125" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="11" fill="#111">User Goal</text>

  <!-- Connection to Supervisor -->
  <line x1="130" y1="120" x2="200" y2="120" stroke="#333" stroke-width="1.5" marker-end="url(#arrow)" />

  <!-- Supervisor Node -->
  <rect x="210" y="65" width="160" height="110" fill="#e8f0fe" stroke="#1a73e8" stroke-width="2" rx="6" />
  <text x="290" y="90" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="12" fill="#1a73e8">SUPERVISOR AGENT</text>
  <text x="290" y="115" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#333">Plans execution steps</text>
  <text x="290" y="130" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#333">Delegates sub-tasks</text>
  <text x="290" y="145" text-anchor="middle" font-family="monospace" font-size="8" fill="#1a73e8">State Coordinator</text>

  <!-- Split paths from Supervisor to Worker Agents -->
  <path d="M 370 120 L 460 60" fill="none" stroke="#333" stroke-width="1.5" marker-end="url(#arrow)" />
  <path d="M 370 120 L 460 120" fill="none" stroke="#333" stroke-width="1.5" marker-end="url(#arrow)" />
  <path d="M 370 120 L 460 180" fill="none" stroke="#333" stroke-width="1.5" marker-end="url(#arrow)" />

  <!-- Worker Agent 1: DBA Agent -->
  <rect x="470" y="30" width="220" height="50" fill="#fff" stroke="#666" rx="4" />
  <text x="580" y="50" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="10">Database Agent (Executes SQL)</text>
  <text x="580" y="68" text-anchor="middle" font-family="monospace" font-size="8" fill="#666">Tool: postgres_query</text>

  <!-- Worker Agent 2: Validator Agent -->
  <rect x="470" y="95" width="220" height="50" fill="#fff" stroke="#666" rx="4" />
  <text x="580" y="115" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="10">Validation Agent (dbt schema check)</text>
  <text x="580" y="133" text-anchor="middle" font-family="monospace" font-size="8" fill="#666">Tool: dbt_assert_runner</text>

  <!-- Worker Agent 3: SRE Agent -->
  <rect x="470" y="160" width="220" height="50" fill="#fff" stroke="#666" rx="4" />
  <text x="580" y="180" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="10">Notification Agent (Slack / Pager)</text>
  <text x="580" y="198" text-anchor="middle" font-family="monospace" font-size="8" fill="#666">Tool: pager_dispatch</text>
</svg>

Managing communications between these nodes requires a formal framework. Using **LangGraph** allows the FDE to define agent states as cyclic graphs, preventing infinite loops while enabling structured state validation at each transition.

---

## 2. Multi-Agent Programming: Cooperative State Machines

Below is a complete Python script implementing a multi-agent system using state management patterns. It demonstrates a supervisor agent orchestrating a database retrieval agent and a verification agent to process customer queries.

```python
# multi_agent_orchestrator.py
from typing import Dict, TypedDict, List
import json

# Define the shared state dictionary passed between agents
class AgentState(TypedDict):
    original_query: str
    sql_query: str
    query_result: List[Dict]
    validation_status: str
    final_answer: str
    errors: List[str]

# Define worker tools
def execute_sql_tool(state: AgentState) -> AgentState:
    print("\n[DB Agent] Reviewing query schema...")
    query = state.get("sql_query", "")
    
    # Simple query parsing to prevent sql injection vulnerabilities
    if "DROP" in query.upper() or "DELETE" in query.upper():
        state["errors"].append("Unauthorized SQL instruction blocked.")
        state["validation_status"] = "FAILED"
        return state
        
    # Mock database retrieval action
    print(f"[DB Agent] Querying: {query}")
    state["query_result"] = [
        {"customer_id": "CUST_01", "balance": 50000},
        {"customer_id": "CUST_02", "balance": 12000}
    ]
    state["validation_status"] = "PENDING_VALIDATION"
    return state

def validate_results_tool(state: AgentState) -> AgentState:
    print("\n[Validator Agent] Auditing query output values...")
    results = state.get("query_result", [])
    
    # Assert validation rules on payload fields
    for row in results:
        if row.get("balance", 0) < 0:
            state["errors"].append(f"Invalid record detected: Negative balance for {row.get('customer_id')}")
            state["validation_status"] = "FAILED"
            return state
            
    state["validation_status"] = "PASSED"
    return state

# Supervisor Controller (Routing Logic)
def run_orchestrator(query: str):
    # Initialize the shared state
    state: AgentState = {
        "original_query": query,
        "sql_query": "SELECT customer_id, balance FROM accounts WHERE balance > 10000",
        "query_result": [],
        "validation_status": "START",
        "final_answer": "",
        "errors": []
    }
    
    # Step 1: Trigger Database Retrieval Agent
    state = execute_sql_tool(state)
    if "FAILED" in state["validation_status"]:
        print(f"[Supervisor] Processing halted: {state['errors'][-1]}")
        return
        
    # Step 2: Trigger Validation Agent
    state = validate_results_tool(state)
    if state["validation_status"] == "FAILED":
        print(f"[Supervisor] Processing halted: {state['errors'][-1]}")
        return
        
    # Step 3: Format final response
    if state["validation_status"] == "PASSED":
        state["final_answer"] = f"Audited {len(state['query_result'])} customer records. Values validated."
        print(f"\n[Supervisor] Process Complete: {state['final_answer']}")

if __name__ == "__main__":
    run_orchestrator("Find all balances exceeding 10000")
```

---

## 3. Error Handling and Token Optimization

Production-grade agent frameworks must implement strategies to manage operational costs and ensure resilience.

### 1. Handling Tool Exceptions (Self-Healing)
If a database query fails because of a missing comma or incorrect column name, the Agent should not crash. Instead, the exception message should be fed back into the agent's context, allowing the LLM to inspect the database schema, correct the syntax, and retry the execution.

```
[Agent] Executing SQL -> [DB Engine] Error: column 'cust_name' does not exist
[Supervisor] Feed error to context -> [Agent] "Ah, the column name is 'customer_name'. Let me correct it."
[Agent] Executing corrected SQL -> [DB Engine] Success
```

### 2. Token Conservation and Context Window Management
As agents run in loops, their prompt histories grow quickly, increasing token costs and causing latency to escalate. FDEs manage context windows using two techniques:
* **Message Truncation**: Dropping intermediate tool execution outputs from the context window once their results have been summarized.
* **Semantic Summary Memory**: Condensing historical execution steps into a single paragraph summary at regular intervals, keeping the active context window small.

---

## Summary

Multi-agent coordination is necessary for executing complex enterprise workflows. By structuring agent loops as state machines, parsing tool errors for self-healing, and implementing context conservation strategies, FDEs build resilient, cost-effective agent systems that run reliably in production.
