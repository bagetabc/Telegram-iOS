# DearTG local API

This is the independent backend foundation for DearTG. It runs on a Windows PC and is reachable by an iPhone on the same trusted Wi-Fi network.

## Run on Windows

```powershell
cd deartg-server
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DEARTG_TOKEN_SECRET = (py -c "import secrets; print(secrets.token_hex(32))")
$env:DEARTG_ADMIN_TOKEN = (py -c "import secrets; print(secrets.token_urlsafe(48))")
$env:DEARTG_DATA_DIR = "$PWD\data"
python -m uvicorn app:app --host 0.0.0.0 --port 8080
```

Open `http://127.0.0.1:8080/docs` on the PC. Find the PC LAN IPv4 address with `ipconfig`; the iPhone uses `http://PC-LAN-IP:8080`. Allow TCP port 8080 in Windows Firewall only on a private network. Keep both devices on the same trusted Wi-Fi.

## API

- `POST /v1/auth/register`, `POST /v1/auth/login`
- `GET /v1/me`
- `POST /v1/chats`, `GET /v1/chats`
- `GET /v1/chats/{id}/messages`, `POST /v1/chats/{id}/messages`
- `WS /v1/ws/chats/{id}?token=...` (new message events)
- `GET /v1/assets/me` (DearTG balances, usernames, assigned numbers, collectible records)
- Admin-only `POST /v1/admin/users/{id}/stars` (issue internal `DEARTG_STARS` ledger credits)
- Admin-only `POST /v1/admin/users/{id}/usernames` (assign a DearTG username)
- Admin-only `POST /v1/admin/numbers` and `POST /v1/admin/users/{id}/numbers/{number_id}/assign` (number inventory)
- Admin-only `POST /v1/admin/users/{id}/collectibles` (off-chain DearTG collectible record)

Admin routes require the `X-Admin-Token` header and the server-side `DEARTG_ADMIN_TOKEN` secret. Never put this token in the iOS app or a public client. The future DearTG bot must call these routes from a trusted server process, not expose the admin token to bot users.

## Asset and number boundary

`DEARTG_STARS` is an internal DearTG points/credits balance. It is not Telegram Stars and cannot be spent in Telegram. Collectibles are off-chain metadata records, not NFTs minted on TON. Phone numbers are inventory records only: adding or assigning a number does not purchase it, prove ownership, receive SMS, or activate an account. Real TON transfers, on-chain NFT minting, SMS verification, and official Telegram asset integrations require separate provider, wallet, and smart-contract integrations.

## Storage and security

SQLite is used for the local prototype. Passwords are PBKDF2-HMAC-SHA256 hashed; bearer tokens are HMAC-signed and expire. Set unique random values for both secrets before use. Do not expose this prototype to the public internet yet: production still needs TLS, refresh/revocation, rate limits, account recovery, moderation, backups, migrations, push notifications, and a reviewed end-to-end encryption design.

The backend is independent of Telegram servers. The upstream iOS repository still contains Telegram source code; this backend alone does not replace its MTProto/account/chat stack.
\nThe companion Python Telegram admin bot is in `../deartg-bot`; follow its README after starting this API.\n