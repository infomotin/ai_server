// ============= OpenLocalAI AI Assistants =============
const PROXY = '/api/assistants/proxy';
let currentView = 'grid';
let currentAssistantId = null;
let currentAssistant = null;
let currentConversationId = null;
let availableModels = [];
let allAssistants = [];
let currentFilter = null;
let searchQuery = '';
let activityChart = null;

const TEMPLATES = {
    support: { name: 'Customer Support', icon: 'fas fa-headset', color: 'blue', description: 'Handle customer inquiries', integrations: ['email', 'chat'] },
    code: { name: 'Code Assistant', icon: 'fas fa-code', color: 'purple', description: 'Help with programming', integrations: ['github', 'git'] },
    research: { name: 'Research Helper', icon: 'fas fa-flask', color: 'cyan', description: 'Web research & analysis', integrations: ['web_search', 'web_fetch'] },
    email: { name: 'Email Assistant', icon: 'fas fa-envelope', color: 'amber', description: 'Read, draft, and reply to emails', integrations: ['imap', 'smtp'] },
    sales: { name: 'Sales Agent', icon: 'fas fa-chart-line', color: 'green', description: 'Generate leads & close deals', integrations: ['email', 'crm'] },
    social: { name: 'Social Media', icon: 'fas fa-share-nodes', color: 'pink', description: 'Create posts & engage', integrations: ['facebook_api', 'telegram'] },
    data: { name: 'Data Analyst', icon: 'fas fa-database', color: 'teal', description: 'Analyze & visualize data', integrations: ['database'] },
    tutor: { name: 'Tutor', icon: 'fas fa-graduation-cap', color: 'yellow', description: 'Teach any subject', integrations: [] },
    translator: { name: 'Translator', icon: 'fas fa-language', color: 'indigo', description: 'Multi-language support', integrations: [] },
    booking: { name: 'Booking Agent', icon: 'fas fa-calendar-check', color: 'rose', description: 'Schedule & bookings', integrations: ['calendar_api', 'email'] },
    hr: { name: 'HR Assistant', icon: 'fas fa-users', color: 'orange', description: 'Recruiting & HR support', integrations: ['email'] },
    custom: { name: 'Blank', icon: 'fas fa-plus', color: 'gray', description: 'Start from scratch', integrations: [] }
};

const INTEGRATION_TYPES = {
    imap: { name: 'Email (IMAP)', icon: 'fas fa-inbox', color: 'blue', fields: ['host', 'port', 'username', 'password', 'use_ssl'] },
    smtp: { name: 'Email (SMTP)', icon: 'fas fa-paper-plane', color: 'blue', fields: ['host', 'port', 'username', 'password', 'use_ssl'] },
    whatsapp_api: { name: 'WhatsApp API', icon: 'fab fa-whatsapp', color: 'green', fields: ['api_key', 'phone_number'] },
    facebook_api: { name: 'Facebook API', icon: 'fab fa-facebook', color: 'indigo', fields: ['app_id', 'app_secret', 'access_token'] },
    web_search: { name: 'Web Search', icon: 'fas fa-search', color: 'cyan', fields: ['api_key', 'search_engine'] },
    web_fetch: { name: 'Web Fetcher', icon: 'fas fa-globe', color: 'cyan', fields: ['proxy_url'] },
    calendar_api: { name: 'Calendar API', icon: 'fas fa-calendar', color: 'amber', fields: ['provider', 'api_key'] },
    notification: { name: 'Notifications', icon: 'fas fa-bell', color: 'amber', fields: ['email', 'webhook_url'] },
    git: { name: 'Git Repository', icon: 'fab fa-git-alt', color: 'red', fields: ['repo_path', 'remote_url'] },
    database: { name: 'Database', icon: 'fas fa-database', color: 'teal', fields: ['connection_url'] },
    chat: { name: 'Live Chat', icon: 'fas fa-comments', color: 'orange', fields: ['widget_id'] },
    slack: { name: 'Slack', icon: 'fab fa-slack', color: 'purple', fields: ['bot_token', 'channel'] },
    telegram: { name: 'Telegram', icon: 'fab fa-telegram', color: 'cyan', fields: ['bot_token'] },
    github: { name: 'GitHub', icon: 'fab fa-github', color: 'gray', fields: ['token', 'repo'] },
    google_drive: { name: 'Google Drive', icon: 'fab fa-google-drive', color: 'amber', fields: ['credentials_json'] },
    dropbox: { name: 'Dropbox', icon: 'fab fa-dropbox', color: 'blue', fields: ['access_token'] },
    notion: { name: 'Notion', icon: 'fas fa-book', color: 'gray', fields: ['api_key', 'database_id'] },
    trello: { name: 'Trello', icon: 'fas fa-trello', color: 'blue', fields: ['api_key', 'token'] }
};

const FIELD_LABELS = {
    host: { label: 'IMAP Host', placeholder: 'imap.gmail.com', type: 'text' },
    port: { label: 'Port', placeholder: '993', type: 'number' },
    username: { label: 'Username / Email', placeholder: '[email protected]', type: 'text' },
    password: { label: 'Password / App Password', placeholder: '••••••••', type: 'password' },
    use_ssl: { label: 'Use SSL/TLS', placeholder: '', type: 'checkbox' },
    api_key: { label: 'API Key', placeholder: 'Your API key', type: 'password' },
    phone_number: { label: 'Phone Number', placeholder: '+1234567890', type: 'text' },
    app_id: { label: 'App ID', placeholder: '', type: 'text' },
    app_secret: { label: 'App Secret', placeholder: '', type: 'password' },
    access_token: { label: 'Access Token', placeholder: '', type: 'password' },
    search_engine: { label: 'Search Engine', placeholder: 'google / bing / duckduckgo', type: 'text' },
    proxy_url: { label: 'Proxy URL', placeholder: 'https://...', type: 'text' },
    provider: { label: 'Provider', placeholder: 'google / outlook', type: 'text' },
    email: { label: 'Email', placeholder: '[email protected]', type: 'text' },
    webhook_url: { label: 'Webhook URL', placeholder: 'https://...', type: 'text' },
    repo_path: { label: 'Repository Path', placeholder: '/path/to/repo', type: 'text' },
    remote_url: { label: 'Remote URL', placeholder: 'https://github.com/...', type: 'text' },
    connection_url: { label: 'Connection URL', placeholder: 'mysql://user:pass@host/db', type: 'text' },
    widget_id: { label: 'Widget ID', placeholder: '', type: 'text' },
    bot_token: { label: 'Bot Token', placeholder: '', type: 'password' },
    channel: { label: 'Channel', placeholder: '#general', type: 'text' },
    token: { label: 'Token', placeholder: '', type: 'password' },
    repo: { label: 'Repository', placeholder: 'owner/repo', type: 'text' },
    credentials_json: { label: 'Credentials JSON', placeholder: '{}', type: 'textarea' },
    database_id: { label: 'Database ID', placeholder: '', type: 'text' }
};

// ============= Utilities =============

function escapeHtml(s) {
    if (s == null) return '';
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function showToast(msg, type = 'success') {
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.innerHTML = `<i class="fas fa-${type === 'error' ? 'exclamation-circle' : type === 'info' ? 'info-circle' : 'check-circle'} mr-2"></i>${escapeHtml(msg)}`;
    document.body.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .3s'; setTimeout(() => t.remove(), 300); }, 3000);
}

async function api(method, path, body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body !== null) opts.body = JSON.stringify(body);
    const resp = await fetch(PROXY + '/' + path, opts);
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(err.detail || err.message || 'Request failed');
    }
    return resp.json();
}

function avatarFor(name) {
    if (!name) return 'AI';
    return name.split(' ').map(s => s[0]).slice(0, 2).join('').toUpperCase();
}

function formatDate(d) {
    if (!d) return '—';
    return new Date(d).toLocaleDateString();
}

