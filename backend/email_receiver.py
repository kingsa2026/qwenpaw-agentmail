"""
AgentMail Plugin - Email Receiver

提供IMAP/POP3邮件接收和同步功能
"""

import imaplib
import email
import poplib
import base64
import logging
from email.header import decode_header
from email.utils import parseaddr
from typing import Dict, Any, List, Optional
from datetime import datetime

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


class EmailReceiver:
    """邮件接收器 - 支持 IMAP 和 POP3"""

    def __init__(self, config: Dict[str, Any], agent_id: str = ""):
        self.config = config
        self.imap_config = config.get("imap", {})
        self.email_addr = config.get("email", "")
        self.protocol = config.get("receive_protocol", "imap")
        self.auth_type = config.get("auth_type", "basic")
        self.provider = config.get("provider", "")
        self.agent_id = agent_id

    def sync_inbox(self, db, max_emails: int = 50) -> Dict[str, Any]:
        if self.auth_type == "oauth2" and self.provider == "outlook":
            return self._sync_outlook_api(db, max_emails)
        if self.protocol.lower() == "imap":
            return self._sync_imap(db, max_emails)
        elif self.protocol.lower() == "pop3":
            return self._sync_pop3(db, max_emails)
        else:
            return {"success": False, "error": f"不支持的协议: {self.protocol}"}

    def _sync_outlook_api(self, db, max_emails: int = 50) -> Dict[str, Any]:
        try:
            access_token = self._get_oauth2_token()
            if not access_token:
                return {"success": False, "error": "OAuth2令牌无效或已过期，请重新授权"}

            from outlook_api_handler import OutlookAPIHandler
            api = OutlookAPIHandler(access_token)

            result = api.get_messages(folder="inbox", top=max_emails,
                                      select="subject,from,toRecipients,ccRecipients,bccRecipients,"
                                             "bodyPreview,body,receivedDateTime,internetMessageId,"
                                             "hasAttachments,isRead,importance")
            if not result["success"]:
                return {"success": False, "error": f"获取邮件列表失败: {result.get('error')}"}

            messages = result["data"].get("value", [])
            total_on_server = result["data"].get("@odata.count", len(messages))

            synced = 0
            skipped = 0

            for msg_data in messages:
                try:
                    message_id = msg_data.get("internetMessageId", msg_data.get("id", ""))
                    if not message_id:
                        continue

                    existing = db.get_inbox_by_message_id(message_id)
                    if existing:
                        skipped += 1
                        continue

                    subject = msg_data.get("subject", "")
                    body_preview = msg_data.get("bodyPreview", "")
                    body_content = msg_data.get("body", {}).get("content", body_preview)

                    from_data = msg_data.get("from", {}).get("emailAddress", {})
                    from_name = from_data.get("name", "")
                    from_email = from_data.get("address", "")

                    to_recipients = msg_data.get("toRecipients", [])
                    to_email = to_recipients[0].get("emailAddress", {}).get("address", "") if to_recipients else ""

                    date_str = msg_data.get("receivedDateTime", "")

                    db.save_inbox_email({
                        'message_id': message_id,
                        'subject': subject,
                        'sender_name': from_name,
                        'sender_email': from_email,
                        'recipient': to_email or self.email_addr,
                        'cc': "",
                        'bcc': "",
                        'body': body_content[:10000],
                        'body_html': None,
                        'date': date_str,
                        'folder': 'inbox',
                    })
                    synced += 1

                except Exception as e:
                    logger.warning(f"处理邮件失败: {e}")
                    continue

            logger.info(f"Outlook API同步完成: 服务器共{total_on_server}封, 新同步{synced}封, 跳过{skipped}封")
            return {
                "success": True,
                "total_on_server": total_on_server,
                "synced": synced,
                "skipped": skipped
            }

        except Exception as e:
            logger.error(f"Outlook API同步失败: {e}")
            return {"success": False, "error": str(e)}

    def _sync_imap(self, db, max_emails: int = 50) -> Dict[str, Any]:
        """通过IMAP同步邮件"""
        try:
            host = self.imap_config.get("host")
            port = self.imap_config.get("port", 993)
            username = self.imap_config.get("username", self.email_addr)
            password = self.imap_config.get("password")
            use_ssl = self.imap_config.get("use_ssl", True)

            if not host:
                return {"success": False, "error": "IMAP配置不完整"}

            if use_ssl:
                conn = imaplib.IMAP4_SSL(host, port)
            else:
                conn = imaplib.IMAP4(host, port)

            try:
                if self.auth_type == "oauth2":
                    access_token = self._get_oauth2_token()
                    if not access_token:
                        return {"success": False, "error": "OAuth2令牌无效或已过期，请重新授权"}
                    conn.authenticate('XOAUTH2', lambda x: f"user={username}\x01auth=Bearer {access_token}\x01\x01")
                    logger.info(f"[IMAP] OAuth2登录成功: {username}@{host}")
                else:
                    if not password:
                        return {"success": False, "error": "IMAP配置不完整"}
                    conn.login(username, password)
                    logger.info(f"[IMAP] 登录成功: {username}@{host}")

                if 'ID' not in imaplib.Commands:
                    imaplib.Commands['ID'] = ('AUTH',)
                client_id = ('name', 'AgentMail', 'version', '2.0', 'vendor', 'qwenpaw')
                conn._simple_command('ID', '("' + '" "'.join(client_id) + '")')
                logger.info(f"[IMAP] ID命令已发送")

                status, data = conn.select("INBOX", readonly=True)
                if status != "OK":
                    return {"success": False, "error": f"SELECT INBOX 失败: {status} {data}"}

                logger.info(f"[IMAP] SELECT INBOX 成功: {data}")

                status, message_ids = conn.search(None, "ALL")
                if status != "OK":
                    return {"success": False, "error": "搜索邮件失败"}

                id_list = message_ids[0].split()
                total_on_server = len(id_list)

                recent_ids = id_list[-max_emails:] if len(id_list) > max_emails else id_list

                synced = 0
                skipped = 0

                for mid in reversed(recent_ids):
                    try:
                        status, msg_data = conn.fetch(mid, "(RFC822)")
                        if status != "OK":
                            continue

                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)

                        message_id = msg.get("Message-ID", f"imap_{mid.decode()}")
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
                            skipped += 1
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
                        synced += 1

                    except Exception as e:
                        logger.warning(f"处理邮件失败: {e}")
                        continue

                logger.info(f"IMAP同步完成: 服务器共{total_on_server}封, 新同步{synced}封, 跳过{skipped}封")
                return {
                    "success": True,
                    "total_on_server": total_on_server,
                    "synced": synced,
                    "skipped": skipped
                }

            finally:
                conn.logout()

        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP连接错误: {e}")
            return {"success": False, "error": f"IMAP连接失败: {str(e)}"}
        except Exception as e:
            logger.error(f"IMAP同步失败: {e}")
            return {"success": False, "error": str(e)}

    def _sync_pop3(self, db, max_emails: int = 50) -> Dict[str, Any]:
        """通过POP3同步邮件"""
        try:
            host = self.imap_config.get("host")
            port = self.imap_config.get("port", 995)
            username = self.imap_config.get("username", self.email_addr)
            password = self.imap_config.get("password")
            use_ssl = self.imap_config.get("use_ssl", True)

            if not host or not password:
                return {"success": False, "error": "POP3配置不完整"}

            if use_ssl:
                conn = poplib.POP3_SSL(host, port)
            else:
                conn = poplib.POP3(host, port)

            try:
                conn.user(username)
                conn.pass_(password)

                msg_count, mailbox_size = conn.stat()
                total_on_server = msg_count

                start = max(1, msg_count - max_emails + 1)
                recent_range = range(start, msg_count + 1)

                synced = 0
                skipped = 0

                for msg_num in reversed(list(recent_range)):
                    try:
                        resp, lines, octets = conn.retr(msg_num)
                        raw_email = b'\r\n'.join(lines)
                        msg = email.message_from_bytes(raw_email)

                        message_id = msg.get("Message-ID", f"pop3_{msg_num}")
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
                            skipped += 1
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
                        synced += 1

                    except Exception as e:
                        logger.warning(f"处理邮件失败: {e}")
                        continue

                logger.info(f"POP3同步完成: 服务器共{total_on_server}封, 新同步{synced}封, 跳过{skipped}封")
                return {
                    "success": True,
                    "total_on_server": total_on_server,
                    "synced": synced,
                    "skipped": skipped
                }

            finally:
                conn.quit()

        except poplib.error_proto as e:
            logger.error(f"POP3连接错误: {e}")
            return {"success": False, "error": f"POP3连接失败: {str(e)}"}
        except Exception as e:
            logger.error(f"POP3同步失败: {e}")
            return {"success": False, "error": str(e)}

    def _get_oauth2_token(self) -> Optional[str]:
        """获取有效的 OAuth2 访问令牌"""
        if not self.agent_id:
            return None
        try:
            from oauth2_handler import get_valid_access_token
            return get_valid_access_token(self.agent_id)
        except Exception as e:
            logger.error(f"[IMAP] 获取OAuth2令牌失败: {e}")
            return None

    @staticmethod
    def _build_xoauth2_string(username: str, access_token: str) -> str:
        auth_string = f"user={username}\x01auth=Bearer {access_token}\x01\x01"
        return base64.b64encode(auth_string.encode()).decode()

    @staticmethod
    def _xoauth2_authenticate(conn, username: str, access_token: str):
        auth_string = f"user={username}\x01auth=Bearer {access_token}\x01\x01"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()
        tag = conn._new_tag()
        conn.send(tag + b' AUTHENTICATE XOAUTH2 ' + auth_b64.encode() + b'\r\n')
        resp = conn.readline()
        if not resp or b'OK' not in resp:
            raise imaplib.IMAP4.error(f"XOAUTH2 authentication failed: {resp}")
