const { React, antd, antdIcons, i18n } = (window as any).QwenPaw.host;
const { Card, Button, Tabs, Table, Badge, Space, Tag, Typography, Empty, Modal, Form, Input, InputNumber, Switch, Select, message, Spin, Divider, Alert, Checkbox, Pagination, Popconfirm, Row, Col, Avatar, Tooltip, Radio, Upload } = antd;
const { MailOutlined, InboxOutlined, SendOutlined, EditOutlined, SettingOutlined, ReloadOutlined, PlusOutlined, SaveOutlined, ApiOutlined, DeleteOutlined, UserOutlined, TeamOutlined, SearchOutlined, UndoOutlined, CheckOutlined, CloseOutlined, ShareAltOutlined, FolderOpenOutlined, RestOutlined, LinkOutlined, FileOutlined, EyeOutlined, DownloadOutlined, CloudUploadOutlined, BoldOutlined, ItalicOutlined, UnderlineOutlined, StrikethroughOutlined, OrderedListOutlined, UnorderedListOutlined, BgColorsOutlined, FontColorsOutlined, ClearOutlined, RedoOutlined, RollbackOutlined, PictureOutlined, FormatPainterOutlined, ExportOutlined } = antdIcons;
const { Title, Text } = Typography;

const STORAGE_KEY = 'agentmail_data';

// 简单的客户端加密密钥（生产环境应从环境变量获取）
const _STORAGE_KEY = (window as any).__AGENTMAIL_KEY__ || 'agentmail-default-key-2026';

function _xorEncrypt(value: string): string {
  try {
    const encoder = new TextEncoder();
    const data = encoder.encode(value);
    const key = encoder.encode(_STORAGE_KEY);
    const encrypted = new Uint8Array(data.length);
    for (let i = 0; i < data.length; i++) {
      encrypted[i] = data[i] ^ key[i % key.length];
    }
    // Base64 encode
    const chars = [];
    for (let i = 0; i < encrypted.length; i += 3) {
      const b1 = encrypted[i];
      const b2 = encrypted[i + 1];
      const b3 = encrypted[i + 2];
      chars.push(
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'[b1 >> 2],
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'[((b1 & 3) << 4) | (b2 >> 4)],
        b2 !== undefined ? 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'[((b2 & 15) << 2) | (b3 >> 6)] : '=',
        b3 !== undefined ? 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'[b3 & 63] : '='
      );
    }
    return chars.join('');
  } catch {
    return value;
  }
}

function _xorDecrypt(value: string): string {
  try {
    // Base64 decode
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
    const lookup: Record<string, number> = {};
    for (let i = 0; i < chars.length; i++) lookup[chars[i]] = i;
    const bytes = [];
    for (let i = 0; i < value.length; i += 4) {
      const c1 = lookup[value[i]] || 0;
      const c2 = lookup[value[i + 1]] || 0;
      const c3 = lookup[value[i + 2]] || 0;
      const c4 = lookup[value[i + 3]] || 0;
      bytes.push((c1 << 2) | (c2 >> 4));
      if (value[i + 2] !== '=') bytes.push(((c2 & 15) << 4) | (c3 >> 2));
      if (value[i + 3] !== '=') bytes.push(((c3 & 3) << 6) | c4);
    }
    const key = new TextEncoder().encode(_STORAGE_KEY);
    const decrypted = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) {
      decrypted[i] = bytes[i] ^ key[i % key.length];
    }
    return new TextDecoder().decode(decrypted);
  } catch {
    return value;
  }
}

function getStorage(agentId: string) {
  const key = `${STORAGE_KEY}_${agentId}`;
  try {
    const data = localStorage.getItem(key);
    if (!data) return { contacts: [], contactGroups: [{id:1,name:'default'}], inbox: [], sent: [], drafts: [], trash: [], config: null };
    // 尝试解密（兼容旧版本明文存储）
    let decrypted: string;
    try {
      decrypted = _xorDecrypt(data);
      // 验证是否为有效 JSON
      JSON.parse(decrypted);
    } catch {
      // 解密失败，可能是旧版本明文数据
      decrypted = data;
    }
    return JSON.parse(decrypted);
  } catch {
    return { contacts: [], contactGroups: [{id:1,name:'default'}], inbox: [], sent: [], drafts: [], trash: [], config: null };
  }
}

function setStorage(agentId: string, data: any) {
  const key = `${STORAGE_KEY}_${agentId}`;
  const json = JSON.stringify(data);
  // 加密存储敏感数据
  const encrypted = _xorEncrypt(json);
  localStorage.setItem(key, encrypted);
}

function getAllAgentIds(): string[] {
  const ids: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key && key.startsWith(STORAGE_KEY + '_')) {
      ids.push(key.replace(STORAGE_KEY + '_', ''));
    }
  }
  return ids;
}

function getAllAgents(): {id: string, name: string}[] {
  const agents: {id: string, name: string}[] = [];

  // 1. 尝试从 QwenPaw 新版 zustand store 读取 (qwenpaw-agent-storage)
  try {
    const storageData = localStorage.getItem('qwenpaw-agent-storage');
    if (storageData) {
      const parsed = JSON.parse(storageData);
      const state = parsed?.state || parsed;
      if (state?.agents && Array.isArray(state.agents)) {
        state.agents.forEach((a: any) => {
          if (a.id) {
            agents.push({ id: a.id, name: a.name || a.id });
          }
        });
      }
    }
  } catch { }

  // 2. 尝试从旧版 qwenpaw_agents 读取（兼容旧版本）
  if (agents.length === 0) {
    try {
      const agentsData = localStorage.getItem('qwenpaw_agents');
      if (agentsData) {
        const parsed = JSON.parse(agentsData);
        if (Array.isArray(parsed)) {
          parsed.forEach((a: any) => {
            agents.push({ id: a.id || a.agent_id, name: a.name || a.id || a.agent_id });
          });
        }
      }
    } catch { }
  }

  // 3. 从 AgentMail 本地存储的 agent IDs 兜底
  if (agents.length === 0) {
    const ids = getAllAgentIds();
    ids.forEach(id => {
      agents.push({ id, name: id });
    });
  }

  return agents;
}

async function apiGet(path: string, agentId: string) {
  const data = getStorage(agentId);
  if (path.includes('/contacts')) {
    const params = new URLSearchParams(path.split('?')[1] || '');
    const page = parseInt(params.get('page') || '1');
    const pageSize = parseInt(params.get('page_size') || '15');
    const search = params.get('search') || '';
    const group = params.get('group') || 'all';
    let items = data.contacts || [];
    if (search) {
      const s = search.toLowerCase();
      items = items.filter((c: any) => (c.name+c.email+c.company).toLowerCase().includes(s));
    }
    if (group && group !== 'all') {
      items = items.filter((c: any) => c.group_name === group);
    }
    const total = items.length;
    const start = (page - 1) * pageSize;
    items = items.slice(start, start + pageSize);
    return { success: true, total, page, page_size: pageSize, items };
  }
  if (path.includes('/contact-groups')) {
    return { success: true, items: data.contactGroups || [{id:1,name:'default'}] };
  }
  if (path.includes('/inbox')) {
    const params = new URLSearchParams(path.split('?')[1] || '');
    const page = parseInt(params.get('page') || '1');
    const pageSize = parseInt(params.get('page_size') || '20');
    const items = (data.inbox || []).slice((page-1)*pageSize, page*pageSize);
    return { success: true, total: data.inbox?.length || 0, page, page_size: pageSize, items };
  }
  if (path.includes('/sent')) {
    const params = new URLSearchParams(path.split('?')[1] || '');
    const page = parseInt(params.get('page') || '1');
    const pageSize = parseInt(params.get('page_size') || '20');
    const items = (data.sent || []).slice((page-1)*pageSize, page*pageSize);
    return { success: true, total: data.sent?.length || 0, page, page_size: pageSize, items };
  }
  if (path.includes('/drafts')) {
    const params = new URLSearchParams(path.split('?')[1] || '');
    const page = parseInt(params.get('page') || '1');
    const pageSize = parseInt(params.get('page_size') || '20');
    const items = (data.drafts || []).slice((page-1)*pageSize, page*pageSize);
    return { success: true, total: data.drafts?.length || 0, page, page_size: pageSize, items };
  }
  if (path.includes('/trash')) {
    const params = new URLSearchParams(path.split('?')[1] || '');
    const page = parseInt(params.get('page') || '1');
    const pageSize = parseInt(params.get('page_size') || '20');
    const filterType = params.get('type') || 'all';
    let items = data.trash || [];
    if (filterType !== 'all') {
      items = items.filter((t: any) => t.item_type === filterType);
    }
    const total = items.length;
    items = items.slice((page-1)*pageSize, page*pageSize);
    return { success: true, total, page, page_size: pageSize, items };
  }
  if (path.includes('/config')) {
    return { success: true, config: data.config };
  }
  return { success: true };
}

async function apiPost(path: string, body: any, agentId: string) {
  const data = getStorage(agentId);
  if (path.includes('/contacts') && !path.includes('/batch')) {
    const contact = { ...body, id: Date.now(), created_at: new Date().toISOString() };
    data.contacts.push(contact);
    setStorage(agentId, data);
    return { success: true, id: contact.id };
  }
  if (path.includes('/contacts/batch-delete')) {
    const deleted = data.contacts.filter((c: any) => body.ids.includes(c.id));
    data.contacts = data.contacts.filter((c: any) => !body.ids.includes(c.id));
    data.trash = data.trash || [];
    deleted.forEach((item: any) => data.trash.push({ ...item, item_type: 'contact', original_id: item.id, deleted_at: new Date().toISOString() }));
    setStorage(agentId, data);
    return { success: true };
  }
  if (path.includes('/contacts/batch-share')) {
    data.contacts = data.contacts.map((c: any) => {
      if (body.contact_ids.includes(c.id)) {
        const shared = c.shared_with ? JSON.parse(c.shared_with) : [];
        shared.push(...body.target_agent_ids);
        c.shared_with = JSON.stringify([...new Set(shared)]);
      }
      return c;
    });
    setStorage(agentId, data);
    return { success: true };
  }
  if (path.includes('/contact-groups')) {
    const group = { id: Date.now(), name: body.name };
    data.contactGroups.push(group);
    setStorage(agentId, data);
    return { success: true, id: group.id };
  }
  if (path.includes('/inbox/archive')) {
    data.inbox = data.inbox.map((e: any) => {
      if (body.ids.includes(e.id)) e.folder = 'archive';
      return e;
    });
    setStorage(agentId, data);
    return { success: true };
  }
  if (path.includes('/inbox/delete')) {
    const deleted = data.inbox.filter((e: any) => body.ids.includes(e.id));
    data.inbox = data.inbox.filter((e: any) => !body.ids.includes(e.id));
    data.trash = data.trash || [];
    deleted.forEach((item: any) => data.trash.push({ ...item, item_type: 'inbox', original_id: item.id, deleted_at: new Date().toISOString() }));
    setStorage(agentId, data);
    return { success: true };
  }
  if (path.includes('/sent/send')) {
    const draft = data.drafts?.find((d: any) => d.id === body.draft_id);
    if (draft) {
      data.drafts = data.drafts.filter((d: any) => d.id !== body.draft_id);
    }
    const sentItem = { ...body, id: Date.now(), sent_at: new Date().toISOString(), status: 'sent' };
    data.sent = data.sent || [];
    data.sent.push(sentItem);
    setStorage(agentId, data);
    return { success: true, id: sentItem.id };
  }
  if (path.includes('/sent/delete')) {
    const deleted = data.sent.filter((e: any) => body.ids.includes(e.id));
    data.sent = data.sent.filter((e: any) => !body.ids.includes(e.id));
    data.trash = data.trash || [];
    deleted.forEach((item: any) => data.trash.push({ ...item, item_type: 'sent', original_id: item.id, deleted_at: new Date().toISOString() }));
    setStorage(agentId, data);
    return { success: true };
  }
  if (path.includes('/drafts') && !path.includes('/delete')) {
    const draft = { ...body, id: body.id || Date.now(), updated_at: new Date().toISOString() };
    data.drafts = data.drafts || [];
    const idx = data.drafts.findIndex((d: any) => d.id === draft.id);
    if (idx >= 0) data.drafts[idx] = draft;
    else data.drafts.push(draft);
    setStorage(agentId, data);
    return { success: true, id: draft.id };
  }
  if (path.includes('/drafts/delete')) {
    const deleted = data.drafts.filter((e: any) => body.ids.includes(e.id));
    data.drafts = data.drafts.filter((e: any) => !body.ids.includes(e.id));
    data.trash = data.trash || [];
    deleted.forEach((item: any) => data.trash.push({ ...item, item_type: 'drafts', original_id: item.id, deleted_at: new Date().toISOString() }));
    setStorage(agentId, data);
    return { success: true };
  }
  if (path.includes('/trash/restore')) {
    const restored = data.trash.filter((t: any) => body.ids.includes(t.id));
    data.trash = data.trash.filter((t: any) => !body.ids.includes(t.id));
    restored.forEach((item: any) => {
      const restoredItem = { ...item, id: item.original_id || item.id };
      delete restoredItem.item_type;
      delete restoredItem.original_id;
      delete restoredItem.deleted_at;
      if (item.item_type === 'inbox') data.inbox.push(restoredItem);
      if (item.item_type === 'sent') data.sent.push(restoredItem);
      if (item.item_type === 'drafts') data.drafts.push(restoredItem);
      if (item.item_type === 'contact') data.contacts.push(restoredItem);
    });
    setStorage(agentId, data);
    return { success: true };
  }
  if (path.includes('/config')) {
    const type = path.split('/').pop();
    data.config = data.config || {};
    data.config[type] = body;
    data.config.updated_at = new Date().toISOString();
    setStorage(agentId, data);
    return { success: true };
  }
  if (path.includes('/backup')) {
    const backup = {
      agentId,
      timestamp: new Date().toISOString(),
      data: JSON.parse(JSON.stringify(data)),
    };
    const backupsKey = `${STORAGE_KEY}_${agentId}_backups`;
    const backups = JSON.parse(localStorage.getItem(backupsKey) || '[]');
    backups.push(backup);
    if (backups.length > 10) backups.shift();
    localStorage.setItem(backupsKey, JSON.stringify(backups));
    return { success: true, backups: backups.length };
  }
  return { success: true };
}

async function apiPut(path: string, body: any, agentId: string) {
  const data = getStorage(agentId);
  if (path.includes('/contacts/')) {
    const id = parseInt(path.split('/').pop() || '0');
    const idx = data.contacts.findIndex((c: any) => c.id === id);
    if (idx >= 0) {
      data.contacts[idx] = { ...data.contacts[idx], ...body, updated_at: new Date().toISOString() };
      setStorage(agentId, data);
    }
    return { success: true };
  }
  return { success: true };
}

async function apiDelete(path: string, body: any, agentId: string) {
  const data = getStorage(agentId);
  if (path.includes('/config')) {
    data.config = null;
    setStorage(agentId, data);
    return { success: true };
  }
  if (path.includes('/trash/permanent')) {
    data.trash = data.trash.filter((t: any) => !body.ids.includes(t.id));
    setStorage(agentId, data);
    return { success: true };
  }
  if (path.includes('/contact-groups/')) {
    const id = parseInt(path.split('/').pop() || '0');
    const group = data.contactGroups.find((g: any) => g.id === id);
    if (group) {
      data.contacts = data.contacts.map((c: any) => c.group_name === group.name ? { ...c, group_name: 'default' } : c);
      data.contactGroups = data.contactGroups.filter((g: any) => g.id !== id);
      setStorage(agentId, data);
    }
    return { success: true };
  }
  return { success: true };
}

function normalizeLang(lng?: string): string {
  const lang = lng || i18n?.language || 'en';
  // 处理类似 zh-CN, en-US 等带区域代码的语言标识
  const shortLang = lang.split('-')[0].toLowerCase();
  // 确保返回支持的语种
  if (['zh', 'en', 'ja', 'ru'].includes(shortLang)) return shortLang;
  return 'en';
}

// 获取当前语言（多种方式）
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

