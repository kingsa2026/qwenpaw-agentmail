# -*- coding: utf-8 -*-
"""
路由模块
"""

from fastapi import APIRouter

# 创建路由
config_router = APIRouter(prefix="/api/v1/email/config", tags=["配置管理"])
email_router = APIRouter(prefix="/api/v1/emails", tags=["邮件管理"])
notification_router = APIRouter(prefix="/api/v1/notifications", tags=["通知管理"])


# 配置路由
@config_router.get("")
async def get_config():
    """获取邮箱配置"""
    return {
        "mode": "traditional",
        "email": "",
        "smtp_server": "",
        "imap_server": "",
        "port": 587,
        "use_ssl": True,
    }


@config_router.post("")
async def update_config(config: dict):
    """更新邮箱配置"""
    return {"success": True, "message": "配置已更新"}


@config_router.get("/agents")
async def get_agent_configs():
    """获取所有 Agent 的邮箱配置"""
    return {"agents": []}


@config_router.post("/switch")
async def switch_mode(mode: str):
    """切换邮箱模式"""
    return {"success": True, "mode": mode}


@config_router.get("/summary")
async def get_config_summary():
    """获取配置摘要"""
    return {
        "mode": "traditional",
        "connected": False,
        "unread_count": 0,
    }


# 邮件路由
@email_router.get("")
async def get_emails(folder: str = "inbox", limit: int = 20):
    """获取邮件列表"""
    return {
        "folder": folder,
        "emails": [],
        "total": 0,
    }


@email_router.get("/{email_id}")
async def get_email(email_id: str):
    """获取邮件详情"""
    return {"id": email_id, "subject": "", "content": ""}


@email_router.post("/{email_id}/read")
async def mark_as_read(email_id: str):
    """标记邮件为已读"""
    return {"success": True}


@email_router.delete("/{email_id}")
async def delete_email(email_id: str):
    """删除邮件"""
    return {"success": True}


@email_router.post("/send")
async def send_email(email: dict):
    """发送邮件"""
    return {"success": True, "message_id": "12345"}


# 通知路由
@notification_router.get("")
async def get_notifications():
    """获取通知列表"""
    return {"notifications": []}


@notification_router.post("/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    """标记通知为已读"""
    return {"success": True}
