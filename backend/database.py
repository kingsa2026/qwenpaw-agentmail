"""
AgentMail Plugin - Database Module

Agent隔离的SQLite数据库管理 - 每个Agent独立数据库
"""

import sqlite3
import json
import os
import re
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# 简单的敏感字段加密（使用 base64 + 异或混淆，生产环境建议使用 AES-256-GCM）
_ENCRYPTION_KEY = os.environ.get("AGENTMAIL_KEY", "agentmail-default-key-2026").encode()

def _encrypt_field(value: Optional[str]) -> Optional[str]:
    """加密敏感字段"""
    if not value:
        return value
    try:
        data = value.encode('utf-8')
        # 使用异或加密（简单保护，生产环境请使用 AES-256-GCM）
        key = _ENCRYPTION_KEY
        encrypted = bytearray()
        for i, b in enumerate(data):
            encrypted.append(b ^ key[i % len(key)])
        return base64.b64encode(bytes(encrypted)).decode('ascii')
    except Exception:
        return value

def _decrypt_field(value: Optional[str]) -> Optional[str]:
    """解密敏感字段"""
    if not value:
        return value
    try:
        data = base64.b64decode(value.encode('ascii'))
        key = _ENCRYPTION_KEY
        decrypted = bytearray()
        for i, b in enumerate(data):
            decrypted.append(b ^ key[i % len(key)])
        return bytes(decrypted).decode('utf-8')
    except Exception:
        return value


import re

