# AgentMail 插件 - Agent 使用指南

> 本文档专为 QwenPaw Agent 设计，帮助 Agent 理解如何与 AgentMail 插件协作，为用户提供最佳的邮件管理体验。

## 插件概述

AgentMail 是 QwenPaw 的邮箱管理插件，核心特性：
- **每个 Agent 拥有独立邮箱**：每个 Agent 可绑定自己的邮箱账户，数据完全隔离
- **IMAP IDLE 实时推送**：新邮件到达时服务器主动通知，无需轮询，节省资源
- **CLI 命令支持**：12 个 CLI 命令覆盖所有功能，更适合 Agent 操作
- **WebUI 可人工操作**：数据透明，回归工程化本身，让 AI 没有黑盒
- **主流邮箱绑定**：支持 QQ/163/126/Gmail/Outlook 及自定义邮箱
- **邮件自动注入上下文**：新邮件自动通知 Agent，Agent 可即时阅读和回复
- **上下文形成持久记忆**：重要邮件可添加到 Agent 长期记忆

## 核心功能与 Agent 协作

### 1. IMAP IDLE 实时推送（核心亮点）

**功能说明**：
通过 IMAP IDLE 协议（RFC 2177）维持与邮件服务器的长连接，新邮件到达时服务器主动推送通知。

**工作原理**：
```
邮件服务器                    AgentMail 后端                    QwenPaw Agent
    │                              │                                │
    │  ←── IMAP IDLE 长连接 ──→   │                                │
    │  ── 新邮件 EXISTS 通知 ──→   │                                │
    │  ←── FETCH 获取内容 ──      │  1. 保存到数据库(inbox)         │
    │  ─── 邮件内容返回 ──→        │  2. 写入通知文件                │
    │                              │  3. 调用 QwenPaw API ──→       │
    │                              │     POST /agent/process/task   │
    │                              │                     Agent 收到  │
    │                              │                     自动阅读    │
    │                              │                     按规则回复  │
```

**Agent 应该**：
- 启动监听后，新邮件会自动通过 QwenPaw API 注入到 Agent 会话
- Agent 收到通知后可自动阅读邮件并根据规则决定是否回复
- 无需轮询，节省计算资源

**CLI 操作**：
```
/agentmail-listen --start       # 启动 IMAP IDLE 实时监听
/agentmail-listen --stop        # 停止监听
/agentmail-listen               # 查看监听状态
```

### 2. 邮件上下文感知（Email Context Awareness）

**功能说明**：
用户可以将任意邮件添加到当前 Agent 会话上下文中，Agent 可以基于邮件内容提供智能分析和建议。

**Agent 应该**：
- 当用户提到"看看这封邮件"、"帮我处理这封邮件"时，引导用户点击邮件的 **"Add to Context"** 按钮
- 邮件内容会自动注入到当前聊天会话的 `sessionStorage` 中
- Agent 可以通过分析邮件内容提供：
  - 邮件摘要和关键点提取
  - 回复建议
  - 任务提取和待办事项生成
  - 紧急程度评估

**数据格式**：
```
[Email Context]
From: {sender_email}
Subject: {subject}
Date: {date}
Content: {body_text}
[/Email Context]
```

**Agent 最佳实践**：
```
用户："帮我看看这封邮件"
Agent："请点击邮件右侧的 'Add to Context' 按钮，将邮件添加到当前会话中，然后我就可以帮您分析了。"

[用户添加邮件后]
Agent："这封邮件来自 {sender}，主题是 {subject}。主要内容涉及..."
```

### 3. 记忆集成（Memory Integration）

**功能说明**：
用户可以将重要邮件添加到 Agent 的长期记忆中，Agent 可以在后续对话中引用这些邮件信息。

**Agent 应该**：
- 建议用户将重要邮件添加到记忆："这封邮件包含重要信息，建议添加到记忆以便后续查阅"
- 记忆会自动提取标签和优先级：
  - **标签**：urgent, meeting, deadline, question, invoice, report
  - **优先级**：1-5 级（基于内容自动计算）