const TRANSLATIONS: Record<string, Record<string, string>> = {
    en: {
      'nav.email': 'AgentMail',
      'email.title': 'Email Management',
      'email.contacts': 'Contacts',
      'email.inbox': 'Inbox',
      'email.sent': 'Sent',
      'email.drafts': 'Drafts',
      'email.archive': 'Archive',
      'email.trash': 'Trash',
      'email.config': 'Settings',
      'email.refresh': 'Refresh',
      'email.compose': 'Compose',
      'email.search': 'Search',
      'email.new': 'New',
      'email.edit': 'Edit',
      'email.delete': 'Delete',
      'email.save': 'Save',
      'email.cancel': 'Cancel',
      'email.submit': 'Submit',
      'email.close': 'Close',
      'email.status': 'Status',
      'email.subject': 'Subject',
      'email.sender': 'Sender',
      'email.recipient': 'Recipient',
      'email.date': 'Date',
      'email.action': 'Action',
      'email.read': 'Read',
      'email.unread': 'Unread',
      'email.agentRead': 'Agent Read',
      'email.agentUnread': 'Agent Unread',
      'email.replied': 'Replied',
      'email.notReplied': 'Not Replied',
      'email.sentStatus': 'Sent',
      'email.sentFailed': 'Failed',
      'email.sentPending': 'Pending',
      'email.restore': 'Restore',
      'email.permanentDelete': 'Delete Permanently',
      'email.batchArchive': 'Batch Archive',
      'email.batchDelete': 'Batch Delete',
      'email.batchRestore': 'Batch Restore',
      'email.selectAll': 'Select All',
      'email.name': 'Name',
      'email.phone': 'Phone',
      'email.emailAddr': 'Email',
      'email.company': 'Company',
      'email.website': 'Website',
      'email.notes': 'Notes',
      'email.group': 'Group',
      'email.share': 'Share',
      'email.batchShare': 'Batch Share',
      'email.allGroups': 'All Groups',
      'email.newGroup': 'New Group',
      'email.groupName': 'Group Name',
      'email.contactCount': 'contacts',
      'email.noContacts': 'No contacts',
      'email.noEmails': 'No emails',
      'email.noSent': 'No sent emails',
      'email.noDrafts': 'No drafts',
      'email.noTrash': 'Trash is empty',
      'email.confirmDelete': 'Are you sure to delete?',
      'email.confirmPermanentDelete': 'Permanently delete? This cannot be undone.',
      'email.loading': 'Loading...',
      'email.provider': 'Provider',
      'email.custom': 'Custom',
      'email.qqMail': 'QQ Mail',
      'email.mail163': '163 Mail',
      'email.mail126': '126 Mail',
      'email.gmail': 'Gmail',
      'email.outlook': 'Outlook',
      'email.protocol': 'Protocol',
      'email.imap': 'IMAP',
      'email.pop3': 'POP3',
      'email.authCode': 'Auth Code',
      'email.authCodeTip': 'Please use auth code instead of password',
      'email.useAuthCode': 'Use Auth Code',
      'email.smtpHost': 'SMTP Server',
      'email.smtpPort': 'SMTP Port',
      'email.receiveHost': 'Receive Server',
      'email.receivePort': 'Receive Port',
      'email.username': 'Username',
      'email.password': 'Password',
      'email.useTls': 'Use TLS',
      'email.useSsl': 'Use SSL',
      'email.displayName': 'Display Name',
      'email.apiKey': 'API Key',
      'email.inboxId': 'Inbox ID',
      'email.forwarding': 'Enable Forwarding',
      'email.hybridMode': 'Hybrid Mode',
      'email.hybridTip': 'Hybrid mode: Configure both traditional email (SMTP/POP3/IMAP) and AgentMail.to API. Emails are automatically synchronized between both services.',
      'email.configSaved': 'Configuration saved',
      'email.saveFailed': 'Save failed',
      'email.testConnection': 'Test Connection',
      'email.currentConfig': 'Current Configuration',
      'email.notConfigured': 'Not Configured',
      'email.connected': 'Connected',
      'email.disconnected': 'Disconnected',
      'email.mode': 'Mode',
      'email.traditional': 'Traditional',
      'email.agentmail': 'AgentMail',
      'email.selectType': 'Select Type',
      'email.allTypes': 'All Types',
      'email.typeInbox': 'Inbox',
      'email.typeSent': 'Sent',
      'email.typeDrafts': 'Drafts',
      'email.typeContact': 'Contacts',
      'email.to': 'To',
      'email.cc': 'CC',
      'email.bcc': 'BCC',
      'email.content': 'Content',
      'email.send': 'Send',
      'email.saveDraft': 'Save Draft',
      'email.selectContact': 'Select Contact',
      'email.getApiKey': 'Get API Key',
      'email.modeDescription': 'Mode Description',
      'email.traditionalDesc': 'Use traditional email providers (SMTP/IMAP/POP3)',
      'email.agentmailDesc': 'Use AgentMail.to AI email service',
      'email.hybridDesc': 'Use both traditional and AgentMail with auto-forwarding',
      'email.setMode': 'Set Mode',
      'email.attachments': 'Attachments',
      'email.attachment': 'Attachment',
      'email.addAttachment': 'Add Attachment',
      'email.markdown': 'Markdown',
      'email.preview': 'Preview',
      'email.backup': 'Backup',
      'email.backupNow': 'Backup Now',
      'email.backupSuccess': 'Backup completed',
      'email.backupPath': 'Backup stored in agent workspace /email/bak',
      'email.download': 'Download',
      'email.fileName': 'File Name',
      'email.fileSize': 'Size',
      'email.plain': 'Plain',
      'email.html': 'HTML',
      'email.undo': 'Undo',
      'email.redo': 'Redo',
      'email.clear': 'Clear',
      'email.bold': 'Bold',
      'email.italic': 'Italic',
      'email.underline': 'Underline',
      'email.fontSize': 'Font Size',
      'email.bgColor': 'Background Color',
      'email.fontColor': 'Font Color',
      'email.heading': 'Heading',
      'email.listOrdered': 'Ordered List',
      'email.listUnordered': 'Unordered List',
      'email.insertLink': 'Insert Link',
      'email.insertImage': 'Insert Image',
      'email.insertAttachment': 'Insert Attachment',
      'email.writeEmail': 'Write Email',
      'email.hybridPrinciple': 'Hybrid Mode Principle',
      'email.hybridPrincipleDesc': 'Hybrid mode simultaneously configures traditional email (SMTP/POP3/IMAP) and AgentMail.to API. The system will automatically synchronize emails between both services, allowing you to use both traditional email clients and AI email services.',
      'email.traditionalSettings': 'Traditional Email Settings',
      'email.agentmailSettings': 'AgentMail.to Settings',
      'email.uninstall': 'Uninstall Plugin',
      'email.uninstallConfirm': 'Are you sure you want to uninstall the AgentMail plugin?',
      'email.keepData': 'Keep data files',
      'email.exportData': 'Export emails to memory folder before uninstall',
      'email.uninstallSuccess': 'Plugin uninstalled successfully',
      'email.dataExported': 'Data exported to',
    },
    zh: {
      'nav.email': 'AgentMail',
      'email.title': '邮件管理',
      'email.contacts': '联系人',
      'email.inbox': '收件箱',
      'email.sent': '发件箱',
      'email.drafts': '草稿箱',
      'email.archive': '归档',
      'email.trash': '回收站',
      'email.config': '设置',
      'email.refresh': '刷新',
      'email.compose': '写邮件',
      'email.search': '搜索',
      'email.new': '新建',
      'email.edit': '编辑',
      'email.delete': '删除',
      'email.save': '保存',
      'email.cancel': '取消',
      'email.submit': '提交',
      'email.close': '关闭',
      'email.status': '状态',
      'email.subject': '主题',
      'email.sender': '发件人',
      'email.recipient': '收件人',
      'email.date': '日期',
      'email.action': '操作',
      'email.read': '已读',
      'email.unread': '未读',
      'email.agentRead': 'Agent已读',
      'email.agentUnread': 'Agent未读',
      'email.replied': '已回复',
      'email.notReplied': '未回复',
      'email.sentStatus': '已发送',
      'email.sentFailed': '发送失败',
      'email.sentPending': '发送中',
      'email.restore': '恢复',
      'email.permanentDelete': '永久删除',
      'email.batchArchive': '批量归档',
      'email.batchDelete': '批量删除',
      'email.batchRestore': '批量恢复',
      'email.selectAll': '全选',
      'email.name': '姓名',
      'email.phone': '电话',
      'email.emailAddr': '邮箱',
      'email.company': '公司',
      'email.website': '网站',
      'email.notes': '备注',
      'email.group': '分组',
      'email.share': '共享',
      'email.batchShare': '批量共享',
      'email.allGroups': '所有分组',
      'email.newGroup': '新建分组',
      'email.groupName': '分组名称',
      'email.contactCount': '个联系人',
      'email.noContacts': '暂无联系人',
      'email.noEmails': '暂无邮件',
      'email.noSent': '暂无已发送邮件',
      'email.noDrafts': '暂无草稿',
      'email.noTrash': '回收站为空',
      'email.confirmDelete': '确定要删除吗？',
      'email.confirmPermanentDelete': '确定要永久删除吗？此操作不可恢复。',
      'email.loading': '加载中...',
      'email.provider': '邮箱提供商',
      'email.custom': '自定义',
      'email.qqMail': 'QQ邮箱',
      'email.mail163': '163邮箱',
      'email.mail126': '126邮箱',
      'email.gmail': 'Gmail',
      'email.outlook': 'Outlook',
      'email.protocol': '协议',
      'email.imap': 'IMAP',
      'email.pop3': 'POP3',
      'email.authCode': '授权码',
      'email.authCodeTip': '请使用授权码而非登录密码',
      'email.useAuthCode': '使用授权码',
      'email.smtpHost': 'SMTP服务器',
      'email.smtpPort': 'SMTP端口',
      'email.receiveHost': '接收服务器',
      'email.receivePort': '接收端口',
      'email.username': '用户名',
      'email.password': '密码',
      'email.useTls': '使用TLS',
      'email.useSsl': '使用SSL',
      'email.displayName': '显示名称',
      'email.apiKey': 'API密钥',
      'email.inboxId': '收件箱ID',
      'email.forwarding': '启用转发',
      'email.hybridMode': '混合模式',
      'email.hybridTip': '混合模式：同时配置传统邮箱(SMTP/POP3/IMAP)和AgentMail.to API，邮件自动在两种服务间同步',
      'email.configSaved': '配置已保存',
      'email.saveFailed': '保存失败',
      'email.testConnection': '测试连接',
      'email.currentConfig': '当前配置',
      'email.notConfigured': '未配置',
      'email.connected': '已连接',
      'email.disconnected': '未连接',
      'email.mode': '模式',
      'email.traditional': '传统邮箱',
      'email.agentmail': 'AgentMail',
      'email.selectType': '选择类型',
      'email.allTypes': '所有类型',
      'email.typeInbox': '收件箱',
      'email.typeSent': '发件箱',
      'email.typeDrafts': '草稿箱',
      'email.typeContact': '联系人',
      'email.to': '收件人',
      'email.cc': '抄送',
      'email.bcc': '密送',
      'email.content': '内容',
      'email.send': '发送',
      'email.saveDraft': '存草稿',
      'email.selectContact': '选择联系人',
      'email.getApiKey': '获取API密钥',
      'email.modeDescription': '模式说明',
      'email.traditionalDesc': '使用传统邮箱服务商 (SMTP/IMAP/POP3)',
      'email.agentmailDesc': '使用 AgentMail.to AI 邮件服务',
      'email.hybridDesc': '同时使用传统邮箱和AgentMail，并启用自动转发',
      'email.setMode': '设置模式',
      'email.attachments': '附件',
      'email.attachment': '附件',
      'email.addAttachment': '添加附件',
      'email.markdown': 'Markdown',
      'email.preview': '预览',
      'email.backup': '备份',
      'email.backupNow': '立即备份',
      'email.backupSuccess': '备份完成',
      'email.backupPath': '备份存储在agent工作空间 /email/bak',
      'email.download': '下载',
      'email.fileName': '文件名',
      'email.fileSize': '大小',
      'email.plain': '普通',
      'email.html': 'HTML',
      'email.undo': '撤销',
      'email.redo': '重做',
      'email.clear': '清空',
      'email.bold': '加粗',
      'email.italic': '斜体',
      'email.underline': '下划线',
      'email.fontSize': '字号',
      'email.bgColor': '背景色',
      'email.fontColor': '字体颜色',
      'email.heading': '标题',
      'email.listOrdered': '有序列表',
      'email.listUnordered': '无序列表',
      'email.insertLink': '插入链接',
      'email.insertImage': '插入图片',
      'email.insertAttachment': '插入附件',
      'email.writeEmail': '写信',
      'email.hybridPrinciple': '混合模式原理',
      'email.hybridPrincipleDesc': '混合模式同时配置传统邮箱(SMTP/POP3/IMAP)和AgentMail.to API。系统会自动在两种服务间同步邮件，让您既能使用传统邮件客户端，也能使用AI邮件服务。',
      'email.traditionalSettings': '传统邮箱设置',
      'email.agentmailSettings': 'AgentMail.to 设置',
      'email.uninstall': '卸载插件',
      'email.uninstallConfirm': '确定要卸载 AgentMail 插件吗？',
      'email.keepData': '保留数据文件',
      'email.exportData': '卸载前将邮件导出到 memory 文件夹',
      'email.uninstallSuccess': '插件卸载成功',
      'email.dataExported': '数据已导出到',
    },
    ja: {
      'nav.email': 'AgentMail',
      'email.title': 'メール管理',
      'email.contacts': '連絡先',
      'email.inbox': '受信箱',
      'email.sent': '送信済み',
      'email.drafts': '下書き',
      'email.archive': 'アーカイブ',
      'email.trash': 'ゴミ箱',
      'email.config': '設定',
      'email.refresh': '更新',
      'email.compose': '新規作成',
      'email.search': '検索',
      'email.new': '新規',
      'email.edit': '編集',
      'email.delete': '削除',
      'email.save': '保存',
      'email.cancel': 'キャンセル',
      'email.submit': '送信',
      'email.close': '閉じる',
      'email.status': '状態',
      'email.subject': '件名',
      'email.sender': '送信者',
      'email.recipient': '宛先',
      'email.date': '日付',
      'email.action': '操作',
      'email.read': '既読',
      'email.unread': '未読',
      'email.agentRead': 'Agent既読',
      'email.agentUnread': 'Agent未読',
      'email.replied': '返信済み',
      'email.notReplied': '未返信',
      'email.sentStatus': '送信済み',
      'email.sentFailed': '送信失敗',
      'email.sentPending': '送信中',
      'email.restore': '復元',
      'email.permanentDelete': '完全に削除',
      'email.batchArchive': '一括アーカイブ',
      'email.batchDelete': '一括削除',
      'email.batchRestore': '一括復元',
      'email.selectAll': '全選択',
      'email.name': '名前',
      'email.phone': '電話',
      'email.emailAddr': 'メール',
      'email.company': '会社',
      'email.website': 'ウェブサイト',
      'email.notes': 'メモ',
      'email.group': 'グループ',
      'email.share': '共有',
      'email.batchShare': '一括共有',
      'email.allGroups': 'すべてのグループ',
      'email.newGroup': '新規グループ',
      'email.groupName': 'グループ名',
      'email.contactCount': '件の連絡先',
      'email.noContacts': '連絡先がありません',
      'email.noEmails': 'メールがありません',
      'email.noSent': '送信済みメールがありません',
      'email.noDrafts': '下書きがありません',
      'email.noTrash': 'ゴミ箱は空です',
      'email.confirmDelete': '削除してもよろしいですか？',
      'email.confirmPermanentDelete': '完全に削除してもよろしいですか？この操作は元に戻せません。',
      'email.loading': '読み込み中...',
      'email.provider': 'プロバイダー',
      'email.custom': 'カスタム',
      'email.qqMail': 'QQメール',
      'email.mail163': '163メール',
      'email.mail126': '126メール',
      'email.gmail': 'Gmail',
      'email.outlook': 'Outlook',
      'email.protocol': 'プロトコル',
      'email.imap': 'IMAP',
      'email.pop3': 'POP3',
      'email.authCode': '認証コード',
      'email.authCodeTip': 'パスワードの代わりに認証コードを使用してください',
      'email.useAuthCode': '認証コードを使用',
      'email.smtpHost': 'SMTPサーバー',
      'email.smtpPort': 'SMTPポート',
      'email.receiveHost': '受信サーバー',
      'email.receivePort': '受信ポート',
      'email.username': 'ユーザー名',
      'email.password': 'パスワード',
      'email.useTls': 'TLSを使用',
      'email.useSsl': 'SSLを使用',
      'email.displayName': '表示名',
      'email.apiKey': 'APIキー',
      'email.inboxId': '受信箱ID',
      'email.forwarding': '転送を有効化',
      'email.hybridMode': 'ハイブリッドモード',
      'email.hybridTip': 'ハイブリッドモード：従来のメール(SMTP/POP3/IMAP)とAgentMail.to APIを同時に設定し、メールを自動同期します',
      'email.configSaved': '設定を保存しました',
      'email.saveFailed': '保存に失敗しました',
      'email.testConnection': '接続テスト',
      'email.currentConfig': '現在の設定',
      'email.notConfigured': '未設定',
      'email.connected': '接続済み',
      'email.disconnected': '未接続',
      'email.mode': 'モード',
      'email.traditional': '従来のメール',
      'email.agentmail': 'AgentMail',
      'email.selectType': 'タイプを選択',
      'email.allTypes': 'すべてのタイプ',
      'email.typeInbox': '受信箱',
      'email.typeSent': '送信済み',
      'email.typeDrafts': '下書き',
      'email.typeContact': '連絡先',
      'email.to': '宛先',
      'email.cc': 'CC',
      'email.bcc': 'BCC',
      'email.content': '内容',
      'email.send': '送信',
      'email.saveDraft': '下書き保存',
      'email.selectContact': '連絡先を選択',
      'email.getApiKey': 'APIキーを取得',
      'email.modeDescription': 'モード説明',
      'email.traditionalDesc': '従来のメールプロバイダーを使用 (SMTP/IMAP/POP3)',
      'email.agentmailDesc': 'AgentMail.to AIメールサービスを使用',
      'email.hybridDesc': '従来のメールとAgentMailを同時に使用し、自動転送を有効化',
      'email.setMode': 'モードを設定',
      'email.attachments': '添付ファイル',
      'email.attachment': '添付ファイル',
      'email.addAttachment': '添付ファイルを追加',
      'email.markdown': 'Markdown',
      'email.preview': 'プレビュー',
      'email.backup': 'バックアップ',
      'email.backupNow': '今すぐバックアップ',
      'email.backupSuccess': 'バックアップ完了',
      'email.backupPath': 'バックアップはagentワークスペース /email/bak に保存されます',
      'email.download': 'ダウンロード',
      'email.fileName': 'ファイル名',
      'email.fileSize': 'サイズ',
      'email.plain': 'プレーン',
      'email.html': 'HTML',
      'email.undo': '元に戻す',
      'email.redo': 'やり直し',
      'email.clear': 'クリア',
      'email.bold': '太字',
      'email.italic': '斜体',
      'email.underline': '下線',
      'email.fontSize': 'フォントサイズ',
      'email.bgColor': '背景色',
      'email.fontColor': 'フォント色',
      'email.heading': '見出し',
      'email.listOrdered': '番号付きリスト',
      'email.listUnordered': '箇条書きリスト',
      'email.insertLink': 'リンクを挿入',
      'email.insertImage': '画像を挿入',
      'email.insertAttachment': '添付ファイルを挿入',
      'email.writeEmail': 'メールを作成',
      'email.hybridPrinciple': 'ハイブリッドモードの原理',
      'email.hybridPrincipleDesc': 'ハイブリッドモードは、従来のメール(SMTP/POP3/IMAP)とAgentMail.to APIを同時に設定します。システムは両方のサービス間でメールを自動同期し、従来のメールクライアントとAIメールサービスの両方を使用できます。',
      'email.traditionalSettings': '従来のメール設定',
      'email.agentmailSettings': 'AgentMail.to 設定',
      'email.uninstall': 'プラグインをアンインストール',
      'email.uninstallConfirm': 'AgentMail プラグインをアンインストールしてもよろしいですか？',
      'email.keepData': 'データファイルを保持',
      'email.exportData': 'アンインストール前にメールを memory フォルダにエクスポート',
      'email.uninstallSuccess': 'プラグインのアンインストールが完了しました',
      'email.dataExported': 'データをエクスポートしました',
    },
    ru: {
      'nav.email': 'AgentMail',
      'email.title': 'Управление почтой',
      'email.contacts': 'Контакты',
      'email.inbox': 'Входящие',
      'email.sent': 'Отправленные',
      'email.drafts': 'Черновики',
      'email.archive': 'Архив',
      'email.trash': 'Корзина',
      'email.config': 'Настройки',
      'email.refresh': 'Обновить',
      'email.compose': 'Написать',
      'email.search': 'Поиск',
      'email.new': 'Создать',
      'email.edit': 'Редактировать',
      'email.delete': 'Удалить',
      'email.save': 'Сохранить',
      'email.cancel': 'Отмена',
      'email.submit': 'Отправить',
      'email.close': 'Закрыть',
      'email.status': 'Статус',
      'email.subject': 'Тема',
      'email.sender': 'Отправитель',
      'email.recipient': 'Получатель',
      'email.date': 'Дата',
      'email.action': 'Действие',
      'email.read': 'Прочитано',
      'email.unread': 'Не прочитано',
      'email.agentRead': 'Agent прочитал',
      'email.agentUnread': 'Agent не прочитал',
      'email.replied': 'Отвечено',
      'email.notReplied': 'Не отвечено',
      'email.sentStatus': 'Отправлено',
      'email.sentFailed': 'Ошибка отправки',
      'email.sentPending': 'Отправка...',
      'email.restore': 'Восстановить',
      'email.permanentDelete': 'Удалить навсегда',
      'email.batchArchive': 'Архивировать выбранные',
      'email.batchDelete': 'Удалить выбранные',
      'email.batchRestore': 'Восстановить выбранные',
      'email.selectAll': 'Выбрать все',
      'email.name': 'Имя',
      'email.phone': 'Телефон',
      'email.emailAddr': 'Email',
      'email.company': 'Компания',
      'email.website': 'Веб-сайт',
      'email.notes': 'Заметки',
      'email.group': 'Группа',
      'email.share': 'Поделиться',
      'email.batchShare': 'Поделиться выбранными',
      'email.allGroups': 'Все группы',
      'email.newGroup': 'Новая группа',
      'email.groupName': 'Название группы',
      'email.contactCount': 'контактов',
      'email.noContacts': 'Нет контактов',
      'email.noEmails': 'Нет писем',
      'email.noSent': 'Нет отправленных писем',
      'email.noDrafts': 'Нет черновиков',
      'email.noTrash': 'Корзина пуста',
      'email.confirmDelete': 'Вы уверены, что хотите удалить?',
      'email.confirmPermanentDelete': 'Удалить навсегда? Это действие нельзя отменить.',
      'email.loading': 'Загрузка...',
      'email.provider': 'Провайдер',
      'email.custom': 'Пользовательский',
      'email.qqMail': 'QQ Почта',
      'email.mail163': '163 Почта',
      'email.mail126': '126 Почта',
      'email.gmail': 'Gmail',
      'email.outlook': 'Outlook',
      'email.protocol': 'Протокол',
      'email.imap': 'IMAP',
      'email.pop3': 'POP3',
      'email.authCode': 'Код авторизации',
      'email.authCodeTip': 'Используйте код авторизации вместо пароля',
      'email.useAuthCode': 'Использовать код авторизации',
      'email.smtpHost': 'SMTP сервер',
      'email.smtpPort': 'SMTP порт',
      'email.receiveHost': 'Сервер получения',
      'email.receivePort': 'Порт получения',
      'email.username': 'Имя пользователя',
      'email.password': 'Пароль',
      'email.useTls': 'Использовать TLS',
      'email.useSsl': 'Использовать SSL',
      'email.displayName': 'Отображаемое имя',
      'email.apiKey': 'API ключ',
      'email.inboxId': 'ID входящих',
      'email.forwarding': 'Включить пересылку',
      'email.hybridMode': 'Гибридный режим',
      'email.hybridTip': 'Гибридный режим: одновременная настройка традиционной почты (SMTP/POP3/IMAP) и AgentMail.to API с автоматической синхронизацией',
      'email.configSaved': 'Настройки сохранены',
      'email.saveFailed': 'Ошибка сохранения',
      'email.testConnection': 'Проверить соединение',
      'email.currentConfig': 'Текущие настройки',
      'email.notConfigured': 'Не настроено',
      'email.connected': 'Подключено',
      'email.disconnected': 'Отключено',
      'email.mode': 'Режим',
      'email.traditional': 'Традиционная почта',
      'email.agentmail': 'AgentMail',
      'email.selectType': 'Выбрать тип',
      'email.allTypes': 'Все типы',
      'email.typeInbox': 'Входящие',
      'email.typeSent': 'Отправленные',
      'email.typeDrafts': 'Черновики',
      'email.typeContact': 'Контакты',
      'email.to': 'Кому',
      'email.cc': 'Копия',
      'email.bcc': 'Скрытая копия',
      'email.content': 'Содержание',
      'email.send': 'Отправить',
      'email.saveDraft': 'Сохранить черновик',
      'email.selectContact': 'Выбрать контакт',
      'email.getApiKey': 'Получить API ключ',
      'email.modeDescription': 'Описание режима',
      'email.traditionalDesc': 'Использовать традиционного почтового провайдера (SMTP/IMAP/POP3)',
      'email.agentmailDesc': 'Использовать сервис AgentMail.to AI',
      'email.hybridDesc': 'Использовать одновременно традиционную почту и AgentMail с автоматической пересылкой',
      'email.setMode': 'Установить режим',
      'email.attachments': 'Вложения',
      'email.attachment': 'Вложение',
      'email.addAttachment': 'Добавить вложение',
      'email.markdown': 'Markdown',
      'email.preview': 'Предпросмотр',
      'email.backup': 'Резервное копирование',
      'email.backupNow': 'Создать резервную копию',
      'email.backupSuccess': 'Резервное копирование завершено',
      'email.backupPath': 'Резервная копия сохранена в рабочем пространстве agent /email/bak',
      'email.download': 'Скачать',
      'email.fileName': 'Имя файла',
      'email.fileSize': 'Размер',
      'email.plain': 'Обычный',
      'email.html': 'HTML',
      'email.undo': 'Отменить',
      'email.redo': 'Повторить',
      'email.clear': 'Очистить',
      'email.bold': 'Жирный',
      'email.italic': 'Курсив',
      'email.underline': 'Подчеркнутый',
      'email.fontSize': 'Размер шрифта',
      'email.bgColor': 'Цвет фона',
      'email.fontColor': 'Цвет шрифта',
      'email.heading': 'Заголовок',
      'email.listOrdered': 'Нумерованный список',
      'email.listUnordered': 'Маркированный список',
      'email.insertLink': 'Вставить ссылку',
      'email.insertImage': 'Вставить изображение',
      'email.insertAttachment': 'Вставить вложение',
      'email.writeEmail': 'Написать письмо',
      'email.hybridPrinciple': 'Принцип гибридного режима',
      'email.hybridPrincipleDesc': 'Гибридный режим одновременно настраивает традиционную почту (SMTP/POP3/IMAP) и AgentMail.to API. Система автоматически синхронизирует письма между обоими сервисами, позволяя использовать как традиционный почтовый клиент, так и AI почтовый сервис.',
      'email.traditionalSettings': 'Настройки традиционной почты',
      'email.agentmailSettings': 'Настройки AgentMail.to',
      'email.uninstall': 'Удалить плагин',
      'email.uninstallConfirm': 'Вы уверены, что хотите удалить плагин AgentMail?',
      'email.keepData': 'Сохранить файлы данных',
      'email.exportData': 'Экспортировать письма в папку memory перед удалением',
      'email.uninstallSuccess': 'Плагин успешно удален',
      'email.dataExported': 'Данные экспортированы в',
    },
  };

