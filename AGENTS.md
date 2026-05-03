# OTA Analyzor

FastAPI web app for analyzing Bluetooth OTA (Over-The-Air) Tx power drop test data from CSV files.

## Quick Start

```bash
# Run dev server (reload on change)
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

# Run tests
python -m unittest tests.test_analysis -v
python -m pytest tests/ -v

# Release (PowerShell, from repo root)
.\scripts\publish.ps1 [-Bump patch|minor|major] [-SkipTests] [-DryRun]
```

## Architecture

- **Framework**: FastAPI, app factory in `app/__init__.py` (`create_app()`)
- **Frontend**: Static HTML/CSS/JS (`static/`) + Plotly.js (trend charts) + matplotlib/seaborn (boxplot PNG via `/api/generate`)
- **DB**: SQLite at `config/ota.db`, WAL mode, thread-local connections
- **Entry**: `main.py` — reads `HOST`/`PORT`/`OPEN_BROWSER` env vars

## Routes

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/files` | GET | List files with cached metadata |
| `/api/upload` | POST | Upload temp CSV (short-lived) |
| `/api/rawdata/upload` | POST | Upload raw data CSV (persistent) |
| `/api/tags` | POST | Update file tags |
| `/api/fetch_chart_data` | POST | Get JSON chart data |
| `/api/generate` | POST | Generate boxplot PNG |

## Data Processing Pipeline

1. **Header detection** (`analysis.find_header_row`): scoring-based (SerialNumber +4, Checkpoint/CP +4, Pass/Fail +1, freq= +1, delta +1; threshold ≥8 returns immediately)
2. **Column parsing** (`analysis.parse_test_column`): handles 3 naming patterns:
   - `tech=BT;rate=1LE;freq=2402;tc=Power subtc=Avg`
   - `tc=Power tech=BT:subtc=Avg ant=0:rate=1LE:pwr=8:freq=2402`
   - `tech=BT;rate=1LE;pwr=8.0;freq=2402;tc=Power subtc=Power_Abs`
3. **Frequency→Channel mapping**: freq≤2420=Tx_LC, 2430-2455=Tx_MC, freq≥2470=Tx_HC
4. **Data type**: `"delta"` (Tx power drop, discovery threshold ≥6) or `"raw"` (absolute dBm, threshold ≥7, excludes ACP columns)
5. **File IDs**: `raw:filename.csv` (data dir) or `upload:filename.csv` (upload dir)

## Key Coding Conventions

- **CP ordering**: `T0`=-2, `HS`=-1, numeric extracted, others=999 (function in `app/utils.py`)
- **Config**: paths set via env vars (`DATA_DIR`, `UPLOAD_DIR`, `TAGS_FILE`, `DB_PATH`, `HOST`, `PORT`)
- **File naming**: raw data CSV stored as `Organized_<name>.csv` (prefix added by `raw_data_filename()` in utils)
- **Tags**: stored in SQLite `tags` table, migrated from legacy `config/tags.json` on first init
- **File cache**: SQLite `file_cache` table keyed by `(file_path, mtime)` — invalidated when file changes

## Testing Gotchas

- Analysis tests use `unittest.TestCase`; database tests use `pytest` with `conftest.py` fixtures (`temp_db_path`, `temp_dirs`)
- Database tests monkey-patch `DB_PATH` and reset thread-local connection — be careful when running alongside other DB operations
- Docker may create `tags.json` as a directory (volume mount behavior) → `init_db` handles this gracefully
- Test CSV fixtures go in `tests/_tmp/`

## Deployment

- **Docker**: `Dockerfile` builds from `python:3.12-slim`, multi-arch (linux/amd64 + arm64)
- **CI** (`.github/workflows/docker-image.yml`): runs tests → builds multi-arch → pushes to `ghcr.io/virgooooox/ota-analyzor`
- **Release**: `scripts/publish.ps1` handles git tag + push, which triggers CI
- Tags follow `vX.Y.Z` semver; Docker image tags include `latest`, `sha-<short>`, semver variants
- **Compose**: `docker-compose.yml` (build from source), `docker-compose.prod.yml` (pre-built GHCR image)
- Max **10 sources** per chart (limit hardcoded in both `chart_service.py` and `data_service.py`)

## Data Handling

- `includeFailData=false` (default): PASS-only records; if no PASS exists for a (SN, CP) group, takes the **last** record
- `filter_pass_records()` sorts by EndTime/StartTime before grouping by SN+CP
- Uploaded files get UUID prefix to avoid collisions; raw data uploads append UUID on name conflict
- Raw data uploaded via `/api/rawdata/upload` auto-tagged `"RawData"`
- Uploaded files **cannot** have tags edited (tag service raises `ValueError`)
