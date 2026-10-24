"""Admin-started conversations and the `before` cursor for older messages, through the HTTP API."""
from __future__ import annotations

import pytest

from app.models.chat import ChatConversation, ChatMessage
from app.models.teacher import Teacher
from app.models.user import User
from tests.routers.test_chat import _docente, _headers, _messages, _send

START = "/api/chat/conversations"


@pytest.fixture
def chat_dir(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "CHAT_ATTACHMENTS_DIR", str(tmp_path / "chat-attachments"))


@pytest.fixture
def admin(db_session, admin_token):
    return db_session.query(User).filter(User.ci == "TEST_ADMIN_9999").one()


@pytest.fixture
def ana(db_session):
    return _docente(db_session, "7001", "Ana Quispe")


@pytest.fixture
def beto(db_session):
    return _docente(db_session, "7002", "Beto Mamani")


def _start(client, user, teacher_ci):
    return client.post(START, json={"teacher_ci": teacher_ci}, headers=_headers(user))


def _admin_thread(client, admin, conversation_id, **params):
    response = client.get(
        f"/api/chat/conversations/{conversation_id}/messages", params=params, headers=_headers(admin)
    )
    assert response.status_code == 200, response.text
    return response.json()


def _ids(thread):
    return [m["id"] for m in thread["messages"]]


# ── S2: admin starts a conversation ──────────────────────────────────────────


def test_admin_start_returns_the_same_conversation_every_time(client, admin, ana, chat_dir):
    first = _start(client, admin, "7001")
    second = _start(client, admin, "7001")

    assert first.status_code == 200, first.text
    assert second.status_code == 200
    body = first.json()
    assert body["id"] == second.json()["id"]
    assert body["teacher_ci"] == "7001"
    assert body["teacher_name"] == "Ana Quispe"
    assert body["unread_count"] == 0
    assert body["last_message_at"] is None


def test_start_reuses_the_conversation_the_docente_already_has(client, admin, ana, chat_dir):
    existing = _messages(client, ana)["conversation"]["id"]

    assert _start(client, admin, "7001").json()["id"] == existing


def test_docente_cannot_start_a_conversation(client, db_session, ana, beto, chat_dir):
    response = _start(client, ana, "7002")

    assert response.status_code == 403
    assert db_session.query(ChatConversation).count() == 0


def test_start_requires_authentication(client, chat_dir):
    response = client.post(START, json={"teacher_ci": "7001"}, headers={"Authorization": "Bearer nope"})

    assert response.status_code == 401


def test_start_for_unknown_teacher_is_404_and_creates_nothing(client, db_session, admin, chat_dir):
    response = _start(client, admin, "0000")

    assert response.status_code == 404
    assert db_session.query(ChatConversation).count() == 0


def test_start_for_teacher_without_portal_user_is_422_with_spanish_message(client, db_session, admin, chat_dir):
    db_session.add(Teacher(ci="7100", full_name="Sin Portal"))
    db_session.commit()

    response = _start(client, admin, "7100")

    assert response.status_code == 422
    assert "portal" in response.json()["detail"].lower()
    assert db_session.query(ChatConversation).count() == 0


def test_start_ignores_an_admin_user_with_the_same_teacher_ci(client, db_session, admin, chat_dir):
    db_session.add(Teacher(ci="7100", full_name="Sin Portal"))
    db_session.flush()
    admin.teacher_ci = "7100"
    db_session.commit()

    assert _start(client, admin, "7100").status_code == 422


def test_start_rejects_a_missing_teacher_ci(client, admin, chat_dir):
    response = client.post(START, json={}, headers=_headers(admin))

    assert response.status_code == 422


def test_started_empty_conversation_stays_out_of_the_list_until_a_message_is_sent(
    client, admin, ana, chat_dir
):
    conversation_id = _start(client, admin, "7001").json()["id"]
    listing = client.get(START, headers=_headers(admin))
    assert listing.status_code == 200
    assert listing.json() == []

    sent = client.post(
        f"{START}/{conversation_id}/messages", data={"body": "Hola Ana"}, headers=_headers(admin)
    )
    assert sent.status_code == 201

    rows = client.get(START, headers=_headers(admin)).json()
    assert [(row["id"], row["teacher_ci"]) for row in rows] == [(conversation_id, "7001")]
    assert rows[0]["last_message"]["preview"] == "Hola Ana"
    # The docente sees the admin's first message in their single conversation.
    thread = _messages(client, ana)
    assert thread["conversation"]["id"] == conversation_id
    assert [m["body"] for m in thread["messages"]] == ["Hola Ana"]