**记忆数据结构**：
```json
{
  "type": "email_memory",
  "emailId": "...",
  "subject": "...",
  "sender": "...",
  "summary": "邮件摘要...",
  "tags": ["urgent", "meeting"],
  "priority": 4,
  "timestamp": "..."
}
```

### 4. 智能回复（Smart Reply）

**功能说明**：
基于邮件内容自动生成回复草稿，支持多种场景识别。

**Agent 应该**：
- 识别邮件类型并提供针对性回复建议：
  - **紧急邮件**："我理解这封邮件的紧急性..."
  - **问题邮件**："感谢您的提问，让我整理一下信息..."
  - **会议邀请**："感谢您的会议邀请，我会确认日程..."
  - **一般邮件**：标准礼貌回复

### 5. 邮件规则引擎（Email Rules）

**功能说明**：
可视化规则管理，自动处理邮件。支持条件和动作的组合。

**规则结构**：
```
规则名称：{name}
条件：
  - 发件人包含：{sender}
  - 主题包含：{subject}
  - 内容包含：{content}
动作：
  - 标记为：{tag}
  - 使用模板回复
  - 归档
  - 通知 Agent
```

**Agent 最佳实践**：
```
用户："帮我设置自动处理规则"
Agent："我建议设置以下规则：
1. 来自 {boss@company.com} 的邮件 → 标记 urgent
2. 主题包含'发票' → 标记 invoice
3. 来自 {newsletter@example.com} → 自动归档

请告诉我您的具体需求，我可以帮您配置。"
```

## 多语言支持

AgentMail 支持四种语言，Agent 应该根据当前会话语言提供对应服务：

| 语言 | 代码 | 特点 |
|------|------|------|
| English | en | 默认语言 |
| 简体中文 | zh | 中文界面 |
| 日本語 | ja | 日文界面 |
| Русский | ru | 俄文界面 |

## 与用户交互的最佳实践

### 场景 1：新邮件到达（IMAP IDLE 推送）
```
[IMAP IDLE 自动检测到新邮件]
AgentMail 后端 → 保存到数据库 → 调用 QwenPaw API 通知 Agent

Agent："你收到一封新邮件！
📧 发件人: sender@example.com
📋 主题: 项目进度更新
📝 正文预览: ...

请根据你的邮件规则决定是否回复。
你可以使用 `agentmail read-inbox` 命令查看完整邮件内容，
使用 `agentmail send` 命令回复邮件。"
```

### 场景 2：手动同步邮件
```
用户："我有新邮件吗？"
Agent："让我帮你同步一下收件箱。"

[执行 /agentmail-sync]

Agent："同步完成！发现 3 封新邮件。要查看详情吗？"
```

### 场景 3：邮件分析请求
```
用户："这封邮件什么意思？"
Agent："请将邮件添加到上下文（Add to Context），我会为您：
1. 提取关键信息
2. 分析紧急程度
3. 建议后续行动"
```

### 场景 4：批量处理
```
用户："帮我处理这些邮件"
Agent："您可以：
1. 使用规则引擎自动分类
2. 批量选择邮件进行归档/删除
3. 将相关邮件添加到记忆，我可以帮您总结"
```

### 场景 5：CLI 批量共享联系人
```
用户："把联系人共享给其他 Agent"
Agent："您可以使用 CLI 命令快速共享：
1. 先查看联系人列表：`/agentmail-contacts`
2. 共享指定联系人：`/agentmail-share --contacts 1,2,3 --agents agent-2,agent-3`
3. 共享所有联系人：`/agentmail-share --all --agents agent-2`

也可以直接在 Web 界面勾选联系人和目标 Agent 进行共享。"
```

### 场景 6：配置邮箱
```
用户："帮我配置邮箱"
Agent："您可以使用 CLI 快速配置：

/agentmail-config --set provider=163 email=xxx@163.com smtp_host=smtp.163.com smtp_port=25 smtp_username=xxx smtp_password=授权码 imap_host=imap.163.com imap_port=993 imap_username=xxx imap_password=授权码

配置完成后，使用 `/agentmail-listen --start` 启动实时监听。"
```

