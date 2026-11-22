#!/usr/bin/env bash
set -euo pipefail
backend_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$backend_directory"
export LOANDESK_REVIEW_MODE=single_agent
exec uv run uvicorn loandesk.main:app --reload --host 127.0.0.1 --port 8011