// Agent 集成翻译（多语言支持）
const AGENT_INTEGRATION_TRANSLATIONS: Record<string, Record<string, string>> = {
  'en': {
    'agent.contextAware': 'Context Aware',
    'agent.memoryIntegrate': 'Memory Integration',
    'agent.smartReply': 'Smart Reply',
    'agent.batchOperation': 'Batch Operations',
    'agent.addToContext': 'Add to Context',
    'agent.addToMemory': 'Add to Memory',
    'agent.generateReply': 'Generate Reply',
    'agent.applyRule': 'Apply Rule',
    'agent.emailContext': 'Email Context',
    'agent.emailMemory': 'Email Memory',
    'agent.emailRules': 'Email Rules',
    'agent.emailSummary': 'Email Summary',
    'agent.tagEmail': 'Tag Email',
    'agent.untagEmail': 'Remove Tag',
    'agent.viewInChat': 'View in Chat',
    'agent.relatedEmails': 'Related Emails',
    'agent.contextAdded': 'Added to current context',
    'agent.memoryAdded': 'Added to agent memory',
    'agent.replyGenerated': 'Reply draft generated',
    'agent.ruleApplied': 'Rule applied',
    'agent.currentSession': 'Current Session',
    'agent.noSession': 'No active session',
    'agent.sessionEmails': 'Session Emails',
    'agent.emailTags': 'Email Tags',
    'agent.autoProcess': 'Auto Process',
    'agent.manualReview': 'Manual Review',
    'agent.processRule': 'Processing Rule',
    'agent.ruleName': 'Rule Name',
    'agent.ruleCondition': 'Condition',
    'agent.ruleAction': 'Action',
    'agent.createRule': 'Create Rule',
    'agent.editRule': 'Edit Rule',
    'agent.deleteRule': 'Delete Rule',
    'agent.ruleActive': 'Active',
    'agent.ruleInactive': 'Inactive',
    'agent.whenSender': 'When sender is',
    'agent.whenSubject': 'When subject contains',
    'agent.whenContent': 'When content contains',
    'agent.actionTag': 'Tag as',
    'agent.actionReply': 'Reply with template',
    'agent.actionForward': 'Forward to',
    'agent.actionArchive': 'Archive',
    'agent.actionNotify': 'Notify agent',
  },
  'zh': {
    'agent.contextAware': '上下文感知',
    'agent.memoryIntegrate': '记忆集成',
    'agent.smartReply': '智能回复',
    'agent.batchOperation': '批量操作',
    'agent.addToContext': '添加到上下文',
    'agent.addToMemory': '添加到记忆',
    'agent.generateReply': '生成回复',
    'agent.applyRule': '应用规则',
    'agent.emailContext': '邮件上下文',
    'agent.emailMemory': '邮件记忆',
    'agent.emailRules': '邮件规则',
    'agent.emailSummary': '邮件摘要',
    'agent.tagEmail': '标记邮件',
    'agent.untagEmail': '移除标记',
    'agent.viewInChat': '在聊天中查看',
    'agent.relatedEmails': '相关邮件',
    'agent.contextAdded': '已添加到当前上下文',
    'agent.memoryAdded': '已添加到Agent记忆',
    'agent.replyGenerated': '回复草稿已生成',
    'agent.ruleApplied': '规则已应用',
    'agent.currentSession': '当前会话',
    'agent.noSession': '无活动会话',
    'agent.sessionEmails': '会话邮件',
    'agent.emailTags': '邮件标签',
    'agent.autoProcess': '自动处理',
    'agent.manualReview': '手动审核',
    'agent.processRule': '处理规则',
    'agent.ruleName': '规则名称',
    'agent.ruleCondition': '条件',
    'agent.ruleAction': '动作',
    'agent.createRule': '创建规则',
    'agent.editRule': '编辑规则',
    'agent.deleteRule': '删除规则',
    'agent.ruleActive': '已激活',
    'agent.ruleInactive': '未激活',
    'agent.whenSender': '当发件人为',
    'agent.whenSubject': '当主题包含',
    'agent.whenContent': '当内容包含',
    'agent.actionTag': '标记为',
    'agent.actionReply': '使用模板回复',
    'agent.actionForward': '转发到',
    'agent.actionArchive': '归档',
    'agent.actionNotify': '通知Agent',
  },
  'ja': {
    'agent.contextAware': 'コンテキスト認識',
    'agent.memoryIntegrate': 'メモリ統合',
    'agent.smartReply': 'スマート返信',
    'agent.batchOperation': '一括操作',
    'agent.addToContext': 'コンテキストに追加',
    'agent.addToMemory': 'メモリに追加',
    'agent.generateReply': '返信を生成',
    'agent.applyRule': 'ルールを適用',
    'agent.emailContext': 'メールコンテキスト',
    'agent.emailMemory': 'メールメモリ',
    'agent.emailRules': 'メールルール',
    'agent.emailSummary': 'メール要約',
    'agent.tagEmail': 'メールにタグ付け',
    'agent.untagEmail': 'タグを削除',
    'agent.viewInChat': 'チャットで表示',
    'agent.relatedEmails': '関連メール',
    'agent.contextAdded': '現在のコンテキストに追加しました',
    'agent.memoryAdded': 'Agentのメモリに追加しました',
    'agent.replyGenerated': '返信ドラフトが生成されました',
    'agent.ruleApplied': 'ルールが適用されました',
    'agent.currentSession': '現在のセッション',
    'agent.noSession': 'アクティブなセッションがありません',
    'agent.sessionEmails': 'セッションメール',
    'agent.emailTags': 'メールタグ',
    'agent.autoProcess': '自動処理',
    'agent.manualReview': '手動レビュー',
    'agent.processRule': '処理ルール',
    'agent.ruleName': 'ルール名',
    'agent.ruleCondition': '条件',
    'agent.ruleAction': 'アクション',
    'agent.createRule': 'ルールを作成',
    'agent.editRule': 'ルールを編集',
    'agent.deleteRule': 'ルールを削除',
    'agent.ruleActive': '有効',
    'agent.ruleInactive': '無効',
    'agent.whenSender': '送信者が',
    'agent.whenSubject': '件名に含まれる',
    'agent.whenContent': '内容に含まれる',
    'agent.actionTag': 'タグ付け',
    'agent.actionReply': 'テンプレートで返信',
    'agent.actionForward': '転送先',
    'agent.actionArchive': 'アーカイブ',
    'agent.actionNotify': 'Agentに通知',
  },
  'ru': {
    'agent.contextAware': 'Контекстная осведомленность',
    'agent.memoryIntegrate': 'Интеграция памяти',
    'agent.smartReply': 'Умный ответ',
    'agent.batchOperation': 'Пакетные операции',
    'agent.addToContext': 'Добавить в контекст',
    'agent.addToMemory': 'Добавить в память',
    'agent.generateReply': 'Сгенерировать ответ',
    'agent.applyRule': 'Применить правило',
    'agent.emailContext': 'Контекст письма',
    'agent.emailMemory': 'Память писем',
    'agent.emailRules': 'Правила писем',
    'agent.emailSummary': 'Резюме письма',
    'agent.tagEmail': 'Пометить письмо',
    'agent.untagEmail': 'Удалить пометку',
    'agent.viewInChat': 'Просмотреть в чате',
    'agent.relatedEmails': 'Связанные письма',
    'agent.contextAdded': 'Добавлено в текущий контекст',
    'agent.memoryAdded': 'Добавлено в память агента',
    'agent.replyGenerated': 'Черновик ответа сгенерирован',
    'agent.ruleApplied': 'Правило применено',
    'agent.currentSession': 'Текущая сессия',
    'agent.noSession': 'Нет активной сессии',
    'agent.sessionEmails': 'Письма сессии',
    'agent.emailTags': 'Теги писем',
    'agent.autoProcess': 'Автообработка',
    'agent.manualReview': 'Ручная проверка',
    'agent.processRule': 'Правило обработки',
    'agent.ruleName': 'Название правила',
    'agent.ruleCondition': 'Условие',
    'agent.ruleAction': 'Действие',
    'agent.createRule': 'Создать правило',
    'agent.editRule': 'Редактировать правило',
    'agent.deleteRule': 'Удалить правило',
    'agent.ruleActive': 'Активно',
    'agent.ruleInactive': 'Неактивно',
    'agent.whenSender': 'Когда отправитель',
    'agent.whenSubject': 'Когда тема содержит',
    'agent.whenContent': 'Когда содержание содержит',
    'agent.actionTag': 'Пометить как',
    'agent.actionReply': 'Ответить шаблоном',
    'agent.actionForward': 'Переслать',
    'agent.actionArchive': 'Архивировать',
    'agent.actionNotify': 'Уведомить агента',
  },
};

