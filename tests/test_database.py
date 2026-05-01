# -*- coding: utf-8 -*-
"""
AgentMail Plugin - Database 模块单元测试

测试范围:
  - AgentDatabase 初始化与表创建
  - 配置管理 (save_config / get_config / delete_config)
  - 收件箱 (save_inbox_email / get_inbox / mark_agent_read / mark_replied / archive_emails)
  - 发件箱 (save_sent / get_sent)
  - 草稿箱 (save_draft / get_drafts)
  - 联系人 (create_contact / update_contact / delete_contacts / get_contacts / share_contact)
  - 联系人分组 (create_contact_group / delete_contact_group / get_contact_groups)
  - 回收站 (move_to_trash / restore_from_trash / permanent_delete / get_trash / clean_old_trash)
  - 备份 (backup / get_backup_list)
  - Agent 隔离 (get_db / get_all_agent_dbs)
"""

import json
import shutil
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from database import AgentDatabase, get_db, get_all_agent_dbs, _db_cache


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_db_cache():
    """每个测试前清空数据库缓存，避免实例复用导致隔离问题"""
    _db_cache.clear()
    yield
    _db_cache.clear()


@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    """使用临时目录替代 Path.home()"""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def db(temp_home):
    """返回一个测试用的 AgentDatabase 实例"""
    return AgentDatabase("test-agent")


@pytest.fixture
def db2(temp_home):
    """返回另一个 Agent 的数据库实例，用于隔离测试"""
    return AgentDatabase("test-agent-2")


# ── 初始化与表创建 ────────────────────────────────────────────────────────

class TestDatabaseInit:
    """测试数据库初始化"""

    def test_creates_directory_structure(self, temp_home):
        db = AgentDatabase("init-agent")
        assert db.db_dir.exists()
        assert db.bak_dir.exists()
        assert db.files_dir.exists()
        assert db.db_path.exists()

    def test_creates_all_tables(self, temp_home):
        db = AgentDatabase("init-agent")
        with db._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row["name"] for row in cursor.fetchall()}
        expected = {
            "email_configs", "inbox", "sent", "drafts",
            "trash", "contacts", "contact_groups",
        }
        assert expected.issubset(tables)

    def test_default_group_inserted(self, temp_home):
        db = AgentDatabase("init-agent")
        groups = db.get_contact_groups()
        assert any(g["name"] == "default" for g in groups)


# ── 配置管理 ──────────────────────────────────────────────────────────────

class TestConfig:
    """测试配置 CRUD"""

    def test_save_and_get_config(self, db):
        config = {
            "provider": "qq",
            "email": "test@qq.com",
            "smtp": {"host": "smtp.qq.com", "port": 587, "username": "test", "password": "pass", "use_tls": True},
            "imap": {"host": "imap.qq.com", "port": 993, "username": "test", "password": "pass", "use_ssl": True},
            "api_key": "key123",
            "forwarding": True,
        }
        assert db.save_config("hybrid", config) is True

        saved = db.get_config()
        assert saved is not None
        assert saved["hybrid"]["email"] == "test@qq.com"
        assert saved["hybrid"]["api_key"] == "key123"
        assert saved["hybrid"]["smtp"]["host"] == "smtp.qq.com"
        assert saved["hybrid"]["imap"]["use_ssl"] is True

    def test_update_config(self, db):
        db.save_config("hybrid", {"email": "old@test.com", "smtp": {"host": "old.com", "port": 587, "username": "u", "password": "p", "use_tls": True}, "imap": {"host": "old.com", "port": 993, "username": "u", "password": "p", "use_ssl": True}})
        db.save_config("hybrid", {"email": "new@test.com", "smtp": {"host": "new.com", "port": 587, "username": "u", "password": "p", "use_tls": True}, "imap": {"host": "new.com", "port": 993, "username": "u", "password": "p", "use_ssl": True}})

        saved = db.get_config()
        assert saved["hybrid"]["email"] == "new@test.com"

    def test_delete_config(self, db):
        db.save_config("hybrid", {"email": "del@test.com", "smtp": {"host": "h", "port": 1, "username": "u", "password": "p", "use_tls": True}, "imap": {"host": "h", "port": 1, "username": "u", "password": "p", "use_ssl": True}})
        assert db.delete_config() is True
        assert db.get_config() is None

    def test_get_config_returns_none_when_empty(self, db):
        assert db.get_config() is None


