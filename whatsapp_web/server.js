const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const cors = require('cors');
const QRCode = require('qrcode');
const http = require('http');
const WebSocket = require('ws');
const path = require('path');
const fs = require('fs');

const PORT = 3333;
const SESSIONS_DIR = path.join(__dirname, 'sessions');
if (!fs.existsSync(SESSIONS_DIR)) fs.mkdirSync(SESSIONS_DIR, { recursive: true });

const app = express();
app.use(cors());
app.use(express.json({ limit: '50mb' }));

const server = http.createServer(app);
const wss = new WebSocket.Server({ server, path: '/ws' });

const sessions = new Map();

function getOrCreateSession(sessionId) {
    if (sessions.has(sessionId)) return sessions.get(sessionId);

    const client = new Client({
        authStrategy: new LocalAuth({
            clientId: sessionId,
            dataPath: SESSIONS_DIR
        }),
        puppeteer: {
            headless: true,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--single-process',
                '--disable-gpu',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding'
            ]
        }
    });

    const sessionData = {
        id: sessionId,
        client,
        qr: null,
        status: 'initializing',
        info: null,
        connectedAt: null
    };

    client.on('qr', async (qr) => {
        try {
            const qrImage = await QRCode.toDataURL(qr, { width: 320, margin: 2 });
            sessionData.qr = qr;
            sessionData.qrImage = qrImage;
            sessionData.status = 'qr_ready';
            console.log(`[${sessionId}] QR code generated`);
            broadcast(sessionId, { type: 'qr', qr, qrImage });
        } catch (e) {
            console.error(`[${sessionId}] QR generation error:`, e.message);
        }
    });

    client.on('authenticated', () => {
        sessionData.status = 'authenticated';
        console.log(`[${sessionId}] Authenticated`);
        broadcast(sessionId, { type: 'authenticated' });
    });

    client.on('auth_failure', (msg) => {
        sessionData.status = 'auth_failure';
        console.log(`[${sessionId}] Auth failure: ${msg}`);
        broadcast(sessionId, { type: 'auth_failure', message: msg });
    });

    client.on('ready', () => {
        sessionData.status = 'ready';
        sessionData.connectedAt = Date.now();
        console.log(`[${sessionId}] Ready`);
        broadcast(sessionId, { type: 'ready' });
    });

    client.on('disconnected', (reason) => {
        sessionData.status = 'disconnected';
        sessionData.qr = null;
        sessionData.qrImage = null;
        console.log(`[${sessionId}] Disconnected: ${reason}`);
        broadcast(sessionId, { type: 'disconnected', reason });
    });

    client.on('message', async (msg) => {
        try {
            const chat = await msg.getChat();
            const contact = await msg.getContact();
            const messageData = {
                from: msg.from,
                to: msg.to,
                body: msg.body,
                type: msg.type,
                timestamp: msg.timestamp,
                fromName: contact.pushname || contact.name || msg.from,
                isGroup: chat.isGroup,
                chatName: chat.name
            };
            broadcast(sessionId, { type: 'message', data: messageData });
            saveIncomingMessage(messageData);
        } catch (e) {
            console.error(`[${sessionId}] Message handler error:`, e.message);
        }
    });

    client.initialize().catch(err => {
        console.error(`[${sessionId}] Init error:`, err.message);
        sessionData.status = 'init_error';
    });

    sessions.set(sessionId, sessionData);
    return sessionData;
}

function broadcast(sessionId, message) {
    const msg = JSON.stringify({ sessionId, ...message });
    wss.clients.forEach(client => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(msg);
        }
    });
}

function saveIncomingMessage(data) {
    try {
        const storagePath = '/www/AI_server/data/whatsapp_messages.json';
        const dir = path.dirname(storagePath);
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        let messages = [];
        if (fs.existsSync(storagePath)) {
            try { messages = JSON.parse(fs.readFileSync(storagePath, 'utf8')); } catch (e) {}
        }
        messages.push({
            from: data.from,
            to: data.to,
            text: data.body,
            type: data.type,
            direction: 'inbound',
            from_name: data.fromName,
            chat_name: data.chatName,
            is_group: data.isGroup,
            timestamp: new Date(data.timestamp * 1000).toISOString()
        });
        messages = messages.slice(-200);
        fs.writeFileSync(storagePath, JSON.stringify(messages, null, 2));
    } catch (e) {
        console.error('Save message error:', e.message);
    }
}

