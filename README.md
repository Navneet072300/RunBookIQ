# RunbookIQ

**AI-powered incident triage and runbook assistant for DevOps and platform engineering teams.**

RunbookIQ ingests alerts from Prometheus/Alertmanager, Kubernetes events, and Zabbix, then uses a RAG pipeline backed by pgvector to retrieve relevant runbook context and generate structured triage playbooks in real time — powered by Google Gemini.

---

## Features

- **Multi-source alert ingestion** — Prometheus webhooks, Kubernetes events, Zabbix problems
- **Automatic deduplication** — SHA-256 fingerprint + 5-minute Redis TTL prevents noise storms
- **RAG-generated playbooks** — pgvector HNSW similarity search retrieves your runbooks, Gemini writes the triage steps
- **SSE streaming** — playbook text streams token-by-token to the UI
- **Auto-remediation** — dry-run and one-click approve for common K8s remediations (restart, scale, cordon, rollback)
- **Runbook indexing** — upload PDF/DOCX/Markdown; chunks are embedded and stored in pgvector
- **Slack notifications** — Block Kit incident cards sent on playbook generation
- **Dark-theme React UI** — incident list, playbook viewer, runbook manager, metrics dashboard
- **Multi-tenancy ready** — `X-Tenant-ID` header and `tenant_id` column on all models
- **Helm chart** — production Kubernetes deployment included

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn (async) |
| Database | PostgreSQL 16 + pgvector (HNSW, cosine, 768 dims) |
| ORM / Migrations | SQLAlchemy 2.0 async + Alembic |
| Queue | Redis + RQ (high / default / low) |
| LLM | Google Gemini 2.0 Flash (via OpenAI-compat endpoint) |
| Embeddings | Google text-embedding-004 (native batchEmbedContents API) |
| Frontend | React 18 + Vite + Tailwind CSS v3 |
| Logging | structlog (JSON in production, console in dev) |
| Container | Docker Compose (dev) · Helm chart (prod) |

---

## Quick Start (Docker Compose)

### Prerequisites

- Docker + Docker Compose
- A free Google Gemini API key — get one at [aistudio.google.com](https://aistudio.google.com)

### 1. Clone and configure

```bash
git clone https://github.com/your-org/runbookiq.git
cd runbookiq

cp .env.example .env
```

Open `.env` and set at minimum:

```env
GEMINI_API_KEY=AIza...          # from aistudio.google.com
POSTGRES_PASSWORD=changeme
SECRET_KEY=your-random-32-char-string
```

### 2. Start all services

```bash
docker compose up -d
```

This starts: `postgres`, `redis`, `api` (FastAPI), `worker` (RQ), `frontend` (Vite dev server).

### 3. Run database migrations

```bash
docker compose exec api alembic upgrade head
```

### 4. Seed demo data (optional)

```bash
docker compose exec api python backend/scripts/seed_demo.py
```

### 5. Open the UI

```
http://localhost:5173       — React UI
http://localhost:8000/docs  — Swagger API docs
http://localhost:8000/redoc — ReDoc
```

---

## Architecture

```
Prometheus / Kubernetes / Zabbix
            │
            ▼
  POST /api/v1/alerts/ingest
            │
            ▼
  Normaliser  ──►  Dedup check (Redis, 5-min TTL, SHA-256)
            │
            ▼
      RQ Worker (async)
            │
            ├─ embed query  ──►  pgvector HNSW similarity_search
            │                    (text-embedding-004, 768 dims)
            │
            ├─ prompt_builder (runbook chunks + alert context)
            │
            ├─ Gemini 2.0 Flash  ──►  structured PlaybookResponse
            │
            ├─ Slack Block Kit notification
            │
            └─ SSE stream  ──►  React frontend
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Liveness probe |
| `POST` | `/api/v1/alerts/ingest` | Ingest Prometheus / K8s / Zabbix alert |
| `GET` | `/api/v1/incidents` | Paginated incident list |
| `GET` | `/api/v1/incidents/{id}` | Full incident detail with playbook |
| `GET` | `/api/v1/incidents/{id}/playbook/stream` | SSE streaming playbook generation |
| `PATCH` | `/api/v1/incidents/{id}` | Update status / assignee |
| `POST` | `/api/v1/runbooks/upload` | Upload and index a runbook file |
| `GET` | `/api/v1/runbooks` | List indexed runbooks |
| `POST` | `/api/v1/remediation/{id}/dry-run` | Preview remediation command |
| `POST` | `/api/v1/remediation/{id}/approve` | Execute auto-remediation |

---

## Alert Ingest Examples

**Prometheus / Alertmanager webhook:**

```bash
curl -X POST http://localhost:8000/api/v1/alerts/ingest \
  -H 'Content-Type: application/json' \
  -d '{
    "source": "prometheus",
    "payload": {
      "alerts": [{
        "labels": {
          "alertname": "HighMemoryUsage",
          "severity": "critical",
          "namespace": "prod"
        },
        "annotations": {"description": "Memory above 90% for 10 minutes"},
        "startsAt": "2025-01-15T10:00:00Z"
      }]
    }
  }'