function formatTime(d) {
    if (!d) return '';
    return new Date(d).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function timeAgo(d) {
    if (!d) return '';
    const seconds = Math.floor((Date.now() - new Date(d).getTime()) / 1000);
    if (seconds < 60) return 'just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    return new Date(d).toLocaleDateString();
}

function renderMarkdown(text) {
    if (!text) return '';
    if (typeof marked === 'undefined') return escapeHtml(text);
    try {
        const html = marked.parse(text, { breaks: true, gfm: true });
        return typeof DOMPurify !== 'undefined' ? DOMPurify.sanitize(html) : html;
    } catch (e) {
        return escapeHtml(text);
    }
}

// ============= Initialization =============

async function init() {
    try {
        const assistants = await api('GET', '');
        allAssistants = Array.isArray(assistants) ? assistants : [];
    } catch (e) {
        showToast('Failed to load assistants: ' + e.message, 'error');
        allAssistants = [];
    }
    renderTemplateGrid();
    renderCreateTemplateGrid();
    populateIntegrationTypes();
    populateTaskTypes();
    await loadModels();
    renderAssistants();
    setTimeout(() => populateModels(), 200);
}

async function loadModels() {
    try {
        const models = await fetch('/v1/models').then(r => r.json()).catch(() => null);
        if (models && models.data) {
            availableModels = models.data.map(m => m.id);
        }
    } catch (e) {
        availableModels = ['qwen2.5-coder:1.5b', 'llama3.2:1b', 'qwen2.5:0.5b'];
    }
    if (availableModels.length === 0) availableModels = ['qwen2.5-coder:1.5b'];
}

function populateModels() {
    const opts = availableModels.map(m => `<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`).join('');
    ['formModel', 'setModel'].forEach(id => {
        const sel = document.getElementById(id);
        if (sel) sel.innerHTML = opts;
    });
}

// ============= View & Filter =============

function setView(view) {
    currentView = view;
    document.getElementById('viewGridBtn').classList.toggle('active', view === 'grid');
    document.getElementById('viewListBtn').classList.toggle('active', view === 'list');
    document.getElementById('assistantsContainer').style.gridTemplateColumns = view === 'list' ? '1fr' : '';
    renderAssistants();
}

function filterByTemplate(template) {
    currentFilter = template;
    renderAssistants();
}

function filterAssistants() {
    searchQuery = document.getElementById('searchInput').value.toLowerCase();
    renderAssistants();
}

function renderTemplateGrid() {
    const grid = document.getElementById('templateGrid');
    grid.innerHTML = Object.entries(TEMPLATES).map(([key, t]) => `
        <div class="template-card" onclick="filterByTemplate('${key}')" data-template="${key}">
            <i class="${t.icon} text-xl text-${t.color}-400 mb-1"></i>
            <p class="text-[11px] text-white font-medium">${t.name}</p>
        </div>
    `).join('');
}

function renderCreateTemplateGrid() {
    const grid = document.getElementById('createTemplateGrid');
    grid.innerHTML = Object.entries(TEMPLATES).map(([key, t]) => `
        <div class="template-card" onclick="selectTemplate('${key}')" data-template="${key}">
            <i class="${t.icon} text-base text-${t.color}-400"></i>
            <p class="text-[10px] text-white mt-1">${t.name}</p>
        </div>
    `).join('');
}

function selectTemplate(key) {
    document.querySelectorAll('#createTemplateGrid .template-card').forEach(el => {
        el.classList.toggle('active', el.dataset.template === key);
    });
    const form = document.getElementById('createForm');
    const t = TEMPLATES[key];
    if (t) {
        if (!form.name.value) form.name.value = `My ${t.name}`;
        if (!form.description.value) form.description.value = t.description;
        if (key !== 'custom' && !form.system_prompt.value) {
            form.system_prompt.value = `You are a ${t.name.toLowerCase()}. ${t.description}. Be helpful, accurate, and concise.`;
        }
    }
}

function renderAssistants() {
    const container = document.getElementById('assistantsContainer');
    let list = allAssistants;
    if (currentFilter) {
        const t = TEMPLATES[currentFilter];
        if (t) {
            const keywords = [currentFilter, t.name.toLowerCase(), ...(t.integrations || [])];
            list = list.filter(a => {
                const tags = (a.tags || '').toLowerCase();
                return keywords.some(k => tags.includes(k));
            });
        }
    }
    if (searchQuery) {
        list = list.filter(a =>
            (a.name || '').toLowerCase().includes(searchQuery) ||
            (a.description || '').toLowerCase().includes(searchQuery) ||
            (a.tags || '').toLowerCase().includes(searchQuery)
        );
    }
    if (!list.length) {
        container.innerHTML = `<div class="col-span-full empty-state">
            <i class="fas fa-robot text-5xl text-gray-700 mb-3"></i>
            <p class="text-sm">No assistants found</p>
            <button onclick="openCreateModal()" class="btn btn-primary mt-3"><i class="fas fa-plus"></i> Create your first assistant</button>
        </div>`;
        return;
    }
    container.innerHTML = list.map(a => {
        const tags = (a.tags || '').split(',').map(t => t.trim()).filter(Boolean);
        const status = a.is_active ? 'Active' : 'Inactive';
        const statusClass = a.is_active ? 'badge-active' : 'badge-inactive';
        return `
        <div class="assistant-card" onclick="openAssistant('${a.id}')">
            <div class="flex items-start justify-between mb-3">
                <div class="flex items-center gap-3 min-w-0">
                    <div class="w-12 h-12 rounded-full avatar-gradient flex-shrink-0">${escapeHtml(avatarFor(a.name))}</div>
                    <div class="min-w-0">
                        <h3 class="text-white font-semibold truncate">${escapeHtml(a.name)}</h3>
                        <p class="text-xs text-gray-400 truncate">${escapeHtml(a.model_id || '—')}</p>
                    </div>
                </div>
                <span class="badge ${statusClass}">${status}</span>
            </div>
            <p class="text-sm text-gray-400 mb-3 line-clamp-2" style="min-height:40px;">${escapeHtml(a.description || 'No description')}</p>
            <div class="flex items-center justify-between text-[10px] text-gray-500 mb-3">
                <span><i class="fas fa-brain mr-1 text-purple-400"></i>${escapeHtml(a.personality || 'professional')}</span>
                <span><i class="fas fa-calendar mr-1 text-cyan-400"></i>${formatDate(a.created_at)}</span>
            </div>
            <div class="flex flex-wrap gap-1">
                ${tags.slice(0, 3).map(t => `<span class="badge badge-tag">${escapeHtml(t)}</span>`).join('')}
                ${tags.length > 3 ? `<span class="badge badge-tag">+${tags.length - 3}</span>` : ''}
            </div>
        </div>`;
    }).join('');
}

// ============= Create Modal =============

function openCreateModal() {
    document.getElementById('createModal').classList.remove('hidden');
    document.querySelectorAll('#createTemplateGrid .template-card').forEach(el => el.classList.remove('active'));
    document.getElementById('createForm').reset();
}
function closeCreateModal() { document.getElementById('createModal').classList.add('hidden'); }

document.getElementById('createForm').addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const tags = (fd.get('tags') || '').split(',').map(t => t.trim()).filter(Boolean);
    const active = document.querySelector('#createTemplateGrid .template-card.active');
    const template = active ? active.dataset.template : 'custom';
    try {
        const r = await api('POST', '', {
            name: fd.get('name'),
            description: fd.get('description') || null,
            template,
            model_id: fd.get('model_id'),
            personality: fd.get('personality'),
            system_prompt: fd.get('system_prompt') || null,
            tags
        });
        showToast('Assistant created: ' + r.name);
        closeCreateModal();
        allAssistants.push(r);
        renderAssistants();
    } catch (e) { showToast(e.message, 'error'); }
});

// ============= Detail Modal =============

async function openAssistant(id) {
    currentAssistantId = id;
    currentAssistant = null;
    currentConversationId = null;
    document.getElementById('detailModal').classList.remove('hidden');
    setTab('chat');
    document.getElementById('chatMessages').innerHTML = `<div class="empty-state"><i class="fas fa-spinner fa-spin text-3xl text-purple-400"></i><p class="text-sm mt-2">Loading...</p></div>`;
    try {
        const data = await api('GET', id);
        currentAssistant = data;
        populateDetail(data);
    } catch (e) {
        showToast('Failed to load: ' + e.message, 'error');
        closeDetailModal();
    }
}

function closeDetailModal() {
    document.getElementById('detailModal').classList.add('hidden');
    currentAssistantId = null;
    currentAssistant = null;
    currentConversationId = null;
}

