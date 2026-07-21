#!/usr/bin/env bash
# One-command local setup for AP Invoice Intelligence.
#
# Default is STANDALONE mode: SQLite, zero infrastructure — no Docker needed.
#
#   ./scripts/setup.sh                       # standalone setup (uv, deps, .env, SQLite, migrations)
#   ./scripts/setup.sh --all                 # setup + seed + tests + live demo (recommended first run)
#   ./scripts/setup.sh -i                    # interactive: prompts for the choices below
#
# Database:
#   --sqlite                 standalone SQLite file (default)
#   --postgres               PostgreSQL via docker compose (bundled container)
#   --db-url <URL>           external database DSN (managed Postgres or a SQLite path)
#   --no-start               with --postgres: write config but don't start the container
#
# LLM provider (mandatory at runtime for extraction + decisions):
#   --llm <provider>         claude | openai | gemini        (default: claude)
#   --llm-key <key>          API key for the chosen provider
#                            (also read from AP_ANTHROPIC_API_KEY / AP_OPENAI_API_KEY / AP_GEMINI_API_KEY)
#
# Server:
#   --api-port <n>           REST API port                   (default: 8000)
#   --mcp-port <n>           MCP server port                 (default: 8080)
#   --email-backend <mode>   console | smtp                  (default: console; console logs the OTP)
#
# Extras:
#   --seed                   create a demo org + API key
#   --seed-email <email>     email for the seeded owner account
#   --verify                 run the full test suite (unit + integration)
#   --demo                   run the live end-to-end demo
#   --all                    --seed + --verify + --demo
#
# Configuration options only apply when .env is first created — an existing
# .env is never overwritten (edit it directly instead).
# Idempotent: safe to re-run.
set -euo pipefail

# --- locate repo root (this script lives in scripts/) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

say()  { printf '\n\033[1;36m==>\033[0m \033[1m%s\033[0m\n' "$1"; }
ok()   { printf '    \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '    \033[33m!\033[0m %s\n' "$1"; }
die()  { printf '\n\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

# --- defaults ---------------------------------------------------------------
MODE=sqlite                 # sqlite | postgres | external
DB_URL=""
LLM_PROVIDER=claude
LLM_KEY=""
API_PORT=8000
MCP_PORT=8080
EMAIL_BACKEND=console
SEED=false
SEED_EMAIL="${AP_SEED_EMAIL:-}"
VERIFY=false
DEMO=false
START_DB=true
INTERACTIVE=false
CONFIG_FLAGS=false          # any option that shapes .env was passed

# --- argument parsing -------------------------------------------------------
need_value() { [ "$#" -ge 2 ] || die "Option $1 requires a value."; }
while [ "$#" -gt 0 ]; do
    case "$1" in
        --sqlite) MODE=sqlite; CONFIG_FLAGS=true ;;
        --postgres) MODE=postgres; CONFIG_FLAGS=true ;;
        --db-url) need_value "$@"; MODE=external; DB_URL="$2"; CONFIG_FLAGS=true; shift ;;
        --llm) need_value "$@"; LLM_PROVIDER="$2"; CONFIG_FLAGS=true; shift ;;
        --llm-key) need_value "$@"; LLM_KEY="$2"; CONFIG_FLAGS=true; shift ;;
        --api-port) need_value "$@"; API_PORT="$2"; CONFIG_FLAGS=true; shift ;;
        --mcp-port) need_value "$@"; MCP_PORT="$2"; CONFIG_FLAGS=true; shift ;;
        --email-backend) need_value "$@"; EMAIL_BACKEND="$2"; CONFIG_FLAGS=true; shift ;;
        --seed) SEED=true ;;
        --seed-email) need_value "$@"; SEED_EMAIL="$2"; SEED=true; shift ;;
        --verify) VERIFY=true ;;
        --demo) DEMO=true; SEED=true ;;
        --all) SEED=true; VERIFY=true; DEMO=true ;;
        --no-start) START_DB=false ;;
        -i|--interactive) INTERACTIVE=true ;;
        -h|--help) grep '^#' "$0" | tail -n +2 | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) die "Unknown option: $1 (see --help)" ;;
    esac
    shift
done