# ── S3: `before` cursor ──────────────────────────────────────────────────────


def _send_many(client, user, count):
    ids = []
    for index in range(count):
        response = _send(client, user, f"m{index}")
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])
    return ids


@pytest.fixture
def long_thread(client, ana, chat_dir):
    return _send_many(client, ana, 205)


def test_default_page_is_the_latest_200_and_reports_older_messages(client, ana, long_thread):
    thread = _messages(client, ana)

    assert _ids(thread) == long_thread[5:]
    assert thread["has_more"] is True


def test_before_returns_the_remaining_older_messages_ascending_without_has_more(client, ana, long_thread):
    thread = _messages(client, ana, before=long_thread[5])

    assert _ids(thread) == long_thread[:5]
    assert thread["has_more"] is False


def test_before_pages_with_limit_and_chains_until_exhausted(client, ana, long_thread):
    page = _messages(client, ana, before=long_thread[5], limit=2)
    assert _ids(page) == long_thread[3:5]
    assert page["has_more"] is True

    page = _messages(client, ana, before=long_thread[3], limit=3)
    assert _ids(page) == long_thread[0:3]
    assert page["has_more"] is False


def test_before_is_exclusive_of_the_cursor_message(client, ana, long_thread):
    assert long_thread[0] not in _ids(_messages(client, ana, before=long_thread[0]))
    assert _messages(client, ana, before=long_thread[0])["messages"] == []


def test_short_thread_has_no_more(client, ana, chat_dir):
    _send_many(client, ana, 3)

    assert _messages(client, ana)["has_more"] is False


def test_before_and_after_together_are_rejected(client, ana, long_thread):
    response = client.get(
        "/api/chat/me", params={"before": long_thread[10], "after": long_thread[0]}, headers=_headers(ana)
    )

    assert response.status_code == 422
    assert "after" in response.json()["detail"] and "before" in response.json()["detail"]


def test_before_and_after_zero_together_are_rejected(client, ana, long_thread):
    response = client.get("/api/chat/me", params={"before": long_thread[10], "after": 0}, headers=_headers(ana))

    assert response.status_code == 422


def test_before_must_be_positive(client, ana, long_thread):
    response = client.get("/api/chat/me", params={"before": 0}, headers=_headers(ana))

    assert response.status_code == 422


def test_polling_with_after_still_returns_only_newer_messages(client, ana, long_thread):
    newer = _send(client, ana, "nuevo").json()["id"]

    thread = _messages(client, ana, after=long_thread[-1])

    assert _ids(thread) == [newer]
    assert thread["has_more"] is False
    assert _ids(_messages(client, ana, after=newer)) == []


def test_admin_before_pages_through_the_conversation_endpoint(client, admin, ana, long_thread):
    conversation_id = _messages(client, ana)["conversation"]["id"]

    latest = _admin_thread(client, admin, conversation_id)
    assert _ids(latest) == long_thread[5:]
    assert latest["has_more"] is True

    older = _admin_thread(client, admin, conversation_id, before=long_thread[5])
    assert _ids(older) == long_thread[:5]
    assert older["has_more"] is False


def test_admin_before_and_after_together_are_rejected(client, admin, ana, long_thread):
    conversation_id = _messages(client, ana)["conversation"]["id"]

    response = client.get(
        f"/api/chat/conversations/{conversation_id}/messages",
        params={"before": long_thread[10], "after": long_thread[0]},
        headers=_headers(admin),
    )

    assert response.status_code == 422


def test_docente_before_never_leaves_their_own_conversation(client, db_session, ana, beto, chat_dir):
    ana_ids = _send_many(client, ana, 3)
    beto_ids = _send_many(client, beto, 3)
    assert max(ana_ids) < min(beto_ids)

    # A cursor from Beto's thread and one above every id: only Ana's messages come back.
    for cursor in (beto_ids[-1], beto_ids[1], beto_ids[-1] + 1000):
        thread = _messages(client, ana, before=cursor)
        assert _ids(thread) == ana_ids
        assert thread["conversation"]["teacher_ci"] == "7001"
        assert thread["has_more"] is False
    assert db_session.query(ChatMessage).count() == 6
