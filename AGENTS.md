# Repository implementation guide

Read `developer-guide/README.md` before substantive implementation. It is the consolidated reference for the brief, architecture, setup, conventions and verification. Keep it and the diagrams aligned with approved design changes.

## Agreed constraints
- React + TypeScript, Redux Toolkit / RTK Query, Python / FastAPI.
- Apply the user-invoked `shwetha-ui-design` skill for UI work (`/Users/shwe/.codex/skills/shwetha-ui-design/SKILL.md`). Project palette takes priority: primary `#233a50`, secondary white; use primary shades for surfaces, borders, text and restrained gradients. Status must have explicit labels/icons, not color alone.
- One shared UI with a runtime Single agent / Multi-agent switch. Two independently runnable backend variants share services, tools, policy, output schemas and evaluation data. Requests and caches must be scoped by the architecture selected when invoked. Applications also have server-assigned workspace ownership; do not mix the saved application lists. Paired benchmarks use separate cases with identical sample inputs.
- Single-agent: one capable generalist with the same tools and approval requirements as the multi-agent system.
- Multi-agent: one supervisor within LangGraph dispatches document, financial, and policy agents built with LangChain in parallel. Supervisor joins results, requests bounded follow-ups, and drafts the memo. Do not introduce additional agents without a concrete responsibility and demonstrated need.
- Financial arithmetic, authorization, persistence, and workflow routing belong in code. Model conclusions must retain source evidence and assumptions.
- Human approval binds to a specific report revision. Changed evidence invalidates dependent findings and prior approvals.
- Synthetic data and fictional lending policy. No real credit decisions or money movement.
- LangSmith tracing and a shared benchmark; no presumption that multi-agent wins.

## Placement and naming
Follow the Repository layout and UI and coding conventions sections in `developer-guide/README.md`. Prefer explicit names such as `financial_review_agent.py`, not `agent2.py` or `utils.py`. Do not create empty abstractions, fake agent implementations, or fabricated benchmark results.

## Verification
Run the checks appropriate to the change in the Verification section of `developer-guide/README.md`. Clearly distinguish scaffolded features from implemented and verified ones. Never commit credentials, raw private documents, local databases, or generated dependency folders. External services must be configured server-side.

## Function documentation — user requirement

Every authored named function, method, React component, and custom hook must have a short plain-language explanation immediately above it (Python comment/docstring; TypeScript JSDoc). Describe purpose and relevant inputs, outputs, side effects, and failure/approval behavior. Add inline comments where business reasoning is not obvious. Keep names explicit and functions focused; extract named handlers for substantial callback logic.

The user means source-code comments for developer reference, not runtime logs or printing live data. Do not add logging solely to satisfy this requirement. Ordinary operational logging, when needed separately, must not expose secrets or sensitive data.

## Live model calls disabled — explicit user constraint

The user intentionally commented out OPENAI_API_KEY to prevent accidental charges. Do not uncomment it, restore it from another environment, or make paid/model API calls or live benchmark runs without a subsequent explicit user instruction permitting live calls. Use offline fixtures and mocks for development. Implement an independent default-off enable flag before introducing model execution, and reject live calls before provider client invocation when disabled. Missing credentials must fail clearly without paid fallback. Do not modify existing secret values.

## Observability built alongside agents — explicit user requirement

Add LangSmith instrumentation with the first agent/model implementation: per-call tokens and estimated costs, timings, retries/errors, tool spans, agent handoffs and correlated review metadata. Track review-level usage and wall-clock time separately from human waiting. Supply custom model pricing when needed; never report missing usage as zero or double-count parent totals/reasoning tokens. Verify offline with mocks before live tests. This is a separate observability requirement from the developer comments requested above; both are required. See the Architecture, LangSmith and Verification sections of `developer-guide/README.md`. Live model calls remain disabled until explicit authorization.
