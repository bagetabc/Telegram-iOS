import asyncio
import os
import shlex
from html import escape

import httpx

BOT_TOKEN = os.getenv("DEARTG_BOT_TOKEN", "").strip()
API_URL = os.getenv("DEARTG_API_URL", "http://127.0.0.1:8080").rstrip("/")
ADMIN_TOKEN = os.getenv("DEARTG_ADMIN_TOKEN", "").strip()
ADMIN_IDS = {
    int(value.strip())
    for value in os.getenv("DEARTG_BOT_ADMIN_IDS", "").split(",")
    if value.strip().isdigit()
}
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def parse_args(text: str) -> list[str]:
    try:
        return shlex.split(text)
    except ValueError:
        return []


def format_assets(data: dict) -> str:
    user = data.get("user", {})
    balances = data.get("balances", {})
    lines = [
        f"Аккаунт: {user.get('username', '—')} (ID {user.get('id', '—')})",
        f"⭐ DearTG Stars: {balances.get('DEARTG_STARS', 0)}",
        "",
        "Юзернеймы:",
    ]
    lines.extend(f"@{item['username']}" for item in data.get("usernames", []))
    if not data.get("usernames"):
        lines.append("— нет")
    lines.extend(["", "Виртуальные номера:"])
    lines.extend(
        f"{item['phone_e164']} · {item['status']} · ID {item['id']}"
        for item in data.get("phone_numbers", [])
    )
    if not data.get("phone_numbers"):
        lines.append("— нет")
    lines.extend(["", "Коллекционные карточки:"])
    lines.extend(
        f"#{item['id']} {item['title']} [{item.get('chain', 'offchain')}]"
        for item in data.get("collectibles", [])
    )
    if not data.get("collectibles"):
        lines.append("— нет")
    return "\n".join(lines)