function populateDetail(data) {
    const a = data.assistant;
    const el = (id) => document.getElementById(id);
    if (el('detailName')) el('detailName').textContent = a.name;
    if (el('detailSubtitle')) el('detailSubtitle').textContent = `${a.model_id} • ${a.personality}`;
    if (el('detailAvatar')) el('detailAvatar').textContent = avatarFor(a.name);
    if (el('infoAvatar')) el('infoAvatar').textContent = avatarFor(a.name);
    if (el('infoName')) el('infoName').textContent = a.name;
    if (el('infoDescription')) el('infoDescription').textContent = a.description || '—';
    if (el('infoModel')) el('infoModel').textContent = a.model_id;
    if (el('infoPersonality')) el('infoPersonality').textContent = a.personality;
    if (el('infoTemp')) el('infoTemp').textContent = a.temperature ?? 0.7;
    if (el('infoTokens')) el('infoTokens').textContent = a.max_tokens ?? 1000;
    if (el('infoCreated')) el('infoCreated').textContent = formatDate(a.created_at);
    if (el('infoStatus')) el('infoStatus').innerHTML = a.is_active ? '<span class="text-green-400"><i class="fas fa-circle text-[6px] mr-1"></i>Active</span>' : '<span class="text-gray-400">Inactive</span>';
    const tagsHtml = (a.tags || '').split(',').map(t => t.trim()).filter(Boolean)
        .map(t => `<span class="badge badge-tag">${escapeHtml(t)}</span>`).join('') || '<span class="text-xs text-gray-500">No tags</span>';
    if (el('infoTags')) el('infoTags').innerHTML = tagsHtml;
    if (el('infoPrompt')) el('infoPrompt').textContent = a.system_prompt || 'No system prompt';
    if (el('currentModel')) el('currentModel').textContent = a.model_id;
    if (el('currentTemp')) el('currentTemp').textContent = a.temperature ?? 0.7;
    if (el('currentTokens')) el('currentTokens').textContent = a.max_tokens ?? 1000;
    renderConversations(data.conversations || []);
    renderIntegrations(data.integrations || []);
    loadConnectedIntegrations();
    renderTasks(data.tasks || []);
    renderLogs(data.recent_logs || []);
    renderAnalytics(data);
    if (data.conversations && data.conversations.length) {
        loadConversation(data.conversations[0].id);
    } else {
        document.getElementById('chatMessages').innerHTML = `<div class="empty-state"><i class="fas fa-robot text-4xl text-gray-700 mb-3"></i><p class="text-sm">Start a conversation with this assistant</p></div>`;
    }
}

function setTab(tab) {
    ['chat', 'integrations', 'tasks', 'monitors', 'schedule', 'analytics', 'logs'].forEach(t => {
        const tabEl = document.getElementById('tab' + t.charAt(0).toUpperCase() + t.slice(1));
        const panelEl = document.getElementById('panel' + t.charAt(0).toUpperCase() + t.slice(1));
        if (tabEl) tabEl.classList.toggle('active', t === tab);
        if (panelEl) panelEl.classList.toggle('hidden', t !== tab);
    });
    if (tab === 'monitors') initMonitorsTab();
    if (tab === 'integrations') loadConnectedIntegrations();
    if (tab === 'analytics' && currentAssistant) {
        setTimeout(() => renderAnalytics(currentAssistant), 100);
    }
}

function renderConversations(conversations) {
    const list = document.getElementById('conversationsList');
    if (!conversations.length) {
        list.innerHTML = '<p class="text-xs text-gray-500 text-center py-8">No conversations yet</p>';
        return;
    }
    list.innerHTML = conversations.map(c => `
        <div class="conv-item ${c.id === currentConversationId ? 'active' : ''}" onclick="loadConversation('${c.id}')">
            <div class="flex items-center justify-between gap-2">
                <p class="text-sm text-white truncate flex-1">${escapeHtml(c.title || 'New conversation')}</p>
                <button onclick="event.stopPropagation();event.preventDefault();deleteConversation('${c.id}')" class="text-gray-500 hover:text-red-400 text-xs flex-shrink-0"><i class="fas fa-trash"></i></button>
            </div>
            <p class="text-[10px] text-gray-500 mt-0.5">${timeAgo(c.updated_at || c.created_at)}</p>
        </div>
    `).join('');
}

async function loadConversation(id) {
    currentConversationId = id;
    document.querySelectorAll('.conv-item').forEach(el => el.classList.remove('active'));
    try {
        const data = await api('GET', `conversations/${id}/messages`);
        renderMessages(data || []);
        if (currentAssistant) {
            const conv = currentAssistant.conversations?.find(c => c.id === id);
            if (conv) {
                const msgs = (data || []).length;
                conv.message_count = msgs;
            }
        }
    } catch (e) {
        showToast('Failed to load conversation: ' + e.message, 'error');
    }
}

async function newConversation() {
    if (!currentAssistantId) return;
    currentConversationId = null;
    document.getElementById('chatMessages').innerHTML = `<div class="empty-state"><i class="fas fa-robot text-4xl text-gray-700 mb-3"></i><p class="text-sm">New conversation started</p></div>`;
    setTab('chat');
    document.getElementById('chatInput').focus();
}

async function deleteConversation(id) {
    if (!confirm('Delete this conversation?')) return;
    try {
        await api('DELETE', `conversations/${id}`);
        if (currentConversationId === id) {
            currentConversationId = null;
            document.getElementById('chatMessages').innerHTML = '';
        }
        const data = await api('GET', currentAssistantId);
        renderConversations(data.conversations || []);
        showToast('Conversation deleted');
    } catch (e) { showToast(e.message, 'error'); }
}

function renderMessages(messages) {
    const el = document.getElementById('chatMessages');
    if (!messages.length) {
        el.innerHTML = `<div class="empty-state"><i class="fas fa-robot text-4xl text-gray-700 mb-3"></i><p class="text-sm">Start the conversation</p></div>`;
        return;
    }
    el.innerHTML = messages.map(m => `
        <div class="flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} mb-4 chat-message">
            <div class="chat-bubble ${m.role === 'user' ? 'user' : 'assistant'}">
                ${m.role === 'user' ? escapeHtml(m.content) : renderMarkdown(m.content)}
            </div>
        </div>
    `).join('');
    el.scrollTop = el.scrollHeight;
}

async function sendMessage() {
    if (!currentAssistantId) { showToast('No assistant selected', 'error'); return; }
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    input.style.height = 'auto';
    const el = document.getElementById('chatMessages');
    if (el.querySelector('.empty-state')) el.innerHTML = '';
    el.innerHTML += `<div class="flex justify-end mb-4 chat-message"><div class="chat-bubble user">${escapeHtml(text)}</div></div>`;
    el.innerHTML += `<div class="flex justify-start mb-4 chat-message" id="typingBubble"><div class="chat-bubble assistant"><div class="typing-dots"><span></span><span></span><span></span></div></div></div>`;
    el.scrollTop = el.scrollHeight;
    const btn = document.getElementById('sendBtn');
    btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    const cmd = detectCommand(text);
    if (cmd) {
        const handled = await executeCommand(cmd, text);
        btn.disabled = false; btn.innerHTML = '<i class="fas fa-paper-plane"></i>';
        if (handled) return;
    }

    try {
        const data = await api('POST', `${currentAssistantId}/chat`, { message: text, conversation_id: currentConversationId });
        document.getElementById('typingBubble')?.remove();
        currentConversationId = data.conversation_id;
        const rendered = renderMarkdown(data.response || 'No response');
        el.innerHTML += `<div class="flex justify-start mb-4 chat-message"><div class="chat-bubble assistant">${rendered}</div></div>`;
        el.scrollTop = el.scrollHeight;
        const refreshData = await api('GET', currentAssistantId);
        renderConversations(refreshData.conversations || []);
    } catch (e) {
        document.getElementById('typingBubble')?.remove();
        el.innerHTML += `<div class="flex justify-start mb-4"><div class="chat-bubble assistant" style="background:rgba(239,68,68,0.2);border-color:#ef4444;">Error: ${escapeHtml(e.message)}</div></div>`;
    }
    btn.disabled = false; btn.innerHTML = '<i class="fas fa-paper-plane"></i>';
}

