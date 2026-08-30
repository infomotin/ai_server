/* OpenLocalAI — AI Assistants v2 (modern UI) */

const PROXY = '/api/assistants/proxy';
let currentAssistant = null;
let currentAssistantId = null;
let currentConversationId = null;
let conversations = [];
let currentTab = 'chat';
let activityChart = null;
let isGenerating = false;
let abortController = null;
let availableModels = ['llama3.2:1b', 'qwen2.5:0.5b', 'phi3:mini', 'codellama:3.5', 'mistral-nemo'];

const TEMPLATES = {
    email: { name: 'Email Assistant', icon: 'fas fa-envelope', color: 'blue', desc: 'Read, draft, and reply to emails',
        caps: ['Read incoming emails', 'Draft professional replies', 'Send responses', 'Summarize threads', 'Filter important emails'],
        prompts: [
            { text: "Hi, my name is John", icon: 'fa-hand-wave' },
            { text: 'Show me new emails today', icon: 'fa-envelope-open' },
            { text: 'Reply to my unread emails', icon: 'fa-reply-all' },
            { text: 'Summarize my inbox', icon: 'fa-list' },
            { text: 'Draft email to team about meeting', icon: 'fa-paper-plane' }
        ]
    },
    whatsapp: { name: 'WhatsApp Assistant', icon: 'fab fa-whatsapp', color: 'green', desc: 'Read and reply to WhatsApp messages',
        caps: ['Read messages', 'Send replies', 'Voice-to-text', 'Message summarization', 'Auto-reply'],
        prompts: [
            { text: 'Hi, my name is John', icon: 'fa-hand-wave' },
            { text: 'Show me new WhatsApp messages', icon: 'fa-comment-dots' },
            { text: 'Reply to unread messages', icon: 'fa-reply' },
            { text: 'Send message to Mom', icon: 'fa-paper-plane' }
        ]
    },
    facebook: { name: 'Facebook Assistant', icon: 'fab fa-facebook', color: 'indigo', desc: 'Manage Facebook posts',
        caps: ['Read posts', 'Draft replies', 'Create posts', 'Manage comments', 'Analytics'],
        prompts: [
            { text: 'Hi, my name is John', icon: 'fa-hand-wave' },
            { text: 'Show me new Facebook posts', icon: 'fa-newspaper' },
            { text: 'Reply to recent comments', icon: 'fa-comment' },
            { text: 'Create a post about AI', icon: 'fa-plus-square' }
        ]
    },
    web_research: { name: 'Web Research', icon: 'fas fa-globe', color: 'cyan', desc: 'Search and summarize web content',
        caps: ['Web search', 'Page reading', 'Content summarization', 'Fact checking', 'Source verification'],
        prompts: [
            { text: 'Search for latest AI news', icon: 'fa-search' },
            { text: 'Read and summarize this URL', icon: 'fa-book-reader' },
            { text: 'Compare AI models', icon: 'fa-balance-scale' }
        ]
    },
    calendar: { name: 'Calendar Assistant', icon: 'fas fa-calendar', color: 'amber', desc: 'Manage calendar events and reminders',
        caps: ['Set reminders', 'Create events', 'Manage schedule', 'Send notifications', 'Time zone handling'],
        prompts: [
            { text: "Hi, I'm John's assistant", icon: 'fa-hand-wave' },
            { text: 'Schedule meeting tomorrow at 3pm', icon: 'fa-calendar-plus' },
            { text: "What's on my calendar today?", icon: 'fa-calendar-alt' },
            { text: 'Set reminder for dentist appointment', icon: 'fa-bell' }
        ]
    },
    git: { name: 'Git Assistant', icon: 'fab fa-git-alt', color: 'red', desc: 'Manage git repositories and code',
        caps: ['Read repos', 'Explain code', 'Create commits', 'Manage branches', 'Code review'],
        prompts: [
            { text: 'Show recent commits', icon: 'fa-code-commit' },
            { text: 'Create a new branch', icon: 'fa-code-branch' },
            { text: 'Review my last PR', icon: 'fa-code-pull-request' }
        ]
    },
    code: { name: 'Code Assistant', icon: 'fas fa-code', color: 'purple', desc: 'Read, explain, and write code',
        caps: ['Code explanation', 'Code generation', 'Bug fixing', 'Refactoring', 'Documentation'],
        prompts: [
            { text: 'Write a Python function to parse JSON', icon: 'fa-file-code' },
            { text: 'Explain this code snippet', icon: 'fa-code' },
            { text: 'Find bugs in my code', icon: 'fa-bug' },
            { text: 'Refactor for readability', icon: 'fa-broom' }
        ]
    },
    data: { name: 'Data Analysis', icon: 'fas fa-chart-line', color: 'teal', desc: 'Analyze data and generate reports',
        caps: ['Data analysis', 'Chart generation', 'Report creation', 'Pattern detection', 'Predictions'],
        prompts: [
            { text: 'Analyze my sales data', icon: 'fa-chart-line' },
            { text: 'Create a weekly report', icon: 'fa-file-alt' },
            { text: 'Show me the trends', icon: 'fa-chart-bar' }
        ]
    },
    customer: { name: 'Support Assistant', icon: 'fas fa-headset', color: 'orange', desc: 'Handle customer inquiries and support',
        caps: ['Answer questions', 'Ticket management', 'Escalation', 'Knowledge base', 'Sentiment analysis'],
        prompts: [
            { text: 'Hi, my name is John', icon: 'fa-hand-wave' },
            { text: 'Show open support tickets', icon: 'fa-ticket-alt' },
            { text: 'Reply to customer inquiries', icon: 'fa-headset' }
        ]
    },
    writer: { name: 'Creative Writer', icon: 'fas fa-pen-fancy', color: 'pink', desc: 'Help with creative writing and content',
        caps: ['Blog posts', 'Story writing', 'Copywriting', 'Editing', 'SEO content'],
        prompts: [
            { text: 'Write a blog intro on AI', icon: 'fa-pen' },
            { text: 'Make this paragraph more engaging', icon: 'fa-marker' },
            { text: 'Suggest 5 catchy titles', icon: 'fa-lightbulb' }
        ]
    },
    translator: { name: 'Translator', icon: 'fas fa-language', color: 'yellow', desc: 'Translate text between languages',
        caps: ['Multi-language translation', 'Context preservation', 'Idioms', 'Formal/informal tone'],
        prompts: [
            { text: 'Translate to Spanish', icon: 'fa-language' },
            { text: 'Translate to French (formal)', icon: 'fa-flag' },
            { text: 'Explain this phrase', icon: 'fa-circle-question' }
        ]
    },
    tutor: { name: 'Personal Tutor', icon: 'fas fa-graduation-cap', color: 'lime', desc: 'Explain concepts and help you learn',
        caps: ['Concept explanation', 'Quiz generation', 'Step-by-step walkthroughs', 'Examples', 'Analogies'],
        prompts: [
            { text: 'Explain quantum computing simply', icon: 'fa-atom' },
            { text: 'Quiz me on world capitals', icon: 'fa-circle-question' },
            { text: 'Walk me through photosynthesis', icon: 'fa-leaf' }
        ]
    },
    custom: { name: 'Custom Assistant', icon: 'fas fa-user-gear', color: 'gray', desc: 'Build your own custom assistant',
        caps: ['Custom tasks', 'Custom integrations', 'Custom workflows', 'Flexible configuration'],
        prompts: [
            { text: 'Hi, my name is John', icon: 'fa-hand-wave' },
            { text: 'What can you help me with?', icon: 'fa-circle-question' }
        ]
    }
};

