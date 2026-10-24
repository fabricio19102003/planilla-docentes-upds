"""Chat authorization, upload hardening and cleanup (S8)."""
from __future__ import annotations

import pytest

from app.models.chat import ChatAttachment, ChatMessage
from app.models.user import User
from app.services import chat_service
from app.services.auth_service import auth_service
from tests.routers.test_chat import (
    JPEG, MAX_BYTES, PDF, PNG, _docente, _files_on_disk, _headers, _messages, _send, _upload,
)


@pytest.fixture
def chat_dir(tmp_path, monkeypatch):
    from app.config import settings
    d = tmp_path / "chat-attachments"
    monkeypatch.setattr(settings, "CHAT_ATTACHMENTS_DIR", str(d))
    return d


@pytest.fixture
def ana(db_session):
    return _docente(db_session, "7001", "Ana Quispe")


@pytest.fixture
def beto(db_session):
    return _docente(db_session, "7002", "Beto Mamani")


def test_deactivated_docente_is_401_everywhere(client, db_session, ana, chat_dir):
    sent = _send(client, ana, "hola", files=[_upload("a.pdf", PDF, "application/pdf")])
    att = sent.json()["attachments"][0]["id"]
    ana.is_active = False
    db_session.commit()
    h = _headers(ana)
    assert client.get("/api/chat/me", headers=h).status_code == 401
    assert client.post("/api/chat/me/messages", data={"body": "x"}, headers=h).status_code == 401
    assert client.post("/api/chat/me/read", headers=h).status_code == 401
    assert client.get("/api/chat/me/unread-count", headers=h).status_code == 401
    assert client.get(f"/api/chat/attachments/{att}", headers=h).status_code == 401


def test_unlinked_docente_gets_400_on_every_me_endpoint_and_404_on_downloads(client, db_session, ana, chat_dir):
    att = _send(client, ana, "", files=[_upload("a.pdf", PDF, "application/pdf")]).json()["attachments"][0]["id"]
    orphan = User(ci="9900", full_name="Sin", password_hash=auth_service.hash_password("Testpass123"),
                  role="docente", teacher_ci=None, is_active=True)
    db_session.add(orphan)
    db_session.commit()
    h = _headers(orphan)
    assert client.post("/api/chat/me/messages", data={"body": "x"}, headers=h).status_code == 400
    assert client.post("/api/chat/me/read", headers=h).status_code == 400
    assert client.get("/api/chat/me/unread-count", headers=h).status_code == 400
    assert client.get(f"/api/chat/attachments/{att}", headers=h).status_code == 404
    assert db_session.query(ChatMessage).count() == 1


def test_must_change_password_docente_cannot_download(client, db_session, ana, chat_dir):
    att = _send(client, ana, "", files=[_upload("a.pdf", PDF, "application/pdf")]).json()["attachments"][0]["id"]
    ana.must_change_password = True
    db_session.commit()
    assert client.get(f"/api/chat/attachments/{att}", headers=_headers(ana)).status_code == 403


def test_after_cursor_cannot_reach_other_conversations(client, ana, beto, chat_dir):
    _send(client, beto, "secreto de beto")
    _send(client, ana, "mio")
    for after in (0, 1, 10**6):
        bodies = [m["body"] for m in _messages(client, ana, after=after)["messages"]]
        assert "secreto de beto" not in bodies
    assert client.get("/api/chat/me", params={"after": -1}, headers=_headers(ana)).status_code == 422
    assert client.get("/api/chat/me", params={"limit": 0}, headers=_headers(ana)).status_code == 422
    assert client.get("/api/chat/me", params={"limit": 501}, headers=_headers(ana)).status_code == 422


def test_docente_mark_read_only_touches_own_conversation(client, db_session, admin_token, ana, beto, chat_dir):
    admin = db_session.query(User).filter(User.ci == "TEST_ADMIN_9999").one()
    _send(client, beto, "hola")
    beto_conv = _messages(client, beto)["conversation"]["id"]
    _send(client, admin, "respuesta", path=f"/api/chat/conversations/{beto_conv}/messages")
    client.post("/api/chat/me/read", headers=_headers(ana))
    assert client.get("/api/chat/me/unread-count", headers=_headers(beto)).json() == {"unread_count": 1}


