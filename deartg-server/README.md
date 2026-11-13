# DearTG local API (foundation)

This is the first independent backend slice for DearTG. It runs on a Windows PC and is reachable by an iPhone on the same Wi-Fi network.

## Run on Windows

```powershell
cd deartg-server
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DEARTG_TOKEN_SECRET = (py -c "import secrets; print(secrets.token_hex(32))")
$env:DEARTG_DATA_DIR = "$PWD\data"
python -m uvicorn app:app --host 0.0.0.0 --port 8080
```

Open `http://127.0.0.1:8080/docs` on the PC. Find the PC's LAN IPv4 address with `ipconfig`; the iPhone uses `http://PC-LAN-IP:8080`. Allow TCP port 8080 in Windows Firewall only on a private network. Keep both devices on the same trusted Wi-Fi.

## API

- `POST /v1/auth/register`, `POST /v1/auth/login`
- `GET /v1/me`
- `POST /v1/chats`, `GET /v1/chats`
- `GET /v1/chats/{id}/messages`, `POST /v1/chats/{id}/messages`
- `WS /v1/ws/chats/{id}?token=...` (new message events)

SQLite is used for the local prototype. Passwords are PBKDF2-HMAC-SHA256 hashed; bearer tokens are HMAC-signed and expire. Set a unique `DEARTG_TOKEN_SECRET` before use. Do not expose this prototype to the public internet yet: production still needs TLS, refresh/revocation, rate limits, account recovery, moderation, backups, migrations, push notifications, and a reviewed end-to-end encryption design.

## Current boundary

This backend is independent of Telegram's servers. The existing iOS repository is still a Telegram client codebase; adding this API does not by itself replace its MTProto/account/chat stack. The DearTG iOS integration and full brand replacement are separate work and must be validated against the actual app entry points before claiming the client is independent.