const TASK_TYPES = {
    email_read: 'Read Emails', email_reply: 'Reply to Email', email_summary: 'Summarize Emails',
    whatsapp_read: 'Read Messages', whatsapp_reply: 'Reply to Message',
    facebook_read: 'Read Posts', facebook_post: 'Create Post',
    web_search: 'Web Search', web_read: 'Read Web Page', web_summarize: 'Summarize Content',
    reminder_set: 'Set Reminder', event_create: 'Create Event',
    git_read: 'Read Repository', git_commit: 'Create Commit', git_explain: 'Explain Code',
    code_write: 'Write Code', code_review: 'Review Code',
    data_analyze: 'Analyze Data', report_create: 'Create Report',
    ticket_handle: 'Handle Ticket', customer_reply: 'Reply to Customer',
    custom_task: 'Custom Task'
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
    document.getElementById('toastContainer').appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .3s'; setTimeout(() => t.remove(), 300); }, 3000);
}

async function api(method, path, body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body !== null) opts.body = JSON.stringify(body);
    const resp = await fetch(PROXY + '/' + path, opts);
    let data;
    try { data = await resp.json(); } catch { data = { error: 'Invalid response' }; }
    if (resp.status === 401) {
        showToast('Session expired — redirecting to login', 'error');
        setTimeout(() => { window.location.href = '/login'; }, 800);
        throw new Error('Session expired');
    }
    if (!resp.ok) throw new Error(data.detail || data.error || 'Request failed');
    return data;
}

// ============= Init =============