## 技术集成细节

### 通知注入机制
- **方式一：QwenPaw API 注入**（推荐）
  - 调用 `POST /api/agent/process/task` 向 Agent 提交后台任务
  - Agent 会自动收到新邮件通知
  - 通过 `X-Agent-Id` 头指定目标 Agent

- **方式二：通知文件**
  - 写入 `~/.qwenpaw/agents/{agent_id}/agentmail_new_email.json`
  - Agent 可在下次对话时读取

### 上下文存储位置
- **Key**: `qwenpaw_pending_user_msg_{sessionId}`
- **存储**: `sessionStorage`（会话级别）
- **格式**: 结构化文本，包含邮件元数据和内容

### 记忆存储位置
- **路径**: `~/.qwenpaw/agents/{agent_id}/mail/agentmail_memory_{agent_id}.json`
- **存储**: 文件持久化
- **限制**: 最多 100 条记忆，自动去重

### 数据库存储位置
- **路径**: `{agent_workspace_dir}/mail/agentmail.db`
- **说明**: 数据库存储在 Agent 的工作空间目录下（通过 QwenPaw API 获取 `workspace_dir`）
- **类型**: SQLite
- **权限**: 755
- **备份**: `{agent_workspace_dir}/mail/bak/`

### 后端 API
- **基础 URL**: `http://127.0.0.1:18088/api/v1/email`
- **配置端点**: `GET/POST/DELETE /config/{agent_id}`
- **测试连接**: `POST /{agent_id}/test-connection`
- **收件箱**: `GET /{agent_id}/inbox`
- **发件箱**: `GET /{agent_id}/sent`
- **草稿箱**: `GET /{agent_id}/drafts`、`POST /{agent_id}/drafts`
- **发送邮件**: `POST /{agent_id}/send`（字段：to[], cc[], bcc[], subject, body, body_html）
- **同步邮件**: `POST /{agent_id}/sync`
- **监听控制**: `POST /{agent_id}/listen/start|stop`、`GET /{agent_id}/listen/status`
- **联系人**: `GET/POST /{agent_id}/contacts`、`PUT/DELETE /{agent_id}/contacts/{id}`
- **联系人共享**: `POST /{agent_id}/contacts/batch-share`（共享时在目标Agent创建副本）
- **备份**: `POST /{agent_id}/backup`
- **Agent信息**: `GET /agents`
- **卸载**: `POST /{agent_id}/uninstall`

## 故障排除指南

### 当用户遇到问题时，Agent 应该：

1. **插件未显示**
   - 检查 QwenPaw 版本是否 >= 1.1.0
   - 确认插件已正确安装
   - 建议重启 QwenPaw

2. **邮件发送失败**
   - 检查邮箱配置（SMTP 设置）
   - 确认授权码/密码正确
   - 检查网络连接

3. **收件箱为空**
   - 使用 `/agentmail-sync` 同步邮件
   - 或启动 IMAP IDLE 监听：`/agentmail-listen --start`
   - 确认 IMAP 配置正确

4. **IMAP IDLE 监听失败**
   - 确认邮箱支持 IMAP 协议
   - 检查 IMAP 用户名和授权码是否正确
   - 部分邮箱需要在网页端开启 IMAP 服务

5. **上下文未注入**
   - 确认有活跃的 Agent 会话
   - 检查 `sessionStorage` 是否有 `qwenpaw_pending_user_msg_*` 键
   - 建议重新点击 "Add to Context"

6. **记忆未保存**
   - 确认 Agent ID 正确
   - 检查文件权限
   - 建议清理旧记忆

## CLI 命令参考

AgentMail 提供 12 个 CLI 命令，覆盖 UI 所有功能，Agent 可以直接在对话中使用：

### 联系人管理

