"""
AgentMail Plugin - API Routes

所有API端点，Agent隔离
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/email", tags=["email"])


# ── Request Models ──────────────────────────────────────────────────────────

class TraditionalConfigRequest(BaseModel):
    provider: str = Field(default="custom", description="邮箱提供商")
    email: str = Field(..., description="邮箱地址")
    display_name: Optional[str] = Field(None, description="显示名称")
    receive_protocol: str = Field(default="imap", description="接收协议: imap/pop3")
    smtp: Dict[str, Any] = Field(..., description="SMTP配置")
    imap: Dict[str, Any] = Field(..., description="IMAP/POP3配置")


class AgentMailConfigRequest(BaseModel):
    api_key: str = Field(..., description="API密钥")
    inbox_id: str = Field(..., description="收件箱ID")
    email: str = Field(..., description="邮箱地址")


class HybridConfigRequest(BaseModel):
    forwarding: bool = Field(default=True, description="启用转发")


class ContactRequest(BaseModel):
    name: str = Field(..., description="姓名")
    phone: Optional[str] = Field(None, description="电话")
    email: str = Field(..., description="邮箱")
    company: Optional[str] = Field(None, description="公司")
    website: Optional[str] = Field(None, description="网站")
    notes: Optional[str] = Field(None, description="备注")
    group_name: str = Field(default="default", description="分组")


class ShareRequest(BaseModel):
    target_agent_ids: List[str] = Field(..., description="目标Agent ID列表")


class BatchIdsRequest(BaseModel):
    ids: List[int] = Field(..., description="ID列表")


class ReplyRequest(BaseModel):
    content: str = Field(..., description="回复内容")


# ── Config API ──────────────────────────────────────────────────────────────

@router.get("/config/{agent_id}")
async def get_config(agent_id: str):
    """获取邮件配置"""
    db = get_db(agent_id)
    config = db.get_config()
    if not config:
        return {"success": True, "config": None}
    return {"success": True, "config": config}


@router.post("/config/{agent_id}/traditional")
async def save_traditional_config(agent_id: str, data: TraditionalConfigRequest):
    """保存传统邮箱配置"""
    db = get_db(agent_id)
    result = db.save_config("traditional", data.dict())
    return {"success": result}


@router.post("/config/{agent_id}/agentmail")
async def save_agentmail_config(agent_id: str, data: AgentMailConfigRequest):
    """保存AgentMail配置"""
    db = get_db(agent_id)
    result = db.save_config("agentmail", data.dict())
    return {"success": result}


@router.post("/config/{agent_id}/hybrid")
async def save_hybrid_config(agent_id: str, data: HybridConfigRequest):
    """保存混合模式配置（仅转发开关）"""
    db = get_db(agent_id)
    # 混合模式只需保存转发开关，实际配置读取traditional和agentmail
    result = db.save_config("hybrid", {
        "forwarding": data.forwarding,
        "default_mode": "traditional"
    })
    return {"success": result}


@router.delete("/config/{agent_id}")
async def delete_config(agent_id: str):
    """删除邮件配置"""
    db = get_db(agent_id)
    result = db.delete_config()
    return {"success": result}


# ── Inbox API ───────────────────────────────────────────────────────────────

@router.get("/{agent_id}/inbox")
async def get_inbox(
    agent_id: str,
    folder: str = Query(default="inbox", description="文件夹: inbox/archive"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100)
):
    """获取收件箱邮件"""
    db = get_db(agent_id)
    result = db.get_inbox(folder=folder, page=page, page_size=page_size)
    return {"success": True, **result}


@router.post("/{agent_id}/inbox/{email_id}/agent-read")
async def mark_agent_read(agent_id: str, email_id: int):
    """标记Agent已读状态"""
    db = get_db(agent_id)
    result = db.mark_agent_read(email_id)
    return {"success": result}


@router.post("/{agent_id}/inbox/{email_id}/reply")
async def mark_replied(agent_id: str, email_id: int, data: ReplyRequest):
    """标记Agent回复状态"""
    db = get_db(agent_id)
    result = db.mark_replied(email_id, data.content)
    return {"success": result}


@router.post("/{agent_id}/inbox/archive")
async def archive_inbox(agent_id: str, data: BatchIdsRequest):
    """归档邮件"""
    db = get_db(agent_id)
    result = db.archive_emails(data.ids)
    return {"success": result}


@router.post("/{agent_id}/inbox/delete")
async def delete_inbox(agent_id: str, data: BatchIdsRequest):
    """删除收件箱邮件（移动到回收站）"""
    db = get_db(agent_id)
    result = db.move_to_trash("inbox", data.ids)
    return {"success": result}


# ── Sent API ────────────────────────────────────────────────────────────────

@router.get("/{agent_id}/sent")
async def get_sent(
    agent_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100)
):
    """获取发件箱"""
    db = get_db(agent_id)
    result = db.get_sent(page=page, page_size=page_size)
    return {"success": True, **result}


# ── Drafts API ──────────────────────────────────────────────────────────────

@router.get("/{agent_id}/drafts")
async def get_drafts(
    agent_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100)
):
    """获取草稿箱"""
    db = get_db(agent_id)
    result = db.get_drafts(page=page, page_size=page_size)
    return {"success": True, **result}


# ── Trash API ───────────────────────────────────────────────────────────────

@router.get("/{agent_id}/trash")
async def get_trash(
    agent_id: str,
    item_type: Optional[str] = Query(default=None, description="类型筛选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100)
):
    """获取回收站"""
    db = get_db(agent_id)
    result = db.get_trash(item_type=item_type, page=page, page_size=page_size)
    return {"success": True, **result}


@router.post("/{agent_id}/trash/restore")
async def restore_trash(agent_id: str, data: BatchIdsRequest):
    """从回收站恢复"""
    db = get_db(agent_id)
    result = db.restore_from_trash(data.ids)
    return {"success": result, "restored": len(data.ids) if result else 0}


@router.delete("/{agent_id}/trash/permanent")
async def permanent_delete(agent_id: str, data: BatchIdsRequest):
    """永久删除"""
    db = get_db(agent_id)
    result = db.permanent_delete(data.ids)
    return {"success": result}


# ── Contacts API ────────────────────────────────────────────────────────────

@router.get("/{agent_id}/contacts")
async def get_contacts(
    agent_id: str,
    group: Optional[str] = Query(default=None, description="分组筛选"),
    search: Optional[str] = Query(default=None, description="搜索关键词"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=15, ge=1, le=100)
):
    """获取联系人列表"""
    db = get_db(agent_id)
    result = db.get_contacts(group=group, search=search, page=page, page_size=page_size)
    return {"success": True, **result}


@router.post("/{agent_id}/contacts")
async def create_contact(agent_id: str, data: ContactRequest):
    """创建联系人"""
    db = get_db(agent_id)
    contact_id = db.create_contact(data.dict())
    return {"success": True, "id": contact_id}


@router.put("/{agent_id}/contacts/{contact_id}")
async def update_contact(agent_id: str, contact_id: int, data: ContactRequest):
    """更新联系人"""
    db = get_db(agent_id)
    result = db.update_contact(contact_id, data.dict())
    return {"success": result}


@router.delete("/{agent_id}/contacts/{contact_id}")
async def delete_contact(agent_id: str, contact_id: int):
    """删除联系人（移动到回收站）"""
    db = get_db(agent_id)
    result = db.delete_contacts([contact_id])
    return {"success": result}


@router.post("/{agent_id}/contacts/batch-delete")
async def batch_delete_contacts(agent_id: str, data: BatchIdsRequest):
    """批量删除联系人"""
    db = get_db(agent_id)
    result = db.delete_contacts(data.ids)
    return {"success": result}


@router.post("/{agent_id}/contacts/{contact_id}/share")
async def share_contact(agent_id: str, contact_id: int, data: ShareRequest):
    """共享联系人"""
    db = get_db(agent_id)
    result = db.share_contact(contact_id, data.target_agent_ids)
    return {"success": result}


@router.post("/{agent_id}/contacts/batch-share")
async def batch_share_contacts(agent_id: str, data: Dict[str, Any]):
    """批量共享联系人"""
    db = get_db(agent_id)
    contact_ids = data.get("contact_ids", [])
    target_agent_ids = data.get("target_agent_ids", [])
    success_count = 0
    for contact_id in contact_ids:
        if db.share_contact(contact_id, target_agent_ids):
            success_count += 1
    return {"success": True, "shared": success_count}


# ── Contact Groups API ──────────────────────────────────────────────────────

@router.get("/{agent_id}/contact-groups")
async def get_contact_groups(agent_id: str):
    """获取联系人分组"""
    db = get_db(agent_id)
    groups = db.get_contact_groups()
    return {"success": True, "items": groups}


@router.post("/{agent_id}/contact-groups")
async def create_contact_group(agent_id: str, data: Dict[str, str]):
    """创建联系人分组"""
    db = get_db(agent_id)
    group_id = db.create_contact_group(data.get("name", ""))
    return {"success": group_id > 0, "id": group_id}


@router.delete("/{agent_id}/contact-groups/{group_id}")
async def delete_contact_group(agent_id: str, group_id: int):
    """删除联系人分组"""
    db = get_db(agent_id)
    result = db.delete_contact_group(group_id)
    return {"success": result}


# ── Uninstall API ───────────────────────────────────────────────────────────

@router.post("/{agent_id}/uninstall")
async def uninstall_plugin(agent_id: str, data: Dict[str, Any]):
    """卸载插件 - 清理数据库和文件"""
    db = get_db(agent_id)
    keep_data = data.get("keep_data", False)
    result = db.uninstall(keep_data=keep_data)
    return {"success": result}
