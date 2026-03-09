# APDA - AI-Powered Data Analytics

APDA lets you query Singapore government policy datasets using plain English. A multi-agent pipeline powered by `pydantic-ai` and `pydantic-graph` interprets your question, selects relevant datasets, runs SQL via DuckDB, and streams results back to the browser in real time over Server-Sent Events (SSE).

Demo:

https://github.com/user-attachments/assets/a6715173-e9ac-4957-8b31-f501c5e21366

Equivalent traces and spans during the demo run:

<img width="835" height="645" alt="image" src="https://github.com/user-attachments/assets/71800f3f-49b2-4a5f-bca2-3043da5e9b38" />

---

## Architecture

APDA uses a finite-state machine (FSM) pipeline of 9 nodes that carries a query from intent classification through data extraction, normalization, and analysis. See [ARCHITECTURE.md](ARCHITECTURE.md) for a full breakdown.

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- Node.js >= 22 and [npm](https://www.npmjs.com/)
- An OpenAI API key
- A GCP API Key
- (Optional) A [Logfire](https://logfire.pydantic.dev/) token, main observability instrumentation for this repo

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/BuddyLim/adpa
cd apda-govtech
```

### 2. Configure environment variables

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and fill in:

| Variable                   | Description            |
| -------------------------- | ---------------------- |
| `OPENAI_KEY`               | Your OpenAI API key    |
| `GCP_KEY`                  | Your GCP API key       |
| `LOGFIRE_TOKEN` (Optional) | Pydantic Logfire token |

### 3. Start the backend

```bash
cd backend
docker compose up --build
```

The API will be available at `http://localhost:8000`.

### 4. Start the frontend

```bash
cd frontend
npm install
npm dev
```

The UI will be available at `http://localhost:3000`.

---

## Running Locally

| Service     | URL                          | Command                                       |
| ----------- | ---------------------------- | --------------------------------------------- |
| Backend API | `http://localhost:8000`      | `docker compose up --build` (from `backend/`) |
| Frontend    | `http://localhost:3000`      | `npm dev` (from `frontend/`)                  |
| API docs    | `http://localhost:8000/docs` | Served automatically by FastAPI               |

---

## Running Tests

### Unit and integration tests

```bash
cd backend
pytest tests/ -v
```

### LLM evaluation tests (makes real LLM calls)

```bash
cd backend
pytest evals/ -v -s
```

### Frontend tests (Vitest)

```bash
cd frontend
npm test
npm test:coverage
```

See [TESTING.md](TESTING.md) for a full description of the testing strategy, eval thresholds, and hallucination detection.

---

## Sample Queries

| Query                                                                                | Domain    |
| ------------------------------------------------------------------------------------ | --------- |
| "What is the percentage of people taking public transport in 2015?"                  | Transport |
| "What are the difference between males and females taking public transport in 2015?" | Transport |
| "What is the trend in terms of age for public transport in 2010 to 2015?"            | Transport |

---

## CI/CD & Deployment

### Workflows

| Workflow           | Trigger                      | What it does                                                            |
| ------------------ | ---------------------------- | ----------------------------------------------------------------------- |
| `ci-cd.yaml`       | Push / PR to `main`          | Secret scan, tests; auto-deploys to App Runner on push if files changed |
| `aws-deploy.yml`   | Manual (`workflow_dispatch`) | Deploy backend, frontend, or both to a target environment               |
| `aws-teardown.yml` | Manual (`workflow_dispatch`) | Delete App Runner services and clear ECR images                         |

### Infrastructure

- **Cloud**: AWS `ap-southeast-1`
- **Hosting**: AWS App Runner — `apda-backend` (port 8000), `apda-frontend` (port 3000)
- **Images**: ECR repositories `apda/backend:latest` and `apda/frontend:latest`
- **Auth**: GitHub OIDC → IAM role `github-actions` (no long-lived AWS credentials stored)

### Deployment Flow

1. Backend image is built and pushed to ECR
2. App Runner service is created (first run) or updated
3. Frontend image is built with `VITE_API_URL` injected as a Docker build arg — the backend URL is **baked into the bundle** at build time
4. Frontend App Runner service is created or updated

> If the backend URL ever changes, the frontend must be redeployed to pick it up.

### One-time AWS Setup

1. **OIDC provider** — IAM → Identity providers → add `token.actions.githubusercontent.com` with audience `sts.amazonaws.com`
2. **`github-actions` IAM role** — trusted by the OIDC provider scoped to `repo:BuddyLim/adpa:environment:DEV`; needs permissions for ECR push, App Runner create/update, and `iam:PassRole` on `AppRunnerECRRole`
3. **`AppRunnerECRRole`** — trusted by `build.apprunner.amazonaws.com`, with `AmazonEC2ContainerRegistryReadOnly`

### GitHub Secrets (DEV environment)

| Secret           | Description                                                    |
| ---------------- | -------------------------------------------------------------- |
| `AWS_ACCOUNT_ID` | 12-digit AWS account number                                    |
| `OPENAI_KEY`     | OpenAI API key                                                 |
| `GCP_KEY`        | GCP service account key                                        |
| `LOGFIRE_TOKEN`  | Pydantic Logfire token                                         |
| `FRONTEND_URL`   | Frontend App Runner URL (injected into backend CORS allowlist) |

---

## Technology Choices

| Technology                       | Role                             | Reason                                                                     |
| -------------------------------- | -------------------------------- | -------------------------------------------------------------------------- |
| **FastAPI**                      | REST API and SSE streaming       | Async-first, minimal boilerplate, native `StreamingResponse` support       |
| **pydantic-ai**                  | Agent definitions and tool calls | Type-safe agent I/O, structured output, built-in retry logic               |
| **pydantic-graph**               | FSM orchestration                | Explicit node routing, backward feedback loops, type-checked state         |
| **DuckDB**                       | In-process SQL over CSV files    | Zero-ETL, runs SQL directly on CSV files with no separate database process |
| **SQLite**                       | Application state persistence    | SQLite is zero-config for local development                                |
| **TanStack Start + React Query** | Full-stack React frontend        | File-based routing, SSE streaming support, server-side rendering           |
| **Recharts**                     | Data visualizations              | Composable React chart components, good TypeScript support                 |
| **Logfire**                      | Observability                    | OpenTelemetry-native, first-class pydantic-ai trace integration            |
| **pydantic-evals**               | LLM output evaluation            | Structured scoring, threshold assertions, integrates with pytest and CI    |