// Auto-resize textarea
document.getElementById('chatInput').addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 160) + 'px';
});

// ============= Settings Modal =============

function openSettingsPanel() {
    if (!currentAssistant) return;
    const a = currentAssistant.assistant;
    const el = (id) => document.getElementById(id);
    if (el('setName')) el('setName').value = a.name || '';
    if (el('setDescription')) el('setDescription').value = a.description || '';
    if (el('setModel')) el('setModel').innerHTML = availableModels.map(m => `<option value="${escapeHtml(m)}" ${m === a.model_id ? 'selected' : ''}>${escapeHtml(m)}</option>`).join('');
    if (el('setPersonality')) el('setPersonality').value = a.personality || 'professional';
    if (el('setTemp')) el('setTemp').value = a.temperature ?? 0.7;
    if (el('setTempVal')) el('setTempVal').textContent = a.temperature ?? 0.7;
    if (el('setTokens')) el('setTokens').value = a.max_tokens ?? 1000;
    if (el('setTokensVal')) el('setTokensVal').textContent = a.max_tokens ?? 1000;
    if (el('setPrompt')) el('setPrompt').value = a.system_prompt || '';
    if (el('setTags')) el('setTags').value = a.tags || '';
    if (el('settingsModal')) el('settingsModal').classList.remove('hidden');
}
function closeSettingsPanel() { document.getElementById('settingsModal').classList.add('hidden'); }

document.getElementById('settingsForm').addEventListener('submit', async e => {
    e.preventDefault();
    if (!currentAssistantId) return;
    const fd = new FormData(e.target);
    const tags = (fd.get('tags') || '').split(',').map(t => t.trim()).filter(Boolean);
    try {
        await api('PUT', currentAssistantId, {
            name: fd.get('name'),
            description: fd.get('description') || null,
            model_id: fd.get('model_id'),
            personality: fd.get('personality'),
            temperature: parseFloat(fd.get('temperature')),
            max_tokens: parseInt(fd.get('max_tokens')),
            system_prompt: fd.get('system_prompt') || null,
            tags
        });
        showToast('Settings saved');
        closeSettingsPanel();
        const data = await api('GET', currentAssistantId);
        currentAssistant = data;
        populateDetail(data);
        allAssistants = await api('GET', '');
        renderAssistants();
    } catch (e) { showToast(e.message, 'error'); }
});

// ============= Actions =============

async function toggleAssistantActive() {
    try {
        const r = await api('POST', `${currentAssistantId}/toggle`);
        showToast(r.is_active ? 'Activated' : 'Deactivated');
        const data = await api('GET', currentAssistantId);
        currentAssistant = data;
        populateDetail(data);
        allAssistants = await api('GET', '');
        renderAssistants();
    } catch (e) { showToast(e.message, 'error'); }
}

async function duplicateCurrentAssistant() {
    try {
        const r = await api('POST', `${currentAssistantId}/duplicate`);
        showToast('Duplicated: ' + r.name);
        allAssistants = await api('GET', '');
        renderAssistants();
    } catch (e) { showToast(e.message, 'error'); }
}

async function shareCurrentAssistant() {
    try {
        const r = await api('POST', `${currentAssistantId}/share`);
        const url = `${location.origin}/share/${r.share_token}`;
        navigator.clipboard.writeText(url).then(() => showToast('Share link copied!', 'info'))
            .catch(() => prompt('Share link:', url));
    } catch (e) { showToast(e.message, 'error'); }
}

async function deleteCurrentAssistant() {
    if (!confirm('Delete this assistant permanently?')) return;
    try {
        await api('DELETE', currentAssistantId);
        showToast('Assistant deleted');
        closeDetailModal();
        allAssistants = await api('GET', '');
        renderAssistants();
    } catch (e) { showToast(e.message, 'error'); }
}

function exportCurrentChat() {
    if (!currentAssistant) return;
    const messages = currentAssistant.conversations?.find(c => c.id === currentConversationId)?.messages || [];
    if (!messages.length) { showToast('No messages to export', 'info'); return; }
    const text = messages.map(m => `[${m.role.toUpperCase()}]\n${m.content}\n`).join('\n---\n\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${currentAssistant.assistant.name}_chat.txt`;
    a.click();
    showToast('Chat exported');
}

// ============= Integrations =============

function populateIntegrationTypes() {
    const sel = document.getElementById('integrationTypeSelect');
    sel.innerHTML = Object.entries(INTEGRATION_TYPES).map(([k, v]) => `<option value="${k}">${escapeHtml(v.name)}</option>`).join('');
    onIntegrationTypeChange();
}

function onIntegrationTypeChange() {
    const sel = document.getElementById('integrationTypeSelect');
    const container = document.getElementById('integrationConfigFields');
    if (!sel || !container) return;
    const type = sel.value;
    const def = INTEGRATION_TYPES[type];
    if (!def || !def.fields || def.fields.length === 0) {
        container.innerHTML = '<p class="text-xs text-gray-500 italic">No additional configuration needed.</p>';
        return;
    }
    container.innerHTML = def.fields.map(f => {
        const meta = FIELD_LABELS[f] || { label: f, placeholder: '', type: 'text' };
        if (meta.type === 'checkbox') {
            return `<div class="flex items-center gap-2">
                <input type="checkbox" name="config_${f}" id="config_${f}" class="w-4 h-4 rounded" ${f === 'use_ssl' ? 'checked' : ''}>
                <label for="config_${f}" class="text-sm text-gray-300">${escapeHtml(meta.label)}</label>
            </div>`;
        }
        if (meta.type === 'textarea') {
            return `<div>
                <label class="block text-xs text-gray-400 mb-1">${escapeHtml(meta.label)}</label>
                <textarea name="config_${f}" rows="3" class="input-field font-mono text-xs" placeholder="${escapeHtml(meta.placeholder)}"></textarea>
            </div>`;
        }
        return `<div>
            <label class="block text-xs text-gray-400 mb-1">${escapeHtml(meta.label)}</label>
            <input type="${meta.type}" name="config_${f}" class="input-field" placeholder="${escapeHtml(meta.placeholder)}" autocomplete="off">
        </div>`;
    }).join('');
}

function openAddIntegrationModal() {
    document.getElementById('integrationModal').classList.remove('hidden');
    onIntegrationTypeChange();
}
function closeIntegrationModal() { document.getElementById('integrationModal').classList.add('hidden'); }

document.getElementById('integrationForm').addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const config = {};
    for (const [key, val] of fd.entries()) {
        if (key.startsWith('config_')) {
            const fieldName = key.replace('config_', '');
            if (val !== '' && val != null) config[fieldName] = val;
        }
    }
    try {
        await api('POST', `${currentAssistantId}/integrations`, {
            integration_type: fd.get('integration_type'),
            name: fd.get('name') || undefined,
            config: Object.keys(config).length ? config : undefined
        });
        showToast('Integration added');
        closeIntegrationModal();
        const data = await api('GET', currentAssistantId);
        renderIntegrations(data.integrations || []);
    } catch (e) { showToast(e.message, 'error'); }
});

function renderIntegrations(integrations) {
    const list = document.getElementById('integrationsList');
    if (!integrations || !integrations.length) {
        list.innerHTML = '<p class="text-sm text-gray-500">No custom integrations configured</p>';
        return;
    }
    list.innerHTML = integrations.map(i => {
        const def = INTEGRATION_TYPES[i.integration_type] || {};
        const icon = def.icon || 'fas fa-plug';
        const color = def.color || 'cyan';
        const hasConfig = i.config && Object.keys(i.config).length > 0;
        const configInfo = hasConfig ? `${Object.keys(i.config).length} field(s) set` : 'No config';
        return `
        <div class="p-3 glass flex items-center justify-between gap-3">
            <div class="flex items-center gap-3 flex-1 min-w-0">
                <div class="w-10 h-10 rounded-lg bg-${color}-600/20 flex items-center justify-center"><i class="${icon} text-${color}-400"></i></div>
                <div class="min-w-0">
                    <p class="text-sm text-white font-medium truncate">${escapeHtml(i.name)}</p>
                    <p class="text-[10px] text-gray-500">${escapeHtml(i.integration_type)} • ${escapeHtml(i.status || 'disconnected')} • ${configInfo}</p>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <button onclick="testIntegration('${i.id}')" class="btn btn-ghost text-gray-500 hover:text-green-400" title="Test connection"><i class="fas fa-plug-circle-bolt text-xs"></i></button>
                <label class="relative inline-flex items-center cursor-pointer" title="Toggle active">
                    <input type="checkbox" ${i.is_active ? 'checked' : ''} onchange="toggleIntegration('${i.id}', this.checked)" class="sr-only peer">
                    <div class="w-9 h-5 bg-gray-600 rounded-full peer peer-checked:bg-cyan-500 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-full"></div>
                </label>
                <button onclick="deleteIntegration('${i.id}')" class="btn btn-ghost text-gray-500 hover:text-red-400" title="Delete"><i class="fas fa-trash text-xs"></i></button>
            </div>
        </div>`;
    }).join('');
}

