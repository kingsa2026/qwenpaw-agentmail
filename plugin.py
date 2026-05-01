# -*- coding: utf-8 -*-
"""
AgentMail Plugin - QwenPaw 标准插件入口

必须导出 `plugin` 对象，QwenPaw 加载器会调用 plugin.register(api)
采用混合模式：同时支持传统邮箱(SMTP/POP3/IMAP)和AgentMail.to API
每个Agent拥有独立的数据库，路径: ~/.qwenpaw/agents/{agent_id}/email/
"""

import logging
from pathlib import Path

# 配置日志
logger = logging.getLogger(__name__)

# 插件目录
PLUGIN_DIR = Path(__file__).parent


class AgentMailPlugin:
    """AgentMail 插件主类 - 混合模式"""

    def __init__(self):
        self.name = "AgentMail"
        self.version = "1.1.0"
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
        """插件启动时的初始化 - 创建Agent数据库目录结构"""
        logger.info(f"[{self.id}] 初始化中...")

        # 确保插件根目录存在
        plugin_dir = Path.home() / ".qwenpaw" / "agentmail"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[{self.id}] 插件目录: {plugin_dir}")

        # Agent数据库会自动在首次访问时创建
        # 路径: ~/.qwenpaw/agents/{agent_id}/email/agentmail.db
        logger.info(f"[{self.id}] Agent数据库路径: ~/.qwenpaw/agents/{{agent_id}}/email/")

        logger.info(f"[{self.id}] ✓ 初始化完成")

    def on_shutdown(self):
        """插件关闭时的清理"""
        logger.info(f"[{self.id}] 关闭中...")
        logger.info(f"[{self.id}] ✓ 已关闭")


# 导出插件实例 - QwenPaw 加载器会查找这个变量
plugin = AgentMailPlugin()
