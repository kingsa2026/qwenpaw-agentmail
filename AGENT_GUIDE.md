# AgentMail 插件 - Agent 使用指南

> 本文档专为 QwenPaw Agent 设计，帮助 Agent 理解如何与 AgentMail 插件协作，为用户提供最佳的邮件管理体验。

## 插件概述

AgentMail 是 QwenPaw 的邮箱管理插件，采用**混合模式**同时支持：
- **传统邮箱**：POP3/IMAP/SMTP 协议（QQ/163/126/Gmail/Outlook）
- **AgentMail.to**：新一代智能邮件服务
- **混合模式**：同时管理传统邮箱和 AgentMail.to 账户

## 核心功能与 Agent 协作

### 1. 邮件上下文感知（Email Context Awareness）

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

### 2. 记忆集成（Memory Integration）

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

**Agent 最佳实践**：
```
用户："记住这封邮件"
Agent："已为您添加到记忆。这封邮件被标记为 [urgent] [meeting]，优先级 4/5。后续您可以问我'之前那封关于会议的邮件说了什么'。"
```

### 3. 智能回复（Smart Reply）

**功能说明**：
基于邮件内容自动生成回复草稿，支持多种场景识别。

**Agent 应该**：
- 识别邮件类型并提供针对性回复建议：
  - **紧急邮件**："我理解这封邮件的紧急性..."
  - **问题邮件**："感谢您的提问，让我整理一下信息..."
  - **会议邀请**："感谢您的会议邀请，我会确认日程..."
  - **一般邮件**：标准礼貌回复

**Agent 最佳实践**：
```
用户："帮我回复这封邮件"
Agent："请点击 'Generate Reply' 按钮，系统会根据邮件内容生成合适的回复草稿。然后您可以：
1. 直接发送
2. 让我帮您修改
3. 重新生成"
```

### 4. 邮件规则引擎（Email Rules）

**功能说明**：
可视化规则管理，自动处理邮件。支持条件和动作的组合。

**Agent 应该**：
- 帮助用户创建高效的邮件处理规则
- 建议常见的规则模板：
  - "来自老板的邮件 → 标记为 urgent"
  - "主题包含'发票' → 标记为 invoice"
  - "来自特定客户 → 自动归档"

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

**Agent 注意事项**：
- 所有翻译键以 `agent.` 或 `email.` 开头
- 使用 `t('key')` 函数获取翻译
- 如果翻译缺失，回退到英文

## 与用户交互的最佳实践

### 场景 1：新邮件到达
```
用户："我有新邮件吗？"
Agent："请打开 AgentMail 插件查看收件箱。如果有重要邮件，您可以：
1. 点击 'Add to Context' 让我帮您分析
2. 点击 'Add to Memory' 保存重要信息
3. 点击 'Generate Reply' 快速回复"
```

### 场景 2：邮件分析请求
```
用户："这封邮件什么意思？"
Agent："请将邮件添加到上下文（Add to Context），我会为您：
1. 提取关键信息
2. 分析紧急程度
3. 建议后续行动"
```

### 场景 3：批量处理
```
用户："帮我处理这些邮件"
Agent："您可以：
1. 使用规则引擎自动分类
2. 批量选择邮件进行归档/删除
3. 将相关邮件添加到记忆，我可以帮您总结"
```

### 场景 4：邮件搜索
```
用户："找一下上周关于项目的邮件"
Agent："请在 AgentMail 中使用搜索功能。如果找到相关邮件，可以添加到上下文，我可以帮您整理项目进展。"
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

## 技术集成细节

### 上下文存储位置
- **Key**: `qwenpaw_pending_user_msg_{sessionId}`
- **存储**: `sessionStorage`（会话级别）
- **格式**: 结构化文本，包含邮件元数据和内容

### 记忆存储位置
- **Key**: `agentmail_memory_{agentId}`
- **存储**: `localStorage`（长期存储）
- **限制**: 最多 100 条记忆，自动去重

### 规则存储位置
- **Key**: `agentmail_rules_{agentId}`
- **存储**: `localStorage`
- **应用**: 新邮件到达时自动匹配

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

3. **上下文未注入**
   - 确认有活跃的 Agent 会话
   - 检查 `sessionStorage` 是否有 `qwenpaw_pending_user_msg_*` 键
   - 建议重新点击 "Add to Context"

4. **记忆未保存**
   - 确认 Agent ID 正确
   - 检查 `localStorage` 空间是否已满
   - 建议清理旧记忆

## CLI 命令参考

AgentMail 提供完整的 CLI 控制命令，覆盖 UI 所有功能，Agent 可以直接在对话中使用：

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
/agentmail-inbox --search "项目"     # 搜索邮件
```

#### /agentmail-sent - 已发送
```
/agentmail-sent                     # 列出已发送邮件
/agentmail-sent --page 2            # 分页查看
/agentmail-sent --search "合同"      # 搜索邮件
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

#### /agentmail-config - 配置
```
/agentmail-config                         # 查看当前配置
/agentmail-config --set-mode hybrid       # 切换到混合模式
/agentmail-config --set-mode traditional  # 切换到传统邮箱
/agentmail-config --set-mode agentmail    # 切换到 AgentMail.to
```

### CLI 使用示例

**场景 1：查看并共享联系人**
```
用户："把张三和李四的联系方式给 Agent-2"
Agent："我来帮您共享。先确认一下联系人 ID..."

[执行 /agentmail-contacts --search "张三"]

Agent："找到张三 (ID:1) 和李四 (ID:2)，现在共享给 agent-2："

[执行 /agentmail-share --contacts 1,2 --agents agent-2]

Agent："已成功共享！张三和李四的联系人信息现在 agent-2 也可以使用了。"
```

**场景 2：查看邮件并添加到上下文**
```
用户："帮我看看那封关于项目的邮件"
Agent："我先查找一下相关邮件..."

[执行 /agentmail-inbox --search "项目"]

Agent："找到一封邮件 (ID: 5)，让我查看详情："

[执行 /agentmail-read --id 5]

Agent："这封邮件是关于项目进度的... 需要我添加到上下文帮您分析吗？"

[执行 /agentmail-read --id 5 --action context]
```

**场景 3：发送邮件**
```
用户："给张三发一封邮件，告诉他会议改到明天"
Agent："好的，我来发送邮件。"

[执行 /agentmail-send --to zhangsan@example.com --subject "会议时间变更" --body "张三，明天的会议改到下午2点，请知悉。"]

Agent："邮件已发送成功！"
```

**场景 4：管理回收站**
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

### 混合模式切换
```
用户："我想同时使用 Gmail 和 AgentMail.to"
Agent："请在设置中选择 'Hybrid' 模式，然后分别配置两个账户。混合模式下您可以：
1. 在统一界面查看所有邮件
2. 分别管理两个账户的设置
3. 使用相同的 Agent 集成功能"
```

## 总结

AgentMail 插件为 Agent 提供了强大的邮件管理能力。作为 Agent，你应该：

1. **主动引导**用户使用 Agent 集成功能
2. **理解邮件内容**并提供有价值的分析
3. **管理用户记忆**帮助建立长期知识库
4. **优化工作流程**通过规则引擎提高效率

记住：AgentMail 不仅是邮件客户端，更是 Agent 与用户协作的桥梁。充分利用上下文和记忆功能，可以为用户提供更智能、更个性化的服务。

---

**文档版本**: v1.1.0  
**最后更新**: 2026-04-30  
**适用插件版本**: >= 1.1.0
