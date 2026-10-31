# Repository guidance

## Project

Place Search is a Python application that crawls place data, checks it against MySQL, indexes dense and sparse vectors in Qdrant, and serves search through FastAPI. The shared CLI is `core/pipeline.py`; see `README.md`, `PROJECT_STRUCTURE.md`, and `PIPELINE_FLOW.md` for detailed workflows.

## Development

- Use the project virtual environment: `source .venv/bin/activate`.
- Dependencies and packaging are defined in `pyproject.toml` and locked in `uv.lock`.
- Configuration is loaded from the project-root `.env`; use `.env.example` to see supported settings. Never commit secrets.
- Keep imports and examples safe: network calls and service connections should happen only when explicitly requested by a command or option, not merely by importing a module.
- Run the CLI help with `python -m core.pipeline --help`. The CLI commands are separate pipeline stages; there is no automatic run-all command.

## Data workflow

- Crawl output goes to `data/craw/`; reviewed/check output goes to `data/checked/`.
- The `check` step compares crawl data with MySQL. Review the generated JSON files before running `import`, which writes to MySQL.
- `embed` reads MySQL and synchronizes vectors with Qdrant. It requires the configured services and embedding credentials.
- Do not overwrite or discard user data in `data/` as part of unrelated changes.

## Services and commands

- Local Qdrant/MySQL services are described in `docker/docker-compose.yml`.
- API entry point: `uvicorn app.main:app --reload`.
- Pipeline entry point: `python -m core.pipeline <command>`.
- Service-backed commands require the corresponding values in `.env` and services to be available.
