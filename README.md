# Closet Corner: AI shopping assistant for online clothing stores

StyleMate is an AI shopping assistant for online clothing shops. Customers ask by text or voice and get answers only from the shop's own catalogue. They can customize dresses with prices calculated by the shop. Owners see what customers ask, including what the shop couldn't answer, and manage custom orders.

Closet Corner (called The House of "M" until October 13, 2026) is a fictional shop with sample data, used to demonstrate the platform. Built with Flask, Vue and Gigalogy's Maira (answers) and Chorus (speech-to-text).

How it all fits together: [docs/architecture.md](docs/architecture.md)

## What you need

- [uv](https://docs.astral.sh/uv/) for Python (it installs Python 3.14 for you)
- Node.js 20.19 or newer (`node --version`)
- Gigalogy keys, plus the shop's Maira profile ID and dataset ID

## Run it

**1. Backend** (first terminal):

```bash
cd backend
cp .env.example .env        # then fill in the keys, IDs and SECRET_KEY
uv sync
uv run flask --app stylemate seed     # builds the tables from the migrations, then asks for an owner email and password
uv run flask --app stylemate run --debug
```

**2. Frontend** (second terminal):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The owner dashboard is at http://localhost:5173/owner.

## Run it with Docker

The same app as one command, the way it would run on a server: nginx serves the built Vue app on port 8080 and passes `/api` to Flask, which runs under gunicorn. You need Docker with Compose, and `backend/.env` filled in as above.

```bash
docker compose up -d --build                 # build both images and start them
docker compose exec backend flask seed       # first time only: shop, products and owner login
```

Open http://localhost:8080 (owner dashboard: http://localhost:8080/owner). The database and customers' pictures live in Docker volumes (`db`, `uploads`), so they survive rebuilds. Product photos come from `data/` on this computer.

| To | Run |
|---|---|
| See the backend's log | `docker compose logs -f backend` |
| Apply new migrations after pulling changes | `docker compose up -d --build` (the backend runs `flask db upgrade` on start) |
| Run any `flask` command | `docker compose exec backend flask sync-help` |
| Copy your local database into Docker | `docker compose cp -a backend/stylemate.db backend:/app/var/stylemate.db`, then `docker compose restart backend` |
| Stop | `docker compose down` (add `-v` to delete the database and pictures too) |

## Tests

```bash
cd backend
uv run pytest
```

The tests use fake Maira and Chorus clients, so they need no keys and cost nothing.

## Repository layout

```
backend/    Flask API (stylemate package), migrations, tests, Dockerfile
frontend/   Vue storefront, chat widget and owner dashboard, Dockerfile, nginx.conf
compose.yaml  Runs both in Docker
data/       Sample products CSV and product photos
docs/       Architecture guide, Maira API notes, profile and dataset setup, test results
```
