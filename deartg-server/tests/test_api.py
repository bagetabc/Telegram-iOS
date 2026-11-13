from fastapi.testclient import TestClient
import pytest

import app as api


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DB_PATH", tmp_path / "test.sqlite3")
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
