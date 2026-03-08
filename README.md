# APDA - AI-Powered Data Analytics

APDA lets you query Singapore government policy datasets using plain English. A multi-agent pipeline powered by `pydantic-ai` and `pydantic-graph` interprets your question, selects relevant datasets, runs SQL via DuckDB, and streams results back to the browser in real time over Server-Sent Events (SSE).

Demo:

https://github.com/user-attachments/assets/a6715173-e9ac-4957-8b31-f501c5e21366




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
| `OPENAI_API_KEY`           | Your OpenAI API key    |
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

| Query                                                                | Domain    |
| -------------------------------------------------------------------- | --------- |
| "What is the commuting trend of males in 2010?"                      | Transport |
| "What is the commuting trend of males in 2010 to 2015?"              | Transport |
| "What is the commuting trend of males vs females from 2010 to 2015?" | Transport |

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
