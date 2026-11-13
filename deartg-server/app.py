import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

DATA_DIR = Path(os.getenv("DEARTG_DATA_DIR", Path(__file__).parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.getenv("DEARTG_DB_PATH", DATA_DIR / "deartg.sqlite3"))
TOKEN_SECRET = os.getenv("DEARTG_TOKEN_SECRET")
if not TOKEN_SECRET:
    # Development fallback only. Set a long random secret before exposing the server.
    TOKEN_SECRET = "LOCAL-ONLY-" + str(DB_PATH.resolve())
TOKEN_TTL = int(os.getenv("DEARTG_TOKEN_TTL", "604800"))

app = FastAPI(title="DearTG Local API", version="0.1.0",
              description="Local-first API foundation for the DearTG client.")
_connections: dict[int, set[WebSocket]] = {}


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL UNIQUE COLLATE NOCASE,
          password_hash TEXT NOT NULL,
          created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chats (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          created_by INTEGER NOT NULL REFERENCES users(id),
          created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS members (
          chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          PRIMARY KEY(chat_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
          sender_id INTEGER NOT NULL REFERENCES users(id),
          body TEXT NOT NULL,
          created_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id, id);
        CREATE TABLE IF NOT EXISTS wallet_ledger (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          asset_code TEXT NOT NULL,
          amount INTEGER NOT NULL,
          reason TEXT NOT NULL,
          created_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_wallet_user ON wallet_ledger(user_id, asset_code, id);
        CREATE TABLE IF NOT EXISTS usernames (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL UNIQUE COLLATE NOCASE,
          owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS phone_numbers (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          phone_e164 TEXT NOT NULL UNIQUE,
          owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
          status TEXT NOT NULL DEFAULT 'available',
          created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS collectibles (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          title TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          metadata_json TEXT NOT NULL DEFAULT '{}',
          chain TEXT NOT NULL DEFAULT 'offchain',
          contract_address TEXT,
          token_id TEXT,
          created_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_collectibles_owner ON collectibles(owner_id, id);

        """)


@app.on_event("startup")
def startup():
    init_db()


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=10, max_length=256)


class ChatCreate(BaseModel):
    title: str = Field(min_length=1, max_length=80)


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return base64.urlsafe_b64encode(salt + digest).decode()


def password_verify(password: str, encoded: str) -> bool:
    try:
        raw = base64.urlsafe_b64decode(encoded.encode())
        salt, expected = raw[:16], raw[16:]
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def issue_token(user_id: int) -> str:
    payload = {"sub": user_id, "exp": int(time.time()) + TOKEN_TTL}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=")
    sig = hmac.new(TOKEN_SECRET.encode(), body, hashlib.sha256).digest()
    return (body + b"." + base64.urlsafe_b64encode(sig).rstrip(b"=")).decode()


def read_token(token: str) -> int:
    try:
        body, signature = token.encode().split(b".", 1)
        expected = hmac.new(TOKEN_SECRET.encode(), body, hashlib.sha256).digest()
        supplied = base64.urlsafe_b64decode(signature + b"=" * (-len(signature) % 4))
        if not hmac.compare_digest(expected, supplied):
            raise ValueError("signature")
        payload = json.loads(base64.urlsafe_b64decode(body + b"=" * (-len(body) % 4)))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("expired")
        return int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")


def current_user(authorization: str | None = Header(default=None)) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    return read_token(authorization[7:])


def require_member(conn, chat_id: int, user_id: int):
    row = conn.execute("SELECT 1 FROM members WHERE chat_id=? AND user_id=?",
                       (chat_id, user_id)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Chat not found")


class StarsIssue(BaseModel):
    amount: int = Field(gt=0, le=1_000_000_000)
    reason: str = Field(min_length=3, max_length=160)


class UsernameIssue(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")


class NumberAdd(BaseModel):
    phone_e164: str = Field(min_length=8, max_length=16, pattern=r"^\+[1-9][0-9]{7,14}$")


class CollectibleIssue(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    metadata: dict = Field(default_factory=dict)


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    configured = os.getenv("DEARTG_ADMIN_TOKEN")
    if not configured:
        raise HTTPException(status_code=503, detail="Admin API is disabled: DEARTG_ADMIN_TOKEN is not configured")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, configured):
        raise HTTPException(status_code=403, detail="Admin token is invalid")


@app.get("/health")
def health():
    return {"ok": True, "service": "DearTG API", "version": "0.1.0"}


@app.post("/v1/auth/register", status_code=201)
def register(data: Credentials):
    with db() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)",
                (data.username, password_hash(data.password), int(time.time())))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Username is already taken")
        user_id = cur.lastrowid
    return {"access_token": issue_token(user_id), "token_type": "bearer",
            "user": {"id": user_id, "username": data.username}}


@app.post("/v1/auth/login")
def login(data: Credentials):
    with db() as conn:
        row = conn.execute("SELECT id,username,password_hash FROM users WHERE username=?",
                           (data.username,)).fetchone()
    if not row or not password_verify(data.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    return {"access_token": issue_token(row["id"]), "token_type": "bearer",
            "user": {"id": row["id"], "username": row["username"]}}


@app.get("/v1/me")
def me(user_id: int = __import__("fastapi").Depends(current_user)):
    with db() as conn:
        row = conn.execute("SELECT id,username,created_at FROM users WHERE id=?",
                           (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Account not found")
    return dict(row)



@app.get("/v1/admin/users")
def admin_list_users(limit: int = 50, offset: int = 0,
                     _: None = __import__("fastapi").Depends(require_admin)):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    with db() as conn:
        rows = conn.execute("""SELECT u.id,u.username,u.created_at,
            COALESCE((SELECT SUM(w.amount) FROM wallet_ledger w
              WHERE w.user_id=u.id AND w.asset_code='DEARTG_STARS'),0) stars
            FROM users u ORDER BY u.id DESC LIMIT ? OFFSET ?""",
            (limit, offset)).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}


@app.get("/v1/admin/users/{user_id}/assets")
def admin_user_assets(user_id: int,
                      _: None = __import__("fastapi").Depends(require_admin)):
    with db() as conn:
        user = conn.execute("SELECT id,username,created_at FROM users WHERE id=?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        balances = conn.execute(
            "SELECT asset_code,COALESCE(SUM(amount),0) balance FROM wallet_ledger WHERE user_id=? GROUP BY asset_code",
            (user_id,)).fetchall()
        names = conn.execute("SELECT username,created_at FROM usernames WHERE owner_id=? ORDER BY id", (user_id,)).fetchall()
        numbers = conn.execute("SELECT id,phone_e164,status,created_at FROM phone_numbers WHERE owner_id=? ORDER BY id", (user_id,)).fetchall()
        items = conn.execute("""SELECT id,title,description,metadata_json,chain,created_at
            FROM collectibles WHERE owner_id=? ORDER BY id DESC""", (user_id,)).fetchall()
    return {
        "user": dict(user),
        "balances": {row["asset_code"]: row["balance"] for row in balances},
        "usernames": [dict(row) for row in names],
        "phone_numbers": [dict(row) for row in numbers],
        "collectibles": [{**dict(row), "metadata": json.loads(row["metadata_json"])} for row in items],
    }

@app.get("/v1/assets/me")
def my_assets(user_id: int = __import__("fastapi").Depends(current_user)):
    with db() as conn:
        balances = conn.execute(
            "SELECT asset_code,COALESCE(SUM(amount),0) balance FROM wallet_ledger WHERE user_id=? GROUP BY asset_code",
            (user_id,)).fetchall()
        names = conn.execute("SELECT username,created_at FROM usernames WHERE owner_id=? ORDER BY id", (user_id,)).fetchall()
        numbers = conn.execute("SELECT phone_e164,status,created_at FROM phone_numbers WHERE owner_id=? ORDER BY id", (user_id,)).fetchall()
        items = conn.execute("""SELECT id,title,description,metadata_json,chain,contract_address,token_id,created_at
            FROM collectibles WHERE owner_id=? ORDER BY id DESC""", (user_id,)).fetchall()
    return {
        "balances": {row["asset_code"]: row["balance"] for row in balances},
        "usernames": [dict(row) for row in names],
        "phone_numbers": [dict(row) for row in numbers],
        "collectibles": [{**dict(row), "metadata": json.loads(row["metadata_json"])} for row in items],
        "notice": "DearTG internal assets only; no TON blockchain transfer or Telegram Stars/NFT is implied."
    }


@app.post("/v1/admin/users/{user_id}/stars", status_code=201)
def issue_deartg_stars(user_id: int, data: StarsIssue,
                       _: None = __import__("fastapi").Depends(require_admin)):
    now = int(time.time())
    with db() as conn:
        if not conn.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone():
            raise HTTPException(status_code=404, detail="User not found")
        conn.execute("INSERT INTO wallet_ledger(user_id,asset_code,amount,reason,created_at) VALUES(?,?,?,?,?)",
                     (user_id, "DEARTG_STARS", data.amount, data.reason, now))
        balance = conn.execute("SELECT COALESCE(SUM(amount),0) FROM wallet_ledger WHERE user_id=? AND asset_code='DEARTG_STARS'",
                               (user_id,)).fetchone()[0]
    return {"user_id": user_id, "asset": "DEARTG_STARS", "issued": data.amount, "balance": balance}


@app.post("/v1/admin/users/{user_id}/usernames", status_code=201)
def issue_username(user_id: int, data: UsernameIssue,
                   _: None = __import__("fastapi").Depends(require_admin)):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone():
            raise HTTPException(status_code=404, detail="User not found")
        try:
            conn.execute("INSERT INTO usernames(username,owner_id,created_at) VALUES(?,?,?)",
                         (data.username, user_id, int(time.time())))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Username is already assigned")
    return {"user_id": user_id, "username": data.username}


@app.post("/v1/admin/numbers", status_code=201)
def add_phone_number(data: NumberAdd,
                     _: None = __import__("fastapi").Depends(require_admin)):
    with db() as conn:
        try:
            cur = conn.execute("INSERT INTO phone_numbers(phone_e164,created_at) VALUES(?,?)",
                               (data.phone_e164, int(time.time())))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Number already exists")
    return {"id": cur.lastrowid, "phone_e164": data.phone_e164, "status": "available"}


@app.post("/v1/admin/users/{user_id}/numbers/{number_id}/assign")
def assign_phone_number(user_id: int, number_id: int,
                        _: None = __import__("fastapi").Depends(require_admin)):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone():
            raise HTTPException(status_code=404, detail="User not found")
        cur = conn.execute("UPDATE phone_numbers SET owner_id=?,status='assigned' WHERE id=? AND status='available'",
                           (user_id, number_id))
        if cur.rowcount != 1:
            raise HTTPException(status_code=409, detail="Number is unavailable")
        row = conn.execute("SELECT phone_e164 FROM phone_numbers WHERE id=?", (number_id,)).fetchone()
    return {"user_id": user_id, "phone_e164": row["phone_e164"], "status": "assigned"}


@app.post("/v1/admin/users/{user_id}/collectibles", status_code=201)
def issue_collectible(user_id: int, data: CollectibleIssue,
                      _: None = __import__("fastapi").Depends(require_admin)):
    now = int(time.time())
    with db() as conn:
        if not conn.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone():
            raise HTTPException(status_code=404, detail="User not found")
        cur = conn.execute("""INSERT INTO collectibles(owner_id,title,description,metadata_json,created_at)
            VALUES(?,?,?,?,?)""",
            (user_id, data.title, data.description, json.dumps(data.metadata, ensure_ascii=False), now))
        item_id = cur.lastrowid
    return {"id": item_id, "user_id": user_id, "title": data.title, "chain": "offchain",
            "notice": "Off-chain DearTG collectible record; not an on-chain NFT."}


@app.post("/v1/chats", status_code=201)
def create_chat(data: ChatCreate, user_id: int = __import__("fastapi").Depends(current_user)):
    now = int(time.time())
    with db() as conn:
        cur = conn.execute("INSERT INTO chats(title,created_by,created_at) VALUES(?,?,?)",
                           (data.title, user_id, now))
        chat_id = cur.lastrowid
        conn.execute("INSERT INTO members(chat_id,user_id) VALUES(?,?)", (chat_id, user_id))
    return {"id": chat_id, "title": data.title, "created_at": now}


@app.get("/v1/chats")
def list_chats(user_id: int = __import__("fastapi").Depends(current_user)):
    with db() as conn:
        rows = conn.execute("""SELECT c.id,c.title,c.created_at,
          (SELECT body FROM messages m WHERE m.chat_id=c.id ORDER BY m.id DESC LIMIT 1) last_message
          FROM chats c JOIN members mm ON mm.chat_id=c.id
          WHERE mm.user_id=? ORDER BY c.id DESC""", (user_id,)).fetchall()
    return [dict(row) for row in rows]


@app.post("/v1/chats/{chat_id}/members", status_code=201)
def add_chat_member(chat_id: int, username: str = __import__("fastapi").Query(min_length=3, max_length=32),
                   user_id: int = __import__("fastapi").Depends(current_user)):
    with db() as conn:
        require_member(conn, chat_id, user_id)
        target = conn.execute("SELECT id,username FROM users WHERE username=?",
                              (username,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        try:
            conn.execute("INSERT INTO members(chat_id,user_id) VALUES(?,?)",
                         (chat_id, target["id"]))
        except sqlite3.IntegrityError:
            pass
    return {"chat_id": chat_id, "user": {"id": target["id"], "username": target["username"]}}


@app.get("/v1/chats/{chat_id}/messages")
def list_messages(chat_id: int, before_id: int | None = None,
                  user_id: int = __import__("fastapi").Depends(current_user)):
    with db() as conn:
        require_member(conn, chat_id, user_id)
        if before_id:
            rows = conn.execute("""SELECT id,chat_id,sender_id,body,created_at FROM messages
                WHERE chat_id=? AND id<? ORDER BY id DESC LIMIT 100""",
                (chat_id, before_id)).fetchall()
        else:
            rows = conn.execute("""SELECT id,chat_id,sender_id,body,created_at FROM messages
                WHERE chat_id=? ORDER BY id DESC LIMIT 100""", (chat_id,)).fetchall()
    return [dict(row) for row in reversed(rows)]


async def publish(chat_id: int, event: dict):
    stale = []
    for socket in list(_connections.get(chat_id, set())):
        try:
            await socket.send_json(event)
        except Exception:
            stale.append(socket)
    for socket in stale:
        _connections.get(chat_id, set()).discard(socket)


@app.post("/v1/chats/{chat_id}/messages", status_code=201)
async def send_message(chat_id: int, data: MessageCreate,
                       user_id: int = __import__("fastapi").Depends(current_user)):
    now = int(time.time())
    with db() as conn:
        require_member(conn, chat_id, user_id)
        cur = conn.execute("""INSERT INTO messages(chat_id,sender_id,body,created_at)
            VALUES(?,?,?,?)""", (chat_id, user_id, data.body, now))
        row = conn.execute("SELECT id,chat_id,sender_id,body,created_at FROM messages WHERE id=?",
                           (cur.lastrowid,)).fetchone()
        event = dict(row)
    await publish(chat_id, {"type": "message.new", "message": event})
    return event


@app.websocket("/v1/ws/chats/{chat_id}")
async def chat_socket(websocket: WebSocket, chat_id: int, token: str):
    try:
        user_id = read_token(token)
        with db() as conn:
            require_member(conn, chat_id, user_id)
    except HTTPException:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    _connections.setdefault(chat_id, set()).add(websocket)
    try:
        while True:
            # Client may send ping frames as JSON; messages are sent via the REST endpoint.
            payload = await websocket.receive_json()
            if payload.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        _connections.get(chat_id, set()).discard(websocket)
