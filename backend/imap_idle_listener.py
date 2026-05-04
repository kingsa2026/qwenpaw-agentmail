"""
AgentMail Plugin - IMAP IDLE Push Listener

通过 IMAP IDLE (RFC 2177) 实现新邮件实时推送
新邮件到达时自动保存到数据库并触发 Agent 通知
"""

import imaplib
import email
import threading
import time
import logging
import select
import json
from email.header import decode_header
from email.utils import parseaddr
from typing import Dict, Any, Optional, Callable
from pathlib import Path

from database import get_db

logger = logging.getLogger(__name__)


def _decode_str(s: str) -> str:
    if not s:
        return ""
    decoded_parts = decode_header(s)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or 'utf-8', errors='replace'))
            except (LookupError, UnicodeDecodeError):
                result.append(part.decode('utf-8', errors='replace'))
        else:
            result.append(part)
    return ''.join(result)


def _get_email_body(msg: email.message.Message) -> tuple:
    body_text = ""
    body_html = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or 'utf-8'
                try:
                    text = payload.decode(charset, errors='replace')
                except (LookupError, UnicodeDecodeError):
                    text = payload.decode('utf-8', errors='replace')
                if content_type == "text/plain" and not body_text:
                    body_text = text
                elif content_type == "text/html" and not body_html:
                    body_html = text
            except Exception:
                continue
    else:
        content_type = msg.get_content_type()
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                try:
                    text = payload.decode(charset, errors='replace')
                except (LookupError, UnicodeDecodeError):
                    text = payload.decode('utf-8', errors='replace')
                if content_type == "text/plain":
                    body_text = text
                elif content_type == "text/html":
                    body_html = text
        except Exception:
            pass
    return body_text, body_html