async function toggleIntegration(id, active) {
    try {
        await api('PUT', `integrations/${id}`, { is_active: active, status: active ? 'connected' : 'disconnected' });
    } catch (e) { showToast(e.message, 'error'); }
}

// Load connected integrations from the integrations page (localStorage)
const INTEGRATION_CATALOG = {
    whatsapp_web: { name: 'WhatsApp Web', icon: 'fab fa-whatsapp', color: 'green', category: 'messaging' },
    telegram_bot: { name: 'Telegram Bot', icon: 'fab fa-telegram', color: 'sky', category: 'messaging' },
    slack: { name: 'Slack', icon: 'fab fa-slack', color: 'purple', category: 'messaging' },
    discord_bot: { name: 'Discord Bot', icon: 'fab fa-discord', color: 'indigo', category: 'messaging' },
    email_imap: { name: 'Email (IMAP/SMTP)', icon: 'fas fa-envelope', color: 'blue', category: 'messaging' },
    github: { name: 'GitHub', icon: 'fab fa-github', color: 'gray', category: 'dev' },
    gitlab: { name: 'GitLab', icon: 'fab fa-gitlab', color: 'orange', category: 'dev' },
    google_calendar: { name: 'Google Calendar', icon: 'fas fa-calendar', color: 'blue', category: 'productivity' },
    google_sheets: { name: 'Google Sheets', icon: 'fas fa-table', color: 'green', category: 'productivity' },
    notion: { name: 'Notion', icon: 'fas fa-book', color: 'gray', category: 'productivity' },
    stripe: { name: 'Stripe', icon: 'fas fa-credit-card', color: 'purple', category: 'payments' },
    facebook_page: { name: 'Facebook Page', icon: 'fab fa-facebook', color: 'indigo', category: 'social' },
    twitter: { name: 'Twitter / X', icon: 'fab fa-twitter', color: 'sky', category: 'social' },
    linkedin: { name: 'LinkedIn', icon: 'fab fa-linkedin', color: 'blue', category: 'social' },
    youtube: { name: 'YouTube', icon: 'fab fa-youtube', color: 'red', category: 'media' },
    shopify: { name: 'Shopify', icon: 'fab fa-shopify', color: 'green', category: 'ecommerce' },
    woocommerce: { name: 'WooCommerce', icon: 'fas fa-shopping-cart', color: 'purple', category: 'ecommerce' },
    slack_webhook: { name: 'Slack Webhook', icon: 'fab fa-slack', color: 'purple', category: 'automation' },
    zapier: { name: 'Zapier', icon: 'fas fa-bolt', color: 'orange', category: 'automation' },
    n8n: { name: 'n8n', icon: 'fas fa-project-diagram', color: 'red', category: 'automation' },
};

let assistantLinkedIntegrations = JSON.parse(localStorage.getItem('asm_linked_integrations') || '{}');

function loadConnectedIntegrations() {
    const container = document.getElementById('connectedIntegrations');
    if (!container) return;
    
    // Get connected integrations from the integrations page
    const connected = JSON.parse(localStorage.getItem('int_connected') || '{}');
    const entries = Object.entries(connected);
    
    if (!entries.length) {
        container.innerHTML = `
            <div class="text-center py-6">
                <i class="fas fa-plug text-3xl text-gray-600 mb-2"></i>
                <p class="text-sm text-gray-400">No integrations connected yet</p>
                <a href="/integrations" target="_blank" class="text-xs text-cyan-400 hover:text-cyan-300 mt-2 inline-block">Go to Integrations page to connect</a>
            </div>`;
        return;
    }

    container.innerHTML = entries.map(([id, acc]) => {
        const svc = INTEGRATION_CATALOG[id] || { name: id, icon: 'fas fa-plug', color: 'gray' };
        const isLinked = assistantLinkedIntegrations[currentAssistantId]?.includes(id);
        return `
        <div class="p-3 glass flex items-center justify-between gap-3" style="border-left: 3px solid ${isLinked ? '#10b981' : '#334155'}">
            <div class="flex items-center gap-3 flex-1 min-w-0">
                <div class="w-10 h-10 rounded-lg bg-${svc.color}-600/20 flex items-center justify-center">
                    <i class="${svc.icon} text-${svc.color}-400"></i>
                </div>
                <div class="min-w-0">
                    <p class="text-sm text-white font-medium truncate">${escapeHtml(acc.name || svc.name)}</p>
                    <p class="text-[10px] text-gray-500">${escapeHtml(svc.category || '')} • Connected</p>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <label class="relative inline-flex items-center cursor-pointer" title="${isLinked ? 'Disable for this assistant' : 'Enable for this assistant'}">
                    <input type="checkbox" ${isLinked ? 'checked' : ''} onchange="toggleLinkedIntegration('${id}', this.checked)" class="sr-only peer">
                    <div class="w-9 h-5 bg-gray-600 rounded-full peer peer-checked:bg-green-500 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-full"></div>
                </label>
            </div>
        </div>`;
    }).join('');
}

function toggleLinkedIntegration(integrationId, enabled) {
    if (!currentAssistantId) return;
    if (!assistantLinkedIntegrations[currentAssistantId]) {
        assistantLinkedIntegrations[currentAssistantId] = [];
    }
    if (enabled) {
        if (!assistantLinkedIntegrations[currentAssistantId].includes(integrationId)) {
            assistantLinkedIntegrations[currentAssistantId].push(integrationId);
        }
        showToast(`Integration enabled for this assistant`);
    } else {
        assistantLinkedIntegrations[currentAssistantId] = assistantLinkedIntegrations[currentAssistantId].filter(id => id !== integrationId);
        showToast(`Integration disabled for this assistant`);
    }
    localStorage.setItem('asm_linked_integrations', JSON.stringify(assistantLinkedIntegrations));
    loadConnectedIntegrations();
}

async function deleteIntegration(id) {
    if (!confirm('Delete this integration?')) return;
    try {
        await api('DELETE', `integrations/${id}`);
        const data = await api('GET', currentAssistantId);
        renderIntegrations(data.integrations || []);
        showToast('Integration deleted');
    } catch (e) { showToast(e.message, 'error'); }
}

async function testIntegration(id) {
    showToast('Testing connection...', 'info');
    try {
        const r = await api('POST', `integrations/${id}/test`);
        if (r.success) showToast('✓ ' + (r.message || 'Connection successful'), 'success');
        else showToast('✗ ' + (r.message || 'Connection failed'), 'error');
        const data = await api('GET', currentAssistantId);
        renderIntegrations(data.integrations || []);
    } catch (e) { showToast(e.message, 'error'); }
}

// ============= Tasks =============

async function populateTaskTypes() {
    try {
        const types = await api('GET', 'task-types');
        const sel = document.getElementById('taskTypeSelect');
        sel.innerHTML = Object.entries(types).map(([k, v]) => `<option value="${k}">${escapeHtml(v.name || k)}</option>`).join('');
    } catch (e) {
        document.getElementById('taskTypeSelect').innerHTML = '<option value="email_read">Read Emails</option>';
    }
}

function openAddTaskModal() { document.getElementById('taskModal').classList.remove('hidden'); }
function closeTaskModal() { document.getElementById('taskModal').classList.add('hidden'); }