def test_admin_can_download_and_docente_cannot_guess_ids(client, db_session, admin_token, ana, beto, chat_dir):
    admin = db_session.query(User).filter(User.ci == "TEST_ADMIN_9999").one()
    ids = [_send(client, beto, "", files=[_upload("b.pdf", PDF, "application/pdf")]).json()["attachments"][0]["id"]]
    for i in ids + [ids[0] + 1, 0, -1]:
        assert client.get(f"/api/chat/attachments/{i}", headers=_headers(ana)).status_code in (404, 422)
    assert client.get(f"/api/chat/attachments/{ids[0]}", headers=_headers(admin)).content == PDF


def test_traversal_and_header_injection_in_filename(client, db_session, ana, chat_dir):
    evil = '../../etc/x"\r\nX-Evil: 1;.pdf'
    r = _send(client, ana, "", files=[_upload(evil, PDF, "application/pdf")])
    assert r.status_code == 201, r.text
    meta = r.json()["attachments"][0]
    assert "/" not in meta["filename"] and "\r" not in meta["filename"] and '"' not in meta["filename"]
    stored = db_session.get(ChatAttachment, meta["id"]).stored_filename
    assert [p.name for p in _files_on_disk(chat_dir)] == [stored]
    d = client.get(f"/api/chat/attachments/{meta['id']}", headers=_headers(ana))
    assert d.status_code == 200
    assert "x-evil" not in {k.lower() for k in d.headers}
    cd = d.headers["content-disposition"]
    assert cd.startswith("attachment; filename=\"") and "\r" not in cd and "\n" not in cd
    print("CD:", cd, "| display:", meta["filename"])


def test_unicode_filename_disposition(client, ana, chat_dir):
    r = _send(client, ana, "", files=[_upload("Boleta año ñandú.png", PNG, "image/png")])
    d = client.get(f"/api/chat/attachments/{r.json()['attachments'][0]['id']}", headers=_headers(ana))
    print("CD:", d.headers["content-disposition"], d.headers["content-type"])
    assert d.headers["content-disposition"].startswith("inline;")


@pytest.mark.parametrize("files,code", [
    ([("files", ("a.pdf", PDF, "application/pdf"))] * 4, 422),
    ([("files", ("x.png", PDF, "image/png"))], 415),
    ([("files", ("x.pdf", b"<html>%PDF-", "application/pdf"))], 415),
    ([("files", ("x.svg", b"<svg/>", "image/svg+xml"))], 415),
    ([("files", ("e.pdf", b"", "application/pdf"))], 415),
    ([("files", ("big.pdf", b"%PDF-" + b"0" * (MAX_BYTES - 4), "application/pdf"))], 413),
    ([("files", ("ok.pdf", PDF, "application/pdf")), ("files", ("big.pdf", b"%PDF-" + b"0" * (MAX_BYTES - 4), "application/pdf"))], 413),
])
def test_rejections_leave_no_message_and_no_file(client, db_session, ana, chat_dir, files, code):
    before = db_session.query(ChatMessage).count()
    r = _send(client, ana, "texto", files=files)
    assert r.status_code == code, r.text
    assert db_session.query(ChatMessage).count() == before
    assert _files_on_disk(chat_dir) == []


def test_empty_filename_part_with_no_body_is_rejected(client, ana, chat_dir):
    r = _send(client, ana, "  ", files=[("files", ("", b"", "application/octet-stream"))])
    print("empty-filename:", r.status_code, r.text)
    assert r.status_code == 422


def test_db_failure_removes_written_files(client, db_session, ana, chat_dir, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(chat_service, "log_activity", boom)
    with pytest.raises(RuntimeError):
        _send(client, ana, "x", files=[_upload("a.pdf", PDF, "application/pdf"), _upload("b.jpg", JPEG, "image/jpeg")])
    assert _files_on_disk(chat_dir) == []
    assert db_session.query(ChatMessage).count() == 0


def test_ci_change_keeps_the_docente_conversation_and_attachments(client, db_session, ana, chat_dir):
    sent = _send(client, ana, "antes", files=[_upload("a.pdf", PDF, "application/pdf")]).json()
    conv = sent["conversation_id"]
    r = client.put("/api/teachers/7001", json={"ci": "7999"})
    assert r.status_code == 200, r.text
    db_session.expire_all()
    user = db_session.get(User, ana.id)
    assert user.teacher_ci == "7999"
    thread = _messages(client, user)
    assert thread["conversation"]["id"] == conv and thread["conversation"]["teacher_ci"] == "7999"
    assert [m["body"] for m in thread["messages"]] == ["antes"]
    assert client.get(f"/api/chat/attachments/{sent['attachments'][0]['id']}", headers=_headers(user)).content == PDF
