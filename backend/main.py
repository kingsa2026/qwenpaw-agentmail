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
    # 确保数据目录存在
    data_dir = Path.home() / ".qwenpaw" / "agentmail" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"[AgentMail] Data directory: {data_dir}")
    yield
    logger.info("[AgentMail] Backend shutting down...")


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
    # 默认只允许本地开发环境
    return ["http://localhost:3000", "http://127.0.0.1:3000"]

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
