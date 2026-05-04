"""
AgentMail Plugin - Email Sender

提供邮件发送功能，支持基本认证和OAuth2认证
"""

import smtplib
import base64
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class EmailSender:
    """邮件发送器"""

    def __init__(self, config: Dict[str, Any], agent_id: str = ""):
        self.config = config
        self.smtp_config = config.get("smtp", {})
        self.email = config.get("email", "")
        self.auth_type = config.get("auth_type", "basic")
        self.provider = config.get("provider", "")
        self.agent_id = agent_id

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html: bool = False
    ) -> Dict[str, Any]:
        try:
            if self.auth_type == "oauth2" and self.provider == "outlook":
                return self._send_outlook_api(to_email, subject, body, html)
            return self._send_smtp(to_email, subject, body, html)
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return {"success": False, "error": str(e)}

    def _send_outlook_api(self, to_email: str, subject: str, body: str, html: bool = False) -> Dict[str, Any]:
        access_token = self._get_oauth2_token()
        if not access_token:
            return {"success": False, "error": "OAuth2令牌无效或已过期，请重新授权"}

        from outlook_api_handler import OutlookAPIHandler
        api = OutlookAPIHandler(access_token)

        message = {
            "subject": subject,
            "body": {
                "contentType": "HTML" if html else "Text",
                "content": body
            },
            "toRecipients": [{"emailAddress": {"address": to_email}}]
        }

        result = api.send_message(message)
        if result["success"]:
            logger.info(f"Outlook API邮件发送成功: {self.email} -> {to_email}")
            return {"success": True, "message": "邮件发送成功"}
        return {"success": False, "error": f"发送失败: {result.get('error', '未知错误')}"}

    def _send_smtp(self, to_email: str, subject: str, body: str, html: bool = False) -> Dict[str, Any]:
        try:
            if not self.smtp_config or not self.email:
                return {"success": False, "error": "SMTP配置不完整"}

            smtp_host = self.smtp_config.get("host")
            smtp_port = self.smtp_config.get("port", 587)
            smtp_username = self.smtp_config.get("username", self.email)
            smtp_password = self.smtp_config.get("password")
            use_tls = self.smtp_config.get("use_tls", True)

            if not smtp_host:
                return {"success": False, "error": "SMTP服务器未配置"}

            msg = MIMEMultipart("alternative")
            msg["From"] = self.email
            msg["To"] = to_email
            msg["Subject"] = subject

            if html:
                msg.attach(MIMEText(body, "html", "utf-8"))
            else:
                msg.attach(MIMEText(body, "plain", "utf-8"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                if use_tls:
                    server.starttls()

                if self.auth_type == "oauth2":
                    access_token = self._get_oauth2_token()
                    if not access_token:
                        return {"success": False, "error": "OAuth2令牌无效或已过期，请重新授权"}
                    auth_string = self._build_xoauth2_string(smtp_username, access_token)
                    code, resp = server.docmd('AUTH', 'XOAUTH2 ' + auth_string)
                    if code != 235:
                        return {"success": False, "error": f"SMTP OAuth2认证失败: {code} {resp}"}
                    logger.info(f"[SMTP] OAuth2认证成功: {smtp_username}@{smtp_host}")
                else:
                    if not smtp_password:
                        return {"success": False, "error": "SMTP密码未配置"}
                    server.login(smtp_username, smtp_password)

                server.sendmail(self.email, [to_email], msg.as_string())

            logger.info(f"邮件发送成功: {self.email} -> {to_email}")
            return {"success": True, "message": "邮件发送成功"}

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP认证失败: {e}")
            if self.auth_type == "oauth2":
                return {"success": False, "error": f"OAuth2认证失败，请重新授权: {str(e)}"}
            return {"success": False, "error": f"SMTP认证失败: {str(e)}"}
        except Exception as e:
            logger.error(f"SMTP发送失败: {e}")
            return {"success": False, "error": str(e)}

    def _get_oauth2_token(self) -> Optional[str]:
        if not self.agent_id:
            return None
        try:
            from oauth2_handler import get_valid_access_token
            return get_valid_access_token(self.agent_id)
        except Exception as e:
            logger.error(f"[SMTP] 获取OAuth2令牌失败: {e}")
            return None

    @staticmethod
    def _build_xoauth2_string(username: str, access_token: str) -> str:
        auth_string = f"user={username}\x01auth=Bearer {access_token}\x01\x01"
        return base64.b64encode(auth_string.encode()).decode()
