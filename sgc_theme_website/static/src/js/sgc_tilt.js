/** @odoo-module */
// (c) SGC TECH — Finance. Systems. Technology. — https://sgctech.ai
// Tier-c subtle 3D tilt on showcase/feature media. Pointer-driven, GPU-cheap,
// and completely disabled under prefers-reduced-motion.

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class SgcTilt extends Interaction {
    static selector = ".s_sgc_tilt";

    dynamicContent = {
        _root: {
            "t-on-pointermove": this.onPointerMove,
            "t-on-pointerleave": this.onPointerLeave,
        },
    };

    setup() {
        this.reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        this.max = parseFloat(this.el.dataset.sgcTiltMax || "8"); // degrees
    }

    onPointerMove(ev) {
        if (this.reduced || ev.pointerType === "touch") {
            return;
        }
        const rect = this.el.getBoundingClientRect();
        const px = (ev.clientX - rect.left) / rect.width - 0.5;
        const py = (ev.clientY - rect.top) / rect.height - 0.5;
        const rx = (-py * this.max).toFixed(2);
        const ry = (px * this.max).toFixed(2);
        this.el.style.transform = `perspective(800px) rotateX(${rx}deg) rotateY(${ry}deg)`;
    }

    onPointerLeave() {
        this.el.style.transform = "";
    }
}

registry.category("public.interactions").add("sgc_theme_website.tilt", SgcTilt);
