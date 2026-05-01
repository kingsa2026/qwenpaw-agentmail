# -*- coding: utf-8 -*-
"""
AgentMail.to Webhook 处理

支持 Webhook 签名验证，通过环境变量 AGENTMAIL_WEBHOOK_SECRET 配置密钥
"""

from fastapi import APIRouter, Request, HTTPException
import logging
import os
import hmac
import hashlib

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/agentmail", tags=["AgentMail Webhook"])

# Webhook 密钥（生产环境应通过环境变量配置）
_WEBHOOK_SECRET = os.environ.get("AGENTMAIL_WEBHOOK_SECRET", "")


def _verify_webhook_signature(body: bytes, signature: str) -> bool:
    """验证 Webhook 签名"""
    if not _WEBHOOK_SECRET:
        # 未配置密钥时跳过验证（仅开发环境）
        logger.warning("Webhook 密钥未配置，跳过签名验证")
        return True
    if not signature:
        return False
    expected = hmac.new(
        _WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    # 支持 'sha256=' 前缀
    if signature.startswith("sha256="):
        signature = signature[7:]
    return hmac.compare_digest(expected, signature)


@router.post("/{agent_id}")
async def receive_agentmail_webhook(agent_id: str, request: Request):
    """接收 AgentMail.to 的邮件推送（带签名验证）"""
    body = await request.body()

    # 验证签名
    signature = request.headers.get("X-Webhook-Signature", "")
    if not _verify_webhook_signature(body, signature):
        logger.warning(f"Webhook 签名验证失败: agent_id={agent_id}")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        import json
        data = json.loads(body)
        logger.info(f"收到 AgentMail Webhook: agent_id={agent_id}")

        email_id = data.get("email_id")
        subject = data.get("subject")
        sender = data.get("from")

        logger.info(f"新邮件: {subject} from {sender}")

        return {"success": True, "message": "Webhook 处理成功"}
    except Exception as e:
        logger.error(f"Webhook 处理失败: {e}")
        return {"success": False, "error": str(e)}
