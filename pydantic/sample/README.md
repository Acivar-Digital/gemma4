# Pydantic AI 2.0 Batch LLM Processing Scaffolding

This directory contains reference scaffolding demonstrating how to orchestrate high-throughput, resilient batch LLM intelligence pipelines using **Pydantic AI 2.0** and **Pydantic Graph**.

---

## Architecture Overview

```text
sample/
├── runner.py            # High-throughput batch worker pool (HTTP/2 isolation, 429 backoff)
├── storage.py           # Atomic I/O (os.fsync), JSONL checkpoints, staging cache auto-purge
├── preflight.py         # Multi-point health checks (gateway, DB, environment)
├── models.py            # Strict Pydantic V2 schemas (extra='forbid') for input/output contracts
├── stages.py            # Pydantic AI Agent definitions, prompt construction, parsing
├── config.py            # Model configurations, concurrency, timeouts, and directories
├── generate_template.py # Top-level CLI entrypoint with customizable flags
├── SKILL.md             # Operational playbook & architectural invariants
├── PROMPT.md            # Exemplars and rubric guidelines
└── rag_tools.py         # Zero-LLM vector search / retrieval tools
```

---

## Core Invariants for LLM Agents

### 1. Dedicated HTTP/2 Client Isolation (`runner.py`)
Sharing a single `httpx.AsyncClient(http2=True)` across concurrent coroutines causes socket contention. Each worker lane in the pool creates and owns its dedicated client:
```python
worker_client = httpx.AsyncClient(http2=True, timeout=120.0)
worker_model = clone_model_with_client(base_model, worker_client)
```

### 2. Zero SDK Micro-Retries (`max_retries = 0`)
Disable SDK-level fast retries so rate limits immediately surface to the macro backoff scheduler:
```python
orig_provider.client.max_retries = 0
```

### 3. Key-Hopping & Jittered Exponential Backoff
On HTTP 429 / rate limits, quarantine the key, hop to the next available key, and apply jittered backoff:
$$\text{delay} = (\text{initial\_delay} \times \text{factor}^{\text{attempt}-1}) \times \text{Uniform}(0.75, 1.25)$$

### 4. Streaming Token Execution with Fallback
Prevent idle reverse proxy socket drops (30–60s timeouts) on long structured generations by using `agent.run_stream()`:
```python
async with agent.run_stream(prompt, model=model) as stream_result:
    raw_output = await stream_result.get_output()
    return _parse_output(raw_output)
```

### 5. Strict Pydantic V2 Contract
All input/output schemas enforce zero hallucinated attributes:
```python
model_config = ConfigDict(extra="forbid", validate_assignment=True)
```