```

**Kubernetes event:**

```bash
curl -X POST http://localhost:8000/api/v1/alerts/ingest \
  -H 'Content-Type: application/json' \
  -d '{
    "source": "kubernetes",
    "payload": {
      "reason": "OOMKilling",
      "message": "Memory limit exceeded in container api",
      "type": "Warning",
      "involvedObject": {"kind": "Pod", "name": "api-7d6b9f-xkp2r", "namespace": "prod"},
      "firstTimestamp": "2025-01-15T10:00:00Z"
    }
  }'
```

**Zabbix problem:**

```bash
curl -X POST http://localhost:8000/api/v1/alerts/ingest \
  -H 'Content-Type: application/json' \
  -d '{
    "source": "zabbix",
    "payload": {
      "event_id": "12345",
      "name": "Disk space is low on /data",
      "severity": "high",
      "host": "db-prod-01",
      "clock": 1705312800
    }
  }'
```

---

## Runbook Indexing

Upload a file via the UI or API:

```bash
curl -X POST http://localhost:8000/api/v1/runbooks/upload \
  -F "file=@./runbooks/redis-oom.md" \
  -F "name=Redis OOM Runbook" \
  -F "tags=redis,memory,oom"
```

Supported formats: `.md`, `.txt`, `.pdf`, `.docx`

Chunks are embedded with `text-embedding-004` (768 dims) and stored in pgvector with an HNSW index for fast cosine similarity retrieval.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | ✅ | — | Google Gemini API key (aistudio.google.com) |
| `GEMINI_BASE_URL` | | `...googleapis.com/v1beta/openai/` | Gemini OpenAI-compat base URL |
| `LLM_MODEL` | | `gemini-2.0-flash` | LLM model name |
| `EMBEDDING_MODEL` | | `text-embedding-004` | Embedding model name |
| `DATABASE_URL` | ✅ | — | `postgresql+asyncpg://user:pass@host/db` |
| `REDIS_URL` | ✅ | — | `redis://host:6379/0` |
| `POSTGRES_PASSWORD` | ✅ | — | PostgreSQL password |
| `SECRET_KEY` | ✅ | — | 32-char random string for JWT signing |
| `APP_ENV` | | `development` | `development` or `production` |
| `LOG_LEVEL` | | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `SLACK_WEBHOOK_URL` | Optional | — | Incoming webhook for incident notifications |
| `ZABBIX_API_URL` | Optional | — | `http://zabbix.internal/api_jsonrpc.php` |
| `ZABBIX_USER` | Optional | — | Zabbix API user |
| `ZABBIX_PASSWORD` | Optional | — | Zabbix API password |
| `K8S_KUBECONFIG` | Optional | in-cluster | Path to kubeconfig (leave blank inside cluster) |
| `K8S_NAMESPACE` | Optional | `default` | Target namespace for remediations |
| `PROMETHEUS_ALERTMANAGER_URL` | Optional | — | Alertmanager base URL |
| `UPLOAD_DIR` | | `/app/uploads` | Runbook file storage path |
| `MAX_UPLOAD_SIZE_MB` | | `50` | Maximum upload size |

---

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest
```

Tests cover: API health, alert normalisation (Prometheus / K8s / Zabbix), and RAG orchestrator unit tests with mocked embeddings and LLM.

---

## Helm Deployment (Kubernetes)

```bash
# Create the secrets
kubectl create secret generic runbookiq-secrets \
  --from-literal=GEMINI_API_KEY=AIza... \
  --from-literal=DATABASE_URL=postgresql+asyncpg://... \
  --from-literal=REDIS_URL=redis://... \
  --from-literal=SECRET_KEY=...

# Install the chart
helm install runbookiq ./helm/runbookiq \
  --set ingress.hosts[0].host=runbookiq.yourdomain.com \
  --set api.image.tag=1.0.0
```

Adjust resource limits and replica counts in `helm/runbookiq/values.yaml`.

---

## Project Structure

```
runbookiq/
├── backend/
│   ├── alembic/              # Database migrations
│   ├── app/
│   │   ├── api/              # FastAPI route handlers
│   │   ├── core/             # Config, logging, Redis, DB session
│   │   ├── embeddings/       # Gemini embedder + runbook ingest
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── normaliser/       # Alert normalisation (Prometheus/K8s/Zabbix)
│   │   ├── rag/              # RAG orchestrator + Gemini caller
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   └── main.py           # FastAPI app entry point
│   ├── scripts/
│   │   └── seed_demo.py      # Demo data seeder
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/              # Axios API client
│       ├── components/       # React components
│       └── pages/            # Route pages
├── helm/runbookiq/           # Helm chart
├── docker-compose.yml
└── .env.example
```

---

## Local Development (without Docker)

**Backend:**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Start postgres + redis first (or use docker compose up postgres redis)
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Worker:**

```bash
rq worker --with-scheduler --url redis://localhost:6379/0 default high low
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

---

## License

MIT