document.getElementById('createForm').addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = Object.fromEntries(fd.entries());
    payload.tags = payload.tags ? payload.tags.split(',').map(t => t.trim()).filter(Boolean) : [];
    payload.temperature = payload.temperature ? parseFloat(payload.temperature) : null;
    payload.max_tokens = payload.max_tokens ? parseInt(payload.max_tokens) : null;
    Object.keys(payload).forEach(k => { if (payload[k] === '' || payload[k] === null) delete payload[k]; });
    try {
        await api('POST', '', payload);
        showToast('Assistant created!');
        closeCreateModal();
        setTimeout(() => location.reload(), 400);
    } catch (err) {
        showToast(err.message, 'error');
    }
});

document.addEventListener('DOMContentLoaded', async () => {
    renderTemplateGrid();
    populateTaskTypes();
    populateIntegrationTypes();
    await loadAvailableModels();
    populateModels();
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            ['createModal', 'detailModal', 'taskModal', 'integrationModal'].forEach(id => {
                const m = document.getElementById(id);
                if (m && !m.classList.contains('hidden')) m.classList.add('hidden');
            });
        }
    });
    ['createModal', 'detailModal', 'taskModal', 'integrationModal'].forEach(id => {
        const m = document.getElementById(id);
        if (m) m.addEventListener('click', e => { if (e.target === m) m.classList.add('hidden'); });
    });
});

async function loadAvailableModels() {
    try {
        const resp = await fetch('/api/models');
        if (resp.ok) {
            const data = await resp.json();
            if (Array.isArray(data) && data.length) {
                availableModels = data.map(m => m.id || m.name).filter(Boolean);
            } else if (data && Array.isArray(data.data)) {
                availableModels = data.data.map(m => m.id).filter(Boolean);
            }
        }
    } catch (e) { /* keep defaults */ }
}

function populateModels() {
    const opts = availableModels.map(m => `<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`).join('');
    ['formModel', 'setModel'].forEach(id => {
        const sel = document.getElementById(id);
        if (sel) sel.innerHTML = opts;
    });
}

function renderTemplateGrid() {
    const grid = document.getElementById('templateGrid');
    grid.innerHTML = Object.entries(TEMPLATES).map(([key, t]) => `
        <div class="template-card" data-template="${key}" onclick="selectTemplate('${key}')">
            <i class="${t.icon} text-lg mb-1 text-purple-400"></i>
            <p class="text-[10px] text-white font-medium leading-tight">${escapeHtml(t.name.replace(' Assistant', ''))}</p>
        </div>
    `).join('');
    selectTemplate('email');
}

function selectTemplate(key) {
    const t = TEMPLATES[key];
    if (!t) return;
    document.getElementById('formTemplate').value = key;
    document.getElementById('formIcon').value = t.icon;
    document.querySelectorAll('.template-card').forEach(c => c.classList.remove('active'));
    document.querySelector(`[data-template="${key}"]`)?.classList.add('active');
    document.getElementById('formName').value = t.name;
    document.getElementById('formDescription').value = t.desc;
    document.getElementById('capabilitiesContent').innerHTML = `
        <p class="text-gray-300 text-xs mb-2">${escapeHtml(t.desc)}</p>
        <ul class="space-y-1">
            ${t.caps.map(c => `<li class="flex items-start gap-1.5"><i class="fas fa-check text-${t.color}-400 mt-0.5 text-[10px]"></i><span>${escapeHtml(c)}</span></li>`).join('')}
        </ul>
    `;
}

function populateTaskTypes() {
    const sel = document.getElementById('taskTypeSelect');
    sel.innerHTML = Object.entries(TASK_TYPES).map(([k, v]) => `<option value="${k}">${escapeHtml(v)}</option>`).join('');
}

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

// ============= List view / filter =============

function setView(view) {
    const c = document.getElementById('assistantsContainer');
    if (!c) return;
    if (view === 'list') c.classList.add('list-view'); else c.classList.remove('list-view');
    document.getElementById('gridViewBtn').classList.toggle('active', view === 'grid');
    document.getElementById('listViewBtn').classList.toggle('active', view === 'list');
}

function filterAssistants() {
    const q = (document.getElementById('searchInput')?.value || '').toLowerCase();
    document.querySelectorAll('.assistant-card').forEach(card => {
        card.style.display = card.dataset.name.includes(q) ? '' : 'none';
    });
}

// ============= Create Modal =============

function openCreateModal() {
    document.getElementById('createModal').classList.remove('hidden');
    selectTemplate('email');
}
function closeCreateModal() { document.getElementById('createModal').classList.add('hidden'); }

