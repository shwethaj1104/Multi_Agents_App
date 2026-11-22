# LoanDesk developer guide

This is the single implementation and operations reference. The root [README](../README.md) provides the portfolio overview and evaluation screenshot. [AGENTS.md](../AGENTS.md) retains contributor instructions.

## Product and scope

LoanDesk prepares evidence-backed business loan assessments and compares a generalist agent against a supervisor with three parallel specialists. A human reviews and signs off on each assessment. This portfolio application uses fictional lending policy and synthetic inputs; it does not authenticate financial documents, issue credit, or move funds.

The interface has Applications, Human approvals, Evaluations and Review workflow. One shared frontend switches between independently runnable backend modes. Saved applications belong to an architecture workspace; comparison experiments create separate records with identical inputs for each mode.

## Architecture

React and TypeScript provide the interface. Redux Toolkit stores architecture/navigation state; RTK Query handles server caches. Python/FastAPI exposes the APIs. LangGraph orchestrates checkpointed workflows and interrupts; LangChain implements the model/tool loops. MongoDB stores application records, reviews, experiments, budget reservations and graph checkpoints. Uploaded files live in the ignored `.runtime/uploads` directory.

Single-agent flow:

1. Load the application and evidence snapshot.
2. One generalist investigates documents, financial checks and policy using shared tools.
3. Code validates sources and calculates the authoritative report values.
4. Persist the report and pause for human review.

Multi-agent flow:

1. Code dispatches the three fixed initial responsibilities without a planning model call.
2. Document, financial and policy specialists run in parallel with the same case snapshot.
3. The supervisor synthesizes their findings with verified evidence, financial checks and policy supplied directly by code.
4. Validate citations, assemble the report and pause for human review.
5. Human feedback can invoke targeted planning. Changed evidence requires all specialists to recheck dependent findings.

A clean multi-agent run is expected to use roughly seven model calls, but tool investigation and structured-output correction can add calls. This is not a guaranteed count or a measured performance claim. The generalist retains equivalent tool access and approval requirements.

[Single-agent diagram](diagrams/single-agent-flow.png) · [Multi-agent diagram](diagrams/multi-agent-flow.png)

The diagram source is `diagrams/render.m`. Rebuild from the repository root with:

```sh
clang -framework AppKit developer-guide/diagrams/render.m -o /tmp/loandesk-render
/tmp/loandesk-render
```

## Repository layout

```text
frontend/
  src/app/                  Store, providers, navigation and architecture state
  src/components/           Shared layout and UI controls
  src/features/             Applications, approvals, reviews and evaluations
  src/services/api/         RTK Query endpoints and artifact downloads
  src/styles/               Palette, dropdowns and shared spacing
  src/types/                API contracts and domain aliases
  src/tests/                Routing, cache and measurement rendering checks
backend/
  src/loandesk/
    api/                    Thin routes and dependencies
    domain/                 Validated input, report and decision contracts
    services/               Application ownership and review lifecycle
    agents/                 Generalist, specialists and supervisor adapters
    workflows/              Shared LangGraph topology
    tools/                  Evidence, decimal financial checks and policy retrieval
    infrastructure/         Storage, document parsing, models and telemetry
    repositories/           Optimistic persistence adapters
    evaluation/             Paired benchmark and LangSmith publishing
    core/                   Private server configuration
  scripts/                  Launch, connection diagnostics and sample-record reset
  tests/                    Offline financial, workflow, persistence and safety checks
data/lending_policies/      Runtime fictional policy (required)
evaluations/datasets/       Runtime labeled development benchmark (required)
developer-guide/            This guide and workflow diagrams
Results/                   Evaluation screenshot used by the root README
```

`sample_case_service.py` and `evaluations/datasets/development-cases.json` are required by the evaluation dashboard and tests. They are not disposable upload files. Removing them breaks paired comparisons. The application list hides benchmark-generated sample cases.

## Local setup

Requirements: Python 3.11+, uv, a Node version compatible with `frontend/package.json`, npm, and configured MongoDB Atlas access.

