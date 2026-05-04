# CHANGELOG

All notable changes to the AgentMail plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] - 2026-05-04

### Added

- **Microsoft Graph API integration** for Outlook.com personal accounts via [outlook_api_handler.py](file:///e:/QwenPaw插件/AgentsEmail/agentmail_temp/backend/outlook_api_handler.py)
  - Send/receive emails through Microsoft Graph REST API
  - Sync inbox from Graph API with message deduplication
  - Full `sendMessage`, `getMessages`, `replyMessage` support
- **OAuth2 device code flow** for Outlook authentication via [oauth2_handler.py](file:///e:/QwenPaw插件/AgentsEmail/agentmail_temp/backend/oauth2_handler.py)
  - Microsoft device code authorization (`MS_DEVICE_CODE_URL`)
  - Token lifecycle management (acquire, refresh, expiry detection)
  - IMAP `XOAUTH2` SASL authentication support
- **OAuth2 field support** in database schema (`auth_type`, `oauth2_client_id`, `oauth2_client_secret`, `oauth2_access_token`, `oauth2_refresh_token`, `oauth2_token_expires_at`)
  - Automatic schema migration for existing databases
  - Encrypted token storage (XOR + Base64)
- **Graph API polling listener** via [graph_poll_listener.py](file:///e:/QwenPaw插件/AgentsEmail/agentmail_temp/backend/graph_poll_listener.py)
  - Periodic polling for Outlook accounts without IMAP IDLE
  - Graceful start/stop with configurable polling interval
- **Auto-restore listeners on backend startup**
  - [main.py](file:///e:/QwenPaw插件/AgentsEmail/agentmail_temp/backend/main.py) automatically restarts IMAP IDLE for configured IMAP agents
  - Automatically starts Graph poll listeners for OAuth2 Outlook agents
  - Runs 3 seconds after startup to ensure database readiness
- **OAuth2 SMTP authentication** (XOAUTH2) in [email_sender.py](file:///e:/QwenPaw插件/AgentsEmail/agentmail_temp/backend/email_sender.py)
- **OAuth2 IMAP authentication** (XOAUTH2) in [email_receiver.py](file:///e:/QwenPaw插件/AgentsEmail/agentmail_temp/backend/email_receiver.py)
- **Agent workspace path resolution** via QwenPaw REST API (`GET /api/agents`)
  - Cached workspace directory lookup
  - Fallback to filesystem scanning when API unavailable
- **Data migration** from legacy path `~/.qwenpaw/agents/{id}/mail/` to `{workspace_dir}/mail/`
- **Environment variable support**: `QWENPAW_WORKING_DIR`, `QWENPAW_API_BASE`
- **Sensitive field encryption**: XOR + Base64 for passwords, tokens, and secrets (both Python backend and TypeScript frontend)
- **IMAP ID command** sent on connection to improve server compatibility
- **Configurable CORS origins** via `AGENTMAIL_CORS_ORIGINS` environment variable

### Changed

- `plugin.json` version bumped from `1.1.0` to `1.2.0`
- `package.json` version bumped from `1.1.0` to `1.2.0`
- `plugin.py` internal version updated to `1.2.0`
- Backend `main.py` API version updated from `1.0.0` to `2.0.0`
- Database initialization now includes OAuth2 column migration
- Email configuration now unified (removed `config_type` distinction between hybrid/traditional/agentmail)
- Contact sharing now creates copies in target Agent databases
- README documentation completely rewritten with bilingual support

### Security

- Password fields encrypted at rest (was plain text)
- OAuth2 tokens encrypted at rest
- Agent ID validation hardened (regex pattern check, path traversal prevention)
- Graceful backend shutdown with proper listener cleanup

---

## [1.1.0] - 2026-04

### Added

- **IMAP IDLE real-time push** via [imap_idle_listener.py](file:///e:/QwenPaw插件/AgentsEmail/agentmail_temp/backend/imap_idle_listener.py)
  - Persistent connection with mail servers (RFC 2177)
  - Server-pushed `EXISTS` notifications for new mail
  - Auto-sync to local database on new mail arrival
  - Resource savings: 90%+ reduction vs. polling
- **12 CLI commands** for Agent operations
  - `/agentmail-config` - email configuration
  - `/agentmail-listen` - IMAP IDLE listener control
  - `/agentmail-sync` - inbox synchronization
  - `/agentmail-inbox` - inbox listing with pagination
  - `/agentmail-sent` - sent folder listing
  - `/agentmail-drafts` - drafts listing
  - `/agentmail-read` - email detail reading
  - `/agentmail-send` - email sending
  - `/agentmail-contacts` - contact listing with search/filter
  - `/agentmail-share` - cross-Agent contact sharing
  - `/agentmail-trash` - trash management (restore/delete)
  - `/agentmail-backup` - backup creation and listing
- **Four-language internationalization** (zh/en/ja/ru) at 100% coverage
- **Email context injection** (Add to Context)
- **Email memory persistence** (Add to Memory) with smart tagging
- **Contact group management** (create/rename/delete groups)
- **Email rules engine** with visual rule configuration
- **Rich text email composer** with HTML/plain text toggle
- **Recycle bin** with 30-day auto-cleanup
- **Backup system** with auto-management (keeps last 10 backups)

### Technical Foundation

- React 18 + Ant Design frontend integrated into QwenPaw sidebar
- FastAPI backend on port 18088 with full REST API
- Agent-isolated SQLite database architecture
- SMTP/IMAP/POP3 protocol support
- Plugin lifecycle hooks (startup/shutdown)

---

## [1.0.0] - 2026-03

### Added

- Initial release of AgentMail plugin for QwenPaw
- Basic SMTP email sending
- Basic IMAP/POP3 email receiving and synchronization
- Simple contact management (CRUD)
- Web UI integration via QwenPaw sidebar
- Plugin manifest and entry point structure
- Database schema for email configuration, inbox, sent, drafts
