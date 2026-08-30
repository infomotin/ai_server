/* OpenLocalAI — Models Hub v2 */

const TASK_ICONS = {
    chat_small: 'fa-comments',
    chat_balanced: 'fa-comments',
    chat_large: 'fa-comments',
    code: 'fa-code',
    embedding: 'fa-vector-square',
    vision: 'fa-eye',
    reasoning: 'fa-brain',
    multilingual: 'fa-language'
};

const TASK_COLORS = {
    chat_small: 'green', chat_balanced: 'cyan', chat_large: 'purple',
    code: 'amber', embedding: 'blue', vision: 'pink', reasoning: 'orange', multilingual: 'lime'
};

const TASK_LABELS = {
    chat_small: 'Chat (small / fast)',
    chat_balanced: 'Chat (balanced)',
    chat_large: 'Chat (large / best quality)',
    code: 'Code generation',
    embedding: 'Embeddings',
    vision: 'Vision (image + text)',
    reasoning: 'Reasoning / chain-of-thought',
    multilingual: 'Multilingual'
};

let ollamaModels = [];
let activeStreams = {};

function escapeHtml(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
function fmtBytes(n) {
    if (n == null) return '?';
    const u = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0; while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return `${n.toFixed(n < 10 ? 1 : 0)} ${u[i]}`;
}

function showToast(msg, type = 'success') {
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.innerHTML = `<i class="fas fa-${type === 'error' ? 'exclamation-circle' : type === 'info' ? 'info-circle' : 'check-circle'} mr-2"></i><span>${escapeHtml(msg)}</span>`;
    document.getElementById('toastContainer').appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .3s'; setTimeout(() => t.remove(), 300); }, 3500);
}

function showTab(name) {
    document.querySelectorAll('[id^="panel-"]').forEach(p => p.classList.add('hidden'));
    document.querySelectorAll('[id^="tab-"]').forEach(t => { t.classList.remove('active'); });
    document.getElementById('panel-' + name).classList.remove('hidden');
    document.getElementById('tab-' + name).classList.add('active');

    if (name === 'ollama') refreshInstalled();
    if (name === 'local') loadLocalFiles();
    if (name === 'trained') loadTrained();
    if (name === 'library') loadLibrary();
}

async function api(path, opts = {}) {
    const resp = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
    if (resp.status === 401) { showToast('Session expired', 'error'); setTimeout(() => location.href = '/login', 800); throw new Error('401'); }
    let data; try { data = await resp.json(); } catch { data = {}; }
    if (!resp.ok) throw new Error(data.error || data.detail || 'Request failed');
    return data;
}

document.addEventListener('DOMContentLoaded', () => {
    checkOllama();
    refreshInstalled();
    renderQuickPulls();
});

// ============= Ollama Status & Installed =============

async function checkOllama() {
    try {
        const r = await api('/api/ollama/status');
        const dot = document.getElementById('ollamaDot');
        const text = document.getElementById('ollamaText');
        if (r.online) {
            dot.classList.remove('gray'); dot.classList.add('text-green-400');
            text.textContent = 'Ollama online';
        } else {
            dot.classList.remove('gray'); dot.classList.add('text-red-400');
            text.textContent = 'Ollama offline';
        }
    } catch {
        document.getElementById('ollamaText').textContent = 'Ollama offline';
    }
}

async function refreshInstalled() {
    try {
        const r = await api('/api/ollama/tags');
        ollamaModels = (r.models || []);
        renderInstalled();
        populateDefaultSelect();
        checkOllama();
    } catch (e) {
        document.getElementById('installedModels').innerHTML = `<p class="text-red-400 text-sm col-span-full text-center py-8">${escapeHtml(e.message)}</p>`;
    }
}

function renderInstalled() {
    const container = document.getElementById('installedModels');
    if (!ollamaModels.length) {
        container.innerHTML = `<div class="col-span-full text-center py-12 glass"><i class="fas fa-box-open text-4xl text-gray-600 mb-3"></i><p class="text-gray-400">No models installed yet. Pull one to get started.</p></div>`;
        return;
    }
    const running = new Set();
    api('/api/ollama/ps').then(r => (r.models || []).forEach(m => running.add(m.name))).catch(() => {});

    container.innerHTML = ollamaModels.map(m => {
        const d = m.details || {};
        const isRunning = running.has(m.name);
        const capabilities = (m.capabilities || []).join(', ') || '—';
        return `
            <div class="model-card" data-name="${escapeHtml(m.name)}">
                <div class="flex items-start justify-between mb-2">
                    <div class="flex items-center gap-3 min-w-0">
                        <div class="w-11 h-11 rounded-xl bg-gradient-to-br from-purple-600/30 to-cyan-600/30 flex items-center justify-center border border-purple-500/20">
                            <i class="fas fa-cube text-purple-300"></i>
                        </div>
                        <div class="min-w-0">
                            <h4 class="text-white font-semibold truncate">${escapeHtml(m.name)}</h4>
                            <p class="text-xs text-gray-500">${escapeHtml(d.family || 'unknown')} • ${escapeHtml(d.parameter_size || '?')}</p>
                        </div>
                    </div>
                    ${isRunning ? '<span class="badge badge-green"><span class="pulse-dot inline-block mr-1" style="width:6px;height:6px"></span>Running</span>' : '<span class="badge badge-gray">Idle</span>'}
                </div>
                <div class="grid grid-cols-2 gap-2 text-xs mb-3">
                    <div class="p-2 bg-black/20 rounded">
                        <p class="text-gray-500">Size</p>
                        <p class="text-white font-medium">${fmtBytes(m.size)}</p>
                    </div>
                    <div class="p-2 bg-black/20 rounded">
                        <p class="text-gray-500">Quantization</p>
                        <p class="text-white font-medium">${escapeHtml(d.quantization_level || '?')}</p>
                    </div>
                    <div class="p-2 bg-black/20 rounded col-span-2">
                        <p class="text-gray-500">Capabilities</p>
                        <p class="text-white font-medium text-[11px]">${escapeHtml(capabilities)}</p>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <button onclick="setDefaultModel('${escapeHtml(m.name)}')" class="btn btn-secondary text-xs flex-1"><i class="fas fa-star"></i> Default</button>
                    <button onclick="showModelInfo('${escapeHtml(m.name)}')" class="btn btn-icon" title="Info"><i class="fas fa-circle-info text-xs"></i></button>
                    <button onclick="deleteModel('${escapeHtml(m.name)}')" class="btn btn-icon hover:!text-red-400" title="Delete"><i class="fas fa-trash text-xs"></i></button>
                </div>
            </div>
        `;
    }).join('');
}

function populateDefaultSelect() {
    const sel = document.getElementById('defaultModelSelect');
    const opts = ['<option value="">Select model...</option>'].concat(
        ollamaModels.map(m => `<option value="${escapeHtml(m.name)}">${escapeHtml(m.name)}</option>`)
    );
    sel.innerHTML = opts.join('');
    fetch('/api/management/default-model').then(r => r.json()).then(d => { if (d.model) sel.value = d.model; }).catch(() => {});
}

async function setDefaultModel(name) {
    if (!name) return;
    try {
        await api('/api/management/default-model', { method: 'POST', body: JSON.stringify({ model: name }) });
        showToast(`Default model set to ${name}`);
        refreshInstalled();
    } catch (e) {
        try {
            await fetch('/models/switch', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: `model=${encodeURIComponent(name)}` });
            showToast(`Default model set to ${name}`);
        } catch (e2) { showToast(e.message, 'error'); }
    }
}