document.getElementById('taskForm').addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
        await api('POST', `${currentAssistantId}/tasks`, {
            task_type: fd.get('task_type'),
            name: fd.get('name'),
            schedule: fd.get('schedule')
        });
        showToast('Task added');
        closeTaskModal();
        const data = await api('GET', currentAssistantId);
        renderTasks(data.tasks || []);
    } catch (e) { showToast(e.message, 'error'); }
});

function renderTasks(tasks) {
    const list = document.getElementById('tasksList');
    if (!tasks || !tasks.length) {
        list.innerHTML = '<p class="text-sm text-gray-500">No tasks configured</p>';
        return;
    }
    list.innerHTML = tasks.map(t => `
        <div class="p-3 glass flex items-center justify-between gap-3">
            <div class="flex items-center gap-3 flex-1 min-w-0">
                <div class="w-9 h-9 rounded-lg bg-amber-600/20 flex items-center justify-center"><i class="fas fa-bolt text-amber-400 text-sm"></i></div>
                <div class="min-w-0">
                    <p class="text-sm text-white font-medium truncate">${escapeHtml(t.name || t.task_type)}</p>
                    <p class="text-[10px] text-gray-500">${escapeHtml(t.task_type)} • ${escapeHtml(t.schedule || 'manual')} • ${t.run_count || 0} runs</p>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <button onclick="runTaskNow('${t.id}')" class="btn btn-ghost text-green-400 hover:text-green-300" title="Run now"><i class="fas fa-play text-xs"></i></button>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" ${t.is_active ? 'checked' : ''} onchange="toggleTask('${t.id}', this.checked)" class="sr-only peer">
                    <div class="w-9 h-5 bg-gray-600 rounded-full peer peer-checked:bg-amber-500 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-full"></div>
                </label>
                <button onclick="deleteTask('${t.id}')" class="btn btn-ghost text-gray-500 hover:text-red-400"><i class="fas fa-trash text-xs"></i></button>
            </div>
        </div>
    `).join('');
}

async function runTaskNow(taskId) {
    try {
        await api('POST', `tasks/${taskId}/run`);
        showToast('Task triggered');
        const data = await api('GET', currentAssistantId);
        renderTasks(data.tasks || []);
    } catch (e) { showToast(e.message, 'error'); }
}

async function toggleTask(id, active) {
    try {
        await api('PUT', `tasks/${id}`, { is_active: active });
    } catch (e) { showToast(e.message, 'error'); }
}

async function deleteTask(taskId) {
    if (!confirm('Delete this task?')) return;
    try {
        await api('DELETE', `tasks/${taskId}`);
        const data = await api('GET', currentAssistantId);
        renderTasks(data.tasks || []);
        showToast('Task deleted');
    } catch (e) { showToast(e.message, 'error'); }
}

// ============= Analytics =============

function renderAnalytics(data) {
    document.getElementById('anaConversations').textContent = (data.conversations || []).length;
    let msgCount = 0;
    (data.conversations || []).forEach(c => { msgCount += c.message_count || 0; });
    document.getElementById('anaMessages').textContent = msgCount;
    const tokens = (data.recent_logs || []).reduce((s, l) => s + (l.tokens_used || 0), 0);
    document.getElementById('anaTokens').textContent = tokens.toLocaleString();
    const runs = (data.tasks || []).reduce((s, t) => s + (t.run_count || 0), 0);
    document.getElementById('anaTasksRun').textContent = runs;
    const byDay = {};
    (data.recent_logs || []).forEach(l => {
        const day = (l.created_at || '').slice(0, 10);
        if (day) byDay[day] = (byDay[day] || 0) + 1;
    });
    const days = Object.keys(byDay).sort().slice(-14);
    const counts = days.map(d => byDay[d]);
    const ctx = document.getElementById('activityChart');
    if (!ctx) return;
    if (activityChart) activityChart.destroy();
    activityChart = new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: {
            labels: days,
            datasets: [{
                label: 'Activity',
                data: counts,
                borderColor: '#8b5cf6',
                backgroundColor: 'rgba(139, 92, 246, 0.15)',
                fill: true,
                tension: 0.35,
                pointRadius: 4,
                pointBackgroundColor: '#06b6d4'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.08)' } },
                y: { beginAtZero: true, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.08)' } }
            }
        }
    });
}

// ============= Logs =============

function renderLogs(logs) {
    const list = document.getElementById('logsList');
    if (!list) return;
    if (!logs || !logs.length) {
        list.innerHTML = '<p class="text-sm text-gray-500">No activity yet</p>';
        return;
    }
    list.innerHTML = logs.map(l => {
        const color = l.status === 'success' ? 'green' : l.status === 'error' ? 'red' : 'gray';
        const icon = l.action.startsWith('run_task') ? 'fa-bolt' : l.action === 'chat' ? 'fa-comment' : 'fa-circle';
        return `
        <div class="p-3 glass flex items-start gap-3">
            <div class="w-8 h-8 rounded-lg bg-${color}-600/20 flex items-center justify-center flex-shrink-0"><i class="fas ${icon} text-${color}-400 text-xs"></i></div>
            <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between mb-1">
                    <span class="text-sm text-white">${escapeHtml(l.action)}</span>
                    <span class="text-[10px] text-gray-500">${(l.created_at || '').slice(0, 16)}</span>
                </div>
                ${l.input_text ? `<p class="text-xs text-gray-400 truncate">${escapeHtml(l.input_text)}</p>` : ''}
                <div class="flex items-center gap-3 mt-1 text-[10px] text-gray-500">
                    <span class="text-${color}-400">${escapeHtml(l.status)}</span>
                    ${l.tokens_used ? `<span>${l.tokens_used} tokens</span>` : ''}
                    ${l.duration_ms ? `<span>${l.duration_ms}ms</span>` : ''}
                </div>
            </div>
        </div>`;
    }).join('');
}

// ============= Monitors (Mr. Robot style) =============
let assistantMonitors = JSON.parse(localStorage.getItem('asm_monitors') || '{}');

function initMonitorsTab() {
    if (!currentAssistantId) return;
    const monitors = assistantMonitors[currentAssistantId] || [];
    const el = document.getElementById('assistantMonitorsList');
    if (monitors.length === 0) {
        el.innerHTML = `<div class="text-center text-gray-500 py-6">
            <i class="fas fa-eye-slash text-2xl mb-2 text-gray-600"></i>
            <p class="text-xs">No monitors configured for this assistant</p>
            <p class="text-xs text-gray-600 mt-1">Click "Add Monitor" or use quick presets above</p>
        </div>`;
        return;
    }
    el.innerHTML = monitors.map(m => `
        <div class="glass p-4 rounded-xl" style="border-left: 3px solid ${m.active ? '#10b981' : '#6b7280'}">
            <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-lg flex items-center justify-center ${m.type === 'facebook' ? 'bg-blue-600/20' : m.type === 'ecommerce' ? 'bg-green-600/20' : 'bg-cyan-600/20'}">
                        <i class="${m.type === 'facebook' ? 'fab fa-facebook' : m.type === 'ecommerce' ? 'fas fa-shopping-cart' : 'fas fa-globe'} ${m.type === 'facebook' ? 'text-blue-400' : m.type === 'ecommerce' ? 'text-green-400' : 'text-cyan-400'}"></i>
                    </div>
                    <div>
                        <p class="text-white text-sm font-medium">${escapeHtml(m.name)}</p>
                        <p class="text-[10px] text-gray-500">${escapeHtml(m.url || '').substring(0, 50)}</p>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full ${m.active ? 'bg-green-400' : 'bg-gray-500'} ${m.active ? 'animate-pulse' : ''}"></span>
                    <button onclick="toggleAssistantMonitor('${m.id}')" class="px-2 py-1 bg-${m.active ? 'green' : 'gray'}-600/20 text-${m.active ? 'green' : 'gray'}-400 rounded text-[10px]">
                        ${m.active ? 'Active' : 'Paused'}
                    </button>
                    <button onclick="deleteAssistantMonitor('${m.id}')" class="px-2 py-1 bg-red-600/20 text-red-400 rounded text-[10px]"><i class="fas fa-trash"></i></button>
                </div>
            </div>
            <div class="flex flex-wrap gap-2 mt-2">
                <span class="text-[10px] px-2 py-1 bg-white/5 rounded text-gray-400"><i class="fas fa-clock mr-1"></i>Every ${m.interval || 15}m</span>
                <span class="text-[10px] px-2 py-1 bg-white/5 rounded text-gray-400"><i class="fas fa-bell mr-1"></i>${m.notify || 'WhatsApp'}</span>
                ${m.keywords ? `<span class="text-[10px] px-2 py-1 bg-amber-600/10 rounded text-amber-400"><i class="fas fa-key mr-1"></i>${escapeHtml(m.keywords.split(',')[0])}</span>` : ''}
            </div>
        </div>
    `).join('');
}

