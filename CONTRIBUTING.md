# Contributing

Thanks for your interest in improving AP Invoice Intelligence! This guide gets
you set up and explains the workflow.

## Development setup

Prerequisites: [`uv`](https://docs.astral.sh/uv/). Docker is only needed if you
develop against PostgreSQL (the default dev database is standalone SQLite).

```bash
git clone https://github.com/AuxiLabs/auxilab-mcp-ap-invoice
cd auxilab-mcp-ap-invoice

./scripts/setup.sh      # deps + .env with secrets + SQLite migrations
make run-api            # http://127.0.0.1:8000/docs
```

To develop against PostgreSQL instead (what production runs), use
`./scripts/setup.sh --postgres`, or by hand: `make db-up`, point
`AP_DATABASE_URL` in `.env` at it, then `make migrate`.

## Quality gates

All of these must pass before a PR is merged (CI enforces them):

```bash
make lint        # ruff
make format      # ruff format + autofix
make typecheck   # mypy (strict)
make test        # unit tests (no DB needed)
make test-int    # integration tests (needs a database — see below)
```

Integration tests run against `AP_DATABASE_URL`. The simplest option is a
throwaway SQLite file:

```bash
AP_DATABASE_URL=sqlite+aiosqlite:///./ap_invoice_test.db uv run pytest -m integration
```

When the variable is unset they default to a dedicated PostgreSQL database
(`ap_invoice_test`), which is what CI and `./scripts/setup.sh --postgres`
use. Create it once with:

```bash
docker compose exec postgres createdb -U ap ap_invoice_test
```

## Conventions

- **Type everything.** `mypy` runs in strict mode.
- **Keep the service layer pure.** Tools in `services/` operate on Pydantic
  schemas, not the ORM — that keeps them unit-testable and reusable by REST, MCP,
  and the orchestrator.
- **Decisions stay deterministic.** New policy logic goes in `policy_engine.py`
  and must be reproducible and covered by unit tests.
- **Never touch lazy ORM relationships in async handlers** — query explicitly
  (see `_get_active_policy`) or you'll hit `MissingGreenlet`.
- **Schema changes** require an Alembic migration: `make revision m="..."`, then
  verify `alembic check` reports no drift.
- **Add tests** for new behaviour (unit for logic, integration for endpoints).

## Pull requests

1. Branch off `main`.
2. Make focused changes with tests and docs.
3. Ensure all quality gates pass.
4. Open a PR describing the change and the motivation.

By contributing you agree your contributions are licensed under the project's
[MIT](./LICENSE) license.
