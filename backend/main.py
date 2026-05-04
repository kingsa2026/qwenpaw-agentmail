"""
AgentMail Plugin - FastAPI Backend

Agent隔离的邮件管理后端服务
"""

import logging
import os
import sys
from pathlib import Path

# 添加backend到路径
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from routes.api_routes import router as email_router

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("[AgentMail] Backend starting...")
    _qwenpaw_home = Path(os.environ.get("QWENPAW_WORKING_DIR", os.environ.get("COPAW_WORKING_DIR", Path.home() / ".qwenpaw")))
    data_dir = _qwenpaw_home / "agentmail" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"[AgentMail] Data directory: {data_dir}")

    import asyncio

    _graph_pollers = []

    async def _auto_start_listeners():
        await asyncio.sleep(3)
        try:
            from database import get_all_agent_dbs
            from imap_idle_listener import ListenerManager
            from graph_poll_listener import GraphPollListener
            manager = ListenerManager()
            dbs = get_all_agent_dbs()
            for agent_id, db in dbs.items():
                config = db.get_config()
                if not config:
                    continue
                if config.get("imap", {}).get("host"):
                    result = manager.start_listener(agent_id)
                    if result.get("success"):
                        logger.info(f"[AgentMail] Auto-started IMAP IDLE for {agent_id}: {config.get('email')}")
                    else:
                        logger.warning(f"[AgentMail] Failed to auto-start for {agent_id}: {result.get('error')}")
                elif config.get("auth_type") == "oauth2" and config.get("provider") == "outlook":
                    poller = GraphPollListener(agent_id, config)
                    result = poller.start()
                    if result.get("success"):
                        _graph_pollers.append(poller)
                        logger.info(f"[AgentMail] Auto-started Graph poll for {agent_id}: {config.get('email')}")
                    else:
                        logger.warning(f"[AgentMail] Failed to auto-start Graph poll for {agent_id}: {result.get('error')}")
        except Exception as e:
            logger.error(f"[AgentMail] Auto-start listeners failed: {e}")

    asyncio.create_task(_auto_start_listeners())

    yield
    logger.info("[AgentMail] Backend shutting down...")
    for poller in _graph_pollers:
        try:
            poller.stop()
        except Exception:
            pass
    try:
        from imap_idle_listener import ListenerManager
        manager = ListenerManager()
        manager.stop_all()
    except Exception:
        pass


# 创建FastAPI应用
app = FastAPI(
    title="AgentMail API",
    description="Agent隔离的邮件管理API",
    version="2.0.0",
    lifespan=lifespan
)

# CORS配置 - 生产环境应指定具体域名
def _get_cors_origins():
    """获取允许的 CORS 来源"""
    env_origins = os.environ.get("AGENTMAIL_CORS_ORIGINS", "")
    if env_origins:
        return [origin.strip() for origin in env_origins.split(",") if origin.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.10.132:8088",
        "http://192.168.10.132:18088",
        "http://localhost:8088",
        "http://localhost:18088",
    ]

_cors_origins = _get_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)

# 注册路由
app.include_router(email_router)


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "agentmail"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18088)