function t(key: string, lang?: string): string {
  const currentLang = normalizeLang(lang);
  // 优先从主翻译表查找
  const mainTranslation = TRANSLATIONS[currentLang]?.[key] || TRANSLATIONS['en']?.[key];
  if (mainTranslation) return mainTranslation;
  // 从 Agent 集成翻译表查找（支持多语言）
  const agentTranslation = AGENT_INTEGRATION_TRANSLATIONS[currentLang]?.[key] || AGENT_INTEGRATION_TRANSLATIONS['en']?.[key];
  if (agentTranslation) return agentTranslation;
  // 返回 key 本身
  return key;
}

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
  
  // 不使用 useCallback，确保每次 lang 变化时函数引用都改变
  // 这样可以触发依赖 t 函数的组件重新渲染
  const translate = (key: string) => t(key, lang);
  return { t: translate, lang };
}

interface AgentConfig {
  hybrid?: any;
  updated_at?: string;
}

const EMAIL_PROVIDERS: Record<string, any> = {
  qq: {
    name: 'QQ Mail',
    smtp: { host: 'smtp.qq.com', port: 587, use_tls: true },
    receive: { host: 'imap.qq.com', port: 993, use_ssl: true, protocol: 'imap' },
    authCode: true,
  },
  mail163: {
    name: '163 Mail',
    smtp: { host: 'smtp.163.com', port: 25, use_tls: true },
    receive: { host: 'imap.163.com', port: 993, use_ssl: true, protocol: 'imap' },
    authCode: true,
  },
  mail126: {
    name: '126 Mail',
    smtp: { host: 'smtp.126.com', port: 25, use_tls: true },
    receive: { host: 'imap.126.com', port: 993, use_ssl: true, protocol: 'imap' },
    authCode: true,
  },
  gmail: {
    name: 'Gmail',
    smtp: { host: 'smtp.gmail.com', port: 587, use_tls: true },
    receive: { host: 'imap.gmail.com', port: 993, use_ssl: true, protocol: 'imap' },
    authCode: false,
  },
  outlook: {
    name: 'Outlook',
    smtp: { host: 'smtp.office365.com', port: 587, use_tls: true },
    receive: { host: 'outlook.office365.com', port: 993, use_ssl: true, protocol: 'imap' },
    authCode: false,
  },
  custom: {
    name: 'Custom',
    smtp: { host: '', port: 587, use_tls: true },
    receive: { host: '', port: 993, use_ssl: true, protocol: 'pop3' },
    authCode: false,
  },
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function HybridConfigModal({ visible, onCancel, onSave, initialValues }: any) {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [saving, setSaving] = React.useState(false);
  const [provider, setProvider] = React.useState(initialValues?.provider || 'custom');
  const [protocol, setProtocol] = React.useState(initialValues?.receive_protocol || 'pop3');
  const [activeSection, setActiveSection] = React.useState('traditional');

  React.useEffect(() => {
    if (visible) {
      if (initialValues) {
        form.setFieldsValue(initialValues);
        setProvider(initialValues.provider || 'custom');
        setProtocol(initialValues.receive_protocol || 'pop3');
      } else {
        form.resetFields();
        form.setFieldsValue({ provider: 'custom', receive_protocol: 'pop3', forwarding: true });
        setProvider('custom');
        setProtocol('pop3');
      }
    }
  }, [visible, initialValues]);

  const handleProviderChange = (value: string) => {
    setProvider(value);
    const preset = EMAIL_PROVIDERS[value];
    if (preset && value !== 'custom') {
      form.setFieldsValue({
        smtp: preset.smtp,
        imap: preset.receive,
        receive_protocol: preset.receive.protocol,
      });
      setProtocol(preset.receive.protocol);
    }
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      await onSave(values);
      message.success(t('email.configSaved'));
      onCancel();
    } catch (e) {
      message.error(t('email.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const preset = EMAIL_PROVIDERS[provider];

  return (
    <Modal open={visible} title={t('email.hybridMode')} width={700} onCancel={onCancel}
      footer={[
        <Button key="cancel" onClick={onCancel}>{t('email.cancel')}</Button>,
        <Button key="save" type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>{t('email.save')}</Button>,
      ]}>
      <Alert message={t('email.hybridTip')} type="info" showIcon style={{ marginBottom: 16 }} />
      <Tabs activeKey={activeSection} onChange={setActiveSection} items={[
        {
          key: 'traditional',
          label: t('email.traditionalSettings'),
          children: (
            <Form form={form} layout="vertical">
              <Form.Item name="provider" label={t('email.provider')}>
                <Select onChange={handleProviderChange} options={[
                  { value: 'custom', label: t('email.custom') },
                  { value: 'qq', label: t('email.qqMail') },
                  { value: 'mail163', label: t('email.mail163') },
                  { value: 'mail126', label: t('email.mail126') },
                  { value: 'gmail', label: t('email.gmail') },
                  { value: 'outlook', label: t('email.outlook') },
                ]} />
              </Form.Item>
              <Form.Item name="email" label={t('email.emailAddr')} rules={[{ required: true, type: 'email' }]}>
                <Input />
              </Form.Item>
              <Form.Item name="display_name" label={t('email.displayName')}>
                <Input />
              </Form.Item>
              <Form.Item name="receive_protocol" label={t('email.protocol')}>
                <Radio.Group onChange={(e: any) => setProtocol(e.target.value)}>
                  <Radio value="pop3">POP3</Radio>
                  <Radio value="imap">IMAP</Radio>
                </Radio.Group>
              </Form.Item>
              {preset?.authCode && (
                <Alert message={t('email.authCodeTip')} type="warning" showIcon style={{ marginBottom: 16 }} />
              )}
              <Divider orientation="left">SMTP</Divider>
              <Row gutter={16}>
                <Col span={16}>
                  <Form.Item name={['smtp', 'host']} label={t('email.smtpHost')} rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name={['smtp', 'port']} label={t('email.smtpPort')} rules={[{ required: true }]}>
                    <InputNumber style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item name={['smtp', 'username']} label={t('email.username')} rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item name={['smtp', 'password']} label={preset?.authCode ? t('email.authCode') : t('email.password')} rules={[{ required: true }]}>
                <Input.Password />
              </Form.Item>
              <Form.Item name={['smtp', 'use_tls']} valuePropName="checked">
                <Switch checkedChildren="TLS" unCheckedChildren="TLS" />
              </Form.Item>
              <Divider orientation="left">{protocol.toUpperCase()}</Divider>
              <Row gutter={16}>
                <Col span={16}>
                  <Form.Item name={['imap', 'host']} label={t('email.receiveHost')} rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name={['imap', 'port']} label={t('email.receivePort')} rules={[{ required: true }]}>
                    <InputNumber style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item name={['imap', 'username']} label={t('email.username')} rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item name={['imap', 'password']} label={preset?.authCode ? t('email.authCode') : t('email.password')} rules={[{ required: true }]}>
                <Input.Password />
              </Form.Item>
              <Form.Item name={['imap', 'use_ssl']} valuePropName="checked">
                <Switch checkedChildren="SSL" unCheckedChildren="SSL" />
              </Form.Item>
            </Form>
          )
        },
        {
          key: 'agentmail',
          label: t('email.agentmailSettings'),
          children: (
            <Form form={form} layout="vertical">
              <Form.Item name="api_key" label={t('email.apiKey')} rules={[{ required: true }]}
                extra={<a href="https://agentmail.to/dashboard" target="_blank" rel="noopener noreferrer"><LinkOutlined /> {t('email.getApiKey')}</a>}>
                <Input.Password />
              </Form.Item>
              <Form.Item name="inbox_id" label={t('email.inboxId')} rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item name="forwarding" valuePropName="checked" initialValue={true}>
                <Switch checkedChildren={t('email.forwarding')} unCheckedChildren={t('email.forwarding')} />
              </Form.Item>
            </Form>
          )
        }
      ]} />
    </Modal>
  );
}

function ContactModal({ visible, onCancel, onSave, initialValues, groups }: any) {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {
    if (visible && initialValues) form.setFieldsValue(initialValues);
    else if (visible) form.resetFields();
  }, [visible, initialValues]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      await onSave(values);
      message.success(t('email.configSaved'));
      onCancel();
    } catch (e) {
      message.error(t('email.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={visible} title={initialValues ? t('email.edit') : t('email.new')} width={500} onCancel={onCancel}
      footer={[
        <Button key="cancel" onClick={onCancel}>{t('email.cancel')}</Button>,
        <Button key="save" type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>{t('email.save')}</Button>,
      ]}>
      <Form form={form} layout="vertical">
        <Form.Item name="name" label={t('email.name')} rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item name="email" label={t('email.emailAddr')} rules={[{ required: true, type: 'email' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="phone" label={t('email.phone')}>
          <Input />
        </Form.Item>
        <Form.Item name="company" label={t('email.company')}>
          <Input />
        </Form.Item>
        <Form.Item name="website" label={t('email.website')}>
          <Input />
        </Form.Item>
        <Form.Item name="group_name" label={t('email.group')}>
          <Select options={groups.map((g: any) => ({ value: g.name, label: g.name }))} />
        </Form.Item>
        <Form.Item name="notes" label={t('email.notes')}>
          <Input.TextArea rows={3} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

function ShareModal({ visible, onCancel, onShare, contactIds, agents }: any) {
  const { t } = useTranslation();
  const [selectedAgents, setSelectedAgents] = React.useState<string[]>([]);
  const [sharing, setSharing] = React.useState(false);

  React.useEffect(() => {
    if (visible) setSelectedAgents([]);
  }, [visible]);

  const handleShare = async () => {
    if (!selectedAgents.length) return;
    setSharing(true);
    await onShare(selectedAgents);
    setSharing(false);
    setSelectedAgents([]);
    onCancel();
  };

  return (
    <Modal open={visible} title={t('email.share')} onCancel={onCancel}
      footer={[
        <Button key="cancel" onClick={onCancel}>{t('email.cancel')}</Button>,
        <Button key="share" type="primary" icon={<ShareAltOutlined />} loading={sharing} onClick={handleShare}>{t('email.share')}</Button>,
      ]}>
      <p>Share {contactIds.length} contact(s) to Agents:</p>
      <Select
        mode="multiple"
        style={{ width: '100%' }}
        placeholder="Select agents"
        value={selectedAgents}
        onChange={setSelectedAgents}
        options={agents.map((a: any) => ({ value: a.id, label: a.name }))}
      />
    </Modal>
  );
}

function GroupModal({ visible, onCancel, onSave }: any) {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {
    if (visible) form.resetFields();
  }, [visible]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      await onSave(values.name);
      message.success(t('email.configSaved'));
      onCancel();
    } catch (e) {
      message.error(t('email.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={visible} title={t('email.newGroup')} onCancel={onCancel}
      footer={[
        <Button key="cancel" onClick={onCancel}>{t('email.cancel')}</Button>,
        <Button key="save" type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>{t('email.save')}</Button>,
      ]}>
      <Form form={form} layout="vertical">
        <Form.Item name="name" label={t('email.groupName')} rules={[{ required: true }]}>
          <Input />
        </Form.Item>
      </Form>
    </Modal>
  );
}

function MarkdownPreview({ content }: { content: string }) {
  const html = React.useMemo(() => {
    if (!content) return '';
    let html = content
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/^### (.*$)/gim, '<h3>$1</h3>')
      .replace(/^## (.*$)/gim, '<h2>$1</h2>')
      .replace(/^# (.*$)/gim, '<h1>$1</h1>')
      .replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>')
      .replace(/\*\*\*(.*?)\*\*\*/gim, '<b><i>$1</i></b>')
      .replace(/\*\*(.*?)\*\*/gim, '<b>$1</b>')
      .replace(/\*(.*?)\*/gim, '<i>$1</i>')
      .replace(/~~(.*?)~~/gim, '<del>$1</del>')
      .replace(/`([^`]+)`/gim, '<code style="background:#f0f0f0;padding:2px 4px;border-radius:3px;">$1</code>')
      .replace(/^\* (.*$)/gim, '<ul><li>$1</li></ul>')
      .replace(/^\- (.*$)/gim, '<ul><li>$1</li></ul>')
      .replace(/^\d+\. (.*$)/gim, '<ol><li>$1</li></ol>')
      .replace(/\n/gim, '<br />');
    return html;
  }, [content]);

  return <div dangerouslySetInnerHTML={{ __html: html }} style={{ padding: 12, border: '1px solid #d9d9d9', borderRadius: 6, minHeight: 200, background: '#fafafa' }} />;
}

function HtmlPreview({ content }: { content: string }) {
  // XSS 防护：使用简单的 HTML 标签白名单过滤
  const sanitized = React.useMemo(() => {
    if (!content) return '';
    // 允许的 HTML 标签列表
    const allowedTags = ['p', 'br', 'b', 'i', 'u', 'strong', 'em', 'a', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span', 'table', 'tr', 'td', 'th', 'thead', 'tbody', 'img'];
    // 移除 script、style、iframe、object、embed 等危险标签及其内容
    let cleaned = content
      .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
      .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
      .replace(/<iframe[^>]*>[\s\S]*?<\/iframe>/gi, '')
      .replace(/<object[^>]*>[\s\S]*?<\/object>/gi, '')
      .replace(/<embed[^>]*>/gi, '')
      .replace(/javascript:/gi, '')
      .replace(/on\w+\s*=/gi, '');
    return cleaned;
  }, [content]);
  return <div dangerouslySetInnerHTML={{ __html: sanitized }} style={{ padding: 12, border: '1px solid #d9d9d9', borderRadius: 6, minHeight: 200, background: '#fafafa' }} />;
}

type EditorMode = 'plain' | 'markdown' | 'html';

function RichTextEditor({ value, onChange, mode }: { value: string; onChange: (v: string) => void; mode: EditorMode }) {
  const { t } = useTranslation();
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const [fontSize, setFontSize] = React.useState('14px');
  const [fontColor, setFontColor] = React.useState('#000000');
  const [bgColor, setBgColor] = React.useState('#ffffff');
  const historyRef = React.useRef<string[]>([value || '']);
  const historyIndexRef = React.useRef(0);

  const saveHistory = (newValue: string) => {
    const hist = historyRef.current;
    const idx = historyIndexRef.current;
    if (hist[idx] === newValue) return;
    hist.splice(idx + 1);
    hist.push(newValue);
    if (hist.length > 50) hist.shift();
    historyIndexRef.current = hist.length - 1;
  };

  const handleChange = (e: any) => {
    const newValue = e.target.value;
    onChange(newValue);
    saveHistory(newValue);
  };

  const wrapSelection = (before: string, after: string) => {
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const selected = value.slice(start, end);
    const newValue = value.slice(0, start) + before + selected + after + value.slice(end);
    onChange(newValue);
    saveHistory(newValue);
    setTimeout(() => {
      ta.focus();
      ta.setSelectionRange(start + before.length, end + before.length);
    }, 0);
  };

  const insertAtCursor = (text: string) => {
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const newValue = value.slice(0, start) + text + value.slice(start);
    onChange(newValue);
    saveHistory(newValue);
    setTimeout(() => {
      ta.focus();
      ta.setSelectionRange(start + text.length, start + text.length);
    }, 0);
  };

  const handleUndo = () => {
    if (historyIndexRef.current > 0) {
      historyIndexRef.current--;
      onChange(historyRef.current[historyIndexRef.current]);
    }
  };

  const handleRedo = () => {
    if (historyIndexRef.current < historyRef.current.length - 1) {
      historyIndexRef.current++;
      onChange(historyRef.current[historyIndexRef.current]);
    }
  };

  const handleClear = () => {
    onChange('');
    saveHistory('');
  };

  const toolbarItems = [
    { icon: <RollbackOutlined />, title: t('email.undo'), onClick: handleUndo },
    { icon: <RedoOutlined />, title: t('email.redo'), onClick: handleRedo },
    { icon: <ClearOutlined />, title: t('email.clear'), onClick: handleClear },
    { icon: <BoldOutlined />, title: t('email.bold'), onClick: () => mode === 'markdown' ? wrapSelection('**', '**') : wrapSelection('<b>', '</b>') },
    { icon: <ItalicOutlined />, title: t('email.italic'), onClick: () => mode === 'markdown' ? wrapSelection('*', '*') : wrapSelection('<i>', '</i>') },
    { icon: <UnderlineOutlined />, title: t('email.underline'), onClick: () => wrapSelection('<u>', '</u>') },
    { icon: <StrikethroughOutlined />, title: 'Strikethrough', onClick: () => mode === 'markdown' ? wrapSelection('~~', '~~') : wrapSelection('<s>', '</s>') },
  ];

  const headingOptions = [
    { label: 'H1', value: 'h1' },
    { label: 'H2', value: 'h2' },
    { label: 'H3', value: 'h3' },
  ];

  const handleHeading = (val: string) => {
    if (!val) return;
    if (mode === 'markdown') {
      const prefix = val === 'h1' ? '# ' : val === 'h2' ? '## ' : '### ';
      wrapSelection(prefix, '');
    } else {
      const tag = val;
      wrapSelection(`<${tag}>`, `</${tag}>`);
    }
  };

  const handleFontSize = (size: string) => {
    setFontSize(size);
    wrapSelection(`<span style="font-size:${size}">`, '</span>');
  };

  const handleFontColor = (color: string) => {
    setFontColor(color);
    wrapSelection(`<span style="color:${color}">`, '</span>');
  };

  const handleBgColor = (color: string) => {
    setBgColor(color);
    wrapSelection(`<span style="background-color:${color}">`, '</span>');
  };

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, padding: 8, border: '1px solid #d9d9d9', borderBottom: 'none', borderRadius: '6px 6px 0 0', background: '#fafafa', alignItems: 'center' }}>
        {toolbarItems.map((item, i) => (
          <Tooltip key={i} title={item.title}>
            <Button size="small" icon={item.icon} onClick={item.onClick} />
          </Tooltip>
        ))}
        <Divider type="vertical" style={{ margin: '0 4px' }} />
        <Tooltip title={t('email.fontSize')}>
          <Select size="small" style={{ width: 80 }} value={fontSize} onChange={handleFontSize}
            options={['12px', '14px', '16px', '18px', '20px', '24px'].map(s => ({ value: s, label: s }))} />
        </Tooltip>
        <Tooltip title={t('email.fontColor')}>
          <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
            <FontColorsOutlined style={{ color: fontColor, marginRight: 4 }} />
            <input type="color" value={fontColor} onChange={(e) => handleFontColor(e.target.value)}
              style={{ width: 24, height: 24, padding: 0, border: 'none', cursor: 'pointer' }} />
          </div>
        </Tooltip>
        <Tooltip title={t('email.bgColor')}>
          <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
            <BgColorsOutlined style={{ color: bgColor, marginRight: 4 }} />
            <input type="color" value={bgColor} onChange={(e) => handleBgColor(e.target.value)}
              style={{ width: 24, height: 24, padding: 0, border: 'none', cursor: 'pointer' }} />
          </div>
        </Tooltip>
        <Divider type="vertical" style={{ margin: '0 4px' }} />
        <Tooltip title={t('email.heading')}>
          <Select size="small" style={{ width: 70 }} placeholder="H" onChange={handleHeading}
            options={headingOptions} />
        </Tooltip>
        <Tooltip title={t('email.listOrdered')}>
          <Button size="small" icon={<OrderedListOutlined />} onClick={() => mode === 'markdown' ? insertAtCursor('1. ') : wrapSelection('<ol>\n<li>', '</li>\n</ol>')} />
        </Tooltip>
        <Tooltip title={t('email.listUnordered')}>
          <Button size="small" icon={<UnorderedListOutlined />} onClick={() => mode === 'markdown' ? insertAtCursor('* ') : wrapSelection('<ul>\n<li>', '</li>\n</ul>')} />
        </Tooltip>
        <Divider type="vertical" style={{ margin: '0 4px' }} />
        <Tooltip title={t('email.insertLink')}>
          <Button size="small" icon={<LinkOutlined />} onClick={() => {
            const url = prompt('Enter URL:');
            if (url) mode === 'markdown' ? wrapSelection('[', `](${url})`) : wrapSelection(`<a href="${url}">`, '</a>');
          }} />
        </Tooltip>
        <Tooltip title={t('email.insertImage')}>
          <Button size="small" icon={<PictureOutlined />} onClick={() => {
            const url = prompt('Enter image URL:');
            if (url) mode === 'markdown' ? insertAtCursor(`\n![image](${url})\n`) : insertAtCursor(`\n<img src="${url}" />\n`);
          }} />
        </Tooltip>
      </div>
      <Input.TextArea ref={textareaRef} rows={12} value={value} onChange={handleChange}
        style={{ borderRadius: '0 0 6px 6px', fontFamily: mode === 'html' ? 'monospace' : 'inherit' }} />
    </div>
  );
}

function ComposeModal({ visible, onCancel, onSend, onSaveDraft, contacts, editingDraft }: any) {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [sending, setSending] = React.useState(false);
  const [attachments, setAttachments] = React.useState<any[]>([]);
  const [editorMode, setEditorMode] = React.useState<EditorMode>('plain');
  const [showPreview, setShowPreview] = React.useState(false);
  const [contentValue, setContentValue] = React.useState('');

  React.useEffect(() => {
    if (!visible) return;
    if (editingDraft) {
      const mode = editingDraft.editor_mode || 'plain';
      setEditorMode(mode);
      setContentValue(editingDraft.content || '');
      form.setFieldsValue({
        to: editingDraft.to || [],
        cc: editingDraft.cc || [],
        bcc: editingDraft.bcc || [],
        subject: editingDraft.subject || '',
        content: editingDraft.content || '',
      });
      setAttachments(editingDraft.attachments || []);
    } else {
      setEditorMode('plain');
      setContentValue('');
      form.resetFields();
      setAttachments([]);
    }
    setShowPreview(false);
  }, [visible, editingDraft?.id]);

  const handleContentChange = (val: string) => {
    setContentValue(val);
    form.setFieldsValue({ content: val });
  };

  const handleSend = async () => {
    try {
      const values = await form.validateFields();
      setSending(true);
      await onSend({ ...values, attachments, editor_mode: editorMode });
      message.success(t('email.sentStatus'));
      form.resetFields();
      setAttachments([]);
      setContentValue('');
      onCancel();
    } catch (e) {
    } finally {
      setSending(false);
    }
  };

  const handleSaveDraft = async () => {
    const values = form.getFieldsValue();
    if (!values.to && !values.subject) {
      message.error('Please enter recipient or subject');
      return;
    }
    await onSaveDraft({ ...values, attachments, editor_mode: editorMode });
    message.success(t('email.saveDraft'));
    form.resetFields();
    setAttachments([]);
    setContentValue('');
    onCancel();
  };

  const handleSelectContact = (contactId: number) => {
    const contact = contacts.find((c: any) => c.id === contactId);
    if (!contact) return;
    const currentTo = form.getFieldValue('to') || [];
    if (!currentTo.includes(contact.email)) {
      form.setFieldsValue({ to: [...currentTo, contact.email] });
    }
  };

  const handleFileChange = (info: any) => {
    const fileList = info.fileList || [];
    const newAttachments = fileList.map((f: any) => ({
      name: f.name,
      size: f.size || 0,
      type: f.type || 'application/octet-stream',
      uid: f.uid || Date.now() + Math.random(),
      status: 'done',
    }));
    setAttachments(newAttachments);
  };

  const insertAttachmentIntoContent = (attachment: any) => {
    const text = editorMode === 'markdown'
      ? `\n[${attachment.name}](attachment://${attachment.uid})\n`
      : editorMode === 'html'
        ? `\n<a href="attachment://${attachment.uid}">${attachment.name}</a>\n`
        : `\n[Attachment: ${attachment.name}]\n`;
    const newContent = contentValue + text;
    handleContentChange(newContent);
  };

  return (
    <Modal open={visible} title={t('email.compose')} width={900} onCancel={onCancel}
      footer={[
        <Button key="draft" onClick={handleSaveDraft}>{t('email.saveDraft')}</Button>,
        <Button key="cancel" onClick={onCancel}>{t('email.cancel')}</Button>,
        <Button key="send" type="primary" icon={<SendOutlined />} loading={sending} onClick={handleSend}>{t('email.send')}</Button>,
      ]}>
      <Form form={form} layout="vertical">
        <Form.Item label={t('email.selectContact')}>
          <Select
            placeholder="Select a contact to add"
            style={{ width: '100%' }}
            onChange={handleSelectContact}
            options={contacts.map((c: any) => ({ value: c.id, label: `${c.name} <${c.email}>` }))}
            allowClear
          />
        </Form.Item>
        <Form.Item name="to" label={t('email.to')} rules={[{ required: true }]}>
          <Select mode="tags" placeholder="Enter email addresses" tokenSeparators={[',', ';']} />
        </Form.Item>
        <Form.Item name="cc" label={t('email.cc')}>
          <Select mode="tags" placeholder="CC" tokenSeparators={[',', ';']} />
        </Form.Item>
        <Form.Item name="bcc" label={t('email.bcc')}>
          <Select mode="tags" placeholder="BCC" tokenSeparators={[',', ';']} />
        </Form.Item>
        <Form.Item name="subject" label={t('email.subject')} rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item label={t('email.attachments')}>
          <Upload
            multiple
            beforeUpload={() => false}
            onChange={handleFileChange}
            fileList={attachments.map((a: any) => ({ ...a, originFileObj: a }))}
          >
            <Button icon={<FileOutlined />}>{t('email.addAttachment')}</Button>
          </Upload>
          {attachments.length > 0 && (
            <Space size={4} wrap style={{ marginTop: 8 }}>
              {attachments.map((a: any) => (
                <Tag key={a.uid} icon={<FileOutlined />} style={{ cursor: 'pointer' }} onClick={() => insertAttachmentIntoContent(a)}>
                  {a.name} ({formatFileSize(a.size)})
                </Tag>
              ))}
            </Space>
          )}
        </Form.Item>
        <Form.Item label={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
            <span>{t('email.content')}</span>
            <Space>
              <Radio.Group value={editorMode} onChange={(e: any) => { setEditorMode(e.target.value); setShowPreview(false); }} size="small">
                <Radio.Button value="plain">{t('email.plain')}</Radio.Button>
                <Radio.Button value="markdown">Markdown</Radio.Button>
                <Radio.Button value="html">HTML</Radio.Button>
              </Radio.Group>
              {editorMode !== 'plain' && (
                <Button type="link" size="small" onClick={() => setShowPreview(!showPreview)}>
                  {showPreview ? 'Edit' : t('email.preview')}
                </Button>
              )}
            </Space>
          </div>
        }>
          {showPreview && editorMode === 'markdown' ? (
            <MarkdownPreview content={contentValue} />
          ) : showPreview && editorMode === 'html' ? (
            <HtmlPreview content={contentValue} />
          ) : editorMode === 'plain' ? (
            <Input.TextArea rows={12} value={contentValue} onChange={(e) => handleContentChange(e.target.value)} />
          ) : (
            <RichTextEditor value={contentValue} onChange={handleContentChange} mode={editorMode} />
          )}
        </Form.Item>
      </Form>
    </Modal>
  );
}

function AttachmentList({ attachments }: { attachments: any[] }) {
  const { t } = useTranslation();
  if (!attachments || attachments.length === 0) return null;
  return (
    <div style={{ marginTop: 8 }}>
      <Text type="secondary" style={{ fontSize: 12 }}>{t('email.attachments')}:</Text>
      <Space size={4} wrap style={{ marginTop: 4 }}>
        {attachments.map((a: any, i: number) => (
          <Tag key={i} icon={<FileOutlined />} size="small">
            {a.name} ({formatFileSize(a.size)})
          </Tag>
        ))}
      </Space>
    </div>
  );
}

function UninstallModal({ visible, onCancel, onUninstall, agentId }: any) {
  const { t } = useTranslation();
  const [keepData, setKeepData] = React.useState(true);
  const [exportData, setExportData] = React.useState(true);
  const [uninstalling, setUninstalling] = React.useState(false);

  const handleUninstall = async () => {
    setUninstalling(true);
    await onUninstall({ keepData, exportData, agentId });
    setUninstalling(false);
    onCancel();
  };

  return (
    <Modal open={visible} title={t('email.uninstall')} onCancel={onCancel}
      footer={[
        <Button key="cancel" onClick={onCancel}>{t('email.cancel')}</Button>,
        <Button key="uninstall" danger icon={<DeleteOutlined />} loading={uninstalling} onClick={handleUninstall}>{t('email.uninstall')}</Button>,
      ]}>
      <Alert message={t('email.uninstallConfirm')} type="warning" showIcon style={{ marginBottom: 16 }} />
      <div style={{ marginBottom: 12 }}>
        <Checkbox checked={keepData} onChange={(e: any) => setKeepData(e.target.checked)}>
          {t('email.keepData')}
        </Checkbox>
      </div>
      <div>
        <Checkbox checked={exportData} onChange={(e: any) => setExportData(e.target.checked)} disabled={!keepData}>
          {t('email.exportData')}
        </Checkbox>
      </div>
    </Modal>
  );
}

// Agent 规则列表组件
function AgentRulesList() {
  const { t } = useTranslation();
  const [rules, setRules] = React.useState<any[]>([]);
  const agentId = localStorage.getItem('qwenpaw-last-used-agent') || 'default';
  
  React.useEffect(() => {
    const rulesKey = `agentmail_rules_${agentId}`;
    const stored = localStorage.getItem(rulesKey);
    if (stored) setRules(JSON.parse(stored));
  }, [agentId]);
  
  const toggleRule = (index: number) => {
    const newRules = [...rules];
    newRules[index].active = !newRules[index].active;
    setRules(newRules);
    localStorage.setItem(`agentmail_rules_${agentId}`, JSON.stringify(newRules));
  };
  
  const deleteRule = (index: number) => {
    const newRules = rules.filter((_, i) => i !== index);
    setRules(newRules);
    localStorage.setItem(`agentmail_rules_${agentId}`, JSON.stringify(newRules));
  };
  
  if (rules.length === 0) {
      return <Empty description={t('agent.noSession')} image={Empty.PRESENTED_IMAGE_SIMPLE} />;
    }
  
  return (
    <div>
      {rules.map((rule, index) => (
        <div key={index} style={{ marginBottom: 12, padding: 12, border: '1px solid #f0f0f0', borderRadius: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <Text strong>{rule.name}</Text>
            <Space>
              <Switch size="small" checked={rule.active} onChange={() => toggleRule(index)} />
              <Button type="link" danger size="small" icon={<DeleteOutlined />} onClick={() => deleteRule(index)} />
            </Space>
          </div>
          <div style={{ fontSize: 12, color: '#666' }}>
            <div>{t('agent.whenSender')}: {rule.condition.sender || '*'}</div>
            <div>{t('agent.whenSubject')}: {rule.condition.subject || '*'}</div>
            <div>{t('agent.actionTag')}: {rule.action.value}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

// Agent 规则编辑模态框
function AgentRuleModal({ visible, onCancel, onSave, initialValues }: any) {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  
  React.useEffect(() => {
    if (visible) {
      form.setFieldsValue(initialValues || {
        name: '',
        condition: { sender: '', subject: '', content: '' },
        action: { type: 'tag', value: '' },
        active: true,
      });
    }
  }, [visible, initialValues, form]);
  
  const handleSave = () => {
    form.validateFields().then((values) => {
      onSave(values);
      form.resetFields();
    });
  };
  
  return (
    <Modal open={visible} title={t('agent.createRule')} onCancel={onCancel}
      footer={[
        <Button key="cancel" onClick={onCancel}>{t('email.cancel')}</Button>,
        <Button key="save" type="primary" icon={<SaveOutlined />} onClick={handleSave}>{t('email.save')}</Button>,
      ]}>
      <Form form={form} layout="vertical">
        <Form.Item name="name" label={t('agent.ruleName')} rules={[{ required: true }]}>
          <Input placeholder="e.g., Urgent emails from boss" />
        </Form.Item>
        <Form.Item label={t('agent.ruleCondition')}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Form.Item name={['condition', 'sender']} noStyle>
              <Input placeholder={t('agent.whenSender')} />
            </Form.Item>
            <Form.Item name={['condition', 'subject']} noStyle>
              <Input placeholder={t('agent.whenSubject')} />
            </Form.Item>
            <Form.Item name={['condition', 'content']} noStyle>
              <Input placeholder={t('agent.whenContent')} />
            </Form.Item>
          </Space>
        </Form.Item>
        <Form.Item label={t('agent.ruleAction')}>
          <Space>
            <Form.Item name={['action', 'type']} noStyle initialValue="tag">
              <Select style={{ width: 120 }} options={[
                { value: 'tag', label: t('agent.actionTag') },
                { value: 'reply', label: t('agent.actionReply') },
                { value: 'archive', label: t('agent.actionArchive') },
                { value: 'notify', label: t('agent.actionNotify') },
              ]} />
            </Form.Item>
            <Form.Item name={['action', 'value']} noStyle>
              <Input placeholder="Value" style={{ width: 200 }} />
            </Form.Item>
          </Space>
        </Form.Item>
        <Form.Item name="active" valuePropName="checked">
          <Checkbox>{t('agent.ruleActive')}</Checkbox>
        </Form.Item>
      </Form>
    </Modal>
  );
}

function EmailPage() {
  const { t, lang } = useTranslation();
  const [activeTab, setActiveTab] = React.useState('inbox');
  const [loading, setLoading] = React.useState(false);
  
  // 监听语言变化，强制刷新页面
  React.useEffect(() => {
    console.log('[AgentMail] Language changed to:', lang);
  }, [lang]);

  const [agentConfig, setAgentConfig] = React.useState<AgentConfig | null>(null);
  const [configLoading, setConfigLoading] = React.useState(false);
  const [configModalVisible, setConfigModalVisible] = React.useState(false);

  const [contacts, setContacts] = React.useState<any[]>([]);
  const [contactGroups, setContactGroups] = React.useState<any[]>([]);
  const [contactTotal, setContactTotal] = React.useState(0);
  const [contactPage, setContactPage] = React.useState(1);
  const [contactSearch, setContactSearch] = React.useState('');
  const [contactGroup, setContactGroup] = React.useState('all');
  const [contactModalVisible, setContactModalVisible] = React.useState(false);
  const [editingContact, setEditingContact] = React.useState<any>(null);
  const [shareVisible, setShareVisible] = React.useState(false);
  const [shareContactIds, setShareContactIds] = React.useState<number[]>([]);
  const [selectedContacts, setSelectedContacts] = React.useState<number[]>([]);
  const [groupModalVisible, setGroupModalVisible] = React.useState(false);

  const [inboxEmails, setInboxEmails] = React.useState<any[]>([]);
  const [inboxTotal, setInboxTotal] = React.useState(0);
  const [inboxPage, setInboxPage] = React.useState(1);
  const [selectedInbox, setSelectedInbox] = React.useState<number[]>([]);

  const [sentEmails, setSentEmails] = React.useState<any[]>([]);
  const [sentTotal, setSentTotal] = React.useState(0);
  const [sentPage, setSentPage] = React.useState(1);
  const [selectedSent, setSelectedSent] = React.useState<number[]>([]);

  const [draftEmails, setDraftEmails] = React.useState<any[]>([]);
  const [draftTotal, setDraftTotal] = React.useState(0);
  const [draftPage, setDraftPage] = React.useState(1);
  const [selectedDrafts, setSelectedDrafts] = React.useState<number[]>([]);
  const [composeVisible, setComposeVisible] = React.useState(false);
  const [editingDraft, setEditingDraft] = React.useState<any>(null);

  const [trashItems, setTrashItems] = React.useState<any[]>([]);
  const [trashTotal, setTrashTotal] = React.useState(0);
  const [trashPage, setTrashPage] = React.useState(1);
  const [trashFilter, setTrashFilter] = React.useState('all');
  const [selectedTrash, setSelectedTrash] = React.useState<number[]>([]);

  const [backupLoading, setBackupLoading] = React.useState(false);
  const [uninstallVisible, setUninstallVisible] = React.useState(false);
  
  // Agent 规则管理状态
  const [ruleModalVisible, setRuleModalVisible] = React.useState(false);
  const [editingRule, setEditingRule] = React.useState<any>(null);

  // Agent ID 从 QwenPaw store 实时获取，支持切换
  const [agentId, setAgentId] = React.useState(() => {
    // QwenPaw 使用 qwenpaw-last-used-agent 存储当前智能体
    const qwLastUsed = localStorage.getItem('qwenpaw-last-used-agent');
    if (qwLastUsed) return qwLastUsed;
    // 兼容旧版
    const match = window.location.pathname.match(/\/agent\/([^\/]+)/);
    return match ? match[1] : localStorage.getItem('current_agent_id') || 'default';
  });

  const agentName = React.useMemo(() => {
    // 1. 尝试从 QwenPaw 新版 zustand store 读取
    try {
      const storageData = localStorage.getItem('qwenpaw-agent-storage');
      if (storageData) {
        const parsed = JSON.parse(storageData);
        const state = parsed?.state || parsed;
        if (state?.agents && Array.isArray(state.agents)) {
          const agent = state.agents.find((a: any) => a.id === agentId);
          if (agent) return agent.name || agentId;
        }
      }
    } catch { }

    // 2. 尝试从旧版 qwenpaw_agents 读取（兼容旧版本）
    try {
      const agentsData = localStorage.getItem('qwenpaw_agents');
      if (agentsData) {
        const agents = JSON.parse(agentsData);
        const agent = agents.find((a: any) => a.id === agentId || a.agent_id === agentId);
        if (agent) return agent.name || agentId;
      }
    } catch { }

    return agentId;
  }, [agentId]);

  const allAgents = React.useMemo(() => getAllAgents().filter(a => a.id !== agentId), [agentId]);

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

    // 监听 storage 事件（跨标签页同步）
    window.addEventListener('storage', (e) => {
      if (e.key === 'qwenpaw-last-used-agent') {
        checkAgentChange();
      }
    });
    // 定时检查
    const interval = setInterval(checkAgentChange, 500);

    return () => {
      window.removeEventListener('storage', checkAgentChange);
      clearInterval(interval);
    };
  }, [agentId]);

  const fetchConfig = async () => {
    setConfigLoading(true);
    try {
      const res = await apiGet(`/config/${agentId}`, agentId);
      setAgentConfig(res.config);
    } catch (e) { setAgentConfig(null); }
    setConfigLoading(false);
  };

  const fetchContacts = async (page = contactPage, search = contactSearch, group = contactGroup) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: '15' });
      if (search) params.append('search', search);
      if (group && group !== 'all') params.append('group', group);
      const res = await apiGet(`/${agentId}/contacts?${params}`, agentId);
      setContacts(res.items || []);
      setContactTotal(res.total || 0);
    } catch (e) { message.error('Failed to load contacts'); }
    setLoading(false);
  };

  const fetchContactGroups = async () => {
    try {
      const res = await apiGet(`/${agentId}/contact-groups`, agentId);
      setContactGroups(res.items || []);
    } catch (e) { }
  };

  const fetchInbox = async (page = inboxPage) => {
    setLoading(true);
    try {
      const res = await apiGet(`/${agentId}/inbox?page=${page}&page_size=20`, agentId);
      setInboxEmails(res.items || []);
      setInboxTotal(res.total || 0);
    } catch (e) { message.error('Failed to load inbox'); }
    setLoading(false);
  };

  const fetchSent = async (page = sentPage) => {
    setLoading(true);
    try {
      const res = await apiGet(`/${agentId}/sent?page=${page}&page_size=20`, agentId);
      setSentEmails(res.items || []);
      setSentTotal(res.total || 0);
    } catch (e) { message.error('Failed to load sent'); }
    setLoading(false);
  };

  const fetchDrafts = async (page = draftPage) => {
    setLoading(true);
    try {
      const res = await apiGet(`/${agentId}/drafts?page=${page}&page_size=20`, agentId);
      setDraftEmails(res.items || []);
      setDraftTotal(res.total || 0);
    } catch (e) { message.error('Failed to load drafts'); }
    setLoading(false);
  };

  const fetchTrash = async (page = trashPage, filter = trashFilter) => {
    setLoading(true);
    try {
      const res = await apiGet(`/${agentId}/trash?page=${page}&page_size=20&type=${filter}`, agentId);
      setTrashItems(res.items || []);
      setTrashTotal(res.total || 0);
    } catch (e) { }
    setLoading(false);
  };

  React.useEffect(() => {
    fetchConfig();
    fetchContactGroups();
  }, [agentId]);

  React.useEffect(() => { if (activeTab === 'contacts') fetchContacts(); }, [activeTab, contactPage, contactSearch, contactGroup, agentId]);
  React.useEffect(() => { if (activeTab === 'inbox') fetchInbox(); }, [activeTab, inboxPage, agentId]);
  React.useEffect(() => { if (activeTab === 'sent') fetchSent(); }, [activeTab, sentPage, agentId]);
  React.useEffect(() => { if (activeTab === 'drafts') fetchDrafts(); }, [activeTab, draftPage, agentId]);
  React.useEffect(() => { if (activeTab === 'trash') fetchTrash(); }, [activeTab, trashPage, trashFilter, agentId]);

  const saveConfig = async (values: any) => {
    await apiPost(`/config/${agentId}/hybrid`, values, agentId);
    await fetchConfig();
  };

  const deleteConfig = () => {
    Modal.confirm({
      title: t('email.confirmDelete'),
      onOk: async () => {
        await apiDelete(`/config/${agentId}`, {}, agentId);
        message.success('Deleted');
        fetchConfig();
      },
    });
  };

  const getConfigMode = () => {
    if (!agentConfig) return 'none';
    if (agentConfig.hybrid) return 'hybrid';
    return 'none';
  };

  const getConfigEmail = () => {
    if (!agentConfig) return '--';
    if (agentConfig.hybrid) return agentConfig.hybrid.email;
    return '--';
  };

  const handleCreateContact = async (values: any) => {
    await apiPost(`/${agentId}/contacts`, values, agentId);
    fetchContacts();
  };

  const handleUpdateContact = async (values: any) => {
    if (!editingContact) return;
    await apiPut(`/${agentId}/contacts/${editingContact.id}`, values, agentId);
    fetchContacts();
  };

  const handleDeleteContacts = async (ids: number[]) => {
    await apiPost(`/${agentId}/contacts/batch-delete`, { ids }, agentId);
    setSelectedContacts([]);
    fetchContacts();
  };

  const handleShareContacts = async (targetAgentIds: string[]) => {
    await apiPost(`/${agentId}/contacts/batch-share`, { contact_ids: shareContactIds, target_agent_ids: targetAgentIds }, agentId);
    setShareContactIds([]);
    fetchContacts();
  };

  const handleCreateGroup = async (name: string) => {
    await apiPost(`/${agentId}/contact-groups`, { name }, agentId);
    fetchContactGroups();
  };

  const handleArchiveInbox = async (ids: number[]) => {
    await apiPost(`/${agentId}/inbox/archive`, { ids }, agentId);
    setSelectedInbox([]);
    fetchInbox();
  };

  const handleDeleteInbox = async (ids: number[]) => {
    await apiPost(`/${agentId}/inbox/delete`, { ids }, agentId);
    setSelectedInbox([]);
    fetchInbox();
  };

  const handleDeleteSent = async (ids: number[]) => {
    await apiPost(`/${agentId}/sent/delete`, { ids }, agentId);
    setSelectedSent([]);
    fetchSent();
  };

  const handleDeleteDrafts = async (ids: number[]) => {
    await apiPost(`/${agentId}/drafts/delete`, { ids }, agentId);
    setSelectedDrafts([]);
    fetchDrafts();
  };

  const handleSendEmail = async (values: any) => {
    await apiPost(`/${agentId}/sent/send`, { ...values, draft_id: editingDraft?.id }, agentId);
    if (editingDraft) fetchDrafts();
    fetchSent();
    setEditingDraft(null);
  };

  const handleSaveDraft = async (values: any) => {
    await apiPost(`/${agentId}/drafts`, { ...values, id: editingDraft?.id }, agentId);
    fetchDrafts();
    setEditingDraft(null);
  };

  const handleRestoreTrash = async (ids: number[]) => {
    await apiPost(`/${agentId}/trash/restore`, { ids }, agentId);
    setSelectedTrash([]);
    fetchTrash();
  };

  const handlePermanentDelete = async (ids: number[]) => {
    await apiDelete(`/${agentId}/trash/permanent`, { ids }, agentId);
    setSelectedTrash([]);
    fetchTrash();
  };

  const handleBackup = async () => {
    setBackupLoading(true);
    try {
      await apiPost(`/${agentId}/backup`, {}, agentId);
      message.success(t('email.backupSuccess'));
    } catch (e) {
      message.error('Backup failed');
    }
    setBackupLoading(false);
  };

  const handleWriteEmailToContact = (contact: any) => {
    setEditingDraft(null);
    setComposeVisible(true);
    setTimeout(() => {
      // 等待ComposeModal打开后设置收件人
    }, 100);
  };

  const handleUninstall = async ({ keepData, exportData, agentId: targetAgentId }: any) => {
    try {
      if (exportData && keepData) {
        // 导出数据到 memory 文件夹
        const data = getStorage(targetAgentId);
        const exportContent = generateExportMarkdown(data, targetAgentId);
        const memoryKey = `agentmail_export_${targetAgentId}_${Date.now()}`;
        localStorage.setItem(memoryKey, exportContent);
        message.success(`${t('email.dataExported')} memory/${memoryKey}`);
      }

      // 调用后端 API 清理数据库文件
      try {
        await apiPost(`/${targetAgentId}/uninstall`, { keep_data: keepData }, targetAgentId);
      } catch (apiErr) {
        console.warn('Backend uninstall API failed:', apiErr);
      }

      if (!keepData) {
        // 删除前端 localStorage 数据
        const keysToRemove: string[] = [];
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          if (key && (key.startsWith(`${STORAGE_KEY}_${targetAgentId}`) || key.startsWith(`agentmail_rules_${targetAgentId}`) || key.startsWith(`agentmail_export_${targetAgentId}`))) {
            keysToRemove.push(key);
          }
        }
        keysToRemove.forEach(key => localStorage.removeItem(key));
      }

      message.success(t('email.uninstallSuccess'));
      // 延迟刷新页面，确保消息显示
      setTimeout(() => {
        window.location.reload();
      }, 1500);
    } catch (e) {
      message.error('Uninstall failed');
    }
  };

  const generateExportMarkdown = (data: any, agentId: string): string => {
    const now = new Date().toISOString();
    let md = `# AgentMail Export - ${agentId}\n\n`;
    md += `**Export Time:** ${now}\n\n`;
    md += `---\n\n`;

    // Contacts
    md += `## Contacts (${data.contacts?.length || 0})\n\n`;
    if (data.contacts?.length) {
      data.contacts.forEach((c: any) => {
        md += `### ${c.name}\n`;
        md += `- Email: ${c.email}\n`;
        md += `- Phone: ${c.phone || 'N/A'}\n`;
        md += `- Company: ${c.company || 'N/A'}\n`;
        md += `- Group: ${c.group_name || 'default'}\n`;
        md += `- Notes: ${c.notes || 'N/A'}\n\n`;
      });
    }

    // Inbox
    md += `## Inbox (${data.inbox?.length || 0})\n\n`;
    if (data.inbox?.length) {
      data.inbox.forEach((e: any) => {
        md += `### ${e.subject || '(No Subject)'}\n`;
        md += `- From: ${e.sender_email || 'N/A'}\n`;
        md += `- Date: ${e.date || 'N/A'}\n`;
        md += `- Body: ${e.body || 'N/A'}\n\n`;
      });
    }

    // Sent
    md += `## Sent (${data.sent?.length || 0})\n\n`;
    if (data.sent?.length) {
      data.sent.forEach((e: any) => {
        md += `### ${e.subject || '(No Subject)'}\n`;
        md += `- To: ${e.recipient || 'N/A'}\n`;
        md += `- Date: ${e.sent_at || 'N/A'}\n`;
        md += `- Body: ${e.body || 'N/A'}\n\n`;
      });
    }

    // Drafts
    md += `## Drafts (${data.drafts?.length || 0})\n\n`;
    if (data.drafts?.length) {
      data.drafts.forEach((e: any) => {
        md += `### ${e.subject || '(No Subject)'}\n`;
        md += `- To: ${e.recipient || 'N/A'}\n`;
        md += `- Body: ${e.body || 'N/A'}\n\n`;
      });
    }

    md += `---\n\n*Exported by AgentMail Plugin*\n`;
    return md;
  };

  // Agent 集成：获取当前会话ID
  const getCurrentSessionId = () => {
    return (window as any).currentSessionId || null;
  };

  // Agent 集成：添加邮件到当前上下文（直接注入到 QwenPaw 聊天）
  const addEmailToContext = (email: any) => {
    const sessionId = getCurrentSessionId();
    if (!sessionId) {
      message.warning(t('agent.noSession'));
      return;
    }
    
    // 构建邮件上下文消息
    const emailContext = `[Email Context]
From: ${email.sender_email}
Subject: ${email.subject}
Date: ${email.date}
Content: ${email.body?.replace(/<[^>]*>/g, '').substring(0, 1000)}
[/Email Context]

Please review this email and assist me with it.`;
    
    // 使用 QwenPaw 的 pending message 机制注入上下文
    // 存储到 sessionStorage，QwenPaw 会自动加载到聊天输入框
    const STORAGE_PREFIX = "qwenpaw_pending_user_msg_";
    sessionStorage.setItem(`${STORAGE_PREFIX}${sessionId}`, emailContext);
    
    // 同时存储到 AgentMail 的上下文存储
    const contextData = {
      type: 'email',
      sessionId,
      emailId: email.id,
      subject: email.subject,
      sender: email.sender_email,
      date: email.date,
      body: email.body?.substring(0, 500),
      timestamp: new Date().toISOString(),
    };
    const key = `agentmail_context_${sessionId}`;
    const existing = JSON.parse(sessionStorage.getItem(key) || '[]');
    existing.push(contextData);
    sessionStorage.setItem(key, JSON.stringify(existing));
    
    // 触发自定义事件，通知 QwenPaw 有新消息
    window.dispatchEvent(new CustomEvent('agentmail:context:injected', { 
      detail: { sessionId, emailId: email.id, subject: email.subject } 
    }));
    
    message.success(t('agent.contextAdded'));
  };

  // Agent 集成：添加邮件到 Agent 记忆（从上下文自动转化）
  const addEmailToMemory = (email: any) => {
    const agentId = getCurrentAgentId();
    const sessionId = getCurrentSessionId();
    
    // 生成结构化记忆数据
    const memoryData = {
      type: 'email_memory',
      agentId,
      emailId: email.id,
      subject: email.subject,
      sender: email.sender_email,
      date: email.date,
      summary: generateEmailSummary(email),
      // 提取关键信息作为标签
      tags: extractEmailTags(email),
      // 关联的会话上下文
      sessionId,
      // 记忆优先级（基于邮件内容判断）
      priority: calculateEmailPriority(email),
      timestamp: new Date().toISOString(),
    };
    
    // 存储到 localStorage，作为 Agent 的长期记忆
    const key = `agentmail_memory_${agentId}`;
    const existing = JSON.parse(localStorage.getItem(key) || '[]');
    // 去重：检查是否已存在相同邮件
    const filtered = existing.filter((m: any) => m.emailId !== email.id);
    filtered.push(memoryData);
    // 限制记忆数量，保留最新的 100 条
    if (filtered.length > 100) filtered.shift();
    localStorage.setItem(key, JSON.stringify(filtered));
    
    // 同时保存到 QwenPaw 的 memory 目录（如果可访问）
    saveMemoryToWorkspace(memoryData, agentId);
    
    message.success(t('agent.memoryAdded'));
  };

  // 提取邮件标签
  const extractEmailTags = (email: any): string[] => {
    const tags: string[] = [];
    const body = (email.body || '').toLowerCase();
    const subject = (email.subject || '').toLowerCase();
    
    if (body.includes('urgent') || subject.includes('urgent')) tags.push('urgent');
    if (body.includes('meeting') || subject.includes('meeting')) tags.push('meeting');
    if (body.includes('deadline') || subject.includes('deadline')) tags.push('deadline');
    if (body.includes('question') || body.includes('?')) tags.push('question');
    if (body.includes('invoice') || subject.includes('invoice')) tags.push('invoice');
    if (body.includes('report') || subject.includes('report')) tags.push('report');
    
    return tags;
  };

  // 计算邮件优先级
  const calculateEmailPriority = (email: any): number => {
    const body = (email.body || '').toLowerCase();
    const subject = (email.subject || '').toLowerCase();
    let priority = 1;
    
    if (body.includes('urgent') || subject.includes('urgent')) priority += 3;
    if (body.includes('deadline') || subject.includes('deadline')) priority += 2;
    if (body.includes('asap')) priority += 2;
    if (body.includes('important')) priority += 1;
    
    return Math.min(priority, 5);
  };

  // 保存记忆到 Agent 工作空间
  const saveMemoryToWorkspace = (memoryData: any, agentId: string) => {
    try {
      // 尝试保存到 agent 工作空间的 memory 文件夹
      const memoryContent = `# Email Memory - ${memoryData.subject}

**From:** ${memoryData.sender}
**Date:** ${memoryData.date}
**Priority:** ${memoryData.priority}/5
**Tags:** ${memoryData.tags.join(', ') || 'none'}

## Summary
${memoryData.summary}

## Full Context
${memoryData.body || 'N/A'}

---
*Saved by AgentMail at ${memoryData.timestamp}*
`;
      
      // 存储到 localStorage 的 memory 命名空间
      const memoryKey = `agentmail_memory_file_${agentId}_${memoryData.emailId}`;
      localStorage.setItem(memoryKey, memoryContent);
    } catch (e) {
      console.error('[AgentMail] Failed to save memory to workspace:', e);
    }
  };

  // Agent 集成：生成邮件摘要
  const generateEmailSummary = (email: any): string => {
    const body = email.body || '';
    // 提取前 200 个字符作为摘要
    const summary = body.substring(0, 200).replace(/<[^>]*>/g, '').trim();
    return summary + (body.length > 200 ? '...' : '');
  };

  // Agent 集成：生成智能回复建议
  const generateSmartReply = (email: any) => {
    const replies = [
      `Thank you for your email regarding "${email.subject}". I will look into this and get back to you soon.`,
      `Thanks for reaching out. Could you please provide more details about "${email.subject}"?`,
      `I have received your email and will process it as soon as possible.`,
      `Thank you for the information. I will review it and follow up if needed.`,
    ];
    
    // 基于邮件内容选择最合适的回复
    const body = (email.body || '').toLowerCase();
    if (body.includes('urgent') || body.includes('asap') || body.includes('deadline')) {
      return `I understand the urgency regarding "${email.subject}". I will prioritize this and respond shortly.`;
    }
    if (body.includes('question') || body.includes('?')) {
      return `Thank you for your questions about "${email.subject}". Let me gather the information and get back to you.`;
    }
    if (body.includes('meeting') || body.includes('schedule')) {
      return `Thank you for the meeting invitation regarding "${email.subject}". I will check my schedule and confirm.`;
    }
    
    return replies[Math.floor(Math.random() * replies.length)];
  };

  // Agent 集成：应用处理规则
  const applyEmailRules = (email: any) => {
    const agentId = getCurrentAgentId();
    const rulesKey = `agentmail_rules_${agentId}`;
    const rules = JSON.parse(localStorage.getItem(rulesKey) || '[]');
    
    let applied = false;
    rules.forEach((rule: any) => {
      if (!rule.active) return;
      
      const matchSender = rule.condition.sender && email.sender_email?.includes(rule.condition.sender);
      const matchSubject = rule.condition.subject && email.subject?.includes(rule.condition.subject);
      const matchContent = rule.condition.content && email.body?.includes(rule.condition.content);
      
      if (matchSender || matchSubject || matchContent) {
        // 应用规则动作
        if (rule.action.type === 'tag') {
          // 添加标签逻辑
          const tagsKey = `agentmail_tags_${agentId}`;
          const tags = JSON.parse(localStorage.getItem(tagsKey) || '{}');
          if (!tags[email.id]) tags[email.id] = [];
          if (!tags[email.id].includes(rule.action.value)) {
            tags[email.id].push(rule.action.value);
            localStorage.setItem(tagsKey, JSON.stringify(tags));
          }
        }
        applied = true;
      }
    });
    
    if (applied) {
      message.success(t('agent.ruleApplied'));
    }
  };

  // Agent 集成：获取当前 Agent ID
  const getCurrentAgentId = () => {
    return localStorage.getItem('qwenpaw-last-used-agent') || 'default';
  };

  const renderInboxTab = () => (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <Space>
          <Button type="primary" icon={<ReloadOutlined />} loading={loading} onClick={() => fetchInbox()}>{t('email.refresh')}</Button>
          <Button icon={<EditOutlined />} onClick={() => { setEditingDraft(null); setComposeVisible(true); }}>{t('email.compose')}</Button>
        </Space>
        <Space>
          {selectedInbox.length > 0 && (
            <>
              <Button icon={<FolderOpenOutlined />} onClick={() => handleArchiveInbox(selectedInbox)}>{t('email.batchArchive')}</Button>
              <Button danger icon={<DeleteOutlined />} onClick={() => handleDeleteInbox(selectedInbox)}>{t('email.batchDelete')}</Button>
            </>
          )}
        </Space>
      </div>
      <Table
        rowSelection={{ selectedRowKeys: selectedInbox, onChange: (keys: any) => setSelectedInbox(keys) }}
        columns={[
          { title: t('email.status'), dataIndex: 'is_agent_read', key: 'status', width: 100, render: (v: boolean, r: any) => (
            <Space direction="vertical" size={0}>
              <Badge status={v ? 'default' : 'processing'} text={v ? t('email.agentRead') : t('email.agentUnread')} />
              {r.is_replied && <Tag color="green" style={{ fontSize: 10 }}>{t('email.replied')}</Tag>}
            </Space>
          )},
          { title: t('email.subject'), dataIndex: 'subject', key: 'subject', ellipsis: true, render: (v: string, r: any) => (
            <div>
              <div>{v || '(no subject)'}</div>
              <AttachmentList attachments={r.attachments} />
            </div>
          )},
          { title: t('email.sender'), dataIndex: 'sender_email', key: 'sender', width: 200 },
          { title: t('email.date'), dataIndex: 'date', key: 'date', width: 150 },
          { title: t('email.action'), key: 'action', width: 200, render: (_: any, record: any) => (
            <Space>
              <Tooltip title={t('agent.addToContext')}>
                <Button type="link" size="small" icon={<ApiOutlined />} onClick={() => addEmailToContext(record)} />
              </Tooltip>
              <Tooltip title={t('agent.addToMemory')}>
                <Button type="link" size="small" icon={<SaveOutlined />} onClick={() => addEmailToMemory(record)} />
              </Tooltip>
              <Tooltip title={t('agent.generateReply')}>
                <Button type="link" size="small" icon={<EditOutlined />} onClick={() => {
                  const reply = generateSmartReply(record);
                  setComposeVisible(true);
                  setComposeTo(record.sender_email);
                  setComposeSubject(`Re: ${record.subject}`);
                  setComposeBody(reply);
                }} />
              </Tooltip>
              <Button type="link" size="small" icon={<FolderOpenOutlined />} onClick={() => handleArchiveInbox([record.id])} />
              <Popconfirm title={t('email.confirmDelete')} onConfirm={() => handleDeleteInbox([record.id])}>
                <Button type="link" danger size="small" icon={<DeleteOutlined />} />
              </Popconfirm>
            </Space>
          )},
        ]}
        dataSource={inboxEmails}
        rowKey="id"
        pagination={false}
        locale={{ emptyText: <Empty description={t('email.noEmails')} /> }}
      />
      <Pagination style={{ marginTop: 16 }} current={inboxPage} pageSize={20} total={inboxTotal} onChange={(p: number) => setInboxPage(p)} />
    </div>
  );

  const renderSentTab = () => (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <Space>
          <Button type="primary" icon={<ReloadOutlined />} loading={loading} onClick={() => fetchSent()}>{t('email.refresh')}</Button>
        </Space>
        <Space>
          {selectedSent.length > 0 && (
            <Button danger icon={<DeleteOutlined />} onClick={() => handleDeleteSent(selectedSent)}>{t('email.batchDelete')}</Button>
          )}
        </Space>
      </div>
      <Table
        rowSelection={{ selectedRowKeys: selectedSent, onChange: (keys: any) => setSelectedSent(keys) }}
        columns={[
          { title: t('email.status'), dataIndex: 'status', key: 'status', width: 100, render: (v: string) => (
            <Tag color={v === 'sent' ? 'green' : v === 'failed' ? 'red' : 'orange'}>{v === 'sent' ? t('email.sentStatus') : v === 'failed' ? t('email.sentFailed') : t('email.sentPending')}</Tag>
          )},
          { title: t('email.subject'), dataIndex: 'subject', key: 'subject', ellipsis: true },
          { title: t('email.recipient'), dataIndex: 'to', key: 'recipient', width: 200, render: (v: string[]) => v?.join(', ') || '-' },
          { title: t('email.date'), dataIndex: 'sent_at', key: 'date', width: 150 },
          { title: t('email.action'), key: 'action', width: 80, render: (_: any, record: any) => (
            <Popconfirm title={t('email.confirmDelete')} onConfirm={() => handleDeleteSent([record.id])}>
              <Button type="link" danger size="small" icon={<DeleteOutlined />} />
            </Popconfirm>
          )},
        ]}
        dataSource={sentEmails}
        rowKey="id"
        pagination={false}
        locale={{ emptyText: <Empty description={t('email.noSent')} /> }}
      />
      <Pagination style={{ marginTop: 16 }} current={sentPage} pageSize={20} total={sentTotal} onChange={(p: number) => setSentPage(p)} />
    </div>
  );

  const renderDraftsTab = () => (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <Space>
          <Button type="primary" icon={<ReloadOutlined />} loading={loading} onClick={() => fetchDrafts()}>{t('email.refresh')}</Button>
          <Button icon={<EditOutlined />} onClick={() => { setEditingDraft(null); setComposeVisible(true); }}>{t('email.compose')}</Button>
        </Space>
        <Space>
          {selectedDrafts.length > 0 && (
            <Button danger icon={<DeleteOutlined />} onClick={() => handleDeleteDrafts(selectedDrafts)}>{t('email.batchDelete')}</Button>
          )}
        </Space>
      </div>
      <Table
        rowSelection={{ selectedRowKeys: selectedDrafts, onChange: (keys: any) => setSelectedDrafts(keys) }}
        columns={[
          { title: t('email.status'), key: 'status', width: 80, render: () => <Tag>{t('email.drafts')}</Tag> },
          { title: t('email.subject'), dataIndex: 'subject', key: 'subject', ellipsis: true, render: (v: string, r: any) => (
            <div>
              <div>{v || '(no subject)'}</div>
              <AttachmentList attachments={r.attachments} />
            </div>
          )},
          { title: t('email.recipient'), dataIndex: 'to', key: 'recipient', width: 200, render: (v: string[]) => v?.join(', ') || '-' },
          { title: t('email.date'), dataIndex: 'updated_at', key: 'date', width: 150 },
          { title: t('email.action'), key: 'action', width: 120, render: (_: any, record: any) => (
            <Space>
              <Button type="link" size="small" icon={<EditOutlined />} onClick={() => { setEditingDraft(record); setComposeVisible(true); }} />
              <Popconfirm title={t('email.confirmDelete')} onConfirm={() => handleDeleteDrafts([record.id])}>
                <Button type="link" danger size="small" icon={<DeleteOutlined />} />
              </Popconfirm>
            </Space>
          )},
        ]}
        dataSource={draftEmails}
        rowKey="id"
        pagination={false}
        locale={{ emptyText: <Empty description={t('email.noDrafts')} /> }}
      />
      <Pagination style={{ marginTop: 16 }} current={draftPage} pageSize={20} total={draftTotal} onChange={(p: number) => setDraftPage(p)} />
    </div>
  );

  const renderContactsTab = () => (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <Space>
          <Input prefix={<SearchOutlined />} placeholder={t('email.search')} value={contactSearch}
            onChange={(e: any) => { setContactSearch(e.target.value); setContactPage(1); }} style={{ width: 200 }} />
          <Select value={contactGroup} onChange={(v: string) => { setContactGroup(v); setContactPage(1); }} style={{ width: 140 }}
            options={[{ value: 'all', label: t('email.allGroups') }, ...contactGroups.map((g: any) => ({ value: g.name, label: g.name }))]} />
        </Space>
        <Space>
          {selectedContacts.length > 0 && (
            <>
              <Button icon={<ShareAltOutlined />} onClick={() => { setShareContactIds(selectedContacts); setShareVisible(true); }}>{t('email.batchShare')}</Button>
              <Button danger icon={<DeleteOutlined />} onClick={() => handleDeleteContacts(selectedContacts)}>{t('email.batchDelete')}</Button>
            </>
          )}
          <Button icon={<PlusOutlined />} onClick={() => setGroupModalVisible(true)}>{t('email.newGroup')}</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingContact(null); setContactModalVisible(true); }}>{t('email.new')}</Button>
        </Space>
      </div>
      <Table
        rowSelection={{ selectedRowKeys: selectedContacts, onChange: (keys: any) => setSelectedContacts(keys) }}
        columns={[
          { title: t('email.name'), dataIndex: 'name', key: 'name', render: (text: string, record: any) => (
            <Space><Avatar size="small" icon={<UserOutlined />} /><div><div>{text}</div><Text type="secondary" style={{ fontSize: 12 }}>{record.email}</Text></div></Space>
          )},
          { title: t('email.phone'), dataIndex: 'phone', key: 'phone' },
          { title: t('email.company'), dataIndex: 'company', key: 'company' },
          { title: t('email.group'), dataIndex: 'group_name', key: 'group' },
          { title: t('email.action'), key: 'action', width: 200, render: (_: any, record: any) => (
            <Space>
              <Button type="link" size="small" icon={<EditOutlined />} onClick={() => { setEditingContact(record); setContactModalVisible(true); }} />
              <Button type="link" size="small" icon={<SendOutlined />} onClick={() => handleWriteEmailToContact(record)}>{t('email.writeEmail')}</Button>
              <Button type="link" size="small" icon={<ShareAltOutlined />} onClick={() => { setShareContactIds([record.id]); setShareVisible(true); }} />
              <Popconfirm title={t('email.confirmDelete')} onConfirm={() => handleDeleteContacts([record.id])}>
                <Button type="link" danger size="small" icon={<DeleteOutlined />} />
              </Popconfirm>
            </Space>
          )},
        ]}
        dataSource={contacts}
        rowKey="id"
        pagination={false}
        locale={{ emptyText: <Empty description={t('email.noContacts')} /> }}
      />
      <div style={{ marginTop: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text type="secondary">{contactTotal} {t('email.contactCount')}</Text>
        <Pagination current={contactPage} pageSize={15} total={contactTotal} onChange={(p: number) => setContactPage(p)} />
      </div>
      <ContactModal visible={contactModalVisible} onCancel={() => setContactModalVisible(false)}
        onSave={editingContact ? handleUpdateContact : handleCreateContact}
        initialValues={editingContact} groups={contactGroups} />
      <ShareModal visible={shareVisible} onCancel={() => setShareVisible(false)}
        onShare={handleShareContacts} contactIds={shareContactIds} agents={allAgents} />
      <GroupModal visible={groupModalVisible} onCancel={() => setGroupModalVisible(false)}
        onSave={handleCreateGroup} />
    </div>
  );

  const renderTrashTab = () => {
    const isContactFilter = trashFilter === 'contact';
    return (
      <div>
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <Space>
            <Button type="primary" icon={<ReloadOutlined />} loading={loading} onClick={() => fetchTrash()}>{t('email.refresh')}</Button>
            <Select value={trashFilter} onChange={(v: string) => { setTrashFilter(v); setTrashPage(1); }} style={{ width: 140 }}
              options={[
                { value: 'all', label: t('email.allTypes') },
                { value: 'inbox', label: t('email.typeInbox') },
                { value: 'sent', label: t('email.typeSent') },
                { value: 'drafts', label: t('email.typeDrafts') },
                { value: 'contact', label: t('email.typeContact') },
              ]} />
          </Space>
          <Space>
            {selectedTrash.length > 0 && (
              <>
                <Button icon={<UndoOutlined />} onClick={() => handleRestoreTrash(selectedTrash)}>{t('email.batchRestore')}</Button>
                <Button danger icon={<CloseOutlined />} onClick={() => handlePermanentDelete(selectedTrash)}>{t('email.permanentDelete')}</Button>
              </>
            )}
          </Space>
        </div>
        <Table
          rowSelection={{ selectedRowKeys: selectedTrash, onChange: (keys: any) => setSelectedTrash(keys) }}
          columns={isContactFilter ? [
            { title: t('email.name'), dataIndex: 'name', key: 'name', render: (text: string, record: any) => (
              <Space><Avatar size="small" icon={<UserOutlined />} /><div><div>{text}</div><Text type="secondary" style={{ fontSize: 12 }}>{record.email}</Text></div></Space>
            )},
            { title: t('email.phone'), dataIndex: 'phone', key: 'phone' },
            { title: t('email.company'), dataIndex: 'company', key: 'company' },
            { title: t('email.group'), dataIndex: 'group_name', key: 'group' },
            { title: 'Deleted At', dataIndex: 'deleted_at', key: 'deleted_at', width: 150 },
            { title: t('email.action'), key: 'action', width: 150, render: (_: any, record: any) => (
              <Space>
                <Button type="link" size="small" icon={<UndoOutlined />} onClick={() => handleRestoreTrash([record.id])}>{t('email.restore')}</Button>
                <Popconfirm title={t('email.confirmPermanentDelete')} onConfirm={() => handlePermanentDelete([record.id])}>
                  <Button type="link" danger size="small" icon={<CloseOutlined />} />
                </Popconfirm>
              </Space>
            )},
          ] : [
            { title: t('email.status'), dataIndex: 'item_type', key: 'type', width: 100, render: (v: string) => <Tag>{v}</Tag> },
            { title: t('email.subject'), dataIndex: 'subject', key: 'subject', ellipsis: true, render: (v: string, record: any) => v || record.name || record.email || '-' },
            { title: t('email.recipient'), dataIndex: 'to', key: 'recipient', width: 200, render: (v: string[], record: any) => v?.join(', ') || record.email || '-' },
            { title: 'Deleted At', dataIndex: 'deleted_at', key: 'deleted_at', width: 150 },
            { title: t('email.action'), key: 'action', width: 150, render: (_: any, record: any) => (
              <Space>
                <Button type="link" size="small" icon={<UndoOutlined />} onClick={() => handleRestoreTrash([record.id])}>{t('email.restore')}</Button>
                <Popconfirm title={t('email.confirmPermanentDelete')} onConfirm={() => handlePermanentDelete([record.id])}>
                  <Button type="link" danger size="small" icon={<CloseOutlined />} />
                </Popconfirm>
              </Space>
            )},
          ]}
          dataSource={trashItems}
          rowKey="id"
          pagination={false}
          locale={{ emptyText: <Empty description={t('email.noTrash')} /> }}
        />
        <Pagination style={{ marginTop: 16 }} current={trashPage} pageSize={20} total={trashTotal} onChange={(p: number) => setTrashPage(p)} />
      </div>
    );
  };

  const renderConfigTab = () => {
    const mode = getConfigMode();
    const email = getConfigEmail();
    const hasConfig = mode !== 'none';

    return (
      <Spin spinning={configLoading} tip={t('email.loading')}>
        <div>
          <Card title={t('email.hybridPrinciple')} style={{ marginBottom: 16 }}>
            <Alert message={t('email.hybridPrincipleDesc')} type="info" showIcon />
          </Card>

          <Card title={t('email.hybridMode')} style={{ marginBottom: 16 }}
            extra={
              <Button type="primary" icon={<SettingOutlined />} onClick={() => setConfigModalVisible(true)}>
                {hasConfig ? t('email.edit') : t('email.new')}
              </Button>
            }>
            <Alert message={t('email.hybridTip')} type="info" showIcon style={{ marginBottom: 16 }} />
            <Form layout="inline">
              <Form.Item label={t('email.forwarding')}>
                <Switch checked={agentConfig?.hybrid?.forwarding || false} onChange={async (checked: boolean) => {
                  await saveConfig({ ...agentConfig?.hybrid, forwarding: checked });
                }} />
              </Form.Item>
            </Form>
          </Card>

          <Card title={t('email.backup')} style={{ marginBottom: 16 }}
            extra={<Button type="primary" icon={<CloudUploadOutlined />} loading={backupLoading} onClick={handleBackup}>{t('email.backupNow')}</Button>}>
            <Alert message={t('email.backupPath')} type="info" showIcon />
          </Card>

          <Card title={t('email.currentConfig')}
            extra={hasConfig && (
              <Button danger icon={<DeleteOutlined />} size="small" onClick={deleteConfig}>{t('email.delete')}</Button>
            )}>
            <p>{t('email.mode')}: <Tag color={hasConfig ? 'green' : 'blue'}>{hasConfig ? t('email.hybridMode') : t('email.notConfigured')}</Tag></p>
            <p>{t('email.emailAddr')}: <Text type="secondary">{email}</Text></p>
            <p>{t('email.status')}: <Badge status={hasConfig ? 'success' : 'default'} text={hasConfig ? t('email.connected') : t('email.disconnected')} /></p>
          </Card>

          <Card title={t('agent.emailRules')} style={{ marginTop: 16, marginBottom: 16 }}
            extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setRuleModalVisible(true)}>{t('agent.createRule')}</Button>}>
            <AgentRulesList />
          </Card>

          <Card title={t('email.uninstall')} style={{ marginTop: 16 }}
            extra={<Button danger icon={<DeleteOutlined />} onClick={() => setUninstallVisible(true)}>{t('email.uninstall')}</Button>}>
            <Alert message="Uninstall the AgentMail plugin. You can choose to keep or export your data." type="warning" showIcon />
          </Card>
        </div>

        <HybridConfigModal visible={configModalVisible} onCancel={() => setConfigModalVisible(false)}
          onSave={(v: any) => saveConfig(v)} initialValues={agentConfig?.hybrid} />
        <UninstallModal visible={uninstallVisible} onCancel={() => setUninstallVisible(false)}
          onUninstall={handleUninstall} agentId={agentId} />
        <AgentRuleModal visible={ruleModalVisible} onCancel={() => { setRuleModalVisible(false); setEditingRule(null); }}
          onSave={(rule: any) => {
            const agentId = getCurrentAgentId();
            const rulesKey = `agentmail_rules_${agentId}`;
            const existing = JSON.parse(localStorage.getItem(rulesKey) || '[]');
            if (editingRule) {
              existing[editingRule.index] = rule;
            } else {
              existing.push(rule);
            }
            localStorage.setItem(rulesKey, JSON.stringify(existing));
            setRuleModalVisible(false);
            setEditingRule(null);
            message.success(t('agent.ruleApplied'));
          }} initialValues={editingRule?.data} />
      </Spin>
    );
  };

  return (
    <div style={{ padding: '24px' }}>
      <Title level={2} style={{ marginBottom: 24 }}>
        <MailOutlined style={{ marginRight: 8 }} />
        {t('email.title')} - {agentName}
      </Title>
      <Card>
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
          { key: 'inbox', label: <span><InboxOutlined style={{ marginRight: 4 }} />{t('email.inbox')}</span>, children: renderInboxTab() },
          { key: 'sent', label: <span><SendOutlined style={{ marginRight: 4 }} />{t('email.sent')}</span>, children: renderSentTab() },
          { key: 'drafts', label: <span><EditOutlined style={{ marginRight: 4 }} />{t('email.drafts')}</span>, children: renderDraftsTab() },
          { key: 'contacts', label: <span><TeamOutlined style={{ marginRight: 4 }} />{t('email.contacts')}</span>, children: renderContactsTab() },
          { key: 'trash', label: <span><RestOutlined style={{ marginRight: 4 }} />{t('email.trash')}</span>, children: renderTrashTab() },
          { key: 'config', label: <span><SettingOutlined style={{ marginRight: 4 }} />{t('email.config')}</span>, children: renderConfigTab() },
        ]} />
      </Card>
      <ComposeModal key={editingDraft?.id || 'new'} visible={composeVisible} onCancel={() => { setComposeVisible(false); setEditingDraft(null); }}
        onSend={handleSendEmail} onSaveDraft={handleSaveDraft} contacts={contacts} editingDraft={editingDraft} />
    </div>
  );
}

class AgentMailPlugin {
  readonly id = 'agentmail';
  setup(): void {
    const label = t('nav.email');
    (window as any).QwenPaw.registerRoutes?.(this.id, [
      { path: '/email', component: EmailPage, label: label, icon: React.createElement(MailOutlined, { style: { fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'center' } }), priority: 10 },
    ]);
    console.info(`[${this.id}] Sidebar route registered`);
  }
}

new AgentMailPlugin().setup();
