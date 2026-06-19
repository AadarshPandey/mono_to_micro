# 🔨 MonolithBreaker — AI-Powered Legacy Modernisation

<div align="center">

![Version](https://img.shields.io/badge/version-1.0-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![FastAPI](https://img.shields.io/badge/fastapi-0.136+-teal)
![Streamlit](https://img.shields.io/badge/streamlit-1.58+-red)
![Docker](https://img.shields.io/badge/docker-ready-blue)
![License](https://img.shields.io/badge/license-MIT-yellow)

**An intelligent platform that decomposes legacy monolithic applications into deployable microservices using static AST analysis, dynamic runtime data, a local knowledge graph, and Google Gemini.**

[Features](#-features) • [Architecture](#-architecture) • [Pipeline](#-pipeline-flow) • [Installation](#-installation) • [Usage](#-usage) • [Docker](#-docker)

</div>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🧩 **Intelligent Decomposition** | Automatically detects Bounded Contexts using Gemini AI and Louvain graph clustering |
| 📊 **Deep Code Analysis** | Parses Java/Python/Go/C# ASTs with Tree-sitter to build a comprehensive dependency graph |
| 🕵️ **Dynamic Tracing** | Ingests OpenTelemetry (OTel) traces to understand actual runtime call patterns |
| 🧑‍💻 **Human-in-the-Loop Gates** | Review, modify, and approve microservice boundaries and API contracts before code generation |
| 📜 **Contract-First Generation** | Generates OpenAPI, AsyncAPI, and gRPC Protobuf specs *before* writing any service code |
| 🏗️ **End-to-End Scaffolding** | Generates Spring Boot / FastAPI code, Dockerfiles, K8s manifests, and Strangler-Fig migration plans |
| 🛡️ **Post-Deployment Drift Detection** | Monitors ongoing monolith commits to alert on circular deps, cross-boundary calls, and god-class regrowth |

---

## 🏗️ Architecture

```mermaid
flowchart TB
    %% ① INPUT
    subgraph INPUT["① Input"]
        ZIP["Monolith Source ZIP"]
        OTEL["OTel Traces JSON"]
        CONFIG["Gemini API Key + Model"]
    end

    %% ② API GATEWAY
    subgraph GATEWAY["② API Gateway — FastAPI + Middleware"]
        direction TB
        UPLOAD["/upload"]
        REVIEW_A["/review/boundaries"]
        REVIEW_B["/review/contracts"]
        JOBS["/jobs — Status Polling"]
        OUTPUT["/output — ZIP Download"]
        MW["Middleware: CORS · RequestID · Timing · GeminiKey"]
    end

    %% ③ PARSE & CONTEXT
    subgraph PARSE["③ Parse and Context — Static + Dynamic"]
        direction TB
        AST["AST Parser — tree-sitter\nJava · Python · Go · C#"]
        DYNAMIC["Dynamic Analyzer\nOpenTelemetry SDK"]
        GRAPH["Graph Builder — neo4j driver\nLouvain Community Detection"]
        EMBED["Embedder — chromadb\nlangchain-chroma"]
        NEO4J[("Neo4j 5\nKnowledge Graph")]
        CHROMA[("ChromaDB\nVector Store")]
    end

    %% ④ AI ORCHESTRATION
    subgraph AI["④ AI Orchestration — On-Premise Privacy Boundary"]
        direction TB
        ORCH["LangGraph StateGraph\nStateful Pipeline"]
        BOUNDARY["Boundary Chain\nlangchain + Gemini"]
        CONFIDENCE["Confidence Scorer\nCohesion vs Coupling"]
        GATE_A{"🟠 Gate A\nHuman Review\nBoundaries"}
        CONTRACT_CHAIN["Contract Chain\nlangchain + Gemini"]
        VALIDATE["Contract Validator\nopenapi-spec-validator"]
        GATE_B{"🟠 Gate B\nHuman Review\nContracts"}
        RAG["RAG Retriever\nchromadb context"]
    end

    %% ⑤ CONTRACT-FIRST GENERATION
    subgraph CONTRACTS["⑤ Contract-First Generation"]
        direction TB
        OPENAPI["OpenAPI Generator\nREST Specs — YAML"]
        ASYNCAPI["AsyncAPI Generator\nEvent-Driven Specs"]
        GRPC["gRPC Generator\nProtobuf Definitions"]
    end

    %% ⑥ SCAFFOLDING & OUTPUT
    subgraph SCAFFOLD["⑥ Code Scaffolding and Output"]
        direction TB
        CODE["Code Scaffolder\nJinja2 Templates"]
        INFRA["Infra Generator\nDockerfile · K8s · Compose"]
        MIGRATION["Strangler Planner\nPhased Migration Plans"]
        ARCHIVER["Archiver\nZIP Packaging"]
    end

    %% ⑦ OUTPUT
    subgraph FINAL["⑦ Output — Downloadable Archive"]
        direction LR
        SVC_CODE["Spring Boot / FastAPI\nMicroservice Source"]
        SVC_CONTRACTS["OpenAPI + AsyncAPI\n+ Protobuf Specs"]
        SVC_INFRA["Dockerfile · K8s YAML\ndocker-compose"]
        SVC_MIGRATE["MIGRATION.md\nStrangler-Fig Plan"]
    end

    %% POST-DEPLOYMENT
    subgraph DRIFT["Post-Deployment — Drift Detection"]
        direction TB
        SCANNER["Drift Scanner\nRe-parse changed files"]
        DETECTOR["Violation Detector\nCircular · Cross-boundary · God-class"]
        ALERTER["Alerter\nWebhook / Neo4j Store"]
    end

    %% ── EDGES ──
    INPUT --> GATEWAY
    GATEWAY --> PARSE

    AST --> GRAPH
    DYNAMIC --> GRAPH
    GRAPH --> NEO4J
    AST --> EMBED
    EMBED --> CHROMA

    PARSE --> AI
    RAG -.->|context| BOUNDARY
    RAG -.->|context| CONTRACT_CHAIN
    CHROMA -.-> RAG

    ORCH --> BOUNDARY
    BOUNDARY --> CONFIDENCE
    CONFIDENCE --> GATE_A
    GATE_A -->|approved| CONTRACTS
    OPENAPI --> CONTRACT_CHAIN
    ASYNCAPI --> CONTRACT_CHAIN
    GRPC --> CONTRACT_CHAIN
    CONTRACT_CHAIN --> VALIDATE
    VALIDATE --> GATE_B

    GATE_B -->|approved| SCAFFOLD
    CODE --> ARCHIVER
    INFRA --> ARCHIVER
    MIGRATION --> ARCHIVER

    ARCHIVER --> FINAL

    FINAL --> GATEWAY
    DRIFT -.->|continuous| NEO4J

    %% Styling
    style INPUT fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20
    style GATEWAY fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    style PARSE fill:#fff3e0,stroke:#e65100,color:#bf360c
    style AI fill:#fce4ec,stroke:#c62828,color:#b71c1c
    style CONTRACTS fill:#f3e5f5,stroke:#6a1b9a,color:#4a148c
    style SCAFFOLD fill:#e0f2f1,stroke:#00695c,color:#004d40
    style FINAL fill:#e8eaf6,stroke:#283593,color:#1a237e
    style DRIFT fill:#fff8e1,stroke:#f9a825,color:#f57f17
```

---

## 🔄 Pipeline Flow

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant S as 🖥️ Streamlit
    participant F as ⚙️ FastAPI
    participant T as 🌳 Tree-sitter
    participant N as 🔵 Neo4j
    participant C as 🟣 ChromaDB
    participant G as 🧠 Gemini AI

    rect rgb(232, 245, 233)
        Note over U,S: ① Input
        U->>S: Upload monolith.zip + API Key
        S->>F: POST /upload (ZIP + headers)
    end

    rect rgb(255, 243, 224)
        Note over F,C: ③ Parse & Context
        F->>T: Parse AST (classes, methods, imports)
        T-->>F: Static edges
        F->>F: Parse OTel traces → dynamic edges
        F->>N: Build knowledge graph + Louvain clustering
        F->>C: Embed code chunks (vector store)
    end

    rect rgb(252, 228, 236)
        Note over F,G: ④ AI Orchestration
        F->>C: RAG retrieve relevant code
        C-->>F: Code context
        F->>G: Propose bounded contexts
        G-->>F: Boundary proposals + confidence scores
    end

    rect rgb(255, 248, 225)
        Note over U,S: Gate A — Human Review
        F-->>S: Suspend pipeline (status: gate_a)
        S-->>U: Display boundaries for approval
        U->>S: Approve / modify boundaries
        S->>F: POST /review/boundaries
    end

    rect rgb(243, 229, 245)
        Note over F,G: ⑤ Contract-First Generation
        F->>G: Generate OpenAPI specs
        F->>G: Generate AsyncAPI specs
        F->>G: Generate Protobuf definitions
        F->>F: Validate contracts (cross-ref check)
    end

    rect rgb(255, 248, 225)
        Note over U,S: Gate B — Human Review
        F-->>S: Suspend pipeline (status: gate_b)
        S-->>U: Display API contracts for approval
        U->>S: Approve / modify contracts
        S->>F: POST /review/contracts
    end

    rect rgb(224, 242, 241)
        Note over F,G: ⑥ Scaffolding
        F->>G: Generate microservice code
        F->>F: Render Dockerfiles + K8s manifests (Jinja2)
        F->>G: Generate strangler-fig migration plans
        F->>F: Package ZIP archive
    end

    rect rgb(232, 234, 246)
        Note over U,S: ⑦ Output
        F-->>S: Status: done (100%)
        S-->>U: Download microservices.zip
    end

    rect rgb(255, 248, 225)
        Note over F,N: Post-Deployment
        F->>T: Re-scan changed files
        F->>N: Compare against approved boundaries
        F-->>S: Drift alerts (circular deps, god-class)
    end
```

---

## 📁 Project Structure

```text
MonolithBreaker/
├── docker-compose.yml              # 🐳 Full-stack orchestration (App + Neo4j + OTel)
├── Dockerfile                      # 🐳 Backend container image
├── pyproject.toml                  # 📦 Dependencies managed by uv
├── Makefile                        # 🛠️ Dev shortcuts
│
├── frontend/                       # 🖥️ Streamlit Application
│   ├── app.py                      #    Landing page + sidebar config
│   └── pages/
│       ├── 01_upload.py            #    ZIP upload + pipeline trigger
│       ├── 02_progress.py          #    Real-time job status polling
│       ├── 03_boundary_review.py   #    Gate A — approve boundaries
│       ├── 04_contract_review.py   #    Gate B — approve contracts
│       ├── 05_download.py          #    Output archive download
│       └── 06_drift_dashboard.py   #    Post-deploy violation alerts
│
├── backend/                        # ⚙️ FastAPI Application
│   ├── main.py                     #    App factory + middleware registration
│   ├── config.py                   #    Pydantic Settings (env-driven)
│   │
│   ├── api/                        #    ② API Gateway Layer
│   │   ├── middleware.py           #       CORS · RequestID · Timing · GeminiKey
│   │   ├── schemas.py              #       Pydantic models + enums
│   │   └── routes/
│   │       ├── upload.py           #       POST /upload
│   │       ├── jobs.py             #       GET  /jobs/{id}
│   │       ├── review.py           #       POST /review/boundaries|contracts
│   │       ├── output.py           #       GET  /output/{id}
│   │       └── drift.py            #       GET  /drift/{id}
│   │
│   ├── ingestion/                  #    ③ Parse & Context Layer
│   │   ├── ast_parser.py           #       Tree-sitter multi-lang AST parsing
│   │   ├── language_registry.py    #       Parser registry (Java/Python/Go/C#)
│   │   ├── dynamic_analyzer.py     #       OTel trace → dynamic call edges
│   │   ├── graph_builder.py        #       Neo4j graph + Louvain clustering
│   │   ├── embedder.py             #       ChromaDB code embeddings
│   │   └── job_runner.py           #       Pipeline entry point + job store
│   │
│   ├── db/                         #    Data Layer
│   │   ├── neo4j_client.py         #       Neo4j async driver wrapper
│   │   └── chroma_client.py        #       ChromaDB persistent client
│   │
│   ├── ai/                         #    ④ AI Orchestration Layer
│   │   ├── orchestrator.py         #       LangGraph StateGraph pipeline
│   │   ├── llm_client.py           #       Gemini LLM client (langchain-google-genai)
│   │   ├── rag_retriever.py        #       RAG context from ChromaDB
│   │   ├── confidence_scorer.py    #       Cohesion / coupling scoring
│   │   ├── chains/
│   │   │   ├── boundary_chain.py   #       Bounded context detection
│   │   │   ├── contract_chain.py   #       API contract generation
│   │   │   ├── code_chain.py       #       Service code extraction
│   │   │   └── strangler_chain.py  #       Migration plan generation
│   │   └── prompts/                #       Prompt templates
│   │
│   ├── contracts/                  #    ⑤ Contract-First Generation
│   │   ├── openapi_generator.py    #       REST OpenAPI 3.0 YAML
│   │   ├── asyncapi_generator.py   #       Event-driven AsyncAPI YAML
│   │   ├── grpc_generator.py       #       gRPC Protobuf definitions
│   │   └── validator.py            #       Cross-reference validation
│   │
│   ├── scaffolding/                #    ⑥ Code Scaffolding
│   │   ├── code_scaffolder.py      #       Jinja2 template renderer
│   │   ├── infra_generator.py      #       Dockerfile + K8s + Compose
│   │   ├── strangler_planner.py    #       Strangler-fig migration plans
│   │   ├── archiver.py             #       ZIP packaging
│   │   └── templates/              #       Jinja2 templates (Spring Boot / FastAPI)
│   │
│   └── drift/                      #    Post-Deployment Layer
│       ├── scanner.py              #       Re-parse changed source files
│       ├── detector.py             #       Violation detection engine
│       └── alerter.py              #       Webhook + Neo4j alert storage
│
├── infra/                          # 🏗️ Infrastructure
│   └── otel/
│       └── collector-config.yaml   #    OpenTelemetry Collector config
│
└── data/                           # 📂 Runtime Data (Docker volume)
    ├── uploads/                    #    Uploaded ZIP files
    ├── outputs/                    #    Generated microservice archives
    └── chroma/                     #    ChromaDB persistent storage
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **② Gateway** | `FastAPI` `uvicorn` `Pydantic` | Async REST API with schema validation |
| **③ Static Parse** | `tree-sitter` `tree-sitter-java` `tree-sitter-python` `tree-sitter-go` `tree-sitter-c-sharp` | Multi-language AST extraction |
| **③ Dynamic Parse** | `opentelemetry-sdk` | Runtime trace ingestion |
| **③ Graph** | `neo4j` (driver) + Neo4j 5 GDS | Knowledge graph + Louvain clustering |
| **③ Embeddings** | `chromadb` `langchain-chroma` | Code vector search (RAG) |
| **④ Orchestration** | `langgraph` `langchain` `langchain-core` | Stateful multi-step agent pipeline |
| **④ LLM** | `langchain-google-genai` (Google Gemini) | Reasoning engine for all AI chains |
| **⑤ Contracts** | `openapi-spec-validator` `pyyaml` | Contract generation + validation |
| **⑥ Scaffolding** | `jinja2` | Template-based code and infra rendering |
| **🖥️ Frontend** | `streamlit` `streamlit-agraph` `httpx` | Interactive multi-page UI |
| **🐳 Infra** | `Docker` `Docker Compose` `OTel Collector` | Container orchestration + observability |

---

## 🚀 Installation

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (fast Python package manager)
- Docker & Docker Compose
- Gemini API Key ([Get one here](https://aistudio.google.com/app/apikey))

### Setup with uv

```bash
# Clone the repository
git clone https://github.com/aadarshpandey/MonolithBreaker.git
cd MonolithBreaker

# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
uv sync
```

---

## ▶️ Usage

### 1. Start the Infrastructure (Neo4j & OTel)

```bash
docker compose up -d neo4j otel-collector
```

### 2. Start the Backend API

```bash
uv run uvicorn backend.main:app --reload --port 8000
```

### 3. Start the Streamlit UI

```bash
uv run streamlit run frontend/app.py
```

Open your browser at `http://localhost:8501`

### First Time Setup

1. Enter your **Gemini API Key** in the sidebar
2. Select your preferred **Gemini Model** (e.g., `gemini-2.5-flash`)
3. Navigate to **Upload** → submit your monolith ZIP
4. Monitor **Progress** → approve **Boundaries** → approve **Contracts** → **Download**

---

## 🐳 Docker

### Pull from Docker Hub

```bash
# Pull the pre-built image (recommended for quick start)
docker pull aadarshpandey/monolith-breaker:v2
```

### Build Locally

```bash
# Build the image from source
docker build -t aadarshpandey/monolith-breaker:v2 .
```

### Docker Compose — Full Stack (Recommended)

Spins up all 3 services (App + Neo4j + OTel Collector) with a single command:

```bash
# Build and start everything in the background
docker compose up -d --build

# Start without rebuilding (if image already exists)
docker compose up -d

# Start only the database (for local development)
docker compose up -d neo4j otel-collector
```

### Container Management

```bash
# View running containers
docker compose ps

# Follow live logs for the app
docker compose logs -f app

# Follow logs for all services
docker compose logs -f

# Restart a specific service
docker compose restart app

# Stop all services (keeps data volumes)
docker compose down

# Stop and remove all data (full reset)
docker compose down -v
```

### Push to Docker Hub

```bash
# Tag and push a new version
docker tag aadarshpandey/monolith-breaker:v2 aadarshpandey/monolith-breaker:latest
docker push aadarshpandey/monolith-breaker:v2
docker push aadarshpandey/monolith-breaker:latest
```

### Access Points

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend UI** | `http://localhost:8501` | Streamlit dashboard |
| **Backend API** | `http://localhost:8000` | FastAPI + Swagger docs at `/docs` |
| **Neo4j Browser** | `http://localhost:7474` | Graph database UI (login: `neo4j` / `password`) |
| **OTel Collector** | `http://localhost:4318` | OpenTelemetry HTTP receiver |

### Docker Images Used

| Image | Purpose |
|-------|---------|
| `aadarshpandey/monolith-breaker:v2` | Backend API + Streamlit frontend |
| `neo4j:5-community` | Graph database for knowledge graph |
| `otel/opentelemetry-collector:latest` | Distributed trace collection |

---

## 🔧 Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_API_KEY` | Gemini API key (or set via UI sidebar) | — |
| `GEMINI_MODEL` | Default Gemini model | `gemini-2.5-flash` |
| `NEO4J_URI` | Neo4j bolt connection | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | `password` |
| `UPLOAD_DIR` | Path for uploaded ZIPs | `data/uploads` |
| `OUTPUT_DIR` | Path for generated output | `data/outputs` |
| `CHROMA_PERSIST_DIR` | ChromaDB storage path | `data/chroma` |

---

## 📄 License

MIT License — feel free to use, modify, and distribute.

---

<div align="center">

**Made with ❤️ using FastAPI, LangGraph, Streamlit & Google Gemini**

[⬆ Back to top](#-monolithbreaker--ai-powered-legacy-modernisation)

</div>
