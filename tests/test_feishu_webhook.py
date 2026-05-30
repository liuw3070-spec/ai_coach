import pytest
from httpx import AsyncClient, ASGITransport
from app import app
from server.feishu.router import detect_intent


@pytest.mark.asyncio
async def test_url_verification_challenge():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/feishu/webhook", json={
            "challenge": "test_challenge_123", "token": "test_token", "type": "url_verification"
        })
    assert response.status_code == 200
    assert response.json()["challenge"] == "test_challenge_123"


@pytest.mark.asyncio
async def test_receive_text_message():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/feishu/webhook", json={
            "header": {"event_type": "im.message.receive_v1", "event_id": "evt_001"},
            "event": {
                "message": {"chat_id": "oc_test", "message_id": "om_001", "content": '{"text":"/new_plan"}'},
                "sender": {"sender_id": {"open_id": "ou_user1"}}
            }
        })
    assert response.status_code == 200


def test_detect_new_plan():
    assert detect_intent("/new_plan") == ("new_plan", None)


def test_detect_feedback():
    assert detect_intent("今天太难了") == ("feedback", "too_hard")


def test_detect_paste_link():
    intent, payload = detect_intent("https://www.youtube.com/watch?v=abc123")
    assert intent == "paste_link"


def test_detect_unknown():
    assert detect_intent("今天天气不错") == ("unknown", None)


def test_detect_help():
    assert detect_intent("/help") == ("help", None)
