# -*- coding: utf-8 -*-
"""
Webhook 模块
"""

from fastapi import APIRouter

agentmail_webhook = APIRouter(prefix="/webhooks/agentmail", tags=["AgentMail Webhook"])
hybrid_webhook = APIRouter(prefix="/webhooks/hybrid", tags=["Hybrid Webhook"])