async function deleteModel(name) {
    if (!confirm(`Delete model "${name}"? This frees disk space but keeps nothing.`)) return;
    try {
        await api('/api/ollama/delete', { method: 'POST', body: JSON.stringify({ name }) });
        showToast(`Deleted ${name}`);
        refreshInstalled();
    } catch (e) { showToast(e.message, 'error'); }
}

async function showModelInfo(name) {
    try {
        const r = await api(`/api/ollama/show?name=${encodeURIComponent(name)}`);
        const text = JSON.stringify(r, null, 2);
        const w = window.open('', '_blank', 'width=600,height=500');
        w.document.write(`<pre style="background:#0f172a;color:#e2e8f0;padding:20px;font-size:12px;">${escapeHtml(text)}</pre>`);
    } catch (e) { showToast(e.message, 'error'); }
}

// ============= Pull Model (real-time SSE) =============

function renderQuickPulls() {
    const quick = ['llama3.2:1b', 'llama3.2:3b', 'qwen2.5:1.5b', 'qwen2.5:7b', 'phi3:mini', 'gemma2:2b', 'mistral-nemo', 'codellama:3.5', 'nomic-embed-text', 'deepseek-r1:1.5b'];
    document.getElementById('quickPulls').innerHTML = quick.map(m =>
        `<button onclick="quickPull('${m}')" class="px-3 py-1.5 bg-gray-800/60 hover:bg-purple-600/30 border border-gray-700 hover:border-purple-500/50 rounded-full text-xs text-gray-300 hover:text-white transition flex items-center gap-1.5">
            <i class="fas fa-download text-purple-400"></i>${escapeHtml(m)}</button>`
    ).join('');
}