#### /agentmail-contacts - 列出联系人
```
/agentmail-contacts                          # 列出所有联系人
/agentmail-contacts --group default          # 按分组筛选
/agentmail-contacts --search "张三"           # 搜索联系人
```

#### /agentmail-share - 共享联系人
```
/agentmail-share --contacts 1,2,3 --agents agent-2,agent-3    # 共享指定联系人
/agentmail-share --all --agents agent-2                        # 共享所有联系人
```

**参数说明：**
- `--contacts`: 要共享的联系人 ID，多个用逗号分隔
- `--agents`: 目标 Agent ID，多个用逗号分隔
- `--all`: 共享所有联系人（与 --contacts 互斥）

### 邮件管理

#### /agentmail-inbox - 收件箱
```
/agentmail-inbox                    # 列出收件箱邮件
/agentmail-inbox --page 2           # 分页查看
/agentmail-inbox --unread           # 仅显示未读
```

#### /agentmail-sent - 已发送
```
/agentmail-sent                     # 列出已发送邮件
/agentmail-sent --page 2            # 分页查看
```

#### /agentmail-drafts - 草稿箱
```
/agentmail-drafts                   # 列出草稿
/agentmail-drafts --page 2          # 分页查看
```

#### /agentmail-read - 读取邮件
```
/agentmail-read --id 123                      # 查看邮件详情
/agentmail-read --id 123 --action context     # 添加到上下文
/agentmail-read --id 123 --action memory      # 添加到记忆
```

#### /agentmail-send - 发送邮件
```
/agentmail-send --to user@example.com --subject "Hello" --body "Content"
/agentmail-send --to user@example.com --subject "Hello" --body-file /path/to/content.txt
```

#### /agentmail-sync - 同步邮件（新增）
```
/agentmail-sync                     # 从IMAP/POP3服务器同步收件箱
/agentmail-sync --max 100           # 最大同步邮件数
```

#### /agentmail-listen - IMAP IDLE 监听（新增）
```
/agentmail-listen                   # 查看监听状态
/agentmail-listen --start           # 启动实时监听
/agentmail-listen --stop            # 停止监听
```

### 回收站管理

#### /agentmail-trash - 回收站
```
/agentmail-trash                          # 列出回收站
/agentmail-trash --page 2                 # 分页查看
/agentmail-trash --restore 1,2,3          # 恢复项目
/agentmail-trash --delete 1,2,3           # 永久删除
```

### 备份与配置

#### /agentmail-backup - 备份
```
/agentmail-backup                         # 创建备份
/agentmail-backup --list                  # 列出备份
```

#### /agentmail-config - 邮箱配置
```
/agentmail-config                         # 查看当前配置
/agentmail-config --set provider=163 email=xxx@163.com smtp_host=smtp.163.com smtp_port=25 smtp_username=xxx smtp_password=xxx imap_host=imap.163.com imap_port=993 imap_username=xxx imap_password=xxx
/agentmail-config --delete                # 删除配置
```

**配置参数说明：**
| 参数 | 说明 | 示例 |
|------|------|------|
| `provider` | 邮箱提供商 | qq, mail163, mail126, gmail, outlook, custom |
| `email` | 邮箱地址 | agent@163.com |
| `smtp_host` | SMTP 服务器 | smtp.163.com |
| `smtp_port` | SMTP 端口 | 25 或 465 |
| `smtp_username` | SMTP 用户名 | agent@163.com |
| `smtp_password` | SMTP 密码/授权码 | NTc4936RkZb9S9gn |
| `imap_host` | IMAP 服务器 | imap.163.com |
| `imap_port` | IMAP 端口 | 993 |
| `imap_username` | IMAP 用户名 | agent@163.com |
| `imap_password` | IMAP 密码/授权码 | NTc4936RkZb9S9gn |

### CLI 使用示例

