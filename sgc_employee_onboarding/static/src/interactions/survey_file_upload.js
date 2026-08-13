/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

export class SurveyFileUpload extends Interaction {
    static selector = ".o_survey-fill-form";

    setup() {
        super.setup();
        this._onFileChange = this._onFileChange.bind(this);
        this.el.addEventListener("change", this._onFileChange);
    }

    async _onFileChange(ev) {
        const inputEl = ev.target.closest(".o_sgc_survey_file_input");
        if (!inputEl) {
            return;
        }
        const file = inputEl.files && inputEl.files[0];
        const boxEl = inputEl.closest(".o_sgc_survey_file_box");
        if (!file || !boxEl) {
            return;
        }
        const statusEl = boxEl.querySelector(".o_sgc_survey_file_status");
        const hiddenEl = boxEl.querySelector(".o_sgc_survey_file_value");
        const csrfEl = this.el.querySelector('input[name="csrf_token"]');

        const formData = new FormData();
        formData.append("ufile", file);
        formData.append("question_id", inputEl.dataset.questionId || "");
        formData.append("answer_token", inputEl.dataset.answerToken || "");
        if (csrfEl) {
            formData.append("csrf_token", csrfEl.value);
        }

        if (statusEl) {
            statusEl.textContent = "Uploading…";
        }
        try {
            const resp = await fetch("/sgc_onboarding/survey/upload_file", {
                method: "POST",
                body: formData,
            });
            const data = await resp.json();
            if (data && data.attachment_id) {
                hiddenEl.value = data.attachment_id;
                if (statusEl) {
                    statusEl.textContent = "Uploaded: " + (data.name || "file");
                }
            } else {
                if (statusEl) {
                    statusEl.textContent =
                        "Upload failed: " + ((data && data.error) || "unknown error");
                }
            }
        } catch (err) {
            if (statusEl) {
                statusEl.textContent = "Upload failed. Please try again.";
            }
        }
    }

    destroy() {
        this.el.removeEventListener("change", this._onFileChange);
        super.destroy();
    }
}

registry.category("public.interactions").add("sgc.SurveyFileUpload", SurveyFileUpload);