function quickDelete(id, name) {
    if (!confirm(`Delete assistant "${name}"?`)) return;
    api('DELETE', id).then(() => { showToast('Assistant deleted'); setTimeout(() => location.reload(), 500); })
        .catch(e => showToast(e.message, 'error'));
}

// ============= Detail Modal =============

async function openAssistant(id) {
    currentAssistantId = id;
    currentConversationId = null;
    document.getElementById('detailModal').classList.remove('hidden');
    document.getElementById('chatScroll').innerHTML = `<div class="empty-state"><i class="fas fa-spinner fa-spin text-2xl"></i></div>`;
    try {
        const data = await api('GET', id);
        currentAssistant = data;
        document.getElementById('detailName').textContent = data.assistant.name;
        document.getElementById('detailSubtitle').textContent = `${data.assistant.model_id} • ${data.assistant.personality}`;
        document.getElementById('detailAvatar').innerHTML = `<i class="${data.assistant.avatar || 'fas fa-robot'} text-purple-300 text-lg"></i>`;
        document.getElementById('chatModelLabel').textContent = data.assistant.model_id;
        conversations = data.conversations || [];
        renderConversations();
        renderQuickPrompts();
        populateInfo(data);
        renderTasks(data.tasks);
        renderIntegrations(data.integrations);
        renderLogs(data.recent_logs);
        renderAnalytics(data);
        const tmplKey = guessTemplate(data.assistant);
        renderQuickPrompts(TEMPLATES[tmplKey] || TEMPLATES.custom);
        if (conversations.length > 0) {
            await loadConversation(conversations[0].id);
        } else {
            document.getElementById('chatScroll').innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-comments text-5xl text-gray-600 mb-4"></i>
                    <p class="text-sm mb-4">Start a new conversation with ${escapeHtml(data.assistant.name)}</p>
                    <button onclick="sendSuggestedPrompt('Hello, introduce yourself')" class="btn btn-primary text-xs"><i class="fas fa-hand-wave mr-1"></i>Say Hello</button>
                </div>
            `;
        }
        setTab('chat');
    } catch (e) {
        showToast(e.message, 'error');
        closeDetailModal();
    }
}

function guessTemplate(a) {
    for (const [k, t] of Object.entries(TEMPLATES)) {
        if (t.icon === a.avatar || t.desc === a.description) return k;
    }
    return 'custom';
}

function closeDetailModal() {
    document.getElementById('detailModal').classList.add('hidden');
    if (isGenerating) stopGeneration();
}

function setTab(tab) {
    currentTab = tab;
    ['chat', 'info', 'tasks', 'integrations', 'analytics', 'logs'].forEach(t => {
        document.getElementById(`panel${t.charAt(0).toUpperCase() + t.slice(1)}`).classList.toggle('hidden', t !== tab);
        document.getElementById(`tab${t.charAt(0).toUpperCase() + t.slice(1)}`).classList.toggle('active', t === tab);
    });
    if (tab === 'analytics' && activityChart) activityChart.resize();
}

// ============= Conversations sidebar =============

function renderConversations() {
    const list = document.getElementById('conversationsList');
    if (!conversations.length) {
        list.innerHTML = '<p class="text-xs text-gray-500 text-center py-8">No conversations yet</p>';
        return;
    }
    list.innerHTML = conversations.map(c => `
        <div class="p-3 mb-1 rounded-lg cursor-pointer transition group ${c.id === currentConversationId ? 'bg-purple-600/20 border border-purple-500/30' : 'hover:bg-gray-800/50 border border-transparent'}" onclick="loadConversation('${c.id}')">
            <div class="flex items-start justify-between gap-2">
                <div class="min-w-0 flex-1">
                    <p class="text-sm text-white truncate">${escapeHtml(c.title || 'New conversation')}</p>
                    <p class="text-[10px] text-gray-500">${(c.updated_at || c.created_at || '').slice(0, 16)}</p>
                </div>
                <button onclick="event.stopPropagation();deleteConversation('${c.id}')" class="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition" title="Delete">
                    <i class="fas fa-trash text-xs"></i>
                </button>
            </div>
        </div>
    `).join('');
}

async function loadConversation(id) {
    currentConversationId = id;
    renderConversations();
    try {
        const msgs = await api('GET', `conversations/${id}/messages`);
        renderMessages(msgs);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function newConversation() {
    currentConversationId = null;
    document.getElementById('chatScroll').innerHTML = `
        <div class="empty-state">
            <i class="fas fa-comments text-5xl text-gray-600 mb-4"></i>
            <p class="text-sm">Type your first message below to start</p>
        </div>
    `;
}

async function deleteConversation(id) {
    if (!confirm('Delete this conversation and all its messages?')) return;
    try {
        await api('DELETE', `conversations/${id}`);
        conversations = conversations.filter(c => c.id !== id);
        if (currentConversationId === id) {
            currentConversationId = null;
            newConversation();
        }
        renderConversations();
        showToast('Conversation deleted');
    } catch (e) { showToast(e.message, 'error'); }
}

// ============= Chat =============

function renderQuickPrompts(tmpl) {
    const container = document.getElementById('quickPrompts');
    if (!tmpl || !tmpl.prompts) { container.innerHTML = ''; return; }
    container.innerHTML = tmpl.prompts.map(p => `
        <button onclick="sendSuggestedPrompt(\`${escapeHtml(p.text).replace(/`/g, '\\`')}\`)" class="px-3 py-1.5 bg-gray-800/60 hover:bg-purple-600/30 border border-gray-700 hover:border-purple-500/50 rounded-full text-xs text-gray-300 hover:text-white transition flex items-center gap-1.5">
            <i class="fas ${p.icon} text-purple-400"></i>${escapeHtml(p.text.length > 35 ? p.text.substring(0, 35) + '...' : p.text)}
        </button>
    `).join('');
}

function renderMessages(messages) {
    const scroll = document.getElementById('chatScroll');
    if (!messages || !messages.length) {
        scroll.innerHTML = `<div class="empty-state"><i class="fas fa-comments text-5xl text-gray-600 mb-4"></i><p class="text-sm">No messages yet</p></div>`;
        return;
    }
    scroll.innerHTML = messages.map(m => renderMessageHtml(m)).join('');
    scroll.scrollTop = scroll.scrollHeight;
}

function renderMessageHtml(m) {
    const isUser = m.role === 'user';
    const avatar = isUser
        ? `<div class="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center flex-shrink-0"><i class="fas fa-user text-white text-xs"></i></div>`
        : `<div class="w-8 h-8 rounded-full bg-gradient-to-br from-purple-600/40 to-cyan-600/40 border border-purple-500/30 flex items-center justify-center flex-shrink-0"><i class="fas fa-robot text-purple-300 text-xs"></i></div>`;
    const bubbleClass = isUser ? 'user' : 'assistant';
    const meta = !isUser && m.duration_ms ? `<span class="text-[10px] text-gray-500 mt-1 block">${m.duration_ms}ms${m.tokens_used ? ' · ' + m.tokens_used + ' tokens' : ''}</span>` : '';
    return `
        <div class="flex items-start gap-3 mb-5 chat-message">
            ${avatar}
            <div class="flex-1 min-w-0">
                <div class="chat-bubble ${bubbleClass}">${renderMarkdown(m.content)}</div>
                ${meta}
                <div class="flex items-center gap-2 mt-1 ml-1">
                    <button onclick="copyMessage(\`${escapeHtml(m.content).replace(/`/g, '\\`').replace(/\\/g, '\\\\')}\`)" class="copy-btn text-[10px] text-gray-500 hover:text-purple-400 transition"><i class="fas fa-copy mr-1"></i>Copy</button>
                    ${!isUser && m.id ? `<button onclick="regenerateMessage('${m.id}')" class="copy-btn text-[10px] text-gray-500 hover:text-cyan-400 transition"><i class="fas fa-rotate mr-1"></i>Regenerate</button>` : ''}
                </div>
            </div>
        </div>
    `;
}

function renderMarkdown(text) {
    if (!text) return '';
    try {
        marked.setOptions({ breaks: true, gfm: true });
        const raw = marked.parse(text);
        const clean = DOMPurify.sanitize(raw, { ADD_ATTR: ['target'] });
        setTimeout(() => {
            document.querySelectorAll('.chat-bubble pre code').forEach(el => {
                if (!el.classList.contains('hljs')) hljs.highlightElement(el);
            });
        }, 0);
        return clean;
    } catch { return escapeHtml(text).replace(/\n/g, '<br>'); }
}

function copyMessage(text) {
    navigator.clipboard.writeText(text).then(() => showToast('Copied to clipboard', 'info')).catch(() => showToast('Copy failed', 'error'));
}

function sendSuggestedPrompt(text) {
    document.getElementById('chatInput').value = text;
    sendMessage();
}

async function sendMessage() {
    if (isGenerating) return;
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    input.style.height = 'auto';

    const scroll = document.getElementById('chatScroll');
    const emptyState = scroll.querySelector('.empty-state');
    if (emptyState) scroll.innerHTML = '';

    const userMsgHtml = renderMessageHtml({ role: 'user', content: text });
    scroll.insertAdjacentHTML('beforeend', userMsgHtml);
    scroll.insertAdjacentHTML('beforeend', `
        <div id="typingIndicator" class="flex items-start gap-3 mb-5">
            <div class="w-8 h-8 rounded-full bg-gradient-to-br from-purple-600/40 to-cyan-600/40 border border-purple-500/30 flex items-center justify-center flex-shrink-0"><i class="fas fa-robot text-purple-300 text-xs"></i></div>
            <div class="chat-bubble assistant">
                <div class="typing-dots"><span></span><span></span><span></span></div>
            </div>
        </div>
    `);
    scroll.scrollTop = scroll.scrollHeight;

    document.getElementById('sendBtn').classList.add('hidden');
    document.getElementById('stopBtn').classList.remove('hidden');
    isGenerating = true;
    abortController = new AbortController();

    try {
        const data = await api('POST', `${currentAssistantId}/chat`, {
            message: text,
            conversation_id: currentConversationId
        });
        const typing = document.getElementById('typingIndicator');
        if (typing) typing.remove();

        if (data.conversation_id) {
            currentConversationId = data.conversation_id;
            if (!conversations.find(c => c.id === data.conversation_id)) {
                conversations.unshift({ id: data.conversation_id, title: text.slice(0, 60), updated_at: new Date().toISOString() });
                renderConversations();
            }
        }

        const aiMsg = {
            id: data.message_id,
            role: 'assistant',
            content: data.response || 'No response',
            tokens_used: data.tokens_used,
            duration_ms: data.duration_ms
        };
        scroll.insertAdjacentHTML('beforeend', renderMessageHtml(aiMsg));
        scroll.scrollTop = scroll.scrollHeight;

        document.getElementById('chatMeta').textContent = `${data.duration_ms || 0}ms · ${data.tokens_used || 0} tokens · ${escapeHtml(data.model || '')}`;

        if (data.error) showToast('Generation error: ' + data.error, 'error');
    } catch (e) {
        const typing = document.getElementById('typingIndicator');
        if (typing) typing.remove();
        scroll.insertAdjacentHTML('beforeend', `
            <div class="flex items-start gap-3 mb-5">
                <div class="w-8 h-8 rounded-full bg-red-600/30 flex items-center justify-center flex-shrink-0"><i class="fas fa-triangle-exclamation text-red-400 text-xs"></i></div>
                <div class="chat-bubble assistant border-red-500/30 text-red-300">Failed to get response: ${escapeHtml(e.message)}</div>
            </div>
        `);
    } finally {
        document.getElementById('sendBtn').classList.remove('hidden');
        document.getElementById('stopBtn').classList.add('hidden');
        isGenerating = false;
        abortController = null;
    }
}

function stopGeneration() {
    if (abortController) abortController.abort();
    isGenerating = false;
    document.getElementById('sendBtn').classList.remove('hidden');
    document.getElementById('stopBtn').classList.add('hidden');
    const typing = document.getElementById('typingIndicator');
    if (typing) typing.remove();
}

async function regenerateMessage(messageId) {
    if (!currentConversationId) return;
    try {
        const msgs = await api('GET', `conversations/${currentConversationId}/messages`);
        const idx = msgs.findIndex(m => m.id === messageId);
        if (idx < 1) return;
        const prevUser = msgs[idx - 1];
        if (prevUser.role !== 'user') return;
        document.getElementById('chatInput').value = prevUser.content;
        await sendMessage();
    } catch (e) { showToast(e.message, 'error'); }
}

function exportCurrentChat() {
    if (!currentConversationId) { showToast('No active conversation', 'error'); return; }
    api('GET', `conversations/${currentConversationId}/messages`).then(msgs => {
        const text = msgs.map(m => `[${m.role.toUpperCase()}]\n${m.content}\n`).join('\n---\n\n');
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${currentAssistant?.assistant.name || 'conversation'}-${new Date().toISOString().slice(0,10)}.txt`;
        a.click();
        URL.revokeObjectURL(url);
        showToast('Conversation exported');
    });
}

