"""
AgentMail Plugin - API Routes

所有API端点，Agent隔离
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging
import time

from database import get_db, get_all_agent_dbs

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/email", tags=["email"])


# ── Request Models ──────────────────────────────────────────────────────────

class EmailConfigRequest(BaseModel):
    provider: str = Field(default="custom", description="邮箱提供商")
    email: str = Field(..., description="邮箱地址")
    display_name: Optional[str] = Field(None, description="显示名称")
    receive_protocol: str = Field(default="imap", description="接收协议: imap/pop3")
    auth_type: str = Field(default="basic", description="认证类型: basic/oauth2")
    smtp: Dict[str, Any] = Field(..., description="SMTP配置")
    imap: Dict[str, Any] = Field(..., description="IMAP/POP3配置")
    oauth2: Optional[Dict[str, Any]] = Field(None, description="OAuth2配置")


class ContactRequest(BaseModel):
    name: str = Field(..., description="姓名")
    phone: Optional[str] = Field(None, description="电话")
    email: str = Field(..., description="邮箱")
    company: Optional[str] = Field(None, description="公司")
    website: Optional[str] = Field(None, description="网站")
    notes: Optional[str] = Field(None, description="备注")
    group_name: str = Field(default="default", description="分组")


class ShareRequest(BaseModel):
    target_agent_ids: List[str] = Field(..., description="目标Agent ID列表")


class BatchIdsRequest(BaseModel):
    ids: List[int] = Field(..., description="ID列表")


class ReplyRequest(BaseModel):
    content: str = Field(..., description="回复内容")


# ── Config API ──────────────────────────────────────────────────────────────

@router.get("/config/{agent_id}")
async def get_config(agent_id: str):
    """获取邮件配置"""
    db = get_db(agent_id)
    config = db.get_config()
    if not config:
        return {"success": True, "config": None}
    return {"success": True, "config": config}


@router.post("/config/{agent_id}")
async def save_config(agent_id: str, data: EmailConfigRequest):
    """保存邮件配置（SMTP + IMAP/POP3）"""
    db = get_db(agent_id)
    result = db.save_config(data.dict())
    return {"success": result}


@router.delete("/config/{agent_id}")
async def delete_config(agent_id: str):
    """删除邮件配置"""
    db = get_db(agent_id)
    result = db.delete_config()
    return {"success": result}


@router.post("/{agent_id}/test-connection")
async def test_connection(agent_id: str):
    """测试邮箱连接"""
    db = get_db(agent_id)
    config = db.get_config()
    if not config:
        return {"success": False, "error": "未配置邮箱"}

    try:
        import imaplib
        imap_config = config.get("imap", {})
        host = imap_config.get("host")
        port = imap_config.get("port", 993)
        username = imap_config.get("username")
        password = imap_config.get("password")
        use_ssl = imap_config.get("use_ssl", True)
        auth_type = config.get("auth_type", "basic")

        if not host:
            return {"success": False, "error": "IMAP配置不完整"}

        if use_ssl:
            conn = imaplib.IMAP4_SSL(host, port)
        else:
            conn = imaplib.IMAP4(host, port)

        if auth_type == "oauth2":
            from oauth2_handler import get_valid_access_token
            access_token = get_valid_access_token(agent_id)
            if not access_token:
                return {"success": False, "error": "OAuth2令牌无效或已过期，请重新授权"}
            conn.authenticate('XOAUTH2', lambda x: f"user={username}\x01auth=Bearer {access_token}\x01\x01")
        else:
            if not password:
                return {"success": False, "error": "IMAP配置不完整"}
            conn.login(username, password)

        if 'ID' not in imaplib.Commands:
            imaplib.Commands['ID'] = ('AUTH',)
        client_id = ('name', 'AgentMail', 'version', '2.0', 'vendor', 'qwenpaw')
        conn._simple_command('ID', '("' + '" "'.join(client_id) + '")')

        conn.select("INBOX", readonly=True)
        conn.logout()

        return {"success": True}
    except imaplib.IMAP4.error as e:
        return {"success": False, "error": f"IMAP连接失败: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"连接测试失败: {str(e)}"}


# ── Inbox API ───────────────────────────────────────────────────────────────

@router.get("/{agent_id}/inbox")
async def get_inbox(
    agent_id: str,
    folder: str = Query(default="inbox", description="文件夹: inbox/archive"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100)
):
    """获取收件箱邮件"""
    db = get_db(agent_id)
    result = db.get_inbox(folder=folder, page=page, page_size=page_size)
    return {"success": True, **result}


@router.post("/{agent_id}/inbox/{email_id}/agent-read")
async def mark_agent_read(agent_id: str, email_id: int):
    """标记Agent已读状态"""
    db = get_db(agent_id)
    result = db.mark_agent_read(email_id)
    return {"success": result}


@router.post("/{agent_id}/inbox/{email_id}/reply")
async def mark_replied(agent_id: str, email_id: int, data: ReplyRequest):
    """标记Agent回复状态"""
    db = get_db(agent_id)
    result = db.mark_replied(email_id, data.content)
    return {"success": result}


@router.post("/{agent_id}/inbox/archive")
async def archive_inbox(agent_id: str, data: BatchIdsRequest):
    """归档邮件"""
    db = get_db(agent_id)
    result = db.archive_emails(data.ids)
    return {"success": result}


@router.post("/{agent_id}/inbox/delete")
async def delete_inbox(agent_id: str, data: BatchIdsRequest):
    """删除收件箱邮件（移动到回收站）"""
    db = get_db(agent_id)
    result = db.move_to_trash("inbox", data.ids)
    return {"success": result}


# ── Sent API ────────────────────────────────────────────────────────────────

@router.get("/{agent_id}/sent")
async def get_sent(
    agent_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100)
):
    """获取发件箱"""
    db = get_db(agent_id)
    result = db.get_sent(page=page, page_size=page_size)
    return {"success": True, **result}


# ── Drafts API ──────────────────────────────────────────────────────────────

@router.get("/{agent_id}/drafts")
async def get_drafts(
    agent_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100)
):
    """获取草稿箱"""
    db = get_db(agent_id)
    result = db.get_drafts(page=page, page_size=page_size)
    return {"success": True, **result}


class DraftRequest(BaseModel):
    to: Optional[List[str]] = Field(default=[], description="收件人列表")
    cc: Optional[List[str]] = Field(default=[], description="抄送列表")
    bcc: Optional[List[str]] = Field(default=[], description="密送列表")
    subject: str = Field(default="", description="邮件主题")
    body: str = Field(default="", description="邮件正文")
    body_html: Optional[str] = Field(None, description="HTML正文")
    id: Optional[int] = Field(None, description="草稿ID（更新时传入）")


@router.post("/{agent_id}/drafts")
async def save_draft(agent_id: str, data: DraftRequest):
    """保存草稿"""
    db = get_db(agent_id)
    draft_data = {
        "subject": data.subject,
        "recipient": ", ".join(data.to) if data.to else "",
        "cc": ", ".join(data.cc) if data.cc else "",
        "bcc": ", ".join(data.bcc) if data.bcc else "",
        "body": data.body,
        "body_html": data.body_html,
    }
    result = db.save_draft(data.id, draft_data)
    return {"success": bool(result), "id": result}


@router.post("/{agent_id}/drafts/delete")
async def delete_drafts(agent_id: str, data: BatchIdsRequest):
    """删除草稿"""
    db = get_db(agent_id)
    result = db.delete_drafts(data.ids)
    return {"success": result, "deleted": len(data.ids)}


@router.post("/{agent_id}/sent/delete")
async def delete_sent(agent_id: str, data: BatchIdsRequest):
    """删除已发送邮件"""
    db = get_db(agent_id)
    for email_id in data.ids:
        db.move_to_trash("sent", email_id)
    return {"success": True, "deleted": len(data.ids)}


# ── Trash API ───────────────────────────────────────────────────────────────

@router.get("/{agent_id}/trash")
async def get_trash(
    agent_id: str,
    item_type: Optional[str] = Query(default=None, description="类型筛选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100)
):
    """获取回收站"""
    db = get_db(agent_id)
    result = db.get_trash(item_type=item_type, page=page, page_size=page_size)
    return {"success": True, **result}


@router.post("/{agent_id}/trash/restore")
async def restore_trash(agent_id: str, data: BatchIdsRequest):
    """从回收站恢复"""
    db = get_db(agent_id)
    result = db.restore_from_trash(data.ids)
    return {"success": result, "restored": len(data.ids) if result else 0}


@router.delete("/{agent_id}/trash/permanent")
async def permanent_delete(agent_id: str, data: BatchIdsRequest):
    """永久删除"""
    db = get_db(agent_id)
    result = db.permanent_delete(data.ids)
    return {"success": result}


# ── Contacts API ────────────────────────────────────────────────────────────

@router.get("/{agent_id}/contacts")
async def get_contacts(
    agent_id: str,
    group: Optional[str] = Query(default=None, description="分组筛选"),
    search: Optional[str] = Query(default=None, description="搜索关键词"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=15, ge=1, le=100)
):
    """获取联系人列表"""
    db = get_db(agent_id)
    result = db.get_contacts(group=group, search=search, page=page, page_size=page_size)
    return {"success": True, **result}


@router.post("/{agent_id}/contacts")
async def create_contact(agent_id: str, data: ContactRequest):
    """创建联系人"""
    db = get_db(agent_id)
    contact_id = db.create_contact(data.dict())
    return {"success": True, "id": contact_id}


@router.put("/{agent_id}/contacts/{contact_id}")
async def update_contact(agent_id: str, contact_id: int, data: ContactRequest):
    """更新联系人"""
    db = get_db(agent_id)
    result = db.update_contact(contact_id, data.dict())
    return {"success": result}


@router.delete("/{agent_id}/contacts/{contact_id}")
async def delete_contact(agent_id: str, contact_id: int):
    """删除联系人（移动到回收站）"""
    db = get_db(agent_id)
    result = db.delete_contacts([contact_id])
    return {"success": result}


@router.post("/{agent_id}/contacts/batch-delete")
async def batch_delete_contacts(agent_id: str, data: BatchIdsRequest):
    """批量删除联系人"""
    db = get_db(agent_id)
    result = db.delete_contacts(data.ids)
    return {"success": result}


@router.post("/{agent_id}/contacts/{contact_id}/share")
async def share_contact(agent_id: str, contact_id: int, data: ShareRequest):
    """共享联系人"""
    db = get_db(agent_id)
    result = db.share_contact(contact_id, data.target_agent_ids)
    return {"success": result}


@router.post("/{agent_id}/contacts/batch-share")
async def batch_share_contacts(agent_id: str, data: Dict[str, Any]):
    """批量共享联系人"""
    db = get_db(agent_id)
    contact_ids = data.get("contact_ids", [])
    target_agent_ids = data.get("target_agent_ids", [])
    success_count = 0
    for contact_id in contact_ids:
        if db.share_contact(contact_id, target_agent_ids):
            success_count += 1
    return {"success": True, "shared": success_count}


# ── Contact Groups API ──────────────────────────────────────────────────────

@router.get("/{agent_id}/contact-groups")
async def get_contact_groups(agent_id: str):
    """获取联系人分组"""
    db = get_db(agent_id)
    groups = db.get_contact_groups()
    return {"success": True, "items": groups}


@router.post("/{agent_id}/contact-groups")
async def create_contact_group(agent_id: str, data: Dict[str, str]):
    """创建联系人分组"""
    db = get_db(agent_id)
    group_id = db.create_contact_group(data.get("name", ""))
    return {"success": group_id > 0, "id": group_id}


@router.delete("/{agent_id}/contact-groups/{group_id}")
async def delete_contact_group(agent_id: str, group_id: int):
    """删除联系人分组"""
    db = get_db(agent_id)
    result = db.delete_contact_group(group_id)
    return {"success": result}


@router.put("/{agent_id}/contact-groups/{group_id}")
async def update_contact_group(agent_id: str, group_id: int, data: Dict[str, str]):
    """更新联系人分组"""
    db = get_db(agent_id)
    result = db.update_contact_group(group_id, data.get("name", ""))
    return {"success": result}


# ── Sync Email API ──────────────────────────────────────────────────────────

@router.post("/{agent_id}/sync")
async def sync_inbox(agent_id: str, max_emails: int = Query(default=50, ge=1, le=200)):
    """同步收件箱邮件（从IMAP/POP3服务器拉取）"""
    from email_receiver import EmailReceiver

    db = get_db(agent_id)
    config = db.get_config()

    if not config:
        return {"success": False, "error": "邮件配置未找到"}

    receiver = EmailReceiver(config, agent_id=agent_id)
    result = receiver.sync_inbox(db, max_emails=max_emails)
    return result


# ── IMAP IDLE Listener API ──────────────────────────────────────────────────

@router.post("/{agent_id}/listen/start")
async def start_listener(agent_id: str):
    """启动 IMAP IDLE 实时监听（新邮件推送）"""
    from imap_idle_listener import ListenerManager
    manager = ListenerManager()
    return manager.start_listener(agent_id)


@router.post("/{agent_id}/listen/stop")
async def stop_listener(agent_id: str):
    """停止 IMAP IDLE 监听"""
    from imap_idle_listener import ListenerManager
    manager = ListenerManager()
    return manager.stop_listener(agent_id)


@router.get("/{agent_id}/listen/status")
async def get_listen_status(agent_id: str):
    """获取 IMAP IDLE 监听状态"""
    from imap_idle_listener import ListenerManager
    manager = ListenerManager()
    return manager.get_status(agent_id)


# ── Send Email API ──────────────────────────────────────────────────────────

class SendEmailRequest(BaseModel):
    to: List[str] = Field(default=[], description="收件人列表")
    cc: List[str] = Field(default=[], description="抄送列表")
    bcc: List[str] = Field(default=[], description="密送列表")
    subject: str = Field(..., description="邮件主题")
    body: str = Field(..., description="邮件正文")
    body_html: Optional[str] = Field(None, description="HTML正文")
    attachments: Optional[List[Dict[str, Any]]] = Field(None, description="附件列表")
    draft_id: Optional[int] = Field(None, description="草稿ID（从草稿发送时）")


@router.post("/{agent_id}/send")
async def send_email(agent_id: str, data: SendEmailRequest):
    """发送邮件"""
    from email_sender import EmailSender

    db = get_db(agent_id)
    config = db.get_config()

    if not config:
        return {"success": False, "error": "邮件配置未找到"}

    to_email = ", ".join(data.to) if data.to else ""
    if not to_email:
        return {"success": False, "error": "收件人不能为空"}

    sender = EmailSender(config, agent_id=agent_id)
    result = sender.send_email(
        to_email=to_email,
        subject=data.subject,
        body=data.body,
        html=bool(data.body_html)
    )

    if result["success"]:
        db.save_sent_email(to_email, data.subject, data.body)

    return result


@router.post("/{agent_id}/sent/send")
async def send_email_alt(agent_id: str, data: SendEmailRequest):
    """发送邮件（兼容前端路径）"""
    return await send_email(agent_id, data)


@router.post("/{agent_id}/backup")
async def backup_data(agent_id: str):
    """备份数据"""
    db = get_db(agent_id)
    result = db.backup()
    return {"success": bool(result), "path": str(db.bak_dir) if result else ""}


@router.get("/agents")
async def get_agents():
    """获取所有Agent信息"""
    dbs = get_all_agent_dbs()
    agents = []
    for agent_id, db in dbs.items():
        config = db.get_config()
        agents.append({
            "id": agent_id,
            "email": config.get("email") if config else None,
            "provider": config.get("provider") if config else None,
            "db_path": str(db.db_path),
        })
    return {"success": True, "agents": agents}


# ── Uninstall API ───────────────────────────────────────────────────────────

@router.post("/{agent_id}/uninstall")
async def uninstall_plugin(agent_id: str, data: Dict[str, Any]):
    """卸载插件 - 清理数据库和文件"""
    db = get_db(agent_id)
    keep_data = data.get("keep_data", False)
    result = db.uninstall(keep_data=keep_data)
    return {"success": result}


# ── OAuth2 API ──────────────────────────────────────────────────────────────

class OAuth2StartRequest(BaseModel):
    client_id: str = Field(..., description="Azure AD 应用 Client ID")
    client_secret: Optional[str] = Field(None, description="Azure AD 应用 Client Secret（可选）")
    tenant_id: str = Field(default="consumers", description="Azure AD 租户 ID")


@router.post("/{agent_id}/oauth2/start")
async def oauth2_start(agent_id: str, data: OAuth2StartRequest):
    """启动 OAuth2 设备代码流"""
    from oauth2_handler import OutlookOAuth2Handler

    handler = OutlookOAuth2Handler(
        client_id=data.client_id,
        client_secret=data.client_secret,
        tenant_id=data.tenant_id,
    )

    result = handler.start_device_flow()
    if result.get("success"):
        db = get_db(agent_id)
        config = db.get_config()
        if config:
            config_data = {
                'provider': config.get('provider', 'custom'),
                'email': config.get('email'),
                'display_name': config.get('display_name'),
                'receive_protocol': config.get('receive_protocol', 'imap'),
                'auth_type': 'oauth2',
                'smtp': config.get('smtp', {}),
                'imap': config.get('imap', {}),
                'oauth2': {
                    'client_id': data.client_id,
                    'client_secret': data.client_secret,
                },
            }
            db.save_config(config_data)

    return result


class OAuth2PollRequest(BaseModel):
    client_id: str = Field(..., description="Azure AD 应用 Client ID")
    device_code: str = Field(..., description="设备代码")
    client_secret: Optional[str] = Field(None, description="Azure AD 应用 Client Secret")
    tenant_id: str = Field(default="consumers", description="Azure AD 租户 ID")


@router.post("/{agent_id}/oauth2/poll")
async def oauth2_poll(agent_id: str, data: OAuth2PollRequest):
    """轮询 OAuth2 设备代码令牌"""
    from oauth2_handler import OutlookOAuth2Handler

    handler = OutlookOAuth2Handler(
        client_id=data.client_id,
        client_secret=data.client_secret,
        tenant_id=data.tenant_id,
    )

    result = handler.poll_device_token(data.device_code)
    if result.get("success"):
        db = get_db(agent_id)
        access_token = result["access_token"]
        refresh_token = result.get("refresh_token", "")
        expires_in = result.get("expires_in", 3600)
        import time
        expires_at = time.time() + expires_in

        db.save_oauth2_tokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )

        logger.info(f"[OAuth2] Agent {agent_id} 授权成功")

    return result


@router.get("/{agent_id}/oauth2/status")
async def oauth2_status(agent_id: str):
    """获取 OAuth2 授权状态"""
    db = get_db(agent_id)
    status = db.get_oauth2_status()
    return {"success": True, **status}


@router.post("/{agent_id}/oauth2/revoke")
async def oauth2_revoke(agent_id: str):
    """撤销 OAuth2 授权（清除令牌）"""
    db = get_db(agent_id)
    config = db.get_config()
    if not config:
        return {"success": False, "error": "未配置邮箱"}

    config_data = {
        'provider': config.get('provider', 'custom'),
        'email': config.get('email'),
        'display_name': config.get('display_name'),
        'receive_protocol': config.get('receive_protocol', 'imap'),
        'auth_type': 'basic',
        'smtp': config.get('smtp', {}),
        'imap': config.get('imap', {}),
        'oauth2': {
            'client_id': None,
            'client_secret': None,
            'access_token': None,
            'refresh_token': None,
            'token_expires_at': 0,
        },
    }
    db.save_config(config_data)
    return {"success": True}


@router.get("/oauth2/callback")
async def oauth2_callback(code: Optional[str] = None, state: Optional[str] = None,
                          error: Optional[str] = None, error_description: Optional[str] = None):
    """OAuth2 授权回调端点 - 接收授权码"""
    from fastapi.responses import HTMLResponse

    if error:
        logger.error(f"[OAuth2] Callback error: {error} - {error_description}")
        return HTMLResponse(content=f"<html><body><h2>Authorization Failed</h2><p>{error}: {error_description}</p></body></html>")

    if not code:
        return HTMLResponse(content="<html><body><h2>Error</h2><p>No authorization code received.</p></body></html>")

    if not state:
        return HTMLResponse(content="<html><body><h2>Error</h2><p>Missing state parameter.</p></body></html>")

    parts = state.split(":", 1)
    agent_id = parts[0] if len(parts) > 0 else ""
    client_id = parts[1] if len(parts) > 1 else ""

    if not agent_id or not client_id:
        return HTMLResponse(content="<html><body><h2>Error</h2><p>Invalid state parameter.</p></body></html>")

    db = get_db(agent_id)
    config = db.get_config()
    client_secret = ""
    if config and config.get("oauth2"):
        client_secret = config.get("oauth2", {}).get("client_secret") or ""

    from oauth2_handler import OutlookOAuth2Handler
    handler = OutlookOAuth2Handler(client_id=client_id, client_secret=client_secret if client_secret else None, tenant_id="common")
    redirect_uri = "http://localhost:18088/api/v1/email/oauth2/callback"
    result = handler.exchange_code_for_tokens(code, redirect_uri)

    if result.get("success"):
        import time
        access_token = result["access_token"]
        refresh_token = result.get("refresh_token", "")
        expires_in = result.get("expires_in", 3600)
        expires_at = time.time() + expires_in

        config_data = {
            'provider': config.get('provider', 'outlook') if config else 'outlook',
            'email': config.get('email') if config else '',
            'display_name': config.get('display_name') if config else '',
            'receive_protocol': config.get('receive_protocol', 'imap') if config else 'imap',
            'auth_type': 'oauth2',
            'smtp': config.get('smtp', {}) if config else {},
            'imap': config.get('imap', {}) if config else {},
            'oauth2': {
                'client_id': client_id,
                'client_secret': client_secret if client_secret else None,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_expires_at': expires_at,
            },
        }
        db.save_config(config_data)

        logger.info(f"[OAuth2] Agent {agent_id} authorization successful via callback")
        return HTMLResponse(content="<html><body><h2>Authorization Successful!</h2><p>You can close this window now.</p></body></html>")
    else:
        error_msg = result.get("error", "Unknown error")
        logger.error(f"[OAuth2] Token exchange failed: {error_msg}")
        return HTMLResponse(content=f"<html><body><h2>Authorization Failed</h2><p>{error_msg}</p></body></html>")


@router.post("/{agent_id}/oauth2/auth-url")
async def oauth2_auth_url(agent_id: str, data: Dict[str, Any]):
    """生成 OAuth2 授权 URL（授权码流程）"""
    from oauth2_handler import OutlookOAuth2Handler

    client_id = data.get("client_id", "")
    client_secret = data.get("client_secret", "")
    if not client_id:
        return {"success": False, "error": "Client ID is required"}

    db = get_db(agent_id)
    config = db.get_config()

    state = f"{agent_id}:{client_id}"

    redirect_type = data.get("redirect_type", "nativeclient")
    if redirect_type == "nativeclient":
        redirect_uri = "http://127.0.0.1:8888"
    else:
        redirect_uri = "http://localhost:18088/api/v1/email/oauth2/callback"

    handler = OutlookOAuth2Handler(client_id=client_id, client_secret=client_secret if client_secret else None, tenant_id="common")
    auth_url = handler.get_authorization_url(redirect_uri=redirect_uri, state=state)

    if config:
        config_data = {
            'provider': config.get('provider', 'outlook'),
            'email': config.get('email'),
            'display_name': config.get('display_name'),
            'receive_protocol': config.get('receive_protocol', 'imap'),
            'auth_type': 'oauth2',
            'smtp': config.get('smtp', {}),
            'imap': config.get('imap', {}),
            'oauth2': {
                'client_id': client_id,
                'client_secret': client_secret if client_secret else None,
            },
        }
        db.save_config(config_data)

    return {"success": True, "data": {"auth_url": auth_url, "redirect_uri": redirect_uri}}


@router.post("/{agent_id}/oauth2/exchange")
async def oauth2_exchange_code(agent_id: str, data: Dict[str, Any]):
    """手动兑换授权码（用于 nativeclient 流程）"""
    from oauth2_handler import OutlookOAuth2Handler

    code = data.get("code", "")
    if not code:
        return {"success": False, "error": "Code is required"}

    db = get_db(agent_id)
    config = db.get_config()
    if not config:
        return {"success": False, "error": "Agent not configured"}

    oauth2_config = config.get("oauth2", {})
    client_id = oauth2_config.get("client_id", "")
    client_secret = oauth2_config.get("client_secret", "")
    if not client_id:
        return {"success": False, "error": "OAuth2 not configured for this agent"}

    redirect_uri = data.get("redirect_uri", "http://127.0.0.1:8888")

    handler = OutlookOAuth2Handler(
        client_id=client_id,
        client_secret=client_secret if client_secret else None,
        tenant_id="common"
    )
    result = handler.exchange_code_for_tokens(code, redirect_uri)

    if result.get("success"):
        access_token = result.get("access_token", "")
        refresh_token = result.get("refresh_token", "")
        expires_in = result.get("expires_in", 3600)
        expires_at = time.time() + expires_in

        db.save_oauth2_tokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
        logger.info(f"[OAuth2] Agent {agent_id} code exchanged successfully via nativeclient")

        token_type = "JWT" if access_token.startswith("eyJ") else "opaque"
        return {
            "success": True,
            "message": "Token获取成功",
            "token_type": token_type,
            "token_prefix": access_token[:30] + "...",
            "expires_in": expires_in,
        }

    error_msg = result.get("error", "Unknown error")
    logger.error(f"[OAuth2] Code exchange failed: {error_msg}")
    return {"success": False, "error": f"兑换失败: {error_msg}"}
