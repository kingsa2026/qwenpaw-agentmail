# AgentMail Plugin for QwenPaw

<p align="center">
  <img src="https://img.shields.io/badge/QwenPaw-1.1.0+-blue.svg" alt="QwenPaw Version">
  <img src="https://img.shields.io/badge/version-1.1.0-green.svg" alt="Plugin Version">
  <img src="https://img.shields.io/badge/license-MIT-yellow.svg" alt="License">
  <img src="https://img.shields.io/badge/language-TypeScript/Python-orange.svg" alt="Languages">
</p>

<p align="center">
  <b>智能邮箱管理插件，为 QwenPaw Agent 提供完整的邮件处理能力</b>
</p>

## ✨ 功能特性

### 核心功能
- 📧 **多邮箱类型支持** - POP3/IMAP/SMTP 传统邮箱、AgentMail.to、混合模式
- 🌍 **多语言界面** - 支持简体中文、English、日本語、Русский
- 🤖 **Agent 上下文集成** - 一键将邮件注入 Agent 聊天上下文
- 🧠 **Agent 记忆集成** - 邮件自动转化为 Agent 长期记忆
- 💡 **智能回复建议** - 基于邮件内容生成智能回复草稿
- 📋 **邮件规则引擎** - 可视化规则管理，自动处理邮件

### 支持的邮箱提供商
| 提供商 | 协议 | 授权方式 |
|--------|------|----------|
| QQ 邮箱 | SMTP/IMAP | 授权码 |
| 163 邮箱 | SMTP/IMAP | 授权码 |
| 126 邮箱 | SMTP/IMAP | 授权码 |
| Gmail | SMTP/IMAP | OAuth/密码 |
| Outlook | SMTP/IMAP | OAuth/密码 |
| 自定义 | SMTP/IMAP/POP3 | 密码/授权码 |

## 🚀 快速开始

### 环境要求
- Node.js >= 18
- Python >= 3.8
- QwenPaw >= 1.1.0

### 安装方法

#### 方式一：本地安装

```bash
# 1. 克隆仓库
git clone https://github.com/yourusername/qwenpaw-agentmail.git

# 2. 进入项目目录
cd qwenpaw-agentmail

# 3. 安装依赖并构建
npm install && npm run build

# 4. 复制到 QwenPaw 插件目录
cp -r . ~/.qwenpaw/plugins/agentmail/

# 5. 重启 QwenPaw
qwenpaw app
```

#### 方式二：服务器部署

```powershell
# 1. 复制插件到服务器
scp -P 22 -r . root@your-server:/root/.qwenpaw/plugins/agentmail/

# 2. 重启 QwenPaw 服务
ssh -p 22 root@your-server "pkill -f 'qwenpaw app' && sleep 2 && cd /root && source .qwenpaw/venv/bin/activate && nohup qwenpaw app --host 0.0.0.0 --port 8088 > /tmp/qwenpaw.log 2>&1 &"
```

## 📖 使用指南

### 1. 配置邮箱

进入插件设置页面，选择邮箱类型并填写配置信息：

```
设置 → 邮箱配置 → 选择提供商 → 填写账号密码
```

### 2. 使用 Agent 集成功能

在收件箱中，每封邮件提供三个 Agent 操作按钮：

| 按钮 | 功能 | 说明 |
|------|------|------|
| **Add to Context** | 添加到上下文 | 将邮件内容注入当前 Agent 会话 |
| **Add to Memory** | 添加到记忆 | 保存邮件为 Agent 长期记忆 |
| **Generate Reply** | 生成回复 | 基于邮件内容生成智能回复草稿 |

### 3. 邮件规则引擎

在设置页面创建自动化规则：

```
设置 → Email Rules → Create Rule
```

规则条件支持：
- 发件人匹配
- 主题包含关键词
- 内容包含关键词

规则动作支持：
- 自动标记标签
- 使用模板回复
- 自动归档
- 通知 Agent

