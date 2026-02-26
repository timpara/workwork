# Work Hours Tracker

A local-first web app for tracking daily working hours against a configurable target (default 7.6h). Enter start/end times and breaks, and the app calculates total hours and overtime automatically.

## Features

- **Daily hour logging** — start time, end time, and multiple breaks per day
- **Configurable daily target** — click the target stat to change it (default 7.6h); existing entries keep their stored overtime
- **Live preview** — form auto-computes hours and overtime as you type
- **Manual overtime adjustments** — standalone +/- hour adjustments with reason (e.g. on-call, comp time)
- **Summaries** — weekly, monthly, and all-time totals with progress bars
- **Calendar view** — color-coded month view showing overtime/undertime per day
- **CSV export** — download all entries and adjustments as CSV
- **Dark mode** — toggle between light and dark themes
- **SQLite storage** — all data stored locally in `data/hours.db`

## Getting Started

### Docker (recommended)

```bash
docker compose up -d
```

The app will be available at [http://localhost:9090](http://localhost:9090). Data is persisted in `./data/hours.db` via a volume mount.

### Local (without Docker)

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run gunicorn --bind 0.0.0.0:9090 app.app:app
```

Open [http://localhost:9090](http://localhost:9090).

## Running Tests

```bash
uv sync --dev
uv run pytest tests/ -v
```

## Tech Stack

- **Backend** — Python, Flask, Gunicorn
- **Frontend** — Vanilla HTML, CSS, JavaScript
- **Database** — SQLite
- **Package management** — uv
- **Deployment** — Docker / docker-compose