// ============= Voice input (Web Speech API) =============

let recognition = null;
let isListening = false;

function toggleVoice() {
    if (isListening) {
        recognition?.stop();
        return;
    }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
        showToast('Voice input not supported in this browser', 'error');
        return;
    }
    recognition = new SR();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';
    recognition.onstart = () => {
        isListening = true;
        document.getElementById('voiceBtn').innerHTML = '<i class="fas fa-stop text-red-400"></i>';
        showToast('Listening...', 'info');
    };
    recognition.onresult = e => {
        let txt = '';
        for (let i = e.resultIndex; i < e.results.length; i++) txt += e.results[i][0].transcript;
        document.getElementById('chatInput').value = txt;
    };
    recognition.onend = () => {
        isListening = false;
        document.getElementById('voiceBtn').innerHTML = '<i class="fas fa-microphone"></i>';
    };
    recognition.onerror = e => {
        isListening = false;
        document.getElementById('voiceBtn').innerHTML = '<i class="fas fa-microphone"></i>';
        showToast('Voice error: ' + e.error, 'error');
    };
    recognition.start();
}

// ============= Info tab =============

function populateInfo(data) {
    const a = data.assistant;
    document.getElementById('infoStatus').innerHTML = a.is_active ? '<span class="text-green-400">Active</span>' : '<span class="text-gray-400">Inactive</span>';
    document.getElementById('infoModel').textContent = a.model_id;
    document.getElementById('infoPersonality').textContent = a.personality;
    document.getElementById('infoTemp').textContent = a.temperature;
    document.getElementById('infoTokens').textContent = a.max_tokens;
    document.getElementById('infoAuto').innerHTML = a.auto_reply ? '<span class="text-green-400">On</span>' : '<span class="text-gray-400">Off</span>';
    document.getElementById('infoPrompt').textContent = a.system_prompt || '(empty)';
    document.getElementById('infoDescription').textContent = a.description || '(no description)';
    let tags = [];
    try { tags = typeof a.tags === 'string' ? JSON.parse(a.tags || '[]') : (a.tags || []); } catch { tags = []; }
    document.getElementById('infoTags').innerHTML = tags.length
        ? tags.map(t => `<span class="badge badge-tag">${escapeHtml(t)}</span>`).join('')
        : '<span class="text-xs text-gray-500">No tags</span>';

    document.getElementById('setName').value = a.name;
    document.getElementById('setDescription').value = a.description || '';
    document.getElementById('setPersonality').value = a.personality || 'professional';
    document.getElementById('setTemp').value = a.temperature || 0.7;
    document.getElementById('setTempVal').textContent = a.temperature || 0.7;
    document.getElementById('setTokens').value = a.max_tokens || 1000;
    document.getElementById('setTokensVal').textContent = a.max_tokens || 1000;
    document.getElementById('setPrompt').value = a.system_prompt || '';
    document.getElementById('setTags').value = tags.join(', ');
    const modelSel = document.getElementById('setModel');
    if (![...modelSel.options].some(o => o.value === a.model_id)) {
        const opt = document.createElement('option');
        opt.value = a.model_id; opt.textContent = a.model_id;
        modelSel.appendChild(opt);
    }
    modelSel.value = a.model_id;
}

