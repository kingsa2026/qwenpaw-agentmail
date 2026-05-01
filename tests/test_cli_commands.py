# -*- coding: utf-8 -*-
"""
AgentMail Plugin - CLI 命令单元测试

测试范围:
  - _get_agent_storage / _save_agent_storage
  - ListContactsCommand.handle
  - ShareContactsCommand.handle
  - ListInboxCommand.handle
  - SendEmailCommand.handle
  - ReadEmailCommand.handle
  - BackupCommand.handle
  - ConfigCommand.handle
"""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys

# 确保项目根目录在路径中
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli_commands import (
    _get_agent_storage,
    _save_agent_storage,
    ListContactsCommand,
    ShareContactsCommand,
    ListInboxCommand,
    SendEmailCommand,
    ReadEmailCommand,
    BackupCommand,
    ConfigCommand,
    STORAGE_KEY,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    """使用临时目录替代 Path.home()，避免污染真实环境"""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def mock_context():
    """构造一个模拟的 CLI 上下文对象"""
    ctx = MagicMock()
    ctx.agent_id = "test-agent"
    ctx.args = {}
    return ctx


@pytest.fixture
def sample_storage(temp_home):
    """创建一份带测试数据的存储并返回 agent_id"""
    agent_id = "test-agent"
    # 同时创建 agents.json 让 _get_all_agents 能识别目标 agent
    agents_path = temp_home / ".qwenpaw" / "agents.json"
    agents_path.parent.mkdir(parents=True, exist_ok=True)
    agents_path.write_text(
        json.dumps([{"id": "agent-2", "name": "Agent Two"}, {"id": "agent-3", "name": "Agent Three"}]),
        encoding="utf-8",
    )
    data = {
        "contacts": [
            {"id": 1, "name": "Alice", "email": "alice@example.com", "group_name": "default", "shared_with": "[]"},
            {"id": 2, "name": "Bob", "email": "bob@company.com", "group_name": "work", "shared_with": '["agent-2"]'},
            {"id": 3, "name": "Charlie", "email": "charlie@test.com", "group_name": "default", "shared_with": "[]"},
        ],
        "contactGroups": [{"id": 1, "name": "default"}, {"id": 2, "name": "work"}],
        "inbox": [
            {"id": 10, "subject": "Hello", "sender_email": "sender@example.com", "date": datetime.now().isoformat(), "is_read": False},
            {"id": 11, "subject": "Meeting", "sender_email": "boss@company.com", "date": datetime.now().isoformat(), "is_read": True},
        ],
        "sent": [
            {"id": 20, "subject": "Re: Hello", "to_email": "alice@example.com", "date": datetime.now().isoformat()},
        ],
        "drafts": [],
        "trash": [],
        "config": {"mode": "hybrid", "hybrid": {"email": "test@example.com"}},
    }
    _save_agent_storage(agent_id, data)
    return agent_id, data


# ── _get_agent_storage / _save_agent_storage ─────────────────────────────

class TestAgentStorage:
    """测试底层存储读写函数"""

    def test_get_storage_returns_default_when_no_file(self, temp_home):
        result = _get_agent_storage("nonexistent")
        assert result["contacts"] == []
        assert result["contactGroups"] == [{"id": 1, "name": "default"}]
        assert result["inbox"] == []
        assert result["config"] is None

    def test_save_and_get_storage_roundtrip(self, temp_home):
        agent_id = "agent-1"
        data = {"contacts": [{"id": 1, "name": "Test"}], "contactGroups": [], "inbox": [], "sent": [], "drafts": [], "trash": [], "config": None}
        assert _save_agent_storage(agent_id, data) is True

        loaded = _get_agent_storage(agent_id)
        assert loaded["contacts"][0]["name"] == "Test"

    def test_get_storage_logs_warning_on_corrupted_json(self, temp_home, caplog):
        agent_id = "bad-agent"
        # 新路径: ~/.qwenpaw/agents/{agent_id}/mail/
        storage_path = temp_home / ".qwenpaw" / "agents" / agent_id / "mail" / f"{STORAGE_KEY}_{agent_id}.json"
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.write_text("not-json", encoding="utf-8")

        with caplog.at_level("WARNING"):
            result = _get_agent_storage(agent_id)
        assert "存储文件 JSON 格式错误" in caplog.text
        assert result["contacts"] == []

    def test_save_storage_returns_false_on_exception(self, temp_home, monkeypatch):
        agent_id = "agent-2"
        # 让 mkdir 抛出异常以触发保存失败路径
        monkeypatch.setattr(Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
        result = _save_agent_storage(agent_id, {"contacts": []})
        assert result is False


# ── ListContactsCommand ───────────────────────────────────────────────────

class TestListContactsCommand:
    """测试 /agentmail-contacts 命令"""

    @pytest.mark.asyncio
    async def test_empty_contacts(self, temp_home, mock_context):
        mock_context.args = {}
        cmd = ListContactsCommand()
        result = await cmd.handle(mock_context)
        assert "当前没有联系人" in result

    @pytest.mark.asyncio
    async def test_list_all_contacts(self, temp_home, mock_context, sample_storage):
        mock_context.args = {}
        cmd = ListContactsCommand()
        result = await cmd.handle(mock_context)
        assert "AgentMail 联系人列表" in result
        assert "Alice" in result
        assert "Bob" in result
        assert "[已共享]" in result  # Bob 已共享

    @pytest.mark.asyncio
    async def test_filter_by_group(self, temp_home, mock_context, sample_storage):
        mock_context.args = {"group": "work"}
        cmd = ListContactsCommand()
        result = await cmd.handle(mock_context)
        assert "Bob" in result
        assert "Alice" not in result

    @pytest.mark.asyncio
    async def test_search_by_name(self, temp_home, mock_context, sample_storage):
        mock_context.args = {"search": "ali"}
        cmd = ListContactsCommand()
        result = await cmd.handle(mock_context)
        assert "Alice" in result
        assert "Bob" not in result

    @pytest.mark.asyncio
    async def test_search_by_email(self, temp_home, mock_context, sample_storage):
        mock_context.args = {"search": "company"}
        cmd = ListContactsCommand()
        result = await cmd.handle(mock_context)
        assert "Bob" in result
        assert "Alice" not in result

    @pytest.mark.asyncio
    async def test_no_match(self, temp_home, mock_context, sample_storage):
        mock_context.args = {"search": "zzzzz"}
        cmd = ListContactsCommand()
        result = await cmd.handle(mock_context)
        assert "没有找到匹配的联系人" in result

    @pytest.mark.asyncio
    async def test_shared_with_parsing_error(self, temp_home, mock_context):
        # 构造 shared_with 为非法 JSON 的情况
        _save_agent_storage(mock_context.agent_id, {
            "contacts": [
                {"id": 1, "name": "Bad", "email": "bad@example.com", "group_name": "default", "shared_with": "not-json"}
            ],
            "contactGroups": [{"id": 1, "name": "default"}],
            "inbox": [], "sent": [], "drafts": [], "trash": [], "config": None,
        })
        mock_context.args = {}
        cmd = ListContactsCommand()
        result = await cmd.handle(mock_context)
        assert "Bad" in result
        assert "[已共享]" not in result  # 解析失败视为未共享


# ── ShareContactsCommand ──────────────────────────────────────────────────

class TestShareContactsCommand:
    """测试 /agentmail-share 命令"""

    @pytest.mark.asyncio
    async def test_missing_agents_arg(self, temp_home, mock_context):
        mock_context.args = {"contacts": "1", "agents": ""}
        cmd = ShareContactsCommand()
        result = await cmd.handle(mock_context)
        assert "请指定目标 Agent" in result

    @pytest.mark.asyncio
    async def test_no_contacts_available(self, temp_home, mock_context):
        mock_context.args = {"contacts": "1", "agents": "agent-2"}
        cmd = ShareContactsCommand()
        result = await cmd.handle(mock_context)
        assert "当前没有联系人可共享" in result

    @pytest.mark.asyncio
    async def test_share_all(self, temp_home, mock_context, sample_storage):
        mock_context.args = {"all": True, "agents": "agent-2,agent-3"}
        cmd = ShareContactsCommand()
        result = await cmd.handle(mock_context)
        assert "成功共享" in result
        assert "3" in result  # 共享了 3 个联系人

    @pytest.mark.asyncio
    async def test_share_specific_contacts(self, temp_home, mock_context, sample_storage):
        mock_context.args = {"contacts": "1,3", "agents": "agent-2"}
        cmd = ShareContactsCommand()
        result = await cmd.handle(mock_context)
        assert "成功共享" in result
        assert "Alice" in result
        assert "Charlie" in result

    @pytest.mark.asyncio
    async def test_invalid_contact_id_format(self, temp_home, mock_context, sample_storage):
        mock_context.args = {"contacts": "abc", "agents": "agent-2"}
        cmd = ShareContactsCommand()
        result = await cmd.handle(mock_context)
        assert "ID 必须是数字" in result

    @pytest.mark.asyncio
    async def test_contact_not_found(self, temp_home, mock_context, sample_storage):
        mock_context.args = {"contacts": "999", "agents": "agent-2"}
        cmd = ShareContactsCommand()
        result = await cmd.handle(mock_context)
        assert "没有找到指定的联系人" in result

    @pytest.mark.asyncio
    async def test_invalid_agent(self, temp_home, mock_context, sample_storage):
        mock_context.args = {"contacts": "1", "agents": "nonexistent-agent"}
        cmd = ShareContactsCommand()
        result = await cmd.handle(mock_context)
        assert "以下 Agent 不存在" in result

    @pytest.mark.asyncio
    async def test_share_without_contacts_and_no_all(self, temp_home, mock_context, sample_storage):
        mock_context.args = {"contacts": "", "agents": "agent-2"}
        cmd = ShareContactsCommand()
        result = await cmd.handle(mock_context)
        assert "请指定要共享的联系人 ID" in result


# ── ListInboxCommand ──────────────────────────────────────────────────────

class TestListInboxCommand:
    """测试 /agentmail-inbox 命令"""

    @pytest.mark.asyncio
    async def test_empty_inbox(self, temp_home, mock_context):
        mock_context.args = {}
        cmd = ListInboxCommand()
        result = await cmd.handle(mock_context)
        assert "收件箱为空" in result

    @pytest.mark.asyncio
    async def test_list_inbox(self, temp_home, mock_context, sample_storage):
        mock_context.args = {}
        cmd = ListInboxCommand()
        result = await cmd.handle(mock_context)
        assert "AgentMail 收件箱" in result
        assert "Hello" in result
        assert "Meeting" in result

    @pytest.mark.asyncio
    async def test_unread_only(self, temp_home, mock_context, sample_storage):
        mock_context.args = {"unread": True}
        cmd = ListInboxCommand()
        result = await cmd.handle(mock_context)
        assert "Hello" in result
        assert "Meeting" not in result  # 已读

    @pytest.mark.asyncio
    async def test_search_inbox(self, temp_home, mock_context, sample_storage):
        mock_context.args = {"search": "meeting"}
        cmd = ListInboxCommand()
        result = await cmd.handle(mock_context)
        assert "Meeting" in result
        assert "Hello" not in result

    @pytest.mark.asyncio
    async def test_pagination(self, temp_home, mock_context):
        # 构造 15 封邮件，测试分页
        emails = [
            {"id": i, "subject": f"Mail {i}", "sender_email": f"user{i}@example.com", "date": datetime.now().isoformat(), "is_read": False}
            for i in range(1, 16)
        ]
        _save_agent_storage(mock_context.agent_id, {
            "contacts": [], "contactGroups": [{"id": 1, "name": "default"}],
            "inbox": emails, "sent": [], "drafts": [], "trash": [], "config": None,
        })
        mock_context.args = {"page": 2}
        cmd = ListInboxCommand()
        result = await cmd.handle(mock_context)
        assert "第 2/" in result
        assert "Mail 11" in result or "Mail 10" in result


# ── SendEmailCommand ──────────────────────────────────────────────────────

class TestSendEmailCommand:
    """测试 /agentmail-send 命令"""

    @pytest.mark.asyncio
    async def test_missing_to_or_subject(self, temp_home, mock_context):
        mock_context.args = {"to": "", "subject": ""}
        cmd = SendEmailCommand()
        result = await cmd.handle(mock_context)
        assert "请提供收件人和主题" in result

    @pytest.mark.asyncio
    async def test_send_email_success(self, temp_home, mock_context):
        mock_context.args = {"to": "alice@example.com", "subject": "Hello", "body": "World"}
        cmd = SendEmailCommand()
        result = await cmd.handle(mock_context)
        assert "邮件发送成功" in result
        assert "alice@example.com" in result
        assert "Hello" in result

        # 验证数据已保存
        data = _get_agent_storage(mock_context.agent_id)
        assert len(data["sent"]) == 1
        assert data["sent"][0]["subject"] == "Hello"

    @pytest.mark.asyncio
    async def test_send_email_with_body_file(self, temp_home, mock_context):
        # 使用相对路径（当前工作目录内）
        import os
        body_path = Path(os.getcwd()) / "test_body.txt"
        body_path.write_text("File content here", encoding="utf-8")
        try:
            mock_context.args = {"to": "bob@example.com", "subject": "File Test", "body-file": "test_body.txt"}
            cmd = SendEmailCommand()
            result = await cmd.handle(mock_context)
            assert "邮件发送成功" in result

            data = _get_agent_storage(mock_context.agent_id)
            assert data["sent"][0]["body"] == "File content here"
        finally:
            if body_path.exists():
                body_path.unlink()

    @pytest.mark.asyncio
    async def test_body_file_not_found(self, temp_home, mock_context):
        mock_context.args = {"to": "bob@example.com", "subject": "File Test", "body-file": "nonexistent_file.txt"}
        cmd = SendEmailCommand()
        result = await cmd.handle(mock_context)
        assert "文件不存在" in result

    @pytest.mark.asyncio
    async def test_send_email_increment_id(self, temp_home, mock_context):
        # 先写入一封已发送邮件
        _save_agent_storage(mock_context.agent_id, {
            "contacts": [], "contactGroups": [{"id": 1, "name": "default"}],
            "inbox": [], "sent": [{"id": 5, "subject": "Old", "to_email": "old@example.com", "date": datetime.now().isoformat()}],
            "drafts": [], "trash": [], "config": None,
        })
        mock_context.args = {"to": "new@example.com", "subject": "New", "body": "Body"}
        cmd = SendEmailCommand()
        result = await cmd.handle(mock_context)

        data = _get_agent_storage(mock_context.agent_id)
        ids = [e["id"] for e in data["sent"]]
        assert max(ids) == 6


# ── ReadEmailCommand ──────────────────────────────────────────────────────

class TestReadEmailCommand:
    """测试 /agentmail-read 命令"""

    @pytest.mark.asyncio
    async def test_missing_id(self, temp_home, mock_context):
        mock_context.args = {"id": ""}
        cmd = ReadEmailCommand()
        result = await cmd.handle(mock_context)
        assert "请指定邮件 ID" in result

    @pytest.mark.asyncio
    async def test_invalid_id(self, temp_home, mock_context):
        mock_context.args = {"id": "abc"}
        cmd = ReadEmailCommand()
        result = await cmd.handle(mock_context)
        assert "ID 必须是数字" in result

    @pytest.mark.asyncio
    async def test_email_not_found(self, temp_home, mock_context):
        mock_context.args = {"id": "999"}
        cmd = ReadEmailCommand()
        result = await cmd.handle(mock_context)
        assert "找不到 ID 为 999 的邮件" in result

    @pytest.mark.asyncio
    async def test_read_inbox_email(self, temp_home, mock_context, sample_storage):
        mock_context.args = {"id": "10"}
        cmd = ReadEmailCommand()
        result = await cmd.handle(mock_context)
        assert "邮件详情" in result
        assert "Hello" in result
        assert "sender@example.com" in result
        assert "未读" in result

    @pytest.mark.asyncio
    async def test_read_sent_email(self, temp_home, mock_context, sample_storage):
        mock_context.args = {"id": "20"}
        cmd = ReadEmailCommand()
        result = await cmd.handle(mock_context)
        assert "Re: Hello" in result
        assert "alice@example.com" in result

    @pytest.mark.asyncio
    async def test_action_context(self, temp_home, mock_context, sample_storage):
        mock_context.args = {"id": "10", "action": "context"}
        cmd = ReadEmailCommand()
        result = await cmd.handle(mock_context)
        assert "已添加到上下文" in result
        assert "[Email Context]" in result

    @pytest.mark.asyncio
    async def test_action_memory(self, temp_home, mock_context, sample_storage):
        mock_context.args = {"id": "10", "action": "memory"}
        cmd = ReadEmailCommand()
        result = await cmd.handle(mock_context)
        assert "已添加到记忆" in result

        # 验证记忆文件已写入 (新路径: ~/.qwenpaw/agents/{agent_id}/mail/)
        memory_path = temp_home / ".qwenpaw" / "agents" / mock_context.agent_id / "mail" / f"agentmail_memory_{mock_context.agent_id}.json"
        assert memory_path.exists()
        memories = json.loads(memory_path.read_text(encoding="utf-8"))
        assert len(memories) == 1
        assert memories[0]["type"] == "email_memory"


# ── BackupCommand ─────────────────────────────────────────────────────────

class TestBackupCommand:
    """测试 /agentmail-backup 命令"""

    @pytest.mark.asyncio
    async def test_create_backup(self, temp_home, mock_context, sample_storage):
        mock_context.args = {}
        cmd = BackupCommand()
        result = await cmd.handle(mock_context)
        assert "备份创建成功" in result
        assert "联系人: 3 个" in result

    @pytest.mark.asyncio
    async def test_list_backups(self, temp_home, mock_context, sample_storage):
        # 先创建一次备份
        cmd = BackupCommand()
        await cmd.handle(mock_context)

        mock_context.args = {"list": True}
        result = await cmd.handle(mock_context)
        assert "AgentMail 备份列表" in result
        assert "联系人: 3 个" in result

    @pytest.mark.asyncio
    async def test_list_backups_empty(self, temp_home, mock_context):
        mock_context.args = {"list": True}
        cmd = BackupCommand()
        result = await cmd.handle(mock_context)
        assert "暂无备份记录" in result

    @pytest.mark.asyncio
    async def test_backup_limits_to_10(self, temp_home, mock_context):
        # 创建 12 个备份，验证只保留最近 10 个
        cmd = BackupCommand()
        for i in range(12):
            _save_agent_storage(mock_context.agent_id, {
                "contacts": [{"id": i, "name": f"User{i}", "email": f"u{i}@example.com", "group_name": "default", "shared_with": "[]"}],
                "contactGroups": [{"id": 1, "name": "default"}],
                "inbox": [], "sent": [], "drafts": [], "trash": [], "config": None,
            })
            await cmd.handle(mock_context)

        # 备份路径: ~/.qwenpaw/agents/{agent_id}/mail/
        backups_path = temp_home / ".qwenpaw" / "agents" / mock_context.agent_id / "mail" / f"{STORAGE_KEY}_{mock_context.agent_id}_backups.json"
        backups = json.loads(backups_path.read_text(encoding="utf-8"))
        assert len(backups) == 10


# ── ConfigCommand ─────────────────────────────────────────────────────────

class TestConfigCommand:
    """测试 /agentmail-config 命令"""

    @pytest.mark.asyncio
    async def test_no_config(self, temp_home, mock_context):
        mock_context.args = {}
        cmd = ConfigCommand()
        result = await cmd.handle(mock_context)
        assert "当前未配置邮箱" in result

    @pytest.mark.asyncio
    async def test_set_invalid_mode(self, temp_home, mock_context):
        mock_context.args = {"set-mode": "invalid"}
        cmd = ConfigCommand()
        result = await cmd.handle(mock_context)
        assert "无效的模式" in result

    @pytest.mark.asyncio
    async def test_set_mode_hybrid(self, temp_home, mock_context):
        mock_context.args = {"set-mode": "hybrid"}
        cmd = ConfigCommand()
        result = await cmd.handle(mock_context)
        assert "已切换到 **hybrid** 模式" in result

        data = _get_agent_storage(mock_context.agent_id)
        assert data["config"]["mode"] == "hybrid"
        assert "hybrid" in data["config"]

    @pytest.mark.asyncio
    async def test_view_config(self, temp_home, mock_context, sample_storage):
        mock_context.args = {}
        cmd = ConfigCommand()
        result = await cmd.handle(mock_context)
        assert "AgentMail 当前配置" in result
        assert "hybrid" in result
        assert "test@example.com" in result

    @pytest.mark.asyncio
    async def test_set_mode_traditional(self, temp_home, mock_context):
        mock_context.args = {"set-mode": "traditional"}
        cmd = ConfigCommand()
        result = await cmd.handle(mock_context)
        assert "traditional" in result

    @pytest.mark.asyncio
    async def test_set_mode_agentmail(self, temp_home, mock_context):
        mock_context.args = {"set-mode": "agentmail"}
        cmd = ConfigCommand()
        result = await cmd.handle(mock_context)
        assert "agentmail" in result

    @pytest.mark.asyncio
    async def test_set_mode_none(self, temp_home, mock_context):
        mock_context.args = {"set-mode": "none"}
        cmd = ConfigCommand()
        result = await cmd.handle(mock_context)
        assert "none" in result