function openAddMonitorModal() {
    document.getElementById('addMonitorModal')?.classList.remove('hidden');
}

function closeAddMonitorModal() {
    document.getElementById('addMonitorModal')?.classList.add('hidden');
}

function createQuickMonitor(type) {
    if (!currentAssistantId) { showToast('Open an assistant first', 'error'); return; }
    const preset = {
        facebook: { name: 'Facebook Page Monitor', type: 'facebook', url: 'https://facebook.com/', keywords: 'new post,like,comment,share', interval: 30, notify: 'whatsapp' },
        ecommerce: { name: 'E-commerce Monitor', type: 'ecommerce', url: '', keywords: 'sale,discount,price drop,offer', interval: 60, notify: 'whatsapp' },
        website: { name: 'Website Monitor', type: 'website', url: '', keywords: 'update,change,new', interval: 15, notify: 'whatsapp' }
    };
    const p = preset[type];
    if (!p) return;

    if (!assistantMonitors[currentAssistantId]) assistantMonitors[currentAssistantId] = [];
    assistantMonitors[currentAssistantId].push({
        id: 'm_' + Date.now(),
        ...p,
        active: true,
        created: new Date().toISOString()
    });
    localStorage.setItem('asm_monitors', JSON.stringify(assistantMonitors));
    initMonitorsTab();
    showToast(`${p.name} created!`);
}

function toggleAssistantMonitor(id) {
    if (!currentAssistantId || !assistantMonitors[currentAssistantId]) return;
    const m = assistantMonitors[currentAssistantId].find(m => m.id === id);
    if (m) {
        m.active = !m.active;
        localStorage.setItem('asm_monitors', JSON.stringify(assistantMonitors));
        initMonitorsTab();
    }
}

function deleteAssistantMonitor(id) {
    if (!currentAssistantId || !assistantMonitors[currentAssistantId]) return;
    if (!confirm('Delete this monitor?')) return;
    assistantMonitors[currentAssistantId] = assistantMonitors[currentAssistantId].filter(m => m.id !== id);
    localStorage.setItem('asm_monitors', JSON.stringify(assistantMonitors));
    initMonitorsTab();
    showToast('Monitor deleted');
}

// ============= Task Execution Commands =============
let assistantTodos = JSON.parse(localStorage.getItem('asm_todos') || '[]');
let assistantReminders = JSON.parse(localStorage.getItem('asm_reminders') || '[]');
let assistantSchedules = JSON.parse(localStorage.getItem('asm_schedules') || '[]');

function saveTodos() { localStorage.setItem('asm_todos', JSON.stringify(assistantTodos)); }
function saveReminders() { localStorage.setItem('asm_reminders', JSON.stringify(assistantReminders)); }
function saveSchedules() { localStorage.setItem('asm_schedules', JSON.stringify(assistantSchedules)); }

