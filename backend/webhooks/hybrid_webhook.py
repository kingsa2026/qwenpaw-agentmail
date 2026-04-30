# -*- coding: utf-8 -*-
"""
Hybrid 模式 Webhook 处理
"""

from fastapi import APIRouter, Request
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/hybrid", tags=["Hybrid Webhook"])


@router.post("/{agent_id}")
async def receive_hybrid_webhook(agent_id: str, request: Request):
    """接收混合模式的邮件推送"""
    try:
        data = await request.json()
        logger.info(f"收到 Hybrid Webhook: agent_id={agent_id}")
        
        email_id = data.get("email_id")
        subject = data.get("subject")
        sender = data.get("from")
        forwarded_from = data.get("forwarded_from", "")
        
        logger.info(f"转发邮件: {subject} from {sender} (原始: {forwarded_from})")
        
        return {"success": True, "message": "Webhook 处理成功"}
    except Exception as e:
        logger.error(f"Webhook 处理失败: {e}")
        return {"success": False, "error": str(e)}