case "$LLM_PROVIDER" in claude|openai|gemini) ;; *) die "--llm must be claude, openai, or gemini." ;; esac
case "$EMAIL_BACKEND" in console|smtp) ;; *) die "--email-backend must be console or smtp." ;; esac
case "$API_PORT$MCP_PORT" in *[!0-9]*) die "--api-port / --mcp-port must be numeric." ;; esac

# --- interactive configuration ----------------------------------------------
if [ "$INTERACTIVE" = true ]; then
    [ -t 0 ] || die "--interactive needs a terminal (stdin is not a TTY)."
    if [ -f .env ]; then
        warn ".env already exists — interactive answers only affect optional steps."
    fi
    say "Interactive setup"
    printf '  Database [1] SQLite standalone (default)  [2] PostgreSQL via Docker  [3] custom URL: '
    read -r a
    case "${a:-1}" in
        2) MODE=postgres ;;
        3) printf '  Database URL: '; read -r DB_URL
           [ -n "$DB_URL" ] || die "A database URL is required for option 3."
           MODE=external ;;
        *) MODE=sqlite ;;
    esac
    printf '  LLM provider [1] claude (default)  [2] openai  [3] gemini: '
    read -r a
    case "${a:-1}" in 2) LLM_PROVIDER=openai ;; 3) LLM_PROVIDER=gemini ;; *) LLM_PROVIDER=claude ;; esac
    printf '  %s API key (Enter to skip and add to .env later): ' "$LLM_PROVIDER"
    read -r LLM_KEY
    printf '  REST API port [8000]: ';  read -r a; API_PORT="${a:-8000}"
    printf '  MCP server port [8080]: '; read -r a; MCP_PORT="${a:-8080}"
    printf '  Seed a demo org + API key? [y/N]: '; read -r a
    case "$a" in y|Y) SEED=true ;; esac
    printf '  Run the test suite after setup? [y/N]: '; read -r a
    case "$a" in y|Y) VERIFY=true ;; esac
    printf '  Run the live end-to-end demo? [y/N]: '; read -r a
    case "$a" in y|Y) DEMO=true; SEED=true ;; esac
    CONFIG_FLAGS=true
fi

# A pre-existing .env decides the database mode on re-runs (never overwritten):
# the app reads .env, so following flags instead would set up the wrong database.
if [ -f .env ]; then
    ENV_DB_URL="$(sed -n 's/^AP_DATABASE_URL=//p' .env | head -1)"
    case "$ENV_DB_URL" in
        postgresql+asyncpg://ap:ap_password@localhost*) MODE=postgres ;;
        postgres*) MODE=external ;;
        sqlite*|"") MODE=sqlite ;;
        *) MODE=external ;;
    esac
    if [ "$CONFIG_FLAGS" = true ]; then
        warn "Configuration options are ignored: .env already exists (edit it directly). Mode: ${MODE}."
    fi
fi

# The shell may pre-set VIRTUAL_ENV to a path uv should ignore.
unset VIRTUAL_ENV || true

# --- 1. prerequisites -------------------------------------------------------
say "Checking prerequisites"
command -v curl >/dev/null 2>&1 || die "curl is required."
if [ "$MODE" = postgres ]; then
    command -v docker >/dev/null 2>&1 || die "Docker is required for --postgres mode. Install Docker and retry (or rerun without --postgres for standalone SQLite)."
    docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required for --postgres mode."
    ok "curl + Docker + Compose found (PostgreSQL mode)"
elif [ "$MODE" = external ]; then
    ok "curl found (external database mode — no local database to manage)"
else
    ok "curl found (standalone SQLite mode — no Docker needed)"
fi

# --- 2. uv (Python toolchain) ----------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
    say "Installing uv (Python package manager)"
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
command -v uv >/dev/null 2>&1 || die "uv install failed; add ~/.local/bin to PATH and retry."
ok "uv $(uv --version | awk '{print $2}')"

# --- 3. dependencies --------------------------------------------------------
say "Installing dependencies (uv sync)"
uv sync --extra dev
ok "Virtualenv ready at .venv"

# --- 4. .env (generate secrets once) ---------------------------------------
case "$MODE" in
    postgres) DB_URL="postgresql+asyncpg://ap:ap_password@localhost:5432/ap_invoice" ;;
    sqlite)   DB_URL="sqlite+aiosqlite:///./ap_invoice.db" ;;
    external) ;;  # provided via --db-url / interactive prompt
