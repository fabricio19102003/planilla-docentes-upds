"""Shared admin/docente inbox with private attachments, exercised through the HTTP API."""
from __future__ import annotations

import pytest

from app.config import settings
from app.models.activity_log import ActivityLog
from app.models.teacher import Teacher
from app.models.user import User
from app.services.auth_service import auth_service

PDF = b"%PDF-1.4\n" + b"0" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 32
WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"0" * 8
MAX_BYTES = 10 * 1024 * 1024


@pytest.fixture
def chat_dir(tmp_path, monkeypatch):
    directory = tmp_path / "chat-attachments"
    monkeypatch.setattr(settings, "CHAT_ATTACHMENTS_DIR", str(directory))
    return directory


def _files_on_disk(directory):
    return [path for path in directory.rglob("*") if path.is_file()] if directory.exists() else []


def _headers(user: User) -> dict:
    token = auth_service.create_access_token(data={"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


def _docente(db_session, ci: str, name: str | None = None) -> User:
    teacher = Teacher(ci=ci, full_name=name or f"Docente {ci}")
    db_session.add(teacher)
    db_session.flush()
    user = User(
        ci=ci,
        full_name=teacher.full_name,
        password_hash=auth_service.hash_password("Testpass123"),
        role="docente",
        teacher_ci=ci,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def admin(db_session, admin_token):
    return db_session.query(User).filter(User.ci == "TEST_ADMIN_9999").one()


@pytest.fixture
def second_admin(db_session):
    user = User(
        ci="TEST_ADMIN_2",
        full_name="Segundo Admin",
        password_hash=auth_service.hash_password("Testpass123"),
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def ana(db_session):
    return _docente(db_session, "7001", "Ana Quispe")


@pytest.fixture
def beto(db_session):
    return _docente(db_session, "7002", "Beto Mamani")


def _send(client, user, body="", files=None, path="/api/chat/me/messages"):
    return client.post(
        path,
        data={"body": body},
        files=files or [],
        headers=_headers(user),
    )


def _upload(name: str, content: bytes, content_type: str):
    return ("files", (name, content, content_type))


def _messages(client, user, path="/api/chat/me", **params):
    response = client.get(path, params=params, headers=_headers(user))
    assert response.status_code == 200, response.text
    return response.json()


def _conversation_id(client, user) -> int:
    return _messages(client, user)["conversation"]["id"]


# ── Docente: own conversation ────────────────────────────────────────────────


def test_docente_gets_one_lazily_created_conversation_with_administracion(client, ana, chat_dir):
    first = _messages(client, ana)
    second = _messages(client, ana)

    assert first["messages"] == []
    assert first["conversation"]["teacher_ci"] == "7001"
    assert first["conversation"]["teacher_name"] == "Ana Quispe"
    assert first["conversation"]["unread_count"] == 0
    assert second["conversation"]["id"] == first["conversation"]["id"]


def test_docente_sends_text_and_sees_it_in_own_conversation(client, ana, chat_dir):
    response = _send(client, ana, "  Hola, necesito ayuda  ")

    assert response.status_code == 201, response.text
    message = response.json()
    assert message["body"] == "Hola, necesito ayuda"
    assert message["sender_role"] == "docente"
    assert message["sender_user_id"] == ana.id
    assert message["attachments"] == []
    assert [m["id"] for m in _messages(client, ana)["messages"]] == [message["id"]]


def test_docente_without_linked_teacher_cannot_use_chat(client, db_session, chat_dir):
    orphan = User(
        ci="9900",
        full_name="Sin Docente",
        password_hash=auth_service.hash_password("Testpass123"),
        role="docente",
        teacher_ci=None,
        is_active=True,
    )
    db_session.add(orphan)
    db_session.commit()

    response = client.get("/api/chat/me", headers=_headers(orphan))

    assert response.status_code == 400
    assert "docente vinculado" in response.json()["detail"]


def test_docente_never_sees_another_conversation(client, ana, beto, chat_dir):
    _send(client, ana, "Mensaje privado de Ana")
    _send(client, beto, "Mensaje de Beto")

    assert [m["body"] for m in _messages(client, beto)["messages"]] == ["Mensaje de Beto"]
    assert [m["body"] for m in _messages(client, ana)["messages"]] == ["Mensaje privado de Ana"]


def test_docente_cannot_use_admin_endpoints(client, ana, beto, chat_dir):
    other = _conversation_id(client, beto)
    headers = _headers(ana)

    assert client.get("/api/chat/conversations", headers=headers).status_code == 403
    assert client.get(f"/api/chat/conversations/{other}/messages", headers=headers).status_code == 403
    assert client.post(
        f"/api/chat/conversations/{other}/messages", data={"body": "intruso"}, headers=headers
    ).status_code == 403
    assert client.post(f"/api/chat/conversations/{other}/read", headers=headers).status_code == 403
    assert client.get("/api/chat/unread-count", headers=headers).status_code == 403
    assert _messages(client, beto)["messages"] == []


def test_admin_cannot_use_docente_endpoints(client, admin, chat_dir):
    headers = _headers(admin)

    assert client.get("/api/chat/me", headers=headers).status_code == 403
    assert client.post("/api/chat/me/messages", data={"body": "x"}, headers=headers).status_code == 403
    assert client.post("/api/chat/me/read", headers=headers).status_code == 403
    assert client.get("/api/chat/me/unread-count", headers=headers).status_code == 403


def test_chat_requires_authentication(client, chat_dir):
    client.headers.pop("Authorization")

    assert client.get("/api/chat/me").status_code == 401
    assert client.get("/api/chat/conversations").status_code == 401
    assert client.get("/api/chat/attachments/1").status_code == 401


# ── Admin inbox, unread counts and reading ───────────────────────────────────


def test_admin_lists_conversations_with_unread_counts_and_reading_resets_them(client, admin, ana, beto, chat_dir):
    _send(client, ana, "uno")
    _send(client, ana, "dos")
    _send(client, beto, "hola desde Beto")

    listing = client.get("/api/chat/conversations", headers=_headers(admin))
    assert listing.status_code == 200
    rows = {row["teacher_ci"]: row for row in listing.json()}
    assert rows["7001"]["teacher_name"] == "Ana Quispe"
    assert rows["7001"]["unread_count"] == 2
    assert rows["7001"]["last_message"]["preview"] == "dos"
    assert rows["7001"]["last_message"]["sender_role"] == "docente"
    assert rows["7002"]["unread_count"] == 1
    assert client.get("/api/chat/unread-count", headers=_headers(admin)).json() == {"unread_count": 3}

    read = client.post(f"/api/chat/conversations/{rows['7001']['id']}/read", headers=_headers(admin))
    assert read.status_code == 200
    assert read.json() == {"unread_count": 0}

    after = {row["teacher_ci"]: row for row in client.get("/api/chat/conversations", headers=_headers(admin)).json()}
    assert after["7001"]["unread_count"] == 0
    assert after["7002"]["unread_count"] == 1
    assert client.get("/api/chat/unread-count", headers=_headers(admin)).json() == {"unread_count": 1}

    _send(client, ana, "tres")
    assert client.get("/api/chat/unread-count", headers=_headers(admin)).json() == {"unread_count": 2}


def test_admin_conversations_are_ordered_by_last_activity_and_skip_empty_ones(client, admin, ana, beto, chat_dir):
    _send(client, ana, "primero")
    _send(client, beto, "segundo")
    _messages(client, ana)  # opening the portal chat must not reorder anything

    order = [row["teacher_ci"] for row in client.get("/api/chat/conversations", headers=_headers(admin)).json()]
    assert order == ["7002", "7001"]

    _send(client, ana, "tercero")
    order = [row["teacher_ci"] for row in client.get("/api/chat/conversations", headers=_headers(admin)).json()]
    assert order == ["7001", "7002"]


def test_admin_search_filters_by_teacher_name_or_ci(client, admin, ana, beto, chat_dir):
    _send(client, ana, "a")
    _send(client, beto, "b")
    headers = _headers(admin)

    by_name = client.get("/api/chat/conversations", params={"q": "quispe"}, headers=headers).json()
    by_ci = client.get("/api/chat/conversations", params={"q": "7002"}, headers=headers).json()
    none = client.get("/api/chat/conversations", params={"q": "zzz"}, headers=headers).json()

    assert [row["teacher_ci"] for row in by_name] == ["7001"]
    assert [row["teacher_ci"] for row in by_ci] == ["7002"]
    assert none == []


def test_any_admin_can_reply_and_docente_gets_unread_until_reading(client, admin, second_admin, ana, chat_dir):
    _send(client, ana, "Consulta")
    conversation_id = _conversation_id(client, ana)

    reply = client.post(
        f"/api/chat/conversations/{conversation_id}/messages",
        data={"body": "Respuesta del segundo admin"},
        headers=_headers(second_admin),
    )
    assert reply.status_code == 201, reply.text
    assert reply.json()["sender_role"] == "admin"
    assert reply.json()["sender_user_id"] == second_admin.id

    # The first admin sees the same shared thread.
    thread = _messages(client, admin, f"/api/chat/conversations/{conversation_id}/messages")
    assert [m["body"] for m in thread["messages"]] == ["Consulta", "Respuesta del segundo admin"]

    me = _messages(client, ana)
    assert me["conversation"]["unread_count"] == 1
    assert client.get("/api/chat/me/unread-count", headers=_headers(ana)).json() == {"unread_count": 1}
    # A docente sees staff replies as Administración, not an individual admin.
    assert me["messages"][1]["sender_name"] == "Administración"

    assert client.post("/api/chat/me/read", headers=_headers(ana)).json() == {"unread_count": 0}
    assert client.get("/api/chat/me/unread-count", headers=_headers(ana)).json() == {"unread_count": 0}
    # The admin side keeps its own unread counter.
    assert client.get("/api/chat/unread-count", headers=_headers(admin)).json() == {"unread_count": 1}


def test_admin_reply_to_unknown_conversation_is_404(client, admin, chat_dir):
    response = client.post(
        "/api/chat/conversations/999999/messages", data={"body": "hola"}, headers=_headers(admin)
    )

    assert response.status_code == 404
    assert client.get("/api/chat/conversations/999999/messages", headers=_headers(admin)).status_code == 404
    assert client.post("/api/chat/conversations/999999/read", headers=_headers(admin)).status_code == 404


# ── Polling ──────────────────────────────────────────────────────────────────


def test_after_cursor_returns_only_newer_messages(client, admin, ana, chat_dir):
    first = _send(client, ana, "uno").json()
    second = _send(client, ana, "dos").json()
    conversation_id = _conversation_id(client, ana)

    newer = _messages(client, ana, after=first["id"])
    assert [m["id"] for m in newer["messages"]] == [second["id"]]
    assert _messages(client, ana, after=second["id"])["messages"] == []

    third = client.post(
        f"/api/chat/conversations/{conversation_id}/messages", data={"body": "tres"}, headers=_headers(admin)
    ).json()
    admin_view = _messages(
        client, admin, f"/api/chat/conversations/{conversation_id}/messages", after=second["id"]
    )
    assert [m["id"] for m in admin_view["messages"]] == [third["id"]]
    assert [m["id"] for m in _messages(client, ana, after=second["id"])["messages"]] == [third["id"]]


# ── Sending: validation and rejections ───────────────────────────────────────


def test_message_may_be_only_an_attachment(client, ana, chat_dir):
    response = _send(client, ana, "", files=[_upload("constancia.pdf", PDF, "application/pdf")])

    assert response.status_code == 201, response.text
    message = response.json()
    assert message["body"] == ""
    assert len(message["attachments"]) == 1
    assert message["attachments"][0]["filename"] == "constancia.pdf"
    assert message["attachments"][0]["content_type"] == "application/pdf"
    assert message["attachments"][0]["size_bytes"] == len(PDF)
    assert len(_files_on_disk(chat_dir)) == 1


def test_all_allowed_types_and_three_files_are_accepted(client, ana, chat_dir):
    response = _send(
        client,
        ana,
        "tres archivos",
        files=[
            _upload("a.jpg", JPEG, "image/jpeg"),
            _upload("b.png", PNG, "image/png"),
            _upload("c.webp", WEBP, "image/webp"),
        ],
    )

    assert response.status_code == 201, response.text
    assert [a["content_type"] for a in response.json()["attachments"]] == ["image/jpeg", "image/png", "image/webp"]
    assert len(_files_on_disk(chat_dir)) == 3


def test_files_totalling_exactly_20_mb_are_accepted(client, ana, chat_dir):
    half = PDF + b"0" * (MAX_BYTES - len(PDF))

    response = _send(client, ana, "dos", files=[_upload(f"{i}.pdf", half, "application/pdf") for i in range(2)])

    assert response.status_code == 201, response.text
    assert len(_files_on_disk(chat_dir)) == 2


def test_body_of_exactly_4000_characters_and_a_file_of_exactly_10_mb_are_accepted(client, ana, chat_dir):
    big = PDF + b"0" * (MAX_BYTES - len(PDF))

    response = _send(client, ana, "x" * 4000, files=[_upload("grande.pdf", big, "application/pdf")])

    assert response.status_code == 201, response.text
    assert response.json()["attachments"][0]["size_bytes"] == MAX_BYTES


REJECTIONS = {
    "empty_message": ("", []),
    "blank_message": ("   \n ", []),
    "body_over_4000": ("x" * 4001, []),
    "oversized_file": ("hola", [("grande.pdf", PDF + b"0" * MAX_BYTES, "application/pdf")]),
    "wrong_magic_bytes": ("hola", [("falso.png", b"MZ\x90\x00 not an image", "image/png")]),
    "magic_does_not_match_declared_type": ("hola", [("raro.png", PDF, "image/png")]),
    "unsupported_type": ("hola", [("script.exe", b"MZ\x90\x00", "application/x-msdownload")]),
    "html_declared_as_pdf": ("hola", [("x.pdf", b"<html><script>1</script></html>", "application/pdf")]),
    "fourth_file": ("hola", [(f"{i}.png", PNG, "image/png") for i in range(4)]),
    # Each file is valid, but together they pass the 20 MB per-message cap that keeps
    # requests under the 25 MB nginx limit.
    "files_over_20_mb_together": (
        "hola",
        [(f"{i}.pdf", PDF + b"0" * (8 * 1024 * 1024), "application/pdf") for i in range(3)],
    ),
    "one_bad_file_among_good_ones": (
        "hola",
        [("ok.png", PNG, "image/png"), ("mal.png", b"nope", "image/png")],
    ),
}


@pytest.mark.parametrize("case", sorted(REJECTIONS))
def test_rejected_messages_store_no_message_and_no_file(client, admin, ana, chat_dir, case):
    body, files = REJECTIONS[case]

    response = _send(client, ana, body, files=[_upload(*f) for f in files])

    assert 400 <= response.status_code < 500, response.text
    assert isinstance(response.json()["detail"], str)
    assert _messages(client, ana)["messages"] == []
    assert _files_on_disk(chat_dir) == []
    assert client.get("/api/chat/unread-count", headers=_headers(admin)).json() == {"unread_count": 0}


def test_admin_replies_are_validated_the_same_way(client, admin, ana, chat_dir):
    conversation_id = _conversation_id(client, ana)

    response = client.post(
        f"/api/chat/conversations/{conversation_id}/messages",
        data={"body": "hola"},
        files=[_upload("falso.png", b"nope", "image/png")],
        headers=_headers(admin),
    )

    assert 400 <= response.status_code < 500
    assert _messages(client, ana)["messages"] == []
    assert _files_on_disk(chat_dir) == []


# ── Private storage and authenticated download ───────────────────────────────


def test_attachments_are_stored_privately_with_random_names(client, ana, chat_dir):
    _send(client, ana, "adjunto", files=[_upload("Mi Constancia.pdf", PDF, "application/pdf")])

    stored = _files_on_disk(chat_dir)
    assert len(stored) == 1
    assert stored[0].read_bytes() == PDF
    assert "constancia" not in stored[0].name.lower()
    assert stored[0].parent == chat_dir


def test_default_attachment_directory_is_outside_the_public_upload_directory():
    from pathlib import Path

    chat = Path(settings.CHAT_ATTACHMENTS_DIR).resolve()
    uploads = Path(settings.UPLOAD_DIR).resolve()
    assert chat != uploads
    assert uploads not in chat.parents


def test_attachment_download_has_safe_headers_and_exact_content(client, admin, ana, chat_dir):
    message = _send(
        client, ana, "", files=[_upload('../../evil"\r\nX-Injected: 1.pdf', PDF, "application/pdf")]
    ).json()
    attachment = message["attachments"][0]

    for user in (ana, admin):
        response = client.get(f"/api/chat/attachments/{attachment['id']}", headers=_headers(user))
        assert response.status_code == 200
        assert response.content == PDF
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["x-content-type-options"] == "nosniff"
        disposition = response.headers["content-disposition"]
        assert disposition.startswith(("attachment", "inline"))
        assert "filename" in disposition
        for forbidden in ("..", "/", "\r", "\n", "X-Injected: 1"):
            assert forbidden not in disposition
        assert "x-injected" not in response.headers
        assert "no-store" in response.headers["cache-control"]
        assert "private" in response.headers["cache-control"]

    assert "/" not in attachment["filename"] and ".." not in attachment["filename"]
    assert "\n" not in attachment["filename"] and '"' not in attachment["filename"]


def test_image_attachment_is_served_with_its_detected_content_type(client, ana, chat_dir):
    attachment = _send(client, ana, "", files=[_upload("foto.png", PNG, "image/png")]).json()["attachments"][0]

    response = client.get(f"/api/chat/attachments/{attachment['id']}", headers=_headers(ana))

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_docente_cannot_download_another_docentes_attachment(client, ana, beto, chat_dir):
    attachment = _send(client, ana, "", files=[_upload("a.pdf", PDF, "application/pdf")]).json()["attachments"][0]

    response = client.get(f"/api/chat/attachments/{attachment['id']}", headers=_headers(beto))

    assert response.status_code in (403, 404)
    assert PDF not in response.content


def test_unknown_attachment_is_404(client, ana, chat_dir):
    assert client.get("/api/chat/attachments/424242", headers=_headers(ana)).status_code == 404


def test_attachment_whose_file_vanished_is_404_not_500(client, ana, chat_dir):
    attachment = _send(client, ana, "", files=[_upload("a.pdf", PDF, "application/pdf")]).json()["attachments"][0]
    for path in _files_on_disk(chat_dir):
        path.unlink()

    assert client.get(f"/api/chat/attachments/{attachment['id']}", headers=_headers(ana)).status_code == 404


def test_sends_are_recorded_in_the_activity_log(client, db_session, ana, chat_dir):
    _send(client, ana, "para el registro")

    entries = db_session.query(ActivityLog).filter(ActivityLog.category == "chat").all()
    assert len(entries) == 1
    assert entries[0].user_id == ana.id
    assert "para el registro" not in (entries[0].description or "")