class DearTGBot:
    def __init__(self):
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(50.0, connect=10.0))
        self.api = httpx.AsyncClient(
            base_url=API_URL,
            timeout=20.0,
            headers={"X-Admin-Token": ADMIN_TOKEN},
        )
        self.offset = 0

    async def telegram(self, method: str, payload: dict):
        response = await self.http.post(f"{TELEGRAM_API}/{method}", json=payload)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("description", "Telegram API error"))
        return data["result"]

    async def send(self, chat_id: int, text: str):
        # Plain text deliberately avoids HTML/Markdown injection from user data.
        await self.telegram("sendMessage", {"chat_id": chat_id, "text": text[:4000]})

    async def server(self, method: str, path: str, **kwargs):
        response = await self.api.request(method, path, **kwargs)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise RuntimeError(f"API {response.status_code}: {detail}")
        return response.json() if response.content else {}

    async def handle(self, message: dict):
        chat_id = message.get("chat", {}).get("id")
        sender_id = message.get("from", {}).get("id")
        text = (message.get("text") or "").strip()
        if not chat_id or not sender_id or not text.startswith("/"):
            return
        if sender_id not in ADMIN_IDS:
            await self.send(chat_id, "⛔ Нет доступа. Этот бот доступен только администраторам.")
            return

        parts = parse_args(text)
        if not parts:
            await self.send(chat_id, "Не удалось разобрать команду. Используй /help.")
            return
        command = parts[0].split("@", 1)[0].lower()
        args = parts[1:]
        try:
            if command in ("/start", "/help"):
                await self.send(chat_id, self.help_text())
            elif command == "/users":
                data = await self.server("GET", "/v1/admin/users", params={"limit": 30})
                lines = [f"Пользователей: {data['total']}"]
                lines.extend(
                    f"ID {u['id']} · @{u['username']} · ⭐ {u['stars']}"
                    for u in data["items"]
                )
                await self.send(chat_id, "\n".join(lines))
            elif command == "/user" and len(args) == 1:
                data = await self.server("GET", f"/v1/admin/users/{int(args[0])}/assets")
                await self.send(chat_id, format_assets(data))
            elif command == "/stars" and len(args) >= 2:
                user_id, amount = int(args[0]), int(args[1])
                reason = " ".join(args[2:]) or "Admin issue"
                data = await self.server(
                    "POST", f"/v1/admin/users/{user_id}/stars",
                    json={"amount": amount, "reason": reason},
                )
                await self.send(chat_id, f"⭐ Начислено {data['issued']} DearTG Stars. Баланс: {data['balance']}.")
            elif command == "/username" and len(args) == 2:
                user_id = int(args[0])
                data = await self.server(
                    "POST", f"/v1/admin/users/{user_id}/usernames",
                    json={"username": args[1].lstrip("@")},
                )
                await self.send(chat_id, f"@{data['username']} закреплён за аккаунтом {user_id}.")
            elif command == "/number_add" and len(args) == 1:
                data = await self.server(
                    "POST", "/v1/admin/numbers",
                    json={"phone_e164": args[0]},
                )
                await self.send(chat_id, f"📱 Номер добавлен в виртуальный пул. ID: {data['id']}.")
            elif command == "/number_assign" and len(args) == 2:
                user_id, number_id = int(args[0]), int(args[1])
                data = await self.server(
                    "POST", f"/v1/admin/users/{user_id}/numbers/{number_id}/assign"
                )
                await self.send(chat_id, f"📱 {data['phone_e164']} назначен аккаунту {user_id}.")
            elif command == "/nft" and len(args) >= 2:
                user_id = int(args[0])
                title = args[1]
                description = " ".join(args[2:])
                data = await self.server(
                    "POST", f"/v1/admin/users/{user_id}/collectibles",
                    json={"title": title, "description": description},
                )
                await self.send(chat_id, f"💎 Карточка «{data['title']}» выдана. ID: {data['id']}.")
            else:
                await self.send(chat_id, "Неверные аргументы. Используй /help.")
        except (ValueError, RuntimeError, httpx.HTTPError) as error:
            await self.send(chat_id, f"Ошибка: {error}")

    @staticmethod
    def help_text() -> str:
        return (
            "DearTG Admin Bot\n\n"
            "/users — последние пользователи и баланс\n"
            "/user ID — активы пользователя\n"
            "/stars ID КОЛИЧЕСТВО [причина] — начислить фейковые Stars\n"
            "/username ID USERNAME — выдать юзернейм\n"
            "/number_add +15551234567 — добавить виртуальный номер\n"
            "/number_assign USER_ID NUMBER_ID — назначить номер\n"
            "/nft ID НАЗВАНИЕ [описание] — выдать фейковую NFT-карточку\n\n"
            "Все активы внутренние и хранятся в базе DearTG."
        )

    async def run(self):
        if not BOT_TOKEN or not ADMIN_TOKEN or not ADMIN_IDS:
            raise SystemExit(
                "Set DEARTG_BOT_TOKEN, DEARTG_ADMIN_TOKEN and "
                "DEARTG_BOT_ADMIN_IDS before starting."
            )
        health = await self.server("GET", "/health")
        if not health.get("ok"):
            raise SystemExit("DearTG API health check failed.")
        print("DearTG Admin Bot is polling. Stop with Ctrl+C.")
        try:
            while True:
                try:
                    updates = await self.telegram(
                        "getUpdates",
                        {"offset": self.offset, "timeout": 35, "allowed_updates": ["message"]},
                    )
                    for update in updates:
                        self.offset = max(self.offset, update["update_id"] + 1)
                        message = update.get("message")
                        if message:
                            await self.handle(message)
                except (httpx.HTTPError, RuntimeError) as error:
                    print(f"Polling/API error: {error}")
                    await asyncio.sleep(3)
        finally:
            await self.api.aclose()
            await self.http.aclose()


async def main():
    await DearTGBot().run()


if __name__ == "__main__":
    asyncio.run(main())
