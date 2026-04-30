# AgentMail Plugin

QwenPaw 邮箱管理插件，支持传统邮箱、AgentMail.to 和混合模式。

## 功能特性

- 📧 多邮箱类型支持（POP3/IMAP/SMTP、AgentMail.to、混合模式）
- 📨 收件箱、已发送、草稿箱管理
- 🔧 邮箱配置管理
- 🎨 原生 QwenPaw UI 风格

## 安装方法

### 方式一：本地安装

```bash
# 1. 构建前端
cd agentmail
npm install && npm run build

# 2. 复制到插件目录
cp -r . ~/.qwenpaw/plugins/agentmail/

# 3. 重启 QwenPaw
qwenpaw app
```

### 方式二：服务器部署

```powershell
# 1. 复制插件到服务器
scp -P 22 -r agentmail/* administrator@192.168.10.132:"C:/Users/administrator/.qwenpaw/plugins/agentmail"

# 2. 重启 QwenPaw（执行两次）
ssh -p 22 administrator@192.168.10.132 "taskkill /F /IM QwenPaw.exe"
Start-Sleep -Seconds 3
ssh -p 22 administrator@192.168.10.132 "Start-Process 'C:\Program Files\QwenPaw\QwenPaw.exe'"

Start-Sleep -Seconds 5

ssh -p 22 administrator@192.168.10.132 "taskkill /F /IM QwenPaw.exe"
Start-Sleep -Seconds 3
ssh -p 22 administrator@192.168.10.132 "Start-Process 'C:\Program Files\QwenPaw\QwenPaw.exe'"
```

## 插件结构

```
agentmail/
├── plugin.json          # 插件清单
├── plugin.py            # 后端入口
├── package.json         # Node.js 依赖
├── tsconfig.json        # TypeScript 配置
├── vite.config.ts       # 构建配置
├── src/
│   └── index.tsx        # 前端源码
├── dist/
│   └── index.js         # 构建输出
└── backend/             # 后端代码
    ├── main.py
    └── routes/
```

## 开发规范

### 前端开发

- 使用 TypeScript + JSX
- 通过 `window.QwenPaw.host` 访问共享依赖
- 使用 `window.QwenPaw.registerRoutes` 注册路由
- 构建配置：`jsxRuntime: "classic"`，`external: ["react", "react-dom"]`

### 后端开发

- 导出 `plugin` 实例
- 实现 `register(api)` 方法
- 使用 `PluginApi` 注册功能

## 故障排查

### 插件未显示

1. 检查 `plugin.json` 格式
2. 确认 `dist/index.js` 存在
3. 查看浏览器控制台错误

### 构建失败

1. 检查 Node.js 版本（建议 18+）
2. 删除 `node_modules` 重新安装

## 依赖

- Node.js >= 18
- Python >= 3.8
- FastAPI >= 0.104.0

## 版本历史

- v1.0.0 - 初始版本，支持基本邮件管理功能
