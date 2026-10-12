# StyleMate backend

Flask API for StyleMate. See the main [README](../README.md) to run it, and [docs/architecture.md](../docs/architecture.md) for how it works.

Common commands, run from this folder:

| Command | What it does |
|---|---|
| `uv sync` | Install the exact package versions from `uv.lock` |
| `uv run flask --app stylemate seed` | Create or update the shop, options, products and owner login |
| `uv run flask --app stylemate run --debug` | Start the API on http://127.0.0.1:5000 |
| `uv run pytest` | Run the tests |
| `uv add <package>` | Add a package (updates `pyproject.toml` and `uv.lock`) |
