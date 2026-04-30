# AgentMail Plugin 功能开发计划

> **日期**: 2026-04-30
> **版本**: v2.0

---

## 目标

实现完整的AgentMail邮件插件功能，包括传统邮箱配置增强、邮件管理（收件箱/发件箱/草稿箱/归档/回收站）、联系人管理、Agent隔离数据库。

---

## 技术栈

- **Backend**: Python, FastAPI, SQLAlchemy, SQLite
- **Frontend**: React, TypeScript, Ant Design (通过 QwenPaw host)
- **Database**: SQLite (Agent隔离)

---

## 任务清单

### Task 1: Agent隔离数据库设计

**文件:**
- Create: `backend/database.py`
- Create: `backend/models/database_models.py`

**数据库表结构:**

```sql
-- 邮件配置表 (每个Agent独立)
CREATE TABLE email_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    config_type TEXT NOT NULL, -- traditional, agentmail, hybrid
    provider TEXT, -- qq, 163, gmail, custom
    email TEXT,
    display_name TEXT,
    -- SMTP
    smtp_host TEXT,
    smtp_port INTEGER,
    smtp_username TEXT,
    smtp_password TEXT,
    smtp_use_tls BOOLEAN DEFAULT 1,
    -- IMAP/POP3
    receive_host TEXT,
    receive_port INTEGER,
    receive_username TEXT,
    receive_password TEXT,
    receive_use_ssl BOOLEAN DEFAULT 1,
    receive_protocol TEXT DEFAULT 'imap', -- imap, pop3
    -- AgentMail
    api_key TEXT,
    inbox_id TEXT,
    -- Hybrid
    forwarding BOOLEAN DEFAULT 0,
    default_mode TEXT DEFAULT 'traditional',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(agent_id, config_type)
);

-- 收件箱
CREATE TABLE inbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    message_id TEXT UNIQUE,
    subject TEXT,
    sender_name TEXT,
    sender_email TEXT,
    recipient TEXT,
    body TEXT,
    body_html TEXT,
    date TIMESTAMP,
    folder TEXT DEFAULT 'inbox', -- inbox, archive
    is_read BOOLEAN DEFAULT 0,
    is_agent_read BOOLEAN DEFAULT 0, -- Agent已读状态
    is_replied BOOLEAN DEFAULT 0, -- Agent回复状态
    reply_content TEXT, -- Agent回复内容
    labels TEXT, -- JSON数组
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 发件箱
CREATE TABLE sent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    message_id TEXT UNIQUE,
    subject TEXT,
    recipient TEXT,
    body TEXT,
    body_html TEXT,
    status TEXT DEFAULT 'pending', -- pending, sent, failed
    error_msg TEXT,
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 草稿箱
CREATE TABLE drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    subject TEXT,
    recipient TEXT,
    body TEXT,
    body_html TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 回收站
CREATE TABLE trash (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    item_type TEXT NOT NULL, -- inbox, sent, drafts, contact
    original_id INTEGER NOT NULL,
    data TEXT NOT NULL, -- JSON备份
    deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 联系人
CREATE TABLE contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT NOT NULL,
    company TEXT,
    website TEXT,
    notes TEXT,
    group_name TEXT DEFAULT 'default',
    shared_with TEXT, -- JSON数组 [agent_id1, agent_id2]
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 联系人分组
CREATE TABLE contact_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(agent_id, name)
);
```

---

### Task 2: 后端API开发

**文件:**
- Create: `backend/database.py` - 数据库连接和初始化
- Create: `backend/routes/config_routes.py` - 配置API
- Create: `backend/routes/email_routes.py` - 邮件API
- Create: `backend/routes/contact_routes.py` - 联系人API
- Modify: `backend/main.py` - 注册路由

**API端点:**

