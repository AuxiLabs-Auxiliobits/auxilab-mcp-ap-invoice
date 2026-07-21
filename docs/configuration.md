# Configuration

All settings come from environment variables prefixed with `AP_` (12-factor).
A local `.env` is read in development; in production inject values from your
orchestrator's secret store. See [`.env.example`](../.env.example).

## Runtime
| Variable | Default | Description |
|----------|---------|-------------|
| `AP_ENVIRONMENT` | `development` | `development` / `staging` / `production` / `test`. `test` uses a NullPool DB engine. |
| `AP_LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `AP_LOG_JSON` | `true` | JSON logs (prod) vs. console logs (dev) |

## Database

`AP_DATABASE_URL` selects the mode: SQLite (standalone, zero infrastructure —
the default) or PostgreSQL (production). Driverless DSNs (`postgresql://…`,
`sqlite://…`) are accepted; the async driver is added automatically.

| Variable | Default | Description |
|----------|---------|-------------|
| `AP_DATABASE_URL` | `sqlite+aiosqlite:///./ap_invoice.db` | Async DSN. SQLite file (standalone) or `postgresql+asyncpg://USER:PASS@HOST:5432/DB` |
| `AP_DB_POOL_SIZE` | `10` | PostgreSQL only |
| `AP_DB_MAX_OVERFLOW` | `20` | PostgreSQL only |
| `AP_DB_ECHO` | `false` | log SQL |

## REST API
| Variable | Default | Description |
|----------|---------|-------------|
| `AP_API_HOST` | `0.0.0.0` | |
| `AP_API_PORT` | `8000` | |
| `AP_API_ROOT_PATH` | `` | when served behind a path prefix |
| `AP_CORS_ALLOW_ORIGINS` | `` | comma-separated origins |
| `AP_RATE_LIMIT` | `120/minute` | default per-client limit (slowapi syntax) |

## Security
| Variable | Default | Description |
|----------|---------|-------------|
| `AP_API_KEY_PEPPER` | _(none — required)_ | Server-side pepper mixed into API-key and password hashes (≥ 16 chars); the app will not start without it. Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |

## Auth (users, sessions, email OTP)
| Variable | Default | Description |
|----------|---------|-------------|
| `AP_JWT_SECRET` | _(none — required)_ | HMAC secret for signing session JWTs (≥ 32 chars); the app will not start without it. Generate as above. |
| `AP_JWT_EXPIRE_MINUTES` | `60` | Session token lifetime. |
| `AP_PASSWORD_MIN_LENGTH` | `8` | Minimum password length at registration. |
| `AP_OTP_LENGTH` | `6` | Digits in an email OTP. |
| `AP_OTP_TTL_MINUTES` | `10` | OTP validity window. |
| `AP_OTP_MAX_ATTEMPTS` | `5` | Failed OTP guesses before a code is invalidated. |

## Email (OTP delivery)
| Variable | Default | Description |
|----------|---------|-------------|
| `AP_EMAIL_BACKEND` | `console` | `console` logs the email (works out of the box); `smtp` sends it. |
| `AP_EMAIL_FROM` | `no-reply@ap-invoice.local` | From address on outgoing email. |
| `AP_SMTP_HOST` / `AP_SMTP_PORT` | _(unset)_ / `587` | SMTP server (required when `AP_EMAIL_BACKEND=smtp`). |
| `AP_SMTP_USERNAME` / `AP_SMTP_PASSWORD` | _(unset)_ | SMTP credentials, if the server requires auth. |
| `AP_SMTP_USE_TLS` | `true` | STARTTLS on connect. |

## MCP server
| Variable | Default | Description |
|----------|---------|-------------|
| `AP_MCP_HOST` | `0.0.0.0` | |
| `AP_MCP_PORT` | `8080` | |
| `AP_MCP_TRANSPORT` | `streamable-http` | `streamable-http` or `stdio` |
| `AP_MCP_API_KEY` | _(unset)_ | API key used to scope stdio calls (no HTTP headers). Over HTTP, clients send their own. |

## LLM provider (mandatory)
One multimodal provider handles **both** stages — invoice extraction (vision over
images/PDFs) and the RAG + approval decision. Choose Claude, GPT, or Gemini.

| Variable | Default | Description |
|----------|---------|-------------|
| `AP_LLM_PROVIDER` | `claude` | `claude` / `openai` / `gemini` |
| `AP_ANTHROPIC_API_KEY` | _(unset)_ | required when provider is `claude` |
| `AP_CLAUDE_MODEL` | `claude-opus-4-8` | Claude model (vision + decision) |
| `AP_OPENAI_API_KEY` | _(unset)_ | required when provider is `openai` |
| `AP_OPENAI_BASE_URL` | _(unset)_ | blank → api.openai.com; set for any OpenAI-compatible endpoint |
| `AP_OPENAI_MODEL` | `gpt-4o` | GPT model (vision + decision) |
| `AP_GEMINI_API_KEY` | _(unset)_ | required when provider is `gemini` |
| `AP_GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model (vision + decision) |
| `AP_EXTRACTOR_MAX_TOKENS` | `4096` | shared LLM token cap |
| `AP_EXTRACTOR_TIMEOUT_SECONDS` | `60` | shared LLM call timeout |

> The LLM is mandatory: if the configured provider has no key, processing fails
> loudly rather than degrading to an offline path.

## Extraction input limits (multi-file uploads)
| Variable | Default | Description |
|----------|---------|-------------|
| `AP_MAX_FILE_BYTES` | `10485760` | max decoded size per uploaded file (10 MiB) |
| `AP_MAX_FILES_PER_INVOICE` | `10` | max files accepted per invoice |
| `AP_MAX_EXTRACTION_IMAGES` | `16` | max image parts (PDF pages + images) sent to the vision model per extraction |
| `AP_DUPLICATE_CANDIDATE_LIMIT` | `1000` | recent invoices scanned as duplicate candidates per request |

## Autonomy (touchless processing)
| Variable | Default | Description |
|----------|---------|-------------|
| `AP_MIN_EXTRACTION_CONFIDENCE` | `0.6` | invoices with any field below this confidence are held for review (0.0–1.0) |

## RAG / embeddings (vendor policy retrieval)
| Variable | Default | Description |
|----------|---------|-------------|
| `AP_EMBEDDING_PROVIDER` | `local` | deterministic offline embedder (no external calls); swap for a hosted provider in production |
| `AP_EMBEDDING_DIM` | `256` | embedding dimensionality |
| `AP_RAG_CHUNK_SIZE` | `1200` | target policy chunk size, in characters |
| `AP_RAG_TOP_K` | `6` | policy chunks retrieved per decision |
| `AP_POLICY_COMPILER_MAX_TOKENS` | `4096` | token cap for the policy-compiler LLM call |
