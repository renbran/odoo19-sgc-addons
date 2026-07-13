/** @odoo-module **/
import { Component, useState, onWillStart, onWillDestroy, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class SgcChatPanel extends Component {
    static template = "sgc_persona.SgcChatPanel";

    setup() {
        this.state = useState({
            personas: [],
            selectedPersona: null,
            messages: [],
            inputValue: "",
            loading: false,
            streaming: false,
            abortController: null,
            error: null,
        });
        this.orm = useService("orm");
        this.notification = useService("notification");

        onWillStart(async () => {
            await this._loadPersonas();
        });

        onWillDestroy(() => {
            this._cancelStream();
        });
    }

    async _loadPersonas() {
        try {
            const allAssistants = await this.orm.searchRead(
                "llm.assistant",
                [["code", "!=", false]],
                ["id", "name", "code"],
                { order: "name" }
            );
            this.state.personas = allAssistants;
        } catch (err) {
            this.state.error = "Failed to load personas.";
        }
    }

    async selectPersona(ev) {
        const assistantId = parseInt(ev.target.value, 10);
        if (!assistantId) {
            this.state.selectedPersona = null;
            return;
        }
        this.state.selectedPersona = this.state.personas.find(
            (p) => p.id === assistantId
        );
        this.state.messages = [];
        this.state.error = null;
        this._addSystemMessage(
            `Switched to ${this.state.selectedPersona.name}. How can I help you?`
        );
    }

    onInputKeyup(ev) {
        if (ev.key === 'Enter') {
            this.sendMessage();
        }
    }

    async sendMessage() {
        const text = this.state.inputValue.trim();
        if (!text || !this.state.selectedPersona) {
            return;
        }
        console.warn("[SGC Persona] sendMessage called", { text, persona: this.state.selectedPersona.code });

        this.state.messages.push({
            id: Date.now(),
            role: "user",
            content: text,
        });
        this.state.inputValue = "";
        this.state.loading = true;
        this.state.streaming = true;
        this.state.error = null;

        const assistantMsg = {
            id: Date.now() + 1,
            role: "assistant",
            content: "",
        };
        this.state.messages.push(assistantMsg);

        await this._streamResponse(text);
    }

    async _streamResponse(userMessage) {
        this._cancelStream();
        const ac = new AbortController();
        this.state.abortController = ac;

        const lastMsg = this.state.messages[this.state.messages.length - 1];
        console.warn("[SGC Persona] _streamResponse starting fetch", { userMessage });

        try {
            const formData = new FormData();
            formData.append("persona_code", this.state.selectedPersona.code);
            formData.append("message", userMessage);

            const resp = await fetch("/sgc/persona/generate", {
                method: "POST",
                body: formData,
                signal: ac.signal,
            });
            console.warn("[SGC Persona] fetch returned", { status: resp.status, ok: resp.ok });

            if (!resp.ok) {
                throw new Error(`HTTP ${resp.status}`);
            }

            const data = await resp.json();
            console.warn("[SGC Persona] response parsed", { hasContent: !!data.content, persona_code: data.persona_code });

            if (data.error) {
                throw new Error(data.error);
            }
            if (!data.content) {
                console.warn("[SGC Persona] WARNING: empty content in response", data);
            }
            this._handleResponse(data);
        } catch (err) {
            console.warn("[SGC Persona] fetch error", { name: err.name, message: err.message });
            if (err.name !== "AbortError") {
                lastMsg.content = "I'm sorry, I encountered an error. Please try again.";
                this.notification.add("AI Assistant encountered an error: " + err.message, { type: "danger" });
            }
        } finally {
            this.state.loading = false;
            this.state.streaming = false;
            this.state.abortController = null;
        }
    }

    _handleResponse(data) {
        const lastMsg = this.state.messages[this.state.messages.length - 1];
        if (!lastMsg || lastMsg.role !== "assistant") {
            console.warn("[SGC Persona] _handleResponse: last message not assistant", { lastMsg });
            return;
        }
        console.warn("[SGC Persona] _handleResponse setting content", { oldLength: lastMsg.content.length, newLength: (data.content || "").length });
        lastMsg.content = data.content || "";
    }

    _cancelStream() {
        if (this.state.abortController) {
            this.state.abortController.abort();
            this.state.abortController = null;
        }
    }

    _addSystemMessage(text) {
        this.state.messages.push({
            id: Date.now(),
            role: "system",
            content: text,
        });
    }

    formatContent(content) {
        if (!content) return markup("");
        const html = this._markdownToHtml(content);
        const result = markup(html);
        return result;
    }

    /**
     * Convert simple markdown to HTML for chat display.
     * Handles: **bold**, *italic*, `code`, ```code blocks```,
     * [links](url), # headers, -/* bullet lists, 1. numbered lists.
     */
    _markdownToHtml(text) {
        // Escape HTML entities first to prevent XSS
        let html = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        // Fenced code blocks (```...```)
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
            const langClass = lang ? ` class="language-${lang}"` : "";
            return `<pre><code${langClass}>${code.trim()}</code></pre>`;
        });

        // Inline code (remaining `...` not inside a block)
        html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

        // Bold
        html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
        // Italic
        html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");

        // Links [text](url)
        html = html.replace(
            /\[([^\]]+)\]\(([^)]+)\)/g,
            '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
        );

        // Headers (# ## ### ####)
        html = html.replace(/^#### (.+)$/gm, "<h6>$1</h6>");
        html = html.replace(/^### (.+)$/gm, "<h5>$1</h5>");
        html = html.replace(/^## (.+)$/gm, "<h4>$1</h4>");
        html = html.replace(/^# (.+)$/gm, "<h4>$1</h4>");

        // Process line by line for lists and paragraphs
        const lines = html.split("\n");
        let result = [];
        let inOl = false;
        let inUl = false;

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const olMatch = line.match(/^(\d+)\.\s+(.+)/);
            const ulMatch = line.match(/^[-*]\s+(.+)/);

            if (olMatch) {
                if (!inOl) {
                    if (inUl) { result.push("</ul>"); inUl = false; }
                    result.push("<ol>");
                    inOl = true;
                }
                result.push(`<li>${olMatch[2]}</li>`);
            } else if (ulMatch) {
                if (!inUl) {
                    if (inOl) { result.push("</ol>"); inOl = false; }
                    result.push("<ul>");
                    inUl = true;
                }
                result.push(`<li>${ulMatch[2]}</li>`);
            } else {
                if (inOl) { result.push("</ol>"); inOl = false; }
                if (inUl) { result.push("</ul>"); inUl = false; }

                // Empty line = paragraph break
                if (line.trim() === "") {
                    // Don't add extra <p> for blank lines
                    result.push("");
                } else if (
                    line.startsWith("<pre") || line.startsWith("<h") ||
                    line.startsWith("<ol") || line.startsWith("<ul") ||
                    line.startsWith("<li") || line.startsWith("</ol") ||
                    line.startsWith("</ul") || line.startsWith("</pre")
                ) {
                    // Already block-level, pass through
                    result.push(line);
                } else {
                    // Paragraph
                    result.push(`<p>${line}</p>`);
                }
            }
        }

        if (inOl) result.push("</ol>");
        if (inUl) result.push("</ul>");

        html = result.join("\n");

        // Clean up empty paragraphs
        html = html.replace(/<p>\s*<\/p>/g, "");

        // Single newlines within paragraphs become <br>
        html = html.replace(/<\/p>\s*<p>/g, "</p>\n<p>");

        return html;
    }
}

registry.category("actions").add("sgc_persona.sgc_chat_panel", SgcChatPanel);
