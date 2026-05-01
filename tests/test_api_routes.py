# -*- coding: utf-8 -*-
"""
AgentMail Plugin - FastAPI API Routes 单元测试

测试范围:
  - 健康检查 /health
  - 配置 API (get_config / save_traditional_config / save_agentmail_config / save_hybrid_config / delete_config)
  - 收件箱 API (get_inbox / mark_agent_read / mark_replied / archive_inbox / delete_inbox)
  - 发件箱 API (get_sent)
  - 草稿箱 API (get_drafts)
  - 回收站 API (get_trash / restore_trash / permanent_delete)
  - 联系人 API (get_contacts / create_contact / update_contact / delete_contact / batch_delete / share_contact / batch_share)
  - 联系人分组 API (get_contact_groups / create_contact_group / delete_contact_group)
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# 在导入 app 之前先 patch database 的 Path.home，避免在真实目录创建数据库
with patch("database.Path.home", return_value=Path("/tmp/agentmail_test_api")):
    from main import app

client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_db_cache(monkeypatch, tmp_path):
    """每个测试前清空数据库缓存，并使用临时目录作为 home"""
    import database as db_mod
    db_mod._db_cache.clear()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yield
    db_mod._db_cache.clear()


# ── 健康检查 ──────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["service"] == "agentmail"


# ── 配置 API ──────────────────────────────────────────────────────────────

class TestConfigAPI:
    def test_get_config_empty(self):
        resp = client.get("/api/v1/email/config/test-agent")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["config"] is None

    def test_save_traditional_config(self):
        payload = {
            "provider": "qq",
            "email": "test@qq.com",
            "receive_protocol": "imap",
            "smtp": {"host": "smtp.qq.com", "port": 587, "username": "test", "password": "pass", "use_tls": True},
            "imap": {"host": "imap.qq.com", "port": 993, "username": "test", "password": "pass", "use_ssl": True},
        }
        resp = client.post("/api/v1/email/config/test-agent/traditional", json=payload)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_save_agentmail_config(self):
        payload = {"api_key": "key123", "inbox_id": "inbox_1", "email": "am@example.com"}
        resp = client.post("/api/v1/email/config/test-agent/agentmail", json=payload)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_save_hybrid_config(self):
        payload = {"forwarding": True}
        resp = client.post("/api/v1/email/config/test-agent/hybrid", json=payload)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_delete_config(self):
        # 先保存再删除
        client.post("/api/v1/email/config/test-agent/agentmail", json={"api_key": "k", "inbox_id": "i", "email": "e"})
        resp = client.delete("/api/v1/email/config/test-agent")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# ── 收件箱 API ────────────────────────────────────────────────────────────

class TestInboxAPI:
    def test_get_empty_inbox(self):
        resp = client.get("/api/v1/email/test-agent/inbox")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []

    def test_mark_agent_read(self):
        # 先创建一封邮件
        import database as db_mod
        db = db_mod.get_db("test-agent")
        eid = db.save_inbox_email({
            "message_id": "m1", "subject": "S", "sender_email": "a@b.com",
            "body": "B", "date": "2024-01-01T00:00:00",
        })
        resp = client.post(f"/api/v1/email/test-agent/inbox/{eid}/agent-read")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_mark_replied(self):
        import database as db_mod
        db = db_mod.get_db("test-agent")
        eid = db.save_inbox_email({
            "message_id": "m2", "subject": "S", "sender_email": "a@b.com",
            "body": "B", "date": "2024-01-01T00:00:00",
        })
        resp = client.post(f"/api/v1/email/test-agent/inbox/{eid}/reply", json={"content": "Thanks"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_archive_inbox(self):
        import database as db_mod
        db = db_mod.get_db("test-agent")
        eid = db.save_inbox_email({
            "message_id": "m3", "subject": "S", "sender_email": "a@b.com",
            "body": "B", "date": "2024-01-01T00:00:00", "folder": "inbox",
        })
        resp = client.post("/api/v1/email/test-agent/inbox/archive", json={"ids": [eid]})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_delete_inbox(self):
        import database as db_mod
        db = db_mod.get_db("test-agent")
        eid = db.save_inbox_email({
            "message_id": "m4", "subject": "S", "sender_email": "a@b.com",
            "body": "B", "date": "2024-01-01T00:00:00",
        })
        resp = client.post("/api/v1/email/test-agent/inbox/delete", json={"ids": [eid]})
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# ── 发件箱 & 草稿箱 API ───────────────────────────────────────────────────

class TestSentAndDraftsAPI:
    def test_get_sent_empty(self):
        resp = client.get("/api/v1/email/test-agent/sent")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_get_drafts_empty(self):
        resp = client.get("/api/v1/email/test-agent/drafts")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ── 回收站 API ────────────────────────────────────────────────────────────

class TestTrashAPI:
    def test_get_trash_empty(self):
        resp = client.get("/api/v1/email/test-agent/trash")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_restore_trash(self):
        import database as db_mod
        db = db_mod.get_db("test-agent")
        eid = db.save_inbox_email({
            "message_id": "mt", "subject": "Trash", "sender_email": "a@b.com",
            "body": "B", "date": "2024-01-01T00:00:00",
        })
        db.move_to_trash("inbox", [eid])
        trash = db.get_trash()
        tid = trash["items"][0]["id"]
        resp = client.post("/api/v1/email/test-agent/trash/restore", json={"ids": [tid]})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["restored"] == 1

    def test_permanent_delete(self):
        import database as db_mod
        db = db_mod.get_db("test-agent")
        eid = db.save_inbox_email({
            "message_id": "mp", "subject": "Perm", "sender_email": "a@b.com",
            "body": "B", "date": "2024-01-01T00:00:00",
        })
        db.move_to_trash("inbox", [eid])
        trash = db.get_trash()
        tid = trash["items"][0]["id"]
        resp = client.request("DELETE", "/api/v1/email/test-agent/trash/permanent", json={"ids": [tid]})
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# ── 联系人 API ────────────────────────────────────────────────────────────

class TestContactsAPI:
    def test_get_contacts_empty(self):
        resp = client.get("/api/v1/email/test-agent/contacts")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_create_contact(self):
        payload = {
            "name": "Alice", "email": "alice@example.com",
            "phone": "13800138000", "company": "ACME", "group_name": "default",
        }
        resp = client.post("/api/v1/email/test-agent/contacts", json=payload)
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["id"] > 0

    def test_update_contact(self):
        import database as db_mod
        db = db_mod.get_db("test-agent")
        cid = db.create_contact({"name": "Old", "email": "old@example.com", "group_name": "default"})
        payload = {"name": "New", "email": "new@example.com", "group_name": "default"}
        resp = client.put(f"/api/v1/email/test-agent/contacts/{cid}", json=payload)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_delete_contact(self):
        import database as db_mod
        db = db_mod.get_db("test-agent")
        cid = db.create_contact({"name": "Del", "email": "del@example.com", "group_name": "default"})
        resp = client.delete(f"/api/v1/email/test-agent/contacts/{cid}")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_batch_delete_contacts(self):
        import database as db_mod
        db = db_mod.get_db("test-agent")
        c1 = db.create_contact({"name": "A", "email": "a@example.com", "group_name": "default"})
        c2 = db.create_contact({"name": "B", "email": "b@example.com", "group_name": "default"})
        resp = client.post("/api/v1/email/test-agent/contacts/batch-delete", json={"ids": [c1, c2]})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_share_contact(self):
        import database as db_mod
        db = db_mod.get_db("test-agent")
        cid = db.create_contact({"name": "Share", "email": "share@example.com", "group_name": "default"})
        resp = client.post(f"/api/v1/email/test-agent/contacts/{cid}/share", json={"target_agent_ids": ["agent-x"]})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_batch_share_contacts(self):
        import database as db_mod
        db = db_mod.get_db("test-agent")
        c1 = db.create_contact({"name": "A", "email": "a@example.com", "group_name": "default"})
        c2 = db.create_contact({"name": "B", "email": "b@example.com", "group_name": "default"})
        resp = client.post("/api/v1/email/test-agent/contacts/batch-share", json={
            "contact_ids": [c1, c2], "target_agent_ids": ["agent-y"],
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["shared"] == 2


# ── 联系人分组 API ────────────────────────────────────────────────────────

class TestContactGroupsAPI:
    def test_get_contact_groups(self):
        resp = client.get("/api/v1/email/test-agent/contact-groups")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert any(g["name"] == "default" for g in resp.json()["items"])

    def test_create_contact_group(self):
        resp = client.post("/api/v1/email/test-agent/contact-groups", json={"name": "VIP"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["id"] > 0

    def test_delete_contact_group(self):
        import database as db_mod
        db = db_mod.get_db("test-agent")
        gid = db.create_contact_group("TempGroup")
        resp = client.delete(f"/api/v1/email/test-agent/contact-groups/{gid}")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
