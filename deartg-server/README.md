# DearTG Local API

The local backend for DearTG. It uses FastAPI and SQLite and is designed for development on a Windows PC.

## Quick start (Windows 10/11)

1. Install Python 3.11 or newer and enable **Add Python to PATH**.
2. Open PowerShell in this folder.
3. Run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\start-windows.ps1
```

The launcher creates a virtual environment, installs dependencies, creates persistent random local secrets in `data/local-secrets.ps1` (never commit this file), creates the SQLite database, and starts the API.

Open:
- API health: http://127.0.0.1:8080/health
- Interactive API docs: http://127.0.0.1:8080/docs

Keep the PowerShell window open. Press Ctrl+C to stop the server. The database and secrets remain in `data/` between restarts.

## iPhone on the same Wi-Fi

Run `ipconfig` on the PC and find its private IPv4 address (usually `192.168.x.x` or `10.x.x.x`). On the iPhone, use `http://PC-IP:8080`.

The launcher binds to the local network so the iPhone can reach it. Only allow inbound TCP 8080 in Windows Firewall on a **Private** network profile. Do not port-forward this server or expose it to the public internet.

## API routes

- `POST /v1/auth/register`, `POST /v1/auth/login`
- `GET /v1/me`
- `POST /v1/chats`, `GET /v1/chats`
- `POST /v1/chats/{id}/members?username=...`
- `GET /v1/chats/{id}/messages`, `POST /v1/chats/{id}/messages`
- `WS /v1/ws/chats/{id}?token=...`
- `GET /v1/assets/me`
- Admin-only: `GET /v1/admin/users`, `GET /v1/admin/users/{id}/assets`
- Admin-only: `POST /v1/admin/users/{id}/stars`
- Admin-only: `POST /v1/admin/users/{id}/usernames`
- Admin-only: `POST /v1/admin/numbers`, `POST /v1/admin/users/{id}/numbers/{number_id}/assign`
- Admin-only: `POST /v1/admin/users/{id}/collectibles`

Admin requests use the `X-Admin-Token` header. The launcher creates and persists this token locally. Do not put it in the iOS app or distribute it to users. The bot should run as a trusted local process and use the same token.

## Asset boundaries

`DEARTG_STARS` are internal DearTG credits, not official Telegram Stars. Collectibles are off-chain records, not TON NFTs. Number entries are inventory records only; they do not provide SMS, verify ownership, or activate Telegram accounts. Real payments, blockchain minting, and SMS require separate legitimate providers and integrations.

## Current scope

This API provides local account registration/login, simple chat/message storage and WebSocket message notifications, internal asset records, and admin operations. It does not replace Telegram's MTProto servers, Telegram account authentication, end-to-end encryption, push delivery, or production infrastructure. Do not use it for real private communications or expose it to the internet until TLS, rate limits, abuse controls, secure key management, backups, migrations, and a security review are implemented.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
