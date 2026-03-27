/**
 * Doc Digest Chat Panel — SSE streaming + text selection integration.
 *
 * Usage: const chat = new ChatPanel('http://localhost:8765');
 */

class ChatPanel {
  constructor(serverUrl = 'http://localhost:8765') {
    this.serverUrl = serverUrl;
    this.sessionId = crypto.randomUUID();
    this.history = [];
    this.isOpen = false;
    this.isStreaming = false;

    this._panel = document.getElementById('chat-panel');
    this._messages = document.getElementById('chat-messages');
    this._input = document.getElementById('chat-input');
    this._sendBtn = document.getElementById('chat-send');
    this._toggle = document.getElementById('chat-toggle');
    this._close = document.getElementById('chat-close');
    this._popup = document.getElementById('selection-popup');

    this._bindEvents();
    this._bindTextSelection();
  }

  /* ── Event Binding ─────────────────────────────────── */

  _bindEvents() {
    this._sendBtn.addEventListener('click', () => this._onSend());
    this._input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this._onSend();
      }
    });
    this._toggle.addEventListener('click', () => this.toggle());
    this._close.addEventListener('click', () => this.close());

    // Popup action buttons
    document.getElementById('popup-ask')?.addEventListener('click', () => this._popupAction('ask'));
    document.getElementById('popup-factcheck')?.addEventListener('click', () => this._popupAction('factcheck'));
    document.getElementById('popup-summarize')?.addEventListener('click', () => this._popupAction('summarize'));
  }

  _bindTextSelection() {
    let selectionTimeout;
    document.addEventListener('mouseup', (e) => {
      // Ignore clicks inside chat panel or popup
      if (e.target.closest('#chat-panel') || e.target.closest('#selection-popup')) return;

      clearTimeout(selectionTimeout);
      selectionTimeout = setTimeout(() => {
        const selection = window.getSelection();
        const text = selection.toString().trim();
        if (text.length > 10) {
          const sectionEl = e.target.closest('[data-section-id]');
          const sectionId = sectionEl?.dataset.sectionId || null;
          this._selectedText = text;
          this._selectedSection = sectionId;
          this._showPopup(e.pageX, e.pageY);
        } else {
          this._hidePopup();
        }
      }, 200);
    });

    // Hide popup on scroll or click elsewhere
    document.addEventListener('mousedown', (e) => {
      if (!e.target.closest('#selection-popup')) {
        this._hidePopup();
      }
    });
  }

  /* ── Chat Core ─────────────────────────────────────── */

  async _onSend() {
    const message = this._input.value.trim();
    if (!message || this.isStreaming) return;
    this._input.value = '';
    this._appendMessage('user', message);
    await this.sendMessage(message);
  }

  async sendMessage(message, sectionId = null) {
    if (this.isStreaming) return;
    this.isStreaming = true;

    if (!this.isOpen) this.open();

    const body = {
      message,
      section_id: sectionId || this._currentSection || null,
      session_id: this.sessionId,
      conversation_history: this.history.slice(-10),
    };

    this.history.push({ role: 'user', content: message });

    const assistantEl = this._appendMessage('assistant', '');
    const contentEl = assistantEl.querySelector('.msg-content');

    try {
      const response = await fetch(`${this.serverUrl}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) throw new Error(`Server error: ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === 'text') {
              fullText += event.content;
              contentEl.innerHTML = this._renderMarkdown(fullText);
              this._scrollToBottom();
            } else if (event.type === 'tool_call') {
              const toolTag = document.createElement('span');
              toolTag.className = 'tool-tag';
              toolTag.textContent = `Using: ${event.tool}`;
              contentEl.appendChild(toolTag);
            }
          } catch { /* skip malformed events */ }
        }
      }

      this.history.push({ role: 'assistant', content: fullText });
    } catch (err) {
      contentEl.textContent = `Error: ${err.message}. Is the chat server running?`;
      contentEl.classList.add('error');
    } finally {
      this.isStreaming = false;
    }
  }

  /* ── Selection Popup ───────────────────────────────── */

  _showPopup(x, y) {
    const popup = this._popup;
    popup.style.left = `${x}px`;
    popup.style.top = `${y - 50}px`;
    popup.classList.add('visible');

    // Keep popup on screen
    const rect = popup.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
      popup.style.left = `${window.innerWidth - rect.width - 10}px`;
    }
    if (rect.top < 0) {
      popup.style.top = `${y + 20}px`;
    }
  }

  _hidePopup() {
    this._popup.classList.remove('visible');
  }

  _popupAction(action) {
    const text = this._selectedText;
    const section = this._selectedSection;
    this._hidePopup();
    window.getSelection().removeAllRanges();

    let message;
    switch (action) {
      case 'ask':
        message = `Explain this passage: "${text}"`;
        break;
      case 'factcheck':
        message = `Fact check this claim: "${text}"`;
        break;
      case 'summarize':
        message = `Summarize this in simpler terms: "${text}"`;
        break;
    }

    this._appendMessage('user', message);
    this.sendMessage(message, section);
  }

  /* ── Quick Actions ─────────────────────────────────── */

  askAbout(text, sectionId) {
    const message = `Explain this: "${text}"`;
    this._appendMessage('user', message);
    this.sendMessage(message, sectionId);
  }

  factCheck(text, sectionId) {
    const message = `Fact check: "${text}"`;
    this._appendMessage('user', message);
    this.sendMessage(message, sectionId);
  }

  summarize(text, sectionId) {
    const message = `Summarize: "${text}"`;
    this._appendMessage('user', message);
    this.sendMessage(message, sectionId);
  }

  async loadFollowUps(sectionId) {
    try {
      const res = await fetch(`${this.serverUrl}/api/followups`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ section_id: sectionId }),
      });
      if (!res.ok) return;
      const data = await res.json();
      this._renderFollowUps(data.questions, sectionId);
    } catch { /* silently fail */ }
  }

  _renderFollowUps(questions, sectionId) {
    const container = document.createElement('div');
    container.className = 'followups';
    container.innerHTML = '<p class="followups-label">Suggested questions:</p>';
    for (const q of questions) {
      const btn = document.createElement('button');
      btn.className = 'followup-btn';
      btn.textContent = q;
      btn.addEventListener('click', () => {
        this._appendMessage('user', q);
        this.sendMessage(q, sectionId);
      });
      container.appendChild(btn);
    }
    this._messages.appendChild(container);
    this._scrollToBottom();
  }

  /* ── Panel Visibility ──────────────────────────────── */

  toggle() {
    this.isOpen ? this.close() : this.open();
  }

  open() {
    this.isOpen = true;
    this._panel.classList.add('open');
    document.body.classList.add('chat-open');
    this._input.focus();
  }

  close() {
    this.isOpen = false;
    this._panel.classList.remove('open');
    document.body.classList.remove('chat-open');
  }

  /* ── Rendering Helpers ─────────────────────────────── */

  _appendMessage(role, content) {
    const el = document.createElement('div');
    el.className = `msg msg-${role}`;
    el.innerHTML = `<div class="msg-content">${this._renderMarkdown(content)}</div>`;
    this._messages.appendChild(el);
    this._scrollToBottom();
    return el;
  }

  _scrollToBottom() {
    this._messages.scrollTop = this._messages.scrollHeight;
  }

  _renderMarkdown(text) {
    if (!text) return '';
    // Minimal markdown: bold, italic, code, links, line breaks
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`(.+?)`/g, '<code>$1</code>')
      .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank">$1</a>')
      .replace(/\n/g, '<br>');
  }
}

/* ── ToC Active Section Tracking ─────────────────────── */

function initTocTracking() {
  const sections = document.querySelectorAll('.doc-section');
  const tocLinks = document.querySelectorAll('.toc-link');

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          const id = entry.target.id;
          tocLinks.forEach((link) => {
            link.classList.toggle('active', link.getAttribute('href') === `#${id}`);
          });
        }
      }
    },
    { rootMargin: '-10% 0px -80% 0px' }
  );

  sections.forEach((section) => observer.observe(section));
}

/* ── Initialization ──────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
  // SERVER_URL is set by Claude during generation
  const SERVER_URL = window.DOC_DIGEST_SERVER_URL || 'http://localhost:8765';
  window.chatPanel = new ChatPanel(SERVER_URL);
  initTocTracking();

  // Mobile ToC toggle
  const tocToggle = document.getElementById('toc-toggle');
  const tocSidebar = document.getElementById('toc-sidebar');
  if (tocToggle && tocSidebar) {
    tocToggle.addEventListener('click', () => {
      tocSidebar.classList.toggle('open');
    });
  }
});