function detectCommand(text) {
    const t = text.toLowerCase().trim();
    if (/^(show|get|tell me|what's|whats).*(weather|temperature|forecast)/i.test(t)) return {cmd: 'weather', args: t};
    if (/^(add|set|create|new).*(todo|task|to-do)/i.test(t) || /add.*to.*(list|todo|tasks)/i.test(t)) return {cmd: 'todo_add', args: t};
    if (/^(show|list|view|get).*(todo|task|to-do|list)/i.test(t)) return {cmd: 'todo_list', args: t};
    if (/^(remind|set reminder|add reminder|reminder)/i.test(t)) return {cmd: 'reminder_add', args: t};
    if (/^(show|list|view).*(reminder|reminders)/i.test(t)) return {cmd: 'reminder_list', args: t};
    if (/^(show|get|read|latest).*(whatsapp|wa|message|messages|chat)/i.test(t)) return {cmd: 'wa_messages', args: t};
    if (/^(reply|send).*(mail|email)/i.test(t)) return {cmd: 'mail_reply', args: t};
    if (/^(schedule|set.*schedule|add.*schedule|every.*read|every.*post)/i.test(t)) return {cmd: 'schedule_add', args: t};
    if (/^(show|list|view).*(schedule|schedules|tasks)/i.test(t)) return {cmd: 'schedule_list', args: t};
    if (/^(what|what's|tell me|show).*(time|date|day)/i.test(t)) return {cmd: 'datetime', args: t};
    return null;
}

async function executeCommand(cmd, text) {
    const el = document.getElementById('chatMessages');
    let responseHtml = '';

    switch(cmd.cmd) {
        case 'datetime': {
            const now = new Date();
            responseHtml = `<div class="chat-bubble assistant"><p><i class="fas fa-clock text-cyan-400 mr-2"></i><b>${now.toLocaleDateString([], {weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'})}</b></p><p class="text-sm text-gray-400 mt-1">${now.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}</p></div>`;
            break;
        }
        case 'todo_add': {
            const taskText = text.replace(/^(add|set|create|new)\s*(to my |a |the )?(todo|task|to-do|list)/i, '').replace(/^(list|to-do|todo|task)/i, '').trim().replace(/^(to|as|is)\s+/i, '');
            if (!taskText) { responseHtml = errorBubble('Please specify the task. Example: "add buy milk to my todo list"'); break; }
            assistantTodos.push({id: Date.now(), task: taskText, done: false, created: new Date().toISOString()});
            saveTodos();
            responseHtml = successBubble(`Added to todo list: <b>${escapeHtml(taskText)}</b><br><span class="text-xs text-gray-400">${assistantTodos.filter(t=>!t.done).length} pending tasks</span>`);
            break;
        }
        case 'todo_list': {
            const pending = assistantTodos.filter(t => !t.done);
            const done = assistantTodos.filter(t => t.done);
            if (pending.length === 0 && done.length === 0) {
                responseHtml = infoBubble('Your todo list is empty. Say "add [task] to my todo list" to get started.');
            } else {
                let html = '<div class="chat-bubble assistant"><p class="font-semibold mb-2"><i class="fas fa-list-check text-green-400 mr-2"></i>Your Todo List</p>';
                pending.forEach((t, i) => {
                    html += `<div class="flex items-center gap-2 py-1 border-b border-gray-700/30"><input type="checkbox" onchange="toggleTodo(${t.id})" class="accent-green-500"><span class="text-sm text-white">${escapeHtml(t.task)}</span><button onclick="deleteTodo(${t.id})" class="ml-auto text-red-400 hover:text-red-300 text-xs"><i class="fas fa-trash"></i></button></div>`;
                });
                if (done.length > 0) {
                    html += `<p class="text-xs text-gray-500 mt-2">${done.length} completed</p>`;
                }
                html += '</div>';
                responseHtml = html;
            }
            break;
        }
        case 'reminder_add': {
            const reminderText = text.replace(/^(remind me to|remind|set reminder|add reminder|set a reminder to|reminder to)/i, '').trim();
            const timeMatch = text.match(/(in|at|on)\s+(\d+)\s*(minute|min|hour|hr|day)|(tomorrow|today|tonight)/i);
            let when = 'soon';
            if (timeMatch) when = timeMatch[0];
            else if (/tomorrow/i.test(text)) when = 'tomorrow';
            else if (/tonight/i.test(text)) when = 'tonight';
            if (!reminderText || reminderText.length < 3) { responseHtml = errorBubble('Please specify the reminder. Example: "remind me to call John at 3pm"'); break; }
            const r = {id: Date.now(), text: reminderText, when: when, done: false, created: new Date().toISOString()};
            assistantReminders.push(r);
            saveReminders();
            setTimeout(() => {
                showToast('⏰ Reminder: ' + reminderText, 'info');
            }, 60000);
            responseHtml = successBubble(`Reminder set ${when}: <b>${escapeHtml(reminderText)}</b><br><span class="text-xs text-gray-400">I'll notify you when it's time</span>`);
            break;
        }
        case 'reminder_list': {
            if (assistantReminders.length === 0) {
                responseHtml = infoBubble('No reminders. Say "remind me to [task]" to set one.');
            } else {
                let html = '<div class="chat-bubble assistant"><p class="font-semibold mb-2"><i class="fas fa-bell text-amber-400 mr-2"></i>Your Reminders</p>';
                assistantReminders.filter(r => !r.done).forEach(r => {
                    html += `<div class="flex items-center gap-2 py-1 border-b border-gray-700/30"><i class="fas fa-clock text-amber-400 text-xs"></i><span class="text-sm text-white">${escapeHtml(r.text)}</span><span class="text-xs text-gray-500 ml-auto">${escapeHtml(r.when)}</span><button onclick="deleteReminder(${r.id})" class="text-red-400 hover:text-red-300 text-xs ml-2"><i class="fas fa-trash"></i></button></div>`;
                });
                html += '</div>';
                responseHtml = html;
            }
            break;
        }
        case 'wa_messages': {
            try {
                const r = await fetch('/api/integrations/whatsapp/messages');
                const d = await r.json();
                const msgs = (d.messages || []).slice(-5).reverse();
                if (msgs.length === 0) {
                    responseHtml = infoBubble('No recent WhatsApp messages. Connect WhatsApp first.');
                } else {
                    let html = '<div class="chat-bubble assistant"><p class="font-semibold mb-2"><i class="fab fa-whatsapp text-green-400 mr-2"></i>Latest WhatsApp Messages</p>';
                    msgs.forEach(m => {
                        const who = m.from_name || (m.from || '').replace('@c.us','');
                        const text = m.text || (m.type ? '[' + m.type + ']' : '(media)');
                        html += `<div class="py-1.5 border-b border-gray-700/30"><p class="text-xs text-gray-400">${escapeHtml(who)}</p><p class="text-sm text-white">${escapeHtml(text).substring(0, 80)}</p></div>`;
                    });
                    html += '</div>';
                    responseHtml = html;
                }
            } catch(e) { responseHtml = errorBubble('Could not fetch WhatsApp: ' + e.message); }
            break;
        }
        case 'mail_reply': {
            responseHtml = infoBubble('Mail reply requires an email integration to be configured. Open <a href="/integrations" class="text-cyan-400 underline">Integrations</a> to set up email.');
            break;
        }
        case 'schedule_add': {
            const scheduleText = text.replace(/^(schedule|set.*schedule|add.*schedule|every)/i, '').trim();
            if (!scheduleText) { responseHtml = errorBubble('Please describe the schedule. Example: "every morning read new tech news and highlight"'); break; }
            const s = {id: Date.now(), task: scheduleText, active: true, created: new Date().toISOString(), lastRun: null};
            assistantSchedules.push(s);
            saveSchedules();
            responseHtml = successBubble(`Schedule added: <b>${escapeHtml(scheduleText)}</b><br><span class="text-xs text-gray-400">I'll execute this on a recurring basis. View all schedules with "show my schedules"</span>`);
            break;
        }
        case 'schedule_list': {
            if (assistantSchedules.length === 0) {
                responseHtml = infoBubble('No schedules. Say "schedule [task]" to add a recurring task.');
            } else {
                let html = '<div class="chat-bubble assistant"><p class="font-semibold mb-2"><i class="fas fa-calendar-check text-purple-400 mr-2"></i>Your Schedules</p>';
                assistantSchedules.forEach(s => {
                    html += `<div class="flex items-center gap-2 py-1.5 border-b border-gray-700/30"><i class="fas fa-${s.active ? 'play text-green-400' : 'pause text-gray-500'} text-xs"></i><span class="text-sm text-white">${escapeHtml(s.task)}</span><button onclick="toggleSchedule(${s.id})" class="ml-auto text-xs text-gray-400 hover:text-white">${s.active ? 'Pause' : 'Resume'}</button><button onclick="deleteSchedule(${s.id})" class="text-red-400 hover:text-red-300 text-xs ml-2"><i class="fas fa-trash"></i></button></div>`;
                });
                html += '</div>';
                responseHtml = html;
            }
            break;
        }
        case 'weather': {
            try {
                const r = await fetch('https://wttr.in/?format=j1');
                if (r.ok) {
                    const d = await r.json();
                    const cur = d.current_condition && d.current_condition[0];
                    if (cur) {
                        responseHtml = `<div class="chat-bubble assistant"><p class="font-semibold mb-2"><i class="fas fa-cloud-sun text-amber-400 mr-2"></i>Current Weather</p><p class="text-sm text-white">${escapeHtml(cur.weatherDesc[0].value)}, ${cur.temp_C}°C / ${cur.temp_F}°F</p><p class="text-xs text-gray-400 mt-1">Humidity: ${cur.humidity}% · Wind: ${cur.windspeedKmph} km/h</p></div>`;
                    } else { responseHtml = infoBubble('Weather data not available.'); }
                } else { throw new Error('API error'); }
            } catch(e) {
                responseHtml = infoBubble('Weather API unavailable. Try again later.');
            }
            break;
        }
        default:
            return null;
    }

    document.getElementById('typingBubble')?.remove();
    el.innerHTML += `<div class="flex justify-start mb-4 chat-message">${responseHtml}</div>`;
    el.scrollTop = el.scrollHeight;
    return true;
}

function successBubble(msg) { return `<div class="chat-bubble assistant" style="background:rgba(16,185,129,0.15);border-color:#10b981;"><p class="text-sm text-white">${msg}</p></div>`; }
function infoBubble(msg) { return `<div class="chat-bubble assistant" style="background:rgba(6,182,212,0.15);border-color:#06b6d4;"><p class="text-sm text-white">${msg}</p></div>`; }
function errorBubble(msg) { return `<div class="chat-bubble assistant" style="background:rgba(239,68,68,0.15);border-color:#ef4444;"><p class="text-sm text-white"><i class="fas fa-exclamation-triangle mr-2"></i>${msg}</p></div>`; }

function toggleTodo(id) {
    const t = assistantTodos.find(x => x.id === id);
    if (t) { t.done = !t.done; saveTodos(); }
}
function deleteTodo(id) {
    assistantTodos = assistantTodos.filter(x => x.id !== id);
    saveTodos();
    showToast('Todo deleted');
}
function deleteReminder(id) {
    assistantReminders = assistantReminders.filter(x => x.id !== id);
    saveReminders();
    showToast('Reminder deleted');
}
function toggleSchedule(id) {
    const s = assistantSchedules.find(x => x.id === id);
    if (s) { s.active = !s.active; saveSchedules(); }
}
function deleteSchedule(id) {
    assistantSchedules = assistantSchedules.filter(x => x.id !== id);
    saveSchedules();
    showToast('Schedule deleted');
}

// ============= Init =============

function quickCommand(text) {
    const input = document.getElementById('chatInput');
    if (input) {
        input.value = text;
        input.focus();
        sendMessage();
    }
}
['createModal', 'detailModal', 'settingsModal', 'integrationModal', 'taskModal', 'addMonitorModal'].forEach(id => {
    const m = document.getElementById(id);
    if (m) m.addEventListener('click', e => { if (e.target === m) {
        if (id === 'createModal') closeCreateModal();
        else if (id === 'settingsModal') closeSettingsPanel();
        else if (id === 'integrationModal') closeIntegrationModal();
        else if (id === 'taskModal') closeTaskModal();
        else if (id === 'addMonitorModal') closeAddMonitorModal();
    }});
});

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
        if (!document.getElementById('createModal').classList.contains('hidden')) closeCreateModal();
        else if (!document.getElementById('settingsModal').classList.contains('hidden')) closeSettingsPanel();
        else if (!document.getElementById('integrationModal').classList.contains('hidden')) closeIntegrationModal();
        else if (!document.getElementById('taskModal').classList.contains('hidden')) closeTaskModal();
        else if (!document.getElementById('detailModal').classList.contains('hidden')) closeDetailModal();
    }
});

init();
