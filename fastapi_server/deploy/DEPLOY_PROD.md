# FastAPI Production Deployment (with existing Django at https://beichenhome.top:9081)

This guide deploys FastAPI on the same server and exposes it via:

- Django: `https://beichenhome.top:9081`
- FastAPI base URL: `https://beichenhome.top:9081/app-api`

Then your app API routes become:

- `https://beichenhome.top:9081/app-api/api/auth/login`
- `https://beichenhome.top:9081/app-api/api/heritages/nearby`
- etc.

## 1. Server prerequisites

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx
```

## 2. Upload project and create venv

Assume project path is `/opt/heritage_system`:

```bash
cd /opt/heritage_system
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r fastapi_server/requirements.txt
```

## 3. Local startup test

```bash
cd /opt/heritage_system/fastapi_server
/opt/heritage_system/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

In another shell:

```bash
curl http://127.0.0.1:8000/
```

Expected JSON includes `FastAPI is running`.

## 4. Configure systemd

Copy service template:

```bash
sudo cp /opt/heritage_system/fastapi_server/deploy/heritage_fastapi.service.example /etc/systemd/system/heritage-fastapi.service
```

If your path/user differs, edit:

```bash
sudo nano /etc/systemd/system/heritage-fastapi.service
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable heritage-fastapi
sudo systemctl restart heritage-fastapi
sudo systemctl status heritage-fastapi
```

Logs:

```bash
sudo journalctl -u heritage-fastapi -f
```

## 5. Add Nginx reverse proxy under existing Django server

Open your existing nginx server config for `beichenhome.top:9081`, then paste the content of:

- `fastapi_server/deploy/nginx_app_api_location.conf`

inside that `server { ... }` block.

Validate and reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 6. Verify production URL

```bash
curl -k https://beichenhome.top:9081/app-api/
curl -k https://beichenhome.top:9081/app-api/api/auth/me
```

## 7. Uni-app backend base URL

Set app API base URL to:

- `https://beichenhome.top:9081/app-api`

So current route paths continue to work without code changes.

## 8. Common issues

1. `ModuleNotFoundError` or Django import failure:
- Check `WorkingDirectory` points to `.../fastapi_server`.
- Ensure venv has packages installed.

2. `502 Bad Gateway` in Nginx:
- Check FastAPI process: `systemctl status heritage-fastapi`.
- Confirm Uvicorn listens on `127.0.0.1:8000`.

3. Permission error writing uploads:
- Ensure service user (example `www-data`) can write:
  - `/opt/heritage_system/media`

4. API reachable locally but not via domain:
- Check the `/app-api/` location is inside the correct SSL server block for port `9081`.
