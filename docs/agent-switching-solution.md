# 智能体切换（Agent Switching）解决方案

## 问题描述

在 QwenPaw 插件中，当用户在多个智能体（Agent）之间切换时，邮件插件的数据没有正确隔离，导致：
1. 切换到新 Agent 后，仍然显示上一个 Agent 的邮件数据
2. 联系人、收件箱、发件箱等数据没有随 Agent 切换而刷新
3. 配置信息在不同 Agent 之间共享

## 根本原因

1. **Agent ID 获取方式不当**：最初使用 `useMemo` 且依赖数组为空，导致 Agent ID 只会在组件挂载时计算一次，后续 URL 变化不会触发更新
2. **未监听 QwenPaw 的 Agent 切换机制**：QwenPaw 使用 `zustand` store 管理智能体状态，存储在 `localStorage` 的 `qwenpaw-last-used-agent` key 中，而非 URL 路径
3. **状态未重置**：切换 Agent 时，各个数据状态（contacts, inbox, sent 等）没有被清空，导致旧数据残留
4. **存储未隔离**：所有 Agent 共享同一个 localStorage key，数据互相覆盖

## 最终实现方案

### 1. 理解 QwenPaw 的智能体切换机制

通过分析 QwenPaw 源码发现：
- QwenPaw 使用 `zustand` 的 `agentStore` 管理当前智能体状态
- `selectedAgent` 存储当前选中的智能体 ID
- `setSelectedAgent` 切换智能体时会更新 `localStorage` 的 `qwenpaw-last-used-agent`
- 智能体切换在 `AgentSelector` 组件中实现，**不会刷新页面**
- 切换后触发 `storage` 事件（跨标签页同步）

### 2. Agent ID 实时获取（关键修复）

从 QwenPaw 的 `localStorage` 中读取当前智能体 ID：

```typescript
// Agent ID 从 QwenPaw store 实时获取，支持切换
const [agentId, setAgentId] = React.useState(() => {
  // QwenPaw 使用 qwenpaw-last-used-agent 存储当前智能体
  const qwLastUsed = localStorage.getItem('qwenpaw-last-used-agent');
  if (qwLastUsed) return qwLastUsed;
  // 兼容旧版
  const match = window.location.pathname.match(/\/agent\/([^\/]+)/);
  return match ? match[1] : localStorage.getItem('current_agent_id') || 'default';
});
```

**关键改进**：
- 优先读取 `qwenpaw-last-used-agent`（QwenPaw 官方存储 key）
- 兼容旧版 `current_agent_id` 和 URL 路径提取
- 使用 `useState` 使 Agent ID 成为响应式状态

### 3. 监听 QwenPaw Agent 切换事件

实现双重监听机制捕获智能体切换：

```typescript
// 监听 QwenPaw Agent 切换
React.useEffect(() => {
  const checkAgentChange = () => {
    // QwenPaw 使用 qwenpaw-last-used-agent 存储当前智能体
    const newAgentId = localStorage.getItem('qwenpaw-last-used-agent') || 'default';
    if (newAgentId !== agentId) {
      setAgentId(newAgentId);
      // 重置所有状态
      setContacts([]);
      setContactGroups([]);
      setContactTotal(0);
      setContactPage(1);
      setInboxEmails([]);
      setInboxTotal(0);
      setInboxPage(1);
      setSentEmails([]);
      setSentTotal(0);
      setSentPage(1);
      setDraftEmails([]);
      setDraftTotal(0);
      setDraftPage(1);
      setTrashItems([]);
      setTrashTotal(0);
      setTrashPage(1);
      setAgentConfig(null);
      setSelectedContacts([]);
      setSelectedInbox([]);
      setSelectedSent([]);
      setSelectedDrafts([]);
      setSelectedTrash([]);
    }
  };

  // 监听 storage 事件（跨标签页同步，QwenPaw 切换智能体时触发）
  window.addEventListener('storage', (e) => {
    if (e.key === 'qwenpaw-last-used-agent') {
      checkAgentChange();
    }
  });
  // 定时检查（应对同一标签页内的切换）
  const interval = setInterval(checkAgentChange, 500);

  return () => {
    window.removeEventListener('storage', checkAgentChange);
    clearInterval(interval);
  };
}, [agentId]);
```

**监听策略**：
1. **`storage` 事件**：监听 `qwenpaw-last-used-agent` 的变化（跨标签页同步时触发）
2. **定时轮询（500ms）**：捕获同一标签页内的智能体切换
3. **状态比较**：只有当 `newAgentId !== agentId` 时才执行重置，避免不必要的刷新

