"""
AgentMail Plugin - OAuth2 Handler for Microsoft Outlook

Outlook.com personal accounts require OAuth2 (basic auth disabled).
Uses Microsoft Graph scopes (Mail.Read, Mail.Send) with Outlook REST API for email operations.
"""

import urllib.parse
import urllib.request
import json
import time
import base64
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

MS_DEVICE_CODE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/devicecode"
MS_TOKEN_URL_V2 = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
MS_TOKEN_URL_V1 = "https://login.microsoftonline.com/common/oauth2/token"
MS_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"

MS_GRAPH_SCOPES = [
    "https://outlook.office.com/IMAP.AccessAsUser.All",
    "offline_access",
]

class OutlookOAuth2Handler:
    """Microsoft Outlook OAuth2 handler using device code flow"""

    def __init__(self, client_id: str, client_secret: str = None, tenant_id: str = "consumers"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id

    @property
    def _token_url_v2(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

    @property
    def _token_url_v1(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/token"

    @property
    def _device_code_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/devicecode"

    @property
    def _auth_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize"

    def start_device_flow(self) -> Dict[str, Any]:
        data = {
            "client_id": self.client_id,
            "scope": " ".join(MS_GRAPH_SCOPES),
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret

        req = urllib.request.Request(
            self._device_code_url,
            data=urllib.parse.urlencode(data).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
                logger.info(f"[OAuth2] Device code flow started for client {self.client_id[:8]}...")
                return {
                    "success": True,
                    "user_code": result.get("user_code"),
                    "device_code": result.get("device_code"),
                    "verification_uri": result.get("verification_uri"),
                    "expires_in": result.get("expires_in", 900),
                    "interval": result.get("interval", 5),
                    "message": result.get("message", ""),
                }
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            logger.error(f"[OAuth2] Device code request failed: {e.code} {error_body}")
            try:
                error_data = json.loads(error_body)
                error_desc = error_data.get("error_description", error_body)
            except Exception:
                error_desc = error_body
            return {"success": False, "error": f"Device code request failed: {error_desc}"}
        except Exception as e:
            logger.error(f"[OAuth2] Device code request error: {e}")
            return {"success": False, "error": str(e)}

    def poll_device_token(self, device_code: str) -> Dict[str, Any]:
        data = {
            "client_id": self.client_id,
            "code": device_code,
            "grant_type": "urn:ietf:params:oauth:grants:device_code",
            "scope": " ".join(MS_GRAPH_SCOPES),
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret

        req = urllib.request.Request(
            self._token_url_v2,
            data=urllib.parse.urlencode(data).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
                logger.info("[OAuth2] Device code token obtained successfully")
                return {
                    "success": True,
                    "access_token": result.get("access_token"),
                    "refresh_token": result.get("refresh_token"),
                    "expires_in": result.get("expires_in", 3600),
                    "token_type": result.get("token_type", "Bearer"),
                    "scope": result.get("scope", ""),
                }
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            try:
                error_data = json.loads(error_body)
                error_code = error_data.get("error", "")
                error_desc = error_data.get("error_description", "")
            except Exception:
                error_code = "unknown"
                error_desc = error_body

            if error_code == "authorization_pending":
                return {"success": False, "pending": True, "error": "Authorization pending"}
            elif error_code == "slow_down":
                return {"success": False, "pending": True, "error": "Slow down", "slow_down": True}
            elif error_code == "expired_token":
                return {"success": False, "pending": False, "error": "Device code expired, please try again"}
            else:
                logger.error(f"[OAuth2] Token request failed: {error_code} {error_desc}")
                return {"success": False, "pending": False, "error": f"Token request failed: {error_desc}"}
        except Exception as e:
            logger.error(f"[OAuth2] Token request error: {e}")
            return {"success": False, "pending": False, "error": str(e)}

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        data = {
            "client_id": self.client_id,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "scope": " ".join(MS_GRAPH_SCOPES),
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret

        req = urllib.request.Request(
            self._token_url_v2,
            data=urllib.parse.urlencode(data).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
                logger.info("[OAuth2] Access token refreshed successfully")
                return {
                    "success": True,
                    "access_token": result.get("access_token"),
                    "refresh_token": result.get("refresh_token", refresh_token),
                    "expires_in": result.get("expires_in", 3600),
                    "token_type": result.get("token_type", "Bearer"),
                }
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            logger.error(f"[OAuth2] Token refresh failed: {e.code} {error_body}")
            try:
                error_data = json.loads(error_body)
                error_desc = error_data.get("error_description", error_body)
            except Exception:
                error_desc = error_body
            return {"success": False, "error": f"Token refresh failed: {error_desc}"}
        except Exception as e:
            logger.error(f"[OAuth2] Token refresh error: {e}")
            return {"success": False, "error": str(e)}

    def get_authorization_url(self, redirect_uri: str, state: str = None) -> str:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": " ".join(MS_GRAPH_SCOPES),
            "response_mode": "query",
            "state": state or "agentmail_oauth2",
        }
        return f"{self._auth_url}?{urllib.parse.urlencode(params)}"

    def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        is_nativeclient = "nativeclient" in redirect_uri or "127.0.0.1" in redirect_uri or "localhost" in redirect_uri

        data = {
            "client_id": self.client_id,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "scope": " ".join(MS_GRAPH_SCOPES),
        }
        if self.client_secret and not is_nativeclient:
            data["client_secret"] = self.client_secret

        req = urllib.request.Request(
            self._token_url_v2,
            data=urllib.parse.urlencode(data).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
                logger.info("[OAuth2] Authorization code exchanged successfully")
                return {
                    "success": True,
                    "access_token": result.get("access_token"),
                    "refresh_token": result.get("refresh_token"),
                    "expires_in": result.get("expires_in", 3600),
                    "token_type": result.get("token_type", "Bearer"),
                }
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            logger.error(f"[OAuth2] Code exchange failed: {e.code} {error_body}")
            return {"success": False, "error": f"Code exchange failed: {error_body}"}
        except Exception as e:
            logger.error(f"[OAuth2] Code exchange error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def generate_xoauth2_string(username: str, access_token: str) -> str:
        auth_string = f"user={username}\x01auth=Bearer {access_token}\x01\x01"
        return base64.b64encode(auth_string.encode()).decode()


def get_valid_access_token(agent_id: str) -> Optional[str]:
    from database import get_db

    db = get_db(agent_id)
    config = db.get_config()
    if not config:
        return None

    auth_type = config.get("auth_type", "basic")
    if auth_type != "oauth2":
        return None

    oauth2_config = config.get("oauth2", {})
    access_token = oauth2_config.get("access_token")
    refresh_token = oauth2_config.get("refresh_token")
    expires_at = oauth2_config.get("token_expires_at", 0)
    client_id = oauth2_config.get("client_id")
    client_secret = oauth2_config.get("client_secret")

    if not access_token or not client_id:
        return None

    if time.time() < expires_at - 300:
        return access_token

    if not refresh_token:
        logger.warning(f"[OAuth2] No refresh token for agent {agent_id}, re-authorization required")
        return None

    handler = OutlookOAuth2Handler(client_id, client_secret)
    result = handler.refresh_access_token(refresh_token)

    if result.get("success"):
        new_access_token = result["access_token"]
        new_refresh_token = result.get("refresh_token", refresh_token)
        new_expires_in = result.get("expires_in", 3600)
        new_expires_at = time.time() + new_expires_in

        db.save_oauth2_tokens(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_at=new_expires_at,
        )

        logger.info(f"[OAuth2] Token refreshed for agent {agent_id}")
        return new_access_token
    else:
        logger.error(f"[OAuth2] Token refresh failed for agent {agent_id}: {result.get('error')}")
        return None