// ============= Tasks tab =============

function renderTasks(tasks) {
    const list = document.getElementById('tasksList');
    if (!tasks || !tasks.length) {
        list.innerHTML = '<p class="text-sm text-gray-500">No tasks configured</p>';
        return;
    }
    list.innerHTML = tasks.map(t => `
        <div class="p-4 glass flex items-center justify-between gap-3">
            <div class="flex items-center gap-3 flex-1 min-w-0">
                <div class="w-10 h-10 rounded-lg bg-blue-600/20 flex items-center justify-center"><i class="fas fa-bolt text-blue-400"></i></div>
                <div class="min-w-0">
                    <p class="text-sm text-white font-medium truncate">${escapeHtml(t.name)}</p>
                    <p class="text-xs text-gray-500">${escapeHtml(t.task_type)} ${t.schedule ? '• ' + escapeHtml(t.schedule) : ''}</p>
                </div>
            </div>
            <div class="flex items-center gap-3">
                <span class="text-xs text-gray-400">${t.run_count || 0} runs</span>
                ${t.last_run ? `<span class="text-[10px] text-gray-500">${t.last_run.slice(0, 16)}</span>` : ''}
                <button onclick="runTaskNow('${t.id}')" class="btn btn-secondary text-xs"><i class="fas fa-play"></i></button>
                <button onclick="deleteTask('${t.id}')" class="btn btn-ghost text-gray-500 hover:text-red-400"><i class="fas fa-trash text-xs"></i></button>
            </div>
        </div>
    `).join('');
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
        renderTasks(data.tasks);
    } catch (e) { showToast(e.message, 'error'); }
});