async function quickPull(name) {
    document.getElementById('pullInput').value = name;
    pullModel();
}

async function pullModel() {
    const input = document.getElementById('pullInput');
    const name = input.value.trim();
    if (!name) { showToast('Enter a model name', 'error'); return; }
    if (activeStreams[name]) { showToast(`Already pulling ${name}`, 'info'); return; }

    const btn = document.getElementById('pullBtn');
    btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Pulling';
    document.getElementById('pullProgress').classList.remove('hidden');
    document.getElementById('pullStatus').textContent = `Starting download of ${name}...`;
    document.getElementById('pullPercent').textContent = '0%';
    document.getElementById('pullFill').style.width = '0%';
    document.getElementById('pullDetail').textContent = '';

    const ctrl = new AbortController();
    activeStreams[name] = ctrl;
    try {
        const resp = await fetch('/api/ollama/pull', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
            signal: ctrl.signal
        });
        if (!resp.ok) throw new Error('Pull failed');
        const reader = resp.body.getReader();
        const dec = new TextDecoder();
        let buf = '';
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buf += dec.decode(value, { stream: true });
            const events = buf.split('\n\n');
            buf = events.pop();
            for (const ev of events) {
                const line = ev.replace(/^data: /, '').trim();
                if (!line) continue;
                let data; try { data = JSON.parse(line); } catch { continue; }
                handlePullEvent(name, data);
            }
        }
    } catch (e) {
        if (e.name !== 'AbortError') showToast(`Pull error: ${e.message}`, 'error');
        document.getElementById('pullStatus').textContent = 'Failed';
    } finally {
        delete activeStreams[name];
        btn.disabled = false; btn.innerHTML = '<i class="fas fa-download mr-1"></i> Pull';
        refreshInstalled();
    }
}

function handlePullEvent(name, data) {
    const status = data.status || '';
    const total = data.total || 0;
    const completed = data.completed || 0;
    let pct = total > 0 ? Math.round((completed / total) * 100) : 0;
    if (status === 'success') pct = 100;
    if (status.includes('verifying')) pct = Math.max(pct, 95);
    if (status.includes('writing')) pct = Math.max(pct, 90);
    if (status.includes('pulling')) pct = Math.max(pct, 70);

    document.getElementById('pullStatus').textContent = `${name}: ${status}`;
    document.getElementById('pullPercent').textContent = pct + '%';
    document.getElementById('pullFill').style.width = pct + '%';

    const detail = data.digest ? data.digest.slice(0, 12) + '…' : '';
    document.getElementById('pullDetail').textContent = detail + (total ? ` (${fmtBytes(completed)} / ${fmtBytes(total)})` : '');

    if (data.done || status === 'success') {
        showToast(`Successfully installed ${name}`);
        document.getElementById('pullStatus').textContent = `${name}: complete`;
    }
    if (data.error) {
        showToast(`Pull error: ${data.error}`, 'error');
    }
}

// ============= Library / Recommendations =============