app.get('/health', (req, res) => {
    res.json({ status: 'ok', sessions: Array.from(sessions.keys()), uptime: process.uptime() });
});

app.get('/sessions', (req, res) => {
    const list = Array.from(sessions.values()).map(s => ({
        id: s.id,
        status: s.status,
        hasQR: !!s.qr,
        connectedAt: s.connectedAt
    }));
    res.json({ sessions: list });
});

app.post('/sessions/:id/init', async (req, res) => {
    const sessionId = req.params.id;
    const session = getOrCreateSession(sessionId);
    res.json({ success: true, status: session.status, message: 'Session initializing' });
});

app.get('/sessions/:id/qr', (req, res) => {
    const sessionId = req.params.id;
    const session = sessions.get(sessionId);
    if (!session) return res.status(404).json({ success: false, error: 'Session not found' });
    if (!session.qrImage) {
        return res.json({
            success: false,
            status: session.status,
            message: session.status === 'ready' ? 'Already connected' : 'QR code not ready yet, please wait...'
        });
    }
    res.json({
        success: true,
        status: session.status,
        qr: session.qr,
        qrImage: session.qrImage,
        message: 'Scan this QR code with your WhatsApp app'
    });
});

app.get('/sessions/:id/status', (req, res) => {
    const sessionId = req.params.id;
    const session = sessions.get(sessionId);
    if (!session) return res.json({ success: true, status: 'not_initialized', exists: false });
    res.json({
        success: true,
        status: session.status,
        exists: true,
        hasQR: !!session.qrImage,
        connectedAt: session.connectedAt
    });
});

app.post('/sessions/:id/logout', async (req, res) => {
    const sessionId = req.params.id;
    const session = sessions.get(sessionId);
    if (!session) return res.status(404).json({ success: false, error: 'Session not found' });
    try {
        await session.client.logout();
        await session.client.destroy();
        sessions.delete(sessionId);
        res.json({ success: true, message: 'Logged out' });
    } catch (e) {
        res.json({ success: false, message: e.message });
    }
});

app.post('/sessions/:id/send', async (req, res) => {
    const sessionId = req.params.id;
    const session = sessions.get(sessionId);
    if (!session) return res.status(404).json({ success: false, error: 'Session not found' });
    if (session.status !== 'ready') return res.json({ success: false, message: 'Not connected' });

    const { to, text } = req.body;
    if (!to || !text) return res.status(400).json({ success: false, message: 'Recipient and text required' });

    try {
        const cleanTo = to.replace(/[^\d]/g, '');
        const chatId = cleanTo.includes('@') ? cleanTo : `${cleanTo}@c.us`;
        const result = await session.client.sendMessage(chatId, text);
        res.json({ success: true, messageId: result.id._serialized });
    } catch (e) {
        res.json({ success: false, message: e.message });
    }
});

app.get('/sessions/:id/chats', async (req, res) => {
    const sessionId = req.params.id;
    const session = sessions.get(sessionId);
    if (!session) return res.status(404).json({ success: false, error: 'Session not found' });
    if (session.status !== 'ready') return res.json({ success: false, message: 'Not connected' });
    try {
        const chats = await session.client.getChats();
        const list = chats.slice(0, 50).map(c => ({
            id: c.id._serialized,
            name: c.name,
            isGroup: c.isGroup,
            lastMessage: c.lastMessage?.body || '',
            timestamp: c.lastMessage?.timestamp || c.timestamp
        }));
        res.json({ success: true, chats: list });
    } catch (e) {
        res.json({ success: false, message: e.message });
    }
});

wss.on('connection', (ws) => {
    console.log('WebSocket client connected');
    ws.on('message', (data) => {
        try {
            const msg = JSON.parse(data);
            if (msg.action === 'subscribe' && msg.sessionId) {
                const session = getOrCreateSession(msg.sessionId);
                ws.send(JSON.stringify({
                    sessionId: msg.sessionId,
                    type: 'subscribed',
                    status: session.status
                }));
            }
        } catch (e) {}
    });
    ws.on('close', () => console.log('WebSocket client disconnected'));
});

server.listen(PORT, '0.0.0.0', () => {
    console.log(`WhatsApp Web bridge listening on port ${PORT}`);
    console.log(`WebSocket available at ws://0.0.0.0:${PORT}/ws`);
});
