# Multi-Store E-commerce ERP — PRD

## Original problem statement
Production-ready, plug-and-play Multi-Store E-commerce ERP acting as a single source of truth for inventory and orders across marketplace stores (2 Shopee, 2 TikTok Shop today; scalable). React + Tailwind frontend, FastAPI + SQLAlchemy + PostgreSQL backend, JWT auth, Docker + docker-compose deployment.

## User choices
- Strict **PostgreSQL + Docker** stack (deliverable code); running in preview via supervisor for validation
- Marketplace integrations **mocked** with realistic seeded data + webhook endpoint accepting payloads
- Auth: **JWT with admin/admin** seeded on first boot
- Design: agent-picked **Tactical Dark Mode** (Chivo / Satoshi / JetBrains Mono, #0A0A0A surfaces, Volt Blue #007AFF accent)

## Architecture
```
frontend (React 19 + Tailwind + Recharts + Phosphor + sonner)
    │ axios (auto JWT header)
    ▼
/api/* (FastAPI, CORS *)  ── JWT (jose + passlib/bcrypt)
    ▼
SQLAlchemy ORM (Users, Stores, Master_SKU, SKU_Mapping, Orders, Inbound_Log)
    ▼
PostgreSQL 15 (docker-compose service `db`, port 5432)
```
Docker Compose orchestrates `db` + `backend` (uvicorn) + `frontend` (nginx serving CRA build with `/api` proxy).

## Personas
1. **Operations Admin** — reviews KPIs, filters orders, batch prints labels
2. **Warehouse Lead** — adds inbound stock, monitors low/oversold SKUs
3. **Founder** — checks GMV / net profit per store

## Implemented (2026-02)
- Backend: JWT login, `/api/me`, `/api/dashboard/metrics` (aggregate + per-store), `/api/orders` with platform + status filters, `/api/inventory`, `/api/inventory/inbound` (weighted-avg cost update), `/api/stores`, `/api/webhooks/orders` (auto stock deduction)
- Seed (`seed.py`, idempotent) — admin user, 4 stores, 8 master SKUs, marketplace SKU mappings for every store, ~60 orders over 14 days, 1 inbound log
- Frontend: Login (with brand panel), sidebar Layout, Dashboard (4 KPI cards + Recharts bar chart + per-store cards), Order Hub (filters, select-all, batch print toast), Inventory (KPI strip + table + Inbound modal with live final-COGS), Stores grid
- Deployment: `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile` + `nginx.conf`, `.env.example`, `README.md`
- 13/13 backend + frontend flows verified by testing agent

## Backlog
### P1
- Order detail drawer (line items, shipping address, tracking)
- Real Shopee & TikTok Shop OAuth + inbound sync workers
- CSV/Excel export for orders + inventory

### P2
- Multi-user + role-based access (manager / operator / viewer)
- Reorder-point alerts (email/Slack) when stock < threshold
- Real thermal-label PDF generator (Zebra ZPL) for batch print
- Alembic migrations (currently `create_all` on startup)
