# -*- coding: utf-8 -*-
"""
AgentMail CLI 命令处理器

提供完整的 CLI 接口，覆盖 UI 所有功能：
  联系人管理：/agentmail-contacts, /agentmail-share
  邮件管理：/agentmail-inbox, /agentmail-sent, /agentmail-drafts
  邮件操作：/agentmail-send, /agentmail-read, /agentmail-sync
  监听控制：/agentmail-listen
  回收站：/agentmail-trash
  备份：/agentmail-backup
  配置：/agentmail-config
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

STORAGE_KEY = "agentmail_data"
API_BASE = "http://127.0.0.1:18088/api/v1/email"

_qwenpaw_working_dir = os.environ.get("QWENPAW_WORKING_DIR", os.environ.get("COPAW_WORKING_DIR", ""))
if _qwenpaw_working_dir:
    _QWENPAW_HOME = Path(_qwenpaw_working_dir).expanduser().resolve()
else:
    _QWENPAW_HOME = Path.home() / ".qwenpaw"


def _get_agent_mail_dir(agent_id: str) -> Path:
    """获取 Agent 的 mail 数据目录（与 backend/database.py 一致）"""
    return _QWENPAW_HOME / "workspaces" / agent_id / "mail"


def _get_agent_mail_file(agent_id: str, filename: str) -> Path:
    """获取 Agent mail 目录下的文件路径"""
    return _get_agent_mail_dir(agent_id) / filename


def _api_get(path: str, agent_id: str) -> Dict[str, Any]:
    try:
        import httpx
        with httpx.Client(base_url=API_BASE, timeout=15) as client:
            resp = client.get(path, headers={"X-Agent-Id": agent_id})
            if resp.status_code == 200:
                return resp.json()
            return {"success": False, "error": f"HTTP {resp.status_code}"}
    except ImportError:
        return {"success": False, "error": "httpx not installed"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _api_post(path: str, data: Dict = None, agent_id: str = "") -> Dict[str, Any]:
    try:
        import httpx
        with httpx.Client(base_url=API_BASE, timeout=15) as client:
            resp = client.post(path, json=data or {}, headers={"X-Agent-Id": agent_id})
            if resp.status_code == 200:
                return resp.json()
            return {"success": False, "error": f"HTTP {resp.status_code}"}
    except ImportError:
        return {"success": False, "error": "httpx not installed"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _api_delete(path: str, agent_id: str) -> Dict[str, Any]:
    try:
        import httpx
        with httpx.Client(base_url=API_BASE, timeout=15) as client:
            resp = client.delete(path, headers={"X-Agent-Id": agent_id})
            if resp.status_code == 200:
                return resp.json()
            return {"success": False, "error": f"HTTP {resp.status_code}"}
    except ImportError:
        return {"success": False, "error": "httpx not installed"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _get_agent_storage(agent_id: str) -> Dict[str, Any]:
    storage_key = f"{STORAGE_KEY}_{agent_id}"
    storage_path = _get_agent_mail_file(agent_id, f"{storage_key}.json")

    if storage_path.exists():
        try:
            with open(storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.warning(f"存储文件 JSON 格式错误: {e}")
        except OSError as e:
            logger.warning(f"读取存储文件失败: {e}")

    return {
        "contacts": [],
        "contactGroups": [{"id": 1, "name": "default"}],
        "inbox": [],
        "sent": [],
        "drafts": [],
        "trash": [],
        "config": None,
    }


def _save_agent_storage(agent_id: str, data: Dict[str, Any]) -> bool:
    storage_key = f"{STORAGE_KEY}_{agent_id}"
    storage_path = _get_agent_mail_file(agent_id, f"{storage_key}.json")

    try:
        storage_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        with open(storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.chmod(storage_path, 0o755)
        return True
    except (OSError, TypeError) as e:
        logger.error(f"保存存储失败: {e}")
        return False


def _get_all_agents() -> List[Dict[str, str]]:
    agents = []

    try:
        storage_data = os.environ.get("QWENPAW_AGENT_STORAGE")
        if not storage_data:
            storage_path = _QWENPAW_HOME / "agent_storage.json"
            if storage_path.exists():
                with open(storage_path, "r", encoding="utf-8") as f:
                    storage_data = f.read()

        if storage_data:
            parsed = json.loads(storage_data)
            state = parsed.get("state", parsed)
            if state.get("agents") and isinstance(state["agents"], list):
                for a in state["agents"]:
                    if a.get("id"):
                        agents.append({"id": a["id"], "name": a.get("name", a["id"])})
    except Exception:
        pass

    if not agents:
        try:
            storage_path = _QWENPAW_HOME / "agents.json"
            if storage_path.exists():
                with open(storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for a in data:
                        agents.append({
                            "id": a.get("id", a.get("agent_id", "unknown")),
                            "name": a.get("name", a.get("id", "unknown")),
                        })
        except Exception:
            pass

    return agents


class ListContactsCommand:
    """Handler for /agentmail-contacts command.

    Usage:
        /agentmail-contacts                    # 列出所有联系人
        /agentmail-contacts --group default    # 按分组筛选
        /agentmail-contacts --search "name"    # 搜索联系人
    """

    command_name = "/agentmail-contacts"

    async def handle(self, context) -> str:
        agent_id = getattr(context, "agent_id", "default")
        args = getattr(context, "args", {})

        group_filter = args.get("group", "")
        search_query = args.get("search", "")

        res = _api_get(f"/{agent_id}/contacts", agent_id)
        if res.get("success"):
            contacts = res.get("items", [])
        else:
            data = _get_agent_storage(agent_id)
            contacts = data.get("contacts", [])

        if not contacts:
            return "**AgentMail**: 当前没有联系人。"

        filtered = contacts
        if group_filter:
            filtered = [c for c in filtered if c.get("group_name") == group_filter]
        if search_query:
            search_lower = search_query.lower()
            filtered = [
                c for c in filtered
                if search_lower in c.get("name", "").lower()
                or search_lower in c.get("email", "").lower()
            ]

        if not filtered:
            return "**AgentMail**: 没有找到匹配的联系人。"

        lines = [f"**AgentMail 联系人列表** ({len(filtered)} 个)", ""]
        for i, contact in enumerate(filtered[:20], 1):
            shared = contact.get("shared_with", "[]")
            try:
                shared_list = json.loads(shared) if isinstance(shared, str) else shared
                shared_count = len(shared_list) if isinstance(shared_list, list) else 0
            except Exception:
                shared_count = 0

            lines.append(
                f"{i}. **{contact.get('name', '未命名')}** "
                f"({contact.get('email', '无邮箱')}) "
                f"[ID: {contact.get('id')}]"
                f"{' [已共享]' if shared_count > 0 else ''}"
            )

        if len(filtered) > 20:
            lines.append(f"\n... 还有 {len(filtered) - 20} 个联系人")

        lines.append("\n---")
        lines.append("使用 `/agentmail-share --contacts ID1,ID2 --agents AGENT1,AGENT2` 共享联系人")

        return "\n".join(lines)


class ShareContactsCommand:
    """Handler for /agentmail-share command.

    Usage:
        /agentmail-share --contacts 1,2,3 --agents agent-2,agent-3
        /agentmail-share --all --agents agent-2
    """

    command_name = "/agentmail-share"

    async def handle(self, context) -> str:
        agent_id = getattr(context, "agent_id", "default")
        args = getattr(context, "args", {})

        contacts_arg = args.get("contacts", "")
        agents_arg = args.get("agents", "")
        share_all = args.get("all", False)

        if not agents_arg:
            return (
                "**AgentMail**: 请指定目标 Agent。\n\n"
                "用法:\n"
                "  `/agentmail-share --contacts 1,2,3 --agents agent-2,agent-3`\n"
                "  `/agentmail-share --all --agents agent-2`\n\n"
                "先使用 `/agentmail-contacts` 查看联系人 ID"
            )

        data = _get_agent_storage(agent_id)
        contacts = data.get("contacts", [])

        if not contacts:
            return "**AgentMail**: 当前没有联系人可共享。"

        if share_all:
            target_contacts = contacts
        else:
            if not contacts_arg:
                return "**AgentMail**: 请指定要共享的联系人 ID，或使用 `--all` 共享所有联系人。"

            try:
                contact_ids = [int(x.strip()) for x in contacts_arg.split(",") if x.strip()]
            except ValueError:
                return "**AgentMail**: 联系人 ID 必须是数字，多个 ID 用逗号分隔。"

            target_contacts = [c for c in contacts if c.get("id") in contact_ids]

        if not target_contacts:
            return "**AgentMail**: 没有找到指定的联系人。"

        target_agent_ids = [x.strip() for x in agents_arg.split(",") if x.strip()]

        all_agents = _get_all_agents()
        valid_agent_ids = [a["id"] for a in all_agents]
        invalid_agents = [a for a in target_agent_ids if a not in valid_agent_ids]

        if invalid_agents:
            return (
                f"**AgentMail**: 以下 Agent 不存在: {', '.join(invalid_agents)}\n\n"
                f"可用 Agent: {', '.join(valid_agent_ids) if valid_agent_ids else '无'}"
            )

        shared_count = 0
        for contact in target_contacts:
            shared = contact.get("shared_with", "[]")
            try:
                shared_list = json.loads(shared) if isinstance(shared, str) else shared
                if not isinstance(shared_list, list):
                    shared_list = []
            except Exception:
                shared_list = []

            shared_list.extend(target_agent_ids)
            shared_list = list(dict.fromkeys(shared_list))
            contact["shared_with"] = json.dumps(shared_list)
            shared_count += 1

        if _save_agent_storage(agent_id, data):
            return (
                f"**AgentMail**: 成功共享 **{shared_count}** 个联系人到 **{len(target_agent_ids)}** 个 Agent。\n\n"
                f"目标 Agent: {', '.join(target_agent_ids)}\n"
                f"共享联系人: {', '.join([c.get('name', f'ID:{c.get('id')}') for c in target_contacts])}"
            )
        else:
            return "**AgentMail**: 共享失败，无法保存数据。"


class ListInboxCommand:
    """Handler for /agentmail-inbox command.

    Usage:
        /agentmail-inbox              # 列出收件箱邮件
        /agentmail-inbox --page 2     # 分页查看
        /agentmail-inbox --unread     # 仅显示未读
    """

    command_name = "/agentmail-inbox"

    async def handle(self, context) -> str:
        agent_id = getattr(context, "agent_id", "default")
        args = getattr(context, "args", {})

        page = int(args.get("page", 1))
        unread_only = args.get("unread", False)

        res = _api_get(f"/{agent_id}/inbox?page={page}&page_size=10", agent_id)
        if res.get("success"):
            inbox = res.get("items", [])
            total = res.get("total", 0)
        else:
            data = _get_agent_storage(agent_id)
            inbox = data.get("inbox", [])
            total = len(inbox)

        if not inbox:
            return "**AgentMail**: 收件箱为空。使用 `/agentmail-sync` 同步邮件。"

        filtered = inbox
        if unread_only:
            filtered = [e for e in filtered if not e.get("is_read")]

        if not filtered:
            return "**AgentMail**: 没有未读邮件。"

        lines = [f"**AgentMail 收件箱** ({total} 封，第 {page} 页)", ""]
        for i, email in enumerate(filtered, 1):
            status = "📧" if not email.get("is_read") else "✓"
            lines.append(
                f"{status} **{email.get('subject', '无主题')}** "
                f"来自: {email.get('sender_email', '未知')} "
                f"[ID: {email.get('id')}] "
                f"({email.get('date', '')})"
            )

        total_pages = max(1, (total + 9) // 10)
        if total_pages > 1:
            lines.append(f"\n第 {page}/{total_pages} 页，使用 `--page N` 查看更多")

        lines.append("\n---")
        lines.append("查看详情: `/agentmail-read --id ID`")
        lines.append("同步邮件: `/agentmail-sync`")

        return "\n".join(lines)


class ListSentCommand:
    """Handler for /agentmail-sent command.

    Usage:
        /agentmail-sent               # 列出已发送邮件
        /agentmail-sent --page 2      # 分页查看
    """

    command_name = "/agentmail-sent"

    async def handle(self, context) -> str:
        agent_id = getattr(context, "agent_id", "default")
        args = getattr(context, "args", {})

        page = int(args.get("page", 1))

        res = _api_get(f"/{agent_id}/sent?page={page}&page_size=10", agent_id)
        if res.get("success"):
            sent = res.get("items", [])
            total = res.get("total", 0)
        else:
            data = _get_agent_storage(agent_id)
            sent = data.get("sent", [])
            total = len(sent)

        if not sent:
            return "**AgentMail**: 已发送邮件为空。"

        lines = [f"**AgentMail 已发送** ({total} 封，第 {page} 页)", ""]
        for i, email in enumerate(sent, 1):
            lines.append(
                f"✓ **{email.get('subject', '无主题')}** "
                f"收件人: {email.get('recipient', email.get('to_email', '未知'))} "
                f"[ID: {email.get('id')}] "
                f"({email.get('sent_at', email.get('date', ''))})"
            )

        total_pages = max(1, (total + 9) // 10)
        if total_pages > 1:
            lines.append(f"\n第 {page}/{total_pages} 页，使用 `--page N` 查看更多")

        return "\n".join(lines)


class ListDraftsCommand:
    """Handler for /agentmail-drafts command.

    Usage:
        /agentmail-drafts             # 列出草稿
        /agentmail-drafts --page 2    # 分页查看
    """

    command_name = "/agentmail-drafts"

    async def handle(self, context) -> str:
        agent_id = getattr(context, "agent_id", "default")
        args = getattr(context, "args", {})

        page = int(args.get("page", 1))

        res = _api_get(f"/{agent_id}/drafts?page={page}&page_size=10", agent_id)
        if res.get("success"):
            drafts = res.get("items", [])
            total = res.get("total", 0)
        else:
            data = _get_agent_storage(agent_id)
            drafts = data.get("drafts", [])
            total = len(drafts)

        if not drafts:
            return "**AgentMail**: 草稿箱为空。"

        lines = [f"**AgentMail 草稿箱** ({total} 封，第 {page} 页)", ""]
        for i, draft in enumerate(drafts, 1):
            lines.append(
                f"📝 **{draft.get('subject', '无主题')}** "
                f"收件人: {draft.get('recipient', draft.get('to_email', '未指定'))} "
                f"[ID: {draft.get('id')}] "
                f"({draft.get('updated_at', '')})"
            )

        total_pages = max(1, (total + 9) // 10)
        if total_pages > 1:
            lines.append(f"\n第 {page}/{total_pages} 页，使用 `--page N` 查看更多")

        lines.append("\n---")
        lines.append("使用 `/agentmail-send --to ... --subject ...` 写新邮件")

        return "\n".join(lines)


class ListTrashCommand:
    """Handler for /agentmail-trash command.

    Usage:
        /agentmail-trash              # 列出回收站
        /agentmail-trash --page 2     # 分页查看
        /agentmail-trash --restore 1,2,3  # 恢复邮件
        /agentmail-trash --delete 1,2,3   # 永久删除
    """

    command_name = "/agentmail-trash"

    async def handle(self, context) -> str:
        agent_id = getattr(context, "agent_id", "default")
        args = getattr(context, "args", {})

        page = int(args.get("page", 1))
        restore_ids = args.get("restore", "")
        delete_ids = args.get("delete", "")

        data = _get_agent_storage(agent_id)
        trash = data.get("trash", [])

        if restore_ids:
            try:
                ids = [int(x.strip()) for x in restore_ids.split(",") if x.strip()]
            except ValueError:
                return "**AgentMail**: ID 必须是数字。"

            restored = [t for t in trash if t.get("id") in ids]
            data["trash"] = [t for t in trash if t.get("id") not in ids]

            for item in restored:
                item_type = item.get("item_type", "inbox")
                if item_type == "inbox":
                    data["inbox"].append({**item, "id": item.get("original_id", item["id"])})
                elif item_type == "sent":
                    data["sent"].append({**item, "id": item.get("original_id", item["id"])})
                elif item_type == "drafts":
                    data["drafts"].append({**item, "id": item.get("original_id", item["id"])})
                elif item_type == "contact":
                    data["contacts"].append({**item, "id": item.get("original_id", item["id"])})

            _save_agent_storage(agent_id, data)
            return f"**AgentMail**: 成功恢复 {len(restored)} 个项目。"

        if delete_ids:
            try:
                ids = [int(x.strip()) for x in delete_ids.split(",") if x.strip()]
            except ValueError:
                return "**AgentMail**: ID 必须是数字。"

            data["trash"] = [t for t in trash if t.get("id") not in ids]
            _save_agent_storage(agent_id, data)
            return f"**AgentMail**: 成功永久删除 {len(ids)} 个项目。"

        if not trash:
            return "**AgentMail**: 回收站为空。"

        page_size = 10
        start = (page - 1) * page_size
        end = start + page_size
        page_items = trash[start:end]

        lines = [f"**AgentMail 回收站** ({len(trash)} 项，第 {page} 页)", ""]
        for i, item in enumerate(page_items, start + 1):
            item_type = item.get("item_type", "unknown")
            type_icon = {"inbox": "📧", "sent": "✓", "drafts": "📝", "contact": "👤"}.get(item_type, "❓")
            lines.append(
                f"{type_icon} **[{item_type}]** {item.get('subject', item.get('name', '未知'))} "
                f"[ID: {item.get('id')}] "
                f"({item.get('deleted_at', '')})"
            )

        total_pages = (len(trash) + page_size - 1) // page_size
        if total_pages > 1:
            lines.append(f"\n第 {page}/{total_pages} 页")

        lines.append("\n---")
        lines.append("恢复: `/agentmail-trash --restore ID1,ID2`")
        lines.append("永久删除: `/agentmail-trash --delete ID1,ID2`")

        return "\n".join(lines)


class BackupCommand:
    """Handler for /agentmail-backup command.

    Usage:
        /agentmail-backup             # 创建备份
        /agentmail-backup --list      # 列出备份
    """

    command_name = "/agentmail-backup"

    async def handle(self, context) -> str:
        agent_id = getattr(context, "agent_id", "default")
        args = getattr(context, "args", {})

        list_mode = args.get("list", False)

        backups_key = f"{STORAGE_KEY}_{agent_id}_backups"
        backups_path = _get_agent_mail_file(agent_id, f"{backups_key}.json")

        if list_mode:
            if backups_path.exists():
                try:
                    with open(backups_path, "r", encoding="utf-8") as f:
                        backups = json.load(f)
                except Exception:
                    backups = []
            else:
                backups = []

            if not backups:
                return "**AgentMail**: 暂无备份记录。"

            lines = [f"**AgentMail 备份列表** ({len(backups)} 个)", ""]
            for i, backup in enumerate(backups[-10:], 1):
                lines.append(
                    f"{i}. **{backup.get('time', '未知时间')}** "
                    f"联系人: {backup.get('contacts_count', 0)} 个, "
                    f"邮件: {backup.get('emails_count', 0)} 封"
                )

            return "\n".join(lines)

        data = _get_agent_storage(agent_id)
        backup = {
            "time": __import__("datetime").datetime.now().isoformat(),
            "contacts_count": len(data.get("contacts", [])),
            "emails_count": len(data.get("inbox", [])) + len(data.get("sent", [])),
            "data": data,
        }

        backups = []
        if backups_path.exists():
            try:
                with open(backups_path, "r", encoding="utf-8") as f:
                    backups = json.load(f)
            except Exception:
                backups = []

        backups.append(backup)
        if len(backups) > 10:
            backups = backups[-10:]

        try:
            backups_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            with open(backups_path, "w", encoding="utf-8") as f:
                json.dump(backups, f, ensure_ascii=False, indent=2)
            os.chmod(backups_path, 0o755)
            return (
                f"**AgentMail**: 备份创建成功！\n\n"
                f"时间: {backup['time']}\n"
                f"联系人: {backup['contacts_count']} 个\n"
                f"邮件: {backup['emails_count']} 封"
            )
        except Exception as e:
            return f"**AgentMail**: 备份失败: {e}"


class ConfigCommand:
    """Handler for /agentmail-config command.

    Usage:
        /agentmail-config                               # 查看当前配置
        /agentmail-config --set provider=163 email=xxx@163.com smtp_host=smtp.163.com smtp_port=25 smtp_username=xxx smtp_password=xxx imap_host=imap.163.com imap_port=993 imap_username=xxx imap_password=xxx
        /agentmail-config --delete                      # 删除配置
    """

    command_name = "/agentmail-config"

    async def handle(self, context) -> str:
        agent_id = getattr(context, "agent_id", "default")
        args = getattr(context, "args", {})

        set_args = args.get("set", "")
        delete = args.get("delete", False)

        if delete:
            res = _api_delete(f"/config/{agent_id}", agent_id)
            if res.get("success"):
                return "**AgentMail**: 配置已删除。"
            return f"**AgentMail**: 删除失败: {res.get('error', '未知错误')}"

        if set_args:
            config = {}
            for pair in set_args.split():
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    config[key] = value

            smtp = {}
            imap = {}
            for key, value in list(config.items()):
                if key.startswith("smtp_"):
                    smtp[key[5:]] = value
                    del config[key]
                elif key.startswith("imap_"):
                    imap[key[5:]] = value
                    del config[key]

            if smtp:
                if "port" in smtp:
                    smtp["port"] = int(smtp["port"])
                smtp.setdefault("use_tls", True)
                config["smtp"] = smtp
            if imap:
                if "port" in imap:
                    imap["port"] = int(imap["port"])
                imap.setdefault("use_ssl", True)
                config["imap"] = imap

            config.setdefault("receive_protocol", "imap")

            res = _api_post(f"/config/{agent_id}", config, agent_id)
            if res.get("success"):
                return (
                    f"**AgentMail**: 配置保存成功！\n\n"
                    f"邮箱: {config.get('email', '未设置')}\n"
                    f"提供商: {config.get('provider', 'custom')}\n"
                    f"协议: {config.get('receive_protocol', 'imap').upper()}"
                )
            return f"**AgentMail**: 配置保存失败: {res.get('error', '未知错误')}"

        res = _api_get(f"/config/{agent_id}", agent_id)
        config = res.get("config") if res.get("success") else None

        if not config:
            return (
                "**AgentMail**: 当前未配置邮箱。\n\n"
                "配置方法:\n"
                "```\n"
                "/agentmail-config --set provider=163 email=xxx@163.com smtp_host=smtp.163.com smtp_port=25 smtp_username=xxx smtp_password=xxx imap_host=imap.163.com imap_port=993 imap_username=xxx imap_password=xxx\n"
                "```\n\n"
                "删除配置: `/agentmail-config --delete`"
            )

        lines = ["**AgentMail 当前配置**", ""]
        lines.append(f"邮箱: **{config.get('email', '未设置')}**")
        lines.append(f"提供商: {config.get('provider', 'custom')}")
        lines.append(f"显示名: {config.get('display_name', '未设置')}")
        lines.append(f"接收协议: {config.get('receive_protocol', 'imap').upper()}")

        smtp = config.get("smtp", {})
        if smtp:
            lines.append(f"\n**SMTP**: {smtp.get('host', '')}:{smtp.get('port', '')} (TLS: {'是' if smtp.get('use_tls') else '否'})")

        imap = config.get("imap", {})
        if imap:
            lines.append(f"**IMAP**: {imap.get('host', '')}:{imap.get('port', '')} (SSL: {'是' if imap.get('use_ssl') else '否'})")

        lines.append("\n---")
        lines.append("修改配置: `/agentmail-config --set key=value ...`")
        lines.append("删除配置: `/agentmail-config --delete`")

        return "\n".join(lines)


class SendEmailCommand:
    """Handler for /agentmail-send command.

    Usage:
        /agentmail-send --to user@example.com --subject "Hello" --body "Content"
        /agentmail-send --to user@example.com --subject "Hello" --body-file /path/to/content.txt
    """

    command_name = "/agentmail-send"

    async def handle(self, context) -> str:
        agent_id = getattr(context, "agent_id", "default")
        args = getattr(context, "args", {})

        to_email = args.get("to", "")
        subject = args.get("subject", "")
        body = args.get("body", "")
        body_file = args.get("body-file", "")

        if not to_email or not subject:
            return (
                "**AgentMail**: 请提供收件人和主题。\n\n"
                "用法:\n"
                "  `/agentmail-send --to user@example.com --subject \"Hello\" --body \"Content\"`\n"
                "  `/agentmail-send --to user@example.com --subject \"Hello\" --body-file /path/to/file.txt`"
            )

        if body_file:
            try:
                path = Path(body_file).resolve()
                if ".." in body_file:
                    return "**AgentMail**: 无效的文件路径，禁止使用相对路径跳转。"
                cwd = Path.cwd().resolve()
                if not str(path).startswith(str(cwd) + os.sep):
                    return "**AgentMail**: 文件必须在当前工作目录内。"
                if path.exists() and path.is_file():
                    body = path.read_text(encoding="utf-8")
                else:
                    return f"**AgentMail**: 文件不存在: {body_file}"
            except Exception as e:
                return f"**AgentMail**: 读取文件失败: {e}"

        res = _api_post(f"/{agent_id}/send", {
            "to_email": to_email,
            "subject": subject,
            "body": body,
        }, agent_id)

        if res.get("success"):
            return (
                f"**AgentMail**: 邮件发送成功！\n\n"
                f"收件人: {to_email}\n"
                f"主题: {subject}"
            )
        return f"**AgentMail**: 发送失败: {res.get('error', '未知错误')}"


class ReadEmailCommand:
    """Handler for /agentmail-read command.

    Usage:
        /agentmail-read --id 123           # 读取指定邮件
        /agentmail-read --id 123 --action context  # 添加到上下文
        /agentmail-read --id 123 --action memory   # 添加到记忆
    """

    command_name = "/agentmail-read"

    async def handle(self, context) -> str:
        agent_id = getattr(context, "agent_id", "default")
        args = getattr(context, "args", {})

        email_id = args.get("id", "")
        action = args.get("action", "")

        if not email_id:
            return "**AgentMail**: 请指定邮件 ID。用法: `/agentmail-read --id 123`"

        try:
            email_id = int(email_id)
        except ValueError:
            return "**AgentMail**: ID 必须是数字。"

        data = _get_agent_storage(agent_id)

        email = None
        for e in data.get("inbox", []):
            if e.get("id") == email_id:
                email = e
                break
        if not email:
            for e in data.get("sent", []):
                if e.get("id") == email_id:
                    email = e
                    break
        if not email:
            for e in data.get("drafts", []):
                if e.get("id") == email_id:
                    email = e
                    break

        if not email:
            return f"**AgentMail**: 找不到 ID 为 {email_id} 的邮件。"

        if action == "context":
            email_context = (
                f"[Email Context]\n"
                f"From: {email.get('sender_email', email.get('from_email', '未知'))}\n"
                f"Subject: {email.get('subject', '无主题')}\n"
                f"Date: {email.get('date', '')}\n"
                f"Content: {email.get('body', '')[:1000]}\n"
                f"[/Email Context]\n\n"
                f"请帮我分析这封邮件。"
            )
            return (
                f"**AgentMail**: 已添加到上下文！\n\n"
                f"邮件: {email.get('subject', '无主题')}\n"
                f"请将以下内容发送给 Agent:\n\n"
                f"```\n{email_context}\n```"
            )

        if action == "memory":
            memory_key = f"agentmail_memory_{agent_id}"
            memory_path = _get_agent_mail_file(agent_id, f"{memory_key}.json")

            memories = []
            if memory_path.exists():
                try:
                    with open(memory_path, "r", encoding="utf-8") as f:
                        memories = json.load(f)
                except Exception:
                    memories = []

            memory = {
                "type": "email_memory",
                "emailId": email_id,
                "subject": email.get("subject", ""),
                "sender": email.get("sender_email", email.get("from_email", "")),
                "summary": email.get("body", "")[:200],
                "tags": ["important"],
                "priority": 3,
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }
            memories.append(memory)
            if len(memories) > 100:
                memories = memories[-100:]

            try:
                memory_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                with open(memory_path, "w", encoding="utf-8") as f:
                    json.dump(memories, f, ensure_ascii=False, indent=2)
                os.chmod(memory_path, 0o755)
                return f"**AgentMail**: 已添加到记忆！\n\n邮件: {email.get('subject', '无主题')}"
            except Exception as e:
                return f"**AgentMail**: 添加记忆失败: {e}"

        lines = [
            f"**邮件详情** [ID: {email_id}]",
            "",
            f"**主题**: {email.get('subject', '无主题')}",
            f"**发件人**: {email.get('sender_email', email.get('from_email', '未知'))}",
            f"**收件人**: {email.get('to_email', '未指定')}",
            f"**日期**: {email.get('date', '')}",
            f"**状态**: {'未读' if not email.get('is_read') else '已读'}",
            "",
            "**内容**:",
            "```",
            email.get("body", "无内容")[:2000],
            "```",
            "",
            "---",
            "添加到上下文: `/agentmail-read --id {id} --action context`",
            "添加到记忆: `/agentmail-read --id {id} --action memory`",
        ]

        return "\n".join(lines)


class SyncInboxCommand:
    """Handler for /agentmail-sync command.

    Usage:
        /agentmail-sync               # 同步收件箱（从IMAP/POP3服务器拉取）
        /agentmail-sync --max 100      # 最大同步邮件数
    """

    command_name = "/agentmail-sync"

    async def handle(self, context) -> str:
        agent_id = getattr(context, "agent_id", "default")
        args = getattr(context, "args", {})

        max_emails = int(args.get("max", 50))

        res = _api_post(f"/{agent_id}/sync?max_emails={max_emails}", {}, agent_id)

        if res.get("success"):
            return (
                f"**AgentMail**: 邮件同步完成！\n\n"
                f"服务器邮件数: {res.get('total_on_server', 0)}\n"
                f"新同步: {res.get('synced', 0)} 封\n"
                f"跳过(已存在): {res.get('skipped', 0)} 封"
            )
        return f"**AgentMail**: 同步失败: {res.get('error', '未知错误')}\n\n请先使用 `/agentmail-config` 配置邮箱。"


class ListenCommand:
    """Handler for /agentmail-listen command.

    Usage:
        /agentmail-listen             # 查看监听状态
        /agentmail-listen --start     # 启动 IMAP IDLE 实时监听
        /agentmail-listen --stop      # 停止监听
    """

    command_name = "/agentmail-listen"

    async def handle(self, context) -> str:
        agent_id = getattr(context, "agent_id", "default")
        args = getattr(context, "args", {})

        start = args.get("start", False)
        stop = args.get("stop", False)

        if start:
            res = _api_post(f"/{agent_id}/listen/start", {}, agent_id)
            if res.get("success"):
                return (
                    f"**AgentMail**: IMAP IDLE 监听已启动！\n\n"
                    f"新邮件到达时将自动保存到收件箱并通知 Agent。\n"
                    f"无需轮询，节省资源。"
                )
            return f"**AgentMail**: 启动监听失败: {res.get('error', '未知错误')}\n\n请先使用 `/agentmail-config` 配置 IMAP 邮箱。"

        if stop:
            res = _api_post(f"/{agent_id}/listen/stop", {}, agent_id)
            if res.get("success"):
                return "**AgentMail**: IMAP IDLE 监听已停止。"
            return f"**AgentMail**: 停止监听失败: {res.get('error', '未知错误')}"

        res = _api_get(f"/{agent_id}/listen/status", agent_id)
        if res.get("listening"):
            return (
                f"**AgentMail IMAP IDLE 监听状态**\n\n"
                f"状态: 🟢 监听中\n"
                f"邮箱: {res.get('email', '未知')}\n\n"
                f"停止监听: `/agentmail-listen --stop`"
            )
        else:
            return (
                f"**AgentMail IMAP IDLE 监听状态**\n\n"
                f"状态: ⚪ 未监听\n\n"
                f"启动监听: `/agentmail-listen --start`\n"
                f"（需要先配置 IMAP 邮箱）"
            )


ALL_COMMANDS = [
    ListContactsCommand,
    ShareContactsCommand,
    ListInboxCommand,
    ListSentCommand,
    ListDraftsCommand,
    ListTrashCommand,
    BackupCommand,
    ConfigCommand,
    SendEmailCommand,
    ReadEmailCommand,
    SyncInboxCommand,
    ListenCommand,
]
