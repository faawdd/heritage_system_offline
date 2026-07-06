# Offline Desktop Guide

This project can run as a local offline desktop system on Windows without mobile app integration.

## Scope retained

- Immovable heritage management
- KML overlay query/check
- Project management

## 1. Prerequisites

- Windows 10/11 or macOS/Linux
- Python 3.10+ (recommended: 3.11)
- Browser (Edge/Chrome/Safari)

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

For macOS/Linux:

```bash
chmod +x ./scripts/start_offline.sh
./scripts/start_offline.sh --init-deps
```

If you see dependency errors like `No matching distribution found for Django>=5.0.3`, your Python version is too low (commonly 3.9). Install Python 3.10+ and rerun the script.

For next runs (no dependency reinstall):

```bash
./scripts/start_offline.sh
```

Optional debug args:

```bash
./scripts/start_offline.sh --host 0.0.0.0 --port 18000 --no-browser
```

Debug account (auto ensured after migration in offline startup scripts):

- Username: `test`
- Password: `test`
- Role: super admin (highest permission)

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

- Main database: `data/database.db`
- Media uploads: `media/`

Simple backup:

```powershell
Copy-Item data/database.db data/database.db.bak_$(Get-Date -Format yyyyMMdd_HHmmss)
Copy-Item media media_bak_$(Get-Date -Format yyyyMMdd_HHmmss) -Recurse
```

## 6. Verification checklist

After startup, verify these modules in browser:

1. Immovable heritage management page can list/create/edit data.
2. KML overlay page can upload/render/query KML/KMZ.
3. Project management page can list and edit project records.

## 7. Known offline limitation

Base maps from external tile services may not load without network. KML overlay and core business workflows should still be usable.