class AgentDatabase:
    """Agent隔离的数据库管理器 - 每个Agent独立数据库文件"""

    # 允许的 Agent ID 字符：字母、数字、下划线、连字符
    _AGENT_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')

    def __init__(self, agent_id: str):
        # 校验 Agent ID，防止路径遍历
        if not agent_id or not self._AGENT_ID_PATTERN.match(agent_id):
            raise ValueError("agent_id must contain only letters, numbers, underscores, and hyphens")
        self.agent_id = agent_id
        # Agent工作空间路径: ~/.qwenpaw/agents/{agent_id}/mail/
        self.db_dir = Path.home() / ".qwenpaw" / "agents" / agent_id / "mail"
        self.db_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db_path = self.db_dir / "agentmail.db"
        self.bak_dir = self.db_dir / "bak"
        self.files_dir = self.db_dir / "files"
        self.bak_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.files_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        # 设置数据库文件权限（仅所有者可读写）
        if self.db_path.exists():
            os.chmod(self.db_path, 0o600)
        self._init_db()

    def _init_db(self):
        """初始化数据库表结构"""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # 邮件配置表 - 混合模式专用
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS email_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    config_type TEXT NOT NULL DEFAULT 'hybrid',
                    provider TEXT DEFAULT 'custom',
                    email TEXT,
                    display_name TEXT,
                    smtp_host TEXT,
                    smtp_port INTEGER,
                    smtp_username TEXT,
                    smtp_password TEXT,
                    smtp_use_tls BOOLEAN DEFAULT 1,
                    receive_host TEXT,
                    receive_port INTEGER,
                    receive_username TEXT,
                    receive_password TEXT,
                    receive_use_ssl BOOLEAN DEFAULT 1,
                    receive_protocol TEXT DEFAULT 'pop3',
                    api_key TEXT,
                    inbox_id TEXT,
                    forwarding BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(agent_id, config_type)
                )
            """)

            # 收件箱
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    message_id TEXT UNIQUE,
                    subject TEXT,
                    sender_name TEXT,
                    sender_email TEXT,
                    recipient TEXT,
                    cc TEXT,
                    bcc TEXT,
                    body TEXT,
                    body_html TEXT,
                    editor_mode TEXT DEFAULT 'plain',
                    attachments TEXT,
                    date TIMESTAMP,
                    folder TEXT DEFAULT 'inbox',
                    is_read BOOLEAN DEFAULT 0,
                    is_agent_read BOOLEAN DEFAULT 0,
                    is_replied BOOLEAN DEFAULT 0,
                    reply_content TEXT,
                    labels TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 发件箱
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sent (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    message_id TEXT UNIQUE,
                    subject TEXT,
                    recipient TEXT,
                    cc TEXT,
                    bcc TEXT,
                    body TEXT,
                    body_html TEXT,
                    editor_mode TEXT DEFAULT 'plain',
                    attachments TEXT,
                    status TEXT DEFAULT 'pending',
                    error_msg TEXT,
                    sent_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 草稿箱
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    subject TEXT,
                    recipient TEXT,
                    cc TEXT,
                    bcc TEXT,
                    body TEXT,
                    body_html TEXT,
                    editor_mode TEXT DEFAULT 'plain',
                    attachments TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 回收站
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trash (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    original_id INTEGER NOT NULL,
                    data TEXT NOT NULL,
                    deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 联系人
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    phone TEXT,
                    email TEXT NOT NULL,
                    company TEXT,
                    website TEXT,
                    notes TEXT,
                    group_name TEXT DEFAULT 'default',
                    shared_with TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 联系人分组
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contact_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(agent_id, name)
                )
            """)

            # 插入默认分组
            cursor.execute("""
                INSERT OR IGNORE INTO contact_groups (agent_id, name) VALUES (?, ?)
            """, (self.agent_id, 'default'))

            conn.commit()

    @contextmanager
    def _get_conn(self):
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # ── 配置操作 ─────────────────────────────────────────────────────────────

    def save_config(self, config_type: str, data: Dict[str, Any]) -> bool:
        """保存配置 - 混合模式"""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # 检查是否已存在
            cursor.execute(
                "SELECT id FROM email_configs WHERE agent_id = ? AND config_type = ?",
                (self.agent_id, config_type)
            )
            existing = cursor.fetchone()

            # 混合模式配置: 同时包含传统邮箱和AgentMail配置
            # 敏感字段加密存储
            fields = {
                'provider': data.get('provider', 'custom'),
                'email': data.get('email'),
                'display_name': data.get('display_name'),
                'smtp_host': data.get('smtp', {}).get('host'),
                'smtp_port': data.get('smtp', {}).get('port'),
                'smtp_username': data.get('smtp', {}).get('username'),
                'smtp_password': _encrypt_field(data.get('smtp', {}).get('password')),
                'smtp_use_tls': data.get('smtp', {}).get('use_tls', True),
                'receive_host': data.get('imap', {}).get('host'),
                'receive_port': data.get('imap', {}).get('port'),
                'receive_username': data.get('imap', {}).get('username'),
                'receive_password': _encrypt_field(data.get('imap', {}).get('password')),
                'receive_use_ssl': data.get('imap', {}).get('use_ssl', True),
                'receive_protocol': data.get('receive_protocol', 'pop3'),
                'api_key': _encrypt_field(data.get('api_key')),
                'inbox_id': data.get('inbox_id'),
                'forwarding': data.get('forwarding', True),
            }

            if existing:
                # 更新
                set_clause = ', '.join([f"{k} = ?" for k in fields.keys()])
                values = list(fields.values()) + [self.agent_id, config_type]
                cursor.execute(
                    f"UPDATE email_configs SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE agent_id = ? AND config_type = ?",
                    values
                )
            else:
                # 插入
                columns = ['agent_id', 'config_type'] + list(fields.keys())
                placeholders = ', '.join(['?' for _ in columns])
                values = [self.agent_id, config_type] + list(fields.values())
                cursor.execute(
                    f"INSERT INTO email_configs ({', '.join(columns)}) VALUES ({placeholders})",
                    values
                )

            conn.commit()
            return True

    def get_config(self) -> Optional[Dict[str, Any]]:
        """获取配置 - 返回混合模式配置"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM email_configs WHERE agent_id = ?",
                (self.agent_id,)
            )
            rows = cursor.fetchall()

            if not rows:
                return None

            config = {}
            for row in rows:
                row_dict = dict(row)
                config_type = row_dict['config_type']

                # 统一返回混合模式结构
                # 敏感字段解密
                config['hybrid'] = {
                    'provider': row_dict.get('provider', 'custom'),
                    'email': row_dict.get('email'),
                    'display_name': row_dict.get('display_name'),
                    'receive_protocol': row_dict.get('receive_protocol', 'pop3'),
                    'smtp': {
                        'host': row_dict.get('smtp_host'),
                        'port': row_dict.get('smtp_port'),
                        'username': row_dict.get('smtp_username'),
                        'password': _decrypt_field(row_dict.get('smtp_password')),
                        'use_tls': bool(row_dict.get('smtp_use_tls', 1)),
                    },
                    'imap': {
                        'host': row_dict.get('receive_host'),
                        'port': row_dict.get('receive_port'),
                        'username': row_dict.get('receive_username'),
                        'password': _decrypt_field(row_dict.get('receive_password')),
                        'use_ssl': bool(row_dict.get('receive_use_ssl', 1)),
                    },
                    'api_key': _decrypt_field(row_dict.get('api_key')),
                    'inbox_id': row_dict.get('inbox_id'),
                    'forwarding': bool(row_dict.get('forwarding', 1)),
                }
                config['updated_at'] = row_dict.get('updated_at')

            return config

    def delete_config(self) -> bool:
        """删除配置"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM email_configs WHERE agent_id = ?",
                (self.agent_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    # ── 收件箱操作 ────────────────────────────────────────────────────────────

    def get_inbox(self, folder: str = 'inbox', page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """获取收件箱邮件"""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # 总数
            cursor.execute(
                "SELECT COUNT(*) as total FROM inbox WHERE agent_id = ? AND folder = ?",
                (self.agent_id, folder)
            )
            total = cursor.fetchone()['total']

            # 分页数据
            offset = (page - 1) * page_size
            cursor.execute(
                """
                SELECT * FROM inbox
                WHERE agent_id = ? AND folder = ?
                ORDER BY date DESC
                LIMIT ? OFFSET ?
                """,
                (self.agent_id, folder, page_size, offset)
            )
            rows = cursor.fetchall()

            return {
                'total': total,
                'page': page,
                'page_size': page_size,
                'items': [dict(row) for row in rows]
            }

    def save_inbox_email(self, data: Dict[str, Any]) -> int:
        """保存收件箱邮件"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO inbox (agent_id, message_id, subject, sender_name, sender_email, recipient, cc, bcc,
                    body, body_html, editor_mode, attachments, date, folder, labels)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (self.agent_id, data.get('message_id'), data.get('subject'), data.get('sender_name'),
                 data.get('sender_email'), data.get('recipient'), data.get('cc'), data.get('bcc'),
                 data.get('body'), data.get('body_html'), data.get('editor_mode', 'plain'),
                 json.dumps(data.get('attachments', [])), data.get('date'), data.get('folder', 'inbox'),
                 data.get('labels'))
            )
            conn.commit()
            return cursor.lastrowid

    def mark_agent_read(self, email_id: int, is_read: bool = True) -> bool:
        """标记Agent已读状态"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE inbox SET is_agent_read = ? WHERE id = ? AND agent_id = ?",
                (1 if is_read else 0, email_id, self.agent_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def mark_replied(self, email_id: int, reply_content: str) -> bool:
        """标记Agent回复状态"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE inbox SET is_replied = 1, reply_content = ? WHERE id = ? AND agent_id = ?",
                (reply_content, email_id, self.agent_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def archive_emails(self, email_ids: List[int]) -> bool:
        """归档邮件"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            placeholders = ', '.join(['?' for _ in email_ids])
            cursor.execute(
                f"UPDATE inbox SET folder = 'archive' WHERE id IN ({placeholders}) AND agent_id = ?",
                email_ids + [self.agent_id]
            )
            conn.commit()
            return cursor.rowcount > 0

    def move_to_trash(self, item_type: str, item_ids: List[int]) -> bool:
        """移动到回收站"""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            for item_id in item_ids:
                # 获取原数据
                if item_type == 'inbox':
                    cursor.execute("SELECT * FROM inbox WHERE id = ?", (item_id,))
                elif item_type == 'sent':
                    cursor.execute("SELECT * FROM sent WHERE id = ?", (item_id,))
                elif item_type == 'drafts':
                    cursor.execute("SELECT * FROM drafts WHERE id = ?", (item_id,))
                elif item_type == 'contact':
                    cursor.execute("SELECT * FROM contacts WHERE id = ?", (item_id,))
                else:
                    continue

                row = cursor.fetchone()
                if row:
                    # 备份到回收站
                    cursor.execute(
                        "INSERT INTO trash (agent_id, item_type, original_id, data) VALUES (?, ?, ?, ?)",
                        (self.agent_id, item_type, item_id, json.dumps(dict(row)))
                    )

                    # 删除原表数据
                    if item_type == 'inbox':
                        cursor.execute("DELETE FROM inbox WHERE id = ?", (item_id,))
                    elif item_type == 'sent':
                        cursor.execute("DELETE FROM sent WHERE id = ?", (item_id,))
                    elif item_type == 'drafts':
                        cursor.execute("DELETE FROM drafts WHERE id = ?", (item_id,))
                    elif item_type == 'contact':
                        cursor.execute("DELETE FROM contacts WHERE id = ?", (item_id,))

            conn.commit()
            return True

    # ── 发件箱操作 ────────────────────────────────────────────────────────────

    def get_sent(self, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """获取发件箱邮件"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) as total FROM sent WHERE agent_id = ?",
                (self.agent_id,)
            )
            total = cursor.fetchone()['total']

            offset = (page - 1) * page_size
            cursor.execute(
                """
                SELECT * FROM sent
                WHERE agent_id = ?
                ORDER BY sent_at DESC
                LIMIT ? OFFSET ?
                """,
                (self.agent_id, page_size, offset)
            )
            rows = cursor.fetchall()

            return {
                'total': total,
                'page': page,
                'page_size': page_size,
                'items': [dict(row) for row in rows]
            }

    def save_sent(self, data: Dict[str, Any]) -> int:
        """保存已发送邮件"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sent (agent_id, message_id, subject, recipient, cc, bcc, body, body_html,
                    editor_mode, attachments, status, sent_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (self.agent_id, data.get('message_id'), data.get('subject'), data.get('recipient'),
                 data.get('cc'), data.get('bcc'), data.get('body'), data.get('body_html'),
                 data.get('editor_mode', 'plain'), json.dumps(data.get('attachments', [])),
                 data.get('status', 'sent'), data.get('sent_at'))
            )
            conn.commit()
            return cursor.lastrowid

    # ── 草稿箱操作 ────────────────────────────────────────────────────────────

    def get_drafts(self, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """获取草稿箱"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) as total FROM drafts WHERE agent_id = ?",
                (self.agent_id,)
            )
            total = cursor.fetchone()['total']

            offset = (page - 1) * page_size
            cursor.execute(
                """
                SELECT * FROM drafts
                WHERE agent_id = ?
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (self.agent_id, page_size, offset)
            )
            rows = cursor.fetchall()

            return {
                'total': total,
                'page': page,
                'page_size': page_size,
                'items': [dict(row) for row in rows]
            }

    def save_draft(self, draft_id: Optional[int], data: Dict[str, Any]) -> int:
        """保存草稿"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if draft_id:
                cursor.execute(
                    """
                    UPDATE drafts SET subject = ?, recipient = ?, cc = ?, bcc = ?, body = ?, body_html = ?,
                        editor_mode = ?, attachments = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND agent_id = ?
                    """,
                    (data.get('subject'), data.get('recipient'), data.get('cc'), data.get('bcc'),
                     data.get('body'), data.get('body_html'), data.get('editor_mode', 'plain'),
                     json.dumps(data.get('attachments', [])), draft_id, self.agent_id)
                )
                if cursor.rowcount > 0:
                    conn.commit()
                    return draft_id

            cursor.execute(
                """
                INSERT INTO drafts (agent_id, subject, recipient, cc, bcc, body, body_html, editor_mode, attachments)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (self.agent_id, data.get('subject'), data.get('recipient'), data.get('cc'),
                 data.get('bcc'), data.get('body'), data.get('body_html'),
                 data.get('editor_mode', 'plain'), json.dumps(data.get('attachments', [])))
            )
            conn.commit()
            return cursor.lastrowid

    def delete_drafts(self, draft_ids: List[int]) -> bool:
        """删除草稿"""
        return self.move_to_trash('drafts', draft_ids)

    # ── 联系人操作 ────────────────────────────────────────────────────────────

    def get_contacts(self, group: Optional[str] = None, search: Optional[str] = None,
                     page: int = 1, page_size: int = 15) -> Dict[str, Any]:
        """获取联系人列表"""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            where_clause = "agent_id = ?"
            params = [self.agent_id]

            if group and group != 'all':
                where_clause += " AND group_name = ?"
                params.append(group)

            if search:
                where_clause += " AND (name LIKE ? OR email LIKE ? OR company LIKE ?)"
                search_pattern = f"%{search}%"
                params.extend([search_pattern, search_pattern, search_pattern])

            # 总数
            cursor.execute(f"SELECT COUNT(*) as total FROM contacts WHERE {where_clause}", params)
            total = cursor.fetchone()['total']

            # 分页数据
            offset = (page - 1) * page_size
            cursor.execute(
                f"""
                SELECT * FROM contacts
                WHERE {where_clause}
                ORDER BY name ASC
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset]
            )
            rows = cursor.fetchall()

            return {
                'total': total,
                'page': page,
                'page_size': page_size,
                'items': [dict(row) for row in rows]
            }

    def create_contact(self, data: Dict[str, Any]) -> int:
        """创建联系人"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO contacts (agent_id, name, phone, email, company, website, notes, group_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (self.agent_id, data.get('name'), data.get('phone'), data.get('email'),
                 data.get('company'), data.get('website'), data.get('notes'),
                 data.get('group_name', 'default'))
            )
            conn.commit()
            return cursor.lastrowid

    def update_contact(self, contact_id: int, data: Dict[str, Any]) -> bool:
        """更新联系人"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE contacts
                SET name = ?, phone = ?, email = ?, company = ?, website = ?, notes = ?,
                    group_name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND agent_id = ?
                """,
                (data.get('name'), data.get('phone'), data.get('email'),
                 data.get('company'), data.get('website'), data.get('notes'),
                 data.get('group_name', 'default'), contact_id, self.agent_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_contacts(self, contact_ids: List[int]) -> bool:
        """批量删除联系人（移动到回收站）"""
        return self.move_to_trash('contact', contact_ids)

    def share_contact(self, contact_id: int, target_agent_ids: List[str]) -> bool:
        """共享联系人给其他Agent"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT shared_with FROM contacts WHERE id = ? AND agent_id = ?",
                (contact_id, self.agent_id)
            )
            row = cursor.fetchone()

            existing = json.loads(row['shared_with']) if row and row['shared_with'] else []
            new_shared = list(set(existing + target_agent_ids))

            cursor.execute(
                "UPDATE contacts SET shared_with = ? WHERE id = ? AND agent_id = ?",
                (json.dumps(new_shared), contact_id, self.agent_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_contact_groups(self) -> List[Dict[str, Any]]:
        """获取联系人分组"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM contact_groups WHERE agent_id = ? ORDER BY name",
                (self.agent_id,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def create_contact_group(self, name: str) -> int:
        """创建联系人分组"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO contact_groups (agent_id, name) VALUES (?, ?)",
                    (self.agent_id, name)
                )
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                return 0

    def delete_contact_group(self, group_id: int) -> bool:
        """删除联系人分组"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # 将分组下的联系人移到default
            cursor.execute(
                "UPDATE contacts SET group_name = 'default' WHERE group_name = (SELECT name FROM contact_groups WHERE id = ?) AND agent_id = ?",
                (group_id, self.agent_id)
            )
            cursor.execute(
                "DELETE FROM contact_groups WHERE id = ? AND agent_id = ?",
                (group_id, self.agent_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    # ── 回收站操作 ────────────────────────────────────────────────────────────

    def get_trash(self, item_type: Optional[str] = None, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """获取回收站内容"""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            where_clause = "agent_id = ?"
            params = [self.agent_id]

            if item_type:
                where_clause += " AND item_type = ?"
                params.append(item_type)

            cursor.execute(f"SELECT COUNT(*) as total FROM trash WHERE {where_clause}", params)
            total = cursor.fetchone()['total']

            offset = (page - 1) * page_size
            cursor.execute(
                f"""
                SELECT * FROM trash
                WHERE {where_clause}
                ORDER BY deleted_at DESC
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset]
            )
            rows = cursor.fetchall()

            # 解析data字段
            items = []
            for row in rows:
                item = dict(row)
                try:
                    item.update(json.loads(item.get('data', '{}')))
                except:
                    pass
                items.append(item)

            return {
                'total': total,
                'page': page,
                'page_size': page_size,
                'items': items
            }

    def restore_from_trash(self, trash_ids: List[int]) -> bool:
        """从回收站恢复"""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            for trash_id in trash_ids:
                cursor.execute(
                    "SELECT * FROM trash WHERE id = ? AND agent_id = ?",
                    (trash_id, self.agent_id)
                )
                row = cursor.fetchone()

                if not row:
                    continue

                data = json.loads(row['data'])
                item_type = row['item_type']

                # 恢复到原表
                if item_type == 'contact':
                    cursor.execute(
                        """
                        INSERT INTO contacts (agent_id, name, phone, email, company, website, notes, group_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (self.agent_id, data.get('name'), data.get('phone'), data.get('email'),
                         data.get('company'), data.get('website'), data.get('notes'),
                         data.get('group_name', 'default'))
                    )
                elif item_type == 'inbox':
                    cursor.execute(
                        """
                        INSERT INTO inbox (agent_id, message_id, subject, sender_name, sender_email, recipient,
                            body, body_html, date, folder)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (self.agent_id, data.get('message_id'), data.get('subject'),
                         data.get('sender_name'), data.get('sender_email'), data.get('recipient'),
                         data.get('body'), data.get('body_html'), data.get('date'), data.get('folder', 'inbox'))
                    )
                elif item_type == 'sent':
                    cursor.execute(
                        """
                        INSERT INTO sent (agent_id, message_id, subject, recipient, body, body_html, status, sent_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (self.agent_id, data.get('message_id'), data.get('subject'),
                         data.get('recipient'), data.get('body'), data.get('body_html'),
                         data.get('status', 'sent'), data.get('sent_at'))
                    )
                elif item_type == 'drafts':
                    cursor.execute(
                        """
                        INSERT INTO drafts (agent_id, subject, recipient, body, body_html, editor_mode, attachments)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (self.agent_id, data.get('subject'), data.get('recipient'),
                         data.get('body'), data.get('body_html'), data.get('editor_mode', 'plain'),
                         data.get('attachments', '[]'))
                    )

                # 删除回收站记录
                cursor.execute("DELETE FROM trash WHERE id = ?", (trash_id,))

            conn.commit()
            return True

    def permanent_delete(self, trash_ids: List[int]) -> bool:
        """永久删除"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            placeholders = ', '.join(['?' for _ in trash_ids])
            cursor.execute(
                f"DELETE FROM trash WHERE id IN ({placeholders}) AND agent_id = ?",
                trash_ids + [self.agent_id]
            )
            conn.commit()
            return cursor.rowcount > 0

    def clean_old_trash(self, days: int = 30) -> int:
        """清理过期回收站数据"""
        # 校验 days 为整数，防止 SQL 注入
        if not isinstance(days, int) or days < 1 or days > 3650:
            raise ValueError("days must be an integer between 1 and 3650")
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # 使用参数绑定传递 days，避免 SQL 注入
            cursor.execute(
                "DELETE FROM trash WHERE agent_id = ? AND deleted_at < datetime('now', '-' || ? || ' days')",
                (self.agent_id, str(days))
            )
            conn.commit()
            return cursor.rowcount

    # ── 备份操作 ────────────────────────────────────────────────────────────

    def backup(self) -> Dict[str, Any]:
        """备份数据库到bak目录"""
        import shutil
        from datetime import datetime

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"agentmail_backup_{timestamp}.db"
        backup_path = self.bak_dir / backup_name

        # 复制数据库文件
        shutil.copy2(str(self.db_path), str(backup_path))

        # 清理旧备份(保留最近10个)
        backups = sorted(self.bak_dir.glob('agentmail_backup_*.db'), key=lambda p: p.stat().st_mtime)
        for old_backup in backups[:-10]:
            old_backup.unlink()

        # 重新获取备份列表数量（清理后）
        total_backups = len(list(self.bak_dir.glob('agentmail_backup_*.db')))

        return {
            'success': True,
            'backup_path': str(backup_path),
            'timestamp': timestamp,
            'total_backups': total_backups
        }

    def get_backup_list(self) -> List[Dict[str, Any]]:
        """获取备份列表"""
        backups = []
        for p in sorted(self.bak_dir.glob('agentmail_backup_*.db'), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = p.stat()
            backups.append({
                'name': p.name,
                'path': str(p),
                'size': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        return backups

    def uninstall(self, keep_data: bool = False) -> bool:
        """卸载插件 - 清理数据库和文件"""
        import shutil
        try:
            if not keep_data:
                # 删除整个 mail 目录
                if self.db_dir.exists():
                    shutil.rmtree(str(self.db_dir))
            else:
                # 只删除数据库文件，保留 bak 和 files
                if self.db_path.exists():
                    self.db_path.unlink()
            # 从缓存中移除
            if self.agent_id in _db_cache:
                del _db_cache[self.agent_id]
            return True
        except Exception as e:
            logger.error(f"卸载失败: {e}")
            return False


# 全局数据库实例缓存
_db_cache: Dict[str, AgentDatabase] = {}


def get_db(agent_id: str) -> AgentDatabase:
    """获取Agent数据库实例 - 自动创建"""
    if agent_id not in _db_cache:
        _db_cache[agent_id] = AgentDatabase(agent_id)
    return _db_cache[agent_id]


def get_all_agent_dbs() -> Dict[str, AgentDatabase]:
    """获取所有Agent数据库实例"""
    agents_dir = Path.home() / ".qwenpaw" / "agents"
    if not agents_dir.exists():
        return {}

    dbs = {}
    for agent_dir in agents_dir.iterdir():
        if agent_dir.is_dir():
            agent_id = agent_dir.name
            db_path = agent_dir / "mail" / "agentmail.db"
            if db_path.exists():
                dbs[agent_id] = get_db(agent_id)
    return dbs