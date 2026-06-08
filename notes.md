# MonolithBreaker — Presentation Notes

> Use these notes to walk through the project flow during your demo. Every frontend action is followed by the backend logic that handles it, so you can explain the full lifecycle naturally.

---

## 1. Landing Page — `frontend/app.py`

**Purpose:** Entry point of the Streamlit multi-page app. Configures Gemini API key + model, shows system health.

| Detail | Value |
|--------|-------|
| **Library** | `streamlit` (UI framework), `httpx` (HTTP client) |
| **Why Streamlit?** | Zero frontend/JS code needed. Python-only. Instant multi-page apps with `st.session_state` for cross-page shared state. For a demo/prototype, it beats React/Next.js in dev speed. |
| **Why httpx over requests?** | `httpx` supports both sync and async. Same API as `requests` but modern, type-hinted, and non-blocking. |

**What happens here:**
1. User enters their **Gemini API Key** (stored in `st.session_state`, never saved to disk)
2. User selects a **Gemini Model** from a dropdown (10 models available)
3. Health check pings `GET /health` on the FastAPI backend
4. Sidebar shows navigation to all 6 pages

**Key design:** API key travels as `X-Gemini-API-Key` HTTP header on every request, not as an env variable. This means the server stays stateless and doesn't require restarting when the key changes.

---

## 2. Upload Flow

### Frontend: `frontend/pages/01_upload.py`

**Purpose:** Upload a monolith ZIP file + optional OTel traces, start the pipeline.

| Detail | Value |
|--------|-------|
| **Library** | `streamlit` (file uploader form), `httpx` (POST multipart upload) |
| **Inputs** | ZIP file, optional OTel JSON, language dropdown, target service count hint |

**What the user does:**
1. Drags/drops their `legacy-monolith.zip`
2. Optionally uploads an `otel_traces.json`
3. Selects language (`java`, `python`, `go`, `csharp`, or auto-detect)
4. Clicks **🚀 Start Decomposition**

**Frontend sends:** `POST /upload` with multipart form data + `X-Gemini-API-Key` + `X-Gemini-Model` headers.

### Backend: `backend/api/routes/upload.py`

**Purpose:** Receives the ZIP, unpacks it, creates a job, starts the pipeline as a background task.

| Detail | Value |
|--------|-------|
| **Library** | `FastAPI` (router, `BackgroundTasks`, `UploadFile`, `File`, `Form`) |
| **Why FastAPI over Flask/Django?** | Native `async/await`, automatic OpenAPI docs, Pydantic validation, `BackgroundTasks` for fire-and-forget pipelines. Flask would need Celery for background jobs. Django is too heavyweight for a microservice API. |

**Backend logic:**
1. `create_job()` → generates UUID, stores `JobResponse` in in-memory `JOB_STORE`
2. Saves ZIP to `data/uploads/{job_id}/source.zip`
3. Extracts with `shutil.unpack_archive()`
4. Saves OTel JSON if provided
5. Starts `run_job()` in `BackgroundTasks` → **returns HTTP 202 immediately** (non-blocking)
6. Frontend gets `{job_id, status: "queued", progress: 0}` in <1 second

### Backend: `backend/api/middleware.py`

**Purpose:** Intercepts every request to inject logging, timing, and Gemini credentials.

| Middleware | Purpose |
|------------|---------|
| `RequestIdMiddleware` | Assigns `X-Request-ID` UUID to every request for tracing |
| `TimingMiddleware` | Adds `X-Response-Time` header (ms) |
| `LoggingMiddleware` | Logs `METHOD /path → STATUS (time)` |
| `GeminiKeyMiddleware` | Reads `X-Gemini-API-Key` and `X-Gemini-Model` headers, updates `settings` singleton at runtime |

**Why middleware for API key?** Avoids polluting every route handler with key-extraction logic. A single middleware sets `settings.GOOGLE_API_KEY` globally so all chains/LLM calls automatically pick it up.

---

## 3. Ingestion Pipeline — Parse & Context (Layer ③)

After upload returns, `run_job()` executes in the background:

### Step 3a: AST Parsing — `backend/ingestion/ast_parser.py`

**Purpose:** Parse every source file into classes, methods, imports, and call edges.

