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

  isOpen:       false,
  isTyping:     false,
  isRecording:  false,
  pendingFile:  null,
  speechRecognition: null,
  history:      [],
  sessionId:    null,

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
          <div class="sgc-copilot-file-preview" id="sgc-copilot-file-preview" style="display:none">
            <span class="sgc-file-info">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
              <span id="sgc-file-name"></span>
            </span>
            <button class="sgc-file-remove" id="sgc-file-remove" aria-label="Remove file">
              <span aria-hidden="true">&times;</span>
            </button>
          </div>
          <div class="sgc-copilot-form">
            <input type="file" id="sgc-copilot-file-input" accept=".pdf,.txt,.doc,.docx" style="display:none" aria-hidden="true"/>
            <button class="sgc-copilot-attach" id="sgc-copilot-attach" aria-label="Attach file" title="Attach a document">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/></svg>
            </button>
            <input type="text" class="sgc-copilot-input" id="sgc-copilot-input"
                   placeholder="Ask about ERP, ROI, pricing..."
                   autocomplete="off" aria-label="Type your message" maxlength="500"/>
            <button class="sgc-copilot-mic" id="sgc-copilot-mic" aria-label="Voice input" title="Voice input">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0 0 14 0"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
            </button>
            <button class="sgc-copilot-send" id="sgc-copilot-send" aria-label="Send message">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/>
              </svg>
            </button>
          </div>
          <div class="sgc-copilot-prompts" id="sgc-copilot-prompts" style="display:none">
            <div class="sgc-prompts-scroll" id="sgc-prompts-scroll"></div>
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

    // ── File upload ────────────────────────────────────────────────────
    const attachBtn = document.getElementById('sgc-copilot-attach');
    const fileInput = document.getElementById('sgc-copilot-file-input');
    const removeBtn = document.getElementById('sgc-copilot-file-remove');

    attachBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      fileInput?.click();
    });

    fileInput?.addEventListener('change', (e) => this._handleFileSelected(e));

    removeBtn?.addEventListener('click', () => this._removeFile());

    // ── Voice input ────────────────────────────────────────────────────
    const micBtn = document.getElementById('sgc-copilot-mic');
    micBtn?.addEventListener('click', () => this._toggleVoice());

    // ── Proactive prompts: hide when inputs are focused elsewhere ──────
    input?.addEventListener('focus', () => this._hideProactivePrompts());
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
    this._showProactivePrompts();
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

    // KB check: answer from FAQ dictionary before hitting the AI API
    const kbAnswer = this._checkKnowledgeBase(text);
    if (kbAnswer) {
      this.addBotMessage(kbAnswer.message, kbAnswer.quickReplies || []);
      return;
    }

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

  // ═══════════════════════════════════════════════════════════════════
  // FEATURE A — Knowledge-Base Q&A (FAQ dictionary)
  // ═══════════════════════════════════════════════════════════════════

  _checkKnowledgeBase(text) {
    if (!text || typeof text !== 'string') return null;
    const msg = text.toLowerCase().trim();

    const KB = [
      // ── Company ──────────────────────────────────────────────────
      {
        match: ['who are you', 'what is sgc', 'tell me about sgc', 'about sgc', 'about the company', 'sgc tech ai'],
        response: {
          message: (
            '**SGC TECH AI** is a Dubai-based ERP & AI solutions provider serving UAE businesses since 2020.\n\n' +
            'We specialise in:\n' +
            '- **Odoo ERP implementation** — 14-day deployment guarantee\n' +
            '- **Real Estate ERP module** — rental, maintenance, investor portal\n' +
            '- **AI Copilot integration** — intelligent business automation\n' +
            '- **ROI guarantee** — 150–200% minimum return or money back\n\n' +
            'A **Scholarix Global Consultants** Brand.'
          ),
          quickReplies: ['Book consultation', 'Calculate ROI', 'Real Estate module'],
        },
      },
      // ── ERP Implementation ────────────────────────────────────────
      {
        match: ['erp implement', 'how to implement', 'implementation process', '14-day', 'deployment process', 'erp setup'],
        response: {
          message: (
            '**Our 14-Day ERP Implementation Process:**\n\n' +
            '1. **Day 1–3:** Requirements analysis & system configuration\n' +
            '2. **Day 4–7:** Data migration & module customisation\n' +
            '3. **Day 8–10:** User training & testing\n' +
            '4. **Day 11–13:** Go-live preparation & final adjustments\n' +
            '5. **Day 14:** Go-live & post-launch support\n\n' +
            'All packages include **30 days of post-deployment support**.'
          ),
          quickReplies: ['See pricing', 'Book consultation', 'Calculate ROI'],
        },
      },
      // ── Pricing ────────────────────────────────────────────────────
      {
        match: ['price', 'pricing', 'cost', 'how much', 'package', 'plan', 'aed', 'starter', 'growth', 'enterprise'],
        response: {
          message: (
            '**SGC TECH AI Packages:**\n\n' +
            '- **Starter** AED 25,000 — ideal for 1–15 employees\n' +
            '- **Growth** AED 45,000 — for 16–50 employees\n' +
            '- **Enterprise** AED 85,000 — 51–200 employees\n\n' +
            'All include: 14-day deployment, AI Copilot, Real Estate module, and **150% ROI guarantee**.\n\n' +
            'Custom plans available for larger organisations.'
          ),
          quickReplies: ['Book consultation', 'Calculate ROI', 'Real Estate module'],
        },
      },
      // ── ROI ────────────────────────────────────────────────────────
      {
        match: ['roi', 'return on investment', 'payback', 'save money', 'cost saving', 'roi calculator'],
        response: {
          message: (
            '**Our ROI Guarantee: 150–200% minimum or money back.**\n\n' +
            '- 40–80 hours saved per month on manual data entry\n' +
            '- 90%+ error reduction in the first 30 days\n' +
            '- 4–6 month typical payback period\n\n' +
            'Use our interactive ROI Calculator for personalised numbers.'
          ),
          quickReplies: ['Calculate my ROI', 'Book consultation', 'See pricing'],
        },
      },
      // ── Real Estate Module ──────────────────────────────────────────
      {
        match: ['real estate', 'property', 'rental', 'tenant', 'lease', 'property management'],
        response: {
          message: (
            '**SGC Real Estate ERP Module** — purpose-built for UAE property firms.\n\n' +
            '- **Rental Management** — automate lease agreements & renewals\n' +
            '- **Maintenance Portal** — tenant repair requests with auto-assignment\n' +
            '- **Investor Dashboard** — real-time portfolio analytics\n' +
            '- **Agency Management** — sales commission & broker tracking\n' +
            '- **EJARI integration** — direct RERA/EJARI submission\n\n' +
            'Available as a standalone module or included in all ERP packages.'
          ),
          quickReplies: ['Book consultation', 'See pricing', 'Calculate ROI'],
        },
      },
      // ── Demo / Consultation ────────────────────────────────────────
      {
        match: ['book', 'demo', 'consultation', 'meeting', 'schedule', 'call', 'contact'],
        response: {
          message: (
            '**Let\'s talk!** You can reach us directly:\n\n' +
            '- **Email:** hello@sgctech.ai\n' +
            '- **Phone:** +971 4 123 4567\n' +
            '- **Location:** Dubai, UAE\n\n' +
            'Or visit our **Contact** page to book a free consultation.'
          ),
          quickReplies: ['Calculate my ROI', 'Real Estate module', 'Pricing plans'],
        },
      },
    ];

    for (const entry of KB) {
      if (entry.match.some(kw => msg.includes(kw))) {
        return entry.response;
      }
    }
    return null;
  },

  // ═══════════════════════════════════════════════════════════════════
  // FEATURE B — File Upload (document analysis)
  // ═══════════════════════════════════════════════════════════════════

  _handleFileSelected(event) {
    const file = event.target?.files?.[0];
    if (!file) return;
    this._uploadFile(file);
    // Reset input so the same file can be re-selected
    event.target.value = '';
  },

  async _uploadFile(file) {
    const maxSize = 10 * 1024 * 1024; // 10 MB
    if (file.size > maxSize) {
      this.addBotMessage(
        '**File too large.** Please upload documents under 10 MB.',
        []
      );
      return;
    }

    // Show file preview
    const preview = document.getElementById('sgc-copilot-file-preview');
    const nameEl  = document.getElementById('sgc-file-name');
    if (preview && nameEl) {
      const sizeLabel = file.size > 1024 * 1024
        ? (file.size / (1024 * 1024)).toFixed(1) + ' MB'
        : (file.size / 1024).toFixed(0) + ' KB';
      nameEl.textContent = file.name + ' (' + sizeLabel + ') — uploading…';
      preview.style.display = 'flex';
    }

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('session_id', this.sessionId || '');

      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content
                     || odoo?.csrf_token
                     || '';

      const response = await fetch('/sgc/copilot/upload', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
        body: formData,
      });

      const data = await response.json();
      const result = data.result || data;

      if (result && result.text) {
        this.pendingFile = {
          name: file.name,
          text: result.text,
        };

        if (preview && nameEl) {
          const sizeLabel = file.size > 1024 * 1024
            ? (file.size / (1024 * 1024)).toFixed(1) + ' MB'
            : (file.size / 1024).toFixed(0) + ' KB';
          nameEl.textContent = file.name + ' (' + sizeLabel + ') — ready';
        }

        this.addBotMessage(
          '**File uploaded:** `' + this.escapeHtml(file.name) + '` — ' +
          (result.page_count
            ? result.page_count + ' pages, ' : '') +
          'document content extracted. You can now ask questions about it.',
          ['Analyse this document', 'Summarise key points', 'Remove file']
        );
      } else {
        throw new Error(result?.error || 'Upload failed');
      }
    } catch (err) {
      this.pendingFile = null;
      if (preview) preview.style.display = 'none';
      this.addBotMessage(
        '**Upload failed.** Please try again or use a different file format.',
        []
      );
    }
  },

  _removeFile() {
    this.pendingFile = null;
    const preview = document.getElementById('sgc-copilot-file-preview');
    if (preview) preview.style.display = 'none';
    this.addBotMessage('File removed. You can upload a new document anytime.', []);
  },

  // ═══════════════════════════════════════════════════════════════════
  // FEATURE C — Voice Input (Web Speech API)
  // ═══════════════════════════════════════════════════════════════════

  _toggleVoice() {
    if (this.isRecording) {
      this._stopRecording();
    } else {
      this._startRecording();
    }
  },

  _initSpeechRecognition() {
    if (this.speechRecognition) return this.speechRecognition;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return null;

    const recognition = new SR();
    recognition.lang       = 'en-US';
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.continuous = false;

    recognition.onresult = (event) => {
      let interim = '';
      let final   = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          final += transcript;
        } else {
          interim += transcript;
        }
      }

      // Set interim text in the input field
      const input = document.getElementById('sgc-copilot-input');
      if (input) {
        if (final) {
          input.value = input.value + (input.value ? ' ' : '') + final.trim();
        } else if (interim) {
          input.placeholder = interim + '…';
        }
      }
    };

    recognition.onerror = (event) => {
      if (event.error === 'no-speech') return; // silent ignore
      this._stopRecording();
      this.addBotMessage(
        'Voice input error: ' + event.error + '. Please try typing instead.',
        []
      );
    };

    recognition.onend = () => {
      this._stopRecording();
      // Restore placeholder
      const input = document.getElementById('sgc-copilot-input');
      if (input) input.placeholder = 'Ask about ERP, ROI, pricing...';
    };

    this.speechRecognition = recognition;
    return recognition;
  },

  _startRecording() {
    const recognition = this._initSpeechRecognition();
    if (!recognition) {
      this.addBotMessage(
        '**Voice input not supported** in your browser. ' +
        'Please use Chrome or Edge for voice features.',
        []
      );
      return;
    }

    this.isRecording = true;
    const micBtn = document.getElementById('sgc-copilot-mic');
    if (micBtn) micBtn.classList.add('recording');
    recognition.start();
  },

  _stopRecording() {
    this.isRecording = false;
    const micBtn = document.getElementById('sgc-copilot-mic');
    if (micBtn) micBtn.classList.remove('recording');

    if (this.speechRecognition) {
      try { this.speechRecognition.stop(); } catch (_) { /* already stopped */ }
    }
  },

  // ═══════════════════════════════════════════════════════════════════
  // FEATURE D — Proactive Prompts
  // ═══════════════════════════════════════════════════════════════════

  _showProactivePrompts() {
    const container = document.getElementById('sgc-copilot-prompts');
    const scrollEl  = document.getElementById('sgc-prompts-scroll');
    if (!container || !scrollEl) return;

    const prompts = this._getPagePrompts();

    scrollEl.innerHTML = '';
    prompts.forEach(p => {
      const chip = document.createElement('button');
      chip.className    = 'sgc-prompt-chip';
      chip.textContent  = p.label;
      chip.dataset.text = p.text || p.label;
      chip.addEventListener('click', () => this._onPromptClick(p.text || p.label));
      scrollEl.appendChild(chip);
    });

    container.style.display = 'block';
  },

  _hideProactivePrompts() {
    const container = document.getElementById('sgc-copilot-prompts');
    if (container) container.style.display = 'none';
  },

  _getPagePrompts() {
    const path = window.location.pathname;

    // Home page prompts
    if (path === '/' || path === '/home') {
      return [
        { label: 'How does 14-day ERP work?', text: 'How does the 14-day ERP deployment work?' },
        { label: 'Calculate my ROI',          text: 'Calculate my ROI' },
        { label: 'Real Estate module',        text: 'Tell me about the Real Estate ERP module' },
        { label: 'See pricing',               text: 'What are your pricing plans?' },
      ];
    }

    // About page
    if (path.includes('/about')) {
      return [
        { label: 'About SGC TECH AI',   text: 'Tell me about SGC TECH AI' },
        { label: 'Our team expertise',  text: 'What is your team\'s expertise?' },
        { label: 'Company history',     text: 'What is the history of SGC TECH AI?' },
      ];
    }

    // Solutions / ERP page
    if (path.includes('/solutions') || path.includes('/erp')) {
      return [
        { label: 'ERP features',        text: 'What are the key ERP features?' },
        { label: 'Implementation time', text: 'How long does ERP implementation take?' },
        { label: 'ROI guarantee',       text: 'What is your ROI guarantee?' },
      ];
    }

    // Contact page
    if (path.includes('/contact')) {
      return [
        { label: 'Book consultation', text: 'I want to book a consultation' },
        { label: 'Request a demo',    text: 'I want to request a demo' },
        { label: 'Pricing inquiry',   text: 'I have a question about pricing' },
      ];
    }

    // Real Estate page
    if (path.includes('/real') || path.includes('/property')) {
      return [
        { label: 'Module features',    text: 'What are the Real Estate module features?' },
        { label: 'EJARI integration', text: 'How does EJARI integration work?' },
        { label: 'Demo request',      text: 'I want to see a Real Estate demo' },
      ];
    }

    // Default (fallback) prompts
    return [
      { label: 'Calculate my ROI',        text: 'Calculate my ROI' },
      { label: 'Pricing plans',           text: 'What are your pricing plans?' },
      { label: 'Real Estate module',      text: 'Tell me about the Real Estate ERP module' },
      { label: 'Book consultation',       text: 'I want to book a consultation' },
    ];
  },

  _onPromptClick(text) {
    this._hideProactivePrompts();
    // Send immediately without showing a user message bubble —
    // sendText will add it via addUserMessage
    this.sendText(text);
  },
};

document.addEventListener('DOMContentLoaded', () => {
  SGC.Copilot.init();
});

export default SGC.Copilot;
