# 语言适配（Language Adaptation）解决方案

## 问题描述

在 QwenPaw 插件中，当用户切换界面语言时，邮件插件的文本内容没有正确更新，导致：
1. 切换语言后，插件界面仍然显示之前的语言
2. 部分文本没有翻译，显示为英文固定文本
3. 语言切换后需要刷新页面才能生效

## 根本原因

1. **翻译函数未响应式**：`t()` 函数是全局静态函数，没有与组件的渲染周期绑定
2. **i18n 事件监听不可靠**：`languageChanged` 事件可能不被触发，或触发时机不确定
3. **语言代码不匹配**：QwenPaw 使用 `zh-CN`、`en-US` 等带区域代码的语言标识，而插件只支持 `zh`、`en`
4. **组件未重新渲染**：即使语言状态变化，使用翻译函数的 JSX 表达式不会自动重新求值

## 最终实现方案

### 1. 语言代码标准化

处理 QwenPaw 的语言代码，统一转换为短格式：

```typescript
function normalizeLang(lng?: string): string {
  const lang = lng || i18n?.language || 'en';
  // 处理类似 zh-CN, en-US 等带区域代码的语言标识
  const shortLang = lang.split('-')[0].toLowerCase();
  // 确保返回支持的语种
  if (['zh', 'en', 'ja', 'ru'].includes(shortLang)) return shortLang;
  return 'en';
}
```

### 2. 多方式获取当前语言

实现 `getCurrentLanguage` 函数，通过多种方式获取当前语言：

```typescript
function getCurrentLanguage(): string {
  // 方式1: i18n 实例
  if (i18n?.language) return normalizeLang(i18n.language);
  // 方式2: localStorage
  const stored = localStorage.getItem('language');
  if (stored) return normalizeLang(stored);
  // 方式3: document lang
  if (document.documentElement.lang) return normalizeLang(document.documentElement.lang);
  return 'en';
}
```

**三种方式的作用**：
1. **i18n 实例**：QwenPaw 暴露的 i18next 实例，最可靠的方式
2. **localStorage**：QwenPaw 存储语言设置的位置，作为备用
3. **document.lang**：HTML 标签的 lang 属性，作为最后的备选

### 3. 翻译数据组织

使用常量对象存储所有翻译，支持四种语言：

```typescript
const TRANSLATIONS: Record<string, Record<string, string>> = {
  en: { 'email.title': 'Email Management', ... },
  zh: { 'email.title': '邮件管理', ... },
  ja: { 'email.title': 'メール管理', ... },
  ru: { 'email.title': 'Управление почтой', ... },
};
```

### 4. 核心翻译函数

```typescript
function t(key: string, lang?: string): string {
  const currentLang = normalizeLang(lang);
  return TRANSLATIONS[currentLang]?.[key] || TRANSLATIONS['en']?.[key] || key;
}
```

**回退机制**：
1. 优先使用指定语言翻译
2. 如果没有，回退到英语
3. 如果英语也没有，返回 key 本身

### 5. 响应式翻译 Hook（核心实现）

使用全局监听器模式，确保所有组件都能响应语言变化：

```typescript
// 全局语言状态，用于强制所有使用翻译的组件重新渲染
let globalLangListeners: Set<(lang: string) => void> = new Set();
let currentGlobalLang = getCurrentLanguage();

function notifyLangChange(lang: string) {
  currentGlobalLang = lang;
  globalLangListeners.forEach(fn => fn(lang));
}

function useTranslation() {
  const [lang, setLang] = React.useState(getCurrentLanguage());
  
  React.useEffect(() => {
    // 注册到全局监听器
    const listener = (newLang: string) => setLang(newLang);
    globalLangListeners.add(listener);
    
    // 立即同步当前语言
    const initialLang = getCurrentLanguage();
    setLang(initialLang);
    
    // 监听 i18n 语言变化事件
    const i18nHandler = (lng: string) => {
      const normalized = normalizeLang(lng);
      setLang(normalized);
      notifyLangChange(normalized);
    };
    
    if (i18n) {
      i18n.on('languageChanged', i18nHandler);
    }
    
    // 监听 localStorage 变化（备用机制）
    const storageHandler = (e: StorageEvent) => {
      if (e.key === 'language' || e.key === 'i18nextLng') {
        const normalized = normalizeLang(e.newValue);
        setLang(normalized);
        notifyLangChange(normalized);
      }
    };
    window.addEventListener('storage', storageHandler);
    
    // 监听 document lang 属性变化（备用机制）
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === 'attributes' && mutation.attributeName === 'lang') {
          const newLang = normalizeLang(document.documentElement.lang);
          setLang(newLang);
          notifyLangChange(newLang);
        }
      });
    });
    observer.observe(document.documentElement, { attributes: true });
    
    // 定时检查语言变化（应对 i18n 事件不可靠的情况）
    const interval = setInterval(() => {
      const current = getCurrentLanguage();
      if (current !== lang) {
        setLang(current);
        notifyLangChange(current);
      }
    }, 500);
    
    return () => {
      globalLangListeners.delete(listener);
      if (i18n) i18n.off('languageChanged', i18nHandler);
      window.removeEventListener('storage', storageHandler);
      observer.disconnect();
      clearInterval(interval);
    };
  }, []);
  
  // 关键：不使用 useCallback，确保每次 lang 变化时函数引用都改变
  const translate = (key: string) => t(key, lang);
  return { t: translate, lang };
}
```

