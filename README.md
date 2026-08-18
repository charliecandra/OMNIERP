# Multi-Store E-commerce ERP

A production-ready ERP for managing **inventory and orders across multiple marketplace stores** (Shopee, TikTok Shop, and more). Single source of truth for stock, orders, GMV and profit.

## Stack
- **Frontend**: React 19, Tailwind CSS, React Router, Axios, Recharts, Phosphor Icons
- **Backend**: FastAPI, SQLAlchemy 2, Pydantic v2, JWT (jose + passlib/bcrypt)
- **Database**: PostgreSQL 15
- **Orchestration**: Docker & Docker Compose

## Quick start (Docker)

```bash
git clone <this-repo> erp && cd erp
cp .env.example .env    # edit JWT_SECRET before going to prod
docker-compose up --build
```

Once healthy:
- Frontend: http://localhost:3000
- Backend:  http://localhost:8001/api/
- Postgres: localhost:5432 (user: `erp_user`, db: `erp_db`)

**Default admin login:** `admin` / `admin` (auto-seeded on first boot)

## Project layout
```
.
├── backend/            FastAPI service
│   ├── server.py       app entry & routes
│   ├── database.py     SQLAlchemy engine/session
│   ├── models.py       ORM models
│   ├── schemas.py      Pydantic schemas
│   ├── auth.py         JWT + bcrypt helpers
│   ├── seed.py         idempotent seed (runs on startup)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/           React SPA
│   ├── src/            app source
│   ├── nginx.conf      production reverse proxy
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## API (all routes prefixed with `/api`)
| Method | Path                     | Auth | Purpose                                              |
|--------|--------------------------|------|------------------------------------------------------|
| GET    | `/api/`                  | –    | Health check                                         |
| POST   | `/api/login`             | –    | Returns JWT `access_token`                           |
| GET    | `/api/me`                | JWT  | Current user                                         |
| GET    | `/api/dashboard/metrics` | JWT  | Aggregate GMV / orders / net profit / per-store      |
| GET    | `/api/orders`            | JWT  | Unified order list; filter by `platform`, `status`   |
| GET    | `/api/inventory`         | JWT  | Master SKU stock levels                              |
| POST   | `/api/inventory/inbound` | JWT  | Add inbound stock; calculates final base cost        |
| GET    | `/api/stores`            | JWT  | Registered marketplace stores                        |
| POST   | `/api/webhooks/orders`   | –    | Marketplace webhook — creates order, deducts stock   |

### Webhook example
```bash
curl -X POST http://localhost:8001/api/webhooks/orders \
  -H "Content-Type: application/json" \
  -d '{
    "store_id": 1,
    "marketplace_order_id": "SHP-DEMO-1",
    "status": "pending",
    "items": [{"marketplace_sku_code": "SHP-1-TEE-BLK-M", "quantity": 2, "unit_price": 12.9}]
  }'
```

## Local development (without Docker)
```bash
# Backend
cd backend && pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg2://erp_user:erp_pass@localhost:5432/erp_db
export JWT_SECRET=dev_secret
uvicorn server:app --reload --port 8001

# Frontend
cd frontend && yarn && yarn start
```