esac

# Per-provider key: --llm-key wins, then the matching AP_* environment variable.
ANTHROPIC_KEY="${AP_ANTHROPIC_API_KEY:-}"
OPENAI_KEY="${AP_OPENAI_API_KEY:-}"
GEMINI_KEY="${AP_GEMINI_API_KEY:-}"
if [ -n "$LLM_KEY" ]; then
    case "$LLM_PROVIDER" in
        claude) ANTHROPIC_KEY="$LLM_KEY" ;;
        openai) OPENAI_KEY="$LLM_KEY" ;;
        gemini) GEMINI_KEY="$LLM_KEY" ;;
    esac
fi

if [ -f .env ]; then
    say ".env already exists — leaving it untouched"
else
    say "Creating .env with generated secrets"
    PEPPER="$(uv run python -c 'import secrets; print(secrets.token_urlsafe(48))')"
    JWT="$(uv run python -c 'import secrets; print(secrets.token_urlsafe(48))')"
    cat > .env <<EOF
# Generated by scripts/setup.sh — local development only. Do not commit.
AP_ENVIRONMENT=development
AP_LOG_JSON=false
# SQLite = standalone mode; point at a postgresql+asyncpg:// DSN for PostgreSQL
# (see .env.example for both forms).
AP_DATABASE_URL=${DB_URL}
AP_API_KEY_PEPPER=${PEPPER}
AP_JWT_SECRET=${JWT}
AP_API_PORT=${API_PORT}
AP_MCP_PORT=${MCP_PORT}
# Email OTP delivery: 'console' logs the code; 'smtp' sends it (set AP_SMTP_* too).
AP_EMAIL_BACKEND=${EMAIL_BACKEND}
# LLM provider (mandatory) — handles extraction (vision) + decision.
AP_LLM_PROVIDER=${LLM_PROVIDER}
AP_ANTHROPIC_API_KEY=${ANTHROPIC_KEY}
AP_OPENAI_API_KEY=${OPENAI_KEY}
AP_GEMINI_API_KEY=${GEMINI_KEY}

# Used by docker compose for the Postgres container (--postgres mode only).
POSTGRES_USER=ap
POSTGRES_PASSWORD=ap_password
POSTGRES_DB=ap_invoice
EOF
    ok "Wrote .env (secrets generated; database: ${DB_URL})"
    case "$LLM_PROVIDER" in
        claude) [ -n "$ANTHROPIC_KEY" ] || warn "No Claude API key yet — set AP_ANTHROPIC_API_KEY in .env before processing invoices." ;;
        openai) [ -n "$OPENAI_KEY" ]    || warn "No OpenAI API key yet — set AP_OPENAI_API_KEY in .env before processing invoices." ;;
        gemini) [ -n "$GEMINI_KEY" ]    || warn "No Gemini API key yet — set AP_GEMINI_API_KEY in .env before processing invoices." ;;
    esac
fi

# Ports may come from a pre-existing .env rather than this run's flags.
EFFECTIVE_API_PORT="$(sed -n 's/^AP_API_PORT=//p' .env | head -1)"
EFFECTIVE_API_PORT="${EFFECTIVE_API_PORT:-8000}"
EFFECTIVE_MCP_PORT="$(sed -n 's/^AP_MCP_PORT=//p' .env | head -1)"
EFFECTIVE_MCP_PORT="${EFFECTIVE_MCP_PORT:-8080}"

if [ "$MODE" = postgres ] && [ "$START_DB" = false ]; then
    say "Skipping database start (--no-start). Run 'make db-up && make migrate' when ready."
    exit 0
fi

# --- 5. database ------------------------------------------------------------
if [ "$MODE" = postgres ]; then
    say "Starting PostgreSQL (docker compose)"
    docker compose up -d postgres
    printf '    waiting for Postgres'
    for _ in $(seq 1 30); do
        if docker compose exec -T postgres pg_isready -U ap -d ap_invoice >/dev/null 2>&1; then
            printf '\n'; ok "Postgres is ready"; break
        fi
        printf '.'; sleep 1
    done
    docker compose exec -T postgres pg_isready -U ap -d ap_invoice >/dev/null 2>&1 \
        || die "Postgres did not become ready in time."

    # Create the dedicated test database (best effort; ignored if it exists).
    docker compose exec -T postgres createdb -U ap ap_invoice_test >/dev/null 2>&1 \
        && ok "Created test database 'ap_invoice_test'" \
        || ok "Test database already present"
