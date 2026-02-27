# Firefly Merge Web Tool

Web-based tool to merge bank exports (CSV/MT940), review duplicates, categorize transactions with Ollama, and export to Firefly III without duplicate imports.

## Current capabilities

- Upload bank statements via file picker or drag-and-drop
- Parse CSV and MT940 exports
- Merge + dedupe transactions with explicit duplicate reasoning
- Manual duplicate review gate before categorization/export
- Transaction table with filtering, sorting, paging, selection, detail modal
- Category editing via dropdown
- Ollama queue with audit details (prompt/response)
- Firefly export queue with stop/delete/retry and event history
- Configuration page for Firefly III, importer JSON, merge account mapping, and Ollama

## Quick start (Docker Compose)

1. Create a host config directory **outside this repo** (recommended):

```bash
mkdir -p ../firefly-merge-config
cp config.example.yml ../firefly-merge-config/config.yml
cp import_config.example.json ../firefly-merge-config/import_config.json
```

2. Start the app:

```bash
docker compose up --build
```

3. Open:

- App: `http://localhost:8080`
- Configuration: `http://localhost:8080/config`

## Persistent storage and filesystem mapping

`docker-compose.yml` uses two bind mounts:

- `${FIREFLY_MERGE_DATA_DIR:-./data}:/data`
  - job state, queues, sqlite db, generated artifacts
- `${FIREFLY_MERGE_CONFIG_DIR:-../firefly-merge-config}:/config`
  - your runtime config files (`config.yml`, `import_config.json`)

The app reads config from:

- `APP_CONFIG_PATH=/config/config.yml`

This setup keeps secrets and account config outside the git repo by default.

## Optional environment overrides

In `docker-compose.yml`:

- `FIREFLY_URL`
- `FIREFLY_SECRET`
- `FIREFLY_TOKEN`
- `FIREFLY_JSON`
- `FIREFLY_TIMEOUT`
- `FIREFLY_BATCH_SIZE`

## Local (non-docker) run

```bash
pip install -r requirements.txt
python -m uvicorn firefly_web.app:app --host 127.0.0.1 --port 8080
```

## Security / repository hygiene

This repo intentionally ignores local sensitive files:

- `config.yml`
- `import_config.json`
- `.env*`
- `data/`, `input/`, `output/`, `balances/`, `output_check/`

Use the provided `config.example.yml` and `import_config.example.json` as templates.
