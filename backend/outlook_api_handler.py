import json
import logging
import urllib.request
import urllib.parse
import urllib.error
import ssl
import time
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


class OutlookAPIHandler:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self._ctx = ssl.create_default_context()

    def _request(self, method: str, path: str, data: Any = None) -> Dict[str, Any]:
        url = f"{GRAPH_API_BASE}{path}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        req = urllib.request.Request(url, headers=headers, method=method)
        if data is not None:
            req.data = json.dumps(data).encode()
        try:
            with urllib.request.urlopen(req, context=self._ctx, timeout=30) as resp:
                body = resp.read().decode()
                return {"success": True, "status": resp.getcode(), "data": json.loads(body) if body else None}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            logger.error(f"[OutlookAPI] {method} {path} failed: {e.code} {error_body}")
            return {"success": False, "status": e.code, "error": error_body}

    def get_messages(self, folder: str = "inbox", top: int = 20, skip: int = 0,
                     select: str = None, orderby: str = "receivedDateTime desc",
                     search: str = None) -> Dict[str, Any]:
        params = {"$top": top, "$skip": skip, "$orderby": orderby}
        if select:
            params["$select"] = select
        if search:
            params["$search"] = f'"{search}"'
        query = urllib.parse.urlencode(params)
        path = f"/me/mailFolders/{folder}/messages?{query}" if folder != "inbox" else f"/me/messages?{query}"
        return self._request("GET", path)

    def get_message(self, message_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/me/messages/{message_id}")

    def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/me/sendMail", {"message": message, "saveToSentItems": True})

    def reply_message(self, message_id: str, comment: str = "") -> Dict[str, Any]:
        body = {"message": {"body": {"content": comment, "contentType": "Text"}}}
        return self._request("POST", f"/me/messages/{message_id}/reply", body)

    def forward_message(self, message_id: str, comment: str = "",
                        to_recipients: List[Dict] = None) -> Dict[str, Any]:
        body = {"message": {"body": {"content": comment, "contentType": "Text"}}}
        if to_recipients:
            body["toRecipients"] = [{"emailAddress": r} for r in to_recipients]
        return self._request("POST", f"/me/messages/{message_id}/forward", body)

    def delete_message(self, message_id: str) -> Dict[str, Any]:
        return self._request("DELETE", f"/me/messages/{message_id}")

    def move_message(self, message_id: str, folder_id: str) -> Dict[str, Any]:
        return self._request("POST", f"/me/messages/{message_id}/move",
                             {"destinationId": folder_id})

    def update_message(self, message_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("PATCH", f"/me/messages/{message_id}", updates)

    def mark_as_read(self, message_id: str) -> Dict[str, Any]:
        return self.update_message(message_id, {"isRead": True})

    def get_folders(self) -> Dict[str, Any]:
        return self._request("GET", "/me/mailFolders")

    def create_folder(self, name: str, parent_folder_id: str = None) -> Dict[str, Any]:
        body = {"displayName": name}
        if parent_folder_id:
            return self._request("POST", f"/me/mailFolders/{parent_folder_id}/childFolders", body)
        return self._request("POST", "/me/mailFolders", body)

    def create_draft(self, message: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/me/messages", message)

    def send_draft(self, message_id: str) -> Dict[str, Any]:
        return self._request("POST", f"/me/messages/{message_id}/send")

    def get_attachments(self, message_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/me/messages/{message_id}/attachments")

    def download_attachment(self, message_id: str, attachment_id: str) -> Dict[str, Any]:
        return self._request("GET",
                             f"/me/messages/{message_id}/attachments/{attachment_id}/$value")
