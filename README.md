# AgentMail - QwenPaw 智能体邮箱插件

<p align="center">
  <img src="https://img.shields.io/badge/QwenPaw-%E2%89%A5%201.1.0-blue.svg" alt="QwenPaw Version">
  <img src="https://img.shields.io/badge/version-1.2.0-green.svg" alt="Plugin Version">
  <img src="https://img.shields.io/badge/license-MIT-yellow.svg" alt="License">
  <img src="https://img.shields.io/badge/language-TypeScript%2FPython-orange.svg" alt="Languages">
  <img src="https://img.shields.io/badge/platform-Linux%20%7C%20Docker-lightgrey.svg" alt="Platform">
</p>

<p align="center">
  <strong>每个 Agent 都值得拥有自己的邮箱</strong><br>
  为 QwenPaw 智能体提供完整、独立、实时的邮件处理能力
</p>

---

## 目录

- [项目简介](#项目简介)
- [核心亮点](#核心亮点)
- [功能特性](#功能特性)
- [技术架构](#技术架构)
- [快速开始](#快速开始)
- [使用指南](#使用指南)
- [CLI 命令参考](#cli-命令参考)
- [项目结构](#项目结构)
- [开发指南](#开发指南)
- [多语言支持](#多语言支持)
- [故障排查](#故障排查)
- [CHANGELOG](#changelog)
- [贡献指南](#贡献指南)
- [许可证](#许可证)

---

## 项目简介

**AgentMail** 是一个专为 QwenPaw 平台设计的智能体邮箱管理插件。它采用 **Agent 隔离架构**，每个 Agent 拥有独立的 SQLite 数据库和邮箱配置，实现完全的邮件数据隔离。

插件通过混合模式同时支持三大类邮件接入方式：

| 接入方式 | 协议/API | 适用场景 |
|---------|----------|---------|
| **传统邮箱** | SMTP / IMAP / POP3 | QQ邮箱、163邮箱、Gmail、企业邮箱等 |
| **Microsoft Graph API** | OAuth2 + REST | Outlook.com 个人账户 |
| **AgentMail.to** | REST API | AgentMail.to 平台 |

后端服务运行在独立端口 `18088`，前端以 React + Ant Design 构建，无缝集成到 QwenPaw 侧边栏。

---

## 核心亮点

### 1. Agent 级数据隔离

每个 Agent 的邮件数据、联系人、配置完全独立存储：

```
~/.qwenpaw/workspaces/{agent_id}/mail/
├── agentmail.db          # SQLite 数据库（所有邮件、联系人、配置）
├── bak/                  # 数据库备份
└── files/                # 附件存储
```

- 通过 QwenPaw API 自动获取 Agent 工作空间路径
- 支持 `QWENPAW_WORKING_DIR` 环境变量自定义路径
- 旧版本数据自动迁移至新路径

### 2. IMAP IDLE 实时推送

采用 **IMAP IDLE 协议（RFC 2177）** 维持与邮件服务器的长连接，新邮件到达时服务器主动推送通知：

```
传统轮询模式：
  Agent 每 5 分钟查询 → 高延迟、高资源消耗

IMAP IDLE 模式：
  新邮件到达 → 服务器主动推送 → Agent 立即获知 → 零延迟、零轮询
```

- 启动时自动恢复所有已配置 Agent 的 IMAP IDLE 监听
- 新邮件自动写入数据库，并通过 QwenPaw API 通知 Agent
- 资源消耗相比轮询降低 90% 以上

### 3. 邮件上下文注入

一键将邮件内容注入当前 Agent 会话上下文：

1. 用户点击邮件的 **"Add to Context"** 按钮
2. 邮件内容自动格式化为结构化文本
3. 通过 `sessionStorage` 注入到 Agent 会话
4. Agent 立即可以基于邮件进行分析、回复、提取任务

### 4. 上下文转化为持久记忆

邮件从临时上下文升级为 Agent 长期记忆：

```
邮件到达 → 用户点击 "Add to Memory" → 系统自动：
  1. 提取邮件摘要
  2. 生成智能标签（urgent/meeting/deadline/invoice/report）
  3. 计算优先级（1-5 级）
  4. 存储到本地 JSON 文件（Agent 级隔离）
```

### 5. CLI 命令优先，更适配 Agent 操作

提供 **12 个 CLI 命令**，覆盖所有功能，Agent 无需 GUI 即可完成全部操作：

```bash
/agentmail-config     # 配置邮箱
/agentmail-listen     # IMAP IDLE 监听控制
/agentmail-sync       # 同步邮件
/agentmail-inbox      # 查看收件箱
/agentmail-sent       # 查看已发送
/agentmail-drafts     # 查看草稿箱
/agentmail-read       # 读取邮件详情
/agentmail-send       # 发送邮件
/agentmail-contacts   # 联系人管理
/agentmail-share      # 联系人共享
/agentmail-trash      # 回收站管理
/agentmail-backup     # 备份管理
```

### 6. 多语言国际化

完整支持四种语言，自动根据 QwenPaw 系统语言切换：

| 语言 | 代码 | 覆盖率 |
|------|------|--------|
| 简体中文 | zh | 100% |
| English | en | 100% |
| 日本語 | ja | 100% |
| Русский | ru | 100% |

### 7. 数据安全透明

- 所有数据本地存储，不上传云端
- 敏感字段（密码、Token）采用 XOR + Base64 加密存储
- 数据可审计：SQLite 文件随时可查
- 配置透明：所有规则、记忆以明文存储，可追踪、可调试

---

## 功能特性

### 邮件管理

- 收件箱 / 发件箱 / 草稿箱 / 回收站完整管理
- 支持纯文本和 HTML 格式邮件
- 附件管理（上传/下载）
- 邮件搜索与排序
- 批量操作（删除、归档、恢复）
- 邮件状态追踪（已读/未读/已回复）

### 联系人管理

- 联系人 CRUD 操作
- 分组管理（创建/重命名/删除分组）
- 联系人搜索与筛选
- 跨 Agent 联系人共享
- 从收件人快速添加联系人

### 写邮件编辑器

- 富文本编辑器（加粗/斜体/下划线/颜色/列表等）
- 纯文本 / HTML 双模式切换
- 收件人自动补全（从联系人列表）
- 草稿自动保存
- 附件上传

### 邮箱配置

- 预设邮箱提供商（QQ/163/126/Gmail/Outlook）
- 自定义 SMTP/IMAP/POP3 配置
- OAuth2 认证（Outlook.com）
- 连接测试功能
- 配置加密存储

### 邮件规则引擎

- 可视化规则管理
- 条件：发件人/主题/内容匹配
- 动作：标记标签/自动回复/归档/通知 Agent

### 备份与恢复

- 一键备份 SQLite 数据库
- 备份文件自动管理（保留最近 10 个）
- 回收站 30 天自动清理

---

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    QwenPaw 主进程                         │
│  ┌─────────────────────┐  ┌───────────────────────────┐ │
│  │   plugin.py          │  │   dist/index.js           │ │
│  │   (后端入口)          │  │   (前端入口)              │ │
│  │   - 启停后端服务      │  │   - React + Ant Design    │ │
│  │   - CLI 命令注册      │  │   - 侧边栏集成            │ │
│  └─────────┬───────────┘  └───────────────────────────┘ │
└────────────┼────────────────────────────────────────────┘
             │ 启动/停止
             ▼
┌─────────────────────────────────────────────────────────┐
│                AgentMail 后端 (Port 18088)               │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │  FastAPI      │  │  IMAP IDLE   │  │  Graph Poll   │ │
│  │  REST API     │  │  Listener    │  │  Listener     │ │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘ │
│         │                 │                   │         │
│         ▼                 ▼                   ▼         │
│  ┌──────────────────────────────────────────────────┐  │
│  │           Agent 隔离 SQLite 数据库                  │  │
│  │  {workspace}/mail/agentmail.db                    │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术 |
|------|------|
| 前端框架 | React 18 (JSX) |
| UI 组件库 | Ant Design |
| 构建工具 | Vite 5 |
| 后端框架 | FastAPI + Uvicorn |
| 数据库 | SQLite3 (Agent 隔离) |
| 邮件协议 | SMTP / IMAP / POP3 |
| 外部 API | Microsoft Graph API / AgentMail.to API |
| 认证 | Basic Auth / OAuth2 (XOAUTH2) |

---

## 快速开始

### 环境要求

- **QwenPaw** >= 1.1.0
- **Node.js** >= 18
- **Python** >= 3.8
- **Linux** 或 Docker 环境（生产部署）

### 方式一：本地安装

```bash
# 1. 克隆仓库
git clone https://github.com/kingsa2026/qwenpaw-agentmail.git
cd qwenpaw-agentmail

# 2. 安装依赖并构建前端
npm install && npm run build

# 3. 复制到 QwenPaw 插件目录
cp -r . ~/.qwenpaw/plugins/agentmail/

# 4. 重启 QwenPaw（需要重启两次以完整加载）
qwenpaw shutdown
qwenpaw app
```

### 方式二：服务器部署

```powershell
# 1. 复制插件文件到服务器
scp -P 22 -r ./* root@192.168.10.132:/root/.qwenpaw/plugins/agentmail/

# 2. 重启 QwenPaw 服务（两次）
ssh -p 22 root@192.168.10.132 "qwenpaw shutdown"
ssh -p 22 root@192.168.10.132 "source .qwenpaw/venv/bin/activate && nohup qwenpaw app --host 0.0.0.0 --port 8088 > /tmp/qwenpaw.log 2>&1 &"
```

### 方式三：Docker 部署

```bash
# 使用 QWENPAW_WORKING_DIR 自定义工作空间路径
docker run -d \
  -e QWENPAW_WORKING_DIR=/data/qwenpaw \
  -v /host/plugins:/data/qwenpaw/plugins \
  -p 8088:8088 \
  your-qwenpaw-image
```

### 安装验证

1. 打开浏览器访问 QwenPaw 控制台
2. 检查侧边栏是否出现 **"AgentMail"** 菜单
3. 点击菜单，确认页面正常加载
4. 检查后端服务：`curl http://127.0.0.1:18088/health` 应返回 `{"status":"ok"}`

---

## 使用指南

### 配置邮箱

**通过 Web UI：**
```
侧边栏 → AgentMail → 设置 → 邮箱配置 → 选择提供商 → 填写账号密码 → 保存
```

**通过 CLI：**
```bash
# 配置 163 邮箱
/agentmail-config --set provider=mail163 email=agent@163.com \
  smtp_host=smtp.163.com smtp_port=25 smtp_username=agent smtp_password=授权码 \
  imap_host=imap.163.com imap_port=993 imap_username=agent imap_password=授权码

# 配置 Outlook（OAuth2）
在 Web UI 中点击 "Connect Outlook"，按提示完成设备代码授权流程
```

### 支持的邮箱提供商

| 提供商 | SMTP 服务器 | IMAP 服务器 | 认证方式 |
|--------|------------|------------|---------|
| QQ 邮箱 | smtp.qq.com:587 | imap.qq.com:993 | 授权码 |
| 163 邮箱 | smtp.163.com:25 | imap.163.com:993 | 授权码 |
| 126 邮箱 | smtp.126.com:25 | imap.126.com:993 | 授权码 |
| Gmail | smtp.gmail.com:587 | imap.gmail.com:993 | 应用密码 |
| Outlook | smtp.office365.com:587 | outlook.office365.com:993 | OAuth2 |
| 自定义 | 用户自定义 | 用户自定义 | 密码/授权码 |

### 启动实时监听

```bash
# 启动 IMAP IDLE 监听（新邮件自动推送）
/agentmail-listen --start

# 查看监听状态
/agentmail-listen

# 停止监听
/agentmail-listen --stop
```

注意：后端启动时（v1.2.0+）会自动恢复所有已配置 Agent 的 IMAP IDLE 监听。

### Agent 集成操作

在收件箱中，每封邮件提供三个 Agent 操作按钮：

| 按钮 | 功能 | 说明 |
|------|------|------|
| **Add to Context** | 添加到上下文 | 将邮件内容注入当前 Agent 会话，Agent 可以立即分析 |
| **Add to Memory** | 添加到记忆 | 保存邮件为 Agent 长期记忆，跨会话可用 |
| **Generate Reply** | 生成回复 | 基于邮件内容生成智能回复草稿 |

---

## CLI 命令参考

### 邮箱配置

```bash
/agentmail-config                          # 查看当前配置
/agentmail-config --set key=value ...      # 设置配置
/agentmail-config --delete                 # 删除配置
```

### 邮件监听与同步

```bash
/agentmail-listen                          # 查看监听状态
/agentmail-listen --start                  # 启动 IMAP IDLE
/agentmail-listen --stop                   # 停止 IMAP IDLE
/agentmail-sync                            # 同步收件箱
/agentmail-sync --max 100                  # 同步（最多 100 封）
```

### 邮件管理

```bash
/agentmail-inbox                           # 收件箱列表
/agentmail-inbox --page 2                  # 分页
/agentmail-inbox --unread                  # 仅未读
/agentmail-sent                            # 已发送列表
/agentmail-sent --page 2                   # 分页
/agentmail-drafts                          # 草稿箱列表
/agentmail-drafts --page 2                 # 分页
/agentmail-trash                           # 回收站列表
/agentmail-trash --restore 1,2,3           # 恢复
/agentmail-trash --delete 1,2,3            # 永久删除
```

### 邮件操作

```bash
/agentmail-read --id 123                   # 读取邮件
/agentmail-read --id 123 --action context  # 添加到上下文
/agentmail-read --id 123 --action memory   # 添加到记忆
/agentmail-send --to user@example.com --subject "Hello" --body "Content"
```

### 联系人管理

```bash
/agentmail-contacts                        # 联系人列表
/agentmail-contacts --group default        # 按分组筛选
/agentmail-contacts --search "张三"        # 搜索
/agentmail-share --contacts 1,2,3 --agents agent-2   # 共享联系人
/agentmail-share --all --agents agent-2               # 共享全部
```

### 备份管理

```bash
/agentmail-backup                          # 创建备份
/agentmail-backup --list                   # 查看备份列表
```

---

## 项目结构

```
agentmail_temp/
├── plugin.json              # 插件清单（ID、版本、依赖、元数据）
├── plugin.py                # QwenPaw 插件入口（启停后端、注册 CLI）
├── cli_commands.py          # CLI 命令处理器（12 个命令）
├── __init__.py              # Python 包初始化
├── package.json             # Node.js 项目配置
├── package-lock.json        # 依赖锁文件
├── tsconfig.json            # TypeScript 编译配置
├── vite.config.ts           # Vite 构建配置（ES 模块输出）
├── pytest.ini               # Pytest 测试配置
├── .gitignore               # Git 忽略规则
│
├── src/
│   └── index.tsx            # 前端主入口（React + Ant Design）
│
├── backend/                 # Python 后端服务
│   ├── main.py              # FastAPI 应用入口（端口 18088）
│   ├── database.py          # SQLite 数据库管理（Agent 隔离）
│   ├── email_sender.py      # 邮件发送（SMTP + Outlook API）
│   ├── email_receiver.py    # 邮件接收（IMAP/POP3 + Outlook API）
│   ├── oauth2_handler.py    # Microsoft OAuth2 设备代码流
│   ├── outlook_api_handler.py  # Microsoft Graph API 封装
│   ├── imap_idle_listener.py   # IMAP IDLE 实时监听器
│   ├── graph_poll_listener.py  # Graph API 轮询监听器
│   └── routes/
│       ├── __init__.py
│       └── api_routes.py    # RESTful API 路由（完整 CRUD）
│
├── tests/                   # 自动化测试
│   ├── __init__.py
│   ├── test_api_routes.py
│   ├── test_cli_commands.py
│   ├── test_database.py
│   ├── test_plugin.py
│   └── test_webhooks.py
│
└── docs/                    # 设计文档
    ├── agent-switching-solution.md
    ├── development-plan.md
    └── language-adaptation-solution.md
```

---

## 开发指南

### 前端开发

```bash
# 安装依赖
npm install

# 开发模式（监听文件变化自动构建）
npm run dev

# 生产构建
npm run build
```

前端通过 QwenPaw 宿主环境获取共享依赖：

```typescript
const { React, antd, antdIcons, i18n } = window.QwenPaw.host;
```

构建输出为 `dist/index.js`（ES 模块格式），通过 `window.QwenPaw.registerRoutes` 注册路由。

### 后端开发

```bash
# 安装 Python 依赖
pip install fastapi uvicorn httpx

# 启动开发服务器
python backend/main.py
```

后端 API 基础路径：`http://127.0.0.1:18088/api/v1/email`

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_database.py -v

# 带覆盖率
pytest tests/ --cov=backend --cov=.
```

---

## 多语言支持

AgentMail 实现完整四语言国际化，自动根据 QwenPaw 系统设置切换：

| 语言 | 代码 | 翻译覆盖率 |
|------|------|-----------|
| 简体中文 | zh | 100% |
| English | en | 100% |
| 日本語 | ja | 100% |
| Русский | ru | 100% |

界面文本、表单验证、错误提示、邮件模板均已翻译。

---

## 故障排查

### 插件未在侧边栏显示

1. 检查 `plugin.json` 格式是否正确
2. 确认 `dist/index.js` 存在（运行 `npm run build`）
3. 查看浏览器控制台错误
4. 确认 QwenPaw 版本 >= 1.1.0
5. 尝试重启 QwenPaw 两次

### 后端服务未启动

```bash
# 检查端口占用
lsof -i :18088

# 手动启动后端
python backend/main.py

# 查看日志
tail -f /tmp/qwenpaw.log
```

### 邮箱连接失败

1. 检查账号和授权码是否正确
2. 确认邮箱的 SMTP/IMAP 服务已开启
3. 使用 "Test Connection" 按钮测试
4. 检查网络防火墙设置
5. 查看后端日志获取详细错误

### Outlook OAuth2 授权问题

1. 确认已注册 Azure AD 应用并配置正确的 Redirect URI
2. 检查 Client ID 和 Client Secret 是否正确
3. 完成设备代码授权流程后等待 Token 刷新

### 构建失败

```bash
# 清理依赖重新安装
rm -rf node_modules package-lock.json
npm install

# 确认 Node.js 版本
node --version  # 需要 >= 18
```

---

## CHANGELOG

详见 [CHANGELOG.md](./CHANGELOG.md)

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| v1.2.0 | 2026-05-04 | OAuth2 支持、Graph API、自动恢复监听、加密增强 |
| v1.1.0 | 2026-04 | IMAP IDLE 实时推送、CLI 命令、多语言国际化 |
| v1.0.0 | 2026-03 | 初始版本，基础邮件收发功能 |

---

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

提交前请确保：
- 代码通过 `pytest` 测试
- 前端通过 `npm run build` 构建成功
- 遵循现有代码风格

---

## 许可证

本项目基于 [MIT](LICENSE) 许可证开源。

---

## 联系方式

- **GitHub Issues**: [提交问题](https://github.com/kingsa2026/qwenpaw-agentmail/issues)
- **邮箱**: 13953629@qq.com

---

<p align="center">
  Made with dedication for the QwenPaw Community
</p>
