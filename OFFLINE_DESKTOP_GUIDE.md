# Offline Desktop Guide

This project can run as a local offline desktop system on Windows without mobile app integration.

## Scope retained

- Immovable heritage management
- KML overlay query/check
- Project management

## 1. Prerequisites

- Windows 10/11
- Python 3.10+
- Browser (Edge/Chrome)

## 2. One-click start (recommended)

From project root:

```powershell
.\scripts\start_offline.bat -InitDeps
```

Notes:

- The first run creates `.venv`.
- `-InitDeps` installs Python dependencies from `requirements.txt`.
- The script runs migrations and starts Django at `http://127.0.0.1:8000`.
- Browser opens automatically to `/`.

For next runs (no dependency reinstall):

```powershell
.\scripts\start_offline.bat
```

## 3. Manual start (fallback)

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python manage.py migrate --noinput
.\.venv\Scripts\python manage.py runserver 127.0.0.1:8000
```

Then open:

- `http://127.0.0.1:8000/`

## 4. Offline environment defaults

Local `.env` includes:

- `DJANGO_DEBUG=1`
- `DJANGO_FORCE_HTTPS=0`
- `DJANGO_WEB_BASE_URL=http://127.0.0.1:8000`

These values ensure generated media and entry URLs use local addresses.

## 5. Data location and backup

- Main database: `db.sqlite3`
- Media uploads: `media/`

Simple backup:

```powershell
Copy-Item db.sqlite3 db.sqlite3.bak_$(Get-Date -Format yyyyMMdd_HHmmss)
Copy-Item media media_bak_$(Get-Date -Format yyyyMMdd_HHmmss) -Recurse
```

## 6. Verification checklist

After startup, verify these modules in browser:

1. Immovable heritage management page can list/create/edit data.
2. KML overlay page can upload/render/query KML/KMZ.
3. Project management page can list and edit project records.

## 7. Known offline limitation

Base maps from external tile services may not load without network. KML overlay and core business workflows should still be usable.
