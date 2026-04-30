# -*- coding: utf-8 -*-
"""
AgentMail.to Webhook 处理
"""

from fastapi import APIRouter, Request
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/agentmail", tags=["AgentMail Webhook"])


@router.post("/{agent_id}")
async def receive_agentmail_webhook(agent_id: str, request: Request):
    """接收 AgentMail.to 的邮件推送"""
    try:
        data = await request.json()
        logger.info(f"收到 AgentMail Webhook: agent_id={agent_id}")
        
        email_id = data.get("email_id")
        subject = data.get("subject")
        sender = data.get("from")
        
        logger.info(f"新邮件: {subject} from {sender}")
        
        return {"success": True, "message": "Webhook 处理成功"}
    except Exception as e:
        logger.error(f"Webhook 处理失败: {e}")
        return {"success": False, "error": str(e)}