async function loadLibrary() {
    const container = document.getElementById('librarySections');
    container.innerHTML = '<p class="text-gray-500 text-sm"><i class="fas fa-spinner fa-spin mr-2"></i>Loading recommendations...</p>';
    try {
        const data = await api('/api/models/library');
        const installed = new Set(ollamaModels.map(m => m.name));
        container.innerHTML = Object.entries(data).map(([cat, models]) => {
            const color = TASK_COLORS[cat] || 'gray';
            const icon = TASK_ICONS[cat] || 'fa-cube';
            return `
                <div class="glass p-4">
                    <h4 class="text-white font-semibold mb-3 flex items-center gap-2">
                        <i class="fas ${icon} text-${color}-400"></i>
                        ${TASK_LABELS[cat] || cat}
                        <span class="badge badge-${color === 'gray' ? 'gray' : color === 'amber' ? 'amber' : color === 'blue' ? 'blue' : 'purple'} ml-auto">${models.length} models</span>
                    </h4>
                    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
                        ${models.map(m => {
                            const isInstalled = installed.has(m.name);
                            return `
                                <div class="p-3 bg-black/20 rounded-lg border border-gray-700/40 hover:border-${color}-500/40 transition flex items-center justify-between gap-3">
                                    <div class="min-w-0">
                                        <div class="flex items-center gap-2">
                                            <span class="text-white font-medium text-sm">${escapeHtml(m.name)}</span>
                                            ${isInstalled ? '<span class="badge badge-green text-[9px]">Installed</span>' : ''}
                                        </div>
                                        <p class="text-xs text-gray-500">${escapeHtml(m.desc)} • ${escapeHtml(m.params)} • ${escapeHtml(m.size)}</p>
                                    </div>
                                    ${isInstalled
                                        ? `<button onclick="setDefaultModel('${escapeHtml(m.name)}')" class="btn btn-secondary text-xs whitespace-nowrap"><i class="fas fa-star"></i></button>`
                                        : `<button onclick="quickPull('${escapeHtml(m.name)}')" class="btn btn-primary text-xs whitespace-nowrap"><i class="fas fa-download"></i> Install</button>`
                                    }
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            `;
        }).join('');
    } catch (e) { container.innerHTML = `<p class="text-red-400 text-sm">${escapeHtml(e.message)}</p>`; }
}

// ============= Hugging Face Search =============

async function searchHF() {
    const q = document.getElementById('hfSearch').value.trim();
    const results = document.getElementById('hfResults');
    if (!q) return;
    results.innerHTML = '<p class="text-gray-500 text-sm"><i class="fas fa-spinner fa-spin mr-2"></i>Searching Hugging Face...</p>';
    try {
        const resp = await fetch(`https://huggingface.co/api/models?search=${encodeURIComponent(q)}&filter=gguf&sort=downloads&direction=-1&limit=10`);
        const data = await resp.json();
        if (!data.length) { results.innerHTML = '<p class="text-gray-500 text-sm">No GGUF models matched.</p>'; return; }
        results.innerHTML = data.map(m => `
            <div class="p-3 bg-black/20 rounded-lg border border-gray-700/40 flex items-center justify-between gap-3">
                <div class="min-w-0">
                    <p class="text-sm text-white font-medium truncate">${escapeHtml(m.id)}</p>
                    <p class="text-xs text-gray-500">${(m.downloads || 0).toLocaleString()} downloads • ${m.likes || 0} likes</p>
                </div>
                <button onclick="queueHFDownload('${escapeHtml(m.id)}')" class="btn btn-primary text-xs whitespace-nowrap"><i class="fas fa-download"></i> Get</button>
            </div>
        `).join('');
    } catch (e) { results.innerHTML = `<p class="text-red-400 text-sm">Search failed: ${escapeHtml(e.message)}</p>`; }
}

async function queueHFDownload(id) {
    document.getElementById('hfModelId').value = id;
    downloadHF();
}

async function downloadHF() {
    const id = document.getElementById('hfModelId').value.trim();
    const pattern = document.getElementById('hfPattern').value;
    if (!id) { showToast('Enter a model ID', 'error'); return; }
    try {
        await fetch('/models/huggingface/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `model_id=${encodeURIComponent(id)}&file_pattern=${encodeURIComponent(pattern)}`
        });
        showToast(`Queued ${id} for background download`);
    } catch (e) { showToast(e.message, 'error'); }
}

// ============= Local Files =============

async function loadLocalFiles() {
    const container = document.getElementById('localFiles');
    container.innerHTML = '<p class="text-gray-500 text-sm col-span-full text-center py-8"><i class="fas fa-spinner fa-spin mr-2"></i>Scanning disk...</p>';
    try {
        const r = await api('/api/models/local');
        if (!r.models || !r.models.length) {
            container.innerHTML = `<div class="col-span-full text-center py-12 glass"><i class="fas fa-folder-open text-4xl text-gray-600 mb-3"></i><p class="text-gray-400">No models in <code class="text-cyan-400">${escapeHtml(r.base_dir || '/www/AI_server/models')}</code></p></div>`;
            return;
        }
        container.innerHTML = r.models.map(m => {
            const gguf = m.gguf_files && m.gguf_files[0];
            return `
                <div class="model-card">
                    <div class="flex items-start justify-between mb-3">
                        <div class="flex items-center gap-3 min-w-0">
                            <div class="w-11 h-11 rounded-xl bg-gradient-to-br from-cyan-600/30 to-blue-600/30 flex items-center justify-center border border-cyan-500/20">
                                <i class="fas fa-file-code text-cyan-300"></i>
                            </div>
                            <div class="min-w-0">
                                <h4 class="text-white font-semibold truncate">${escapeHtml(m.name)}</h4>
                                <p class="text-xs text-gray-500">${m.file_count} files • ${fmtBytes(m.size_bytes)}</p>
                            </div>
                        </div>
                    </div>
                    ${gguf ? `<p class="text-xs text-gray-500 mb-3"><i class="fas fa-file mr-1"></i>${escapeHtml(gguf)}</p>` : ''}
                    <div class="flex items-center gap-2">
                        <button onclick="createModelfile('${escapeHtml(m.name)}', '${escapeHtml(gguf || '')}')" class="btn btn-primary text-xs flex-1"><i class="fas fa-plus-circle"></i> Register in Ollama</button>
                        <button onclick="showLocalPath('${escapeHtml(m.path)}')" class="btn btn-icon" title="Show path"><i class="fas fa-folder text-xs"></i></button>
                    </div>
                </div>
            `;
        }).join('');
    } catch (e) { container.innerHTML = `<p class="text-red-400 text-sm col-span-full">${escapeHtml(e.message)}</p>`; }
}

function showLocalPath(p) { prompt('Local path:', p); }

async function createModelfile(folderName, ggufFile) {
    if (!ggufFile) { showToast('No GGUF file found in this folder', 'error'); return; }
    const modelName = prompt('Ollama model name (e.g. my-model:latest):', folderName.split('/').pop().toLowerCase() + ':latest');
    if (!modelName) return;
    const modelfile = `FROM ./${ggufFile}\n`;
    try {
        const r = await fetch('/api/ollama/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: modelName, modelfile, folder: `/www/AI_server/models/${folderName}` })
        });
        const data = await r.json();
        if (data.success || data.status === 'success') { showToast(`Registered as ${modelName}`); refreshInstalled(); }
        else showToast(data.error || 'Failed to create', 'error');
    } catch (e) { showToast(e.message, 'error'); }
}