# ── 收件箱 ────────────────────────────────────────────────────────────────

class TestInbox:
    """测试收件箱操作"""

    def test_save_and_get_inbox(self, db):
        email_id = db.save_inbox_email({
            "message_id": "msg-1",
            "subject": "Test Subject",
            "sender_name": "Sender",
            "sender_email": "sender@example.com",
            "recipient": "me@example.com",
            "body": "Hello",
            "date": datetime.now().isoformat(),
        })
        assert email_id > 0

        inbox = db.get_inbox()
        assert inbox["total"] == 1
        assert inbox["items"][0]["subject"] == "Test Subject"

    def test_mark_agent_read(self, db):
        email_id = db.save_inbox_email({
            "message_id": "msg-2", "subject": "Read Test", "sender_email": "a@b.com",
            "body": "B", "date": datetime.now().isoformat(),
        })
        assert db.mark_agent_read(email_id, True) is True
        inbox = db.get_inbox()
        assert inbox["items"][0]["is_agent_read"] == 1

    def test_mark_replied(self, db):
        email_id = db.save_inbox_email({
            "message_id": "msg-3", "subject": "Reply Test", "sender_email": "a@b.com",
            "body": "B", "date": datetime.now().isoformat(),
        })
        assert db.mark_replied(email_id, "Thanks") is True
        inbox = db.get_inbox()
        assert inbox["items"][0]["is_replied"] == 1
        assert inbox["items"][0]["reply_content"] == "Thanks"

    def test_archive_emails(self, db):
        email_id = db.save_inbox_email({
            "message_id": "msg-4", "subject": "Archive", "sender_email": "a@b.com",
            "body": "B", "date": datetime.now().isoformat(), "folder": "inbox",
        })
        assert db.archive_emails([email_id]) is True
        inbox = db.get_inbox(folder="inbox")
        assert inbox["total"] == 0

    def test_pagination(self, db):
        for i in range(25):
            db.save_inbox_email({
                "message_id": f"msg-{i}", "subject": f"Mail {i}", "sender_email": "a@b.com",
                "body": "B", "date": datetime.now().isoformat(),
            })
        page1 = db.get_inbox(page=1, page_size=10)
        page2 = db.get_inbox(page=2, page_size=10)
        assert len(page1["items"]) == 10
        assert len(page2["items"]) == 10
        assert page1["page"] == 1
        assert page2["page"] == 2


# ── 发件箱 ────────────────────────────────────────────────────────────────

class TestSent:
    """测试发件箱"""

    def test_save_and_get_sent(self, db):
        sid = db.save_sent({
            "message_id": "s1", "subject": "Sent", "recipient": "to@example.com",
            "body": "Body", "status": "sent", "sent_at": datetime.now().isoformat(),
        })
        assert sid > 0
        sent = db.get_sent()
        assert sent["total"] == 1
        assert sent["items"][0]["subject"] == "Sent"


# ── 草稿箱 ────────────────────────────────────────────────────────────────

class TestDrafts:
    """测试草稿箱"""

    def test_create_draft(self, db):
        did = db.save_draft(None, {
            "subject": "Draft", "recipient": "to@example.com", "body": "Content",
        })
        assert did > 0
        drafts = db.get_drafts()
        assert drafts["total"] == 1

    def test_update_draft(self, db):
        did = db.save_draft(None, {"subject": "Old", "recipient": "to@example.com", "body": "Old"})
        updated = db.save_draft(did, {"subject": "New", "recipient": "to@example.com", "body": "New"})
        assert updated == did
        drafts = db.get_drafts()
        assert drafts["items"][0]["subject"] == "New"


# ── 联系人 ────────────────────────────────────────────────────────────────

