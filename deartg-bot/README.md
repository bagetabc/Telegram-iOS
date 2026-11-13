# DearTG Admin Bot

A Python Telegram bot for managing the internal, fictional assets stored by the DearTG API. It uses long polling and the existing server admin API; no webhook or public inbound port is required.

## Windows setup

Open PowerShell in this folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DEARTG_BOT_TOKEN = "TOKEN_FROM_BOTFATHER"
$env:DEARTG_API_URL = "http://127.0.0.1:8080"
$env:DEARTG_ADMIN_TOKEN = "THE_SAME_SECRET_USED_BY_THE_API"
$env:DEARTG_BOT_ADMIN_IDS = "YOUR_TELEGRAM_NUMERIC_ID"
python bot.py
```

Start the DearTG API first. Keep the bot and API on the same trusted PC/network. Get the Telegram numeric user ID from a trusted ID lookup bot; do not use a username as the allowlist. Multiple administrators can be comma-separated.

## Commands

- `/users` — recent accounts and internal Stars balances
- `/user ID` — account assets and inventory
- `/stars ID AMOUNT [reason]` — issue internal DearTG Stars
- `/username ID USERNAME` — reserve a DearTG username for an account
- `/number_add +15551234567` — add a virtual number record to inventory
- `/number_assign USER_ID NUMBER_ID` — assign an inventory record
- `/nft ID TITLE [description]` — issue a fictional off-chain collectible card

## Security and scope

Only numeric Telegram IDs in `DEARTG_BOT_ADMIN_IDS` can use commands. The bot token and admin API token are read from environment variables and must never be committed. Run one bot instance per token because Telegram long polling does not support competing pollers.

Stars, usernames, phone numbers, and NFT cards are simulated DearTG database records. The number inventory does not provide SMS or phone service. Collectible cards are not blockchain NFTs, and DearTG Stars are not Telegram Stars.