```python
# 配置API
GET    /api/v1/email/config/{agent_id}
POST   /api/v1/email/config/{agent_id}/traditional
POST   /api/v1/email/config/{agent_id}/agentmail
POST   /api/v1/email/config/{agent_id}/hybrid
DELETE /api/v1/email/config/{agent_id}
POST   /api/v1/email/config/{agent_id}/test

# 邮件API
GET    /api/v1/email/{agent_id}/inbox?page=&page_size=
POST   /api/v1/email/{agent_id}/inbox/{id}/read
POST   /api/v1/email/{agent_id}/inbox/{id}/agent-read
POST   /api/v1/email/{agent_id}/inbox/{id}/reply
POST   /api/v1/email/{agent_id}/inbox/archive
POST   /api/v1/email/{agent_id}/inbox/delete
POST   /api/v1/email/{agent_id}/inbox/batch-archive
POST   /api/v1/email/{agent_id}/inbox/batch-delete

GET    /api/v1/email/{agent_id}/sent?page=&page_size=
POST   /api/v1/email/{agent_id}/sent/delete
POST   /api/v1/email/{agent_id}/sent/batch-delete

GET    /api/v1/email/{agent_id}/drafts?page=&page_size=
POST   /api/v1/email/{agent_id}/drafts
PUT    /api/v1/email/{agent_id}/drafts/{id}
DELETE /api/v1/email/{agent_id}/drafts/{id}
POST   /api/v1/email/{agent_id}/drafts/batch-delete

GET    /api/v1/email/{agent_id}/archive?page=&page_size=
POST   /api/v1/email/{agent_id}/archive/restore

GET    /api/v1/email/{agent_id}/trash?page=&page_size=
POST   /api/v1/email/{agent_id}/trash/restore
DELETE /api/v1/email/{agent_id}/trash/permanent

# 联系人API
GET    /api/v1/email/{agent_id}/contacts?page=&page_size=&group=&search=
POST   /api/v1/email/{agent_id}/contacts
PUT    /api/v1/email/{agent_id}/contacts/{id}
DELETE /api/v1/email/{agent_id}/contacts/{id}
POST   /api/v1/email/{agent_id}/contacts/batch-delete
POST   /api/v1/email/{agent_id}/contacts/{id}/share
POST   /api/v1/email/{agent_id}/contacts/batch-share

GET    /api/v1/email/{agent_id}/contact-groups
POST   /api/v1/email/{agent_id}/contact-groups
DELETE /api/v1/email/{agent_id}/contact-groups/{id}
```

---

### Task 3: 前端UI开发

**文件:**
- Modify: `src/index.tsx` - 主页面重构

**Tab结构:**
```
Email Management
├── Contacts (联系人) - NEW, 默认页
│   ├── 搜索框
│   ├── 分组筛选
│   ├── 联系人列表 (15条/页)
│   ├── 新建/编辑/删除/共享/批量操作
│   └── 分页
├── Inbox (收件箱)
│   ├── 邮件列表
│   ├── Agent已读/回复状态标记
│   ├── 归档/删除/批量操作
│   └── 分页
├── Sent (发件箱)
│   ├── 邮件列表
│   ├── 发送状态标记
│   ├── 删除/批量删除
│   └── 分页
├── Drafts (草稿箱)
│   ├── 草稿列表
│   ├── 编辑/删除/批量删除
│   └── 分页
├── Archive (归档)
│   └── 归档邮件列表
└── Config (配置)
    └── 三种配置方式
```

---

### Task 4: 传统邮箱配置增强

**功能:**
1. 协议选择: IMAP/SMTP 或 POP3/SMTP
2. 邮箱提供商下拉菜单:
   - QQ邮箱 (预置: smtp.qq.com:587, imap.qq.com:993, 授权码提示)
   - 163邮箱 (预置: smtp.163.com:25, imap.163.com:993, 授权码提示)
   - Gmail (预置: smtp.gmail.com:587, imap.gmail.com:993)
   - Outlook (预置: smtp.office365.com:587, outlook.office365.com:993)
   - 自定义
3. 授权码机制:
   - 选择QQ/163时显示授权码输入框和密码输入框
   - 提示用户使用授权码而非登录密码

---

### Task 5: 回收站功能

**功能:**
- 左侧菜单: 回收站
- 分类显示: 收件箱/发件箱/草稿箱/联系人
- 操作: 恢复/永久删除
- 自动清理: 30天后自动永久删除

---

## 开发顺序

1. 数据库设计和初始化
2. 后端API开发 (配置/邮件/联系人)
3. 前端联系人Tab页面
4. 前端收件箱功能增强
5. 前端发件箱/草稿箱功能
6. 前端归档/回收站功能
7. 前端配置页面增强
8. 集成测试

---

## 数据库路径

```
~/.qwenpaw/agentmail/data/{agent_id}/agentmail.db
```

每个Agent有独立的数据库文件，实现完全隔离。