On a fresh checkout, copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env.local`. Never overwrite an existing private configuration. Install dependencies:

```sh
npm --prefix frontend ci
cd backend
uv sync --frozen --extra dev
```

From the repository root, run these in three separate terminals:

```sh
bash backend/scripts/run-single-agent.sh
```

```sh
bash backend/scripts/run-multi-agent.sh
```

```sh
npm --prefix frontend run dev
```

Open http://localhost:5173. The APIs use ports 8011 and 8012. Vite proxies `/api/single-agent` and `/api/multi-agent` to the corresponding backend, rewriting each prefix to `/api`. API documentation is at `/docs` on each backend. Production hosting must provide equivalent proxy routes; Vite preview is not a production API proxy.

## Configuration and external services

Settings load `backend/.env` regardless of launch directory. Actual environment variables take precedence. The launch scripts assign the mode for each API process. Never expose OpenAI, MongoDB or LangSmith credentials to frontend environment variables.

- `MONGODB_URI`: Atlas connection string. Keep `LOANDESK_STORAGE_BACKEND=mongodb` and the selected `MONGODB_DATABASE`.
- `OPENAI_API_KEY`: private provider credential entered by the user.
- `LOANDESK_LIVE_MODEL_CALLS_ENABLED`: independent execution gate; default false. A key alone does not enable calls.
- `LOANDESK_MODEL`: configured model; the default is `gpt-5.6-luna`. Pricing must exist in the versioned table before invocation.
- `LOANDESK_REASONING_EFFORT` and `LOANDESK_MAX_OUTPUT_TOKENS`: reasoning/output limits.
- `LOANDESK_MAX_MODEL_CALLS_PER_REVIEW`, `LOANDESK_REVIEW_BUDGET_USD` and `LOANDESK_SESSION_BUDGET_USD`: application reservation limits, not provider billing guarantees.
- `LOANDESK_ACCESS_TOKEN`: optional workspace API access credential; this is not a complete user identity or bank authorization system.

Reviews and comparisons use live execution when explicitly started from the UI. Opening a view or changing architecture does not invoke a model. Disabled calls or missing credentials fail without an offline or paid-provider fallback. Offline fixtures remain for explicit automated development tests. Never restore credentials, enable live execution or run paid benchmarks without user authorization.

Both modes use the OpenAI Responses API for reasoning with function tools. SDK automatic model retries are disabled. No application-side arithmetic is delegated to model reasoning.

### MongoDB

Create/select an Atlas project and cluster, configure a database user, and add the current public IP under Network Access. Wait for an Active entry before connecting. Verify cluster availability, credentials and VPN/firewall settings if startup fails. TLS validation stays enabled and MongoDB failures never silently switch storage.

Connectivity-only diagnostic from the repository root:

```sh
backend/.venv/bin/python backend/scripts/check_database.py
```

SQLite adapters exist for isolated automated tests; they are not the selected manual application store. `.runtime` must not be committed or deleted as part of ordinary code cleanup.

### LangSmith

Configure `LANGSMITH_API_KEY`, the correct regional `LANGSMITH_ENDPOINT`, and either agent addressing (`LANGSMITH_AGENT_ID` with `LANGSMITH_AGENT_ENVIRONMENT`) or legacy `LANGSMITH_PROJECT` addressing. Enable `LANGSMITH_TRACING` only for an intended tracing destination. Restart both APIs after changing configuration.

Traces correlate review IDs, architecture, agent roles, tool activity, timings, provider usage and estimated cost. Costs are estimated from leaf model calls; reasoning tokens already included in output totals are not counted twice. Unknown usage remains unknown. Review processing time excludes human waiting. Budget reservations for uncertain failures are not automatically assumed free.

Inspect both the app and hosted traces after an explicitly authorized live run. A passing offline test does not prove provider access or successful trace delivery. Publishing a completed experiment sends saved results; it does not rerun the model.

## Evidence and approval behavior

Uploads accept PDF, CSV, JSON and TXT, up to 5 MB. PDFs must contain extractable text; OCR for scanned documents is not implemented. JSON/text financial statements label `annual_revenue`, `annual_expenses` and `annual_debt_service`. Bank CSV uses `date,amount,category`; positive income rows have category `income`, covering twelve consecutive months. Values are AED.

Files are parsed and versioned. A later document of the same type is used for current checks while earlier evidence remains in history. Identical duplicate uploads are rejected. Documents and reviewer notes are treated as untrusted inputs, never executable instructions. Models must cite known document IDs; financial values use decimal calculations and policy checks in code.

Human actions are approve, reject, request changes and provide information. Approval binds to a report revision and evidence version. Changed evidence invalidates previous sign-off. The register shows the latest review state; it shows Needs review when that review used older evidence. Reviewer names are operator-entered, not verified bank identities. Approval signs off on an assessment only.

## Evaluations

The dashboard runs both architectures on the same selected development cases. It uses its built-in labeled dataset, not arbitrary manually uploaded applications. Case counts 1–5 produce 2–10 assessments. It does not automatically approve those assessments.

The interface shows six quality rings and three resource comparisons:

| Measurement | Interpretation |
| --- | --- |
| Assessments generated | Share of reviews that produced a report |
| Finding precision / recall | Agent-selected issue codes against reference labels |
| Tool calculation accuracy | Authoritative installment versus reference |
| Guardrail recommendation accuracy | Code-enforced recommendation versus reference |
| Citation ID validity | Known document references, not semantic grounding |
| Mean / p95 processing time | Review processing wall time, excluding human waiting |
| Mean model cost | Estimated provider-token cost; unknown stays unavailable |

The current scorer assigns zero to all six quality metrics when no report was generated. A failed review is therefore not evidence that every underlying calculation was independently wrong. Inspect per-case status and review errors. Time and cost can still accrue on failures. An experiment can finish processing all cases while individual reviews fail.

The five development fixtures are a smoke-test set, not a held-out generalization benchmark. Ragas, paid LLM judging, semantic grounding and statistically robust repeated comparisons are not implemented. Avoid claiming that either architecture wins universally. Compare runs using consistent prompts, models, settings and input cases; historical runs may precede optimizations.

Exports support CSV and JSON through the Export menu. Changing the displayed experiment never runs models.

## Verification

Run from the repository root:

```sh
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run test
npm --prefix frontend run build
backend/.venv/bin/pytest backend/tests -q
backend/.venv/bin/ruff check backend
```

Automated tests isolate storage and mock provider execution. Verify both architectures, real monetary calculations, parallel fan-out/fan-in, revision-bound approval, stale evidence, API gates, usage accounting and cache ownership. Live checks require separate explicit authorization. Do not create fake measured results.

Manual smoke test: create an application, attach documents, explicitly run a review, inspect sources/activity/cost, approve the exact report revision, refresh and verify persistence. Repeat with identical input in the other mode. Run a one-case comparison first if authorized; inspect individual outcomes and traces before broadening the benchmark.

## UI and coding conventions

The palette is primary `#233a50`, white and primary shades. Apply the user-invoked `shwetha-ui-design` skill for UI changes. All pages use shared compact spacing and responsive layouts. Status has explicit text; color is supplementary. The workflow animation is a process illustration, not live telemetry; it respects reduced motion and pauses offscreen or in hidden tabs. Dropdowns use native form semantics with modern picker styling and a native fallback.

