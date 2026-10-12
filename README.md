# The House of "M": AI shopping assistant for online clothing stores

StyleMate is an AI shopping assistant for online clothing shops. Customers ask by text or voice and get answers only from the shop's own catalogue. They can customize dresses with prices calculated by the shop. Owners see what customers ask, including what the shop couldn't answer, and manage custom orders.

The House of "M" is a fictional shop with sample data, used to demonstrate the platform. Built with Flask, Vue and Gigalogy's Maira (answers) and Chorus (speech-to-text).

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
uv run flask --app stylemate seed     # asks for an owner email and password
uv run flask --app stylemate run --debug
```

**2. Frontend** (second terminal):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The owner dashboard is at http://localhost:5173/owner.

## Tests

```bash
cd backend
uv run pytest
```

The tests use fake Maira and Chorus clients, so they need no keys and cost nothing.

## Repository layout

```
backend/    Flask API (stylemate package), tests
frontend/   Vue storefront, chat widget and owner dashboard
data/       Sample products CSV and product photos
docs/       Architecture guide, Maira API notes, profile and dataset setup, test results
```
