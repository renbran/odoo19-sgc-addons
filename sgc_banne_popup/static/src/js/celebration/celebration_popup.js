/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, useRef, onWillDestroy } from "@odoo/owl";
import { burstConfetti } from "./confetti";

const BUS_CHANNEL = "sgc_crm_celebration";
const AUTO_DISMISS_MS = 7000;

export class SgcCelebrationPopup extends Component {
    static template = "sgc_banne_popup.CelebrationPopup";
    static props = {};

    setup() {
        this.busService = useService("bus_service");
        this.canvasRef = useRef("confettiCanvas");
        this.state = useState({ visible: false, effect: "pop", title: "", lines: [] });
        this._stopConfetti = null;
        this._timeoutId = null;

        this.busService.subscribe(BUS_CHANNEL, (payload) => this._onCelebration(payload));
        this.busService.addChannel(BUS_CHANNEL);

        onWillDestroy(() => {
            if (this._stopConfetti) this._stopConfetti();
            if (this._timeoutId) clearTimeout(this._timeoutId);
        });
    }

    _onCelebration(payload) {
        if (this._timeoutId) clearTimeout(this._timeoutId);
        if (this._stopConfetti) this._stopConfetti();

        this.state.title = payload.title || "";
        this.state.lines = payload.lines || [];
        this.state.effect = payload.effect === "confetti" ? "confetti" : "pop";
        this.state.visible = true;

        if (this.state.effect === "confetti") {
            requestAnimationFrame(() => {
                if (this.canvasRef.el) {
                    this._stopConfetti = burstConfetti(this.canvasRef.el, 4000);
                }
            });
        }

        this._timeoutId = setTimeout(() => this.close(), AUTO_DISMISS_MS);
    }

    close() {
        this.state.visible = false;
        if (this._stopConfetti) {
            this._stopConfetti();
            this._stopConfetti = null;
        }
    }
}

registry.category("main_components").add("SgcCelebrationPopup", { Component: SgcCelebrationPopup });
