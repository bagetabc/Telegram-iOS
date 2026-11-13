from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as api


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DB_PATH", tmp_path / "test.sqlite3")
    monkeypatch.setenv("DEARTG_ADMIN_TOKEN", "test-admin-secret")
    with TestClient(api.app) as test_client:
        yield test_client


def register(client, username):
    response = client.post("/v1/auth/register", json={
        "username": username,
        "password": "correct-horse-battery"
    })
    assert response.status_code == 201, response.text
    payload = response.json()
    return payload["access_token"], payload["user"]


def test_registration_login_and_duplicate(client):
    token, user = register(client, "alice")
    assert user["username"] == "alice"
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {token}"}).json()["id"] == user["id"]

    duplicate = client.post("/v1/auth/register", json={
        "username": "alice", "password": "correct-horse-battery"
    })
    assert duplicate.status_code == 409

    login = client.post("/v1/auth/login", json={
        "username": "alice", "password": "correct-horse-battery"
    })
    assert login.status_code == 200
    assert login.json()["user"]["id"] == user["id"]


def test_two_users_can_chat_and_exchange_messages(client):
    alice_token, _ = register(client, "alice")
    bob_token, bob = register(client, "bob")
    alice = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    created = client.post("/v1/chats", headers=alice, json={"title": "Test chat"})
    assert created.status_code == 201
    chat_id = created.json()["id"]

    invited = client.post(
        f"/v1/chats/{chat_id}/members",
        headers=alice,
        params={"username": "bob"},
    )
    assert invited.status_code == 201
    assert invited.json()["user"]["id"] == bob["id"]

    sent = client.post(
        f"/v1/chats/{chat_id}/messages",
        headers=bob_headers,
        json={"body": "Hello DearTG"},
    )
    assert sent.status_code == 201
    assert sent.json()["sender_id"] == bob["id"]

    history = client.get(f"/v1/chats/{chat_id}/messages", headers=alice)
    assert history.status_code == 200
    assert [message["body"] for message in history.json()] == ["Hello DearTG"]

    bob_chats = client.get("/v1/chats", headers=bob_headers)
    assert bob_chats.status_code == 200
    assert bob_chats.json()[0]["id"] == chat_id


def test_chat_membership_is_enforced(client):
    alice_token, _ = register(client, "alice")
    bob_token, _ = register(client, "bob")
    alice = {"Authorization": f"Bearer {alice_token}"}
    bob = {"Authorization": f"Bearer {bob_token}"}
    chat = client.post("/v1/chats", headers=alice, json={"title": "Private"}).json()

    response = client.post(
        f"/v1/chats/{chat['id']}/messages",
        headers=bob,
        json={"body": "not allowed"},
    )
    assert response.status_code == 404


def test_admin_asset_issuance_and_user_asset_listing(client):
    token, user = register(client, "assetuser")
    headers = {"Authorization": f"Bearer {token}"}
    admin = {"X-Admin-Token": "test-admin-secret"}

    denied = client.post(f"/v1/admin/users/{user['id']}/stars",
                         json={"amount": 100, "reason": "welcome bonus"})
    assert denied.status_code == 403

    stars = client.post(f"/v1/admin/users/{user['id']}/stars", headers=admin,
                        json={"amount": 100, "reason": "welcome bonus"})
    assert stars.status_code == 201
    assert stars.json()["balance"] == 100

    username = client.post(f"/v1/admin/users/{user['id']}/usernames", headers=admin,
                           json={"username": "assetuser_pro"})
    assert username.status_code == 201

    number = client.post("/v1/admin/numbers", headers=admin,
                         json={"phone_e164": "+15551234567"})
    assert number.status_code == 201
    assigned = client.post(
        f"/v1/admin/users/{user['id']}/numbers/{number.json()['id']}/assign",
        headers=admin)
    assert assigned.status_code == 200

    collectible = client.post(f"/v1/admin/users/{user['id']}/collectibles", headers=admin,
                              json={"title": "Founders badge", "metadata": {"level": 1}})
    assert collectible.status_code == 201
    assert collectible.json()["chain"] == "offchain"

    assets = client.get("/v1/assets/me", headers=headers)
    assert assets.status_code == 200
    payload = assets.json()
    assert payload["balances"]["DEARTG_STARS"] == 100
    assert payload["usernames"][0]["username"] == "assetuser_pro"
    assert payload["phone_numbers"][0]["phone_e164"] == "+15551234567"
    assert payload["collectibles"][0]["metadata"] == {"level": 1}


def test_admin_api_rejects_unknown_users_and_duplicate_inventory(client):
    admin = {"X-Admin-Token": "test-admin-secret"}
    missing = client.post("/v1/admin/users/999/stars", headers=admin,
                          json={"amount": 5, "reason": "test issue"})
    assert missing.status_code == 404
    first = client.post("/v1/admin/numbers", headers=admin,
                        json={"phone_e164": "+15557654321"})
    assert first.status_code == 201
    duplicate = client.post("/v1/admin/numbers", headers=admin,
                            json={"phone_e164": "+15557654321"})
    assert duplicate.status_code == 409


def test_admin_bot_user_directory_and_asset_lookup(client):
    token, user = register(client, "botmanaged")
    headers = {"Authorization": f"Bearer {token}"}
    admin = {"X-Admin-Token": "test-admin-secret"}
    client.post(f"/v1/admin/users/{user['id']}/stars", headers=admin,
                json={"amount": 75, "reason": "bot test"})

    listing = client.get("/v1/admin/users", headers=admin)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["stars"] == 75

    assets = client.get(f"/v1/admin/users/{user['id']}/assets", headers=admin)
    assert assets.status_code == 200
    assert assets.json()["user"]["username"] == "botmanaged"
    assert assets.json()["balances"]["DEARTG_STARS"] == 75

    missing = client.get("/v1/admin/users/999/assets", headers=admin)
    assert missing.status_code == 404