// ============= My Trained Models =============

async function loadTrained() {
    const container = document.getElementById('trainedList');
    container.innerHTML = '<p class="text-gray-500 text-sm col-span-full text-center py-8"><i class="fas fa-spinner fa-spin mr-2"></i>Loading...</p>';
    try {
        const list = await api('/api/models/trained');
        if (!list || !list.length) {
            container.innerHTML = `<div class="col-span-full text-center py-12 glass">
                <i class="fas fa-graduation-cap text-4xl text-gray-600 mb-3"></i>
                <p class="text-gray-400 mb-3">No custom-trained models yet</p>
                <a href="/model-builder" class="btn btn-primary text-xs"><i class="fas fa-hammer mr-1"></i>Open Model Builder</a>
            </div>`;
            return;
        }
        container.innerHTML = list.map(m => {
            const status = m.status || 'building';
            const statusColor = status === 'ready' ? 'green' : status === 'training' ? 'amber' : 'gray';
            const progress = m.training_progress || 0;
            return `
                <div class="model-card">
                    <div class="flex items-start justify-between mb-3">
                        <div class="flex items-center gap-3 min-w-0">
                            <div class="w-11 h-11 rounded-xl bg-gradient-to-br from-pink-600/30 to-purple-600/30 flex items-center justify-center border border-pink-500/20">
                                <i class="fas fa-graduation-cap text-pink-300"></i>
                            </div>
                            <div class="min-w-0">
                                <h4 class="text-white font-semibold truncate">${escapeHtml(m.name)}</h4>
                                <p class="text-xs text-gray-500 truncate">${escapeHtml(m.domain || '')} • ${escapeHtml(m.base_model || '')}</p>
                            </div>
                        </div>
                        <span class="badge badge-${statusColor}">${escapeHtml(status)}</span>
                    </div>
                    <p class="text-xs text-gray-400 mb-3 line-clamp-2">${escapeHtml((m.description || '').slice(0, 100))}</p>
                    <div class="grid grid-cols-2 gap-2 mb-3 text-xs">
                        <div class="p-2 bg-black/20 rounded">
                            <p class="text-gray-500">Characters</p>
                            <p class="text-white font-medium">${(m.total_chars || 0).toLocaleString()}</p>
                        </div>
                        <div class="p-2 bg-black/20 rounded">
                            <p class="text-gray-500">Chunks</p>
                            <p class="text-white font-medium">${m.chunk_count || 0}</p>
                        </div>
                    </div>
                    ${status === 'training' ? `
                        <div class="mb-3">
                            <div class="flex items-center justify-between text-xs mb-1">
                                <span class="text-gray-500">Training progress</span>
                                <span class="text-amber-400 font-mono">${progress}%</span>
                            </div>
                            <div class="progress-bar"><div style="width:${progress}%"></div></div>
                        </div>
                    ` : ''}
                    <div class="flex items-center gap-2">
                        <a href="/model-builder" class="btn btn-secondary text-xs flex-1"><i class="fas fa-hammer"></i> Edit</a>
                        <a href="/assistants" class="btn btn-primary text-xs flex-1"><i class="fas fa-robot"></i> Use</a>
                    </div>
                </div>
            `;
        }).join('');
    } catch (e) { container.innerHTML = `<p class="text-red-400 text-sm col-span-full">${escapeHtml(e.message)}</p>`; }
}