elif [ "$MODE" = external ]; then
    say "External database mode: using the configured AP_DATABASE_URL"
    ok "No local database to start"
else
    say "Standalone mode: SQLite database file (created on first use)"
    ok "No database server to start"
fi

# --- 6. migrations ----------------------------------------------------------
say "Applying database migrations"
uv run alembic upgrade head
ok "Schema is up to date"

# --- 7. optional demo seed --------------------------------------------------
if [ "$SEED" = true ]; then
    say "Bootstrapping the first owner account + API key"
    SEED_EMAIL="${SEED_EMAIL:-owner-$(date +%s)@example.com}"
    uv run python scripts/seed.py --email "$SEED_EMAIL"
fi

# --- 8. optional: run the test suite ----------------------------------------
if [ "$VERIFY" = true ]; then
    say "Running the full test suite (unit + integration)"
    if [ "$MODE" = postgres ]; then
        uv run pytest -q
    else
        # Point the suite at a throwaway SQLite file instead of the Postgres
        # test database (conftest's default when the variable is unset).
        AP_DATABASE_URL="sqlite+aiosqlite:///./ap_invoice_test.db" uv run pytest -q
        rm -f ./ap_invoice_test.db
    fi
    ok "All tests passed"
fi

# --- 9. optional: live end-to-end demo --------------------------------------
if [ "$DEMO" = true ]; then
    say "Running the live end-to-end demo (starting the API briefly)"
    uv run uvicorn ap_invoice.api.main:app --host 127.0.0.1 --port "$EFFECTIVE_API_PORT" \
        >/tmp/ap_demo_api.log 2>&1 &
    DEMO_API_PID=$!
    # shellcheck disable=SC2064
    trap "kill ${DEMO_API_PID} 2>/dev/null || true" EXIT
    printf '    waiting for the API'
    for _ in $(seq 1 30); do
        if curl -fs -o /dev/null "http://127.0.0.1:${EFFECTIVE_API_PORT}/health/ready" 2>/dev/null; then
            printf '\n'; break
        fi
        printf '.'; sleep 1
    done
    curl -fs -o /dev/null "http://127.0.0.1:${EFFECTIVE_API_PORT}/health/ready" 2>/dev/null \
        || die "API did not start (see /tmp/ap_demo_api.log)."
    uv run python scripts/demo.py
    kill "${DEMO_API_PID}" 2>/dev/null || true
    trap - EXIT
fi

# --- done -------------------------------------------------------------------
say "Setup complete 🎉"
cat <<EOF
Run the services (each in its own shell):
  make run-api     # REST API  → http://127.0.0.1:${EFFECTIVE_API_PORT}/docs
  make run-mcp     # MCP server → http://127.0.0.1:${EFFECTIVE_MCP_PORT}/mcp

Handy commands:
  make seed        # create a demo account + API key (prints login + key)
  make demo        # live end-to-end walkthrough (needs the API running)
  make test        # unit tests        |   make test-int   # integration tests

Create your own account instead of seeding:
  curl -s -X POST http://127.0.0.1:${EFFECTIVE_API_PORT}/auth/register \\
    -H "content-type: application/json" \\
    -d '{"email":"you@example.com","password":"a-strong-password"}'
  # the OTP is printed to the API log (AP_EMAIL_BACKEND=console); then:
  #   POST /auth/verify  {email, code}   → returns a session token
  #   POST /auth/login   {email, password} → returns a session token

Connect a Claude client (with the MCP server running and an org key):
  claude mcp add --transport http ap-invoice http://localhost:${EFFECTIVE_MCP_PORT}/mcp \\
    --header "Authorization: Bearer <your-org-api-key>"
  # full guide: docs/local-testing.md

The LLM is mandatory (extraction + decision). Set the provider in .env:
  AP_LLM_PROVIDER=claude   AP_ANTHROPIC_API_KEY=sk-ant-...   # or openai / gemini

Your API-key pepper and JWT secret are in .env.
EOF
