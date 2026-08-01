# LedgerFlow

[![Backend tests](https://github.com/odungaJr/ledgerflow/actions/workflows/backend-tests.yml/badge.svg)](https://github.com/odungaJr/ledgerflow/actions/workflows/backend-tests.yml)

A personal finance tracker with AI-assisted categorisation, budgets, income
tracking, assets and liabilities, and a dashboard that ties it all together.
Multi-tenant — each registered user gets fully private data.

## Features

- **Bank statement import** — CSV and PDF, with automatic deduplication
- **AI-powered categorisation** — Claude suggests a category for each
  imported transaction; anomaly detection and a narrative monthly insights
  report
- **Budgets** — monthly or weekly caps per category, with warning/breach
  alerts
- **Income tracking** — one-off or recurring entries, expected vs. received,
  pending/overdue status
- **Assets & liabilities** — anything owned or owed, with dated value
  history and a combined net-worth trend
- **Dashboard** — spending summaries, income-vs-expenses and category-spend
  charts, budget alerts, net worth, AI insights
- **P&L statement** — income/expense breakdown by category for any custom
  date range, with CSV export
- **Settings** — light/dark/system theme, category management, account
  security (login lockout, idle session timeout, password change)
- **Multi-tenant** — open registration; every account's data (accounts,
  transactions, budgets, income, assets, liabilities, categories) is fully
  private to that user

## Tech stack

- **Backend:** FastAPI, SQLAlchemy, PostgreSQL, Alembic (Python 3.11)
- **Frontend:** Next.js 16, React 19, TypeScript, plain CSS — client-rendered,
  calls the backend API directly
- **AI:** Anthropic Claude — Haiku for categorisation/anomaly detection,
  Sonnet for narrative insights
- **Deploy:** Docker Compose (Postgres + FastAPI + Next.js + Caddy reverse
  proxy)

## Getting started

Requires Docker.

```bash
cd "Personal finance/ledgerflow"
cp .env.example .env
# fill in ANTHROPIC_API_KEY in .env
docker compose up -d --build
```

The app is then available at `http://localhost`. First visit shows a
"create your account" screen — set a username and password to get started.
Registration stays open afterward, so anyone else can create their own
private account too.

## Project structure

```
Personal finance/ledgerflow/
├── docker-compose.yml   db + backend + frontend + Caddy
├── Caddyfile             reverse proxy config
├── backend/
│   ├── app/               FastAPI app — routers, models, services, auth
│   ├── alembic/            DB migrations
│   └── tests/              pytest suite
└── frontend/
    ├── app/                Next.js pages
    ├── components/         shared UI components
    └── lib/                API client + shared types
```

## Status

Actively developed, personal project. Holds real financial data for its
users — never commit `.env` files or database backups (see `.gitignore`).
