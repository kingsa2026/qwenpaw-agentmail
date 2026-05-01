# -*- coding: utf-8 -*-
"""
AgentMail CLI 命令处理器

提供完整的 CLI 接口，覆盖 UI 所有功能：
  联系人管理：/agentmail-contacts, /agentmail-share
  邮件管理：/agentmail-inbox, /agentmail-sent, /agentmail-drafts
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


def _get_agent_storage(agent_id: str) -> Dict[str, Any]:
    """获取指定 Agent 的本地存储数据"""
    storage_key = f"{STORAGE_KEY}_{agent_id}"
    storage_path = Path.home() / ".qwenpaw" / "agentmail" / f"{storage_key}.json"

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
    """保存指定 Agent 的本地存储数据"""
    storage_key = f"{STORAGE_KEY}_{agent_id}"
    storage_path = Path.home() / ".qwenpaw" / "agentmail" / f"{storage_key}.json"

    try:
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except (OSError, TypeError) as e:
        logger.error(f"保存存储失败: {e}")
        return False


def _get_all_agents() -> List[Dict[str, str]]:
    """获取所有 Agent 列表"""
    agents = []

    # 1. 尝试从 QwenPaw 新版 zustand store 读取
    try:
        import os
        storage_data = os.environ.get("QWENPAW_AGENT_STORAGE")
        if not storage_data:
            storage_path = Path.home() / ".qwenpaw" / "agent_storage.json"
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

    # 2. 尝试从旧版存储读取
    if not agents:
        try:
            storage_path = Path.home() / ".qwenpaw" / "agents.json"
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
            except:
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
            except:
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
        search = args.get("search", "")

        data = _get_agent_storage(agent_id)
        inbox = data.get("inbox", [])

        if not inbox:
            return "**AgentMail**: 收件箱为空。"

        filtered = inbox
        if unread_only:
            filtered = [e for e in filtered if not e.get("is_read")]
        if search:
            search_lower = search.lower()
            filtered = [
                e for e in filtered
                if search_lower in e.get("subject", "").lower()
                or search_lower in e.get("sender_email", "").lower()
            ]

        if not filtered:
            return "**AgentMail**: 没有找到匹配的邮件。"

        page_size = 10
        start = (page - 1) * page_size
        end = start + page_size
        page_items = filtered[start:end]

        lines = [f"**AgentMail 收件箱** ({len(filtered)} 封，第 {page} 页)", ""]
        for i, email in enumerate(page_items, start + 1):
            status = "📧" if not email.get("is_read") else "✓"
            lines.append(
                f"{status} **{email.get('subject', '无主题')}** "
                f"来自: {email.get('sender_email', '未知')} "
                f"[ID: {email.get('id')}] "
                f"({email.get('date', '')})"
            )

        total_pages = (len(filtered) + page_size - 1) // page_size
        if total_pages > 1:
            lines.append(f"\n第 {page}/{total_pages} 页，使用 `--page N` 查看更多")

        lines.append("\n---")
        lines.append("使用 `/agentmail-read --id ID` 查看邮件详情")

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
        search = args.get("search", "")

        data = _get_agent_storage(agent_id)
        sent = data.get("sent", [])

        if not sent:
            return "**AgentMail**: 已发送邮件为空。"

        filtered = sent
        if search:
            search_lower = search.lower()
            filtered = [
                e for e in filtered
                if search_lower in e.get("subject", "").lower()
                or search_lower in e.get("to_email", "").lower()
            ]

        page_size = 10
        start = (page - 1) * page_size
        end = start + page_size
        page_items = filtered[start:end]

        lines = [f"**AgentMail 已发送** ({len(filtered)} 封，第 {page} 页)", ""]
        for i, email in enumerate(page_items, start + 1):
            lines.append(
                f"✓ **{email.get('subject', '无主题')}** "
                f"收件人: {email.get('to_email', '未知')} "
                f"[ID: {email.get('id')}] "
                f"({email.get('date', '')})"
            )

        total_pages = (len(filtered) + page_size - 1) // page_size
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

        data = _get_agent_storage(agent_id)
        drafts = data.get("drafts", [])

        if not drafts:
            return "**AgentMail**: 草稿箱为空。"

        page_size = 10
        start = (page - 1) * page_size
        end = start + page_size
        page_items = drafts[start:end]

        lines = [f"**AgentMail 草稿箱** ({len(drafts)} 封，第 {page} 页)", ""]
        for i, draft in enumerate(page_items, start + 1):
            lines.append(
                f"📝 **{draft.get('subject', '无主题')}** "
                f"收件人: {draft.get('to_email', '未指定')} "
                f"[ID: {draft.get('id')}] "
                f"({draft.get('updated_at', '')})"
            )

        total_pages = (len(drafts) + page_size - 1) // page_size
        if total_pages > 1:
            lines.append(f"\n第 {page}/{total_pages} 页，使用 `--page N` 查看更多")

        lines.append("\n---")
        lines.append("使用 `/agentmail-compose --to ... --subject ...` 写新邮件")

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
        backups_path = Path.home() / ".qwenpaw" / "agentmail" / f"{backups_key}.json"

        if list_mode:
            if backups_path.exists():
                try:
                    with open(backups_path, "r", encoding="utf-8") as f:
                        backups = json.load(f)
                except:
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

        # 创建备份
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
            except:
                backups = []

        backups.append(backup)
        if len(backups) > 10:
            backups = backups[-10:]

        try:
            backups_path.parent.mkdir(parents=True, exist_ok=True)
            with open(backups_path, "w", encoding="utf-8") as f:
                json.dump(backups, f, ensure_ascii=False, indent=2)
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
        /agentmail-config             # 查看当前配置
        /agentmail-config --set-mode hybrid|traditional|agentmail
    """

    command_name = "/agentmail-config"

    async def handle(self, context) -> str:
        agent_id = getattr(context, "agent_id", "default")
        args = getattr(context, "args", {})

        set_mode = args.get("set-mode", "")

        data = _get_agent_storage(agent_id)
        config = data.get("config", {})

        if set_mode:
            if set_mode not in ["hybrid", "traditional", "agentmail", "none"]:
                return (
                    "**AgentMail**: 无效的模式。可用模式:\n"
                    "  - `hybrid` - 混合模式（传统邮箱 + AgentMail.to）\n"
                    "  - `traditional` - 传统邮箱（SMTP/POP3/IMAP）\n"
                    "  - `agentmail` - AgentMail.to 服务\n"
                    "  - `none` - 未配置"
                )

            if not config:
                config = {}
            config["mode"] = set_mode
            if set_mode == "hybrid":
                config["hybrid"] = config.get("hybrid", {"email": "", "password": ""})
            data["config"] = config
            _save_agent_storage(agent_id, data)
            return f"**AgentMail**: 已切换到 **{set_mode}** 模式。"

        if not config:
            return (
                "**AgentMail**: 当前未配置邮箱。\n\n"
                "可用命令:\n"
                "  `/agentmail-config --set-mode hybrid` - 混合模式\n"
                "  `/agentmail-config --set-mode traditional` - 传统邮箱\n"
                "  `/agentmail-config --set-mode agentmail` - AgentMail.to"
            )

        mode = config.get("mode", "none")
        lines = ["**AgentMail 当前配置**", ""]
        lines.append(f"模式: **{mode}**")

        if mode == "hybrid" and config.get("hybrid"):
            hybrid = config["hybrid"]
            lines.append(f"邮箱: {hybrid.get('email', '未设置')}")
            lines.append(f"提供商: {hybrid.get('provider', '未设置')}")
        elif mode == "traditional" and config.get("traditional"):
            trad = config["traditional"]
            lines.append(f"SMTP: {trad.get('smtp_host', '未设置')}:{trad.get('smtp_port', '')}")
            lines.append(f"IMAP: {trad.get('imap_host', '未设置')}:{trad.get('imap_port', '')}")
        elif mode == "agentmail" and config.get("agentmail"):
            am = config["agentmail"]
            lines.append(f"API Key: {'已设置' if am.get('api_key') else '未设置'}")

        lines.append("\n---")
        lines.append("切换模式: `/agentmail-config --set-mode MODE`")

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
                # 防止路径遍历：禁止包含 .. 的相对路径
                if ".." in body_file:
                    return "**AgentMail**: 无效的文件路径，禁止使用相对路径跳转。"
                # 只允许读取当前工作目录下的文件
                cwd = Path.cwd().resolve()
                if not str(path).startswith(str(cwd) + os.sep):
                    return "**AgentMail**: 文件必须在当前工作目录内。"
                if path.exists() and path.is_file():
                    body = path.read_text(encoding="utf-8")
                else:
                    return f"**AgentMail**: 文件不存在: {body_file}"
            except Exception as e:
                return f"**AgentMail**: 读取文件失败: {e}"

        data = _get_agent_storage(agent_id)
        if "sent" not in data:
            data["sent"] = []

        new_email = {
            "id": max([e.get("id", 0) for e in data["sent"]] + [0]) + 1,
            "to_email": to_email,
            "subject": subject,
            "body": body,
            "date": __import__("datetime").datetime.now().isoformat(),
            "status": "sent",
        }
        data["sent"].append(new_email)

        if _save_agent_storage(agent_id, data):
            return (
                f"**AgentMail**: 邮件发送成功！\n\n"
                f"收件人: {to_email}\n"
                f"主题: {subject}\n"
                f"[ID: {new_email['id']}]"
            )
        else:
            return "**AgentMail**: 发送失败，无法保存数据。"


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

        # 在所有邮件中查找
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
            # 添加到上下文（sessionStorage）
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
            # 添加到记忆（localStorage）
            memory_key = f"agentmail_memory_{agent_id}"
            memory_path = Path.home() / ".qwenpaw" / "agentmail" / f"{memory_key}.json"

            memories = []
            if memory_path.exists():
                try:
                    with open(memory_path, "r", encoding="utf-8") as f:
                        memories = json.load(f)
                except:
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
                memory_path.parent.mkdir(parents=True, exist_ok=True)
                with open(memory_path, "w", encoding="utf-8") as f:
                    json.dump(memories, f, ensure_ascii=False, indent=2)
                return f"**AgentMail**: 已添加到记忆！\n\n邮件: {email.get('subject', '无主题')}"
            except Exception as e:
                return f"**AgentMail**: 添加记忆失败: {e}"

        # 默认显示邮件详情
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