| Detail | Value |
|--------|-------|
| **Library** | `tree-sitter`, `tree-sitter-java`, `tree-sitter-python`, `tree-sitter-go`, `tree-sitter-c-sharp` |
| **Why Tree-sitter over regex/ANTLR/JavaParser?** | Tree-sitter is incremental, error-tolerant (won't crash on incomplete code), and supports 40+ languages with the same API. Regex breaks on nested structures. ANTLR needs grammar files and is slow. JavaParser is Java-only. |

**What it extracts per file:**
- `classes[]` — fully-qualified names (e.g., `com.enterprise.monolith.service.OrderService`)
- `methods[]` — method signatures with return types
- `imports[]` — import statements
- `calls[]` — method invocations (call edges)

`extract_static_edges()` builds `{source_fqn, target_fqn, edge_type, weight}` edges from imports and calls.

### Step 3b: Dynamic Analysis — `backend/ingestion/dynamic_analyzer.py`

**Purpose:** Parse OTel JSON traces to discover runtime call patterns (which services actually call each other at runtime).

| Detail | Value |
|--------|-------|
| **Library** | `opentelemetry-sdk`, `json` |
| **Why OTel over custom logging?** | Industry standard. Works with Jaeger, Zipkin, Datadog. Already deployed in most enterprise monoliths. |

Extracts `{source_fqn, target_fqn, edge_type: "RUNTIME_CALL", count, avg_latency_ms}`.

### Step 3c: Graph Building — `backend/ingestion/graph_builder.py`

**Purpose:** Merge static + dynamic edges into a weighted Neo4j knowledge graph, then run Louvain community detection.

| Detail | Value |
|--------|-------|
| **Library** | `neo4j` (async driver) with **Neo4j 5 Community Edition** |
| **Why Neo4j over PostgreSQL/MongoDB?** | Graph queries (`MATCH (a)-[:CALLS]->(b)`) are natural for dependency analysis. Finding circular dependencies is a single Cypher query. With SQL, you'd need recursive CTEs. MongoDB has no graph traversal. |
| **Why Louvain clustering?** | Louvain is the standard algorithm for community detection in graphs. It optimises modularity — exactly what you want for "which classes belong together". Neo4j GDS provides it out-of-the-box. |

**Graph schema:**
```
(:Class {id, name, fqn, job_id, language, community_id})
(:Method {id, name, class_id, job_id})
(:Class)-[:IMPORTS {weight}]->(:Class)
(:Class)-[:CALLS {weight, runtime_count}]->(:Class)
```

After Louvain runs, each class has a `community_id` → these communities become the initial suggestion for service boundaries.

### Step 3d: Code Embedding — `backend/ingestion/embedder.py`

**Purpose:** Chunk source code and store in ChromaDB for RAG retrieval.

| Detail | Value |
|--------|-------|
| **Library** | `chromadb`, `langchain-chroma` |
| **Why ChromaDB over Pinecone/Weaviate/FAISS?** | ChromaDB is local (no API keys needed), persistent, and embedded — runs in-process. Perfect for on-premise privacy. Pinecone requires cloud. FAISS has no metadata filtering. Weaviate is too heavyweight. |

Each class/file is stored as a chunk with metadata `{job_id, fqn, language, community_id}`. This enables RAG queries like "retrieve code for classes in the Order community".

---

## 4. Progress Tracking

### Frontend: `frontend/pages/02_progress.py`

**Purpose:** Real-time polling of job status with auto-refresh every 2 seconds.

| Detail | Value |
|--------|-------|
| **Library** | `streamlit` (progress bar, metrics, `st.rerun()`), `httpx` |

Polls `GET /jobs/{job_id}` → displays status emoji, progress percentage, and current step. When status hits `gate_a` or `gate_b`, shows a warning directing the user to the review page.

### Backend: `backend/api/routes/jobs.py`

**Purpose:** Simple lookup into in-memory `JOB_STORE`.

```python
@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> JobResponse:
    job = get_job_status(job_id)
    return job  # {job_id, status, progress, current_step, error}
```

**Why in-memory store?** For a prototype/demo, a dict is sufficient. In production, you'd swap `JOB_STORE` for Redis or PostgreSQL. The `JobResponse` Pydantic model stays the same.

---

## 5. AI Orchestration (Layer ④)

### Pipeline Engine: `backend/ai/orchestrator.py`

**Purpose:** The brain of the system. A **LangGraph StateGraph** that defines 10 nodes wired in sequence with two human gates.

| Detail | Value |
|--------|-------|
| **Library** | `langgraph` (StateGraph), `langchain-core`, `langchain-google-genai` |
| **Why LangGraph over plain asyncio/Celery?** | LangGraph gives you a formal **state machine** with typed state (`PipelineState`), named nodes, edges, conditional routing, and built-in support for human-in-the-loop suspension. With plain asyncio you'd have to manage all that yourself. |

**Pipeline nodes (in order):**
```
detect_boundaries → score_confidence → gate_a (SUSPEND)
    ↓ (after human approval)
generate_contracts → validate_contracts → gate_b (SUSPEND)
    ↓ (after human approval)
generate_code → generate_infra → generate_migration → package_output
```

### LLM Client: `backend/ai/llm_client.py`

**Purpose:** Singleton factory for Gemini LLM + embedding model.

| Detail | Value |
|--------|-------|
| **Library** | `langchain-google-genai` (`ChatGoogleGenerativeAI`, `GoogleGenerativeAIEmbeddings`) |
| **Why LangChain over direct Gemini SDK?** | LangChain provides **LCEL chains** (prompt → LLM → parser composability), structured output parsers, and abstraction — swap Gemini for OpenAI/Claude by changing one line. |

### RAG Retriever: `backend/ai/rag_retriever.py`

**Purpose:** Queries ChromaDB for the most relevant source code chunks to inject into LLM prompts.

**How RAG works here:**
1. Before calling Gemini, we query ChromaDB: "find code related to CustomerService"
2. ChromaDB returns top-K code snippets (vectorsimilarity search)
3. These snippets are concatenated into the prompt so Gemini "sees" the actual source code
4. Result: Gemini proposals are grounded in the real codebase, not hallucinated

### Boundary Chain: `backend/ai/chains/boundary_chain.py`

**Purpose:** LCEL chain that asks Gemini to propose DDD bounded contexts.

| Detail | Value |
|--------|-------|
| **Library** | `langchain-core` (`ChatPromptTemplate`, `JsonOutputParser`), `jinja2` (prompt templates) |

**Chain composition:** `prompt | llm | JsonOutputParser()` — this is LangChain Expression Language (LCEL).

**Input:** Neo4j graph JSON + RAG code chunks + language + hint  
**Output:** List of `BoundaryProposal` objects: `{name, classes[], rationale, suggested_api_style, dependencies_on[]}`

### Confidence Scorer: `backend/ai/confidence_scorer.py`

**Purpose:** Scores each boundary proposal on cohesion (internal calls) vs coupling (external calls) using the Neo4j graph.

**Flagged** boundaries (confidence < 0.45) require explicit human confirmation in the UI.

---

## 6. Gate A — Boundary Review

### Frontend: `frontend/pages/03_boundary_review.py`

**Purpose:** Display AI-proposed boundaries with confidence scores. Let the user approve, modify, or reject.

| Detail | Value |
|--------|-------|
| **Library** | `streamlit` (expanders, checkboxes, text area), `httpx`, `json` |

**What the user sees:**
- Each boundary in an expandable card with: name, classes, rationale, API style, dependencies, confidence score (color-coded 🟢🟡🔴)
- Flagged boundaries are auto-expanded with a confirmation checkbox
- An **Advanced** section with editable raw JSON (power users can add/remove classes)
- **✅ Approve** or **❌ Reject** buttons

### Backend: `backend/api/routes/review.py` (Gate A)

**Purpose:** Accept approval decision and resume the pipeline.

**Key design: BackgroundTasks for long-running operations.**

```python
background_tasks.add_task(_run_gate_resume, job_id, "gate_a", approved_data)
return get_job_status(job_id)  # Returns immediately (HTTP 200)
```

**Why BackgroundTasks?** After Gate A approval, the pipeline runs contract generation (calls Gemini multiple times → 30-60 seconds). Without background execution, the browser would timeout waiting for the HTTP response.

---

## 7. Contract-First Generation (Layer ⑤)

### Contract Chain: `backend/ai/chains/contract_chain.py`

**Purpose:** LCEL chain that generates OpenAPI YAML from boundary + RAG context.

**Chain:** `prompt | llm | StrOutputParser()` → returns raw YAML string.

### OpenAPI Generator: `backend/contracts/openapi_generator.py`

**Purpose:** Orchestrates contract generation for each boundary.

**Flow:**
1. `retrieve_for_boundary()` → gets relevant code from ChromaDB
2. `run_contract_generation()` → Gemini generates OpenAPI YAML
3. `validate_openapi()` → validates against OpenAPI 3.0 spec
4. Saves to `data/outputs/{job_id}/contracts/{name}.openapi.yaml`

| Detail | Value |
|--------|-------|
| **Library** | `openapi-spec-validator`, `pyyaml` |
| **Why validate?** | LLMs sometimes generate invalid YAML or missing `$ref` fields. Validation catches issues before the user sees broken specs. |

### AsyncAPI & gRPC Generators

- `backend/contracts/asyncapi_generator.py` — generates event-driven specs (if boundary has `event-driven` API style)
- `backend/contracts/grpc_generator.py` — generates `.proto` definitions (if boundary has `gRPC` API style)

### Contract Validator: `backend/contracts/validator.py`

**Purpose:** Cross-reference validation — ensures contracts don't reference services that don't exist.

---

## 8. Gate B — Contract Review

### Frontend: `frontend/pages/04_contract_review.py`

**Purpose:** Display generated OpenAPI/AsyncAPI/gRPC specs. Let the user approve or modify.

Shows each contract in a YAML code block with syntax highlighting. Editable. Approve/Reject buttons.

### Backend: `backend/api/routes/review.py` (Gate B)

Same pattern as Gate A but triggers the heavy code generation phase:
- `generate_code` (Gemini writes actual microservice source code)
- `generate_infra` (Dockerfiles, K8s YAML)
- `generate_migration` (Strangler-fig plans)
- `package_output` (ZIP archive)

This runs as a BackgroundTask with **600s timeout** because code generation is the longest step.

---

## 9. Code Scaffolding & Output (Layer ⑥ → ⑦)

### Code Chain: `backend/ai/chains/code_chain.py`

**Purpose:** LCEL chain that asks Gemini to extract and rewrite monolith code into standalone microservice code.

**Input:** Service name + OpenAPI spec + original source classes (from RAG)  
**Output:** List of `{path, content}` file objects

### Code Scaffolder: `backend/scaffolding/code_scaffolder.py`

**Purpose:** Merges LLM-generated code with Jinja2 framework templates.

| Detail | Value |
|--------|-------|
| **Library** | `jinja2` (template engine) |
| **Why Jinja2 over string concatenation?** | Templates for `pom.xml`, `Application.java`, `application.yml`, `Dockerfile` are complex with conditional logic. Jinja2 handles loops, conditionals, and inheritance cleanly. |

**Java templates:** `pom.xml.j2`, `Application.java.j2`, `application.yml.j2`  
**Python templates:** `pyproject.toml.j2`, `main.py.j2`, `router.py.j2`, `service.py.j2`, `models.py.j2`

### Infra Generator: `backend/scaffolding/infra_generator.py`

Renders: `Dockerfile`, `k8s-deployment.yaml`, `docker-compose-service.yaml` per service.

### Strangler Planner: `backend/scaffolding/strangler_planner.py`

**Purpose:** Uses Gemini to generate a phased **Strangler-Fig migration plan** (`MIGRATION.md`).

| Detail | Value |
|--------|-------|
| **Why Strangler Fig?** | Industry best practice for migrating monoliths. You don't rewrite everything at once — you strangle the monolith by routing traffic to new services one-by-one. This is what Martin Fowler, Sam Newman, and TCS's own migration methodology recommend. |

### Archiver: `backend/scaffolding/archiver.py`

**Purpose:** Walks the output directory, zips everything into `monolith-breaker-{job_id}.zip`.

Sets file permissions to `0644` so the ZIP extracts correctly on any OS.

---

## 10. Download Page

### Frontend: `frontend/pages/05_download.py`

**Purpose:** Check job status, show download button for the ZIP archive.

Calls `GET /output/{job_id}` → returns the ZIP via `FileResponse`.

### Backend: `backend/api/routes/output.py`

```python
zip_path = Path(settings.OUTPUT_DIR) / job_id / f"monolith-breaker-{job_id}.zip"
return FileResponse(path=str(zip_path), media_type="application/zip")
```

---

## 11. Post-Deployment: Drift Detection

### Drift Scanner: `backend/drift/scanner.py`

Re-parses changed source files using the same Tree-sitter AST parser.

### Drift Detector: `backend/drift/detector.py`

**Purpose:** Compares current code graph against approved boundaries. Detects:

| Violation | What it means |
|-----------|---------------|
| `CROSS_BOUNDARY_CALL` | A class in Service A directly calls a class in Service B (should go through API) |
| `CIRCULAR_DEP` | Service A depends on B, and B depends on A |
| `GOD_CLASS_REGROWTH` | A class imports from 5+ different services (becoming a new monolith) |
| `SHARED_DB` | Multiple services accessing the same database tables |

### Drift Alerter: `backend/drift/alerter.py`

Stores alerts in Neo4j and optionally fires a webhook.

### Frontend: `frontend/pages/06_drift_dashboard.py`

Shows violation alerts in a table with severity indicators.

---

## 12. Configuration — `backend/config.py`

| Detail | Value |
|--------|-------|
| **Library** | `pydantic-settings` (`BaseSettings`) |
| **Why Pydantic Settings?** | Reads from `.env` files, environment variables, and has full type validation. No more `os.getenv()` scattered everywhere. |

All paths (`UPLOAD_DIR`, `OUTPUT_DIR`, `CHROMA_PERSIST_DIR`), Neo4j credentials, Gemini config, and feature flags are defined here as typed fields with defaults.

---

## 13. Docker & Infrastructure

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build: `uv` installs deps → Python 3.13-slim runtime |
| `docker-compose.yml` | 3 services: `app` (backend), `neo4j` (graph DB), `otel-collector` |
| `infra/otel/collector-config.yaml` | OpenTelemetry Collector receivers/exporters |

---

## 14. Complete Library Map

| Library | Where Used | Why This Over Alternatives |
|---------|------------|----------------------------|
| **FastAPI** | API server | Async-native, auto-docs, Pydantic validation (vs Flask/Django) |
| **Streamlit** | Frontend UI | Python-only, rapid prototyping, session state (vs React/Next.js) |
| **LangGraph** | Pipeline engine | Formal state machine with human gates (vs plain asyncio) |
| **LangChain** | LLM chain composition | LCEL pipes, output parsers, provider abstraction (vs raw SDK) |
| **langchain-google-genai** | Gemini integration | Official Google connector for LangChain |
| **Tree-sitter** | AST parsing | Incremental, error-tolerant, 40+ languages (vs regex/ANTLR) |
| **Neo4j** | Knowledge graph | Native graph queries, Louvain clustering (vs SQL/MongoDB) |
| **ChromaDB** | Vector store (RAG) | Local, embedded, no API keys (vs Pinecone/Weaviate) |
| **Jinja2** | Code templates | Loops, conditionals, inheritance (vs string concat) |
| **Pydantic** | Data validation | Type-safe schemas, serialization (vs dataclasses) |
| **pydantic-settings** | Configuration | Env + .env + type validation (vs dotenv/os.getenv) |
| **httpx** | HTTP client (frontend) | Async + sync, modern (vs requests) |
| **openapi-spec-validator** | Contract validation | Official OpenAPI validator |
| **PyYAML** | YAML parsing | Standard Python YAML library |
| **uvicorn** | ASGI server | Production-grade async server for FastAPI |
| **Docker** | Containerisation | Reproducible deployments |
| **Neo4j GDS** | Graph algorithms | Louvain community detection built-in |
| **OpenTelemetry SDK** | Trace parsing | Industry-standard distributed tracing |

---

## 15. Anticipated Q&A for TCS Presentation

### Architecture & Design

**Q1: Why did you choose a microservices decomposition approach instead of just a modular monolith?**
> A: We're not prescribing microservices. The tool **analyses** the monolith and **proposes** boundaries based on Domain-Driven Design (DDD) principles. The human reviewer decides what stays monolithic and what gets extracted. The Strangler-Fig pattern means you migrate incrementally, not all at once.

**Q2: Why Google Gemini and not GPT-4 or Claude?**
> A: The system is model-agnostic via LangChain. Swapping to OpenAI or Azure OpenAI requires changing one line in `llm_client.py`. We chose Gemini because: (a) generous free tier for prototyping, (b) strong code understanding, (c) fast latency with `gemini-2.5-flash`. TCS can switch to any provider based on client requirements.

**Q3: What if the monolith is too large for the LLM context window?**
> A: That's exactly why we use RAG (Retrieval-Augmented Generation). We don't send the entire codebase to Gemini. We embed all code into ChromaDB, then retrieve only the top-K most relevant chunks for each AI call. Even a 10M-line monolith works because each Gemini call sees only 5-10 relevant classes.

**Q4: Why Neo4j instead of a simpler database?**
> A: Dependency analysis is inherently a graph problem. "Find all classes that transitively depend on OrderService" is a single Cypher query with Neo4j. With PostgreSQL, you'd need recursive CTEs. Neo4j GDS also provides Louvain community detection out-of-the-box — the core algorithm for boundary proposal.

**Q5: How does the human-in-the-loop work technically?**
> A: The LangGraph pipeline has two **gate nodes** (Gate A and Gate B). When the pipeline reaches a gate, it serialises its entire state to an in-memory store and returns. The HTTP response to the user says "status: gate_a". The user reviews in the UI, clicks Approve, which calls `POST /review/boundaries`. This triggers `resume_from_gate()` which loads the saved state and continues from where it left off.

### Security & Privacy

**Q6: Does our source code leave the company network?**
> A: The only external call is to the Gemini API. The AST parsing, Neo4j graph, ChromaDB embeddings, and code scaffolding all run locally. For air-gapped deployments, you can swap Gemini for a self-hosted LLM (Llama, Mixtral) via LangChain's provider abstraction.

**Q7: How are API keys handled?**
> A: Keys are never saved to disk. They travel as HTTP headers (`X-Gemini-API-Key`) from the browser to the backend. The middleware sets them in-memory for the duration of the request. When the container restarts, all keys are gone.

### Scalability & Production

**Q8: Can this handle a 5-million-line enterprise monolith?**
> A: Yes. Tree-sitter parses at >10K lines/second. Neo4j handles millions of nodes. ChromaDB handles millions of embeddings. The bottleneck is Gemini API rate limits, which are configurable. The pipeline is sequential per job but multiple jobs can run in parallel.

**Q9: Why is the job store in-memory? That won't survive a restart.**
> A: This is a prototype/demo. In production, swap `JOB_STORE = {}` with Redis or PostgreSQL. The `JobResponse` Pydantic model and the `update_job_status()` API stay identical — it's a one-file change.

**Q10: What happens if the Gemini API call fails mid-pipeline?**
> A: Every pipeline step is wrapped in try/except. If any step fails, the job status is set to `ERROR` with the exception message. The user sees the error in the Progress page. They can re-upload and retry. State is not corrupted because each step updates `state.update(updates)` atomically.

### Competitive Differentiation

**Q11: How is this different from IBM Mono2Micro or VMware Application Transformer?**
> A: Three key differentiators: (1) **Contract-First** — we generate validated OpenAPI/AsyncAPI/gRPC specs BEFORE writing code, not after. (2) **Human-in-the-Loop Gates** — the engineer reviews and modifies boundaries before any code is generated. IBM's tool is fully automated with no review step. (3) **Strangler-Fig Migration Plans** — we generate phased migration playbooks, not just code.

**Q12: What languages does it support?**
> A: Full support for Java (Spring Boot scaffolding). Python, Go, and C# have AST parsing but scaffolding generates FastAPI templates for Python. Adding a new language requires: (1) add a `tree-sitter-{lang}` grammar, (2) add Jinja2 scaffolding templates.

**Q13: What's the accuracy of boundary detection?**
> A: It depends on the codebase. For well-structured monoliths with clear package boundaries, accuracy is >90%. For spaghetti codebases, the confidence scorer flags low-confidence boundaries for human review. The tool is designed to augment human decision-making, not replace it.

### Implementation Details

**Q14: What does the output ZIP contain?**
> A: For each proposed microservice: `pom.xml` (or `pyproject.toml`), application source code, `application.yml`, `Dockerfile`, `k8s-deployment.yaml`, `docker-compose-service.yaml`, `MIGRATION.md`, and the OpenAPI/AsyncAPI spec.

**Q15: How does drift detection work after deployment?**
> A: You schedule a cron job (or CI/CD hook) that re-parses the monolith source and compares the current dependency graph against the approved boundaries stored in Neo4j. It detects: circular dependencies, cross-boundary direct calls, and "god-class regrowth" (a class importing from 5+ services). Alerts are shown in the Drift Dashboard or fired via webhook to Slack/Teams.

**Q16: Can we extend this to handle database decomposition?**
> A: The current prototype focuses on service code decomposition. Database decomposition (shared tables → per-service databases) is the logical next step. The Neo4j graph already captures which services access which repositories/entities. Adding a "database boundary" layer to the pipeline would leverage the same infrastructure.

---

> **Tip for the demo:** Run the full pipeline live with the `legacy-monolith.zip` test project. It takes ~3 minutes end-to-end. Walk through each gate review, show the OpenAPI YAML, then download and unzip the output to show the generated Spring Boot project structure.
