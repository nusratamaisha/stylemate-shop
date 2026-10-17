# StyleMate backend: Flask served by gunicorn. Built by compose.yaml from this folder.
FROM python:3.14-slim

# uv installs the exact versions in uv.lock, as on our own computers
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=stylemate \
    PATH="/app/backend/.venv/bin:$PATH"

# Same layout as the repo (backend/ next to data/), so config.py's paths still work
WORKDIR /app/backend

# Dependencies first: this layer is reused until pyproject.toml or uv.lock change
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

# Run as an ordinary user, not root. The code stays root's: readable by everyone (some folders
# are owner-only on our computers, and COPY keeps that), but the app can't change it.
# The database and uploads folders belong to the app, so the volumes mounted there are writable.
RUN chmod -R a+rX /app/backend \
    && useradd --uid 1000 --create-home app \
    && mkdir -p /app/var /app/backend/uploads \
    && chown -R app:app /app/var /app/backend/uploads
USER app

EXPOSE 5000

# Bring the database up to date, then serve. --timeout 150: a picture preview can take 120 s.
CMD ["sh", "-c", "flask db upgrade && exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 150 --access-logfile - 'stylemate:create_app()'"]
