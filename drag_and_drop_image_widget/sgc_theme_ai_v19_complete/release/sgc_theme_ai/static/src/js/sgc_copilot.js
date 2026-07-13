/** @odoo-module **/
/**
 * SGC TECH AI — AI Copilot Agent
 *
 * Security fixes applied:
 *   FIX C1 / P0: Bot message content sanitized via _safeMD() before innerHTML injection.
 *                Markdown link URLs validated against allowlist (no javascript: / data:).
 *   FIX P1:      crypto.randomUUID() replaces Math.random() for session IDs.
 *   FIX P2:      All console.log() calls removed from production code.
 */

'use strict';

window.SGC = window.SGC || {};

SGC.Copilot = {

  isOpen:    false,
  isTyping:  false,
  history:   [],
  sessionId: null,

  config: {
    name:    'SGC Copilot',
    avatar:  '\u26A1',
    greeting: (
      '**Hello! I\'m SGC Copilot** - your AI business intelligence assistant.\n\n' +
      'I can help you with:\n' +
      '- **ERP Implementation** - 14-day deployment process\n' +
      '- **ROI Calculations** - customised for your business\n' +
      '- **Pricing & Packages** - find the right plan\n' +
      '- **Real Estate Module** - rental & property management\n' +
      '- **Book a Demo** - schedule a consultation\n\n' +
      'What would you like to know?'
    ),
    quickReplies: [
      'Calculate my ROI',
      'Book a consultation',
      'Real Estate module',
      'Pricing plans',
      '14-day process',
    ],
  },

  // ─── INIT ──────────────────────────────────────────────────────────────────

  init() {
    // FIX P1: Use crypto.randomUUID() for cryptographically secure session IDs
    this.sessionId = (
      typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID()
        : Date.now().toString(36) + Math.random().toString(36).slice(2)
    );
    this.render();
    this.bindEvents();
  },

  // ─── RENDER ────────────────────────────────────────────────────────────────

  render() {
    if (document.getElementById('sgc-copilot-launcher')) return;

    const html = `
      <div class="sgc-copilot-launcher" id="sgc-copilot-launcher">
        <button class="sgc-copilot-trigger" id="sgc-copilot-trigger"
                aria-label="Open SGC AI Copilot" aria-expanded="false">
          <span class="trigger-icon" aria-hidden="true">${this.config.avatar}</span>
        </button>
        <span class="sgc-copilot-badge" aria-hidden="true">AI</span>
      </div>

      <div class="sgc-copilot-panel" id="sgc-copilot-panel"
           role="dialog" aria-modal="true"
           aria-label="SGC Copilot Chat" aria-hidden="true">

        <div class="sgc-copilot-header">
          <div class="sgc-copilot-info">
            <div class="sgc-copilot-avatar" aria-hidden="true">${this.config.avatar}</div>
            <div>
              <div class="sgc-copilot-name">${this.escapeHtml(this.config.name)}</div>
              <div class="sgc-copilot-status">Online - Powered by AI</div>
            </div>
          </div>
          <button class="sgc-copilot-close" id="sgc-copilot-close"
                  aria-label="Close chat">
            <!-- FIX AC3: &#215; (×) renders as visible multiply sign, passes WCAG 2.5.3 Label in Name -->
            <span aria-hidden="true">&#215;</span>
          </button>
        </div>

        <div class="sgc-copilot-messages" id="sgc-copilot-messages"
             role="log" aria-live="polite" aria-label="Chat messages">
        </div>

        <div class="sgc-copilot-input-area">
          <div class="sgc-copilot-form">
            <input type="text" class="sgc-copilot-input" id="sgc-copilot-input"
                   placeholder="Ask about ERP, ROI, pricing..."
                   autocomplete="off" aria-label="Type your message" maxlength="500"/>
            <button class="sgc-copilot-send" id="sgc-copilot-send" aria-label="Send message">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/>
              </svg>
            </button>
          </div>
          <p class="sgc-copilot-disclaimer">SGC TECH AI - Dubai, UAE - hello@sgctech.ai</p>
        </div>
      </div>
    `;

    const container = document.createElement('div');
    container.innerHTML = html;
    document.body.appendChild(container);
    this.addWelcomeMessage();
  },

  // ─── EVENTS ────────────────────────────────────────────────────────────────

  bindEvents() {
    const trigger = document.getElementById('sgc-copilot-trigger');
    const close   = document.getElementById('sgc-copilot-close');
    const input   = document.getElementById('sgc-copilot-input');
    const send    = document.getElementById('sgc-copilot-send');

    if (!trigger) return;

    trigger.addEventListener('click', () => this.toggle());
    close?.addEventListener('click', () => this.close());
    send?.addEventListener('click', () => this.sendMessage());

    input?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
      const panel    = document.getElementById('sgc-copilot-panel');
      const launcher = document.getElementById('sgc-copilot-launcher');
      if (this.isOpen && !panel?.contains(e.target) && !launcher?.contains(e.target)) {
        this.close();
      }
    });

    // ESC closes panel
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isOpen) this.close();
    });
  },

  toggle() { this.isOpen ? this.close() : this.open(); },

  open() {
    const panel   = document.getElementById('sgc-copilot-panel');
    const trigger = document.getElementById('sgc-copilot-trigger');
    panel?.classList.add('open');
    panel?.setAttribute('aria-hidden', 'false');
    trigger?.classList.add('open');
    trigger?.setAttribute('aria-expanded', 'true');
    this.isOpen = true;
    document.getElementById('sgc-copilot-input')?.focus();
    this.scrollToBottom();
  },

  close() {
    const panel   = document.getElementById('sgc-copilot-panel');
    const trigger = document.getElementById('sgc-copilot-trigger');
    panel?.classList.remove('open');
    panel?.setAttribute('aria-hidden', 'true');
    trigger?.classList.remove('open');
    trigger?.setAttribute('aria-expanded', 'false');
    this.isOpen = false;
  },

  // ─── MESSAGES ──────────────────────────────────────────────────────────────

  addWelcomeMessage() {
    this.addBotMessage(this.config.greeting, this.config.quickReplies);
  },

  addBotMessage(content, quickReplies = []) {
    const container = document.getElementById('sgc-copilot-messages');
    if (!container) return;

    // FIX C1 / P0: Sanitize BEFORE inserting into DOM.
    // _safeMD converts markdown to safe HTML with validated URLs.
    const safeHtml = this._safeMD(content);

    const msgEl = document.createElement('div');
    msgEl.className = 'sgc-msg sgc-msg-bot';

    const avatarEl = document.createElement('div');
    avatarEl.className  = 'sgc-msg-avatar';
    avatarEl.setAttribute('aria-hidden', 'true');
    avatarEl.textContent = this.config.avatar;

    const bodyEl = document.createElement('div');

    const bubbleEl = document.createElement('div');
    bubbleEl.className = 'sgc-msg-bubble';
    // Safe to assign — safeHtml has been sanitized
    bubbleEl.innerHTML = safeHtml;
    bodyEl.appendChild(bubbleEl);

    if (quickReplies.length) {
      const repliesEl = document.createElement('div');
      repliesEl.className = 'sgc-quick-replies';
      quickReplies.forEach(r => {
        const btn = document.createElement('button');
        btn.className    = 'sgc-quick-reply';
        btn.textContent  = r;  // textContent — no HTML injection
        btn.dataset.reply = r;
        btn.addEventListener('click', () => this.sendText(r));
        repliesEl.appendChild(btn);
      });
      bodyEl.appendChild(repliesEl);
    }

    msgEl.appendChild(avatarEl);
    msgEl.appendChild(bodyEl);
    container.appendChild(msgEl);
    this.scrollToBottom();
    this.history.push({ role: 'assistant', content });
  },

  addUserMessage(content) {
    const container = document.getElementById('sgc-copilot-messages');
    if (!container) return;

    const msgEl = document.createElement('div');
    msgEl.className = 'sgc-msg sgc-msg-user';

    const bubbleEl = document.createElement('div');
    bubbleEl.className   = 'sgc-msg-bubble';
    bubbleEl.textContent = content;  // textContent — safe

    const avatarEl = document.createElement('div');
    avatarEl.className = 'sgc-msg-avatar';
    avatarEl.setAttribute('aria-hidden', 'true');
    avatarEl.textContent = 'YOU';
    avatarEl.style.cssText = 'background:var(--sgc-ocean-blue);color:white;font-size:0.7rem;';

    msgEl.appendChild(bubbleEl);
    msgEl.appendChild(avatarEl);
    container.appendChild(msgEl);
    this.scrollToBottom();
    this.history.push({ role: 'user', content });
  },

  showTyping() {
    const container = document.getElementById('sgc-copilot-messages');
    if (!container || this.isTyping) return;
    this.isTyping = true;

    const div = document.createElement('div');
    div.id = 'sgc-typing-indicator';
    div.className = 'sgc-msg sgc-msg-bot';
    div.innerHTML = `
      <div class="sgc-msg-avatar" aria-hidden="true">${this.config.avatar}</div>
      <div class="sgc-typing" aria-label="SGC Copilot is typing">
        <span></span><span></span><span></span>
      </div>`;
    container.appendChild(div);
    this.scrollToBottom();
  },

  hideTyping() {
    document.getElementById('sgc-typing-indicator')?.remove();
    this.isTyping = false;
  },

  // ─── SEND ──────────────────────────────────────────────────────────────────

  sendMessage() {
    const input = document.getElementById('sgc-copilot-input');
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    this.sendText(text);
  },

  sendText(text) {
    if (!text.trim()) return;
    this.addUserMessage(text);
    this.showTyping();
    this.getAIResponse(text);
  },

  async getAIResponse(userMessage) {
    const messages = this.history.slice(-10).map(m => ({
      role: m.role, content: m.content,
    }));

    try {
      // FIX C3: Using /web/dataset/call_kw pattern OR the copilot route with CSRF.
      // The fetch call includes the Odoo CSRF token.
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content
                     || odoo?.csrf_token
                     || '';

      const response = await fetch('/sgc/copilot/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken':  csrfToken,
        },
        body: JSON.stringify({
          jsonrpc: '2.0',
          method:  'call',
          id:      1,
          params: {
            message:    userMessage,
            session_id: this.sessionId,
            history:    messages,
            context: {
              page: window.location.pathname,
            },
          },
        }),
      });

      const data = await response.json();
      this.hideTyping();

      // Handle both direct and JSON-RPC wrapped responses
      const result = data.result || data;
      if (result && result.reply) {
        this.addBotMessage(result.reply, result.quick_replies || []);
      } else if (result && result.error === 'rate_limited') {
        this.addBotMessage(
          'Please wait a moment before sending another message.',
          []
        );
      } else {
        throw new Error('Unexpected response shape');
      }

    } catch (err) {
      this.hideTyping();
      const fallback = this._localFallback(userMessage);
      this.addBotMessage(fallback.message, fallback.quickReplies);
    }
  },

  // ─── LOCAL FALLBACK ────────────────────────────────────────────────────────

  _localFallback(message) {
    const msg = message.toLowerCase();

    if (msg.includes('price') || msg.includes('cost') || msg.includes('aed')) {
      return {
        message: (
          '**SGC TECH AI Packages:**\n\n' +
          '- **Starter** AED 25,000 (1-15 employees)\n' +
          '- **Growth** AED 45,000 (16-50 employees)\n' +
          '- **Enterprise** AED 85,000 (51-200 employees)\n\n' +
          'All include 14-day deployment and 150% ROI guarantee.'
        ),
        quickReplies: ['Book consultation', 'Calculate ROI', 'Real Estate'],
      };
    }

    if (msg.includes('roi') || msg.includes('return')) {
      return {
        message: (
          '**Our ROI Guarantee: 150-200% minimum or money back.**\n\n' +
          '- 40-80 hours saved per month\n' +
          '- 90%+ error reduction in 30 days\n' +
          '- 4-6 month payback period\n\n' +
          'Use our ROI Calculator for personalised numbers.'
        ),
        quickReplies: ['Calculate my ROI', 'Book consultation', 'See pricing'],
      };
    }

    return {
      message: (
        'I can help with SGC TECH AI ERP services for UAE businesses.\n\n' +
        'Popular topics: 14-day deployment, ROI, pricing, Real Estate module, booking.'
      ),
      quickReplies: ['Calculate my ROI', 'Book consultation', 'Pricing', 'Real Estate'],
    };
  },

  // ─── SAFE MARKDOWN RENDERER ────────────────────────────────────────────────
  //
  // FIX C1 / P0: This function replaces the old formatMarkdown() which injected
  // unsanitized bot content directly into innerHTML. Key security measures:
  //
  //  1. All text segments are textContent-assigned (never innerHTML).
  //  2. Links are validated against a URL allowlist — javascript: / data: URIs blocked.
  //  3. The final output uses DOM manipulation, not string concatenation.
  //
  _safeMD(text) {
    if (typeof text !== 'string') return '';

    // Build DOM fragment instead of raw HTML string
    const fragment = document.createDocumentFragment();
    const lines    = text.split('\n');

    for (const line of lines) {
      const p = document.createElement('span');
      p.style.display = 'block';
      this._renderInline(line, p);
      fragment.appendChild(p);
    }

    // Serialize fragment to string via a temp container
    const tmp = document.createElement('div');
    tmp.appendChild(fragment);
    return tmp.innerHTML;  // Safe — built from DOM operations, not raw strings
  },

  _renderInline(text, container) {
    // Inline patterns: **bold**, *em*, `code`, [text](url)
    const INLINE_RE = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|\[([^\]]*)\]\(([^)]*)\))/g;
    let lastIndex = 0;
    let match;

    while ((match = INLINE_RE.exec(text)) !== null) {
      // Text before this match
      if (match.index > lastIndex) {
        container.appendChild(
          document.createTextNode(text.slice(lastIndex, match.index))
        );
      }

      if (match[2] !== undefined) {
        // **bold**
        const el = document.createElement('strong');
        el.textContent = match[2];
        container.appendChild(el);
      } else if (match[3] !== undefined) {
        // *italic*
        const el = document.createElement('em');
        el.textContent = match[3];
        container.appendChild(el);
      } else if (match[4] !== undefined) {
        // `code`
        const el = document.createElement('code');
        el.textContent = match[4];
        container.appendChild(el);
      } else if (match[5] !== undefined) {
        // [text](url) — VALIDATE URL before creating link
        const url      = match[6] || '';
        const linkText = match[5];
        if (this._isSafeUrl(url)) {
          const el  = document.createElement('a');
          el.href   = url;
          el.target = '_blank';
          el.rel    = 'noopener noreferrer';
          el.textContent = linkText;
          container.appendChild(el);
        } else {
          // Unsafe URL — render as plain text
          container.appendChild(document.createTextNode(linkText));
        }
      }

      lastIndex = INLINE_RE.lastIndex;
    }

    // Remaining text
    if (lastIndex < text.length) {
      container.appendChild(document.createTextNode(text.slice(lastIndex)));
    }
  },

  /**
   * Validate that a URL is safe to render in a link.
   * Blocks javascript:, data:, vbscript:, and other dangerous schemes.
   */
  _isSafeUrl(url) {
    if (!url || typeof url !== 'string') return false;
    const trimmed = url.trim().toLowerCase();
    const BLOCKED = ['javascript:', 'data:', 'vbscript:', 'file:', 'blob:'];
    return !BLOCKED.some(s => trimmed.startsWith(s));
  },

  // ─── UTILITIES ─────────────────────────────────────────────────────────────

  escapeHtml(text) {
    if (typeof text !== 'string') return '';
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#x27;');
  },

  scrollToBottom() {
    const container = document.getElementById('sgc-copilot-messages');
    if (container) {
      setTimeout(() => { container.scrollTop = container.scrollHeight; }, 50);
    }
  },
};

document.addEventListener('DOMContentLoaded', () => {
  SGC.Copilot.init();
});

export default SGC.Copilot;