**场景 1：首次配置邮箱并启动监听**
```
用户："帮我配置邮箱"
Agent："好的，我来帮你配置163邮箱。"

[执行 /agentmail-config --set provider=mail163 email=agent@163.com smtp_host=smtp.163.com smtp_port=25 smtp_username=agent smtp_password=授权码 imap_host=imap.163.com imap_port=993 imap_username=agent imap_password=授权码]

Agent："配置成功！现在启动实时监听："

[执行 /agentmail-listen --start]

Agent："IMAP IDLE 监听已启动！新邮件到达时会自动通知我，无需轮询。"
```

**场景 2：查看并共享联系人**
```
用户："把张三和李四的联系方式给 Agent-2"
Agent："我来帮您共享。先确认一下联系人 ID..."

[执行 /agentmail-contacts --search "张三"]

Agent："找到张三 (ID:1) 和李四 (ID:2)，现在共享给 agent-2："

[执行 /agentmail-share --contacts 1,2 --agents agent-2]

Agent："已成功共享！张三和李四的联系人信息现在 agent-2 也可以使用了。"
```

**场景 3：查看邮件并添加到上下文**
```
用户："帮我看看那封关于项目的邮件"
Agent："我先查找一下相关邮件..."

[执行 /agentmail-inbox]

Agent："找到一封邮件 (ID: 5)，让我查看详情："

[执行 /agentmail-read --id 5]

Agent："这封邮件是关于项目进度的... 需要我添加到上下文帮您分析吗？"

[执行 /agentmail-read --id 5 --action context]
```

**场景 4：发送邮件**
```
用户："给张三发一封邮件，告诉他会议改到明天"
Agent："好的，我来发送邮件。"

[执行 /agentmail-send --to zhangsan@example.com --subject "会议时间变更" --body "张三，明天的会议改到下午2点，请知悉。"]

Agent："邮件已发送成功！"
```

**场景 5：同步邮件**
```
用户："帮我检查一下有没有新邮件"
Agent："好的，我来同步收件箱。"

[执行 /agentmail-sync]

Agent："同步完成！服务器共有 15 封邮件，新同步 3 封。要查看详情吗？"
```

**场景 6：管理回收站**
```
用户："恢复昨天删除的那封邮件"
Agent："我先查看回收站..."

[执行 /agentmail-trash]

Agent："找到删除的邮件 (ID: 8)，现在恢复："

[执行 /agentmail-trash --restore 8]

Agent："邮件已恢复到收件箱。"
```

## 高级功能

### 自定义 Provider 支持
AgentMail 支持自定义邮件提供商，Agent 可以指导用户配置：
```
用户："我想用公司邮箱"
Agent："请选择 'Custom' 提供商，然后填写：
- SMTP 服务器：smtp.company.com
- SMTP 端口：587
- IMAP 服务器：imap.company.com
- IMAP 端口：993"
```

### 预设邮箱提供商
| 提供商 | SMTP | IMAP | 需要授权码 |
|--------|------|------|-----------|
| QQ 邮箱 | smtp.qq.com:587 | imap.qq.com:993 | 是 |
| 163 邮箱 | smtp.163.com:25 | imap.163.com:993 | 是 |
| 126 邮箱 | smtp.126.com:25 | imap.126.com:993 | 是 |
| Gmail | smtp.gmail.com:587 | imap.gmail.com:993 | 是（应用密码） |
| Outlook | smtp.office365.com:587 | outlook.office365.com:993 | 否 |

## 总结

AgentMail 插件为 Agent 提供了强大的邮件管理能力。作为 Agent，你应该：

1. **主动引导**用户使用 IMAP IDLE 实时监听，实现新邮件自动通知
2. **理解邮件内容**并提供有价值的分析
3. **管理用户记忆**帮助建立长期知识库
4. **优化工作流程**通过规则引擎提高效率
5. **善用 CLI 命令**快速完成邮件操作

记住：AgentMail 不仅是邮件客户端，更是 Agent 与用户协作的桥梁。充分利用 IMAP IDLE 推送和上下文注入功能，可以为用户提供更智能、更实时的邮件服务。

---

**文档版本**: v2.0.0  
**最后更新**: 2026-05-02  
**适用插件版本**: >= 2.0.0
