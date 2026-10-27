import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class AccountingUploadProgress extends Interaction {
    static selector = ".sgc-upload-form";
    static selectorHas = ".sgc-upload-progress";

    setup() {
        this.xhr = null;
        const wrapper = this.el.querySelector(".sgc-upload-progress");
        this.bar = wrapper.querySelector(".progress-bar");
        this.status = wrapper.querySelector(".sgc-upload-status");
        this.cancelBtn = wrapper.querySelector(".sgc-upload-cancel");
        this.submitBtn = this.el.querySelector('button[type="submit"]');
        this.dynamicContent = {
            _root: { "t-on-submit": (event) => this.onSubmit(event) },
            ".sgc-upload-cancel": { "t-on-click": () => this.onCancel() },
        };
    }

    destroy() {
        if (this.xhr) {
            this.xhr.abort();
            this.xhr = null;
        }
        super.destroy();
    }

    setStatus(text) {
        if (this.status) {
            this.status.textContent = text;
        }
    }

    resetBar() {
        this.bar.style.width = "0%";
        this.bar.setAttribute("aria-valuenow", "0");
    }

    lock(locked) {
        if (this.submitBtn) {
            this.submitBtn.disabled = locked;
        }
        if (this.cancelBtn) {
            this.cancelBtn.disabled = locked === "too-late";
        }
    }

    onCancel() {
        if (this.xhr) {
            this.xhr.abort();
        }
    }

    onSubmit(event) {
        event.preventDefault();
        if (!this.bar || !this.status || this.xhr) {
            if (!this.bar) {
                this.el.submit();
            }
            return;
        }
        const form = this.el;
        const bar = this.bar;
        this.lock(true);
        form.querySelector(".sgc-upload-progress").classList.remove("d-none");
        this.resetBar();
        this.setStatus("Uploading\u2026 0%");

        const xhr = new XMLHttpRequest();
        this.xhr = xhr;

        xhr.upload.addEventListener("progress", (e) => {
            if (e.lengthComputable) {
                const pct = Math.round((e.loaded / e.total) * 100);
                bar.style.width = pct + "%";
                bar.setAttribute("aria-valuenow", String(pct));
                this.setStatus("Uploading\u2026 " + pct + "%");
                if (pct >= 100) {
                    this.cancelBtn.disabled = true;
                }
            } else {
                this.setStatus("Uploading\u2026");
            }
        });
        xhr.upload.addEventListener("load", () => {
            this.setStatus("Processing on the server\u2026");
            if (this.cancelBtn) {
                this.cancelBtn.disabled = true;
            }
        });
        xhr.addEventListener("abort", () => {
            this.xhr = null;
            if (this.submitBtn) {
                this.submitBtn.disabled = false;
            }
            if (this.cancelBtn) {
                this.cancelBtn.disabled = false;
            }
            form.querySelector('input[type="file"]').value = "";
            form.querySelector(".sgc-upload-progress").classList.add("d-none");
            this.resetBar();
            this.setStatus("");
        });
        xhr.addEventListener("error", () => {
            this.xhr = null;
            this.lock(false);
            this.resetBar();
            this.setStatus("Upload failed. Please try again.");
        });
        xhr.addEventListener("load", () => {
            const url = xhr.responseURL;
            this.xhr = null;
            window.location.href = url || form.getAttribute("action");
        });

        xhr.open("POST", form.getAttribute("action"), true);
        xhr.send(new FormData(form));
    }
}

registry.category("public.interactions").add(
    "sgc_accounting_clients.accounting_upload_progress",
    AccountingUploadProgress,
);
