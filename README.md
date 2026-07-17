# OTA Analyzor

> [!IMPORTANT]
> **Vibe Coding 说明 / Disclaimer**
>
> 本仓库是作者在 AI 辅助下以 **vibe coding** 方式完成的个人作品：主要通过自然语言描述需求、由 AI 生成和修改代码，作者负责产品想法、体验验证和方向取舍。作者不是专业开发者，也不具备系统的代码审计能力；代码按现状提供，请在使用、部署或二次开发前自行审查、测试并承担相应风险。
Bluetooth OTA (Over-The-Air) Tx power drop test data analysis tool. Built with FastAPI + Plotly.js + matplotlib.

## Features

- **CSV upload & analysis** — parse BLE Tx power test CSVs with automatic header detection and column mapping
- **Interactive charts** — Plotly.js trend charts comparing power drop across devices, checkpoints, and channels
- **Statistical boxplots** — matplotlib/seaborn-generated PNG boxplots via `/api/generate`
- **Dual data modes** — "delta" (power drop) and "raw" (absolute dBm) analysis
- **File tagging** — organize uploaded data with persistent tags stored in SQLite
- **Docker deployment** — multi-arch images (linux/amd64 + arm64) with CI/CD via GitHub Actions

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run dev server (auto-reload)
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

# Run tests
python -m unittest tests.test_analysis -v
python -m pytest tests/ -v
```

## API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/files` | GET | List files with cached metadata |
| `/api/upload` | POST | Upload temp CSV (short-lived) |
| `/api/rawdata/upload` | POST | Upload raw data CSV (persistent) |
| `/api/tags` | POST | Update file tags |
| `/api/fetch_chart_data` | POST | Get JSON chart data |
| `/api/generate` | POST | Generate boxplot PNG |

## Data Processing Pipeline

1. **Header detection** — scoring-based row detection (SerialNumber +4, Checkpoint/CP +4, Pass/Fail +1, freq +1, delta +1; threshold ≥8)
2. **Column parsing** — handles 3 naming patterns (BT;rate;freq;tc;subtc, etc.)
3. **Frequency → Channel mapping** — ≤2420=Tx_LC, 2430-2455=Tx_MC, ≥2470=Tx_HC
4. **Data classification** — "delta" (power drop, threshold ≥6) or "raw" (absolute dBm, threshold ≥7)
5. **File IDs** — `raw:filename.csv` (data dir) or `upload:filename.csv` (upload dir)

## Architecture

```
OTA analyzor/
├── app/              # FastAPI application factory & services
├── static/           # HTML/CSS/JS frontend (Plotly.js)
├── analysis.py       # CSV parsing & data analysis core
├── main.py           # Entry point (HOST/PORT/OPEN_BROWSER env vars)
├── config/           # SQLite DB, tags
├── tests/            # unittest + pytest suites
├── scripts/          # publish.ps1 release script
└── Dockerfile        # python:3.12-slim, multi-arch
```

- **Backend**: FastAPI with app factory pattern (`app/__init__.py` → `create_app()`)
- **Frontend**: Static HTML/CSS/JS + Plotly.js + matplotlib/seaborn
- **Database**: SQLite at `config/ota.db`, WAL mode, thread-local connections

## Docker

```bash
# Build & run from source
docker compose up -d

# Run pre-built image from GHCR
docker compose -f docker-compose.prod.yml up -d
```

Images published to `ghcr.io/virgooooox/ota-analyzor` with tags: `latest`, `sha-<short>`, and semver (`v1.0.0`).

## Release

```powershell
.\scripts\publish.ps1 [-Bump patch|minor|major] [-SkipTests] [-DryRun]
```

Creates a git tag and pushes, which triggers the GitHub Actions CI/CD pipeline.

## License

MIT