class ImapIdleListener:
    """
    IMAP IDLE 推送监听器

    通过 IMAP IDLE 命令维持与服务器的长连接，
    当新邮件到达时服务器主动推送通知，
    监听器自动获取新邮件并保存到数据库。

    工作原理:
    1. 连接 IMAP 服务器并 SELECT INBOX
    2. 发送 IDLE 命令进入等待状态
    3. 服务器有新邮件时发送 EXISTS 响应
    4. 退出 IDLE，获取新邮件，保存到数据库
    5. 触发 Agent 通知回调
    6. 重新进入 IDLE 等待
    """

    IDLE_TIMEOUT = 25 * 60
    RECONNECT_DELAY = 30
    MAX_RECONNECT_DELAY = 300
    POLL_INTERVAL = 30

    def __init__(self, agent_id: str, config: Dict[str, Any],
                 on_new_email: Optional[Callable] = None):
        self.agent_id = agent_id
        self.config = config
        self.imap_config = config.get("imap", {})
        self.email_addr = config.get("email", "")
        self.auth_type = config.get("auth_type", "basic")
        self.on_new_email = on_new_email

        self._conn: Optional[imaplib.IMAP4_SSL] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_seen_count = 0
        self._reconnect_count = 0
        self._supports_idle = True

    @property
    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    def start(self) -> Dict[str, Any]:
        if self.is_running:
            return {"success": False, "error": "监听器已在运行"}

        if not self.imap_config.get("host") or not self.imap_config.get("password"):
            return {"success": False, "error": "IMAP配置不完整，无法启动监听"}

        self._running = True
        self._reconnect_count = 0
        self._thread = threading.Thread(
            target=self._listen_loop,
            name=f"imap-idle-{self.agent_id}",
            daemon=True
        )
        self._thread.start()
        logger.info(f"[IMAP IDLE] 监听器已启动: agent={self.agent_id}, email={self.email_addr}")
        return {"success": True, "message": f"IMAP IDLE 监听已启动: {self.email_addr}"}

    def stop(self) -> Dict[str, Any]:
        if not self._running:
            return {"success": False, "error": "监听器未在运行"}

        self._running = False
        try:
            if self._conn:
                self._conn.noop()
        except Exception:
            pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)

        logger.info(f"[IMAP IDLE] 监听器已停止: agent={self.agent_id}")
        return {"success": True, "message": "IMAP IDLE 监听已停止"}

    def _connect(self) -> bool:
        try:
            host = self.imap_config.get("host")
            port = self.imap_config.get("port", 993)
            username = self.imap_config.get("username", self.email_addr)
            password = self.imap_config.get("password")
            use_ssl = self.imap_config.get("use_ssl", True)

            if not host:
                logger.error("[IMAP IDLE] IMAP配置不完整")
                return False

            if use_ssl:
                self._conn = imaplib.IMAP4_SSL(host, port)
            else:
                self._conn = imaplib.IMAP4(host, port)

            if self.auth_type == "oauth2":
                access_token = self._get_oauth2_token()
                if not access_token:
                    logger.error("[IMAP IDLE] OAuth2令牌无效或已过期")
                    return False
                self._conn.authenticate('XOAUTH2', lambda x: f"user={username}\x01auth=Bearer {access_token}\x01\x01")
                logger.info(f"[IMAP IDLE] OAuth2登录成功: {username}@{host}")
            else:
                if not password:
                    logger.error("[IMAP IDLE] IMAP配置不完整")
                    return False
                self._conn.login(username, password)
                logger.info(f"[IMAP IDLE] 登录成功: {username}@{host}")

            if 'ID' not in imaplib.Commands:
                imaplib.Commands['ID'] = ('AUTH',)
            client_id = ('name', 'AgentMail', 'version', '2.0', 'vendor', 'qwenpaw')
            self._conn._simple_command('ID', '("' + '" "'.join(client_id) + '")')
            logger.info(f"[IMAP IDLE] ID命令已发送")

            status, data = self._conn.select("INBOX", readonly=True)
            if status != "OK":
                logger.error(f"[IMAP IDLE] SELECT INBOX 失败: {status} {data}")
                return False

            logger.info(f"[IMAP IDLE] SELECT INBOX 成功: {data}")

            status, data = self._conn.search(None, "ALL")
            if status == "OK" and data[0]:
                self._last_seen_count = len(data[0].split())
            else:
                self._last_seen_count = 0

            self._reconnect_count = 0
            logger.info(f"[IMAP IDLE] 连接成功: {self.email_addr}, 当前邮件数: {self._last_seen_count}")
            return True

        except imaplib.IMAP4.error as e:
            logger.error(f"[IMAP IDLE] IMAP错误: {e}")
            self._conn = None
            return False
        except Exception as e:
            logger.error(f"[IMAP IDLE] 连接失败: {e}")
            self._conn = None
            return False

    def _listen_loop(self):
        while self._running:
            try:
                if not self._connect():
                    delay = min(
                        self.RECONNECT_DELAY * (2 ** self._reconnect_count),
                        self.MAX_RECONNECT_DELAY
                    )
                    self._reconnect_count += 1
                    logger.warning(f"[IMAP IDLE] 连接失败，{delay}秒后重连...")
                    time.sleep(delay)
                    continue

                if not self._supports_idle:
                    self._poll_loop()
                else:
                    self._idle_loop()

            except Exception as e:
                logger.error(f"[IMAP IDLE] 监听循环异常: {e}")

            if self._running:
                delay = min(
                    self.RECONNECT_DELAY * (2 ** self._reconnect_count),
                    self.MAX_RECONNECT_DELAY
                )
                self._reconnect_count += 1
                logger.info(f"[IMAP IDLE] {delay}秒后重新连接...")
                time.sleep(delay)

        logger.info(f"[IMAP IDLE] 监听线程退出: agent={self.agent_id}")

    def _poll_loop(self):
        logger.info(f"[IMAP IDLE] 使用NOOP轮询模式: {self.email_addr} (间隔{self.POLL_INTERVAL}秒)")
        while self._running:
            try:
                time.sleep(self.POLL_INTERVAL)
                if not self._running or not self._conn:
                    break
                status, _ = self._conn.noop()
                if status != "OK":
                    logger.warning("[IMAP IDLE] NOOP失败，需要重连")
                    break
                status, data = self._conn.search(None, "ALL")
                if status != "OK":
                    break
                current_count = len(data[0].split()) if data[0] else 0
                if current_count > self._last_seen_count:
                    logger.info(f"[IMAP IDLE] 轮询检测到新邮件: {self.email_addr} ({self._last_seen_count}->{current_count})")
                    self._process_new_emails()
                    self._last_seen_count = current_count
            except (imaplib.IMAP4.error, OSError, ConnectionError) as e:
                logger.warning(f"[IMAP IDLE] 轮询连接异常: {e}")
                break

    def _idle_loop(self):
        while self._running:
            try:
                tag = self._conn._new_tag()
                self._conn.send(tag + b' IDLE\r\n')

                response = self._conn.readline()
                if b'+' not in response:
                    logger.warning(f"[IMAP IDLE] 服务器不支持IDLE，切换到轮询模式: {response}")
                    self._supports_idle = False
                    self._poll_loop()
                    break

                logger.debug(f"[IMAP IDLE] 进入IDLE等待: {self.email_addr}")

                while self._running:
                    try:
                        readable, _, _ = select.select(
                            [self._conn.sock], [], [],
                            min(self.IDLE_TIMEOUT, 60)
                        )

                        if readable:
                            data = self._conn.readline()
                            if not data:
                                logger.warning("[IMAP IDLE] 连接断开")
                                break

                            line = data.decode('utf-8', errors='replace').strip()

                            if 'EXISTS' in line or 'RECENT' in line:
                                logger.info(f"[IMAP IDLE] 检测到新邮件: {line}")
                                self._conn.send(b'DONE\r\n')
                                self._conn.readline()
                                self._process_new_emails()
                                break

                            elif 'EXPUNGE' in line:
                                pass

                            elif line.startswith(tag.decode()):
                                logger.debug("[IMAP IDLE] IDLE超时，重新进入")
                                break

                    except (select.error, OSError) as e:
                        logger.warning(f"[IMAP IDLE] select错误: {e}")
                        break

                if self._running:
                    try:
                        self._conn.noop()
                    except Exception:
                        break

            except (imaplib.IMAP4.error, OSError, ConnectionError) as e:
                logger.warning(f"[IMAP IDLE] 连接异常: {e}")
                break

    def _process_new_emails(self):
        try:
            status, data = self._conn.search(None, "ALL")
            if status != "OK" or not data[0]:
                return

            current_ids = data[0].split()
            current_count = len(current_ids)

            if current_count <= self._last_seen_count:
                self._last_seen_count = current_count
                return

            new_count = current_count - self._last_seen_count
            new_ids = current_ids[self._last_seen_count:]

            logger.info(f"[IMAP IDLE] 发现{new_count}封新邮件: {self.email_addr}")

            db = get_db(self.agent_id)

            for mid in new_ids:
                try:
                    status, msg_data = self._conn.fetch(mid, "(RFC822)")
                    if status != "OK":
                        continue

                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    message_id = msg.get("Message-ID", f"imap_idle_{mid.decode()}")
                    subject = _decode_str(msg.get("Subject", ""))

                    from_header = msg.get("From", "")
                    from_name, from_email = parseaddr(from_header)
                    from_name = _decode_str(from_name)

                    to_header = msg.get("To", "")
                    _, to_email = parseaddr(to_header)

                    date_str = msg.get("Date", "")
                    body_text, body_html = _get_email_body(msg)

                    existing = db.get_inbox_by_message_id(message_id)
                    if existing:
                        continue

                    db.save_inbox_email({
                        'message_id': message_id,
                        'subject': subject,
                        'sender_name': from_name,
                        'sender_email': from_email,
                        'recipient': to_email or self.email_addr,
                        'cc': msg.get("Cc", ""),
                        'bcc': msg.get("Bcc", ""),
                        'body': body_text[:10000],
                        'body_html': body_html[:50000] if body_html else None,
                        'date': date_str,
                        'folder': 'inbox',
                    })

                    logger.info(
                        f"[IMAP IDLE] 新邮件已保存: agent={self.agent_id}, "
                        f"from={from_email}, subject={subject}"
                    )

                    self._notify_agent(db, {
                        'message_id': message_id,
                        'subject': subject,
                        'sender_name': from_name,
                        'sender_email': from_email,
                        'body': body_text[:2000],
                    })

                except Exception as e:
                    logger.warning(f"[IMAP IDLE] 处理新邮件失败: {e}")
                    continue

            self._last_seen_count = current_count

            self._conn.select("INBOX")

        except Exception as e:
            logger.error(f"[IMAP IDLE] 处理新邮件异常: {e}")

    def _notify_agent(self, db, email_data: Dict[str, Any]):
        self._write_notification_file(email_data)
        self._inject_to_qwenpaw(email_data)
        if self.on_new_email:
            try:
                self.on_new_email(self.agent_id, email_data)
            except Exception as e:
                logger.error(f"[IMAP IDLE] 回调通知失败: {e}")

    def _get_oauth2_token(self) -> Optional[str]:
        """获取有效的 OAuth2 访问令牌"""
        try:
            from oauth2_handler import get_valid_access_token
            return get_valid_access_token(self.agent_id)
        except Exception as e:
            logger.error(f"[IMAP IDLE] 获取OAuth2令牌失败: {e}")
            return None

    def _write_notification_file(self, email_data: Dict[str, Any]):
        try:
            db = get_db(self.agent_id)
            mail_dir = Path(db.db_dir)
            context_file = mail_dir / "agentmail_new_email.json"

            notification = {
                "type": "new_email",
                "agent_id": self.agent_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "email": email_data
            }

            mail_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
            with open(context_file, 'w', encoding='utf-8') as f:
                json.dump(notification, f, ensure_ascii=False, indent=2)

            if context_file.exists():
                os.chmod(context_file, 0o755)

            logger.info(f"[IMAP IDLE] Agent通知已写入: {context_file}")

        except Exception as e:
            logger.error(f"[IMAP IDLE] 写入通知文件失败: {e}")

    def _inject_to_qwenpaw(self, email_data: Dict[str, Any]):
        try:
            import httpx

            subject = email_data.get('subject', '(无主题)')
            sender = email_data.get('sender_email', '未知发件人')
            sender_name = email_data.get('sender_name', '')
            body_preview = email_data.get('body', '')[:500]

            prompt = (
                f"**AgentMail**: 你收到一封新邮件！\n\n"
                f"📧 发件人: {sender_name} <{sender}>\n"
                f"📋 主题: {subject}\n"
                f"📝 正文预览:\n{body_preview}\n\n"
                f"请根据你的邮件规则决定是否回复。"
                f"你可以使用 `agentmail read-inbox` 命令查看完整邮件内容，"
                f"使用 `agentmail send` 命令回复邮件。"
            )

            request_payload = {
                "session_id": f"agentmail-{self.agent_id}-{int(time.time())}",
                "input": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": prompt}]
                    }
                ]
            }

            base_url = "http://127.0.0.1:8088/api"

            try:
                with httpx.Client(base_url=base_url, timeout=10) as client:
                    response = client.post(
                        "/agent/process/task",
                        json=request_payload,
                        headers={"X-Agent-Id": self.agent_id},
                    )
                    result = response.json()
                    task_id = result.get("task_id", "")
                    logger.info(
                        f"[IMAP IDLE] 已通过QwenPaw API通知Agent: "
                        f"agent={self.agent_id}, task_id={task_id}"
                    )
            except httpx.ConnectError:
                logger.warning("[IMAP IDLE] QwenPaw API不可用，跳过API通知")
            except Exception as e:
                logger.warning(f"[IMAP IDLE] QwenPaw API通知失败: {e}")

        except ImportError:
            logger.warning("[IMAP IDLE] httpx未安装，无法通过API通知Agent")
        except Exception as e:
            logger.error(f"[IMAP IDLE] 注入QwenPaw失败: {e}")


