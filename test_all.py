# -*- coding: utf-8 -*-
"""
AgentMail Plugin - 全面模拟测试
测试所有功能模块
"""

import sys
import os
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# 添加backend到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from database import AgentDatabase, get_db, get_all_agent_dbs


class TestRunner:
    """测试运行器"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []

    def test(self, name):
        """装饰器：注册测试"""
        def decorator(func):
            self.tests.append((name, func))
            return func
        return decorator

    def run(self):
        """运行所有测试"""
        print("=" * 60)
        print("AgentMail Plugin - 全面功能测试")
        print("=" * 60)
        print()

        for name, func in self.tests:
            try:
                print(f"[测试] {name}...", end=" ")
                func()
                print("✅ 通过")
                self.passed += 1
            except AssertionError as e:
                print(f"❌ 失败: {e}")
                self.failed += 1
            except Exception as e:
                print(f"❌ 错误: {e}")
                self.failed += 1

        print()
        print("=" * 60)
        print(f"测试结果: {self.passed} 通过, {self.failed} 失败")
        print("=" * 60)
        return self.failed == 0


runner = TestRunner()

# ========== 数据库初始化测试 ==========

@runner.test("数据库初始化 - Agent独立数据库创建")
def test_db_init():
    """测试数据库是否正确初始化"""
    agent_id = "test_agent_001"
    db = get_db(agent_id)

    # 验证数据库文件是否存在
    assert db.db_path.exists(), f"数据库文件不存在: {db.db_path}"

    # 验证目录结构
    assert db.db_dir.exists(), "数据库目录不存在"
    assert db.bak_dir.exists(), "备份目录不存在"
    assert db.files_dir.exists(), "文件目录不存在"

    print(f"(路径: {db.db_path})")


@runner.test("数据库初始化 - 默认分组自动创建")
def test_default_group():
    """测试默认分组是否自动创建"""
    agent_id = "test_agent_002"
    db = get_db(agent_id)

    groups = db.get_contact_groups()
    assert len(groups) > 0, "默认分组未创建"
    assert groups[0]['name'] == 'default', f"默认分组名称错误: {groups[0]['name']}"


# ========== 配置管理测试 ==========

@runner.test("混合模式配置 - 保存和读取")
def test_hybrid_config():
    """测试混合模式配置保存和读取"""
    agent_id = "test_agent_003"
    db = get_db(agent_id)

    config = {
        'provider': 'qq',
        'email': 'test@qq.com',
        'display_name': 'Test User',
        'receive_protocol': 'pop3',
        'smtp': {
            'host': 'smtp.qq.com',
            'port': 587,
            'username': 'test@qq.com',
            'password': 'auth_code_123',
            'use_tls': True,
        },
        'imap': {
            'host': 'imap.qq.com',
            'port': 993,
            'username': 'test@qq.com',
            'password': 'auth_code_123',
            'use_ssl': True,
        },
        'api_key': 'am_api_key_123',
        'inbox_id': 'inbox_123',
        'forwarding': True,
    }

    # 保存配置
    result = db.save_config('hybrid', config)
    assert result, "配置保存失败"

    # 读取配置
    saved = db.get_config()
    assert saved is not None, "配置读取失败"
    assert saved['hybrid']['email'] == 'test@qq.com', "邮箱不匹配"
    assert saved['hybrid']['api_key'] == 'am_api_key_123', "API密钥不匹配"
    assert saved['hybrid']['forwarding'] == True, "转发设置不匹配"
    assert saved['hybrid']['receive_protocol'] == 'pop3', "协议不匹配"


@runner.test("混合模式配置 - 更新配置")
def test_update_config():
    """测试配置更新"""
    agent_id = "test_agent_004"
    db = get_db(agent_id)

    # 初始配置
    db.save_config('hybrid', {
        'provider': 'custom',
        'email': 'old@test.com',
        'smtp': {'host': 'smtp.old.com', 'port': 587, 'username': 'old', 'password': 'old', 'use_tls': True},
        'imap': {'host': 'imap.old.com', 'port': 993, 'username': 'old', 'password': 'old', 'use_ssl': True},
        'api_key': 'old_key',
    })

    # 更新配置
    db.save_config('hybrid', {
        'provider': 'gmail',
        'email': 'new@gmail.com',
        'smtp': {'host': 'smtp.gmail.com', 'port': 587, 'username': 'new', 'password': 'new', 'use_tls': True},
        'imap': {'host': 'imap.gmail.com', 'port': 993, 'username': 'new', 'password': 'new', 'use_ssl': True},
        'api_key': 'new_key',
    })

    saved = db.get_config()
    assert saved['hybrid']['email'] == 'new@gmail.com', "配置未更新"
    assert saved['hybrid']['api_key'] == 'new_key', "API密钥未更新"


@runner.test("混合模式配置 - 删除配置")
def test_delete_config():
    """测试配置删除"""
    agent_id = "test_agent_005"
    db = get_db(agent_id)

    db.save_config('hybrid', {
        'provider': 'custom',
        'email': 'delete@test.com',
        'smtp': {'host': 'smtp.test.com', 'port': 587, 'username': 'test', 'password': 'test', 'use_tls': True},
        'imap': {'host': 'imap.test.com', 'port': 993, 'username': 'test', 'password': 'test', 'use_ssl': True},
    })

    # 删除配置
    result = db.delete_config()
    assert result, "配置删除失败"

    saved = db.get_config()
    assert saved is None or not saved.get('hybrid'), "配置未完全删除"


# ========== 联系人管理测试 ==========

@runner.test("联系人 - 创建联系人")
def test_create_contact():
    """测试创建联系人"""
    agent_id = "test_agent_006"
    db = get_db(agent_id)

    contact_id = db.create_contact({
        'name': '张三',
        'phone': '13800138000',
        'email': 'zhangsan@test.com',
        'company': 'Test Corp',
        'website': 'https://test.com',
        'notes': '重要客户',
        'group_name': 'default',
    })

    assert contact_id > 0, "联系人创建失败"

    # 验证
    contacts = db.get_contacts()
    assert contacts['total'] >= 1, "联系人未保存"


@runner.test("联系人 - 更新联系人")
def test_update_contact():
    """测试更新联系人"""
    agent_id = "test_agent_007"
    db = get_db(agent_id)

    contact_id = db.create_contact({
        'name': '李四',
        'email': 'lisi@test.com',
        'group_name': 'default',
    })

    # 更新
    result = db.update_contact(contact_id, {
        'name': '李四（已更新）',
        'email': 'lisi_new@test.com',
        'company': 'New Company',
    })
    assert result, "更新失败"

    # 验证
    contacts = db.get_contacts()
    updated = [c for c in contacts['items'] if c['id'] == contact_id][0]
    assert updated['name'] == '李四（已更新）', "名称未更新"
    assert updated['email'] == 'lisi_new@test.com', "邮箱未更新"


@runner.test("联系人 - 删除联系人（移动到回收站）")
def test_delete_contact():
    """测试删除联系人并验证回收站"""
    agent_id = "test_agent_008"
    db = get_db(agent_id)

    contact_id = db.create_contact({
        'name': '王五',
        'email': 'wangwu@test.com',
        'group_name': 'default',
    })

    # 删除前数量
    before = db.get_contacts()['total']

    # 删除
    result = db.delete_contacts([contact_id])
    assert result, "删除失败"

    # 验证联系人列表
    after = db.get_contacts()['total']
    assert after == before - 1, f"联系人未从列表移除: {after} != {before - 1}"

    # 验证回收站
    trash = db.get_trash(item_type='contact')
    assert trash['total'] >= 1, "联系人未进入回收站"


@runner.test("联系人 - 搜索和分组筛选")
def test_contact_search():
    """测试联系人搜索和分组筛选"""
    agent_id = "test_agent_009"
    db = get_db(agent_id)

    # 创建测试联系人
    db.create_contact({'name': 'Alice', 'email': 'alice@test.com', 'group_name': 'default'})
    db.create_contact({'name': 'Bob', 'email': 'bob@company.com', 'group_name': 'default'})
    db.create_contact({'name': 'Charlie', 'email': 'charlie@test.com', 'group_name': 'work'})

    # 创建分组
    db.create_contact_group('work')

    # 搜索
    result = db.get_contacts(search='alice')
    assert result['total'] >= 1, "搜索失败"
    assert any('Alice' in c['name'] for c in result['items']), "搜索结果不匹配"

    # 分组筛选
    result = db.get_contacts(group='work')
    assert all(c['group_name'] == 'work' for c in result['items']), "分组筛选失败"


@runner.test("联系人 - 分享联系人")
def test_share_contact():
    """测试联系人分享功能"""
    agent_id = "test_agent_010"
    db = get_db(agent_id)

    contact_id = db.create_contact({
        'name': 'Shared Contact',
        'email': 'shared@test.com',
        'group_name': 'default',
    })

    # 分享给其他Agent
    result = db.share_contact(contact_id, ['agent_002', 'agent_003'])
    assert result, "分享失败"

    # 验证
    contacts = db.get_contacts()
    shared = [c for c in contacts['items'] if c['id'] == contact_id][0]
    shared_with = json.loads(shared.get('shared_with', '[]'))
    assert 'agent_002' in shared_with, "分享目标未记录"
    assert 'agent_003' in shared_with, "分享目标未记录"


@runner.test("联系人分组 - 创建和删除分组")
def test_contact_groups():
    """测试联系人分组管理"""
    agent_id = "test_agent_011"
    db = get_db(agent_id)

    # 创建分组
    group_id = db.create_contact_group('VIP')
    assert group_id > 0, "分组创建失败"

    # 验证
    groups = db.get_contact_groups()
    assert any(g['name'] == 'VIP' for g in groups), "分组未创建"

    # 删除分组
    result = db.delete_contact_group(group_id)
    assert result, "分组删除失败"

    # 验证
    groups = db.get_contact_groups()
    assert not any(g['name'] == 'VIP' for g in groups), "分组未删除"


# ========== 邮件管理测试 ==========

@runner.test("收件箱 - 保存和读取邮件")
def test_inbox():
    """测试收件箱邮件管理"""
    agent_id = "test_agent_012"
    db = get_db(agent_id)

    # 保存邮件
    email_id = db.save_inbox_email({
        'message_id': 'msg_001',
        'subject': '测试邮件',
        'sender_name': 'Sender',
        'sender_email': 'sender@test.com',
        'recipient': 'recipient@test.com',
        'body': '这是邮件正文',
        'body_html': '<p>这是邮件正文</p>',
        'editor_mode': 'plain',
        'attachments': json.dumps([{'name': 'file.txt', 'size': 1024}]),
        'date': datetime.now().isoformat(),
        'folder': 'inbox',
    })

    assert email_id > 0, "邮件保存失败"

    # 读取
    emails = db.get_inbox()
    assert emails['total'] >= 1, "邮件未保存"
    assert emails['items'][0]['subject'] == '测试邮件', "邮件主题不匹配"


@runner.test("收件箱 - Agent已读和回复状态")
def test_inbox_status():
    """测试Agent已读和回复状态"""
    agent_id = "test_agent_013"
    db = get_db(agent_id)

    email_id = db.save_inbox_email({
        'message_id': 'msg_002',
        'subject': 'Status Test',
        'sender_email': 'test@test.com',
        'body': 'Test body',
        'date': datetime.now().isoformat(),
    })

    # 标记Agent已读
    result = db.mark_agent_read(email_id, True)
    assert result, "标记已读失败"

    # 标记回复
    result = db.mark_replied(email_id, 'Reply content')
    assert result, "标记回复失败"

    # 验证
    emails = db.get_inbox()
    email = [e for e in emails['items'] if e['id'] == email_id][0]
    assert email['is_agent_read'] == 1, "已读状态未更新"
    assert email['is_replied'] == 1, "回复状态未更新"


@runner.test("收件箱 - 归档邮件")
def test_archive():
    """测试邮件归档"""
    agent_id = "test_agent_014"
    db = get_db(agent_id)

    email_id = db.save_inbox_email({
        'message_id': 'msg_003',
        'subject': 'Archive Test',
        'sender_email': 'test@test.com',
        'body': 'Test',
        'date': datetime.now().isoformat(),
        'folder': 'inbox',
    })

    # 归档
    result = db.archive_emails([email_id])
    assert result, "归档失败"

    # 验证不在收件箱
    inbox = db.get_inbox(folder='inbox')
    assert not any(e['id'] == email_id for e in inbox['items']), "邮件仍在收件箱"


@runner.test("发件箱 - 保存已发送邮件")
def test_sent():
    """测试发件箱"""
    agent_id = "test_agent_015"
    db = get_db(agent_id)

    sent_id = db.save_sent({
        'message_id': 'sent_001',
        'subject': 'Sent Email',
        'recipient': 'to@test.com',
        'body': 'Sent body',
        'status': 'sent',
        'sent_at': datetime.now().isoformat(),
    })

    assert sent_id > 0, "保存失败"

    sent = db.get_sent()
    assert sent['total'] >= 1, "发件箱为空"


@runner.test("草稿箱 - 保存和更新草稿")
def test_drafts():
    """测试草稿箱"""
    agent_id = "test_agent_016"
    db = get_db(agent_id)

    # 创建草稿
    draft_id = db.save_draft(None, {
        'subject': 'Draft Test',
        'recipient': 'draft@test.com',
        'body': 'Draft content',
        'editor_mode': 'markdown',
    })

    assert draft_id > 0, "草稿创建失败"

    # 更新草稿
    updated_id = db.save_draft(draft_id, {
        'subject': 'Draft Updated',
        'recipient': 'draft@test.com',
        'body': 'Updated content',
    })

    assert updated_id == draft_id, "草稿ID应保持一致"

    drafts = db.get_drafts()
    assert drafts['total'] >= 1, "草稿未保存"


# ========== 回收站测试 ==========

@runner.test("回收站 - 邮件删除和恢复")
def test_trash_email():
    """测试邮件删除进入回收站和恢复"""
    agent_id = "test_agent_017"
    db = get_db(agent_id)

    # 创建邮件
    email_id = db.save_inbox_email({
        'message_id': 'msg_trash_001',
        'subject': 'Trash Test',
        'sender_email': 'test@test.com',
        'body': 'Test body',
        'date': datetime.now().isoformat(),
    })

    # 删除到回收站
    result = db.move_to_trash('inbox', [email_id])
    assert result, "移动到回收站失败"

    # 验证回收站
    trash = db.get_trash(item_type='inbox')
    assert trash['total'] >= 1, "邮件未进入回收站"

    # 恢复
    trash_id = trash['items'][0]['id']
    result = db.restore_from_trash([trash_id])
    assert result, "恢复失败"

    # 验证回到收件箱
    inbox = db.get_inbox()
    assert any(e['subject'] == 'Trash Test' for e in inbox['items']), "邮件未恢复"


@runner.test("回收站 - 联系人删除和恢复")
def test_trash_contact():
    """测试联系人删除进入回收站和恢复"""
    agent_id = "test_agent_018"
    db = get_db(agent_id)

    contact_id = db.create_contact({
        'name': 'Trash Contact',
        'email': 'trash@test.com',
        'group_name': 'default',
    })

    # 删除
    result = db.move_to_trash('contact', [contact_id])
    assert result, "删除到回收站失败"

    # 验证回收站
    trash = db.get_trash(item_type='contact')
    assert trash['total'] >= 1, "联系人未进入回收站"

    # 验证联系人列表
    contacts = db.get_contacts()
    assert not any(c['id'] == contact_id for c in contacts['items']), "联系人未从列表移除"

    # 恢复
    trash_id = trash['items'][0]['id']
    result = db.restore_from_trash([trash_id])
    assert result, "恢复失败"

    # 验证
    contacts = db.get_contacts()
    assert any(c['name'] == 'Trash Contact' for c in contacts['items']), "联系人未恢复"


@runner.test("回收站 - 永久删除")
def test_permanent_delete():
    """测试永久删除"""
    agent_id = "test_agent_019"
    db = get_db(agent_id)

    contact_id = db.create_contact({
        'name': 'Permanent Delete',
        'email': 'perm@test.com',
        'group_name': 'default',
    })

    # 删除到回收站
    db.move_to_trash('contact', [contact_id])

    # 获取回收站ID
    trash = db.get_trash(item_type='contact')
    trash_id = trash['items'][0]['id']

    # 永久删除
    result = db.permanent_delete([trash_id])
    assert result, "永久删除失败"

    # 验证回收站为空
    trash = db.get_trash(item_type='contact')
    assert trash['total'] == 0, "回收站未清空"


@runner.test("回收站 - 分类筛选")
def test_trash_filter():
    """测试回收站分类筛选"""
    agent_id = "test_agent_020"
    db = get_db(agent_id)

    # 创建不同类型的数据
    inbox_id = db.save_inbox_email({
        'message_id': 'filter_001',
        'subject': 'Filter Test',
        'sender_email': 'test@test.com',
        'body': 'Test',
        'date': datetime.now().isoformat(),
    })
    draft_id = db.save_draft(None, {
        'subject': 'Draft Filter',
        'recipient': 'test@test.com',
        'body': 'Draft',
    })

    # 删除到回收站
    db.move_to_trash('inbox', [inbox_id])
    db.move_to_trash('drafts', [draft_id])

    # 筛选收件箱
    inbox_trash = db.get_trash(item_type='inbox')
    assert inbox_trash['total'] >= 1, "收件箱筛选失败"

    # 筛选草稿
    draft_trash = db.get_trash(item_type='drafts')
    assert draft_trash['total'] >= 1, "草稿筛选失败"

    # 全部
    all_trash = db.get_trash()
    assert all_trash['total'] >= 2, "全部筛选失败"


# ========== 备份测试 ==========

@runner.test("备份 - 创建备份")
def test_backup():
    """测试数据库备份"""
    agent_id = "test_agent_021"
    db = get_db(agent_id)

    # 先创建一些数据
    db.create_contact({'name': 'Backup Test', 'email': 'backup@test.com', 'group_name': 'default'})

    # 备份
    result = db.backup()
    assert result['success'], "备份失败"
    assert Path(result['backup_path']).exists(), "备份文件不存在"

    print(f"(备份路径: {result['backup_path']})")


@runner.test("备份 - 获取备份列表")
def test_backup_list():
    """测试获取备份列表"""
    agent_id = "test_agent_022"
    db = get_db(agent_id)

    # 先创建一些数据确保数据库文件有内容
    db.create_contact({'name': 'Backup List Test', 'email': 'blist@test.com', 'group_name': 'default'})

    # 等待1秒确保时间戳不同
    import time
    time.sleep(1.1)

    # 创建多个备份
    db.backup()

    time.sleep(1.1)
    db.backup()

    # 获取列表
    backups = db.get_backup_list()
    assert len(backups) >= 2, f"备份列表不完整，实际数量: {len(backups)}"


# ========== Agent隔离测试 ==========

@runner.test("Agent隔离 - 数据完全隔离")
def test_agent_isolation():
    """测试不同Agent数据完全隔离"""
    agent1 = "isolation_agent_1"
    agent2 = "isolation_agent_2"

    db1 = get_db(agent1)
    db2 = get_db(agent2)

    # 在Agent1创建数据
    db1.create_contact({'name': 'Agent1 Contact', 'email': 'a1@test.com', 'group_name': 'default'})
    db1.save_config('hybrid', {'provider': 'custom', 'email': 'agent1@test.com', 'smtp': {'host': 'smtp.test.com', 'port': 587, 'username': 'test', 'password': 'test', 'use_tls': True}, 'imap': {'host': 'imap.test.com', 'port': 993, 'username': 'test', 'password': 'test', 'use_ssl': True}})

    # 在Agent2创建数据
    db2.create_contact({'name': 'Agent2 Contact', 'email': 'a2@test.com', 'group_name': 'default'})
    db2.save_config('hybrid', {'provider': 'custom', 'email': 'agent2@test.com', 'smtp': {'host': 'smtp.test.com', 'port': 587, 'username': 'test', 'password': 'test', 'use_tls': True}, 'imap': {'host': 'imap.test.com', 'port': 993, 'username': 'test', 'password': 'test', 'use_ssl': True}})

    # 验证Agent1数据
    contacts1 = db1.get_contacts()
    assert any(c['name'] == 'Agent1 Contact' for c in contacts1['items']), "Agent1数据丢失"
    assert not any(c['name'] == 'Agent2 Contact' for c in contacts1['items']), "Agent2数据泄漏到Agent1"

    config1 = db1.get_config()
    assert config1['hybrid']['email'] == 'agent1@test.com', "Agent1配置错误"

    # 验证Agent2数据
    contacts2 = db2.get_contacts()
    assert any(c['name'] == 'Agent2 Contact' for c in contacts2['items']), "Agent2数据丢失"
    assert not any(c['name'] == 'Agent1 Contact' for c in contacts2['items']), "Agent1数据泄漏到Agent2"

    config2 = db2.get_config()
    assert config2['hybrid']['email'] == 'agent2@test.com', "Agent2配置错误"

    # 验证数据库文件路径不同
    assert db1.db_path != db2.db_path, "数据库路径相同，隔离失败"


@runner.test("Agent隔离 - 数据库路径正确")
def test_db_path():
    """测试数据库路径格式"""
    agent_id = "path_test_agent"
    db = get_db(agent_id)

    expected_path = Path.home() / ".qwenpaw" / "agents" / agent_id / "email" / "agentmail.db"
    assert db.db_path == expected_path, f"数据库路径错误: {db.db_path} != {expected_path}"

    print(f"(路径: {db.db_path})")


# ========== 批量操作测试 ==========

@runner.test("批量操作 - 批量删除联系人")
def test_batch_delete_contacts():
    """测试批量删除联系人"""
    agent_id = "test_agent_023"
    db = get_db(agent_id)

    # 创建多个联系人
    ids = []
    for i in range(3):
        cid = db.create_contact({
            'name': f'Batch Contact {i}',
            'email': f'batch{i}@test.com',
            'group_name': 'default',
        })
        ids.append(cid)

    # 批量删除
    result = db.delete_contacts(ids)
    assert result, "批量删除失败"

    # 验证
    contacts = db.get_contacts()
    for cid in ids:
        assert not any(c['id'] == cid for c in contacts['items']), f"联系人{cid}未删除"

    # 验证回收站
    trash = db.get_trash(item_type='contact')
    assert trash['total'] >= 3, "回收站数量不正确"


@runner.test("批量操作 - 批量恢复")
def test_batch_restore():
    """测试批量恢复"""
    agent_id = "test_agent_024"
    db = get_db(agent_id)

    # 创建并删除多个联系人
    ids = []
    for i in range(2):
        cid = db.create_contact({
            'name': f'Restore Contact {i}',
            'email': f'restore{i}@test.com',
            'group_name': 'default',
        })
        ids.append(cid)

    db.delete_contacts(ids)

    # 获取回收站ID
    trash = db.get_trash(item_type='contact')
    trash_ids = [t['id'] for t in trash['items'][:2]]

    # 批量恢复
    result = db.restore_from_trash(trash_ids)
    assert result, "批量恢复失败"

    # 验证
    contacts = db.get_contacts()
    assert any(c['name'] == 'Restore Contact 0' for c in contacts['items']), "恢复失败"


if __name__ == '__main__':
    # 清理测试数据
    print("清理旧测试数据...")
    agents_dir = Path.home() / ".qwenpaw" / "agents"
    if agents_dir.exists():
        for agent_dir in agents_dir.iterdir():
            if agent_dir.is_dir() and agent_dir.name.startswith('test_agent_'):
                shutil.rmtree(agent_dir)
                print(f"  已清理: {agent_dir.name}")
            elif agent_dir.is_dir() and agent_dir.name.startswith('isolation_'):
                shutil.rmtree(agent_dir)
                print(f"  已清理: {agent_dir.name}")
            elif agent_dir.is_dir() and agent_dir.name == 'path_test_agent':
                shutil.rmtree(agent_dir)
                print(f"  已清理: {agent_dir.name}")

    print()

    # 运行测试
    success = runner.run()

    # 再次清理
    print()
    print("清理测试数据...")
    if agents_dir.exists():
        for agent_dir in agents_dir.iterdir():
            if agent_dir.is_dir() and (
                agent_dir.name.startswith('test_agent_') or
                agent_dir.name.startswith('isolation_') or
                agent_dir.name == 'path_test_agent'
            ):
                shutil.rmtree(agent_dir)

    sys.exit(0 if success else 1)
