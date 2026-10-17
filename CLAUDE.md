# StyleMate: Closet Corner (formerly The House of "M")
AI shopping assistant for clothing shops. Flask + Vue 3, Maira (catalogue answers), Chorus (voice). Due 2026-11-10.
Status: docs/handoff.md. Architecture: docs/architecture.md. Maira/Chorus API: docs/maira-api.md.

## Working with me (Maisha, intern)
- Build features end to end without waiting for my OK. Afterwards explain what was built and why, so I can present it and answer questions.
- Ask first before anything that changes the Maira project (profiles, datasets) or spends on real API calls.
- Give exact commands with folder. Explain errors before fixes.
- SOLID/DRY/YAGNI: start simple, abstract on second use. Comment where applied.
- Conventional Commits, one topic each.
- Never print `.env` or ask for keys.

## Commands
- `backend/`: `uv run pytest` | `uv run flask seed` (runs `flask db upgrade` first) | `uv run flask db migrate -m "..."` / `uv run flask db upgrade` | `uv run flask run --debug` | `uv run flask sync-help` (FAQ + size guide → Maira) | `uv run flask sync-recommender` (catalogue → Gigalogy recommender) | `uv run flask set-plan <starter|growth|pro>` | `uv run flask demo-requests`
- `frontend/`: `npm run dev` | `npm run build`
- Docker (repo root): `docker compose up -d --build` → http://localhost:8080 | `docker compose exec backend flask <command>` | `docker compose logs -f backend`. Docker Desktop must be running (`systemctl --user start docker-desktop`); the system daemon needs sudo.

## Rules
- Prices and delivery charges only from `services/pricing.py`, never the AI or the browser; checkout recalculates server-side.
- Gigalogy calls only via `clients/`; update `tests/fakes.py` when clients change.
- Every query filters by `tenant_id` (`current_tenant()`).
- Services raise `UserInputError` / `ServiceUnavailableError`; no try/except in routes.
- Run tests/build after changes; add a test per bug fix.
- Database changes: edit `models.py`, then `uv run flask db migrate -m "..."`, read the generated file in `backend/migrations/versions/`, then `uv run flask db upgrade`. Never `ALTER TABLE` by hand or delete the database. `tests/test_migrations.py` fails if a model changes without a migration.
- Packages only via `uv add` / `npm install`.
- Keep docs/architecture.md and docs/handoff.md current.
- Chorus is async and blocks browsers (Flask only).
- Maira match score: ~42 good, <24 not sold.
- Customers (`Customer`, session `customer_id`) and owners (`User`, session `user_id`) are separate logins; never mix them.
- Saved checkout details: an account's on the `Customer` row (`accounts.remember_details()`, only with `remember`), a guest's only in their browser (`utils/savedDetails.js`). Never store a transaction ID.
- Made to measure (`needs_measurements` option): no size, measurements checked by `pricing.clean_measurements()`.
- Ready-made orders lower `Product.stock` (`orders._take_from_stock()`); a CSV upload overwrites stock with the file's numbers.
- Chat orders: the profile writes an `[ORDER ...]` line; `read_order()` in `services/chat.py` checks it. The AI never places an order itself.
- After a dataset upload, wait for Maira to read the file before training (`MairaClient.upload_and_train()`).
- Payment (`services/payments.py`): cash on delivery, or a bKash/Nagad/Rocket transaction ID the owner checks; no gateway, no money moves through the app. Wallet numbers on `Tenant` are sample values.
- Customer pictures (tailor reference, Help message photo) go through `services/uploads.py`; only the owner can open them.
- Daily per-visitor limits via `services/limits.py` (hash of IP); limits in `.env`.
- Plans (`services/plans.py`) are the one place for plan prices and limits; anything that costs per use calls `plans.require()` before and `plans.record()` after. Prices are examples until Maisha has Gigalogy's prices. Sold to Facebook-only shops via `/stylemate` + "Request a demo".
- Recommendations (`services/recommendations.py`): off until `flask sync-recommender` sets `Tenant.recommender_ready`; Flask filters Gigalogy's picks by stock and usual size and falls back to the shop's own picks. Cached 10 minutes.

## Image preview (`services/preview.py`, live with `gpt-image-2` since Oct 11)
- Same `/v1/maira/ask` endpoint, with the shop's image profile (`Tenant.maira_image_profile_id`); empty ID hides the feature.
- The picture is a preview only; options are checked by `services/pricing.py` and never priced from the picture.
- No customer photo: the garment alone, no person or face. With a photo: the chosen size (size-guide numbers) or made-to-measure numbers go in the prompt (`fit_description()`); a try-on needs a size.
- Pictures arrive in `detail.generated_images`; a failed model still answers 200 with the reason in `detail.response`.
- Products carry optional `length_inches` and `sleeve`; `pricing.options_for()` fits the option menu to them.
- Size guide (`services/sizes.py`) and Help page (`services/help.py`: FAQ, contact, messages) are per-shop rows seeded from `cli.py`; sample values, not the shop's own.
