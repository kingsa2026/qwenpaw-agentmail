# -*- coding: utf-8 -*-
"""
AgentMail Plugin - 插件生命周期单元测试

测试范围:
  - AgentMailPlugin.register
  - AgentMailPlugin.on_startup
  - AgentMailPlugin.on_shutdown
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from plugin import AgentMailPlugin


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def plugin():
    """返回一个干净的插件实例"""
    return AgentMailPlugin()


@pytest.fixture
def mock_api():
    """构造模拟的 PluginApi 对象"""
    api = MagicMock()
    api.register_startup_hook = MagicMock()
    api.register_shutdown_hook = MagicMock()
    api.register_control_command = MagicMock()
    return api


@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    """使用临时目录替代 Path.home()"""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


# ── AgentMailPlugin.register ──────────────────────────────────────────────

class TestPluginRegister:
    """测试插件注册逻辑"""

    def test_register_returns_true(self, plugin, mock_api):
        result = plugin.register(mock_api)
        assert result is True

    def test_register_startup_hook(self, plugin, mock_api):
        plugin.register(mock_api)
        mock_api.register_startup_hook.assert_called_once_with(
            hook_name="agentmail_init",
            callback=plugin.on_startup,
            priority=100,
        )

    def test_register_shutdown_hook(self, plugin, mock_api):
        plugin.register(mock_api)
        mock_api.register_shutdown_hook.assert_called_once_with(
            hook_name="agentmail_cleanup",
            callback=plugin.on_shutdown,
            priority=100,
        )

    def test_register_cli_commands(self, plugin, mock_api, monkeypatch):
        """验证 CLI 命令注册逻辑：直接 patch register 内部的 import 结果"""
        import plugin as plugin_mod
        import builtins

        # 构造假的命令类，避免相对导入失败
        fake_cmd = MagicMock()
        fake_cmd.command_name = "/fake"

        fake_module = MagicMock()
        fake_module.ListContactsCommand = lambda: fake_cmd
        fake_module.ShareContactsCommand = lambda: fake_cmd
        fake_module.ListInboxCommand = lambda: fake_cmd
        fake_module.ListSentCommand = lambda: fake_cmd
        fake_module.ListDraftsCommand = lambda: fake_cmd
        fake_module.ListTrashCommand = lambda: fake_cmd
        fake_module.BackupCommand = lambda: fake_cmd
        fake_module.ConfigCommand = lambda: fake_cmd
        fake_module.SendEmailCommand = lambda: fake_cmd
        fake_module.ReadEmailCommand = lambda: fake_cmd

        original_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name.endswith("cli_commands"):
                return fake_module
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        # 构造一个新的插件实例，使用已被 patch 的导入
        test_plugin = plugin_mod.AgentMailPlugin()
        test_plugin.register(mock_api)
        assert mock_api.register_control_command.call_count == 10

        # 验证每个命令都有 priority_level=10
        for c in mock_api.register_control_command.call_args_list:
            assert c.kwargs.get("priority_level") == 10

    def test_register_logs_info(self, plugin, mock_api, caplog, monkeypatch):
        """验证注册日志输出，patch 掉相对导入"""
        import plugin as plugin_mod
        import builtins

        fake_module = MagicMock()
        for cls_name in [
            "ListContactsCommand", "ShareContactsCommand", "ListInboxCommand",
            "ListSentCommand", "ListDraftsCommand", "ListTrashCommand",
            "BackupCommand", "ConfigCommand", "SendEmailCommand", "ReadEmailCommand",
        ]:
            setattr(fake_module, cls_name, MagicMock)

        original_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name.endswith("cli_commands"):
                return fake_module
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        test_plugin = plugin_mod.AgentMailPlugin()
        with caplog.at_level("INFO"):
            test_plugin.register(mock_api)
        assert "注册插件" in caplog.text
        assert "CLI 命令注册成功" in caplog.text
        assert "插件注册成功" in caplog.text

    def test_register_handles_cli_import_error(self, plugin, mock_api, monkeypatch):
        """模拟 cli_commands 导入失败时的降级行为"""
        import plugin as plugin_mod

        def raise_import(*args, **kwargs):
            raise ImportError("mocked import failure")

        monkeypatch.setitem(sys.modules, f"{plugin_mod.__name__}.cli_commands", None)
        # 让 __import__ 在尝试加载 cli_commands 时失败
        original_import = __builtins__["__import__"]

        def fake_import(name, *args, **kwargs):
            if "cli_commands" in name:
                raise ImportError("mocked")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)
        result = plugin.register(mock_api)
        assert result is True  # register 整体仍应返回 True

    def test_plugin_attributes(self, plugin):
        assert plugin.name == "AgentMail"
        assert plugin.version == "1.1.0"
        assert plugin.id == "agentmail"
        assert "混合模式" in plugin.description


# ── AgentMailPlugin.on_startup ────────────────────────────────────────────

class TestPluginStartup:
    """测试插件启动初始化"""

    def test_creates_plugin_directory(self, plugin, temp_home):
        plugin.on_startup()
        expected = temp_home / ".qwenpaw" / "agentmail"
        assert expected.exists()
        assert expected.is_dir()

    def test_logs_info(self, plugin, temp_home, caplog):
        with caplog.at_level("INFO"):
            plugin.on_startup()
        assert "初始化中" in caplog.text
        assert "插件目录" in caplog.text
        assert "初始化完成" in caplog.text


# ── AgentMailPlugin.on_shutdown ───────────────────────────────────────────

class TestPluginShutdown:
    """测试插件关闭清理"""

    def test_logs_shutdown(self, plugin, caplog):
        with caplog.at_level("INFO"):
            plugin.on_shutdown()
        assert "关闭中" in caplog.text
        assert "已关闭" in caplog.text


# ── 集成风格测试 ──────────────────────────────────────────────────────────

class TestPluginLifecycle:
    """模拟完整的注册 -> 启动 -> 关闭 生命周期"""

    def test_full_lifecycle(self, plugin, mock_api, temp_home, caplog):
        with caplog.at_level("INFO"):
            # 1. 注册
            assert plugin.register(mock_api) is True

            # 2. 启动
            plugin.on_startup()
            assert (temp_home / ".qwenpaw" / "agentmail").exists()

            # 3. 关闭
            plugin.on_shutdown()

        assert "注册插件" in caplog.text
        assert "初始化完成" in caplog.text
        assert "已关闭" in caplog.text