async function runTaskNow(taskId) {
    try {
        await api('POST', `tasks/${taskId}/run`);
        showToast('Task triggered');
        const data = await api('GET', currentAssistantId);
        renderTasks(data.tasks);
    } catch (e) { showToast(e.message, 'error'); }
}

async function deleteTask(taskId) {
    if (!confirm('Delete this task?')) return;
    try {
        await api('DELETE', `tasks/${taskId}`);
        const data = await api('GET', currentAssistantId);
        renderTasks(data.tasks);
        showToast('Task deleted');
    } catch (e) { showToast(e.message, 'error'); }
}

// ============= Integrations tab =============

function renderIntegrations(integrations) {
    const list = document.getElementById('integrationsList');
    if (!integrations || !integrations.length) {
        list.innerHTML = '<p class="text-sm text-gray-500">No integrations configured</p>';
        return;
    }
    list.innerHTML = integrations.map(i => {
        const def = INTEGRATION_TYPES[i.integration_type] || {};
        const icon = def.icon || 'fas fa-plug';
        const color = def.color || 'cyan';
        const hasConfig = i.config && Object.keys(i.config).length > 0;
        const configInfo = hasConfig ? `${Object.keys(i.config).length} field(s) set` : 'No config';
        return `
        <div class="p-4 glass flex items-center justify-between gap-3">
            <div class="flex items-center gap-3 flex-1 min-w-0">
                <div class="w-10 h-10 rounded-lg bg-${color}-600/20 flex items-center justify-center"><i class="${icon} text-${color}-400"></i></div>
                <div class="min-w-0">
                    <p class="text-sm text-white font-medium truncate">${escapeHtml(i.name)}</p>
                    <p class="text-xs text-gray-500">${escapeHtml(i.integration_type)} • ${escapeHtml(i.status || 'disconnected')} • ${configInfo}</p>
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
        </div>
    `;}).join('');
}

