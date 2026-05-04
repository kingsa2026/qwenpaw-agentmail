import json
import logging
import threading
import time
import os
from pathlib import Path
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)

POLL_INTERVAL = 600


class GraphPollListener:

    def __init__(self, agent_id: str, config: Dict[str, Any],
                 on_new_email: Optional[Callable] = None):
        self.agent_id = agent_id
        self.config = config
        self.email_addr = config.get("email", "")
        self.on_new_email = on_new_email

        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_message_dates: Dict[str, str] = {}

    @property
    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    def start(self) -> Dict[str, Any]:
        if self.is_running:
            return {"success": False, "error": "Graph轮询已在运行"}

        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop,
            name=f"graph-poll-{self.agent_id}",
            daemon=True
        )
        self._thread.start()
        logger.info(f"[GraphPoll] 轮询已启动: agent={self.agent_id}, interval={POLL_INTERVAL}s")
        return {"success": True, "message": f"Graph轮询已启动: {self.email_addr}"}

    def stop(self) -> Dict[str, Any]:
        if not self._running:
            return {"success": False, "error": "Graph轮询未在运行"}
        self._running = False
        logger.info(f"[GraphPoll] 轮询已停止: agent={self.agent_id}")
        return {"success": True, "message": "Graph轮询已停止"}

    def _poll_loop(self):
        logger.info(f"[GraphPoll] 轮询线程启动: agent={self.agent_id}")
        while self._running:
            try:
                self._check_new_emails()
            except Exception as e:
                logger.error(f"[GraphPoll] 轮询异常: {e}")
            time.sleep(POLL_INTERVAL)

    def _check_new_emails(self):
        access_token = self._get_oauth2_token()
        if not access_token:
            return

        try:
            from outlook_api_handler import OutlookAPIHandler
            api = OutlookAPIHandler(access_token)
            result = api.get_messages(top=10, select="subject,from,toRecipients,"
                                       "bodyPreview,body,receivedDateTime,"
                                       "internetMessageId,hasAttachments,isRead")
            if not result["success"]:
                logger.warning(f"[GraphPoll] 获取邮件列表失败: {result.get('error')}")
                return

            messages = result["data"].get("value", [])
            if not messages:
                return

            from database import get_db
            db = get_db(self.agent_id)
            new_found = 0

            for msg_data in messages:
                try:
                    message_id = msg_data.get("internetMessageId", msg_data.get("id", ""))
                    if not message_id:
                        continue

                    existing = db.get_inbox_by_message_id(message_id)
                    if existing:
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

                    logger.info(f"[GraphPoll] 新邮件已保存: from={from_email}, subject={subject}")

                    self._notify_agent(db, {
                        'message_id': message_id,
                        'subject': subject,
                        'sender_name': from_name,
                        'sender_email': from_email,
                        'body': body_content[:2000],
                    })

                    new_found += 1

                except Exception as e:
                    logger.warning(f"[GraphPoll] 处理邮件失败: {e}")
                    continue

            if new_found:
                logger.info(f"[GraphPoll] 本轮发现 {new_found} 封新邮件: agent={self.agent_id}")

        except Exception as e:
            logger.error(f"[GraphPoll] 检查新邮件失败: {e}")

    def _notify_agent(self, db, email_data: Dict[str, Any]):
        self._write_notification_file(email_data)
        self._inject_to_qwenpaw(email_data)
        if self.on_new_email:
            try:
                self.on_new_email(self.agent_id, email_data)
            except Exception as e:
                logger.error(f"[GraphPoll] 回调通知失败: {e}")

    def _get_oauth2_token(self) -> Optional[str]:
        try:
            from oauth2_handler import get_valid_access_token
            return get_valid_access_token(self.agent_id)
        except Exception as e:
            logger.error(f"[GraphPoll] 获取OAuth2令牌失败: {e}")
            return None

    def _write_notification_file(self, email_data: Dict[str, Any]):
        try:
            from database import get_db
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

            logger.info(f"[GraphPoll] Agent通知已写入: {context_file}")

        except Exception as e:
            logger.error(f"[GraphPoll] 写入通知文件失败: {e}")

    def _inject_to_qwenpaw(self, email_data: Dict[str, Any]):
        try:
            import httpx

            subject = email_data.get('subject', '(无主题)')
            sender = email_data.get('sender_email', '未知发件人')
            sender_name = email_data.get('sender_name', '')
            body_preview = email_data.get('body', '')[:500]

            prompt = (
                f"**AgentMail**: 你收到一封新邮件！\n\n"
                f"发件人: {sender_name} <{sender}>\n"
                f"主题: {subject}\n"
                f"正文预览:\n{body_preview}\n\n"
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
                        f"[GraphPoll] 已通过QwenPaw API通知Agent: "
                        f"agent={self.agent_id}, task_id={task_id}"
                    )
            except httpx.ConnectError:
                logger.warning("[GraphPoll] QwenPaw API不可用，跳过API通知")
            except Exception as e:
                logger.warning(f"[GraphPoll] QwenPaw API通知失败: {e}")

        except ImportError:
            logger.warning("[GraphPoll] httpx未安装，无法通过API通知Agent")
        except Exception as e:
            logger.error(f"[GraphPoll] 注入QwenPaw失败: {e}")