import os


class ListenerManager:
    """
    监听器管理器 - 管理所有 Agent 的 IMAP IDLE 监听器

    单例模式，全局管理所有监听器的生命周期
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._listeners: Dict[str, ImapIdleListener] = {}
            return cls._instance

    def start_listener(self, agent_id: str) -> Dict[str, Any]:
        if agent_id in self._listeners and self._listeners[agent_id].is_running:
            return {"success": False, "error": "该Agent的监听器已在运行"}

        db = get_db(agent_id)
        config = db.get_config()

        if not config:
            return {"success": False, "error": "邮件配置未找到，请先配置邮箱"}

        if not config.get("imap", {}).get("host"):
            return {"success": False, "error": "IMAP配置不完整"}

        listener = ImapIdleListener(agent_id, config)
        self._listeners[agent_id] = listener
        return listener.start()

    def stop_listener(self, agent_id: str) -> Dict[str, Any]:
        if agent_id not in self._listeners:
            return {"success": False, "error": "该Agent没有运行中的监听器"}

        result = self._listeners[agent_id].stop()
        del self._listeners[agent_id]
        return result

    def get_status(self, agent_id: str) -> Dict[str, Any]:
        if agent_id not in self._listeners:
            email_addr = None
            try:
                db = get_db(agent_id)
                config = db.get_config()
                if config:
                    email_addr = config.get("email")
            except Exception:
                pass
            return {
                "listening": False,
                "agent_id": agent_id,
                "email": email_addr
            }

        listener = self._listeners[agent_id]
        return {
            "listening": listener.is_running,
            "agent_id": agent_id,
            "email": listener.email_addr,
            "mode": "poll" if not listener._supports_idle else "idle"
        }

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        return {
            agent_id: self.get_status(agent_id)
            for agent_id in self._listeners
        }

    def stop_all(self):
        for agent_id in list(self._listeners.keys()):
            self._listeners[agent_id].stop()
        self._listeners.clear()
