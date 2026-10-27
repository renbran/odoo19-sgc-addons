import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class AccountingUploadProgress extends Interaction {
    static selector = ".sgc-upload-form";

    start() {
        const form = this.el;
        const wrapper = form.querySelector(".sgc-upload-progress");
        if (!wrapper) {
            return;
        }
        this.bar = wrapper.querySelector(".progress-bar");
        this.status = wrapper.querySelector(".sgc-upload-status");
        this.cancelBtn = wrapper.querySelector(".sgc-upload-cancel");
        this.submitBtn = form.querySelector('button[type="submit"]');
        if (this.cancelBtn) {
            this.cancelBtn.addEventListener("click", () => {
                if (this.xhr) {
                    this.xhr.abort();
                }
            });
        }
        form.addEventListener("submit", (event) => this.onSubmit(event));
    }

    setStatus(text) {
        if (this.status) {
            this.status.textContent = text;
        }
    }

    onSubmit(event) {
        event.preventDefault();
        if (!this.bar || !this.status || (this.submitBtn && this.submitBtn.disabled)) {
            if (!this.bar) {
                this.el.submit();
            }
            return;
        }
        const form = this.el;
        const bar = this.bar;
        const xhr = new XMLHttpRequest();
        this.xhr = xhr;

        const releaseUi = (clearFile) => {
            if (this.submitBtn) {
                this.submitBtn.disabled = false;
            }
            if (this.cancelBtn) {
                this.cancelBtn.disabled = false;
            }
            bar.style.width = "0%";
            bar.setAttribute("aria-valuenow", "0");
            if (clearFile) {
                form.querySelector('input[type="file"]').value = "";
            }
            form.querySelector(".sgc-upload-progress").classList.add("d-none");
            this.setStatus("");
        };

        xhr.upload.addEventListener("progress", (e) => {
            if (e.lengthComputable) {
                const pct = Math.round((e.loaded / e.total) * 100);
                bar.style.width = pct + "%";
                bar.setAttribute("aria-valuenow", String(pct));
                this.setStatus("Uploading\u2026 " + pct + "%");
                if (pct >= 100 && this.cancelBtn) {
                    this.cancelBtn.disabled = true;
                }
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
            releaseUi(true);
        });
        xhr.addEventListener("error", () => {
            this.xhr = null;
            releaseUi(false);
            form.querySelector(".sgc-upload-progress").classList.remove("d-none");
            this.setStatus("Upload failed. Please try again.");
        });
        xhr.addEventListener("load", () => {
            const url = xhr.responseURL;
            this.xhr = null;
            window.location.href = url || form.getAttribute("action");
        });

        if (this.submitBtn) {
            this.submitBtn.disabled = true;
        }
        form.querySelector(".sgc-upload-progress").classList.remove("d-none");
        this.setStatus("Uploading\u2026 0%");
        xhr.open("POST", form.getAttribute("action"), true);
        xhr.send(new FormData(form));
    }
}

registry.category("public.interactions").add(
    "sgc_accounting_clients.accounting_upload_progress",
    AccountingUploadProgress,
);
