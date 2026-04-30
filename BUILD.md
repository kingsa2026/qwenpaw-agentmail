# AgentMail Plugin 构建和部署指南

## 项目结构

```
agentmail/
├── plugin.json          # 插件清单
├── plugin.py            # 后端入口
├── package.json         # Node.js 依赖
├── tsconfig.json        # TypeScript 配置
├── vite.config.ts       # Vite 构建配置
├── src/
│   └── index.tsx        # 前端源码
├── dist/
│   └── index.js         # 构建输出（由 Vite 生成）
└── backend/             # 后端代码
    ├── main.py
    └── routes/
```

## 构建步骤

### 1. 安装依赖

```bash
cd agentmail
npm install
```

### 2. 构建前端

```bash
npm run build
```

这将生成 `dist/index.js` 文件。

### 3. 验证构建输出

确保 `dist/index.js` 存在且包含以下内容：
- 使用 `window.QwenPaw.host` 访问共享依赖
- 使用 `React.createElement` 而不是 JSX
- 调用 `window.QwenPaw.registerRoutes` 注册路由

## 部署步骤

### 方式一：本地安装

```bash
# 复制插件到 QwenPaw 插件目录
cp -r agentmail ~/.qwenpaw/plugins/

# 重启 QwenPaw
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

## 验证安装

1. 打开浏览器访问 QwenPaw 控制台
2. 检查侧边栏是否有 **"邮件管理"** 菜单
3. 点击菜单，确认页面显示正常

## 故障排查

### 构建失败

- 检查 Node.js 版本（建议 18+）
- 删除 `node_modules` 重新安装

### 插件未显示

- 检查 `plugin.json` 格式是否正确
- 确认 `dist/index.js` 存在
- 查看浏览器控制台是否有错误

### 路由注册失败

- 确认 `window.QwenPaw` 存在
- 检查 `registerRoutes` 调用是否正确