Use explicit filenames: `financial_review_agent.py`, not `agent2.py` or `utils.py`. Python uses snake_case and PascalCase classes; React uses PascalCase component filenames and kebab-case feature folders. Keep routes thin and financial logic in shared tools. Do not introduce empty abstraction layers or agents without distinct responsibilities.

Every authored named function, method, component and custom hook needs a concise explanation immediately above it: Python comment/docstring or TypeScript JSDoc. Explain purpose, relevant inputs/outputs, side effects and failure/approval behavior. These are developer comments, not a request to print sensitive runtime data.

RTK Query owns remote state, Redux owns cross-page client state, and component state owns local form interaction. Architecture belongs in API cache keys and captured mutation arguments. Never store File objects or secrets in Redux. Keep API types aligned with FastAPI OpenAPI, preserve lockfiles, and keep secrets/configuration server-side.

## Maintenance and recovery

The manual upload fixture kit, its generator, unused scaffold directories and redundant Markdown files were removed. The evaluation screenshot is stored at `Results/Evaluation_matrix.png`. Source, lockfiles, configuration templates, runtime policy, evaluation dataset, automated tests and private local configuration remain intact.

`backend/scripts/reset_sample_records.py` is a destructive maintenance utility: use only when explicitly asked to clear synthetic samples. It backs up matched records, checks for active work, and removes sample applications, their reviews/checkpoints and development experiments transactionally. It preserves manual applications and budget records. Ordinary UI or file cleanup must never invoke it automatically.