**关键设计点**：

1. **全局监听器模式**：使用 `Set` 存储所有语言变化监听器，确保语言切换时所有使用 `useTranslation` 的组件都能收到通知

2. **四重监听机制**：
   - `i18n.on('languageChanged')`：监听 i18next 官方事件
   - `window.addEventListener('storage')`：监听 localStorage 变化
   - `MutationObserver`：监听 HTML 标签 lang 属性变化
   - `setInterval`（500ms）：定时轮询，作为最终保障

3. **不使用 `useCallback`**：这是最关键的设计决策。如果使用 `useCallback`，当 `lang` 变化时，`t` 函数的引用不会改变，React 不会重新渲染依赖 `t` 的 JSX 表达式。通过不使用 `useCallback`，每次 `lang` 变化时 `t` 函数都是新的引用，强制触发重新渲染。

### 6. 在组件中使用翻译

所有需要翻译的组件都使用 `useTranslation`：

```typescript
function EmailPage() {
  const { t, lang } = useTranslation();
  // ... 组件逻辑
  
  return (
    <div>
      <Title level={2}>
        <MailOutlined style={{ marginRight: 8 }} />
        {t('email.title')} - {agentName}
      </Title>
      <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
        { key: 'inbox', label: <span><InboxOutlined />{t('email.inbox')}</span> },
        { key: 'sent', label: <span><SendOutlined />{t('email.sent')}</span> },
        // ...
      ]} />
    </div>
  );
}
```

**使用规范**：
1. 在函数组件顶部调用 `const { t, lang } = useTranslation()`
2. 所有用户可见文本都通过 `t('key')` 获取
3. 避免硬编码任何语言文本

### 7. 支持的语言列表

当前支持以下语言：

| 语言代码 | 语言名称 | 覆盖程度 |
|---------|---------|---------|
| `en` | English | 完整 |
| `zh` | 简体中文 | 完整 |
| `ja` | 日本語 | 完整 |
| `ru` | Русский | 完整 |

## 验证方法

1. 打开插件，确认当前语言显示正确
2. 在 QwenPaw 设置中切换语言（如从中文切换到英文）
3. 观察插件界面，确认所有文本实时更新为新语言
4. 测试日语和俄语切换
5. 切换回原始语言，确认恢复正常

## 关键发现

### 为什么最初的方法失败

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 语言切换无反应 | `useCallback` 缓存了 `t` 函数 | 不使用 `useCallback` |
| i18n 事件不触发 | QwenPaw 的 i18n 实例事件系统不可靠 | 多重监听机制 |
| 语言代码不匹配 | `zh-CN` vs `zh` | `normalizeLang` 函数 |
| 组件不重新渲染 | React 无法追踪 `t` 函数变化 | 全局监听器 + 新函数引用 |

### 性能考虑

1. **500ms 轮询间隔**：平衡实时性和性能，可根据需求调整
2. **全局监听器**：使用 `Set` 存储，添加/删除都是 O(1) 操作
3. **不使用 `useCallback`**：虽然会创建新函数，但避免了复杂的依赖追踪问题

## 注意事项

1. **事件清理**：在 `useEffect` 返回函数中正确清理所有监听器
2. **内存泄漏**：`globalLangListeners` 使用 `Set`，确保组件卸载时删除监听器
3. **语言回退**：始终提供英语作为最终回退
4. **扩展性**：新增语言时，只需在 `TRANSLATIONS` 对象中添加新的语言代码和翻译内容
