"""
AgentMail Plugin - Database Module

Agent隔离的SQLite数据库管理 - 每个Agent独立数据库
"""

import sqlite3
import json
import os
import re
import base64
import logging
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

_QWENPAW_API_BASE = os.environ.get("QWENPAW_API_BASE", "http://localhost:8088")
_qwenpaw_working_dir = os.environ.get("QWENPAW_WORKING_DIR", os.environ.get("COPAW_WORKING_DIR", ""))
if _qwenpaw_working_dir:
    _QWENPAW_HOME = Path(_qwenpaw_working_dir).expanduser().resolve()
else:
    _QWENPAW_HOME = Path.home() / ".qwenpaw"

_agent_workspace_cache: Dict[str, str] = {}


def get_agent_workspace_dir(agent_id: str) -> Optional[str]:
    """获取 Agent 的 workspace_dir（对外统一的接口）

    优先级：
    1. QwenPaw API /api/agents 查询（从配置文件读取 workspace_dir）
    2. 环境变量 QWENPAW_WORKING_DIR → {WORKING_DIR}/workspaces/{agent_id}
    3. 默认路径 ~/.qwenpaw/workspaces/{agent_id}
    """
    if agent_id in _agent_workspace_cache:
        return _agent_workspace_cache[agent_id]

    result = _try_api_workspace(agent_id)
    if result and os.path.isdir(result):
        _agent_workspace_cache[agent_id] = result
        return result

    result = str(_QWENPAW_HOME / "workspaces" / agent_id)
    if os.path.isdir(result):
        _agent_workspace_cache[agent_id] = result
        return result

    _agent_workspace_cache[agent_id] = result
    logger.warning(f"[AgentMail] Agent '{agent_id}' workspace not found, using: {result}")
    return result


def _try_api_workspace(agent_id: str) -> Optional[str]:
    """通过 QwenPaw API 获取 Agent 的 workspace_dir"""
    try:
        url = f"{_QWENPAW_API_BASE}/api/agents"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            agents = data.get("agents", [])
            for agent in agents:
                aid = agent.get("id", "")
                ws_dir = agent.get("workspace_dir", "")
                if ws_dir:
                    _agent_workspace_cache[aid] = ws_dir
            result = _agent_workspace_cache.get(agent_id)
            if result:
                logger.info(f"[AgentMail] Agent '{agent_id}' workspace_dir (API): {result}")
                return result
    except Exception as e:
        logger.warning(f"[AgentMail] Failed to get workspace_dir from QwenPaw API: {e}")

    return None

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