function openAddIntegrationModal() { document.getElementById('integrationModal').classList.remove('hidden'); }
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
        renderIntegrations(data.integrations);
    } catch (e) { showToast(e.message, 'error'); }
});

async function toggleIntegration(id, active) {
    try {
        await api('PUT', `integrations/${id}`, { is_active: active, status: active ? 'connected' : 'disconnected' });
    } catch (e) { showToast(e.message, 'error'); }
}

async function deleteIntegration(id) {
    if (!confirm('Delete this integration?')) return;
    try {
        await api('DELETE', `integrations/${id}`);
        const data = await api('GET', currentAssistantId);
        renderIntegrations(data.integrations);
        showToast('Integration deleted');
    } catch (e) { showToast(e.message, 'error'); }
}

async function testIntegration(id) {
    showToast('Testing connection...', 'info');
    try {
        const r = await api('POST', `integrations/${id}/test`);
        if (r.success) {
            showToast('✓ ' + (r.message || 'Connection successful'), 'success');
        } else {
            showToast('✗ ' + (r.message || 'Connection failed'), 'error');
        }
        const data = await api('GET', currentAssistantId);
        renderIntegrations(data.integrations);
    } catch (e) { showToast(e.message, 'error'); }
}

// ============= Analytics tab =============

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
    const ctx = document.getElementById('activityChart').getContext('2d');
    if (activityChart) activityChart.destroy();
    activityChart = new Chart(ctx, {
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

// ============= Logs tab =============

function renderLogs(logs) {
    const list = document.getElementById('logsList');
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
        </div>
    `;}).join('');
}

// ============= Assistant actions =============

async function toggleAssistantActive() {
    try {
        const r = await api('POST', `${currentAssistantId}/toggle`);
        showToast(r.is_active ? 'Activated' : 'Deactivated');
        location.reload();
    } catch (e) { showToast(e.message, 'error'); }
}

async function duplicateCurrentAssistant() {
    try {
        const r = await api('POST', `${currentAssistantId}/duplicate`);
        showToast('Duplicated: ' + r.name);
        setTimeout(() => location.reload(), 500);
    } catch (e) { showToast(e.message, 'error'); }
}

async function shareCurrentAssistant() {
    try {
        const r = await api('POST', `${currentAssistantId}/share`);
        const url = `${location.origin}/share/${r.share_token}`;
        navigator.clipboard.writeText(url).then(() => showToast('Share link copied to clipboard', 'info'))
            .catch(() => prompt('Share link:', url));
    } catch (e) { showToast(e.message, 'error'); }
}

async function deleteCurrentAssistant() {
    if (!confirm('Delete this assistant permanently?')) return;
    try {
        await api('DELETE', currentAssistantId);
        showToast('Assistant deleted');
        setTimeout(() => location.reload(), 500);
    } catch (e) { showToast(e.message, 'error'); }
}