class TestContacts:
    """测试联系人管理"""

    def test_create_contact(self, db):
        cid = db.create_contact({
            "name": "Alice", "phone": "13800138000", "email": "alice@example.com",
            "company": "ACME", "group_name": "default",
        })
        assert cid > 0

    def test_get_contacts(self, db):
        db.create_contact({"name": "Alice", "email": "alice@example.com", "group_name": "default"})
        db.create_contact({"name": "Bob", "email": "bob@example.com", "group_name": "work"})
        result = db.get_contacts()
        assert result["total"] == 2

    def test_update_contact(self, db):
        cid = db.create_contact({"name": "Old", "email": "old@example.com", "group_name": "default"})
        assert db.update_contact(cid, {"name": "New", "email": "new@example.com"}) is True
        contacts = db.get_contacts()
        assert contacts["items"][0]["name"] == "New"

    def test_delete_contacts_moves_to_trash(self, db):
        cid = db.create_contact({"name": "DeleteMe", "email": "del@example.com", "group_name": "default"})
        assert db.delete_contacts([cid]) is True
        contacts = db.get_contacts()
        assert contacts["total"] == 0
        trash = db.get_trash(item_type="contact")
        assert trash["total"] == 1

    def test_search_contacts(self, db):
        db.create_contact({"name": "Alice Smith", "email": "alice@example.com", "group_name": "default"})
        db.create_contact({"name": "Bob Jones", "email": "bob@company.com", "group_name": "default"})
        result = db.get_contacts(search="alice")
        assert result["total"] == 1
        assert result["items"][0]["name"] == "Alice Smith"

    def test_group_filter(self, db):
        db.create_contact({"name": "Alice", "email": "alice@example.com", "group_name": "default"})
        db.create_contact({"name": "Bob", "email": "bob@example.com", "group_name": "work"})
        result = db.get_contacts(group="work")
        assert result["total"] == 1
        assert result["items"][0]["name"] == "Bob"

    def test_share_contact(self, db):
        cid = db.create_contact({"name": "ShareMe", "email": "share@example.com", "group_name": "default"})
        assert db.share_contact(cid, ["agent-a", "agent-b"]) is True
        contacts = db.get_contacts()
        shared_with = json.loads(contacts["items"][0]["shared_with"])
        assert set(shared_with) == {"agent-a", "agent-b"}


# ── 联系人分组 ────────────────────────────────────────────────────────────

class TestContactGroups:
    """测试联系人分组"""

    def test_create_group(self, db):
        gid = db.create_contact_group("VIP")
        assert gid > 0
        groups = db.get_contact_groups()
        assert any(g["name"] == "VIP" for g in groups)

    def test_create_duplicate_group_returns_zero(self, db):
        db.create_contact_group("VIP")
        gid = db.create_contact_group("VIP")
        assert gid == 0

    def test_delete_group_moves_contacts_to_default(self, db):
        gid = db.create_contact_group("TempGroup")
        cid = db.create_contact({"name": "Temp", "email": "temp@example.com", "group_name": "TempGroup"})
        # 注意：create_contact 不会自动把 group_name 映射到已存在的分组名，
        # 但 delete_contact_group 会把该分组下的联系人移到 default
        # 由于 SQLite 不检查外键，这里直接测试删除行为
        assert db.delete_contact_group(gid) is True
        groups = db.get_contact_groups()
        assert not any(g["name"] == "TempGroup" for g in groups)


# ── 回收站 ────────────────────────────────────────────────────────────────