// ============= Upload =============

document.getElementById('uploadForm').addEventListener('submit', async e => {
    e.preventDefault();
    const name = document.getElementById('uploadName').value.trim();
    const file = document.getElementById('uploadFile').files[0];
    if (!name || !file) { showToast('Name and file are required', 'error'); return; }

    const xhr = new XMLHttpRequest();
    const fd = new FormData();
    fd.append('model_name', name);
    fd.append('model_file', file);

    document.getElementById('uploadProgress').classList.remove('hidden');
    document.getElementById('uploadBtn').disabled = true;
    document.getElementById('uploadBtn').innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Uploading';

    xhr.upload.addEventListener('progress', e => {
        if (!e.lengthComputable) return;
        const pct = Math.round((e.loaded / e.total) * 100);
        document.getElementById('uploadPercent').textContent = pct + '%';
        document.getElementById('uploadFill').style.width = pct + '%';
    });
    xhr.addEventListener('load', () => {
        document.getElementById('uploadBtn').disabled = false;
        document.getElementById('uploadBtn').innerHTML = '<i class="fas fa-upload mr-2"></i> Upload';
        if (xhr.status === 200 || xhr.status === 302) {
            showToast(`Uploaded ${name}`);
            loadLocalFiles();
        } else showToast('Upload failed', 'error');
    });
    xhr.addEventListener('error', () => {
        document.getElementById('uploadBtn').disabled = false;
        showToast('Upload error', 'error');
    });
    xhr.open('POST', '/models/upload');
    xhr.send(fd);
});