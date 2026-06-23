# RunbookIQ

**AI-powered incident triage and runbook assistant for DevOps and platform engineering teams.**

RunbookIQ connects to your Kubernetes cluster, Prometheus/Alertmanager, and Zabbix — then uses a RAG pipeline to retrieve relevant runbook context and generate structured triage playbooks in real time using Groq's Llama 3.3 70B.

---

## Screenshots

### Dashboard

![Dashboard](assets/dashboard.png)

### Incidents — Real K8s Events

![Incidents](assets/incidents.png)

### AI Triage Playbook

![Playbook](assets/playbook.png)

---

## Features

- **Live Kubernetes event streaming** — connects directly to your cluster via kubeconfig, streams events in real time with automatic reconnection
- **Multi-source alert ingestion** — Prometheus/Alertmanager webhooks, Kubernetes events, Zabbix problems
- **Automatic deduplication** — SHA-256 fingerprint + 5-minute Redis TTL, no noise storms
- **RAG-generated playbooks** — pgvector HNSW similarity search retrieves your runbooks, Groq Llama 3.3 generates structured triage steps
- **SSE streaming** — playbook text streams token-by-token to the UI
- **Auto-remediation** — dry-run and one-click approve for K8s remediations (restart, scale, cordon, rollback)
- **Runbook indexing** — upload PDF/DOCX/Markdown; chunks are embedded and stored in pgvector
- **Slack notifications** — Block Kit incident cards on playbook generation
- **Dark-theme React UI** — incident list, playbook viewer, runbook manager, metrics dashboard
- **Multi-tenancy ready** — `X-Tenant-ID` header and `tenant_id` column on all models
- **Helm chart** — production Kubernetes deployment included

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| API | FastAPI + Uvicorn (async) |
| Database | PostgreSQL 16 + pgvector (HNSW, cosine, 768 dims) |
| ORM / Migrations | SQLAlchemy 2.0 async + Alembic |
| Queue | Redis + RQ (high / default / low) |
| LLM | Groq — Llama 3.3 70B Versatile (free tier, OpenAI-compatible) |
| Embeddings | Google text-embedding-004 (native batchEmbedContents API, 768 dims) |
| Frontend | React 18 + Vite + Tailwind CSS v3 |
| Logging | structlog (JSON in production, console in dev) |
| Container | Docker Compose (dev) · Helm chart (prod) |

---

## Quick Start (Docker Compose)

### Prerequisites

