# -*- coding: utf-8 -*-
"""
AgentMail Plugin - Webhook 处理单元测试

测试范围:
  - agentmail_webhook.receive_agentmail_webhook
  - hybrid_webhook.receive_hybrid_webhook
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from webhooks.agentmail_webhook import router as agentmail_router
from webhooks.hybrid_webhook import router as hybrid_router

# 构造最小 FastAPI 应用挂载两个 webhook router
from fastapi import FastAPI

app = FastAPI()
app.include_router(agentmail_router)
app.include_router(hybrid_router)
client = TestClient(app)


# ── AgentMail Webhook ─────────────────────────────────────────────────────

class TestAgentMailWebhook:
    """测试 /webhooks/agentmail/{agent_id} 端点"""

    def test_receive_webhook_success(self):
        payload = {
            "email_id": "email-123",
            "subject": "Test Subject",
            "from": "sender@example.com",
        }
        resp = client.post("/webhooks/agentmail/agent-1", json=payload)
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert "Webhook 处理成功" in resp.json()["message"]

    def test_receive_webhook_invalid_json(self):
        # Webhook 端点对非 JSON body 会捕获异常并返回 200
        resp = client.post("/webhooks/agentmail/agent-1", data="not-json")
        assert resp.status_code == 200
        assert resp.json()["success"] is False


# ── Hybrid Webhook ────────────────────────────────────────────────────────

class TestHybridWebhook:
    """测试 /webhooks/hybrid/{agent_id} 端点"""

    def test_receive_webhook_success(self):
        payload = {
            "email_id": "email-456",
            "subject": "Forwarded Email",
            "from": "original@example.com",
            "forwarded_from": "forwarder@example.com",
        }
        resp = client.post("/webhooks/hybrid/agent-2", json=payload)
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert "Webhook 处理成功" in resp.json()["message"]

    def test_receive_webhook_missing_fields(self):
        # 缺少可选字段也应成功处理
        payload = {"email_id": "email-789"}
        resp = client.post("/webhooks/hybrid/agent-2", json=payload)
        assert resp.status_code == 200
        assert resp.json()["success"] is True