## 🏗️ 项目结构

```
agentmail/
├── plugin.json              # 插件清单配置
├── plugin.py                # Python 后端入口
├── package.json             # Node.js 依赖配置
├── tsconfig.json            # TypeScript 配置
├── vite.config.ts           # 构建工具配置
├── .gitignore               # Git 忽略规则
│
├── src/
│   └── index.tsx            # 前端主代码（React + TypeScript）
│
├── dist/                    # 构建输出目录（自动生成）
│
├── backend/                 # Python 后端代码
│   ├── main.py              # FastAPI 应用入口
│   ├── database.py          # 数据库模型与操作
│   ├── routes/
│   │   ├── __init__.py
│   │   └── api_routes.py    # RESTful API 路由
│   └── webhooks/
│       ├── __init__.py
│       ├── agentmail_webhook.py    # AgentMail.to  webhook
│       └── hybrid_webhook.py       # 混合模式 webhook
│
├── frontend/                # 前端源码备份
│   ├── index.tsx
│   └── index.js
│
└── docs/                    # 开发文档
    ├── development-plan.md
    ├── language-adaptation-solution.md
    └── agent-switching-solution.md
```

## 🔧 开发指南

### 前端开发

```bash
# 安装依赖
npm install

# 开发模式（热重载）
npm run dev

# 生产构建
npm run build
```

技术栈：
- TypeScript + JSX
- React 18
- Ant Design 组件库
- Vite 构建工具

关键 API：
```typescript
// 注册路由
window.QwenPaw.registerRoutes(pluginId, [
  { path: '/email', component: EmailPage, label: 'AgentMail', icon: <MailOutlined /> }
]);

// 获取共享依赖
const { React, antd } = window.QwenPaw.host;
```

### 后端开发

```bash
# 安装 Python 依赖
pip install fastapi uvicorn

# 启动开发服务器
python backend/main.py
```

插件接口：
```python
from qwenpaw.plugins import PluginApi

class AgentMailPlugin:
    def register(self, api: PluginApi):
        # 注册路由
        api.router.include_router(router)
        
        # 注册启动钩子
        api.register_startup_hook(self.on_startup)
        
        # 注册关闭钩子
        api.register_shutdown_hook(self.on_shutdown)
```

## 🌐 多语言支持

AgentMail 支持四种语言，自动根据 QwenPaw 系统语言切换：

| 语言 | 代码 | 完成度 |
|------|------|--------|
| English | en | 100% |
| 简体中文 | zh | 100% |
| 日本語 | ja | 100% |
| Русский | ru | 100% |

## 🐛 故障排查

### 插件未显示在侧边栏

1. 检查 `plugin.json` 格式是否正确
2. 确认 `dist/index.js` 文件存在
3. 查看浏览器控制台是否有错误信息
4. 确认 QwenPaw 版本 >= 1.1.0

### 邮箱连接失败

1. 检查邮箱账号和密码/授权码是否正确
2. 确认邮箱的 SMTP/IMAP 服务已开启
3. 检查服务器防火墙是否放行相关端口
4. 查看后端日志获取详细错误信息

### 构建失败

```bash
# 清理并重新安装依赖
rm -rf node_modules package-lock.json
npm install

# 检查 Node.js 版本
node --version  # 需要 >= 18
```

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目基于 [MIT](LICENSE) 许可证开源。

## 🙏 致谢

- [QwenPaw](https://github.com/qwenpaw/qwenpaw) - 强大的 Agent 开发框架
- [Ant Design](https://ant.design/) - UI 组件库
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能 Python Web 框架

## 📞 联系方式

如有问题或建议，欢迎通过以下方式联系：

- 提交 [GitHub Issue](https://github.com/yourusername/qwenpaw-agentmail/issues)
- 发送邮件至：your-email@example.com

---

<p align="center">
  Made with ❤️ for QwenPaw Community
</p>
