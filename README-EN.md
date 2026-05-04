# AgentMail - QwenPaw Agent Email Plugin

<p align="center">
  <img src="https://img.shields.io/badge/QwenPaw-%E2%89%A5%201.1.0-blue.svg" alt="QwenPaw Version">
  <img src="https://img.shields.io/badge/version-1.2.0-green.svg" alt="Plugin Version">
  <img src="https://img.shields.io/badge/license-MIT-yellow.svg" alt="License">
  <img src="https://img.shields.io/badge/language-TypeScript%2FPython-orange.svg" alt="Languages">
  <img src="https://img.shields.io/badge/platform-Linux%20%7C%20Docker-lightgrey.svg" alt="Platform">
</p>

<p align="center">
  <strong>Every Agent Deserves Its Own Inbox</strong><br>
  Complete, isolated, real-time email capabilities for QwenPaw Agents
</p>

---

## Table of Contents

- [Overview](#overview)
- [Key Highlights](#key-highlights)
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Usage Guide](#usage-guide)
- [CLI Command Reference](#cli-command-reference)
- [Project Structure](#project-structure)
- [Development Guide](#development-guide)
- [Internationalization](#internationalization)
- [Troubleshooting](#troubleshooting)
- [CHANGELOG](#changelog)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

**AgentMail** is a dedicated email management plugin for the QwenPaw platform. It features an **Agent-isolated architecture** where each Agent gets its own independent SQLite database and email configuration, ensuring complete data isolation.

The plugin supports three categories of email access via a hybrid mode:

| Access Method | Protocol/API | Use Case |
|--------------|-------------|---------|
| **Traditional Email** | SMTP / IMAP / POP3 | QQ Mail, 163 Mail, Gmail, corporate email, etc. |
| **Microsoft Graph API** | OAuth2 + REST | Outlook.com personal accounts |
| **AgentMail.to** | REST API | AgentMail.to platform |

The backend runs on a dedicated port `18088`, while the frontend is built with React + Ant Design and seamlessly integrates into the QwenPaw sidebar.

---

## Key Highlights

### 1. Agent-Level Data Isolation

Each Agent's email data, contacts, and configuration are stored completely independently:

```
~/.qwenpaw/workspaces/{agent_id}/mail/
├── agentmail.db          # SQLite database (all emails, contacts, configs)
├── bak/                  # Database backups
└── files/                # Attachment storage
```

- Automatically retrieves Agent workspace paths via QwenPaw API
- Supports `QWENPAW_WORKING_DIR` environment variable for custom paths
- Automatic migration from legacy data paths

### 2. IMAP IDLE Real-Time Push

Uses **IMAP IDLE protocol (RFC 2177)** to maintain persistent connections with mail servers, enabling server-pushed notifications when new mail arrives:

```
Traditional Polling:
  Agent polls every 5 minutes → high latency, high resource usage

IMAP IDLE Mode:
  New mail arrives → server actively pushes → Agent notified instantly → zero latency, zero polling
```

- Auto-restores IMAP IDLE listeners for all configured Agents on startup
- New emails auto-saved to database with QwenPaw API notification
- Resource consumption reduced by 90%+ compared to polling

### 3. Email Context Injection

One-click injection of email content into the current Agent conversation:

1. User clicks the **"Add to Context"** button on an email
2. Email content is automatically formatted as structured text
3. Injected into Agent session via `sessionStorage`
4. Agent can immediately analyze, reply, or extract tasks

### 4. Context to Persistent Memory

Emails upgraded from temporary context to Agent long-term memory:

```
Email arrives → User clicks "Add to Memory" → System auto:
  1. Extracts email summary
  2. Generates smart tags (urgent/meeting/deadline/invoice/report)
  3. Calculates priority (levels 1-5)
  4. Stores to local JSON file (Agent-isolated)
```

### 5. CLI-First Design, Agent-Optimized

**12 CLI commands** covering all functionality -- Agents can operate without any GUI:

```bash
/agentmail-config     # Configure email
/agentmail-listen     # IMAP IDLE listener control
/agentmail-sync       # Sync emails
/agentmail-inbox      # View inbox
/agentmail-sent       # View sent
/agentmail-drafts     # View drafts
/agentmail-read       # Read email details
/agentmail-send       # Send email
/agentmail-contacts   # Contact management
/agentmail-share      # Contact sharing
/agentmail-trash      # Trash management
/agentmail-backup     # Backup management
```

### 6. Multi-Language Internationalization

Full support for four languages, automatically switching based on QwenPaw system locale:

| Language | Code | Coverage |
|----------|------|----------|
| Simplified Chinese | zh | 100% |
| English | en | 100% |
| Japanese | ja | 100% |
| Russian | ru | 100% |

### 7. Data Security & Transparency

- All data stored locally, never uploaded to cloud
- Sensitive fields (passwords, tokens) encrypted with XOR + Base64
- Fully auditable: SQLite files inspectable at any time
- Transparent configuration: all rules and memories stored in plain text, traceable and debuggable

---

## Features

### Email Management

- Full inbox / sent / drafts / trash management
- Plain text and HTML email support
- Attachment management (upload/download)
- Email search and sorting
- Batch operations (delete, archive, restore)
- Email status tracking (read/unread/replied)

### Contact Management

- Contact CRUD operations
- Group management (create/rename/delete groups)
- Contact search and filtering
- Cross-Agent contact sharing
- Quick-add contacts from recipients

### Email Composer

- Rich text editor (bold/italic/underline/colors/lists, etc.)
- Plain text / HTML dual-mode toggle
- Recipient autocomplete (from contacts)
- Auto-save drafts
- Attachment upload

### Email Configuration

- Preset email providers (QQ/163/126/Gmail/Outlook)
- Custom SMTP/IMAP/POP3 configuration
- OAuth2 authentication (Outlook.com)
- Connection test functionality
- Encrypted configuration storage

### Email Rules Engine

- Visual rule management
- Conditions: sender/subject/content matching
- Actions: tag/auto-reply/archive/notify Agent

### Backup & Recovery

- One-click SQLite database backup
- Automatic backup management (keeps last 10)
- 30-day auto-clean for trash

---

## Architecture

```
+-----------------------------------------------------------+
|                    QwenPaw Main Process                     |
|  +-----------------------+  +---------------------------+  |
|  |   plugin.py            |  |   dist/index.js           |  |
|  |   (Backend Entry)      |  |   (Frontend Entry)        |  |
|  |   - Start/stop backend |  |   - React + Ant Design    |  |
|  |   - CLI registration   |  |   - Sidebar integration   |  |
|  +-----------+-----------+  +---------------------------+  |
+--------------|---------------------------------------------+
               | Start/Stop
               v
+-----------------------------------------------------------+
|              AgentMail Backend (Port 18088)                |
|  +----------------+  +----------------+  +---------------+ |
|  |  FastAPI        |  |  IMAP IDLE     |  |  Graph Poll   | |
|  |  REST API       |  |  Listener      |  |  Listener     | |
|  +--------+-------+  +--------+-------+  +-------+-------+ |
|           |                   |                   |         |
|           v                   v                   v         |
|  +------------------------------------------------------+ |
|  |         Agent-Isolated SQLite Databases               | |
|  |  {workspace}/mail/agentmail.db                        | |
|  +------------------------------------------------------+ |
+-----------------------------------------------------------+
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend Framework | React 18 (JSX) |
| UI Library | Ant Design |
| Build Tool | Vite 5 |
| Backend Framework | FastAPI + Uvicorn |
| Database | SQLite3 (Agent-isolated) |
| Email Protocols | SMTP / IMAP / POP3 |
| External APIs | Microsoft Graph API / AgentMail.to API |
| Authentication | Basic Auth / OAuth2 (XOAUTH2) |

---

## Quick Start

### Requirements

- **QwenPaw** >= 1.1.0
- **Node.js** >= 18
- **Python** >= 3.8
- **Linux** or Docker environment (production deployment)

### Method 1: Local Installation

```bash
# 1. Clone the repository
git clone https://github.com/kingsa2026/qwenpaw-agentmail.git
cd qwenpaw-agentmail

# 2. Install dependencies and build frontend
npm install && npm run build

# 3. Copy to QwenPaw plugins directory
cp -r . ~/.qwenpaw/plugins/agentmail/

# 4. Restart QwenPaw (restart twice for full loading)
qwenpaw shutdown
qwenpaw app
```

### Method 2: Server Deployment

```powershell
# 1. Copy plugin files to server
scp -P 22 -r ./* root@192.168.10.132:/root/.qwenpaw/plugins/agentmail/

# 2. Restart QwenPaw service (twice)
ssh -p 22 root@192.168.10.132 "qwenpaw shutdown"
ssh -p 22 root@192.168.10.132 "source .qwenpaw/venv/bin/activate && nohup qwenpaw app --host 0.0.0.0 --port 8088 > /tmp/qwenpaw.log 2>&1 &"
```

### Method 3: Docker Deployment

```bash
# Use QWENPAW_WORKING_DIR for custom workspace path
docker run -d \
  -e QWENPAW_WORKING_DIR=/data/qwenpaw \
  -v /host/plugins:/data/qwenpaw/plugins \
  -p 8088:8088 \
  your-qwenpaw-image
```

### Verification

1. Open QwenPaw console in your browser
2. Check that **"AgentMail"** appears in the sidebar
3. Click the menu item and confirm the page loads correctly
4. Verify backend: `curl http://127.0.0.1:18088/health` should return `{"status":"ok"}`

---

## Usage Guide

### Configure Email

**Via Web UI:**
```
Sidebar → AgentMail → Settings → Email Config → Select Provider → Enter credentials → Save
```

**Via CLI:**
```bash
# Configure 163 Mail
/agentmail-config --set provider=mail163 email=agent@163.com \
  smtp_host=smtp.163.com smtp_port=25 smtp_username=agent smtp_password=your_auth_code \
  imap_host=imap.163.com imap_port=993 imap_username=agent imap_password=your_auth_code

# Configure Outlook (OAuth2)
In the Web UI, click "Connect Outlook" and follow the device code authorization flow
```

### Supported Email Providers

| Provider | SMTP Server | IMAP Server | Auth Method |
|----------|------------|------------|-------------|
| QQ Mail | smtp.qq.com:587 | imap.qq.com:993 | Auth Code |
| 163 Mail | smtp.163.com:25 | imap.163.com:993 | Auth Code |
| 126 Mail | smtp.126.com:25 | imap.126.com:993 | Auth Code |
| Gmail | smtp.gmail.com:587 | imap.gmail.com:993 | App Password |
| Outlook | smtp.office365.com:587 | outlook.office365.com:993 | OAuth2 |
| Custom | User-defined | User-defined | Password/Auth Code |

### Start Real-Time Listening

```bash
# Start IMAP IDLE listening (auto-push new emails)
/agentmail-listen --start

# Check listening status
/agentmail-listen

# Stop listening
/agentmail-listen --stop
```

Note: Since v1.2.0, the backend auto-restores IMAP IDLE listeners for all configured Agents on startup.

### Agent Integration Actions

In the inbox, each email provides three Agent action buttons:

| Button | Function | Description |
|--------|----------|-------------|
| **Add to Context** | Add to Context | Inject email into current Agent session for immediate analysis |
| **Add to Memory** | Add to Memory | Save email as Agent long-term memory, available across sessions |
| **Generate Reply** | Generate Reply | Auto-generate smart reply draft based on email content |

---

## CLI Command Reference

### Email Configuration

```bash
/agentmail-config                          # View current config
/agentmail-config --set key=value ...      # Set configuration
/agentmail-config --delete                 # Delete configuration
```

### Listening & Sync

```bash
/agentmail-listen                          # View listener status
/agentmail-listen --start                  # Start IMAP IDLE
/agentmail-listen --stop                   # Stop IMAP IDLE
/agentmail-sync                            # Sync inbox
/agentmail-sync --max 100                  # Sync (max 100 emails)
```

### Email Management

```bash
/agentmail-inbox                           # Inbox list
/agentmail-inbox --page 2                  # Pagination
/agentmail-inbox --unread                  # Unread only
/agentmail-sent                            # Sent list
/agentmail-sent --page 2                   # Pagination
/agentmail-drafts                          # Drafts list
/agentmail-drafts --page 2                 # Pagination
/agentmail-trash                           # Trash list
/agentmail-trash --restore 1,2,3           # Restore items
/agentmail-trash --delete 1,2,3            # Permanent delete
```

### Email Operations

```bash
/agentmail-read --id 123                   # Read email
/agentmail-read --id 123 --action context  # Add to context
/agentmail-read --id 123 --action memory   # Add to memory
/agentmail-send --to user@example.com --subject "Hello" --body "Content"
```

### Contact Management

```bash
/agentmail-contacts                        # Contact list
/agentmail-contacts --group default        # Filter by group
/agentmail-contacts --search "John"        # Search
/agentmail-share --contacts 1,2,3 --agents agent-2   # Share contacts
/agentmail-share --all --agents agent-2               # Share all
```

### Backup Management

```bash
/agentmail-backup                          # Create backup
/agentmail-backup --list                   # View backup list
```

---

## Project Structure

```
agentmail_temp/
├── plugin.json              # Plugin manifest (ID, version, deps, metadata)
├── plugin.py                # QwenPaw plugin entry (start/stop backend, CLI reg)
├── cli_commands.py          # CLI command handlers (12 commands)
├── __init__.py              # Python package init
├── package.json             # Node.js project config
├── package-lock.json        # Dependency lock file
├── tsconfig.json            # TypeScript compiler config
├── vite.config.ts           # Vite build config (ES module output)
├── pytest.ini               # Pytest configuration
├── .gitignore               # Git ignore rules
│
├── src/
│   └── index.tsx            # Frontend entry (React + Ant Design)
│
├── backend/                 # Python backend service
│   ├── main.py              # FastAPI app entry (port 18088)
│   ├── database.py          # SQLite database (Agent-isolated)
│   ├── email_sender.py      # Email sending (SMTP + Outlook API)
│   ├── email_receiver.py    # Email receiving (IMAP/POP3 + Outlook API)
│   ├── oauth2_handler.py    # Microsoft OAuth2 device code flow
│   ├── outlook_api_handler.py  # Microsoft Graph API wrapper
│   ├── imap_idle_listener.py   # IMAP IDLE real-time listener
│   ├── graph_poll_listener.py  # Graph API polling listener
│   └── routes/
│       ├── __init__.py
│       └── api_routes.py    # RESTful API routes (full CRUD)
│
├── tests/                   # Automated tests
│   ├── __init__.py
│   ├── test_api_routes.py
│   ├── test_cli_commands.py
│   ├── test_database.py
│   ├── test_plugin.py
│   └── test_webhooks.py
│
└── docs/                    # Design documentation
    ├── agent-switching-solution.md
    ├── development-plan.md
    └── language-adaptation-solution.md
```

---

## Development Guide

### Frontend Development

```bash
# Install dependencies
npm install

# Development mode (watch for changes)
npm run dev

# Production build
npm run build
```

The frontend accesses shared dependencies through the QwenPaw host environment:

```typescript
const { React, antd, antdIcons, i18n } = window.QwenPaw.host;
```

Build output is `dist/index.js` (ES module format), registered via `window.QwenPaw.registerRoutes`.

### Backend Development

```bash
# Install Python dependencies
pip install fastapi uvicorn httpx

# Start development server
python backend/main.py
```

API base path: `http://127.0.0.1:18088/api/v1/email`

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_database.py -v

# With coverage
pytest tests/ --cov=backend --cov=.
```

---

## Internationalization

AgentMail implements full four-language internationalization, automatically switching based on QwenPaw system settings:

| Language | Code | Translation Coverage |
|----------|------|---------------------|
| Simplified Chinese | zh | 100% |
| English | en | 100% |
| Japanese | ja | 100% |
| Russian | ru | 100% |

All UI text, form validation, error messages, and email templates have been translated.

---

## Troubleshooting

### Plugin Not Showing in Sidebar

1. Verify `plugin.json` format is correct
2. Confirm `dist/index.js` exists (run `npm run build`)
3. Check browser console for errors
4. Verify QwenPaw version >= 1.1.0
5. Try restarting QwenPaw twice

### Backend Service Not Starting

```bash
# Check port usage
lsof -i :18088

# Manually start backend
python backend/main.py

# Check logs
tail -f /tmp/qwenpaw.log
```

### Email Connection Failed

1. Verify account credentials and auth code
2. Confirm SMTP/IMAP service is enabled for the email account
3. Use the "Test Connection" button
4. Check network firewall settings
5. Review backend logs for detailed errors

### Outlook OAuth2 Authorization Issues

1. Verify Azure AD app registration with correct Redirect URI
2. Check Client ID and Client Secret correctness
3. Complete device code authorization flow and wait for token refresh

### Build Failed

```bash
# Clean and reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Verify Node.js version
node --version  # Must be >= 18
```

---

## CHANGELOG

See [CHANGELOG.md](./CHANGELOG.md) for details.

| Version | Date | Key Changes |
|---------|------|-------------|
| v1.2.0 | 2026-05-04 | OAuth2 support, Graph API, auto-restore listeners, encryption hardening |
| v1.1.0 | 2026-04 | IMAP IDLE real-time push, CLI commands, multi-language i18n |
| v1.0.0 | 2026-03 | Initial release, basic email send/receive |

---

## Contributing

Issues and Pull Requests are welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Create a Pull Request

Before submitting, please ensure:
- Code passes `pytest` tests
- Frontend builds successfully with `npm run build`
- Existing code style is followed

---

## License

This project is open source under the [MIT](LICENSE) license.

---

## Contact

- **GitHub Issues**: [Submit an issue](https://github.com/kingsa2026/qwenpaw-agentmail/issues)
- **Email**: 13953629@qq.com

---

<p align="center">
  Made with dedication for the QwenPaw Community
</p>