### 4. 数据状态完全重置

当检测到 Agent 切换时，必须重置所有相关状态：

| 状态类别 | 重置内容 |
|---------|---------|
| 联系人 | `contacts`, `contactGroups`, `contactTotal`, `contactPage` |
| 邮件数据 | `inboxEmails`, `inboxTotal`, `inboxPage` |
| 发件箱 | `sentEmails`, `sentTotal`, `sentPage` |
| 草稿箱 | `draftEmails`, `draftTotal`, `draftPage` |
| 回收站 | `trashItems`, `trashTotal`, `trashPage` |
| 配置 | `agentConfig` |
| 选择状态 | `selectedContacts`, `selectedInbox`, `selectedSent`, `selectedDrafts`, `selectedTrash` |

### 5. 存储层 Agent 隔离

每个 Agent 使用独立的 localStorage key：

```typescript
const STORAGE_KEY = 'agentmail_data';

function getStorage(agentId: string) {
  const key = `${STORAGE_KEY}_${agentId}`;
  try {
    const data = localStorage.getItem(key);
    return data ? JSON.parse(data) : { contacts: [], contactGroups: [{id:1,name:'default'}], inbox: [], sent: [], drafts: [], trash: [], config: null };
  } catch {
    return { contacts: [], contactGroups: [{id:1,name:'default'}], inbox: [], sent: [], drafts: [], trash: [], config: null };
  }
}

function setStorage(agentId: string, data: any) {
  const key = `${STORAGE_KEY}_${agentId}`;
  localStorage.setItem(key, JSON.stringify(data));
}
```

**隔离规则**：
- Key 格式：`agentmail_data_{agentId}`
- 每个 Agent 拥有完全独立的数据命名空间
- 数据操作函数 `getStorage`/`setStorage` 必须传入 `agentId` 参数

### 6. API 层 Agent 隔离

所有数据操作 API 都接收 `agentId` 参数，并操作对应 Agent 的数据：

```typescript
async function apiGet(path: string, agentId: string) {
  const data = getStorage(agentId);
  // ... 根据 path 返回对应数据
}

async function apiPost(path: string, body: any, agentId: string) {
  const data = getStorage(agentId);
  // ... 修改数据后保存
  setStorage(agentId, data);
}
```

### 7. 数据获取依赖 Agent ID

所有 `useEffect` 数据获取都包含 `agentId` 依赖：

```typescript
React.useEffect(() => {
  fetchConfig();
  fetchContactGroups();
}, [agentId]);

React.useEffect(() => { 
  if (activeTab === 'contacts') fetchContacts(); 
}, [activeTab, contactPage, contactSearch, contactGroup, agentId]);
```

## 验证方法

1. 在 Agent A 中创建联系人、邮件数据
2. 切换到 Agent B，确认数据为空
3. 在 Agent B 中创建不同的数据
4. 切换回 Agent A，确认显示的是 Agent A 的原始数据
5. 检查 localStorage，确认存在多个独立的 key：`agentmail_data_agentA`、`agentmail_data_agentB`

## 关键发现

### QwenPaw 智能体切换的技术细节

通过分析 QwenPaw 源码（`agentStore.ts` 和 `AgentSelector/index.tsx`）：

1. **存储位置**：`localStorage.setItem('qwenpaw-last-used-agent', agentId)`
2. **切换方式**：React state 更新，不刷新页面
3. **同步机制**：`zustand` persist middleware 同时写入 `sessionStorage` 和 `localStorage`
4. **事件触发**：`storage` 事件在跨标签页时触发，同一标签页需要轮询检测

### 为什么最初的方法失败

1. **URL 路径不包含 Agent ID**：QwenPaw 使用 React Router 的 state 管理，URL 始终是 `/chat` 或 `/email`
2. **`popstate` 事件无效**：智能体切换不涉及浏览器历史导航
3. **必须使用 `storage` 事件 + 轮询**：这是捕获 QwenPaw 智能体切换的唯一可靠方式

## 注意事项

1. **性能优化**：500ms 的轮询间隔是平衡实时性和性能的选择，可根据实际需求调整
2. **内存泄漏**：在 `useEffect` 返回函数中正确清理事件监听器和定时器
3. **边界情况**：处理 localStorage 中没有 Agent ID 的情况，默认使用 `'default'`
4. **数据持久化**：localStorage 有容量限制（通常 5-10MB），大量数据时需要考虑分页或 IndexedDB