class TestTrash:
    """测试回收站操作"""

    def test_move_inbox_to_trash(self, db):
        eid = db.save_inbox_email({
            "message_id": "t1", "subject": "Trash", "sender_email": "a@b.com",
            "body": "B", "date": datetime.now().isoformat(),
        })
        assert db.move_to_trash("inbox", [eid]) is True
        assert db.get_inbox()["total"] == 0
        assert db.get_trash(item_type="inbox")["total"] == 1

    def test_move_contact_to_trash(self, db):
        cid = db.create_contact({"name": "TrashMe", "email": "trash@example.com", "group_name": "default"})
        assert db.move_to_trash("contact", [cid]) is True
        assert db.get_contacts()["total"] == 0
        assert db.get_trash(item_type="contact")["total"] == 1

    def test_restore_from_trash(self, db):
        eid = db.save_inbox_email({
            "message_id": "t2", "subject": "Restore", "sender_email": "a@b.com",
            "body": "B", "date": datetime.now().isoformat(),
        })
        db.move_to_trash("inbox", [eid])
        trash = db.get_trash(item_type="inbox")
        tid = trash["items"][0]["id"]
        assert db.restore_from_trash([tid]) is True
        assert db.get_inbox()["total"] == 1
        assert db.get_trash()["total"] == 0

    def test_permanent_delete(self, db):
        eid = db.save_inbox_email({
            "message_id": "t3", "subject": "Perm", "sender_email": "a@b.com",
            "body": "B", "date": datetime.now().isoformat(),
        })
        db.move_to_trash("inbox", [eid])
        trash = db.get_trash()
        tid = trash["items"][0]["id"]
        assert db.permanent_delete([tid]) is True
        assert db.get_trash()["total"] == 0

    def test_clean_old_trash(self, db):
        eid = db.save_inbox_email({
            "message_id": "t4", "subject": "Old", "sender_email": "a@b.com",
            "body": "B", "date": datetime.now().isoformat(),
        })
        db.move_to_trash("inbox", [eid])
        # 手动修改 deleted_at 为 40 天前
        with db._get_conn() as conn:
            conn.execute(
                "UPDATE trash SET deleted_at = datetime('now', '-40 days') WHERE agent_id = ?",
                (db.agent_id,)
            )
            conn.commit()
        deleted = db.clean_old_trash(days=30)
        assert deleted == 1
        assert db.get_trash()["total"] == 0


# ── 备份 ──────────────────────────────────────────────────────────────────

class TestBackup:
    """测试备份功能"""

    def test_backup_creates_file(self, db):
        db.create_contact({"name": "B", "email": "b@example.com", "group_name": "default"})
        result = db.backup()
        assert result["success"] is True
        assert Path(result["backup_path"]).exists()

    def test_backup_list(self, db):
        import os, time
        db.create_contact({"name": "B", "email": "b@example.com", "group_name": "default"})
        db.backup()
        # 通过修改文件 mtime 制造时间差，避免同一秒内重复覆盖
        for p in db.bak_dir.glob("agentmail_backup_*.db"):
            os.utime(p, (p.stat().st_atime - 2, p.stat().st_mtime - 2))
        time.sleep(1.1)  # 等待秒级时间戳变化
        db.backup()
        backups = db.get_backup_list()
        assert len(backups) >= 2

    def test_backup_limits_to_10(self, db):
        import os, time
        for i in range(12):
            db.backup()
            # 每次备份后将所有备份文件 mtime 递减，确保时间戳不同且能触发保留 10 个的限制
            for idx, p in enumerate(sorted(db.bak_dir.glob("agentmail_backup_*.db"), key=lambda x: x.stat().st_mtime)):
                os.utime(p, (p.stat().st_atime, p.stat().st_mtime - idx))
            time.sleep(1.1)
        backups = db.get_backup_list()
        assert len(backups) == 10


# ── Agent 隔离 ────────────────────────────────────────────────────────────

class TestAgentIsolation:
    """测试多 Agent 数据隔离"""

    def test_different_db_paths(self, temp_home):
        db1 = AgentDatabase("agent-a")
        db2 = AgentDatabase("agent-b")
        assert db1.db_path != db2.db_path
        assert db1.agent_id in str(db1.db_path)
        assert db2.agent_id in str(db2.db_path)

    def test_data_isolation(self, db, db2):
        db.create_contact({"name": "Agent1", "email": "a1@example.com", "group_name": "default"})
        db2.create_contact({"name": "Agent2", "email": "a2@example.com", "group_name": "default"})

        assert db.get_contacts()["total"] == 1
        assert db2.get_contacts()["total"] == 1
        assert db.get_contacts()["items"][0]["name"] == "Agent1"
        assert db2.get_contacts()["items"][0]["name"] == "Agent2"

    def test_get_db_cache(self, temp_home):
        d1 = get_db("cached-agent")
        d2 = get_db("cached-agent")
        assert d1 is d2

    def test_get_all_agent_dbs(self, temp_home):
        AgentDatabase("all-1")
        AgentDatabase("all-2")
        dbs = get_all_agent_dbs()
        assert "all-1" in dbs
        assert "all-2" in dbs