- Docker + Docker Compose
- Free [Groq API key](https://console.groq.com) — 14,400 req/day, no credit card
- Free [Google Gemini API key](https://aistudio.google.com) — for embeddings only

### 1. Clone and configure

```bash
git clone https://github.com/Navneet072300/RunBookIQ.git
cd RunBookIQ

cp .env.example .env
```

Open `.env` and set:

```env
GROQ_API_KEY=gsk_...          # from console.groq.com
GEMINI_API_KEY=AIza...        # from aistudio.google.com (embeddings only)
POSTGRES_PASSWORD=changeme
SECRET_KEY=your-random-32-char-string
```

### 2. Start all services

```bash
docker compose up -d
```

Starts: `postgres`, `redis`, `api` (FastAPI), `worker` (RQ), `frontend` (Vite).

### 3. Run database migrations

```bash
docker compose exec api alembic upgrade head
```

### 4. Seed demo data (optional)

```bash
docker compose exec api python scripts/seed_demo.py
```

### 5. Open the UI

```text
http://localhost:5173       — React UI
http://localhost:8000/docs  — Swagger API docs
```

---

## Connect Your Kubernetes Cluster

RunbookIQ streams live events directly from your cluster and generates playbooks automatically.

### Setup

In your `.env`:

```env
K8S_KUBECONFIG=/root/.kube/config
K8S_NAMESPACE=your-namespace    # e.g. hrms, production, default
```

In `docker-compose.yml` the kubeconfig is already mounted:

```yaml
volumes:
  - ${HOME}/.kube:/root/.kube:ro
```

Start the stack — the watcher auto-starts on API startup:

```bash
docker compose up -d
docker compose logs -f api | grep k8s
# k8s_watcher_started  namespace=your-namespace ✓
```

Every pod crash, OOMKill, BackOff, or node pressure event now flows into RunbookIQ and generates a triage playbook automatically.

---

## Architecture

```text
Kubernetes Events / Prometheus / Zabbix
              │
              ▼
  POST /api/v1/alerts/ingest   ◄── K8s watcher (live stream)
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
              ├─ Groq Llama 3.3 70B  ──►  structured PlaybookResponse
              │
              ├─ Slack Block Kit notification
              │
              └─ SSE stream  ──►  React frontend
```

---

## API Reference

| Method | Path | Description |
| ------ | ---- | ----------- |
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

**Prometheus Alertmanager config:**

```yaml
receivers:
  - name: runbookiq
    webhook_configs:
      - url: http://<your-host>:8000/api/v1/alerts/ingest
        send_resolved: true

route:
  receiver: runbookiq
```

---

## Runbook Indexing

Upload your runbooks via the UI or API — they are chunked, embedded, and used as context when generating playbooks.

```bash
curl -X POST http://localhost:8000/api/v1/runbooks/upload \
  -F "file=@./runbooks/redis-oom.md" \
  -F "name=Redis OOM Runbook" \
  -F "tags=redis,memory,oom"
```

Supported formats: `.md`, `.txt`, `.pdf`, `.docx`

---

## Environment Variables

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `GROQ_API_KEY` | ✅ | — | Groq API key — [console.groq.com](https://console.groq.com) |
| `GROQ_BASE_URL` | | `https://api.groq.com/openai/v1` | Groq OpenAI-compat endpoint |
| `LLM_MODEL` | | `llama-3.3-70b-versatile` | Groq model to use |
| `GEMINI_API_KEY` | ✅ | — | Google Gemini key for embeddings only |
| `EMBEDDING_MODEL` | | `text-embedding-004` | Embedding model (768 dims) |
| `DATABASE_URL` | ✅ | — | `postgresql+asyncpg://user:pass@host/db` |
| `REDIS_URL` | ✅ | — | `redis://host:6379/0` |
| `POSTGRES_PASSWORD` | ✅ | — | PostgreSQL password |
| `SECRET_KEY` | ✅ | — | 32-char random string |
| `APP_ENV` | | `development` | `development` or `production` |
| `LOG_LEVEL` | | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `K8S_KUBECONFIG` | Optional | — | Path to kubeconfig inside container |
| `K8S_NAMESPACE` | Optional | `default` | Namespace to watch |
| `SLACK_WEBHOOK_URL` | Optional | — | Slack incoming webhook |
| `ZABBIX_API_URL` | Optional | — | Zabbix API URL |
| `PROMETHEUS_ALERTMANAGER_URL` | Optional | — | Alertmanager base URL |

---

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest
```

---

## Helm Deployment (Kubernetes)

```bash
kubectl create secret generic runbookiq-secrets \
  --from-literal=GROQ_API_KEY=gsk_... \
  --from-literal=GEMINI_API_KEY=AIza... \
  --from-literal=DATABASE_URL=postgresql+asyncpg://... \
  --from-literal=REDIS_URL=redis://... \
  --from-literal=SECRET_KEY=...

helm install runbookiq ./helm/runbookiq \
  --set ingress.hosts[0].host=runbookiq.yourdomain.com \
  --set api.image.tag=1.0.0
```

---

## Local Development (without Docker)

**Backend:**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
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

## Project Structure

```text
RunBookIQ/
├── backend/
│   ├── alembic/              # Database migrations
│   ├── app/
│   │   ├── api/              # FastAPI route handlers
│   │   ├── core/             # Config, logging, Redis, DB session
│   │   ├── embeddings/       # Gemini embedder + runbook ingest
│   │   ├── ingestion/        # Alert normaliser + K8s/Prometheus/Zabbix connectors
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── rag/              # RAG orchestrator + Groq LLM caller
│   │   ├── remediation/      # kubectl runner + remediation registry
│   │   ├── schemas/          # Pydantic schemas
│   │   └── main.py
│   ├── scripts/
│   │   └── seed_demo.py
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/              # Axios API client
│       ├── components/       # React components
│       └── pages/            # Route pages
├── helm/runbookiq/           # Helm chart
├── assets/                   # Screenshots
├── docker-compose.yml
└── .env.example
```

---

## License

MIT
