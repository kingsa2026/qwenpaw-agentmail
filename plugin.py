# -*- coding: utf-8 -*-
"""
AgentMail Plugin - QwenPaw 标准插件入口

必须导出 `plugin` 对象，QwenPaw 加载器会调用 plugin.register(api)
采用混合模式：同时支持传统邮箱(SMTP/POP3/IMAP)和AgentMail.to API
每个Agent拥有独立的数据库，路径: ~/.qwenpaw/agents/{agent_id}/mail/
"""

import logging
import subprocess
import os
import signal
from pathlib import Path

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path(__file__).parent

_qwenpaw_working_dir = os.environ.get("QWENPAW_WORKING_DIR", os.environ.get("COPAW_WORKING_DIR", ""))
if _qwenpaw_working_dir:
    _QWENPAW_HOME = Path(_qwenpaw_working_dir).expanduser().resolve()
else:
    _QWENPAW_HOME = Path.home() / ".qwenpaw"

# 后端进程引用
_backend_process = None


class AgentMailPlugin:
    """AgentMail 插件主类 - 混合模式"""

    def __init__(self):
        self.name = "AgentMail"
        self.version = "1.2.0"
        self.description = "邮箱管理插件，采用混合模式同时支持传统邮箱和AgentMail.to"
        self.id = "agentmail"

    def register(self, api):
        """
        注册插件到 QwenPaw

        Args:
            api: PluginApi 实例
        """
        logger.info(f"[{self.id}] 注册插件: {self.name} v{self.version}")

        # 注册启动钩子
        api.register_startup_hook(
            hook_name=f"{self.id}_init",
            callback=self.on_startup,
            priority=100,
        )

        # 注册关闭钩子
        api.register_shutdown_hook(
            hook_name=f"{self.id}_cleanup",
            callback=self.on_shutdown,
            priority=100,
        )

        # 注册 CLI 控制命令
        try:
            from .cli_commands import (
                ListContactsCommand,
                ShareContactsCommand,
                ListInboxCommand,
                ListSentCommand,
                ListDraftsCommand,
                ListTrashCommand,
                BackupCommand,
                ConfigCommand,
                SendEmailCommand,
                ReadEmailCommand,
            )
            api.register_control_command(ListContactsCommand(), priority_level=10)
            api.register_control_command(ShareContactsCommand(), priority_level=10)
            api.register_control_command(ListInboxCommand(), priority_level=10)
            api.register_control_command(ListSentCommand(), priority_level=10)
            api.register_control_command(ListDraftsCommand(), priority_level=10)
            api.register_control_command(ListTrashCommand(), priority_level=10)
            api.register_control_command(BackupCommand(), priority_level=10)
            api.register_control_command(ConfigCommand(), priority_level=10)
            api.register_control_command(SendEmailCommand(), priority_level=10)
            api.register_control_command(ReadEmailCommand(), priority_level=10)
            logger.info(f"[{self.id}] ✓ CLI 命令注册成功 (10 个命令)")
        except Exception as e:
            logger.warning(f"[{self.id}] CLI 命令注册失败: {e}")

        logger.info(f"[{self.id}] ✓ 插件注册成功")
        return True

    def on_startup(self):
        """插件启动时的初始化 - 启动后端服务"""
        logger.info(f"[{self.id}] 初始化中...")

        # 确保插件根目录存在
        plugin_dir = _QWENPAW_HOME / "agentmail"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[{self.id}] 插件目录: {plugin_dir}")

        logger.info(f"[{self.id}] Agent数据库路径: {_QWENPAW_HOME}/workspaces/{{agent_id}}/mail/")

        # 启动后端服务
        self._start_backend()

        logger.info(f"[{self.id}] ✓ 初始化完成")

    def on_shutdown(self):
        """插件关闭时的清理 - 停止后端服务"""
        logger.info(f"[{self.id}] 关闭中...")
        self._stop_backend()
        logger.info(f"[{self.id}] ✓ 已关闭")

    def _start_backend(self):
        """启动AgentMail后端服务"""
        global _backend_process
        try:
            # 检查后端服务是否已在运行
            result = subprocess.run(
                ["lsof", "-i", ":18088"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                logger.info(f"[{self.id}] 后端服务已在运行 (端口18088)")
                return
        except Exception:
            pass

        try:
            # 使用QwenPaw的Python环境启动后端
            backend_path = PLUGIN_DIR / "backend" / "main.py"
            python_path = _QWENPAW_HOME / "venv" / "bin" / "python"

            if not python_path.exists():
                python_path = Path("/usr/bin/python3")

            env = os.environ.copy()
            env["PYTHONPATH"] = str(PLUGIN_DIR)
            env["AGENTMAIL_CORS_ORIGINS"] = "http://localhost:3000,http://127.0.0.1:3000,http://192.168.10.132:8088"

            _backend_process = subprocess.Popen(
                [str(python_path), str(backend_path)],
                cwd=str(PLUGIN_DIR),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

            logger.info(f"[{self.id}] ✓ 后端服务已启动 (PID: {_backend_process.pid}, 端口18088)")
        except Exception as e:
            logger.error(f"[{self.id}] 后端服务启动失败: {e}")

    def _stop_backend(self):
        """停止AgentMail后端服务"""
        global _backend_process
        try:
            if _backend_process:
                _backend_process.terminate()
                _backend_process.wait(timeout=5)
                logger.info(f"[{self.id}] ✓ 后端服务已停止")
                _backend_process = None
            else:
                # 尝试查找并停止后端进程
                subprocess.run(
                    ["pkill", "-f", "agentmail/backend/main.py"],
                    capture_output=True,
                    timeout=5
                )
        except Exception as e:
            logger.warning(f"[{self.id}] 后端服务停止时出错: {e}")


# 导出插件实例 - QwenPaw 加载器会查找这个变量
plugin = AgentMailPlugin()