class AgentDatabase:
    """Agent隔离的数据库管理器 - 每个Agent独立数据库文件"""

    # 允许的 Agent ID 字符：字母、数字、下划线、连字符
    _AGENT_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_.-]+$')

    def __init__(self, agent_id: str):
        if not agent_id or not self._AGENT_ID_PATTERN.match(agent_id):
            raise ValueError("agent_id must contain only letters, numbers, underscores, dots, and hyphens")
        if '..' in agent_id or agent_id.startswith('.') or agent_id.startswith('-'):
            raise ValueError("agent_id contains invalid sequence")
        self.agent_id = agent_id

        workspace_dir = get_agent_workspace_dir(agent_id)
        if workspace_dir and os.path.isdir(workspace_dir):
            self.db_dir = Path(workspace_dir) / "mail"
            logger.info(f"[AgentMail] Using workspace-based path for '{agent_id}': {self.db_dir}")
        else:
            self.db_dir = _QWENPAW_HOME / "workspaces" / agent_id / "mail"
            logger.info(f"[AgentMail] Using fallback path for '{agent_id}': {self.db_dir}")

        self._migrate_from_old_path(agent_id)

        self.db_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        self.db_path = self.db_dir / "agentmail.db"
        self.bak_dir = self.db_dir / "bak"
        self.files_dir = self.db_dir / "files"
        self.bak_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        self.files_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        self._init_db()
        if self.db_path.exists():
            os.chmod(self.db_path, 0o755)

    def _migrate_from_old_path(self, agent_id: str):
        """从旧路径 {QWENPAW_HOME}/agents/{agent_id}/mail/ 迁移数据到新路径 {workspace_dir}/mail/"""
        old_dir = _QWENPAW_HOME / "agents" / agent_id / "mail"
        if self.db_dir == old_dir:
            return
        if not old_dir.exists():
            return
        if self.db_dir.exists() and (self.db_dir / "agentmail.db").exists():
            return

        logger.info(f"[AgentMail] Migrating data from {old_dir} to {self.db_dir}")
        try:
            import shutil
            self.db_dir.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            shutil.copytree(str(old_dir), str(self.db_dir), dirs_exist_ok=True)
            logger.info(f"[AgentMail] Migration complete for '{agent_id}'")
        except Exception as e:
            logger.error(f"[AgentMail] Migration failed for '{agent_id}': {e}")

    def _init_db(self):
        """初始化数据库表结构"""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # 邮件配置表 - 统一配置（SMTP + IMAP/POP3）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS email_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
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
                    receive_protocol TEXT DEFAULT 'imap',
                    auth_type TEXT DEFAULT 'basic',
                    oauth2_client_id TEXT,
                    oauth2_client_secret TEXT,
                    oauth2_access_token TEXT,
                    oauth2_refresh_token TEXT,
                    oauth2_token_expires_at REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(agent_id)
                )
            """)

            # 迁移旧表结构（如果存在 config_type 列，说明是旧版数据库）
            self._migrate_old_config_table(cursor)

            # 添加 OAuth2 字段（如果不存在）
            self._add_oauth2_columns(cursor)

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

    def _migrate_old_config_table(self, cursor):
        """迁移旧版 email_configs 表结构（移除 config_type/api_key/inbox_id/forwarding 列）"""
        try:
            cursor.execute("PRAGMA table_info(email_configs)")
            columns = {row['name'] for row in cursor.fetchall()}

            if 'config_type' not in columns:
                # 新版表结构，无需迁移
                return

            logger.info(f"[Migration] 检测到旧版 email_configs 表结构，开始迁移...")

            # 创建新表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS email_configs_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
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
                    receive_protocol TEXT DEFAULT 'imap',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(agent_id)
                )
            """)

            # 按 hybrid > traditional > agentmail 优先级迁移数据
            # 1. 优先迁移 hybrid 类型
            cursor.execute("""
                INSERT OR IGNORE INTO email_configs_new
                    (agent_id, provider, email, display_name,
                     smtp_host, smtp_port, smtp_username, smtp_password, smtp_use_tls,
                     receive_host, receive_port, receive_username, receive_password, receive_use_ssl,
                     receive_protocol, created_at, updated_at)
                SELECT agent_id, provider, email, display_name,
                       smtp_host, smtp_port, smtp_username, smtp_password, smtp_use_tls,
                       receive_host, receive_port, receive_username, receive_password, receive_use_ssl,
                       receive_protocol, created_at, updated_at
                FROM email_configs
                WHERE config_type = 'hybrid'
            """)

            # 2. 其次迁移 traditional 类型（仅 agent_id 未被 hybrid 覆盖的）
            cursor.execute("""
                INSERT OR IGNORE INTO email_configs_new
                    (agent_id, provider, email, display_name,
                     smtp_host, smtp_port, smtp_username, smtp_password, smtp_use_tls,
                     receive_host, receive_port, receive_username, receive_password, receive_use_ssl,
                     receive_protocol, created_at, updated_at)
                SELECT agent_id, provider, email, display_name,
                       smtp_host, smtp_port, smtp_username, smtp_password, smtp_use_tls,
                       receive_host, receive_port, receive_username, receive_password, receive_use_ssl,
                       receive_protocol, created_at, updated_at
                FROM email_configs
                WHERE config_type = 'traditional'
                  AND agent_id NOT IN (SELECT agent_id FROM email_configs_new)
            """)

            # 3. 最后迁移 agentmail 类型（仅 agent_id 未被覆盖的）
            cursor.execute("""
                INSERT OR IGNORE INTO email_configs_new
                    (agent_id, provider, email, display_name,
                     smtp_host, smtp_port, smtp_username, smtp_password, smtp_use_tls,
                     receive_host, receive_port, receive_username, receive_password, receive_use_ssl,
                     receive_protocol, created_at, updated_at)
                SELECT agent_id, provider, email, display_name,
                       smtp_host, smtp_port, smtp_username, smtp_password, smtp_use_tls,
                       receive_host, receive_port, receive_username, receive_password, receive_use_ssl,
                       receive_protocol, created_at, updated_at
                FROM email_configs
                WHERE config_type = 'agentmail'
                  AND agent_id NOT IN (SELECT agent_id FROM email_configs_new)
            """)

            # 替换旧表
            cursor.execute("DROP TABLE email_configs")
            cursor.execute("ALTER TABLE email_configs_new RENAME TO email_configs")

            logger.info("[Migration] email_configs 表迁移完成")
        except Exception as e:
            logger.error(f"[Migration] email_configs 表迁移失败: {e}")

    def _add_oauth2_columns(self, cursor):
        """为旧版 email_configs 表添加 OAuth2 字段"""
        try:
            cursor.execute("PRAGMA table_info(email_configs)")
            columns = {row['name'] for row in cursor.fetchall()}

            oauth2_columns = {
                'auth_type': 'TEXT DEFAULT \'basic\'',
                'oauth2_client_id': 'TEXT',
                'oauth2_client_secret': 'TEXT',
                'oauth2_access_token': 'TEXT',
                'oauth2_refresh_token': 'TEXT',
                'oauth2_token_expires_at': 'REAL DEFAULT 0',
            }

            for col_name, col_type in oauth2_columns.items():
                if col_name not in columns:
                    cursor.execute(f"ALTER TABLE email_configs ADD COLUMN {col_name} {col_type}")
                    logger.info(f"[Migration] Added column {col_name} to email_configs")

        except Exception as e:
            logger.error(f"[Migration] Failed to add OAuth2 columns: {e}")

    # ── 配置操作 ─────────────────────────────────────────────────────────────

    def save_config(self, data: Dict[str, Any]) -> bool:
        """保存邮件配置（SMTP + IMAP/POP3）"""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # 检查是否已存在
            cursor.execute(
                "SELECT id FROM email_configs WHERE agent_id = ?",
                (self.agent_id,)
            )
            existing = cursor.fetchone()

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
                'receive_protocol': data.get('receive_protocol', 'imap'),
                'auth_type': data.get('auth_type', 'basic'),
                'oauth2_client_id': data.get('oauth2', {}).get('client_id'),
                'oauth2_client_secret': _encrypt_field(data.get('oauth2', {}).get('client_secret')),
                'oauth2_access_token': _encrypt_field(data.get('oauth2', {}).get('access_token')),
                'oauth2_refresh_token': _encrypt_field(data.get('oauth2', {}).get('refresh_token')),
                'oauth2_token_expires_at': data.get('oauth2', {}).get('token_expires_at', 0),
            }

            if existing:
                # 更新
                set_clause = ', '.join([f"{k} = ?" for k in fields.keys()])
                values = list(fields.values()) + [self.agent_id]
                cursor.execute(
                    f"UPDATE email_configs SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE agent_id = ?",
                    values
                )
            else:
                # 插入
                columns = ['agent_id'] + list(fields.keys())
                placeholders = ', '.join(['?' for _ in columns])
                values = [self.agent_id] + list(fields.values())
                cursor.execute(
                    f"INSERT INTO email_configs ({', '.join(columns)}) VALUES ({placeholders})",
                    values
                )

            conn.commit()
            return True

    def get_config(self) -> Optional[Dict[str, Any]]:
        """获取邮件配置 - 直接返回配置（不再包裹在 hybrid 键中）"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM email_configs WHERE agent_id = ?",
                (self.agent_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            row_dict = dict(row)

            return {
                'provider': row_dict.get('provider', 'custom'),
                'email': row_dict.get('email'),
                'display_name': row_dict.get('display_name'),
                'receive_protocol': row_dict.get('receive_protocol', 'imap'),
                'auth_type': row_dict.get('auth_type', 'basic'),
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
                'oauth2': {
                    'client_id': row_dict.get('oauth2_client_id'),
                    'client_secret': _decrypt_field(row_dict.get('oauth2_client_secret')),
                    'access_token': _decrypt_field(row_dict.get('oauth2_access_token')),
                    'refresh_token': _decrypt_field(row_dict.get('oauth2_refresh_token')),
                    'token_expires_at': row_dict.get('oauth2_token_expires_at', 0),
                },
                'updated_at': row_dict.get('updated_at'),
            }

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

    def save_oauth2_tokens(self, access_token: str, refresh_token: str, expires_at: float) -> bool:
        """保存 OAuth2 令牌"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE email_configs 
                   SET oauth2_access_token = ?, oauth2_refresh_token = ?, oauth2_token_expires_at = ?,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE agent_id = ?""",
                (_encrypt_field(access_token), _encrypt_field(refresh_token), expires_at, self.agent_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_oauth2_status(self) -> Dict[str, Any]:
        """获取 OAuth2 授权状态"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT auth_type, oauth2_client_id, oauth2_access_token, oauth2_token_expires_at FROM email_configs WHERE agent_id = ?",
                (self.agent_id,)
            )
            row = cursor.fetchone()
            if not row:
                return {"auth_type": "basic", "authorized": False}

            auth_type = row['auth_type'] or 'basic'
            client_id = row['oauth2_client_id']
            access_token = _decrypt_field(row['oauth2_access_token'])
            expires_at = row['oauth2_token_expires_at'] or 0

            return {
                "auth_type": auth_type,
                "client_id": client_id,
                "authorized": bool(access_token and client_id),
                "token_expired": time.time() > expires_at if expires_at else True,
            }

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

    def get_inbox_by_message_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """根据message_id查询收件箱邮件（用于去重）"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM inbox WHERE message_id = ? AND agent_id = ?",
                (message_id, self.agent_id)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

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

    def save_sent_email(self, to_email: str, subject: str, body: str) -> int:
        """简化版保存已发送邮件"""
        from datetime import datetime
        return self.save_sent({
            'message_id': f"sent_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'subject': subject,
            'recipient': to_email,
            'body': body,
            'status': 'sent',
            'sent_at': datetime.now().isoformat()
        })

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
        """共享联系人给其他Agent - 在目标Agent数据库中创建联系人副本"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM contacts WHERE id = ? AND agent_id = ?",
                (contact_id, self.agent_id)
            )
            row = cursor.fetchone()
            if not row:
                return False

            contact_data = dict(row)
            existing = json.loads(contact_data.get('shared_with') or '[]')
            new_shared = list(set(existing + target_agent_ids))

            cursor.execute(
                "UPDATE contacts SET shared_with = ? WHERE id = ? AND agent_id = ?",
                (json.dumps(new_shared), contact_id, self.agent_id)
            )
            conn.commit()

        for target_id in target_agent_ids:
            try:
                target_db = AgentDatabase(target_id)
                target_db.create_contact({
                    'name': contact_data.get('name', ''),
                    'phone': contact_data.get('phone'),
                    'email': contact_data.get('email', ''),
                    'company': contact_data.get('company'),
                    'website': contact_data.get('website'),
                    'notes': f"Shared by {self.agent_id}",
                    'group_name': 'default',
                })
                logger.info(f"Shared contact '{contact_data.get('name')}' to agent {target_id}")
            except Exception as e:
                logger.error(f"Failed to share contact to {target_id}: {e}")

        return True

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

    def update_contact_group(self, group_id: int, new_name: str) -> bool:
        """更新联系人分组名称"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM contact_groups WHERE id = ? AND agent_id = ?",
                (group_id, self.agent_id)
            )
            row = cursor.fetchone()
            if not row:
                return False
            old_name = row['name']
            cursor.execute(
                "UPDATE contacts SET group_name = ? WHERE group_name = ? AND agent_id = ?",
                (new_name, old_name, self.agent_id)
            )
            try:
                cursor.execute(
                    "UPDATE contact_groups SET name = ? WHERE id = ? AND agent_id = ?",
                    (new_name, group_id, self.agent_id)
                )
                conn.commit()
                return cursor.rowcount > 0
            except sqlite3.IntegrityError:
                return False

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
    """获取所有Agent数据库实例 - 从QwenPaw API获取Agent列表"""
    dbs = {}
    try:
        url = f"{_QWENPAW_API_BASE}/api/agents"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for agent in data.get("agents", []):
                agent_id = agent.get("id", "")
                if agent_id:
                    db = get_db(agent_id)
                    if db.db_path.exists():
                        dbs[agent_id] = db
    except Exception as e:
        logger.warning(f"[AgentMail] Failed to get agents from API, scanning workspace directories: {e}")
        workspaces_dir = _QWENPAW_HOME / "workspaces"
        if workspaces_dir.exists():
            for ws_dir in workspaces_dir.iterdir():
                if ws_dir.is_dir():
                    db_path = ws_dir / "mail" / "agentmail.db"
                    if db_path.exists():
                        dbs[ws_dir.name] = get_db(ws_dir.name)
    return dbs